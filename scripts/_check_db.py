"""检查主仓库 DB 状态"""

import sqlite3

conn = sqlite3.connect("localData/dataset/lifewatch_ai.db")

tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
diary = conn.execute("SELECT count(*) FROM diary").fetchone()[0]
mood = conn.execute("SELECT count(*) FROM mood_entries").fetchone()[0]
crt = conn.execute("SELECT count(*) FROM custom_record_types").fetchone()[0]
goal = conn.execute("SELECT count(*) FROM goal").fetchone()[0]
session_files = conn.execute(
    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name LIKE 'session_%'"
).fetchone()[0]

print(f"总表数: {tables}")
print(f"diary: {diary} 条")
print(f"mood_entries: {mood} 条")
print(f"custom_record_types: {crt} 条")
print(f"goal: {goal} 条")
print(f"session_ 表: {session_files} 个")

conn.close()
