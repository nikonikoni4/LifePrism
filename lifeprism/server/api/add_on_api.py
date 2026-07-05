"""
Add-on 扩展功能 API 路由
"""

from fastapi import APIRouter, HTTPException

from lifeprism.server.schemas.add_on_schemas import (
    CreateExpandDirRequest,
    UpdateExpandDirRequest,
    ExpandDirItem,
    ExpandDirListResponse,
)
from lifeprism.server.services import add_on_service
from lifeprism.utils.exceptions import LWBaseError
from lifeprism.utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/add_on", tags=["Add-on - 扩展功能"])


@router.get("/expand_dir", response_model=ExpandDirListResponse, summary="获取所有扩展数据文件夹")
async def get_expand_dirs():
    """获取所有扩展数据文件夹"""
    try:
        expand_dirs = add_on_service.get_all_expand_dirs()
        return ExpandDirListResponse(expand_dirs=expand_dirs)
    except LWBaseError:
        raise
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("获取扩展文件夹列表失败: error=%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.post("/expand_dir", response_model=ExpandDirItem, status_code=201, summary="创建新的扩展数据文件夹")
async def create_expand_dir(data: CreateExpandDirRequest):
    """创建新的扩展数据文件夹"""
    try:
        return add_on_service.create_expand_dir(data)
    except LWBaseError:
        raise
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("创建扩展文件夹失败（业务逻辑错误）: error=%s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("创建扩展文件夹失败（服务器错误）: error=%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.patch("/expand_dir/{id}", response_model=ExpandDirItem, summary="更新扩展数据文件夹配置")
async def update_expand_dir(id: str, data: UpdateExpandDirRequest):
    """更新扩展数据文件夹配置"""
    try:
        return add_on_service.update_expand_dir(id, data)
    except LWBaseError:
        raise
    except HTTPException:
        raise
    except ValueError as e:
        error_msg = str(e)
        # 判断是否为资源不存在错误
        if "不存在" in error_msg:
            logger.warning("更新扩展文件夹失败（资源不存在）: id=%s, error=%s", id, e)
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            logger.warning("更新扩展文件夹失败（业务逻辑错误）: id=%s, error=%s", id, e)
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error("更新扩展文件夹失败（服务器错误）: id=%s, error=%s", id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.delete("/expand_dir/{id}", status_code=204, summary="删除扩展数据文件夹配置")
async def delete_expand_dir(id: str):
    """删除扩展数据文件夹配置（仅删除配置，不删除磁盘文件）"""
    try:
        add_on_service.delete_expand_dir(id)
    except LWBaseError:
        raise
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("删除扩展文件夹失败（资源不存在）: id=%s, error=%s", id, e)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("删除扩展文件夹失败（服务器错误）: id=%s, error=%s", id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")
