
# ===============================
# 我曾经是谁？的测试schemas
# ===============================
from typing import List
from pydantic import BaseModel,Field
class JudgeItem(BaseModel): 
    judge: str = Field(..., description="判断（+/0/-）") 
    reason: str = Field(..., description="原因")
    time: str = Field(..., description="评判时间")
class WhoWasIItem(BaseModel):
    id: int = Field(..., description="id")
    content: str = Field(..., description="我曾经是谁的问题的回答")
    judge_items: Optional[List[JudgeItem]] = Field(default=None, description="两周后的评判列表")

class PositivePastReframingItem(BaseModel):
    id:int = Field(...,description="id")
    negative_past:str = Field(...,description="消极的过去")
    positive_takeaways:str = Field(...,description="正面的收获")
    how_positive_takeaways_help_me:str = Field(...,description="这些正面的收获在未来将会如何帮助我")

class WhoWasIResponse(BaseModel):
    version:int = Field(...,description="版本")
    who_was_i_items:List[WhoWasIItem]
    positive_past_reframing_items:List[PositivePastReframingItem]


# ===============================
# 我现在是谁？的测试schemas
# ===============================

class WhoAmIItem(BaseModel):
    id:int = Field(...,description="id")
    who_am_i:str = Field(...,description="我现在是谁的问题的回答")
class WhatTime(BaseModel):
    id:int = Field(...,description="id")
    what_time:str = Field(...,description="现在是什么时候|人生什么阶段")
class WhereAmI(BaseModel):
    id:int = Field(...,description="id")
    where_am_i:str = Field(...,description="我现在在哪里;声音，气味，在周围的环境中，你最喜欢什么？不喜欢什么？")
class HowAmIFeeling(BaseModel):
    id:int = Field(...,description="id")
    how_am_i_feeling:str = Field(...,description="我现在的感觉|真正的感受")
class WhoAmIResponse(BaseModel):
    version:int = Field(...,description="版本")
    who_am_i_items:List[WhoAmIItem]
    what_time_items:List[WhatTime]
    where_am_i_items:List[WhereAmI]
    how_am_i_feeling_items:List[HowAmIFeeling]
    

# ===============================
# 我未来会成为什么样的人？的测试schemas
# ===============================

class WhoIWantToBeItem(BaseModel):
    id:int = Field(...,description="id")
    who_i_want_to_be:str = Field(...,description="我未来会成为什么样的人的问题的回答")
class SpecificGoalsItem(BaseModel):
    id:int = Field(...,description="id")
    specific_goals:str = Field(...,description="具体目标")
    when_will_i_reach_them:str = Field(...,description="何时实现")
class WhoIWantToBeResponse(BaseModel):
    version:int = Field(...,description="版本")
    who_i_want_to_be_items:List[WhoIWantToBeItem]
    specific_goals_items:List[SpecificGoalsItem]