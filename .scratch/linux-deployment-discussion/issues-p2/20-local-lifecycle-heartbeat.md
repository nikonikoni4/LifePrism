# 本地生命周期心跳发送

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 消息路由与本地在线判断

---

## What to build

在本地 FastAPI 的 lifespan 中，启动时发送 `online` 事件，关闭时发送 `offline` 事件，让云端能立即知道本地状态变化。

**功能说明**：
- 启动时发送 `POST /api/sync/heartbeat {"event": "online"}`
- 关闭时发送 `POST /api/sync/heartbeat {"event": "offline"}`
- 云端收到 offline 后立即接管微信消息处理（不等 15 分钟超时）

**实现端到端**：

修改 `lifeprism/server/main.py` 的 `lifespan` 函数：

```python
async def send_heartbeat(event: str):
    """发送心跳事件到云端
    
    Args:
        event: 'online' | 'offline'
    """
    from lifeprism.config.settings_manager import get_setting
    from lifeprism.sync.sync_config import get_sync_api_key
    
    remote_url = get_setting("sync.remote_url")
    api_key = get_sync_api_key()
    
    if not remote_url or not api_key:
        logger.debug("未配置同步，跳过心跳发送")
        return
    
    try:
        response = httpx.post(
            url=f"{remote_url}/api/sync/heartbeat",
            json={"event": event},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        logger.info("心跳事件已发送: event=%s", event)
    except Exception as e:
        logger.warning("心跳事件发送失败: event=%s, error=%s", event, e)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 发送 online 事件
    await send_heartbeat("online")
    
    # 2. 现有启动逻辑（数据库初始化、Monitor、SyncClient、AgentLoop 等）
    # ...
    
    yield  # 应用运行期间
    
    # 3. 发送 offline 事件
    await send_heartbeat("offline")
    
    # 4. 现有关闭逻辑（Monitor、AgentLoop 清理等）
    # ...
```

集成测试：
- Mock httpx，测试启动时发送 online
- Mock httpx，测试关闭时发送 offline
- 测试未配置同步时跳过发送
- 测试网络失败时的 warning 日志

---

## Acceptance criteria

- [ ] lifespan 启动时发送 `online` 事件
- [ ] lifespan 关闭时发送 `offline` 事件
- [ ] 未配置 remote_url 或 api_key 时跳过发送
- [ ] 网络失败不影响启动/关闭流程（仅记录 WARNING）
- [ ] 日志记录：INFO 级别记录发送成功，WARNING 级别记录发送失败
- [ ] 集成测试通过：启动场景、关闭场景、未配置场景、网络失败场景
- [ ] 不影响现有启动/关闭流程

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/17-heartbeat-api.md` - 心跳 API 端点
