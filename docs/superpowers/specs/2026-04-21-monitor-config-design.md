# 监控频率配置化设计

**日期**: 2026-04-21  
**状态**: 设计完成，待实现

## 概述

将监控频率等级和截图保留天数从硬编码改为可配置项，支持用户在前端设置页面调整，并通过配置迁移脚本实现平滑升级。

## 需求

1. 在config中添加频率等级配置（`active_screenshot_frequency_level`，默认2）
2. 在config中添加截图保留天数配置（`screenshot_retention_days`，默认7天，最小3天）
3. 编写yaml配置迁移脚本
4. 在前端设置页面添加这两个配置项
5. 实现完整的前后端交互回路

## 设计方案

### 1. 后端配置层

#### 修改 `settings_manager.py` 的 DEFAULTS

```python
DEFAULTS = {
    # ... 现有配置 ...
    'active_screenshot_frequency_level': 2,  # 已存在，保持默认值2
    'screenshot_retention_days': 7,  # 修改默认值：3 → 7
}
```

#### 添加配置验证

在 `SettingsManager.update()` 方法中添加验证逻辑：

```python
def update(self, updates: dict) -> None:
    # 验证 screenshot_retention_days
    if 'screenshot_retention_days' in updates:
        days = updates['screenshot_retention_days']
        if days < 3:
            raise ValueError(f"截图保留天数不能小于3天，当前值：{days}")
    
    # 验证 active_screenshot_frequency_level
    if 'active_screenshot_frequency_level' in updates:
        level = updates['active_screenshot_frequency_level']
        if level not in [1, 2, 3]:
            raise ValueError(f"频率等级必须是1、2或3，当前值：{level}")
    
    # ... 原有逻辑 ...
```

**验证策略**：
- 仅后端验证，前端不做强制限制
- 如果验证失败，raise错误返回给前端
- 最小保留天数硬编码为3天，便于后续统一修改

#### 修改 `runtime.py` 中的硬编码

**当前代码**：
```python
cleanup_worker = ScreenshotCleanupWorker(
    provider=screenshot_provider,
    data_root=Path(settings.lifeprism_data_path),
    retention_days=3,  # 硬编码
)
```

**修改为**：
```python
cleanup_worker = ScreenshotCleanupWorker(
    provider=screenshot_provider,
    data_root=Path(settings.lifeprism_data_path),
    retention_days=settings.get("screenshot_retention_days", 7),
)
```

---

### 2. 配置迁移脚本

#### 新增迁移文件

**文件路径**: `lifeprism/config/migrations/scripts/s004_add_monitor_config.py`

```python
"""
配置迁移 s004: 添加监控配置项

添加字段:
- active_screenshot_frequency_level: 截图频率等级 (默认2)
- screenshot_retention_days: 截图保留天数 (默认7)
"""

VERSION = 4
NAME = "s004_add_monitor_config"


def check_if_applied(data: dict) -> bool:
    """检查迁移是否已应用"""
    return (
        'active_screenshot_frequency_level' in data 
        and 'screenshot_retention_days' in data
    )


def upgrade(data: dict) -> dict:
    """执行迁移"""
    if 'active_screenshot_frequency_level' not in data:
        data['active_screenshot_frequency_level'] = 2
    
    if 'screenshot_retention_days' not in data:
        data['screenshot_retention_days'] = 7
    
    return data
```

#### 注册迁移

在 `lifeprism/config/migrations/scripts/__init__.py` 中注册：

```python
from . import s001_baseline, s002_add_monitor_type, s003_add_vlm_fields, s004_add_monitor_config, p001_baseline

# settings.yaml 迁移列表（按 VERSION 升序）
SETTINGS_MIGRATIONS = [
    s001_baseline,
    s002_add_monitor_type,
    s003_add_vlm_fields,
    s004_add_monitor_config,  # 新增
]
```

**说明**：
- 迁移脚本已在 `settings_manager._load_config()` 中自动执行
- 只需创建迁移文件并在 `__init__.py` 中注册即可

---

### 3. API层

**无需修改**，`setting_schemas.py` 已包含这两个字段：
- `active_screenshot_frequency_level: int`
- `screenshot_retention_days: int`

`UpdateSettingsRequest` 也已支持这两个字段的更新。

---

### 4. 前端UI设计

#### 添加状态

在 `SettingsApp.tsx` 中添加状态（第78行附近）：

```typescript
// 6. Screenshot Monitor
const [screenshotMonitor, setScreenshotMonitor] = useState(false);
const [screenshotFrequencyLevel, setScreenshotFrequencyLevel] = useState(2);
const [screenshotRetentionDays, setScreenshotRetentionDays] = useState(7);
const [isVlmTesting, setIsVlmTesting] = useState(false);
```

#### 加载配置

在 `loadSettings()` 中加载（第176行附近）：

```typescript
setScreenshotMonitor(settings.screenshot_monitor || false);
setScreenshotFrequencyLevel(settings.active_screenshot_frequency_level || 2);
setScreenshotRetentionDays(settings.screenshot_retention_days || 7);
```

#### 更新自动保存依赖

在 `triggerAutoSave` 中添加新字段（第221行附近）：

```typescript
const triggerAutoSave = useCallback((overrides: Record<string, unknown> = {}) => {
    const currentSettings = {
        // ... 现有字段 ...
        active_screenshot_frequency_level: screenshotFrequencyLevel,
        screenshot_retention_days: screenshotRetentionDays,
        ...overrides,
    };
    debouncedSave(currentSettings);
}, [
    // ... 现有依赖 ...
    screenshotFrequencyLevel, 
    screenshotRetentionDays, 
    debouncedSave
]);
```

#### UI组件

在"截图监控"section内添加（第1056行之前）：

**截图频率等级（单选按钮组）**：
```tsx
<div className="space-y-3">
    <h4 className="text-sm font-bold text-slate-700">截图频率等级</h4>
    
    <div className="space-y-2">
        {/* L1 - 低频 */}
        <label className="flex items-start gap-3 p-4 bg-gray-50 rounded-xl border border-gray-100 cursor-pointer hover:border-blue-300 transition-all">
            <input
                type="radio"
                name="frequency"
                value={1}
                checked={screenshotFrequencyLevel === 1}
                onChange={(e) => {
                    const newLevel = Number(e.target.value);
                    setScreenshotFrequencyLevel(newLevel);
                    triggerAutoSave({ active_screenshot_frequency_level: newLevel });
                }}
                className="mt-1"
            />
            <div className="flex-1">
                <div className="text-sm font-bold text-slate-700">低频(L1) - 节省存储和tokens使用</div>
                <div className="text-xs text-slate-400 mt-1">
                    测试数据：高活跃度5.5小时，约70张截图，tokens约11万
                </div>
            </div>
        </label>

        {/* L2 - 中频（推荐） */}
        <label className="flex items-start gap-3 p-4 bg-gray-50 rounded-xl border border-gray-100 cursor-pointer hover:border-blue-300 transition-all">
            <input
                type="radio"
                name="frequency"
                value={2}
                checked={screenshotFrequencyLevel === 2}
                onChange={(e) => {
                    const newLevel = Number(e.target.value);
                    setScreenshotFrequencyLevel(newLevel);
                    triggerAutoSave({ active_screenshot_frequency_level: newLevel });
                }}
                className="mt-1"
            />
            <div className="flex-1">
                <div className="text-sm font-bold text-slate-700">中频(L2) - 推荐，平衡语义质量、存储和tokens使用</div>
                <div className="text-xs text-slate-400 mt-1">
                    测试数据：高活跃度5.5小时，约95张截图，tokens约15万
                </div>
            </div>
        </label>

        {/* L3 - 高频 */}
        <label className="flex items-start gap-3 p-4 bg-gray-50 rounded-xl border border-gray-100 cursor-pointer hover:border-blue-300 transition-all">
            <input
                type="radio"
                name="frequency"
                value={3}
                checked={screenshotFrequencyLevel === 3}
                onChange={(e) => {
                    const newLevel = Number(e.target.value);
                    setScreenshotFrequencyLevel(newLevel);
                    triggerAutoSave({ active_screenshot_frequency_level: newLevel });
                }}
                className="mt-1"
            />
            <div className="flex-1">
                <div className="text-sm font-bold text-slate-700">高频(L3) - 高精度，适合需要详细记录的场景</div>
                <div className="text-xs text-slate-400 mt-1">
                    测试数据：高活跃度5.5小时，约200张截图，tokens约32万
                </div>
            </div>
        </label>
    </div>
</div>
```

**截图保留天数（数字输入框 + 加减按钮）**：
```tsx
<div className="flex items-center gap-4 bg-gray-50 p-4 rounded-xl border border-gray-100">
    <div className="flex-1">
        <h4 className="text-sm font-bold text-slate-700">截图保留天数</h4>
        <p className="text-xs text-slate-400 mt-1">最小3天，超过保留期的截图将被自动清理</p>
    </div>
    <div className="flex items-center gap-2">
        <button
            onClick={() => {
                const newValue = Math.max(3, screenshotRetentionDays - 1);
                setScreenshotRetentionDays(newValue);
                triggerAutoSave({ screenshot_retention_days: newValue });
            }}
            className="w-8 h-8 flex items-center justify-center rounded-lg bg-white border border-gray-200 text-slate-500 hover:border-blue-300 hover:text-blue-600 transition-all"
        >
            <Minus size={14} />
        </button>

        <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-lg border border-gray-200 shadow-sm w-24 justify-center">
            <input
                type="number"
                min="3"
                value={screenshotRetentionDays}
                onChange={(e) => {
                    const value = parseInt(e.target.value) || 3;
                    setScreenshotRetentionDays(Math.max(3, value));
                }}
                onBlur={() => triggerAutoSave({ screenshot_retention_days: screenshotRetentionDays })}
                className="w-full text-center font-bold text-slate-800 outline-none bg-transparent"
            />
        </div>

        <button
            onClick={() => {
                const newValue = screenshotRetentionDays + 1;
                setScreenshotRetentionDays(newValue);
                triggerAutoSave({ screenshot_retention_days: newValue });
            }}
            className="w-8 h-8 flex items-center justify-center rounded-lg bg-white border border-gray-200 text-slate-500 hover:border-blue-300 hover:text-blue-600 transition-all"
        >
            <Plus size={14} />
        </button>

        <span className="text-xs font-bold text-slate-400 uppercase ml-1">天</span>
    </div>
</div>
```

---

### 5. 前后端交互流程

#### 加载流程
1. 前端调用 `SettingsAPI.getSettings()`
2. 后端返回包含 `active_screenshot_frequency_level` 和 `screenshot_retention_days` 的配置
3. 前端更新状态

#### 保存流程
1. 用户修改配置（单选按钮或输入框）
2. 前端调用 `triggerAutoSave()` 自动保存
3. 后端验证配置（`screenshot_retention_days >= 3`，`active_screenshot_frequency_level in [1,2,3]`）
4. 验证通过：保存到yaml，返回成功
5. 验证失败：raise错误，前端显示toast错误提示

#### 错误处理
```typescript
try {
    await SettingsAPI.updateSettings(updates);
    toast.success('保存成功');
} catch (error) {
    // 后端验证失败（如 retention_days < 3）
    toast.error(error.message || '保存失败');
}
```

---

## 测试数据说明

基于 `test/explore/monitor_prompt/frequency_comparison_report.txt` 的测试结果：

- **测试环境**：engaged时长97分钟，430个segment
- **换算到5.5小时高活跃度**：系数 ≈ 3.4倍

| 等级 | Active截图 | Tokens估算 | 说明 |
|------|-----------|-----------|------|
| L1 | 约70张 | 约11万 | 节省存储和tokens |
| L2 | 约95张 | 约15万 | 推荐，平衡质量和成本 |
| L3 | 约200张 | 约32万 | 高精度，详细记录 |

---

## 实现清单

### 后端
- [ ] 修改 `settings_manager.py` 的 `DEFAULTS`（`screenshot_retention_days: 7`）
- [ ] 在 `settings_manager.update()` 中添加验证逻辑
- [ ] 修改 `runtime.py` 中的硬编码（`retention_days=settings.get(...)`）
- [ ] 创建迁移文件 `s004_add_monitor_config.py`
- [ ] 在 `migrations/scripts/__init__.py` 中注册迁移

### 前端
- [ ] 添加状态：`screenshotFrequencyLevel`, `screenshotRetentionDays`
- [ ] 在 `loadSettings()` 中加载配置
- [ ] 更新 `triggerAutoSave` 依赖数组
- [ ] 添加UI组件：频率等级单选按钮组
- [ ] 添加UI组件：保留天数输入框

### 测试
- [ ] 测试配置迁移（旧配置文件升级）
- [ ] 测试后端验证（`retention_days < 3` 应报错）
- [ ] 测试前端UI交互（单选按钮、输入框）
- [ ] 测试自动保存功能
- [ ] 测试错误提示显示

---

## 风险与注意事项

1. **配置迁移**：确保旧版本配置文件能平滑升级，不影响用户使用
2. **验证逻辑**：后端验证必须严格，防止无效配置导致系统异常
3. **前端最小值**：前端使用 `Math.max(3, value)` 限制最小值，但最终验证在后端
4. **自动保存**：使用 `triggerAutoSave` 而不是手动调用API，保持与现有代码一致
5. **依赖数组**：确保 `triggerAutoSave` 的依赖数组包含新增的状态

---

## 后续优化

1. 考虑添加"预估存储空间"提示，帮助用户选择合适的保留天数
2. 考虑添加"一键清理历史截图"功能
3. 考虑添加频率等级的实时预览（显示当前等级的具体参数）
