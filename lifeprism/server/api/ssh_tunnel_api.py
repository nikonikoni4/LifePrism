"""SSH 隧道管理 API 路由

提供 SSH 隧道管理的 3 个 REST API 端点（仅 full 模式注册路由）：
- POST /api/v2/settings/ssh-tunnel/enable: 自动生成 ed25519 密钥对（如无私钥）+ 返回派生公钥
- GET /api/v2/settings/ssh-tunnel/public-key: 从 keyring 私钥实时派生公钥
- POST /api/v2/settings/ssh-tunnel/test: 测试 SSH 连接 + 隧道建立 + 远程 8102 可达性

API 层不使用 try/except，异常自然冒泡到全局异常处理器。
SSHTunnel.test_connection() 内部已封装"建立→验证→关闭"完整测试逻辑，
不会抛异常到 API 层（结构化返回 status=error），且不留孤儿进程。

参考:
- Issue: .scratch/ssh-tunnel-integration/issues/04-ssh-tunnel-api.md
- PRD: .scratch/ssh-tunnel-integration/prd.md
- 错误处理: docs/coding-rules/backend-error-handling.md
"""

import asyncssh
from fastapi import APIRouter
from pydantic import BaseModel, Field

from lifeprism.config.settings_manager import settings
from lifeprism.sync.ssh_tunnel import SSHTunnel
from lifeprism.utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/settings/ssh-tunnel", tags=["Settings - SSH Tunnel"])

# keyring 中存储 SSH 私钥的 storage key 名称
_STORAGE_KEY = "ssh_tunnel_private_key"


# ==================== 请求/响应 Schema ====================


class SSHTunnelTestRequest(BaseModel):
    """SSH 隧道测试连接请求参数

    用户在前端填写 SSH 连接参数后点击"测试连接"按钮时提交。
    私钥不通过请求体传递，从 keyring 读取（与 enable 端点保持一致）。
    """

    host: str = Field(..., description="SSH 服务器地址（如 1.2.3.4）")
    port: int = Field(default=22, ge=1, le=65535, description="SSH 端口，默认 22")
    username: str = Field(..., description="SSH 用户名（如 lifeprism）")
    local_port: int = Field(default=8102, ge=1, le=65535, description="本地监听端口，默认 8102")
    remote_port: int = Field(default=8102, ge=1, le=65535, description="远程目标端口，默认 8102")


# ==================== API 端点 ====================


@router.post("/enable", summary="启用 SSH 隧道（自动准备密钥）")
async def enable_ssh_tunnel():
    """启用 SSH 隧道模式：自动生成 ed25519 密钥对（如 keyring 中无私钥）

    用户切换到 SSH 模式时调用。如 keyring 中无私钥则自动生成 ed25519 密钥对
    （私钥存 keyring，公钥丢弃不存储），如有私钥则保留不覆盖（避免已部署到
    云端的公钥失效）。返回当前公钥（从私钥实时派生）。

    **响应**:
    - public_key: 公钥字符串（OpenSSH 格式，以 `ssh-ed25519 ` 开头）
    - is_new: 本次是否新生成了密钥对（True=新生成，False=保留已有私钥）
    """
    existing_private_key = settings.get_storage_key(_STORAGE_KEY)

    if existing_private_key:
        # keyring 已有私钥 → 保留不覆盖，从已有私钥派生公钥
        logger.info("SSH 私钥已存在，保留不覆盖，从已有私钥派生公钥")
        private_key_obj = asyncssh.import_private_key(existing_private_key)
        is_new = False
    else:
        # keyring 无私钥 → 自动生成 ed25519 密钥对
        logger.info("SSH 私钥不存在，自动生成 ed25519 密钥对")
        private_key_obj = asyncssh.generate_private_key("ssh-ed25519")
        private_key_pem = private_key_obj.export_private_key().decode("utf-8")
        settings.set_storage_key(_STORAGE_KEY, private_key_pem)
        is_new = True

    # 从私钥实时派生公钥（不存储，每次实时派生）
    public_key = private_key_obj.export_public_key().decode("utf-8")

    return {
        "public_key": public_key,
        "is_new": is_new,
    }


@router.get("/public-key", summary="获取 SSH 公钥（从私钥实时派生）")
async def get_ssh_public_key():
    """获取 SSH 公钥（从 keyring 私钥实时派生）

    用于前端进入 SSH 配置页面时加载展示，用户可复制公钥部署到云端
    `~/.ssh/authorized_keys`。

    keyring 无私钥时返回空字符串（不抛错），前端据此判断"未启用 SSH 模式"。

    **响应**:
    - public_key: 公钥字符串（OpenSSH 格式），无私钥时为空字符串
    """
    existing_private_key = settings.get_storage_key(_STORAGE_KEY)

    if not existing_private_key:
        # keyring 无私钥 → 返回空字符串（不抛错）
        return {"public_key": ""}

    # 从私钥实时派生公钥
    private_key_obj = asyncssh.import_private_key(existing_private_key)
    public_key = private_key_obj.export_public_key().decode("utf-8")

    return {"public_key": public_key}


@router.post("/test", summary="测试 SSH 隧道连接")
async def test_ssh_tunnel(request: SSHTunnelTestRequest):
    """测试 SSH 隧道连接 + 远程 8102 可达性

    调用 SSHTunnel.test_connection()（Issue 03 实现）执行一次性测试：
    1. 建立 SSH 连接
    2. 启动本地端口转发
    3. 通过本地端口转发访问远程健康端点验证可达
    4. 关闭连接（不留孤儿进程）

    test_connection() 内部已封装"建立→验证→关闭"完整逻辑，不会抛异常到
    API 层（结构化返回 status=error），API 层直接返回测试结果。

    **请求体**: SSHTunnelTestRequest（SSH 连接参数，私钥从 keyring 读取）

    **响应**:
    - 成功: ``{"status": "ok", "remote_response": {...}}``
    - 失败: ``{"status": "error", "error": "<错误消息>", "code": "<错误码>"}``，
      错误码如 SSH_KEY_REJECTED / SSH_NETWORK_UNREACHABLE / SSH_LOCAL_PORT_IN_USE
      / REMOTE_UNREACHABLE 等
    """
    private_key_pem = settings.get_storage_key(_STORAGE_KEY)

    # SSHTunnel.test_connection() 内部已处理所有异常并结构化返回，
    # 不会抛异常到 API 层，且通过 finally 调用 close() 确保不留孤儿进程。
    tunnel = SSHTunnel(
        host=request.host,
        port=request.port,
        username=request.username,
        private_key=private_key_pem,
        local_port=request.local_port,
        remote_host="127.0.0.1",
        remote_port=request.remote_port,
    )
    return await tunnel.test_connection()
