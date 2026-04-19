# VLM 截图监控功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在配置模块增加 VLM 支持，实现截图监控功能的开关控制

**Architecture:** 后端在 settings_manager 新增 is_vlm 缓存和 is_visual() 方法，新增 /settings/test-vlm API；前端在 API 设置区新增 VLM 测试按钮，在设置页新增截图监控区域

**Tech Stack:** Python/FastAPI (后端), React/TypeScript (前端)

---

## 文件结构

```
后端修改:
- lifeprism/config/settings_manager.py     # DEFAULTS 新增字段 + is_visual() 方法
- lifeprism/server/schemas/setting_schemas.py  # 新增 TestVlmResponse + UpdateSettingsRequest 新增字段
- lifeprism/server/services/setting_service.py # test_vlm() 函数
- lifeprism/server/api/setting_api.py      # POST /settings/test-vlm 接口

前端修改:
- frontend/apps/settings/types.ts          # 新增 TestVlmResponse 类型
- frontend/apps/settings/api.ts            # 新增 testVlm() API 方法
- frontend/apps/settings/SettingsApp.tsx  # 新增截图监控区域 + VLM 测试按钮
```

---

## Task 1: settings_manager.py 新增配置字段和 is_visual() 方法

**Files:**
- Modify: `lifeprism/config/settings_manager.py:32-59` (DEFAULTS)
- Modify: `lifeprism/config/settings_manager.py:707` (末尾新增方法)

- [ ] **Step 1: 在 DEFAULTS 中新增 is_vlm 和 screenshot_monitor 字段**

找到 `DEFAULTS` 字典，在 `cleanup_check_interval_seconds` 后添加:

```python
DEFAULTS = {
    # ... existing fields ...
    'cleanup_check_interval_seconds': 86400,
    'is_vlm': {},  # Dict[str, bool], key = "provider_id/model_name"
    'screenshot_monitor': False,
}
```

- [ ] **Step 2: 新增 is_visual() 方法**

在 `settings_manager.py` 末尾（在最后一个属性方法后）添加:

```python
def is_visual(self) -> bool:
    """
    判断当前配置的模型是否具备 VLM 能力

    Returns:
        bool: 当前模型是否支持图像理解
    """
    provider_id = self._get_provider_id_from_name(self.provider)
    if not provider_id or not self.model:
        return False
    key = f"{provider_id}/{self.model}"
    return self._config.get('is_vlm', {}).get(key, False)
```

- [ ] **Step 3: 验证代码语法正确**

```bash
python -m py_compile lifeprism/config/settings_manager.py
```

预期: 无输出

- [ ] **Step 4: 提交**

```bash
git add lifeprism/config/settings_manager.py
git commit -m "feat(settings): 新增 is_vlm 缓存和 screenshot_monitor 配置项"
```

---

## Task 2: setting_schemas.py 新增 TestVlmResponse 和更新 UpdateSettingsRequest

**Files:**
- Modify: `lifeprism/server/schemas/setting_schemas.py:58-78` (UpdateSettingsRequest)
- Modify: `lifeprism/server/schemas/setting_schemas.py:125` (末尾新增 TestVlmResponse)

- [ ] **Step 1: 在 UpdateSettingsRequest 中新增 screenshot_monitor 字段**

在 `setting_schemas.py` 的 `UpdateSettingsRequest` 类中，在 `cleanup_check_interval_seconds` 后添加:

```python
class UpdateSettingsRequest(BaseModel):
    # ... existing fields ...
    cleanup_check_interval_seconds: Optional[int] = None
    screenshot_monitor: Optional[bool] = None
```

- [ ] **Step 2: 在文件末尾新增 TestVlmResponse 类**

在 `MigrateDataPathResponse` 类后添加:

```python
class TestVlmResponse(BaseModel):
    """测试 VLM 能力响应"""
    success: bool = Field(description="测试是否成功")
    message: str = Field(description="结果消息")
    is_vlm: bool = Field(description="测试结果，该模型是否具备 VLM 能力")
    model_response: Optional[str] = Field(default=None, description="模型回复内容")
```

- [ ] **Step 3: 验证代码语法正确**

```bash
python -m py_compile lifeprism/server/schemas/setting_schemas.py
```

预期: 无输出

- [ ] **Step 4: 提交**

```bash
git add lifeprism/server/schemas/setting_schemas.py
git commit -m "feat(schemas): 新增 TestVlmResponse 和 screenshot_monitor 字段"
```

---

## Task 3: setting_service.py 新增 test_vlm() 函数

**Files:**
- Modify: `lifeprism/server/services/setting_service.py` (末尾新增函数)

- [ ] **Step 1: 在 setting_service.py 末尾新增 test_vlm_capability() 函数**

导入已需要的模块（test_connect, test_vlm），新增函数:

```python
async def test_vlm_capability() -> dict:
    """
    测试当前模型的 VLM 能力

    流程:
    1. 调用 test_connect() 验证 LLM 连接
    2. 连接失败 → 返回错误
    3. 连接成功 → 调用 test_vlm() 测试图像理解
    4. 写入 is_vlm[provider_id/model] = result.success

    Returns:
        dict: 包含 success, message, is_vlm, model_response
    """
    from lifeprism.llm.function.test_connect import test_connect
    from lifeprism.llm.function.test_vlm import test_vlm

    # 1. 先测试连接
    connect_result = await test_connect()
    if not connect_result.get('success', False):
        return {
            'success': False,
            'message': f"连接失败: {connect_result.get('message', '未知错误')}",
            'is_vlm': False,
            'model_response': None
        }

    # 2. 连接成功，测试 VLM
    vlm_result = await test_vlm()

    # 3. 获取 provider_id 和 model 构建 key
    provider_name = settings.provider
    provider_id = provider_manager.get_provider_id(provider_name) if provider_name else ""
    model = settings.model
    if provider_id and model:
        key = f"{provider_id}/{model}"
        is_vlm = vlm_result.get('success', False)
        # 更新 is_vlm 缓存
        is_vlm_cache = settings.get('is_vlm', {})
        is_vlm_cache[key] = is_vlm
        settings.set('is_vlm', is_vlm_cache)
        logger.info(f"VLM 能力测试完成: {key} = {is_vlm}")

    return {
        'success': vlm_result.get('success', False),
        'message': vlm_result.get('message', '测试完成'),
        'is_vlm': vlm_result.get('success', False),
        'model_response': vlm_result.get('model_response')
    }
```

- [ ] **Step 2: 验证代码语法正确**

```bash
python -m py_compile lifeprism/server/services/setting_service.py
```

预期: 无输出

- [ ] **Step 3: 提交**

```bash
git add lifeprism/server/services/setting_service.py
git commit -m "feat(service): 新增 test_vlm_capability 测试 VLM 能力"
```

---

## Task 4: setting_api.py 新增 POST /settings/test-vlm 接口

**Files:**
- Modify: `lifeprism/server/api/setting_api.py` (新增 import 和路由)

- [ ] **Step 1: 在 import 中新增 TestVlmResponse**

在 `setting_api.py` 顶部的 import 语句中，从 schemas 导入 `TestVlmResponse`:

```python
from lifeprism.server.schemas.setting_schemas import (
    SettingsResponse,
    UpdateSettingsRequest,
    UpdateApiKeyRequest,
    UpdateApiKeyResponse,
    ProviderListResponse,
    ProviderInfo,
    ValidatePathRequest,
    ValidatePathResponse,
    MigrateDataPathRequest,
    MigrateDataPathResponse,
    TestVlmResponse,  # 新增
)
```

- [ ] **Step 2: 在 test-connection 路由后新增 test-vlm 路由**

在 `@router.post("/test-connection")` 路由后添加:

```python
@router.post("/test-vlm", response_model=TestVlmResponse, summary="测试 VLM 图像理解能力")
async def test_vlm_capability():
    """
    测试当前模型的图片理解能力

    流程:
    1. 先调用 test_connect() 验证 LLM 连接
    2. 连接失败 → 返回错误
    3. 连接成功 → 调用 test_vlm() 测试图像理解
    4. 根据测试结果更新 is_vlm 缓存

    Returns:
        TestVlmResponse: 测试结果
    """
    from lifeprism.server.services import setting_service

    try:
        result = await setting_service.test_vlm_capability()
        return TestVlmResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VLM 测试失败: {str(e)}")
```

- [ ] **Step 3: 验证代码语法正确**

```bash
python -m py_compile lifeprism/server/api/setting_api.py
```

预期: 无输出

- [ ] **Step 4: 提交**

```bash
git add lifeprism/server/api/setting_api.py
git commit -m "feat(api): 新增 POST /settings/test-vlm 接口"
```

---

## Task 5: 前端 types.ts 新增 TestVlmResponse 类型

**Files:**
- Modify: `frontend/apps/settings/types.ts:85-90` (新增 TestVlmResponse)

- [ ] **Step 1: 在 TestConnectionResponse 后新增 TestVlmResponse 接口**

在 `types.ts` 中，在 `TestConnectionResponse` 接口后添加:

```typescript
/** VLM 测试响应 */
export interface TestVlmResponse {
    success: boolean;
    message: string;
    is_vlm: boolean;
    model_response: string | null;
}
```

- [ ] **Step 2: 在 UpdateSettingsRequest 中新增 screenshot_monitor**

```typescript
export interface UpdateSettingsRequest {
    // ... existing fields ...
    screenshot_monitor?: boolean;
}
```

- [ ] **Step 3: 在 Settings 接口中新增 screenshot_monitor 和 is_vlm**

```typescript
export interface Settings {
    // ... existing fields ...
    screenshot_monitor?: boolean;
    is_vlm?: Record<string, boolean>;
}
```

- [ ] **Step 4: 提交**

```bash
git add frontend/apps/settings/types.ts
git commit -m "feat(frontend): 新增 TestVlmResponse 类型和 screenshot_monitor 字段"
```

---

## Task 6: 前端 api.ts 新增 testVlm() API 方法

**Files:**
- Modify: `frontend/apps/settings/api.ts` (新增 import 和 API 方法)

- [ ] **Step 1: 在 import 中新增 TestVlmResponse**

```typescript
import {
    Settings,
    SettingsResponse,
    UpdateSettingsRequest,
    UpdateApiKeyRequest,
    UpdateApiKeyResponse,
    ApiKeyStatusResponse,
    TestConnectionResponse,
    TestVlmResponse,  // 新增
    ProviderInfo,
    ProviderListResponse,
    ValidatePathRequest,
    ValidatePathResponse,
    MigrateDataPathRequest,
    MigrateDataPathResponse,
} from './types';
```

- [ ] **Step 2: 在 SettingsAPI 中新增 testVlm 方法**

在 `SettingsAPI.testConnection` 方法后添加:

```typescript
/**
 * 测试 VLM 图像理解能力
 */
async testVlm(): Promise<TestVlmResponse> {
    const response = await fetch(`${getApiBase()}/settings/test-vlm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `VLM 测试失败: ${response.statusText}`);
    }
    return response.json();
},
```

- [ ] **Step 3: 提交**

```bash
git add frontend/apps/settings/api.ts
git commit -m "feat(frontend): 新增 testVlm() API 方法"
```

---

## Task 7: 前端 SettingsApp.tsx 新增截图监控区域和 VLM 测试按钮

**Files:**
- Modify: `frontend/apps/settings/SettingsApp.tsx` (多处修改)

- [ ] **Step 1: 新增状态变量**

在 `SettingsApp` 组件中，在其他 useState 声明后添加:

```typescript
// 6. Screenshot Monitor
const [screenshotMonitor, setScreenshotMonitor] = useState(false);
const [isVlmTesting, setIsVlmTesting] = useState(false);
const [currentModelVlmStatus, setCurrentModelVlmStatus] = useState<boolean | null>(null);
```

- [ ] **Step 2: 在加载配置时读取 screenshot_monitor 和 is_vlm**

在 `loadSettings` 函数中，在 `setFilterDuration` 后添加:

```typescript
setFilterDuration(settings.data_cleaning_threshold);
setScreenshotMonitor(settings.screenshot_monitor || false);
// 获取当前模型的 VLM 状态
const providerId = providerIdMap[provider] || '';
if (providerId && modelName) {
    const isVlm = settings.is_vlm?.[`${providerId}/${modelName}`];
    setCurrentModelVlmStatus(isVlm ?? null);
}
```

- [ ] **Step 3: 新增 handleTestVlm 函数**

在 `handleTestConnection` 函数后添加:

```typescript
const handleTestVlm = async () => {
    setIsVlmTesting(true);
    try {
        const result = await SettingsAPI.testVlm();
        if (result.success) {
            toast.success(`图像理解能力测试成功: ${result.model_response || ''}`);
        } else {
            toast.error(result.message || 'VLM 测试失败');
        }
        // 更新本地 VLM 状态
        setCurrentModelVlmStatus(result.is_vlm);
        // 同步更新 screenshot_monitor 状态（如果后端已更新）
        const updatedSettings = await SettingsAPI.getSettings();
        setScreenshotMonitor(updatedSettings.screenshot_monitor || false);
    } catch (err) {
        toast.error(err instanceof Error ? err.message : 'VLM 测试失败');
    } finally {
        setIsVlmTesting(false);
    }
};
```

- [ ] **Step 4: 在模型切换时处理 VLM 测试**

在 `handleProviderChange` 函数末尾，在 `setShowVolcEngineModal(true)` 前添加:

```typescript
// 如果 screenshot_monitor 已开启，自动测试新模型的 VLM 能力
if (screenshotMonitor) {
    const newProviderId = providerIdMap[newProvider] || '';
    const newModel = nextModel;
    setIsVlmTesting(true);
    try {
        const result = await SettingsAPI.testVlm();
        if (!result.success) {
            setScreenshotMonitor(false);
            triggerAutoSave({ screenshot_monitor: false });
            toast.warning(`截图监控已自动关闭: ${result.message}`);
        } else {
            // VLM 测试成功，screenshot_monitor 保持开启
            setCurrentModelVlmStatus(true);
        }
    } catch (err) {
        setScreenshotMonitor(false);
        triggerAutoSave({ screenshot_monitor: false });
        toast.warning(`截图监控已自动关闭`);
    } finally {
        setIsVlmTesting(false);
    }
}
```

- [ ] **Step 5: 在 handleSelectModel 中也添加相同的 VLM 测试逻辑**

在 `handleSelectModel` 函数中，在 `setShowModelDropdown(false)` 后添加类似的逻辑

- [ ] **Step 6: 在 API 设置区域的按钮旁边新增 VLM 测试按钮**

找到 test-connect 按钮所在的 flex 容器，修改为:

```tsx
<div className="flex items-center gap-4">
    <button
        onClick={handleTestConnection}
        disabled={apiStatus === 'testing'}
        className={`flex items-center gap-2 px-4 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-all border ${apiStatus === 'success'
            ? 'bg-green-50 text-green-700 border-green-200'
            : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
            }`}
    >
        {apiStatus === 'testing' ? (
            <div className="w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
        ) : apiStatus === 'success' ? (
            <Check size={14} />
        ) : (
            <Zap size={14} />
        )}
        {apiStatus === 'testing' ? '测试中...' : apiStatus === 'success' ? '已连接' : '测试连接'}
    </button>

    {/* VLM 测试按钮 */}
    <button
        onClick={handleTestVlm}
        disabled={isVlmTesting || !modelName}
        className={`flex items-center gap-2 px-4 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-all border ${
            currentModelVlmStatus === true
                ? 'bg-green-50 text-green-700 border-green-200'
                : isVlmTesting
                ? 'bg-slate-50 text-slate-400 border-slate-200 cursor-not-allowed'
                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
        }`}
        title={currentModelVlmStatus === true ? '该模型具备图像理解能力，点击可重新验证' : '测试该模型的图像理解能力'}
    >
        {isVlmTesting ? (
            <div className="w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
        ) : currentModelVlmStatus === true ? (
            <Check size={14} />
        ) : (
            <Cpu size={14} />
        )}
        {isVlmTesting ? '验证中...' : currentModelVlmStatus === true ? '具备图片理解能力' : '测试图片理解能力'}
    </button>
</div>
```

- [ ] **Step 7: 在「数据清洗」和「分类逻辑」之间新增截图监控区域**

在 `Data Hygiene` section 后，添加:

```tsx
{/* 6. Screenshot Monitor */}
<section className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm">
    <div className="flex items-center gap-3 mb-6">
        <div className="p-2.5 bg-red-50 rounded-xl text-red-500">
            <Eye size={20} />
        </div>
        <h2 className="text-lg font-bold text-slate-800">截图监控</h2>
    </div>

    <div className="space-y-6">
        {/* 开关 */}
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100">
            <div>
                <h4 className="text-sm font-bold text-slate-700">开启截图监控</h4>
                <p className="text-xs text-slate-400 mt-1">启用后将对屏幕进行周期性截图分析</p>
            </div>
            <button
                onClick={async () => {
                    if (!screenshotMonitor) {
                        // 尝试开启
                        try {
                            setIsVlmTesting(true);
                            const result = await SettingsAPI.testVlm();
                            if (result.success) {
                                setScreenshotMonitor(true);
                                triggerAutoSave({ screenshot_monitor: true });
                                setCurrentModelVlmStatus(true);
                                toast.success('截图监控已开启');
                            } else {
                                toast.error(`无法开启截图监控: ${result.message}`);
                            }
                        } catch (err) {
                            toast.error(err instanceof Error ? err.message : '开启失败');
                        } finally {
                            setIsVlmTesting(false);
                        }
                    } else {
                        // 关闭
                        setScreenshotMonitor(false);
                        triggerAutoSave({ screenshot_monitor: false });
                    }
                }}
                disabled={isVlmTesting || !modelName}
                className={`relative w-14 h-8 rounded-full transition-all ${
                    screenshotMonitor ? 'bg-green-500' : 'bg-slate-200'
                } ${isVlmTesting || !modelName ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
                <div
                    className={`absolute top-1 w-6 h-6 bg-white rounded-full shadow-sm transition-all ${
                        screenshotMonitor ? 'left-7' : 'left-1'
                    }`}
                />
                {isVlmTesting && (
                    <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    </div>
                )}
            </button>
        </div>

        {/* 当前模型状态 */}
        <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-xs text-slate-400">当前模型</p>
                    <p className="text-sm font-bold text-slate-700 mt-1">{modelName || '未选择'}</p>
                </div>
                <div className="text-right">
                    <p className="text-xs text-slate-400">图片理解能力</p>
                    <p className={`text-sm font-bold mt-1 ${
                        currentModelVlmStatus === true ? 'text-green-600' :
                        currentModelVlmStatus === false ? 'text-red-500' : 'text-slate-400'
                    }`}>
                        {currentModelVlmStatus === true ? '✓ 具备' :
                         currentModelVlmStatus === false ? '✗ 不具备' : '未知'}
                    </p>
                </div>
            </div>
            {isVlmTesting && (
                <p className="text-xs text-slate-400 mt-2 flex items-center gap-1">
                    <div className="w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                    验证中...
                </p>
            )}
        </div>
    </div>
</section>
```

- [ ] **Step 8: 提交**

```bash
git add frontend/apps/settings/SettingsApp.tsx
git commit -m "feat(frontend): 新增截图监控区域和 VLM 测试按钮"
```

---

## Task 8: 整体测试

- [ ] **Step 1: 启动后端服务，测试 API**

```bash
# 测试 settings API 是否正常
curl http://localhost:18792/api/v2/settings

# 测试 test-vlm API（需要配置好 LLM）
curl -X POST http://localhost:18792/api/v2/settings/test-vlm
```

预期: 返回包含 success, message, is_vlm 字段的 JSON

- [ ] **Step 2: 验证前端页面**

启动前端开发服务器，访问设置页面，验证:
1. API 设置区域显示 VLM 测试按钮
2. 截图监控区域正常显示
3. 点击 VLM 测试按钮能正常调用后端 API

- [ ] **Step 3: 提交最终更改**

```bash
git status
git add -A
git commit -m "feat: 完成 VLM 截图监控功能"
```

---

## 实施检查清单

- [ ] Task 1: settings_manager.py 新增字段和 is_visual() 方法
- [ ] Task 2: setting_schemas.py 新增 TestVlmResponse
- [ ] Task 3: setting_service.py 新增 test_vlm_capability()
- [ ] Task 4: setting_api.py 新增 /settings/test-vlm 路由
- [ ] Task 5: frontend types.ts 新增类型
- [ ] Task 6: frontend api.ts 新增 API 方法
- [ ] Task 7: frontend SettingsApp.tsx 新增 UI
- [ ] Task 8: 整体测试验证
