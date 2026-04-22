# 监控频率配置化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将监控频率等级和截图保留天数从硬编码改为可配置项，支持前端设置和配置迁移

**Architecture:** 后端添加配置验证，创建迁移脚本自动升级旧配置，前端添加UI组件实现完整交互回路

**Tech Stack:** Python (后端配置/迁移), TypeScript/React (前端UI), YAML (配置文件)

---

## 文件结构

### 后端文件
- **Modify**: `lifeprism/config/settings_manager.py:57` - 修改 DEFAULTS 中的 screenshot_retention_days
- **Modify**: `lifeprism/config/settings_manager.py:220-250` - 添加配置验证逻辑
- **Modify**: `lifeprism/monitor/windows_monitor/runtime.py:108` - 修改测试代码硬编码
- **Create**: `lifeprism/config/migrations/scripts/s004_add_monitor_config.py` - 配置迁移脚本
- **Modify**: `lifeprism/config/migrations/scripts/__init__.py:7,10-14` - 注册迁移脚本

### 前端文件
- **Modify**: `frontend/apps/settings/SettingsApp.tsx:78-82` - 添加状态
- **Modify**: `frontend/apps/settings/SettingsApp.tsx:176-178` - 加载配置
- **Modify**: `frontend/apps/settings/SettingsApp.tsx:204-221` - 更新 triggerAutoSave
- **Modify**: `frontend/apps/settings/SettingsApp.tsx:1056` - 添加UI组件

### 测试文件
- **Create**: `test/core/unit/config/test_settings_validation.py` - 配置验证测试
- **Create**: `test/core/unit/config/test_migration_s004.py` - 迁移脚本测试

---

### Task 1: 修改后端配置默认值

**Files:**
- Modify: `lifeprism/config/settings_manager.py:57`

- [ ] **Step 1: 修改 screenshot_retention_days 默认值**

在 `settings_manager.py` 第57行，将 `screenshot_retention_days` 的默认值从 3 改为 7：

```python
'screenshot_retention_days': 7,
```

- [ ] **Step 2: 验证修改**

运行：`grep -n "screenshot_retention_days" lifeprism/config/settings_manager.py`

预期输出：包含 `'screenshot_retention_days': 7,`

- [ ] **Step 3: 提交**

```bash
git add lifeprism/config/settings_manager.py
git commit -m "config: 修改截图保留天数默认值为7天

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 添加配置验证逻辑

**Files:**
- Modify: `lifeprism/config/settings_manager.py:220-250`
- Create: `test/core/unit/config/test_settings_validation.py`

- [ ] **Step 1: 编写验证测试**

创建 `test/core/unit/config/test_settings_validation.py`：

```python
"""测试配置验证逻辑"""
import pytest
from lifeprism.config.settings_manager import SettingsManager


def test_screenshot_retention_days_validation():
    """测试截图保留天数验证"""
    settings = SettingsManager()
    
    # 测试小于3天应该报错
    with pytest.raises(ValueError, match="截图保留天数不能小于3天"):
        settings.update({'screenshot_retention_days': 2})
    
    # 测试等于3天应该通过
    settings.update({'screenshot_retention_days': 3})
    assert settings.get('screenshot_retention_days') == 3
    
    # 测试大于3天应该通过
    settings.update({'screenshot_retention_days': 7})
    assert settings.get('screenshot_retention_days') == 7


def test_frequency_level_validation():
    """测试频率等级验证"""
    settings = SettingsManager()
    
    # 测试无效等级应该报错
    with pytest.raises(ValueError, match="频率等级必须是1、2或3"):
        settings.update({'active_screenshot_frequency_level': 0})
    
    with pytest.raises(ValueError, match="频率等级必须是1、2或3"):
        settings.update({'active_screenshot_frequency_level': 4})
    
    # 测试有效等级应该通过
    for level in [1, 2, 3]:
        settings.update({'active_screenshot_frequency_level': level})
        assert settings.get('active_screenshot_frequency_level') == level
```

- [ ] **Step 2: 运行测试确认失败**

运行：`PYTHONPATH=. pytest test/core/unit/config/test_settings_validation.py -v`

预期：FAIL（验证逻辑尚未实现）

- [ ] **Step 3: 添加验证逻辑**

在 `settings_manager.py` 的 `update()` 方法开头添加验证（约第220行）：

```python
def update(self, updates: dict) -> None:
    """更新配置项（部分更新）"""
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

- [ ] **Step 4: 运行测试确认通过**

运行：`PYTHONPATH=. pytest test/core/unit/config/test_settings_validation.py -v`

预期：PASS（所有测试通过）

- [ ] **Step 5: 提交**

```bash
git add lifeprism/config/settings_manager.py test/core/unit/config/test_settings_validation.py
git commit -m "feat(config): 添加配置验证逻辑

- 验证截图保留天数 >= 3
- 验证频率等级 in [1,2,3]
- 添加单元测试

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 创建配置迁移脚本

**Files:**
- Create: `lifeprism/config/migrations/scripts/s004_add_monitor_config.py`
- Create: `test/core/unit/config/test_migration_s004.py`

- [ ] **Step 1: 编写迁移测试**

创建 `test/core/unit/config/test_migration_s004.py`：

```python
"""测试 s004 配置迁移"""
from lifeprism.config.migrations.scripts import s004_add_monitor_config


def test_check_if_applied_both_fields_exist():
    """测试两个字段都存在时，迁移已应用"""
    data = {
        'active_screenshot_frequency_level': 2,
        'screenshot_retention_days': 7,
    }
    assert s004_add_monitor_config.check_if_applied(data) is True


def test_check_if_applied_missing_fields():
    """测试缺少字段时，迁移未应用"""
    assert s004_add_monitor_config.check_if_applied({}) is False
    assert s004_add_monitor_config.check_if_applied({'active_screenshot_frequency_level': 2}) is False
    assert s004_add_monitor_config.check_if_applied({'screenshot_retention_days': 7}) is False


def test_upgrade_adds_missing_fields():
    """测试迁移添加缺失字段"""
    data = {}
    result = s004_add_monitor_config.upgrade(data)
    
    assert result['active_screenshot_frequency_level'] == 2
    assert result['screenshot_retention_days'] == 7


def test_upgrade_preserves_existing_fields():
    """测试迁移保留已存在的字段"""
    data = {
        'active_screenshot_frequency_level': 1,
        'screenshot_retention_days': 10,
        'other_field': 'value',
    }
    result = s004_add_monitor_config.upgrade(data)
    
    assert result['active_screenshot_frequency_level'] == 1
    assert result['screenshot_retention_days'] == 10
    assert result['other_field'] == 'value'
```

- [ ] **Step 2: 运行测试确认失败**

运行：`PYTHONPATH=. pytest test/core/unit/config/test_migration_s004.py -v`

预期：FAIL（迁移脚本尚未创建）

- [ ] **Step 3: 创建迁移脚本**

创建 `lifeprism/config/migrations/scripts/s004_add_monitor_config.py`：

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

- [ ] **Step 4: 运行测试确认通过**

运行：`PYTHONPATH=. pytest test/core/unit/config/test_migration_s004.py -v`

预期：PASS（所有测试通过）

- [ ] **Step 5: 提交**

```bash
git add lifeprism/config/migrations/scripts/s004_add_monitor_config.py test/core/unit/config/test_migration_s004.py
git commit -m "feat(migration): 添加 s004 配置迁移脚本

添加监控配置项的迁移逻辑和测试

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 注册迁移脚本

**Files:**
- Modify: `lifeprism/config/migrations/scripts/__init__.py:7,10-14`

- [ ] **Step 1: 修改 import 语句**

在 `__init__.py` 第7行，添加 `s004_add_monitor_config` 到 import：

```python
from . import s001_baseline, s002_add_monitor_type, s003_add_vlm_fields, s004_add_monitor_config, p001_baseline
```

- [ ] **Step 2: 注册到迁移列表**

在 `SETTINGS_MIGRATIONS` 列表中添加（第10-14行）：

```python
SETTINGS_MIGRATIONS = [
    s001_baseline,
    s002_add_monitor_type,
    s003_add_vlm_fields,
    s004_add_monitor_config,
]
```

- [ ] **Step 3: 验证导入**

运行：`PYTHONPATH=. python -c "from lifeprism.config.migrations.scripts import SETTINGS_MIGRATIONS; print(len(SETTINGS_MIGRATIONS))"`

预期输出：`4`

- [ ] **Step 4: 提交**

```bash
git add lifeprism/config/migrations/scripts/__init__.py
git commit -m "feat(migration): 注册 s004 迁移脚本

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 修改测试代码硬编码

**Files:**
- Modify: `lifeprism/monitor/windows_monitor/runtime.py:108`

- [ ] **Step 1: 修改测试代码中的硬编码**

在 `runtime.py` 第108行，将硬编码的 `retention_days=3` 改为使用配置：

```python
cleanup_worker = ScreenshotCleanupWorker(
    provider=screenshot_provider,
    data_root=data_root,
    retention_days=settings.get("screenshot_retention_days", 7),
)
```

- [ ] **Step 2: 验证修改**

运行：`grep -n "retention_days=" lifeprism/monitor/windows_monitor/runtime.py`

预期输出：两处都使用 `settings.get("screenshot_retention_days", 7)`

- [ ] **Step 3: 运行相关测试**

运行：`PYTHONPATH=. pytest test/core/unit/monitor/ -v -k runtime`

预期：PASS（测试通过）

- [ ] **Step 4: 提交**

```bash
git add lifeprism/monitor/windows_monitor/runtime.py
git commit -m "refactor(monitor): 移除测试代码中的硬编码

使用配置项替代硬编码的 retention_days

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: 前端添加状态

**Files:**
- Modify: `frontend/apps/settings/SettingsApp.tsx:78-82`

- [ ] **Step 1: 添加状态声明**

在 `SettingsApp.tsx` 第78行附近（`// 6. Screenshot Monitor` 注释后），添加两个新状态：

```typescript
// 6. Screenshot Monitor
const [screenshotMonitor, setScreenshotMonitor] = useState(false);
const [screenshotFrequencyLevel, setScreenshotFrequencyLevel] = useState(2);
const [screenshotRetentionDays, setScreenshotRetentionDays] = useState(7);
const [isVlmTesting, setIsVlmTesting] = useState(false);
```

- [ ] **Step 2: 验证语法**

运行：`cd frontend && npm run type-check`

预期：无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/apps/settings/SettingsApp.tsx
git commit -m "feat(frontend): 添加监控配置状态

添加 screenshotFrequencyLevel 和 screenshotRetentionDays 状态

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 前端加载配置

**Files:**
- Modify: `frontend/apps/settings/SettingsApp.tsx:176-178`

- [ ] **Step 1: 在 loadSettings 中加载配置**

在 `SettingsApp.tsx` 第176行附近（`setScreenshotMonitor` 之后），添加两行：

```typescript
setScreenshotMonitor(settings.screenshot_monitor || false);
setScreenshotFrequencyLevel(settings.active_screenshot_frequency_level || 2);
setScreenshotRetentionDays(settings.screenshot_retention_days || 7);
```

- [ ] **Step 2: 验证语法**

运行：`cd frontend && npm run type-check`

预期：无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/apps/settings/SettingsApp.tsx
git commit -m "feat(frontend): 加载监控配置

在 loadSettings 中加载频率等级和保留天数

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: 前端更新自动保存依赖

**Files:**
- Modify: `frontend/apps/settings/SettingsApp.tsx:204-221`

- [ ] **Step 1: 在 triggerAutoSave 中添加新字段**

在 `SettingsApp.tsx` 第204行附近的 `triggerAutoSave` 函数中，添加两个字段到 `currentSettings`：

```typescript
const triggerAutoSave = useCallback((overrides: Record<string, unknown> = {}) => {
    const currentSettings = {
        user_name: nickname,
        provider: provider,
        model: modelName,
        api_base: apiBase,
        input_tokens_cost: costInput,
        output_tokens_cost: costOutput,
        classification_mode: classificationMode === 'complex' ? 'classify_graph' : 'classify_simple',
        long_log_threshold: longLogThreshold,
        multi_purpose_app_names: browserApps,
        aw_db_path: awPath,
        lifeprism_data_path: lifeprismDataPath,
        data_cleaning_threshold: filterDuration,
        active_screenshot_frequency_level: screenshotFrequencyLevel,
        screenshot_retention_days: screenshotRetentionDays,
        ...overrides,
    };
    debouncedSave(currentSettings);
}, [nickname, provider, modelName, apiBase, costInput, costOutput, classificationMode, longLogThreshold, browserApps, awPath, lifeprismDataPath, filterDuration, screenshotFrequencyLevel, screenshotRetentionDays, debouncedSave]);
```

- [ ] **Step 2: 验证语法**

运行：`cd frontend && npm run type-check`

预期：无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/apps/settings/SettingsApp.tsx
git commit -m "feat(frontend): 更新自动保存依赖

添加频率等级和保留天数到自动保存

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: 前端添加频率等级UI组件

**Files:**
- Modify: `frontend/apps/settings/SettingsApp.tsx:1056`

- [ ] **Step 1: 在截图监控section添加频率等级UI**

在 `SettingsApp.tsx` 第1056行之前（`</section>` 标签之前），添加频率等级单选按钮组：

```tsx
{/* 截图频率等级 */}
<div className="space-y-3">
    <h4 className="text-sm font-bold text-slate-700">截图频率等级</h4>
    
    <div className="space-y-2">
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

- [ ] **Step 2: 验证语法**

运行：`cd frontend && npm run type-check`

预期：无类型错误

- [ ] **Step 3: 启动前端验证UI**

运行：`cd frontend && npm run dev`

在浏览器中打开设置页面，验证：
- 频率等级单选按钮显示正常
- 默认选中L2
- 点击切换等级时状态更新

- [ ] **Step 4: 提交**

```bash
git add frontend/apps/settings/SettingsApp.tsx
git commit -m "feat(frontend): 添加频率等级UI组件

添加L1/L2/L3单选按钮组，包含测试数据说明

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: 前端添加保留天数UI组件

**Files:**
- Modify: `frontend/apps/settings/SettingsApp.tsx:1056`

- [ ] **Step 1: 在截图监控section添加保留天数UI**

在 `SettingsApp.tsx` 第1056行之前（频率等级UI之后），添加保留天数输入框：

```tsx
{/* 截图保留天数 */}
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

- [ ] **Step 2: 验证语法**

运行：`cd frontend && npm run type-check`

预期：无类型错误

- [ ] **Step 3: 启动前端验证UI**

运行：`cd frontend && npm run dev`

在浏览器中打开设置页面，验证：
- 保留天数输入框显示正常
- 默认值为7
- 点击加减按钮时值正确变化
- 最小值限制为3（点击减号到3时不再减少）
- 手动输入小于3的值时自动修正为3

- [ ] **Step 4: 提交**

```bash
git add frontend/apps/settings/SettingsApp.tsx
git commit -m "feat(frontend): 添加保留天数UI组件

添加数字输入框和加减按钮，最小值限制为3天

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: 端到端测试

**Files:**
- 无新文件

- [ ] **Step 1: 测试配置迁移**

1. 备份当前配置：`cp localData/config/config.yaml localData/config/config.yaml.backup`
2. 删除两个配置项：手动编辑 `config.yaml`，删除 `active_screenshot_frequency_level` 和 `screenshot_retention_days`
3. 启动后端：`PYTHONPATH=. python -m lifeprism.main`
4. 检查配置文件：`grep -E "active_screenshot_frequency_level|screenshot_retention_days" localData/config/config.yaml`

预期：两个字段已自动添加，值分别为2和7

- [ ] **Step 2: 测试后端验证**

使用curl测试后端验证：

```bash
# 测试无效的保留天数（应该失败）
curl -X PATCH http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"screenshot_retention_days": 2}'

# 预期：返回400错误，消息包含"截图保留天数不能小于3天"

# 测试有效的保留天数（应该成功）
curl -X PATCH http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"screenshot_retention_days": 10}'

# 预期：返回200成功
```

- [ ] **Step 3: 测试前端UI交互**

1. 启动前端：`cd frontend && npm run dev`
2. 打开浏览器访问设置页面
3. 测试频率等级：
   - 点击L1，观察状态变化
   - 点击L3，观察状态变化
   - 刷新页面，验证配置已保存
4. 测试保留天数：
   - 点击加号，观察值增加
   - 点击减号到3，验证不能再减少
   - 手动输入2，失焦后验证自动修正为3
   - 刷新页面，验证配置已保存

预期：所有交互正常，配置正确保存

- [ ] **Step 4: 测试错误提示**

1. 使用浏览器开发者工具，修改前端代码临时移除 `Math.max(3, value)` 限制
2. 手动输入保留天数为2
3. 观察是否显示错误toast

预期：显示错误提示"截图保留天数不能小于3天"

- [ ] **Step 5: 验证运行时使用配置**

1. 修改配置：将 `screenshot_retention_days` 改为5
2. 重启后端
3. 检查日志：`grep "retention_days" localData/debug_logs/*.log`

预期：日志显示使用了配置值5

- [ ] **Step 6: 最终提交**

```bash
git add -A
git commit -m "test: 完成端到端测试

验证配置迁移、后端验证、前端UI和运行时使用

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 自审清单

### 1. Spec覆盖检查

- [x] 需求1：在config中添加频率等级配置 → Task 1（已存在，无需修改）
- [x] 需求2：在config中添加截图保留天数配置 → Task 1（修改默认值）
- [x] 需求3：编写yaml配置迁移脚本 → Task 3, 4
- [x] 需求4：在前端设置页面添加配置项 → Task 6-10
- [x] 需求5：实现完整的前后端交互回路 → Task 2（验证）, Task 11（测试）

### 2. Placeholder检查

- [x] 无TBD、TODO
- [x] 所有代码步骤都包含完整代码
- [x] 所有测试步骤都包含预期输出

### 3. 类型一致性检查

- [x] `active_screenshot_frequency_level` 在所有任务中类型一致（int）
- [x] `screenshot_retention_days` 在所有任务中类型一致（int）
- [x] 前后端字段名称完全一致

---

## 执行选择

计划已完成并保存到 `docs/superpowers/plans/2026-04-21-monitor-config.md`。

**两种执行方式：**

**1. Subagent-Driven（推荐）** - 每个任务派发新的子agent，任务间review，快速迭代

**2. Inline Execution** - 在当前会话中使用 executing-plans 执行，批量执行带检查点

你选择哪种方式？

