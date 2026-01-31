from typing import TypedDict, Annotated, List

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver


# ===============================
# LLM CONFIGURATION
# ===============================
llm = ChatOllama(
    model="qwen3:0.6b",
    temperature=0.5
)

# ===============================
# GRAPH STATE
# ===============================
class ChatState(TypedDict):
    """
    Persistent state stored in SQLite.
    """
    messages: Annotated[List[BaseMessage], add_messages]


# ===============================
# CHAT NODE (WITH HITL)
# ===============================
def chat_node(state: ChatState):
    """
    Interrupt before answering and wait for human approval.
    """

    approval = interrupt({
        "type": "human_approval",
        "question": state["messages"][-1].content,
        "instruction": "Approve this response? (yes/no)"
    })

    if approval["approved"].lower() != "yes":
        return {
            "messages": [
                AIMessage(content="Response blocked by human approval.")
            ]
        }

    response = llm.invoke(state["messages"])

    return {
        "messages": [response]
    }


# ===============================
# BUILD GRAPH
# ===============================
builder = StateGraph(ChatState)

builder.add_node("chat", chat_node)
builder.add_edge(START, "chat")
builder.add_edge("chat", END)

# ===============================
# SQLITE CHECKPOINTER (PERSISTENT)
# ===============================
# Create connection and pass it to SqliteSaver
import sqlite3

conn = sqlite3.connect("langgraph_state.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)

# Compile app
app = builder.compile(checkpointer=checkpointer)


# ===============================
# ENTRY POINT
# ===============================
if __name__ == "__main__":
    """
    This file is ONLY responsible for starting the graph
    and triggering the interrupt.
    """

    thread_id = "chat-thread-001"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    initial_input = {
        "messages": [
            HumanMessage(content="Explain gradient descent in very simple terms.")
        ]
    }

    # This WILL STOP at interrupt
    result = app.invoke(initial_input, config=config)

    interrupt_data = result["__interrupt__"][0].value

    print("\n--- GRAPH PAUSED (HITL) ---")
    print("Thread ID   :", thread_id)
    print("Question    :", interrupt_data["question"])
    print("Instruction :", interrupt_data["instruction"])
    print("\nWaiting for approval...\n")

