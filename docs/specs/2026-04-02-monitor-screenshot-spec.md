---
version: 1.0
created_at: 2026-04-02
updated_at: 2026-04-02
last_updated:
abstract: 为 monitor 模块增加截图能力，补充仅靠窗口标题无法覆盖的语义信息。截图分为固定截图（背景信息，每1分钟1次）和主动截图（主要分析内容，围绕连续工作片段触发），采用 AFK 与 engaged 分层状态机，统一走 ScreenshotStore 本地落文件与元数据，默认保留3天。
id: monitor-screenshot-spec
title: Monitor Screenshot
status: draft
module: lifeprism/monitor
sourc_spec: docs/superpowers/specs/2026-04-02-monitor-screenshot-design.md
related_plan: docs/superpowers/plans/2026-04-02-monitor-screenshot.md
code_scope:
  - lifeprism/monitor/screenshot/
  - lifeprism/config/settings_manager.py
  - lifeprism/config/database.py
contract_refs:
  - lifeprism/monitor/screenshot/models.py
  - lifeprism/monitor/screenshot/policy.py
---

# Monitor Screenshot

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |

## Overview

为 `monitor` 模块增加截图能力，补充仅靠窗口标题无法覆盖的语义信息。

截图分为两类：

- **固定截图（scheduled）**：背景信息，默认每 1 分钟 1 次
- **主动截图（active / enter）**：主要分析内容，围绕连续工作片段触发

共同约束：

- 若 `is_afk = True`，不执行任何截图
- 截图文件与元数据都保留在本地
- 默认只保留 3 天，并支持通过配置修改

## Scope

### 功能范围

1. 截图能力：`scheduled` / `active` / `enter` 三类截图触发逻辑
2. 状态机：AFK 粗粒度判断 + engaged 细粒度工作状态
3. 片段语义：`engaged_segment_id` 作为同一连续工作片段的关联标识
4. 本地存储：截图文件按天分目录 + `screen_captures` 元数据表
5. 过期清理：后台任务清理超过保留天数的截图文件与元数据

### 实现边界

- 保留当前独立 monitor 进程，不新增第二个守护进程
- 同进程多线程协作：WindowMonitor / InputActivityTracker / ScreenshotScheduler / ScreenshotStore / ScreenshotCleanupWorker
- 不扩展前端页面，不新增公开 API 契约
- 不保存原始键鼠事件流

## Core Behavior

### 1. AFK 粗粒度状态

AFK 判定由 `WindowMonitor._compute_afk_state(idle_time, video_playing)` 实现，区分媒体与非媒体场景：

- 非媒体场景：`idle_time > afk_timeout`（默认 180s）→ AFK
- 媒体播放场景（`is_any_video_playing()=True`）：`idle_time > afk_timeout_media`（默认 3600s）→ AFK

媒体场景使用更长超时，避免看视频/玩游戏时被误判；同时设有上限，避免用户离开后视频继续播放导致时长无限积累。`afk_timeout_media` 实际只对媒体场景生效（非媒体场景由更短的 `afk_timeout` 先触发）。

- `AFK = True`：固定截图和主动截图都不执行
- `AFK = False`：允许继续判断主动截图逻辑

### 2. engaged 细粒度状态

新增短时状态 `engaged`，用于表示"当前是否处于值得主动截图的连续工作中"。

`engaged` 与 `AFK` 并存：

- `AFK` 回答"人是否离开"
- `engaged` 回答"人是否正在形成有语义的工作片段"

输入规则：

- 键盘 keepalive 更宽松（默认 12s）
- 鼠标 keepalive 更严格（默认 6s）
- 只要任一输入源仍在自己的 keepalive 窗口内，就维持 `engaged = True`
- 键盘信号不忽略纯修饰键
- 鼠标不采用"普通移动直接触发截图"的策略，鼠标的价值主要在于维持或进入 `engaged`

### 3. 主动截图策略

#### First Capture Rule

主动截图不直接绑定单次输入事件，而是绑定 `engaged` 持续时长：

- 当系统从非 `engaged` 进入 `engaged` 后，开始计时
- 连续处于 `engaged` 满足阈值时，拍第一张主动截图

#### Repeated Active Captures

在同一个 `engaged` 片段中：

- 第一张主动截图拍完后
- 只要仍保持 `engaged`
- 就按"主动截图频率等级"继续截图

#### Enter Rule

`Enter` 是独立高优先级语义事件：

- 不受"第一张主动截图阈值"约束
- 直接触发主动截图
- 建议延迟约 `0.5-1s` 再截图，以获取提交后的语义结果
- 需要短冷却，避免高频回车导致截图爆量

### 4. Frequency Level

单一配置项 `active_screenshot_frequency_level`，只影响主动截图，不影响固定截图。

固定截图维持：`scheduled_screenshot_interval_seconds = 60`

3 档主动等级：

| 等级 | 第一张主动截图阈值 | 后续主动截图间隔 | Enter 冷却 |
| ---- | ------------------ | ---------------- | ---------- |
| L1 Low | 45s | 90s | 8s |
| L2 Medium | 30s | 60s | 6s |
| L3 High | 20s | 40s | 4s |

### 5. Segment Semantics

`engaged_segment_id` 是主动截图的核心语义单位：

- 每次从非 `engaged` 进入 `engaged`，生成新的 `engaged_segment_id`
- 同一 `engaged` 期间产生的所有 `active` 和 `enter` 截图，共享该 ID
- 一旦 `engaged` 断开，该 segment 结束
- `scheduled` 截图不挂 `engaged_segment_id`

### 6. Cleanup Policy

- 定期扫描超过 `screenshot_retention_days` 的截图
- 删除本地文件
- 删除对应元数据
- 文件删除失败时记录日志，并在后续周期重试

## Technical Contract

### 1. 配置项

| 配置键 | 默认值 | 说明 |
| ------ | ------ | ---- |
| `scheduled_screenshot_interval_seconds` | 60 | 固定截图间隔 |
| `active_screenshot_frequency_level` | 2 | 主动截图频率等级（1/2/3） |
| `keyboard_keepalive_seconds` | 12 | 键盘 keepalive 窗口 |
| `mouse_keepalive_seconds` | 6 | 鼠标 keepalive 窗口 |
| `enter_screenshot_delay_ms` | 700 | Enter 截图延迟毫秒数 |
| `screenshot_retention_days` | 3 | 截图保留天数 |
| `cleanup_check_interval_seconds` | 86400 | 清理检查间隔（秒） |

### 2. 数据目录

截图文件目录固定为：

```
{lifeprism_data_path}/screenshots/YYYY-MM-DD/
```

### 3. Metadata Table: screen_captures

独立表，不扩展 `window_events`。

| 字段 | 类型 | 约束 | 说明 |
| ---- | ---- | ---- | ---- |
| `id` | TEXT | PK, NOT NULL | 截图记录唯一标识 |
| `captured_at` | TEXT | NOT NULL | 截图时间（ISO 格式） |
| `capture_reason` | TEXT | NOT NULL | scheduled / active / enter |
| `file_path` | TEXT | NOT NULL, UNIQUE | 截图文件相对路径 |
| `window_app` | TEXT | | 窗口所属应用 |
| `window_title` | TEXT | | 窗口标题 |
| `frequency_level` | INTEGER | | 主动截图等级（1/2/3），scheduled 为 NULL |
| `engaged_segment_id` | TEXT | | 所属 engaged 片段 ID，scheduled 为 NULL |
| `is_afk` | INTEGER | NOT NULL | 截图时是否处于 AFK 状态 |

索引：

- `idx_screen_captures_captured_at` on `captured_at`
- `idx_screen_captures_segment_id` on `engaged_segment_id`
- `idx_screen_captures_reason_time` on `(capture_reason, captured_at)`

### 4. CaptureReason 枚举

```python
class CaptureReason(str, Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    ENTER = "enter"
```

### 5. FrequencyPolicy 数据类

```python
@dataclass(frozen=True)
class FrequencyPolicy:
    level: int
    first_active_after_seconds: int
    repeat_active_every_seconds: int
    enter_cooldown_seconds: int
```

### 6. 数据流

1. `WindowMonitor` 更新当前窗口信息与 AFK 状态
2. `InputActivityTracker` 基于键盘/鼠标维护 `engaged` 状态
3. `ScreenshotScheduler` 判断是否满足以下任一条件：
   - 固定截图（时间间隔到达）
   - `engaged` 满足主动截图阈值
   - `Enter` 直接触发
4. `ScreenshotStore` 执行截图，保存文件并写入 `screen_captures`
5. `ScreenshotCleanupWorker` 清理过期截图和元数据

## Interaction / UX Notes

- 无前端交互，本期不开放 UI 配置
- 截图参数变更先依赖配置文件或内部构造参数

## Acceptance Notes

1. `scheduled` 记录永远 `engaged_segment_id = NULL`
2. `active` / `enter` 记录总是同时带 `frequency_level` 与 `engaged_segment_id`
3. AFK 状态下彻底阻止三类截图
4. 元数据写入失败时正确回滚已生成的截图文件
5. 清理任务只删除超过 `screenshot_retention_days` 的记录
6. 旧 `window_events` 链路保持不变

## Out of Spec

- 不设计复杂的输入行为回放
- 不保存原始键鼠事件流
- 不追求最优触发算法
- 不把截图数据塞入现有 `window_events` 表
