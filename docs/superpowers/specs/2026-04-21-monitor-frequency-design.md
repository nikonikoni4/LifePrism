---
version: 1.0
created_at: 2026-04-21
status: draft
title: 监控频率等级重新设计
abstract: 基于测试数据（稀释一半active截图后语义质量无明显下降）和segment分布分析（62%的segment只有1张截图），重新设计监控频率等级，降低存储和token消耗，同时保持语义质量。
related_spec: docs/specs/2026-04-02-monitor-screenshot-spec.md
---

# 监控频率等级重新设计

## 背景

### 测试发现

1. **语义质量测试**：将active截图稀释一半（只保留单数截图）后，语义判断准确率无明显下降
   - 原始：234张active截图，token消耗343,643
   - 稀释后：123张active截图，token消耗198,853（减少42%）
   - 测试结果：docs/temp/monitor/screenshot_analysis_v2_result.txt

2. **Segment分布分析**：
   - 总active截图：370张
   - 第一张截图：200张（54.1%）
   - 后续截图：170张（45.9%）
   - **关键发现**：62%的engaged segment只产生1张截图（124/200）
   - 平均每个segment：1.85张截图

### 问题

1. **存储压力**：当前频率下，不到一天产生800MB截图数据
2. **Token消耗**：单次分析消耗34万token
3. **频率过高**：大量短暂engaged状态（<60s）产生冗余截图

## 设计目标

1. **降低存储和token消耗**：减少50%以上的截图数量
2. **保持语义质量**：不错过有意义的工作片段
3. **优化segment覆盖**：针对62%只有1张截图的segment，优化第一张阈值
4. **全局默认等级**：大部分时间不需要用户调整

## 频率等级设计

### 新的频率参数表

| 等级 | 第一张主动截图阈值 | 后续主动截图间隔 | Enter 冷却 |
| ---- | ------------------ | ---------------- | ---------- |
| L1 Low | 60s | 240s (4min) | 120s (2min) |
| L2 Medium（默认） | 45s | 180s (3min) | 90s (1.5min) |
| L3 High | 30s | 120s (2min) | 60s (1min) |

**Scheduled截图间隔**：180s (3min)

### 与原始设计对比

| 参数 | 原始设计 | 新设计（方案A'） | 变化 |
|------|---------|----------------|------|
| **L2 - 第一张阈值** | 30s | 45s | +50% |
| **L2 - 后续间隔** | 60s | 180s | +200% |
| **L2 - Enter冷却** | 6s | 90s | +1400% |
| **Scheduled间隔** | 60s | 180s | +200% |

### 设计原则

1. **降低第一张阈值**（相比简单翻倍方案）
   - 原因：62%的segment只有1张截图，第一张阈值太高会错过短暂工作片段
   - L2从60s降至45s，在捕获覆盖和频率控制间取得平衡

2. **提高后续间隔**（相比简单翻倍方案）
   - 原因：大部分segment只有1张，后续间隔长一点影响不大
   - L2从120s提高至180s，进一步降低长时间工作的截图密度

3. **大幅提高Enter冷却**
   - 原因：编码场景下频繁回车导致截图爆量
   - L2从6s提高至90s，避免高频Enter事件

4. **提高Scheduled间隔**
   - 原因：scheduled截图仅作为背景信息，不需要太高频率
   - 从60s提高至180s，减少背景截图数量

## 预期效果

### 截图数量估算

以L2为例，假设一个10分钟的engaged segment：

| 版本 | 第一张时机 | 后续截图次数 | 总截图数 |
|------|-----------|------------|---------|
| 原始设计 | 30s | (600-30)/60 ≈ 9张 | 10张 |
| 新设计 | 45s | (600-45)/180 ≈ 3张 | 4张 |

**减少60%的active截图**

### Token消耗估算

基于测试数据推算：
- 原始设计：~34万token/天
- 新设计：~13-15万token/天（减少55-60%）

### 语义质量

- 测试验证：稀释50%后语义质量无明显下降
- 新设计：通过优化第一张阈值，保持对短暂工作片段的捕获能力

## 技术实现

### 1. 硬编码频率参数（临时方案）

**本期不修改配置文件，直接硬编码在代码中，待测试验证后再固化到配置**

### 2. FrequencyPolicy 预定义策略

**修改 `lifeprism/monitor/screenshot/models.py`**

```python
from dataclasses import dataclass
from enum import Enum

@dataclass(frozen=True)
class FrequencyPolicy:
    level: int
    first_active_after_seconds: int
    repeat_active_every_seconds: int
    enter_cooldown_seconds: int
```

**新增 `lifeprism/monitor/screenshot/policy.py`**

```python
from lifeprism.monitor.screenshot.models import FrequencyPolicy

# 预定义3档策略
FREQUENCY_POLICIES = {
    1: FrequencyPolicy(
        level=1,
        first_active_after_seconds=60,
        repeat_active_every_seconds=240,
        enter_cooldown_seconds=120,
    ),
    2: FrequencyPolicy(
        level=2,
        first_active_after_seconds=45,
        repeat_active_every_seconds=180,
        enter_cooldown_seconds=90,
    ),
    3: FrequencyPolicy(
        level=3,
        first_active_after_seconds=30,
        repeat_active_every_seconds=120,
        enter_cooldown_seconds=60,
    ),
}

def get_frequency_policy(level: int) -> FrequencyPolicy:
    """根据等级获取频率策略"""
    if level not in FREQUENCY_POLICIES:
        raise ValueError(f"Invalid frequency level: {level}, must be 1, 2, or 3")
    return FREQUENCY_POLICIES[level]
```

### 3. 使用方式

**在 `ScreenshotScheduler` 中硬编码使用L2策略**

```python
from lifeprism.monitor.screenshot.policy import get_frequency_policy

class ScreenshotScheduler:
    def __init__(self):
        # 硬编码使用L2等级，待测试验证后再改为从配置读取
        self.policy = get_frequency_policy(2)
        
        # 使用policy中的参数
        self.first_active_threshold = self.policy.first_active_after_seconds
        self.repeat_interval = self.policy.repeat_active_every_seconds
        self.enter_cooldown = self.policy.enter_cooldown_seconds
        
        # scheduled间隔硬编码为180s
        self.scheduled_interval = 180
```

### 4. 后续配置化（待测试验证后）

待实际测试验证频率参数合理后，再将参数固化到配置文件：

**config.yaml**

```yaml
# 监控截图配置
scheduled_screenshot_interval_seconds: 180  # scheduled截图间隔（秒）
active_screenshot_frequency_level: 2        # 主动截图频率等级（1/2/3）
screenshot_retention_days: 3                # 截图保留天数
```

**settings_manager.py**

```python
DEFAULT_SETTINGS = {
    "scheduled_screenshot_interval_seconds": 180,
    "active_screenshot_frequency_level": 2,
}
```

## 前端设置界面（未来）

本期不开放前端UI配置，用户需要修改配置文件。

未来可在设置页面添加：

```
截图监控频率：
○ 低频（L1）- 节省存储，适合长时间监控
● 中频（L2）- 推荐，平衡语义质量和存储
○ 高频（L3）- 高精度，适合需要详细记录的场景

说明：
- L1：第一张60s后，后续每4分钟
- L2：第一张45s后，后续每3分钟（推荐）
- L3：第一张30s后，后续每2分钟
```

## 验收标准

1. **硬编码生效**：ScreenshotScheduler使用L2策略（45s/180s/90s）
2. **scheduled间隔**：硬编码为180s
3. **参数正确**：3档策略的参数与设计文档一致
4. **policy.py存在**：新增的policy.py文件包含FREQUENCY_POLICIES和get_frequency_policy函数
5. **不修改配置**：本期不修改settings_manager.py和config.yaml

## 后续优化

**本设计为临时方案，需要经过实际测试验证**

后续优化方向：
1. 收集实际使用数据，分析新频率下的语义质量
2. 根据不同工作场景（编码/阅读/会议）动态调整频率
3. 基于窗口变化频率自适应调整截图策略
4. 优化prompt，进一步降低token消耗

## Out of Scope

1. 不实现前端UI配置（本期）
2. 不实现动态频率调整（本期）
3. 不实现场景识别（本期）
4. 不修改keyboard_keepalive和mouse_keepalive参数（保持12s/6s）
