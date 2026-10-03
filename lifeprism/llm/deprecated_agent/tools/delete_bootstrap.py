"""bootstrap.md 删除工具

由于暂时不想提供删除文件以及bash工具，所以暂时添加bootstrap.md删除工具
"""

from lifeprism.config import settings

from .base import ERROR, SUCCESS, Tool


class DeleteBootstrapTool(Tool):
    """删除 bootstrap.md 文件的工具"""

    @property
    def name(self) -> str:
        return "delete_bootstrap"

    @property
    def description(self) -> str:
        return "删除 bootstrap.md 文件"

    @property
    def parameters(self) -> dict[str, dict]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, **kwargs) -> str:
        bootstrap_path = settings.lifeprism_data_path / "agent/chat/bootstrap.md"
        if not bootstrap_path.exists():
            return f"{ERROR}文件 {bootstrap_path} 不存在"

        try:
            bootstrap_path.unlink()
            return f"{SUCCESS}已成功删除 {bootstrap_path}"
        except Exception as e:
            return f"{ERROR}删除文件失败: {e}"
