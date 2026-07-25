"""检查云端数据库迁移状态"""
import os
import sqlite3

path = "explore/LifePrism/localData/dataset/lifewatch_ai.db"
print(f"DB path: {path}")
print(f"Exists: {os.path.exists(path)}")
if os.path.exists(path):
    print(f"Size: {os.path.getsize(path)} bytes")
    conn = sqlite3.connect(path)
    c = conn.cursor()

    # schema_version
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    sv = c.fetchone() is not None
    print(f"schema_version table exists: {sv}")
    if sv:
        c.execute("SELECT MAX(version) FROM schema_version")
        print(f"Current version: {c.fetchone()[0]}")

    # timeline_custom_block columns
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timeline_custom_block'")
    if c.fetchone():
        c.execute("PRAGMA table_info(timeline_custom_block)")
        cols = [r[1] for r in c.fetchall()]
        print(f"timeline_custom_block columns: {cols}")
        print(f"  has hash_id: {'hash_id' in cols}")

    # deletion_log table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deletion_log'")
    print(f"deletion_log table exists: {c.fetchone() is not None}")

    # custom_record_types
    c.execute("SELECT COUNT(*) FROM custom_record_types")
    print(f"custom_record_types count: {c.fetchone()[0]}")

    conn.close()
else:
    print("DB does not exist - cloud has not been initialized yet")
