# 文件同步 API - Pull 接口

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 文件同步

---

## What to build

云端新增 `POST /api/sync/pull-files` 端点，支持增量文件拉取，返回 gzip 压缩 + base64 编码的文件内容。

**同步范围**：
- `agent/`、`assets/`、`channel/wechat/account.json`、`diary/`、`docs/`
- `external_files/`、`plan/`、`prompts/`、`session/`、`user/`、`workflow/`

**不同步**：
- `.schedule_state.json`、`config/`、`dataset/`、`debug_logs/`、`screenshots/`、`channel/wechat/media/`

**实现端到端**：

1. 在 `lifeprism/server/api/sync_cloud_api.py` 中新增端点：

```python
class SyncPullFilesRequest(BaseModel):
    last_sync_time: str = Field(..., description="上次同步时间（ISO 8601 格式）")
    directories: list[str] = Field(..., description="需要拉取的目录列表")

@router.post("/pull-files", summary="从云端拉取增量文件")
async def sync_pull_files(
    request: SyncPullFilesRequest, 
    _: None = Depends(verify_sync_api_key)
):
    """从云端拉取增量文件
    
    返回自 last_sync_time 后变更的文件，内容经过 gzip 压缩 + base64 编码。
    """
    from lifeprism.config.settings_manager import settings
    import gzip
    import base64
    from pathlib import Path
    from datetime import datetime
    
    logger.info("文件同步 Pull 请求: last_sync_time=%s, directories=%s", 
                request.last_sync_time, request.directories)
    
    data_path = Path(settings.lifeprism_data_path)
    last_sync_dt = datetime.fromisoformat(request.last_sync_time) if request.last_sync_time else None
    
    files = []
    for dir_pattern in request.directories:
        dir_path = data_path / dir_pattern
        
        if not dir_path.exists():
            continue
        
        # 递归遍历文件
        for file_path in dir_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if last_sync_dt and mtime <= last_sync_dt:
                continue
            
            # 读取、压缩、编码
            content_bytes = file_path.read_bytes()
            compressed = gzip.compress(content_bytes)
            encoded = base64.b64encode(compressed).decode()
            
            files.append({
                "path": str(file_path.relative_to(data_path)),
                "content": encoded,
                "mtime": mtime.isoformat()
            })
    
    logger.info("文件同步 Pull 完成: 文件数=%d", len(files))
    
    return {
        "files": files,
        "sync_time": datetime.now().isoformat()
    }
```

2. 集成测试：
   - 测试增量拉取（只返回 mtime > last_sync_time 的文件）
   - 测试 gzip + base64 编解码
   - 测试目录不存在时跳过
   - 测试 API Key 认证

---

## Acceptance criteria

- [ ] 端点 `POST /api/sync/pull-files` 已实现
- [ ] 支持增量查询（mtime > last_sync_time）
- [ ] 文件内容 gzip 压缩 + base64 编码
- [ ] 支持递归遍历目录（rglob）
- [ ] 目录不存在时跳过（不报错）
- [ ] API Key 认证生效
- [ ] 日志记录：INFO 级别记录请求参数和返回文件数
- [ ] 集成测试通过：增量拉取、编解码、目录不存在、认证失败
- [ ] 返回格式正确：`{files: [{path, content, mtime}], sync_time}`

---

## Blocked by

None - 可以立即开始
