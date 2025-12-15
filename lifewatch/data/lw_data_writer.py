"""
LifeWatch 数据写入器
负责将清洗后的数据写入 LifeWatch 数据库

职责：
- 保存用户行为日志
- 保存应用分类数据  
- 增量同步相关操作
"""
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LWDataWriter:
    """
    LifeWatch 数据写入器
    
    负责数据清洗后写入 lw_db 的操作
    """
    
    def __init__(self, db_manager=None):
        """
        初始化数据写入器
        
        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        if db_manager is None:
            from lifewatch.storage import lw_db_manager
            self.db = lw_db_manager
        else:
            self.db = db_manager
    
    def save_user_app_behavior_log(self, cleaned_events_df: pd.DataFrame) -> int:
        """
        保存行为分类后的数据到 user_app_behavior_log 表
        
        使用 INSERT OR IGNORE 策略，避免插入重复记录（基于 UNIQUE(app, start_time) 约束）
        自动生成 event_id 如果不存在
        
        Args:
            cleaned_events_df: 清洗后的事件数据DataFrame，应包含以下字段：
                - start_time: 开始时间（必需）
                - end_time: 结束时间（必需）
                - app: 应用名称（必需）
                - id: 事件ID（可选，不存在会自动生成）
                - duration: 持续时间（可选）
                - title: 窗口标题（可选）
                - category: 默认分类（可选）
                - sub_category: 目标分类（可选）
                - is_multipurpose_app: 是否多用途应用（可选）
                - category_id: 主分类ID（可选）
                - sub_category_id: 子分类ID（可选）
        
        Returns:
            int: 实际插入的行数
        """
        try:
            data_list = []
            for _, row in cleaned_events_df.iterrows():
                # 确保id字段存在，自动生成如果缺失
                event_id = row.get('id', f"event_{row.get('start_time', '')}_{row.get('app', 'unknown')}")
                
                data_list.append({
                    'id': event_id,
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'duration': row.get('duration'),
                    'app': row['app'],
                    'title': row.get('title'),
                    'category': row.get('category'),
                    'sub_category': row.get('sub_category'),
                    'is_multipurpose_app': int(row.get('is_multipurpose_app', False)),
                    'category_id': row.get('category_id'),
                    'sub_category_id': row.get('sub_category_id')
                })
            
            # 使用 INSERT OR IGNORE（基于 UNIQUE 约束）
            if not data_list:
                return 0
            
            columns = list(data_list[0].keys())
            columns_str = ', '.join(columns)
            placeholders = ', '.join(['?' for _ in columns])
            sql = f"INSERT OR IGNORE INTO user_app_behavior_log ({columns_str}) VALUES ({placeholders})"
            
            values_list = [
                [row.get(col) for col in columns]
                for row in data_list
            ]
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, values_list)
                affected = cursor.rowcount
                logger.info(f"成功保存 {affected} 行清洗数据到数据库（共尝试 {len(data_list)} 行）")
                return affected
                
        except Exception as e:
            logger.error(f"保存清洗数据失败: {e}")
            raise
    
    def save_app_purpose_category(self, ai_metadata_df: pd.DataFrame) -> int:
        """
        保存AI元数据到 app_purpose_category 表
        
        使用 UPSERT 策略：已存在的应用会被更新，新应用会被插入
        自动处理字段名映射：'class' -> 'sub_category'
        
        Args:
            ai_metadata_df: AI元数据DataFrame，应包含以下字段：
                - app: 应用名称（必需）
                - title: 应用标题（可选）
                - is_multipurpose_app: 是否多用途应用（可选）
                - app_description: 应用描述（可选）
                - title_description: 标题描述（可选）
                - class 或 sub_category: 分类（可选）
        
        Returns:
            int: 受影响的行数
        """
        try:
            data_list = ai_metadata_df.to_dict('records')
            
            # 映射字段名：'class' -> 'sub_category'
            for data in data_list:
                if 'class' in data and 'sub_category' not in data:
                    data['sub_category'] = data.pop('class')
            
            affected = self.db.upsert_many('app_purpose_category', 
                                       data_list, 
                                       conflict_columns=['app'])
            logger.info(f"成功保存 {len(data_list)} 行AI元数据到数据库")
            return affected
        except Exception as e:
            logger.error(f"保存AI元数据失败: {e}")
            raise
    
    def get_latest_end_time(self) -> Optional[str]:
        """
        获取数据库中最新的 end_time
        用于增量同步，获取上次同步的最后时间点
        
        Returns:
            Optional[str]: 最新的 end_time，格式：'YYYY-MM-DD HH:MM:SS'，如果表为空返回 None
        """
        try:
            sql = "SELECT MAX(end_time) as latest_end_time FROM user_app_behavior_log"
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                result = cursor.fetchone()
                latest_time = result[0] if result and result[0] else None
                
                if latest_time:
                    logger.info(f"数据库中最新的 end_time: {latest_time}")
                else:
                    logger.info("数据库为空，没有历史数据")
                
                return latest_time
        except Exception as e:
            logger.error(f"获取最新 end_time 失败: {e}")
            return None


# ==================== 全局实例 ====================
lw_data_writer = LWDataWriter()


if __name__ == "__main__":
    # 测试数据写入器
    writer = LWDataWriter()
    latest = writer.get_latest_end_time()
    print(f"最新 end_time: {latest}")
