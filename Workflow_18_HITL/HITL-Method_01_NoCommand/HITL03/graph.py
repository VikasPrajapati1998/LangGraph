from pydantic import BaseModel
from typing import Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3


# -------------------------
# SQLite Connection (IMPORTANT FIX)
# -------------------------
# Create a real SQLite connection
conn = sqlite3.connect(
    "graph_state.db",
    check_same_thread=False  # REQUIRED for multi-process usage
)

# Pass the CONNECTION, not the file path
checkpointer = SqliteSaver(conn)


# -------------------------
# State Definition
# -------------------------
class State(BaseModel):
    input: str
    user_feedback: Optional[str] = None


# -------------------------
# Node Definitions
# -------------------------
def step_A(state: State) -> State:
    print("Step_A executed")
    return state


def human_feedback(state: State) -> State:
    print("Human feedback node")
    return state


def step_B(state: State) -> State:
    print("Step_B executed")
    print("User feedback:", state.user_feedback)
    return state

def step_C(state: State) -> State:
    print("Step_C executed")
    print("User feedback:", state.user_feedback)
    return state


# -------------------------
# Graph Builder
# -------------------------
def build_graph():
    builder = StateGraph(State)

    builder.add_node("step_A", step_A)
    builder.add_node("human_feedback", human_feedback)
    builder.add_node("step_B", step_B)
    builder.add_node("step_C", step_C)

    builder.add_edge(START, "step_A")
    builder.add_edge("step_A", "human_feedback")
    builder.add_edge("human_feedback", "step_B")
    builder.add_edge("step_B", "step_C")
    builder.add_edge("step_C", END)

    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_feedback"]
    )

    return graph
