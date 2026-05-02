# 微信 QR 码登录功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在前端设置页面添加微信 QR 码登录功能，用户扫码后保存 token 到本地文件

**Architecture:** 后端提供两个 API（获取 QR 码、查询状态），前端轮询状态直到登录成功或过期。扫码成功后后端保存 token 到 account.json。

**Tech Stack:** Python FastAPI, React TypeScript, qrcode.react, WechatClient

---

## 文件结构

### 后端
- **Modify**: `lifeprism/server/schemas/setting_schemas.py` - 添加 QR 码相关 schema
- **Modify**: `lifeprism/server/services/setting_service.py` - 添加获取 QR 码和查询状态的服务函数
- **Modify**: `lifeprism/server/api/setting_api.py` - 添加两个 API 路由

### 前端
- **Modify**: `frontend/apps/settings/types.ts` - 添加 QR 码类型定义
- **Modify**: `frontend/apps/settings/api.ts` - 添加 API 调用函数
- **Modify**: `frontend/apps/settings/SettingsApp.tsx` - 添加 UI 组件和轮询逻辑
- **Modify**: `frontend/package.json` - 添加 qrcode.react 依赖

---

## Task 1: 后端 Schema 定义

**Files:**
- Modify: `lifeprism/server/schemas/setting_schemas.py`

- [ ] **Step 1: 添加 QR 码响应 schema**

在文件末尾添加：

```python
class QRCodeResponse(BaseModel):
    """QR 码响应"""
    qr_string: str
    qrcode_id: str


class QRCodeStatusResponse(BaseModel):
    """QR 码状态响应"""
    status: str  # waiting | scanning | confirmed | expired
    message: str
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/server/schemas/setting_schemas.py
git commit -m "feat(backend): 添加 QR 码 schema 定义"
```

---

## Task 2: 后端服务层 - 获取 QR 码

**Files:**
- Modify: `lifeprism/server/services/setting_service.py`

- [ ] **Step 1: 添加获取 QR 码函数**

在文件末尾添加：

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
    if channel != "wechat":
        raise ValueError(f"不支持的通道类型: {channel}")
    
    from lifeprism.llm.channel.wechat.client import WechatClient
    
    base_url = "https://ilinkai.weixin.qq.com"
    async with WechatClient(base_url) as client:
        data = await client.api_get("ilink/bot/get_bot_qrcode", params={"bot_type": "3"}, auth=False)
        qrcode_id = data.get("qrcode", "")
        qrcode_img = data.get("qrcode_img_content", qrcode_id)
        
        if not qrcode_id:
            raise ValueError("获取 QR 码失败")
        
        return {
            "qr_string": qrcode_img,
            "qrcode_id": qrcode_id
        }
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/server/services/setting_service.py
git commit -m "feat(backend): 实现获取 QR 码服务函数"
```

---

## Task 3: 后端服务层 - 查询 QR 码状态

**Files:**
- Modify: `lifeprism/server/services/setting_service.py`

- [ ] **Step 1: 添加查询状态函数**

在 `get_qrcode` 函数后添加：

```python
async def get_qrcode_status(channel: str, qrcode_id: str) -> dict:
    """查询 QR 码扫描状态
    
    Args:
        channel: 通道类型（wechat）
        qrcode_id: QR 码 ID
    
    Returns:
        包含 status 和 message 的字典
    """
    if channel != "wechat":
        raise ValueError(f"不支持的通道类型: {channel}")
    
    from lifeprism.llm.channel.wechat.client import WechatClient
    import json
    
    base_url = "https://ilinkai.weixin.qq.com"
    async with WechatClient(base_url) as client:
        data = await client.api_get(
            "ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode_id},
            auth=False
        )
        status = data.get("status", "waiting")
        
        # 映射状态
        status_map = {
            "": "waiting",
            "waiting": "waiting",
            "scanning": "scanning",
            "confirmed": "confirmed",
            "expired": "expired"
        }
        mapped_status = status_map.get(status, "waiting")
        
        # 状态消息
        message_map = {
            "waiting": "等待扫描",
            "scanning": "用户正在扫描",
            "confirmed": "登录成功",
            "expired": "二维码已过期"
        }
        message = message_map.get(mapped_status, "等待扫描")
        
        # 如果状态为 confirmed，保存 token
        if mapped_status == "confirmed":
            token = data.get("bot_token", "")
            if token:
                # 保存到 account.json
                wechat_dir = settings.channel_path / "wechat"
                wechat_dir.mkdir(parents=True, exist_ok=True)
                state_file = wechat_dir / "account.json"
                
                state = {"token": token, "context_tokens": {}}
                state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
                logger.info(f"已保存微信 token 到 {state_file}")
        
        return {
            "status": mapped_status,
            "message": message
        }
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/server/services/setting_service.py
git commit -m "feat(backend): 实现查询 QR 码状态并保存 token"
```

---

## Task 4: 后端 API 路由

**Files:**
- Modify: `lifeprism/server/api/setting_api.py`

- [ ] **Step 1: 导入新的 schema**

在文件顶部的 import 区域，找到 `from lifeprism.server.schemas.setting_schemas import` 这一行，添加新的 schema：

```python
from lifeprism.server.schemas.setting_schemas import (
    # ... 现有的 imports ...
    QRCodeResponse,
    QRCodeStatusResponse,
)
```

- [ ] **Step 2: 添加获取 QR 码路由**

在文件末尾添加：

```python
@router.get("/qrcode", response_model=QRCodeResponse, summary="获取通道 QR 码")
async def get_qrcode(channel: str = Query(..., description="通道类型，如 wechat")):
    """
    获取指定通道的 QR 码
    
    Args:
        channel: 通道类型（当前仅支持 wechat）
    
    Returns:
        QR 码字符串和 ID
    """
    try:
        result = await setting_service.get_qrcode(channel)
        return QRCodeResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取 QR 码失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取 QR 码失败: {str(e)}")
```

- [ ] **Step 3: 添加查询状态路由**

在 `get_qrcode` 路由后添加：

```python
@router.get("/qrcode/status", response_model=QRCodeStatusResponse, summary="查询 QR 码状态")
async def get_qrcode_status(
    channel: str = Query(..., description="通道类型"),
    qrcode_id: str = Query(..., description="QR 码 ID")
):
    """
    查询 QR 码扫描状态
    
    Args:
        channel: 通道类型（wechat）
        qrcode_id: QR 码 ID
    
    Returns:
        扫描状态和消息
    """
    try:
        result = await setting_service.get_qrcode_status(channel, qrcode_id)
        return QRCodeStatusResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"查询 QR 码状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询状态失败: {str(e)}")
```

- [ ] **Step 4: 提交**

```bash
git add lifeprism/server/api/setting_api.py
git commit -m "feat(backend): 添加 QR 码 API 路由"
```

---

## Task 5: 前端类型定义

**Files:**
- Modify: `frontend/apps/settings/types.ts`

- [ ] **Step 1: 添加 QR 码类型**

在文件末尾添加：

```typescript
/** QR 码响应 */
export interface QRCodeResponse {
    qr_string: string;
    qrcode_id: string;
}

/** QR 码状态响应 */
export interface QRCodeStatusResponse {
    status: 'waiting' | 'scanning' | 'confirmed' | 'expired';
    message: string;
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/apps/settings/types.ts
git commit -m "feat(frontend): 添加 QR 码类型定义"
```

---

## Task 6: 前端 API 调用

**Files:**
- Modify: `frontend/apps/settings/api.ts`

- [ ] **Step 1: 导入类型**

在文件顶部的 import 区域添加：

```typescript
import {
    // ... 现有的 imports ...
    QRCodeResponse,
    QRCodeStatusResponse,
} from './types';
```

- [ ] **Step 2: 添加 API 方法**

在 `SettingsAPI` 对象的末尾添加（在最后一个方法后，闭合大括号前）：

```typescript
    /**
     * 获取通道 QR 码
     */
    async getQRCode(channel: string): Promise<QRCodeResponse> {
        const response = await fetch(`${getApiBase()}/settings/qrcode?channel=${channel}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || '获取二维码失败');
        }
        return response.json();
    },

    /**
     * 查询 QR 码状态
     */
    async getQRCodeStatus(channel: string, qrcodeId: string): Promise<QRCodeStatusResponse> {
        const response = await fetch(`${getApiBase()}/settings/qrcode/status?channel=${channel}&qrcode_id=${qrcodeId}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || '查询状态失败');
        }
        return response.json();
    },
```

- [ ] **Step 3: 提交**

```bash
git add frontend/apps/settings/api.ts
git commit -m "feat(frontend): 添加 QR 码 API 调用方法"
```

---

## Task 7: 安装前端依赖

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: 安装 qrcode.react**

```bash
cd frontend
npm install qrcode.react
npm install --save-dev @types/qrcode.react
```

- [ ] **Step 2: 提交**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): 添加 qrcode.react 依赖"
```

---

## Task 8: 前端 UI 组件 - 状态管理

**Files:**
- Modify: `frontend/apps/settings/SettingsApp.tsx`

- [ ] **Step 1: 导入依赖**

在文件顶部的 import 区域添加：

```typescript
import QRCode from 'qrcode.react';
import type { QRCodeResponse, QRCodeStatusResponse } from './types';
```

- [ ] **Step 2: 添加状态变量**

在 `SettingsApp` 组件内部，找到其他 `useState` 声明的位置，添加：

```typescript
// 9. Remote Channel QR Code
const [selectedChannel, setSelectedChannel] = useState('wechat');
const [qrString, setQrString] = useState('');
const [qrCodeId, setQrCodeId] = useState('');
const [qrStatus, setQrStatus] = useState<'idle' | 'waiting' | 'scanning' | 'confirmed' | 'expired'>('idle');
const [isLoadingQr, setIsLoadingQr] = useState(false);
```

- [ ] **Step 3: 提交**

```bash
git add frontend/apps/settings/SettingsApp.tsx
git commit -m "feat(frontend): 添加 QR 码状态管理"
```

---

## Task 9: 前端 UI 组件 - 获取 QR 码逻辑

**Files:**
- Modify: `frontend/apps/settings/SettingsApp.tsx`

- [ ] **Step 1: 添加获取 QR 码函数**

在组件内部，找到其他函数定义的位置（如 `handleSave` 等），添加：

```typescript
// 获取 QR 码
const handleGetQRCode = async () => {
    setIsLoadingQr(true);
    setQrStatus('idle');
    setQrString('');
    setQrCodeId('');
    
    try {
        const result = await SettingsAPI.getQRCode(selectedChannel);
        setQrString(result.qr_string);
        setQrCodeId(result.qrcode_id);
        setQrStatus('waiting');
        toast.success('二维码已生成，请扫描');
    } catch (error) {
        toast.error(error instanceof Error ? error.message : '获取二维码失败');
        setQrStatus('idle');
    } finally {
        setIsLoadingQr(false);
    }
};
```

- [ ] **Step 2: 提交**

```bash
git add frontend/apps/settings/SettingsApp.tsx
git commit -m "feat(frontend): 实现获取 QR 码逻辑"
```

---

## Task 10: 前端 UI 组件 - 轮询状态逻辑

**Files:**
- Modify: `frontend/apps/settings/SettingsApp.tsx`

- [ ] **Step 1: 添加轮询 useEffect**

在组件内部，找到其他 `useEffect` 的位置，添加：

```typescript
// 轮询 QR 码状态
useEffect(() => {
    if (!qrCodeId || qrStatus === 'idle' || qrStatus === 'confirmed' || qrStatus === 'expired') {
        return;
    }
    
    const startTime = Date.now();
    const TIMEOUT = 5 * 60 * 1000; // 5 分钟
    const INTERVAL = 2000; // 2 秒
    
    const pollStatus = async () => {
        try {
            const result = await SettingsAPI.getQRCodeStatus(selectedChannel, qrCodeId);
            setQrStatus(result.status as any);
            
            if (result.status === 'confirmed') {
                toast.success('登录成功！');
            } else if (result.status === 'expired') {
                toast.error('二维码已过期');
            }
        } catch (error) {
            console.error('查询状态失败:', error);
        }
    };
    
    const intervalId = setInterval(() => {
        if (Date.now() - startTime > TIMEOUT) {
            clearInterval(intervalId);
            setQrStatus('expired');
            toast.error('请求超时，请重试');
            return;
        }
        pollStatus();
    }, INTERVAL);
    
    // 立即执行一次
    pollStatus();
    
    return () => clearInterval(intervalId);
}, [qrCodeId, qrStatus, selectedChannel]);
```

- [ ] **Step 2: 提交**

```bash
git add frontend/apps/settings/SettingsApp.tsx
git commit -m "feat(frontend): 实现 QR 码状态轮询逻辑"
```

---

## Task 11: 前端 UI 组件 - 渲染 UI

**Files:**
- Modify: `frontend/apps/settings/SettingsApp.tsx`

- [ ] **Step 1: 添加 UI 渲染代码**

在组件的 return 语句中，找到合适的位置（建议在"截图监控"区域之后），添加：

```typescript
{/* 远程通信 */}
<motion.section
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: 0.7 }}
    className="bg-white/80 backdrop-blur-sm rounded-2xl p-8 shadow-lg border border-gray-100"
>
    <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-purple-100 rounded-lg">
            <Zap className="w-5 h-5 text-purple-600" />
        </div>
        <h2 className="text-xl font-semibold text-gray-800">远程通信</h2>
    </div>

    <div className="space-y-6">
        {/* 通道选择 */}
        <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
                通道选择
            </label>
            <select
                value={selectedChannel}
                onChange={(e) => setSelectedChannel(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
                <option value="wechat">微信</option>
            </select>
        </div>

        {/* 获取二维码按钮 */}
        <div>
            <button
                onClick={handleGetQRCode}
                disabled={isLoadingQr}
                className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
                {isLoadingQr ? (
                    <span className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        获取中...
                    </span>
                ) : (
                    '获取二维码'
                )}
            </button>
        </div>

        {/* QR 码显示区域 */}
        {qrString && (
            <div className="border border-gray-200 rounded-lg p-6 bg-gray-50">
                <div className="flex flex-col items-center gap-4">
                    {/* QR 码 */}
                    <QRCode value={qrString} size={256} />
                    
                    {/* 状态显示 */}
                    <div className="text-center">
                        {qrStatus === 'waiting' && (
                            <p className="text-gray-600">等待扫描...</p>
                        )}
                        {qrStatus === 'scanning' && (
                            <p className="text-blue-600">正在扫描...</p>
                        )}
                        {qrStatus === 'confirmed' && (
                            <p className="text-green-600 font-semibold">登录成功 ✓</p>
                        )}
                        {qrStatus === 'expired' && (
                            <div className="space-y-2">
                                <p className="text-red-600">二维码已过期</p>
                                <button
                                    onClick={handleGetQRCode}
                                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                                >
                                    重新获取
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        )}
    </div>
</motion.section>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/apps/settings/SettingsApp.tsx
git commit -m "feat(frontend): 添加 QR 码 UI 组件"
```

---

## Task 12: 验证功能

**Files:**
- None (manual testing)

- [ ] **Step 1: 启动后端**

```bash
# 在项目根目录
python -m lifeprism.main
```

预期：后端启动成功，监听 8000 端口

- [ ] **Step 2: 启动前端**

```bash
cd frontend
npm run dev
```

预期：前端启动成功，浏览器打开 http://localhost:5173

- [ ] **Step 3: 测试获取 QR 码**

1. 打开设置页面
2. 找到"远程通信"区域
3. 点击"获取二维码"按钮
4. 预期：显示 QR 码，状态为"等待扫描..."

- [ ] **Step 4: 测试扫码流程**

1. 使用微信扫描 QR 码
2. 预期：状态变为"正在扫描..."
3. 在微信中确认登录
4. 预期：状态变为"登录成功 ✓"

- [ ] **Step 5: 验证 token 保存**

```bash
# 检查文件是否存在
cat localData/channel/wechat/account.json
```

预期：文件存在，包含 token 和 context_tokens 字段

- [ ] **Step 6: 测试过期场景**

1. 获取新的 QR 码
2. 等待 5 分钟不扫描
3. 预期：状态变为"二维码已过期"，显示"重新获取"按钮

- [ ] **Step 7: 最终提交**

```bash
git add -A
git commit -m "feat: 完成微信 QR 码登录功能"
```

---

## 完成检查清单

- [ ] 后端 API 正常响应
- [ ] 前端 UI 正常显示
- [ ] QR 码可以正常渲染
- [ ] 状态轮询正常工作
- [ ] 扫码成功后 token 保存到文件
- [ ] 过期和超时场景正常处理
- [ ] 所有代码已提交
