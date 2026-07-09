# Web-Demo 演示数据脚本使用说明

## 概述

`scripts/demo/` 提供两套脚本，用于为 LifePrism Web-Demo 模式生成和管理模拟用户数据，解决 Linux 服务器上无 Monitor 采集数据导致前端空白的问题。

| 脚本 | 用途 | 运行频率 |
|---|---|---|
| `generate_demo_data.py` | 一次性生成过去 7 天完整演示数据 | 仅一次 |
| `refresh_daily_data.py` | 刷新"今天"的数据，使演示环境持续有新数据 | 每天 12:00 |
| `setup_demo_crontab.sh` | 安装 crontab 定时任务 | 仅一次 |

---

## 前置条件

1. **数据库已初始化**：必须先启动一次 web-demo，让 `init_database()` 完成建表和默认数据写入
   ```bash
   cd /path/to/LifeWatch-AI
   uvicorn lifeprism.server.main_web_demo:app --host 0.0.0.0 --port 8101
   # 看到启动日志后 Ctrl+C 停止
   ```

2. **Python 环境**：脚本依赖 `sqlite3`（Python 标准库，无需额外安装）

3. **数据目录存在**：默认使用项目根目录下的 `localData/`，确保该目录已存在

---

## 一、生成初始演示数据

```bash
cd /path/to/LifeWatch-AI
python scripts/demo/generate_demo_data.py
```

### 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--data-path PATH` | `localData` | 数据目录路径（相对于项目根目录或绝对路径） |
| `--days N` | `7` | 生成过去 N 天的数据 |
| `--force` | 关闭 | 强制重新生成，覆盖已有数据 |

### 生成内容

#### 数据库表（21 张）

| 类别 | 表 | 数量 |
|---|---|---|
| 时间线核心 | `user_app_behavior_log` | ~210 条（30条/天） |
| | `behavior_analysis` | ~70 条（10条/天） |
| | `raw_behavior_analysis` | ~50 条（7条/天） |
| 缓存 | `category_map_cache`, `multi_purpose_map_cache`, `single_purpose_map_cache` | ~40 条 |
| 用户数据 | `mood_entries`, `diary`, `todo_list`, `goal_journal` | ~60 条 |
| 日/周焦点 | `daily_focus`, `weekly_focus` | ~11 条 |
| 习惯系统 | `habits`, `habit_challenges`, `habit_checkins` | ~40 条 |
| | `habit_chains`, `habit_chain_nodes` | 5 条 |
| 价值/承诺 | `user_values`, `commitments` | 10 条 |
| 统计/其他 | `goal_stats`, `time_paradoxes`, `tokens_usage_log` | ~20 条 |
| 时间块 | `timeline_custom_block` | ~20 条 |

#### 文件（3 类）

| 文件 | 路径 | 数量 |
|---|---|---|
| 日记 MD | `diary/{YYYY/MM/YYYY-MM-DD}.md` | 7 个 |
| 行为总结 | `user/daily_data/behavior.md` | 1 个（含 7 天内容） |
| 近期状态 | `user/daily_data/recent_state.md` | 1 个 |

### 跳过已存在数据

脚本默认**幂等**——检测到已有演示数据时自动跳过，避免重复生成：

```
[WARN] 检测到已有演示数据，跳过生成（使用 --force 强制覆盖）
```

### 生成的数据特征

- **无个人信息**：所有内容为虚构模板数据，不包含真实用户信息
- **中文环境**：应用名、心情描述、日记摘要均为中文
- **合理的时间分布**：工作日在 8:00~18:00 以工作/学习为主，晚上以娱乐为主
- **随机变化**：每次生成的具体数值（时长、心情内容等）有随机波动，看起来更自然

---

## 二、每日数据刷新

### 手动触发

```bash
python scripts/demo/refresh_daily_data.py
```

### 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--data-path PATH` | `localData` | 数据目录路径 |
| `--force` | 关闭 | 强制刷新（即使今天已有数据） |

### 刷新内容

#### 数据库（9 张表）

| 表 | 说明 |
|---|---|
| `user_app_behavior_log` | 生成今天 8:00~当前时间的应用使用记录 |
| `behavior_analysis` | 今天的行为分析片段 |
| `raw_behavior_analysis` | 今天的原始行为分析 |
| `mood_entries` | 今天 1~2 条心情记录 |
| `daily_focus` | 今天的日焦点 |
| `timeline_custom_block` | 今天的时间块（午休、专注开发、阅读等） |
| `goal_stats` | 今天的目标时间统计 |
| `habit_checkins` | 今天的习惯打卡（上午 ~80% 完成率，下午 ~50%） |
| `todo_list` | 15:00 后将今天 scheduled 的 todo 随机标记为完成 |

#### 文件（2 个）

| 文件 | 说明 |
|---|---|
| `diary/{YYYY/MM/YYYY-MM-DD}.md` | 今天的日记文件（Morning Page + Evening Page） |
| `user/daily_data/behavior.md` | 追加今天的行为总结条目 |

#### 不刷新

- `recent_state.md`：仅生成一次，每日刷新不更新

### 跳过已存在数据

```
[INFO] 今天的数据已存在，跳过刷新（使用 --force 强制刷新）
```

---

## 三、安装定时任务

```bash
bash scripts/demo/setup_demo_crontab.sh
```

脚本会：
1. 检测 Python 路径
2. 生成 crontab 条目：`0 12 * * *`（每天 12:00 执行）
3. 日志输出到 `localData/debug_logs/demo_refresh.log`

### 验证

```bash
# 查看 crontab
crontab -l

# 查看日志
tail -f localData/debug_logs/demo_refresh.log

# 手动测试
python scripts/demo/refresh_daily_data.py
```

---

## 常见问题

### Q: 运行脚本后前端仍然空白？

1. 确认数据库路径正确：`--data-path` 需要指向 web-demo 实际使用的数据目录
2. 确认 web-demo 启动时设置了正确的 `LIFEPRISM_DATA_PATH` 环境变量
3. 确认数据库中有 `category`、`mood_types` 等默认数据（由 web-demo 首次启动自动初始化）

### Q: 在 Windows 上能用吗？

可以。脚本使用纯 Python 标准库，Windows/Linux/macOS 都能运行。但 crontab 安装脚本仅适用于 Linux。

### Q: 如何生成更多天的数据？

```bash
python scripts/demo/generate_demo_data.py --days 30 --force
```

### Q: 如何重置所有演示数据？

删除数据库后重新走完整流程：
```bash
rm localData/dataset/lifewatch_ai.db
# 重新启动 web-demo 初始化数据库
uvicorn lifeprism.server.main_web_demo:app --host 0.0.0.0 --port 8101
# Ctrl+C 后重新生成
python scripts/demo/generate_demo_data.py --force
```

---

## 数据流示意

```
┌──────────────────────────────────────────────────┐
│                  generate_demo_data.py            │
│  （仅运行一次）                                    │
│                                                   │
│  ┌─ 数据库 ───────────────────────────────────┐  │
│  │ user_app_behavior_log (过去7天, ~210条)     │  │
│  │ behavior_analysis (过去7天, ~70条)          │  │
│  │ mood_entries, diary, todo_list, ...         │  │
│  │ habits, goals, values, commitments, ...     │  │
│  └────────────────────────────────────────────┘  │
│                                                   │
│  ┌─ 文件 ─────────────────────────────────────┐  │
│  │ diary/YYYY/MM/YYYY-MM-DD.md ×7            │  │
│  │ user/daily_data/behavior.md                │  │
│  │ user/daily_data/recent_state.md            │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│              refresh_daily_data.py               │
│  （每天 12:00 crontab 触发）                      │
│                                                   │
│  ┌─ 数据库（仅今天）────────────────────────┐    │
│  │ user_app_behavior_log (今天 8:00~现在)    │    │
│  │ behavior_analysis, mood_entries, ...      │    │
│  │ habit_checkins (今天打卡)                  │    │
│  │ todo_list (更新状态为 completed)           │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  ┌─ 文件（仅今天）──────────────────────────┐    │
│  │ diary/YYYY/MM/YYYY-MM-DD.md (今天)       │    │
│  │ behavior.md (追加今天条目)                │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```
