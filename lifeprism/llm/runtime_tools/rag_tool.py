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
            "检索用户个人资料和日记，返回原文片段与来源文件。默认只使用 vec 语义检索。"
            "只有查询包含明确关键词，例如人名、项目名、具体术语或需精确匹配的词语时，"
            "才设置 use_bm25=true 增加关键词检索；概括性或语义性问题保持 false。"
            "问题涉及多个方面时可拆成不同角度分别检索，结果不足时换词重试。"
            "结果来自每日索引快照，可能尚未包含最新修改；不要将未检索到解释为事实不存在。"
            "回答应引用来源文件；来源行号是清洗后文本位置，不是原文件行号。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "description": "单个主题的自然语言检索词",
                },
                "k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                "use_bm25": {
                    "type": "boolean",
                    "default": False,
                    "description": "仅有明确关键词时才启用 own_bm25 通道；默认 false，只用 vec",
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
                sources = "\n".join(
                    f"来源：{s.path}（清洗后文本行 {s.start_line + 1}–{s.end_line + 1}）"
                    for s in hit.sources
                )
                blocks.append(f"[{i}]\n{hit.content}\n{sources}")
            return "\n\n".join(blocks)
        except Exception as exc:
            logger.warning("rag_search 失败: %s", type(exc).__name__)
            return ToolResult.error(
                "RAG 检索暂时不可用，请检查开关、模型密钥及索引状态。", ToolErrorType.TOOL_EXECUTION
            )
