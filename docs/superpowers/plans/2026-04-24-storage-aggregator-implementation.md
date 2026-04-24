# Storage Aggregator 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 6 个 Aggregator 类聚合相关 Provider，并统一导出为 `xxx_store` 接口

**Architecture:** 采用方案 E（统一 Store 命名）- 内部保持 Provider/Aggregator 清晰职责，对外统一使用 `xxx_store` 命名。使用 `as` 重命名，不创建透传层。

**Tech Stack:** Python 3.x, SQLite, 现有 Provider 基础设施

**参考文档:** `docs/temp/Investigation/2026-04-24-provider-aggregator-architecture-research.md`

---

## 文件结构概览

**新建文件:**
- `lifeprism/storage/aggregators/__init__.py` - Aggregator 导出
- `lifeprism/storage/aggregators/habit_aggregator.py` - Habit 聚合器
- `lifeprism/storage/aggregators/mood_aggregator.py` - Mood 聚合器
- `lifeprism/storage/aggregators/goal_aggregator.py` - Goal 聚合器
- `lifeprism/storage/aggregators/habit_chain_aggregator.py` - HabitChain 聚合器
- `lifeprism/storage/aggregators/category_aggregator.py` - Category 聚合器
- `lifeprism/storage/aggregators/map_cache_aggregator.py` - MapCache 聚合器

**修改文件:**
- `lifeprism/storage/__init__.py` - 添加统一 store 导出
- `lifeprism/storage/providers/__init__.py` - 保持 provider 导出（内部使用）

---

## Task 1: 创建 Aggregators 目录和基础结构

**Files:**
- Create: `lifeprism/storage/aggregators/__init__.py`

- [ ] **Step 1: 创建 aggregators 目录**

```bash
mkdir -p lifeprism/storage/aggregators
```

- [ ] **Step 2: 创建 __init__.py 文件**

```python
"""
Storage Aggregators - 数据聚合层

聚合多个相关 Provider，提供统一的业务数据视图。
"""
# 占位文件，后续任务会添加具体导出
```

- [ ] **Step 3: 验证目录结构**

```bash
ls -la lifeprism/storage/aggregators/
```

Expected: 看到 `__init__.py` 文件

- [ ] **Step 4: Commit**

```bash
git add lifeprism/storage/aggregators/__init__.py
git commit -m "feat(storage): 创建 aggregators 目录结构"
```

---

## Task 2: 创建 HabitAggregator

**Files:**
- Create: `lifeprism/storage/aggregators/habit_aggregator.py`

**聚合对象:** HabitProvider, HabitChallengeProvider, HabitCheckinProvider

- [ ] **Step 1: 创建 HabitAggregator 类框架**

```python
"""
Habit Aggregator - 习惯数据聚合层

聚合 HabitProvider, HabitChallengeProvider, HabitCheckinProvider
提供习惯相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers import (
    habit_provider,
    habit_challenge_provider,
    habit_checkin_provider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class HabitAggregator:
    """
    习惯聚合器
    
    职责：聚合 habit、challenge、checkin 三个表的数据
    """
    
    def __init__(self):
        self.habit_provider = habit_provider
        self.challenge_provider = habit_challenge_provider
        self.checkin_provider = habit_checkin_provider
```

- [ ] **Step 2: 添加获取习惯详情方法（聚合 habit + challenge）**

```python
    def get_habit_with_challenge(self, habit_id: str) -> Optional[Dict[str, Any]]:
        """
        获取习惯详情（包含当前挑战信息）
        
        Args:
            habit_id: 习惯 ID
            
        Returns:
            包含 habit 和 current_challenge 的字典，不存在返回 None
        """
        habit = self.habit_provider.get_habit_by_id(habit_id)
        if not habit:
            return None
        
        # 获取当前活跃的挑战
        challenges = self.challenge_provider.get_challenges_by_habit(
            habit_id, status='active'
        )
        habit['current_challenge'] = challenges[0] if challenges else None
        
        return habit
```

- [ ] **Step 3: 添加获取习惯列表方法（聚合 habit + challenge）**

```python
    def get_habits_with_challenges(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取习惯列表（每个习惯包含当前挑战）
        
        Args:
            status: 状态过滤（'active'|'paused'），None 返回全部
            
        Returns:
            习惯列表，每个包含 current_challenge 字段
        """
        habits = self.habit_provider.get_habits(status)
        
        # 批量获取所有习惯的挑战
        for habit in habits:
            challenges = self.challenge_provider.get_challenges_by_habit(
                habit['id'], status='active'
            )
            habit['current_challenge'] = challenges[0] if challenges else None
        
        return habits
```

- [ ] **Step 4: 添加获取习惯统计方法（聚合 habit + checkin）**

```python
    def get_habit_with_stats(
        self, habit_id: str, days: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        获取习惯详情（包含打卡统计）
        
        Args:
            habit_id: 习惯 ID
            days: 统计最近多少天
            
        Returns:
            包含 habit 和 stats 的字典
        """
        habit = self.habit_provider.get_habit_by_id(habit_id)
        if not habit:
            return None
        
        # 获取最近的打卡记录
        from datetime import datetime, timedelta
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        checkins = self.checkin_provider.get_checkins_by_habit(
            habit_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )
        
        habit['stats'] = {
            'total_checkins': len(checkins),
            'recent_checkins': checkins[:7] if len(checkins) > 7 else checkins,
        }
        
        return habit
```

- [ ] **Step 5: 添加创建习惯和挑战方法（事务性操作）**

```python
    def create_habit_with_challenge(
        self, habit_data: Dict[str, Any], challenge_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        创建习惯并可选创建初始挑战
        
        Args:
            habit_data: 习惯数据
            challenge_data: 挑战数据（可选）
            
        Returns:
            新创建的 habit_id
        """
        # 创建习惯
        habit_id = self.habit_provider.create_habit(habit_data)
        
        # 如果提供了挑战数据，创建挑战
        if challenge_data:
            challenge_data['habit_id'] = habit_id
            self.challenge_provider.create_challenge(challenge_data)
        
        logger.info(f"创建习惯 {habit_id}，包含挑战: {challenge_data is not None}")
        return habit_id
```

- [ ] **Step 6: 验证代码语法**

```bash
python -m py_compile lifeprism/storage/aggregators/habit_aggregator.py
```

Expected: 无输出表示编译成功

- [ ] **Step 7: Commit**

```bash
git add lifeprism/storage/aggregators/habit_aggregator.py
git commit -m "feat(storage): 添加 HabitAggregator 聚合器"
```

---

## Task 3: 创建 MoodAggregator

**Files:**
- Create: `lifeprism/storage/aggregators/mood_aggregator.py`

**聚合对象:** MoodTypeProvider, MoodEntryProvider, MoodImpactProvider

- [ ] **Step 1: 创建 MoodAggregator 类框架**

```python
"""
Mood Aggregator - 心情数据聚合层

聚合 MoodTypeProvider, MoodEntryProvider, MoodImpactProvider
提供心情相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers import (
    mood_type_provider,
    mood_entry_provider,
    mood_impact_provider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class MoodAggregator:
    """
    心情聚合器
    
    职责：聚合 mood_type、mood_entry、mood_impact 三个表的数据
    """
    
    def __init__(self):
        self.type_provider = mood_type_provider
        self.entry_provider = mood_entry_provider
        self.impact_provider = mood_impact_provider
```

- [ ] **Step 2: 添加获取心情条目详情方法（聚合 entry + type）**

```python
    def get_mood_entry_with_type(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        获取心情条目详情（包含类型信息）
        
        Args:
            entry_id: 条目 ID
            
        Returns:
            包含 entry 和 type_info 的字典，不存在返回 None
        """
        entry = self.entry_provider.get_mood_entry_by_id(entry_id)
        if not entry:
            return None
        
        # 获取类型信息
        if entry.get('mood_type_id'):
            mood_type = self.type_provider.get_mood_type_by_id(entry['mood_type_id'])
            entry['type_info'] = mood_type
        else:
            entry['type_info'] = None
        
        return entry
```

- [ ] **Step 3: 添加获取心情条目列表方法（聚合 entry + type）**

```python
    def get_mood_entries_with_types(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取心情条目列表（每个条目包含类型信息）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            心情条目列表，每个包含 type_info 字段
        """
        entries = self.entry_provider.get_mood_entries(start_date, end_date)
        
        # 批量获取类型信息（先收集所有类型 ID）
        type_ids = {e['mood_type_id'] for e in entries if e.get('mood_type_id')}
        type_map = {}
        for type_id in type_ids:
            mood_type = self.type_provider.get_mood_type_by_id(type_id)
            if mood_type:
                type_map[type_id] = mood_type
        
        # 为每个条目添加类型信息
        for entry in entries:
            type_id = entry.get('mood_type_id')
            entry['type_info'] = type_map.get(type_id) if type_id else None
        
        return entries
```

- [ ] **Step 4: 添加获取心情类型统计方法（聚合 type + entry）**

```python
    def get_mood_type_with_stats(self, mood_type_id: str) -> Optional[Dict[str, Any]]:
        """
        获取心情类型详情（包含使用统计）
        
        Args:
            mood_type_id: 类型 ID
            
        Returns:
            包含 type 和 stats 的字典
        """
        mood_type = self.type_provider.get_mood_type_by_id(mood_type_id)
        if not mood_type:
            return None
        
        # 获取使用统计
        entry_count = self.type_provider.count_entries_by_type(mood_type_id)
        
        mood_type['stats'] = {
            'entry_count': entry_count,
        }
        
        return mood_type
```

- [ ] **Step 5: 添加获取心情影响分析方法（聚合 entry + impact）**

```python
    def get_mood_analysis_with_impacts(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取心情分析（包含影响因素）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            包含 entries 和 impacts 的分析数据
        """
        entries = self.entry_provider.get_mood_entries(start_date, end_date)
        impacts = self.impact_provider.get_mood_impacts()
        
        return {
            'entries': entries,
            'impacts': impacts,
            'total_entries': len(entries),
            'total_impacts': len(impacts),
        }
```

- [ ] **Step 6: 验证代码语法**

```bash
python -m py_compile lifeprism/storage/aggregators/mood_aggregator.py
```

Expected: 无输出表示编译成功

- [ ] **Step 7: Commit**

```bash
git add lifeprism/storage/aggregators/mood_aggregator.py
git commit -m "feat(storage): 添加 MoodAggregator 聚合器"
```

---

## Task 4: 创建 GoalAggregator

**Files:**
- Create: `lifeprism/storage/aggregators/goal_aggregator.py`

**聚合对象:** GoalProvider, GoalStatsProvider

- [ ] **Step 1: 创建 GoalAggregator 类框架**

```python
"""
Goal Aggregator - 目标数据聚合层

聚合 GoalProvider, GoalStatsProvider
提供目标相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers import (
    goal_provider,
    goal_stats_provider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class GoalAggregator:
    """
    目标聚合器
    
    职责：聚合 goal、goal_stats 两个表的数据
    """
    
    def __init__(self):
        self.goal_provider = goal_provider
        self.stats_provider = goal_stats_provider
```

- [ ] **Step 2: 添加获取目标详情方法（聚合 goal + stats）**

```python
    def get_goal_with_stats(
        self, goal_id: str, stats_limit: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        获取目标详情（包含统计数据）
        
        Args:
            goal_id: 目标 ID
            stats_limit: 统计数据条数限制
            
        Returns:
            包含 goal 和 stats 的字典，不存在返回 None
        """
        goal = self.goal_provider.get_goal_by_id(goal_id)
        if not goal:
            return None
        
        # 获取统计数据
        stats = self.stats_provider.get_stats_by_goal(goal_id, limit=stats_limit)
        cumulative_stats = self.stats_provider.get_cumulative_stats(
            goal_id, limit=stats_limit
        )
        
        goal['stats'] = stats
        goal['cumulative_stats'] = cumulative_stats
        
        return goal
```

- [ ] **Step 3: 添加获取目标列表方法（聚合 goal + stats）**

```python
    def get_goals_with_latest_stats(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取目标列表（每个目标包含最新统计）
        
        Args:
            status: 状态过滤
            
        Returns:
            目标列表，每个包含 latest_stat 字段
        """
        goals = self.goal_provider.get_goals(status=status)
        
        # 为每个目标获取最新统计
        for goal in goals:
            stats = self.stats_provider.get_stats_by_goal(goal['id'], limit=1)
            goal['latest_stat'] = stats[0] if stats else None
        
        return goals
```

- [ ] **Step 4: 添加同步目标统计方法（事务性操作）**

```python
    def sync_goal_stats(
        self, goal_id: str, target_date: str, start_date: Optional[str] = None
    ) -> bool:
        """
        同步目标统计数据到指定日期
        
        Args:
            goal_id: 目标 ID
            target_date: 目标日期
            start_date: 开始日期（可选）
            
        Returns:
            是否成功
        """
        # 验证目标存在
        goal = self.goal_provider.get_goal_by_id(goal_id)
        if not goal:
            logger.error(f"目标 {goal_id} 不存在")
            return False
        
        # 同步统计数据
        success = self.stats_provider.sync_stats_to_date(
            goal_id, target_date, start_date
        )
        
        if success:
            logger.info(f"目标 {goal_id} 统计同步成功")
        
        return success
```

- [ ] **Step 5: 验证代码语法**

```bash
python -m py_compile lifeprism/storage/aggregators/goal_aggregator.py
```

Expected: 无输出表示编译成功

- [ ] **Step 6: Commit**

```bash
git add lifeprism/storage/aggregators/goal_aggregator.py
git commit -m "feat(storage): 添加 GoalAggregator 聚合器"
```

---

## Task 5: 创建 HabitChainAggregator

**Files:**
- Create: `lifeprism/storage/aggregators/habit_chain_aggregator.py`

**聚合对象:** HabitChainProvider, HabitChainNodeProvider

- [ ] **Step 1: 创建 HabitChainAggregator 类框架**

```python
"""
HabitChain Aggregator - 习惯链数据聚合层

聚合 HabitChainProvider, HabitChainNodeProvider
提供习惯链相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers import (
    habit_chain_provider,
    habit_chain_node_provider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class HabitChainAggregator:
    """
    习惯链聚合器
    
    职责：聚合 habit_chain、habit_chain_node 两个表的数据
    """
    
    def __init__(self):
        self.chain_provider = habit_chain_provider
        self.node_provider = habit_chain_node_provider
```

- [ ] **Step 2: 添加获取习惯链详情方法（聚合 chain + nodes）**

```python
    def get_chain_with_nodes(self, chain_id: int) -> Optional[Dict[str, Any]]:
        """
        获取习惯链详情（包含所有节点）
        
        Args:
            chain_id: 习惯链 ID
            
        Returns:
            包含 chain 和 nodes 的字典，不存在返回 None
        """
        chain = self.chain_provider.get_chain_by_id(chain_id)
        if not chain:
            return None
        
        # 获取节点列表（包含习惯名称）
        nodes = self.node_provider.get_nodes_with_habit_names(chain_id)
        
        chain['nodes'] = nodes
        chain['node_count'] = len(nodes)
        
        return chain
```

- [ ] **Step 3: 添加获取习惯链列表方法（聚合 chain + nodes）**

```python
    def get_chains_with_nodes(
        self, show_in_timeline: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        获取习惯链列表（每个链包含节点信息）
        
        Args:
            show_in_timeline: 是否在时间线显示
            
        Returns:
            习惯链列表，每个包含 nodes 和 node_count 字段
        """
        chains = self.chain_provider.get_chains(show_in_timeline)
        
        # 为每个链获取节点
        for chain in chains:
            nodes = self.node_provider.get_nodes_with_habit_names(chain['id'])
            chain['nodes'] = nodes
            chain['node_count'] = len(nodes)
        
        return chains
```

- [ ] **Step 4: 添加创建习惯链方法（事务性操作）**

```python
    def create_chain_with_nodes(
        self, chain_data: Dict[str, Any], nodes_data: List[Dict[str, Any]]
    ) -> int:
        """
        创建习惯链并添加节点
        
        Args:
            chain_data: 习惯链数据
            nodes_data: 节点数据列表
            
        Returns:
            新创建的 chain_id
        """
        # 创建习惯链
        chain_id = self.chain_provider.create_chain(chain_data)
        
        # 创建节点
        for i, node_data in enumerate(nodes_data):
            node_data['chain_id'] = chain_id
            node_data['sort_order'] = i
            self.node_provider.create_node(node_data)
        
        logger.info(f"创建习惯链 {chain_id}，包含 {len(nodes_data)} 个节点")
        return chain_id
```

- [ ] **Step 5: 添加删除习惯链方法（级联删除）**

```python
    def delete_chain_with_nodes(self, chain_id: int) -> bool:
        """
        删除习惯链及其所有节点
        
        Args:
            chain_id: 习惯链 ID
            
        Returns:
            是否成功
        """
        # 先获取所有节点
        nodes = self.node_provider.get_nodes_by_chain(chain_id)
        
        # 删除所有节点
        for node in nodes:
            self.node_provider.delete_node(node['id'])
        
        # 删除习惯链
        success = self.chain_provider.delete_chain(chain_id)
        
        if success:
            logger.info(f"删除习惯链 {chain_id} 及其 {len(nodes)} 个节点")
        
        return success
```

- [ ] **Step 6: 验证代码语法**

```bash
python -m py_compile lifeprism/storage/aggregators/habit_chain_aggregator.py
```

Expected: 无输出表示编译成功

- [ ] **Step 7: Commit**

```bash
git add lifeprism/storage/aggregators/habit_chain_aggregator.py
git commit -m "feat(storage): 添加 HabitChainAggregator 聚合器"
```

---

## Task 6: 创建 CategoryAggregator

**Files:**
- Create: `lifeprism/storage/aggregators/category_aggregator.py`

**聚合对象:** CategoryProvider, SubCategoryProvider

- [ ] **Step 1: 创建 CategoryAggregator 类框架**

```python
"""
Category Aggregator - 分类数据聚合层

聚合 CategoryProvider, SubCategoryProvider
提供分类相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers import (
    category_provider,
    sub_category_provider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class CategoryAggregator:
    """
    分类聚合器
    
    职责：聚合 category、sub_category 两个表的数据
    """
    
    def __init__(self):
        self.category_provider = category_provider
        self.sub_category_provider = sub_category_provider
```

- [ ] **Step 2: 添加获取分类详情方法（聚合 category + sub_categories）**

```python
    def get_category_with_subs(self, category_id: str) -> Optional[Dict[str, Any]]:
        """
        获取分类详情（包含所有子分类）
        
        Args:
            category_id: 分类 ID
            
        Returns:
            包含 category 和 sub_categories 的字典，不存在返回 None
        """
        category = self.category_provider.get_category_by_id(category_id)
        if not category:
            return None
        
        # 获取子分类列表
        from lifeprism.storage.providers.common_query_options import QueryOptions
        options = QueryOptions(filters={'category_id': category_id})
        sub_categories, _ = self.sub_category_provider.query_sub_categories(options)
        
        category['sub_categories'] = sub_categories
        category['sub_count'] = len(sub_categories)
        
        return category
```

- [ ] **Step 3: 添加获取分类树方法（聚合 category + sub_categories）**

```python
    def get_category_tree(self) -> List[Dict[str, Any]]:
        """
        获取完整的分类树（所有分类及其子分类）
        
        Returns:
            分类树列表，每个分类包含 sub_categories 字段
        """
        from lifeprism.storage.providers.common_query_options import QueryOptions
        
        # 获取所有分类
        categories, _ = self.category_provider.query_categories(QueryOptions())
        
        # 获取所有子分类
        all_subs, _ = self.sub_category_provider.query_sub_categories(QueryOptions())
        
        # 按 category_id 分组
        subs_by_category = {}
        for sub in all_subs:
            cat_id = sub.get('category_id')
            if cat_id:
                if cat_id not in subs_by_category:
                    subs_by_category[cat_id] = []
                subs_by_category[cat_id].append(sub)
        
        # 为每个分类添加子分类
        for category in categories:
            cat_id = category['id']
            category['sub_categories'] = subs_by_category.get(cat_id, [])
            category['sub_count'] = len(category['sub_categories'])
        
        return categories
```

- [ ] **Step 4: 添加创建分类方法（事务性操作）**

```python
    def create_category_with_subs(
        self, category_data: Dict[str, Any], sub_categories_data: List[Dict[str, Any]] = None
    ) -> str:
        """
        创建分类并可选创建子分类
        
        Args:
            category_data: 分类数据
            sub_categories_data: 子分类数据列表（可选）
            
        Returns:
            新创建的 category_id
        """
        # 创建分类
        success = self.category_provider.insert_category(category_data)
        if not success:
            raise Exception("创建分类失败")
        
        category_id = category_data['id']
        
        # 如果提供了子分类数据，创建子分类
        if sub_categories_data:
            for sub_data in sub_categories_data:
                sub_data['category_id'] = category_id
                self.sub_category_provider.insert_sub_category(sub_data)
        
        logger.info(f"创建分类 {category_id}，包含 {len(sub_categories_data or [])} 个子分类")
        return category_id
```

- [ ] **Step 5: 添加删除分类方法（级联删除）**

```python
    def delete_category_with_subs(self, category_id: str) -> bool:
        """
        删除分类及其所有子分类
        
        Args:
            category_id: 分类 ID
            
        Returns:
            是否成功
        """
        from lifeprism.storage.providers.common_query_options import QueryOptions
        
        # 先获取所有子分类
        options = QueryOptions(filters={'category_id': category_id})
        sub_categories, _ = self.sub_category_provider.query_sub_categories(options)
        
        # 删除所有子分类
        for sub in sub_categories:
            self.sub_category_provider.delete_sub_category(sub['id'])
        
        # 删除分类
        success = self.category_provider.delete_category(category_id)
        
        if success:
            logger.info(f"删除分类 {category_id} 及其 {len(sub_categories)} 个子分类")
        
        return success
```

- [ ] **Step 6: 验证代码语法**

```bash
python -m py_compile lifeprism/storage/aggregators/category_aggregator.py
```

Expected: 无输出表示编译成功

- [ ] **Step 7: Commit**

```bash
git add lifeprism/storage/aggregators/category_aggregator.py
git commit -m "feat(storage): 添加 CategoryAggregator 聚合器"
```

---

## Task 7: 创建 MapCacheAggregator

**Files:**
- Create: `lifeprism/storage/aggregators/map_cache_aggregator.py`

**聚合对象:** MultiPurposeMapCacheProvider, SinglePurposeMapCacheProvider

- [ ] **Step 1: 创建 MapCacheAggregator 类框架**

```python
"""
MapCache Aggregator - 缓存数据聚合层

聚合 MultiPurposeMapCacheProvider, SinglePurposeMapCacheProvider
提供缓存相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers import (
    multi_purpose_map_cache_provider,
    single_purpose_map_cache_provider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class MapCacheAggregator:
    """
    缓存聚合器
    
    职责：聚合 multi_purpose_map_cache、single_purpose_map_cache 两个表的数据
    """
    
    def __init__(self):
        self.multi_provider = multi_purpose_map_cache_provider
        self.single_provider = single_purpose_map_cache_provider
```

- [ ] **Step 2: 添加获取所有缓存方法（聚合两个表）**

```python
    def get_all_caches(self) -> Dict[str, Any]:
        """
        获取所有缓存数据（包含多用途和单用途）
        
        Returns:
            包含 multi_purpose 和 single_purpose 的字典
        """
        from lifeprism.storage.providers.common_query_options import QueryOptions
        
        # 获取多用途缓存
        multi_caches, multi_total = self.multi_provider.query_multi_purpose_map_cache(
            QueryOptions()
        )
        
        # 获取单用途缓存
        single_caches, single_total = self.single_provider.query_single_purpose_map_cache(
            QueryOptions()
        )
        
        return {
            'multi_purpose': multi_caches,
            'single_purpose': single_caches,
            'multi_count': multi_total,
            'single_count': single_total,
            'total_count': multi_total + single_total,
        }
```

- [ ] **Step 3: 添加按用途查找缓存方法**

```python
    def get_cache_by_purpose(
        self, purpose: str, is_multi_purpose: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        按用途查找缓存
        
        Args:
            purpose: 用途标识
            is_multi_purpose: 是否为多用途缓存
            
        Returns:
            缓存数据，不存在返回 None
        """
        from lifeprism.storage.providers.common_query_options import QueryOptions
        
        if is_multi_purpose:
            options = QueryOptions(filters={'purpose': purpose})
            results, _ = self.multi_provider.query_multi_purpose_map_cache(options)
        else:
            options = QueryOptions(filters={'purpose': purpose})
            results, _ = self.single_provider.query_single_purpose_map_cache(options)
        
        return results[0] if results else None
```

- [ ] **Step 4: 添加批量清理缓存方法**

```python
    def clear_all_caches(self) -> Dict[str, int]:
        """
        清理所有缓存
        
        Returns:
            清理统计信息
        """
        from lifeprism.storage.providers.common_query_options import QueryOptions
        
        # 获取所有缓存 ID
        multi_caches, _ = self.multi_provider.query_multi_purpose_map_cache(
            QueryOptions()
        )
        single_caches, _ = self.single_provider.query_single_purpose_map_cache(
            QueryOptions()
        )
        
        # 批量删除
        multi_ids = [c['id'] for c in multi_caches]
        single_ids = [c['id'] for c in single_caches]
        
        multi_deleted = self.multi_provider.batch_delete_multi_purpose_map_cache(multi_ids)
        single_deleted = self.single_provider.batch_delete_single_purpose_map_cache(single_ids)
        
        logger.info(f"清理缓存：多用途 {multi_deleted} 条，单用途 {single_deleted} 条")
        
        return {
            'multi_deleted': multi_deleted,
            'single_deleted': single_deleted,
            'total_deleted': multi_deleted + single_deleted,
        }
```

- [ ] **Step 5: 验证代码语法**

```bash
python -m py_compile lifeprism/storage/aggregators/map_cache_aggregator.py
```

Expected: 无输出表示编译成功

- [ ] **Step 6: Commit**

```bash
git add lifeprism/storage/aggregators/map_cache_aggregator.py
git commit -m "feat(storage): 添加 MapCacheAggregator 聚合器"
```

---

## Task 8: 更新 Aggregators __init__.py 导出

**Files:**
- Modify: `lifeprism/storage/aggregators/__init__.py`

- [ ] **Step 1: 导入所有 Aggregator 类**

```python
"""
Storage Aggregators - 数据聚合层

聚合多个相关 Provider，提供统一的业务数据视图。
"""
from lifeprism.storage.aggregators.habit_aggregator import HabitAggregator
from lifeprism.storage.aggregators.mood_aggregator import MoodAggregator
from lifeprism.storage.aggregators.goal_aggregator import GoalAggregator
from lifeprism.storage.aggregators.habit_chain_aggregator import HabitChainAggregator
from lifeprism.storage.aggregators.category_aggregator import CategoryAggregator
from lifeprism.storage.aggregators.map_cache_aggregator import MapCacheAggregator
from lifeprism.utils import LazySingleton
```

- [ ] **Step 2: 创建全局单例**

```python
# 创建全局单例
habit_aggregator = LazySingleton(HabitAggregator)
mood_aggregator = LazySingleton(MoodAggregator)
goal_aggregator = LazySingleton(GoalAggregator)
habit_chain_aggregator = LazySingleton(HabitChainAggregator)
category_aggregator = LazySingleton(CategoryAggregator)
map_cache_aggregator = LazySingleton(MapCacheAggregator)
```

- [ ] **Step 3: 添加 __all__ 导出列表**

```python
__all__ = [
    # 类
    'HabitAggregator',
    'MoodAggregator',
    'GoalAggregator',
    'HabitChainAggregator',
    'CategoryAggregator',
    'MapCacheAggregator',
    # 单例
    'habit_aggregator',
    'mood_aggregator',
    'goal_aggregator',
    'habit_chain_aggregator',
    'category_aggregator',
    'map_cache_aggregator',
]
```

- [ ] **Step 4: 验证导入**

```bash
python -c "from lifeprism.storage.aggregators import habit_aggregator, mood_aggregator, goal_aggregator, habit_chain_aggregator, category_aggregator, map_cache_aggregator; print('导入成功')"
```

Expected: 输出 "导入成功"

- [ ] **Step 5: Commit**

```bash
git add lifeprism/storage/aggregators/__init__.py
git commit -m "feat(storage): 更新 aggregators 导出所有聚合器单例"
```

---

## Task 9: 更新 Storage __init__.py 统一导出为 Store

**Files:**
- Modify: `lifeprism/storage/__init__.py`

- [ ] **Step 1: 在文件开头添加文档说明**

```python
"""
Storage Layer - 数据访问层统一入口

架构设计：
- Provider: 单表数据访问（内部实现）
- Aggregator: 多表数据聚合（内部实现）
- Store: 统一对外接口（使用 as 重命名）

使用方式：
    from lifeprism.storage import diary_store, habit_store
    
    # 统一的 store 接口，无需区分 provider 或 aggregator
    diaries = diary_store.query_diaries(options)
    habits = habit_store.get_habits_with_challenges()

参考文档：docs/temp/Investigation/2026-04-24-provider-aggregator-architecture-research.md
"""
```

- [ ] **Step 2: 导入单表 Provider 并重命名为 store**

```python
# ==================== 单表 Store（内部是 Provider）====================
from lifeprism.storage.providers import diary_provider as diary_store
from lifeprism.storage.providers import todo_provider as todo_store
from lifeprism.storage.providers import timeline_provider as timeline_store
from lifeprism.storage.providers import plan_doc_provider as plan_doc_store
from lifeprism.storage.providers import tokens_usage_provider as tokens_usage_store
```

- [ ] **Step 3: 导入多表 Aggregator 并重命名为 store**

```python
# ==================== 多表 Store（内部是 Aggregator）====================
from lifeprism.storage.aggregators import habit_aggregator as habit_store
from lifeprism.storage.aggregators import mood_aggregator as mood_store
from lifeprism.storage.aggregators import goal_aggregator as goal_store
from lifeprism.storage.aggregators import habit_chain_aggregator as habit_chain_store
from lifeprism.storage.aggregators import category_aggregator as category_store
from lifeprism.storage.aggregators import map_cache_aggregator as map_cache_store
```

- [ ] **Step 4: 更新 __all__ 导出列表（只导出 store）**

```python
__all__ = [
    # 单表 Store
    'diary_store',
    'todo_store',
    'timeline_store',
    'plan_doc_store',
    'tokens_usage_store',
    # 多表 Store
    'habit_store',
    'mood_store',
    'goal_store',
    'habit_chain_store',
    'category_store',
    'map_cache_store',
]
```

- [ ] **Step 5: 验证统一导出**

```bash
python -c "from lifeprism.storage import diary_store, habit_store, mood_store, goal_store; print('统一 store 导出成功')"
```

Expected: 输出 "统一 store 导出成功"

- [ ] **Step 6: Commit**

```bash
git add lifeprism/storage/__init__.py
git commit -m "feat(storage): 统一导出为 xxx_store 接口"
```

---

## Task 10: 验证完整架构

**Files:**
- Test: 验证所有 store 接口可用

- [ ] **Step 1: 创建验证脚本**

```python
# test_storage_architecture.py
"""验证 Storage 架构重构"""
from lifeprism.storage import (
    # 单表 Store
    diary_store,
    todo_store,
    timeline_store,
    plan_doc_store,
    tokens_usage_store,
    # 多表 Store
    habit_store,
    mood_store,
    goal_store,
    habit_chain_store,
    category_store,
    map_cache_store,
)

def test_single_table_stores():
    """测试单表 Store"""
    print("测试单表 Store...")
    
    # diary_store
    assert hasattr(diary_store, 'query_diaries')
    assert hasattr(diary_store, 'get_diary_by_id')
    print("✓ diary_store")
    
    # todo_store
    assert hasattr(todo_store, 'query_todos')
    print("✓ todo_store")
    
    # timeline_store
    assert hasattr(timeline_store, 'query_timeline')
    print("✓ timeline_store")
    
    # plan_doc_store
    assert hasattr(plan_doc_store, 'query_plan_docs')
    print("✓ plan_doc_store")
    
    # tokens_usage_store
    assert hasattr(tokens_usage_store, 'query_tokens_usage')
    print("✓ tokens_usage_store")

def test_multi_table_stores():
    """测试多表 Store（Aggregator）"""
    print("\n测试多表 Store...")
    
    # habit_store
    assert hasattr(habit_store, 'get_habit_with_challenge')
    assert hasattr(habit_store, 'get_habits_with_challenges')
    print("✓ habit_store")
    
    # mood_store
    assert hasattr(mood_store, 'get_mood_entry_with_type')
    assert hasattr(mood_store, 'get_mood_entries_with_types')
    print("✓ mood_store")
    
    # goal_store
    assert hasattr(goal_store, 'get_goal_with_stats')
    assert hasattr(goal_store, 'get_goals_with_latest_stats')
    print("✓ goal_store")
    
    # habit_chain_store
    assert hasattr(habit_chain_store, 'get_chain_with_nodes')
    assert hasattr(habit_chain_store, 'get_chains_with_nodes')
    print("✓ habit_chain_store")
    
    # category_store
    assert hasattr(category_store, 'get_category_with_subs')
    assert hasattr(category_store, 'get_category_tree')
    print("✓ category_store")
    
    # map_cache_store
    assert hasattr(map_cache_store, 'get_all_caches')
    print("✓ map_cache_store")

if __name__ == '__main__':
    test_single_table_stores()
    test_multi_table_stores()
    print("\n✅ 所有 Store 接口验证通过！")
```

- [ ] **Step 2: 运行验证脚本**

```bash
python test_storage_architecture.py
```

Expected: 输出所有 ✓ 和最后的 "✅ 所有 Store 接口验证通过！"

- [ ] **Step 3: 删除验证脚本**

```bash
rm test_storage_architecture.py
```

- [ ] **Step 4: 验证导入一致性（确保没有命名冲突）**

```bash
python -c "
from lifeprism.storage import diary_store, habit_store
from lifeprism.storage.providers import diary_provider
from lifeprism.storage.aggregators import habit_aggregator

# 验证 store 是 provider/aggregator 的别名
assert diary_store is diary_provider
assert habit_store is habit_aggregator
print('✅ Store 别名验证通过')
"
```

Expected: 输出 "✅ Store 别名验证通过"

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(storage): 验证 Storage 架构重构完成"
```

---

## Task 11: 更新文档

**Files:**
- Create: `docs/coding-rules/storage-layer-usage.md`

- [ ] **Step 1: 创建 Storage 层使用规范文档**

```markdown
# Storage 层使用规范

## 概述

Storage 层采用统一的 `xxx_store` 接口命名，内部实现分为 Provider（单表）和 Aggregator（多表）。

## 架构设计

### 三层架构

```
Provider（原子操作）→ Aggregator（数据聚合）→ Service（业务逻辑）
```

### 统一 Store 接口

对外统一使用 `xxx_store` 命名，隐藏内部实现细节：

- **单表场景**：内部是 Provider，对外命名为 `xxx_store`
- **多表场景**：内部是 Aggregator，对外命名为 `xxx_store`

## 使用方式

### 导入 Store

```python
from lifeprism.storage import diary_store, habit_store, goal_store
```

### 单表 Store（Provider）

```python
# diary_store - 日记数据访问
from lifeprism.storage import diary_store

# 查询日记
diaries, total = diary_store.query_diaries(options)

# 获取单条日记
diary = diary_store.get_diary_by_id(date)
```

### 多表 Store（Aggregator）

```python
# habit_store - 习惯数据聚合
from lifeprism.storage import habit_store

# 获取习惯详情（包含挑战信息）
habit = habit_store.get_habit_with_challenge(habit_id)

# 获取习惯列表（每个包含挑战）
habits = habit_store.get_habits_with_challenges(status='active')
```

## Store 列表

### 单表 Store

| Store 名称 | 内部实现 | 对应表 | 说明 |
|-----------|---------|-------|------|
| `diary_store` | DiaryProvider | diary | 日记数据 |
| `todo_store` | TodoProvider | todos | 待办事项 |
| `timeline_store` | TimelineProvider | timeline | 时间线 |
| `plan_doc_store` | PlanDocProvider | plan_docs | 计划文档 |
| `tokens_usage_store` | TokensUsageProvider | tokens_usage_log | Token 使用记录 |

### 多表 Store

| Store 名称 | 内部实现 | 聚合表 | 说明 |
|-----------|---------|-------|------|
| `habit_store` | HabitAggregator | habits, habit_challenges, habit_checkins | 习惯数据聚合 |
| `mood_store` | MoodAggregator | mood_types, mood_entries, mood_impacts | 心情数据聚合 |
| `goal_store` | GoalAggregator | goals, goal_stats | 目标数据聚合 |
| `habit_chain_store` | HabitChainAggregator | habit_chains, habit_chain_nodes | 习惯链数据聚合 |
| `category_store` | CategoryAggregator | categories, sub_categories | 分类数据聚合 |
| `map_cache_store` | MapCacheAggregator | multi_purpose_map_cache, single_purpose_map_cache | 缓存数据聚合 |

## 编码规范

### 1. 统一使用 Store 接口

✅ **正确**：
```python
from lifeprism.storage import diary_store, habit_store
```

❌ **错误**：
```python
# 不要直接导入 provider 或 aggregator
from lifeprism.storage.providers import diary_provider
from lifeprism.storage.aggregators import habit_aggregator
```

### 2. 不要混用 Provider/Aggregator 和 Store

✅ **正确**：
```python
from lifeprism.storage import habit_store

habits = habit_store.get_habits_with_challenges()
```

❌ **错误**：
```python
from lifeprism.storage.providers import habit_provider
from lifeprism.storage.aggregators import habit_aggregator

# 混用会导致混乱
habits = habit_provider.get_habits()
habit = habit_aggregator.get_habit_with_challenge(habit_id)
```

### 3. Service 层只依赖 Store

Service 层应该只导入和使用 Store 接口：

```python
# lifeprism/server/services/habit_service.py
from lifeprism.storage import habit_store

class HabitService:
    def get_habit_details(self, habit_id: str):
        return habit_store.get_habit_with_challenge(habit_id)
```

## 内部实现说明

### Provider（单表数据访问）

- 位置：`lifeprism/storage/providers/`
- 职责：提供单表的 CRUD 操作
- 特点：原子操作，可复用

### Aggregator（多表数据聚合）

- 位置：`lifeprism/storage/aggregators/`
- 职责：聚合多个 Provider，提供统一的业务数据视图
- 特点：组合多个 Provider，包含聚合逻辑

## 参考文档

- 架构设计调查报告：`docs/temp/Investigation/2026-04-24-provider-aggregator-architecture-research.md`
- 重构原因说明：`docs/temp/refactor-repository-architecture-draft/reason-and-new-architecture.md`
```

- [ ] **Step 2: 验证文档格式**

```bash
cat docs/coding-rules/storage-layer-usage.md | head -20
```

Expected: 看到文档开头内容

- [ ] **Step 3: Commit**

```bash
git add docs/coding-rules/storage-layer-usage.md
git commit -m "docs(storage): 添加 Storage 层使用规范文档"
```

---

## 完成总结

完成后，架构将具备以下特性：

1. ✅ **统一接口**：所有数据访问都使用 `xxx_store` 命名
2. ✅ **内部清晰**：Provider 处理单表，Aggregator 处理多表
3. ✅ **符合 YAGNI**：不创建透传层，使用 `as` 重命名
4. ✅ **AI 友好**：接口正交化，动作空间最小化
5. ✅ **易于维护**：职责明确，扩展方便

**预期工作量**：2-3 天

**文件统计**：
- 新建：7 个文件（6 个 aggregator + 1 个文档）
- 修改：2 个文件（storage/__init__.py, aggregators/__init__.py）

---

