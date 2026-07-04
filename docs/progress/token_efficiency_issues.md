# Token 效率评估 - 待解决问题清单

> 创建时间：2026-06-30  
> 状态：待讨论

---

## 核心问题

### 1. **Token Type 分类粒度问题**

**现状**：
- 当前 `token_type`（`lifeprism/llm/bus/events.py`）是按**大任务**分类
- 例如：`DREAM_TASK`、`GENERAL_TASK`、`CLASSIFY` 等

**问题**：
- 针对 **workflow** 评估时，需要按**节点级别**记录
  - 例如：`dreaming` workflow 包含 `summary_activities`、`summary_moods`、`update_memory` 等多个节点
  - 当前无法区分这些节点的 token 消耗
- 针对 **chat** 场景，当前分类不太适用

**需要改造**：
- 重构 `token_type` 为节点级别的名称
  - 方案1：直接用 `prompt_name`（如 `ACTIVITY_SUMMARY`、`MOOD_SUMMARY`）
  - 方案2：新增 `workflow_node` 字段，保留原有 `token_type`

---

### 2. **历史数据冷启动问题**

**问题**：
- 复杂度评分依赖历史数据（"输入相近情况下的输出对比"）
- 但刚开始使用时没有历史数据

**需要解决**：
1. **数据量阈值**：多少条历史记录才能开始计算复杂度？
   - 建议：至少 20-30 条同类型记录
   
2. **冷启动策略**：
   - 初期只计算绝对值（cost、total_tokens）
   - 积累足够数据后才启用复杂度评分
   
3. **判断逻辑**：
   ```python
   if len(historical_records) < MIN_RECORDS_FOR_COMPLEXITY:
       return {"error": "历史数据不足，无法计算复杂度"}
   ```

---

### 3. **Reasoning Tokens 记录问题**

**现状**：
- 当前 `llm_call_logger` 只记录 `prompt_tokens` 和 `completion_tokens`
- 没有单独记录 reasoning tokens

**问题**：
- 无法监控 LLM 的思考过程长度
- 无法区分"输出长是因为思考多"还是"输出内容本身多"

**需要改造**：
1. **模型支持检查**：
   - 并非所有模型都提供 reasoning tokens
   - 需要判断当前模型是否支持（如 OpenAI o1）
   
2. **数据结构扩展**：
   ```python
   "tokens": {
       "prompt_tokens": xxx,
       "completion_tokens": xxx,
       "reasoning_tokens": xxx,  # 新增
       "content_tokens": xxx,     # completion - reasoning
       "total_tokens": xxx,
   }
   ```

3. **兼容性处理**：
   - 不支持的模型：`reasoning_tokens = 0`

---

### 4. **数据存储方式问题**

**现状**：
- 当前 `llm_call_logger` 以 JSON 文件存储（按日期分文件）

**问题**：
- 统计分析需要遍历多个文件
- 复杂查询（如"输入相近的历史记录"）效率低

**建议方案**：
1. **建立数据库表**（推荐）
   ```sql
   CREATE TABLE llm_call_logs (
       id TEXT PRIMARY KEY,
       timestamp DATETIME,
       prompt_module TEXT,
       prompt_name TEXT,
       prompt_tokens INTEGER,
       completion_tokens INTEGER,
       reasoning_tokens INTEGER,
       total_tokens INTEGER,
       io_ratio REAL,
       cost_usd REAL,
       model TEXT,
       error TEXT,
       -- 其他字段...
   );
   
   CREATE INDEX idx_prompt ON llm_call_logs(prompt_module, prompt_name);
   CREATE INDEX idx_timestamp ON llm_call_logs(timestamp);
   ```

2. **优点**：
   - 查询效率高
   - 支持复杂统计（SQL 聚合函数）
   - 易于实现"输入相近"的查询（WHERE input_tokens BETWEEN x AND y）

3. **迁移成本**：
   - 需要从 JSON 迁移到数据库
   - 需要修改 `llm_call_logger` 的写入逻辑

---

### 5. **Token 效率指标的评估阈值问题**

**问题**：
- "Token 消耗是否异常"需要阈值判断
- 但不同任务的阈值完全不同

**待确定**：
1. **离群值阈值**：
   - 当前建议：均值 + 2σ
   - 是否合理？是否需要调整为 1.5σ 或 3σ？
   
2. **复杂度评分阈值**：
   - 复杂度 > 多少算"复杂"？
   - 复杂度 > 多少算"异常"？
   - 建议：1.5（复杂）、2.5（异常）
   
3. **io_ratio 正常范围**：
   - 不同任务类型的正常范围不同
   - 需要实验数据来确定

---

## 改造工作量估算

### Phase 1：数据记录改造（2-3 天）
1. 重构 `token_type` 为节点级别
2. 扩展 `tokens` 字段（reasoning_tokens）
3. 增加派生字段（io_ratio、cost_usd）

### Phase 2：数据存储改造（3-5 天）
1. 设计数据库表结构
2. 实现数据库写入逻辑（兼容 JSON fallback）
3. 迁移历史 JSON 数据到数据库

### Phase 3：统计分析实现（3-5 天）
1. 实现基础统计（avg、std、outlier）
2. 实现复杂度评分（需要等数据积累）
3. 实现 reasoning 分析（需要模型支持）

**总计**：8-13 天（假设全职投入）

---

## 后续讨论点

1. **是否立即启动改造？**
   - 还是先用当前数据结构实现基础指标，积累数据后再改造？
   
2. **数据库选型**：
   - SQLite（简单，与现有架构一致）
   - PostgreSQL（性能更好，但增加部署复杂度）
   
3. **向后兼容**：
   - 改造后是否保留 JSON 导出功能？
   - 历史数据是否需要全部迁移？

4. **阈值标定**：
   - 是否需要先跑一段时间数据，再标定阈值？
   - 还是先用经验值？

---

## 结论

Token 效率评估的工作量比预想的大，主要原因：
1. 数据记录粒度不够细（需要重构 token_type）
2. 数据存储方式不适合复杂查询（需要建表）
3. 复杂度评分需要历史数据（冷启动问题）
4. Reasoning tokens 记录缺失（需要扩展数据结构）

**建议**：
- **短期（P0）**：基于现有数据实现基础指标（cost、avg tokens、outlier）
- **中期（P1）**：积累数据 + 标定阈值
- **长期（P2）**：完整改造（建表 + 复杂度评分 + reasoning 分析）

---

## 相关文件

- `lifeprism/llm/bus/events.py` - TokenType 定义
- `lifeprism/llm/utils/llm_call_logger.py` - 日志记录器
- `docs/progress/agent_evaluation_task.md` - 评估任务清单
