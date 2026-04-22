# 数据密度计算工具函数提取完成

## 完成内容

### 1. 创建工具函数模块

**文件**: `lifeprism/llm/utils/density_utils.py`

提取了以下函数：

- `compute_bucket_density()` - 计算时间桶内的活动密度
- `build_time_segments()` - 识别并构建高密度时间段列表
- `_to_dt()` - 时间格式转换辅助函数
- `_collect_buckets()` - 时间桶切分辅助函数
- `_build_segment_item()` - 构建时间段信息辅助函数

### 2. 函数特性

- **纯函数设计**: 所有函数接收数据作为参数，不自行访问数据库
- **可配置参数**: `bucket_minutes`、`max_bridge_buckets` 等参数可自定义
- **完整文档**: 包含 Google 风格的文档字符串和类型注解
- **向后兼容**: 不修改 `activity_aggregator.py`，保持原有代码不变

### 3. 导出配置

**文件**: `lifeprism/llm/utils/__init__.py`

已将函数添加到 `__all__` 列表，可通过以下方式导入：

```python
from lifeprism.llm.utils import compute_bucket_density, build_time_segments
```

### 4. 测试验证

**文件**: `test/core/unit/llm/test_utils.py`

创建了完整的测试套件，包括：

- **基础功能测试** (5个测试)
  - 空日志测试
  - 完全覆盖测试
  - 部分覆盖测试
  - 多日志重叠测试
  - 日志在时间桶外测试

- **时间段识别测试** (4个测试)
  - 空日志测试
  - 单个高密度时间段测试
  - 过滤短时间段测试
  - 自定义段类型测试

- **一致性验证测试** (3个测试)
  - 默认参数一致性测试
  - 自定义参数一致性测试
  - 真实场景一致性测试

**测试结果**: ✅ 12/12 测试全部通过

### 5. 使用示例

**文件**: `test/explore/monitor_prompt/density_utils_example.py`

提供了三个使用示例：
1. 计算时间桶密度
2. 识别高密度时间段
3. 截图分析场景（模拟 screenshot_analysis_v2.py）

## 使用方法

```python
from lifeprism.llm.utils import build_time_segments

# 获取高密度时间段
segments = build_time_segments(
    logs=activity_logs,  # 活动日志列表
    range_start="2026-04-19 00:00:00",
    range_end="2026-04-20 18:00:00",
    threshold=0.6,  # 密度阈值 60%
    min_duration_minutes=6,  # 最小时长 6 分钟
    bucket_minutes=10,  # 时间桶大小 10 分钟
    max_bridge_buckets=0  # 不允许桥接
)

# 遍历时间段
for seg in segments:
    print(f"{seg['start']} -> {seg['end']}")
    print(f"时长: {seg['duration_seconds']} 秒")
```

## 与原有代码的一致性

通过测试验证，新工具函数与 `activity_aggregator._build_segments()` 在相同参数下输出完全一致：
- 时间段数量相同
- 每个时间段的 start、end、duration_seconds 完全匹配
- segment_type 标识一致

## 下一步

可以在 `screenshot_analysis_v2.py` 中使用这些工具函数替换直接调用 `_build_segments` 的代码。
