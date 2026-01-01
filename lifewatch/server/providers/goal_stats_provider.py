"""
Goal Stats 数据提供者
提供目标统计数据的查询和懒更新操作
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class GoalStatsProvider(LWBaseDataProvider):
    """
    目标统计数据提供者
    
    继承 LWBaseDataProvider，提供 goal_stats 的查询和更新操作
    支持懒加载：在查询时自动补全缺失日期的统计数据
    """
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    # ==================== 查询操作 ====================
    
    def get_stats_by_goal(self, goal_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """
        获取目标的统计历史数据
        
        Args:
            goal_id: 目标 ID
            limit: 返回最近 N 天的数据
        
        Returns:
            List[Dict]: 统计数据列表，按日期升序排列
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM goal_stats 
                    WHERE goal_id = ?
                    ORDER BY date DESC
                    LIMIT ?
                """, (goal_id, limit))
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                # 返回时按日期升序
                items = [dict(zip(columns, row)) for row in rows]
                items.reverse()
                return items
                
        except Exception as e:
            logger.error(f"获取目标 {goal_id} 统计数据失败: {e}")
            return []
    
    def get_latest_stat_date(self, goal_id: str) -> Optional[str]:
        """
        获取目标统计的最后更新日期
        
        Args:
            goal_id: 目标 ID
        
        Returns:
            Optional[str]: 最后日期 (YYYY-MM-DD)，无数据返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(date) FROM goal_stats WHERE goal_id = ?
                """, (goal_id,))
                
                result = cursor.fetchone()
                return result[0] if result and result[0] else None
                
        except Exception as e:
            logger.error(f"获取目标 {goal_id} 最新统计日期失败: {e}")
            return None
    
    def get_stat_by_date(self, goal_id: str, date: str) -> Optional[Dict[str, Any]]:
        """
        获取指定日期的统计数据
        
        Args:
            goal_id: 目标 ID
            date: 日期 (YYYY-MM-DD)
        
        Returns:
            Optional[Dict]: 统计数据
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM goal_stats 
                    WHERE goal_id = ? AND date = ?
                """, (goal_id, date))
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            logger.error(f"获取目标 {goal_id} 在 {date} 的统计数据失败: {e}")
            return None
    
    # ==================== 更新操作 ====================
    
    def upsert_stat(self, goal_id: str, date: str, time_spent: int, todo_count: int) -> bool:
        """
        插入或更新统计数据
        
        Args:
            goal_id: 目标 ID
            date: 日期 (YYYY-MM-DD)
            time_spent: 花费时间（秒）
            todo_count: 完成的待办数量
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 检查是否已存在
                cursor.execute("""
                    SELECT id FROM goal_stats WHERE goal_id = ? AND date = ?
                """, (goal_id, date))
                
                existing = cursor.fetchone()
                
                if existing:
                    # 更新
                    cursor.execute("""
                        UPDATE goal_stats 
                        SET time_spent = ?, completed_todo_count = ?
                        WHERE goal_id = ? AND date = ?
                    """, (time_spent, todo_count, goal_id, date))
                else:
                    # 插入
                    cursor.execute("""
                        INSERT INTO goal_stats (goal_id, date, time_spent, completed_todo_count)
                        VALUES (?, ?, ?, ?)
                    """, (goal_id, date, time_spent, todo_count))
                
                logger.debug(f"目标 {goal_id} 在 {date} 的统计数据已更新")
                return True
                
        except Exception as e:
            logger.error(f"更新目标 {goal_id} 在 {date} 的统计数据失败: {e}")
            return False
    
    # ==================== 聚合操作 ====================
    
    def aggregate_time_spent_from_behavior_log(self, goal_id: str, date: str) -> int:
        """
        从 user_app_behavior_log 聚合指定日期的时间花费
        
        Args:
            goal_id: 目标 ID
            date: 日期 (YYYY-MM-DD)
        
        Returns:
            int: 花费时间（秒）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 使用日期前缀匹配，避免时区问题
                # start_time 格式可能是: 2025-12-31T14:30:00+08:00
                date_prefix = f"{date}%"
                
                cursor.execute("""
                    SELECT COALESCE(SUM(duration), 0) as total_duration
                    FROM user_app_behavior_log
                    WHERE link_to_goal_id = ?
                      AND start_time LIKE ?
                """, (goal_id, date_prefix))
                
                result = cursor.fetchone()
                total = int(result[0]) if result and result[0] else 0
                logger.debug(f"aggregate_time_spent: goal_id={goal_id}, date={date}, total={total}")
                return total
                
        except Exception as e:
            logger.error(f"聚合目标 {goal_id} 在 {date} 的时间花费失败: {e}")
            return 0
    
    def aggregate_completed_todos(self, goal_id: str, date: str) -> int:
        """
        从 todo_list 统计指定日期完成的待办数量
        
        Args:
            goal_id: 目标 ID
            date: 日期 (YYYY-MM-DD)
        
        Returns:
            int: 完成的待办数量
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM todo_list
                    WHERE link_to_goal_id = ?
                      AND state = 'completed'
                      AND actual_finished_at = ?
                """, (goal_id, date))
                
                result = cursor.fetchone()
                return int(result[0]) if result and result[0] else 0
                
        except Exception as e:
            logger.error(f"统计目标 {goal_id} 在 {date} 完成的待办数量失败: {e}")
            return 0
    
    def sync_stats_to_date(self, goal_id: str, target_date: str, start_date: str = None) -> bool:
        """
        同步统计数据到指定日期
        
        检查最后更新日期，补全缺失的日期数据
        
        Args:
            goal_id: 目标 ID
            target_date: 目标日期 (YYYY-MM-DD)
            start_date: 起始日期 (YYYY-MM-DD)，用于新 reward 时从特定日期开始统计
        
        Returns:
            bool: 是否成功
        """
        try:
            last_date = self.get_latest_stat_date(goal_id)
            logger.debug(f"sync_stats_to_date: goal_id={goal_id}, target_date={target_date}, start_date={start_date}, last_date={last_date}")
            
            target_dt = datetime.strptime(target_date, "%Y-%m-%d")
            
            if last_date is None:
                # 没有历史数据
                if start_date:
                    # 从 start_date 开始同步到 target_date
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    dates_to_sync = []
                    current = start_dt
                    while current <= target_dt:
                        dates_to_sync.append(current.strftime("%Y-%m-%d"))
                        current += timedelta(days=1)
                else:
                    # 只计算今天
                    dates_to_sync = [target_date]
            else:
                # 已有历史数据
                last_dt = datetime.strptime(last_date, "%Y-%m-%d")
                
                # 确定实际的起始日期
                # 如果 start_date 早于 last_date，需要从 start_date 开始补全
                if start_date:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    # 找出最早需要的日期
                    earliest_date = self._get_earliest_stat_date(goal_id)
                    earliest_dt = datetime.strptime(earliest_date, "%Y-%m-%d") if earliest_date else last_dt
                    
                    if start_dt < earliest_dt:
                        # start_date 比现有最早的记录还早，需要向前补全
                        dates_to_sync = []
                        current = start_dt
                        while current < earliest_dt:
                            dates_to_sync.append(current.strftime("%Y-%m-%d"))
                            current += timedelta(days=1)
                        # 再加上从 last_date 之后到 target_date 的日期
                        if last_dt < target_dt:
                            current = last_dt + timedelta(days=1)
                            while current <= target_dt:
                                dates_to_sync.append(current.strftime("%Y-%m-%d"))
                                current += timedelta(days=1)
                        # 最后更新今天
                        if target_date not in dates_to_sync:
                            dates_to_sync.append(target_date)
                    else:
                        # 正常情况：补全从 last_date 之后到 target_date
                        if last_dt >= target_dt:
                            dates_to_sync = [target_date]
                        else:
                            dates_to_sync = []
                            current = last_dt + timedelta(days=1)
                            while current <= target_dt:
                                dates_to_sync.append(current.strftime("%Y-%m-%d"))
                                current += timedelta(days=1)
                else:
                    # 没有 start_date，正常补全
                    if last_dt >= target_dt:
                        dates_to_sync = [target_date]
                    else:
                        dates_to_sync = []
                        current = last_dt + timedelta(days=1)
                        while current <= target_dt:
                            dates_to_sync.append(current.strftime("%Y-%m-%d"))
                            current += timedelta(days=1)
            
            # 同步每个日期的数据
            for date in dates_to_sync:
                time_spent = self.aggregate_time_spent_from_behavior_log(goal_id, date)
                todo_count = self.aggregate_completed_todos(goal_id, date)
                self.upsert_stat(goal_id, date, time_spent, todo_count)
            
            logger.info(f"目标 {goal_id} 同步了 {len(dates_to_sync)} 天的统计数据")
            return True
            
        except Exception as e:
            logger.error(f"同步目标 {goal_id} 统计数据失败: {e}")
            return False
    
    def _get_earliest_stat_date(self, goal_id: str) -> Optional[str]:
        """
        获取目标统计的最早日期
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MIN(date) FROM goal_stats WHERE goal_id = ?
                """, (goal_id,))
                
                result = cursor.fetchone()
                return result[0] if result and result[0] else None
                
        except Exception as e:
            logger.error(f"获取目标 {goal_id} 最早统计日期失败: {e}")
            return None
    
    def get_cumulative_stats(self, goal_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """
        获取累积统计数据（用于图表展示）
        
        Args:
            goal_id: 目标 ID
            limit: 返回最近 N 天的数据
        
        Returns:
            List[Dict]: 累积统计数据
                - date: 日期
                - cumulative_time_spent: 累积时间（秒）
                - cumulative_todo_count: 累积完成数
        """
        stats = self.get_stats_by_goal(goal_id, limit)
        
        cumulative_time = 0
        cumulative_todos = 0
        result = []
        
        for stat in stats:
            cumulative_time += stat.get('time_spent', 0)
            cumulative_todos += stat.get('completed_todo_count', 0)
            result.append({
                'date': stat['date'],
                'cumulative_time_spent': cumulative_time,
                'cumulative_todo_count': cumulative_todos
            })
        
        return result


# 创建全局单例
goal_stats_provider = GoalStatsProvider()
