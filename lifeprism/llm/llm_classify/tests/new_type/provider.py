"""
LLM 模块专用数据提供者
继承 LWBaseDataProvider，添加 LLM 分类特定的数据库操作
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta

from lifeprism.storage import LWBaseDataProvider
logger = logging.getLogger(__name__)


class DataProvider(LWBaseDataProvider):
    """
    测试用provider，为 LLM 提供基础数据库查询能力
    """
    
    # time_paradoxes mode 中文映射
    MODE_MAP = {
        "past": "我曾经是谁",
        "present": "我现在是谁",
        "future": "我要成为什么样的人"
    }
    
    def __init__(self, db_manager=None):
        """
        初始化 LLM 数据提供者
        
        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        super().__init__(db_manager)
        
        # 缓存映射（延迟初始化）
        self._category_map: Optional[Dict[str, str]] = None      # category_id -> name
        self._sub_category_map: Optional[Dict[str, str]] = None  # sub_category_id -> name
        self._goal_map: Optional[Dict[str, str]] = None          # goal_id -> name
    
    def _ensure_category_maps(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        确保分类映射已初始化（延迟加载）
        
        Returns:
            Tuple: (category_map, sub_category_map)
        """
        if self._category_map is None or self._sub_category_map is None:
            self._category_map = {}
            self._sub_category_map = {}
            
            # 加载主分类
            categories_df = self.load_categories()
            if categories_df is not None and not categories_df.empty:
                self._category_map = {
                    str(row['id']): row['name'] 
                    for _, row in categories_df.iterrows()
                }
            
            # 加载子分类
            sub_categories_df = self.load_sub_categories()
            if sub_categories_df is not None and not sub_categories_df.empty:
                self._sub_category_map = {
                    str(row['id']): row['name'] 
                    for _, row in sub_categories_df.iterrows()
                }
            
            logger.debug(f"分类映射已加载: {len(self._category_map)} 个主分类, {len(self._sub_category_map)} 个子分类")
        
        return self._category_map, self._sub_category_map
    
    def _ensure_goal_map(self) -> Dict[str, str]:
        """
        确保目标映射已初始化（延迟加载）
        
        Returns:
            Dict: goal_id -> goal_name 映射
        """
        if self._goal_map is None:
            self._goal_map = {}
            
            goals_df = self.db.query('goal', columns=['id', 'name'])
            if not goals_df.empty:
                self._goal_map = {
                    str(row['id']): row['name'] 
                    for _, row in goals_df.iterrows()
                }
            
            logger.debug(f"目标映射已加载: {len(self._goal_map)} 个目标")
        
        return self._goal_map
    
    def get_category_name(self, category_id: str) -> str:
        """获取主分类名称"""
        category_map, _ = self._ensure_category_maps()
        return category_map.get(str(category_id), "未知分类")
    
    def get_sub_category_name(self, sub_category_id: str) -> str:
        """获取子分类名称"""
        _, sub_category_map = self._ensure_category_maps()
        return sub_category_map.get(str(sub_category_id), "未知子分类")
    
    def get_goal_name(self, goal_id: str) -> str:
        """获取目标名称"""
        goal_map = self._ensure_goal_map()
        return goal_map.get(str(goal_id), "")
    
    def query_behavior_logs(
        self,
        start_time: str,
        end_time: str,
        limit: int = None,
        order_by: str = "start_time DESC"
    ) -> List[Dict]:
        """
        查询用户行为日志
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
            limit: 返回记录数限制
            order_by: 排序方式，默认按开始时间降序
            
        Returns:
            List[Dict]: 包含以下字段:
                - start_time: 开始时间
                - end_time: 结束时间
                - duration: 持续时间(秒)
                - app: 应用名称
                - title: 窗口标题
                - category_name: 主分类名称
                - sub_category_name: 子分类名称
                - goal_name: 目标名称（如无则为空字符串）
        """
        try:
            df = self.db.query_advanced(
                table_name='user_app_behavior_log',
                columns=['start_time', 'end_time', 'duration', 'app', 'title', 
                         'category_id', 'sub_category_id', 'link_to_goal_id'],
                conditions=[
                    ('start_time', '>=', start_time),
                    ('end_time', '<=', end_time)
                ],
                order_by=order_by,
                limit=limit
            )
            
            if df.empty:
                return []
            
            # 确保映射已加载
            self._ensure_category_maps()
            self._ensure_goal_map()
            
            results = []
            for _, row in df.iterrows():
                results.append({
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'duration': row['duration'],
                    'app': row['app'],
                    'title': row['title'],
                    'category_name': self.get_category_name(row.get('category_id', '')),
                    'sub_category_name': self.get_sub_category_name(row.get('sub_category_id', '')),
                    'goal_name': self.get_goal_name(row.get('link_to_goal_id', ''))
                })
            
            logger.debug(f"查询行为日志: {start_time} ~ {end_time}, 返回 {len(results)} 条记录")
            return results
            
        except Exception as e:
            logger.error(f"查询行为日志失败: {e}")
            return []
    
    def query_todos(self, date: str) -> List[Dict]:
        """
        查询指定日期的 todo（排除 inactive 状态）
        
        Args:
            date: 日期 YYYY-MM-DD
            
        Returns:
            List[Dict]: 包含 content 字段的 todo 列表
        """
        try:
            df = self.db.query_advanced(
                table_name='todo_list',
                columns=['id', 'content', 'state', 'link_to_goal_id'],
                conditions=[
                    ('date', '=', date),
                    ('state', '!=', 'inactive')
                ],
                order_by='order_index ASC'
            )
            
            if df.empty:
                return []
            
            results = []
            for _, row in df.iterrows():
                results.append({
                    'id': row['id'],
                    'content': row['content'],
                    'state': row['state'],
                    'goal_name': self.get_goal_name(row.get('link_to_goal_id', ''))
                })
            
            logger.debug(f"查询 todo: {date}, 返回 {len(results)} 条记录")
            return results
            
        except Exception as e:
            logger.error(f"查询 todo 失败: {e}")
            return []
    
    def query_goals(self) -> List[Dict]:
        """
        查询所有目标，并刷新 goal_id -> name 映射缓存
        
        Returns:
            List[Dict]: 包含 id, name 的目标列表
        """
        try:
            df = self.db.query(
                table_name='goal',
                columns=['id', 'name', 'status'],
                order_by='order_index ASC'
            )
            
            if df.empty:
                self._goal_map = {}
                return []
            
            # 刷新缓存
            self._goal_map = {
                str(row['id']): row['name'] 
                for _, row in df.iterrows()
            }
            
            results = [
                {'id': row['id'], 'name': row['name'], 'status': row['status']}
                for _, row in df.iterrows()
            ]
            
            logger.debug(f"查询目标: 返回 {len(results)} 个目标")
            return results
            
        except Exception as e:
            logger.error(f"查询目标失败: {e}")
            return []
    
    def query_time_paradoxes(self) -> List[Dict]:
        """
        查询用户的时间悖论测试结果（每个 mode 的最新版本）
        
        Args:
            user_id: 用户ID，默认为1
            
        Returns:
            List[Dict]: 包含:
                - mode: 模式（past/present/future）
                - mode_name: 模式中文名称
                - ai_abstract: AI总结
        """
        user_id = 1 # 默认用户ID
        try:
            results = []
            
            for mode in ['past', 'present', 'future']:
                # 查询每个 mode 的最新版本
                df = self.db.query_advanced(
                    table_name='time_paradoxes',
                    columns=['mode', 'ai_abstract', 'version'],
                    conditions=[
                        ('user_id', '=', user_id),
                        ('mode', '=', mode)
                    ],
                    order_by='version DESC',
                    limit=1
                )
                
                if not df.empty:
                    row = df.iloc[0]
                    results.append({
                        'mode': mode,
                        'mode_name': self.MODE_MAP.get(mode, mode),
                        'ai_abstract': row.get('ai_abstract', '')
                    })
            
            logger.debug(f"查询时间悖论: user_id={user_id}, 返回 {len(results)} 条记录")
            return results
            
        except Exception as e:
            logger.error(f"查询时间悖论失败: {e}")
            return []
    
    def get_logs_by_time(self, date: str) -> Dict[str, Dict]:
        """
        按时间段（每小时）获取活动日志
        
        每个小时内筛选时长大于1分钟的日志，按时长降序排序，最多返回3条。
        如果某个小时没有数据，则不返回该时间段。
        
        Args:
            date: 日期 YYYY-MM-DD
        
        Returns:
            Dict[str, Dict]: 按小时分组的日志数据
                格式: {
                    "08:00-09:00": {
                        "logs": [
                            {
                                "start_time": "2026-01-05 08:15:30",
                                "end_time": "2026-01-05 08:25:30",
                                "duration": 600,  # 秒
                                "app": "Chrome",
                                "title": "..."
                            },
                            ...
                        ],
                        "category_stats": [
                            {
                                "id": "cat-xxx",
                                "name": "工作/学习",
                                "duration": 1800
                            },
                            ...
                        ]
                    },
                    ...
                }
        """
        from datetime import datetime, timedelta
        from collections import defaultdict
        
        try:
            # 构建时间范围
            start_time = f"{date} 00:00:00"
            end_time = f"{date} 23:59:59"
            
            # 获取当天所有活动日志
            df = self.db.query_advanced(
                table_name='user_app_behavior_log',
                columns=['id', 'start_time', 'end_time', 'duration', 'app', 'title', 'category_id'],
                conditions=[
                    ('start_time', '>=', start_time),
                    ('end_time', '<=', end_time),
                    ('duration', '>', 60)  # 筛选时长大于1分钟
                ],
                order_by='start_time ASC'
            )
            
            if df.empty:
                return {}
            
            # 确保分类映射已加载
            category_map, _ = self._ensure_category_maps()
            
            # 按小时分组
            hourly_logs = defaultdict(list)
            
            for _, log in df.iterrows():
                # 解析开始时间，确定所属小时
                start_time_str = log['start_time']
                try:
                    start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                
                # 构建小时段标识，例如 "08:00-09:00"
                hour_start = start_dt.replace(minute=0, second=0, microsecond=0)
                hour_end = hour_start + timedelta(hours=1)
                hour_key = f"{hour_start.strftime('%H:%M')}-{hour_end.strftime('%H:%M')}"
                
                # 添加到对应小时段
                hourly_logs[hour_key].append(log)
            
            # 对每个小时段的日志进行处理
            result = {}
            for hour_key in sorted(hourly_logs.keys()):
                logs_in_hour = hourly_logs[hour_key]
                
                # 按时长降序排序，选择top3
                sorted_logs = sorted(logs_in_hour, key=lambda x: x['duration'], reverse=True)
                top3_logs = sorted_logs[:3]
                
                # 计算该小时的主分类统计
                category_stats = defaultdict(int)
                for log in logs_in_hour:
                    category_id = log.get('category_id')
                    if category_id:
                        category_stats[str(category_id)] += log['duration']
                
                # 转换为带名称的统计列表
                category_list = [
                    {
                        "id": cat_id,
                        "name": category_map.get(cat_id, "未分类"),
                        "duration": total_duration
                    }
                    for cat_id, total_duration in category_stats.items()
                ]
                
                # 按时长降序排序
                category_list.sort(key=lambda x: x['duration'], reverse=True)
                
                # 清理日志数据
                cleaned_logs = [
                    {
                        "id": log['id'],
                        "start_time": log['start_time'],
                        "end_time": log['end_time'],
                        "duration": log['duration'],
                        "app": log['app'],
                        "title": log.get('title', '')
                    }
                    for log in top3_logs
                ]
                
                result[hour_key] = {
                    "logs": cleaned_logs,
                    "category_stats": category_list
                }
            
            logger.debug(f"按小时查询日志: {date}, 返回 {len(result)} 个时段")
            return result
            
        except Exception as e:
            logger.error(f"按小时查询日志失败: {e}")
            return {}
    
    def get_user_focus_notes(self, start_time: str, end_time: str) -> List[Dict]:
        """
        获取用户手动添加的时间块备注
        
        从 timeline_custom_block 表查询用户在指定时间范围内
        手动添加的活动记录，这些记录的 content 字段代表用户的备注。
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
        
        Returns:
            List[Dict]: 用户备注列表，每条包含：
                - start_time: 开始时间
                - end_time: 结束时间
                - duration_minutes: 持续时间（分钟）
                - content: 备注内容
                - category_id: 关联的分类ID（可选）
                - sub_category_id: 关联的子分类ID（可选）
        """
        try:
            # 转换时间格式为 ISO 格式（timeline_custom_block 使用 ISO 格式）
            start_iso = start_time.replace(" ", "T")
            end_iso = end_time.replace(" ", "T")
            
            df = self.db.query_advanced(
                table_name='timeline_custom_block',
                columns=['start_time', 'end_time', 'duration', 'content', 'category_id', 'sub_category_id'],
                conditions=[
                    ('start_time', '>=', start_iso),
                    ('end_time', '<=', end_iso)
                ],
                order_by='start_time ASC'
            )
            
            if df.empty:
                return []
            
            # 过滤掉空内容
            df = df[df['content'].notna() & (df['content'] != '')]
            
            results = []
            for _, row in df.iterrows():
                results.append({
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'duration_minutes': row['duration'],
                    'content': row['content'],
                    'category_id': row.get('category_id'),
                    'sub_category_id': row.get('sub_category_id')
                })
            
            logger.debug(f"查询用户备注: {start_time} ~ {end_time}, 返回 {len(results)} 条记录")
            return results
            
        except Exception as e:
            logger.error(f"查询用户备注失败: {e}")
            return []

if __name__ == "__main__":
    """测试 DataProvider 的数据库查询功能"""
    from datetime import datetime, timedelta
    
    # 初始化 provider
    provider = DataProvider()
    
    print("=" * 60)
    print("DataProvider 测试")
    print("=" * 60)
    
    # 1. 测试分类映射
    print("\n1. 测试分类映射加载")
    print("-" * 60)
    category_map, sub_category_map = provider._ensure_category_maps()
    print(f"主分类数量: {len(category_map)}")
    print(f"子分类数量: {len(sub_category_map)}")
    if category_map:
        print(f"示例主分类: {list(category_map.items())[:3]}")
    if sub_category_map:
        print(f"示例子分类: {list(sub_category_map.items())[:3]}")
    
    # 2. 测试目标映射
    print("\n2. 测试目标查询和映射")
    print("-" * 60)
    goals = provider.query_goals()
    print(f"目标数量: {len(goals)}")
    if goals:
        print(f"前3个目标:")
        for goal in goals[:3]:
            print(f"  - {goal['id']}: {goal['name']} ({goal['status']})")
    
    # 3. 测试行为日志查询（最近一天）
    print("\n3. 测试行为日志查询（今天）")
    print("-" * 60)
    today = datetime.now().strftime("%Y-%m-%d")
    start_time = f"{today} 00:00:00"
    end_time = f"{today} 23:59:59"
    
    logs = provider.query_behavior_logs(
        start_time=start_time,
        end_time=end_time,
        limit=5
    )
    print(f"查询时间范围: {start_time} ~ {end_time}")
    print(f"返回记录数: {len(logs)}")
    if logs:
        print(f"前3条记录:")
        for log in logs[:3]:
            print(f"  - {log['start_time']} | {log['app']} | {log['category_name']}/{log['sub_category_name']}")
            if log['goal_name']:
                print(f"    关联目标: {log['goal_name']}")
    
    # 4. 测试 todo 查询
    print("\n4. 测试 Todo 查询（今天）")
    print("-" * 60)
    todos = provider.query_todos(date=today)
    print(f"查询日期: {today}")
    print(f"返回 todo 数量: {len(todos)}")
    if todos:
        print(f"前5条 todo:")
        for todo in todos[:5]:
            status_icon = "✓" if todo['state'] == 'completed' else "○"
            print(f"  {status_icon} {todo['content']}")
            if todo['goal_name']:
                print(f"    → {todo['goal_name']}")
    
    # 5. 测试时间悖论查询
    print("\n5. 测试时间悖论查询")
    print("-" * 60)
    paradoxes = provider.query_time_paradoxes(user_id=1)
    print(f"返回记录数: {len(paradoxes)}")
    if paradoxes:
        for p in paradoxes:
            print(f"\n【{p['mode_name']}】")
            if p['ai_abstract']:
                # 截取前100个字符
                abstract = p['ai_abstract'][:100] + "..." if len(p['ai_abstract']) > 100 else p['ai_abstract']
                print(f"  {abstract}")
            else:
                print(f"  (暂无总结)")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
