"""
lifewatch数据提供者
"""
from lifewatch.storage.database_manager import DatabaseManager
from lifewatch.config.database import LW_DB_PATH
class LWDataProviders:
    def __init__(self):
        self.db_manager = DatabaseManager(LW_DB_PATH,use_pool=True,pool_size=1)

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

if __name__ == "__main__":
    providers = LWDataProviders()
    print(providers.query_title_description(["test"]))