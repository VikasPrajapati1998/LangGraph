# LangGraph Tools Guide

## Table of Contents
- [Introduction](#introduction)
- [What are Tools in LangGraph?](#what-are-tools-in-langgraph)
- [How Tools Work](#how-tools-work)
- [Tool Implementation](#tool-implementation)
- [Complete Example](#complete-example)
- [Best Practices](#best-practices)
- [Common Issues and Solutions](#common-issues-and-solutions)

---

## Introduction

LangGraph is a framework for building stateful, multi-agent applications with LLMs. Tools are external functions that LLMs can call to perform specific tasks like searching the web, performing calculations, or fetching data from APIs.

---

## What are Tools in LangGraph?

Tools are Python functions that:
- Extend the capabilities of LLMs beyond text generation
- Enable LLMs to interact with external systems and APIs
- Perform computations, data retrieval, or other operations
- Return results back to the LLM for further processing

**Common Tool Types:**
- Web search tools
- Calculator tools
- Database query tools
- API integration tools
- File system tools

---

## How Tools Work

### The Tool Execution Flow

```
User Query → LLM → Tool Call Decision → Tool Execution → LLM Response
```

**Step-by-Step Process:**

1. **User sends a message** to the chatbot
2. **LLM analyzes** the message and decides if a tool is needed
3. **Tool call is generated** with specific parameters
4. **Tool executes** the requested operation
5. **Results return** to the LLM
6. **LLM synthesizes** the tool results into a natural language response
7. **User receives** the final answer

### Key Components

#### 1. Tool Definition
Tools are defined using the `@tool` decorator or pre-built tools from LangChain:

```python
from langchain_core.tools import tool

@tool
def my_custom_tool(param1: str, param2: int) -> dict:
    """
    Description of what this tool does.
    This docstring is crucial - the LLM uses it to understand when to use the tool.
    """
    # Tool logic here
    result = perform_operation(param1, param2)
    return {"result": result}
```

#### 2. Tool Binding
Bind tools to your LLM so it knows they're available:

```python
llm_with_tools = llm.bind_tools([tool1, tool2, tool3])
```

#### 3. ToolNode
A special node that executes tool calls:

```python
from langgraph.prebuilt import ToolNode

tool_node = ToolNode([tool1, tool2, tool3])
```

#### 4. Conditional Edges
Route between chat and tool execution:

```python
from langgraph.prebuilt import tools_condition

graph.add_conditional_edges("chat_node", tools_condition)
```

---

## Tool Implementation

### Creating Custom Tools

#### Basic Tool Structure

```python
from langchain_core.tools import tool

@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform basic arithmetic operations.
    
    Args:
        first_num: First number
        second_num: Second number
        operation: One of 'add', 'sub', 'mul', 'div'
    
    Returns:
        Dictionary with operation result
    """
    if operation == "add":
        result = first_num + second_num
    elif operation == "sub":
        result = first_num - second_num
    elif operation == "mul":
        result = first_num * second_num
    elif operation == "div":
        if second_num == 0:
            return {"error": "Division by zero"}
        result = first_num / second_num
    else:
        return {"error": f"Unknown operation: {operation}"}
    
    return {
        "first_num": first_num,
        "second_num": second_num,
        "operation": operation,
        "result": result
    }
```

### Using Pre-built Tools

```python
from langchain_community.tools import DuckDuckGoSearchRun

# Web search tool
search_tool = DuckDuckGoSearchRun(region="us-en")

# Wikipedia tool
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
```

### API Integration Tools

```python
import requests
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> dict:
    """
    Get current weather for a city using OpenWeatherMap API.
    
    Args:
        city: Name of the city
    
    Returns:
        Weather information dictionary
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    url = f"http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            "city": city,
            "temperature": data["main"]["temp"],
            "description": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"]
        }
    except Exception as e:
        return {"error": str(e)}
```

---

## Complete Example

Here's a complete working example with multiple tools:

```python
from langgraph.graph import StateGraph, START
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool

# Define LLM
llm = ChatOllama(model="llama3.2:3b", temperature=0.7)

# Define Tools
@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """Perform arithmetic: add, sub, mul, div"""
    operations = {
        "add": first_num + second_num,
        "sub": first_num - second_num,
        "mul": first_num * second_num,
        "div": first_num / second_num if second_num != 0 else None
    }
    result = operations.get(operation)
    return {"result": result} if result is not None else {"error": "Invalid operation"}

search_tool = DuckDuckGoSearchRun()

# Bind tools to LLM
tools = [calculator, search_tool]
llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)

# Define State
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# System Prompt
SYSTEM_PROMPT = """You are a helpful AI assistant with access to:
- Calculator for math operations
- Web search for current information

Only use tools when necessary. For greetings and general chat, respond directly."""

# Chat Node
def chat_node(state: ChatState):
    messages = state['messages']
    if not any(isinstance(msg, SystemMessage) for msg in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# Build Graph
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)
graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition)
graph.add_edge("tools", "chat_node")

# Compile
chatbot = graph.compile()

# Run
response = chatbot.invoke({
    "messages": [HumanMessage(content="What is 15 multiplied by 8?")]
})
print(response['messages'][-1].content)
```

---

## Best Practices

### 1. Clear Tool Descriptions
The docstring is critical - it tells the LLM when and how to use the tool:

```python
@tool
def good_tool(param: str) -> dict:
    """
    Fetch user data from database by username.
    Use this when the user asks about user information or profiles.
    """
    pass

@tool
def bad_tool(param: str) -> dict:
    """Does stuff"""  # Too vague!
    pass
```

### 2. Strong Type Hints
Use proper type hints for parameters and return values:

```python
@tool
def typed_tool(name: str, age: int, active: bool) -> dict:
    """Tool with clear types for the LLM to understand."""
    return {"name": name, "age": age, "active": active}
```

### 3. Error Handling
Always handle errors gracefully:

```python
@tool
def robust_tool(url: str) -> dict:
    """Fetch data from URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return {"data": response.json()}
    except requests.Timeout:
        return {"error": "Request timed out"}
    except requests.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
```

### 4. System Prompts
Guide the LLM on when to use tools:

```python
SYSTEM_PROMPT = """You are an AI assistant with the following tools:

1. calculator - Use ONLY for math operations
2. search_tool - Use ONLY when current web information is needed
3. weather_tool - Use ONLY when asked about weather

For general conversation, respond directly without tools."""
```

### 5. Return Structured Data
Return dictionaries with clear keys:

```python
@tool
def get_user(user_id: int) -> dict:
    """Get user information."""
    return {
        "user_id": user_id,
        "name": "John Doe",
        "email": "john@example.com",
        "status": "active"
    }
```

---

## Common Issues and Solutions

### Issue 1: Tools Called Unnecessarily

**Problem:** LLM calls tools for simple greetings

**Solution:** Use a clear system prompt:
```python
SYSTEM_PROMPT = """Only use tools when explicitly needed. 
For greetings like 'Hello' or 'Hi', respond directly."""
```

### Issue 2: Responses Getting Concatenated

**Problem:** Multiple test responses appear together

**Solution:** Create fresh state for each conversation:
```python
# Wrong - reuses state
state = {"messages": []}
result1 = chatbot.invoke(state)  # state gets modified
result2 = chatbot.invoke(state)  # contains result1's messages!

# Correct - fresh state each time
result1 = chatbot.invoke({"messages": [HumanMessage(content="Hi")]})
result2 = chatbot.invoke({"messages": [HumanMessage(content="Bye")]})
```

### Issue 3: Tool Not Being Called

**Problem:** LLM doesn't use the tool when it should

**Solutions:**
- Improve tool docstring to be more specific
- Adjust LLM temperature (lower = more consistent)
- Use a more capable model
- Make the user query more explicit

### Issue 4: Missing Edge from Tools to Chat

**Problem:** Graph hangs after tool execution

**Solution:** Add the return edge:
```python
graph.add_edge("tools", "chat_node")  # Don't forget this!
```

### Issue 5: API Keys Not Working

**Problem:** API tools fail with authentication errors

**Solution:** Use environment variables:
```python
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("YOUR_API_KEY")
```

---

## Graph Structure Explained

### Basic Graph Structure

```
START → chat_node → [decision] → tools → chat_node → END
                         ↓
                        END
```

**Nodes:**
- `chat_node`: LLM processes messages and decides on tool usage
- `tools`: Executes tool calls and returns results

**Edges:**
- `START → chat_node`: Entry point
- `chat_node → tools` (conditional): Only if tools are needed
- `tools → chat_node`: Return results to LLM for processing
- `chat_node → END` (conditional): When response is ready

### The Conditional Edge

```python
graph.add_conditional_edges("chat_node", tools_condition)
```

The `tools_condition` function checks if the LLM's response contains tool calls:
- **If YES**: Route to `tools` node
- **If NO**: Route to `END`

---

## Advanced Topics

### Multi-Turn Tool Usage

```python
# Conversation with multiple tool calls
state = {"messages": [HumanMessage(content="Hi")]}
result = chatbot.invoke(state)

# Continue conversation
state = {
    "messages": result['messages'] + [
        HumanMessage(content="What's 50 times 20?")
    ]
}
result = chatbot.invoke(state)
```

### Custom Tool Routing

Instead of `tools_condition`, you can create custom routing:

```python
def custom_router(state: ChatState) -> str:
    last_message = state['messages'][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    return "end"

graph.add_conditional_edges("chat_node", custom_router, {
    "tools": "tools",
    "end": END
})
```

### Streaming Responses

```python
for event in chatbot.stream({"messages": [HumanMessage(content="Hello")]}):
    for value in event.values():
        print(value['messages'][-1].content)
```

---

## Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Tools](https://python.langchain.com/docs/modules/agents/tools/)
- [LangGraph Examples](https://github.com/langchain-ai/langgraph/tree/main/examples)

---

## Conclusion

Tools in LangGraph enable LLMs to interact with the real world through function calls. By following best practices and understanding the execution flow, you can build powerful agentic applications that combine the reasoning capabilities of LLMs with the functionality of external systems.

**Key Takeaways:**
1. Tools extend LLM capabilities beyond text generation
2. Clear docstrings and type hints are essential
3. System prompts guide tool usage behavior
4. Always handle errors gracefully
5. Fresh state for new conversations, preserved state for multi-turn chat

