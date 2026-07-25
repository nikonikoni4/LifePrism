"""
云端同步端到端测试

测试场景：
1. 基本数据库同步（push 到云端）
2. 墓碑同步（删除操作同步到云端）

参考: scripts/prompts/sync-e2e-testing.md
"""
import os
import sys
import uuid
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

# 确保使用本地数据路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifeprism.config.settings_manager import settings, get_setting, set_setting
from lifeprism.repository.database_manager import DatabaseManager
from lifeprism.repository.sync_repository import SyncRepository
from lifeprism.sync.sync_client import SyncClient
from lifeprism.utils.time_utils import get_utc_now_iso as utc_now_iso

# 确保指向本地云端
set_setting("sync.remote_url", "http://localhost:8102")

LOCAL_DB = str(settings.lw_db_path)
CLOUD_DB = r"explore\LifePrism\localData\dataset\lifewatch_ai.db"

print("=" * 70)
print("云端同步端到端测试")
print("=" * 70)
print(f"Local DB:  {LOCAL_DB}")
print(f"Cloud DB:  {CLOUD_DB}")
print(f"Remote URL: {get_setting('sync.remote_url')}")
print()

# ==================== Step 0: 验证云端服务可用 ====================
print("=" * 70)
print("Step 0: 验证云端服务可用")
print("=" * 70)
import httpx
try:
    resp = httpx.get("http://localhost:8102/health", timeout=5)
    print(f"Cloud health check: {resp.status_code}")
    if resp.status_code != 200:
        print(f"WARNING: Cloud health returned {resp.status_code}")
except Exception as e:
    print(f"ERROR: Cloud service not reachable: {e}")
    sys.exit(1)

# ==================== Step 1: 准备测试数据 ====================
print("\n" + "=" * 70)
print("Step 1: 准备测试数据")
print("=" * 70)

test_id = f"e2e-{uuid.uuid4().hex[:8]}"
now = utc_now_iso()
print(f"Test record ID: {test_id}")
print(f"Timestamp: {now}")

# 在本地 user_values 表插入测试记录
conn = sqlite3.connect(LOCAL_DB)
# 先检查表是否存在
cursor = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='user_values'"
)
if cursor.fetchone():
    conn.execute(
        "INSERT OR REPLACE INTO user_values (id, keywords, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (test_id, f"e2e_sync_test_{test_id}", now, now),
    )
    conn.commit()
    print(f"Inserted test record into user_values (id={test_id})")
else:
    print("ERROR: user_values table not found in local DB")
    sys.exit(1)
conn.close()

# ==================== Step 2: 运行同步 ====================
print("\n" + "=" * 70)
print("Step 2: 运行 SyncClient.sync_once()")
print("=" * 70)

db_manager = DatabaseManager(
    DB_PATH=LOCAL_DB,
    use_pool=True,
    pool_size=3,
)
sync_repo = SyncRepository(db_manager=db_manager)
client = SyncClient(db_manager=db_manager, sync_repository=sync_repo)

sync_success = False
try:
    client.sync_once()
    sync_success = True
    print(">>> sync_once() completed successfully")
except Exception as e:
    print(f">>> sync_once() FAILED: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        client.finish_sync()
    except Exception:
        pass
    db_manager._close_connection_pool()

# ==================== Step 3: 验证数据到达云端 ====================
print("\n" + "=" * 70)
print("Step 3: 验证数据到达云端")
print("=" * 70)

if sync_success:
    cloud_conn = sqlite3.connect(CLOUD_DB)
    row = cloud_conn.execute(
        "SELECT id, keywords, updated_at FROM user_values WHERE id = ?", (test_id,)
    ).fetchone()
    if row:
        print(f"✅ Cloud received record: id={row[0]}, keywords={row[1]}, updated_at={row[2]}")
        if row[2] == now:
            print(f"✅ updated_at matches: {now}")
        else:
            print(f"⚠️ updated_at mismatch: local={now}, cloud={row[2]}")
    else:
        print(f"❌ Cloud did NOT receive record (id={test_id})")
    cloud_conn.close()
else:
    print("⏭️ Skipping verification (sync failed)")

# ==================== Step 4: 测试墓碑同步（删除） ====================
print("\n" + "=" * 70)
print("Step 4: 测试墓碑同步（删除记录）")
print("=" * 70)

if sync_success:
    # 在本地删除测试记录
    conn = sqlite3.connect(LOCAL_DB)
    conn.execute("DELETE FROM user_values WHERE id = ?", (test_id,))
    conn.commit()
    print(f"Deleted test record from local (id={test_id})")

    # 检查本地 deletion_log 是否有记录
    cursor = conn.execute(
        "SELECT target_table, record_id, source FROM deletion_log WHERE record_id = ?",
        (test_id,),
    )
    tombstone = cursor.fetchone()
    if tombstone:
        print(f"✅ Local tombstone created: table={tombstone[0]}, id={tombstone[1]}, source={tombstone[2]}")
    else:
        print(f"⚠️ No tombstone in deletion_log (may use different delete path)")
    conn.close()

    # 再次同步（推送墓碑到云端）
    print("\nRunning sync_once() to push tombstone...")
    db_manager = DatabaseManager(
        DB_PATH=LOCAL_DB,
        use_pool=True,
        pool_size=3,
    )
    sync_repo = SyncRepository(db_manager=db_manager)
    client = SyncClient(db_manager=db_manager, sync_repository=sync_repo)
    try:
        client.sync_once()
        print(">>> Second sync_once() completed")
    except Exception as e:
        print(f">>> Second sync_once() FAILED: {e}")
    finally:
        try:
            client.finish_sync()
        except Exception:
            pass
        db_manager._close_connection_pool()

    # 验证云端记录已删除
    cloud_conn = sqlite3.connect(CLOUD_DB)
    row = cloud_conn.execute(
        "SELECT id FROM user_values WHERE id = ?", (test_id,)
    ).fetchone()
    if row is None:
        print(f"✅ Cloud record deleted (id={test_id}) - tombstone sync works!")
    else:
        print(f"❌ Cloud record still exists (id={test_id}) - tombstone sync FAILED")

    # 检查云端 deletion_log
    cursor = cloud_conn.execute(
        "SELECT target_table, record_id, source FROM deletion_log WHERE record_id = ?",
        (test_id,),
    )
    cloud_tombstone = cursor.fetchone()
    if cloud_tombstone:
        print(f"✅ Cloud tombstone received: table={cloud_tombstone[0]}, id={cloud_tombstone[1]}, source={cloud_tombstone[2]}")
    else:
        print(f"⚠️ No tombstone in cloud deletion_log")
    cloud_conn.close()

# ==================== 总结 ====================
print("\n" + "=" * 70)
print("测试总结")
print("=" * 70)
print("E2E 测试完成。请检查上方结果。")
