from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph.message import add_messages
from dotenv import load_dotenv, find_dotenv
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
import requests
import os

load_dotenv(find_dotenv())

# LLM Model
llm = ChatOllama(
    model="mistral:latest",
    temperature=0.7,
)

# Tools
## Search Tool
search_tool = DuckDuckGoSearchRun(region="us-en")

## Calculator Tool
@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}
        return {"first_num": first_num, "second_num": second_num, "operation": operation, "result": result}
    except Exception as e:
        return {"error": str(e)}

## Stock Tool
@tool
def get_stock_price(symbol: str) -> dict: 
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA')
    using Alpha Vantage with API key in the URL.
    """
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": os.getenv("ALPHAVANTAGE_API_KEY"),
    }
    try:
        response = requests.get(url, params=params, timeout=10).json()
        return response.get("Global Quote", {})
    except Exception as e:
        return {"error": str(e)}

tools = [search_tool, get_stock_price, calculator]
llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)

# State
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# System message to guide the LLM
SYSTEM_PROMPT = """You are a helpful AI assistant. You have access to tools for searching the web, calculating math operations, and fetching stock prices.

IMPORTANT: Only use tools when they are actually needed for the user's request:
- Use the search tool ONLY when the user asks for current information, news, or web searches
- Use the calculator tool ONLY when the user asks to perform mathematical calculations
- Use the stock price tool ONLY when the user asks for stock prices or ticker information

For simple greetings, general questions, or casual conversation, respond directly WITHOUT using any tools.

Be concise and clear in your responses."""

# Node
def chat_node(state: ChatState):
    """LLM node that may answer or request a tool call."""
    messages = state['messages']
    
    # Add system message if not present
    if not any(isinstance(msg, SystemMessage) for msg in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# Graph Structure
graph = StateGraph(ChatState)

## Nodes
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

## Edges
graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition)
graph.add_edge("tools", "chat_node")

## Compile
chatbot = graph.compile()

query = "How much will be the price of 400 stock of Apple today?"
answer1 = chatbot.invoke({"messages": [HumanMessage(content=query)]})
print(f"Response: {answer1['messages'][-1].content}\n")
