# 测试时，直接给skills内容
from lifeprism.llm.llm_classify.utils import create_ChatTongyiModel
from utils import get_skill_non_json_content
from schemas import NodeDefinition,ExecutionPlan,Context 
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from plans import get_daily_summary_plan
# =====================================
# 生成plan
# =====================================
skill_definition = get_skill_non_json_content(r"D:\desktop\软件开发\LifeWatch-AI\lifeprism\llm\llm_classify\tests\data_driving_agent\skills.md")
parser = PydanticOutputParser(pydantic_object=ExecutionPlan)

question = "总结2026-01-05我做了什么"

prompt = f"""你需要依据给定的技能定义，为用户生成一个执行计划。
# 技能定义
{skill_definition}
# 输出格式
{parser.get_format_instructions()}
# 用户的任务
{question}
"""
print(prompt)
plan_llm = create_ChatTongyiModel(enable_search=False,enable_thinking=True)
result = plan_llm.invoke(prompt)
print(result)
# 调用结果
# execution_plan = get_daily_summary_plan(date="2026-01-05")
