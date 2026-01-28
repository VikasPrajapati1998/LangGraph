from typing import TypedDict, Annotated, List, Tuple
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from dotenv import find_dotenv, load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_community.tools import DuckDuckGoSearchRun
import asyncio
import uuid
import sys

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
    model="qwen2.5:3b",
    temperature=0.7,
)

SERVER = {
            "Calculator": {
                "command": "uv",
                "args": [
                    "--directory",
                    "D:\\Study\\LangGraph\\Workflow_16_Chatbot_MCP\\MCP-Servers\\Calculator",
                    "run", "--with", "fastmcp", "fastmcp", "run", "main.py"
                ],
                "transport": "stdio"
            },
            "StockServer": {
                "command": "uv",
                "args": [
                    "--directory",
                    "D:\\Study\\LangGraph\\Workflow_16_Chatbot_MCP\\MCP-Servers\\StockPrice",
                    "run", "--with", "fastmcp", "fastmcp", "run", "main.py"
                ],
                "transport": "stdio"
            }
        }


async def build_graph(pool: AsyncConnectionPool):
    """
    Build the LangGraph workflow using the provided (already opened) connection pool.
    Returns the compiled graph and the pool (for clarity / future use).
    """
    try:
        # ------------------- TOOL --------------------
        search_tool = DuckDuckGoSearchRun(region="us-en")

        client = MultiServerMCPClient(SERVER)
        mcp_tools = await client.get_tools()

        tools = [search_tool, *mcp_tools]
        model = llm.bind_tools(tools)
        
        # -------------------- NODE --------------------
        async def chat_node(state: ChatState) -> dict:
            """Node that processes chat messages with improved system prompt"""
            messages = state["messages"]
            
            # System message
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                messages = [
                    SystemMessage(content="You are Arya, a helpful assistant.")
                ] + messages
            
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
        
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()  # safe to call multiple times

        # Compile the graph
        chatbot = workflow.compile(checkpointer=checkpointer)
        
        return chatbot, pool

    except Exception as e:
        print("Error building graph:", str(e))
        raise

async def main():
    # Create and open the connection pool once â€” lives for the whole program
    pool = AsyncConnectionPool(
        conninfo=DB_URI,
        min_size=2,
        max_size=12,
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=False
    )

    # Explicitly open the pool
    await pool.open()

    try:
        # Build the graph (pool is already open)
        chatbot, _ = await build_graph(pool)

        # Run
        thread_id = f"user-{uuid.uuid4()}"
        print(f"Starting new conversation with thread_id: {thread_id}")

        result = await chatbot.ainvoke(
            {"messages": [HumanMessage(content="Find the multiplication of 34 and 87.")]},
            config={"configurable": {"thread_id": thread_id}}
        )
        
        print("\nFinal answer:")
        print(result)

    except Exception as e:
        print("Error during execution:", str(e))
    finally:
        # Clean up â€” close pool only when everything is done
        print("\nClosing database connection pool...")
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
