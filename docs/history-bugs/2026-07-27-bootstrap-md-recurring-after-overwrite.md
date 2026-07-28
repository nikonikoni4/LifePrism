# Bootstrap 文件被错误复制（多次复发）

## Bug简述

`bootstrap.md` 是 Agent 首次引导流程文件，用户完成引导后由 Agent 调用 `delete_bootstrap` 工具删除。但每次启动 `initialize_resources()` 时，该文件被反复复制回 `data_path/agent/chat/bootstrap.md`，导致引导流程反复出现，干扰用户体验。此 bug 在项目历史中**多次复发**，每次根因不同，长期是隐患。

## 复用场景

- 任何"用户完成后删除、不应再生成"的引导类文件保护场景
- "整目录强制覆盖"与"单文件特殊跳过"的优先级设计问题
- 防御性编程：当某条保护逻辑可被更高优先级的覆盖逻辑绕过时，必须将保护逻辑提前到所有覆盖逻辑之前
- 配置类隐患：列表型配置（如 `OVERWRITE_DIR_LIST`）误包含某项目后绕过单文件保护的同类型 bug

## 代码位置

- **核心文件**：`lifeprism/repository/resource_initializer.py`
- **修复点（优先级 0）**：`lifeprism/repository/resource_initializer.py:97-102`（bootstrap.md 特殊跳过逻辑，已提前到优先级 1 之前）
- **覆盖逻辑**：
  - 优先级 1：`OVERWRITE_FILE_LIST` 精确路径白名单 → `lifeprism/repository/resource_initializer.py:104-109`
  - 优先级 2：`OVERWRITE_DIR_LIST` 第一级子目录白名单 → `lifeprism/repository/resource_initializer.py:111-116`
  - 优先级 3：仅复制不覆盖 → `lifeprism/repository/resource_initializer.py:118-123`
- **关联调用**：
  - 启动入口：`lifeprism/server/main.py:408`（lifespan 阶段调用 `initialize_resources()`）
  - 引导删除工具：`lifeprism/llm/agent/tools/delete_bootstrap.py:30-37`

## 发生原因

此 bug 多次复发，每次根因不同。共同特征是：**bootstrap.md 的保护逻辑被覆盖逻辑绕过**。

### 复发历史

#### 第 1 次（早期版本，已修复）

- **根因**：`initialize_resources()` 没有 bootstrap.md 的特殊保护逻辑，遵循"已存在则跳过"原则
- **现象**：首次复制后，用户删除 bootstrap.md，下次启动因目标不存在又复制回来
- **修复**：增加 bootstrap.md 特殊跳过逻辑（agent/chat 已存在时跳过）

#### 第 2 次（2026-07-03 引入，2026-07-27 修复前复发）

- **引入 commit**：`7f4f3b62a36ef832cc5faf20738ce3cc71b9495c`（2026-07-03，message：`refactor:资源初始化的强制覆盖列表添加tool.m和agent.md`，作者 nikonikoni4）
- **根因**：commit 将 `OVERWRITE_DIR_LIST` 从 `["prompts"]` 改为 `["prompts", "tool", "agent"]`，把整个 `agent` 目录放入强制覆盖列表
- **机制**：
  1. `OVERWRITE_DIR_LIST` 命中 `agent` → 走优先级 2 强制覆盖分支 → `continue`
  2. 永远不会走到优先级 3 的 bootstrap.md 跳过逻辑
  3. 结果：bootstrap.md 每次启动都被强制覆盖回 data_path
- **修复**（2026-07-27）：
  1. `OVERWRITE_DIR_LIST` 移除 `"agent"`，恢复为 `["prompts"]`
  2. 新增 `OVERWRITE_FILE_LIST` 精确白名单，仅覆盖系统提示词（`agent.md`/`soul.md`/`tool.md`），不含 `bootstrap.md`/`identity.md`
  3. bootstrap.md 跳过逻辑通过 `agent_chat_existed_before` 标志位实现"仅首次复制"

#### 第 3 次（隐患，2026-07-27 本次修复）

- **根因**：第 2 次修复后，bootstrap.md 跳过逻辑位于**优先级 3**，仍可被优先级 2 的整目录覆盖绕过
- **隐患场景**：若未来有人再次把 `"agent"` 加入 `OVERWRITE_DIR_LIST`（无论是失误还是误以为需要更新 agent 目录），优先级 2 命中后会直接 `continue`，跳过优先级 3 的 bootstrap.md 保护，bug 立即复发
- **本质**：保护逻辑放在覆盖逻辑之后，依赖"覆盖列表不会误包含 agent"这一脆弱前提

## 最佳方案

**将 bootstrap.md 跳过逻辑提前到所有覆盖逻辑之前（优先级 0，最高优先级）**，使其成为不可绕过的防御性保护。

### 修复前（优先级 3，可被绕过）

```python
# 优先级 1：精确文件路径白名单命中 → 强制覆盖
if rel_posix in OVERWRITE_FILE_LIST:
    shutil.copy2(source, target)
    continue

# 优先级 2：第一级子目录白名单命中 → 强制覆盖
if rel.parts[0] in OVERWRITE_DIR_LIST:  # ★ 若 "agent" 误入此列表，bootstrap.md 被覆盖
    shutil.copy2(source, target)
    continue

# 优先级 3：bootstrap.md 特殊跳过（位置太晚，被优先级 2 绕过）
if rel_posix == "agent/chat/bootstrap.md" and agent_chat_existed_before:
    continue
```

### 修复后（优先级 0，不可绕过）

```python
# 优先级 0（最高，防御性保护）：bootstrap.md 特殊跳过
# 必须早于所有覆盖逻辑，防止 OVERWRITE_DIR_LIST 误包含 "agent" 时绕过保护
if rel_posix == "agent/chat/bootstrap.md" and agent_chat_existed_before:
    logger.debug("agent/chat 目录已存在，跳过复制 bootstrap.md: %s", target)
    continue

# 优先级 1：精确文件路径白名单命中 → 强制覆盖
if rel_posix in OVERWRITE_FILE_LIST:
    ...

# 优先级 2：第一级子目录白名单命中 → 强制覆盖
if rel.parts[0] in OVERWRITE_DIR_LIST:
    ...
```

### 设计原则

**防御性编程**：保护逻辑（"不应被覆盖的文件"）必须放在所有覆盖逻辑之前，不能依赖"覆盖列表配置正确"这一脆弱前提。配置可被人为修改，但保护逻辑应不可绕过。

具体地：
- `OVERWRITE_FILE_LIST` 与 `OVERWRITE_DIR_LIST` 是"显式覆盖白名单"，可被维护者修改
- bootstrap.md 跳过是"硬性保护"，不应被任何白名单绕过
- 因此硬性保护必须优先级最高，先于所有白名单判断

## 验证

### 回归测试

`test/core/unit/repository/test_resource_initializer.py` 包含 10 个测试场景：

- **场景 4** `test_bootstrap_md_is_not_overwritten`：常规场景，agent/chat 已存在时 bootstrap.md 不被复制
- **场景 7** `test_bootstrap_md_is_created_on_first_init`：首次初始化时 bootstrap.md 正常复制
- **场景 10** `test_bootstrap_md_not_overwritten_even_if_agent_in_dir_list`（新增，防御性测试）：**模拟 `"agent"` 误入 `OVERWRITE_DIR_LIST` 的历史 bug 场景**，验证优先级 0 的 bootstrap.md 保护仍能拦截

### 测试结果

```
test/core/unit/repository/test_resource_initializer.py::TestInitializeResources::test_prompts_file_is_overwritten PASSED
test/core/unit/repository/test_resource_initializer.py::TestInitializeResources::test_non_overwrite_file_is_not_overwritten PASSED
test/core/unit/repository/test_resource_initializer.py::TestInitializeResources::test_agent_system_prompt_is_overwritten PASSED
test/core/unit/repository/test_resource_initializer.py::TestInitializeResources::test_bootstrap_md_is_not_overwritten PASSED
test/core/unit/repository/test_resource_initializer.py::TestInitializeResources::test_identity_md_is_not_overwritten PASSED
test/core/unit/repository/test_resource_initializer.py::TestInitializeResources::test_classify_preference_md_is_not_overwritten PASSED
test/core/unit/repository/test_resource_initializer.py::TestInitializeResources::test_bootstrap_md_is_created_on_first_init PASSED
test/core/unit/repository/test_resource_initializer.py::TestInitializeResources::test_non_existent_user_file_is_copied PASSED
test/core/unit/repository/test_resource_initializer.py::TestInitializeResources::test_overwrite_file_list_priority_over_dir_list PASSED
test/core/unit/repository/test_resource_initializer.py::TestInitializeResources::test_bootstrap_md_not_overwritten_even_if_agent_in_dir_list PASSED

============================= 10 passed in 0.84s ==============================
```

## 相关文档

- 权威参考：`docs/authority/resource-init.md` v1.1（资源初始化权威参考，需同步更新至 v1.2 描述本次优先级调整）
- Flow 文档：`docs/flows/2026-07-06-repository-initialization-flow.md`（需同步更新优先级顺序描述）
- 引入复发 commit：`7f4f3b62a36ef832cc5faf20738ce3cc71b9495c`（2026-07-03）
- 引导删除工具：`lifeprism/llm/agent/tools/delete_bootstrap.py`

## 沉淀教训

1. **保护逻辑优先级必须最高**：任何"不应被覆盖/删除/修改"的硬性保护逻辑，必须放在所有可能绕过它的覆盖逻辑之前，不能依赖配置正确性
2. **列表型配置是隐患源头**：`OVERWRITE_DIR_LIST` 这类"整目录覆盖"配置一旦误包含某项目，会绕过所有后续单文件保护。设计时应优先使用精确路径白名单（`OVERWRITE_FILE_LIST`）而非整目录白名单
3. **复发 bug 需防御性测试**：对于多次复发的 bug，仅修复当前根因不够，必须添加"模拟历史 bug 场景"的防御性测试，防止未来同类配置失误导致复发
4. **优先级顺序应反映安全性**：代码注释中的优先级顺序（0/1/2/3）应明确反映"保护 > 覆盖"的安全性原则，而非简单的"先精确后宽泛"
