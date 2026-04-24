## 数据库接口创建规则

核心规则：创建接口时，必须查看现有的方法是如何实现的。provider类必须继承自LWBaseDataProvider

### 1. 创建数据表

需要在lifeprism/config/database.py编写原数据

#### 2.  创建数据库接口规则

1. **创建接口触发条件**：新增表时需要新增数据库接口

2. **如何创建新增的数据库接口**：在`lifeprism/repository/provider`中编写该数据表的provider类，在`lifeprism/repository/provider/__init__.py`创建单例并导出

3. 创建provider时，必须符合下面的结构：

   

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

4. 实现方法时，必须使用LWBaseDataset类的基础CURD方法（_generic_query、_generic_insert，_generic_update，_generic_delete）

5. 必须实现的核心方法

每个 Provider 必须实现以下 5 个核心方法：

- `query_{table}()` - 通用查询接口（使用 QueryOptions）
- `get_{table}_by_id()` - 按 ID 查询
- `create_{table}()` - 插入记录
- `update_{table}()` - 更新记录
- `delete_{table}()` - 删除记录

#### 3 聚合类规则

1. **aggregators创建的触发条件**：仅人工认定之后才可在`lifeprism\repository\aggregators`创建新的聚合类 
3. 聚合类方法必须透传所包括的provider成员的所有CURD核心方法，常用查询（超过3次引用）建议透传而不是在聚合层实现，特殊方法编写在聚合层。

