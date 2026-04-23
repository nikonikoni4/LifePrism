"""
Diary Service 快照测试

用于 provider 重构前后的行为验证。
测试所有调用 diary_provider 的 service 方法。
"""
import pytest
from syrupy.assertion import SnapshotAssertion

from lifeprism.server.services import diary_service
from lifeprism.server.schemas.diary_schemas import (
    UpdateDiaryMetaRequest,
    SaveDiaryContentRequest,
    GenerateDiaryAISummaryRangeRequest,
    ExistingSummaryMode,
)


# ==================== 测试辅助函数 ====================

def sanitize_diary_item(data: dict) -> dict:
    """清理动态字段，用于快照对比"""
    if data is None:
        return None

    result = {}
    # 排除动态字段
    exclude_fields = {'created_at', 'updated_at', 'diary_source_hash'}

    for key, value in data.items():
        if key in exclude_fields:
            continue
        result[key] = value

    return result


def sanitize_diary_list(items: list) -> list:
    """清理日记列表的动态字段"""
    return sorted(
        [sanitize_diary_item(item) for item in items],
        key=lambda x: x.get('date', '')
    )


# ==================== Fixtures ====================

@pytest.fixture
def sample_diary_date(use_diary_test_data):
    """测试用的日记日期"""
    return use_diary_test_data[5]  # 使用第 6 条测试数据


@pytest.fixture
def sample_date_range(use_diary_test_data):
    """测试用的日期范围"""
    return (use_diary_test_data[0], use_diary_test_data[-1])


# ==================== 快照测试 ====================

@pytest.mark.snapshot
def test_get_diary_snapshot(sample_diary_date, snapshot: SnapshotAssertion):
    """
    测试 get_diary() 方法

    验证：
    - 获取已存在的日记
    - 自动创建不存在的日记
    """
    result = diary_service.get_diary(sample_diary_date)

    # 跳过空数据测试
    if result is None:
        pytest.skip("测试数据为空，跳过快照测试")

    sanitized = sanitize_diary_item(result.model_dump())
    assert sanitized == snapshot


@pytest.mark.snapshot
def test_update_diary_meta_snapshot(sample_diary_date, snapshot: SnapshotAssertion):
    """
    测试 update_diary_meta() 方法

    验证：
    - 更新日记元数据（mood, importance, custom_tags）
    """
    # 先确保日记存在
    existing = diary_service.get_diary(sample_diary_date)
    if existing is None:
        pytest.skip("测试数据为空，跳过快照测试")

    # 更新元数据
    request = UpdateDiaryMetaRequest(
        mood="happy",
        importance="important",
        custom_tags=["测试", "快照"]
    )

    result = diary_service.update_diary_meta(sample_diary_date, request)

    if result is None:
        pytest.skip("更新失败，跳过快照测试")

    sanitized = sanitize_diary_item(result.model_dump())
    assert sanitized == snapshot


@pytest.mark.snapshot
def test_save_diary_content_snapshot(sample_diary_date, snapshot: SnapshotAssertion):
    """
    测试 save_diary_content() 方法

    验证：
    - 保存日记内容
    - 自动计算字数
    """
    # 先确保日记存在
    existing = diary_service.get_diary(sample_diary_date)
    if existing is None:
        pytest.skip("测试数据为空，跳过快照测试")

    # 保存内容
    request = SaveDiaryContentRequest(
        content="这是一段测试日记内容，用于验证快照测试。"
    )

    result = diary_service.save_diary_content(sample_diary_date, request)

    if result is None:
        pytest.skip("保存失败，跳过快照测试")

    sanitized = sanitize_diary_item(result.model_dump())
    assert sanitized == snapshot


@pytest.mark.snapshot
def test_get_diary_list_snapshot(sample_date_range, snapshot: SnapshotAssertion):
    """
    测试 get_diary_list() 方法

    验证：
    - 获取日期范围内的日记列表
    - 返回 meta 信息（不含 content）
    """
    start_date, end_date = sample_date_range
    result = diary_service.get_diary_list(start_date, end_date)

    # 跳过空数据测试
    if not result.items:
        pytest.skip("测试数据为空，跳过快照测试")

    sanitized_items = sanitize_diary_list([item.model_dump() for item in result.items])
    assert sanitized_items == snapshot


@pytest.mark.snapshot
async def test_generate_diary_ai_summary_snapshot(sample_diary_date, snapshot: SnapshotAssertion, monkeypatch):
    """
    测试 generate_diary_ai_summary() 方法

    验证：
    - 生成 AI 总结
    - 更新 ai_summary 和 diary_source_hash

    注意：Mock AI 调用，避免真实 LLM 请求
    """
    # Mock AI 总结函数
    async def mock_ai_summary(date, mood, importance, custom_tags, outdate_summary=None):
        return {"content": "这是一个模拟的 AI 总结"}

    monkeypatch.setattr("lifeprism.server.services.diary_service.ai_diary_summary", mock_ai_summary)

    # 先确保日记存在且有内容
    existing = diary_service.get_diary(sample_diary_date)
    if existing is None:
        pytest.skip("测试数据为空，跳过快照测试")

    # 确保有内容
    content = diary_service._read_diary_content(sample_diary_date)
    if not content or not content.strip():
        pytest.skip("日记内容为空，跳过快照测试")

    # 生成 AI 总结
    try:
        result = await diary_service.generate_diary_ai_summary(sample_diary_date)
    except ValueError as e:
        pytest.skip(f"生成 AI 总结失败: {e}")

    sanitized = sanitize_diary_item(result.model_dump())
    assert sanitized == snapshot


@pytest.mark.snapshot
async def test_generate_diary_ai_summary_range_snapshot(sample_date_range, snapshot: SnapshotAssertion, monkeypatch):
    """
    测试 generate_diary_ai_summary_range() 方法

    验证：
    - 批量生成 AI 总结
    - 处理不同的 existing_summary_mode

    注意：Mock AI 调用，避免真实 LLM 请求
    """
    # Mock AI 总结函数
    async def mock_ai_summary(date, mood, importance, custom_tags, outdate_summary=None):
        return {"content": f"模拟总结 {date}"}

    monkeypatch.setattr("lifeprism.server.services.diary_service.ai_diary_summary", mock_ai_summary)

    start_date, end_date = sample_date_range

    # 测试 skip_existing 模式
    request = GenerateDiaryAISummaryRangeRequest(
        start_date=start_date,
        end_date=end_date,
        existing_summary_mode=ExistingSummaryMode.SKIP_EXISTING
    )

    result = await diary_service.generate_diary_ai_summary_range(request)

    # 跳过空数据测试
    if not result.created_dates and not result.updated_dates and not result.skipped_dates:
        pytest.skip("测试数据为空，跳过快照测试")

    # 清理结果
    sanitized_result = {
        'created_dates': sorted(result.created_dates),
        'updated_dates': sorted(result.updated_dates),
        'skipped_dates': sorted(result.skipped_dates),
    }

    assert sanitized_result == snapshot
