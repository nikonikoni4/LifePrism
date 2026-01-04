
from pydantic import BaseModel,Field
from typing import Annotated
import operator
from langgraph.types import Send
"""
测试中间的私有变量路径中能否访问到主state,结论：可以读到
测试可否通过条件update 结论:多节点并发处理用update 容易触发Use an Annotated key to handle multiple values.
在节点中修改state但不返回，则不会影响全局state
"""
class Item(BaseModel):
    id:int
    name:str
def update(old_data: list[Item],update_data:dict)-> list[Item]:
    print(f"update Old_data:{old_data}")
    flag = update_data.get("update_name","")
    id = update_data.get("id",None)
    name = update_data.get("name",None)
    if flag and id and name:
        for item in old_data:
            if item.id == id:
                old_data.name = name
    return {
        "items":old_data
    }
            


class MainState(BaseModel):
    test:int 
    items :Annotated[list[Item]|dict,update] |None
class SubState(BaseModel):
    name : str

def node_start(state:MainState)->MainState:
    return {
        # 不更新任何参数
    }

def node_A_sent(state:MainState):
    # 发出sent
    return [
        Send("node_B",state),Send("node_C",SubState(name="C")) 
    ]

def node_B(state:MainState)->SubState:
    return {
        "name":"B"
    }

def node_BB(substate:SubState)->MainState:
    # 判断node BB能否读到state
    print(f"判断node BB能否读到state :{state}")
    # 判断能否更新
    state.test = 3
    print(f"修改test:{state.test}")
    return {
        "items" : {
            "flag" : "update_name",
            "id":1,
            "name":substate.name
        }
        
    }
def node_C(substate:SubState)->MainState:
    # 判断node BB能否读到state
    print(f"判断node C能否读到state:{state}")
    # 判断能否更新
    return {
        "items" : {
            "flag" : "update_name",
            "id":2,
            "name":substate.name
        }
        
    }


def node_D(state:MainState)->MainState:
    print(f"判断BB中更改但没传出的state会不会被修改:{state.test}")
    return state
# 结构 Start -> A ->B -> BB ->D
#                 ->C ->D
if __name__ == "__main__":
    items = [Item(id=i,name="") for i in range(4)]
    state = MainState(test=1,items=items)

    from langgraph.graph import START,END,StateGraph
    graph = StateGraph(MainState)
    graph.add_node("node_start",node_start)
    graph.add_node("node_B",node_B)
    graph.add_node("node_BB",node_BB)
    graph.add_node("node_C",node_C)
    graph.add_node("node_D",node_D)
    graph.add_edge(START,"node_start")
    graph.add_conditional_edges("node_start",node_A_sent)
    graph.add_edge("node_B","node_BB")
    graph.add_edge("node_BB","node_D")
    graph.add_edge("node_C","node_D")
    graph.add_edge("node_D",END)
    app = graph.compile()
    output = app.invoke(state)
    print(output)