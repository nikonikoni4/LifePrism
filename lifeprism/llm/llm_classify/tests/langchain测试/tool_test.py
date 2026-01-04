from lifeprism.llm.llm_classify.tools import query_title_description
from lifeprism.llm.llm_classify.utils import LangChainToonAdapter
import json

# 方式 1：转换为 JSON Schema
tools_json = LangChainToonAdapter.tools_to_json([query_title_description])
print("JSON Schema:")
print(json.dumps(tools_json, indent=2, ensure_ascii=False))

# 方式 2：转换为 Toon 格式
tools_toon = LangChainToonAdapter.tools_to_toon([query_title_description])
print("\nToon Format:")
print(tools_toon)

# 方式 3：查看工具基本信息
print("\n工具信息:")
print(f"名称: {query_title_description.name}")
print(f"描述: {query_title_description.description}")
print(f"参数: {query_title_description.args_schema.model_json_schema()}")