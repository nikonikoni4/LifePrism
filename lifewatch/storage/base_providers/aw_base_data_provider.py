"""
ActivityWatch 基础数据提供者
封装 AW 数据库的通用表操作，供各模块继承使用
"""
import json
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import pytz

from lifewatch.config import WINDOW_BUCKET_ID, LOCAL_TIMEZONE

logger = logging.getLogger(__name__)


class AWBaseDataProvider:
    """
    ActivityWatch 基础数据提供者
    
    特点：
    - 内置全局单例，简化继承类的初始化
    - 提供 AW 数据库的只读操作
    - 各模块继承此类即可使用
    """
    
    def __init__(self, db_manager=None):
        """
        初始化基础数据提供者
        
        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        if db_manager is None:
            from lifewatch.storage import aw_db_manager
            self.db = aw_db_manager
        else:
            self.db = db_manager
        
        self.local_tz = pytz.timezone(LOCAL_TIMEZONE)
        self.utc_tz = timezone.utc
        
        # 验证数据库路径存在
        self._validate_database()
    
    def _validate_database(self):
        """验证数据库文件是否存在"""
        if not os.path.exists(self.db.DB_PATH):
            raise FileNotFoundError(
                f"ActivityWatch 数据库文件不存在: {self.db.DB_PATH}\n"
                f"请检查配置文件中的 ACTIVITYWATCH_DATABASE_PATH 是否正确"
            )
    
    # ==================== 时间转换工具 ====================
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """解析 ISO 时间戳字符串"""
        if '+00:00' in timestamp_str or 'Z' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(timestamp_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=self.utc_tz)
        return dt
    
    def _utc_to_local(self, utc_dt: datetime) -> datetime:
        """将 UTC 时间转换为本地时间"""
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=self.utc_tz)
        return utc_dt.astimezone(self.local_tz)
    
    def _local_to_utc(self, local_dt: datetime) -> datetime:
        """将本地时间转换为 UTC 时间"""
        if isinstance(local_dt, str):
            local_dt = datetime.fromisoformat(local_dt)
        
        if local_dt.tzinfo is None:
            local_dt = local_dt.replace(tzinfo=self.local_tz)
        
        return local_dt.astimezone(self.utc_tz)
    
    # ==================== Bucket 操作 ====================
    
    def get_buckets(self, bucket_type: Optional[str] = None) -> List[Dict]:
        """
        获取存储桶列表
        
        Args:
            bucket_type: 桶类型过滤，如 'currentwindow', 'afkstatus'
            
        Returns:
            List[Dict]: 存储桶列表
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            if bucket_type:
                cursor.execute(
                    "SELECT * FROM bucketmodel WHERE type = ?",
                    (bucket_type,)
                )
            else:
                cursor.execute("SELECT * FROM bucketmodel")
            
            buckets = []
            for row in cursor.fetchall():
                bucket = {
                    'id': row['key'],
                    'key': row['id'],
                    'name': row['name'],
                    'type': row['type'],
                    'client': row['client'],
                    'hostname': row['hostname'],
                    'created': row['created']
                }
                buckets.append(bucket)
            
            return buckets
    
    # ==================== 事件获取 ====================
    
    def get_window_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        hours: Optional[int] = None
    ) -> List[Dict]:
        """
        获取窗口事件
        
        Args:
            start_time: 开始时间（本地时间）
            end_time: 结束时间（本地时间）
            hours: 获取最近 N 小时的数据
            
        Returns:
            List[Dict]: 窗口事件列表
        """
        # 处理时间参数
        if hours:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
        elif not start_time or not end_time:
            raise ValueError("必须提供 start_time 和 end_time，或 hours 参数")
        
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        # 将本地时间转换为 UTC
        start_utc = self._local_to_utc(start_time)
        end_utc = self._local_to_utc(end_time)
        
        start_time_str = start_utc.isoformat().replace('T', ' ')
        end_time_str = end_utc.isoformat().replace('T', ' ')
        
        logger.info(f"获取窗口事件(UTC): {start_time_str} ~ {end_time_str}")
        
        # 获取 window bucket key
        bucket_key = self._get_bucket_key_by_type('currentwindow')
        
        if not bucket_key:
            buckets = self.get_buckets()
            for bucket in buckets:
                if bucket['key'].startswith(WINDOW_BUCKET_ID):
                    bucket_key = bucket['key']
                    break
        
        if not bucket_key:
            logger.warning("未找到窗口事件存储桶")
            return []
        
        events = self._get_events(bucket_key, start_time_str, end_time_str)
        logger.info(f"获取到 {len(events)} 个窗口事件")
        
        return events
    
    def _get_bucket_key_by_type(self, bucket_type: str) -> Optional[str]:
        """根据类型获取第一个匹配的 bucket key"""
        buckets = self.get_buckets(bucket_type=bucket_type)
        if buckets:
            return buckets[0]['key']
        return None
    
    def _get_events(
        self,
        bucket_key: str,
        start_time: str,
        end_time: str,
        limit: int = 10000
    ) -> List[Dict]:
        """获取指定存储桶的事件数据"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT key FROM bucketmodel WHERE id = ?", (bucket_key,))
            bucket_row = cursor.fetchone()
            
            if not bucket_row:
                logger.warning(f"未找到存储桶: {bucket_key}")
                return []
            
            bucket_id = bucket_row['key']
            
            query = """
                SELECT id, timestamp, duration, datastr
                FROM eventmodel
                WHERE bucket_id = ?
                AND timestamp >= ?
                AND timestamp < ?
                ORDER BY timestamp DESC LIMIT ?
            """
            params = [bucket_id, start_time, end_time, limit]
            
            cursor.execute(query, params)
            
            events = []
            for row in cursor.fetchall():
                timestamp_utc = self._parse_timestamp(row['timestamp'])
                data = json.loads(row['datastr']) if row['datastr'] else {}
                
                event = {
                    'id': row['id'],
                    'timestamp': timestamp_utc.isoformat(),
                    'duration': row['duration'],
                    'data': data
                }
                events.append(event)
            
            return events
