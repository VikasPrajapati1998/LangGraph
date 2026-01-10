from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

# -------------------- STATE --------------------

class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

# -------------------- MODEL --------------------

model = ChatOllama(
    model="qwen2.5:0.5b",
    temperature=0.3
)

# -------------------- NODE --------------------

def chat_node(state: ChatState):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

# -------------------- GRAPH --------------------

graph = StateGraph(ChatState)
graph.add_node("chat", chat_node)

graph.add_edge(START, "chat")
graph.add_edge("chat", END)

# -------------------- CHECKPOINT --------------------

conn = sqlite3.connect("chat_memory.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)

workflow = graph.compile(checkpointer=checkpointer)

# -------------------- RUN FUNCTION --------------------

def run_chat(messages: List[BaseMessage], thread_id: str):
    """
    Run chat with the given messages and thread_id.
    Returns the updated state after processing.
    """
    config = {"configurable": {"thread_id": thread_id}}
    return workflow.invoke({"messages": messages}, config=config)

