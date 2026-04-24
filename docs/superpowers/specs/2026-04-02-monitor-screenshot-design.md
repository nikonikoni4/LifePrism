# Monitor Screenshot Design

**Date:** 2026-04-02

**Status:** Approved

## Goal

为 `monitor` 模块增加截图能力，补充仅靠窗口标题无法覆盖的语义信息。截图分为两类：

- 固定截图：背景信息，默认每 1 分钟 1 次
- 主动截图：主要分析内容，围绕连续工作片段触发

共同约束：

- 若 `is_afk = True`，不执行任何截图
- 截图文件与元数据都保留在本地
- 默认只保留 3 天，并支持通过配置修改

## Non-Goals

- 本阶段不设计复杂的输入行为回放
- 不保存原始键鼠事件流
- 不追求最优触发算法，只追求逻辑通畅、参数可调
- 不把截图数据塞入现有 `window_events`

## Trigger Model

### 1. Coarse State: AFK

继续沿用现有 `afk_timeout = 180s` 的粗粒度 AFK 判断。

职责只有一个：决定用户是否彻底不在工作状态。

- `AFK = True`：固定截图和主动截图都不执行
- `AFK = False`：允许继续判断主动截图逻辑

### 2. Fine-Grained State: engaged

新增一个短时状态 `engaged`，用于表示“当前是否处于值得主动截图的连续工作中”。

`engaged` 与 `AFK` 并存：

- `AFK` 回答“人是否离开”
- `engaged` 回答“人是否正在形成有语义的工作片段”

### 3. Input Rules

键盘和鼠标都参与 `engaged` 判定，但规则不同：

- 键盘 keepalive 更宽松
- 鼠标 keepalive 更严格
- 只要任一输入源仍在自己的 keepalive 窗口内，就维持 `engaged = True`

当前确认的方向：

- 键盘信号不忽略纯修饰键
- 鼠标不采用“普通移动直接触发截图”的策略
- 鼠标的价值主要在于维持或进入 `engaged`

建议默认 keepalive：

- keyboard keepalive: 12s
- mouse keepalive: 6s

这些值定义“连续工作状态”本身，不跟截图频率等级联动。

## Active Screenshot Strategy

### 1. First Capture Rule

主动截图不直接绑定单次输入事件，而是绑定 `engaged` 持续时长。

- 当系统从非 `engaged` 进入 `engaged` 后，开始计时
- 连续处于 `engaged` 满足阈值时，拍第一张主动截图

用户已确认选择此模型，而不是“按有效输入累计量触发”的模型。

### 2. Repeated Active Captures

在同一个 `engaged` 片段中：

- 第一张主动截图拍完后
- 只要仍保持 `engaged`
- 就按“主动截图频率等级”继续截图

### 3. Enter Rule

`Enter` 是独立高优先级语义事件：

- 不受“第一张主动截图阈值”约束
- 直接触发主动截图
- 建议延迟约 `0.5-1s` 再截图，以获取提交后的语义结果
- 需要短冷却，避免高频回车导致截图爆量

### 4. Frequency Level

新增单一配置项 `active_screenshot_frequency_level`，只影响主动截图，不影响固定截图。

固定截图维持：

- `scheduled_screenshot_interval_seconds = 60`

推荐 3 档主动等级：

#### L1 Low

- first active capture: 45s
- next active capture interval: 90s
- enter cooldown: 8s

#### L2 Medium

- first active capture: 30s
- next active capture interval: 60s
- enter cooldown: 6s

#### L3 High

- first active capture: 20s
- next active capture interval: 40s
- enter cooldown: 4s

说明：

- `engaged` keepalive 定义状态，不随等级明显变化
- 等级控制的是“截图积极程度”

## Segment Semantics

主动截图的核心语义单位不是单张图片，而是连续工作片段。

因此需要 `engaged_segment_id`：

- 每次从非 `engaged` 进入 `engaged`，生成新的 `engaged_segment_id`
- 同一 `engaged` 期间产生的所有 `active` 和 `enter` 截图，共享该 ID
- 一旦 `engaged` 断开，该 segment 结束
- `scheduled` 截图不挂 `engaged_segment_id`

该字段是后续理解片段连续性的重要基础字段。

## Runtime Architecture

推荐方案：**保留当前 monitor 独立进程，在进程内拆多个线程/组件**

不推荐：

- 把所有逻辑继续塞进 `WindowMonitor` 单循环
- 为截图再单独拉起第二个进程

推荐分层：

- `WindowMonitor`
  - 继续负责窗口事件采集与 AFK 状态
- `InputActivityTracker`
  - 监听键盘/鼠标输入
  - 维护 keyboard/mouse keepalive
  - 输出 `engaged` 状态与 `engaged_segment_id`
- `ScreenshotScheduler`
  - 调度三类截图：`scheduled` / `active` / `enter`
- `ScreenshotStore`
  - 负责本地文件保存与元数据落库
- `ScreenshotCleanupWorker`
  - 周期清理过期文件与元数据

### Why Threads

选择同进程多线程的原因：

- 当前项目已经有独立 monitor 进程
- 输入监听、窗口轮询、截图调度天然是不同节奏
- `sleep` 只阻塞当前线程，不阻塞整个进程
- 不需要为状态同步引入额外 IPC

## repository Design

### File Path

截图文件目录固定为：

`settings.lifeprism_data_path/screenshots/YYYY-MM-DD/`

这样便于：

- 按天浏览
- 按天清理
- 避免把大文件存入数据库

### Metadata Table

新增独立表 `screen_captures`，不扩展 `window_events`。

推荐字段：

- `id`
- `captured_at`
- `capture_reason`
  - `scheduled`
  - `active`
  - `enter`
- `file_path`
- `window_app`
- `window_title`
- `frequency_level`
- `engaged_segment_id`
- `is_afk`

字段说明：

- `capture_reason` 取代 `capture_type + trigger_source`，避免语义重叠
- `engaged_segment_id` 对 `scheduled` 为 `NULL`
- `frequency_level` 用于还原当时的主动截图等级
- `is_afk` 正常情况下几乎总为 `False`，但保留用于调试和排障

## Configuration

建议在 `config` 模块中新增：

- `scheduled_screenshot_interval_seconds`
- `active_screenshot_frequency_level`
- `screenshot_retention_days`

默认值：

- `scheduled_screenshot_interval_seconds = 60`
- `active_screenshot_frequency_level = 2`
- `screenshot_retention_days = 3`

## Cleanup Policy

清理采用统一后台任务：

- 定期扫描超过 `screenshot_retention_days` 的截图
- 删除本地文件
- 删除对应元数据
- 文件删除失败时记录日志，并在后续周期重试

## Data Flow

1. `WindowMonitor` 更新当前窗口信息与 AFK 状态
2. `InputActivityTracker` 基于键盘/鼠标维护 `engaged`
3. `ScreenshotScheduler` 判断是否满足以下任一条件：
   - 固定截图
   - `engaged` 满足主动截图阈值
   - `Enter` 直接触发
4. `ScreenshotStore` 执行截图，保存文件并写入 `screen_captures`
5. `ScreenshotCleanupWorker` 清理过期截图和元数据

## Final Decisions

- 主动截图是主要分析内容，固定截图是背景补充
- `AFK` 与 `engaged` 分层共存
- 主动截图采用“连续 `engaged` 满 N 秒拍第一张”的模型
- `Enter` 独立直拍，并带短冷却
- 主动截图频率通过单一等级配置统一调整
- 截图继续放在 `windows_monitor` 体系内
- 实现上采用同进程多线程分层
- 截图文件和元数据都保留在本地，默认保留 3 天
- 元数据单独建表 `screen_captures`
- `scheduled` 截图不挂 `engaged_segment_id`
