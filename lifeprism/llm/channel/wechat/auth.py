import json
import asyncio
import qrcode
from pathlib import Path
from lifeprism.utils.logger import get_logger
from lifeprism.llm.channel.wechat.client import WechatClient

logger = get_logger(__name__)


class WechatAuth:
    """微信认证模块"""

    def __init__(self, client: WechatClient, state_file: Path):
        """初始化认证模块

        Args:
            client: 微信客户端实例
            state_file: 状态文件路径
        """
        self.client = client
        self.state_file = state_file

    def _print_qr_code(self, data: str):
        """在终端打印 QR 码

        Args:
            data: QR 码数据
        """
        qr = qrcode.QRCode()
        qr.add_data(data)
        qr.make()
        qr.print_ascii()
        logger.info("请使用微信扫描上方二维码登录")

    def load_state(self) -> dict:
        """加载保存的状态

        Returns:
            状态字典，如果文件不存在或加载失败则返回空字典
        """
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text())
        except Exception as e:
            logger.error(f"加载状态失败: {e}")
            return {}

    def save_state(self, state: dict):
        """保存状态

        Args:
            state: 要保存的状态字典
        """
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    async def qr_login(self) -> bool:
        """QR 码登录流程

        Returns:
            登录是否成功
        """
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
