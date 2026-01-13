from typing import TypedDict, Annotated, List, Iterator
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import BaseMessage, AIMessageChunk
from langchain_ollama import ChatOllama
import sqlite3

# -------------------- STATE --------------------

class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

# -------------------- MODEL --------------------

model = ChatOllama(
    model="qwen2.5:0.5b",
    temperature=0.4,
    streaming=True
)

# -------------------- NODE --------------------

def chat_node(state: ChatState) -> Iterator[dict]:
    for chunk in model.stream(state["messages"]):
        yield {"messages": [chunk]}

# -------------------- GRAPH --------------------

workflow = StateGraph(state_schema=ChatState)

workflow.add_node("chat", chat_node)

workflow.add_edge(START, "chat")
workflow.add_edge("chat", END)

# -------------------- CHECKPOINT --------------------

conn = sqlite3.connect("chat_memory.db", check_same_thread=False)
memory = SqliteSaver(conn)

chatbot = workflow.compile(checkpointer=memory)

# for checkpoint in memory.list(None):
#     print(checkpoint)
