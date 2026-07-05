---
version: 1.0
created_at: 2026-05-03
updated_at: 2026-05-03
last_updated: 创建文档初稿
abstract: 电脑使用详细日志查询工具设计决策：选择独立工具而非合并到聚合查询工具，基于信息密度差异、使用场景差异和 LLM 工具调用可理解性考虑
status: decided
---

## 版本历史

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿，确立工具分离方案 |

## 问题界定

### 问题简述

在为 LLM Agent 设计数据查询工具时，需要决定是否将"电脑使用详细日志查询"功能合并到现有的 `UserActivitySummaryTool` 聚合查询工具中，还是创建独立的工具。

### 讨论范围

- 电脑使用详细日志查询工具的职责定义
- 工具合并 vs 分离的设计权衡
- 参数设计和时间范围验证策略
- LLM 工具选择机制和误触发风险控制
- 工具描述（description）的可理解性设计

### 非讨论范围

- 工具调用框架的选择（已确定使用 LiteLLM）
- 数据库查询性能优化（属于实现细节）
- 其他数据类型的加入（如 habits、goals）
- 前端展示逻辑

### 关键信息明确定义

1. **聚合查询工具**：指现有的 `UserActivitySummaryTool`，包含 4 类数据：
   - `computer_usage_stats`：电脑使用时段统计（高密度时间段 + 分类占比）
   - `user_behavior_notes`：用户自定义行为备注
   - `ai_behavior_notes`：AI 行为分析
   - `todolist`：待办事项

2. **详细日志查询**：指查询原始的电脑使用记录，每条记录包含：
   - `start_time`, `end_time`, `app`, `title`, `duration`, `category_name`, `sub_category_name`

3. **信息密度差异**：
   - 聚合数据：固定输出约 6 个时间段，约 500-1000 tokens
   - 详细日志：假设每 5 分钟切换一次应用，2 天 = 576 条记录，约 30k-60k tokens
   - **差异倍数：30-60 倍**

4. **使用场景**：
   - **概览查询（高频）**：用户问"我这两天做了什么？" → 使用聚合数据
   - **详细查询（低频）**：用户问"我昨天下午 3 点到 4 点具体做了什么？" → 使用详细日志
   - **关键特征**：详细查询的时间范围通常是用户明确指定的小范围（1-2 小时）

### 问题深度

本决策不仅涉及"合并还是分离"的表层选择，更深层次涉及：

1. **工具设计的职责划分原则**：单一职责 vs 功能聚合的权衡
2. **LLM 工具调用的可理解性**：工具描述如何影响 LLM 的选择准确性
3. **误触发风险控制**：如何通过设计避免性能问题和 token 浪费
4. **用户认知流程匹配**：工具设计如何反映"先概览后细节"的自然思维模式

## 现状分析

### 当前工具设计

`UserActivitySummaryTool` 采用"多选项聚合"设计：

```python
{
    "name": "user_activity_summary",
    "description": "查询 LifePrism 系统中的数据，包括电脑使用日志，电脑使用时段和该时段内的分类统计数据，用户自定义行为备注，AI行为备注，目标数据，todolist",
    "parameters": {
        "query_option": ["computer_usage_stats", "user_behavior_notes", "ai_behavior_notes", "todolist"],
        "start_time": "YYYY-MM-DD HH:MM:SS",
        "end_time": "YYYY-MM-DD HH:MM:SS"
    }
}
```

**设计特点**：
- 所有数据类型共享相同的时间范围参数
- 通过 `query_option` 数组让 LLM 选择需要的数据类型
- 所有选项的信息密度相近（都是汇总性数据）

### 待解决的问题

1. **信息密度不匹配**：
   - 现有 4 个选项的信息密度相近（都是低密度汇总数据）
   - 详细日志的信息密度是它们的 30-60 倍
   - 如果合并，会导致一个工具同时处理两种截然不同的数据量级

2. **时间范围约束冲突**：
   - 聚合数据适合 1-7 天的时间范围
   - 详细日志只能支持最多 2 小时（否则数据过多）
   - 如果合并，需要根据 `query_option` 动态验证时间范围

3. **使用场景混淆**：
   - 聚合数据：用于"了解一段时间的整体情况"
   - 详细日志：用于"追溯特定时刻的具体操作"
   - 两者的查询意图本质不同

4. **工具描述的可理解性**：
   - 当前描述已经较长（包含 4 类数据）
   - 如果加入详细日志，需要同时说明两种使用场景和时间范围约束
   - 描述过长可能降低 LLM 的理解准确性

## 可选方案

### 方案 A：合并到现有工具

**设计**：
- 在 `query_option` 中增加 `computer_usage` 选项
- 在工具内部根据 `query_option` 验证时间范围
- 如果选择 `computer_usage` 且时间范围超过 2 小时，返回错误提示

**优势**：
1. 工具数量少，接口统一
2. 所有数据查询都在一个工具中，减少 LLM 的选择负担
3. 代码复用度高（共享时间解析、错误处理逻辑）

**劣势**：
1. **职责混乱**：一个工具同时承担"概览"和"详细"两种截然不同的查询意图
2. **参数验证复杂**：需要根据 `query_option` 动态验证时间范围，增加条件分支
3. **错误恢复成本高**：LLM 需要多次尝试才能找到正确的参数组合（先尝试大时间范围 → 收到错误 → 重试小时间范围）
4. **描述难以清晰**：很难在一个 description 中同时说明两种使用场景而不让 LLM 困惑
5. **误触发风险**：LLM 可能在不合适的场景下选择 `computer_usage`，导致性能问题

**实现示例**：
```python
async def execute(self, **kwargs: Any) -> Any:
    query_option = set(kwargs.get('query_option', []))
    start_time = kwargs.get('start_time', '')
    end_time = kwargs.get('end_time', '')
    
    # 时间范围验证
    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    time_diff_hours = (end_dt - start_dt).total_seconds() / 3600
    
    if 'computer_usage' in query_option and time_diff_hours > 2:
        return "错误：详细日志查询的时间范围不能超过 2 小时，请缩小范围或使用 computer_usage_stats"
    
    # ... 后续查询逻辑
```

### 方案 B：分层设计

**设计**：
- 聚合工具作为主入口，在返回结果中提供"如需查看详细日志，请使用 xxx 工具"的提示
- 详细日志工具作为二级工具，需要明确的时间范围约束

**优势**：
1. 符合"先概览后细节"的认知流程
2. 通过提示引导 LLM 正确使用工具

**劣势**：
1. **增加交互复杂度**：需要 LLM 理解"先调用工具 A，根据返回结果决定是否调用工具 B"
2. **不符合 function calling 范式**：OpenAI 的工具调用是"一次性决策"，不是"多轮探索"
3. **用户体验差**：用户明确问"昨天下午 3 点做了什么"，LLM 却先返回概览再问"需要详细信息吗？"
4. **增加 token 消耗**：需要两次工具调用才能得到最终结果

### 方案 C：完全分离（推荐）

**设计**：
- 保持 `UserActivitySummaryTool` 不变（聚合查询工具）
- 创建独立的 `ComputerUsageDetailQueryTool`（详细日志查询工具）
- 两个工具通过 description 互相引用，帮助 LLM 理解何时切换

**优势**：
1. **职责清晰**：每个工具有明确的单一职责
2. **避免误触发**：通过工具名称和描述明确区分使用场景
3. **参数验证简单**：详细日志工具只需验证时间范围，无需条件分支
4. **描述易于理解**：每个工具的描述专注于一个场景，LLM 更容易理解
5. **符合用户认知**：工具设计反映了"概览"和"详细"的自然区分
6. **错误提示友好**：详细日志工具可以在错误信息中明确建议使用聚合工具

**劣势**：
1. 工具数量增加（从 1 个变为 2 个）
2. 需要在两个工具的描述中互相引用（增加维护成本）

**实现示例**：

**工具 1：`UserActivitySummaryTool`（更新描述）**
```python
{
    "name": "user_activity_summary",
    "description": "查询 LifePrism 系统的概览数据，适用于了解一段时间内的整体情况。包括：电脑使用时段统计（高密度时间段+分类占比）、用户自定义备注、AI 行为分析、待办事项。时间范围建议：1-7 天。如需查看特定时间段的详细操作记录，请使用 computer_usage_detail_query 工具。",
    "parameters": {
        "query_option": ["computer_usage_stats", "user_behavior_notes", "ai_behavior_notes", "todolist"],
        "start_time": "YYYY-MM-DD HH:MM:SS",
        "end_time": "YYYY-MM-DD HH:MM:SS"
    }
}
```

**工具 2：`ComputerUsageDetailQueryTool`（新增）**
```python
{
    "name": "computer_usage_detail_query",
    "description": "查询电脑使用的详细日志，返回每个应用窗口的切换记录（应用名、窗口标题、开始时间、结束时间、时长、分类）。⚠️ 仅在用户明确询问特定时间段的详细操作时使用。时间范围限制：最多 2 小时。如需查看更长时间的概览，请使用 user_activity_summary 工具的 computer_usage_stats 选项。",
    "parameters": {
        "start_time": "YYYY-MM-DD HH:MM:SS",
        "end_time": "YYYY-MM-DD HH:MM:SS"
    }
}
```

```python
class ComputerUsageDetailQueryTool(Tool):
    async def execute(self, **kwargs: Any) -> Any:
        start_time = kwargs.get('start_time', '')
        end_time = kwargs.get('end_time', '')
        
        # 时间范围验证
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        time_diff_hours = (end_dt - start_dt).total_seconds() / 3600
        
        if time_diff_hours > 2:
            return (
                f"❌ 时间范围过大（{time_diff_hours:.1f} 小时），详细日志查询最多支持 2 小时。\n"
                f"建议：\n"
                f"1. 缩小时间范围到 2 小时内\n"
                f"2. 或使用 user_activity_summary 工具的 computer_usage_stats 选项查看概览"
            )
        
        # 查询详细日志
        logs, _ = computer_usage_repository.query_computer_usage_with_names(
            QueryOptions(fields=['start_time', 'end_time', 'app', 'title', 'duration', 'category_name', 'sub_category_name'])
            .with_time_range(start_time, end_time)
        )
        
        if not logs:
            return f"## 电脑使用详细日志\n{start_time} ~ {end_time} 期间没有使用记录"
        
        # 格式化输出
        content = f"## 电脑使用详细日志\n时间范围：{start_time} ~ {end_time}\n共 {len(logs)} 条记录\n\n"
        for i, log in enumerate(logs, 1):
            duration_min = log['duration'] // 60
            content += (
                f"{i}. {log['start_time']} ~ {log['end_time']} ({duration_min}分钟)\n"
                f"   应用：{log['app']}\n"
                f"   窗口：{log['title']}\n"
                f"   分类：{log['category_name']} > {log['sub_category_name']}\n\n"
            )
        
        return content
```

## 最终决策

**选择方案 C：完全分离**

创建独立的 `ComputerUsageDetailQueryTool`，与现有的 `UserActivitySummaryTool` 并存。

## 决策原因

### 核心论点

**信息密度差异（30-60 倍）+ 使用场景本质不同 → 应该分离为两个工具**

### 详细理由

#### 1. 职责单一原则

- **聚合查询工具**的职责：回答"这段时间我做了什么"（宏观视角）
- **详细日志工具**的职责：回答"某个时刻发生了什么"（微观视角）
- 两者的查询意图本质不同，不应强行合并

#### 2. 避免误触发的代价

- 如果详细日志查询被大时间范围触发，可能导致：
  - 数据库查询性能问题（返回数千条记录）
  - Token 浪费（30k-60k tokens）
  - API 调用成本增加
- 通过工具分离，可以在工具名称和描述层面就明确区分，降低误触发概率

#### 3. 参数验证的简洁性

- **分离方案**：详细日志工具只需验证时间范围 ≤ 2 小时，逻辑简单
- **合并方案**：需要根据 `query_option` 动态验证，增加条件分支和复杂度

#### 4. LLM 工具选择的可理解性

- 现代 LLM（GPT-4、Claude 3.5+）能够理解工具描述中的使用场景
- 通过明确的工具名称（`user_activity_summary` vs `computer_usage_detail_query`）和描述，LLM 可以准确匹配用户意图
- 在描述中使用 ⚠️ 符号和"仅在...时使用"的明确限定，进一步提高可理解性

#### 5. 符合用户认知流程

- 用户的自然思维模式是"先概览后细节"
- 工具设计应该反映这种认知流程，而不是强行统一接口
- 当用户问"我这两天做了什么"时，自然应该使用聚合工具
- 当用户问"昨天下午 3 点做了什么"时，自然应该使用详细工具

#### 6. 错误恢复的友好性

- **分离方案**：如果 LLM 误用详细工具查询大时间范围，工具返回明确的错误提示和建议（"请使用 user_activity_summary 工具"）
- **合并方案**：LLM 需要多次尝试不同的参数组合，增加交互轮次

### 权衡取舍

**优先级排序**：
- ✅ 职责清晰 > 工具数量少
- ✅ 避免误触发 > 统一接口
- ✅ 符合用户认知流程 > 减少参数验证

**接受的代价**：
- 工具数量从 1 个增加到 2 个
- 需要在两个工具的描述中互相引用（增加维护成本）

**不接受的代价**（方案 A 的问题）：
- 职责混乱导致的长期维护困难
- 误触发导致的性能问题和成本浪费
- 参数验证复杂度增加

## 实施建议

### 立即行动

1. **实现 `ComputerUsageDetailQueryTool`**（参考上面的代码示例）
2. **更新 `UserActivitySummaryTool` 的 description**，明确说明它是"概览工具"，并引用详细工具
3. **在两个工具的 description 中互相引用**，帮助 LLM 理解何时切换

### 后续观察

1. **收集工具调用日志**：
   - 记录 LLM 选择哪个工具
   - 记录使用的参数（特别是时间范围）
   - 记录是否触发错误提示

2. **监控误触发率**：
   - 统计"详细日志工具被用于大时间范围"的频率
   - 目标：误触发率 < 10%

3. **分析用户问题模式**：
   - 哪些问法会导致 LLM 选错工具
   - 是否需要调整工具描述

### 可能的优化方向

如果发现误触发率高（>10%），可以考虑：

1. **在 system prompt 中添加工具使用指南**：
   ```
   工具选择原则：
   - 用户问"这几天/这周/最近" → 使用 user_activity_summary
   - 用户问"昨天下午 3 点/今天上午 10-11 点" → 使用 computer_usage_detail_query
   ```

2. **调整工具描述的措辞**：
   - 增加更多的使用场景示例
   - 使用更强的限定词（"必须"、"仅限"）

3. **添加工具调用前的确认机制**（如果框架支持）

4. **使用 LLM 的 reasoning 能力**（如 Claude 的 thinking 模式）让它先判断再调用

## 适用条件

这个决策适用于以下情况：

1. **LLM 能力足够**：使用现代 LLM（GPT-4、Claude 3.5+）能够理解工具描述中的使用场景
2. **用户意图明确**：用户会用自然语言区分"概览"和"详细"需求
3. **错误成本可控**：即使 LLM 误用工具，2 小时的限制也能防止严重的性能问题

如果使用较弱的 LLM（如 GPT-3.5），可能需要更强的约束机制（如 system prompt 中的明确指南）。

## 相关文档

- 实现文件：`lifeprism/llm/agent/tools/lifeprismsystem.py`
- Repository 接口：`lifeprism/repository/computer_usage_repository.py`
- 相关决策：`docs/design-decisions/2026-04-24-repository-interface-encapsulation.md`（repository 强封装策略）
