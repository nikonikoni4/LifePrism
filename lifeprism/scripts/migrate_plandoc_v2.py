import sys
import os
from pathlib import Path
import sqlite3

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

# Try to import lw_db_manager, might need environment setup
try:
    from lifeprism.storage import lw_db_manager
except ImportError:
    # Fallback to direct connection if package import fails (e.g. if script run directly)
    # But usually sys.path append handles it.
    print("Could not import lw_db_manager directly. attempting manually.")
    raise

def migrate():
    print("Starting PlanDoc migration...")
    
    try:
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if title column exists
            cursor.execute("PRAGMA table_info(plan_doc)")
            columns = cursor.fetchall()
            has_title = any(col[1] == 'title' for col in columns)
            
            if not has_title:
                print("Migration unnecessary: 'title' column not found.")
                return

            print("Found 'title' column. Proceeding with migration.")
            
            # Create new table
            # Manual definition based on updated config
            create_sql = """
            CREATE TABLE plan_doc_new (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                content TEXT DEFAULT "",
                status TEXT DEFAULT "active",
                order_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (goal_id) REFERENCES goal(id) ON DELETE CASCADE
            );
            """
            cursor.execute(create_sql)
            
            # Copy data
            # old schema had: id, goal_id, title, content, status, order_index, created_at, updated_at
            # new schema has: id, goal_id,          content, status, order_index, created_at, updated_at
            
            cursor.execute("""
                INSERT INTO plan_doc_new (id, goal_id, content, status, order_index, created_at, updated_at)
                SELECT id, goal_id, content, status, order_index, created_at, updated_at FROM plan_doc
            """)
            
            row_count = cursor.rowcount
            print(f"Copied {row_count} rows.")
            
            # Drop old table
            cursor.execute("DROP TABLE plan_doc")
            
            # Rename new table
            cursor.execute("ALTER TABLE plan_doc_new RENAME TO plan_doc")
            
            # Recreate indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_doc_goal_id ON plan_doc(goal_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_doc_status ON plan_doc(status)")
            
            print("Migration completed successfully.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        # Connection context manager will rollback if error raised within it?
        # sqlite3 default context manager commits on exit, but we might need explicit handling if exception caught here.
        # Actually lw_db_manager.get_connection() likely returns a connection where we can handle transaction.
        # If it uses standard sqlite3, exception propagates.
        raise e

if __name__ == "__main__":
    migrate()
