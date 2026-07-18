# Issue 6: 新增 Sync 专用日志文件（sync.log，500KB 覆盖式滚动）

## Parent

无（来源：`.scratch/file-conflict-resolution-redesign/prd.md` 决策 20）

## What to build

新增 sync 专用日志文件，独立记录同步过程和冲突处理过程，同时保留在全局 `lifeprism.log` 中。

**目标**：

- 独立查看同步过程，无需从混合日志中筛选
- 控制磁盘占用（上限 500KB，覆盖式滚动）
- 不影响现有日志架构，零侵入 sync_client.py / loop.py

**实现机制**（利用 Python logging 层级传播）：

- `sync_client.py` 的 `__name__` 为 `lifeprism.sync.sync_client`，是 `lifeprism.sync` 的子 logger
- 给 `lifeprism.sync` logger 附加专用 `RotatingFileHandler`
- 通过 `propagate=True`（默认）实现：日志同时写入 sync.log + lifeprism.log + 控制台
- **sync_client.py / loop.py 都不需要改动**

**配置参数**：

| 参数 | 值 | 说明 |
|------|-----|------|
| 文件路径 | `{lifeprism_data_path}/debug_logs/sync.log` | 与 `lifeprism.log` 同目录 |
| maxBytes | 500 * 1024（500KB） | 满足"只写入最大 500k"需求 |
| backupCount | 0 | 覆盖式：超过 500KB 时清空重新写，不保留备份文件 |
| encoding | utf-8 | 与现有 FileHandler 一致 |
| formatter | `TruncatingFormatter(_LOG_FORMAT)` | 复用现有 formatter，截断保护 2000 字符 |
| 启动行为 | 不清空，追加写入 | 保留上次启动后的同步日志，由 500KB 滚动自然淘汰 |

**改动点**：

1. **`lifeprism/utils/logger.py`** 新增 `setup_sync_logging(log_dir: Path)` 函数（约 15 行）：

```python
def setup_sync_logging(log_dir: Path) -> None:
    """配置 sync 专用日志（RotatingFileHandler，覆盖式 500KB）"""
    from logging.handlers import RotatingFileHandler
    log_dir.mkdir(parents=True, exist_ok=True)
    sync_log = log_dir / "sync.log"
    handler = RotatingFileHandler(
        sync_log,
        maxBytes=500 * 1024,
        backupCount=0,
        encoding="utf-8",
    )
    handler.setFormatter(TruncatingFormatter(_LOG_FORMAT))
    # 给 lifeprism.sync logger 附加专用 handler
    sync_logger = logging.getLogger("lifeprism.sync")
    sync_logger.addHandler(handler)
    # propagate=True（默认），日志自动传播到 root logger
    # → 同时写入 sync.log + lifeprism.log + 控制台
```

2. **`lifeprism/config/settings_manager.py`** `_setup_logging` 末尾追加一行：

```python
def _setup_logging(self) -> None:
    from lifeprism.utils.logger import setup_file_logging, setup_sync_logging
    setup_file_logging(self._lifeprism_data_path / "debug_logs")
    setup_sync_logging(self._lifeprism_data_path / "debug_logs")  # 新增
```

3. **sync_client.py / loop.py**：**无需改动**

**覆盖范围**：

- ✅ sync_client.py 全部日志（同步流程 + 冲突处理流程 + 错误重试）
- ✅ sync/ 目录下所有子模块（constants.py、hash_utils.py、heartbeat_manager.py、sync_config.py）
- ❌ loop.py 中 LLM 调用的通用日志（不区分消息类型，不在 sync.log 中）
  - 冲突处理 LLM 调用的**返回值**会通过 sync_client.py 的 `bus.send` 返回结果记录在 sync.log 中（如 "AI 合并超时"、"AI 返回空内容"、"AI 合并完成"）
  - LLM 调用过程中的工具调用细节日志不写入 sync.log

## Acceptance criteria

- [ ] 新增 `setup_sync_logging(log_dir)` 函数（`lifeprism/utils/logger.py`）
- [ ] `settings_manager._setup_logging` 调用 `setup_sync_logging`
- [ ] sync.log 文件路径为 `{lifeprism_data_path}/debug_logs/sync.log`
- [ ] maxBytes=500KB，backupCount=0（覆盖式滚动）
- [ ] 启动时不清空 sync.log（追加写入）
- [ ] 复用现有 `TruncatingFormatter` 和 `_LOG_FORMAT`
- [ ] sync_client.py 同步日志同时写入 sync.log + lifeprism.log + 控制台（验证 propagate）
- [ ] 冲突处理日志（超时/失败/成功/降级 keep_ours）出现在 sync.log 中
- [ ] sync.log 超过 500KB 时被清空重写（覆盖式）
- [ ] sync_client.py / loop.py 代码无改动
- [ ] 验证：触发一次同步后检查 sync.log 内容
- [ ] 验证：同时检查 lifeprism.log 是否也有相同日志（propagate 生效）

## Blocked by

None - can start immediately

## User stories covered

无直接用户故事（基础设施改造，来源是 PRD 决策 20「Sync 专用日志」）

## Related ADRs

- 无对应独立 ADR（本 issue 来源是 PRD 决策 20「Sync 专用日志」，未单独编写 ADR，因为实现极简且无架构性决策）
- 参见 [.scratch/file-conflict-resolution-redesign/prd.md](file:///d:/desktop/软件开发/LifeWatch-AI/.scratch/file-conflict-resolution-redesign/prd.md) 决策 20（Sync 专用日志）
