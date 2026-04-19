# VLM 截图监控功能设计

## 1. 需求概述

在配置模块增加 VLM（视觉语言模型）支持，用于判断当前模型是否具备图像理解能力，并控制截图监控功能的启用。

### 1.1 新增配置字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `is_vlm` | Dict[str, bool] | VLM 能力缓存，key 格式为 `"provider_id/model_name"` |
| `screenshot_monitor` | bool | 截图监控开关，默认为 false |

### 1.2 新增方法

**settings_manager.py** 新增 `is_visual() -> bool` 方法，通过 `is_vlm` 判断当前模型是否支持视觉能力。

---

## 2. 配置结构变更

### 2.1 settings_manager.py

**DEFAULTS 新增字段**:
```python
DEFAULTS = {
    # ... 现有字段 ...
    'is_vlm': {},           # Dict[str, bool], key = "provider_id/model_name"
    'screenshot_monitor': False,
}
```

**新增 is_visual 方法**:
```python
def is_visual(self) -> bool:
    """
    判断当前配置的模型是否具备 VLM 能力

    Returns:
        bool: 当前模型是否支持图像理解
    """
    # 获取 provider_id（而非显示名称）
    provider_id = self._get_provider_id_from_name(self.provider)
    if not provider_id or not self.model:
        return False
    key = f"{provider_id}/{self.model}"
    return self._config.get('is_vlm', {}).get(key, False)
```

---

## 3. API 设计

### 3.1 schemas (setting_schemas.py)

**TestVlmResponse**:
```python
class TestVlmResponse(BaseModel):
    """测试 VLM 能力响应"""
    success: bool = Field(description="测试是否成功")
    message: str = Field(description="结果消息")
    is_vlm: bool = Field(description="测试结果，该模型是否具备 VLM 能力")
    model_response: Optional[str] = Field(default=None, description="模型回复内容")
```

**UpdateSettingsRequest** 新增字段:
```python
class UpdateSettingsRequest(BaseModel):
    # ... 现有字段 ...
    screenshot_monitor: Optional[bool] = None
```

### 3.2 接口

**POST /settings/test-vlm** — 测试图片理解能力

```
路由: POST /settings/test-vlm
响应模型: TestVlmResponse

流程:
1. 调用 test_connect() 验证 LLM 连接
2. 连接失败 → 返回错误
3. 连接成功 → 调用 test_vlm() 测试图像理解
4. 写入 is_vlm[provider_id/model] = result.success
5. 返回 TestVlmResponse

响应示例:
{
  "success": true,
  "message": "VLM 图像理解测试成功",
  "is_vlm": true,
  "model_response": "这是一张猫的图片"
}
```

**PATCH /settings** — 支持 `screenshot_monitor` 字段更新

---

## 4. 前端 UI 设计

### 4.1 新增「截图监控」区域

位置：位于「数据清洗」和「分类逻辑」之间

```
┌─────────────────────────────────────────────────────────────┐
│ [📷] 截图监控                                               │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  ○ 开启截图监控                                      │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   当前模型: qwen-vl-max                                     │
│   图片理解能力: ✓ 具备  或  ✗ 不具备  [重新验证]           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**交互逻辑**:
- 开关开启时：如果 `is_vlm[model] == True` 直接开启；否则自动调用 test-vlm 验证
- 验证中：开关禁用，显示 "验证中..."
- 验证失败：开关保持关闭，toast 错误信息
- 验证成功：写入 is_vlm，开启 screenshot_monitor

### 4.2 API 设置区域变更

在 test-connect 按钮旁边增加：

```
┌─────────────────────────────────────────────────────────────┐
│  [测试连接]  [✓ 具备图片理解能力]  或  [测试图片理解能力]    │
└─────────────────────────────────────────────────────────────┘
```

**按钮状态**:
- `is_vlm[model] == True` → 显示 "✓ 具备图片理解能力"（可点击重新验证）
- `is_vlm[model] == False` 或不存在 → 显示 "测试图片理解能力"

**点击流程**:
1. 先调用 test-connect
2. 连接成功 → 调用 test-vlm
3. 连接失败 → toast 错误，不修改配置
4. 更新 is_vlm，显示结果 toast

---

## 5. 模型切换行为

### 5.1 自动测试逻辑

当用户切换模型时（handleProviderChange 或选择历史模型）:

```typescript
if (screenshot_monitor === true) {
    // 自动测试新模型的 VLM 能力
    const result = await SettingsAPI.testVlm();
    if (result.success) {
        // 保持 screenshot_monitor = true（已在后端更新）
    } else {
        // screenshot_monitor 自动变为 false（后端处理）
        toast.warning(`截图监控已自动关闭：${result.message}`);
    }
}
```

### 5.2 UI 状态

- 测试期间：截图监控开关禁用，显示 "验证中..."
- 测试完成后：根据结果更新开关状态

---

## 6. 数据流

### 6.1 截图监控开启流程

```
用户点击开启截图监控
  → 前端调用 PATCH /settings { screenshot_monitor: true }
  → 后端检查 is_vlm[provider_id/model]
    → 存在且为 true: 直接设置 screenshot_monitor = true
    → 不存在或为 false: 返回错误，指引前端调用 test-vlm
  → 前端调用 POST /settings/test-vlm
  → 后端执行: test_connect() → test_vlm()
  → 写入 is_vlm[provider_id/model] = result.success
  → 如果成功: 设置 screenshot_monitor = true
  → 返回结果
```

### 6.2 测试图片理解能力流程

```
用户点击测试图片理解能力
  → 前端调用 POST /settings/test-vlm
  → 后端执行: test_connect() → test_vlm()
  → 写入 is_vlm[provider_id/model] = result.success
  → 返回 TestVlmResponse（不改变 screenshot_monitor）
  → 前端更新按钮文案
```

---

## 7. 错误处理

| 场景 | 行为 |
|------|------|
| test_connect 失败 | 返回错误，不修改 is_vlm |
| test_vlm 失败 | 写入 is_vlm[model] = false，返回失败结果 |
| 模型切换时 test_vlm 失败 | screenshot_monitor 自动设为 false |
| 测试图片不存在 | 返回特定错误消息 |

---

## 8. 测试图片

默认测试图片路径: `{lifeprism_data_path}/assets/test-vlm.png`

图片内容：一张猫的图片（用于验证模型能否识别 "猫"）
