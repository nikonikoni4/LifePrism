import unittest
import os
import sqlite3
import tempfile
from datetime import datetime
from lifeprism.monitor.windows_monitor.storage import Storage

class TestStorage(unittest.TestCase):
    def setUp(self):
        # 创建一个临时文件用于测试数据库
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.storage = Storage(self.db_path)

    def tearDown(self):
        # 关闭连接并删除临时数据库文件
        self.storage.close()
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_init_db(self):
        """验证数据库和表是否正确初始化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='window_events';")
        table_exists = cursor.fetchone()
        self.assertIsNotNone(table_exists)
        conn.close()

    def test_save_event(self):
        """验证保存事件并读取的正确性"""
        timestamp = datetime.now().isoformat()
        duration = 5.0
        app = "test_app.exe"
        title = "Test Window Title"

        self.storage.save_event(timestamp, duration, app, title)

        # 读取验证
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, duration, app, title FROM window_events")
        row = cursor.fetchone()

        self.assertEqual(row[0], timestamp)
        self.assertEqual(row[1], duration)
        self.assertEqual(row[2], app)
        self.assertEqual(row[3], title)
        conn.close()

if __name__ == '__main__':
    unittest.main()
