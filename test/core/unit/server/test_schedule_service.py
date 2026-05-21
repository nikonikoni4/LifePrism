"""
ScheduleService 测试

测试定时任务和间隔任务是否能正确执行。
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from lifeprism.server.services.schedule_service import ScheduleService


class TestScheduleService:
    """ScheduleService 测试类"""

    @pytest.fixture
    def schedule_service(self):
        """创建 ScheduleService 实例"""
        return ScheduleService()

    @pytest.fixture
    def mock_scheduler(self):
        """创建模拟的调度器"""
        scheduler = MagicMock(spec=AsyncIOScheduler)
        scheduler.start = MagicMock()
        scheduler.shutdown = MagicMock()
        scheduler.add_job = MagicMock()
        scheduler.remove_job = MagicMock()
        scheduler.get_jobs = MagicMock(return_value=[])
        return scheduler

    def test_init(self, schedule_service):
        """测试初始化"""
        assert schedule_service._scheduler is None

    def test_start(self, schedule_service, mock_scheduler):
        """测试启动调度器"""
        # 模拟 AsyncIOScheduler
        with pytest.MonkeyPatch.context() as m:
            m.setattr("lifeprism.server.services.schedule_service.AsyncIOScheduler", 
                      lambda: mock_scheduler)
            schedule_service.start()
            
            assert schedule_service._scheduler is not None
            mock_scheduler.start.assert_called_once()

    def test_start_already_started(self, schedule_service, mock_scheduler):
        """测试重复启动调度器"""
        schedule_service._scheduler = mock_scheduler
        
        with pytest.MonkeyPatch.context() as m:
            m.setattr("lifeprism.server.services.schedule_service.AsyncIOScheduler", 
                      lambda: mock_scheduler)
            schedule_service.start()
            
            # 不应该再次调用 start
            mock_scheduler.start.assert_not_called()

    def test_shutdown(self, schedule_service, mock_scheduler):
        """测试关闭调度器"""
        schedule_service._scheduler = mock_scheduler
        
        schedule_service.shutdown()
        
        mock_scheduler.shutdown.assert_called_once_with(wait=True)
        assert schedule_service._scheduler is None

    def test_shutdown_not_started(self, schedule_service):
        """测试关闭未启动的调度器"""
        # 应该不会抛出异常
        schedule_service.shutdown()

    def test_add_interval_job_seconds(self, schedule_service, mock_scheduler):
        """测试添加秒级间隔任务"""
        schedule_service._scheduler = mock_scheduler
        
        def test_func():
            pass
        
        mock_job = MagicMock()
        mock_job.id = "test_job_1"
        mock_scheduler.add_job.return_value = mock_job
        
        job_id = schedule_service.add_interval_job(test_func, seconds=30)
        
        assert job_id == "test_job_1"
        mock_scheduler.add_job.assert_called_once()

    def test_add_interval_job_minutes(self, schedule_service, mock_scheduler):
        """测试添加分钟级间隔任务"""
        schedule_service._scheduler = mock_scheduler
        
        def test_func():
            pass
        
        mock_job = MagicMock()
        mock_job.id = "test_job_2"
        mock_scheduler.add_job.return_value = mock_job
        
        job_id = schedule_service.add_interval_job(test_func, minutes=1.2)
        
        assert job_id == "test_job_2"
        mock_scheduler.add_job.assert_called_once()

    def test_add_interval_job_not_started(self, schedule_service):
        """测试在调度器未启动时添加间隔任务"""
        def test_func():
            pass
        
        with pytest.raises(RuntimeError, match="调度器未启动"):
            schedule_service.add_interval_job(test_func, seconds=30)

    def test_add_interval_job_no_interval(self, schedule_service, mock_scheduler):
        """测试添加间隔任务时未指定时间间隔"""
        schedule_service._scheduler = mock_scheduler
        
        def test_func():
            pass
        
        with pytest.raises(ValueError, match="必须指定至少一个时间间隔参数"):
            schedule_service.add_interval_job(test_func)

    def test_add_cron_job(self, schedule_service, mock_scheduler):
        """测试添加 Cron 表达式任务"""
        schedule_service._scheduler = mock_scheduler
        
        def test_func():
            pass
        
        mock_job = MagicMock()
        mock_job.id = "cron_job_1"
        mock_scheduler.add_job.return_value = mock_job
        
        job_id = schedule_service.add_cron_job(test_func, "0 10 * * *")
        
        assert job_id == "cron_job_1"
        mock_scheduler.add_job.assert_called_once()

    def test_add_cron_job_not_started(self, schedule_service):
        """测试在调度器未启动时添加 Cron 任务"""
        def test_func():
            pass
        
        with pytest.raises(RuntimeError, match="调度器未启动"):
            schedule_service.add_cron_job(test_func, "0 10 * * *")

    def test_remove_job(self, schedule_service, mock_scheduler):
        """测试移除任务"""
        schedule_service._scheduler = mock_scheduler
        
        schedule_service.remove_job("test_job_1")
        
        mock_scheduler.remove_job.assert_called_once_with("test_job_1")

    def test_remove_job_not_started(self, schedule_service):
        """测试在调度器未启动时移除任务"""
        with pytest.raises(RuntimeError, match="调度器未启动"):
            schedule_service.remove_job("test_job_1")

    def test_get_jobs(self, schedule_service, mock_scheduler):
        """测试获取任务列表"""
        schedule_service._scheduler = mock_scheduler
        
        mock_jobs = [MagicMock(), MagicMock()]
        mock_scheduler.get_jobs.return_value = mock_jobs
        
        jobs = schedule_service.get_jobs()
        
        assert len(jobs) == 2
        mock_scheduler.get_jobs.assert_called_once()

    def test_get_jobs_not_started(self, schedule_service):
        """测试在调度器未启动时获取任务列表"""
        with pytest.raises(RuntimeError, match="调度器未启动"):
            schedule_service.get_jobs()


class TestScheduleServiceIntegration:
    """ScheduleService 集成测试类（测试实际调度功能）"""

    @pytest_asyncio.fixture
    async def schedule_service(self):
        """创建并启动 ScheduleService 实例"""
        service = ScheduleService()
        service.start()
        yield service
        service.shutdown()

    @pytest.mark.asyncio
    async def test_interval_job_execution_seconds(self, schedule_service):
        """测试间隔任务是否能正确执行（秒级）"""
        execution_count = 0
        
        def test_func():
            nonlocal execution_count
            execution_count += 1
        
        # 添加30秒间隔的任务
        job_id = schedule_service.add_interval_job(test_func, seconds=30, job_id="test_30s")
        
        # 等待足够的时间让任务执行（等待35秒以确保至少执行一次）
        await asyncio.sleep(35)
        
        # 验证任务是否被执行
        assert execution_count > 0, "30秒间隔任务未被执行"
        
        # 清理
        schedule_service.remove_job(job_id)

    @pytest.mark.asyncio
    async def test_interval_job_execution_quick(self, schedule_service):
        """测试间隔任务是否能正确执行（快速验证）"""
        execution_count = 0
        
        def test_func():
            nonlocal execution_count
            execution_count += 1
        
        # 添加1秒间隔的任务
        job_id = schedule_service.add_interval_job(test_func, seconds=1, job_id="test_1s")
        
        # 等待足够的时间让任务执行几次（等待3秒）
        await asyncio.sleep(3)
        
        # 验证任务是否被执行多次
        assert execution_count >= 2, f"1秒间隔任务应至少执行2次，实际执行了{execution_count}次"
        
        # 清理
        schedule_service.remove_job(job_id)

    @pytest.mark.asyncio
    async def test_interval_job_execution_minutes(self, schedule_service):
        """测试间隔任务是否能正确执行（分钟级）"""
        execution_count = 0
        
        def test_func():
            nonlocal execution_count
            execution_count += 1
        
        # 添加1.2分钟间隔的任务（72秒）
        job_id = schedule_service.add_interval_job(test_func, minutes=1.2, job_id="test_1.2min")
        
        # 等待足够的时间让任务执行（等待80秒以确保至少执行一次）
        await asyncio.sleep(80)
        
        # 验证任务是否被执行
        assert execution_count > 0, "1.2分钟间隔任务未被执行"
        
        # 清理
        schedule_service.remove_job(job_id)

    @pytest.mark.asyncio
    async def test_cron_job_execution(self, schedule_service):
        """测试 Cron 定时任务是否能正确执行"""
        execution_count = 0
        
        def test_func():
            nonlocal execution_count
            execution_count += 1
        
        # 添加每分钟执行的任务（用于测试）
        job_id = schedule_service.add_cron_job(test_func, "* * * * *", job_id="test_cron")
        
        # 等待足够的时间让任务执行（等待65秒以确保至少执行一次）
        await asyncio.sleep(65)
        
        # 验证任务是否被执行
        assert execution_count > 0, "Cron 定时任务未被执行"
        
        # 清理
        schedule_service.remove_job(job_id)

    @pytest.mark.asyncio
    async def test_multiple_interval_jobs(self, schedule_service):
        """测试多个间隔任务是否能同时执行"""
        execution_count_30s = 0
        execution_count_1_2min = 0
        
        def test_func_30s():
            nonlocal execution_count_30s
            execution_count_30s += 1
        
        def test_func_1_2min():
            nonlocal execution_count_1_2min
            execution_count_1_2min += 1
        
        # 添加两个不同间隔的任务
        job_id_30s = schedule_service.add_interval_job(test_func_30s, seconds=30, job_id="test_30s_multi")
        job_id_1_2min = schedule_service.add_interval_job(test_func_1_2min, minutes=1.2, job_id="test_1.2min_multi")
        
        # 等待足够的时间让两个任务都执行（等待80秒）
        await asyncio.sleep(80)
        
        # 验证两个任务是否都被执行
        assert execution_count_30s > 0, "30秒间隔任务未被执行"
        assert execution_count_1_2min > 0, "1.2分钟间隔任务未被执行"
        
        # 清理
        schedule_service.remove_job(job_id_30s)
        schedule_service.remove_job(job_id_1_2min)

    @pytest.mark.asyncio
    async def test_job_removal(self, schedule_service):
        """测试任务移除功能"""
        execution_count = 0
        
        def test_func():
            nonlocal execution_count
            execution_count += 1
        
        # 添加任务
        job_id = schedule_service.add_interval_job(test_func, seconds=1, job_id="test_removal")
        
        # 等待任务执行几次
        await asyncio.sleep(3)
        
        # 记录移除前的执行次数
        count_before_removal = execution_count
        
        # 移除任务
        schedule_service.remove_job(job_id)
        
        # 等待一段时间，确保任务不再执行
        await asyncio.sleep(3)
        
        # 验证任务已停止执行
        assert execution_count == count_before_removal, "任务移除后仍在执行"

    @pytest.mark.asyncio
    async def test_get_jobs_list(self, schedule_service):
        """测试获取任务列表功能"""
        def test_func():
            pass
        
        # 添加几个任务
        job_id_1 = schedule_service.add_interval_job(test_func, seconds=30, job_id="test_job_1")
        job_id_2 = schedule_service.add_interval_job(test_func, seconds=60, job_id="test_job_2")
        
        # 获取任务列表
        jobs = schedule_service.get_jobs()
        
        # 验证任务列表
        assert len(jobs) >= 2, "任务列表应包含至少两个任务"
        
        # 清理
        schedule_service.remove_job(job_id_1)
        schedule_service.remove_job(job_id_2)