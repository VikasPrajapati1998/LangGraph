import os
import glob
from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool


def setup():
    """Create vector_data directory if it doesn't exist"""
    os.makedirs("vector_data", exist_ok=True)
    os.makedirs("data", exist_ok=True)


def find_pdf_by_name(pdf_name: str) -> str:
    """
    Find the PDF file path by name (searches in data/ folder)
    
    Args:
        pdf_name: Name of the PDF (with or without .pdf extension)
        
    Returns:
        str: Full path to the PDF file
        
    Raises:
        FileNotFoundError: If PDF is not found
    """
    # Ensure pdf_name has .pdf extension
    if not pdf_name.lower().endswith('.pdf'):
        pdf_name = f"{pdf_name}.pdf"
    
    # Search in data/ folder
    data_path = os.path.join("data", pdf_name)
    if os.path.exists(data_path):
        return data_path
    
    # Also check root directory (for backward compatibility)
    if os.path.exists(pdf_name):
        return pdf_name
    
    # Case-insensitive search in data/ folder
    data_files = glob.glob(os.path.join("data", "*.pdf"))
    for file_path in data_files:
        if os.path.basename(file_path).lower() == pdf_name.lower():
            return file_path
    
    # Not found - list available PDFs
    available = [os.path.basename(f) for f in data_files]
    raise FileNotFoundError(
        f"PDF '{pdf_name}' not found.\n"
        f"Available PDFs: {', '.join(available) if available else 'None'}"
    )


def get_vector_store_name(file_path: str) -> str:
    """
    Get the vector store directory name from file path
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        str: Directory name for vector store (cleaned filename)
    """
    # Get filename without path and extension
    file_name = os.path.basename(file_path)
    file_name = file_name.replace('.pdf', '').replace('.PDF', '')
    
    # Clean the name (replace spaces and special chars with underscore)
    clean_name = file_name.replace(' ', '_')
    clean_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in clean_name)
    
    return clean_name


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
    
    # Get clean vector store directory name
    vector_store_name = get_vector_store_name(file_path)
    vector_db_dir = os.path.join("vector_data", vector_store_name)

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
        
        print(f"   Loaded {len(docs)} pages from PDF")

        # Split documents
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1800,
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
        os.makedirs(vector_db_dir, exist_ok=True)
        vector_store.save_local(vector_db_dir)
        print(f"   ✅ Vector store saved to {vector_db_dir}")
        
    else:
        print(f"Loading existing vector store from {vector_db_dir}...")
        vector_store = FAISS.load_local(
            folder_path=vector_db_dir,
            embeddings=embedding,
            allow_dangerous_deserialization=True
        )
        print(f"   ✅ Vector store loaded successfully")

    # ========== RETRIEVER ==========
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5}
    )
    
    return retriever


def list_available_pdfs() -> list:
    """
    List all available PDF files in data/ folder
    
    Returns:
        list: List of PDF names (without path)
    """
    pdf_files = glob.glob(os.path.join("data", "*.pdf"))
    return [os.path.basename(f) for f in pdf_files]


# ========== TOOL ==========
@tool
def book_tool(query: str, pdf_name: str):
    """Retrieve relevant information from a PDF document by name.
    
    This tool searches through a PDF document to find relevant information
    based on your query. It uses semantic search to find the most relevant
    sections of the document.
    
    **How to use:**
    - User mentions the PDF name in their question
    - Examples:
      * "From machine_learning.pdf, explain gradient descent"
      * "Ask intro_to_python about list comprehension"
      * "What does software_development say about testing?"
    
    Args:
        query: The question or search query about the document content
        pdf_name: Name of the PDF file to search (e.g., "machine_learning" or "machine_learning.pdf")
        
    Returns:
        Dictionary containing the query, relevant context from the PDF, and metadata
        
    Examples:
        >>> book_tool(query="What is gradient descent?", pdf_name="machine_learning")
        >>> book_tool(query="Explain testing", pdf_name="software_development.pdf")
    """
    try:
        # Ensure directories exist
        setup()
        
        print(f"\n{'='*60}")
        print(f"📖 BOOK TOOL CALLED")
        print(f"{'='*60}")
        print(f"📝 Query: {query}")
        print(f"📄 PDF Name: {pdf_name}")
        
        # Find the PDF file by name
        try:
            file_path = find_pdf_by_name(pdf_name)
            print(f"✅ Found PDF: {file_path}")
        except FileNotFoundError as e:
            available_pdfs = list_available_pdfs()
            error_msg = (
                f"❌ PDF '{pdf_name}' not found.\n\n"
                f"**Available PDFs:**\n"
                + "\n".join([f"  • {pdf}" for pdf in available_pdfs])
                if available_pdfs else
                f"❌ PDF '{pdf_name}' not found. No PDFs available in data/ folder."
            )
            print(error_msg)
            return {"error": error_msg, "available_pdfs": available_pdfs}
        
        # Get retriever for the specific file
        retriever = get_retriever(file_path)
        
        # Retrieve relevant documents
        docs = retriever.invoke(query)
        
        print(f"✅ Found {len(docs)} relevant chunks")
        print(f"{'='*60}\n")
        
        # Format the context
        context = "\n\n---\n\n".join(d.page_content for d in docs)
        
        return {
            "query": query,
            "pdf_name": pdf_name,
            "pdf_path": file_path,
            "context": context,
            "metadata": [d.metadata for d in docs],
            "num_chunks": len(docs)
        }
        
    except FileNotFoundError as e:
        error_msg = str(e)
        print(f"❌ {error_msg}")
        return {"error": error_msg}
        
    except Exception as e:
        error_msg = f"Book Tool Error: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}


# ========== HELPER FUNCTION FOR FRONTEND ==========
def create_vector_store_for_pdf(file_path: str) -> dict:
    """
    Create vector store for a PDF file (called from frontend during upload)
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        dict: Status information
    """
    try:
        setup()
        print(f"\n{'='*60}")
        print(f"🔄 CREATING VECTOR STORE")
        print(f"{'='*60}")
        print(f"📄 File: {file_path}")
        
        # Create the retriever (this will create the vector store)
        retriever = get_retriever(file_path)
        
        vector_store_name = get_vector_store_name(file_path)
        vector_db_dir = os.path.join("vector_data", vector_store_name)
        
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "file_path": file_path,
            "vector_store_dir": vector_db_dir,
            "vector_store_name": vector_store_name,
            "message": f"✅ Vector store created: {vector_store_name}"
        }
        
    except Exception as e:
        error_msg = f"Failed to create vector store: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "error": error_msg
        }


# ========== TEST ==========
if __name__ == "__main__":
    # Example usage
    setup()
    
    print("=" * 60)
    print("TESTING BOOK TOOL")
    print("=" * 60)
    
    # Test 1: List available PDFs
    print("\n1. Listing available PDFs:")
    available = list_available_pdfs()
    for pdf in available:
        print(f"   • {pdf}")
    
    if available:
        # Test 2: Query a PDF by name
        test_pdf = available[0].replace('.pdf', '')
        query = "What are the main topics covered?"
        
        print(f"\n2. Testing query with PDF: {test_pdf}")
        print(f"   Query: {query}")
        
        result = book_tool.invoke({
            "query": query,
            "pdf_name": test_pdf
        })
        
        print("\n" + "=" * 60)
        print("RESULT:")
        print("=" * 60)
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✅ Query: {result['query']}")
            print(f"✅ PDF: {result['pdf_name']}")
            print(f"✅ Found {result['num_chunks']} relevant chunks")
            print(f"\nContext preview:\n{result['context'][:300]}...")
    else:
        print("\n❌ No PDFs found in data/ folder")
        print("💡 Upload a PDF first!")


__all__ = [
        "book_tool", 
        "get_retriever", 
        "setup", 
        "create_vector_store_for_pdf", 
        "find_pdf_by_name", 
        "list_available_pdfs"
    ]

