from typing import TypedDict, Annotated, List

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
# from langchain_community.document_loaders import UnstructuredPDFLoader, PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, BaseMessage

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


# ========== RAG ==========
# Embedding Model
embedding = OllamaEmbeddings(model="nomic-embed-text:v1.5")

# Load the Documents
loader = PyPDFLoader("Intro2ML.pdf")
docs = loader.load()

# Chunking
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = splitter.split_documents(docs)

# Generate Embeddings
vector_store = FAISS.from_documents(documents=chunks, embedding=embedding)

# Retriever
retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={'k': 4})
# result = retriever.invoke("What is a Decision Tree. Explain in detail.")
# print(result)

# ========== Tool ==========
@tool
def rag_tool(query):
    """
    Retrieve relevant information from the pdf document.
    Use this tool when the user asks factual / conceptual questions
    that might be answered from the stored documents.
    """
    result = retriever.invoke(query)
    context = [doc.page_content for doc in result]
    metadata = [doc.metadata for doc in result]

    return {
        'query': query,
        'context': context,
        'metadata': metadata
    }

tools = [rag_tool]

# LLM Model
llm = ChatOllama(model="qwen2.5:3b", temperature=0.4)
model = llm.bind_tools(tools)

# State
class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

# Node
def chat_node(state: ChatState):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

tool_node = ToolNode(tools)

# Graph
graph = StateGraph(ChatState)

graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges(
    "chat_node",
    tools_condition,
    {
        "tools": "tools",
        END: END
    }
)
graph.add_edge("tools", "chat_node")

chatbot = graph.compile()

# Run
while True: 
    print("="*80)
    query = input("User: ")
    if query.lower().strip() in ["exit", "quit"]:
        break
    response = chatbot.invoke({"messages": [HumanMessage(content=(query))]})
    result = response['messages'][-1].content
    print("Bot: ", result)
    print("="*80)

