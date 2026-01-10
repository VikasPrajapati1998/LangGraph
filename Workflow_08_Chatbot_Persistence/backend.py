from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# State
class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

# Model
model = ChatOllama(
    model="qwen2.5:0.5b",
    temperature=0.3
)

# Nodes
def chat_node(state: ChatState):
    message = state['messages']
    response = model.invoke(message)
    return {'messages': [response]}

# Graph
graph = StateGraph(ChatState)

# Node
graph.add_node('chat_node', chat_node)

# Edge
graph.add_edge(START, 'chat_node')
graph.add_edge('chat_node', END)

# Compile
conn = sqlite3.connect("conversation.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)

workflow = graph.compile(checkpointer=checkpointer)


thread_id = '1'
config = {'configurable': {'thread_id': thread_id}}

user_message = "What is capital of India?"
response = workflow.invoke({'messages': [HumanMessage(content=user_message)]}, config=config)

