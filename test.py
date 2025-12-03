import os
import logging
import json
from lifewatch.server.services.data_processing_service import DataProcessingService
from lifewatch.config import database as db_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_data_processing_service():
    print("=" * 60)
    print("开始测试 DataProcessingService")
    print("=" * 60)

    # 1. 配置路径
    # ActivityWatch 数据库路径
    aw_db_path = r"C:\Users\15535\AppData\Local\activitywatch\activitywatch\aw-server\peewee-sqlite.v2.db"
    # LifeWatch 数据库路径
    lifewatch_db_path = db_config.DB_PATH
    
    print(f"ActivityWatch DB: {aw_db_path}")
    print(f"LifeWatch DB: {lifewatch_db_path}")
    
    if not os.path.exists(aw_db_path):
        print(f"❌ 错误: 找不到 ActivityWatch 数据库文件: {aw_db_path}")
        return

    try:
        # 2. 初始化服务
        print("\n正在初始化 DataProcessingService...")
        service = DataProcessingService(
            db_path=lifewatch_db_path,
            aw_db_path=aw_db_path
        )
        
        # 3. 执行数据处理
        # 测试参数: 最近 1 小时, 开启自动分类, 不使用增量同步(强制获取最近数据)
        hours = 24
        auto_classify = True
        use_incremental_sync = False
        
        print(f"\n正在执行数据处理:")
        print(f"- 时间范围: 最近 {hours} 小时")
        print(f"- 自动分类: {auto_classify}")
        print(f"- 增量同步: {use_incremental_sync}")
        
        result = service.process_activitywatch_data(
            hours=hours,
            auto_classify=auto_classify,
            use_incremental_sync=use_incremental_sync
        )
        
        # 4. 输出结果
        print("\n✅ 处理完成!")
        print("\n处理结果统计:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # test_data_processing_service()
    sql = """SELECT id, timestamp, duration, datastr
                FROM eventmodel
                WHERE bucket_id = ?
             AND timestamp >= ? AND timestamp < ? ORDER BY timestamp DESC LIMIT ?"""
    import sqlite3
    param = [2, '2025-12-03T02:00:40.792302+00:00', '2025-12-03T03:00:40.792302+00:00', 10000]
    aw_db_path = r"C:\Users\15535\AppData\Local\activitywatch\activitywatch\aw-server\peewee-sqlite.v2.db"
    conn = sqlite3.connect(aw_db_path)
    cursor = conn.cursor()
    cursor.execute(sql, param)
    cursor.execute("""SELECT id, timestamp, duration, datastr FROM eventmodel where bucket_id = 2 and 
        timestamp >= '2025-12-03 02:56:29.452000+00:00' and timestamp < '2025-12-03 03:03:27.919000+00:00' ORDER BY timestamp DESC LIMIT 10000""")
    rows = cursor.fetchall()
    print(rows)
