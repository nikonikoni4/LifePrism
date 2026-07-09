# 云端 FastAPI 服务启动

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 云端与本地 API 区分

---

## What to build

修改 `main_agent_only.py`，启动轻量 FastAPI 服务（端口 8101），仅注册同步 API，解决当前云端无 HTTP API 导致本地无法调用的问题。

**问题背景**：
- 当前 `main_agent_only.py` 不启动 FastAPI
- 本地 `SyncClient` 调用 `POST /api/sync/pull` 找不到服务器
- 心跳机制无法工作（没有 `/api/sync/heartbeat` 端点）

**解决方案**：云端启动轻量 FastAPI，仅提供同步 API（不需要其他 30+ 个业务 API）。

**实现端到端**：

修改 `lifeprism/server/main_agent_only.py`：

```python
async def _run_agent_and_api():
    """Agent Only 主循环 + FastAPI 服务"""
    from fastapi import FastAPI
    from lifeprism.server.api import sync_cloud_router
    import uvicorn
    
    # 1. 创建 FastAPI 实例（仅同步 API）
    app = FastAPI(
        title="LifePrism Agent Only - Sync API",
        description="云端同步 API 服务（仅数据同步，不包含业务 API）",
        version="1.0.0"
    )
    app.include_router(sync_cloud_router)  # 仅注册同步 API
    
    logger.info("[AGENT-ONLY] FastAPI 实例创建完成（仅同步 API）")
    
    # 2. 启动 FastAPI（后台任务）
    config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=8101,  # 云端专用端口
        log_level="info"
    )
    server = uvicorn.Server(config)
    api_task = asyncio.create_task(server.serve())
    
    logger.info("[AGENT-ONLY] FastAPI 启动: host=0.0.0.0, port=8101")
    
    # 3. 启动 Agent Loop + WeChat Channel
    init_database_full()
    loop_task, wechat_channel = await start_agent_and_channel()
    
    logger.info("[AGENT-ONLY] Agent Loop + WeChat Channel 启动完成")
    
    # 4. 等待终止信号
    def handle_signal(sig, frame):
        logger.info("[AGENT-ONLY] 收到终止信号: %s", sig)
        # 取消任务
        api_task.cancel()
        loop_task.cancel()
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # 5. 等待任务完成
    try:
        await asyncio.gather(api_task, loop_task)
    except asyncio.CancelledError:
        logger.info("[AGENT-ONLY] 任务已取消，开始清理")
    
    # 6. 清理
    await stop_agent_and_channel(wechat_channel)
    logger.info("[AGENT-ONLY] 服务已停止")

# 修改 main 函数
def main():
    parser = argparse.ArgumentParser(description="LifePrism Linux Agent Only")
    # ... 现有参数
    
    args = parser.parse_args()
    
    if args.command == "start":
        asyncio.run(_run_agent_and_api())
    elif args.command == "reinit-config":
        # ... 现有逻辑
    # ...
```

集成测试（`test/integration/test_agent_only_api.py`）：
- 测试 FastAPI 启动成功
- 测试端口 8101 可访问
- 测试同步端点可用（/api/sync/pull, /api/sync/push, /api/sync/heartbeat）
- 测试 Agent Loop 同时运行

---

## Acceptance criteria

- [ ] `main_agent_only.py` 启动 FastAPI 服务（端口 8101）
- [ ] 仅注册 `sync_cloud_router`（不注册其他业务 API）
- [ ] FastAPI 和 Agent Loop 并行运行（asyncio.gather）
- [ ] 终止信号（SIGINT/SIGTERM）正确处理
- [ ] 日志记录：INFO 级别记录 FastAPI 启动、Agent Loop 启动
- [ ] 集成测试通过：端口可访问、同步端点可用、Agent Loop 运行
- [ ] 不影响现有 CLI 命令（reinit-config, show-config, test-llm）

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/03-sync-api-pull.md` - Pull API
- `.scratch/linux-deployment-discussion/issues-p2/04-sync-api-push.md` - Push API
- `.scratch/linux-deployment-discussion/issues-p2/17-heartbeat-api.md` - 心跳 API
- `.scratch/linux-deployment-discussion/issues-p2/21-file-sync-pull-api.md` - 文件 Pull API
- `.scratch/linux-deployment-discussion/issues-p2/22-file-sync-push-api.md` - 文件 Push API
