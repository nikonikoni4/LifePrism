"""
PlanDoc 服务层 - Plan Doc 计划书业务逻辑

设计原则：数据库只存 meta 信息，内容存 md 文件
文件存储路径：frontend/customData/plan/{id}.md
"""
from typing import Optional, List
from pathlib import Path
import os

from lifeprism.server.schemas.goal_schemas import (
    PlanDocItem,
    PlanDocListResponse,
    CreatePlanDocRequest,
    UpdatePlanDocRequest,
)
from lifeprism.server.providers.plan_doc_provider import plan_doc_provider
from lifeprism.utils import get_logger

logger = get_logger(__name__)

# 计划书文件存储目录（相对于项目根目录）
PLAN_DOC_DIR = Path("frontend/customData/plan")


class PlanDocService:
    """
    计划书服务类

    提供 Plan Doc 的业务逻辑操作
    数据库存储 meta 信息，文件系统存储 content
    """

    def __init__(self):
        self.plan_doc_provider = plan_doc_provider
        self._ensure_plan_doc_dir()

    def _ensure_plan_doc_dir(self):
        """确保计划书目录存在"""
        try:
            PLAN_DOC_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建计划书目录失败: {e}")

    def _get_plan_doc_path(self, doc_id: str) -> Path:
        """获取计划书文件路径"""
        return PLAN_DOC_DIR / f"{doc_id}.md"

    def _read_content_from_file(self, doc_id: str) -> str:
        """从文件读取内容，不存在则返回空字符串"""
        file_path = self._get_plan_doc_path(doc_id)
        try:
            if file_path.exists():
                return file_path.read_text(encoding='utf-8')
            return ""
        except Exception as e:
            logger.error(f"读取计划书文件 {doc_id} 失败: {e}")
            return ""

    def _write_content_to_file(self, doc_id: str, content: str):
        """写入内容到文件"""
        file_path = self._get_plan_doc_path(doc_id)
        try:
            self._ensure_plan_doc_dir()
            file_path.write_text(content, encoding='utf-8')
            logger.info(f"写入计划书文件 {doc_id} 成功")
        except Exception as e:
            logger.error(f"写入计划书文件 {doc_id} 失败: {e}")

    def _delete_content_file(self, doc_id: str):
        """删除对应的 md 文件"""
        file_path = self._get_plan_doc_path(doc_id)
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"删除计划书文件 {doc_id} 成功")
        except Exception as e:
            logger.error(f"删除计划书文件 {doc_id} 失败: {e}")

    def _convert_db_item_to_plan_doc_item(self, item: dict, include_content: bool = False) -> PlanDocItem:
        """
        将数据库记录转换为 PlanDocItem

        Args:
            item: 数据库记录
            include_content: 是否从文件读取内容
        """
        content = ""
        if include_content:
            content = self._read_content_from_file(item['id'])

        return PlanDocItem(
            id=item['id'],
            goal_id=item['goal_id'],
            title=item['title'],
            content=content,
            status=item.get('status', 'active'),
            order_index=item.get('order_index', 0),
            created_at=item.get('created_at', ''),
            updated_at=item.get('updated_at')
        )

    def get_plan_docs(
        self,
        goal_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> PlanDocListResponse:
        """
        获取计划书列表（只返回 meta 信息，不含 content）

        Args:
            goal_id: 按目标筛选
            doc_type: 按类型筛选（暂未使用）
            page: 页码
            page_size: 每页数量

        Returns:
            PlanDocListResponse: 计划书列表响应
        """
        if goal_id:
            items = self.plan_doc_provider.get_plan_docs_by_goal(goal_id)
        else:
            # 如果没有指定 goal_id，返回空列表（或可以实现获取所有的逻辑）
            items = []

        plan_doc_items = [self._convert_db_item_to_plan_doc_item(item, include_content=False) for item in items]
        return PlanDocListResponse(items=plan_doc_items)

    def get_plan_docs_by_goal(self, goal_id: str) -> PlanDocListResponse:
        """
        获取指定目标的所有计划书（只返回 meta 信息）

        Args:
            goal_id: 目标 ID

        Returns:
            PlanDocListResponse: 计划书列表响应
        """
        items = self.plan_doc_provider.get_plan_docs_by_goal(goal_id)
        plan_doc_items = [self._convert_db_item_to_plan_doc_item(item, include_content=False) for item in items]
        return PlanDocListResponse(items=plan_doc_items)

    def get_plan_doc_detail(self, doc_id: str) -> Optional[PlanDocItem]:
        """
        获取计划书详情（meta + 文件内容）

        Args:
            doc_id: 计划书 ID

        Returns:
            Optional[PlanDocItem]: 计划书详情，不存在返回 None
        """
        item = self.plan_doc_provider.get_plan_doc_by_id(doc_id)
        if not item:
            return None
        return self._convert_db_item_to_plan_doc_item(item, include_content=True)

    def create_plan_doc(self, request: CreatePlanDocRequest) -> Optional[PlanDocItem]:
        """
        创建计划书（数据库 + 文件）

        Args:
            request: 创建计划书请求

        Returns:
            Optional[PlanDocItem]: 新创建的计划书，失败返回 None
        """
        data = {
            'goal_id': request.goal_id,
            'title': request.title,
        }

        new_id = self.plan_doc_provider.create_plan_doc(data)
        if new_id is None:
            return None

        # 创建 md 文件
        self._write_content_to_file(new_id, request.content)

        return self.get_plan_doc_detail(new_id)

    def update_plan_doc(self, doc_id: str, request: UpdatePlanDocRequest) -> Optional[PlanDocItem]:
        """
        更新计划书（meta + 文件内容）

        Args:
            doc_id: 计划书 ID
            request: 更新计划书请求

        Returns:
            Optional[PlanDocItem]: 更新后的计划书，失败返回 None
        """
        update_data = {}
        explicitly_set_fields = request.model_fields_set

        if 'title' in explicitly_set_fields:
            update_data['title'] = request.title
        if 'status' in explicitly_set_fields:
            update_data['status'] = request.status

        # 更新数据库 meta（如果有需要更新的字段）
        if update_data:
            success = self.plan_doc_provider.update_plan_doc(doc_id, update_data)
            if not success:
                # 检查文档是否存在
                existing = self.plan_doc_provider.get_plan_doc_by_id(doc_id)
                if not existing:
                    return None

        # 更新文件内容
        if 'content' in explicitly_set_fields:
            self._write_content_to_file(doc_id, request.content)

        return self.get_plan_doc_detail(doc_id)

    def delete_plan_doc(self, doc_id: str) -> bool:
        """
        删除计划书（数据库 + 文件）

        Args:
            doc_id: 计划书 ID

        Returns:
            bool: 是否成功
        """
        # 先删除文件
        self._delete_content_file(doc_id)
        # 再删除数据库记录
        return self.plan_doc_provider.delete_plan_doc(doc_id)


# 创建全局单例
plan_doc_service = PlanDocService()
