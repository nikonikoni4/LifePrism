# 微信 Channel 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 lifeprism 中实现微信 channel，通过 ilinkai.weixin.qq.com API 实现与微信的消息互通

**Architecture:** 模块化设计，拆分为 config、client、auth、media、message、channel 六个模块，通过 MessageQueue (bus) 与 agent 通信

**Tech Stack:** Python 3.10+, httpx, asyncio, Cryptography (AES 解密)

---

## File Structure

**新建文件：**
- `lifeprism/llm/channel/wechat/__init__.py` - 导出 WechatChannel
- `lifeprism/llm/channel/wechat/config.py` - 配置类定义
- `lifeprism/llm/channel/wechat/client.py` - HTTP 客户端
- `lifeprism/llm/channel/wechat/auth.py` - QR 码登录
- `lifeprism/llm/channel/wechat/media.py` - 媒体处理
- `lifeprism/llm/channel/wechat/message.py` - 消息处理
- `lifeprism/llm/channel/wechat/channel.py` - 主类

**修改文件：**
- `lifeprism/llm/channel/base.py` - 定义 BaseChannel 基类

---

## Task 1: BaseChannel 基类

**Files:**
- Modify: `lifeprism/llm/channel/base.py`

- [ ] **Step 1: 实现 BaseChannel 基类**

```python
from abc import ABC, abstractmethod
from typing import Any
from lifeprism.llm.bus.queue import MessageQueue
from lifeprism.llm.bus.events import OutboundMessage
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)

class BaseChannel(ABC):
    """消息平台接入基类"""
    
    name: str = "base"
    
    def __init__(self, config: Any, bus: MessageQueue):
        self.config = config
        self.bus = bus
        self._running = False
    
    @abstractmethod
    async def start(self) -> None:
        """启动 channel，开始接收消息"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止 channel"""
        pass
    
    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """发送消息到平台"""
        pass
    
    def is_allowed(self, sender_id: str) -> bool:
        """检查发送者是否被允许"""
        allow_list = getattr(self.config, "allow_from", [])
        if not allow_list:
            logger.warning(f"{self.name}: allow_from is empty - all access denied")
            return False
        if "*" in allow_list:
            return True
        return str(sender_id) in allow_list
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/llm/channel/base.py
git commit -m "feat: 实现 BaseChannel 基类"
```

## Task 2: 配置模块

**Files:**
- Create: `lifeprism/llm/channel/wechat/__init__.py`
- Create: `lifeprism/llm/channel/wechat/config.py`

- [ ] **Step 1: 创建 __init__.py**

```python
# 占位文件，后续导出 WechatChannel
```

- [ ] **Step 2: 创建 WechatConfig 配置类**

```python
from dataclasses import dataclass, field

@dataclass
class WechatConfig:
    """微信 channel 配置"""
    enabled: bool = False
    base_url: str = "https://ilinkai.weixin.qq.com"
    cdn_base_url: str = "https://novac2c.cdn.weixin.qq.com/c2c"
    poll_timeout: int = 35
    allow_from: list[str] = field(default_factory=list)
```

- [ ] **Step 3: 提交**

```bash
git add lifeprism/llm/channel/wechat/__init__.py lifeprism/llm/channel/wechat/config.py
git commit -m "feat: 添加微信 channel 配置模块"
```

## Task 3: HTTP 客户端模块

**Files:**
- Create: `lifeprism/llm/channel/wechat/client.py`

- [ ] **Step 1: 实现 HTTP 客户端基础功能**

```python
import base64
import os
import httpx
from typing import Any
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)

ILINK_APP_ID = "bot"
ILINK_APP_CLIENT_VERSION = 0x020101  # 2.1.1
BASE_INFO = {"channel_version": "2.1.1"}

class WechatClient:
    """微信 API HTTP 客户端"""
    
    def __init__(self, base_url: str, token: str = ""):
        self.base_url = base_url
        self.token = token
        self._client: httpx.AsyncClient | None = None
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=60.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
    
    @staticmethod
    def _random_wechat_uin() -> str:
        """生成随机 UIN"""
        uint32 = int.from_bytes(os.urandom(4), "big")
        return base64.b64encode(str(uint32).encode()).decode()
    
    def _make_headers(self, auth: bool = True) -> dict[str, str]:
        """构建请求头"""
        headers = {
            "X-WECHAT-UIN": self._random_wechat_uin(),
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "iLink-App-Id": ILINK_APP_ID,
            "iLink-App-ClientVersion": str(ILINK_APP_CLIENT_VERSION),
        }
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    
    async def api_get(self, endpoint: str, params: dict | None = None, auth: bool = True) -> dict:
        """GET 请求"""
        if not self._client:
            raise RuntimeError("Client not initialized")
        url = f"{self.base_url}/{endpoint}"
        resp = await self._client.get(url, params=params, headers=self._make_headers(auth=auth))
        resp.raise_for_status()
        return resp.json()
    
    async def api_post(self, endpoint: str, body: dict | None = None, auth: bool = True) -> dict:
        """POST 请求"""
        if not self._client:
            raise RuntimeError("Client not initialized")
        url = f"{self.base_url}/{endpoint}"
        payload = body or {}
        if "base_info" not in payload:
            payload["base_info"] = BASE_INFO
        resp = await self._client.post(url, json=payload, headers=self._make_headers(auth=auth))
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/llm/channel/wechat/client.py
git commit -m "feat: 实现微信 HTTP 客户端"
```

## Task 4: 认证模块

**Files:**
- Create: `lifeprism/llm/channel/wechat/auth.py`

- [ ] **Step 1: 实现 QR 码打印功能**

```python
import json
import qrcode
from pathlib import Path
from lifeprism.utils.logger import get_logger
from lifeprism.llm.channel.wechat.client import WechatClient

logger = get_logger(__name__)

class WechatAuth:
    """微信认证模块"""
    
    def __init__(self, client: WechatClient, state_file: Path):
        self.client = client
        self.state_file = state_file
    
    def _print_qr_code(self, data: str):
        """在终端打印 QR 码"""
        qr = qrcode.QRCode()
        qr.add_data(data)
        qr.make()
        qr.print_ascii()
        logger.info("请使用微信扫描上方二维码登录")
    
    def load_state(self) -> dict:
        """加载保存的状态"""
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text())
        except Exception as e:
            logger.error(f"加载状态失败: {e}")
            return {}
    
    def save_state(self, state: dict):
        """保存状态"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    
    async def qr_login(self) -> bool:
        """QR 码登录流程"""
        try:
            # 获取 QR 码
            data = await self.client.api_get("ilink/bot/get_bot_qrcode", params={"bot_type": "3"}, auth=False)
            qrcode_id = data.get("qrcode", "")
            qrcode_img = data.get("qrcode_img_content", qrcode_id)
            if not qrcode_id:
                logger.error("获取 QR 码失败")
                return False
            
            self._print_qr_code(qrcode_img)
            
            # 轮询状态
            while True:
                status_data = await self.client.api_get(
                    "ilink/bot/get_qrcode_status",
                    params={"qrcode": qrcode_id},
                    auth=False
                )
                status = status_data.get("status", "")
                
                if status == "confirmed":
                    token = status_data.get("bot_token", "")
                    if token:
                        self.client.token = token
                        state = self.load_state()
                        state["token"] = token
                        self.save_state(state)
                        logger.info("登录成功")
                        return True
                elif status == "expired":
                    logger.error("QR 码已过期")
                    return False
                
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/llm/channel/wechat/auth.py
git commit -m "feat: 实现微信 QR 码登录"
```

## Task 5: 媒体处理模块

**Files:**
- Create: `lifeprism/llm/channel/wechat/media.py`

- [ ] **Step 1: 实现媒体下载和解密**

```python
import base64
import time
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from lifeprism.utils.logger import get_logger
from lifeprism.llm.channel.wechat.client import WechatClient

logger = get_logger(__name__)

class WechatMedia:
    """微信媒体处理"""
    
    def __init__(self, client: WechatClient, media_dir: Path):
        self.client = client
        self.media_dir = media_dir
        self.media_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _decrypt_aes_ecb(data: bytes, key_b64: str) -> bytes:
        """AES-ECB 解密"""
        key = base64.b64decode(key_b64)
        cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()
    
    async def download_media(self, media_info: dict, media_type: str) -> str | None:
        """下载媒体文件"""
        try:
            full_url = media_info.get("full_url", "")
            encrypt_param = media_info.get("encrypt_query_param", "")
            aes_key = media_info.get("aes_key", "")
            
            if not full_url and not encrypt_param:
                return None
            
            # 下载
            if not self.client._client:
                return None
            
            url = full_url or f"{self.client.base_url.replace('ilinkai', 'novac2c.cdn')}/c2c/download?encrypted_query_param={encrypt_param}"
            resp = await self.client._client.get(url)
            resp.raise_for_status()
            data = resp.content

            
            # 解密
            if aes_key and data:
                data = self._decrypt_aes_ecb(data, aes_key)
            
            if not data:
                return None
            
            # 保存
            ext_map = {"image": ".jpg", "voice": ".mp3", "file": ".bin", "video": ".mp4"}
            ext = ext_map.get(media_type, ".bin")
            filename = f"{media_type}_{int(time.time())}_{hash(url) % 100000}{ext}"
            file_path = self.media_dir / filename
            file_path.write_bytes(data)
            
            return str(file_path)
        except Exception as e:
            logger.error(f"下载媒体失败: {e}")
            return None
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/llm/channel/wechat/media.py
git commit -m "feat: 实现微信媒体下载和解密"
```

## Task 6: 消息处理模块

**Files:**
- Create: `lifeprism/llm/channel/wechat/message.py`

- [ ] **Step 1: 实现消息解析和构造**

```python
import uuid
from typing import Any
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)

ITEM_TEXT = 1
ITEM_IMAGE = 2
ITEM_VOICE = 3
ITEM_FILE = 4
ITEM_VIDEO = 5

MESSAGE_TYPE_BOT = 2
MESSAGE_STATE_FINISH = 2

class WechatMessage:
    """微信消息处理"""
    
    @staticmethod
    def parse_message(msg: dict) -> dict:
        """解析接收到的消息"""
        result = {
            "from_user_id": msg.get("from_user_id", ""),
            "content": "",
            "media": [],
            "context_token": msg.get("context_token", "")
        }
        
        item_list = msg.get("item_list", [])
        for item in item_list:
            item_type = item.get("type")
            if item_type == ITEM_TEXT:
                text_item = item.get("text_item", {})
                result["content"] += text_item.get("text", "")
            elif item_type in [ITEM_IMAGE, ITEM_VOICE, ITEM_FILE, ITEM_VIDEO]:
                media_key = {ITEM_IMAGE: "image_item", ITEM_VOICE: "voice_item", 
                            ITEM_FILE: "file_item", ITEM_VIDEO: "video_item"}[item_type]
                media_item = item.get(media_key, {})
                result["media"].append({
                    "type": {ITEM_IMAGE: "image", ITEM_VOICE: "voice", 
                            ITEM_FILE: "file", ITEM_VIDEO: "video"}[item_type],
                    "info": media_item
                })
        
        return result

    
    @staticmethod
    def build_text_message(to_user_id: str, text: str, context_token: str = "") -> dict:
        """构造文本消息"""
        client_id = f"lifeprism-{uuid.uuid4().hex[:12]}"
        
        msg = {
            "from_user_id": "",
            "to_user_id": to_user_id,
            "client_id": client_id,
            "message_type": MESSAGE_TYPE_BOT,
            "message_state": MESSAGE_STATE_FINISH,
            "item_list": [{"type": ITEM_TEXT, "text_item": {"text": text}}]
        }
        
        if context_token:
            msg["context_token"] = context_token
        
        return {"msg": msg}
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/llm/channel/wechat/message.py
git commit -m "feat: 实现微信消息解析和构造"
```

## Task 7: WechatChannel 主类（第一部分）

**Files:**
- Create: `lifeprism/llm/channel/wechat/channel.py`

- [ ] **Step 1: 实现 WechatChannel 初始化和启动**

```python
import asyncio
from pathlib import Path
from lifeprism.llm.channel.base import BaseChannel
from lifeprism.llm.channel.wechat.config import WechatConfig
from lifeprism.llm.channel.wechat.client import WechatClient
from lifeprism.llm.channel.wechat.auth import WechatAuth
from lifeprism.llm.channel.wechat.media import WechatMedia
from lifeprism.llm.channel.wechat.message import WechatMessage
from lifeprism.llm.bus.queue import MessageQueue
from lifeprism.llm.bus.events import InboundMessage, OutboundMessage
from lifeprism.config.settings_manager import settings
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)

class WechatChannel(BaseChannel):
    """微信 Channel"""
    
    name = "wechat"
    
    def __init__(self, config: WechatConfig, bus: MessageQueue):
        super().__init__(config, bus)
        self.config: WechatConfig = config
        
        # 路径设置
        self.wechat_dir = settings.channel_path / "wechat"
        self.media_dir = self.wechat_dir / "media"
        self.state_file = self.wechat_dir / "account.json"
        
        # 模块
        self.client: WechatClient | None = None
        self.auth: WechatAuth | None = None
        self.media: WechatMedia | None = None
        
        # 状态
        self._poll_task: asyncio.Task | None = None
        self._context_tokens: dict[str, str] = {}

    
    async def start(self):
        """启动 channel"""
        if self._running:
            return
        
        self._running = True
        logger.info("启动微信 channel")
        
        # 初始化客户端
        self.client = WechatClient(self.config.base_url)
        await self.client.__aenter__()
        
        # 初始化认证
        self.auth = WechatAuth(self.client, self.state_file)
        
        # 加载状态
        state = self.auth.load_state()
        token = state.get("token", "")
        self._context_tokens = state.get("context_tokens", {})
        
        if token:
            self.client.token = token
            logger.info("使用已保存的 token")
        else:
            # QR 登录
            success = await self.auth.qr_login()
            if not success:
                logger.error("登录失败")
                self._running = False
                return
        
        # 初始化媒体处理
        self.media = WechatMedia(self.client, self.media_dir)
        
        # 启动长轮询
        self._poll_task = asyncio.create_task(self._poll_loop())
    
    async def stop(self):
        """停止 channel"""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self.client:
            await self.client.__aexit__(None, None, None)
        logger.info("微信 channel 已停止")
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/llm/channel/wechat/channel.py
git commit -m "feat: 实现 WechatChannel 初始化和启动"
```

## Task 8: WechatChannel 主类（第二部分 - 消息接收）

**Files:**
- Modify: `lifeprism/llm/channel/wechat/channel.py`

- [ ] **Step 1: 实现长轮询和消息处理**

在 `WechatChannel` 类中添加：

```python
    async def _poll_loop(self):
        """长轮询循环"""
        get_updates_buf = ""
        
        while self._running:
            try:
                body = {"get_updates_buf": get_updates_buf}
                data = await self.client.api_post("ilink/bot/getupdates", body)
                
                get_updates_buf = data.get("get_updates_buf", "")
                messages = data.get("messages", [])
                
                for msg in messages:
                    await self._handle_wechat_message(msg)
                
            except Exception as e:
                logger.error(f"长轮询错误: {e}")
                await asyncio.sleep(5)
    
    async def _handle_wechat_message(self, msg: dict):
        """处理微信消息"""
        parsed = WechatMessage.parse_message(msg)
        from_user_id = parsed["from_user_id"]
        content = parsed["content"]
        context_token = parsed["context_token"]
        
        # 检查权限
        if not self.is_allowed(from_user_id):
            logger.warning(f"拒绝未授权用户: {from_user_id}")
            return
        
        # 保存 context_token
        if context_token:
            self._context_tokens[from_user_id] = context_token
        
        # 下载媒体
        media_paths = []
        for media_item in parsed["media"]:
            media_type = media_item["type"]
            media_info = media_item["info"]
            path = await self.media.download_media(media_info, media_type)
            if path:
                media_paths.append(path)

        
        # 构造 InboundMessage
        inbound_msg = InboundMessage(
            type="chat",
            content=content,
            session_id=f"wechat:{from_user_id}",
            extra={
                "media": media_paths,
                "sender_id": from_user_id,
                "chat_id": from_user_id
            }
        )
        
        # 发送到 bus
        await self.bus.publish_inbound(inbound_msg)
        logger.info(f"接收到微信消息: {from_user_id}")
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/llm/channel/wechat/channel.py
git commit -m "feat: 实现微信消息接收和长轮询"
```

## Task 9: WechatChannel 主类（第三部分 - 消息发送）

**Files:**
- Modify: `lifeprism/llm/channel/wechat/channel.py`

- [ ] **Step 1: 实现消息发送**

在 `WechatChannel` 类中添加：

```python
    async def send(self, msg: OutboundMessage):
        """发送消息到微信"""
        if not self.client or not self._running:
            logger.warning("客户端未初始化或未运行")
            return
        
        # 提取用户 ID
        session_id = msg.session_id or ""
        if not session_id.startswith("wechat:"):
            logger.error(f"无效的 session_id: {session_id}")
            return
        
        to_user_id = session_id.replace("wechat:", "")
        context_token = self._context_tokens.get(to_user_id, "")
        
        # 提取内容
        content = ""
        if msg.response and hasattr(msg.response, "content"):
            content = msg.response.content
        
        if not content:
            return
        
        # 构造并发送消息
        try:
            message_body = WechatMessage.build_text_message(to_user_id, content, context_token)
            await self.client.api_post("ilink/bot/sendmessage", message_body)
            logger.info(f"发送消息到微信: {to_user_id}")
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/llm/channel/wechat/channel.py
git commit -m "feat: 实现微信消息发送"
```

## Task 10: 导出和集成

**Files:**
- Modify: `lifeprism/llm/channel/wechat/__init__.py`

- [ ] **Step 1: 导出 WechatChannel**

```python
from lifeprism.llm.channel.wechat.channel import WechatChannel
from lifeprism.llm.channel.wechat.config import WechatConfig

__all__ = ["WechatChannel", "WechatConfig"]
```

- [ ] **Step 2: 提交**

```bash
git add lifeprism/llm/channel/wechat/__init__.py
git commit -m "feat: 导出 WechatChannel 和 WechatConfig"
```

---

## 自我审查

**Spec 覆盖检查：**
- ✅ BaseChannel 基类定义
- ✅ WechatConfig 配置
- ✅ HTTP 客户端和 API 调用
- ✅ QR 码登录认证
- ✅ 媒体文件下载和解密
- ✅ 消息解析和构造
- ✅ 长轮询消息接收
- ✅ 消息发送
- ✅ 与 MessageQueue (bus) 集成
- ✅ 路径管理（settings.channel_path）

**占位符检查：**
- ✅ 无 TBD、TODO
- ✅ 所有代码块完整
- ✅ 所有步骤有具体实现

**类型一致性检查：**
- ✅ WechatConfig 在所有任务中一致
- ✅ WechatClient、WechatAuth、WechatMedia、WechatMessage 命名一致
- ✅ InboundMessage、OutboundMessage 使用一致

计划完成！

