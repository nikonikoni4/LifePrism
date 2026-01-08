# 测试时，直接给skills内容
from lifeprism.llm.llm_classify.utils import create_ChatTongyiModel
from lifeprism.llm.llm_classify.utils import get_skill_non_json_content
from lifeprism.llm.llm_classify.tests.data_driving_agent_v2.data_driving_schemas import NodeDefinition,ExecutionPlan,Context 
from langchain_core.output_parsers import PydanticOutputParser
# =====================================
# 生成plan
# =====================================
def plan_generator(date:str,skills_path:str):
    skill_definition = get_skill_non_json_content(skills_path)
    parser = PydanticOutputParser(pydantic_object=ExecutionPlan)
    question = f"总结{date}我做了什么"

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
    
    # 将 result.content 解析为 ExecutionPlan 类型
    execution_plan: ExecutionPlan = parser.parse(result.content)
    return execution_plan
if __name__ == "__main__":
    from lifeprism.llm.llm_classify.tests.data_driving_agent_v2.save_plan import save_plan_as_template
    plan = plan_generator(date="2026-01-03", skills_path=r"D:\desktop\软件开发\LifeWatch-AI\lifeprism\llm\custom_prompt\skills\user_behavior_summary\skill.md")
    print(plan)
    # 提取工具调用次数作为默认限制
    tools_limit = {}
    for node in plan.nodes:
        if node.node_type == "tool" and node.tool_name:
            tools_limit[node.tool_name] = tools_limit.get(node.tool_name, 0) + 1
            
    save_plan_as_template(
        plan=plan,
        date="2026-01-03", 
        output_path=r"lifeprism\llm\llm_classify\tests\data_driving_agent_v2\patterns\test.json",
        pattern_name="comprehensive",
        tools_limit=tools_limit
    )
# 调用结果
# execution_plan = get_daily_summary_plan(date="2026-01-05")
