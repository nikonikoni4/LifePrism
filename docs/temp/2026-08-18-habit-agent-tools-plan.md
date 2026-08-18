# 习惯打卡 Agent 工具方案

范围（已确认）：**查询 + 打卡/补签** 最小集，不暴露创建/修改/删除/结算动作。本地与云端共用同一 agent 系统，工具只需注册一次。

## 同步层面结论（已核实，无障碍）

- `habits`/`habit_challenges`/`habit_checkins` 均在 `SYNC_TABLES`，云端数据完整
- 云端 `habit_chains`/`habit_chain_nodes` 为空 → 仅 `anchorInfo` 为 null（降级可用）+ 删除解绑 no-op，无害
- 云端打卡写入经既有同步机制（hash_id + LWW）回传本地，无需额外改动

## 关键设计决策

1. **必须走 `HabitService`，不能像 custom_records_tool 那样直连 repository**：打卡/补签涉及 `completed_count` 更新、结算判定（`_judge_challenge_result`）、Streak 计算，直连 repository 会跳过业务规则导致挑战状态错乱。
2. **延迟导入解决循环依赖**：`lifeprism/server/services/__init__.py` → `schedule_service` → `lifeprism.llm`（agent loop）。`habit_tool.py` 若模块级导入 `habit_service` 会循环导入，改为在函数体内延迟导入。
3. **时间处理**（遵循 time-handling-rules）：习惯日期是本地 `YYYY-MM-DD`（service 内部用 `get_local_today()`），Agent 输入输出均为本地日期，无需转换；`completed_at` 等 UTC ISO 输出时用 `utc_to_local_display` 转本地。

## 新增文件 `lifeprism/llm/agent/tools/habit_tool.py`

4 个 Tool 子类（execute 返回 str，遵循 `tools/CLAUDE.md`）：

| 工具 | 参数 | 实现 |
|---|---|---|
| `QueryUserHabitsTool` (`query_user_habits`) | `status` 可选（active/paused） | `habit_service.get_habits(status)`，格式化输出：id、name、频率、等级(0-4)、状态、streak、今日是否已打卡、当前挑战进度（completed/required、起止日期、剩余可休息天数） |
| `CheckinHabitTool` (`checkin_habit`) | `habit_id` 必填 | `habit_service.checkin_today()`；若返回 settlement（升级成功/失败预警）显著提示；捕获 NotFound/Validation/Conflict → `ERROR` 前缀字符串 |
| `CancelCheckinHabitTool` (`cancel_checkin_habit`) | `habit_id` 必填 | `habit_service.cancel_checkin(habit_id, 今日)`（仅限今日，service 已校验） |
| `BackfillCheckinTool` (`backfill_checkin`) | `habit_id`、`dates` 数组（YYYY-MM-DD） | 内部经 `habit_repository.get_current_challenge()` 取 challenge_id，组装 `BackfillCheckInRequest` 调 `backfill_checkin()`，逐日期输出成功/失败与原因（service 已含 6 天窗口、挑战周期、重复打卡校验） |

## 注册

- `lifeprism/llm/agent/tools/__init__.py` 导出 4 个类
- `lifeprism/llm/agent/loop.py` CHAT 分支注册（`loop.py:484-502`，与 mood 工具相邻）；DREAM_TASK 分支不注册（dreaming 无打卡需求）

## 测试（遵循 test-rules.md）

新增 `test/core/` 下习惯工具单测，覆盖：
- 查询输出格式（有/无习惯、status 过滤）
- 打卡：成功 / 重复打卡（ConflictError）/ 暂停习惯 / habit_id 不存在
- 取消：仅限当日
- 补签：窗口外日期、挑战周期外、已有打卡的失败分支
- 打卡触发挑战升级时 settlement 提示出现在输出

## 文档（遵循 docs-rules）

- `docs/specs/2026-07-06-llm-agent-spec.md`：工具清单 17 → 21，补 4 个 habit 工具
- `docs/specs/2026-04-15-habit-system.md`：新增 Agent 工具小节（记录暴露范围决策：查询+打卡/补签，不含增删改）

## 风险

1. `HabitService` 是有状态单例（`_habit_name_map` 缓存）——直接复用 `LazySingleton` 导出，无新风险
2. Agent 打卡与用户手动打卡并发：`UNIQUE(habit_id, date)` 约束兜底，冲突返回错误信息
3. 结算动作（重新开始/暂停）不暴露：Agent 查询看到 settlement item 时输出提示，引导用户在前端手动处理
4. `registry copy.py`/`base copy.py` 等历史副本文件不动
