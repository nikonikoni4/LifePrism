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
from lifeprism.server.services.habit_stats_service import get_habit_streak
from lifeprism.utils import get_logger, LazySingleton
from lifeprism.utils.exceptions import NotFoundError, ValidationError

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
            except (json.JSONDecodeError, TypeError) as e:
                raise ValidationError(f"习惯频率配置损坏: {e}") from e
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

        # 计算当前 Streak（含上次挑战遗留的 streak_base）
        streak = get_habit_streak(row["id"], freq, challenge_row)

        # 锚点信息
        anchor_map = habit_chain_provider.get_anchor_info_by_habit_ids([row["id"]])
        anchor_info = None
        if row["id"] in anchor_map:
            a = anchor_map[row["id"]]
            anchor_info = AnchorInfoObject(
                chainName=a["chainName"], nodeName=a["nodeName"],
                triggerTime=a.get("triggerTime"),
            )

        # 今日是否已打卡
        today_str = date.today().isoformat()
        today_checkin = habit_checkin_provider.get_checkin_by_date(row["id"], today_str)

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
            todayCompleted=bool(today_checkin),
        )

    def _create_challenge_for_habit(
        self, habit_id: str, level: int, freq: FrequencyObject, streak_base: int
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

    def get_habits(self, status: Optional[str]) -> HabitListResponse:
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
        self._create_challenge_for_habit(habit_id, req.initialLevel, req.frequency, 0)
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
            self._create_challenge_for_habit(habit_id, new_level, freq_obj, 0)

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
        self._create_challenge_for_habit(row["id"], row["current_level"], freq, 0)
        habit_provider.update_habit(habit_id, {"status": "active", "paused_at": None})
        return self.get_habit_detail(habit_id)

    def _judge_challenge_result(
        self, habit_id: str, challenge_id: str,
    ) -> Optional["SettlementItem"]:
        """判定挑战结果，返回 SettlementItem 或 None（未到期/无需结算）"""
        from lifeprism.server.schemas.habit_schemas import SettlementItem

        challenge = habit_challenge_provider.get_challenge_by_id(challenge_id)
        if not challenge or challenge["status"] != "in_progress":
            return None

        today = date.today()
        end_date = date.fromisoformat(challenge["end_date"])

        # 未到期 → 不结算
        if end_date >= today:
            return None

        completed = challenge["completed_count"]
        required = challenge["required_completions"]
        habit_row = habit_provider.get_habit_by_id(habit_id)
        habit_name = habit_row["name"] if habit_row else ""

        if completed >= required:
            # 成功：升级 + 创建新挑战
            new_level = min(challenge["to_level"], MAX_LEVEL)
            habit_challenge_provider.update_challenge(challenge["id"], {
                "status": "succeeded",
                "finished_at": datetime.now().isoformat(),
            })
            habit_provider.update_habit(habit_id, {"current_level": new_level})
            freq = self._parse_frequency(habit_row)
            self._create_challenge_for_habit(habit_id, new_level, freq, completed)
            return SettlementItem(
                habitId=habit_id, habitName=habit_name,
                result="succeeded",
                fromLevel=challenge["from_level"], toLevel=new_level,
                completedCount=completed,
                requiredCompletions=required,
                canSaveByBackfill=False,
            )
        else:
            # 失败：计算是否可补签挽救
            can_save = self._can_save_by_backfill(
                habit_id, challenge, completed, required,
            )
            habit_challenge_provider.update_challenge(challenge["id"], {
                "status": "failed",
                "finished_at": datetime.now().isoformat(),
            })
            return SettlementItem(
                habitId=habit_id, habitName=habit_name,
                result="failed",
                fromLevel=challenge["from_level"],
                toLevel=challenge["from_level"],  # 失败等级不变
                completedCount=completed,
                requiredCompletions=required,
                canSaveByBackfill=can_save,
            )

    def _can_save_by_backfill(
        self, habit_id: str, challenge: Dict, completed: int, required: int,
    ) -> bool:
        """判断补签近7天能否挽救失败挑战"""
        today = date.today()
        start_date = date.fromisoformat(challenge["start_date"])
        backfill_count = 0
        for i in range(1, 7):  # today-1 ~ today-6
            d = (today - timedelta(days=i)).isoformat()
            if date.fromisoformat(d) < start_date:
                break
            existing = habit_checkin_provider.get_checkin_by_date(habit_id, d)
            if not existing:
                backfill_count += 1
        return (completed + backfill_count) >= required

    def checkin_today(self, habit_id: str) -> "CheckInResponse":
        """今日打卡"""
        from lifeprism.server.schemas.habit_schemas import CheckInResponse, CheckInObject
        from lifeprism.utils.exceptions import ConflictError

        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在")
        if row["status"] != "active":
            raise ValidationError("习惯处于暂停状态，无法打卡")

        challenge = habit_challenge_provider.get_current_challenge(habit_id)
        if not challenge:
            raise NotFoundError("当前无进行中的挑战")

        today_str = date.today().isoformat()
        now_str = datetime.now().isoformat()

        checkin_id = habit_checkin_provider.create_checkin({
            "habit_id": habit_id,
            "challenge_id": challenge["id"],
            "date": today_str,
        })
        if not checkin_id:
            raise ConflictError("今日已打卡，不可重复打卡")

        new_count = challenge["completed_count"] + 1
        habit_challenge_provider.update_challenge(challenge["id"], {
            "completed_count": new_count,
        })

        # 判定挑战结果
        settlement = self._judge_challenge_result(habit_id, challenge["id"])

        checkin_obj = CheckInObject(
            id=checkin_id, habitId=habit_id,
            challengeId=challenge["id"], date=today_str,
            completed=True, completedAt=now_str, createdAt=now_str,
        )
        habit_item = self._build_habit_response(habit_provider.get_habit_by_id(habit_id))
        return CheckInResponse(
            checkin=checkin_obj, habit=habit_item, settlement=settlement,
        )

    def cancel_checkin(self, habit_id: str, date_str: str) -> "CancelCheckInResponse":
        """取消打卡（仅限今日）"""
        from lifeprism.server.schemas.habit_schemas import CancelCheckInResponse

        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在")

        today_str = date.today().isoformat()
        if date_str != today_str:
            raise ValidationError("只能取消当天的打卡")

        existing = habit_checkin_provider.get_checkin_by_date(habit_id, date_str)
        if not existing:
            raise NotFoundError("该日期无打卡记录")

        challenge = habit_challenge_provider.get_challenge_by_id(existing["challenge_id"])
        if not challenge or challenge["status"] != "in_progress":
            raise ValidationError("挑战已结束，无法取消打卡")

        habit_checkin_provider.delete_checkin(habit_id, date_str)
        new_count = max(challenge["completed_count"] - 1, 0)
        habit_challenge_provider.update_challenge(challenge["id"], {
            "completed_count": new_count,
        })

        settlement = self._judge_challenge_result(habit_id, challenge["id"])
        habit_item = self._build_habit_response(habit_provider.get_habit_by_id(habit_id))
        return CancelCheckInResponse(habit=habit_item, settlement=settlement)

    def backfill_checkin(self, habit_id: str, req: "BackfillCheckInRequest") -> "CheckInResponse":
        """补签（过去7天内）"""
        from lifeprism.server.schemas.habit_schemas import CheckInResponse, CheckInObject
        from lifeprism.utils.exceptions import ConflictError

        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在")
        if row["status"] != "active":
            raise ValidationError("习惯处于暂停状态，无法补签")

        target_date = date.fromisoformat(req.date)
        today = date.today()

        if target_date >= today:
            raise ValidationError("今日打卡请使用打卡接口")
        if (today - target_date).days > 7:
            raise ValidationError("只能补签过去 7 天内的日期")

        challenge = habit_challenge_provider.get_current_challenge(habit_id)
        if not challenge:
            raise NotFoundError("当前无进行中的挑战")

        now_str = datetime.now().isoformat()
        checkin_id = habit_checkin_provider.create_checkin({
            "habit_id": habit_id,
            "challenge_id": challenge["id"],
            "date": req.date,
        })
        if not checkin_id:
            raise ConflictError("该日期已有打卡记录")

        new_count = challenge["completed_count"] + 1
        habit_challenge_provider.update_challenge(challenge["id"], {
            "completed_count": new_count,
        })

        settlement = self._judge_challenge_result(habit_id, challenge["id"])

        checkin_obj = CheckInObject(
            id=checkin_id, habitId=habit_id,
            challengeId=challenge["id"], date=req.date,
            completed=True, completedAt=now_str, createdAt=now_str,
        )
        habit_item = self._build_habit_response(habit_provider.get_habit_by_id(habit_id))
        return CheckInResponse(
            checkin=checkin_obj, habit=habit_item, settlement=settlement,
        )

    def get_challenge_history(
        self, habit_id: str, status: Optional[str]
    ) -> List[Dict[str, Any]]:
        """获取习惯的挑战历史记录"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在")
        return habit_challenge_provider.get_challenge_history(habit_id, status)

    def check_settlements(self) -> "CheckSettlementsResponse":
        """批量检查所有到期未结算的挑战，执行结算并返回结果列表"""
        from lifeprism.server.schemas.habit_schemas import CheckSettlementsResponse
        today = date.today().isoformat()
        expired = habit_challenge_provider.get_expired_in_progress_challenges(today)
        settlements = []
        for challenge in expired:
            item = self._judge_challenge_result(challenge["habit_id"], challenge["id"])
            if item:
                settlements.append(item)
        return CheckSettlementsResponse(settlements=settlements)


habit_service = LazySingleton(HabitService)
