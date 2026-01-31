import os
from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool

# ========== CONFIG ==========
PDF_PATH = "Intro2ML.pdf"
VECTOR_DB_DIR = "./faiss_db_book"

# ========== EMBEDDINGS ==========
embedding = OllamaEmbeddings(model="nomic-embed-text:v1.5")

# ========== LOGIC ==========
if not os.path.exists(VECTOR_DB_DIR) or not os.listdir(VECTOR_DB_DIR):
    # Load PDF
    loader = PDFPlumberLoader(PDF_PATH)
    docs = loader.load()

    # Split documents
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunks = splitter.split_documents(docs)

    # Create FAISS vector store
    vector_store = FAISS.from_documents(
        documents=chunks,
        embedding=embedding
    )

    # Save locally
    vector_store.save_local(VECTOR_DB_DIR)
    
else:
    vector_store = FAISS.load_local(
        folder_path=VECTOR_DB_DIR,
        embeddings=embedding,
        allow_dangerous_deserialization=True
    )

# ========== RETRIEVER ==========
retriever = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 4}
)

# ========== TOOL ==========
@tool
def book_tool(query: str):
    """Retrieve relevant information from the Book PDF."""
    try:
        docs = retriever.invoke(query)
        return {
            "query": query,
            "context": "\n\n".join(d.page_content for d in docs),
            "metadata": [d.metadata for d in docs]
        }
    except Exception as e:
        return {"error": f"Book Tool Error: {str(e)}"}

# # ========== TEST ==========
# query = "What is XGBoost? Explain it in detail."
# result = retriever.invoke(query)
# print(result)

__all__ = ["book_tool"]
