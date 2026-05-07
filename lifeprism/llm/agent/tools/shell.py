from lifeprism.llm.agent.tools.base import Tool
from lifeprism.config import settings
# 确认可执行的命令
# 1. 文件阅读，搜索类
# 


class PowerShellTool(Tool):
    """Tool to execute PowerShell commands."""
    @property
    def name(self) -> str:
        return "exec_powershell"

    @property
    def description(self) -> str:
        return "需要使用控制台命令时使用，可执行的PowerShell命令："

    @property
    def parameters(self) -> dict[str, Any]:
        pass

    @property
    async def execute(self, **kwargs: Any) -> str:
        """powershell命令"""
        # 获取指令

        # 从指令中解析命令与路径

        # 命令和路径的权限验证

        # 权限通过之后，执行命令

        # 返回信息utf-8编码
        pass

    def _check_workspace_permission(self, allowed_path: str) -> bool:
        """检查工作空间权限"""
        pass

    def _check_cmd_permission(self, cmd: str) -> bool:
        """检查命令权限"""
        pass

    def _cmd_path_resolve(self, cmd: str) -> str:
        """解析命令路径"""
        pass
