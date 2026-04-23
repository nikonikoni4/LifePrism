# Provider 重构标准流程

本文档提供 Provider 重构的标准流程，用于将旧的 Provider 迁移到新的通用方法架构。
构建todolist，逐步完成下面的构建步骤

## 参考示例

- **完整实现**: `lifeprism/storage/providers/diary_provider.py`
- **快照测试**: `test/core/services/test_diary_service_snapshot.py`
- **单元测试**: `test/core/unit/storage/test_base_provider_generic_methods.py`

## 架构原则

### 单表对应一个 Provider

**核心原则**：Provider 层是数据访问层，职责是提供单表的 CRUD 操作。业务聚合应该在 Service 层完成。

**多表场景处理**：
- 如果旧的 Provider 管理多张表（如 `MoodProvider` 管理 `mood_types`、`mood_entries`、`mood_impacts`）
- **必须拆分为多个独立的 Provider**，每个 Provider 对应一张表
- 可以写在同一个文件内，避免文件数量过多

**示例**：
```python
# lifeprism/storage/providers/mood_providers.py（注意文件名用复数）

# ==================== MoodTypeProvider ====================
class MoodTypeProvider(LWBaseDataProvider):
    """心情类型数据提供者（对应 mood_types 表）"""
    _TABLE_NAME = "mood_types"
    _PRIMARY_KEY = "id"
    # ...

# ==================== MoodEntryProvider ====================
class MoodEntryProvider(LWBaseDataProvider):
    """心情记录数据提供者（对应 mood_entries 表）"""
    _TABLE_NAME = "mood_entries"
    _PRIMARY_KEY = "id"
    # ...

# ==================== MoodImpactProvider ====================
class MoodImpactProvider(LWBaseDataProvider):
    """影响因素数据提供者（对应 mood_impacts 表）"""
    _TABLE_NAME = "mood_impacts"
    _PRIMARY_KEY = "id"
    # ...

# 导出单例
mood_type_provider = LazySingleton(MoodTypeProvider)
mood_entry_provider = LazySingleton(MoodEntryProvider)
mood_impact_provider = LazySingleton(MoodImpactProvider)
```

**Service 层协调**：
```python
# lifeprism/server/services/mood_service.py
from lifeprism.storage.providers import (
    mood_type_provider,
    mood_entry_provider,
    mood_impact_provider
)

def get_mood_types():
    items = mood_type_provider.get_mood_types()
    # ...

def create_mood_entry(request):
    # Service 层协调多个 Provider
    mood_type = mood_type_provider.get_mood_type_by_id(request.mood_type_id)
    if not mood_type:
        raise ValueError("无效的心情类型")
    
    data = {
        'mood_type_id': request.mood_type_id,
        'score': mood_type['score'],  # 从 mood_type 获取 score
        # ...
    }
    return mood_entry_provider.create_mood_entry(data)
```

**为什么不在 Provider 层聚合？**
- ❌ Provider 层聚合 = 违反单一职责原则
- ❌ Provider 层应该是"哑"的数据访问层，不应该承担业务聚合
- ✅ Service 层聚合 = 符合分层架构，职责清晰
- ✅ 更灵活：其他模块可以单独使用某个 Provider

## 重构流程

### 步骤 1: 构建 Service 快照测试

**目的**: 在重构前捕获当前行为，确保重构后行为不变。

**测试文件位置**: `test/core/services/test_<service_name>_snapshot.py`

**快照测试构建方法**:

```python
import pytest
from syrupy.assertion import SnapshotAssertion

# 1. 创建 conftest.py 配置测试数据库
# test/core/services/conftest.py
@pytest.fixture(scope="session")
def test_data_path(tmp_path_factory):
    """使用独立的测试数据库"""
    test_db = Path("test/localData/dataset/lifewatch_ai-test.db")
    return test_db.parent

# 2. 编写快照测试
def test_get_item_snapshot(snapshot: SnapshotAssertion):
    """测试获取单条记录"""
    result = service.get_item("test-id")
    assert result == snapshot

def test_query_items_snapshot(snapshot: SnapshotAssertion):
    """测试查询列表"""
    result = service.query_items(start_date="2026-01-01", end_date="2026-01-31")
    assert result == snapshot

def test_create_item_snapshot(snapshot: SnapshotAssertion):
    """测试创建记录"""
    result = service.create_item(data={"field": "value"})
    assert result == snapshot

def test_update_item_snapshot(snapshot: SnapshotAssertion):
    """测试更新记录"""
    result = service.update_item("test-id", data={"field": "new_value"})
    assert result == snapshot
```

**快照测试原则**:
- 测试 Service 层的公开接口（不是直接测试 Provider）
- 覆盖核心 CRUD 操作：查询、创建、更新、删除
- 使用独立的测试数据库（`lifewatch_ai-test.db`）
- 首次运行使用 `--snapshot-update` 生成快照

**运行命令**:
```bash
# 生成快照
pytest test/core/services/test_<service>_snapshot.py --snapshot-update

# 验证快照
pytest test/core/services/test_<service>_snapshot.py -v
```

---

### 步骤 2: 重构 Provider 使用通用方法

**目的**: 使用基类的通用方法替换手写的 SQL，减少代码重复。

#### 2.1 定义表元数据

在 Provider 类中定义以下元数据：

```python
class YourProvider(LWBaseDataProvider):
    """
    数据提供者
    
    职责：提供 your_table 表的所有数据访问接口
    """
    
    # ==================== 表元数据定义 ====================
    
    _TABLE_NAME = "your_table"           # 表名
    _PRIMARY_KEY = "id"                  # 主键字段（默认 "id"）
    _DATE_FIELD = "date"                 # 日期字段（可选，用于日期范围查询）
    _TIME_FIELD = "time"                 # 时间字段（可选，用于时间范围查询）
    
    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: Set[str] = {
        'id', 'name', 'status', 'date', 'time',
        'created_at', 'updated_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'name', 'date', 'created_at'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'name', 'status', 'date', 'time',
        'created_at', 'updated_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'name', 'status'  # 不包含主键和自动管理的字段
    }
```

**元数据定义原则**:
- `_TABLE_NAME`: 必须定义，使用实际表名
- `_PRIMARY_KEY`: 默认 "id"，如果表使用其他主键（如 "date"）需要覆盖
- `_DATE_FIELD` / `_TIME_FIELD`: 如果表有日期/时间字段，定义后可使用 `date_range` / `time_range` 查询
- 白名单字段：
  - `_FILTER_FIELDS`: 可用于 WHERE 条件的字段
  - `_ORDER_FIELDS`: 可用于 ORDER BY 的字段
  - `_SELECT_FIELDS`: 可用于 SELECT 的字段
  - `_UPDATE_FIELDS`: 可用于 UPDATE 的字段（不包含主键、created_at、updated_at）

#### 2.2 重构核心方法

使用通用方法替换手写 SQL：

```python
# ==================== 核心方法（使用通用方法） ====================

def query_items(
    self,
    options: Optional[QueryOptions] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    通用查询接口
    
    Args:
        options: 查询选项
        
    Returns:
        (记录列表, 总记录数)
    """
    return self._generic_query(options)  # ✅ 直接调用基类方法

def get_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
    """
    按主键获取单条记录
    
    Args:
        item_id: 主键值
        
    Returns:
        记录，不存在返回 None
    """
    options = QueryOptions(filters={self._PRIMARY_KEY: item_id})
    results, _ = self._generic_query(options)
    return results[0] if results else None

def insert_item(self, data: Dict[str, Any]) -> bool:
    """
    插入记录
    
    Args:
        data: 记录数据（必须包含主键，除非使用自动生成）
        
    Returns:
        是否成功
    """
    try:
        # 白名单验证
        allowed_fields = self._UPDATE_FIELDS | {self._PRIMARY_KEY}
        invalid_fields = set(data.keys()) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Invalid insert fields: {invalid_fields}")
        
        self._generic_insert(data)
        logger.info(f"创建记录成功: {data.get(self._PRIMARY_KEY)}")
        return True
    except Exception as e:
        logger.error(f"创建记录失败: {e}")
        return False

def update_item(self, item_id: str, data: Dict[str, Any]) -> bool:
    """
    更新记录
    
    Args:
        item_id: 主键值
        data: 要更新的字段
        
    Returns:
        是否成功
    """
    if not data:
        return True
    
    try:
        # 白名单验证
        invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
        if invalid_fields:
            raise ValueError(f"Invalid update fields: {invalid_fields}")
        
        # 如果需要自定义 updated_at 更新逻辑，手动处理
        # 否则使用 auto_timestamp=True（默认）
        return self._generic_update(item_id, data, auto_timestamp=True)
    except Exception as e:
        logger.error(f"更新记录 {item_id} 失败: {e}")
        return False

def delete_item(self, item_id: str) -> bool:
    """
    删除记录
    
    Args:
        item_id: 主键值
        
    Returns:
        是否成功
    """
    try:
        success = self._generic_delete(item_id)
        if success:
            logger.info(f"删除记录 {item_id} 成功")
        return success
    except Exception as e:
        logger.error(f"删除记录 {item_id} 失败: {e}")
        return False
```

**重构原则**:
- ✅ 使用 `_generic_query()` 替换 SELECT 查询
- ✅ 使用 `_generic_insert()` 替换 INSERT 语句
- ✅ 使用 `_generic_update()` 替换 UPDATE 语句
- ✅ 使用 `_generic_delete()` 替换 DELETE 语句
- ✅ 保留白名单验证（防止非法字段）
- ✅ 保留异常处理和日志记录
- ✅ 保留业务逻辑（如自动计算字段）
- ❌ 不要删除兼容旧接口的方法（如 `get_item_by_date` 等别名方法）

#### 2.3 特殊情况处理

**情况 1: 自定义主键（非 "id"）**

```python
class DiaryProvider(LWBaseDataProvider):
    _TABLE_NAME = "diary"
    _PRIMARY_KEY = "date"  # ✅ 覆盖默认主键
    _DATE_FIELD = "date"
    _TIME_FIELD = None
```

**情况 2: SQLite 特定的时间戳更新**

```python
def update_item(self, item_id: str, data: Dict[str, Any]) -> bool:
    if 'updated_at' not in data:
        # 使用 SQLite 的 datetime('now','localtime')
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            set_clauses = [f"{key} = ?" for key in data.keys()]
            set_clauses.append("updated_at = datetime('now','localtime')")
            values = list(data.values()) + [item_id]
            sql = f"UPDATE {self._TABLE_NAME} SET {', '.join(set_clauses)} WHERE {self._PRIMARY_KEY} = ?"
            cursor.execute(sql, values)
            conn.commit()
            return cursor.rowcount > 0
    else:
        # 使用通用方法
        return self._generic_update(item_id, data, auto_timestamp=False)
```

**情况 3: 自动生成 ID**

```python
def insert_item(self, data: Dict[str, Any]) -> bool:
    # 如果没有提供 ID，自动生成
    if self._PRIMARY_KEY not in data:
        data[self._PRIMARY_KEY] = f"prefix-{uuid.uuid4().hex[:8]}"
    
    return self._generic_insert(data)
```

---

### 步骤 3: 替换单例

**目的**: 在 Service 层使用新的 Provider，保持向后兼容。

#### 3.1 在 storage/providers/__init__.py 中导出新 Provider

```python
# lifeprism/storage/providers/__init__.py
from lifeprism.storage.providers.your_provider import YourProvider, QueryOptions
from lifeprism.utils import LazySingleton

# 创建全局单例（已重构为使用通用方法）
your_provider = LazySingleton(YourProvider)

__all__ = [
    'YourProvider',
    'QueryOptions',
    'your_provider',
]
```

#### 3.2 在 Service 中替换 import

**修改前**:
```python
from lifeprism.server.providers.your_provider import your_provider
```

**修改后**:
```python
from lifeprism.storage.providers import your_provider
```

**注意**: 
- 直接在 import 处替换，不需要创建临时的 `new_your_provider`
- Service 层代码无需修改，只改 import 路径

---

### 步骤 4: 运行快照测试并提交

#### 4.1 运行快照测试

```bash
# 运行快照测试
pytest test/core/services/test_<service>_snapshot.py -v --tb=short

# 如果快照不匹配，检查差异
pytest test/core/services/test_<service>_snapshot.py -vv

# 确认行为一致后，更新快照（如果需要）
pytest test/core/services/test_<service>_snapshot.py --snapshot-update
```

**验证标准**:
- ✅ 所有快照测试通过（X/X passed）
- ✅ 无新增或修改的快照（除非是预期的行为变更）
- ✅ 测试执行时间合理（< 1s）

#### 4.2 提交代码

```bash
# 查看修改
git add -A
git status
git diff --cached

# 提交
git commit -m "refactor(storage): 完成 <Provider> 重构迁移

将 <service> 从旧的 server.providers.<provider> 迁移到新的 storage.providers.<provider>。

变更：
- <service>.py: 改用 storage.providers.<provider>（已重构版本）
- storage/providers/<provider>.py: 使用通用方法重构核心 CRUD
- storage/providers/__init__.py: 导出新的 provider 单例

测试：
- 所有快照测试通过（X/X），验证新旧 provider 行为完全一致

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 重构检查清单

### Provider 重构
- [ ] 定义表元数据（_TABLE_NAME, _PRIMARY_KEY, _DATE_FIELD, _TIME_FIELD）
- [ ] 定义白名单字段（_FILTER_FIELDS, _ORDER_FIELDS, _SELECT_FIELDS, _UPDATE_FIELDS）
- [ ] 使用 `_generic_query()` 替换查询方法
- [ ] 使用 `_generic_insert()` 替换插入方法
- [ ] 使用 `_generic_update()` 替换更新方法
- [ ] 使用 `_generic_delete()` 替换删除方法
- [ ] 保留白名单验证和异常处理
- [ ] 保留兼容旧接口的方法

### 测试
- [ ] 创建快照测试文件
- [ ] 覆盖核心 CRUD 操作
- [ ] 使用独立测试数据库
- [ ] 所有快照测试通过

### 集成
- [ ] 在 storage/providers/__init__.py 中导出单例
- [ ] 在 Service 中替换 import 路径
- [ ] 运行快照测试验证行为一致
- [ ] 提交代码

---

## 常见问题

### Q1: 快照测试失败怎么办？

**A**: 
1. 检查差异：`pytest test/core/services/test_<service>_snapshot.py -vv`
2. 如果是预期的行为变更，更新快照：`--snapshot-update`
3. 如果是非预期变更，检查 Provider 实现是否正确

### Q2: 如何处理复杂的查询逻辑？

**A**: 
- 简单查询：使用 `QueryOptions` + `_generic_query()`
- 复杂查询：保留手写 SQL，但使用参数化查询防止注入

### Q3: 是否需要删除旧的 Provider？

**A**: 
- 重构完成后，旧的 `server/providers/<provider>.py` 可以删除
- 但建议先保留一段时间，确保没有其他地方引用

### Q4: 如何处理没有 Service 层的 Provider？

**A**: 
- 如果 Provider 直接被 API 或其他模块使用，创建集成测试
- 测试应覆盖所有公开方法的行为

---

## 参考资料

- **DiaryProvider 实现**: `lifeprism/storage/providers/diary_provider.py`
- **快照测试示例**: `test/core/services/test_diary_service_snapshot.py`
- **通用方法文档**: `lifeprism/storage/base_providers/lw_base_data_provider.py`
- **QueryOptions 文档**: `lifeprism/storage/providers/common_query_options.py`
