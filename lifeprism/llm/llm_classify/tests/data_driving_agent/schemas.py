from typing import Annotated,TypedDict,Literal
from pydantic import BaseModel,Field
from langchain_core.messages import AIMessage,HumanMessage,SystemMessage,ToolMessage
import operator 
from langchain_core.output_parsers import PydanticOutputParser

class Context(TypedDict):
    messages:Annotated[list[AIMessage | HumanMessage],operator.add]

   
class NodeDefinition(BaseModel):
    node_name: str 
    task_prompt: str = Field(description="调用llm的prompt")
    tools : list[str] | None= Field(description="该节点可调用的工具,如果不需要调用工具,则为None")
class ExecutionPlan(BaseModel):
    task : str = Field(description="任务名称")
    nodes : list[NodeDefinition] = Field(description="安排的节点列表")
    
if __name__ == "__main__":
    context = Context(messages=[HumanMessage(content="Hello")])
    print(context.get_history())