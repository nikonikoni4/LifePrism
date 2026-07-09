"""
ScheduleService run_mode 守卫单元测试

验证 ScheduleService.start() 在非 full 模式下的行为：
1. web_demo 模式不注册任务，不创建调度器
2. agent_only 模式不注册任务，不创建调度器
3. full 模式正常注册任务（回归保护）

注意：run_mode 通过 set_runtime_config() 注入，测试中 patch _runtime_config。
"""

from unittest.mock import patch

import pytest

from lifeprism.config.settings_manager import settings

pytestmark = pytest.mark.core


class TestScheduleServiceRunModeGuard:
    """测试 ScheduleService 的 run_mode 守卫"""

    def test_start_skips_in_web_demo_mode(self):
        """web_demo 模式下 start() 不注册任务"""
        from lifeprism.server.services.schedule_service import ScheduleService

        service = ScheduleService()

        with patch.object(settings, "_runtime_config", {"run_mode": "web_demo"}):
            service.start()

        # 调度器未创建
        assert service._scheduler is None

    def test_start_skips_in_agent_only_mode(self):
        """agent_only 模式下 start() 不注册任务"""
        from lifeprism.server.services.schedule_service import ScheduleService

        service = ScheduleService()

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}):
            service.start()

        assert service._scheduler is None

    @pytest.mark.asyncio
    async def test_start_registers_jobs_in_full_mode(self):
        """full 模式下 start() 正常创建调度器（回归保护）"""
        from lifeprism.server.services.schedule_service import ScheduleService

        service = ScheduleService()

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}):
            service.start()

        # 调度器应被创建
        assert service._scheduler is not None

        # 清理
        if service._scheduler:
            service.shutdown()
