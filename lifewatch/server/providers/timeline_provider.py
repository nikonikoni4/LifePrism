"""
Timeline 数据提供者

为 Timeline 模块提供专用的数据加载方法
"""
from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger
logger = get_logger(__name__)


class TimelineProvider(LWBaseDataProvider):
    """
    Timeline 模块专用数据提供者
    
    继承 LWBaseDataProvider，使用基类的 get_activity_logs 方法
    封装 Timeline 相关的数据加载逻辑
    """
    
    def get_timeline_events_by_date(self, date: str, channel: str = 'pc') -> list[dict]:
        """
        获取指定日期的时间线事件数据
        
        内部调用基类 get_activity_logs，封装为 timeline 专用格式
        
        Args:
            date: str, 日期（YYYY-MM-DD 格式）
            channel: str, 数据通道 ('pc' 或 'mobile'，当前仅支持 'pc')
        
        Returns:
            list[dict]: 事件列表
        """
        # 调用基类方法
        logs, _ = self.get_activity_logs(
            date=date,
            query_fields=["id", "start_time", "end_time", "duration", "app", "title", 
                         "category_id", "sub_category_id"],
            order_desc=False  # 升序
        )
        
        # 转换为 timeline 格式
        events = []
        for log in logs:
            events.append({
                "id": log.get("id"),
                "start_time": log.get("start_time"),
                "end_time": log.get("end_time"),
                "duration": log.get("duration"),
                "app": log.get("app"),
                "title": log.get("title"),
                "category_id": log.get("category_id") or "",
                "category_name": log.get("category_name") or "",
                "sub_category_id": log.get("sub_category_id") or "",
                "sub_category_name": log.get("sub_category_name") or "",
                "app_description": "",  # 保留字段
                "title_analysis": "",   # 保留字段
                "device_type": "pc"
            })
        
        return events

    # ============================================================================
    # UserCustomBlock CRUD 方法
    # ============================================================================
    
    def create_custom_block(self, data: dict) -> dict:
        """
        创建用户自定义时间块
        
        Args:
            data: dict, 包含 content, start_time, end_time, duration, category_id, sub_category_id
        
        Returns:
            dict: 创建后的完整记录（含 id 和时间戳）
        """
        self.db.insert("timeline_custom_block", data)
        
        # 查询刚插入的记录（按创建时间倒序取最新一条）
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM timeline_custom_block ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
        return {}
    
    def get_custom_block_by_id(self, block_id: int) -> dict | None:
        """
        根据 ID 获取单条自定义时间块
        
        Args:
            block_id: int, 时间块 ID
        
        Returns:
            dict | None: 记录或 None
        """
        return self.db.get_by_id("timeline_custom_block", "id", block_id)
    
    def get_custom_blocks_by_date(self, date: str) -> list[dict]:
        """
        获取指定日期的所有自定义时间块
        
        Args:
            date: str, 日期（YYYY-MM-DD 格式）
        
        Returns:
            list[dict]: 时间块列表
        """
        # 使用 start_time 的日期部分过滤
        start_of_day = f"{date}T00:00:00"
        end_of_day = f"{date}T23:59:59"
        
        # 使用原生 SQL 查询时间范围
        sql = """
        SELECT * FROM timeline_custom_block
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time ASC
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, [start_of_day, end_of_day])
            rows = cursor.fetchall()
            if not rows:
                return []
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    def update_custom_block(self, block_id: int, data: dict) -> dict | None:
        """
        更新用户自定义时间块
        
        Args:
            block_id: int, 时间块 ID
            data: dict, 要更新的字段
        
        Returns:
            dict | None: 更新后的完整记录或 None
        
        注意：
            - todo_id, category_id, sub_category_id 允许设置为 None（清除绑定）
            - 其他字段（content, start_time 等）不接受 None 值
        """
        # 可清空的字段列表（这些字段允许显式设置为 None）
        nullable_fields = {'todo_id', 'category_id', 'sub_category_id'}
        
        # 构建更新数据：
        # - 可清空字段：保留 None 值（用于清除绑定）
        # - 其他字段：过滤掉 None 值
        update_data = {}
        for k, v in data.items():
            if k in nullable_fields:
                # 可清空字段：无论是 None 还是有效值都保留
                update_data[k] = v
            elif v is not None:
                # 其他字段：只保留非 None 值
                update_data[k] = v
        
        if not update_data:
            return self.get_custom_block_by_id(block_id)
        
        affected_rows = self.db.update(
            "timeline_custom_block",
            data=update_data,
            where={"id": block_id}
        )
        if affected_rows > 0:
            return self.get_custom_block_by_id(block_id)
        return None
    
    def delete_custom_block(self, block_id: int) -> bool:
        """
        删除用户自定义时间块
        
        Args:
            block_id: int, 时间块 ID
        
        Returns:
            bool: 是否删除成功
        """
        affected_rows = self.db.delete("timeline_custom_block", where={"id": block_id})
        return affected_rows > 0
