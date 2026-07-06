# 自定义记录数据录入与查询 - LLM 通道端到端

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD.md`

## What to build

在 Slice 1（类型管理）的基础上，实现自定义记录的数据录入与查询功能，继续走 LLM 通道端到端。完成后，用户可以通过 AI 对话向已创建的类型录入数据，并按日期范围查询记录。

端到端行为：
1. 用户说"今天跑了5公里"
2. AI 调用 `list_custom_record_types` 获取"体育活动"类型的字段定义
3. AI 解析字段值（如 `exercise_content: "跑了5公里"`），在对话内展示
4. 用户确认后，AI 调用 `create_custom_record_entry` 落库
5. 用户问"这周记录了哪些运动"
6. AI 调用 `query_custom_record_entries`（带 date_range），返回结果整理后回复用户
7. 如果 AI 传错 field_key，后端返回 `valid_fields`，AI 重新解析并重试

### Repository 层

- **新增方法到 `CustomRecordRepository`**（Slice 1 已创建）：
  - `create_entry(type_id, data)` — 录入一条记录到 `custom_<slug>` 表
  - `query_entries(type_id, date_range, page, page_size)` — 按日期范围分页查询
  - `get_entry(type_id, entry_id)` — 获取单条记录
  - `delete_entry(type_id, entry_id)` — 删除单条记录
- **录入时 field_key 校验**：
  - 校验 data 的 key 是否匹配 `custom_record_fields` 中该 type_id 的 field_key
  - 不匹配时抛 `ValidationError`，details 包含 `valid_fields`（字段 key 与显示名列表）
  - `valid_fields` 由 Repository 层构造（Repository 知道字段定义）
  - 缺失字段不报错，存为 NULL
  - data 为空字典允许（插入一行全 NULL 的记录）
- **查询参数**：
  - date_range 可只传 start 或只传 end，缺失侧不加约束
  - 分页：page + page_size
  - 排序：按 created_at DESC

### LLM Tool 层

- **2 个 tool**（直接调用 `custom_record_repository`，不经过 service）：
  3. `create_custom_record_entry` — 参数 `{type_id, data: {field_key: value}}`，返回 `{entry_id}`
  4. `query_custom_record_entries` — 参数 `{type_id, date_range?: [start, end], limit?}`，返回 `[{entry}]`
- **注册位置**：在 `lifeprism/llm/agent/loop.py` 的 CHAT 分支中注册（与 Slice 1 的 2 个 tool 同位置）
- **注意**：LLM tool 用 `limit` 而非 `page/page_size`（AI 不需要分页，一次拿够）
- **错误提示契约**：录入时 field_key 错误，tool 捕获 Repository 抛出的 `ValidationError`，返回 JSON 字符串：
  ```json
  {
    "error": "INVALID_FIELD_KEY",
    "message": "字段 'wrong_field' 不存在",
    "valid_fields": [
      {"field_key": "exercise_date", "field_name": "日期"},
      {"field_key": "exercise_content", "field_name": "锻炼内容"}
    ]
  }
  ```
  引导 AI 重新解析（`valid_fields` 由 Repository 层构造，Tool 层仅做 JSON 序列化）

### Prompt 设计

- 在 Slice 1 追加的"自定义记录"段落基础上，补充录入与查询流程
- 说明：用户表达"记录某事"时，先调 `list_custom_record_types` 获取字段，再调 `create_custom_record_entry`
- 说明：用户查询历史记录时，调 `query_custom_record_entries`（带 date_range）
- 说明：收到 `INVALID_FIELD_KEY` 错误时，根据 `valid_fields` 重新解析并重试

### 测试

- **测试 seam**：Repository 层（`test/core/unit/repository/test_custom_records_repository.py`，Slice 1 已创建）
- 新增测试覆盖：
  - 录入记录 → 断言 entry_id 返回且数据表有记录
  - 录入时 field_key 错误 → 断言抛 `ValidationError` 且 details 含 `valid_fields`
  - 录入时字段缺失 → 断言落库成功且缺失字段为 NULL
  - 录入时 data 为空字典 → 断言落库成功
  - 查询记录（日期筛选）→ 创建多条记录，按日期范围查询，断言返回正确子集
  - date_range 单侧缺失 → 断言查询正常，缺失侧不加约束
  - 查询分页 → 断言 page/page_size 生效
  - 删除记录 → 断言记录从数据表删除

## Acceptance criteria

- [ ] `CustomRecordRepository` 新增 4 个方法：`create_entry`、`query_entries`、`get_entry`、`delete_entry`
- [ ] 通过 AI 对话录入记录：data 的 key 匹配 field_key，落库成功，返回 entry_id
- [ ] 录入时 field_key 错误 → 返回 `ValidationError` + `valid_fields` 列表
- [ ] 录入时字段缺失 → 落库成功，缺失字段为 NULL
- [ ] data 为空字典 → 允许落库
- [ ] 通过 AI 对话查询记录：按 date_range 筛选，返回结果
- [ ] date_range 单侧缺失 → 查询正常
- [ ] 查询分页 → page/page_size 生效
- [ ] 2 个新 LLM tool 在 `loop.py` CHAT 分支注册
- [ ] prompt 中补充录入与查询流程
- [ ] 错误返回 JSON 含 `valid_fields`，引导 AI 重试
- [ ] Repository 层测试全部通过
- [ ] 遵循 `lifeprism/CLAUDE.md`（日志用 %s 格式、错误处理规则）

## Blocked by

- `.scratch/custom-records-module/issues/01-type-management-llm.md`（Slice 1 必须先完成，因为录入需要类型已存在）
