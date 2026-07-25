"""
云端同步端到端测试 - 墓碑同步专项（修正版）

测试流程：
1. 插入记录 → 第一次同步（记录到达云端，updated_at <= last_sync_time）
2. 删除记录 + 写墓碑 → 第二次同步（墓碑推送到云端，数据 Pull 不会拉回）
3. 验证云端记录被删除

参考: scripts/prompts/sync-e2e-testing.md
"""
import sys
import uuid
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifeprism.config.settings_manager import settings, set_setting
from lifeprism.repository.database_manager import DatabaseManager
from lifeprism.repository.sync_repository import SyncRepository
from lifeprism.sync.sync_client import SyncClient
from lifeprism.utils.time_utils import get_utc_now_iso as utc_now_iso

set_setting("sync.remote_url", "http://localhost:8102")

LOCAL_DB = str(settings.lw_db_path)
CLOUD_DB = r"explore\LifePrism\localData\dataset\lifewatch_ai.db"


def run_sync():
    """执行一次 sync_once"""
    db_manager = DatabaseManager(DB_PATH=LOCAL_DB, use_pool=True, pool_size=3)
    sync_repo = SyncRepository(db_manager=db_manager)
    client = SyncClient(db_manager=db_manager, sync_repository=sync_repo)
    try:
        client.sync_once()
        return True
    except Exception as e:
        print(f"sync_once FAILED: {e}")
        return False
    finally:
        try:
            client.finish_sync()
        except Exception:
            pass
        db_manager._close_connection_pool()


print("=" * 70)
print("云端同步端到端测试 - 墓碑同步（修正版）")
print("=" * 70)

# ==================== Step 1: 插入记录 + 第一次同步 ====================
print("\n=== Step 1: 插入记录 + 第一次同步（让记录到达云端）===")
test_id = f"e2e-ts-{uuid.uuid4().hex[:8]}"
now = utc_now_iso()

for db_path, label in [(LOCAL_DB, "local"), (CLOUD_DB, "cloud")]:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO user_values (id, keywords, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (test_id, "e2e_tombstone_test", now, now),
    )
    conn.commit()
    conn.close()
print(f"Inserted: id={test_id}, updated_at={now}")

run_sync()
print("First sync done (record should be in cloud now)")

# 验证云端有记录
cloud_conn = sqlite3.connect(CLOUD_DB)
row = cloud_conn.execute("SELECT id FROM user_values WHERE id = ?", (test_id,)).fetchone()
print(f"Cloud has record: {row is not None}")
cloud_conn.close()

# ==================== Step 2: 删除记录 + 写墓碑 + 第二次同步 ====================
print("\n=== Step 2: 删除记录 + 写墓碑 + 第二次同步 ===")

# 写墓碑
db_manager = DatabaseManager(DB_PATH=LOCAL_DB, use_pool=True, pool_size=3)
from lifeprism.repository.providers.deletion_log_provider import DeletionLogProvider
tombstone_provider = DeletionLogProvider(db_manager=db_manager)
tombstone_id = tombstone_provider.create_tombstone(
    target_table="user_values", record_id=test_id, source="local"
)
db_manager._close_connection_pool()
print(f"Tombstone created: {tombstone_id}")

# 删除本地记录
conn = sqlite3.connect(LOCAL_DB)
conn.execute("DELETE FROM user_values WHERE id = ?", (test_id,))
conn.commit()
conn.close()
print(f"Local record deleted: {test_id}")

# 第二次同步
run_sync()
print("Second sync done (tombstone pushed to cloud)")

# ==================== Step 3: 验证云端记录被删除 ====================
print("\n=== Step 3: 验证云端记录被删除 ===")
cloud_conn = sqlite3.connect(CLOUD_DB)
row = cloud_conn.execute("SELECT id FROM user_values WHERE id = ?", (test_id,)).fetchone()
if row is None:
    print(f"✅ Cloud record deleted (id={test_id}) - 墓碑同步成功！")
else:
    print(f"❌ Cloud record still exists (id={test_id}) - 墓碑同步失败")

tombstone = cloud_conn.execute(
    "SELECT target_table, record_id, source FROM deletion_log WHERE record_id = ?", (test_id,)
).fetchone()
if tombstone:
    print(f"✅ Cloud tombstone: table={tombstone[0]}, record_id={tombstone[1]}, source={tombstone[2]}")
else:
    print(f"❌ No tombstone in cloud deletion_log")
cloud_conn.close()

# ==================== Step 4: 测试反向墓碑同步（云端→本地）====================
print("\n=== Step 4: 测试反向墓碑同步（云端→本地）===")
test_id_2 = f"e2e-ts2-{uuid.uuid4().hex[:8]}"
now2 = utc_now_iso()

# 在两端插入记录
for db_path, label in [(LOCAL_DB, "local"), (CLOUD_DB, "cloud")]:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO user_values (id, keywords, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (test_id_2, "e2e_reverse", now2, now2),
    )
    conn.commit()
    conn.close()

# 第一次同步让记录到达两端
run_sync()
print(f"First sync done for test_id_2={test_id_2}")

# 云端删除 + 写墓碑（created_at 用当前时间，确保 > last_sync_time）
cloud_conn = sqlite3.connect(CLOUD_DB)
tombstone_created = utc_now_iso()
cloud_conn.execute(
    "INSERT OR IGNORE INTO deletion_log (id, target_table, record_id, source, created_at, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (f"dl-{uuid.uuid4().hex[:8]}", "user_values", test_id_2, "cloud", tombstone_created, tombstone_created),
)
cloud_conn.execute("DELETE FROM user_values WHERE id = ?", (test_id_2,))
cloud_conn.commit()
cloud_conn.close()
print(f"Cloud: tombstone created (created_at={tombstone_created}) + record deleted: {test_id_2}")

# 第二次同步（拉取云端墓碑到本地）
run_sync()
print("Second sync done (cloud tombstone pulled to local)")

# 验证本地记录被删除
conn = sqlite3.connect(LOCAL_DB)
row = conn.execute("SELECT id FROM user_values WHERE id = ?", (test_id_2,)).fetchone()
if row is None:
    print(f"✅ Local record deleted (id={test_id_2}) - 反向墓碑同步成功！")
else:
    print(f"❌ Local record still exists (id={test_id_2}) - 反向墓碑同步失败")
conn.close()

# ==================== 清理 ====================
print("\n=== 清理测试数据 ===")
for db_path, label in [(LOCAL_DB, "local"), (CLOUD_DB, "cloud")]:
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM deletion_log WHERE record_id IN (?, ?)", (test_id, test_id_2))
    conn.execute("DELETE FROM user_values WHERE id IN (?, ?)", (test_id, test_id_2))
    conn.commit()
    conn.close()
    print(f"Cleaned {label}")

print("\n=== 测试完成 ===")
