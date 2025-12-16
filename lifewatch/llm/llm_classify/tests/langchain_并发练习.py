
from pydantic import BaseModel, Field

from typing import Annotated
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
# 假设输入一批数据,一部分是进行加法，一部分是进行乘法,使用langgraph进行并行分类测试
# 静态并发
# 输入数据
class InputData(BaseModel):
    id:int
    flag:bool = Field("用途判断是否需要进行乘法")
    a:int 
    b:int
# 输出数据
class ResultData(BaseModel):
    id:int 
    result:int

# 主状态
class MainState(BaseModel):
    input_data : list[InputData]
    result_data : Annotated[list[ResultData],operator.add]

# # 子图状态
# class SubState(BaseModel):
#     input_data : list[InputData]
#     result_data : Annotated[list[ResultData],operator.add] = []

def add(state:MainState)->MainState:
    result_data = []
    for input_data in state.input_data:
        result_data.append(input_data.a+input_data.b)
    return {
        "result_data" : result_data
    }

def multi(state:MainState)->MainState:
    result_data = []
    for input_data in state.input_data:
        result_data.append(input_data.a*input_data.b)
    return {
        "result_data" : result_data
    }
def router(state:MainState):
    input_data_for_add :list[InputData] = []
    input_data_for_multi:list[InputData] = []
    for input_data in state.input_data:
        if input_data.flag == False:
            input_data_for_add.append(input_data)
        else:
            input_data_for_multi.append(input_data)
    state_for_add = MainState(
        input_data=input_data_for_add,
        result_data=[]
    )
    state_for_multi = MainState(
        input_data=input_data_for_multi,
        result_data=[]
    )
    return [
        Send("add",state_for_add),Send("multi",state_for_multi)
    ]
graph = StateGraph(MainState)
graph.add_node("add",add)
graph.add_node("multi",multi)
graph.add_conditional_edges(START,router)
graph.add_edge("add",END)
graph.add_edge("multi",END)
app = graph.compile()
input_data :list[InputData] = []
for i in range(10):
    if i <5 :
        input_data.append(InputData(
            id = i,
            a = i,
            b = i+1,
            flag = False
        ))
    else:
        input_data.append(InputData(
            id = i,
            a = i,
            b = i+1,
            flag = True
        ))
state = MainState(
    input_data=input_data,
    result_data=[]
)
state = app.invoke(state) # invoke 会返回一个dict
print(type(state))