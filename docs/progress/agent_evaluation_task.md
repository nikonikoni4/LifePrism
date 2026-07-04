# Agent 评估任务清单

> 创建时间：2026-06-30  
> 目的：建立 LLM Agent 的系统化评估体系，支持 prompt 优化和模型选型

---

## 评估架构说明

### 评估层级
1. **通用场景**：适用于所有 LLM 调用的基础指标
2. **业务场景**：针对特定 workflow 的专项指标

### 数据来源
- 主要依赖 `lifeprism/llm/utils/llm_call_logger.py` 记录的调用日志
- 部分指标需要人工标注或 LLM 辅助评分

### 实现优先级
- **P0（立即可做）**：完全自动化，基于现有日志直接计算
- **P1（两周内）**：半自动化，需要少量人工标注或 LLM 辅助
- **P2（长期规划）**：需要构建完整数据集和评估基础设施

---

## 通用场景（所有 LLM 任务）

### 1. Token 效率 [P0]

**评估目的**：
1. 成本控制：监控各任务的 token 消耗，控制 API 成本
2. 模型对比：对比不同模型在相同任务上的 token 效率
3. 异常检测：识别消耗异常高的调用，可能是输入异常或 LLM 出问题

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 平均 input tokens | `Σ prompt_tokens / N` | 取决于任务 | - |
| 平均 output tokens | `Σ completion_tokens / N` | 取决于任务 | - |
| Token 标准差 | `std(total_tokens)` | < 平均值的 50% | **标准差过大**（>50%均值）说明输入不稳定或 prompt 需要优化 |
| 输入输出比 | `avg_output / avg_input` | 总结<1, 对话≈0.5, 生成>1 | **比例异常**说明任务类型与预期不符 |
| 成本估算 | `(input×单价 + output×单价)` | 按预算设定 | **超预算**需优化 prompt 或换模型 |
| 离群值数量 | `count(tokens > μ+2σ)` | < 5% | **离群值过多**（>5%）说明有异常调用，需排查 |

**问题诊断**：
- ✅ **成本过高**：考虑缩短 prompt、减少示例、或换更便宜的模型
- ✅ **波动过大**：检查输入是否有极端情况（如特别长的日记）
- ✅ **离群值频繁**：检查对应的输入和输出，可能是 LLM 陷入重复或错误推理

**数据来源**：`llm_call_logger.export_by_prompt()` → `tokens` 字段

**⚠️ 注意事项**：
- 当前 `token_type` 粒度较粗，详见 `docs/progress/token_efficiency_issues.md`
- 复杂度评分需要历史数据支持，冷启动时无法计算

---

### 2. 错误率 [P0]（节点错误率，包含llm调用）

**评估目的**：
1. 稳定性监控：确保 LLM 调用成功率在可接受范围
2. 问题定位：识别高频错误类型，针对性优化
3. 模型对比：对比不同模型的稳定性

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 错误率 | `error_count / total_calls` | < 2% | **错误率 >2%** 说明调用不稳定，需排查原因 |
| 超时错误占比 | `timeout_errors / total_errors` | - | **超时多**说明 prompt 过长或模型过载 |
| 参数错误占比 | `param_errors / total_errors` | - | **参数错误多**说明 prompt 构造有 bug |
| 模型拒绝占比 | `refusal_errors / total_errors` | - | **拒绝多**说明 prompt 可能触发安全策略 |

**问题诊断**：
- ✅ **超时频繁**：缩短 prompt、减少图片数量、或增加 timeout 配置
- ✅ **参数错误**：检查 prompt 构造逻辑，确保参数格式正确
- ✅ **模型拒绝**：检查 prompt 是否包含敏感内容，调整措辞

**数据来源**：`llm_call_logger` → `error` 字段

---

### 3. 延迟 [P0]

**评估目的**：
1. 用户体验：确保响应时间在可接受范围（尤其是 chat 场景）
2. 性能优化：识别慢查询，针对性优化
3. 模型对比：对比不同模型的响应速度

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 平均延迟 | `Σ duration / N` | chat<5s, workflow<30s | **延迟过高**影响用户体验 |
| P95 延迟 | 95% 的调用在此时间内完成 | chat<10s, workflow<60s | **P95 过高**说明有慢查询拖后腿 |
| P99 延迟 | 99% 的调用在此时间内完成 | chat<15s, workflow<120s | **P99 过高**说明有极端慢查询 |
| 超时次数 | `count(duration > 30s)` | < 1% | **超时多**说明模型过载或 prompt 过长 |

**问题诊断**：
- ✅ **平均延迟高**：缩短 prompt、减少图片、或换更快的模型
- ✅ **P95/P99 高**：排查慢查询的输入特征（如特别长的输入）
- ✅ **超时频繁**：考虑增加 timeout 配置或换模型

**数据来源**：`llm_call_logger` → `timestamp` 字段

**⚠️ 注意事项**：当前 logger 只记录单个 timestamp，需要增加 `duration` 字段

---

### 4. 格式正确性 [P0]（仅 JSON 输出任务）

**评估目的**：
1. prompt 质量：检查 prompt 是否清晰指定了输出格式
2. 模型能力：检查模型是否能稳定输出结构化数据
3. 解析成功率：确保下游代码能正确解析输出

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| JSON 有效率 | `valid_json / total` | > 95% | **有效率 <95%** 说明 prompt 格式说明不清晰 |
| 字段完整率 | `has_required_fields / total` | > 98% | **完整率 <98%** 说明模型经常遗漏字段 |
| 值类型正确率 | `correct_type / total` | > 98% | **类型错误多**说明模型理解有偏差 |
| 枚举值合法率 | `valid_enum / total` | > 95% | **非法枚举多**说明类别定义不清晰 |

**问题诊断**：
- ✅ **JSON 无效**：在 prompt 中强调 "只输出 JSON，不要输出其他内容"
- ✅ **字段缺失**：在 prompt 中列出必需字段，强调 "必须包含"
- ✅ **类型错误**：在 prompt 中明确字段类型（如 "category 是字符串"）
- ✅ **枚举非法**：在 prompt 中列出所有合法值，强调 "必须从以下选项中选择"

**适用任务**：
- `_behavior_summary`（需要 title + behavior_summary）
- `classify` 系列（需要 {id: [category, sub_category, link_to_goal]}）

**实现方式**：
```python
try:
    data = json.loads(extract_json_from_response(output))
    # 检查必需字段
    assert "title" in data and "behavior_summary" in data
except (json.JSONDecodeError, AssertionError):
    format_error = True
```

---

## 业务场景 1：dreaming workflow

**涉及任务**：
- `summary_activities`：总结活动数据
- `summary_moods`：总结心情数据
- `extract_from_chat_messages`：提取聊天记录关键信息
- `update_memory`：更新用户记忆文档

---

### summary_activities业务评估

#### 1.1 格式遵循度 [P0]

**评估目的**：
- 确保输出格式符合下游解析需求
- 发现模型是否理解格式要求

**定义** ：
有没有按照相关提示词要求输出相应的格式


#### 1.2 幻觉率

**评估目的**：
- 防止 LLM 编造不存在的活动或事件
- 确保总结忠实于原始数据







### 1.1 格式遵循度 [P0]

**评估目的**：
- 确保输出格式符合下游解析需求
- 发现模型是否理解格式要求

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 正确格式率 | `有序号格式的调用 / 总调用` | > 95% | **<95%** 说明 prompt 格式说明不清晰 |
| 错误格式率 | `有 markdown 标题的调用 / 总调用` | < 5% | **>5%** 说明模型经常忽略格式要求 |

**问题诊断**：
- ✅ **频繁用 markdown 标题**：在 prompt 中强调 "使用序号格式（1. 2. 3.），不要使用 markdown 标题（### ##）"
- ✅ **部分模型不遵守**：考虑在 prompt 中增加正例示例

**背景**：代码中有 `_normalize_activity_summary_format` 函数专门修正格式，说明这个问题很常见

**数据来源**：`behavior.md` 文件内容或日志中的输出

**实现方式**：
```python
has_correct = bool(re.search(r'^\d+\. ', content, re.MULTILINE))
has_wrong = bool(re.search(r'^#{1,3}\s+', content, re.MULTILINE))
compliance = 1.0 if (has_correct and not has_wrong) else 0.0
```

---

### 1.2 幻觉率 [P1] ⚠️ **待讨论**

> **待讨论原因**：幻觉检测方法论复杂，当前简单的关键词匹配和 LLM 辅助评分都有局限性。
> 需要更系统的方案（如基于事实核查的方法、多模型交叉验证等）。

**评估目的**：
- 防止 LLM 编造不存在的活动或事件
- 确保总结忠实于原始数据

**挑战**：
- 总结本身会进行概括和抽象，不是简单的文本复制
- 关键词匹配容易误判（如 "Chrome" → "浏览器"）
- LLM 辅助评分的准确性本身也需要验证

**后续讨论方向**：
1. 是否需要构建标注数据集进行监督学习
2. 是否结合检索增强（RAG）进行事实核查
3. 是否通过多个 LLM 交叉验证提高准确性

---

### 1.3 输出完整性 [P0]

**评估目的**：
- 确保每个节点的输出符合 prompt 模板要求
- 发现输出格式不完整或字段缺失的问题

**说明**：
- dreaming workflow 的每个节点都有固定的输出模板
- 例如：`summary_activities` 要求输出 "1. 今日概览" "2. 电脑使用总览" "3. 高频使用时段"
- 需要针对每个节点的 prompt 模板定义必需字段

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 字段完整率 | `包含所有必需字段 / 总调用` | > 95% | **<95%** 说明模型经常遗漏字段 |
| 字段缺失率（按字段） | 统计每个字段的缺失次数 | < 5% | 某个字段缺失率高说明该字段定义不清晰 |

**问题诊断**：
- ✅ **特定字段缺失率高**：在 prompt 中强调该字段，提供示例
- ✅ **整体完整率低**：检查 prompt 模板是否清晰，考虑增加输出格式示例

**实现方式**：

**针对不同节点定义模板**：
```python
# 定义每个节点的必需字段
NODE_TEMPLATES = {
    "summary_activities": {
        "required_sections": [
            "1. 今日概览",
            "2. 电脑使用总览", 
            "3. 高频使用时段"
        ]
    },
    "summary_moods": {
        "required_sections": [
            "心情总体趋势",
            "主要心情事件"
        ]
    },
    "extract_from_chat_messages": {
        "check_type": "not_none",  # 只检查是否返回了内容
    },
}

def check_completeness(node_name: str, output: str) -> dict:
    """检查输出完整性"""
    template = NODE_TEMPLATES.get(node_name)
    if not template:
        return {"completeness": 1.0, "missing_fields": []}
    
    required_sections = template.get("required_sections", [])
    missing = [s for s in required_sections if s not in output]
    
    return {
        "completeness": 1 - len(missing) / len(required_sections),
        "missing_fields": missing,
    }
```

**数据来源**：
- 从 `llm_call_logger` 读取各节点的输出
- 按 `node_name` 分组统计

**示例**：
```python
# summary_activities 节点
dataset = llm_call_logger.export_by_prompt("schedule", "ACTIVITY_SUMMARY")

missing_stats = {}
for record in dataset:
    output = record["output"]["content"]
    result = check_completeness("summary_activities", output)
    
    for field in result["missing_fields"]:
        missing_stats[field] = missing_stats.get(field, 0) + 1

# 报告
print(f"总调用: {len(dataset)}")
print(f"字段缺失统计:")
for field, count in missing_stats.items():
    rate = count / len(dataset)
    print(f"  {field}: {count}次 ({rate:.1%})")
```

---

### 1.4 工具调用成功率 [P0]（仅 update_memory）

**评估目的**：
- 监控工具调用的稳定性
- 发现工具接口或参数问题

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 工具调用成功率 | `成功调用数 / 总调用数` | > 95% | **<95%** 说明工具接口不稳定或参数经常错误 |
| 失败工具分布 | 统计每个工具的失败次数 | - | 某个工具失败特别多说明该工具有问题 |
| 参数错误率 | `参数错误数 / 失败数` | < 50% | **>50%** 说明 LLM 经常构造错误参数 |

**问题诊断**：
- ✅ **某个工具失败率高**：检查该工具的实现，可能是接口不稳定或参数校验过严
- ✅ **参数错误率高**：在 prompt 中更清晰地说明参数格式，提供示例
- ✅ **所有工具都失败**：检查工具调用框架是否有问题

**数据来源**：`llm_call_logger` → `tool_call_chain` 字段

**实现方式**：
```python
tool_chain = record.get("tool_call_chain", [])
failures = [t for t in tool_chain if t.get("status") == "error"]
failure_rate = len(failures) / len(tool_chain) if tool_chain else 0

# 失败工具分布
failure_by_tool = {}
for tool in failures:
    name = tool.get("name")
    failure_by_tool[name] = failure_by_tool.get(name, 0) + 1
```

---

## 业务场景 2：screenshot_analysis workflow

**涉及任务**：
- `analyze_chunk_screenshots`：分析截图语义
- `_behavior_summary`：总结行为并生成 title

---

### 2.1 图片识别准确率 [P1]

**评估目的**：
- 检查 LLM 是否正确识别了截图内容
- 发现视觉理解的薄弱点（如特定 app 识别错误）

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 行为准确率 | 人工评分，准确识别 / 总样本 | > 80% | **<80%** 说明视觉识别能力不足 |
| 误识率 | 识别错误 / 总样本 | < 10% | **>10%** 说明模型经常误判 |
| 漏识率 | 遗漏关键信息 / 总样本 | < 10% | **>10%** 说明模型经常遗漏信息 |
| LLM 辅助评分 | 另一个 LLM 评分（1-5） | > 4.0 | **<4.0** 说明识别质量不稳定 |

**问题诊断**：
- ✅ **特定 app 识别差**：在 prompt 中增加该 app 的描述或示例
- ✅ **遗漏关键信息**：在 prompt 中强调 "详细描述所有可见的活动"
- ✅ **误判频繁**：检查是否是图片质量问题（模糊、截取不全）

**实现方式**：
1. **人工标注**：随机抽取 10-20 张截图，人工标注"真实行为"
2. **对比评分**：对比 LLM 输出与人工标注
3. **LLM 辅助**（可选）：让另一个 LLM 看截图+总结，评分准确性

---

### 2.2 格式正确性 [P0]

**评估目的**：
- 确保 `_behavior_summary` 输出可被正确解析
- 发现 JSON 格式问题

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| JSON 有效率 | `有效 JSON / 总调用` | > 95% | **<95%** 说明 prompt 格式说明不清晰 |
| 字段完整率 | `包含 title+summary / 总调用` | > 98% | **<98%** 说明模型经常遗漏字段 |

**问题诊断**：
- ✅ **JSON 无效**：在 prompt 中强调 "只输出 JSON，格式为 {\"title\": \"...\", \"behavior_summary\": \"...\"}"
- ✅ **字段缺失**：在 prompt 中列出必需字段，强调 "必须同时包含 title 和 behavior_summary"

**实现方式**：参考"通用场景 4 - 格式正确性"

---

### 2.3 字数控制 [P0]

**评估目的**：
- 确保输出符合长度限制
- 控制 token 成本
- 确保下游展示不会过长

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| title 超限率 | `len(title)>30 的次数 / 总次数` | < 5% | **>5%** 说明模型经常输出过长 title |
| summary 超限率 | `len(summary)>150 的次数 / 总次数` | < 5% | **>5%** 说明模型不遵守字数限制 |
| title 平均长度 | `Σ len(title) / N` | 15-25 字 | **>25** 说明 prompt 需要强调简洁性 |
| summary 平均长度 | `Σ len(summary) / N` | 80-120 字 | **>120** 说明 prompt 需要强调简洁性 |

**问题诊断**：
- ✅ **title 过长**：在 prompt 中强调 "title 不超过 30 字，要极致压缩"
- ✅ **summary 过长**：在 prompt 中强调 "summary 不超过 150 字"
- ✅ **平均长度偏高**：调整 prompt 措辞，如 "用最简洁的语言概括"

**实现方式**：
```python
title_len = len(data["title"])
summary_len = len(data["behavior_summary"])
violations = []
if title_len > 30:
    violations.append(("title", title_len))
if summary_len > 150:
    violations.append(("summary", summary_len))
```

---

### 2.4 ignore 过滤准确率 [P1]

**评估目的**：
- 验证 `screen_analysis_ignore` 配置是否合理
- 发现误忽略或误保留的情况

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 忽略率 | `被忽略的截图 / 总截图` | 20-40% | **<20%** 说明过滤不够，**>40%** 说明过滤过度 |
| 误忽略率 | `不该忽略但被忽略 / 总忽略` | < 10% | **>10%** 说明过滤规则有问题 |
| 误保留率 | `该忽略但未忽略 / 总保留` | < 10% | **>10%** 说明过滤规则不够严格 |

**问题诊断**：
- ✅ **忽略率过低**：扩展 `screen_analysis_ignore` 列表，增加无意义类别（如系统工具）
- ✅ **忽略率过高**：检查是否误把有用的类别加入了忽略列表
- ✅ **误忽略频繁**：调整类别定义，或改进分类准确率

**实现方式**：
1. 从日志中提取被忽略的截图（`category_info["is_ignored"] == True`）
2. 人工抽样验证 10-20 张，标注"是否应该忽略"
3. 计算误判率

---

## 业务场景 3：diary_summary workflow

**涉及任务**：
- `ai_diary_summary`：总结日记内容

---

### 3.1 摘要质量 [P1]

**评估目的**：
- 确保日记总结忠实于原文
- 发现过度简化或遗漏关键信息的问题

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 忠实度评分 | LLM 辅助评分（1-5） | > 4.0 | **<4.0** 说明总结质量不稳定 |
| 信息保留率 | 关键信息出现在总结中 / 原文关键信息 | > 80% | **<80%** 说明总结遗漏了重要内容 |
| 过度简化率 | 评分<3 的次数 / 总次数 | < 10% | **>10%** 说明模型经常过度简化 |

**问题诊断**：
- ✅ **忠实度低**：在 prompt 中强调 "保留关键细节，不要过度简化"
- ✅ **信息保留率低**：检查是否是日记过长导致，考虑增加 upper_limit
- ✅ **过度简化**：调整 prompt，如 "详细总结重要事件和情感变化"

**实现方式**：
```python
judge_prompt = f"""
判断"总结"是否忠实于"日记原文"。
评分 1-5：
1 = 严重扭曲或遗漏核心内容
3 = 基本准确但遗漏部分细节
5 = 完全忠实，保留了所有关键信息

## 日记原文
{diary_content}

## 总结
{summary}

只输出分数（1/2/3/4/5）。
"""
```

---

### 3.2 字数控制 [P0]

**评估目的**：
- 确保总结长度合理（不过长也不过短）
- 验证 `upper_limit` 计算逻辑是否合理

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 超限率 | `len(summary)>upper_limit 的次数 / 总次数` | < 5% | **>5%** 说明模型不遵守字数限制 |
| 压缩率 | `len(summary) / len(diary)` | 0.2-0.4 | **>0.4** 说明压缩不够，**<0.2** 可能过度简化 |
| 平均长度 | `Σ len(summary) / N` | 150-300 字 | - |

**问题诊断**：
- ✅ **频繁超限**：在 prompt 中强调字数限制，如 "总结字数不超过 {upper_limit} 字"
- ✅ **压缩率异常**：调整 `upper_limit` 计算公式（当前是 `min(max(len*0.3, 100), 500)`）
- ✅ **平均长度过短**：检查是否是 `upper_limit` 设置过低

**实现方式**：
```python
actual_len = len(summary)
diary_len = len(diary)
upper_limit = int(min(max(diary_len * 0.3, 100), 500))
violation = actual_len > upper_limit
compression_ratio = actual_len / diary_len if diary_len > 0 else 0
```

---

### 3.3 标签整合 [P0]

**评估目的**：
- 确保用户输入的标签被正确体现在总结中
- 验证标签传递逻辑是否正确

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| mood 整合率 | `包含 mood 的次数 / 输入了 mood 的次数` | > 95% | **<95%** 说明标签传递有问题 |
| importance 整合率 | `包含 importance 的次数 / 输入了 importance 的次数` | > 95% | **<95%** 说明标签传递有问题 |
| custom_label 整合率 | `包含 custom_label 的次数 / 输入了 custom_label 的次数` | > 95% | **<95%** 说明标签传递有问题 |

**问题诊断**：
- ✅ **标签缺失**：检查 `label_to_save` 是否正确构造并写入 behavior.md
- ✅ **标签格式错误**：检查是否是格式问题导致下游解析失败

**实现方式**：
```python
# 检查 behavior.md 中是否包含标签
if mood and mood not in summary:
    missing_labels.append("mood")
if importance and importance not in summary:
    missing_labels.append("importance")
if custom_label:
    for label in custom_label:
        if label not in summary:
            missing_labels.append(f"custom_label:{label}")
```

---

## 业务场景 4：classify workflow

**涉及任务**：
- `get_app_description`：获取 app 描述
- `single_classify`：单用途 app 分类
- `multi_classify_short`：短时长多用途分类
- `multi_classify_long`：长时长多用途分类
- `get_titles`：获取 title 分析

---

### 4.1 分类准确率 [P1]

**评估目的**：
- 评估分类器的核心能力
- 对比不同分类策略（classify_simple vs classify_graph）
- 发现需要优化的类别

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 总体准确率 | `正确分类 / 总样本` | > 80% | **<80%** 说明分类能力不足 |
| category 准确率 | `category 正确 / 总样本` | > 85% | **<85%** 说明一级分类有问题 |
| sub_category 准确率 | `sub_category 正确 / 总样本` | > 75% | **<75%** 说明二级分类有问题 |
| 混淆率 Top 3 | 统计最容易混淆的类别对 | - | 针对性优化这些类别的定义 |

**问题诊断**：
- ✅ **总体准确率低**：检查类别定义是否清晰，考虑增加示例
- ✅ **某些类别准确率特别低**：重新定义该类别，或合并到其他类别
- ✅ **混淆严重**：在 prompt 中强调两个类别的区别

**实现方式**：
1. **构建标注数据集**：人工标注 50-100 个样本（app, title, category, sub_category）
2. **运行分类器**：对比预测结果与人工标注
3. **计算准确率**：
```python
correct = sum(1 for pred, true in zip(predictions, labels) if pred == true)
accuracy = correct / len(labels)
```
4. **生成混淆矩阵**：
```python
from sklearn.metrics import confusion_matrix
cm = confusion_matrix(true_labels, predictions)
```

---

### 4.2 link_to_goal 准确率 [P1]

**评估目的**：
- 验证模型是否正确识别与用户目标相关的活动
- 确保用户目标追踪功能有效

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| link_to_goal 准确率 | `link_to_goal 正确 / 总样本` | > 85% | **<85%** 说明目标关联能力不足 |
| 误判率（假阳性） | `错误关联 / 总预测关联` | < 15% | **>15%** 说明关联过于宽松 |
| 漏判率（假阴性） | `遗漏关联 / 总实际关联` | < 15% | **>15%** 说明关联过于严格 |

**问题诊断**：
- ✅ **误判率高**：在 prompt 中强调 "只有高度相关的活动才关联目标"
- ✅ **漏判率高**：在 prompt 中放宽关联条件，增加目标描述的详细程度
- ✅ **准确率低**：检查目标定义是否清晰，考虑重新表述目标

**实现方式**：
1. **构建标注数据集**：人工标注 30-50 个样本的"是否与 goal 相关"
2. **运行分类器**：检查 link_to_goal 字段
3. **计算准确率**：
```python
correct = sum(1 for pred, true in zip(predictions, labels) 
              if (pred is not None) == (true is not None))
accuracy = correct / len(labels)
```

---

### 4.3 null 分类率 [P0]

**评估目的**：
- 监控无法分类的比例
- 发现类别体系的覆盖度不足问题

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| category null 率 | `category==null / 总样本` | < 10% | **>10%** 说明类别体系覆盖度不足 |
| sub_category null 率 | `sub_category==null / 有category的样本` | < 20% | **>20%** 说明二级分类粒度不够 |
| null 率趋势 | 对比不同时间段的 null 率 | 下降 | **上升**说明新出现的 app/行为无法分类 |

**问题诊断**：
- ✅ **category null 率高**：扩展类别体系，增加新类别
- ✅ **sub_category null 率高**：细化现有类别的子类别
- ✅ **null 率上升**：定期审查新出现的 null 案例，补充类别

**实现方式**：
```python
null_category = sum(1 for r in results if r["category"] is None)
null_rate = null_category / len(results)

# 统计哪些 app/title 经常无法分类
null_apps = [r["app"] for r in results if r["category"] is None]
from collections import Counter
null_app_freq = Counter(null_apps).most_common(10)
```

---

### 4.4 描述质量 [P1]（get_app_description）

**评估目的**：
- 确保 app 描述准确且简洁
- 监控描述获取的成功率

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 字数合规率 | `len(desc)≤50 的次数 / 总次数` | > 90% | **<90%** 说明模型不遵守字数限制 |
| 描述缺失率 | `desc==None 的次数 / 总次数` | < 5% | **>5%** 说明获取失败率高 |
| 重试率 | `重试次数 / 总次数` | < 20% | **>20%** 说明首次获取成功率低 |
| 平均字数 | `Σ len(desc) / N` | 30-45 字 | **>45** 说明描述过详细 |

**问题诊断**：
- ✅ **字数超限**：在 prompt 中强调 "50 字以内"
- ✅ **描述缺失率高**：检查是否是网络问题或 API 限流
- ✅ **重试率高**：优化 prompt，让首次成功率更高

**实现方式**：
```python
desc_len = len(app_info.description)
violation = desc_len > 50

# 统计重试次数（从日志中提取）
retry_count = record.get("retry_count", 0)
```

---

### 4.5 分类器对比 [P1]（classify_simple vs classify_graph）

**评估目的**：
- 对比两种分类策略的性能
- 为模型选型提供依据

**评估指标**：

| 指标 | classify_simple | classify_graph | 说明 |
|------|----------------|---------------|------|
| 准确率 | - | - | 哪个更准确？ |
| 平均 token 消耗 | - | - | 哪个更省 token？ |
| 平均延迟 | - | - | 哪个更快？ |
| null 率 | - | - | 哪个覆盖度更好？ |

**问题诊断**：
- ✅ **simple 准确率低但快**：简单场景用 simple，复杂场景用 graph
- ✅ **graph 准确率高但慢**：优化 graph 的并发策略，减少串行步骤
- ✅ **两者差异不大**：优先用 simple（更简单）

**实现方式**：
1. 在相同的测试集上分别运行两种分类器
2. 对比各项指标
3. 生成对比报告

---

## 业务场景 5：chat agent

**涉及任务**：
- `ChatBot.chat`：聊天对话

**⚠️ 注意**：当前 chat agent 刚刚集成日志记录，功能说明（客服）部分还未实现，部分评估指标暂时无法实施

---

### 5.1 工具路由准确率 [P1]

**评估目的**：
- 验证 agent 是否能根据用户意图选择正确的工具
- 发现工具选择的混淆情况

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 路由准确率 | `正确工具 / 总工具调用` | > 90% | **<90%** 说明工具路由能力不足 |
| 混淆矩阵 | 统计工具间的误选情况 | - | 针对性优化混淆严重的工具对 |
| 未选工具率 | `应该调用但未调用 / 总样本` | < 10% | **>10%** 说明工具触发条件不清晰 |

**问题诊断**：
- ✅ **路由准确率低**：在 system prompt 中更清晰地描述每个工具的用途
- ✅ **特定工具经常误选**：调整该工具的描述，突出与其他工具的区别
- ✅ **未选工具率高**：降低工具触发条件，或在 prompt 中增加示例

**实现方式**：
1. **构建测试用例**：20 个典型用户请求，标注"正确工具"
```python
test_cases = [
    {"query": "最近我都做了什么", "expected_tool": "query_recent_activities"},
    {"query": "我今天心情怎么样", "expected_tool": "query_user_mood"},
    {"query": "帮我记录一下心情很好", "expected_tool": "record_mood"},
    # ...
]
```
2. **运行 chat**：收集 tool_call_chain
3. **计算准确率**：
```python
correct = sum(1 for case in test_cases 
              if case["expected_tool"] in [t["name"] for t in tool_chain])
accuracy = correct / len(test_cases)
```

---

### 5.2 参数提取正确率 [P1]

**评估目的**：
- 验证 agent 是否能正确构造工具参数
- 发现参数提取的常见错误

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 参数完整率 | `包含所有必需参数 / 总工具调用` | > 95% | **<95%** 说明参数提取不稳定 |
| 参数正确率 | `参数值正确 / 总参数` | > 90% | **<90%** 说明参数理解有偏差 |
| 时间解析准确率 | `时间参数正确 / 总时间参数` | > 85% | **<85%** 说明时间理解能力弱 |

**问题诊断**：
- ✅ **参数缺失**：在工具描述中强调必需参数，提供示例
- ✅ **时间解析错误**：在 prompt 中提供时间格式示例（"YYYY-MM-DD HH:MM:SS"）
- ✅ **参数值错误**：检查是否是工具描述不清晰

**实现方式**：
```python
# 从 tool_call_chain 中提取参数
tool = tool_chain[0]
params = tool.get("arguments", {})

# 检查必需参数
required_params = ["start_time", "end_time"]
missing = [p for p in required_params if p not in params]

# 检查参数值（需要预定义期望值）
expected = {"start_time": "2026-06-23 00:00:00", "end_time": "2026-06-30 23:59:59"}
param_correct = all(params.get(k) == v for k, v in expected.items())
```

---

### 5.3 工具调用成功率 [P0]

**评估目的**：
- 监控工具调用的稳定性
- 发现工具接口问题

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 工具调用成功率 | `成功调用 / 总调用` | > 95% | **<95%** 说明工具接口不稳定 |
| 失败工具分布 | 统计每个工具的失败次数 | - | 某个工具失败特别多说明该工具有问题 |
| 参数错误占比 | `参数错误 / 总失败` | < 50% | **>50%** 说明参数构造有问题 |

**问题诊断**：参考"业务场景 1.4 - 工具调用成功率"

---

### 5.4 幻觉率 [P1]（客服场景）

**评估目的**：
- 验证 agent 是否编造了不存在的功能
- 确保客服回答的准确性

**⚠️ 前提**：需要先实现功能说明 skill

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| FAQ 准确率 | `正确回答 / 总 FAQ` | > 90% | **<90%** 说明知识库不完善或理解有误 |
| 编造率 | `编造答案 / 总回答` | < 5% | **>5%** 说明 agent 经常编造内容 |
| 一致性 | 同一问题多次回答的一致性 | > 95% | **<95%** 说明回答不稳定 |

**问题诊断**：
- ✅ **编造率高**：在 system prompt 中强调 "只回答功能说明中的内容，不确定时说'我不知道'"
- ✅ **FAQ 准确率低**：补充功能说明，或优化知识检索
- ✅ **一致性低**：固定 temperature=0，减少随机性

**实现方式**：
1. **构建 FAQ 测试集**：10 个有答案的问题 + 5 个超纲问题
```python
faq_tests = [
    {"question": "如何记录心情", "answer": "说'我今天心情很好'即可"},
    {"question": "如何导出数据", "answer": "在设置页面点击'导出数据'"},
    {"question": "支持哪些语言", "answer": "当前只支持中文"},  # 超纲问题
    # ...
]
```
2. **运行 chat**：收集回答
3. **LLM 辅助评分**或人工对比

---

### 5.5 知识边界感知 [P1]

**评估目的**：
- 验证 agent 是否知道自己的能力边界
- 确保不会误导用户

**评估指标**：

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 拒绝准确率 | `正确拒绝 / 总超纲问题` | > 90% | **<90%** 说明边界感知不足 |
| 误拒率 | `错误拒绝 / 总正常问题` | < 10% | **>10%** 说明拒绝过于保守 |

**问题诊断**：
- ✅ **拒绝准确率低**：在 system prompt 中列出能力范围，强调"超出范围时说'我不知道'"
- ✅ **误拒率高**：放宽拒绝条件，或优化知识检索

**实现方式**：
1. **构建测试集**：5 个超纲问题 + 5 个正常问题
```python
boundary_tests = [
    {"question": "怎么越狱 iPhone", "should_refuse": True},
    {"question": "如何破解密码", "should_refuse": True},
    {"question": "最近我都做了什么", "should_refuse": False},
    # ...
]
```
2. **运行 chat**：检查回答
3. **判断是否拒绝**：检查是否包含 "我不知道"、"超出我的能力" 等关键词

---

## 跨场景评估：工具调用统计

**评估视角**：从**工具本身**的角度统计，而非场景角度

**核心价值**：
- 区分**工具问题** vs **场景使用问题**
- 识别高频失败的工具（工具本身有 bug）
- 监控工具接口的稳定性

---

### 评估目的

通过跨所有场景的统计，识别：
1. 哪些工具本身不稳定（在所有场景下成功率都低）
2. 哪些工具使用频率最高（需要重点优化）
3. 主要的失败原因分布

### 评估指标

| 指标 | 计算方式 | 正常范围 | 异常情况说明 |
|------|----------|----------|-------------|
| 工具总成功率 | `总成功调用 / 总调用次数` | > 95% | **<95%** 说明工具体系整体不稳定 |
| 单个工具成功率 | `某工具成功 / 某工具总调用` | > 90% | **<90%** 说明该工具有问题 |
| 调用频率 Top 10 | 统计调用次数最多的工具 | - | 高频工具需要重点优化 |
| 失败原因排行 | 统计各错误信息出现次数 | - | 识别主要问题点 |

### 双视角对比

| 维度 | 工具视角（本节） | 场景视角（1.4/5.3） |
|------|----------------|---------------------|
| **统计范围** | 跨所有场景 | 单个场景内 |
| **问题定位** | 工具本身有问题 | 场景使用方式有问题 |
| **优化方向** | 修复工具接口/实现 | 优化 prompt/参数构造 |
| **示例** | `read_file` 在所有场景下成功率都低 → 工具权限配置有问题 | `read_file` 在 chat 场景成功率低，但 dreaming 场景正常 → chat 的文件路径构造有问题 |

### 数据来源

从所有记录的 `evaluation.tool_call_chain` 中提取：

```python
# 遍历所有日志记录
for record in all_records:
    evaluation = record.get("evaluation", {})
    tool_chain = evaluation.get("tool_call_chain", [])
    
    for tool_call in tool_chain:
        tool_name = tool_call.get("name")
        status = tool_call.get("status")  # "success" 或 "error"
        result = tool_call.get("result")  # 工具返回的字符串
        
        # 从 result 中提取错误信息
        if status == "error" or (result and result.startswith("Error: ")):
            error_message = result.replace("Error: ", "") if result else "未知错误"
```

### 错误信息提取规则

当前工具的错误返回格式统一为：`"Error: <错误描述>"`

**常见错误信息示例**（从代码中提取）：

| 错误信息 | 来源工具 | 原因 |
|---------|---------|------|
| `文件 xxx 不存在` | `read_file` | 文件路径错误或文件被删除 |
| `没有权限访问该文件: xxx` | 文件工具 | 文件不在允许的工作目录内 |
| `文件编码错误: xxx` | `read_file`, `edit_file` | 文件编码不是 UTF-8 |
| `没有权限写入文件: xxx` | `write_file`, `edit_file` | 文件权限问题 |
| `未找到要替换的内容` | `edit_file` | old_content 不匹配 |
| `目录 xxx 不存在` | `file_tree_py` | 目录路径错误 |
| `路径 xxx 不是目录` | `file_tree_py` | 传入的是文件而非目录 |
| `没有权限访问目录: xxx` | `file_tree_py`, `search_file_py` | 目录权限问题 |
| `搜索超时（xx秒）` | `search_file_py`, `search_string_py` | 搜索范围过大 |
| `无效的正则表达式: xxx` | `search_string_py` | 正则语法错误 |
| `文件 xxx 不是可搜索的文本文件类型` | `search_string_py` | 文件后缀不在白名单中 |
| `参数错误: xxx` | 所有工具 | 参数校验失败 |
| `查询失败: xxx` | 系统工具 | 数据库查询错误 |
| `创建失败: xxx` | 系统工具 | 数据库写入错误 |

### 统计实现

```python
class ToolCallAnalyzer:
    def analyze_all_tools(self, start_date=None, end_date=None) -> dict:
        """分析所有工具的调用情况（跨场景）"""
        all_records = self._load_all_records(start_date, end_date)
        
        tool_stats = {}
        
        for record in all_records:
            evaluation = record.get("evaluation", {})
            tool_chain = evaluation.get("tool_call_chain", [])
            
            for tool_call in tool_chain:
                tool_name = tool_call.get("name")
                status = tool_call.get("status")
                result = tool_call.get("result", "")
                
                # 初始化工具统计
                if tool_name not in tool_stats:
                    tool_stats[tool_name] = {
                        "total": 0,
                        "success": 0,
                        "failed": 0,
                        "error_messages": {}  # 错误信息 -> 出现次数
                    }
                
                tool_stats[tool_name]["total"] += 1
                
                # 判断成功/失败
                if status == "success" and not result.startswith("Error: "):
                    tool_stats[tool_name]["success"] += 1
                else:
                    tool_stats[tool_name]["failed"] += 1
                    
                    # 提取错误信息
                    error_msg = result.replace("Error: ", "") if result.startswith("Error: ") else result
                    if error_msg:
                        tool_stats[tool_name]["error_messages"][error_msg] = \
                            tool_stats[tool_name]["error_messages"].get(error_msg, 0) + 1
        
        # 计算成功率
        for tool_name, stats in tool_stats.items():
            stats["success_rate"] = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        
        return tool_stats
```

### 报告示例

```
=== 工具调用统计报告 ===
时间范围: 2026-06-01 ~ 2026-06-30
总调用次数: 1523
总成功率: 96.3%

== 调用频率 Top 10 ==
1. query_user_mood             456 次 (成功率 98.2%) ✅
2. query_user_activity_summary 387 次 (成功率 97.4%) ✅
3. read_file                   234 次 (成功率 89.3%) ⚠️
4. create_or_update_user_behavior_note 198 次 (成功率 91.4%) ⚠️
5. query_user_activity_log     156 次 (成功率 99.4%) ✅
6. write_file                   92 次 (成功率 95.7%) ✅

== 问题工具（成功率 <90%）==
- read_file: 89.3%
  失败原因 Top 3:
    1. "没有权限访问该文件: xxx" - 15 次
    2. "文件 xxx 不存在" - 8 次
    3. "文件编码错误: xxx" - 2 次
  建议: 检查 allowed_dir_path 配置是否过严

- edit_file: 87.5%
  失败原因 Top 3:
    1. "未找到要替换的内容" - 12 次
    2. "没有权限写入文件: xxx" - 5 次
  建议: 在 prompt 中强调 old_content 必须精确匹配

== 全局失败原因排行 ==
1. "没有权限访问该文件: xxx" - 28 次
2. "文件 xxx 不存在" - 15 次
3. "未找到要替换的内容" - 12 次
4. "搜索超时（30秒）" - 7 次
5. "参数错误: xxx" - 6 次
```

### 问题诊断

| 问题特征 | 可能原因 | 优化方向 |
|---------|---------|---------|
| **某工具在所有场景下成功率都低** | 工具本身有 bug 或配置问题 | 修复工具实现或调整配置 |
| **"没有权限访问"高频出现** | `allowed_dir_path` 配置过严 | 扩展允许的工作目录 |
| **"未找到要替换的内容"高频** | LLM 经常构造错误的 old_content | 优化 prompt，强调精确匹配 |
| **"搜索超时"高频** | 搜索范围过大 | 增加超时配置或限制搜索深度 |
| **某工具调用频率极高** | 该工具是核心功能 | 优先优化该工具的性能和稳定性 |

### 实现位置

建议创建独立的统计模块：`lifeprism/llm/utils/tool_call_analyzer.py`

或集成到 `AgentEvaluator` 中作为一个独立方法：
```python
class AgentEvaluator:
    # ... 其他方法 ...
    
    def analyze_tool_calls_global(self, start_date=None, end_date=None) -> dict:
        """全局工具调用统计（跨场景）"""
        pass
```

### 第一阶段（本周，P0 任务）
1. 实现 `AgentEvaluator` 类，支持通用指标计算
2. 为每个业务场景实现自动化指标
3. 生成评估报告（markdown 格式）

### 第二阶段（两周内，P1 任务）
1. 构建人工标注工具
2. 标注种子数据集（分类 50 个、截图 10-20 张、FAQ 10 个）
3. 实现 LLM 辅助评分
4. 完善评估报告

### 第三阶段（长期，P2 任务）
1. 建立持续评估流水线（每次 prompt 更新后自动跑评估）
2. 构建评估看板（可视化展示各项指标）
3. 建立模型对比体系（不同模型的性能对比）

---

## 待讨论问题

1. **Token 效率的成本计算**：是否需要按实际使用的模型计价？
2. **延迟统计**：是否需要修改 llm_call_logger 记录 duration？
3. **评估频率**：是每次 prompt 更新后手动跑，还是定时自动跑？
4. **评估报告格式**：markdown 文件还是 HTML 可视化？
5. **标注工具**：是否需要开发专门的标注界面？
