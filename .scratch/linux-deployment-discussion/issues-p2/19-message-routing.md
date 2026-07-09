# 消息路由逻辑

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 消息路由与本地在线判断

---

## What to build

在云端 WeChat Channel 中集成心跳判断逻辑，本地在线时跳过消息处理，避免重复回复。

**问题背景**：微信消息群发到本地和云端，如果两端都处理会导致用户收到 2 条相同回复。

**解决方案**：云端收到消息时，判断本地是否在线：
- 在线（`is_local_online() = True`）：跳过处理，让本地处理
- 离线（`is_local_online() = False`）：云端接管处理

**实现端到端**：

修改 `lifeprism/llm/channel/wechat/wechat_channel.py::_handle_message()`：

```python
async def _handle_message(self, msg):
    """处理收到的消息（增加消息路由逻辑）"""
    from lifeprism.sync.heartbeat_manager import heartbeat_manager
    
    # 消息路由：本地在线时跳过
    if heartbeat_manager.is_local_online():
        logger.info(
            "本地在线，跳过云端处理: from_user=%s, message=%s",
            msg.get("from_user_name"),
            msg.get("content", "")[:50]
        )
        return
    
    # 本地离线，云端处理
    logger.info(
        "本地离线，云端接管处理: from_user=%s, message=%s",
        msg.get("from_user_name"),
        msg.get("content", "")[:50]
    )
    
    # 现有处理逻辑
    content = msg.get("content")
    from_user = msg.get("from_user_name")
    
    if not content or not from_user:
        logger.warning("消息缺少必需字段: msg=%s", msg)
        return
    
    # 调用 AgentLoop 处理
    await self._agent_loop.process_message(content, from_user)
```

集成测试（`test/integration/test_message_routing.py`）：
- Mock heartbeat_manager，测试本地在线时跳过
- Mock heartbeat_manager，测试本地离线时处理
- 验证日志记录

---

## Acceptance criteria

- [ ] WeChat Channel 集成 `is_local_online()` 判断
- [ ] 本地在线时跳过处理（不调用 AgentLoop）
- [ ] 本地离线时正常处理
- [ ] 日志记录：INFO 级别记录路由决策（跳过/接管）
- [ ] 集成测试通过：本地在线场景、本地离线场景
- [ ] 性能无影响（is_local_online() 是内存操作）
- [ ] 不影响现有消息处理逻辑

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/14-heartbeat-manager.md` - 心跳状态管理器
