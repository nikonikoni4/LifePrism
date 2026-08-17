---
version: 1.0
created_at: 2026-08-14
updated_at: 2026-08-14
last_updated: 记录媒体播放时 AFK 判定无上限导致离开后时长无限积累的修复过程
abstract: WindowMonitor 的 AFK 判定在 is_any_video_playing()=True 时恒返回 False（永不 AFK），全屏看视频或玩游戏时即使用户离开，窗口时长也会无限积累；修复为引入 afk_timeout_media（默认 3600s）作为媒体场景的 AFK 上限。
status: fixed
---

# 媒体播放时 AFK 判定无上限导致离开后时长无限积累

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 记录问题根因、修复方案、回归测试和规则沉淀 |

## 元信息

- **发生时间**: 历史遗留（参考 aw-watcher-afk 的媒体豁免设计引入）
- **发现时间**: 2026-08-14（用户反馈）
- **修复状态**: 已修复（2026-08-14）
- **影响范围**: `WindowMonitor` 的 AFK 判定；全屏看视频、玩游戏（触发 `is_any_video_playing()=True`）场景下的窗口时长统计
- **bug 类型**: 边界条件缺失——豁免逻辑无上限
- **严重程度**: P2 — 不会造成数据丢失，但会导致时长统计严重失真（看视频/玩游戏离开后时长持续积累）

## 触发规则

在以下场景时阅读本文档：

- 修改 `WindowMonitor` 的 AFK 判定逻辑
- 修改 `is_any_video_playing()` 或 `powercfg /requests` 相关逻辑
- 排查"全屏看视频/玩游戏后窗口时长远超实际使用时间"
- 调整 `afk_timeout` 或 `afk_timeout_media` 配置
- 设计基于电源请求或媒体状态的 AFK 豁免逻辑

## Bug 简述

[`WindowMonitor.run()`](../../lifeprism/monitor/windows_monitor/monitor.py) 的 AFK 判定原实现为：

```python
currently_afk = idle_time > self.afk_timeout and not is_any_video_playing()
```

当 `is_any_video_playing()` 返回 `True`（系统有 DISPLAY/EXECUTION 电源请求，通常是视频播放或部分全屏游戏触发），`not is_any_video_playing()` 为 `False`，整个表达式恒为 `False`——**永不判 AFK**。

这导致：用户全屏看视频或玩游戏时，即使中途离开（无任何键鼠输入），该窗口的时长也会持续积累，直到用户回来操作或视频/游戏停止发出电源请求。`_flush()` 只在窗口切换或 AFK 状态变化时触发，无 AFK 状态变化意味着单次事件无限延长。

[`is_any_video_playing()`](../../lifeprism/monitor/windows_monitor/windows_api.py) 通过 `powercfg /requests` 检测 DISPLAY/EXECUTION 电源请求（参考 aw-watcher-afk 实现）。该豁免的初衷是合理的——看视频时本就没有键鼠输入，不应误判为离开——但缺少上限，无法区分"正在看视频"和"视频还在播但人已离开"。

## 复用场景

此问题可作为以下设计和排查场景的参考：

- 基于"信号 X 存在则豁免"的 AFK/空闲判定逻辑——任何豁免都应有上限或反向验证
- 参考第三方工具（如 aw-watcher-afk）实现时，需审视其设计前提是否与自身场景完全一致
- `powercfg /requests` 或电源请求作为活跃信号的使用场景
- 监控系统中"无输入但活动持续"的边界情况处理

核心经验是：**豁免逻辑不能是无上限的恒等式**。"信号存在则不判 AFK"必须配合"信号存在但长时间无输入仍判 AFK"的兜底，否则信号持续存在时（如视频循环播放、游戏挂机）会导致状态永远无法退出。

## 代码位置

### Bug 发生位置

- **AFK 判定（修复前）**：[`lifeprism/monitor/windows_monitor/monitor.py`](../../lifeprism/monitor/windows_monitor/monitor.py) L82 — `currently_afk = idle_time > self.afk_timeout and not is_any_video_playing()`
- **媒体检测**：[`lifeprism/monitor/windows_monitor/windows_api.py`](../../lifeprism/monitor/windows_monitor/windows_api.py) L27-L56 — `is_any_video_playing()` 通过 `powercfg /requests` 检测电源请求
- **事件持久化**：[`lifeprism/monitor/windows_monitor/monitor.py`](../../lifeprism/monitor/windows_monitor/monitor.py) L44-L56 — `_flush()` 只在窗口切换或 AFK 状态变化时触发

### 修复位置

- **新判定方法**：[`lifeprism/monitor/windows_monitor/monitor.py`](../../lifeprism/monitor/windows_monitor/monitor.py) L47-L62 — `_compute_afk_state(idle_time, video_playing)` 区分媒体/非媒体场景
- **配置默认值**：[`lifeprism/config/settings_manager.py`](../../lifeprism/config/settings_manager.py) L73 — `DEFAULTS["afk_timeout_media"] = 3600.0`
- **API schema**：[`lifeprism/server/schemas/setting_schemas.py`](../../lifeprism/server/schemas/setting_schemas.py) L67-L71, L110 — `SettingItems` 和 `UpdateSettingsRequest` 加 `afk_timeout_media` 字段（`ge=300`）
- **前端 UI**：[`frontend/apps/settings/SettingsApp.tsx`](../../frontend/apps/settings/SettingsApp.tsx) L1178-L1207 — "离开判定"区块
- **前端类型**：[`frontend/apps/settings/types.ts`](../../frontend/apps/settings/types.ts) L49, L81 — `afk_timeout_media` 字段

### 回归测试位置

- [`test/core/unit/monitor/test_window_monitor_afk.py`](../../test/core/unit/monitor/test_window_monitor_afk.py) — 6 个测试覆盖媒体/非媒体场景的 AFK 判定边界

## 触发条件

以下条件同时成立时触发：

1. 用户全屏看视频或玩游戏，应用向系统发出 DISPLAY/EXECUTION 电源请求（`is_any_video_playing()=True`）。
2. 用户中途离开，无任何键鼠输入。
3. 视频继续播放或游戏继续运行（电源请求持续存在）。
4. 用户离开期间未切换窗口（`_flush()` 不触发）。

非媒体场景（无电源请求）不受影响，仍由 `afk_timeout=180s` 正常判定。

## 完整失败数据流

假设用户 19:00 开始全屏看电影，19:30 离开，视频继续播放：

```text
19:00 用户开始看视频，is_any_video_playing()=True
      current_app="视频播放器", start_time=19:00

19:30 用户离开，无键鼠输入
      idle_time 持续增长

19:33 idle_time=180s (> afk_timeout)
      但 is_any_video_playing()=True
      currently_afk = True and not True = False
      不进入 AFK 状态，current_app/start_time 保持不变

20:00 用户仍未回，视频仍在播
      idle_time=1800s
      currently_afk 仍为 False
      _flush() 未触发，事件未结束

23:00 用户回来
      窗口时长 = 23:00 - 19:00 = 4小时（实际只看了30分钟）
```

## 发生原因

### 1. 豁免逻辑写成无上限的恒等式

原实现 `idle_time > afk_timeout and not is_any_video_playing()` 中，`not is_any_video_playing()` 是一个独立布尔项。当它为 `False` 时，无论 `idle_time` 多大，整个表达式都为 `False`。这是一个"信号存在则永久豁免"的逻辑，缺少"信号存在但长时间无输入仍判 AFK"的兜底。

### 2. 参考第三方实现时未审视设计前提

`is_any_video_playing()` 的实现参考了 aw-watcher-afk。aw-watcher-afk 的设计前提是"媒体播放=用户在消费内容=不算离开"，这在用户全程观看时成立，但未覆盖"媒体播放但用户已离开"的场景。引入第三方逻辑时需审视其假设是否完全匹配自身需求。

### 3. `_flush()` 的触发条件依赖状态变化

`_flush()` 在窗口切换、AFK 状态变化、排除标题匹配时触发。永不判 AFK 意味着 AFK 状态永不变化，`_flush()` 只在窗口切换时触发。若用户离开期间视频应用一直保持前台，事件会无限延长。

## 最佳方案

引入 `afk_timeout_media`（默认 3600s/60分钟）作为媒体场景的 AFK 上限，将内联判定抽取为 `_compute_afk_state()` 方法：

```python
def _compute_afk_state(self, idle_time: float, video_playing: bool) -> bool:
    if video_playing:
        return idle_time > self.afk_timeout_media
    return idle_time > self.afk_timeout
```

选择该方案的原因：

1. **保留媒体豁免的初衷**：看视频时仍用更长超时（60分钟），避免正常观看被误判。
2. **加上限防止无限积累**：60分钟无输入即使视频在播也判 AFK，覆盖"看一会就走"的主流场景。
3. **非媒体场景零影响**：`afk_timeout=180s` 先于 `afk_timeout_media=3600s` 触发，非媒体场景行为不变。
4. **配置可调**：用户可根据自己看视频习惯调整（最小 300s）。

### 默认值选择的权衡

| 默认值 | 看电影体验 | 看短视频/剧集体验 | 防"看一会就走"效果 |
|--------|------------|-------------------|----------------------|
| 10 分钟 | 差，2小时电影得动 11 次鼠标 | 好 | 强 |
| 30 分钟 | 中 | 好 | 中 |
| **60 分钟** | **好，多数电影能看完** | **好** | **中弱，但可接受** |
| 120 分钟 | 极好 | 好 | 弱 |

最终选择 60 分钟（3600s）：看长电影体验好，"看一会就走"单次损失 ≤60 分钟，远优于无限积累。

## 修复内容

### 1. 后端：抽取判定方法 + 新配置

- `WindowMonitor.__init__` 读取 `afk_timeout_media`（默认 3600.0）
- 新增 `_compute_afk_state(idle_time, video_playing)` 方法，媒体场景用 `afk_timeout_media`，非媒体用 `afk_timeout`
- `run()` 中内联判定改为调用 `_compute_afk_state()`
- `settings_manager.DEFAULTS` 加 `"afk_timeout_media": 3600.0`
- `setting_schemas.py` 的 `SettingItems` 和 `UpdateSettingsRequest` 加 `afk_timeout_media` 字段（`ge=300`）

### 2. 前端：配置项 UI

- `types.ts` 的 `Settings` 和 `UpdateSettingsRequest` 加 `afk_timeout_media?: number`
- `SettingsApp.tsx` 加 state、初始化、保存逻辑，在"数据源选择"和"截图监控"区块之间插入"离开判定"区块，单个 number 输入框（最小 300）

### 3. 回归测试

新增 [`test/core/unit/monitor/test_window_monitor_afk.py`](../../test/core/unit/monitor/test_window_monitor_afk.py)，6 个测试：

- **媒体场景**：`idle > media_timeout` → AFK；`idle < media_timeout` → 非 AFK；`idle == media_timeout` → 非 AFK（`>` 判定）
- **非媒体场景**：`idle > afk_timeout` → AFK；`idle < afk_timeout` → 非 AFK
- **隔离验证**：非媒体时即使 `idle > media_timeout`（故意设小）但 `< afk_timeout` 也不判 AFK，验证 `media_timeout` 不反向影响非媒体场景

## 验证结果

### 回归测试

```bash
python -m pytest test/core/unit/monitor/test_window_monitor_afk.py -v
```

结果：

```text
6 passed
```

修复前同一测试全部失败（`AttributeError: 'WindowMonitor' object has no attribute '_compute_afk_state'`），修复后全部通过。

## 教训与规则沉淀

1. **豁免逻辑必须有上限**：任何"信号 X 存在则豁免"的逻辑，都要配合"信号存在但长时间无反向输入仍触发"的兜底，否则信号持续存在时状态永远无法退出。
2. **参考第三方实现需审视前提**：引入 aw-watcher-afk 的媒体豁免时，未审视其"媒体播放=用户在消费内容"的假设是否覆盖"媒体播放但用户已离开"的场景。
3. **内联布尔表达式难以测试**：原 `idle_time > afk_timeout and not is_any_video_playing()` 内联在 `run()` 循环里，无法直接测试。抽取为 `_compute_afk_state()` 方法后可独立测试，也使逻辑更清晰。
4. **配置项暴露需考虑梯度关系**：`afk_timeout_media` 是该方向上第一个暴露给前端的 AFK 参数（`afk_timeout` 仍是隐藏配置）。用户看到"媒体播放超时"时需通过 UI 说明理解它与基础超时的关系，不能假设用户知道 180s 基础值的存在。

## 预防措施

- 新增"信号存在则豁免"类逻辑时，必须同时设计上限或反向验证机制。
- 参考 aw-watcher-afk 等第三方工具时，在代码注释中说明其设计前提，并审视是否与自身场景完全匹配。
- AFK/空闲判定逻辑抽取为独立方法，便于单元测试覆盖边界条件。

## 关联问题

- 监控截图 spec：[`docs/specs/2026-04-02-monitor-screenshot-spec.md`](../specs/2026-04-02-monitor-screenshot-spec.md) — AFK 段落已同步更新为双超时逻辑
- 配置 spec：[`docs/specs/2026-07-06-config-settings-spec.md`](../specs/2026-07-06-config-settings-spec.md) — 配置表已加 `afk_timeout_media` 行
