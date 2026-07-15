"""
云端配置生成 API 路由

提供生成云端配置文件的 REST API 端点：
- POST /api/sync/generate-cloud-config: 生成 cloud_init.yaml

API 层不使用 try/except，异常自然冒泡到全局异常处理器。
"""

from fastapi import APIRouter
from pydantic import BaseModel

from lifeprism.config.cloud_config_generator import CloudConfigGenerator
from lifeprism.utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/sync", tags=["Cloud Config"])


class GenerateCloudConfigRequest(BaseModel):
    """生成云端配置请求"""

    replace_key: bool = False


@router.post("/generate-cloud-config", summary="生成云端配置文件")
async def generate_cloud_config(request: GenerateCloudConfigRequest | None = None):
    """生成云端配置文件 cloud_init.yaml

    从 keyring 读取所有 Key（LLM/微信/同步），生成完整的 cloud_init.yaml，
    保存到 {lifeprism_data_path}/cloud_init.yaml。

    **请求体**:
    - replace_key: 是否强制重新生成 sync_api_key（默认 False）

    **响应**:
    - cloud_config_path: 生成的配置文件路径
    - key_is_new: 同步 API Key 是否为新生成
    """
    replace_key = request.replace_key if request else False
    generator = CloudConfigGenerator()
    cloud_config_path, key_is_new = generator.generate_cloud_config(replace_key=replace_key)
    return {
        "cloud_config_path": cloud_config_path,
        "key_is_new": key_is_new,
    }
