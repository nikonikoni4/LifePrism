"""
Report 数据提供者
提供 Daily Report 的数据库操作

重构版本：使用 DatabaseManager 内置的 CRUD 方法
"""
import json
from typing import Optional, List, Dict, Any

from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class DailyReportProvider(LWBaseDataProvider):
    """
    报告数据提供者
    
    继承 LWBaseDataProvider，提供 Daily Report 的 CRUD 操作
    使用 DatabaseManager 内置方法进行数据库操作
    """
    
    TABLE_NAME = 'daily_report'
    ID_COLUMN = 'date'
    
    # JSON 字段列表
    JSON_FIELDS = ['sunburst_data', 'todo_data', 'goal_data', 'daily_trend_data']
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    # ==================== 辅助方法 ====================
    
    def _serialize_json_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """将 JSON 字段序列化为字符串"""
        result = data.copy()
        for field in self.JSON_FIELDS:
            if field in result and result[field] is not None:
                result[field] = json.dumps(result[field], ensure_ascii=False)
        return result
    
    def _deserialize_json_fields(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """将 JSON 字符串字段反序列化为对象"""
        if not row:
            return row
        result = row.copy()
        for field in self.JSON_FIELDS:
            if field in result and result[field] is not None:
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    result[field] = None
        return result
    
    def _df_to_dict_list(self, df) -> List[Dict[str, Any]]:
        """将 DataFrame 转换为带 JSON 反序列化的字典列表"""
        if df.empty:
            return []
        
        results = []
        for _, row in df.iterrows():
            item = row.to_dict()
            results.append(self._deserialize_json_fields(item))
        return results
    
    # ==================== CRUD 操作 ====================
    
    def get_daily_report(self, date: str) -> Optional[Dict[str, Any]]:
        """
        按日期获取日报告
        
        Args:
            date: 日期 YYYY-MM-DD
        
        Returns:
            Optional[Dict]: 报告数据，不存在返回 None
        """
        try:
            result = self.db.get_by_id(self.TABLE_NAME, self.ID_COLUMN, date)
            if result:
                return self._deserialize_json_fields(result)
            return None
        except Exception as e:
            logger.error(f"获取日报告 {date} 失败: {e}")
            return None
    
    def upsert_daily_report(self, date: str, data: Dict[str, Any]) -> bool:
        """
        创建或更新日报告 (UPSERT)
        
        Args:
            date: 日期 YYYY-MM-DD
            data: 报告数据（只更新非 None 字段）
        
        Returns:
            bool: 是否成功
        """
        try:
            # 检查是否已存在
            exists = self.db.get_by_id(self.TABLE_NAME, self.ID_COLUMN, date) is not None
            
            if exists:
                # UPDATE - 只更新传入的非 None 字段
                update_data = {k: v for k, v in data.items() if v is not None}
                if not update_data:
                    return True
                
                # 序列化 JSON 字段
                update_data = self._serialize_json_fields(update_data)
                
                rows_affected = self.db.update_by_id(
                    self.TABLE_NAME, 
                    self.ID_COLUMN, 
                    date, 
                    update_data
                )
                
                if rows_affected > 0:
                    logger.info(f"更新日报告 {date} 成功")
                return True
            else:
                # INSERT
                insert_data = {self.ID_COLUMN: date}
                insert_data.update({k: v for k, v in data.items() if v is not None})
                
                # 序列化 JSON 字段
                insert_data = self._serialize_json_fields(insert_data)
                
                self.db.insert(self.TABLE_NAME, insert_data)
                logger.info(f"创建日报告 {date} 成功")
                return True
                
        except Exception as e:
            logger.error(f"保存日报告 {date} 失败: {e}")
            return False
    
    def update_report_state(self, date: str, state: str) -> bool:
        """
        更新报告状态
        
        Args:
            date: 日期 YYYY-MM-DD
            state: 状态 ("0": 未完成, "1": 已完成)
        
        Returns:
            bool: 是否成功
        """
        try:
            rows_affected = self.db.update_by_id(
                self.TABLE_NAME,
                self.ID_COLUMN,
                date,
                {'state': state}
            )
            
            success = rows_affected > 0
            if success:
                logger.info(f"更新日报告 {date} 状态为 {state}")
            return success
            
        except Exception as e:
            logger.error(f"更新日报告 {date} 状态失败: {e}")
            return False
    
    def delete_daily_report(self, date: str) -> bool:
        """
        删除日报告
        
        Args:
            date: 日期 YYYY-MM-DD
        
        Returns:
            bool: 是否成功
        """
        try:
            rows_affected = self.db.delete_by_id(
                self.TABLE_NAME,
                self.ID_COLUMN,
                date
            )
            
            success = rows_affected > 0
            if success:
                logger.info(f"删除日报告 {date} 成功")
            return success
            
        except Exception as e:
            logger.error(f"删除日报告 {date} 失败: {e}")
            return False
    
    def get_reports_in_range(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        获取日期范围内的报告列表
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        
        Returns:
            List[Dict]: 报告列表
        """
        try:
            df = self.db.query_advanced(
                self.TABLE_NAME,
                conditions=[
                    (self.ID_COLUMN, '>=', start_date),
                    (self.ID_COLUMN, '<=', end_date)
                ],
                order_by=f'{self.ID_COLUMN} ASC'
            )
            
            return self._df_to_dict_list(df)
            
        except Exception as e:
            logger.error(f"获取日期范围 {start_date} 至 {end_date} 报告失败: {e}")
            return []
    
    def get_completed_report_dates(
        self,
        start_date: str,
        end_date: str
    ) -> List[str]:
        """
        获取日期范围内已完成的报告日期列表
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        
        Returns:
            List[str]: 日期列表
        """
        try:
            df = self.db.query_advanced(
                self.TABLE_NAME,
                columns=[self.ID_COLUMN],
                conditions=[
                    (self.ID_COLUMN, '>=', start_date),
                    (self.ID_COLUMN, '<=', end_date),
                    ('state', '=', '1')
                ],
                order_by=f'{self.ID_COLUMN} ASC'
            )
            
            if df.empty:
                return []
            return df[self.ID_COLUMN].tolist()
            
        except Exception as e:
            logger.error(f"获取已完成报告日期失败: {e}")
            return []


# 创建全局单例
daily_report_provider = DailyReportProvider()


class WeeklyReportProvider(LWBaseDataProvider):
    """
    周报告数据提供者
    
    继承 LWBaseDataProvider，提供 Weekly Report 的 CRUD 操作
    使用 DatabaseManager 内置方法进行数据库操作
    """
    
    TABLE_NAME = 'weekly_report'
    ID_COLUMN = 'date'  # 使用周开始日期作为主键
    
    # JSON 字段列表
    JSON_FIELDS = ['sunburst_data', 'todo_data', 'goal_data', 'daily_trend_data']
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    # ==================== 辅助方法 ====================
    
    def _serialize_json_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """将 JSON 字段序列化为字符串"""
        result = data.copy()
        for field in self.JSON_FIELDS:
            if field in result and result[field] is not None:
                result[field] = json.dumps(result[field], ensure_ascii=False)
        return result
    
    def _deserialize_json_fields(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """将 JSON 字符串字段反序列化为对象"""
        if not row:
            return row
        result = row.copy()
        for field in self.JSON_FIELDS:
            if field in result and result[field] is not None:
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    result[field] = None
        return result
    
    def _df_to_dict_list(self, df) -> List[Dict[str, Any]]:
        """将 DataFrame 转换为带 JSON 反序列化的字典列表"""
        if df.empty:
            return []
        
        results = []
        for _, row in df.iterrows():
            item = row.to_dict()
            results.append(self._deserialize_json_fields(item))
        return results
    
    # ==================== CRUD 操作 ====================
    
    def get_weekly_report(self, week_start_date: str) -> Optional[Dict[str, Any]]:
        """
        按周开始日期获取周报告
        
        Args:
            week_start_date: 周开始日期 YYYY-MM-DD（周一）
        
        Returns:
            Optional[Dict]: 报告数据，不存在返回 None
        """
        try:
            result = self.db.get_by_id(self.TABLE_NAME, self.ID_COLUMN, week_start_date)
            if result:
                return self._deserialize_json_fields(result)
            return None
        except Exception as e:
            logger.error(f"获取周报告 {week_start_date} 失败: {e}")
            return None
    
    def upsert_weekly_report(self, week_start_date: str, data: Dict[str, Any]) -> bool:
        """
        创建或更新周报告 (UPSERT)
        
        Args:
            week_start_date: 周开始日期 YYYY-MM-DD（周一）
            data: 报告数据（只更新非 None 字段）
        
        Returns:
            bool: 是否成功
        """
        try:
            # 检查是否已存在
            exists = self.db.get_by_id(self.TABLE_NAME, self.ID_COLUMN, week_start_date) is not None
            
            if exists:
                # UPDATE - 只更新传入的非 None 字段
                update_data = {k: v for k, v in data.items() if v is not None}
                if not update_data:
                    return True
                
                # 序列化 JSON 字段
                update_data = self._serialize_json_fields(update_data)
                
                rows_affected = self.db.update_by_id(
                    self.TABLE_NAME, 
                    self.ID_COLUMN, 
                    week_start_date, 
                    update_data
                )
                
                if rows_affected > 0:
                    logger.info(f"更新周报告 {week_start_date} 成功")
                return True
            else:
                # INSERT
                insert_data = {self.ID_COLUMN: week_start_date}
                insert_data.update({k: v for k, v in data.items() if v is not None})
                
                # 序列化 JSON 字段
                insert_data = self._serialize_json_fields(insert_data)
                
                self.db.insert(self.TABLE_NAME, insert_data)
                logger.info(f"创建周报告 {week_start_date} 成功")
                return True
                
        except Exception as e:
            logger.error(f"保存周报告 {week_start_date} 失败: {e}")
            return False
    
    def update_report_state(self, week_start_date: str, state: str) -> bool:
        """
        更新报告状态
        
        Args:
            week_start_date: 周开始日期 YYYY-MM-DD
            state: 状态 ("0": 未完成, "1": 已完成)
        
        Returns:
            bool: 是否成功
        """
        try:
            rows_affected = self.db.update_by_id(
                self.TABLE_NAME,
                self.ID_COLUMN,
                week_start_date,
                {'state': state}
            )
            
            success = rows_affected > 0
            if success:
                logger.info(f"更新周报告 {week_start_date} 状态为 {state}")
            return success
            
        except Exception as e:
            logger.error(f"更新周报告 {week_start_date} 状态失败: {e}")
            return False
    
    def delete_weekly_report(self, week_start_date: str) -> bool:
        """
        删除周报告
        
        Args:
            week_start_date: 周开始日期 YYYY-MM-DD
        
        Returns:
            bool: 是否成功
        """
        try:
            rows_affected = self.db.delete_by_id(
                self.TABLE_NAME,
                self.ID_COLUMN,
                week_start_date
            )
            
            success = rows_affected > 0
            if success:
                logger.info(f"删除周报告 {week_start_date} 成功")
            return success
            
        except Exception as e:
            logger.error(f"删除周报告 {week_start_date} 失败: {e}")
            return False
    
    def get_reports_in_range(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        获取日期范围内的周报告列表
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        
        Returns:
            List[Dict]: 报告列表
        """
        try:
            df = self.db.query_advanced(
                self.TABLE_NAME,
                conditions=[
                    (self.ID_COLUMN, '>=', start_date),
                    (self.ID_COLUMN, '<=', end_date)
                ],
                order_by=f'{self.ID_COLUMN} ASC'
            )
            
            return self._df_to_dict_list(df)
            
        except Exception as e:
            logger.error(f"获取日期范围 {start_date} 至 {end_date} 周报告失败: {e}")
            return []


# 创建全局单例
weekly_report_provider = WeeklyReportProvider()


class MonthlyReportProvider(LWBaseDataProvider):
    """
    月报告数据提供者
    
    继承 LWBaseDataProvider，提供 Monthly Report 的 CRUD 操作
    使用 DatabaseManager 内置方法进行数据库操作
    """
    
    TABLE_NAME = 'monthly_report'
    ID_COLUMN = 'date'  # 使用月开始日期 YYYY-MM-01 作为主键
    
    # JSON 字段列表
    JSON_FIELDS = ['sunburst_data', 'todo_data', 'goal_data', 'daily_trend_data', 'heatmap_data']
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    # ==================== 辅助方法 ====================
    
    def _serialize_json_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """将 JSON 字段序列化为字符串"""
        result = data.copy()
        for field in self.JSON_FIELDS:
            if field in result and result[field] is not None:
                result[field] = json.dumps(result[field], ensure_ascii=False)
        return result
    
    def _deserialize_json_fields(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """将 JSON 字符串字段反序列化为对象"""
        if not row:
            return row
        result = row.copy()
        for field in self.JSON_FIELDS:
            if field in result and result[field] is not None:
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    result[field] = None
        return result
    
    def _df_to_dict_list(self, df) -> List[Dict[str, Any]]:
        """将 DataFrame 转换为带 JSON 反序列化的字典列表"""
        if df.empty:
            return []
        
        results = []
        for _, row in df.iterrows():
            item = row.to_dict()
            results.append(self._deserialize_json_fields(item))
        return results
    
    # ==================== CRUD 操作 ====================
    
    def get_monthly_report(self, month_start_date: str) -> Optional[Dict[str, Any]]:
        """
        按月开始日期获取月报告
        
        Args:
            month_start_date: 月开始日期 YYYY-MM-01
        
        Returns:
            Optional[Dict]: 报告数据，不存在返回 None
        """
        try:
            result = self.db.get_by_id(self.TABLE_NAME, self.ID_COLUMN, month_start_date)
            if result:
                return self._deserialize_json_fields(result)
            return None
        except Exception as e:
            logger.error(f"获取月报告 {month_start_date} 失败: {e}")
            return None
    
    def upsert_monthly_report(self, month_start_date: str, data: Dict[str, Any]) -> bool:
        """
        创建或更新月报告 (UPSERT)
        
        Args:
            month_start_date: 月开始日期 YYYY-MM-01
            data: 报告数据（只更新非 None 字段）
        
        Returns:
            bool: 是否成功
        """
        try:
            # 检查是否已存在
            exists = self.db.get_by_id(self.TABLE_NAME, self.ID_COLUMN, month_start_date) is not None
            
            if exists:
                # UPDATE - 只更新传入的非 None 字段
                update_data = {k: v for k, v in data.items() if v is not None}
                if not update_data:
                    return True
                
                # 序列化 JSON 字段
                update_data = self._serialize_json_fields(update_data)
                
                rows_affected = self.db.update_by_id(
                    self.TABLE_NAME, 
                    self.ID_COLUMN, 
                    month_start_date, 
                    update_data
                )
                
                if rows_affected > 0:
                    logger.info(f"更新月报告 {month_start_date} 成功")
                return True
            else:
                # INSERT
                insert_data = {self.ID_COLUMN: month_start_date}
                insert_data.update({k: v for k, v in data.items() if v is not None})
                
                # 序列化 JSON 字段
                insert_data = self._serialize_json_fields(insert_data)
                
                self.db.insert(self.TABLE_NAME, insert_data)
                logger.info(f"创建月报告 {month_start_date} 成功")
                return True
                
        except Exception as e:
            logger.error(f"保存月报告 {month_start_date} 失败: {e}")
            return False
    
    def update_report_state(self, month_start_date: str, state: str) -> bool:
        """
        更新报告状态
        
        Args:
            month_start_date: 月开始日期 YYYY-MM-01
            state: 状态 ("0": 未完成, "1": 已完成)
        
        Returns:
            bool: 是否成功
        """
        try:
            rows_affected = self.db.update_by_id(
                self.TABLE_NAME,
                self.ID_COLUMN,
                month_start_date,
                {'state': state}
            )
            
            success = rows_affected > 0
            if success:
                logger.info(f"更新月报告 {month_start_date} 状态为 {state}")
            return success
            
        except Exception as e:
            logger.error(f"更新月报告 {month_start_date} 状态失败: {e}")
            return False
    
    def delete_monthly_report(self, month_start_date: str) -> bool:
        """
        删除月报告
        
        Args:
            month_start_date: 月开始日期 YYYY-MM-01
        
        Returns:
            bool: 是否成功
        """
        try:
            rows_affected = self.db.delete_by_id(
                self.TABLE_NAME,
                self.ID_COLUMN,
                month_start_date
            )
            
            success = rows_affected > 0
            if success:
                logger.info(f"删除月报告 {month_start_date} 成功")
            return success
            
        except Exception as e:
            logger.error(f"删除月报告 {month_start_date} 失败: {e}")
            return False
    
    def get_reports_in_range(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        获取日期范围内的月报告列表
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        
        Returns:
            List[Dict]: 报告列表
        """
        try:
            df = self.db.query_advanced(
                self.TABLE_NAME,
                conditions=[
                    (self.ID_COLUMN, '>=', start_date),
                    (self.ID_COLUMN, '<=', end_date)
                ],
                order_by=f'{self.ID_COLUMN} ASC'
            )
            
            return self._df_to_dict_list(df)
            
        except Exception as e:
            logger.error(f"获取日期范围 {start_date} 至 {end_date} 月报告失败: {e}")
            return []


# 创建全局单例
monthly_report_provider = MonthlyReportProvider()
