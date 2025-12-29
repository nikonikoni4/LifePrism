from pydantic import BaseModel, Field
from langchain.messages import HumanMessage, SystemMessage,AIMessage
from typing_extensions import Annotated
import operator

class ChatBotSchemas(BaseModel):
    messages: Annotated[list[HumanMessage| AIMessage],operator.add]= Field(description="用户输入的消息")
    intent:Annotated[list[str],operator.add] = Field(description="用户意图")
    guide_content : Annotated[list[str],operator.add] = Field(description="用户意图对应的引导内容")


    
