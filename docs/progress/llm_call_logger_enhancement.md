# llm_call_logger 增强方案

> 创建时间：2026-06-30  
> 原则：**零业务侵入**，只增加评估所需字段，不修改现有业务逻辑

---

## 设计原则

### ✅ **保持简单**
- 不修改 `TokenType`（避免大面积修改业务代码）
- 不修改现有字段的含义
- 只在 `llm_call_logger` 层增加字段

### ✅ **评估与业务分离**
- 评估是辅助功能，不应该反向影响业务逻辑
- 所有新增字段都是可选的，不影响现有调用
- 即使不填新字段，现有功能也能正常工作

### ✅ **渐进式扩展**
- 优先增加容易实现的字段（P0）
- 复杂字段后续再加（P1/P2）
- 保持向后兼容

---

## 当前 llm_call_logger 字段分析

### 已有字段（当前实现）

```python
record = {
    "id": str(uuid.uuid4()),
    "timestamp": datetime.now().isoformat(),
    "caller": caller,  # 调用位置
    "message_type": inbound_msg.type,
    "session_id": inbound_msg.session_id,
    "channel": inbound_msg.channel,
    "workflow_id": workflow_id,  # 可选
    "prompt": {
        "module": prompt_module,  # 可选
        "name": prompt_name,      # 可选
        "version": prompt_version,  # 可选
        "content": system_prompt_content
    },
    "input": {
        "content_type": "multimodal" if image_filenames else "text",
        "text": text_content,
        "images": image_filenames
    },
    "output": {
        "content": output_content
    },
    "tool_call_chain": tool_call_chain,  # 可选
    "model": model,  # 可选
    "tokens": tokens,  # 可选
    "error": None,  # ⚠️ 当前固定为 None
    "score": score,  # 可选
}
```

### 问题点

| 字段 | 问题 | 影响 |
|------|------|------|
| `error` | **固定为 None**，从未真正记录错误 | 无法统计错误率 |
| `tokens` | 可选，依赖 `outbound_msg.response.usage` | 部分调用可能没有 tokens |
| `timestamp` | 只记录一个时间点 | 无法计算延迟 |
| `model` | 可选，未传时从 settings 获取 | 可能不准确 |

---

## 新增字段方案

### Phase 1：立即可加（P0）

这些字段**不需要修改业务代码**，只需要在 `llm_call_logger.log_call()` 中计算或提取。

#### 1.1 错误信息（修复现有字段）

```python
"error": {
    "has_error": False,  # 是否有错误
    "error_type": None,  # 错误类型：timeout/api_error/param_error/model_refusal
    "error_message": None,  # 错误信息
}
```

**实现方式**：
```python
# 在 log_call 中判断
error_info = {
    "has_error": False,
    "error_type": None,
    "error_message": None,
}

if outbound_msg is None or outbound_msg.response is None:
    error_info["has_error"] = True
    error_info["error_type"] = "api_error"
    error_info["error_message"] = "未返回响应"
elif outbound_msg.response.content is None or outbound_msg.response.content == "":
    error_info["has_error"] = True
    error_info["error_type"] = "empty_response"
    error_info["error_message"] = "返回内容为空"

record["error"] = error_info
```

**数据来源**：
- 检查 `outbound_msg` 是否为 None
- 检查 `outbound_msg.response` 是否为 None
- 检查 `outbound_msg.response.content` 是否为空

---

#### 1.2 延迟（改造方案调整）

**问题分析**：
- `bus.send()` 包含时间窗口，延迟可能包含等待时间
- 不能在 `send()` 调用之前就开始计时（不准确）
- 需要在 `bus.send()` 内部记录开始和结束时间

**改造方案**：
1. 在 `bus.send()` 内部记录 `start_time`（第一次实际调用 LLM 时）
2. 在 `bus.send()` 返回前记录 `end_time`
3. 通过 `outbound_msg` 传递 timing 信息给 `llm_call_logger`

**实现方式**：

**方案 A：通过 outbound_msg.extra 传递**（推荐）
```python
# 在 bus.send() 中
start_time = datetime.now()
# ... 调用 LLM ...
end_time = datetime.now()

outbound_msg.extra["timing"] = {
    "start_time": start_time.isoformat(),
    "end_time": end_time.isoformat(),
    "duration_ms": int((end_time - start_time).total_seconds() * 1000),
}

# 在 log_call 中提取
timing = None
if outbound_msg and outbound_msg.extra:
    timing = outbound_msg.extra.get("timing")
record["timing"] = timing
```

**方案 B：新增 evaluation 字段统一管理**（见 1.5）

---

#### 1.3 Token 派生指标（修正）

**修正说明**：保留原始 tokens 数据，派生指标单独存放

```python
"tokens": {
    # === 原始数据（保留不变）===
    "prompt_tokens": 1000,
    "completion_tokens": 500,
    "total_tokens": 1500,
},

"token_metrics": {
    # === 派生指标（新增）===
    "io_ratio": 0.5,  # completion / prompt
    "cost_usd": 0.0012,  # 成本估算
}
```

**实现方式**：
```python
# 在 log_call 中计算
if tokens:
    input_tokens = tokens.get("prompt_tokens", 0)
    output_tokens = tokens.get("completion_tokens", 0)
    
    io_ratio = output_tokens / input_tokens if input_tokens > 0 else 0
    cost_usd = self._estimate_cost(input_tokens, output_tokens, model)
    
    record["token_metrics"] = {
        "io_ratio": io_ratio,
        "cost_usd": cost_usd,
    }
else:
    record["token_metrics"] = None
```

---

#### 1.4 节点名称（保持不变）

```python
"node_name": "summary_activities",  # 节点名称
```

**实现方式**：
```python
def log_call(
    self,
    inbound_msg,
    outbound_msg,
    node_name: Optional[str] = None,  # 新增参数
    ...
):
    record["node_name"] = node_name
```

---

#### 1.5 evaluation 字段（新方案，推荐）⭐

**核心思路**：
- 将 `tool_call_chain` 和其他评估相关字段统一放入 `evaluation` 字段
- 所有评估数据由 `bus.send()` 在内部生成，通过 `outbound_msg.extra` 传递
- `llm_call_logger` 只负责提取和存储

```python
"evaluation": {
    # === 延迟信息 ===
    "timing": {
        "start_time": "2026-06-30T12:00:00.123456",
        "end_time": "2026-06-30T12:00:05.678901",
        "duration_ms": 5555,
    },
    
    # === 工具调用链（原 tool_call_chain）===
    "tool_call_chain": [
        {
            "name": "query_user_mood",
            "arguments": {...},
            "status": "success",
            "result": {...},
        }
    ],
    
    # === 可扩展字段 ===
    # 未来可以增加：
    # - retry_count: 重试次数
    # - cache_hit: 是否命中缓存
    # - routing_info: 路由信息
    # ...
}
```

**优点**：
1. **语义清晰**：所有评估相关的字段集中管理
2. **零侵入**：在 `bus.send()` 内部生成，调用方无需修改
3. **易扩展**：未来增加新字段不影响外层结构

**实现方式**：
```python
# 在 bus.send() 中
start_time = datetime.now()
# ... 调用 LLM ...
end_time = datetime.now()

# 构建 evaluation 数据
evaluation = {
    "timing": {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_ms": int((end_time - start_time).total_seconds() * 1000),
    },
    "tool_call_chain": tool_call_chain,  # 原有字段
}

outbound_msg.extra["evaluation"] = evaluation

# 在 log_call 中提取
evaluation = None
if outbound_msg and outbound_msg.extra:
    evaluation = outbound_msg.extra.get("evaluation")
    
# 兼容旧数据：如果没有 evaluation，从 extra 中提取 tool_call_chain
if evaluation is None:
    tool_call_chain = outbound_msg.extra.get("tool_call_chain") if outbound_msg.extra else None
    if tool_call_chain:
        evaluation = {"tool_call_chain": tool_call_chain}

record["evaluation"] = evaluation
```

---

### Phase 2：需要少量修改（P1）

这些字段需要在调用方做小幅修改，但不影响核心业务逻辑。

#### 2.1 输入长度（新增字段）⚠️ **已搁置**

> **搁置原因**：复杂度评分方案过于复杂（需要找输入相近的历史记录对比输出）。
> 后续考虑用机器学习模型（SVM/线性分类器）训练评估器，而非手工规则。

```python
"input_length": {
    "text_chars": 1234,  # 文本字符数
    "image_count": 2,    # 图片数量
}
```

**实现方式**：
```python
# 在 log_call 中计算
input_length = {
    "text_chars": len(text_content),
    "image_count": len(image_filenames),
}
record["input_length"] = input_length
```

---

#### 2.2 输出长度（新增字段）

```python
"output_length": {
    "chars": 567,  # 字符数
}
```

**实现方式**：
```python
# 在 log_call 中计算
if output_content:
    output_length = {"chars": len(output_content)}
else:
    output_length = {"chars": 0}
record["output_length"] = output_length
```

---

#### 2.3 格式检查（新增字段）

**目的**：自动检查输出格式是否正确

```python
"format_check": {
    "is_valid_json": True,  # 是否是有效 JSON
    "has_required_fields": True,  # 是否包含必需字段（需要配置）
    "detected_format": "json",  # 检测到的格式：json/markdown/text
}
```

**实现方式**：
```python
def _check_format(self, output_content, expected_format=None):
    """检查输出格式"""
    result = {
        "is_valid_json": False,
        "has_required_fields": None,
        "detected_format": "text",
    }
    
    # 检查是否是 JSON
    try:
        data = json.loads(extract_json_from_response(output_content))
        result["is_valid_json"] = True
        result["detected_format"] = "json"
        
        # 检查必需字段（如果指定了）
        if expected_format and "required_fields" in expected_format:
            required = expected_format["required_fields"]
            result["has_required_fields"] = all(f in data for f in required)
    except:
        pass
    
    return result

# 在 log_call 中调用
record["format_check"] = self._check_format(output_content)
```

---

### Phase 3：需要模型支持（P2）

这些字段依赖特定模型的能力，暂时可以不实现。

#### 3.1 Reasoning Tokens（新增字段）

**前提**：模型支持输出 reasoning（如 OpenAI o1）

```python
"reasoning_tokens": {
    "reasoning": 1000,  # 思考过程 tokens
    "content": 500,     # 实际输出 tokens
    "reasoning_ratio": 0.67,  # reasoning / (reasoning + content)
}
```

**实现方式**：
```python
# 需要模型在 usage 中返回 reasoning_tokens
if tokens and "reasoning_tokens" in tokens:
    reasoning_tokens = tokens["reasoning_tokens"]
    content_tokens = tokens["completion_tokens"] - reasoning_tokens
    reasoning_ratio = reasoning_tokens / tokens["completion_tokens"]
    
    record["reasoning_tokens"] = {
        "reasoning": reasoning_tokens,
        "content": content_tokens,
        "reasoning_ratio": reasoning_ratio,
    }
else:
    record["reasoning_tokens"] = None
```

---

## 完整的新字段结构

### 方案 A：平铺结构（兼容现有）

```python
record = {
    # === 现有字段 ===
    "id": "...",
    "timestamp": "...",
    "caller": "...",
    "message_type": "...",
    "session_id": "...",
    "channel": "...",
    "workflow_id": "...",
    "prompt": {...},
    "input": {...},
    "output": {...},
    "tool_call_chain": [...],  # 保留（向后兼容）
    "model": "...",
    "tokens": {
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "total_tokens": 1500,
    },
    "score": None,
    
    # === 新增字段（Phase 1，P0）===
    "node_name": "summary_activities",
    
    "error": {
        "has_error": False,
        "error_type": None,
        "error_message": None,
    },
    
    "timing": {
        "start_time": "2026-06-30T12:00:00.123456",
        "end_time": "2026-06-30T12:00:05.678901",
        "duration_ms": 5555,
    },
    
    "token_metrics": {
        "io_ratio": 0.5,
        "cost_usd": 0.0012,
    },
    
    "output_length": {
        "chars": 567,
    },
    
    # === 新增字段（Phase 2，P1）===
    "format_check": {
        "is_valid_json": True,
        "has_required_fields": True,
        "detected_format": "json",
    },
}
```

### 方案 B：evaluation 统一管理（推荐）⭐

```python
record = {
    # === 现有字段 ===
    "id": "...",
    "timestamp": "...",
    "caller": "...",
    "message_type": "...",
    "session_id": "...",
    "channel": "...",
    "workflow_id": "...",
    "prompt": {...},
    "input": {...},
    "output": {...},
    "model": "...",
    "tokens": {
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "total_tokens": 1500,
    },
    "score": None,
    
    # === 新增：统一的评估字段 ===
    "evaluation": {
        # 由 bus.send() 内部生成
        "timing": {
            "start_time": "2026-06-30T12:00:00.123456",
            "end_time": "2026-06-30T12:00:05.678901",
            "duration_ms": 5555,
        },
        "tool_call_chain": [...],  # 原 tool_call_chain 移到这里
        
        # 未来可扩展：
        # "retry_count": 0,
        # "cache_hit": False,
        # "routing_info": {...},
    },
    
    # === 由 llm_call_logger 计算的字段 ===
    "node_name": "summary_activities",
    
    "error": {
        "has_error": False,
        "error_type": None,
        "error_message": None,
    },
    
    "token_metrics": {
        "io_ratio": 0.5,
        "cost_usd": 0.0012,
    },
    
    "output_length": {
        "chars": 567,
    },
    
    "format_check": {
        "is_valid_json": True,
        "has_required_fields": True,
        "detected_format": "json",
    },
}
```

**方案对比**：

| 维度 | 方案 A（平铺） | 方案 B（evaluation） |
|------|---------------|---------------------|
| 兼容性 | ✅ 保留 tool_call_chain | ⚠️ 需要兼容逻辑 |
| 语义清晰 | ⚠️ 字段较散 | ✅ 评估字段集中 |
| 扩展性 | ⚠️ 顶层字段会越来越多 | ✅ 在 evaluation 内扩展 |
| 实施难度 | ✅ 简单 | ⚠️ 需要修改 bus.send() |

**推荐**：方案 B（evaluation 统一管理），长期更清晰

---

## 实施计划

### 方案选择

推荐使用**方案 B（evaluation 统一管理）**，原因：
1. **语义清晰**：所有运行时评估数据集中在 `evaluation` 字段
2. **零侵入调用方**：在 `bus.send()` 内部生成，`llm_call_logger` 只负责提取
3. **易扩展**：未来增加新字段不会让顶层结构越来越乱

### Step 1：修改 `bus.send()` 内部逻辑

**在哪里修改**：`lifeprism/llm/bus/` 相关文件

```python
# 在 bus.send() 中
async def send(self, msg: InboundMessage) -> OutboundMessage:
    # 记录开始时间
    start_time = datetime.now()
    
    # ... 现有逻辑（调用 LLM、工具调用等）...
    
    # 记录结束时间
    end_time = datetime.now()
    
    # 构建 evaluation 数据
    evaluation = {
        "timing": {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_ms": int((end_time - start_time).total_seconds() * 1000),
        },
        "tool_call_chain": tool_call_chain,  # 原有字段
    }
    
    # 通过 outbound_msg.extra 传递
    if outbound_msg.extra is None:
        outbound_msg.extra = {}
    outbound_msg.extra["evaluation"] = evaluation
    
    return outbound_msg
```

### Step 2：修改 `llm_call_logger.log_call()`

```python
def log_call(
    self,
    inbound_msg: Any,
    outbound_msg: Any,
    prompt_module: Optional[str] = None,
    prompt_name: Optional[str] = None,
    prompt_version: Optional[str] = None,
    model: Optional[str] = None,
    workflow_id: Optional[str] = None,
    score: Optional[float] = None,
    system_prompt: Optional[str] = None,
    node_name: Optional[str] = None,  # 新增
) -> Optional[str]:
    """记录一次 LLM 调用"""
    
    # 1. 提取 evaluation 数据（从 outbound_msg.extra）
    evaluation = None
    if outbound_msg and outbound_msg.extra:
        evaluation = outbound_msg.extra.get("evaluation")
        
        # 兼容旧数据：如果没有 evaluation，从 extra 中提取 tool_call_chain
        if evaluation is None:
            tool_call_chain = outbound_msg.extra.get("tool_call_chain")
            if tool_call_chain:
                evaluation = {"tool_call_chain": tool_call_chain}
    
    # 2. 提取错误信息
    error_info = self._extract_error(outbound_msg)
    
    # 3. 计算 token 派生指标
    token_metrics = self._calculate_token_metrics(tokens, model)
    
    # 4. 计算输出长度
    output_length = {"chars": len(output_content) if output_content else 0}
    
    # 5. 格式检查
    format_check = self._check_format(output_content)
    
    # 6. 构建 record
    record = {
        # ... 现有字段 ...
        "evaluation": evaluation,
        "node_name": node_name,
        "error": error_info,
        "token_metrics": token_metrics,
        "output_length": output_length,
        "format_check": format_check,
    }
    
    # 7. 写入文件
    self._write_record(record)
    
    return record["id"]
```

### Step 3：增加辅助方法

```python
def _extract_error(self, outbound_msg) -> dict:
    """提取错误信息"""
    error_info = {
        "has_error": False,
        "error_type": None,
        "error_message": None,
    }
    
    if outbound_msg is None or outbound_msg.response is None:
        error_info["has_error"] = True
        error_info["error_type"] = "api_error"
        error_info["error_message"] = "未返回响应"
    elif not outbound_msg.response.content:
        error_info["has_error"] = True
        error_info["error_type"] = "empty_response"
        error_info["error_message"] = "返回内容为空"
    
    return error_info

def _calculate_token_metrics(self, tokens, model) -> dict:
    """计算 token 派生指标"""
    if not tokens:
        return None
    
    input_tokens = tokens.get("prompt_tokens", 0)
    output_tokens = tokens.get("completion_tokens", 0)
    
    io_ratio = output_tokens / input_tokens if input_tokens > 0 else 0
    cost_usd = self._estimate_cost(input_tokens, output_tokens, model)
    
    return {
        "io_ratio": io_ratio,
        "cost_usd": cost_usd,
    }

def _estimate_cost(self, input_tokens, output_tokens, model) -> float:
    """估算成本"""
    # 简化实现：硬编码价格表
    price_table = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
        "doubao": {"input": 0.0008, "output": 0.002},
    }
    
    default_price = {"input": 0.001, "output": 0.002}
    price = price_table.get(model, default_price)
    
    return (input_tokens / 1000) * price["input"] + (output_tokens / 1000) * price["output"]

def _check_format(self, output_content) -> dict:
    """检查输出格式"""
    result = {
        "is_valid_json": False,
        "has_required_fields": None,
        "detected_format": "text",
    }
    
    if not output_content:
        return result
    
    # 检查是否是 JSON
    try:
        from lifeprism.llm.utils.parse_utils import extract_json_from_response
        data = json.loads(extract_json_from_response(output_content))
        result["is_valid_json"] = True
        result["detected_format"] = "json"
    except:
        pass
    
    return result
```

### Step 4：更新调用方（可选，渐进式）

由于 `evaluation` 由 `bus.send()` 自动生成，调用方**无需修改**。

如果需要传递 `node_name`：
```python
# 修改前（依然能工作）
llm_call_logger.log_call(msg, result, prompt_module="schedule", prompt_name="summary")

# 修改后（增加节点名称）
llm_call_logger.log_call(
    msg, result, 
    prompt_module="schedule", 
    prompt_name="summary",
    node_name="summary_activities",  # 新增
)
```

---

## 工作量估算

| 阶段 | 工作内容 | 工作量 | 优先级 |
|------|----------|--------|--------|
| **Phase 1** | 修改 `llm_call_logger.log_call()` 增加新字段计算 | 2-3 小时 | P0 |
| | 更新 5-10 个关键调用点（传递 start_time） | 1-2 小时 | P0 |
| | 测试验证 | 1 小时 | P0 |
| **Phase 2** | 增加格式检查逻辑 | 1-2 小时 | P1 |
| **Phase 3** | 增加 reasoning tokens 支持 | 等模型支持 | P2 |
| **总计** | | **5-8 小时** | |

---

## 向后兼容性保证

1. ✅ **所有新参数都是可选的**：不传也能正常工作
2. ✅ **新字段都有默认值**：不会导致现有逻辑报错
3. ✅ **现有调用无需修改**：可以渐进式更新
4. ✅ **数据格式向后兼容**：旧数据可以正常读取（缺失字段视为 None）

---

## 总结

### ✅ **优点**
1. **零业务侵入**：不修改 `TokenType`，不影响现有业务逻辑
2. **实施简单**：只需修改 `llm_call_logger`，5-8 小时完成 P0 阶段
3. **渐进式扩展**：可以先实现 P0，后续再加 P1/P2
4. **向后兼容**：现有调用无需修改

### ✅ **能解决的问题**
1. **错误率统计**：修复 `error` 字段
2. **延迟统计**：新增 `timing` 字段
3. **Token 效率**：新增 `token_metrics` 字段（io_ratio + cost_usd）
4. **节点级别追踪**：新增 `node_name` 字段
5. **格式检查**：新增 `format_check` 字段

### ⚠️ **已搁置的功能**
1. **输入长度 + 复杂度评分**：
   - 原方案：通过"输入相近"的历史记录对比输出
   - 搁置原因：实现过于复杂，规则难以标定
   - 替代方案：后续考虑用机器学习模型（SVM/线性分类器）训练评估器

### ❓ **待讨论**
1. `start_time` 由调用方传递，还是在 `bus.send()` 内部记录？
2. `node_name` 是手动传递，还是从 `prompt_name` 自动推断？
3. 成本估算的价格表放在哪里（配置文件 vs 硬编码）？
