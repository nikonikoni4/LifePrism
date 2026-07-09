# 分批同步机制 - 客户端层

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 通信架构

---

## What to build

在 `SyncClient` 中实现分批拉取循环，每表分批 1000 条，避免首次同步大数据集时超时。

**问题背景**：首次同步 16MB 数据（~10,000 条记录）时，单次请求可能超时。需要客户端按表逐个拉取，每表分批 1000 条。

**实现端到端**：

修改 `lifeprism/sync/sync_client.py::pull_from_remote()`：

```python
def pull_from_remote(self, remote_url, api_key, last_sync_time, tables):
    """拉取云端数据（分批拉取）
    
    对每个表分批拉取（1000 条/批），应用 Last-Write-Wins 冲突解决。
    """
    for table_name in tables:
        logger.info("开始拉取表: %s", table_name)
        offset = 0
        batch_size = 1000
        total_rows = 0
        
        while True:
            response = httpx.post(
                url=f"{remote_url}/api/sync/pull",
                json={
                    "last_sync_time": last_sync_time,
                    "tables": [table_name],  # 一次只拉一个表
                    "offset": offset,
                    "limit": batch_size,
                },
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            
            rows = data.get("changes", {}).get(table_name, [])
            if not rows:
                break
            
            # 应用 Last-Write-Wins 冲突解决
            rows_to_upsert = []
            for remote_row in rows:
                pk_field = self.sync_repository.get_primary_key_field(table_name)
                pk_value = remote_row.get(pk_field)
                local_row = self.sync_repository.get_row_by_pk(table_name, pk_field, pk_value)
                
                if local_row is None:
                    rows_to_upsert.append(remote_row)
                elif str(local_row.get("updated_at", "")) <= str(last_sync_time):
                    rows_to_upsert.append(remote_row)
                elif str(remote_row.get("updated_at", "")) > str(local_row.get("updated_at", "")):
                    rows_to_upsert.append(remote_row)
            
            if rows_to_upsert:
                self.sync_repository.upsert_rows(table_name, rows_to_upsert)
            
            total_rows += len(rows)
            logger.debug("表 %s 分批拉取：offset=%d, 本批=%d, 累计=%d", 
                        table_name, offset, len(rows), total_rows)
            
            if len(rows) < batch_size:
                break  # 最后一批
            
            offset += batch_size
        
        logger.info("表 %s 拉取完成，总计 %d 条记录", table_name, total_rows)
```

集成测试：
- 测试首次同步大数据集（> 1000 条）
- 测试分批拉取逻辑（多批次）
- 测试最后一批（< 1000 条）

---

## Acceptance criteria

- [ ] `pull_from_remote()` 实现分批拉取循环
- [ ] 每表分批 1000 条（batch_size = 1000）
- [ ] 按表逐个拉取（tables 列表只传单个表名）
- [ ] 最后一批判断：`len(rows) < batch_size` 时退出循环
- [ ] Last-Write-Wins 冲突解决逻辑保持不变
- [ ] 日志记录：INFO 级别记录每表总记录数，DEBUG 级别记录分批进度
- [ ] 集成测试通过：首次同步大数据集（10,000+ 条记录）
- [ ] 性能验证：首次同步 16MB 数据耗时 < 60 秒

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/15-batch-sync-repository.md` - Repository 层分页支持
