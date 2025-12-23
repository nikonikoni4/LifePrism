"""
测试分类状态同步逻辑

测试场景：
1. 单分类应用（如 notepad.exe）：禁用后恢复时，只匹配 app 删除冲突记录
2. 多分类应用（如 chrome）：禁用后恢复时，匹配 app + title 删除冲突记录

流程：
1. 启用分类 → 产生记录 A (created_at = T1)
2. 禁用分类 → 记录 A 的 state 变为 0
3. 再次识别 → 产生新记录 B (created_at = T2, T2 > T1)
4. 恢复分类 → 应删除记录 B，保留记录 A
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lifewatch.storage import lw_db_manager
from lifewatch.server.services.category_service import CategoryService
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class TestCategoryStateSync:
    """测试分类状态同步"""
    
    def __init__(self):
        self.db = lw_db_manager
        self.service = CategoryService()
        
        # 测试用分类ID（使用实际存在的分类，或创建测试分类）
        self.test_category_id = "test-cat-001"
        self.test_sub_category_id = "test-sub-001"
        
        # 测试用应用
        self.single_purpose_app = "notepad.exe"  # 单分类应用
        self.multi_purpose_app = "chrome"  # 多分类应用（浏览器）
    
    def setup(self):
        """设置测试环境，创建测试分类和子分类"""
        print("\n" + "="*60)
        print("设置测试环境")
        print("="*60)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 清理旧的测试数据
            cursor.execute("DELETE FROM category_map_cache WHERE app IN (?, ?)", 
                          (self.single_purpose_app, self.multi_purpose_app))
            cursor.execute("DELETE FROM sub_category WHERE id = ?", (self.test_sub_category_id,))
            cursor.execute("DELETE FROM category WHERE id = ?", (self.test_category_id,))
            
            # 创建测试主分类
            cursor.execute("""
                INSERT OR REPLACE INTO category (id, name, color, order_index, state)
                VALUES (?, '测试分类', '#FF5733', 999, 1)
            """, (self.test_category_id,))
            
            # 创建测试子分类
            cursor.execute("""
                INSERT OR REPLACE INTO sub_category (id, category_id, name, order_index, state)
                VALUES (?, ?, '测试子分类', 1, 1)
            """, (self.test_sub_category_id, self.test_category_id))
            
            conn.commit()
        
        # 刷新服务缓存
        self.service._refresh_cache()
        print("✓ 测试分类和子分类创建完成")
    
    def insert_mock_category_map_record(self, app: str, title: str, category_id: str, 
                                        sub_category_id: str, state: int, 
                                        created_at: str) -> None:
        """插入模拟的 category_map_cache 记录"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO category_map_cache 
                (app, title, category_id, sub_category_id, state, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (app, title, category_id, sub_category_id, state, created_at))
            conn.commit()
    
    def get_category_map_records(self, app: str) -> list:
        """获取指定应用的所有记录"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT app, title, category_id, sub_category_id, state, created_at
                FROM category_map_cache
                WHERE app = ?
                ORDER BY created_at
            """, (app,))
            return cursor.fetchall()
    
    def print_records(self, app: str, label: str = ""):
        """打印指定应用的记录"""
        records = self.get_category_map_records(app)
        print(f"\n{label} - {app} 的记录 ({len(records)} 条):")
        print("-" * 80)
        for r in records:
            print(f"  app={r[0]}, title={r[1]}, cat={r[2]}, sub={r[3]}, state={r[4]}, created={r[5]}")
        print("-" * 80)
    
    def test_single_purpose_app(self):
        """
        测试单分类应用的状态同步逻辑
        
        预期行为：恢复时只匹配 app 删除冲突记录（不管 title）
        """
        print("\n" + "="*60)
        print("测试1: 单分类应用 (notepad.exe)")
        print("="*60)
        
        app = self.single_purpose_app
        
        # 清理该应用的旧记录
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM category_map_cache WHERE app = ?", (app,))
            conn.commit()
        
        # 时间点
        t1 = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        t2 = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Step 1: 模拟启用状态下识别产生的记录
        print(f"\n[Step 1] 启用分类，识别产生记录 (created_at = {t1})")
        self.insert_mock_category_map_record(
            app=app, 
            title="记事本 - 文档1.txt",
            category_id=self.test_category_id,
            sub_category_id=self.test_sub_category_id,
            state=1,
            created_at=t1
        )
        self.print_records(app, "[Step 1]")
        
        # Step 2: 模拟禁用分类（手动将 state 改为 0）
        print(f"\n[Step 2] 禁用分类，记录 state 变为 0")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE category_map_cache 
                SET state = 0, updated_at = CURRENT_TIMESTAMP
                WHERE app = ? AND category_id = ?
            """, (app, self.test_category_id))
            conn.commit()
        self.print_records(app, "[Step 2]")
        
        # Step 3: 模拟禁用期间产生的新记录（不同 title，被分到其他分类）
        print(f"\n[Step 3] 禁用期间再次识别，产生新记录 (created_at = {t2}, 不同 title)")
        other_category_id = "other-cat-xxx"  # 模拟被分到其他分类
        self.insert_mock_category_map_record(
            app=app, 
            title="记事本 - 新文档.txt",  # 不同的 title
            category_id=other_category_id,
            sub_category_id="other-sub-xxx",
            state=1,
            created_at=t2
        )
        self.print_records(app, "[Step 3]")
        
        # Step 4: 恢复分类
        print(f"\n[Step 4] 恢复分类，调用 _enable_category_map_records_by_category")
        self.service._enable_category_map_records_by_category(self.test_category_id)
        self.print_records(app, "[Step 4]")
        
        # 验证结果
        records = self.get_category_map_records(app)
        print("\n验证结果:")
        
        # 对于单分类应用，应该只保留原始记录（t1），删除新记录（t2）
        if len(records) == 1 and records[0][4] == 1:  # 只有1条记录且 state=1
            print("✓ 测试通过: 单分类应用正确删除了冲突记录")
            return True
        else:
            print("✗ 测试失败: 记录数量或状态不正确")
            print(f"  预期: 1条记录, state=1")
            print(f"  实际: {len(records)}条记录")
            return False
    
    def test_multi_purpose_app(self):
        """
        测试多分类应用的状态同步逻辑
        
        预期行为：恢复时匹配 app + title 删除冲突记录
        """
        print("\n" + "="*60)
        print("测试2: 多分类应用 (chrome)")
        print("="*60)
        
        app = self.multi_purpose_app
        
        # 清理该应用的旧记录
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM category_map_cache WHERE app = ?", (app,))
            conn.commit()
        
        # 时间点
        t1 = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        t2 = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Step 1: 模拟启用状态下识别产生的记录
        print(f"\n[Step 1] 启用分类，识别产生记录 (created_at = {t1})")
        self.insert_mock_category_map_record(
            app=app, 
            title="GitHub - Pull Requests",  # 工作相关
            category_id=self.test_category_id,
            sub_category_id=self.test_sub_category_id,
            state=1,
            created_at=t1
        )
        self.print_records(app, "[Step 1]")
        
        # Step 2: 模拟禁用分类
        print(f"\n[Step 2] 禁用分类，记录 state 变为 0")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE category_map_cache 
                SET state = 0, updated_at = CURRENT_TIMESTAMP
                WHERE app = ? AND category_id = ?
            """, (app, self.test_category_id))
            conn.commit()
        self.print_records(app, "[Step 2]")
        
        # Step 3: 模拟禁用期间产生的新记录（不同 title，被分到其他分类）
        # 对于多分类应用，不同 title 应该保留（因为可能是不同用途）
        print(f"\n[Step 3] 禁用期间再次识别，产生新记录 (created_at = {t2}, 不同 title)")
        other_category_id = "entertainment-cat"  # 娱乐分类
        self.insert_mock_category_map_record(
            app=app, 
            title="YouTube - Music",  # 娱乐相关，不同 title
            category_id=other_category_id,
            sub_category_id="entertainment-sub",
            state=1,
            created_at=t2
        )
        self.print_records(app, "[Step 3]")
        
        # Step 4: 恢复分类
        print(f"\n[Step 4] 恢复分类，调用 _enable_category_map_records_by_category")
        self.service._enable_category_map_records_by_category(self.test_category_id)
        self.print_records(app, "[Step 4]")
        
        # 验证结果
        records = self.get_category_map_records(app)
        print("\n验证结果:")
        
        # 对于多分类应用，两条记录都应该保留（不同 title 是不同用途）
        if len(records) == 2:
            print("✓ 测试通过: 多分类应用正确保留了不同 title 的记录")
            return True
        else:
            print("✗ 测试失败: 记录数量不正确")
            print(f"  预期: 2条记录 (不同 title 应保留)")
            print(f"  实际: {len(records)}条记录")
            return False
    
    def test_multi_purpose_app_same_title(self):
        """
        测试多分类应用相同 title 的情况
        
        预期行为：恢复时相同 title 的冲突记录应被删除
        """
        print("\n" + "="*60)
        print("测试3: 多分类应用相同 title 场景 (chrome)")
        print("="*60)
        
        app = self.multi_purpose_app
        same_title = "GitHub - Same Page"
        
        # 清理该应用的旧记录
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM category_map_cache WHERE app = ?", (app,))
            conn.commit()
        
        # 时间点
        t1 = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        t2 = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Step 1: 模拟启用状态下识别产生的记录
        print(f"\n[Step 1] 启用分类，识别产生记录 (created_at = {t1})")
        self.insert_mock_category_map_record(
            app=app, 
            title=same_title,
            category_id=self.test_category_id,
            sub_category_id=self.test_sub_category_id,
            state=1,
            created_at=t1
        )
        self.print_records(app, "[Step 1]")
        
        # Step 2: 模拟禁用分类
        print(f"\n[Step 2] 禁用分类，记录 state 变为 0")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE category_map_cache 
                SET state = 0, updated_at = CURRENT_TIMESTAMP
                WHERE app = ? AND category_id = ?
            """, (app, self.test_category_id))
            conn.commit()
        self.print_records(app, "[Step 2]")
        
        # Step 3: 模拟禁用期间产生的新记录（相同 title，被分到其他分类）
        print(f"\n[Step 3] 禁用期间再次识别，产生新记录 (created_at = {t2}, 相同 title)")
        other_category_id = "other-cat-xxx"
        self.insert_mock_category_map_record(
            app=app, 
            title=same_title,  # 相同 title
            category_id=other_category_id,
            sub_category_id="other-sub-xxx",
            state=1,
            created_at=t2
        )
        self.print_records(app, "[Step 3]")
        
        # Step 4: 恢复分类
        print(f"\n[Step 4] 恢复分类，调用 _enable_category_map_records_by_category")
        self.service._enable_category_map_records_by_category(self.test_category_id)
        self.print_records(app, "[Step 4]")
        
        # 验证结果
        records = self.get_category_map_records(app)
        print("\n验证结果:")
        
        # 对于多分类应用相同 title，应该只保留原始记录
        if len(records) == 1 and records[0][4] == 1:
            print("✓ 测试通过: 多分类应用相同 title 正确删除了冲突记录")
            return True
        else:
            print("✗ 测试失败: 记录数量或状态不正确")
            print(f"  预期: 1条记录, state=1")
            print(f"  实际: {len(records)}条记录")
            return False
    
    def test_sub_category_sync(self):
        """
        测试子分类状态同步逻辑
        """
        print("\n" + "="*60)
        print("测试4: 子分类状态同步 (单分类应用)")
        print("="*60)
        
        app = "vscode.exe"  # 单分类应用
        
        # 清理该应用的旧记录
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM category_map_cache WHERE app = ?", (app,))
            conn.commit()
        
        # 时间点
        t1 = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        t2 = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Step 1: 插入记录
        print(f"\n[Step 1] 启用子分类，识别产生记录 (created_at = {t1})")
        self.insert_mock_category_map_record(
            app=app, 
            title="VSCode - project",
            category_id=self.test_category_id,
            sub_category_id=self.test_sub_category_id,
            state=1,
            created_at=t1
        )
        self.print_records(app, "[Step 1]")
        
        # Step 2: 禁用子分类
        print(f"\n[Step 2] 禁用子分类")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE category_map_cache 
                SET state = 0, updated_at = CURRENT_TIMESTAMP
                WHERE app = ? AND sub_category_id = ?
            """, (app, self.test_sub_category_id))
            conn.commit()
        self.print_records(app, "[Step 2]")
        
        # Step 3: 产生新记录
        print(f"\n[Step 3] 禁用期间产生新记录 (created_at = {t2})")
        self.insert_mock_category_map_record(
            app=app, 
            title="VSCode - other",
            category_id="other-cat",
            sub_category_id="other-sub",
            state=1,
            created_at=t2
        )
        self.print_records(app, "[Step 3]")
        
        # Step 4: 恢复子分类
        print(f"\n[Step 4] 恢复子分类，调用 _enable_category_map_records_by_sub_category")
        self.service._enable_category_map_records_by_sub_category(
            self.test_sub_category_id, 
            self.test_category_id
        )
        self.print_records(app, "[Step 4]")
        
        # 验证结果
        records = self.get_category_map_records(app)
        print("\n验证结果:")
        
        if len(records) == 1 and records[0][4] == 1:
            print("✓ 测试通过: 子分类同步正确删除了冲突记录")
            return True
        else:
            print("✗ 测试失败")
            return False
    
    def cleanup(self):
        """清理测试数据"""
        print("\n" + "="*60)
        print("清理测试数据")
        print("="*60)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 清理测试记录
            cursor.execute("DELETE FROM category_map_cache WHERE app IN (?, ?, ?)", 
                          (self.single_purpose_app, self.multi_purpose_app, "vscode.exe"))
            cursor.execute("DELETE FROM sub_category WHERE id = ?", (self.test_sub_category_id,))
            cursor.execute("DELETE FROM category WHERE id = ?", (self.test_category_id,))
            
            conn.commit()
        
        print("✓ 测试数据已清理")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("开始测试分类状态同步逻辑")
        print("="*60)
        
        results = []
        
        try:
            self.setup()
            
            results.append(("单分类应用测试", self.test_single_purpose_app()))
            results.append(("多分类应用不同title测试", self.test_multi_purpose_app()))
            results.append(("多分类应用相同title测试", self.test_multi_purpose_app_same_title()))
            results.append(("子分类状态同步测试", self.test_sub_category_sync()))
            
        finally:
            self.cleanup()
        
        # 打印测试结果汇总
        print("\n" + "="*60)
        print("测试结果汇总")
        print("="*60)
        
        passed = 0
        failed = 0
        for name, result in results:
            status = "✓ 通过" if result else "✗ 失败"
            print(f"  {name}: {status}")
            if result:
                passed += 1
            else:
                failed += 1
        
        print(f"\n总计: {passed} 通过, {failed} 失败")
        
        return failed == 0


if __name__ == "__main__":
    test = TestCategoryStateSync()
    success = test.run_all_tests()
    sys.exit(0 if success else 1)
