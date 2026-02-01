# 🤖 Arya Chatbot - RAG-Enabled Chat System with Intelligent History Management

A production-ready AI chatbot with PDF document querying (RAG), intelligent chat history management, and 5 different memory strategies including AI-powered summarization.

## 🎯 Key Features

- 📄 **PDF Document RAG** - Upload and query PDF documents with FAISS vector search
- 💾 **Persistent Storage** - PostgreSQL database for conversations and vector stores
- 🔄 **Multi-Chat Support** - Create, switch, and delete conversations
- 🧠 **5 Memory Strategies** - Optimized context management for different use cases
- 🤖 **AI Summarization** - Automatic summaries for long conversations
- ⚡ **Streaming Responses** - Real-time message generation with tool call visibility
- 🛠️ **MCP Tool Integration** - Calculator, Stock Price, Expense Tracker, and DuckDuckGo search

## 📋 Prerequisites

```bash
# Python 3.8+
pip install streamlit langgraph langchain-ollama langchain-core
pip install psycopg psycopg-binary faiss-cpu pdfplumber
pip install langchain-community python-dotenv langchain-mcp-adapters

# PostgreSQL database
# Ollama with models: qwen3:0.6b, nomic-embed-text:v1.5
```

## 📁 Project Structure

```
project/
├── frontend.py              # Streamlit UI with PDF upload
├── backend.py              # LangGraph chatbot + MCP tools
├── book_tool.py            # PDF RAG retrieval tool
├── database.py             # PostgreSQL operations
├── history.py              # 5 history strategies + summarization
├── data/                   # 📄 Uploaded PDF files
│   ├── document1.pdf
│   └── document2.pdf
└── vector_data/            # 🗄️ FAISS vector stores (auto-generated)
    ├── document1/
    │   ├── index.faiss
    │   └── index.pkl
    └── document2/
```

## 🚀 Quick Start

### 1. Database Setup

```bash
# Create PostgreSQL database
createdb langgraph_memory

# Configure connection in backend.py
DB_URI = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/langgraph_memory"
```

### 2. Install Ollama Models

```bash
ollama pull qwen3:0.6b              # Main chat model
ollama pull nomic-embed-text:v1.5   # Embeddings for PDF RAG
```

### 3. Run Application

```bash
streamlit run frontend.py
```

## 📄 PDF Document RAG

### Upload & Query Workflow

```
1. Upload PDF → Saved to data/ folder
2. Auto-process → FAISS vector store created in vector_data/
3. Ask questions → AI automatically searches relevant context
4. Get answers → Based on actual document content
```

### Usage Examples

```python
# Upload "machine_learning.pdf" via UI

# Then ask naturally:
"What does machine_learning.pdf say about neural networks?"
"Summarize the key concepts from the document"
"Explain gradient descent from the PDF"
```

### How It Works

```python
# book_tool.py - Automatic RAG retrieval
@tool
def book_tool(query: str, file_path: str):
    """Retrieve relevant information from PDF"""
    retriever = get_retriever(file_path)  # FAISS vector search
    docs = retriever.invoke(query)         # Find top-5 chunks
    return {"context": context, "metadata": metadata}

# backend.py - LangGraph integration
tools = [search_tool, *mcp_tools, book_tool]
model = llm.bind_tools(tools)
```

## 🧠 Memory Management Strategies

| Strategy | Best For | Context Size | Description |
|----------|----------|--------------|-------------|
| **Message Count** | Short (< 20 msgs) | Fixed | Keep last N messages |
| **Token-Based** | Production | Dynamic | Stay within token limit |
| **Sliding Window** | Q&A | Balanced | Complete user-assistant exchanges |
| **Hybrid** ⭐ | General (20-50) | Smart | First message + recent context |
| **Summarization** | Long (50+) | Compressed | AI summary + recent messages |

### Strategy Configuration

```python
# frontend.py
history_manager = ChatHistoryManager(
    strategy="hybrid",              # Default: hybrid
    max_messages=20,                # For message_count/sliding_window
    max_tokens=3000,                # For token_based/hybrid
    summarize_threshold=30,         # When to trigger summarization
    recent_messages_count=10,       # Recent messages to keep
    system_prompt="You are Arya, a helpful AI assistant."
)
```

## 🛠️ MCP Tool Servers

Configure custom MCP servers in `backend.py`:

```python
SERVER = {
    "Calculator": {
        "command": "uv",
        "args": ["--directory", "path/to/Calculator", "run", "main.py"],
        "transport": "stdio"
    },
    "StockServer": {...},
    "ExpenseTracker": {...}
}
```

Available tools: Calculator, Stock Price Lookup, Expense Tracker, Web Search, PDF Query

## 📊 Database Schema

```sql
-- Conversations
chat_threads (thread_id, title, created_at, updated_at)

-- Messages
chat_messages (id, thread_id, role, content, created_at, message_order)

-- AI Summaries
conversation_summaries (id, thread_id, summary, messages_covered, last_message_order)

-- LangGraph Checkpoints (auto-created)
checkpoints, checkpoint_writes, checkpoint_migrations
```

## 💡 Advanced Usage

### Custom Document Querying

```python
# In chat: Mention specific file path
"What does data/custom_doc.pdf say about topic X?"

# book_tool automatically called with correct path
tool_call = {
    'name': 'book_tool',
    'args': {
        'query': 'topic X',
        'file_path': 'data/custom_doc.pdf'
    }
}
```

### Force Summary Generation

```python
from history import ConversationSummarizer

summarizer = ConversationSummarizer(model=llm, db=db)
summary = summarizer.update_summary_if_needed(
    thread_id="your-thread-id",
    all_messages=messages,
    force=True  # Generate immediately
)
```

### Change LLM Model

```python
# backend.py
llm = ChatOllama(
    model="llama3.2:1b",    # Options: qwen3:0.6b, mistral:latest
    temperature=0.7,
)
```

## 🎨 UI Features

### Sidebar
- **Document Management** - Upload, view, delete PDFs with size info
- **Memory Strategy Selector** - Choose from 5 strategies with live parameters
- **Real-time Metrics** - Total messages, sent to model, token reduction %
- **Conversation List** - Switch between chats, delete unwanted threads
- **Summary Viewer** - View AI-generated conversation summaries

### Main Chat
- **Document Tips** - Expandable guide showing available PDFs and query examples
- **Tool Call Visibility** - See when book_tool, calculator, or search is used
- **Retrieved Context Preview** - View PDF chunks used for answers
- **Streaming Responses** - Real-time message generation with status updates

## 🔧 Performance Optimization

```python
# Small models (2K-4K context)
strategy="token_based", max_tokens=2000

# Medium models (8K context)
strategy="hybrid", max_tokens=4000

# Large models (32K+ context)
strategy="summarization", summarize_threshold=50
```

## 🐛 Troubleshooting

### PDF Upload Error
```bash
# Ensure directories exist
mkdir -p data vector_data

# Check Ollama embedding model
ollama list | grep nomic-embed-text
```

### Database Connection Error
```bash
# Verify PostgreSQL is running
pg_isready

# Check database exists
psql -U postgres -l | grep langgraph_memory
```

### Vector Store Not Creating
```bash
# Manually test embedding model
ollama pull nomic-embed-text:v1.5
ollama run nomic-embed-text:v1.5 "test"
```

### StreamlitAPIException
```python
# Fixed in updated frontend.py
# Changed st.sidebar.spinner() → st.spinner()
```

## 📈 Metrics Example

```
Sidebar Display:
├── Total Messages: 45
├── Sent to Model: 12
└── Token Reduction: 73%

Summary Status:
✅ Summary: 35 msgs covered
```

This means: 45 total messages → Only 12 sent to model (73% token savings)

## 🔐 Security Notes

- Database credentials in code (use environment variables in production)
- Local models only (no external API calls)
- Vector stores stored locally (no cloud dependencies)
- Consider encryption for sensitive document content

## 🎯 Best Practices

1. **Start with Hybrid strategy** - Best for 80% of use cases
2. **Monitor token reduction** - Aim for 50-70% savings
3. **Name PDFs clearly** - Avoid special characters in filenames
4. **Use summarization** - For conversations exceeding 50 messages
5. **Delete unused PDFs** - Saves disk space (removes vector stores too)

## 📝 Example Session

```bash
# 1. Start app
streamlit run frontend.py

# 2. Upload PDF
Upload "machine_learning.pdf" → Saved to data/machine_learning.pdf
Vector store created → vector_data/machine_learning/

# 3. Ask questions
User: "What does machine_learning.pdf cover?"
AI: [Uses book_tool] → Returns summary from PDF

User: "Calculate 25 * 67"
AI: [Uses calculator MCP] → Returns 1675

User: "Search for latest AI news"
AI: [Uses DuckDuckGo search] → Returns search results

# 4. Switch to Summarization (after 30+ messages)
Strategy: Summarization
AI generates summary of conversation
Only sends: [Summary] + [Recent 10 messages]
```

## 🚦 Directory Setup

```bash
# Auto-created on first run
data/           # PDF storage
vector_data/    # FAISS indices
venv/          # Python environment (create manually)

# Manual setup
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

## 📦 File Responsibilities

| File | Purpose |
|------|---------|
| `backend.py` | LangGraph workflow, model config, MCP integration |
| `frontend.py` | Streamlit UI, PDF upload, chat interface |
| `book_tool.py` | FAISS retrieval, PDF processing, vector store |
| `database.py` | PostgreSQL CRUD, thread/message/summary management |
| `history.py` | 5 memory strategies, token estimation, summarization |

## 🎓 Technical Details

### Vector Store Creation
```python
# Triggered on PDF upload
PDFPlumberLoader → RecursiveCharacterTextSplitter (1000/200) 
→ OllamaEmbeddings (nomic-embed-text) → FAISS.from_documents 
→ Saved to vector_data/<filename>/
```

### Context Management Flow
```python
# Each user message
Full history → Strategy filter → Managed history → LLM
Example: 50 msgs → Hybrid strategy → 12 msgs → Model (76% reduction)
```

### Tool Calling
```python
# Automatic based on query
User query → LLM analyzes → Determines tool needed 
→ Calls tool (book_tool/calculator/search) 
→ Returns result → LLM generates final answer
```

## 📄 License

MIT License - Free to use and modify

---

**Built with:** LangGraph • LangChain • Streamlit • PostgreSQL • FAISS • Ollama  
**Author:** Your Name  
**Version:** 2.0 (RAG-enabled)
