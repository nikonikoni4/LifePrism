#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ActivityWatch 数据库直接读取器
直接从 ActivityWatch SQLite 数据库读取数据,替代 API 方式,提升性能
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
import pytz

from lifewatch.config import WINDOW_BUCKET_ID, LOCAL_TIMEZONE

logger = logging.getLogger(__name__)


class ActivityWatchDBReader:
    """
    ActivityWatch 数据库读取器
    
    直接从 SQLite 数据库读取 ActivityWatch 数据,提供与 API 相同的接口
    优势:
    - 性能更好(无网络请求开销)
    - 独立性强(不需要 AW 服务运行)
    - 灵活查询(可自定义 SQL 优化)
    """
    
    def __init__(self, db_path: str, local_tz: str = LOCAL_TIMEZONE):
        """
        初始化数据库读取器
        
        Args:
            db_path: ActivityWatch 数据库路径(必需)
            local_tz: 本地时区,默认 'Asia/Shanghai'
        """
        self.db_path = db_path
        self.local_tz = pytz.timezone(local_tz)
        self.utc_tz = timezone.utc
        
        # 验证数据库文件存在
        self._validate_database()
        
        logger.info(f"初始化 ActivityWatch 数据库读取器: {self.db_path}")
    
    def _validate_database(self):
        """验证数据库文件是否存在且可访问"""
        import os
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"ActivityWatch 数据库文件不存在: {self.db_path}\n"
                f"请检查配置文件中的 ACTIVITYWATCH_DATABASE_PATH 是否正确"
            )
        
        # 尝试连接数据库
        try:
            conn = sqlite3.connect(self.db_path)
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"无法连接到 ActivityWatch 数据库: {e}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接(只读模式)
        
        Returns:
            sqlite3.Connection: 数据库连接对象
        """
        # 使用只读模式打开数据库,避免意外修改
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row  # 使用字典式访问
        return conn
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        解析 ISO 时间戳字符串
        
        Args:
            timestamp_str: ISO 格式时间戳
            
        Returns:
            datetime: 带时区的 datetime 对象
        """
        # ActivityWatch 数据库中的时间戳是 UTC 时间
        if '+00:00' in timestamp_str or 'Z' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(timestamp_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=self.utc_tz)
        return dt
    
    def _utc_to_local(self, utc_dt: datetime) -> datetime:
        """
        将 UTC 时间转换为本地时间
        
        Args:
            utc_dt: UTC datetime 对象
            
        Returns:
            datetime: 本地时区 datetime 对象
        """
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=self.utc_tz)
        return utc_dt.astimezone(self.local_tz)
    
    def _local_to_utc(self, local_dt: datetime) -> datetime:
        """
        将本地时间转换为 UTC 时间
        
        Args:
            local_dt: 本地 datetime 对象
            
        Returns:
            datetime: UTC datetime 对象
        """
        if isinstance(local_dt, str):
            local_dt = datetime.fromisoformat(local_dt)
        
        if local_dt.tzinfo is None:
            local_dt = local_dt.replace(tzinfo=self.local_tz)
        
        return local_dt.astimezone(self.utc_tz)
    
    def get_buckets(self, bucket_type: Optional[str] = None) -> List[Dict]:
        """
        获取存储桶列表
        
        Args:
            bucket_type: 桶类型过滤,如 'currentwindow', 'afkstatus', 'web.tab.current'
            
        Returns:
            List[Dict]: 存储桶列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if bucket_type:
                cursor.execute(
                    "SELECT * FROM bucketmodel WHERE type = ?",
                    (bucket_type,)
                )
            else:
                cursor.execute("SELECT * FROM bucketmodel")
            
            buckets = []
            for row in cursor.fetchall():
                # 注意: 数据库中列名似乎是反的/特殊的
                # id 列存储的是 string key (如 aw-watcher-window_nico)
                # key 列存储的是 integer ID (如 1, 2)
                bucket = {
                    'id': row['key'],      # Integer ID
                    'key': row['id'],      # String Key
                    'name': row['name'],
                    'type': row['type'],
                    'client': row['client'],
                    'hostname': row['hostname'],
                    'created': row['created']
                }
                buckets.append(bucket)
            
            return buckets
        
        finally:
            conn.close()
    
    def get_events(
        self,
        bucket_key: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 10000
    ) -> List[Dict]:
        """
        获取指定存储桶的事件数据
        
        Args:
            bucket_key: 存储桶 key (如 'aw-watcher-window_...')
            start_time: 开始时间(本地时间)
            end_time: 结束时间(本地时间)
            limit: 最大返回数量
            
        Returns:
            List[Dict]: 事件列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取 bucket_id (Integer)
            # 注意: 查询 id 列(String Key) 来获取 key 列(Integer ID)
            cursor.execute("SELECT key FROM bucketmodel WHERE id = ?", (bucket_key,))
            bucket_row = cursor.fetchone()
            
            if not bucket_row:
                logger.warning(f"未找到存储桶: {bucket_key}")
                return []
            
            bucket_id = bucket_row['key']
            
            # 构建查询
            query = """
                SELECT id, timestamp, duration, datastr
                FROM eventmodel
                WHERE bucket_id = ?
            """
            params = [bucket_id]
            
            # 添加时间范围过滤
            if start_time:
                start_utc = self._local_to_utc(start_time)
                query += " AND timestamp >= ?"
                params.append(start_utc.isoformat())
            
            if end_time:
                end_utc = self._local_to_utc(end_time)
                query += " AND timestamp < ?"
                params.append(end_utc.isoformat())
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            # 解析事件
            events = []
            for row in cursor.fetchall():
                # 解析时间戳
                timestamp_utc = self._parse_timestamp(row['timestamp'])
                timestamp_local = self._utc_to_local(timestamp_utc)
                
                # 解析数据
                data = json.loads(row['datastr']) if row['datastr'] else {}
                
                # 构建事件对象(与 API 格式保持一致)
                event = {
                    'id': row['id'],
                    'timestamp': timestamp_utc.isoformat(),  # 保持 UTC 格式
                    'duration': row['duration'],
                    'data': data
                }
                
                events.append(event)
            
            return events
        
        finally:
            conn.close()
    
    def _get_bucket_key_by_type(self, bucket_type: str) -> Optional[str]:
        """
        根据类型获取第一个匹配的 bucket key
        
        Args:
            bucket_type: 桶类型
            
        Returns:
            Optional[str]: bucket key,如果未找到返回 None
        """
        buckets = self.get_buckets(bucket_type=bucket_type)
        if buckets:
            return buckets[0]['key']
        return None
    
    def get_window_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        hours: Optional[int] = None
    ) -> List[Dict]:
        """
        获取窗口事件(currentwindow)
        
        Args:
            start_time: 开始时间(本地时间)
            end_time: 结束时间(本地时间)
            hours: 获取最近 N 小时的数据(如果未指定 start_time 和 end_time)
            
        Returns:
            List[Dict]: 窗口事件列表
        """
        # 处理时间参数
        if hours:
            # 使用 UTC 时间
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
        elif not start_time or not end_time:
            raise ValueError("必须提供 start_time 和 end_time,或 hours 参数")
        
        # 确保时间是 UTC
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        else:
            start_time = start_time.astimezone(timezone.utc)
            
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        else:
            end_time = end_time.astimezone(timezone.utc)
            
        logger.info(f"获取窗口事件(UTC): {start_time} ~ {end_time}")
        
        # 获取 window bucket key
        bucket_key = self._get_bucket_key_by_type('currentwindow')
        
        if not bucket_key:
            # 尝试使用配置的 bucket ID 前缀
            buckets = self.get_buckets()
            for bucket in buckets:
                if bucket['key'].startswith(WINDOW_BUCKET_ID):
                    bucket_key = bucket['key']
                    break
        
        if not bucket_key:
            logger.warning("未找到窗口事件存储桶")
            return []
        
        events = self.get_events(bucket_key, start_time, end_time)
        logger.info(f"获取到 {len(events)} 个窗口事件")
        
        return events
    
    def get_afk_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        hours: Optional[int] = None
    ) -> List[Dict]:
        """
        获取 AFK(Away From Keyboard)事件
        
        Args:
            start_time: 开始时间(本地时间)
            end_time: 结束时间(本地时间)
            hours: 获取最近 N 小时的数据
            
        Returns:
            List[Dict]: AFK 事件列表
        """
        # 处理时间参数
        if hours:
            end_time = datetime.now(self.local_tz)
            start_time = end_time - timedelta(hours=hours)
        elif not start_time or not end_time:
            raise ValueError("必须提供 start_time 和 end_time,或 hours 参数")
        
        logger.info(f"获取 AFK 事件: {start_time} ~ {end_time}")
        
        # 获取 afk bucket key
        bucket_key = self._get_bucket_key_by_type('afkstatus')
        
        if not bucket_key:
            logger.warning("未找到 AFK 事件存储桶")
            return []
        
        events = self.get_events(bucket_key, start_time, end_time)
        logger.info(f"获取到 {len(events)} 个 AFK 事件")
        
        return events
    
    def get_browser_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        hours: Optional[int] = None
    ) -> List[Dict]:
        """
        获取浏览器事件(web.tab.current)
        
        Args:
            start_time: 开始时间(本地时间)
            end_time: 结束时间(本地时间)
            hours: 获取最近 N 小时的数据
            
        Returns:
            List[Dict]: 浏览器事件列表
        """
        # 处理时间参数
        if hours:
            end_time = datetime.now(self.local_tz)
            start_time = end_time - timedelta(hours=hours)
        elif not start_time or not end_time:
            raise ValueError("必须提供 start_time 和 end_time,或 hours 参数")
        
        logger.info(f"获取浏览器事件: {start_time} ~ {end_time}")
        
        # 获取 browser bucket key
        bucket_key = self._get_bucket_key_by_type('web.tab.current')
        
        if not bucket_key:
            logger.warning("未找到浏览器事件存储桶")
            return []
        
        events = self.get_events(bucket_key, start_time, end_time)
        logger.info(f"获取到 {len(events)} 个浏览器事件")
        
        return events


# 便捷函数,用于快速获取窗口事件
def get_window_events_from_db(
    db_path: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    hours: int = 1
) -> List[Dict]:
    """
    从数据库获取窗口事件的便捷函数
    
    Args:
        db_path: ActivityWatch 数据库路径
        start_time: 开始时间
        end_time: 结束时间
        hours: 最近 N 小时(默认 1)
        
    Returns:
        List[Dict]: 窗口事件列表
    """
    reader = ActivityWatchDBReader(db_path=db_path)
    return reader.get_window_events(start_time, end_time, hours)


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("ActivityWatch 数据库读取器测试")
    print("=" * 60)
    
    # 指定数据库路径
    db_path = r"C:\Users\15535\AppData\Local\activitywatch\activitywatch\aw-server\peewee-sqlite.v2.db"
    
    try:
        reader = ActivityWatchDBReader(db_path=db_path)
        
        # 测试获取 buckets
        print("\n1. 获取存储桶列表:")
        buckets = reader.get_buckets()
        for bucket in buckets:
            print(f"   - {bucket['key']} ({bucket['type']})")
        
        # 测试获取窗口事件
        print("\n2. 获取最近 1 小时的窗口事件:")
        events = reader.get_window_events(hours=1)
        print(f"   获取到 {len(events)} 个事件")
        
        if events:
            print("\n   最新事件示例:")
            event = events[0]
            print(f"   - 时间: {event['timestamp']}")
            print(f"   - 持续: {event['duration']:.2f} 秒")
            print(f"   - 应用: {event['data'].get('app', 'N/A')}")
            print(f"   - 标题: {event['data'].get('title', 'N/A')[:50]}...")
        
        print("\n✅ 测试完成!")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
