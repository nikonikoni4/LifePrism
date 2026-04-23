# Diary Provider 迁移记录

## 依赖分析

### 1. diary_provider 方法清单

| 方法名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `get_diary_by_date(date)` | 按日期获取单条日记 | date: str | Optional[Dict] |
| `get_diaries_by_date_range(start_date, end_date)` | 获取日期范围内的日记列表 | start_date: str, end_date: str | List[Dict] |
| `create_diary(date)` | 创建日记记录 | date: str | bool |
| `update_diary(date, data)` | 更新日记 meta | date: str, data: Dict | bool |

**注意**：没有 `delete_diary()` 方法，需要在新 provider 中补充。

### 2. 依赖的 Service

#### diary_service.py
调用的方法：
- `get_diary_by_date()` - 6 次调用（行 198, 205, 222, 240, 256, 265, 283, 288）
- `create_diary()` - 1 次调用（行 201）
- `update_diary()` - 3 次调用（行 237, 262, 304）
- `get_diaries_by_date_range()` - 2 次调用（行 315, 386）

使用场景：
- `get_diary()` - 获取或自动创建日记
- `update_diary_meta()` - 更新日记元数据
- `update_diary_content()` - 更新日记内容和字数
- `generate_diary_ai_summary()` - 生成单日 AI 总结
- `generate_diary_ai_summary_range()` - 批量生成 AI 总结
- `get_diary_list()` - 获取日记列表

#### summary_read_provider.py (LLM 模块)
调用的方法：
- `get_diaries_by_date_range()` - 1 次调用（行 60）

使用场景：
- `get_diaries_by_range()` - 为 LLM 提供日记数据

### 3. 测试文件

- `test/core/api/test_diary_ai_summary_api.py`
- `test/core/api/test_diary_ai_summary_range_api.py`

这些测试文件通过 API 间接调用 diary_provider。

### 4. 迁移注意事项

1. **缺失的方法**：需要补充 `delete_diary()` 方法
2. **白名单字段**：当前 `update_diary()` 有硬编码的 allowed_fields，需要改为类属性
3. **LLM 模块依赖**：`summary_read_provider.py` 需要在迁移后更新导入路径
4. **主键特殊性**：diary 表使用 `date` 作为主键，不是常规的 `id`
