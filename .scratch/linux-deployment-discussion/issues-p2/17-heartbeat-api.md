# 心跳 API 端点

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 消息路由与本地在线判断

---

## What to build

云端新增 `POST /api/sync/heartbeat` 端点，接收本地发送的生命周期事件（online/offline），用于消息路由判断。

**功能说明**：
- 本地 FastAPI 启动时发送 `{"event": "online"}`
- 本地 FastAPI 关闭时发送 `{"event": "offline"}`
- 云端调用 `heartbeat_manager.set_event()` 更新状态

**实现端到端**：

在 `lifeprism/server/api/sync_cloud_api.py` 中新增端点：

```python
class HeartbeatRequest(BaseModel):
    """心跳请求"""
    event: str = Field(..., description="事件类型（online/offline/ping）")

@router.post("/heartbeat", summary="接收本地心跳/生命周期事件")
async def sync_heartbeat(
    request: HeartbeatRequest, 
    _: None = Depends(verify_sync_api_key)
):
    """接收本地心跳/生命周期事件
    
    **请求参数**:
    - event: 'online'（启动）| 'offline'（关闭）| 'ping'（心跳）
    
    **认证**:
    - Authorization: Bearer {api_key} HTTP Header
    
    **响应**:
    - status: 'ok'
    - server_time: 服务器时间（ISO 8601 格式）
    """
    from lifeprism.sync.heartbeat_manager import heartbeat_manager
    
    if request.event in ("online", "offline"):
        heartbeat_manager.set_event(request.event)
        logger.info("收到生命周期事件: event=%s", request.event)
    elif request.event == "ping":
        heartbeat_manager.update_heartbeat()
        logger.debug("收到心跳 ping")
    else:
        raise ValidationError(
            message=f"无效的事件类型: {request.event}",
            code="INVALID_HEARTBEAT_EVENT"
        )
    
    return {
        "status": "ok",
        "server_time": datetime.now().isoformat()
    }
```

集成测试（`test/integration/api/test_sync_heartbeat_api.py`）：
- 测试 online 事件
- 测试 offline 事件
- 测试 ping 事件
- 测试 API Key 认证失败
- 测试无效事件类型

---

## Acceptance criteria

- [ ] 端点 `POST /api/sync/heartbeat` 已实现
- [ ] 接受 `online`、`offline`、`ping` 事件
- [ ] online/offline 调用 `heartbeat_manager.set_event()`
- [ ] ping 调用 `heartbeat_manager.update_heartbeat()`
- [ ] API Key 认证生效（使用 `verify_sync_api_key` 依赖）
- [ ] 无效事件类型抛出 ValidationError
- [ ] 日志记录：INFO 级别记录生命周期事件，DEBUG 级别记录 ping
- [ ] 集成测试通过：所有事件类型、认证失败、无效事件
- [ ] 返回格式正确：`{status, server_time}`

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/14-heartbeat-manager.md` - 心跳状态管理器
