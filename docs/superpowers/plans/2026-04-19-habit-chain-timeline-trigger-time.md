# Habit Chain Timeline 节点时间计算实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将时间计算逻辑从前端移至后端，实现纯后端计算（不存库），前端仅负责显示

**Architecture:**
- 后端 Service 层新增 `_calculate_node_trigger_times()` 方法，计算每个节点的 `calculated_time`
- 后端验证逻辑新增相邻节点最小间距 >= 10min 检查
- 前端移除时间计算逻辑，使用后端返回的 `calculated_time` 显示
- 前端常量放大4倍（1px=4min）

**Tech Stack:** Python/FastAPI (后端), React/TypeScript (前端)

---

## 影响范围

| 文件 | 改动 |
|------|------|
| `lifeprism/server/services/habit_chain_service.py` | 新增时间计算逻辑（计算结果临时填充到 trigger_time，不存库） |
| `frontend/apps/habits/constants.ts` | 调整布局常量（4倍放大） |
| `frontend/apps/habits/hooks/useTimelineStore.ts` | 简化，移除时间计算逻辑 |
| `frontend/apps/habits/components/views/timeline/TimelineView.tsx` | 容器高度调整 |
| `test/regression/test_habit_chain_trigger_time.py` | 更新测试 |

**注意**：Schema 不变，不新增 `calculated_time` 字段。后端计算结果通过 `trigger_time` 字段返回给前端，但不写入数据库。

---

## Task 1: (已移除 - Schema 不需要修改)

**说明**：不需要修改 Schema。`trigger_time` 字段复用，后端计算结果通过该字段返回（不存库）。

---

## Task 2: 后端新增时间计算逻辑

**Files:**
- Modify: `lifeprism/server/services/habit_chain_service.py`

- [ ] **Step 1: 在 HabitChainService 类中新增常量和方法**

在 `_MSG_INVALID_ORDER` 之后添加：

```python
# 时间计算常量
_DEFAULT_INTERVAL_MINUTES = 30  # 默认时长（分钟）
_MIN_GAP_MINUTES = 10  # 相邻节点最小间距（分钟）
```

新增方法 `_calculate_node_times()`（注意：仅在返回数据前调用，不写库）：

```python
def _calculate_node_times(self, nodes: List[dict]) -> List[dict]:
    """
    计算每个节点的 trigger_time（不存库，仅返回计算结果）

    规则：
    - 显式设置的 trigger_time 保持不变
    - 隐式节点（无 trigger_time）根据规则计算：
      a. 若后续有显式节点，按平均间距分配
      b. 若后续无显式节点，按默认30min递推

    返回的节点中，trigger_time 字段已填充计算结果
    """
    if not nodes:
        return nodes

    sorted_nodes = sorted(nodes, key=lambda n: n["sort_order"])

    # 找出所有锚点（显式设置了 trigger_time 的节点）
    anchors = []
    for i, node in enumerate(sorted_nodes):
        if node.get("trigger_time"):
            minutes = self._parse_time_to_minutes(node["trigger_time"], "INTERNAL_ERROR")
            anchors.append({"index": i, "minutes": minutes})

    # 情况A：没有锚点，所有节点按默认30min递推
    if not anchors:
        current_minutes = 0  # 从0点开始
        for node in sorted_nodes:
            node["trigger_time"] = self._format_minutes_to_time(current_minutes)
            current_minutes += _DEFAULT_INTERVAL_MINUTES
        return sorted_nodes

    # 情况B：有锚点，处理第一段（第一个锚点之前的节点）
    first_anchor = anchors[0]
    if first_anchor["index"] > 0:
        current_minutes = first_anchor["minutes"] - (first_anchor["index"] * _DEFAULT_INTERVAL_MINUTES)
        for i in range(first_anchor["index"]):
            sorted_nodes[i]["trigger_time"] = self._format_minutes_to_time(current_minutes)
            current_minutes += _DEFAULT_INTERVAL_MINUTES

    # 处理锚点之间的节点
    for a in range(len(anchors) - 1):
        curr_anchor = anchors[a]
        next_anchor = anchors[a + 1]
        nodes_between = next_anchor["index"] - curr_anchor["index"] - 1

        if nodes_between == 0:
            # 连续锚点，中间无节点
            pass
        else:
            # 有中间节点，平均分配
            total_minutes = next_anchor["minutes"] - curr_anchor["minutes"]
            interval = total_minutes / (nodes_between + 1)
            for i in range(nodes_between):
                idx = curr_anchor["index"] + 1 + i
                sorted_nodes[idx]["trigger_time"] = self._format_minutes_to_time(
                    curr_anchor["minutes"] + int(interval * (i + 1))
                )

    # 处理最后一个锚点之后的节点
    last_anchor = anchors[-1]
    if last_anchor["index"] < len(sorted_nodes) - 1:
        current_minutes = last_anchor["minutes"] + _DEFAULT_INTERVAL_MINUTES
        for i in range(last_anchor["index"] + 1, len(sorted_nodes)):
            sorted_nodes[i]["trigger_time"] = self._format_minutes_to_time(current_minutes)
            current_minutes += _DEFAULT_INTERVAL_MINUTES

    return sorted_nodes


def _format_minutes_to_time(self, minutes: int) -> str:
    """将分钟数转换为 HH:mm 格式"""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"
```

- [ ] **Step 2: 修改 `_validate_chain_timeline_rules` 方法**

在现有的递增检查之后，新增相邻节点最小间距检查：

```python
def _validate_chain_timeline_rules(
    self, nodes: List[dict], is_showing_in_timeline: bool, error_code: str,
) -> None:
    if not is_showing_in_timeline:
        return

    if not nodes:
        raise ValidationError(self._MSG_NO_NODES, code=error_code)

    sorted_nodes = sorted(nodes, key=lambda n: n["sort_order"])
    first_minutes = self._parse_time_to_minutes(sorted_nodes[0].get("trigger_time"), error_code)
    if first_minutes is None:
        raise ValidationError(self._MSG_FIRST_NODE_NEEDS_TIME, code=error_code)

    last_minutes = first_minutes
    for node in sorted_nodes[1:]:
        current_minutes = self._parse_time_to_minutes(node.get("trigger_time"), error_code)
        if current_minutes is None:
            continue
        if current_minutes < last_minutes:
            raise ValidationError(self._MSG_INVALID_ORDER, code=error_code)
        # 新增：检查相邻节点最小间距
        gap = current_minutes - last_minutes
        if gap < _MIN_GAP_MINUTES:
            prev_time = self._format_minutes_to_time(last_minutes)
            curr_time = self._format_minutes_to_time(current_minutes)
            raise ValidationError(
                f"节点触发时间间距不足：{prev_time} → {curr_time} 间距{gap}min，要求>={_MIN_GAP_MINUTES}min",
                code=error_code
            )
        last_minutes = current_minutes
```

- [ ] **Step 3: 修改 `get_timeline()` 方法**

在组装 `TimelineNodeItem` 前，调用 `_calculate_node_times()` 填充计算结果：

```python
def get_timeline(self) -> TimelineResponse:
    chains = habit_chain_provider.get_chains(show_in_timeline=True)
    chain_items = []
    for chain in chains:
        nodes = habit_chain_provider.get_nodes_with_habit_names(chain["id"])
        # 计算每个节点的 trigger_time（不存库）
        nodes_with_calculated = self._calculate_node_times(nodes)
        habit_ids = [n["habit_id"] for n in nodes if n.get("habit_id")]
        today_map = habit_checkin_provider.get_today_checkins(habit_ids) if habit_ids else {}
        node_items = [
            TimelineNodeItem(
                id=n["id"],
                name=n["name"],
                habit_id=n.get("habit_id"),
                habit_name=n.get("habit_name"),
                trigger_time=n.get("trigger_time"),  # 已填充计算结果
                sort_order=n["sort_order"],
                today_checked_in=today_map.get(n.get("habit_id"), False),
            )
            for n in sorted(nodes_with_calculated, key=lambda x: x["sort_order"])
        ]
        chain_items.append(TimelineChainItem(id=chain["id"], name=chain["name"], nodes=node_items))
    return TimelineResponse(chains=chain_items)
```

- [ ] **Step 4: 修改 `get_chain_detail()` 方法**

同样在返回前调用 `_calculate_node_times()`：

```python
def get_chain_detail(self, chain_id: int) -> ChainDetailResponse:
    chain = self._get_chain_or_404(chain_id)
    nodes = habit_chain_provider.get_nodes_with_habit_names(chain_id)
    nodes_with_calculated = self._calculate_node_times(nodes)
    return ChainDetailResponse(**self._build_chain_item(chain, nodes_with_calculated).model_dump())
```

- [ ] **Step 5: Commit**

```bash
git add lifeprism/server/services/habit_chain_service.py
git commit -m "feat(habit_chain): add time calculation logic to backend"
```

---

## Task 3: 前端常量放大4倍

**Files:**
- Modify: `frontend/apps/habits/constants.ts`

- [ ] **Step 1: 修改布局常量**

```typescript
/** Timeline 布局常量 — 放大4倍 (1px=4min) */
export const PIXELS_PER_MINUTE = 4;      // 原值1，改为4
export const HOUR_HEIGHT = PIXELS_PER_MINUTE * 60;  // 240px
export const MIN_NODE_HEIGHT = 48;       // 保持不变
export const MIN_ANCHOR_GAP = 320;       // 原值80，改为320
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/habits/constants.ts
git commit -m "feat(frontend): scale timeline 4x for better node display"
```

---

## Task 4: 前端移除错误的时间计算逻辑

**Files:**
- Modify: `frontend/apps/habits/hooks/useTimelineStore.ts`

- [ ] **Step 1: 简化 useMemo 中的时间计算逻辑**

新的 `useMemo` 逻辑直接使用后端返回的 `trigger_time`（已填充计算结果），不再本地计算：

```typescript
const timelineEvents = useMemo(() => {
    const events: TimelineEvent[] = [];

    const activeChains = chains.filter(c => c.showInTimeline);

    activeChains.forEach(chain => {
        const nodes = [...chain.nodes].sort((a, b) => a.sortOrder - b.sortOrder);
        if (nodes.length === 0) return;

        // 直接使用后端计算并返回的 trigger_time
        nodes.forEach((node) => {
            const triggerTime = node.triggerTime || "00:00";
            const minutes = parseTimeToMinutes(triggerTime);

            events.push({
                id: `${chain.id}_${node.id}`,
                title: node.name,
                startTime: triggerTime,
                endTime: formatMinutesToTime(minutes + 30),  // 默认30min
                associatedHabitId: node.habitId,
                height: MIN_NODE_HEIGHT,
                top: minutes * PIXELS_PER_MINUTE
            });
        });
    });

    return events;
}, [chains]);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/habits/hooks/useTimelineStore.ts
git commit -m "feat(frontend): use trigger_time from backend, remove local computation"
```

---

## Task 5: 更新回归测试

**Files:**
- Modify: `test/regression/test_habit_chain_trigger_time.py`

- [ ] **Step 1: 更新测试以验证新的时间计算逻辑**

```python
"""
回归测试：习惯链条 Timeline 节点触发时间计算逻辑

验证点（新版）：
1. 后端 _calculate_node_times 自动计算 trigger_time（填充结果）
2. _validate_chain_timeline_rules 验证相邻节点间距 >= 10min
3. 相邻节点间距 < 10min 时抛出 ValidationError
4. 计算结果通过 trigger_time 字段返回（不存库）
"""
import pytest
from lifeprism.server.services.habit_chain_service import HabitChainService
from lifeprism.utils.exceptions import ValidationError


class TestChainTimelineTriggerTimeCalculation:

    def _make_node(self, id: int, sort_order: int, trigger_time: str | None, habit_id: str | None = None):
        return {
            "id": id,
            "chain_id": 1,
            "sort_order": sort_order,
            "name": f"节点{id}",
            "trigger_time": trigger_time,
            "habit_id": habit_id,
        }

    # ============================================================================
    # 场景1：只给第一个节点触发时间（8:00），后续节点按默认30min递推
    # ============================================================================

    def test_calculate_only_first_node_has_time(self):
        """
        场景1：第一个节点8:00，其他节点无显式时间
        预期：后端计算 trigger_time
        - 节点1: 08:00 (显式)
        - 节点2: 08:30 (30min递推)
        - 节点3: 09:00 (30min递推)
        - 节点4: 09:30 (30min递推)
        - 节点5: 10:00 (30min递推)
        """
        service = HabitChainService()
        nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, None),
            self._make_node(3, 3, None),
            self._make_node(4, 4, None),
            self._make_node(5, 5, None),
        ]

        result = service._calculate_node_times(nodes)

        assert result[0]["trigger_time"] == "08:00"
        assert result[1]["trigger_time"] == "08:30"
        assert result[2]["trigger_time"] == "09:00"
        assert result[3]["trigger_time"] == "09:30"
        assert result[4]["trigger_time"] == "10:00"

    # ============================================================================
    # 场景2：第一节点8:00，第四节点9:00，中间节点平均分配
    # ============================================================================

    def test_calculate_with_gap_in_trigger_times(self):
        """
        场景2：第1节点8:00，第4节点9:00，中间2个节点平均分配
        - 总时长: 60min, 中间2个节点
        - 每段: 60min / 3 = 20min
        - 节点1: 08:00 (显式)
        - 节点2: 08:20 (20min间隔)
        - 节点3: 08:40 (20min间隔)
        - 节点4: 09:00 (显式)
        - 节点5: 09:30 (默认30min递推)
        """
        service = HabitChainService()
        nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, None),
            self._make_node(3, 3, None),
            self._make_node(4, 4, "09:00"),
            self._make_node(5, 5, None),
        ]

        result = service._calculate_node_times(nodes)

        assert result[0]["trigger_time"] == "08:00"
        assert result[1]["trigger_time"] == "08:20"
        assert result[2]["trigger_time"] == "08:40"
        assert result[3]["trigger_time"] == "09:00"
        assert result[4]["trigger_time"] == "09:30"

    # ============================================================================
    # 验证：相邻节点间距 < 10min 时抛出错误
    # ============================================================================

    def test_validate_gap_less_than_10min_fails(self):
        """
        验证：相邻节点间距5min < 10min，应报错
        """
        service = HabitChainService()
        nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, "08:05"),  # 间距5min
        ]

        with pytest.raises(ValidationError) as exc:
            service._validate_chain_timeline_rules(nodes, is_showing_in_timeline=True, error_code="TEST")
        assert "间距不足" in str(exc.value)

    def test_validate_gap_equal_10min_passes(self):
        """
        验证：相邻节点间距10min = 10min，应通过
        """
        service = HabitChainService()
        nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, "08:10"),  # 间距10min
        ]

        service._validate_chain_timeline_rules(nodes, is_showing_in_timeline=True, error_code="TEST")

    def test_validate_gap_greater_than_10min_passes(self):
        """
        验证：相邻节点间距15min > 10min，应通过
        """
        service = HabitChainService()
        nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, "08:15"),  # 间距15min
        ]

        service._validate_chain_timeline_rules(nodes, is_showing_in_timeline=True, error_code="TEST")

    # ============================================================================
    # 验证：计算结果不存库（原始节点数据不变）
    # ============================================================================

    def test_calculated_time_not_persisted(self):
        """
        验证：_calculate_node_times 不修改原始 trigger_time
        计算结果仅在返回时填充，不写入数据库
        """
        service = HabitChainService()
        original_nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, None),
            self._make_node(3, 3, None),
        ]

        result = service._calculate_node_times(original_nodes)

        # 原始节点 trigger_time 未被修改（仍然是None）
        assert original_nodes[1]["trigger_time"] is None
        # 计算结果中 trigger_time 已填充
        assert result[1]["trigger_time"] == "08:30"
```

- [ ] **Step 2: Commit**

```bash
git add test/regression/test_habit_chain_trigger_time.py
git commit -m "test(regression): update tests for new time calculation logic"
```

---

## Task 6: 运行测试验证

- [ ] **Step 1: 运行回归测试**

```bash
cd D:/desktop/软件开发/LifeWatch-AI
pytest test/regression/test_habit_chain_trigger_time.py -v
```

Expected: All tests should PASS

- [ ] **Step 2: 运行相关核心测试（如果有）**

```bash
pytest tests/core/ -v -k habit
```

---

## 自检清单

- [ ] spec 中每个需求都有对应 task 实现
- [ ] 无 placeholder (TBD/TODO)
- [ ] 类型一致性：Schema 不变，复用 `trigger_time` 字段
- [ ] Task 2 中 `_MIN_GAP_MINUTES = 10` 与设计一致
- [ ] Task 2 中 `_DEFAULT_INTERVAL_MINUTES = 30` 与设计一致
- [ ] 前端常量放大4倍 (PIXELS_PER_MINUTE: 1 → 4)
- [ ] 计算结果通过 `trigger_time` 字段返回，不写入数据库
