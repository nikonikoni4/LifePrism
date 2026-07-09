# 文件同步 API - Push 接口

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 文件同步

---

## What to build

云端新增 `POST /api/sync/push-files` 端点，接收本地推送的文件，使用 Last-Write-Wins 冲突解决（比较 mtime）。

**冲突解决**：比较 mtime，谁更晚保留谁。

**为什么简单策略足够**：
1. 云端 agent-only 不启动 dreaming
2. 文件修改只来自会话（agent 处理消息）
3. 同一时间只有一端的 agent 在工作（本地在线则云端跳过）
4. 不会同时修改同一个文件

**实现端到端**：

在 `lifeprism/server/api/sync_cloud_api.py` 中新增端点：

```python
class FilePushItem(BaseModel):
    path: str = Field(..., description="相对 lifeprism_data_path 的路径")
    content: str = Field(..., description="gzip 压缩 + base64 编码的内容")
    mtime: str = Field(..., description="文件修改时间（ISO 8601 格式）")

class SyncPushFilesRequest(BaseModel):
    files: list[FilePushItem] = Field(..., description="待推送的文件列表")

@router.post("/push-files", summary="推送本地文件到云端")
async def sync_push_files(
    request: SyncPushFilesRequest, 
    _: None = Depends(verify_sync_api_key)
):
    """推送本地文件到云端
    
    使用 Last-Write-Wins 冲突解决：比较 mtime，谁更晚保留谁。
    """
    from lifeprism.config.settings_manager import settings
    import gzip
    import base64
    from pathlib import Path
    from datetime import datetime
    
    logger.info("文件同步 Push 请求: 文件数=%d", len(request.files))
    
    data_path = Path(settings.lifeprism_data_path)
    written_count = 0
    skipped_count = 0
    
    for file_item in request.files:
        file_path = data_path / file_item.path
        remote_mtime = datetime.fromisoformat(file_item.mtime)
        
        # Last-Write-Wins 冲突解决
        if file_path.exists():
            local_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if local_mtime >= remote_mtime:
                logger.debug("跳过文件（本地更新）: %s", file_item.path)
                skipped_count += 1
                continue
        
        # 解码、解压、写入
        compressed = base64.b64decode(file_item.content)
        content_bytes = gzip.decompress(compressed)
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content_bytes)
        
        # 设置 mtime（保持时间一致性）
        import os
        os.utime(file_path, (remote_mtime.timestamp(), remote_mtime.timestamp()))
        
        written_count += 1
        logger.debug("写入文件: %s", file_item.path)
    
    logger.info("文件同步 Push 完成: 写入=%d, 跳过=%d", written_count, skipped_count)
    
    return {
        "status": "ok",
        "written": written_count,
        "skipped": skipped_count,
        "sync_time": datetime.now().isoformat()
    }
```

集成测试：
- 测试文件写入
- 测试 Last-Write-Wins（本地更新时跳过）
- 测试 gzip + base64 解码
- 测试目录自动创建
- 测试 mtime 设置

---

## Acceptance criteria

- [ ] 端点 `POST /api/sync/push-files` 已实现
- [ ] Last-Write-Wins 冲突解决（比较 mtime）
- [ ] 文件内容 base64 解码 + gzip 解压
- [ ] 自动创建父目录（mkdir parents=True）
- [ ] 写入后设置 mtime（os.utime）
- [ ] API Key 认证生效
- [ ] 日志记录：INFO 级别记录写入/跳过统计
- [ ] 集成测试通过：写入、冲突解决、解码、目录创建、认证失败
- [ ] 返回格式正确：`{status, written, skipped, sync_time}`

---

## Blocked by

None - 可以立即开始
