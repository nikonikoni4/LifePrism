"""微信消息处理模块
本文件源自 https://github.com/HKUDS/nanobot.git，经 AI 改写适配 lifeprism 项目。
"""

import uuid
from typing import Any, Dict

ITEM_TEXT: int = 1
ITEM_IMAGE: int = 2
ITEM_VOICE: int = 3
ITEM_FILE: int = 4
ITEM_VIDEO: int = 5

MESSAGE_TYPE_BOT: int = 2
MESSAGE_STATE_FINISH: int = 2

CLIENT_ID_LENGTH: int = 12


class WechatMessage:
    """微信消息处理"""

    _MEDIA_KEY_MAP: Dict[int, str] = {
        ITEM_IMAGE: "image_item",
        ITEM_VOICE: "voice_item",
        ITEM_FILE: "file_item",
        ITEM_VIDEO: "video_item"
    }

    _MEDIA_TYPE_MAP: Dict[int, str] = {
        ITEM_IMAGE: "image",
        ITEM_VOICE: "voice",
        ITEM_FILE: "file",
        ITEM_VIDEO: "video"
    }

    @staticmethod
    def parse_message(msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析接收到的消息

        Args:
            msg: 原始消息字典

        Returns:
            解析后的消息字典，包含 from_user_id, content, media, context_token
        """
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
                media_key = WechatMessage._MEDIA_KEY_MAP[item_type]
                media_item = item.get(media_key, {})
                result["media"].append({
                    "type": WechatMessage._MEDIA_TYPE_MAP[item_type],
                    "info": media_item
                })

        return result

    @staticmethod
    def build_text_message(to_user_id: str, text: str, context_token: str = "") -> Dict[str, Any]:
        """
        构造文本消息

        Args:
            to_user_id: 接收用户 ID
            text: 消息文本内容
            context_token: 上下文令牌（可选）

        Returns:
            构造好的消息字典
        """
        client_id = f"lifeprism-{uuid.uuid4().hex[:CLIENT_ID_LENGTH]}"

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
