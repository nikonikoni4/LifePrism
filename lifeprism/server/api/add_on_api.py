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


router = APIRouter(prefix="/api/v2/add_on", tags=["Add-on - 扩展功能"])


@router.get("/expand_dir", response_model=ExpandDirListResponse)
async def get_expand_dirs():
    """获取所有扩展数据文件夹"""
    try:
        expand_dirs = add_on_service.get_all_expand_dirs()
        return ExpandDirListResponse(expand_dirs=expand_dirs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expand_dir", response_model=ExpandDirItem, status_code=201)
async def create_expand_dir(data: CreateExpandDirRequest):
    """创建新的扩展数据文件夹"""
    try:
        return add_on_service.create_expand_dir(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/expand_dir/{id}", response_model=ExpandDirItem)
async def update_expand_dir(id: str, data: UpdateExpandDirRequest):
    """更新扩展数据文件夹配置"""
    try:
        return add_on_service.update_expand_dir(id, data)
    except ValueError as e:
        # ValueError 用于业务逻辑错误（路径无效、ID不存在等）
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/expand_dir/{id}", status_code=204)
async def delete_expand_dir(id: str):
    """删除扩展数据文件夹配置（仅删除配置，不删除磁盘文件）"""
    try:
        add_on_service.delete_expand_dir(id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
