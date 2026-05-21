# 2026-05-21 update_memory 测试数据路径错误导致测试失效

## Bug 信息

- **发现日期**: 2026-05-21
- **严重程度**: 中等（影响测试效率，但不影响生产环境）
- **影响范围**: `test/llm_prompt_test/test_update_memory.py` 中的记忆更新提示词测试
- **状态**: 已修复
- **相关文件**: 
  - `test/llm_prompt_test/test_update_memory.py` (第 163-193 行)
  - `test/llm_prompt_test/dataset/update_memory/behavior.md`（正确数据源）
  - `test/llm_prompt_test/dataset/behavior_raw_data/*.md`（错误数据源）

## 问题描述

在编写 `update_memory` 提示词测试时，AI 错误理解了数据输入路径，导致测试代码读取了**错误的数据源**。

### 错误实现

```python
def data_input(self, input_files: list[str] | None = None) -> list[dict[str, Any]]:
    # 错误：从 behavior_raw_data 目录获取原始文件
    behavior_files = self._get_behavior_files(self.start_date, self.end_date)
    behavior_content = self._build_behavior_content(behavior_files)
    ...
```

代码读取的是 `behavior_raw_data/2026-05-13.md` 等**原始行为数据文件**，而不是包含完整总结的 `update_memory/behavior.md`。

### 正确数据源对比

| 错误数据源 (`behavior_raw_data/*.md`) | 正确数据源 (`update_memory/behavior.md`) |
|-------------------------------------|----------------------------------------|
| `## 电脑使用统计` | `### 行为总结` |
| `## 用户自定义行为备注` | `### 心情总结` |
| `## AI分析行为备注` | `### 聊天总结` |
| `## 用户待办事项` | `### 日记总结` |

## 症状表现

1. **数据不完整**：测试输入缺少 `心情总结`、`聊天总结`、`日记总结` 章节
2. **测试结果失真**：LLM 收到的输入与实际生产环境不符
3. **时间浪费**：后续多次测试基于错误数据，无法验证提示词真实效果
4. **难以察觉**：测试能正常运行，不会报错，但结果不可靠

## 根本原因分析

### 1. AI 对数据流理解错误

AI 没有理解 `build_behavior_md.py` 脚本的作用：
- 该脚本从多个测试结果中组装生成 `update_memory/behavior.md`
- 生成的文件包含完整的四类总结（行为、心情、聊天、日记）
- 测试应该读取这个生成后的文件，而非原始数据

### 2. 目录结构混淆

```
dataset/
├── behavior_raw_data/      # 原始行为数据（不含总结）
│   ├── 2026-05-13.md
│   ├── 2026-05-14.md
│   └── ...
├── update_memory/
│   └── behavior.md         # 由脚本生成的完整数据（含总结）
└── ...
```

AI 错误地认为应该从 `behavior_raw_data` 读取，而实际上应该从 `update_memory/behavior.md` 读取。

## 修复方案

修改 `data_input` 方法，直接读取 `update_memory/behavior.md` 并按日期筛选：

```python
def _filter_behavior_by_date(self, content: str, start_date: str, end_date: str) -> str:
    """按日期范围筛选 behavior.md 内容"""
    import re
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    date_pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})', re.MULTILINE)
    matches = list(date_pattern.finditer(content))
    
    filtered_parts = []
    for i, match in enumerate(matches):
        date_str = match.group(1)
        date = datetime.strptime(date_str, "%Y-%m-%d")
        if start <= date <= end:
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            filtered_parts.append(content[start_pos:end_pos].rstrip())
    
    return "\n\n".join(filtered_parts)

def data_input(self, input_files: list[str] | None = None) -> list[dict[str, Any]]:
    # 正确：读取预生成的 behavior.md
    behavior_path = self.input_path / "update_memory" / "behavior.md"
    full_content = read_md(behavior_path)
    
    # 按日期范围筛选内容
    behavior_content = self._filter_behavior_by_date(full_content, self.start_date, self.end_date)
    ...
```

## 教训总结

1. **理解数据流**：在修改测试代码前，必须先理解完整的数据生成流程
2. **验证数据内容**：测试前应验证输入数据是否包含预期的所有字段
3. **区分原始与生成数据**：明确区分原始数据文件和脚本生成的文件
4. **检查数据完整性**：不要只测试能否运行，要验证数据内容是否正确

## 后续改进

1. **添加数据验证**：在 `data_input` 中添加断言，检查输入是否包含必要字段
2. **文档说明**：在测试文件顶部注释说明正确的数据源路径
3. **目录说明**：在 `dataset/` 目录添加 README 说明各子目录用途
