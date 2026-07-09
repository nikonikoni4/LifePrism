# 文件同步客户端集成

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 文件同步

---

## What to build

在 `SyncClient` 中集成文件同步，`sync_once()` 同时同步数据库和文件。

**关键文件**：`channel/wechat/account.json` 必须同步（包含微信 session_id，保证对话历史连贯）。

**实现端到端**：

修改 `lifeprism/sync/sync_client.py`：

```python
# 文件同步白名单
SYNC_DIRECTORIES = [
    "agent/",
    "assets/",
    "channel/wechat/account.json",  # 单文件特殊处理
    "diary/",
    "docs/",
    "external_files/",
    "plan/",
    "prompts/",
    "session/",
    "user/",
    "workflow/",
]

class SyncClient:
    def sync_once(self, tables=None, directories=None):
        """执行一次完整同步（数据库 + 文件）
        
        Args:
            tables: 同步表列表，None 则使用默认 SYNC_TABLES
            directories: 同步目录列表，None 则使用默认 SYNC_DIRECTORIES
        """
        from lifeprism.config.settings_manager import get_setting, set_setting
        from lifeprism.sync.sync_config import get_sync_api_key
        
        remote_url = get_setting("sync.remote_url")
        api_key = get_sync_api_key()
        last_sync_time = get_setting("sync.last_sync_time", "")
        
        if tables is None:
            tables = SYNC_TABLES
        if directories is None:
            directories = SYNC_DIRECTORIES
        
        # 数据库同步：Pull -> Push
        self.pull_from_remote(remote_url, api_key, last_sync_time, tables)
        self.push_to_remote(remote_url, api_key, tables)
        
        # 文件同步：Pull -> Push
        self.pull_files_from_remote(remote_url, api_key, last_sync_time, directories)
        self.push_files_to_remote(remote_url, api_key, last_sync_time, directories)
        
        # 只有全部成功才更新 last_sync_time
        current_time = datetime.now().isoformat()
        set_setting("sync.last_sync_time", current_time)
        logger.info("sync_once: 同步完成，last_sync_time 已更新为 %s", current_time)
    
    def pull_files_from_remote(self, remote_url, api_key, last_sync_time, directories):
        """拉取云端文件"""
        response = httpx.post(
            url=f"{remote_url}/api/sync/pull-files",
            json={"last_sync_time": last_sync_time, "directories": directories},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        
        for file_item in data.get("files", []):
            self._write_file(file_item)
        
        logger.info("pull_files_from_remote: 拉取 %d 个文件", len(data.get("files", [])))
    
    def push_files_to_remote(self, remote_url, api_key, last_sync_time, directories):
        """推送本地文件"""
        files = self._collect_changed_files(last_sync_time, directories)
        
        if not files:
            return
        
        response = httpx.post(
            url=f"{remote_url}/api/sync/push-files",
            json={"files": files},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        response.raise_for_status()
        
        logger.info("push_files_to_remote: 推送 %d 个文件", len(files))
    
    def _collect_changed_files(self, last_sync_time, directories):
        """收集变更文件"""
        import gzip
        import base64
        from pathlib import Path
        from lifeprism.config.settings_manager import settings
        
        data_path = Path(settings.lifeprism_data_path)
        last_sync_dt = datetime.fromisoformat(last_sync_time) if last_sync_time else None
        
        files = []
        for dir_pattern in directories:
            path = data_path / dir_pattern
            if path.is_file():
                # 单文件处理（如 channel/wechat/account.json）
                if self._should_sync_file(path, last_sync_dt):
                    files.append(self._encode_file(path, data_path))
            elif path.is_dir():
                # 目录递归
                for file_path in path.rglob("*"):
                    if file_path.is_file() and self._should_sync_file(file_path, last_sync_dt):
                        files.append(self._encode_file(file_path, data_path))
        
        return files
    
    def _should_sync_file(self, file_path, last_sync_dt):
        """判断文件是否需要同步"""
        if not last_sync_dt:
            return True
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        return mtime > last_sync_dt
    
    def _encode_file(self, file_path, data_path):
        """编码文件"""
        import gzip
        import base64
        
        content_bytes = file_path.read_bytes()
        compressed = gzip.compress(content_bytes)
        encoded = base64.b64encode(compressed).decode()
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        
        return {
            "path": str(file_path.relative_to(data_path)),
            "content": encoded,
            "mtime": mtime.isoformat()
        }
    
    def _write_file(self, file_item):
        """写入文件（Last-Write-Wins）"""
        import gzip
        import base64
        import os
        from pathlib import Path
        from lifeprism.config.settings_manager import settings
        
        data_path = Path(settings.lifeprism_data_path)
        file_path = data_path / file_item["path"]
        remote_mtime = datetime.fromisoformat(file_item["mtime"])
        
        # Last-Write-Wins
        if file_path.exists():
            local_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if local_mtime >= remote_mtime:
                logger.debug("跳过文件（本地更新）: %s", file_item["path"])
                return
        
        # 解码、解压、写入
        compressed = base64.b64decode(file_item["content"])
        content_bytes = gzip.decompress(compressed)
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content_bytes)
        os.utime(file_path, (remote_mtime.timestamp(), remote_mtime.timestamp()))
        
        logger.debug("写入文件: %s", file_item["path"])
```

集成测试：
- 测试 sync_once() 同时同步数据库和文件
- 测试单文件同步（channel/wechat/account.json）
- 测试目录递归同步
- 测试增量同步（只同步变更文件）

---

## Acceptance criteria

- [ ] `sync_once()` 集成文件同步
- [ ] 数据库和文件同步都成功才更新 `last_sync_time`
- [ ] 支持单文件特殊处理（channel/wechat/account.json）
- [ ] 支持目录递归同步
- [ ] 增量同步（mtime > last_sync_time）
- [ ] Last-Write-Wins 冲突解决
- [ ] 日志记录：INFO 级别记录文件同步统计
- [ ] 集成测试通过：完整同步、单文件、目录递归、增量同步

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/21-file-sync-pull-api.md` - Pull 接口
- `.scratch/linux-deployment-discussion/issues-p2/22-file-sync-push-api.md` - Push 接口
- `.scratch/linux-deployment-discussion/issues-p2/05-sync-client-basic.md` - SyncClient 基础逻辑
