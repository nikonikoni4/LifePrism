import unittest
import os
from datetime import datetime
from lifeprism.storage.database_manager import DatabaseManager
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider
from lifeprism.storage.lw_table_manager import LWTableManager

class TestMonitorDataProvider(unittest.TestCase):
    def setUp(self):
        # 使用临时文件数据库进行测试，避免内存数据库连接重置问题
        self.test_db_path = "test_temp.db"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

        self.db_manager = DatabaseManager(DB_PATH=self.test_db_path)

        # 初始化数据库表结构
        self.table_manager = LWTableManager(db_manager=self.db_manager)
        self.table_manager.init_database()

        # 初始化 Provider
        self.provider = MonitorDataProvider(db_manager=self.db_manager)

    def tearDown(self):
        # 清理测试数据库
        if hasattr(self, 'db_manager'):
            # 如果使用了连接池，需要关闭（虽然目前 DatabaseManager 在内存中处理池，但文件句柄可能还在）
            pass
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except:
                pass

    def test_save_event(self):
        # 测试数据
        timestamp = datetime.now().isoformat()
        duration = 60.5
        app = "test_app.exe"
        title = "Test Window Title"

        # 执行保存
        result = self.provider.save_event(timestamp, duration, app, title)

        # 验证返回值为 True (表示成功)
        self.assertTrue(result)

        # 验证数据库中是否存在该记录
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM window_events WHERE app = ? AND title = ?", (app, title))
            row = cursor.fetchone()

            self.assertIsNotNone(row)
            self.assertEqual(row['timestamp'], timestamp)
            self.assertEqual(row['duration'], duration)
            self.assertEqual(row['app'], app)
            self.assertEqual(row['title'], title)

if __name__ == '__main__':
    unittest.main()