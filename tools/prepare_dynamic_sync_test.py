"""
动态表双向同步测试 —— 环境准备脚本

用法:
    python tools/prepare_dynamic_sync_test.py

功能:
    1. 清理本地 DB（localData/dataset/lifewatch_ai.db）的动态表和定义表
    2. 本地创建 "exercise_log"（运动记录），插入 2 条数据
    3. 清理云端 DB（explore/LifePrism/localData/dataset/lifewatch_ai.db）的动态表和定义表
    4. 云端创建 "reading_log"（阅读记录），插入 2 条数据

完成后手动测试:
    1. 先启动云端: 在 explore/LifePrism 目录下 python -m lifeprism.server.main
    2. 再启本地: 在项目根目录下 python -m lifeprism.server.main
    3. 观察双方日志，检查是否:
       - 本地拉到了云端的 reading_log 定义 + 数据
       - 云端收到了本地的 exercise_log 定义 + 数据
       - 不再出现 "重建动态表请求/skipped" 每条同步循环都有的日志

恢复:
    git checkout localData/dataset/lifewatch_ai.db
    git checkout explore/LifePrism/localData/dataset/lifewatch_ai.db
"""

import sqlite3
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

LOCAL_DB = PROJECT_ROOT / "localData" / "dataset" / "lifewatch_ai.db"
CLOUD_DB = PROJECT_ROOT / "explore" / "LifePrism" / "localData" / "dataset" / "lifewatch_ai.db"

NOW = datetime.now(timezone.utc).isoformat()


def _backup(db_path: Path):
    backup_path = db_path.with_suffix(f".backup-dynamic-sync-test{db_path.suffix}")
    shutil.copy2(db_path, backup_path)
    print(f"  备份: {db_path.name} -> {backup_path.name}")


def _cleanup_custom_tables(db_path: Path):
    """删除所有动态表和定义表"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 1. 找到所有 custom_ 开头的动态数据表
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'custom_%' "
        "AND name NOT IN ('custom_record_types', 'custom_record_fields')"
    )
    dynamic_tables = [row[0] for row in cursor.fetchall()]
    for t in dynamic_tables:
        cursor.execute(f"DROP TABLE IF EXISTS {t}")
        print(f"  删除动态表: {t}")

    # 2. 清空定义表（meta）
    cursor.execute("DELETE FROM custom_record_fields")
    cursor.execute("DELETE FROM custom_record_types")
    conn.commit()
    conn.close()
    print(f"  清空 custom_record_types + custom_record_fields")


def _create_custom_type(db_path: Path, type_id: str, name: str, slug: str,
                        fields: list[dict], rows: list[dict]):
    """创建自定义记录类型定义 + 数据表 + 插入数据"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 1. 插入类型定义
    cursor.execute(
        "INSERT INTO custom_record_types (id, name, slug, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (type_id, name, slug, "", NOW, NOW),
    )

    # 2. 插入字段定义
    for sort_order, f in enumerate(fields, start=1):
        field_id = f"crf-{uuid.uuid4().hex[:8]}"
        cursor.execute(
            "INSERT INTO custom_record_fields "
            "(id, type_id, field_name, field_key, field_type, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (field_id, type_id, f["field_key"], f["field_key"],
             f.get("field_type", "text"), sort_order, NOW, NOW),
        )

    # 3. 生成 DDL 并建表
    data_table = f"custom_{slug}"
    col_defs = ["id TEXT PRIMARY KEY"]
    for f in fields:
        sql_type = {"text": "TEXT", "integer": "INTEGER", "float": "REAL"}.get(
            f.get("field_type", "text"), "TEXT"
        )
        col_defs.append(f"{f['field_key']} {sql_type}")
    col_defs.extend(["event_time TEXT", "created_at TEXT", "updated_at TEXT"])
    ddl = f"CREATE TABLE {data_table} ({', '.join(col_defs)})"
    cursor.execute(ddl)
    print(f"  建表: {data_table} ({len(fields)} 字段)")

    # 4. 插入数据
    for row in rows:
        row.setdefault("event_time", NOW)
        row.setdefault("created_at", NOW)
        row.setdefault("updated_at", NOW)
        columns = list(row.keys())
        placeholders = ", ".join(["?"] * len(columns))
        values = [row[c] for c in columns]
        cursor.execute(
            f"INSERT INTO {data_table} ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )

    conn.commit()
    conn.close()
    print(f"  插入 {len(rows)} 条数据到 {data_table}")


def main():
    print("=" * 60)
    print("动态表双向同步 —— 测试环境准备")
    print(f"时间: {NOW}")
    print("=" * 60)

    # ==================== 本地 DB ====================
    print(f"\n[本地 DB] {LOCAL_DB}")
    _backup(LOCAL_DB)
    _cleanup_custom_tables(LOCAL_DB)

    print("  创建类型: exercise_log（运动记录）...")
    _create_custom_type(
        LOCAL_DB,
        type_id="crt-exercise-001",
        name="运动记录",
        slug="exercise_log",
        fields=[
            {"field_key": "exercise_type", "field_type": "text"},
            {"field_key": "duration_minutes", "field_type": "integer"},
            {"field_key": "calories", "field_type": "integer"},
        ],
        rows=[
            {"id": "ex-local-1", "exercise_type": "跑步", "duration_minutes": 30, "calories": 280},
            {"id": "ex-local-2", "exercise_type": "游泳", "duration_minutes": 45, "calories": 350},
        ],
    )

    # ==================== 云端 DB ====================
    print(f"\n[云端 DB] {CLOUD_DB}")
    _backup(CLOUD_DB)
    _cleanup_custom_tables(CLOUD_DB)

    print("  创建类型: reading_log（阅读记录）...")
    _create_custom_type(
        CLOUD_DB,
        type_id="crt-reading-001",
        name="阅读记录",
        slug="reading_log",
        fields=[
            {"field_key": "book_name", "field_type": "text"},
            {"field_key": "pages_read", "field_type": "integer"},
        ],
        rows=[
            {"id": "rd-cloud-1", "book_name": "三体", "pages_read": 150},
            {"id": "rd-cloud-2", "book_name": "活着", "pages_read": 80},
        ],
    )

    print("\n" + "=" * 60)
    print("环境准备完成！")
    print("=" * 60)
    print("""
测试步骤:
  1. 先启动云端服务器:
     cd explore/LifePrism
     python -m lifeprism.server.main

  2. 等待云端启动完成后，再启动本地服务器:
     cd ../../  （回到项目根目录）
     python -m lifeprism.server.main

  3. 观察本地日志，应看到:
     - _sync_dynamic_tables_definitions: 云端动态表 slug={'reading_log'}
     - _sync_dynamic_tables_definitions: 本地动态表 slug={'exercise_log'}
     - _create_local_dynamic_tables: 本地建表 custom_reading_log
     - 发送动态表重建请求到云端: 1 个类型定义
     - pull 拉到了 cloud reading_log 的数据
     - push 推送了 local exercise_log 的数据

  4. 验证：
     - 本地数据库有 custom_reading_log 表和数据
     - 云端数据库有 custom_exercise_log 表和数据
     - 不再每次同步都出现 "重建动态表完成: skipped" 日志

恢复方法:
  备份文件在同目录下 *.backup-dynamic-sync-test.db，复制覆盖即可
""")


if __name__ == "__main__":
    main()
