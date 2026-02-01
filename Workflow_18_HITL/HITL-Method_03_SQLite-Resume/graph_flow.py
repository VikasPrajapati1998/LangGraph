import sqlite3
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver


class FlowState(TypedDict):
    proposal: str
    approved: bool


def generate_proposal(state: FlowState) -> FlowState:
    state["proposal"] = "Deploy model to production"
    return state


def approval_node(state: FlowState) -> FlowState:
    decision = interrupt(
        {
            "message": "Approve deployment?",
            "proposal": state["proposal"]
        }
    )
    state["approved"] = decision["approved"]
    return state


def final_node(state: FlowState) -> FlowState:
    if state["approved"]:
        print("✅ Deployment Approved")
    else:
        print("❌ Deployment Rejected")
    return state


builder = StateGraph(FlowState)

builder.add_node("generate", generate_proposal)
builder.add_node("approval", approval_node)
builder.add_node("final", final_node)

builder.add_edge(START, "generate")
builder.add_edge("generate", "approval")
builder.add_edge("approval", "final")
builder.add_edge("final", END)

conn = sqlite3.connect("hitl.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph = builder.compile(checkpointer=checkpointer)
