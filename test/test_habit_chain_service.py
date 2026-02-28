"""
test_habit_chain_service.py
习惯链 Service 单元测试。

mock 策略：
  habit_chain_provider 是 LazySingleton，不能直接 patch 其属性（delattr 会失败）。
  正确做法是 patch HabitChainProvider / HabitCheckinProvider 类方法，
  LazySingleton.__getattr__ 代理到实例方法时会读取到 mock。
"""
import pytest
from unittest.mock import patch, MagicMock
from lifeprism.server.services.habit_chain_service import HabitChainService
from lifeprism.server.schemas.habit_schemas import (
    CreateChainRequest, UpdateChainRequest,
    CreateNodeRequest, UpdateNodeRequest,
    ReorderItem, ReorderNodesRequest,
)
from lifeprism.utils.exceptions import ValidationError, NotFoundError

# patch 到类方法而非 LazySingleton 对象
CHAIN_CLS = "lifeprism.server.providers.habit_chain_provider.HabitChainProvider"
CHECKIN_CLS = "lifeprism.server.providers.habit_checkin_provider.HabitCheckinProvider"


@pytest.fixture
def svc():
    return HabitChainService()


# ── 链 CRUD ──

def test_create_chain(svc):
    """create_chain 调用 provider.create_chain 并返回完整链数据"""
    chain_data = {"id": 1, "name": "晨间链", "description": None, "show_in_timeline": 0}
    with patch(f"{CHAIN_CLS}.create_chain", return_value=1) as mock_create, \
         patch(f"{CHAIN_CLS}.get_chain_by_id", return_value=chain_data), \
         patch(f"{CHAIN_CLS}.get_nodes_with_habit_names", return_value=[]):
        result = svc.create_chain(CreateChainRequest(name="晨间链"))
    mock_create.assert_called_once()
    assert result.name == "晨间链"


def test_update_chain_show_in_timeline_requires_node_with_trigger(svc):
    """showInTimeline=True 但第一节点无 triggerTime → ValidationError"""
    chain_data = {"id": 1, "name": "链", "show_in_timeline": 0}
    nodes = [{"id": 1, "trigger_time": None, "sort_order": 1}]
    with patch(f"{CHAIN_CLS}.get_chain_by_id", return_value=chain_data), \
         patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=nodes):
        with pytest.raises(ValidationError):
            svc.update_chain(1, UpdateChainRequest(showInTimeline=True))


def test_update_chain_show_in_timeline_no_nodes(svc):
    """showInTimeline=True 但链中无节点 → ValidationError"""
    chain_data = {"id": 1, "name": "链", "show_in_timeline": 0}
    with patch(f"{CHAIN_CLS}.get_chain_by_id", return_value=chain_data), \
         patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=[]):
        with pytest.raises(ValidationError, match="没有节点"):
            svc.update_chain(1, UpdateChainRequest(showInTimeline=True))


def test_update_chain_snake_case_conversion(svc):
    """update_chain 将 showInTimeline 转换为 show_in_timeline 再传给 provider"""
    chain_data = {"id": 1, "name": "链", "show_in_timeline": 0}
    # get_nodes_by_chain 用于校验（需要 trigger_time 和 sort_order）
    nodes_for_check = [{"id": 1, "trigger_time": "07:00", "sort_order": 1}]
    # get_nodes_with_habit_names 用于构建响应（需要完整字段）
    nodes_for_build = [
        {"id": 1, "name": "起床", "trigger_time": "07:00", "sort_order": 1,
         "habit_id": None, "habit_name": None}
    ]
    updated_chain = {"id": 1, "name": "链", "show_in_timeline": 1, "description": None}
    with patch(f"{CHAIN_CLS}.get_chain_by_id", side_effect=[chain_data, updated_chain]), \
         patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=nodes_for_check), \
         patch(f"{CHAIN_CLS}.update_chain") as mock_update, \
         patch(f"{CHAIN_CLS}.get_nodes_with_habit_names", return_value=nodes_for_build):
        svc.update_chain(1, UpdateChainRequest(showInTimeline=True))
    call_data = mock_update.call_args[0][1]
    assert "show_in_timeline" in call_data
    assert "showInTimeline" not in call_data


def test_delete_chain(svc):
    """delete_chain 先检查存在性，再调用 provider.delete_chain"""
    with patch(f"{CHAIN_CLS}.get_chain_by_id", return_value={"id": 1}), \
         patch(f"{CHAIN_CLS}.delete_chain") as mock_del:
        svc.delete_chain(1)
    mock_del.assert_called_once_with(1)


def test_delete_chain_not_found(svc):
    with patch(f"{CHAIN_CLS}.get_chain_by_id", return_value=None):
        with pytest.raises(NotFoundError):
            svc.delete_chain(999)


def test_get_chains_returns_list(svc):
    """get_chains 返回 ChainListResponse，chains 为列表"""
    chains = [
        {"id": 1, "name": "早晨", "description": None, "show_in_timeline": 0},
        {"id": 2, "name": "晚间", "description": None, "show_in_timeline": 1},
    ]
    with patch(f"{CHAIN_CLS}.get_chains", return_value=chains), \
         patch(f"{CHAIN_CLS}.get_nodes_with_habit_names", return_value=[]):
        result = svc.get_chains(show_in_timeline=None)
    assert len(result.chains) == 2
    assert result.chains[0].name == "早晨"


# ── 节点操作 ──

def test_create_node_appends_to_end(svc):
    """未指定位置 → sort_order = 现有节点数 + 1"""
    existing = [{"id": 1, "sort_order": 1}, {"id": 2, "sort_order": 2}]
    node_data = {"id": 3, "sort_order": 3, "chain_id": 1, "name": "冥想"}
    with patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=existing), \
         patch(f"{CHAIN_CLS}.create_node", return_value=3) as mock_create, \
         patch(f"{CHAIN_CLS}.get_node_by_id", return_value=node_data):
        result = svc.create_node(1, CreateNodeRequest(name="冥想"))
    call_data = mock_create.call_args[0][0]
    assert call_data["sort_order"] == 3


def test_create_node_inserts_after_given_node(svc):
    """指定 insertAfterNodeId → 在目标节点后插入，触发 increment_sort_order_after"""
    existing = [
        {"id": 1, "sort_order": 1},
        {"id": 2, "sort_order": 2},
        {"id": 3, "sort_order": 3},
    ]
    node_data = {"id": 4, "sort_order": 2, "chain_id": 1, "name": "新节点"}
    with patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=existing), \
         patch(f"{CHAIN_CLS}.increment_sort_order_after") as mock_inc, \
         patch(f"{CHAIN_CLS}.create_node", return_value=4) as mock_create, \
         patch(f"{CHAIN_CLS}.get_node_by_id", return_value=node_data):
        svc.create_node(1, CreateNodeRequest(name="新节点", insertAfterNodeId=1))
    # 在 sort_order=1 节点后插入，新节点 sort_order 应为 2
    call_data = mock_create.call_args[0][0]
    assert call_data["sort_order"] == 2
    mock_inc.assert_called_once_with(1, 2)


def test_create_node_camelcase_to_snake(svc):
    """habitId 和 triggerTime 应被转换为 snake_case 再传给 provider"""
    existing = []
    node_data = {"id": 1, "sort_order": 1, "chain_id": 1, "name": "起床"}
    with patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=existing), \
         patch(f"{CHAIN_CLS}.create_node", return_value=1) as mock_create, \
         patch(f"{CHAIN_CLS}.get_node_by_id", return_value=node_data):
        svc.create_node(
            1,
            CreateNodeRequest(name="起床", habitId="habit-abc", triggerTime="06:30"),
        )
    call_data = mock_create.call_args[0][0]
    assert "habit_id" in call_data
    assert "trigger_time" in call_data
    assert "habitId" not in call_data
    assert "triggerTime" not in call_data


def test_delete_node_reorders_remaining(svc):
    """删除节点后，剩余节点 sort_order 重新从 1 开始排列"""
    nodes_after = [{"id": 1, "sort_order": 1}, {"id": 3, "sort_order": 3}]
    with patch(f"{CHAIN_CLS}.get_node_by_id", return_value={"id": 2, "chain_id": 1}), \
         patch(f"{CHAIN_CLS}.delete_node"), \
         patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=nodes_after), \
         patch(f"{CHAIN_CLS}.batch_update_sort_order") as mock_batch:
        svc.delete_node(2)
    mock_batch.assert_called_once()
    updates = mock_batch.call_args[0][0]
    assert updates[0]["sort_order"] == 1
    assert updates[1]["sort_order"] == 2


def test_delete_node_not_found(svc):
    with patch(f"{CHAIN_CLS}.get_node_by_id", return_value=None):
        with pytest.raises(NotFoundError):
            svc.delete_node(999)


def test_delete_node_no_remaining_skips_batch(svc):
    """删除最后一个节点后，remaining 为空，不调用 batch_update_sort_order"""
    with patch(f"{CHAIN_CLS}.get_node_by_id", return_value={"id": 1, "chain_id": 1}), \
         patch(f"{CHAIN_CLS}.delete_node"), \
         patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=[]), \
         patch(f"{CHAIN_CLS}.batch_update_sort_order") as mock_batch:
        svc.delete_node(1)
    mock_batch.assert_not_called()


def test_reorder_nodes_validates_completeness(svc):
    """新顺序中缺少节点 → ValidationError"""
    existing = [{"id": 1}, {"id": 2}, {"id": 3}]
    with patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=existing):
        with pytest.raises(ValidationError):
            svc.reorder_nodes(1, ReorderNodesRequest(items=[
                ReorderItem(nodeId=1, sortOrder=1),
                ReorderItem(nodeId=2, sortOrder=2),
                # 缺少 id=3
            ]))


def test_reorder_nodes_validates_extra_ids(svc):
    """新顺序中包含不存在的节点 ID → ValidationError"""
    existing = [{"id": 1}, {"id": 2}]
    with patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=existing):
        with pytest.raises(ValidationError):
            svc.reorder_nodes(1, ReorderNodesRequest(items=[
                ReorderItem(nodeId=1, sortOrder=1),
                ReorderItem(nodeId=99, sortOrder=2),  # 99 不存在
            ]))


def test_reorder_nodes_success(svc):
    """正确 ID 集合 → 调用 batch_update_sort_order"""
    existing = [{"id": 1}, {"id": 2}]
    with patch(f"{CHAIN_CLS}.get_nodes_by_chain", return_value=existing), \
         patch(f"{CHAIN_CLS}.batch_update_sort_order") as mock_batch:
        svc.reorder_nodes(1, ReorderNodesRequest(items=[
            ReorderItem(nodeId=2, sortOrder=1),
            ReorderItem(nodeId=1, sortOrder=2),
        ]))
    mock_batch.assert_called_once()
    updates = mock_batch.call_args[0][0]
    assert len(updates) == 2


# ── Timeline ──

def test_get_timeline_returns_response(svc):
    """get_timeline 返回 TimelineResponse，仅包含 show_in_timeline=True 的链"""
    chains = [{"id": 1, "name": "晨间链", "show_in_timeline": 1}]
    nodes = [
        {"id": 1, "name": "起床", "habit_id": "h1", "habit_name": "起床习惯",
         "trigger_time": "07:00", "sort_order": 1},
    ]
    with patch(f"{CHAIN_CLS}.get_chains", return_value=chains), \
         patch(f"{CHAIN_CLS}.get_nodes_with_habit_names", return_value=nodes), \
         patch(f"{CHECKIN_CLS}.get_today_checkins", return_value={"h1": True}):
        result = svc.get_timeline()
    assert len(result.chains) == 1
    assert result.chains[0].name == "晨间链"
    assert result.chains[0].nodes[0].todayCheckedIn is True


def test_get_timeline_no_habit_id_skips_checkin(svc):
    """节点无 habit_id 时，get_today_checkins 不被调用"""
    chains = [{"id": 1, "name": "链", "show_in_timeline": 1}]
    nodes = [
        {"id": 1, "name": "冥想", "habit_id": None, "habit_name": None,
         "trigger_time": None, "sort_order": 1},
    ]
    with patch(f"{CHAIN_CLS}.get_chains", return_value=chains), \
         patch(f"{CHAIN_CLS}.get_nodes_with_habit_names", return_value=nodes), \
         patch(f"{CHECKIN_CLS}.get_today_checkins") as mock_checkin:
        result = svc.get_timeline()
    mock_checkin.assert_not_called()
    assert result.chains[0].nodes[0].todayCheckedIn is False
