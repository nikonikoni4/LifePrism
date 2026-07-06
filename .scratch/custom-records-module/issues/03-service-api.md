# 自定义记录模块 Service 与 API 层

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD.md`

## What to build

在 Slice 1 + Slice 2（Repository 层 + LLM 通道）已就位的基础上，为前端实现 HTTP API 通道。`CustomRecordService` 作为 API 层的薄包装，调用 `custom_record_repository` 完成业务操作。7 个 REST API 端点覆盖类型管理 + 记录 CRUD 的所有操作。

端到端行为：
1. 前端启动后调用 `GET /custom-records/types` 获取所有类型列表
2. 前端新建类型：`POST /custom-records/types`，后端调 repository 完成 meta 写入 + DDL
3. 前端进入类型详情页：`GET /custom-records/types/{type_id}` 获取字段定义 + `GET /custom-records/{type_id}/entries` 获取记录
4. 前端录入记录：`POST /custom-records/{type_id}/entries`（AI 通道也可录，但前端走 API）
5. 前端删除记录/类型：`DELETE` 端点
6. 错误响应遵循全局异常处理器映射

### Service 层（API 层薄包装）

- **`CustomRecordService` 仅服务 API 层**，做参数转换与 repository 调用编排
- **不包含核心业务逻辑**：slug 冲突、field_key 校验、valid_fields 构造等都在 Repository 层（Slice 1+2 已实现）
- **方法**：直接转发到 `custom_record_repository` 对应方法，无额外业务逻辑
- **LLM Tool 不经过 Service**：遵循现有架构（`lifeprism/llm/agent/tools/lifeprismsystem.py` 第 6-13 行证明 LLM tool 直接引用 repository），LLM tool 已在 Slice 1+2 中直接调 repository，不经过 service

### 架构依赖关系

```
API 路由 ──→ Service ──→ Repository (CustomRecordRepository)  [Slice 1+2 已实现]
                              ↑
LLM Tool ──────────────────────┘  (直接访问，不经过 Service)  [Slice 1+2 已实现]
```

### API 层

- **路由前缀**：`/custom-records`
- **挂载位置**：在 `main.py` 中 `app.include_router(custom_records_router, prefix="/api/v2")`（参考 mood_router 的挂载方式）
- **7 个端点**：
  1. `GET /custom-records/types` — 类型列表（含 fields）
  2. `GET /custom-records/types/{type_id}` — 单个类型详情（含 fields）
  3. `POST /custom-records/types` — 创建类型（body: `{name, slug, fields: [{field_name, field_key, field_type}]}`）
  4. `DELETE /custom-records/types/{type_id}` — 硬删类型
  5. `GET /custom-records/{type_id}/entries` — 查询记录（query: `start_date, end_date, page, page_size`）
  6. `POST /custom-records/{type_id}/entries` — 录入记录（body: `{data: {field_key: value}}`）
  7. `DELETE /custom-records/{type_id}/entries/{entry_id}` — 删除单条记录
- **错误响应**：遵循项目全局异常处理器映射（ValidationError → 422，EntityNotFoundError → 404，DuplicateEntityError → 409）
- **API 层不写 try/except**（遵循 `lifeprism/CLAUDE.md` 错误处理规则）
- **参考实现**：`lifeprism/server/services/mood_api.py` 的 router 定义和 service 调用模式

### 不测的内容

- Service 层（Repository 的薄包装，无业务逻辑）
- API 路由的请求转发（FastAPI 已有保证）
- 测试仍由 Slice 1+2 的 Repository 层测试覆盖

## Acceptance criteria

- [ ] `CustomRecordService` 实现为 API 层薄包装，所有方法直接转发到 `custom_record_repository`
- [ ] 7 个 API 端点实现，路由前缀 `/custom-records`
- [ ] 路由在 `main.py` 中挂载到 `/api/v2/custom-records`
- [ ] `GET /types` 返回类型列表（含 fields）
- [ ] `POST /types` 创建类型成功，slug 冲突返回 409，格式错误返回 422
- [ ] `DELETE /types/{type_id}` 硬删类型（DROP 表 + 删 meta）
- [ ] `GET /{type_id}/entries` 支持日期筛选 + 分页
- [ ] `POST /{type_id}/entries` 录入记录，field_key 错误返回 422 + `valid_fields`
- [ ] `DELETE /{type_id}/entries/{entry_id}` 删除单条记录
- [ ] 错误响应状态码：ValidationError → 422，EntityNotFoundError → 404，DuplicateEntityError → 409
- [ ] API 层不写 try/except
- [ ] 遵循 `lifeprism/CLAUDE.md`（日志用 %s 格式、错误处理规则）

## Blocked by

- `.scratch/custom-records-module/issues/01-type-management-llm.md`（Slice 1 的 Repository 必须先完成）
- `.scratch/custom-records-module/issues/02-entry-management-llm.md`（Slice 2 的 Repository 必须先完成）
