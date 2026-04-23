# Provider迁移测试规范

**日期**: 2026-04-23  
**状态**: 草案 (Draft)  
**目的**: 确保provider重构过程中service行为不变

---

## 1. 测试策略概述

### 1.1 核心原则

**黄金法则**：重构前后，service的输出必须完全一致

**测试方法**：快照测试（Snapshot Testing）
- 在重构前捕获service的输出作为"黄金标准"
- 重构后运行相同测试，对比输出是否一致
- 任何差异都需要人工审查

### 1.2 测试流程

```
1. 确认迁移目标provider
   ↓
2. 识别依赖该provider的所有service
   ↓
3. 为每个service编写快照测试
   ↓
4. 运行测试，生成快照（必须有真实数据输出）
   ↓
5. 重构provider
   ↓
6. 逐步替换service中的provider调用
   ↓
7. 运行测试，验证快照一致
   ↓
8. 如有差异，分析原因（bug修复 or 预期变更）
```

---

## 2. 快照测试规范

### 2.1 测试框架选择

**推荐**: pytest + pytest-snapshot

```bash
pip install pytest pytest-snapshot
```

### 2.2 快照测试模板

```python
# tests/services/test_diary_service_snapshot.py
import pytest
from datetime import date
from lifeprism.server.services.diary_service import DiaryService

@pytest.fixture
def diary_service():
    """创建diary service实例"""
    return DiaryService()

@pytest.fixture
def test_date():
    """测试日期（使用固定日期确保可重复）"""
    return "2026-04-23"

class TestDiaryServiceSnapshot:
    """Diary Service快照测试"""
    
    def test_get_diary_by_date_snapshot(self, diary_service, test_date, snapshot):
        """
        测试get_diary_by_date方法的输出
        
        前提条件：
        - 数据库中必须存在2026-04-23的日记数据
        - 如果数据为空，先创建测试数据
        """
        # 1. 准备测试数据（如果需要）
        result = diary_service.get_diary_by_date(test_date)
        
        # 2. 验证数据非空（快照测试的前提）
        if result is None or (isinstance(result, dict) and not result):
            pytest.skip("数据为空，无法生成快照。请先创建测试数据。")
        
        # 3. 生成快照
        snapshot.assert_match(result, "get_diary_by_date_2026-04-23.json")
    
    def test_get_diaries_by_date_range_snapshot(self, diary_service, snapshot):
        """测试日期范围查询"""
        start_date = "2026-04-01"
        end_date = "2026-04-30"
        
        result = diary_service.get_diaries_by_date_range(start_date, end_date)
        
        # 验证数据非空
        if not result or len(result) == 0:
            pytest.skip("日期范围内无数据，无法生成快照。")
        
        # 生成快照
        snapshot.assert_match(result, "get_diaries_by_date_range_april.json")
    
    def test_insert_and_get_diary_snapshot(self, diary_service, snapshot):
        """测试插入日记后的查询结果"""
        test_date = "2026-04-25"
        test_data = {
            "date": test_date,
            "content": "测试日记内容",
            "mood": "happy",
            "weather": "sunny"
        }
        
        # 1. 插入日记
        diary_id = diary_service.insert_diary(test_data)
        
        # 2. 查询刚插入的日记
        result = diary_service.get_diary_by_date(test_date)
        
        # 3. 验证数据非空
        assert result is not None, "插入后应该能查询到数据"
        
        # 4. 生成快照（排除动态字段）
        # 移除created_at等时间戳字段，因为每次运行都不同
        result_for_snapshot = {k: v for k, v in result.items() 
                               if k not in ['created_at', 'updated_at']}
        
        snapshot.assert_match(result_for_snapshot, "insert_diary_result.json")
        
        # 5. 清理测试数据
        diary_service.delete_diary(test_date)
```

### 2.3 快照数据处理规则

#### 规则1：排除动态字段

```python
# 需要排除的字段（每次运行都不同）
DYNAMIC_FIELDS = [
    'created_at',      # 创建时间
    'updated_at',      # 更新时间
    'timestamp',       # 时间戳
    'id',              # 自动生成的ID（如果是UUID）
]

def sanitize_for_snapshot(data):
    """清理数据用于快照对比"""
    if isinstance(data, dict):
        return {k: sanitize_for_snapshot(v) 
                for k, v in data.items() 
                if k not in DYNAMIC_FIELDS}
    elif isinstance(data, list):
        return [sanitize_for_snapshot(item) for item in data]
    else:
        return data
```

#### 规则2：数据非空验证

```python
def validate_data_for_snapshot(data, test_name):
    """验证数据是否适合生成快照"""
    
    # 检查None
    if data is None:
        pytest.skip(f"{test_name}: 数据为None，无法生成快照")
    
    # 检查空列表
    if isinstance(data, list) and len(data) == 0:
        pytest.skip(f"{test_name}: 数据为空列表，无法生成快照")
    
    # 检查空字典
    if isinstance(data, dict) and len(data) == 0:
        pytest.skip(f"{test_name}: 数据为空字典，无法生成快照")
    
    return True
```

#### 规则3：排序确保一致性

```python
def normalize_list_for_snapshot(data_list, sort_key='id'):
    """对列表排序，确保快照一致"""
    if not isinstance(data_list, list):
        return data_list
    
    # 如果列表元素是字典，按指定key排序
    if data_list and isinstance(data_list[0], dict):
        return sorted(data_list, key=lambda x: x.get(sort_key, ''))
    
    return sorted(data_list)
```

---

## 3. 测试数据准备

### 3.1 测试数据库

**方案A：使用独立测试数据库**（推荐）

```python
# conftest.py
import pytest
from lifeprism.storage.database_manager import DatabaseManager
from lifeprism.config.settings_manager import settings

@pytest.fixture(scope="session")
def test_db():
    """创建测试数据库"""
    test_db_path = settings.lifeprism_data_path / "test_lw.db"
    
    # 创建测试数据库
    db_manager = DatabaseManager(str(test_db_path))
    
    # 初始化表结构
    from lifeprism.storage.resource_initializer import initialize_database
    initialize_database(db_manager)
    
    yield db_manager
    
    # 清理测试数据库
    test_db_path.unlink(missing_ok=True)

@pytest.fixture
def diary_service_with_test_db(test_db):
    """使用测试数据库的diary service"""
    from lifeprism.server.services.diary_service import DiaryService
    service = DiaryService()
    service.provider.db = test_db  # 注入测试数据库
    return service
```

**方案B：使用事务回滚**（如果数据库支持）

```python
@pytest.fixture
def db_transaction():
    """每个测试使用独立事务，测试后回滚"""
    from lifeprism.storage import lw_db_manager
    
    conn = lw_db_manager.get_connection()
    conn.execute("BEGIN")
    
    yield conn
    
    conn.execute("ROLLBACK")
```

### 3.2 测试数据生成器

```python
# tests/fixtures/diary_fixtures.py
from datetime import date, timedelta

class DiaryTestDataGenerator:
    """日记测试数据生成器"""
    
    @staticmethod
    def insert_sample_diary(diary_service, test_date="2026-04-23"):
        """插入示例日记"""
        data = {
            "date": test_date,
            "content": "这是一篇测试日记。今天学习了Python。",
            "mood": "happy",
            "weather": "sunny",
            "tags": ["学习", "Python"]
        }
        diary_id = diary_service.insert_diary(data)
        return diary_id, data
    
    @staticmethod
    def insert_diary_range(diary_service, start_date, days=7):
        """插入一系列日记"""
        diaries = []
        for i in range(days):
            current_date = (date.fromisoformat(start_date) + timedelta(days=i)).isoformat()
            diary_id, data = DiaryTestDataGenerator.insert_sample_diary(
                diary_service, 
                current_date
            )
            diaries.append((diary_id, data))
        return diaries
```

---

## 4. 迁移测试检查清单

### 4.1 重构前（Pre-Migration）

- [ ] 识别所有依赖该provider的service
- [ ] 为每个service的关键方法编写快照测试
- [ ] 准备测试数据（确保非空）
- [ ] 运行测试，生成快照文件
- [ ] 提交快照文件到git（作为基准）
- [ ] 确认所有测试通过

### 4.2 重构中（During Migration）

- [ ] 创建新的provider（在storage/providers/）
- [ ] 实现通用查询接口（query_*方法）
- [ ] 实现5个核心方法（query/get/insert/update/delete）
- [ ] 保持旧provider不变（兼容期）
- [ ] 在service中逐步替换provider调用
- [ ] 每替换一个方法，运行对应的快照测试
- [ ] 如有差异，分析原因并修复

### 4.3 重构后（Post-Migration）

- [ ] 运行完整的快照测试套件
- [ ] 确认所有快照一致
- [ ] 运行集成测试
- [ ] 手动测试关键功能
- [ ] 删除旧provider
- [ ] 更新文档

---

## 5. 示例：diary_provider迁移测试

### 5.1 测试文件结构

```
tests/
├── conftest.py                          # 全局fixtures
├── fixtures/
│   └── diary_fixtures.py                # 日记测试数据生成器
├── services/
│   └── test_diary_service_snapshot.py   # 快照测试
└── snapshots/                           # 快照文件（自动生成）
    └── test_diary_service_snapshot/
        ├── get_diary_by_date_2026-04-23.json
        └── get_diaries_by_date_range_april.json
```

### 5.2 完整测试代码

```python
# tests/services/test_diary_service_snapshot.py
import pytest
from datetime import date
from tests.fixtures.diary_fixtures import DiaryTestDataGenerator

@pytest.fixture(scope="module")
def diary_service_with_data(diary_service_with_test_db):
    """准备带测试数据的diary service"""
    service = diary_service_with_test_db
    
    # 插入测试数据
    DiaryTestDataGenerator.insert_sample_diary(service, "2026-04-23")
    DiaryTestDataGenerator.insert_diary_range(service, "2026-04-01", days=10)
    
    yield service
    
    # 清理测试数据（如果需要）
    # service.delete_all_test_data()

class TestDiaryServiceSnapshot:
    """Diary Service快照测试"""
    
    def test_get_diary_by_date(self, diary_service_with_data, snapshot):
        """测试按日期查询日记"""
        result = diary_service_with_data.get_diary_by_date("2026-04-23")
        
        # 验证数据非空
        assert result is not None, "应该查询到日记数据"
        
        # 排除动态字段
        result_clean = {k: v for k, v in result.items() 
                       if k not in ['created_at', 'updated_at']}
        
        # 生成快照
        snapshot.assert_match(result_clean, "get_diary_by_date.json")
    
    def test_get_diaries_by_date_range(self, diary_service_with_data, snapshot):
        """测试日期范围查询"""
        result = diary_service_with_data.get_diaries_by_date_range(
            "2026-04-01", 
            "2026-04-10"
        )
        
        # 验证数据非空
        assert len(result) > 0, "应该查询到多条日记"
        
        # 排序确保一致性
        result_sorted = sorted(result, key=lambda x: x['date'])
        
        # 排除动态字段
        result_clean = [
            {k: v for k, v in item.items() 
             if k not in ['created_at', 'updated_at']}
            for item in result_sorted
        ]
        
        # 生成快照
        snapshot.assert_match(result_clean, "get_diaries_by_date_range.json")
    
    def test_insert_diary_workflow(self, diary_service_with_test_db, snapshot):
        """测试插入日记的完整流程"""
        service = diary_service_with_test_db
        test_date = "2026-04-30"
        
        # 1. 插入日记
        test_data = {
            "date": test_date,
            "content": "新插入的测试日记",
            "mood": "neutral"
        }
        diary_id = service.insert_diary(test_data)
        
        # 2. 查询验证
        result = service.get_diary_by_date(test_date)
        assert result is not None
        
        # 3. 快照对比
        result_clean = {k: v for k, v in result.items() 
                       if k not in ['created_at', 'updated_at', 'id']}
        snapshot.assert_match(result_clean, "insert_diary_workflow.json")
        
        # 4. 清理
        service.delete_diary(test_date)
```

### 5.3 运行测试

```bash
# 首次运行：生成快照
pytest tests/services/test_diary_service_snapshot.py --snapshot-update

# 后续运行：验证快照
pytest tests/services/test_diary_service_snapshot.py

# 如果快照不匹配，查看差异
pytest tests/services/test_diary_service_snapshot.py -v
```

---

## 6. 常见问题和解决方案

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
# 只保留关键字段
result_minimal = {
    'id': result['id'],
    'date': result['date'],
    'content': result['content'][:100]  # 只保留前100字符
}
snapshot.assert_match(result_minimal, "snapshot.json")
```

### 问题5：重构后快照不匹配，但结果看起来正确

**解决方案**：人工审查差异，确认后更新快照
```bash
# 查看差异
pytest tests/services/test_diary_service_snapshot.py -v

# 确认差异合理后，更新快照
pytest tests/services/test_diary_service_snapshot.py --snapshot-update
```

---

## 7. 测试覆盖率要求

### 7.1 必须测试的场景

- [ ] 基础CRUD操作（insert, read, update, delete）
- [ ] 查询筛选（按日期、状态、关联ID等）
- [ ] 分页查询
- [ ] 排序功能
- [ ] 批量操作（如果有）
- [ ] 边界情况（空结果、单条结果、大量结果）

### 7.2 可选测试的场景

- [ ] 错误处理（参数验证失败）
- [ ] 并发操作
- [ ] 性能测试

---

## 8. 总结

### 8.1 测试流程总结

```
1. 准备测试数据（确保非空）
   ↓
2. 编写快照测试
   ↓
3. 运行测试生成快照（--snapshot-update）
   ↓
4. 提交快照到git
   ↓
5. 重构provider
   ↓
6. 运行测试验证快照
   ↓
7. 如有差异，分析并修复
   ↓
8. 所有测试通过后，完成迁移
```

### 8.2 关键原则

1. **数据非空原则**：快照测试必须基于真实数据
2. **排除动态字段**：时间戳、自动生成ID等不应包含在快照中
3. **排序一致性**：列表数据必须排序后再对比
4. **人工审查**：快照不匹配时，必须人工确认差异是否合理
5. **渐进式替换**：每替换一个方法，立即运行测试验证

### 8.3 成功标准

- ✅ 所有快照测试通过
- ✅ 无未预期的差异
- ✅ 测试覆盖所有关键功能
- ✅ 测试可重复运行
- ✅ 测试运行时间合理（< 5分钟）
