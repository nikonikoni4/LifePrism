"""
从数据库中读取数据,计算统计指标,为前端显示提供数据支持
"""
from lifewatch.storage.database_manager import DatabaseManager
from lifewatch import config
from datetime import datetime

class StatisticalDataProvider:
    def __init__(self):
        self.lw_db_manager = DatabaseManager(db_path=config.DB_PATH)
        self._current_date = None
        self._start_time = None
        self._end_time = None

    @property
    def current_date(self):
        if not self._current_date:
            raise AttributeError("请先使用 self.current_date = 'YYYY-MM-DD' 设置日期。")
        return self._current_date

    @current_date.setter
    def current_date(self, value):
        start_time = datetime.strptime(value, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
        end_time = datetime.strptime(value, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        self._start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")
        self._end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")
        self._current_date = value

    def get_active_time(self) -> int:
        """
        获取指定日期的总活跃时长
        return 
            int, 活跃时长(秒)
        """
        if not self._current_date:
            raise AttributeError("请先使用 self.current_date = 'YYYY-MM-DD' 设置日期。")
        sql = """
        SELECT SUM(duration) 
        FROM user_app_behavior_log 
        WHERE start_time >= ? AND start_time <= ?
        """
        
        with self.lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time))
            result = cursor.fetchone()
            
        return result[0] if result and result[0] is not None else 0
    

    def get_top_applications(self,top_n) -> list[dict]:
        """
        获取指定日期的Top应用排行
        arg:
            top_n: int, Top N
        return 
            list[dict], Top应用排行:
                name: str, 应用名称
                duration: int, 活跃时长(秒)
        """
        if not self._current_date:
            raise AttributeError("请先使用 self.current_date = 'YYYY-MM-DD' 设置日期。")
        sql = """
        SELECT app, SUM(duration) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ?
        GROUP BY app
        ORDER BY total_duration DESC
        LIMIT ?
        """
        
        with self.lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time, top_n))
            results = cursor.fetchall()
            
        return [{"name": row[0], "duration": row[1]} for row in results]

    def get_top_title(self, top_n) -> list[dict]:
        """
        获取指定日期的Top窗口标题排行
        arg:
            top_n: int, Top N
        return 
            list[dict], Top窗口标题排行:
                name: str, 窗口标题
                duration: int, 活跃时长(秒)
        """
        if not self._current_date:
            raise AttributeError("请先使用 self.current_date = 'YYYY-MM-DD' 设置日期。")
        sql = """
        SELECT title, SUM(duration) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ?
        GROUP BY title
        ORDER BY total_duration DESC
        LIMIT ?
        """
        
        with self.lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time, top_n))
            results = cursor.fetchall()
            
        return [{"name": row[0], "duration": row[1]} for row in results]
    def get_category_stats(self) -> list[dict]:
        """
        获取指定日期的分类统计
        return 
            list[dict], 分类统计:
                name: str, 分类名称
                color: str, 分类颜色
                id: int, 分类ID
                duration: int, 活跃时长(秒)
        """
        if not self._current_date:
            raise AttributeError("请先使用 self.current_date = 'YYYY-MM-DD' 设置日期。")
        sql_data = """
        SELECT category, SUM(duration) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ?
        GROUP BY category
        """
        sql_color = """
        SELECT name, color,id
        FROM category
        """

        with self.lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_data, (self._start_time, self._end_time))
            results = cursor.fetchall()
            
            cursor.execute(sql_color)
            category_color = cursor.fetchall()
        category_color_dict = {row[0]: {"id": row[2], "color": row[1]} for row in category_color}
            
        return [{"name": row[0], "duration": row[1],"color": category_color_dict[row[0]]["color"],"id": category_color_dict[row[0]]["id"]} for row in results]
    def get_sub_category_stats(self) -> list[dict]:
        """
        获取指定日期的子分类统计
        return 
            list[dict], 子分类统计:
                name: str, 子分类名称
                duration: int, 活跃时长(秒)
        """
        if not self._current_date:
            raise AttributeError("请先使用 self.current_date = 'YYYY-MM-DD' 设置日期。")
        sql = """
        SELECT sub_category, SUM(duration) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ? AND sub_category IS NOT NULL
        GROUP BY sub_category
        """
        sql_id = """
        SELECT name, id,category_id
        FROM sub_category
        """
        with self.lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time))
            results = cursor.fetchall()
            cursor.execute(sql_id)
            sub_category_id = cursor.fetchall()
            sub_category_id_dict = {row[0]: {"id": row[1],"category_id": row[2]} for row in sub_category_id}
        # return [{"name": row[0], "duration": row[1]} for row in results]
    
        return [{"name": row[0], "duration": row[1],"id": sub_category_id_dict[row[0]]["id"],"category_id": sub_category_id_dict[row[0]]["category_id"]} for row in results]
    
if __name__ == "__main__":
    sdp = StatisticalDataProvider()
    sdp.current_date = "2025-12-02"
    print(sdp.current_date)
    print(sdp._start_time)
    print(sdp._end_time)
    # print(sdp.get_active_time())
    # print(sdp.get_top_applications(10))
    # print(sdp.get_top_title(10))
    # print(sdp.get_category_stats())
    print(sdp.get_sub_category_stats())
    with sdp.lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("select distinct sub_category from user_app_behavior_log")
        result = cursor.fetchall()
    for row in result:
        for sub_category in row:
            print(sub_category)