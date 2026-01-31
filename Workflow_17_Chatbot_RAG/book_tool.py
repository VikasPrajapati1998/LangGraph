import os
from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool


def setup():
    """Create vector_data directory if it doesn't exist"""
    os.makedirs("vector_data", exist_ok=True)


def get_retriever(file_path: str):
    """
    Create or load a FAISS retriever for the given PDF file.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        FAISS retriever object
    """
    # ========== EMBEDDINGS ==========
    embedding = OllamaEmbeddings(model="nomic-embed-text:v1.5")
    
    # Create a unique directory name based on the file name
    file_name = os.path.basename(file_path).replace('.pdf', '').replace(' ', '_')
    vector_db_dir = os.path.join("vector_data", file_name)

    # ========== LOGIC ==========
    if not os.path.exists(vector_db_dir) or not os.listdir(vector_db_dir):
        print(f"Creating vector store for {file_path}...")
        
        # Ensure the PDF file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        # Load PDF
        loader = PDFPlumberLoader(file_path)
        docs = loader.load()
        
        if not docs:
            raise ValueError(f"No content extracted from PDF: {file_path}")
        
        print(f"Loaded {len(docs)} pages from PDF")

        # Split documents
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = splitter.split_documents(docs)
        print(f"   Split into {len(chunks)} chunks")

        # Create FAISS vector store
        vector_store = FAISS.from_documents(
            documents=chunks,
            embedding=embedding
        )

        # Save locally
        vector_store.save_local(vector_db_dir)
        print(f"Vector store saved to {vector_db_dir}")
        
    else:
        print(f"Loading existing vector store from {vector_db_dir}...")
        vector_store = FAISS.load_local(
            folder_path=vector_db_dir,
            embeddings=embedding,
            allow_dangerous_deserialization=True
        )
        print(f"Vector store loaded successfully")

    # ========== RETRIEVER ==========
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5}
    )
    
    return retriever


# ========== TOOL ==========
@tool
def book_tool(query: str, file_path: str = "software_development.pdf"):
    """Retrieve relevant information from a PDF book.
    
    This tool searches through a PDF document to find relevant information
    based on your query. It uses semantic search to find the most relevant
    sections of the document.
    
    Args:
        query: The question or search query about the book content
        file_path: Path to the PDF file to search (default: software_development.pdf)
        
    Returns:
        Dictionary containing the query, relevant context, and metadata
    """
    try:
        # Ensure vector_data directory exists
        setup()
        
        print(f"Searching PDF: {file_path}")
        print(f"Query: {query}")
        
        # Get retriever for the specific file
        retriever = get_retriever(file_path)
        
        # Retrieve relevant documents
        docs = retriever.invoke(query)
        
        print(f"Found {len(docs)} relevant chunks")
        
        # Format the context
        context = "\n\n---\n\n".join(d.page_content for d in docs)
        
        return {
            "query": query,
            "context": context,
            "metadata": [d.metadata for d in docs],
            "num_chunks": len(docs)
        }
    except FileNotFoundError as e:
        error_msg = f"PDF file not found: {str(e)}\nPlease make sure the file '{file_path}' exists."
        print(f"{error_msg}")
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Book Tool Error: {str(e)}"
        print(f"{error_msg}")
        return {"error": error_msg}


# ========== TEST ==========
if __name__ == "__main__":
    # Example usage
    file_path = "software_development.pdf"  # Replace with your PDF path
    query = "What is the Life Cycle of a Software Development Project?"
    
    print("=" * 60)
    print("TESTING BOOK TOOL")
    print("=" * 60)
    
    # Direct tool test
    result = book_tool.invoke({
        "query": query,
        "file_path": file_path
    })
    
    print("\n" + "=" * 60)
    print("RESULT:")
    print("=" * 60)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Query: {result['query']}")
        print(f"Found {result['num_chunks']} relevant chunks")
        print(f"Context:\n{result['context'][:500]}...")


__all__ = ["book_tool", "get_retriever", "setup"]

