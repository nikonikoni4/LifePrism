---
title: _generic_insert 兜底生成 hash_id
status: ready-for-agent
created_at: 2026-07-22
parent_prd: .scratch/deletion-sync-01-schema/prd.md
---

# 03 - _generic_insert 兜底生成 hash_id

## Parent

- PRD: [.scratch/deletion-sync-01-schema/prd.md](file:///d:/desktop/软件开发/LifeWatch-AI/.scratch/deletion-sync-01-schema/prd.md)

## What to build

改造基类 `LWBaseDataProvider._generic_insert`，对在 `HASH_ID_PREFIXES` 中的表（即有 hash_id 字段的表），如果调用方未传入 `hash_id` 则兜底生成（前缀 + `uuid.uuid4().hex[:12]`），已传入则保留。

判断方式：用 `HASH_ID_PREFIXES.get(self._TABLE_NAME)` 判断，返回非 None 即需要生成 hash_id。**不依赖 `_is_autoincrement_table()`**（该方法在 SyncRepository 中，不在基类）。

具体实现：

```python
# 兜底生成 hash_id（同步专用标识，与 _PRIMARY_KEY 无关）
# 前缀字典同时作为"哪些表需要 hash_id"的判断依据
hash_prefix = HASH_ID_PREFIXES.get(self._TABLE_NAME)
if hash_prefix and "hash_id" not in data:
    data["hash_id"] = f"{hash_prefix}{uuid.uuid4().hex[:12]}"
```

## Acceptance criteria

- [ ] `lifeprism/repository/base_providers/lw_base_data_provider.py` 的 `_generic_insert` 方法加入 hash_id 兜底生成逻辑
- [ ] 用 `HASH_ID_PREFIXES.get(self._TABLE_NAME)` 判断（非 None 即需要生成）
- [ ] 未传入 `hash_id` 时自动生成（前缀 + `uuid.uuid4().hex[:12]`）
- [ ] 已传入 `hash_id` 时保留不覆盖
- [ ] TEXT 主键表（不在 `HASH_ID_PREFIXES` 中）不受影响
- [ ] 建议在 `_generic_insert` 内部延迟导入 `HASH_ID_PREFIXES`（参考现有 `from lifeprism.utils.time_utils import get_utc_now_iso` 的导入风格），避免模块加载顺序问题
- [ ] 测试覆盖未传入 `hash_id` 时自动生成
- [ ] 测试覆盖已传入 `hash_id` 时保留不覆盖
- [ ] 测试覆盖 TEXT 主键表不受影响（不生成 hash_id）
- [ ] Prior art: `test/core/unit/storage/test_base_provider_generic_methods.py`

## Blocked by

- Issue 01（hash_id schema 基础）— 必须先有 `HASH_ID_PREFIXES` 字典定义

## Comments

### 关键设计约束（来自 ADR）

- `hash_id` 是**兜底策略**：Provider 子类无感知，调用方也可显式传入。详见 [ADR 2026-07-22-hash-id-sync-only-identifier.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/ADR/2026-07-22-hash-id-sync-only-identifier.md)
- 前缀字典的 key 集合 = 有 hash_id 字段的表集合（一对一映射），一份字典即可承担"判断哪些表需要 hash_id"和"提供前缀"两个职责
- 依赖方向：`lifeprism.repository.base_providers` → `lifeprism.sync.constants`，单向，无循环依赖（已验证）
