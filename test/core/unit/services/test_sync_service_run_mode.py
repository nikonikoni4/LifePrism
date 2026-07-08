"""
SyncService run_mode 守卫单元测试

验证 SyncService 在非 full 模式下的行为：
1. incremental_sync() 在非 full 模式下抛出 ValidationError
2. sync_by_time_range() 在非 full 模式下抛出 ValidationError
3. full 模式下不抛出（不执行实际同步逻辑，仅验证守卫不触发）

注意：run_mode 是 property，通过环境变量 LIFEPRISM_RUN_MODE 控制。
"""

import os
from unittest.mock import patch

import pytest

from lifeprism.config.settings_manager import settings
from lifeprism.server.errors.error_codes import DEMO_MODE_NOT_SUPPORTED
from lifeprism.utils.exceptions import ValidationError

pytestmark = pytest.mark.core


class TestSyncServiceRunModeGuard:
    """测试 SyncService 的 run_mode 守卫"""

    @pytest.mark.asyncio
    async def test_incremental_sync_raises_in_web_demo_mode(self):
        """incremental_sync() 在 web_demo 模式下抛出 ValidationError"""
        from lifeprism.server.services.sync_service import SyncService

        with patch.dict(os.environ, {"LIFEPRISM_RUN_MODE": "web_demo"}):
            service = SyncService()
            with pytest.raises(ValidationError) as exc_info:
                await service.incremental_sync()

            assert exc_info.value.code == DEMO_MODE_NOT_SUPPORTED

    @pytest.mark.asyncio
    async def test_incremental_sync_raises_in_agent_only_mode(self):
        """incremental_sync() 在 agent_only 模式下抛出 ValidationError"""
        from lifeprism.server.services.sync_service import SyncService

        with patch.dict(os.environ, {"LIFEPRISM_RUN_MODE": "agent_only"}):
            service = SyncService()
            with pytest.raises(ValidationError) as exc_info:
                await service.incremental_sync()

            assert exc_info.value.code == DEMO_MODE_NOT_SUPPORTED

    @pytest.mark.asyncio
    async def test_sync_by_time_range_raises_in_web_demo_mode(self):
        """sync_by_time_range() 在 web_demo 模式下抛出 ValidationError"""
        from lifeprism.server.services.sync_service import SyncService

        with patch.dict(os.environ, {"LIFEPRISM_RUN_MODE": "web_demo"}):
            service = SyncService()
            with pytest.raises(ValidationError) as exc_info:
                await service.sync_by_time_range(
                    start_time="2026-01-01 00:00:00",
                    end_time="2026-01-02 00:00:00",
                )

            assert exc_info.value.code == DEMO_MODE_NOT_SUPPORTED

    @pytest.mark.asyncio
    async def test_sync_by_time_range_raises_in_agent_only_mode(self):
        """sync_by_time_range() 在 agent_only 模式下抛出 ValidationError"""
        from lifeprism.server.services.sync_service import SyncService

        with patch.dict(os.environ, {"LIFEPRISM_RUN_MODE": "agent_only"}):
            service = SyncService()
            with pytest.raises(ValidationError) as exc_info:
                await service.sync_by_time_range(
                    start_time="2026-01-01 00:00:00",
                    end_time="2026-01-02 00:00:00",
                )

            assert exc_info.value.code == DEMO_MODE_NOT_SUPPORTED

    @pytest.mark.asyncio
    async def test_incremental_sync_does_not_raise_demo_mode_in_full_mode(self):
        """incremental_sync() 在 full 模式下不抛出 DEMO_MODE_NOT_SUPPORTED

        注意：full 模式下会继续执行同步逻辑，可能因测试环境缺少依赖而抛其他异常，
        但不应抛出 ValidationError(DEMO_MODE_NOT_SUPPORTED)。
        """
        from lifeprism.server.services.sync_service import SyncService

        with patch.dict(os.environ, {}, clear=True):
            service = SyncService()
            try:
                await service.incremental_sync()
            except ValidationError as e:
                if e.code == DEMO_MODE_NOT_SUPPORTED:
                    pytest.fail("full 模式不应抛出 DEMO_MODE_NOT_SUPPORTED")
            except Exception:
                # full 模式下可能因测试环境缺少依赖而抛其他异常，这是预期的
                pass

    @pytest.mark.asyncio
    async def test_sync_by_time_range_does_not_raise_demo_mode_in_full_mode(self):
        """sync_by_time_range() 在 full 模式下不抛出 DEMO_MODE_NOT_SUPPORTED"""
        from lifeprism.server.services.sync_service import SyncService

        with patch.dict(os.environ, {}, clear=True):
            service = SyncService()
            try:
                await service.sync_by_time_range(
                    start_time="2026-01-01 00:00:00",
                    end_time="2026-01-02 00:00:00",
                )
            except ValidationError as e:
                if e.code == DEMO_MODE_NOT_SUPPORTED:
                    pytest.fail("full 模式不应抛出 DEMO_MODE_NOT_SUPPORTED")
            except Exception:
                pass
