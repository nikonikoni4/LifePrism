# test/test_habit_chain_provider.py
import pytest
from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.habit_chain_provider import habit_chain_provider


@pytest.fixture(autouse=True)
def cleanup():
    yield
    with habit_chain_provider.db.get_connection() as conn:
        conn.execute("DELETE FROM habit_chain_nodes")
        conn.execute("DELETE FROM habit_chains")
        conn.execute("DELETE FROM habits")


def test_create_and_get_chain():
    cid = habit_chain_provider.create_chain({"name": "晨间流程", "description": "早起链条"})
    assert cid is not None
    assert isinstance(cid, int)
    chain = habit_chain_provider.get_chain_by_id(cid)
    assert chain["name"] == "晨间流程"


def test_get_chains_filter_timeline():
    habit_chain_provider.create_chain({"name": "A"})
    c2 = habit_chain_provider.create_chain({"name": "B"})
    habit_chain_provider.update_chain(c2, {"show_in_timeline": 1})
    timeline = habit_chain_provider.get_chains(show_in_timeline=True)
    assert len(timeline) == 1
    assert timeline[0]["name"] == "B"


def test_create_node_and_get_nodes():
    cid = habit_chain_provider.create_chain({"name": "Test"})
    nid = habit_chain_provider.create_node({
        "chain_id": cid, "sort_order": 1, "name": "起床", "trigger_time": "07:00",
    })
    assert nid is not None
    assert isinstance(nid, int)
    nodes = habit_chain_provider.get_nodes_by_chain(cid)
    assert len(nodes) == 1
    assert nodes[0]["name"] == "起床"


def test_batch_update_sort_order():
    cid = habit_chain_provider.create_chain({"name": "Test"})
    n1 = habit_chain_provider.create_node({"chain_id": cid, "sort_order": 1, "name": "A"})
    n2 = habit_chain_provider.create_node({"chain_id": cid, "sort_order": 2, "name": "B"})
    habit_chain_provider.batch_update_sort_order([
        {"node_id": n2, "sort_order": 1},
        {"node_id": n1, "sort_order": 2},
    ])
    nodes = habit_chain_provider.get_nodes_by_chain(cid)
    assert nodes[0]["name"] == "B"
    assert nodes[1]["name"] == "A"


def test_unlink_habit_from_nodes():
    hid = habit_provider.create_habit({"name": "H", "frequency_type": "daily", "status": "active"})
    cid = habit_chain_provider.create_chain({"name": "C"})
    habit_chain_provider.create_node({"chain_id": cid, "sort_order": 1, "name": "N", "habit_id": hid})
    habit_chain_provider.unlink_habit_from_nodes(hid)
    nodes = habit_chain_provider.get_nodes_by_chain(cid)
    assert nodes[0]["habit_id"] is None


def test_get_anchor_info_by_habit_ids():
    hid = habit_provider.create_habit({"name": "H", "frequency_type": "daily", "status": "active"})
    cid = habit_chain_provider.create_chain({"name": "晨间"})
    habit_chain_provider.create_node({
        "chain_id": cid, "sort_order": 1, "name": "冥想", "habit_id": hid, "trigger_time": "07:05",
    })
    info = habit_chain_provider.get_anchor_info_by_habit_ids([hid])
    assert hid in info
    assert info[hid]["chainName"] == "晨间"
    assert info[hid]["nodeName"] == "冥想"
    assert info[hid]["triggerTime"] == "07:05"


def test_delete_chain_cascades_nodes():
    cid = habit_chain_provider.create_chain({"name": "C"})
    habit_chain_provider.create_node({"chain_id": cid, "sort_order": 1, "name": "N"})
    habit_chain_provider.delete_chain(cid)
    assert habit_chain_provider.get_chain_by_id(cid) is None
    assert habit_chain_provider.get_nodes_by_chain(cid) == []
