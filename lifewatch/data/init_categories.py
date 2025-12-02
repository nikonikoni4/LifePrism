"""
分类数据初始化模块
用于初始化默认的主分类和子分类数据
"""

from lifewatch.storage.database_manager import DatabaseManager
import logging

logger = logging.getLogger(__name__)


# 默认主分类数据
DEFAULT_CATEGORIES = [
    {
        'id': 'work',
        'name': '工作/学习',
        'color': '#5B8FF9',
        'order_index': 0
    },
    {
        'id': 'entertainment',
        'name': '生活/娱乐',
        'color': '#FA8C16',
        'order_index': 1
    },
    {
        'id': 'other',
        'name': '其他',
        'color': '#BFBFBF',
        'order_index': 2
    }
]

# 默认子分类数据
DEFAULT_SUB_CATEGORIES = [
    # Work 子分类
    {'id': 'coding', 'category_id': 'work', 'name': 'Coding', 'order_index': 0},
    {'id': 'meeting', 'category_id': 'work', 'name': 'Meetings', 'order_index': 1},
    {'id': 'planning', 'category_id': 'work', 'name': 'Planning', 'order_index': 2},
    {'id': 'research', 'category_id': 'work', 'name': 'Research', 'order_index': 3},
    
    # Entertainment 子分类
    {'id': 'video', 'category_id': 'entertainment', 'name': 'Video Streaming', 'order_index': 0},
    {'id': 'games', 'category_id': 'entertainment', 'name': 'Gaming', 'order_index': 1},
    {'id': 'social', 'category_id': 'entertainment', 'name': 'Social Media', 'order_index': 2},
    
    # Other 子分类
    {'id': 'utilities', 'category_id': 'other', 'name': 'System Utilities', 'order_index': 0},
    {'id': 'browsing', 'category_id': 'other', 'name': 'General Browsing', 'order_index': 1},
    {'id': 'untracked', 'category_id': 'other', 'name': 'Untracked', 'order_index': 2}
]


def init_default_categories(db_path: str = None) -> bool:
    """
    初始化默认分类数据
    
    如果分类表为空，则插入默认的主分类和子分类数据
    
    Args:
        db_path: 数据库路径，None 则使用默认路径
        
    Returns:
        bool: 是否成功初始化
    """
    try:
        from lifewatch.config.database import DB_PATH
        if db_path is None:
            db_path = DB_PATH
        
        db = DatabaseManager(db_path=db_path)
        
        # 检查是否已有分类数据
        existing_categories = db.query('category')
        
        if not existing_categories.empty:
            logger.info("分类数据已存在，跳过初始化")
            return True
        
        # 插入默认主分类
        logger.info("开始初始化默认主分类...")
        affected = db.insert_many('category', DEFAULT_CATEGORIES)
        logger.info(f"成功插入 {affected} 条主分类数据")
        
        # 插入默认子分类
        logger.info("开始初始化默认子分类...")
        affected = db.insert_many('sub_category', DEFAULT_SUB_CATEGORIES)
        logger.info(f"成功插入 {affected} 条子分类数据")
        
        logger.info("默认分类数据初始化完成！")
        return True
        
    except Exception as e:
        logger.error(f"初始化默认分类数据失败: {e}")
        return False


def reset_categories(db_path: str = None) -> bool:
    """
    重置分类数据（清空并重新初始化）
    
    警告：此操作会删除所有现有分类数据！
    
    Args:
        db_path: 数据库路径，None 则使用默认路径
        
    Returns:
        bool: 是否成功重置
    """
    try:
        from lifewatch.config.database import DB_PATH
        if db_path is None:
            db_path = DB_PATH
            
        db = DatabaseManager(db_path=db_path)
        
        # 清空子分类表
        logger.warning("清空子分类表...")
        db.truncate('sub_category')
        
        # 清空主分类表
        logger.warning("清空主分类表...")
        db.truncate('category')
        
        # 重新初始化
        return init_default_categories(db_path)
        
    except Exception as e:
        logger.error(f"重置分类数据失败: {e}")
        return False


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 执行初始化
    print("=" * 60)
    print("开始初始化默认分类数据...")
    print("=" * 60)
    
    success = init_default_categories()
    
    if success:
        print("\n✓ 分类数据初始化成功！")
        
        # 验证数据
        from lifewatch.config.database import DB_PATH
        db = DatabaseManager(db_path=DB_PATH)
        categories = db.query('category')
        sub_categories = db.query('sub_category')
        
        print(f"\n主分类数量: {len(categories)}")
        print(f"子分类数量: {len(sub_categories)}")
        
        print("\n主分类列表:")
        for _, cat in categories.iterrows():
            print(f"  - {cat['id']}: {cat['name']} ({cat['color']})")
            
        print("\n子分类列表:")
        for _, sub in sub_categories.iterrows():
            print(f"  - {sub['id']}: {sub['name']} (属于: {sub['category_id']})")
    else:
        print("\n✗ 分类数据初始化失败！")

