# wechat_account_state 表 + Provider + account.json 迁移

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 文件同步冲突处理

## What to build

新增 `wechat_account_state` 表（存储在 lifewatch_ai.db 中），加入 SYNC_TABLES 自动走数据库同步的记录级 LWW，新建 WechatAccountStateProvider，实现 account.json 到数据库的迁移。

**ADR 参考**：`docs/adr/2026-07-14-file-sync-conflict-resolution.md` v2.1 决策 4

**表结构**：

```sql
CREATE TABLE wechat_account_state (
    wechat_user_id  TEXT PRIMARY KEY,
    context_token   TEXT,
    last_session_id TEXT,
    updated_at      TEXT NOT NULL
);
```

- 以 wechat_user_id 为主键（当前实际只有单用户，但设计上支持多微信用户）
- 加入 SYNC_TABLES，自动走数据库同步的记录级 LWW，无需走文件同步链路
- 从 SYNC_DIRECTORIES 移除 `channel/wechat/account.json`

**WechatAccountStateProvider**（继承 LWBaseDataProvider，只做 CRUD）：
- `get_state(wechat_user_id)` → 查询状态（context_token + last_session_id）
- `save_state(wechat_user_id, context_token, last_session_id)` → 保存状态

**WechatChannel 改造**：
- 现有 `WechatChannel._user_data` 改为从数据库读写（通过 WechatAccountStateProvider 访问）
- 不再读写 `channel/wechat/account.json` 文件

**迁移策略**：
- 首次启动时检测 `channel/wechat/account.json` 是否存在
- 若存在且数据库中无对应记录 → 读取 account.json → 写入 wechat_account_state 表 → 重命名 account.json 为 account.json.bak（不删除，防御性策略）
- 若表中已有记录 → 跳过迁移（以数据库为准）

**TABLE_CONFIGS 注册**：`wechat_account_state` 表必须在 `database.py` 的 TABLE_CONFIGS 中注册 DDL，并设置 `timestamps: True`（用于 LWW 的 updated_at 自动管理）。加入 SYNC_TABLES 时直接修改 `sync_client.py` 的 SYNC_TABLES 列表。

**sync_repository 校验**：`sync_repository.py` 的 `_validate_table_name` 会校验表名是否在 TABLE_CONFIGS 中注册。wechat_account_state 不是动态表（不以 custom_ 开头），必须在 TABLE_CONFIGS 注册才能被 sync_repository 接受。

**WechatChannel.stop() 改造**：现有 `channel.py:stop()` 将 `_user_data` 保存到 account.json 文件，改造后应调用 `WechatAccountStateProvider.save_state()` 保存到数据库。

## Acceptance criteria

- [ ] `wechat_account_state` 表 DDL 在 `database.py` 的 TABLE_CONFIGS 中注册（`timestamps: True`）
- [ ] WechatAccountStateProvider 继承 LWBaseDataProvider，实现 get_state / save_state
- [ ] `wechat_account_state` 加入 SYNC_TABLES（直接修改 `sync_client.py` 的 SYNC_TABLES 列表）
- [ ] `channel/wechat/account.json` 从 SYNC_DIRECTORIES 移除
- [ ] WechatChannel._user_data 改为从数据库读写（通过 WechatAccountStateProvider）
- [ ] WechatChannel.stop() 保存状态到数据库（不再写 account.json 文件）
- [ ] 首次启动迁移：account.json 存在时自动迁移到数据库，原文件重命名为 .bak
- [ ] 已有数据库记录时跳过迁移
- [ ] 单元测试：Provider CRUD 正确
- [ ] 单元测试：迁移逻辑正确（文件→数据库→重命名）
- [ ] 单元测试：WechatChannel.stop() 正确保存到数据库
- [ ] 集成测试：wechat_account_state 表通过 SYNC_TABLES 自动同步

## Blocked by

None - can start immediately
