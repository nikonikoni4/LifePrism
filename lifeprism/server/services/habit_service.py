"""习惯系统核心业务逻辑"""
import json
import math
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
from lifeprism.server.providers.habit_chain_provider import habit_chain_provider
from lifeprism.server.schemas.habit_schemas import (
    CreateHabitRequest, UpdateHabitRequest, FrequencyObject,
    HabitListItem, HabitListResponse, HabitDetailResponse,
    ChallengeObject, AnchorInfoObject,
)
from lifeprism.utils import get_logger, LazySingleton
from lifeprism.utils.exceptions import NotFoundError, ValidationError, ConflictError

logger = get_logger(__name__)

# 等级 → 挑战周数映射
LEVEL_CHALLENGE_WEEKS = {0: 2, 1: 3, 2: 4, 3: 8, 4: 12}
MAX_LEVEL = 4


def get_weekly_frequency_days(freq: FrequencyObject) -> int:
    """频率 → 每周打卡天数"""
    if freq.type == "daily":
        return 7
    elif freq.type == "weekdays":
        return 5
    elif freq.type == "weekend":
        return 2
    elif freq.type == "custom":
        return len(freq.specificDays) if freq.specificDays else 0
    return 0


def calculate_challenge_params(level: int, freq: FrequencyObject) -> dict:
    """根据等级和频率计算挑战参数"""
    weeks = LEVEL_CHALLENGE_WEEKS.get(level, 2)
    weekly_days = get_weekly_frequency_days(freq)
    total_expected = weeks * weekly_days
    required = math.ceil(total_expected * 0.85)
    return {"challengeWeeks": weeks, "requiredCompletions": required}


class HabitService:
    """习惯系统核心 Service（有状态单例，维护 habit_name_map）"""

    def __init__(self):
        self._habit_name_map: Dict[str, str] = {}
        self._refresh_cache()

    def _refresh_cache(self):
        """刷新 habit_id → name 缓存"""
        habits = habit_provider.get_habits()
        self._habit_name_map = {h["id"]: h["name"] for h in habits}

    def _parse_frequency(self, row: Dict) -> FrequencyObject:
        """从数据库行解析 FrequencyObject"""
        config = None
        if row.get("frequency_config"):
            try:
                config = json.loads(row["frequency_config"])
            except (json.JSONDecodeError, TypeError):
                config = None
        specific_days = config.get("specificDays") if config else None
        return FrequencyObject(type=row["frequency_type"], specificDays=specific_days)

    def _build_challenge_object(self, c: Optional[Dict]) -> Optional[ChallengeObject]:
        """将 challenge 行转为 ChallengeObject"""
        if not c:
            return None
        return ChallengeObject(
            id=c["id"], habitId=c["habit_id"],
            fromLevel=c["from_level"], toLevel=c["to_level"],
            challengeWeeks=c["challenge_weeks"],
            requiredCompletions=c["required_completions"],
            completedCount=c["completed_count"],
            startDate=c["start_date"], endDate=c["end_date"],
            streakBase=c["streak_base"], status=c["status"],
            finishedAt=c.get("finished_at"),
        )

    def _build_habit_response(self, row: Dict) -> HabitListItem:
        """将 habit 行 + 关联数据组装为 HabitListItem"""
        freq = self._parse_frequency(row)
        challenge_row = habit_challenge_provider.get_current_challenge(row["id"])
        challenge_obj = self._build_challenge_object(challenge_row)

        # Streak 暂时返回 0，Task 10 实现后替换
        streak = 0

        # 锚点信息
        anchor_map = habit_chain_provider.get_anchor_info_by_habit_ids([row["id"]])
        anchor_info = None
        if row["id"] in anchor_map:
            a = anchor_map[row["id"]]
            anchor_info = AnchorInfoObject(
                chainName=a["chainName"], nodeName=a["nodeName"],
                triggerTime=a.get("triggerTime"),
            )

        return HabitListItem(
            id=row["id"], name=row["name"],
            description=row.get("description"),
            frequency=freq, currentLevel=row["current_level"],
            status=row["status"],
            currentChallenge=challenge_obj,
            valueId=row.get("value_id"),
            commitmentId=row.get("commitment_id"),
            createdAt=row["created_at"],
            pausedAt=row.get("paused_at"),
            streak=streak, anchorInfo=anchor_info,
        )

    def _create_challenge_for_habit(
        self, habit_id: str, level: int, freq: FrequencyObject, streak_base: int = 0,
    ) -> Dict:
        """为习惯创建新挑战，返回 challenge 行"""
        params = calculate_challenge_params(level, freq)
        today = date.today()
        start = today.isoformat()
        end = (today + timedelta(weeks=params["challengeWeeks"])).isoformat()
        to_level = min(level + 1, MAX_LEVEL)
        data = {
            "habit_id": habit_id,
            "challenge_weeks": params["challengeWeeks"],
            "required_completions": params["requiredCompletions"],
            "from_level": level, "to_level": to_level,
            "start_date": start, "end_date": end,
            "completed_count": 0, "streak_base": streak_base,
            "status": "in_progress",
        }
        cid = habit_challenge_provider.create_challenge(data)
        return habit_challenge_provider.get_challenge_by_id(cid)

    def _cancel_current_challenge(self, habit_id: str):
        """将当前 in_progress 挑战标记为 cancelled"""
        current = habit_challenge_provider.get_current_challenge(habit_id)
        if current:
            habit_challenge_provider.update_challenge(current["id"], {
                "status": "cancelled",
                "finished_at": datetime.now().isoformat(),
            })

    def get_habits(self, status: Optional[str] = None) -> HabitListResponse:
        """获取习惯列表"""
        rows = habit_provider.get_habits(status=status)
        items = [self._build_habit_response(r) for r in rows]
        return HabitListResponse(habits=items)

    def get_habit_detail(self, habit_id: str) -> HabitDetailResponse:
        """获取习惯详情"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在")
        item = self._build_habit_response(row)
        return HabitDetailResponse(**item.model_dump())

    def create_habit(self, req: CreateHabitRequest) -> HabitDetailResponse:
        """创建习惯 + 自动创建首个挑战"""
        freq_config = None
        if req.frequency.type == "custom" and req.frequency.specificDays:
            freq_config = json.dumps({"specificDays": req.frequency.specificDays})

        data = {
            "name": req.name, "description": req.description,
            "frequency_type": req.frequency.type,
            "frequency_config": freq_config,
            "current_level": req.initialLevel,
            "status": "active",
            "value_id": req.valueId, "commitment_id": req.commitmentId,
        }
        habit_id = habit_provider.create_habit(data)
        self._create_challenge_for_habit(habit_id, req.initialLevel, req.frequency)
        self._habit_name_map[habit_id] = req.name
        return self.get_habit_detail(habit_id)

    def update_habit(self, habit_id: str, req: UpdateHabitRequest) -> HabitDetailResponse:
        """更新习惯（PATCH 语义），level/frequency 变更触发挑战重置"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在")

        update_data = {}
        need_reset_challenge = False
        new_level = row["current_level"]
        fields = req.model_dump(exclude_unset=True)

        if "name" in fields:
            update_data["name"] = fields["name"]
        if "description" in fields:
            update_data["description"] = fields["description"]
        if "valueId" in fields:
            update_data["value_id"] = fields["valueId"]
        if "commitmentId" in fields:
            update_data["commitment_id"] = fields["commitmentId"]

        if "level" in fields and fields["level"] is not None:
            new_level = fields["level"]
            update_data["current_level"] = new_level
            need_reset_challenge = True

        if "frequency" in fields and fields["frequency"] is not None:
            freq = fields["frequency"]
            update_data["frequency_type"] = freq["type"] if isinstance(freq, dict) else freq.type
            if (freq.get("type") if isinstance(freq, dict) else freq.type) == "custom":
                sd = freq.get("specificDays") if isinstance(freq, dict) else freq.specificDays
                update_data["frequency_config"] = json.dumps({"specificDays": sd}) if sd else None
            else:
                update_data["frequency_config"] = None
            need_reset_challenge = True

        habit_provider.update_habit(habit_id, update_data)

        if need_reset_challenge:
            self._cancel_current_challenge(habit_id)
            updated_row = habit_provider.get_habit_by_id(habit_id)
            freq_obj = self._parse_frequency(updated_row)
            self._create_challenge_for_habit(habit_id, new_level, freq_obj)

        if "name" in update_data:
            self._habit_name_map[habit_id] = update_data["name"]

        return self.get_habit_detail(habit_id)

    def delete_habit(self, habit_id: str) -> bool:
        """删除习惯（级联：checkins 删除、challenges cancelled、链条节点降级）"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在")
        habit_checkin_provider.delete_by_habit_id(habit_id)
        self._cancel_current_challenge(habit_id)
        habit_chain_provider.unlink_habit_from_nodes(habit_id)
        habit_provider.delete_habit(habit_id)
        self._habit_name_map.pop(habit_id, None)
        return True

    def pause_habit(self, habit_id: str) -> HabitDetailResponse:
        """暂停习惯：当前挑战 cancelled，状态 paused"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在")
        if row["status"] == "paused":
            raise ValidationError("习惯已经处于暂停状态")
        self._cancel_current_challenge(habit_id)
        habit_provider.update_habit(habit_id, {
            "status": "paused", "paused_at": datetime.now().isoformat(),
        })
        return self.get_habit_detail(habit_id)

    def resume_habit(self, habit_id: str) -> HabitDetailResponse:
        """恢复习惯：创建同等级新挑战，状态 active"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在")
        if row["status"] == "active":
            raise ValidationError("习惯已经处于激活状态")
        freq = self._parse_frequency(row)
        self._create_challenge_for_habit(row["id"], row["current_level"], freq)
        habit_provider.update_habit(habit_id, {"status": "active", "paused_at": None})
        return self.get_habit_detail(habit_id)


habit_service = LazySingleton(HabitService)
