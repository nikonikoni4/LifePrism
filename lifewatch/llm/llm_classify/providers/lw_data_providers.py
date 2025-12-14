"""
lifewatch数据提供者
"""
from lifewatch.storage import lw_db_manager



class LWDataProviders:
    def __init__(self):
        self.db_manager = lw_db_manager

    def query_title_description(self,query_list:list[str])->list[dict[str,str]]:
        sql = """
        SELECT key_word, description
        FROM title_description
        WHERE key_word IN ({})
        """.format(",".join(["?" for _ in query_list]))
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, query_list)
            results = cursor.fetchall()
        return [{"key_word": row[0], "description": row[1]} for row in results]

    def update_app_description(self,app_description_list:list[dict[str,str]]):
        """
        更新app_description表中的描述
        """
        self.db_manager.upsert_many("app_purpose_category",app_description_list,"app")



lw_data_providers = LWDataProviders() # 全局唯一的实例
if __name__ == "__main__":
    providers = LWDataProviders()
   # providers.update_app_description([{"app":"test","app_description":"test1"},{"app":"test2","app_description":"test2"}])