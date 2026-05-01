# 微信 QR 码登录功能设计

## 概述

在前端设置模块添加远程通信连接功能，支持通过扫描 QR 码登录微信通道。用户选择通道、点击确认后显示 QR 码，前端轮询状态直到登录成功或过期。

## 一、后端设计

### 1. API 端点

#### 1.1 获取 QR 码
**路径**：`GET /api/v2/settings/qrcode`  
**参数**：
- `channel: str`（查询参数，值为 `wechat`）

**响应**：
```json
{
  "qr_string": "https://login.weixin.qq.com/l/xxx-xxx-xxx",
  "qrcode_id": "xxx"
}
```

**错误响应**：
```json
{
  "detail": "不支持的通道类型: xxx"
}
```

#### 1.2 查询 QR 码状态
**路径**：`GET /api/v2/settings/qrcode/status`  
**参数**：
- `channel: str`（wechat）
- `qrcode_id: str`（从获取 QR 码接口返回的 ID）

**响应**：
```json
{
  "status": "waiting" | "scanning" | "confirmed" | "expired",
  "message": "等待扫描" | "用户正在扫描" | "登录成功" | "二维码已过期",
  "token": "xxx"  // 仅当 status 为 confirmed 时返回
}
```

### 2. 服务层实现

在 `lifeprism/server/services/setting_service.py` 添加两个函数：

#### 2.1 获取 QR 码
```python
async def get_qrcode(channel: str) -> dict:
    """获取指定通道的 QR 码
    
    Args:
        channel: 通道类型（当前仅支持 wechat）
    
    Returns:
        包含 qr_string 和 qrcode_id 的字典
        
    Raises:
        ValueError: 不支持的通道类型
    """
```

**实现逻辑**：
1. 验证 `channel` 参数（当前只支持 `wechat`）
2. 使用默认 `base_url`（`https://ilinkai.weixin.qq.com`）创建临时 `WechatClient` 实例
3. 调用微信 API：`ilink/bot/get_bot_qrcode`，参数 `{"bot_type": "3"}`
4. 提取响应中的 `qrcode_img_content`（QR 码 URL）和 `qrcode`（ID）
5. 返回 `{"qr_string": qrcode_img_content, "qrcode_id": qrcode}`
6. 不启动 channel

#### 2.2 查询 QR 码状态
```python
async def get_qrcode_status(channel: str, qrcode_id: str) -> dict:
    """查询 QR 码扫描状态
    
    Args:
        channel: 通道类型（wechat）
        qrcode_id: QR 码 ID
    
    Returns:
        包含 status 和 message 的字典
    """
```

**实现逻辑**：
1. 验证 `channel` 参数
2. 使用默认 `base_url` 创建临时 `WechatClient` 实例
3. 调用微信 API：`ilink/bot/get_qrcode_status`，参数 `{"qrcode": qrcode_id}`
4. 提取响应中的 `status` 字段
5. 映射状态到前端：
   - 微信 API 返回空或 `waiting` → `"waiting"`
   - 微信 API 返回 `scanning` → `"scanning"`
   - 微信 API 返回 `confirmed` → `"confirmed"`
   - 微信 API 返回 `expired` → `"expired"`
6. **如果状态为 `confirmed`**：
   - 提取响应中的 `bot_token`
   - 保存 token 到 `{lifeprism_data_path}/channel/wechat/account.json`
   - 文件格式：`{"token": "xxx", "context_tokens": {}}`
   - 返回 `{"status": "confirmed", "message": "登录成功", "token": token}`
7. 其他状态返回 `{"status": status, "message": message}`

### 3. API 路由

在 `lifeprism/server/api/setting_api.py` 添加两个路由：

```python
@router.get("/qrcode")
async def get_qrcode(channel: str = Query(..., description="通道类型，如 wechat")):
    """获取指定通道的 QR 码"""
    
@router.get("/qrcode/status")
async def get_qrcode_status(
    channel: str = Query(..., description="通道类型"),
    qrcode_id: str = Query(..., description="QR 码 ID")
):
    """查询 QR 码扫描状态"""
```

### 4. Schema 定义

在 `lifeprism/server/schemas/setting_schemas.py` 添加：

```python
class QRCodeResponse(BaseModel):
    qr_string: str
    qrcode_id: str

class QRCodeStatusResponse(BaseModel):
    status: str  # waiting | scanning | confirmed | expired
    message: str
    token: str | None = None  # 仅当 status 为 confirmed 时返回
```

## 二、前端设计

### 1. UI 组件结构

在 `SettingsApp.tsx` 的设置页面添加"远程通信"区域，包含：

#### 组件 1：通道选择下拉菜单
- 显示名称：`微信`
- 实际值：`wechat`
- 当前硬编码，未来可扩展

#### 组件 2：确认按钮
- 文本：`获取二维码`
- 点击后调用 API 获取 QR 码

#### 组件 3：QR 码显示区域
- 使用 `qrcode.react` 库渲染 QR 码
- 显示状态文本：
  - `等待扫描...`（waiting）
  - `正在扫描...`（scanning）
  - `登录成功 ✓`（confirmed，绿色）
  - `二维码已过期`（expired，红色）
- 过期时显示"重新获取"按钮

### 2. 状态管理

```typescript
const [selectedChannel, setSelectedChannel] = useState('wechat');
const [qrString, setQrString] = useState('');
const [qrCodeId, setQrCodeId] = useState('');
const [qrStatus, setQrStatus] = useState<'idle' | 'waiting' | 'scanning' | 'confirmed' | 'expired'>('idle');
const [isLoadingQr, setIsLoadingQr] = useState(false);
```

### 3. 轮询逻辑

**触发时机**：获取 QR 码成功后立即开始轮询

**轮询间隔**：2 秒

**停止条件**：
- 状态变为 `confirmed` 或 `expired`
- 超时（5 分钟）
- 组件卸载

**实现**：使用 `useEffect` + `setInterval`

### 4. API 调用

在 `frontend/apps/settings/api.ts` 添加：

```typescript
async getQRCode(channel: string): Promise<{ qr_string: string; qrcode_id: string }> {
    const response = await fetch(`${getApiBase()}/settings/qrcode?channel=${channel}`);
    if (!response.ok) throw new Error('获取二维码失败');
    return response.json();
}

async getQRCodeStatus(channel: string, qrcodeId: string): Promise<{ status: string; message: string; token?: string }> {
    const response = await fetch(`${getApiBase()}/settings/qrcode/status?channel=${channel}&qrcode_id=${qrcodeId}`);
    if (!response.ok) throw new Error('查询状态失败');
    return response.json();
}
```

### 5. 类型定义

在 `frontend/apps/settings/types.ts` 添加：

```typescript
export interface QRCodeResponse {
    qr_string: string;
    qrcode_id: string;
}

export interface QRCodeStatusResponse {
    status: 'waiting' | 'scanning' | 'confirmed' | 'expired';
    message: string;
    token?: string;  // 仅当 status 为 confirmed 时返回
}
```

### 6. 依赖安装

```bash
cd frontend
npm install qrcode.react
npm install --save-dev @types/qrcode.react
```

## 三、交互流程

```
用户选择"微信"通道
    ↓
点击"获取二维码"按钮
    ↓
调用 GET /api/v2/settings/qrcode?channel=wechat
    ↓
显示 QR 码（使用 qrcode.react 渲染）
    ↓
开始轮询状态（每 2 秒）
    ↓
状态更新：waiting → scanning → confirmed/expired
    ↓
confirmed：显示"登录成功 ✓"，停止轮询
expired：显示"二维码已过期"，显示"重新获取"按钮
```

## 四、错误处理

### 后端
- 不支持的通道类型 → 返回 400 错误
- 微信 API 调用失败 → 返回 500 错误，记录日志

### 前端
- API 调用失败 → 显示 toast 提示
- 轮询超时（5 分钟）→ 停止轮询，显示"请求超时，请重试"

## 五、技术约束

1. **不启动 channel**：获取 QR 码和查询状态都是独立的 API 调用，不涉及 channel 的启动和停止
2. **临时客户端**：每次 API 调用创建临时 `WechatClient`，用完即销毁
3. **状态保存**：当扫码确认后（status=confirmed），保存 token 到 `{lifeprism_data_path}/channel/wechat/account.json`
4. **前端轮询**：使用轮询而非 WebSocket，简化实现
5. **文件路径**：使用 `settings.channel_path` 获取 channel 数据目录（`{lifeprism_data_path}/channel`）

## 六、未来扩展

1. 支持更多通道类型（钉钉、企业微信等）
2. WebSocket 实时推送替代轮询
3. QR 码自动刷新（过期后自动获取新的）
