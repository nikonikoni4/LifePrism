#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ActivityWatch指定时间段数据访问脚本
功能：访问指定时间段的数据，并进行时间戳分析
集成功能：时间戳格式分析、时区转换、事件详细分析
"""

import requests
from datetime import datetime, timedelta, timezone
import pytz
from lifewatch.config import WINDOW_BUCKET_ID
class ActivityWatchTimeRangeAccessor:
    def __init__(self, base_url="http://localhost:5600", local_tz='Asia/Shanghai',headers=None):
        self.base_url = base_url
        self.headers = headers 
        
        # 时间戳分析相关设置
        self.local_tz = pytz.timezone(local_tz)  # UTC+8
        self.utc_tz = timezone.utc
    
    def parse_timestamp(self, timestamp_str):
        """解析ISO时间戳字符串"""
        # 处理带时区的ISO格式
        if '+00:00' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt
        else:
            # 如果没有时区信息，假设为UTC
            dt = datetime.fromisoformat(timestamp_str)
            return dt.replace(tzinfo=self.utc_tz)
    
    def convert_to_local(self, dt):
        """将UTC时间转换为本地时间"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.utc_tz)
        return dt.astimezone(self.local_tz)
    
    def utc_to_local(self, utc_time_input):
        """将UTC时间字符串或datetime对象转换为本地区时间"""
        if isinstance(utc_time_input, str):
            dt_utc = self.parse_timestamp(utc_time_input)
        elif hasattr(utc_time_input, 'replace'):  # datetime对象
            dt_utc = utc_time_input
        else:
            return None
            
        if dt_utc is None:
            return None
            
        dt_local = self.convert_to_local(dt_utc)
        return dt_local
    
    def local_to_utc(self, local_time):
        """将本地时间转换为UTC时间"""
        if isinstance(local_time, str):
            local_time = datetime.fromisoformat(local_time)
        
        # 添加本地时区信息
        if local_time.tzinfo is None:
            local_time = local_time.replace(tzinfo=self.local_tz)
        
        # 转换为UTC
        return local_time.astimezone(timezone.utc)
    
    def check_server_status(self):
        """检查ActivityWatch服务器状态"""
        try:
            response = requests.get(f"{self.base_url}/api/0/info", timeout=5)
            if response.status_code == 200:
                server_info = response.json()
                print("✅ ActivityWatch服务器连接成功")
                print(f"   服务器版本: {server_info.get('version', 'Unknown')}")
                print(f"   服务器URL: {self.base_url}")
                return True
            else:
                print(f"❌ 服务器响应异常: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print("❌ 无法连接到ActivityWatch服务器")
            print("请确保ActivityWatch服务正在运行:")
            print("  - 启动aw-qt图形界面, 或")
            print("  - 运行命令: python -m aw_server.main")
            return False
        except Exception as e:
            print(f"❌ 连接错误: {e}")
            return False
    
    
    def get_time_range_data(self, 
                            start_time=None, 
                            end_time=None, 
                            hours=None):

        """
        获取指定时间段的数据并进行时间戳分析
        
        Args:
            start_time: 开始时间 (datetime对象或字符串, 可选)
            end_time: 结束时间 (datetime对象或字符串, 可选)  
            hours: 获取最近N小时的数据 (int, 可选)
        Returns:
            dict: 包含原始数据、时间戳分析、特定事件等完整信息
        """
        # 处理时间参数
        if hours:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
        elif not start_time or not end_time:
            raise ValueError("必须提供start_time和end_time，或hours参数")
        
        # 格式化时间
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        # 🔧 关键修正：API请求需要UTC时间，所以将本地时间转换为UTC
        start_utc = self.local_to_utc(start_time)
        end_utc = self.local_to_utc(end_time)
        
        start_iso = start_utc.isoformat()
        end_iso = end_utc.isoformat()
        
        print(f"\n📊 正在获取时间段数据...")
        print(f"   开始时间: {start_iso}")
        print(f"   结束时间: {end_iso}")
        print(f"   时间跨度: {(end_time - start_time).total_seconds()} 秒")

        
        # 初始化结果容器
        result = {
            'time_range': {
                'start': start_iso,
                'end': end_iso,
                'duration_seconds': (end_time - start_time).total_seconds()
            },
            'buckets': {},
            'events_by_bucket': {},
            'timestamp_analysis': {},
            'summary': {}
        }
        
        # 1. 获取所有bucket信息
        print("\n🔍 步骤1: 获取所有数据容器...")
        try:
            buckets_response = requests.get(
                f"{self.base_url}/api/0/buckets",
                headers=self.headers,
                timeout=10
            )
            
            if buckets_response.status_code != 200:
                print(f"❌ 获取bucket失败: {buckets_response.status_code}")
                return result
            
            buckets = buckets_response.json()
            result['buckets'] = buckets
            print(f"✅ 发现 {len(buckets)} 个数据容器:")
            
            for bucket_id, bucket_info in buckets.items():
                print(f"   📦 {bucket_id} ({bucket_info.get('type', 'unknown')})")
            
        except Exception as e:
            print(f"❌ 获取bucket信息失败: {e}")
            return result
        
        # 2. 步骤2: 获取事件数据并修改时间戳时区
        print("\n🔍 步骤2: 获取事件数据并修改时间戳时区")
        
        total_events = 0
        window_events_nums = 0  # 收集所有窗口事件用于后续分析
        
        for bucket_id in buckets.keys():
            try:
                # 构建请求参数
                params = {
                    'start': start_iso,
                    'end': end_iso,
                    'limit': 10000  # 设置一个较大的限制
                }
                
                events_response = requests.get(
                    f"{self.base_url}/api/0/buckets/{bucket_id}/events",
                    params=params,
                    headers=self.headers,
                    timeout=15
                )
                
                if events_response.status_code == 200:
                    events = events_response.json()
                    result['events_by_bucket'][bucket_id] = events
                    total_events += len(events)
                    if bucket_id.startswith(WINDOW_BUCKET_ID):
                        window_events_nums = len(events)
                else:
                    print(f"   ❌ {bucket_id}: 获取失败 ({events_response.status_code})")
                    result['events_by_bucket'][bucket_id] = []
                    
            except Exception as e:
                print(f"   ❌ {bucket_id}: 错误 - {e}")
                result['events_by_bucket'][bucket_id] = []
        # 4. 生成汇总信息
        result['summary'] = {
            'total_buckets': len(buckets),
            'total_events': total_events,
            'window_events_count': window_events_nums
        }
        
        # 5. 显示完整分析结果
        print(f"\n📋 数据获取与分析完成!")
        print(f"   时间范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   数据容器: {result['summary']['total_buckets']} 个")
        print(f"   总事件数: {result['summary']['total_events']} 个")
        print(f"   窗口事件数: {result['summary']['window_events_count']} 个")
        
        return result
    
    def get_window_events(self,start_time=None,end_time=None,hours=1):
        """从事件数据中提取窗口事件"""
        result = self.get_time_range_data(start_time,end_time,hours)
        for bucket_id, events in result['events_by_bucket'].items():
            if bucket_id.startswith(WINDOW_BUCKET_ID):
                window_events = events
                break
        else:
            window_events = []
        return window_events
# 测试用
def get_window_events(start_time=None, end_time=None, hours=None, use_database=True, aw_LW_DB_PATH=None):
    """
    从事件数据中提取窗口事件
    
    Args:
        start_time: 开始时间
        end_time: 结束时间
        hours: 获取最近 N 小时的数据
        use_database: 是否使用数据库模式(默认 True,性能更好)
        aw_LW_DB_PATH: ActivityWatch 数据库路径(仅在 use_database=True 时需要)
    
    Returns:
        list: 窗口事件列表
    """
    if use_database:
        # 使用数据库模式
        from lifewatch.data.aw_db_reader import ActivityWatchDBReader
        
        if not aw_LW_DB_PATH:
            # 默认数据库路径
            aw_LW_DB_PATH = r"C:\Users\15535\AppData\Local\activitywatch\activitywatch\aw-server\peewee-sqlite.v2.db"
        
        reader = ActivityWatchDBReader(LW_DB_PATH=aw_LW_DB_PATH)
        window_events = reader.get_window_events(start_time, end_time, hours)
    else:
        # 使用 API 模式(向后兼容)
        aw_accessor = ActivityWatchTimeRangeAccessor(
            base_url="http://localhost:5600",
            local_tz="Asia/Shanghai"
        )
        result = aw_accessor.get_time_range_data(start_time, end_time, hours)
        
        for bucket_id, events in result['events_by_bucket'].items():
            if bucket_id.startswith(WINDOW_BUCKET_ID):
                window_events = events
                break
        else:
            window_events = []
    
    return window_events

if __name__ == "__main__":
    # 测试代码
    aw_accessor = ActivityWatchTimeRangeAccessor(
        base_url="http://localhost:5600",
        local_tz="Asia/Shanghai"
    )
    user_behavior_logs = aw_accessor.get_window_events(hours=1)
    print(user_behavior_logs[0])
