---
version: 1.1
created_at: 2026-04-18
updated_at: 2026-07-27
last_updated: 补充强制覆盖策略章节，明确 OVERWRITE_DIR_LIST 与 OVERWRITE_FILE_LIST 的优先级与适用场景
abstract: 资源文件体系权威参考，定义 templates/ 模板目录结构、资源初始化机制（含强制覆盖策略）、懒加载目录以及数据迁移时的资源处理
---

## 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-04-18 | 初始版本 |
| 1.1 | 2026-07-27 | 补充强制覆盖策略章节（OVERWRITE_DIR_LIST + OVERWRITE_FILE_LIST + bootstrap.md 特殊跳过），修正"仅复制不覆盖"的描述 |

---

# 资源文件体系

## 概述

资源文件体系由三部分组成：

| 组件 | 说明 |
|------|------|
| `templates/` | 模板源目录，包含默认配置文件和用户模板 |
| `resource_initializer.py` | 启动时按需复制模板到数据目录 |
| `_DATA_SUBDIRS` | 迁移时复制的数据子目录列表 |

---

## `templates/` 目录结构

```
templates/
├── config/
│   └── config.json          # 端口配置（前后端共用）
├── diary/
│   └── template/
│       └── 默认模板.md        # 日记默认模板
├── agent/                    # Agent 相关模板
│   ├── README.md
│   ├── chat/
│   │   ├── agent.md
│   │   ├── bootstrap.md
│   │   └── memory.md
│   └── classify/
│       ├── agent.md
│       └── classify_preference.md
├── user/                     # 用户数据模板
│   ├── README.md
│   ├── user.md
│   ├── daily_data/
│   │   ├── behavior.md
│   │   └── recent_status.md
│   ├── narrative/
│   │   └── growth_story.md
│   └── psychological_model/
│       ├── contradictions/contradictions.md
│       ├── growth_insights.md
│       ├── ideal_self/{creed.md, values.md}
│       └── real_self/{cognition.md, cog_emo_interface.md, emotion.md}
└── ...                       # 其他模板文件
```

---

## 资源初始化机制

### `initialize_resources()` — 启动时按需复制

**代码位置**: `lifeprism/repository/resource_initializer.py`

**调用时机**: `lifespan` 阶段（FastAPI 应用启动时）

```python
def initialize_resources() -> None:
    # 打包环境：来自 PyInstaller 内嵌资源
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)
        templates_dir = bundle_dir / "templates"
    # 开发环境：来自项目根目录
    else:
        templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"

    # 记录初始化前 agent/chat 目录是否已存在（用于 bootstrap.md 特殊跳过）
    agent_chat_existed_before = (data_path / "agent/chat").exists()

    for source in templates_dir.rglob("*"):
        if not source.is_file():
            continue

        rel = source.relative_to(templates_dir)
        rel_posix = rel.as_posix()

        # config/ 目录映射到固定路径
        if rel.parts[0] == "config":
            target = config_base_path / rel
        # 其他目录映射到数据路径
        else:
            target = data_path / rel

        # 优先级 1：OVERWRITE_FILE_LIST 命中 → 强制覆盖
        if rel_posix in OVERWRITE_FILE_LIST:
            shutil.copy2(source, target)
            continue

        # 优先级 2：OVERWRITE_DIR_LIST 命中 → 强制覆盖
        if rel.parts[0] in OVERWRITE_DIR_LIST:
            shutil.copy2(source, target)
            continue

        # 优先级 3：bootstrap.md 特殊跳过
        if rel_posix == "agent/chat/bootstrap.md" and agent_chat_existed_before:
            continue

        # 优先级 4：仅复制不覆盖
        if target.exists():
            continue
        shutil.copy2(source, target)
```

### 路径映射规则

| 源路径 (`templates/`) | 目标路径 |
|----------------------|----------|
| `templates/config/...` | `{config_base_path}/config/...` |
| `templates/diary/...` | `{lifeprism_data_path}/diary/...` |
| `templates/agent/...` | `{lifeprism_data_path}/agent/...` |
| `templates/user/...` | `{lifeprism_data_path}/user/...` |
| `templates/...` (其他) | `{lifeprism_data_path}/...` |

### 强制覆盖策略

`initialize_resources()` 按以下优先级处理每个模板文件（高优先级先命中先处理）：

| 优先级 | 命中条件 | 行为 | 适用场景 |
|--------|---------|------|---------|
| 1 | `OVERWRITE_FILE_LIST` 精确路径命中 | 强制覆盖 | 混杂系统提示词与用户数据的目录（如 `agent/chat/` 下的 `soul.md`/`agent.md`/`tool.md`） |
| 2 | `OVERWRITE_DIR_LIST` 第一级子目录命中 | 强制覆盖 | 纯系统级、无用户数据的目录（如 `prompts/`） |
| 3 | `agent/chat/bootstrap.md` 且 `agent/chat` 目录已存在 | 跳过复制 | 用户完成引导删除 `bootstrap.md` 后不再复制，避免反复出现 |
| 4 | 其余文件 | 仅复制不覆盖 | 保护用户数据（`identity.md`、`classify_preference.md` 等） |

#### `OVERWRITE_DIR_LIST` — 目录白名单

```python
OVERWRITE_DIR_LIST = ["prompts"]
```

仅包含纯系统级、无用户数据的目录。整个目录下所有文件强制覆盖。

**历史背景**：原实现包含 `["prompts", "tool", "agent"]`，其中：
- `"tool"` 是无效配置（`templates/` 下无此第一级子目录）
- `"agent"` 会导致 `agent/chat/` 下所有文件被强制覆盖，误伤 `identity.md`（用户数据）和 `bootstrap.md`（引导文件，被删除后反复出现）

v1.1 修复后 `agent` 移出 `OVERWRITE_DIR_LIST`，改为通过 `OVERWRITE_FILE_LIST` 精确控制系统提示词的覆盖。

#### `OVERWRITE_FILE_LIST` — 文件白名单

```python
OVERWRITE_FILE_LIST = {
    "agent/README.md",
    "agent/chat/agent.md",
    "agent/chat/soul.md",
    "agent/chat/tool.md",
    "agent/classify/agent.md",
    "agent/skills/knowledge-learning/SKILL.md",
}
```

仅包含 `agent/` 下的系统级提示词文件，精确匹配相对 `templates/` 的 POSIX 路径。新增 `agent/` 下的系统提示词时需同步加入此白名单。

**未列入白名单的 `agent/` 文件遵循"仅复制不覆盖"原则**：
- `agent/chat/identity.md`：用户在引导流程中编辑，保存 AI 名称
- `agent/chat/bootstrap.md`：引导文件，由优先级 3 特殊处理
- `agent/classify/classify_preference.md`：用户分类偏好，用户主动写入
- `agent/chat/tool copy.md`：`tool.md` 的旧版备份（建议手动清理）

#### `bootstrap.md` 特殊跳过

`bootstrap.md` 是 Chat Agent 的首次引导文件，引导完成后由 Agent 调用 `delete_bootstrap` 工具删除。为避免反复出现，特殊处理逻辑如下：

- **首次启动**：`agent/chat` 目录不存在 → `agent_chat_existed_before = False` → 走优先级 4 复制
- **后续启动**：`agent/chat` 目录已存在 → `agent_chat_existed_before = True` → 跳过复制

此逻辑在循环外计算一次 `agent_chat_existed_before`，避免循环中目录被创建后误判。

### 关键特性

1. **分级覆盖策略**: 通过 `OVERWRITE_FILE_LIST` 与 `OVERWRITE_DIR_LIST` 精确控制系统提示词覆盖，保护用户数据
2. **bootstrap.md 反复出现防护**: 用户完成引导删除后不再复制
3. **按需创建目录**: `mkdir(parents=True, exist_ok=True)` 自动创建父目录
4. **打包环境隔离**: `sys._MEIPASS` 是 PyInstaller 的只读内嵌文件系统

---

## 开发环境 vs 打包环境

| 特性 | 开发环境 | 打包环境 |
|------|----------|----------|
| 模板来源 | `LifeWatch-AI/templates/` | `pyinstaller-dist/.../_internal/templates/` |
| `templates/` 是否源码 | 是（可编辑） | 否（PyInstaller 打包时复制） |
| `config_base_path` | `localData/` | `%LOCALAPPDATA%/LifePrism/lifeprismData/` |
| `lifeprism_data_path` | `localData/` | `%LOCALAPPDATA%/LifePrism/lifeprismData/` |

**注意**: 打包后的 `templates/` 位于 PyInstaller 的 `_internal/templates/`，由 `lifeprism.spec` 中的 `datas=[('templates', 'templates')]` 指定。

---

## 懒加载目录

以下目录/文件不是由 `initialize_resources()` 创建，而是在首次使用时自动创建：

| 目录/文件 | 创建时机 | 代码位置 |
|----------|----------|----------|
| `dataset/*.db` | 首次 import `lifeprism.repository` | `lifeprism/repository/__init__.py:11-17` |
| `debug_logs/` | 首次调用 `setup_file_logging()` | `lifeprism/utils/logger.py:47` |
| `config/config.yaml` | 首次调用 `_save_config()` | `lifeprism/config/settings_manager.py:198` |

懒加载创建的目录可能不存在于初始状态，这对正常功能无影响。

---

## 数据迁移时的资源处理

**API**: `POST /settings/migrate-data-path`

### 迁移流程

```
1. 开发模式检查（禁用迁移）
2. 计算新路径：{用户选择目录}/lifeprismData
3. 验证路径（不与当前路径相同、不在安装目录内）
4. 关闭数据库连接池
5. 复制除黑名单外的所有数据子目录
6. 更新 config.yaml 中的 lifeprism_data_path
7. 重启生效
```

### `_EXCLUDED_SUBDIRS` — 迁移时排除的子目录黑名单

```python
_EXCLUDED_SUBDIRS = [
    "config",  # 配置文件固定在默认路径，不参与迁移
]
```

迁移时会自动复制 `current_path` 下除 `config/` 外的所有子目录，新增子目录无需手动同步列表。

### 迁移与初始化的关系

| 阶段 | 行为 |
|------|------|
| **首次启动** | `initialize_resources()` 从 `templates/` 复制默认文件到数据目录 |
| **数据迁移** | `migrate_data_path()` 复制除 `config/` 外的所有子目录到新路径 |
| **非迁移场景** | `templates/` 中的文件在首次启动后不会被再次使用 |

---

## 已知问题

### 打包环境 `templates/` 可能与源码不同步

PyInstaller 打包时复制 `templates/` 到 `pyinstaller-dist/`，但后续对源码 `templates/` 的修改**不会自动同步**到打包目录。

**现象**: 打包后应用缺少源码新增的模板文件

**解决**: 重新打包前先同步 `templates/` 到打包目录，或重新执行 PyInstaller 打包

---

## 相关文件索引

| 文件 | 说明 |
|------|------|
| `lifeprism/repository/resource_initializer.py` | 资源初始化实现 |
| `lifeprism/server/services/setting_service.py` | 数据迁移实现（含 `_EXCLUDED_SUBDIRS` 黑名单） |
| `lifeprism/repository/__init__.py` | 数据库懒加载创建 |
| `lifeprism/utils/logger.py` | 日志目录懒加载创建 |
| `lifeprism/config/settings_manager.py` | 配置保存、`_save_config` |
| `lifeprism.spec` | PyInstaller 打包配置（`datas=[('templates', 'templates')]`） |
