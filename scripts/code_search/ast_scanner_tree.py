"""Tree-sitter 多语言 AST 函数引用扫描器"""

import json
from collections import defaultdict
from pathlib import Path

import tree_sitter_javascript as tsjs
import tree_sitter_python as tspython
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

# 语言配置
LANGUAGES = {
    ".py": {"lang": Language(tspython.language()), "name": "python"},
    ".js": {"lang": Language(tsjs.language()), "name": "javascript"},
    ".jsx": {"lang": Language(tsjs.language()), "name": "javascript"},
    ".ts": {"lang": Language(tsts.language_typescript()), "name": "typescript"},
    ".tsx": {"lang": Language(tsts.language_typescript()), "name": "typescript"},
}


class TreeSitterScanner:
    def __init__(self, root_dir, exclude_dirs=None):
        self.root = Path(root_dir)
        self.exclude_dirs = exclude_dirs or {
            ".venv",
            "__pycache__",
            ".claude",
            "node_modules",
            ".git",
            "dist",
            "build",
        }
        self.definitions = {}
        self.calls = []
        self.imports = defaultdict(dict)

    def scan(self):
        for ext, config in LANGUAGES.items():
            for file in self.root.rglob(f"*{ext}"):
                if any(excluded in file.parts for excluded in self.exclude_dirs):
                    continue
                self._scan_file(file, config)
        return self._build_output()

    def _to_module(self, filepath, ext):
        rel = filepath.relative_to(self.root)
        parts = list(rel.parts)
        if parts[-1] == f"__init__{ext}":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1].replace(ext, "")
        return ".".join(parts)

    def _scan_file(self, filepath, config):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            # 统一换行符
            raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            source = raw.decode("utf-8")
            parser = Parser(config["lang"])
            tree = parser.parse(raw)
            # 保存 raw 用于字节切片
            self._raw = raw
        except Exception:
            return

        ext = filepath.suffix
        module = self._to_module(filepath, ext)
        lang_name = config["name"]

        if lang_name == "python":
            self._scan_python(tree.root_node, source, module)
        elif lang_name in ("javascript", "typescript"):
            self._scan_js_ts(tree.root_node, source, module, lang_name)

    def _get_text(self, node):
        """从字节切片获取节点文本"""
        return self._raw[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    # ==================== Python 扫描 ====================

    def _scan_python(self, root, source, module):
        for child in root.children:
            if child.type == "function_definition":
                self._collect_python_func(child, source, module, None)
            elif child.type == "class_definition":
                self._collect_python_class(child, source, module)
            elif child.type == "import_statement":
                self._collect_python_import(child, source, module)
            elif child.type == "import_from_statement":
                self._collect_python_import_from(child, source, module)

        # 收集调用
        self._collect_python_calls(root, source, module)

    def _collect_python_func(self, node, source, module, class_name):
        # tree-sitter-python: 函数名是第一个 identifier 子节点
        for child in node.children:
            if child.type == "identifier":
                func_name = self._get_text(child)
                if class_name:
                    func_name = f"{class_name}.{func_name}"
                self.definitions[(module, func_name)] = node.start_point[0] + 1
                break

    def _collect_python_class(self, node, source, module):
        # tree-sitter-python: 类名是第一个 identifier 子节点
        class_name = None
        for child in node.children:
            if child.type == "identifier":
                class_name = self._get_text(child)
                self.definitions[(module, class_name)] = node.start_point[0] + 1
                break

        if not class_name:
            return

        # 找到 class body (block 节点)
        for child in node.children:
            if child.type == "block":
                for item in child.children:
                    if item.type == "function_definition":
                        self._collect_python_func(item, source, module, class_name)

    def _collect_python_import(self, node, source, module):
        # import X 或 import X as Y
        names = []
        for child in node.children:
            if child.type == "dotted_name":
                names.append(self._get_text(child))
            elif child.type == "aliased_import":
                # import X as Y: 两个 identifier 子节点
                ids = [
                    c for c in child.children if c.type == "dotted_name" or c.type == "identifier"
                ]
                if len(ids) >= 2:
                    name = self._get_text(ids[0])
                    alias = self._get_text(ids[1])
                    self.imports[module][alias] = name
        for name in names:
            self.imports[module][name] = name

    def _collect_python_import_from(self, node, source, module):
        # from X import Y, Z
        module_name = ""
        import_names = []

        for child in node.children:
            if child.type in ("dotted_name", "relative_import"):
                module_name = self._get_text(child)
            elif child.type == "import_list":
                for item in child.children:
                    if item.type == "aliased_import":
                        # Y as Z
                        ids = [c for c in item.children if c.type in ("dotted_name", "identifier")]
                        if len(ids) >= 2:
                            name = self._get_text(ids[0])
                            alias = self._get_text(ids[1])
                            self.imports[module][alias] = f"{module_name}.{name}"
                    elif item.type in ("dotted_name", "identifier"):
                        name = self._get_text(item)
                        self.imports[module][name] = f"{module_name}.{name}"

    def _collect_python_calls(self, node, source, module):
        if node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                callee = self._resolve_python_callee(func_node, source, module)
                if callee:
                    caller = self._find_enclosing_func(node, source, module)
                    self.calls.append(
                        (module, caller, callee[0], callee[1], node.start_point[0] + 1)
                    )

        for child in node.children:
            self._collect_python_calls(child, source, module)

    def _resolve_python_callee(self, node, source, module):
        if node.type == "identifier":
            name = self._get_text(node)
            if name in self.imports[module]:
                full = self.imports[module][name]
                parts = full.rsplit(".", 1)
                return (parts[0], parts[1]) if len(parts) == 2 else (module, name)
            return (module, name)
        elif node.type == "attribute":
            # obj.attr 形式
            # tree-sitter-python: attribute 节点有 object 和 attribute 子节点
            children = list(node.children)
            if len(children) >= 2:
                # object 可能是 identifier 或嵌套 attribute
                obj_node = children[0]
                attr_node = children[-1]  # 最后一个是属性名
                if attr_node.type == "identifier":
                    attr_name = self._get_text(attr_node)
                    obj_name = self._get_text(obj_node)
                    if obj_node.type == "identifier" and obj_name in self.imports[module]:
                        return (self.imports[module][obj_name], attr_name)
        return None

    # ==================== JS/TS 扫描 ====================

    def _scan_js_ts(self, root, source, module, lang_name):
        for child in root.children:
            if child.type in (
                "function_declaration",
                "lexical_declaration",
                "variable_declaration",
            ):
                self._collect_js_func(child, source, module)
            elif child.type == "class_declaration":
                self._collect_js_class(child, source, module)
            elif child.type in ("import_statement", "import_declaration"):
                self._collect_js_import(child, source, module)
            elif child.type == "export_statement":
                self._collect_js_export(child, source, module)

        self._collect_js_calls(root, source, module)

    def _collect_js_func(self, node, source, module):
        for child in node.children:
            if child.type == "function":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    self.definitions[(module, name)] = node.start_point[0] + 1
            elif child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if name_node and value_node and value_node.type in ("arrow_function", "function"):
                    name = self._get_text(name_node)
                    self.definitions[(module, name)] = node.start_point[0] + 1

    def _collect_js_class(self, node, source, module):
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        class_name = self._get_text(name_node)
        self.definitions[(module, class_name)] = node.start_point[0] + 1

        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if child.type == "method_definition":
                    method_name_node = child.child_by_field_name("name")
                    if method_name_node:
                        method_name = self._get_text(method_name_node)
                        self.definitions[(module, f"{class_name}.{method_name}")] = (
                            child.start_point[0] + 1
                        )

    def _collect_js_import(self, node, source, module):
        source_node = node.child_by_field_name("source")
        if source_node:
            import_path = self._get_text(source_node).strip("'\"")
            for child in node.children:
                if child.type == "import_clause":
                    self._parse_import_clause(child, source, module, import_path)

    def _parse_import_clause(self, node, source, module, import_path):
        for child in node.children:
            if child.type == "identifier":
                name = self._get_text(child)
                self.imports[module][name] = import_path
            elif child.type == "named_imports":
                for item in child.children:
                    if item.type == "import_specifier":
                        name_node = item.child_by_field_name("name")
                        alias_node = item.child_by_field_name("alias")
                        if name_node:
                            name = self._get_text(name_node)
                            alias = self._get_text(alias_node) if alias_node else name
                            self.imports[module][alias] = f"{import_path}.{name}"

    def _collect_js_export(self, node, source, module):
        for child in node.children:
            if child.type in ("function_declaration", "lexical_declaration", "class_declaration"):
                self._collect_js_func(
                    child, source, module
                ) if child.type != "class_declaration" else self._collect_js_class(
                    child, source, module
                )

    def _collect_js_calls(self, node, source, module):
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node:
                callee = self._resolve_js_callee(func_node, source, module)
                if callee:
                    caller = self._find_enclosing_func_js(node, source, module)
                    self.calls.append(
                        (module, caller, callee[0], callee[1], node.start_point[0] + 1)
                    )

        for child in node.children:
            self._collect_js_calls(child, source, module)

    def _resolve_js_callee(self, node, source, module):
        if node.type == "identifier":
            name = self._get_text(node)
            if name in self.imports[module]:
                full = self.imports[module][name]
                return (full, name)
            return (module, name)
        elif node.type == "member_expression":
            obj_node = node.child_by_field_name("object")
            prop_node = node.child_by_field_name("property")
            if obj_node and prop_node:
                obj_name = self._get_text(obj_node)
                prop_name = self._get_text(prop_node)
                if obj_name in self.imports[module]:
                    return (self.imports[module][obj_name], prop_name)
        return None

    def _find_enclosing_func(self, node, source, module, lang="python"):
        parent = node.parent
        while parent:
            if lang == "python" and parent.type == "function_definition":
                name_node = parent.child_by_field_name("name")
                if name_node:
                    return self._get_text(name_node)
            elif lang in ("js", "ts"):
                if parent.type in ("function", "function_declaration"):
                    name_node = parent.child_by_field_name("name")
                    if name_node:
                        return self._get_text(name_node)
                elif parent.type == "method_definition":
                    name_node = parent.child_by_field_name("name")
                    if name_node:
                        return self._get_text(name_node)
            parent = parent.parent
        return "<module>"

    def _find_enclosing_func_js(self, node, source, module):
        return self._find_enclosing_func(node, source, module, "js")

    # ==================== 输出构建 ====================

    def _build_output(self):
        defs = {}
        for (mod, func), line in self.definitions.items():
            key = f"{mod}.{func}"
            defs[key] = {"line": line, "module": mod, "name": func}

        called_by = defaultdict(list)
        calls_to = defaultdict(list)

        for caller_mod, caller_func, callee_mod, callee_func, line in self.calls:
            caller_key = f"{caller_mod}.{caller_func}"
            callee_key = f"{callee_mod}.{callee_func}"
            called_by[callee_key].append({"from": caller_key, "line": line})
            calls_to[caller_key].append({"to": callee_key, "line": line})

        return {
            "total_files": len(set(m for m, _ in self.definitions.keys())),
            "total_definitions": len(defs),
            "total_calls": sum(len(v) for v in calls_to.values()),
            "definitions": defs,
            "called_by": {k: v for k, v in called_by.items()},
            "calls_to": {k: v for k, v in calls_to.items()},
        }


def main():
    project_root = Path(__file__).parent.parent.parent
    scan_dirs = [
        project_root / "lifeprism",
        project_root / "frontend" / "src",
    ]

    # 合并扫描结果
    all_definitions = {}
    all_calls_raw = []  # 原始元组格式: (caller_mod, caller_func, callee_mod, callee_func, line)

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            print(f"跳过不存在的目录: {scan_dir}")
            continue

        scanner = TreeSitterScanner(scan_dir)
        result = scanner.scan()

        # 合并定义
        all_definitions.update(result["definitions"])

        # 从 called_by 反向构建原始调用关系
        for callee_key, callers in result["called_by"].items():
            for call in callers:
                caller_key = call["from"]
                line = call["line"]
                # 拆分 key: "module.func" -> (module, func)
                caller_parts = caller_key.rsplit(".", 1)
                callee_parts = callee_key.rsplit(".", 1)
                if len(caller_parts) == 2 and len(callee_parts) == 2:
                    all_calls_raw.append(
                        (caller_parts[0], caller_parts[1], callee_parts[0], callee_parts[1], line)
                    )

        label = "backend" if "lifeprism" in str(scan_dir) else "frontend"
        print(f"\n[{label}] 扫描完成:")
        print(f"  模块数: {result['total_files']}")
        print(f"  定义数: {result['total_definitions']}")
        print(f"  调用关系数: {result['total_calls']}")

    # 构建合并输出
    called_by = defaultdict(list)
    calls_to = defaultdict(list)
    for caller_mod, caller_func, callee_mod, callee_func, line in all_calls_raw:
        caller_key = f"{caller_mod}.{caller_func}"
        callee_key = f"{callee_mod}.{callee_func}"
        called_by[callee_key].append({"from": caller_key, "line": line})
        calls_to[caller_key].append({"to": callee_key, "line": line})

    # 计算唯一模块数
    unique_modules = set()
    for key in all_definitions.keys():
        module = all_definitions[key]["module"]
        unique_modules.add(module)

    merged_result = {
        "total_files": len(unique_modules),
        "total_definitions": len(all_definitions),
        "total_calls": len(all_calls_raw),
        "definitions": all_definitions,
        "called_by": {k: v for k, v in called_by.items()},
        "calls_to": {k: v for k, v in calls_to.items()},
    }

    output_path = Path(__file__).parent / "ast_scan_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged_result, f, indent=2, ensure_ascii=False)

    print(f"\n总计:")
    print(f"  模块数: {merged_result['total_files']}")
    print(f"  定义数: {merged_result['total_definitions']}")
    print(f"  调用关系数: {merged_result['total_calls']}")
    print(f"\n结果已保存到: {output_path}")

    # 打印被调用最多的
    print("\n=== 被调用最多的函数 (Top 10) ===")
    top = sorted(merged_result["called_by"].items(), key=lambda x: len(x[1]), reverse=True)[:10]
    for func, callers in top:
        print(f"  {func}  (被调用 {len(callers)} 次)")


if __name__ == "__main__":
    main()
