# Web-Demo 演示数据说明

## 当前机制（2026-07-10 重构后）

**演示数据在 web-demo 每次启动时自动全量重建**，无需外部脚本或 crontab。

启动 web-demo 时，`lifespan` 生命周期自动执行：

```
init_database_full()          # 建表 + 默认数据
    ↓
generate_demo_data()          # 删除旧数据 → 生成过去 7 天新数据
    ↓
start_agent_and_channel()     # 启动 Agent + Channel
```

核心代码位于 `lifeprism/server/demo/` 包：
- `demo_data_config.py` — 模板常量
- `demo_data_generator.py` — 生成器（含 3 个 bug 修复：时间格式、行为日志重叠、行为分析重叠）

## 手动触发（可选）

```bash
cd /path/to/LifeWatch-AI
python scripts/demo/generate_demo_data.py [--data-path PATH] [--days 7]
```

本脚本保留作为独立测试/调试入口，实际逻辑委托到 `lifeprism.server.demo.DemoDataGenerator`。

## 生成内容

| 类别 | 表/文件 | 数量 |
|------|---------|------|
| 应用日志 | `user_app_behavior_log` | ~210 条（30条/天，不重叠） |
| 行为分析 | `behavior_analysis` | ~70 条（10条/天，不重叠） |
| 原始行为 | `raw_behavior_analysis` | ~50 条（7条/天，不重叠） |
| 自定义时间块 | `timeline_custom_block` | ~20 条（时间格式已修复） |
| 心情 | `mood_entries` | ~12 条 |
| 日记 | `diary` + 文件 | 7 条 + 7 个 MD 文件 |
| 待办 | `todo_list` | ~25 条 |
| 目标 | `goal_journal`, `goal_stats`, `daily_focus`, `weekly_focus` | ~30 条 |
| 习惯 | `habits`, `habit_challenges`, `habit_checkins`, `habit_chain` | ~45 条 |
| 价值观 | `user_values`, `commitments` | 10 条 |
| 其他 | `time_paradoxes`, `tokens_usage_log`, 缓存表 | ~30 条 |
| 文件 | `behavior.md`, `recent_state.md` | 2 个 |

## 已修复的 Bug（2026-07-10）

| Bug | 修复 |
|-----|------|
| `timeline_custom_block` 时间格式用 T 分隔（`2026-07-05T20:34:00`）导致数据不可见 | 统一改为空格分隔（`2026-07-05 20:34:00`） |
| `user_app_behavior_log` 时间范围严重重叠 | 时间槽分区算法，确保不重叠 |
| `behavior_analysis` 时间范围可能重叠 | 同上 |

## 废弃的脚本

| 脚本 | 状态 |
|------|------|
| `refresh_daily_data.py` | ⚠️ 废弃 — 不再需要增量刷新 |
| `reset_demo_data.sh` | ⚠️ 废弃 — 重启服务即自动重置 |
| `setup_demo_crontab.sh` | ⚠️ 废弃 — 不再需要 crontab |
