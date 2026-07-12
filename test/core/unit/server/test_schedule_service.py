"""
ScheduleService 测试

测试定时任务和间隔任务是否能正确执行。
"""

import asyncio
import json
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
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
                      lambda *args, **kwargs: mock_scheduler)
            schedule_service.start()
            
            assert schedule_service._scheduler is not None
            mock_scheduler.start.assert_called_once()

    def test_start_already_started(self, schedule_service, mock_scheduler):
        """测试重复启动调度器"""
        schedule_service._scheduler = mock_scheduler
        
        with pytest.MonkeyPatch.context() as m:
            m.setattr("lifeprism.server.services.schedule_service.AsyncIOScheduler", 
                      lambda *args, **kwargs: mock_scheduler)
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


class TestScheduleServiceCronState:
    """ScheduleService Cron 状态持久化测试类"""

    @pytest.fixture
    def temp_state_file(self):
        """创建临时状态文件路径"""
        temp_dir = Path("test_temp")
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / ".schedule_state_test.json"
        yield temp_file
        # 清理
        if temp_file.exists():
            temp_file.unlink()
        if temp_dir.exists() and not list(temp_dir.iterdir()):
            temp_dir.rmdir()

    @pytest.fixture
    def schedule_service_with_temp_state(self, temp_state_file):
        """创建使用临时状态文件的 ScheduleService 实例"""
        service = ScheduleService()
        service._state_file_path = temp_state_file
        return service

    def test_load_cron_state_empty(self, schedule_service_with_temp_state):
        """测试加载不存在的状态文件"""
        state = schedule_service_with_temp_state._load_cron_state()
        assert state == {}, "不存在的状态文件应返回空字典"

    def test_save_and_load_cron_state(self, schedule_service_with_temp_state, temp_state_file):
        """测试保存和加载状态"""
        # 保存状态
        schedule_service_with_temp_state._save_cron_state("update_memory", "2026-05-22")

        # 验证文件存在
        assert temp_state_file.exists(), "状态文件应该被创建"

        # 加载状态
        state = schedule_service_with_temp_state._load_cron_state()
        assert state == {"update_memory": "2026-05-22"}, "加载的状态应与保存的一致"

    def test_save_multiple_cron_states(self, schedule_service_with_temp_state):
        """测试保存多个任务状态"""
        # 保存第一个任务状态
        schedule_service_with_temp_state._save_cron_state("update_memory", "2026-05-22")

        # 保存第二个任务状态
        schedule_service_with_temp_state._save_cron_state("another_job", "2026-05-23")

        # 加载状态
        state = schedule_service_with_temp_state._load_cron_state()
        assert state == {
            "update_memory": "2026-05-22",
            "another_job": "2026-05-23"
        }, "应该包含两个任务的状态"

    def test_update_existing_cron_state(self, schedule_service_with_temp_state):
        """测试更新已存在的任务状态"""
        # 保存初始状态
        schedule_service_with_temp_state._save_cron_state("update_memory", "2026-05-22")

        # 更新状态
        schedule_service_with_temp_state._save_cron_state("update_memory", "2026-05-23")

        # 加载状态
        state = schedule_service_with_temp_state._load_cron_state()
        assert state == {"update_memory": "2026-05-23"}, "状态应该被更新"

    def test_should_execute_cron_today_no_record(self, schedule_service_with_temp_state):
        """测试没有执行记录时应该执行"""
        should_execute = schedule_service_with_temp_state._should_execute_cron_today("update_memory")
        assert should_execute is True, "没有执行记录时应该返回 True"

    def test_should_execute_cron_today_same_date(self, schedule_service_with_temp_state):
        """测试同一天已执行时不应该再执行"""
        from datetime import datetime, timezone
        # 使用 UTC 日期匹配代码行为（_should_execute_cron_today 使用 UTC）
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 保存今天的执行记录
        schedule_service_with_temp_state._save_cron_state("update_memory", today)

        # 检查是否应该执行
        should_execute = schedule_service_with_temp_state._should_execute_cron_today("update_memory")
        assert should_execute is False, "同一天已执行时应该返回 False"

    def test_should_execute_cron_today_different_date(self, schedule_service_with_temp_state):
        """测试不同日期时应该执行"""
        # 保存昨天的执行记录
        schedule_service_with_temp_state._save_cron_state("update_memory", "2026-05-21")

        # 检查是否应该执行（假设今天是 2026-05-22）
        should_execute = schedule_service_with_temp_state._should_execute_cron_today("update_memory")
        assert should_execute is True, "不同日期时应该返回 True"

    def test_load_cron_state_corrupted_file(self, schedule_service_with_temp_state, temp_state_file):
        """测试加载损坏的状态文件"""
        # 创建损坏的 JSON 文件
        temp_state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_state_file.write_text("invalid json content", encoding='utf-8')

        # 加载状态应该返回空字典并记录警告
        state = schedule_service_with_temp_state._load_cron_state()
        assert state == {}, "损坏的状态文件应返回空字典"

    def test_state_file_json_format(self, schedule_service_with_temp_state, temp_state_file):
        """测试状态文件的 JSON 格式"""
        # 保存状态
        schedule_service_with_temp_state._save_cron_state("update_memory", "2026-05-22")

        # 读取文件内容
        with open(temp_state_file, 'r', encoding='utf-8') as f:
            content = json.load(f)

        # 验证格式
        assert isinstance(content, dict), "状态文件应该是 JSON 对象"
        assert "update_memory" in content, "应该包含任务 ID"
        assert content["update_memory"] == "2026-05-22", "应该包含正确的日期"

    @pytest.mark.asyncio
    async def test_execute_cron_with_state(self, schedule_service_with_temp_state):
        """测试执行 Cron 任务并记录状态"""
        from datetime import datetime, timezone

        execution_count = 0

        async def test_func():
            nonlocal execution_count
            execution_count += 1

        # 执行任务
        await schedule_service_with_temp_state._execute_cron_with_state(test_func, "test_job")

        # 验证任务被执行
        assert execution_count == 1, "任务应该被执行一次"

        # 验证状态被保存（_execute_cron_with_state 使用 UTC 日期记录）
        state = schedule_service_with_temp_state._load_cron_state()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert state.get("test_job") == today, "执行后应该保存今天的 UTC 日期"

    @pytest.mark.asyncio
    async def test_execute_cron_with_state_on_failure(self, schedule_service_with_temp_state):
        """测试 Cron 任务执行失败时不保存状态"""
        async def failing_func():
            raise Exception("Test error")

        # 执行任务（应该捕获异常）
        await schedule_service_with_temp_state._execute_cron_with_state(failing_func, "failing_job")

        # 验证状态未被保存
        state = schedule_service_with_temp_state._load_cron_state()
        assert "failing_job" not in state, "失败的任务不应该保存状态"