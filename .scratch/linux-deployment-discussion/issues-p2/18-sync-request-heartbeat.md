# 同步请求心跳更新

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 消息路由与本地在线判断

---

## What to build

在 `sync_pull` API 处理请求的开头调用 `heartbeat_manager.update_heartbeat()`，复用数据同步请求作为心跳信号。

**功能说明**：
- 本地每 10 分钟发起 `POST /api/sync/pull` 拉取数据
- 云端收到请求后，**第一步**更新心跳时间戳
- 不需要单独的心跳请求，节省网络开销

**为什么必须在请求开头**：
- 如果放在查询结束后，中间可能有几秒延迟
- 微信消息恰好在这几秒内到达，可能误判为离线
- 开头调用确保状态实时生效

**实现端到端**：

修改 `lifeprism/server/api/sync_cloud_api.py::sync_pull()`：

```python
@router.post("/pull", summary="从云端拉取增量数据")
async def sync_pull(request: SyncPullRequest, _: None = Depends(verify_sync_api_key)):
    """从云端拉取增量数据
    
    第一步：更新心跳时间戳（复用同步请求作为心跳）
    """
    from lifeprism.sync.heartbeat_manager import heartbeat_manager
    
    # 第一步：更新心跳
    heartbeat_manager.update_heartbeat()
    
    logger.info(
        "同步 Pull 请求开始: last_sync_time=%s, tables=%s, offset=%d, limit=%s",
        request.last_sync_time,
        request.tables,
        request.offset,
        request.limit,
    )
    start_time = time.perf_counter()
    
    # 对每个表执行增量查询（现有逻辑）
    changes: dict[str, list[dict[str, Any]]] = {}
    for table_name in request.tables:
        rows = sync_repository.query_incremental(
            table_name, 
            request.last_sync_time,
            offset=request.offset,
            limit=request.limit
        )
        if rows:
            changes[table_name] = rows
    
    # ... 现有逻辑
```

集成测试：
- 测试 pull 请求后 `is_local_online()` 返回 True
- 测试连续 pull 请求保持在线状态
- 测试 15 分钟后超时离线

---

## Acceptance criteria

- [ ] `sync_pull()` 开头调用 `heartbeat_manager.update_heartbeat()`
- [ ] 调用在日志记录之前（确保最先执行）
- [ ] 不影响现有查询逻辑
- [ ] 集成测试通过：pull 请求后在线状态生效
- [ ] 性能无影响（update_heartbeat() 是内存操作，耗时 < 1μs）

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/14-heartbeat-manager.md` - 心跳状态管理器
- `.scratch/linux-deployment-discussion/issues-p2/03-sync-api-pull.md` - Pull API 基础实现
