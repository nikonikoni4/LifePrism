from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from typing_extensions import TypedDict, Annotated
import operator
from pydantic import BaseModel
class OverallState(BaseModel):
    topic: str =""
    subjects: list[str] =[]
    jokes: Annotated[list[str], operator.add] =[]
    best_selected_joke: str =""

def test_node(state:OverallState)->dict :
    return {
        "jokes" : ["haha"],
        "best_selected_joke" :"heihie"
    }

def print_node(state:OverallState) ->OverallState:
    print(state.jokes)
    print(state.best_selected_joke)
    return state
graph = StateGraph(OverallState)

# 方案3a：add_sequence + 手动入口
graph.add_sequence([test_node, print_node])
graph.set_entry_point("test_node")

# 方案3b：纯手动（最清晰）
# graph.add_edge(START, "test_node")
# graph.add_edge("test_node", "print_node")
# graph.add_edge("print_node", END)

app = graph.compile()
state = OverallState()
state = app.invoke(state)
print(state)
