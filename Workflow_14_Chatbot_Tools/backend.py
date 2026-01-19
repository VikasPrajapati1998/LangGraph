from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessageChunk
from langchain_ollama import ChatOllama
import psycopg
from psycopg.rows import dict_row
import os
from dotenv import find_dotenv, load_dotenv
from tools import search_tool, calculator, get_stock_price


# Load Dotenv
load_dotenv(find_dotenv())

# -------------------- DATABASE CONFIG --------------------
# Centralized database URI that can be imported by other modules
DB_URI = "postgresql://postgres:abcd%401234@localhost:5432/langgraph_memory"

# -------------------- STATE --------------------

class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

# -------------------- MODEL --------------------

llm = ChatOllama(
    model="qwen2.5:0.5b",  # llama3.2:1b, qwen2.5:0.5b, mistral:latest, qwen2.5:0.5b
    temperature=0.7,
)

tools = [get_stock_price, search_tool, calculator]
model = llm.bind_tools(tools)
tool_node = ToolNode(tools)

# -------------------- NODE --------------------

def chat_node(state: ChatState) -> dict:
    """Node that processes chat messages with improved system prompt"""
    messages = state["messages"]
    
    # Add a system message about tool usage if not already present
    has_system = any(isinstance(msg, SystemMessage) for msg in messages)
    if not has_system:
        system_msg = SystemMessage(content="""You are Arya, a helpful and friendly AI assistant.

IMPORTANT TOOL USAGE GUIDELINES:
- Only use tools when explicitly needed to answer the user's question
- For greetings (hi, hello, hey), introductions, or casual conversation, respond directly WITHOUT using any tools
- For general knowledge questions you can answer, respond directly WITHOUT searching
- Use the search tool ONLY for current events, recent information, or topics you're uncertain about
- Use the calculator tool ONLY when the user asks for mathematical calculations
- Use the stock price tool ONLY when the user asks about specific stock prices

When you DO use a tool, provide a clean, natural response based on the tool's output without repeating the raw tool data.""")
        messages = [system_msg] + messages
    
    response = model.invoke(messages)
    return {"messages": [response]}

# -------------------- GRAPH --------------------

workflow = StateGraph(state_schema=ChatState)
workflow.add_node("chat_node", chat_node)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "chat_node")
workflow.add_conditional_edges("chat_node", tools_condition)
workflow.add_edge("tools", "chat_node")

# -------------------- CHECKPOINT --------------------

# Create connection with proper settings for PostgresSaver
conn = psycopg.connect(DB_URI, autocommit=True, row_factory=dict_row)

# Initialize checkpointer
checkpointer = PostgresSaver(conn)
checkpointer.setup()  # Create tables if they don't exist

# Compile chatbot with checkpointer
chatbot = workflow.compile(checkpointer=checkpointer)

# Export model and other components for use in other modules
__all__ = ['chatbot', 'model', 'DB_URI']

