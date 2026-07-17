---
version: 1.0
created_at: 2026-07-17
updated_at: 2026-07-17
last_updated: 初始版本，记录 mood_impacts 表使用 AUTOINCREMENT 自增 ID 与项目主流 TEXT hash ID 风格不符
abstract: mood_impacts 表 id 列使用 INTEGER PRIMARY KEY AUTOINCREMENT，与项目所有其他表使用 TEXT hash ID 的风格不一致。已验证无功能影响（无外键引用、mood_entries 存 name 而非 ID、排序由 sort_order 控制），延期处理。
---

# mood_impacts 自增 ID 与项目 TEXT ID 风格不一致

**优先级**: 低
**影响范围**: `lifeprism/config/database.py`（表定义）、`lifeprism/repository/providers/mood_providers.py`（MoodImpactProvider）

---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0  | 创建文档初稿 |

---

## 问题描述

`mood_impacts` 表的 `id` 列定义为 `INTEGER PRIMARY KEY AUTOINCREMENT`，而项目所有其他表均使用 `TEXT` 类型 + hash 命名风格作为主键。

### 具体差异

| 对比项 | mood_impacts | 项目其他表 |
|--------|-------------|-----------|
| 主键类型 | INTEGER AUTOINCREMENT | TEXT |
| 主键生成方式 | SQLite 自动分配 | uuid4/slug/hash |
| 示例 | 1, 2, 3 | `a1b2c3d4-...`, `mood_happy`, `category_work` |

### 为何无功能影响

| 检查项 | 结论 |
|--------|------|
| 外键引用 | 无其他表通过外键引用 `mood_impacts.id` |
| mood_entries.factors | 存储的是 name 字符串（JSON 数组形式），不是 ID |
| 排序逻辑 | 由 `sort_order` 字段控制，不依赖自增 ID 语义 |
| 同步 | LWW 比较使用 updated_at 字段，与主键类型无关 |

---

## 根因分析

| 根因 | 说明 |
|------|------|
| 历史遗留 | mood_impacts 是早期开发的表，当时未统一为 TEXT ID 风格 |
| 全清覆盖方案否决黑名单后回滚 | 原先为支持黑名单已将 ID 改造为 TEXT，后否决黑名单方案回滚为 AUTOINCREMENT（无功能影响，保留现状） |

---

## 当前影响

- **代码风格一致性问题**：mood_impacts 是唯一使用自增 ID 的表，影响代码库的一致性
- **开发混淆风险**：新的开发者可能以为自增 ID 是可接受的风格，导致未来新增表也使用自增 ID
- 无功能影响，不影响运行

---

## 清理计划

| 步骤 | 内容 | 依赖 |
|------|------|------|
| 1 | 修改 `database.py` MOOD_IMPACTS_CONFIG 中 id 列类型为 TEXT | 无 |
| 2 | 重建 mood_impacts 表，将现有自增 ID 迁移为 UUID | 步骤 1 |
| 3 | 修改 `MoodImpactProvider` 中 create/delete 方法的参数类型 | 步骤 2 |
| 4 | 更新同步测试验证 TEXT ID 不影响同步行为 | 步骤 2 |

触发条件：由"代码风格统一"驱动，优先级最低。建议在下次涉及 `mood_impacts` 表结构变更时同步实施。

---

## 相关代码文件

- `lifeprism/config/database.py` — MOOD_IMPACTS_CONFIG id 列定义
- `lifeprism/repository/providers/mood_providers.py` — MoodImpactProvider 方法签名
- `docs/history-bugs/2026-07-17-cloud-init-seed-data-syncs-to-local.md` — 原始种子数据同步重复问题

## 相关文档

- ADR：[2026-07-17 云端初始化与首次同步策略：全清覆盖替代黑名单过滤](../adr/2026-07-17-cloud-init-first-sync-full-clear.md)
