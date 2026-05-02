"""微信媒体处理模块
本文件源自 https://github.com/HKUDS/nanobot.git，经 AI 改写适配 lifeprism 项目。
"""

import base64
import httpx
import uuid
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from lifeprism.utils.logger import get_logger
from lifeprism.llm.channel.wechat.client import WechatClient
from lifeprism.llm.channel.wechat.exceptions import WechatMediaError

logger = get_logger(__name__)


class WechatMedia:
    """微信媒体处理

    负责微信媒体文件的下载、解密和存储。

    Attributes:
        client: 微信 API 客户端
        media_dir: 媒体文件存储目录
    """

    def __init__(self, client: WechatClient, media_dir: Path):
        """初始化媒体处理器

        Args:
            client: 微信 API 客户端实例
            media_dir: 媒体文件存储目录路径
        """
        self.client = client
        self.media_dir = media_dir
        self.media_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _decrypt_aes_ecb(data: bytes, key_b64: str) -> bytes:
        """AES-ECB 解密

        注意：使用 ECB 模式是因为微信 API 要求此格式，不建议在其他场景使用 ECB 模式。

        Args:
            data: 加密的字节数据
            key_b64: Base64 编码的 AES 密钥

        Returns:
            解密后的字节数据
        """
        key = base64.b64decode(key_b64)
        cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()

    async def download_media(self, media_info: dict, media_type: str) -> str | None:
        """下载媒体文件

        从微信服务器下载媒体文件，如果需要则进行解密，并保存到本地。

        Args:
            media_info: 媒体信息字典，包含 full_url、encrypt_query_param、aes_key 等字段
            media_type: 媒体类型，如 "image"、"voice"、"file"、"video"

        Returns:
            本地文件路径字符串，失败返回 None
        """
        try:
            full_url = media_info.get("full_url", "")
            encrypt_param = media_info.get("encrypt_query_param", "")
            aes_key = media_info.get("aes_key", "")

            if not full_url and not encrypt_param:
                logger.warning("媒体信息缺少 URL 和加密参数")
                return None

            # 检查客户端是否已初始化
            if not self.client._client:
                logger.error("HTTP 客户端未初始化")
                return None

            # 下载
            url = full_url or f"{self.client.base_url.replace('ilinkai', 'novac2c.cdn')}/c2c/download?encrypted_query_param={encrypt_param}"
            resp = await self.client._client.get(url)
            resp.raise_for_status()
            data = resp.content

            # 解密
            if aes_key and data:
                data = self._decrypt_aes_ecb(data, aes_key)

            if not data:
                logger.warning(f"下载的媒体数据为空: {media_type}")
                return None

            # 保存
            ext_map = {"image": ".jpg", "voice": ".mp3", "file": ".bin", "video": ".mp4"}
            ext = ext_map.get(media_type, ".bin")
            filename = f"{media_type}_{uuid.uuid4().hex[:12]}{ext}"
            file_path = self.media_dir / filename
            file_path.write_bytes(data)

            logger.info(f"媒体文件已保存: {file_path}, 类型: {media_type}, 大小: {len(data)} bytes")
            return str(file_path)
        except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as e:
            logger.error(f"下载媒体网络错误: {e}, 类型: {media_type}", exc_info=True)
            raise WechatMediaError(f"媒体下载失败: {e}") from e
        except (KeyError, ValueError) as e:
            logger.error(f"媒体数据解析错误: {e}, 类型: {media_type}", exc_info=True)
            raise WechatMediaError(f"媒体数据格式错误: {e}") from e
        except OSError as e:
            logger.error(f"媒体文件保存错误: {e}, 类型: {media_type}", exc_info=True)
            raise WechatMediaError(f"媒体文件保存失败: {e}") from e
