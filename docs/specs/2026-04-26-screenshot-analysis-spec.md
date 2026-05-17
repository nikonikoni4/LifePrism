---
version: 1.0
created_at: 2026-04-26
updated_at: 2026-04-26
last_updated: 创建截图分析功能规格文档
abstract: >
  截图分析功能规格文档。定义基于 LLM 的截图语义分析流程，包括高密度时间段识别、
  chunk 切分、截图查询、LLM 分析、行为总结等核心功能，以及新增的 tokens 消耗控制机制
  （基于分类的截图过滤，保留每个 app 的首张截图以提供初始语义）。
id: screenshot-analysis-spec
title: 截图语义分析功能
status: draft
module: lifeprism/llm/function/screenshot_analysis
sourc_spec: lifeprism/llm/function/screenshot_analysis.py
related_plan: docs/plans/active/2026-04-26-screenshot-tokens-control.md
code_scope:
  - lifeprism/llm/function/screenshot_analysis.py
  - lifeprism/repository/providers/screen_capture_repository.py
  - lifeprism/config/settings_manager.py
contract_refs:
  - lifeprism/llm/function/screenshot_analysis.py
  - lifeprism/config/database.py
---

# 截图语义分析功能

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿，包含现有实现和新增 tokens 控制功能 |

## Overview

截图语义分析功能通过 LLM 分析用户的行为截图，识别用户在特定时间段的行为语义。系统自动识别高密度活动时间段，将其切分为固定大小的 chunk，查询每个 chunk 的 active 截图，调用 LLM 进行语义分析，最后生成行为总结。

核心价值：
1. 自动识别用户行为模式，无需手动记录
2. 基于实际截图内容，避免过度推断
3. 结合用户目标（todolist），提供更精准的行为语义
4. 支持 tokens 消耗控制，通过分类过滤减少不必要的截图分析

## Scope

**在范围内：**

- 高密度活动时间段识别（基于 `density_utils.build_time_segments`）
- 时间段切分为固定大小的 chunk（默认 15 分钟）
- 查询 active 截图（从 `screen_captures` 表）
- LLM 截图语义分析（基于 `ANALYSIS_SYSTEM_PROMPT`）
- 行为总结生成（基于 `SUMMARY_SYSTEM_PROMPT`）
- 分析结果持久化（`raw_behavior_analysis` 和 `behavior_analysis` 表）
- Tokens 消耗控制机制（基于分类的截图过滤）

**不在范围内：**

- 截图采集机制（见 `monitor-screenshot-spec`）
- 分类系统实现（见 `category-spec` 和 `classify-spec`）
- 用户目标（todolist）管理
- 行为统计与可视化

## Core Behavior

### 1. 截图分析流程

完整流程分为以下步骤：

```
1. 查询活动日志（activity_logs）
   ↓
2. 识别高密度时间段（density_utils.build_time_segments）
   ↓
3. 根据频率等级动态切分 chunk（等级1=12分钟，等级2=10分钟，等级3=8分钟）
   ↓
4. 对每个 chunk 查询 active 截图（最多9张，超过则截断）
   ↓
5. 应用 tokens 控制过滤（基于分类忽略列表，保留每个 app 的首张截图）
   ↓
6. 调用 LLM 分析截图语义
   ↓
7. 合并相邻时间段的分析结果
   ↓
8. 调用 LLM 生成行为总结
   ↓
9. 持久化到数据库
```

### 2. 高密度时间段识别

**目的：** 识别用户活跃的时间段，避免分析空闲时间

**参数：**
- `density_threshold`：密度阈值（默认 0.6）
- `min_duration_minutes`：最小时长（默认 6 分钟）
- `bucket_minutes`：时间桶大小（默认 10 分钟）
- `max_bridge_buckets`：最大桥接桶数（默认 1）

**输出：** 高密度时间段列表，每项包含 `start` 和 `end`（ISO 格式）

### 3. Chunk 切分

**目的：** 将长时间段切分为固定大小的 chunk，便于 LLM 分析

**参数：**
- `frequency_level`：截图频率等级（1=低频 2=中频 3=高频，默认2）
- `chunk_minutes`：根据频率等级动态设置
  - 等级1（低频）：12分钟
  - 等级2（中频）：10分钟
  - 等级3（高频）：8分钟

**计算依据：**
- 考虑 engaged segment 冷却时间（12秒）
- 单张截图周期 = `first_active_after_seconds` + 12秒冷却
- 9张图片总时间 = 单张周期 × 9 + 20%余量
- 例如等级2：(45s + 12s) × 9 ≈ 8.55分钟 → 设置为10分钟

**规则：**
- 从时间段起点开始，每 `chunk_minutes` 分钟切分一次
- 最后一个 chunk 可能小于 `chunk_minutes`
- 每个 chunk 包含 `start` 和 `end`（ISO 格式）
- 每个 chunk 最多分析 9 张截图（Doubao Seed 2.0 Lite 限制）

### 4. 截图查询与数量限制

**数据源：** `screen_captures` 表

**查询条件：**
- `captured_at` 在 chunk 的 `[start, end)` 范围内
- `capture_reason = 'active'`（仅查询主动截图）

**数量限制：**
- 每个 chunk 最多分析 **9 张截图**（Doubao Seed 2.0 Lite 模型限制）
- 超过 9 张时，直接截断保留前 9 张（按时间顺序）
- 通过动态调整 chunk 大小，使大部分情况下截图数量接近 9 张

**返回字段：**
- `file_path`：截图文件路径（相对于 `lifeprism_data_path`）
- `window_app`：截图时的应用程序名称
- `window_title`：截图时的窗口标题
- `captured_at`：截图时间戳（YYYY-MM-DD HH:MM:SS 格式）

### 5. Tokens 消耗控制（新增功能）

**目的：** 通过过滤不需要分析的截图，减少 LLM tokens 消耗

**核心逻辑：**

```
对于每张截图：
1. 判断 window_app 是否为多用途应用（settings.is_multi_purpose_app）
   - 是：在 multi_purpose_map_cache 中查找该截图对应的分类
   - 否：在 single_purpose_map_cache 中查找该截图对应的分类

2. 获取该截图的分类（category_id）

3. 判断该分类是否在忽略列表中（settings.screen_analysis_ignore）
   - 是：判断是否是该 app 在当前时间段的第一张截图
     - 是：保留该截图（正常发送给 LLM）
     - 否：用文字替换该截图（不发送给 LLM）
   - 否：正常发送给 LLM
```


**配置项：**
- `screen_analysis_ignore`：需要忽略的分类 ID 列表（存储在 `config.yaml`）
- 前端提供多选界面，用户可选择需要忽略的主分类

**替换策略：**
- 被忽略的截图（非第一张）用文字描述替换，格式：`[无截图] timestamp: {captured_at} | app: {window_app} | title: {window_title} | category: {category_name} | description: {app_description}`
- 第一张截图正常发送，为 LLM 提供该 app 的初始语义上下文

### 6. LLM 截图语义分析

对每个chuck的截图结合截图时的app和title进行语义分析，生成行为

### 7. 行为总结生成

**目的：** 将连续的 chunk 分析结果合并为一个时间段的行为总结


## Technical Contract

### 1. 数据表结构

#### screen_captures 表
存储截图元数据，包含应用和窗口信息用于分类判断。

| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| id | TEXT | PRIMARY KEY, NOT NULL | 截屏记录 ID（如 sc-{uuid[:8]}） |
| captured_at | TEXT | NOT NULL | 截屏时间戳（YYYY-MM-DD HH:MM:SS 格式） |
| capture_reason | TEXT | NOT NULL | 触发截屏的原因（scheduled/active/enter） |
| file_path | TEXT | NOT NULL, UNIQUE | 相对 lifeprism_data_path 的路径 |
| window_app | TEXT | | 截屏时的应用程序名称 |
| window_title | TEXT | | 截屏时的窗口标题 |
| frequency_level | INTEGER | | 截屏频率等级（scheduled 为 NULL） |
| engaged_segment_id | TEXT | | 关联时间段 ID |
| is_afk | INTEGER | DEFAULT 0 | 是否处于 AFK 状态（0=否, 1=是） |
| created_at | TEXT | | 创建时间 |

**索引：**
- `idx_screen_captures_captured_at` (captured_at)
- `idx_screen_captures_segment_id` (engaged_segment_id)
- `idx_screen_captures_reason_time` (capture_reason, captured_at)

#### raw_behavior_analysis 表
存储 LLM 原始分析结果（未总结）。

| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| start_time | TEXT | PRIMARY KEY, NOT NULL | 开始时间（YYYY-MM-DD HH:MM:SS 格式） |
| end_time | TEXT | NOT NULL | 结束时间（YYYY-MM-DD HH:MM:SS 格式） |
| behavior | TEXT | NOT NULL | 行为描述（分点列出） |
| screen_count | INTEGER | NOT NULL, DEFAULT 0 | 截图数量 |
| created_at | TEXT | | 创建时间 |

**约束：**
- CHECK(end_time > start_time)

**索引：**
- `idx_raw_behavior_start_time` (start_time)
- `idx_raw_behavior_time_range` (start_time, end_time)

#### behavior_analysis 表
存储行为总结结果，用于 Timeline 展示。

| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| start_time | TEXT | PRIMARY KEY, NOT NULL | 开始时间（YYYY-MM-DD HH:MM:SS 格式） |
| end_time | TEXT | NOT NULL | 结束时间（YYYY-MM-DD HH:MM:SS 格式） |
| behavior | TEXT | NOT NULL | 行为详细描述（分点列出） |
| behavior_summary | TEXT | | 行为摘要（不超过 150 字） |
| title | TEXT | | 行为标题（不超过 30 字） |
| screen_count | INTEGER | NOT NULL, DEFAULT 0 | 截图数量 |
| created_at | TEXT | | 创建时间 |

**约束：**
- CHECK(end_time > start_time)

**索引：**
- `idx_behavior_start_time` (start_time)
- `idx_behavior_time_range` (start_time, end_time)

### 2. API 契约

#### 2.1 Timeline Behavior Summary API

**获取行为分析数据**

```
GET /timeline/behavior_summary?date={date}
```

**Query Parameters:**
- `date` (required): 查询日期，格式 YYYY-MM-DD

**Response:**
```json
{
  "behavior_list": [
    {
      "title": "重构用户认证接口为异步实现",
      "start_time": "2026-04-26 09:15:00",
      "end_time": "2026-04-26 10:30:00",
      "screen_count": 12,
      "behavior_summary": "阅读 FastAPI 官方文档的异步编程章节，在 api_service.py 中重构用户认证接口，将同步调用改为异步实现",
      "behavior": [
        {
          "time_range": "2026-04-26 09:15:00 ~ 2026-04-26 09:30:00",
          "behavior_items": "1. 查看 FastAPI 官方文档的异步编程章节\n2. 编辑 api_service.py 中的登录验证逻辑"
        },
        {
          "time_range": "2026-04-26 09:30:00 ~ 2026-04-26 10:30:00",
          "behavior_items": "1. 测试异步接口响应"
        }
      ],
      "created_at": "2026-04-26 10:30:15"
    }
  ]
}
```

**Schema:**
```python
class BehaviorItem(BaseModel):
    time_range: str = Field(..., description="时间区间，格式：YYYY-MM-DD HH:MM:SS ~ YYYY-MM-DD HH:MM:SS")
    behavior_items: str = Field(..., description="该区间范围内的详细行为分析")

class BehaviorAnalysisItem(BaseModel):
    title: str = Field(..., description="标题")
    start_time: str = Field(..., description="开始时间，格式：YYYY-MM-DD HH:MM:SS")
    end_time: str = Field(..., description="结束时间，格式：YYYY-MM-DD HH:MM:SS")
    screen_count: int = Field(..., description="截图数量")
    behavior_summary: str = Field(..., description="总结性描述")
    behavior: list[BehaviorItem] = Field(..., description="分区间的详细行为分析")
    created_at: Optional[str] = Field(None, description="创建时间")

class BehaviorAnalysisResponse(BaseModel):
    behavior_list: List[BehaviorAnalysisItem] = Field(default_factory=list)
```

#### 2.2 Sync Service API

截图分析触发依附于原来的同步逻辑，不新增新的 API 接口。

**增量同步** ： 输入时间范围是raw_behavior_analysis表的最后一条记录的end_time作为start_time，当前时间作为end_time

**按时间范围同步** ： 输入时间范围是用户指定的start_time和end_time，包含start_time和end_time在内


#### 2.3 Settings API（Tokens 控制配置）

**获取截图分析忽略配置**

```
GET /settings/screen-analysis-ignore
```

### 4. 前端契约

#### 4.1 Timeline 页面 - Behavior Summary 展示

**展示内容：**
    1. title展示：依附于时间轴右侧，采用customblock类似的展示形式，作为时间轴的一个"批注"
    2. 点击title：右侧展示详细行为（behavior）
    3. behavior 数据结构：behavior 为结构化列表，每项包含 `time_range`（时间区间）和 `behavior_items`（该区间的详细行为），前端需按时间段分组展示

#### 4.2 Settings 页面 - 截图分析配置


    
**UI 布局：**
```
┌─────────────────────────────────────┐
│ 截图分析配置                         │
├─────────────────────────────────────┤
│ 选择需要忽略的分类（不进行截图分析）  │
│                                     │
│                                     │
│ ☐ 工作                           │
│ ☑ 娱乐                           │
│ ☐ 学习                           │
│ ☑ 其他                           │
│                                     │
│ 建议：选择目的明确且不需要仔细分析的分类，例如娱乐等│
| 说明：被忽略分类的每个 app 会保留第一张截图提供初始语义，后续截图用文字替代以减少 tokens 消耗|
│                                     │
└─────────────────────────────────────┘
```
**功能需求：**
1. 获取主分类列表
2. 获取当前截图分析忽略配置
3. 在 UI 中展示每个分类以及被忽略的分类，用户可选择是否忽略该分类

### 5. 配置项

```yaml
# config.yaml

# 截图分析忽略的分类列表（主分类 ID）
screen_analysis_ignore:
  - cat-xxxxxxxx  # 娱乐
  - cat-yyyyyyyy  # 其他
```

## Acceptance Notes

- [ ] 高密度时间段识别正确，密度阈值和最小时长可配置
- [ ] Chunk 大小根据截图频率等级动态调整
- [ ] 每个 chunk 最多分析 9 张截图，超过则截断前 9 张
- [ ] 仅查询 active 截图，不包括 scheduled 和 enter 截图
- [ ] 数据库存储时间戳格式为 YYYY-MM-DD HH:MM:SS，查询接口支持 ISO 格式输入并自动转换
- [ ] LLM 分析遵循"精确度优先"原则，不输出不确定的结果
- [ ] 行为总结合并相似内容，结合用户目标进行说明
- [ ] 原始分析结果和行为总结分别存储到不同表
- [ ] Tokens 控制功能正确过滤忽略分类的截图
- [ ] 前端配置界面可多选需要忽略的分类
- [ ] 配置保存后立即生效，下次分析时应用新配置

## Out of Spec

- 截图采集机制（scheduled/active/enter 三类截图的触发逻辑）
- 分类系统的完整实现（分类 CRUD、Map Cache 管理）
- 用户目标（todolist）的管理和展示
- 行为统计与可视化（时间分布、分类占比等）
- LLM 模型选择和参数配置
- 截图清理策略（过期截图的删除逻辑）
