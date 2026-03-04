"""习惯系统核心业务逻辑"""
import json
import math
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
from lifeprism.server.providers.habit_chain_provider import habit_chain_provider
from lifeprism.server.errors.error_codes import (
    BACKFILL_DATE_OUT_OF_WINDOW,
    CANNOT_CANCEL_PAST_CHECKIN,
    CHALLENGE_NOT_FOUND,
    CHECKIN_ALREADY_EXISTS,
    CHECKIN_NOT_FOUND,
    HABIT_NOT_ACTIVE,
    HABIT_NOT_FOUND,
    INVALID_STATUS_TRANSITION,
    VALIDATION_FAILED,
)
from lifeprism.server.schemas.habit_schemas import (
    CreateHabitRequest, UpdateHabitRequest, FrequencyObject,
    HabitListItem, HabitListResponse, HabitDetailResponse,
    ChallengeObject, AnchorInfoObject, SettlementActionRequest,
    BackfillAvailabilityRequest,
)
from lifeprism.server.services.habit_stats_service import get_habit_streak
from lifeprism.utils import get_logger, LazySingleton
from lifeprism.utils.exceptions import ConflictError, NotFoundError, ValidationError

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
        return len(freq.specific_days) if freq.specific_days else 0
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
                raise ValidationError(f"习惯频率配置损坏: {e}", code=VALIDATION_FAILED) from e
        specific_days = config.get("specificDays") if config else None
        return FrequencyObject(type=row["frequency_type"], specific_days=specific_days)

    def _calculate_remaining_rest_days(self, habit_id: str, challenge: Dict) -> int:
        """计算挑战剩余可休息天数。"""
        if challenge["status"] != "in_progress":
            return 0

        remaining_checkin_days = self._get_remaining_checkin_days(
            habit_id, challenge, date.today(),
        )
        return max(
            0,
            challenge["completed_count"] + remaining_checkin_days - challenge["required_completions"],
        )

    def _build_challenge_object(self, c: Optional[Dict], habit_id: str) -> Optional[ChallengeObject]:
        """将 challenge 行转为 ChallengeObject"""
        if not c:
            return None
        remaining_rest_days = self._calculate_remaining_rest_days(habit_id, c)
        return ChallengeObject(
            id=c["id"], habit_id=c["habit_id"],
            from_level=c["from_level"], to_level=c["to_level"],
            challenge_weeks=c["challenge_weeks"],
            required_completions=c["required_completions"],
            completed_count=c["completed_count"],
            remaining_rest_days=remaining_rest_days,
            start_date=c["start_date"], end_date=c["end_date"],
            streak_base=c["streak_base"], status=c["status"],
            finished_at=c.get("finished_at"),
        )

    def _build_habit_response(self, row: Dict) -> HabitListItem:
        """将 habit 行 + 关联数据组装为 HabitListItem"""
        freq = self._parse_frequency(row)
        challenge_row = habit_challenge_provider.get_current_challenge(row["id"])
        challenge_obj = self._build_challenge_object(challenge_row, row["id"])

        # 计算当前 Streak（含上次挑战遗留的 streak_base）
        streak = get_habit_streak(row["id"], freq, challenge_row)

        # 锚点信息
        anchor_map = habit_chain_provider.get_anchor_info_by_habit_ids([row["id"]])
        anchor_info = None
        if row["id"] in anchor_map:
            a = anchor_map[row["id"]]
            anchor_info = AnchorInfoObject(
                chain_name=a["chainName"], node_name=a["nodeName"],
                trigger_time=a.get("triggerTime"),
            )

        # 今日是否已打卡
        today_str = date.today().isoformat()
        today_checkin = habit_checkin_provider.get_checkin_by_date(row["id"], today_str)

        return HabitListItem(
            id=row["id"], name=row["name"],
            description=row.get("description"),
            frequency=freq, current_level=row["current_level"],
            status=row["status"],
            current_challenge=challenge_obj,
            value_id=row.get("value_id"),
            commitment_id=row.get("commitment_id"),
            created_at=row["created_at"],
            paused_at=row.get("paused_at"),
            streak=streak, anchor_info=anchor_info,
            today_completed=bool(today_checkin),
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
            raise NotFoundError("习惯不存在", code=HABIT_NOT_FOUND)
        item = self._build_habit_response(row)
        return HabitDetailResponse(**item.model_dump())

    def create_habit(self, req: CreateHabitRequest) -> HabitDetailResponse:
        """创建习惯 + 自动创建首个挑战"""
        freq_config = None
        if req.frequency.type == "custom" and req.frequency.specific_days:
            freq_config = json.dumps({"specificDays": req.frequency.specific_days})

        data = {
            "name": req.name, "description": req.description,
            "frequency_type": req.frequency.type,
            "frequency_config": freq_config,
            "current_level": req.initial_level,
            "status": "active",
            "value_id": req.value_id, "commitment_id": req.commitment_id,
        }
        habit_id = habit_provider.create_habit(data)
        self._create_challenge_for_habit(habit_id, req.initial_level, req.frequency, 0)
        self._habit_name_map[habit_id] = req.name
        return self.get_habit_detail(habit_id)

    def update_habit(self, habit_id: str, req: UpdateHabitRequest) -> HabitDetailResponse:
        """更新习惯（PATCH 语义），level/frequency 变更触发挑战重置"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在", code=HABIT_NOT_FOUND)

        update_data = {}
        need_reset_challenge = False
        new_level = row["current_level"]
        fields = req.model_dump(exclude_unset=True)

        if "name" in fields:
            update_data["name"] = fields["name"]
        if "description" in fields:
            update_data["description"] = fields["description"]
        if "value_id" in fields:
            update_data["value_id"] = fields["value_id"]
        if "commitment_id" in fields:
            update_data["commitment_id"] = fields["commitment_id"]

        if "level" in fields and fields["level"] is not None:
            new_level = fields["level"]
            update_data["current_level"] = new_level
            need_reset_challenge = True

        if "frequency" in fields and fields["frequency"] is not None:
            freq = fields["frequency"]
            update_data["frequency_type"] = freq["type"] if isinstance(freq, dict) else freq.type
            if (freq.get("type") if isinstance(freq, dict) else freq.type) == "custom":
                sd = freq.get("specific_days") if isinstance(freq, dict) else freq.specific_days
                update_data["frequency_config"] = json.dumps({"specificDays": sd}) if sd else None
            else:
                update_data["frequency_config"] = None
            need_reset_challenge = True

        habit_provider.update_habit(habit_id, update_data)

        if need_reset_challenge:
            current_challenge = habit_challenge_provider.get_current_challenge(habit_id)
            inherit_streak_base = 0
            if row["status"] == "active" and current_challenge:
                inherit_streak_base = get_habit_streak(habit_id, self._parse_frequency(row), current_challenge)
            self._cancel_current_challenge(habit_id)
            updated_row = habit_provider.get_habit_by_id(habit_id)
            freq_obj = self._parse_frequency(updated_row)
            self._create_challenge_for_habit(habit_id, new_level, freq_obj, inherit_streak_base)

        if "name" in update_data:
            self._habit_name_map[habit_id] = update_data["name"]

        return self.get_habit_detail(habit_id)

    def delete_habit(self, habit_id: str) -> bool:
        """删除习惯（级联：checkins 删除、challenges cancelled、链条节点降级）"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在", code=HABIT_NOT_FOUND)
        habit_checkin_provider.delete_by_habit_id(habit_id)
        self._cancel_current_challenge(habit_id)
        habit_chain_provider.unlink_habit_from_nodes(habit_id)
        habit_provider.delete_habit(habit_id)
        self._habit_name_map.pop(habit_id, None)
        return True

    def pause_habit(
        self,
        habit_id: str,
        settlement_action: Optional[SettlementActionRequest] = None,
    ) -> HabitDetailResponse:
        """暂停习惯：当前挑战 cancelled，状态 paused"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在", code=HABIT_NOT_FOUND)
        if row["status"] == "paused":
            raise ValidationError("习惯已经处于暂停状态", code=INVALID_STATUS_TRANSITION)
        if settlement_action:
            if settlement_action.source != "settlement":
                raise ValidationError("invalid settlement source", code=INVALID_STATUS_TRANSITION)
            updated = habit_challenge_provider.mark_in_progress_challenge_failed(
                habit_id, settlement_action.challenge_id,
            )
            if not updated:
                raise ValidationError(
                    "settlement challenge not found or already processed",
                    code=INVALID_STATUS_TRANSITION,
                )
        else:
            self._cancel_current_challenge(habit_id)
        habit_provider.update_habit(habit_id, {
            "status": "paused", "paused_at": datetime.now().isoformat(),
        })
        return self.get_habit_detail(habit_id)

    def resume_habit(
        self,
        habit_id: str,
        settlement_action: Optional[SettlementActionRequest] = None,
    ) -> HabitDetailResponse:
        """恢复/重启习惯：创建同等级新挑战，状态 active"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在", code=HABIT_NOT_FOUND)

        if settlement_action:
            if settlement_action.source != "settlement":
                raise ValidationError("invalid settlement source", code=INVALID_STATUS_TRANSITION)
            updated = habit_challenge_provider.mark_in_progress_challenge_failed(
                habit_id, settlement_action.challenge_id,
            )
            if not updated:
                raise ValidationError(
                    "settlement challenge not found or already processed",
                    code=INVALID_STATUS_TRANSITION,
                )

            freq = self._parse_frequency(row)
            self._create_challenge_for_habit(row["id"], row["current_level"], freq, 0)
            if row["status"] == "paused":
                habit_provider.update_habit(habit_id, {"status": "active", "paused_at": None})
            return self.get_habit_detail(habit_id)

        current = habit_challenge_provider.get_current_challenge(habit_id)
        if row["status"] == "active" and current:
            raise ValidationError("习惯已经处于激活状态", code=INVALID_STATUS_TRANSITION)

        freq = self._parse_frequency(row)
        self._create_challenge_for_habit(row["id"], row["current_level"], freq, 0)
        if row["status"] == "paused":
            habit_provider.update_habit(habit_id, {"status": "active", "paused_at": None})
        return self.get_habit_detail(habit_id)

    def _judge_challenge_result(
        self,
        habit_id: str,
        challenge_id: str,
        persist_succeeded: bool,
        persist_failed: bool,
    ) -> Optional["SettlementItem"]:
        """判定挑战结果，返回 SettlementItem 或 None。"""
        from lifeprism.server.schemas.habit_schemas import SettlementItem

        challenge = habit_challenge_provider.get_challenge_by_id(challenge_id)
        if not challenge or challenge["status"] != "in_progress":
            return None

        today = date.today()
        end_date = date.fromisoformat(challenge["end_date"])

        completed = challenge["completed_count"]
        required = challenge["required_completions"]
        habit_row = habit_provider.get_habit_by_id(habit_id)
        habit_name = habit_row["name"] if habit_row else ""
        reached_end_date = today >= end_date
        remaining_checkin_days = self._get_remaining_checkin_days(habit_id, challenge, today)

        if reached_end_date and completed >= required:
            new_level = min(challenge["to_level"], MAX_LEVEL)
            if persist_succeeded:
                habit_challenge_provider.update_challenge(challenge["id"], {
                    "status": "succeeded",
                    "finished_at": datetime.now().isoformat(),
                })
                habit_provider.update_habit(habit_id, {"current_level": new_level})
                freq = self._parse_frequency(habit_row)
                self._create_challenge_for_habit(habit_id, new_level, freq, completed)
            return SettlementItem(
                challenge_id=challenge["id"],
                habit_id=habit_id, habit_name=habit_name,
                result="succeeded",
                from_level=challenge["from_level"], to_level=new_level,
                completed_count=completed,
                required_completions=required,
                can_save_by_backfill=False,
            )

        if required > (completed + remaining_checkin_days):
            can_save = self._can_save_by_backfill(
                habit_id, challenge, completed, required,
            )
            if persist_failed:
                habit_challenge_provider.update_challenge(challenge["id"], {
                    "status": "failed",
                    "finished_at": datetime.now().isoformat(),
                })
            return SettlementItem(
                challenge_id=challenge["id"],
                habit_id=habit_id, habit_name=habit_name,
                result="failed",
                from_level=challenge["from_level"],
                to_level=challenge["from_level"],  # 失败等级不变
                completed_count=completed,
                required_completions=required,
                can_save_by_backfill=can_save,
            )

        return None

    def _get_remaining_checkin_days(self, habit_id: str, challenge: Dict, today: date) -> int:
        """计算从 today 到 end_date 仍可打卡的最大天数（含今日未打卡场景）。"""
        end_date = date.fromisoformat(challenge["end_date"])
        if end_date < today:
            return 0

        remaining_future_days = (end_date - today).days
        today_checkin = habit_checkin_provider.get_checkin_by_date(
            habit_id, today.isoformat(),
        )
        return remaining_future_days + (0 if today_checkin else 1)

    def _can_save_by_backfill(
        self, habit_id: str, challenge: Dict, completed: int, required: int,
    ) -> bool:
        """判断补签近7天能否挽救失败挑战"""
        today = date.today()
        start_date = date.fromisoformat(challenge["start_date"])
        end_date = date.fromisoformat(challenge["end_date"])
        backfill_count = 0
        for i in range(1, 7):  # today-1 ~ today-6
            d = (today - timedelta(days=i)).isoformat()
            if date.fromisoformat(d) < start_date:
                break
            existing = habit_checkin_provider.get_checkin_by_date(habit_id, d)
            if not existing:
                backfill_count += 1

        remaining_future_days = max((end_date - today).days, 0)
        return (completed + backfill_count + remaining_future_days) >= required

    def checkin_today(self, habit_id: str) -> "CheckInResponse":
        """今日打卡"""
        from lifeprism.server.schemas.habit_schemas import CheckInResponse, CheckInObject

        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在", code=HABIT_NOT_FOUND)
        if row["status"] != "active":
            raise ValidationError("习惯处于暂停状态，无法打卡", code=HABIT_NOT_ACTIVE)

        challenge = habit_challenge_provider.get_current_challenge(habit_id)
        if not challenge:
            raise NotFoundError("当前无进行中的挑战", code=CHALLENGE_NOT_FOUND)

        today_str = date.today().isoformat()
        now_str = datetime.now().isoformat()

        checkin_id = habit_checkin_provider.create_checkin({
            "habit_id": habit_id,
            "challenge_id": challenge["id"],
            "date": today_str,
        })
        if not checkin_id:
            raise ConflictError("今日已打卡，不可重复打卡", code=CHECKIN_ALREADY_EXISTS)

        new_count = challenge["completed_count"] + 1
        habit_challenge_provider.update_challenge(challenge["id"], {
            "completed_count": new_count,
        })

        # 判定挑战结果
        settlement = self._judge_challenge_result(
            habit_id, challenge["id"], True, False,
        )

        checkin_obj = CheckInObject(
            id=checkin_id, habit_id=habit_id,
            challenge_id=challenge["id"], date=today_str,
            completed=True, completed_at=now_str, created_at=now_str,
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
            raise NotFoundError("习惯不存在", code=HABIT_NOT_FOUND)

        today_str = date.today().isoformat()
        if date_str != today_str:
            raise ValidationError("只能取消当天的打卡", code=CANNOT_CANCEL_PAST_CHECKIN)

        existing = habit_checkin_provider.get_checkin_by_date(habit_id, date_str)
        if not existing:
            raise NotFoundError("该日期无打卡记录", code=CHECKIN_NOT_FOUND)

        challenge = habit_challenge_provider.get_challenge_by_id(existing["challenge_id"])
        if not challenge or challenge["status"] != "in_progress":
            raise ValidationError("挑战已结束，无法取消打卡", code=CANNOT_CANCEL_PAST_CHECKIN)

        habit_checkin_provider.delete_checkin(habit_id, date_str)
        new_count = max(challenge["completed_count"] - 1, 0)
        habit_challenge_provider.update_challenge(challenge["id"], {
            "completed_count": new_count,
        })

        settlement = self._judge_challenge_result(
            habit_id, challenge["id"], True, False,
        )
        habit_item = self._build_habit_response(habit_provider.get_habit_by_id(habit_id))
        return CancelCheckInResponse(habit=habit_item, settlement=settlement)

    def _validate_backfill_target_date(
        self, target_date: date, today: date, start_date: date, end_date: date,
    ) -> Optional[str]:
        """补录日期校验（本地窗口 + 挑战周期）。"""
        if target_date >= today:
            return "今日打卡请使用打卡接口"
        if (today - target_date).days > 6:
            return "只能补签过去 6 天内的日期"
        if target_date < start_date or target_date > end_date:
            return "补签日期不在当前挑战周期内"
        return None

    def backfill_checkin(self, habit_id: str, req: "BackfillCheckInRequest") -> "BackfillCheckInBatchResponse":
        """批量补签（过去 6 天内，按请求顺序逐项处理，部分成功继续）。"""
        from lifeprism.server.schemas.habit_schemas import (
            BackfillCheckInBatchResponse,
            BackfillCheckInBatchSummary,
            BackfillCheckInResultItem,
            CheckInObject,
        )

        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在", code=HABIT_NOT_FOUND)
        if row["status"] != "active":
            raise ValidationError("习惯处于暂停状态，无法补签", code=HABIT_NOT_ACTIVE)

        challenge = habit_challenge_provider.get_challenge_by_id(req.challenge_id)
        if not challenge or challenge["habit_id"] != habit_id:
            raise NotFoundError("挑战不存在", code=CHALLENGE_NOT_FOUND)

        today = date.today()
        seen_dates: set[str] = set()
        results: List[BackfillCheckInResultItem] = []

        def _append_failed(date_str: str, message: str, error_code: str):
            results.append(BackfillCheckInResultItem(
                date=date_str,
                status="failed",
                checkin=None,
                settlement=None,
                error_code=error_code,
                message=message,
            ))

        for item in req.items:
            date_str = item.date
            if date_str in seen_dates:
                _append_failed(date_str, "请求内存在重复补签日期", CHECKIN_ALREADY_EXISTS)
                continue
            seen_dates.add(date_str)

            try:
                target_date = date.fromisoformat(date_str)
            except ValueError:
                _append_failed(date_str, "补签日期格式无效", BACKFILL_DATE_OUT_OF_WINDOW)
                continue

            latest_challenge = habit_challenge_provider.get_challenge_by_id(req.challenge_id)
            if not latest_challenge or latest_challenge["habit_id"] != habit_id:
                raise NotFoundError("挑战不存在", code=CHALLENGE_NOT_FOUND)
            if latest_challenge["status"] != "in_progress":
                _append_failed(date_str, "挑战已结束，无法补签", BACKFILL_DATE_OUT_OF_WINDOW)
                continue

            start_date = date.fromisoformat(latest_challenge["start_date"])
            end_date = date.fromisoformat(latest_challenge["end_date"])
            date_error = self._validate_backfill_target_date(
                target_date, today, start_date, end_date,
            )
            if date_error:
                _append_failed(date_str, date_error, BACKFILL_DATE_OUT_OF_WINDOW)
                continue

            now_str = datetime.now().isoformat()
            checkin_id = habit_checkin_provider.create_checkin({
                "habit_id": habit_id,
                "challenge_id": latest_challenge["id"],
                "date": date_str,
            })
            if not checkin_id:
                _append_failed(date_str, "该日期已有打卡记录", CHECKIN_ALREADY_EXISTS)
                continue

            new_count = latest_challenge["completed_count"] + 1
            habit_challenge_provider.update_challenge(latest_challenge["id"], {
                "completed_count": new_count,
            })

            settlement = self._judge_challenge_result(
                habit_id, latest_challenge["id"], True, False,
            )
            checkin_obj = CheckInObject(
                id=checkin_id,
                habit_id=habit_id,
                challenge_id=latest_challenge["id"],
                date=date_str,
                completed=True,
                completed_at=now_str,
                created_at=now_str,
            )
            results.append(BackfillCheckInResultItem(
                date=date_str,
                status="succeeded",
                checkin=checkin_obj,
                settlement=settlement,
                error_code=None,
                message=None,
            ))

        habit_item = self._build_habit_response(habit_provider.get_habit_by_id(habit_id))
        succeeded_count = sum(1 for item in results if item.status == "succeeded")
        failed_count = len(results) - succeeded_count
        summary = BackfillCheckInBatchSummary(
            total=len(results),
            succeeded=succeeded_count,
            failed=failed_count,
        )
        return BackfillCheckInBatchResponse(
            habit=habit_item,
            results=results,
            summary=summary,
        )

    def get_challenge_history(
        self, habit_id: str, status: Optional[str]
    ) -> List[Dict[str, Any]]:
        """获取习惯的挑战历史记录"""
        row = habit_provider.get_habit_by_id(habit_id)
        if not row:
            raise NotFoundError("习惯不存在", code=HABIT_NOT_FOUND)
        return habit_challenge_provider.get_challenge_history(habit_id, status)

    def get_backfill_availability(
        self, req: BackfillAvailabilityRequest,
    ) -> "BackfillAvailabilityResponse":
        """获取补录可选日期（today-6 ~ today-1）。"""
        from lifeprism.server.schemas.habit_schemas import (
            BackfillAvailabilityResponse, BackfillDateAvailabilityItem,
        )

        habit = habit_provider.get_habit_by_id(req.habit_id)
        if not habit:
            raise NotFoundError("习惯不存在", code=HABIT_NOT_FOUND)

        challenge = habit_challenge_provider.get_challenge_by_id(req.challenge_id)
        if not challenge or challenge["habit_id"] != req.habit_id:
            raise NotFoundError("挑战不存在", code=CHALLENGE_NOT_FOUND)

        start_date = date.fromisoformat(challenge["start_date"])
        end_date = date.fromisoformat(challenge["end_date"])
        today = date.today()
        days: List[BackfillDateAvailabilityItem] = []

        for i in range(6, 0, -1):
            d = today - timedelta(days=i)
            date_str = d.isoformat()

            if d < start_date:
                days.append(BackfillDateAvailabilityItem(
                    date=date_str, selectable=False, reason="before_challenge_start",
                ))
                continue

            if d > end_date:
                days.append(BackfillDateAvailabilityItem(
                    date=date_str, selectable=False, reason="after_challenge_end",
                ))
                continue

            existing = habit_checkin_provider.get_checkin_by_date(req.habit_id, date_str)
            if existing:
                days.append(BackfillDateAvailabilityItem(
                    date=date_str, selectable=False, reason="already_checked_in",
                ))
            else:
                days.append(BackfillDateAvailabilityItem(
                    date=date_str, selectable=True, reason=None,
                ))

        return BackfillAvailabilityResponse(
            habit_id=req.habit_id, challenge_id=req.challenge_id, days=days,
        )

    def check_settlements(self) -> "CheckSettlementsResponse":
        """批量检查所有到期未结算挑战（成功落库，失败仅检测不落库）。"""
        from lifeprism.server.schemas.habit_schemas import CheckSettlementsResponse
        today = date.today().isoformat()
        expired = habit_challenge_provider.get_expired_in_progress_challenges(today)
        settlements = []
        for challenge in expired:
            item = self._judge_challenge_result(
                challenge["habit_id"], challenge["id"], True, False,
            )
            if item:
                settlements.append(item)
        return CheckSettlementsResponse(settlements=settlements)


habit_service = LazySingleton(HabitService)
