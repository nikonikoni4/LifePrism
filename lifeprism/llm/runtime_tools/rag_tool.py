"""原生 myagent 的个人记录检索工具。"""

from lifeprism.llm.runtime_tools.base import Tool, ToolErrorType, ToolResult
from lifeprism.rag.service import get_rag_service
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class RagSearchTool(Tool):
    """本次检索可选 BM25，生命周期由版本化 RAG 服务管理。"""

    def __init__(self, service=None):
        super().__init__()
        self.service = service

    @property
    def name(self) -> str:
        return "rag_search"

    @property
    def description(self) -> str:
        return (
            "工具描述：用于检索个人资料和日记的工具，心情等其他内容不包含在rag检索之内"
            "使用情况：可用于检索dairy、user文件夹下的文档时有限使用rag_search"
            "结果返回: 返回最终匹配的前k个内容"
            "可使用的场景：1. 用户主动询问相关内容 2. 对于用户当前消息的回应需要结合个人资料和日记回答"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "description": "单个主题的自然语言检索词；查询时，对问题进行query改写，一个问题可以经过多个改写来进行多次查询； 问题涉及多个方面时可拆成不同角度分别检索，结果不足时换词重试",
                },
                "k": {
                    "type": "integer",
                    "description": "当需要大范围查询时增大k的数量，当不需要大范围查询时减小k的数量",
                    "minimum": 3,
                    "maximum": 20,
                    "default": 5,
                },
                "use_bm25": {
                    "type": "boolean",
                    "default": False,
                    "description": "只有查询包含明确关键词，例如人名、项目名、具体术语或需精确匹配的词语时才启用 bm25 通道；默认 false，只用 vec",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, k: int = 5, use_bm25: bool = False) -> ToolResult | str:
        """执行检索；失败返回工具错误，不泄露服务商凭据。"""
        try:
            service = self.service or get_rag_service()
            results = await service.search(query, k, use_bm25=use_bm25)
            if not results:
                return "未检索到相关内容。"
            blocks = []
            for i, hit in enumerate(results, 1):
                sources = "\n".join(f"来源：{s.path}" for s in hit.sources)
                blocks.append(f"[{i}]\n{hit.content}\n{sources}")
            return "\n\n".join(blocks)
        except Exception as exc:
            logger.warning("rag_search 失败: %s", type(exc).__name__)
            return ToolResult.error(
                "RAG 检索暂时不可用，请检查开关、模型密钥及索引状态。", ToolErrorType.TOOL_EXECUTION
            )
