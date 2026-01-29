# from typing import TypedDict, Annotated, List

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
# from langchain_community.document_loaders import UnstructuredPDFLoader, PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# from langchain_core.tools import tool
# from langchain_core.messages import HumanMessage, BaseMessage

# from langgraph.graph import StateGraph, START, END
# from langgraph.graph.message import add_messages
# from langgraph.prebuilt import ToolNode, tools_condition


# LLM Model
llm = ChatOllama(model="qwen2.5:0.5b", temperature=0.3)

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
result = retriever.invoke("What is a Decision Tree")
print(result)
