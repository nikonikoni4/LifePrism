import sqlite3
import logging
from typing import Optional
# from lifeprism.utils.logger import get_logger

# logger = get_logger(__name__)
import logging
logger = logging.getLogger()
class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.init_db()

    def init_db(self):
        """
        初始化数据库，创建 window_events 表。
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS window_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    duration REAL NOT NULL,
                    app TEXT,
                    title TEXT
                )
            ''')
            self.conn.commit()
            logger.info(f"数据库初始化完成: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"初始化数据库失败: {e}")
            raise

    def save_event(self, timestamp: str, duration: float, app: str, title: str):
        """
        插入一条新的窗口事件记录。
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO window_events (timestamp, duration, app, title)
                VALUES (?, ?, ?, ?)
            ''', (timestamp, duration, app, title))
            self.conn.commit()
            logger.debug(f"保存事件: {app} - {title}")
        except sqlite3.Error as e:
            logger.error(f"保存事件失败: {e}")
            raise

    def close(self):
        """
        关闭数据库连接。
        """
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")
