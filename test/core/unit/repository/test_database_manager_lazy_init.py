"""
DatabaseManager readonly 懒加载单元测试

issue #11: readonly 模式的 DatabaseManager 不应在 __init__ 中创建连接池，
应延迟到首次 get_connection() 时初始化，避免 AW 数据库文件不存在时应用启动崩溃。

测试场景：
1. readonly DatabaseManager 构造时不崩溃（DB 路径不存在）
2. readonly DatabaseManager 首次 get_connection() 时抛出 OperationalError（路径不存在）
3. 非 readonly DatabaseManager 仍然在构造时初始化连接池（回归保护）
4. readonly DatabaseManager 路径存在时懒加载正常工作
"""
import sqlite3

import pytest

from lifeprism.repository.database_manager import DatabaseManager

pytestmark = pytest.mark.core


class TestReadonlyLazyInit:
    """readonly DatabaseManager 懒加载测试"""

    def test_readonly_construct_does_not_crash_when_db_missing(self, tmp_path):
        """
        测试1：readonly DatabaseManager 构造时不崩溃（DB 路径不存在）

        前置条件：数据库文件路径不存在
        预期结果：构造成功，不抛出异常，连接池未初始化（None）
        """
        missing_path = tmp_path / "missing_aw.db"
        assert not missing_path.exists()

        # 构造不应抛出异常
        mgr = DatabaseManager(
            DB_PATH=str(missing_path), use_pool=True, pool_size=1, readonly=True
        )

        # 连接池应未初始化（懒加载）
        assert mgr._connection_pool is None
        assert mgr.readonly is True
        assert mgr.use_pool is True

    def test_readonly_get_connection_raises_operational_error_when_db_missing(
        self, tmp_path
    ):
        """
        测试2：readonly DatabaseManager 首次 get_connection() 时抛出 OperationalError

        前置条件：数据库文件路径不存在，readonly 模式
        预期结果：首次 get_connection() 触发懒加载并抛出 sqlite3.OperationalError
        """
        missing_path = tmp_path / "missing_aw.db"
        assert not missing_path.exists()

        mgr = DatabaseManager(
            DB_PATH=str(missing_path), use_pool=True, pool_size=1, readonly=True
        )

        # 构造时连接池未初始化
        assert mgr._connection_pool is None

        # 首次使用应触发懒加载并抛出 OperationalError（在 try 块之外，不包装为 DataAccessError）
        with pytest.raises(sqlite3.OperationalError):
            with mgr.get_connection() as conn:
                conn.execute("SELECT 1")

    def test_readonly_lazy_init_works_when_db_exists(self, tmp_path):
        """
        测试4：readonly DatabaseManager 路径存在时懒加载正常工作

        前置条件：数据库文件存在，readonly 模式
        预期结果：构造时连接池未初始化；首次 get_connection() 时延迟初始化连接池，查询正常返回
        """
        db_path = tmp_path / "aw_exists.db"
        # 创建一个真实的 SQLite 数据库文件并写入测试数据
        setup_conn = sqlite3.connect(str(db_path))
        setup_conn.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
        setup_conn.execute("INSERT INTO test_table VALUES (1, 'hello')")
        setup_conn.commit()
        setup_conn.close()
        assert db_path.exists()

        mgr = DatabaseManager(
            DB_PATH=str(db_path), use_pool=True, pool_size=2, readonly=True
        )

        # 构造时连接池未初始化（懒加载）
        assert mgr._connection_pool is None

        # 首次使用触发懒加载，查询应正常返回
        with mgr.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM test_table")
            row = cursor.fetchone()

        assert row is not None
        assert row[0] == 1
        assert row[1] == "hello"

        # 懒加载后连接池已初始化
        assert mgr._connection_pool is not None

        mgr._close_connection_pool()


class TestNonReadonlyEagerInit:
    """非 readonly DatabaseManager 立即初始化连接池（回归保护）"""

    def test_non_readonly_initializes_pool_in_init(self, tmp_path):
        """
        测试3：非 readonly DatabaseManager 仍然在构造时初始化连接池

        前置条件：数据库文件存在，非 readonly 模式
        预期结果：构造后连接池立即初始化（不为 None），且预创建 pool_size 个连接
        """
        db_path = tmp_path / "lw.db"
        db_path.touch()
        assert db_path.exists()

        mgr = DatabaseManager(
            DB_PATH=str(db_path), use_pool=True, pool_size=3, readonly=False
        )

        # 非 readonly 应在 __init__ 中立即初始化连接池
        assert mgr._connection_pool is not None
        # 预创建的连接数应等于 pool_size
        assert mgr._connection_pool.qsize() == 3
        assert mgr.readonly is False

        mgr._close_connection_pool()
