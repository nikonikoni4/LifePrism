"""
启动入口集成测试

验证三个启动入口（main.py / main_web_demo.py / main_agent_only.py）的导入行为和依赖隔离：
1. 各入口可正常导入
2. Web Demo 不加载 Monitor 模块
3. Agent Only 不加载 FastAPI 和 Monitor 模块
4. bootstrap 模块提供共享函数
"""

import sys

import pytest

pytestmark = pytest.mark.core


class TestStartupModeImports:
    """测试三个启动入口的导入行为"""

    def test_main_py_imports_cleanly(self):
        """main.py（Windows 桌面完整版）可正常导入"""
        import lifeprism.server.main

        assert hasattr(lifeprism.server.main, "app")
        assert hasattr(lifeprism.server.main, "lifespan")

    def test_web_demo_imports_cleanly(self):
        """main_web_demo.py（Linux Web Demo）可正常导入"""
        import lifeprism.server.main_web_demo

        assert hasattr(lifeprism.server.main_web_demo, "app")
        assert hasattr(lifeprism.server.main_web_demo, "lifespan")

    def test_agent_only_imports_cleanly(self):
        """main_agent_only.py（Linux Agent Only）可正常导入"""
        import lifeprism.server.main_agent_only

        assert hasattr(lifeprism.server.main_agent_only, "main")
        assert callable(lifeprism.server.main_agent_only.main)

    def test_bootstrap_provides_shared_functions(self):
        """bootstrap 模块提供共享的初始化函数"""
        from lifeprism.server import bootstrap

        assert hasattr(bootstrap, "init_database_full")
        assert hasattr(bootstrap, "start_agent_and_channel")
        assert hasattr(bootstrap, "stop_agent_and_channel")
        assert callable(bootstrap.init_database_full)
        assert callable(bootstrap.start_agent_and_channel)
        assert callable(bootstrap.stop_agent_and_channel)


class TestDependencyIsolation:
    """测试依赖隔离：各入口不加载不该有的模块"""

    def test_web_demo_has_no_monitor_dependency(self):
        """Web Demo 不加载 lifeprism.monitor.windows_monitor 模块"""
        # 清除可能已加载的模块
        for key in list(sys.modules.keys()):
            if key.startswith("lifeprism.monitor.windows_monitor"):
                del sys.modules[key]

        # 重新导入 Web Demo
        import importlib

        import lifeprism.server.main_web_demo

        importlib.reload(lifeprism.server.main_web_demo)

        monitor_modules = [
            m for m in sys.modules if m.startswith("lifeprism.monitor.windows_monitor")
        ]
        assert monitor_modules == [], f"Web Demo 不应加载 Monitor 模块，但加载了: {monitor_modules}"

    def test_agent_only_has_no_fastapi_dependency(self):
        """Agent Only 不加载 fastapi 模块"""
        # 清除已加载的 fastapi
        for key in list(sys.modules.keys()):
            if key.startswith("fastapi"):
                del sys.modules[key]

        # 重新导入 Agent Only
        import importlib

        import lifeprism.server.main_agent_only

        importlib.reload(lifeprism.server.main_agent_only)

        fastapi_loaded = any(m.startswith("fastapi") for m in sys.modules)
        assert not fastapi_loaded, "Agent Only 不应加载 FastAPI"

    def test_agent_only_has_no_monitor_dependency(self):
        """Agent Only 不加载 lifeprism.monitor.windows_monitor 模块"""
        for key in list(sys.modules.keys()):
            if key.startswith("lifeprism.monitor.windows_monitor"):
                del sys.modules[key]

        import importlib

        import lifeprism.server.main_agent_only

        importlib.reload(lifeprism.server.main_agent_only)

        monitor_modules = [
            m for m in sys.modules if m.startswith("lifeprism.monitor.windows_monitor")
        ]
        assert monitor_modules == [], f"Agent Only 不应加载 Monitor 模块，但加载了: {monitor_modules}"


class TestWebDemoRoutes:
    """测试 Web Demo 的路由注册"""

    def test_web_demo_has_api_routes(self):
        """Web Demo 注册了 API 路由"""
        import lifeprism.server.main_web_demo

        routes = lifeprism.server.main_web_demo.app.routes
        # 至少有 100+ 路由（包含所有 v2 API）
        assert len(routes) > 100, f"Web Demo 应有大量路由，实际: {len(routes)}"

    def test_web_demo_has_health_endpoint(self):
        """Web Demo 有 /health 健康检查端点"""
        import lifeprism.server.main_web_demo

        health_routes = [
            r for r in lifeprism.server.main_web_demo.app.routes
            if hasattr(r, "path") and r.path == "/health"
        ]
        assert len(health_routes) == 1, "Web Demo 应有 /health 端点"

    def test_web_demo_has_root_endpoint(self):
        """Web Demo 有 / 根路径端点"""
        import lifeprism.server.main_web_demo

        root_routes = [
            r for r in lifeprism.server.main_web_demo.app.routes
            if hasattr(r, "path") and r.path == "/"
        ]
        assert len(root_routes) == 1, "Web Demo 应有 / 根路径端点"
