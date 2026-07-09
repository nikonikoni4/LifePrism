# Web-Demo 演示数据说明

## 运行流程

### 1. 启动后端（带断线自动重启）

使用 `scripts/start.sh` 启动 web-demo 后端，Linux 上推荐用 `systemd` 或 `nohup` + 循环实现进程守护：

```bash
bash scripts/start.sh
```

启动后服务监听 `0.0.0.0:8101`，进程崩溃或断开后自动重启。

### 2. 定时刷新数据（每天 04:00）

后端启动时自动生成一次演示数据（lifespan）。但长期运行中数据会"过时"——日期范围不会自动推进。因此配置 cron 每天凌晨 4 点重新生成一次，保持数据以当天为终点：

```bash
# 编辑 crontab
crontab -e

# 添加以下行
0 4 * * * cd /path/to/LifeWatch-AI && /path/to/venv/bin/python scripts/demo/generate_demo_data.py >> /path/to/LifeWatch-AI/localData/debug_logs/demo_cron.log 2>&1
```

> **注意**：脚本直接操作 SQLite 数据库和文件，不需要停止或重启后端服务。

---

## 数据生成机制

### 启动时自动生成

web-demo 启动时，`lifespan` 生命周期自动执行：

```
init_database_full()          # 建表 + 默认数据
    ↓
generate_demo_data()          # 删除旧 demo 数据 → 生成过去 7 天新数据
    ↓
start_agent_and_channel()     # 启动 Agent + Channel
```

### 手动触发

```bash
cd /path/to/LifeWatch-AI
python scripts/demo/generate_demo_data.py [--data-path PATH] [--days 7]
```

核心代码位于 `scripts/demo/` 包：
- `demo_data_config.py` — 模板常量
- `demo_data_generator.py` — 生成器（含 3 个 bug 修复）
- `generate_demo_data.py` — CLI 入口

---

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

---

## 已修复的 Bug（2026-07-10）

| Bug | 修复 |
|-----|------|
| `timeline_custom_block` 时间格式用 T 分隔（`2026-07-05T20:34:00`）导致数据不可见 | 统一改为空格分隔（`2026-07-05 20:34:00`） |
| `user_app_behavior_log` 时间范围严重重叠 | 时间槽分区算法，确保不重叠 |
| `behavior_analysis` 时间范围可能重叠 | 同上 |

---

## 废弃的脚本

| 脚本 | 状态 |
|------|------|
| `refresh_daily_data.py` | ⚠️ 废弃 — 由 cron + `generate_demo_data.py` 替代 |
| `reset_demo_data.sh` | ⚠️ 废弃 — 不再需要停服重置 |
| `setup_demo_crontab.sh` | ⚠️ 废弃 — 手动配置 cron（见上方说明） |
