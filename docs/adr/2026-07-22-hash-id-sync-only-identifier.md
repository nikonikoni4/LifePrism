---
version: 1.0
created_at: 2026-07-22
updated_at: 2026-07-22
last_updated: 2026-07-22
abstract: 6 张 AUTOINCREMENT 表新增 hash_id 字段作为同步专用标识，_PRIMARY_KEY 保持为自增 id 不变，调用方无感知
status: decided
---

# hash_id 定位为同步专用标识（非主键）

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

删除同步需要跨端稳定标识，但 6 张 AUTOINCREMENT 表的自增 id 在两端不同。需要为这些表引入跨端稳定标识，但又不能破坏现有本地 CRUD 链路。

### 讨论范围

- 6 张 AUTOINCREMENT 表（`timeline_custom_block`、`time_paradoxes`、`mood_impacts`、`habit_chains`、`habit_chain_nodes`、`user_app_behavior_log`）
- `_PRIMARY_KEY` 字段定位
- `_generic_insert` 兜底生成逻辑
- sync_repository 的 LWW 查找/删除同步路径

### 非讨论范围

- TEXT 主键表（已具备跨端稳定标识，无需改造）
- Provider 子类的 update/delete/get_by_id 方法签名
- API/Service/前端层的参数类型

### 模糊信息的明确定义

- "同步专用标识"：hash_id 字段仅参与 sync_repository 的 LWW 去重查找与 PRD 3 的删除同步路径，不参与本地 CRUD 的 WHERE 条件
- "_PRIMARY_KEY"：LWBaseDataProvider 子类的类属性，决定 update/delete/get_by_id 的 WHERE 条件字段

### 问题深度

涉及架构原则——"本地 CRUD 路径"与"同步路径"的字段定位分离。这关系到未来 PRD 2/3 的代码适配范围，以及"未来是否改 _PRIMARY_KEY"的演进路径。

## 现状

- 6 张 AUTOINCREMENT 表的自增 id 在两端不同
- 5 张表有 Provider（`timeline_custom_block`、`habit_chains`、`habit_chain_nodes`、`mood_impacts`、`user_app_behavior_log`），全部使用 `_PRIMARY_KEY = "id"` 做 update/delete/get_by_id
- 调用方（API 路由参数、Service 层、LLM Tool、前端 TS 接口）全部传递 int 自增 id
- `_generic_insert` 在基类 LWBaseDataProvider（[lw_base_data_provider.py#L1074](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/base_providers/lw_base_data_provider.py#L1074)）
- `_is_autoincrement_table()` 在 SyncRepository（[sync_repository.py#L127](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/sync_repository.py#L127)），不在基类

## 决策前提

- 前提 1：6 张 AUTOINCREMENT 表的自增 id 在两端不同，需要跨端稳定标识用于同步去重和删除同步
- 前提 2：5 张表有 Provider，update/delete/get_by_id 全部使用自增 id
- 前提 3：所有调用方（API/Service/前端/LLM Tool）全部传递 int 自增 id
- 前提 4：用户在 PRD 审查中发现，一开始想用 hash_id 作主键，但发现本地 CRUD 改动面太广

## 可选方案

### 方案 A：hash_id 作为同步专用标识，_PRIMARY_KEY 保持自增 id

不改 `_PRIMARY_KEY`，hash_id 只在以下两个场景使用：
1. 同步去重：`upsert_rows_with_lww` 对自增表用 hash_id 作 LWW 查找键
2. 删除同步（PRD 3）：墓碑记录 record_id 存 hash_id，对端按 hash_id 删除

**优势**

- Provider 的 update/delete/get_by_id 完全不动，调用方不动
- 本地 CRUD 操作仍用自增 id，正常工作
- hash_id 只在 sync_repository 中使用，影响面收敛在同步模块
- PRD 1 改动范围可控（schema + 基类兜底生成 + sync_repository 查找路径）

**劣势**

- PRD 3 删除同步需要新增 `_delete_by_hash_id(hash_id)` 方法，不能用 `_generic_delete`
- hash_id 字段存在但本地 CRUD 不使用，未来读者可能困惑"为什么有 hash_id 却不用作主键"

### 方案 B：hash_id 作为主键，_PRIMARY_KEY 改为 hash_id

`_PRIMARY_KEY` 改为 `"hash_id"`，所有 update/delete/get_by_id 改用 hash_id 做 WHERE。

**优势**

- 单一标识，本地 CRUD 与同步使用同一字段，语义统一
- PRD 3 删除同步可直接复用 `_generic_delete`

**劣势**

- `_generic_update(record_id, data)` 会按 `WHERE hash_id = ?` 执行，但所有调用方传 int id，WHERE 命中 0 行 → 更新静默失败
- `_generic_delete` 同理，删除失败
- 手写 SQL 也受影响（如 `DELETE FROM habit_chains WHERE id = ?`）
- API 路由参数、Service 方法签名、前端 TS 接口、LLM Tool 参数全部需要从 int id 改为 hash_id 字符串
- 改动面远超 PRD 1 范围，实际等于 PRD 1+2 合并

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 前提 1 + 前提 2 + 前提 3 + 前提 4 成立 | 方案 A | 当前选择 |
| 未来本地 CRUD 也需要用 hash_id（如本地删除也要写墓碑）| 方案 B | 备选触发条件 |

## 最终决策

当前成立的前提：前提 1、2、3、4 均成立。

因此选择 `方案 A：hash_id 作为同步专用标识，_PRIMARY_KEY 保持自增 id`。

前提失效时的切换路径：当 PRD 2/3 完成后，若本地 CRUD 也需要用 hash_id（如本地删除也要写墓碑），则改 `_PRIMARY_KEY` 为 hash_id（即方案 B），并相应改造调用方。

## 决策原因

- 原因 1：方案 B 会导致所有调用方的 WHERE 条件失效（update/delete 静默失败），改动面扩散到 Provider/API/Service/前端，远超 PRD 1 范围
- 原因 2：方案 A 将 hash_id 影响面收敛在同步模块，符合"修改不能影响正常运行"的硬约束
- 原因 3：用户明确判断"如果使用 hash id 修改面太广"，从风险控制出发选择方案 A

## 后续影响

- PRD 1 范围：schema 加 hash_id 字段 + `_generic_insert` 兜底生成 + sync_repository LWW 查找用 hash_id
- PRD 2 范围：Provider 子类无需改造（_PRIMARY_KEY 不变）
- PRD 3 范围：需新增 `_delete_by_hash_id(hash_id)` 方法，不能用 `_generic_delete`；墓碑表 record_id 存 hash_id
- 需要后续验证：PRD 3 完成后，若发现本地 CRUD 也需要用 hash_id，触发方案 B 切换
- 文档影响：`_generic_insert` 的兜底逻辑（用 `HASH_ID_PREFIXES.get(self._TABLE_NAME)` 判断）作为本决策的实现细节，不单独写 ADR
