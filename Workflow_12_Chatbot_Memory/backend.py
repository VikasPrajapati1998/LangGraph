from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessageChunk
from langchain_ollama import ChatOllama
import psycopg
from psycopg.rows import dict_row

# -------------------- STATE --------------------

class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

# -------------------- MODEL --------------------

model = ChatOllama(
    model="qwen2.5:0.5b",
    temperature=0.4,
)

# -------------------- NODE --------------------

def chat_node(state: ChatState) -> dict:
    """Node that processes chat messages - uses invoke instead of stream for compatibility"""
    response = model.invoke(state["messages"])
    return {"messages": [response]}

# -------------------- GRAPH --------------------

workflow = StateGraph(state_schema=ChatState)
workflow.add_node("chat", chat_node)
workflow.add_edge(START, "chat")
workflow.add_edge("chat", END)

# -------------------- CHECKPOINT --------------------
DB_URI = "postgresql://postgres:abcd%401234@localhost:5432/langgraph_memory"

# Create connection with proper settings for PostgresSaver
conn = psycopg.connect(DB_URI, autocommit=True, row_factory=dict_row)

# Initialize checkpointer
checkpointer = PostgresSaver(conn)
checkpointer.setup()  # Create tables if they don't exist

# Compile chatbot with checkpointer
chatbot = workflow.compile(checkpointer=checkpointer)

# -------------------- RUN --------------------
initial_state = {
    "messages": [
        HumanMessage(content="What is the capital of India?")
    ]
}

config = {"configurable": {"thread_id": "thread-1"}}

print("AI Response: ", end='')

# Stream the response - you can use this same pattern in other scripts
for event in chatbot.stream(input=initial_state, config=config, stream_mode="values"):
    if "messages" in event and len(event["messages"]) > 0:
        last_message = event["messages"][-1]
        # Only print AI messages, not human messages
        if hasattr(last_message, 'content') and last_message.__class__.__name__ == 'AIMessage':
            print(last_message.content)

