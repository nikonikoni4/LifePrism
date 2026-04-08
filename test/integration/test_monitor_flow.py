import unittest
import os
from datetime import datetime
from lifeprism.storage.database_manager import DatabaseManager
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider
from lifeprism.storage.lw_table_manager import LWTableManager

class TestMonitorFlow(unittest.TestCase):
    def setUp(self):
        self.test_db_path = "test_integration_temp.db"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

        self.db_manager = DatabaseManager(DB_PATH=self.test_db_path)
        self.table_manager = LWTableManager(db_manager=self.db_manager)
        self.table_manager.init_database()
        self.provider = MonitorDataProvider(db_manager=self.db_manager)

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_save_window_event_flow(self):
        """模拟 WindowMonitor 保存数据的完整流程"""
        event_timestamp = datetime.now().isoformat()
        event_app = "TestApp"
        event_title = "Test Title"
        event_duration = 5.0

        # 1. 保存数据
        success = self.provider.save_event(
            timestamp=event_timestamp,
            duration=event_duration,
            app=event_app,
            title=event_title
        )
        self.assertTrue(success)

        # 2. 验证数据是否存在
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM window_events WHERE app = ?", (event_app,))
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['timestamp'], event_timestamp)
            self.assertEqual(row['app'], event_app)
            self.assertEqual(row['title'], event_title)
            self.assertEqual(row['duration'], event_duration)
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='screen_captures'"
            )
            self.assertIsNotNone(cursor.fetchone())

if __name__ == "__main__":
    unittest.main()
