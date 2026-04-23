# Step 1 - 快照测试准备

**日期**: 2026-04-23  
**类型**: 测试规范  
**来源**: `2026-04-23-refactor-repository-architecture-draft.md` & `2026-04-23-provider-migration-testing-guide.md`

---

## 1. 测试策略概述

### 1.1 核心原则

**黄金法则**：重构前后，service的输出必须完全一致

**测试方法**：快照测试（Snapshot Testing）
- 在重构前捕获service的输出作为"黄金标准"
- 重构后运行相同测试，对比输出是否一致
- 任何差异都需要人工审查

---

## 2. 快照测试关键规则

1. **数据非空原则**：快照测试必须基于真实数据，空数据应skip测试
2. **排除动态字段**：时间戳、自动生成ID等不应包含在快照中
3. **排序一致性**：列表数据必须排序后再对比
4. **人工审查**：快照不匹配时，必须人工确认差异是否合理

---

## 3. 数据处理规范

### 3.1 排除动态字段

```python
# 需要排除的字段（每次运行都不同）
DYNAMIC_FIELDS = [
    'created_at',      # 创建时间
    'updated_at',      # 更新时间
    'timestamp',       # 时间戳
    'last_modified',   # 最后修改时间
    'modified_at',     # 修改时间
]

def sanitize_for_snapshot(data, exclude_fields=None):
    """
    清理数据用于快照对比
    """
    if exclude_fields is None:
        exclude_fields = DYNAMIC_FIELDS
    
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k in exclude_fields:
                continue
            if isinstance(v, float):
                result[k] = round(v, 6)  # 浮点数精度问题
            else:
                result[k] = sanitize_for_snapshot(v, exclude_fields)
        return result
    elif isinstance(data, list):
        return [sanitize_for_snapshot(item, exclude_fields) for item in data]
    else:
        return data
```

### 3.2 数据非空验证

```python
def validate_data_for_snapshot(data, test_name):
    """验证数据是否适合生成快照"""
    
    if data is None:
        pytest.skip(f"{test_name}: 数据为None，无法生成快照")
    
    if isinstance(data, list) and len(data) == 0:
        pytest.skip(f"{test_name}: 数据为空列表，无法生成快照")
    
    if isinstance(data, dict) and len(data) == 0:
        pytest.skip(f"{test_name}: 数据为空字典，无法生成快照")
    
    return True
```

### 3.3 排序确保一致性

```python
from typing import List, Dict, Any

def normalize_list_for_snapshot(
    data_list: List[Dict[str, Any]], 
    sort_keys: List[str] = None
) -> List[Dict[str, Any]]:
    """
    对列表排序，确保快照一致
    
    Args:
        data_list: 要排序的列表
        sort_keys: 排序键列表（支持多级排序）
    """
    if not isinstance(data_list, list) or not data_list:
        return data_list
    
    if not isinstance(data_list[0], dict):
        return sorted(data_list)
    
    if sort_keys is None:
        sort_keys = ['id', 'date', 'created_at']
    
    def sort_key_func(item):
        keys = []
        for key in sort_keys:
            value = item.get(key)
            if value is None:
                keys.append('')
            elif isinstance(value, str):
                keys.append(value)
            elif isinstance(value, (int, float)):
                keys.append(value)
            else:
                keys.append(str(value))
        return tuple(keys)
    
    return sorted(data_list, key=sort_key_func)
```

---

## 4. 测试示例

```python
# tests/services/test_diary_service_snapshot.py
def test_get_diary_by_date_snapshot(diary_service, test_date, snapshot):
    """测试get_diary_by_date方法的输出"""
    result = diary_service.get_diary_by_date(test_date)
    
    # 验证数据非空（快照测试的前提）
    if result is None or not result:
        pytest.skip("数据为空，无法生成快照。请先创建测试数据。")
    
    # 排除动态字段
    result_clean = {k: v for k, v in result.items() 
                   if k not in ['created_at', 'updated_at']}
    
    # 生成快照
    snapshot.assert_match(result_clean, "get_diary_by_date.json")
```

---


## 快照检查清单

- [ ] 识别所有依赖该provider的service
- [ ] 为每个service的关键方法编写快照测试
- [ ] 准备测试数据（确保非空）
- [ ] 运行测试，生成快照文件
- [ ] 提交快照文件到git（作为基准）
- [ ] 确认所有测试通过

### 7.2 重构中（During Migration）

- [ ] 创建新的provider（在storage/providers/）
- [ ] 实现通用查询接口（query_*方法）
- [ ] 实现5个核心方法（query/get/insert/update/delete）
- [ ] 保持旧provider不变（兼容期）
- [ ] 在service中逐步替换provider调用
- [ ] 每替换一个方法，运行对应的快照测试
- [ ] 如有差异，分析原因并修复

### 7.3 重构后（Post-Migration）

- [ ] 运行完整的快照测试套件
- [ ] 确认所有快照一致
- [ ] 运行集成测试
- [ ] 手动测试关键功能
- [ ] 删除旧provider
- [ ] 更新文档

---

## 8. 测试覆盖率要求

### 8.1 必须测试的场景

- [ ] 基础CRUD操作（insert, read, update, delete）
- [ ] 查询筛选（按日期、状态、关联ID等）
- [ ] 分页查询
- [ ] 排序功能
- [ ] 批量操作（如果有）
- [ ] 边界情况（空结果、单条结果、大量结果）

### 8.2 可选测试的场景

- [ ] 错误处理（参数验证失败）
- [ ] 并发操作
- [ ] 性能测试

---

## 9. 常见问题和解决方案

### 问题1：快照包含时间戳导致每次都不匹配

**解决方案**：排除动态字段
```python
EXCLUDE_FIELDS = ['created_at', 'updated_at', 'timestamp']
result_clean = {k: v for k, v in result.items() if k not in EXCLUDE_FIELDS}
```

### 问题2：列表顺序不一致导致快照不匹配

**解决方案**：排序后再对比
```python
result_sorted = sorted(result, key=lambda x: x['id'])
snapshot.assert_match(result_sorted, "snapshot.json")
```

### 问题3：测试数据为空，无法生成快照

**解决方案**：使用pytest.skip跳过
```python
if not result:
    pytest.skip("数据为空，无法生成快照。请先创建测试数据。")
```

### 问题4：快照文件过大

**解决方案**：只测试关键字段
```python
result_minimal = {
    'id': result['id'],
    'date': result['date'],
    'content': result['content'][:100]
}
snapshot.assert_match(result_minimal, "snapshot.json")
```

### 问题5：重构后快照不匹配，但结果看起来正确

**解决方案**：人工审查差异，确认后更新快照
```bash
pytest tests/services/test_diary_service_snapshot.py -v
pytest tests/services/test_diary_service_snapshot.py --snapshot-update
```

---

## 10. 关键原则

1. **数据非空原则**：快照测试必须基于真实数据
2. **排除动态字段**：时间戳、自动生成ID等不应包含在快照中
3. **排序一致性**：列表数据必须排序后再对比
4. **人工审查**：快照不匹配时，必须人工确认差异是否合理
5. **渐进式替换**：每替换一个方法，立即运行测试验证

---

## 11. 成功标准

- ✅ 所有快照测试通过
- ✅ 无未预期的差异
- ✅ 测试覆盖所有关键功能
- ✅ 测试可重复运行

