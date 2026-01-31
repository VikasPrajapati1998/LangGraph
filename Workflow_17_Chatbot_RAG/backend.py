from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
from psycopg_pool import AsyncConnectionPool
from dotenv import find_dotenv, load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_community.tools import DuckDuckGoSearchRun
import asyncio
import sys

from book_tool import book_tool


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
    model="qwen3:0.6b",  # llama3.2:1b, qwen2.5:0.5b, mistral:latest
    temperature=0.7,
)

SERVER = {
    "Calculator": {
        "command": "uv",
        "args": [
            "--directory",
            "D:\\Study\\LangGraph\\Workflow_15_Chatbot_MCP\\MCP-Servers\\Calculator",
            "run", "--with", "fastmcp", "fastmcp", "run", "main.py"
        ],
        "transport": "stdio"
    },
    "StockServer": {
        "command": "uv",
        "args": [
            "--directory",
            "D:\\Study\\LangGraph\\Workflow_15_Chatbot_MCP\\MCP-Servers\\StockPrice",
            "run", "--with", "fastmcp", "fastmcp", "run", "main.py"
        ],
        "transport": "stdio"
    },
    "ExpenseTracker": {
        "command": "uv",
        "args": [
            "--directory",
            "D:\\Study\\LangGraph\\Workflow_15_Chatbot_MCP\\MCP-Servers\\ExpenseTracker",
            "run", "--with", "fastmcp", "fastmcp", "run", "main.py"
        ],
        "transport": "stdio"
    }
}



async def build_graph():
    # ------------------- TOOL --------------------
    # Initialize tools
    search_tool = DuckDuckGoSearchRun(region="us-en")

    # Initialize MCP client and get tools (async)
    client = MultiServerMCPClient(SERVER)
    mcp_tools = await client.get_tools()
    
    tools = [search_tool, *mcp_tools, book_tool]
    model = llm.bind_tools(tools)

    # -------------------- NODE --------------------
    async def chat_node(state: ChatState) -> dict:
        """Node that processes chat messages with improved system prompt"""
        messages = state["messages"]
        
        # Add a system message about tool usage if not already present
        has_system = any(isinstance(msg, SystemMessage) for msg in messages)
        if not has_system:
            system_msg = SystemMessage(content="You are Arya, a helpful and friendly AI assistant.")
            messages = [system_msg] + messages
        
        response = await model.ainvoke(messages)
        return {"messages": [response]}

    # Tool node
    async def tool_node(state: ChatState) -> dict:
        """Async tool execution node"""
        tool_executor = ToolNode(tools)
        response = await tool_executor.ainvoke(state)
        return response

    # -------------------- GRAPH --------------------
    workflow = StateGraph(state_schema=ChatState)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "chat_node")
    workflow.add_conditional_edges("chat_node", tools_condition)
    workflow.add_edge("tools", "chat_node")

    # -------------------- CHECKPOINT --------------------
    # Create async connection pool for AsyncPostgresSaver
    pool = AsyncConnectionPool(
        conninfo=DB_URI,
        max_size=20,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False
    )
    
    await pool.open()
    
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()

    # Compile chatbot with checkpointer
    chatbot = workflow.compile(checkpointer=checkpointer)
    
    return chatbot


# -------------------- TEST --------------------
async def test_chatbot():
    """Test function to run the chatbot with PDF query"""
    
    # Build the graph
    chatbot = await build_graph()
    
    # Configuration for the conversation thread
    config = {
        "configurable": {
            "thread_id": "test-thread-001"
        }
    }
    
    # Path to your PDF file - UPDATE THIS PATH
    pdf_file_path = "software_development.pdf"  # Change this to your actual PDF path
    
    # Create the message with file path instruction
    question = f"""From the PDF file located at '{pdf_file_path}', 
    please explain the Life Cycle of a Software Development Project in detail."""
    
    initial_input = {
        "messages": [
            HumanMessage(content=question)
        ]
    }
    
    print("=" * 60)
    print("TESTING CHATBOT WITH PDF QUERY")
    print("=" * 60)
    print(f"\nQuestion: {question}\n")
    print("Processing...\n")
    
    # Invoke the chatbot
    result = await chatbot.ainvoke(initial_input, config=config)
    
    print("=" * 60)
    print("RESPONSE:")
    print("=" * 60)
    
    # Print all messages in the conversation
    for msg in result["messages"]:
        if hasattr(msg, 'type'):
            print(f"\n[{msg.type.upper()}]:")
            print(msg.content)
            print("-" * 60)


if __name__ == "__main__":
    # Run the async test function
    asyncio.run(test_chatbot())


# Export model and other components for use in other modules
__all__ = ['build_graph', 'llm', 'DB_URI']
