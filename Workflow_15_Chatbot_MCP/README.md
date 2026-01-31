# 🤖 Arya Chatbot - Complete Chat History Management System

A production-ready chatbot with intelligent chat history management, supporting 5 different strategies including AI-powered summarization for long conversations.

## 📁 Project Structure

```
project/
├── backend.py              # LangGraph chatbot with checkpoint
├── database.py             # PostgreSQL database management
├── history.py              # All 5 history strategies + summarization
├── frontend.py             # Streamlit UI
└── README.md              # This file
```

## 🚀 Features

### ✅ Core Features
- 💾 **Persistent Storage** - All conversations stored in PostgreSQL
- 🔄 **Multi-Chat Support** - Create, switch, and delete conversations
- 📊 **Real-time Metrics** - Token usage and reduction statistics
- 🎯 **5 History Strategies** - Choose the best for your use case
- 🤖 **AI Summarization** - Automatic summaries for long conversations
- ⚡ **Streaming Responses** - Real-time message generation
- 🎨 **Beautiful UI** - Clean Streamlit interface

### 🎯 History Management Strategies

| Strategy | Best For | Description |
|----------|----------|-------------|
| **Message Count** | Short chats (< 20 msgs) | Keep last N messages |
| **Token-Based** | Production apps | Keep messages within token limit |
| **Sliding Window** | Q&A bots | Complete conversation exchanges |
| **Hybrid** ⭐ | General purpose (20-50 msgs) | First message + recent context |
| **Summarization** | Long chats (50+ msgs) | AI summary + recent messages |

## 📋 Prerequisites

```bash
# Python 3.8+
pip install streamlit
pip install langgraph
pip install langchain-ollama
pip install langchain-core
pip install psycopg
pip install psycopg-binary

# PostgreSQL database
# Ollama with qwen2.5:0.5b model (or your preferred model)
```

## 🛠️ Setup

### 1. Database Setup

```bash
# Create PostgreSQL database
createdb langgraph_memory

# Or using psql
psql -U postgres
CREATE DATABASE langgraph_memory;
\q
```

### 2. Configure Database URI

Update `backend.py` line 11:
```python
DB_URI = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/langgraph_memory"
```

### 3. Install Ollama Model

```bash
# Download and run Ollama
ollama pull qwen2.5:0.5b

# Or use a different model (update backend.py accordingly)
ollama pull llama3:8b
```

### 4. Run the Application

```bash
streamlit run frontend.py
```

## 📊 Database Schema

### Tables Created Automatically

```sql
-- Chat threads (conversations)
chat_threads
├── thread_id (VARCHAR PRIMARY KEY)
├── title (TEXT)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)

-- Individual messages
chat_messages
├── id (SERIAL PRIMARY KEY)
├── thread_id (VARCHAR FOREIGN KEY)
├── role (VARCHAR)
├── content (TEXT)
├── created_at (TIMESTAMP)
└── message_order (INTEGER)

-- AI-generated summaries
conversation_summaries
├── id (SERIAL PRIMARY KEY)
├── thread_id (VARCHAR FOREIGN KEY)
├── summary (TEXT)
├── messages_covered (INTEGER)
├── last_message_order (INTEGER)
└── created_at (TIMESTAMP)

-- LangGraph checkpoint tables (created automatically)
checkpoints
checkpoint_writes
checkpoint_migrations
```

## 🎮 Usage Guide

### Basic Usage

1. **Start the app**: `streamlit run frontend.py`
2. **Select a strategy** in the sidebar
3. **Adjust parameters** using sliders
4. **Start chatting!**

### Strategy Selection

#### For Short Conversations (< 20 messages)
```python
Strategy: "Message Count"
Max messages: 15-20
```

#### For Medium Conversations (20-50 messages)
```python
Strategy: "Hybrid" ⭐ RECOMMENDED
Max tokens: 3000
```

#### For Long Conversations (50+ messages)
```python
Strategy: "Summarization"
Summarize threshold: 30
Recent messages: 10
```

### Understanding the Metrics

**Sidebar displays:**
- **Total Messages**: All messages in conversation
- **Sent to Model**: Messages actually sent (after management)
- **Token Reduction**: Percentage of tokens saved

**Example:**
```
Total Messages: 50
Sent to Model: 12
Token Reduction: 76%
```
This means 76% of tokens were saved by using the strategy!

## 🔧 Configuration Options

### In `frontend.py`

```python
history_manager = ChatHistoryManager(
    strategy="hybrid",              # Choose strategy
    max_messages=20,                # For message_count/sliding_window
    max_tokens=3000,                # For token_based/hybrid
    system_prompt="Your prompt",    # System message
    summarize_threshold=30,         # When to start summarizing
    recent_messages_count=10,       # Recent messages to keep
    summarizer_callback=callback    # AI summarizer function
)
```

### Available Strategies

```python
# Simple - last N messages
strategy="message_count"

# Token-aware - within limit
strategy="token_based"

# Complete exchanges
strategy="sliding_window"

# Smart hybrid (RECOMMENDED)
strategy="hybrid"

# AI summarization (for long chats)
strategy="summarization"
```

## 📖 How Each Strategy Works

### 1. Message Count
```
Full History: [M1, M2, M3, M4, M5, M6, M7, M8, M9, M10]
Max: 6
Sent:         [               M5, M6, M7, M8, M9, M10]
```

### 2. Token-Based
```
Full History: [M1(500t), M2(300t), M3(600t), M4(400t), M5(200t)]
Max: 1000 tokens
Sent:         [           M3(600t), M4(400t), M5(200t)]
```

### 3. Sliding Window
```
Full History: [U1, A1, U2, A2, U3, A3, U4, A4, U5, A5]
Keep: 3 exchanges
Sent:         [           U3, A3, U4, A4, U5, A5]
```

### 4. Hybrid (RECOMMENDED)
```
Full History: [M1, M2, M3, M4, M5, M6, M7, M8, M9, M10]
Keep: First + Recent (within tokens)
Sent:         [M1, [...], M6, M7, M8, M9, M10]
```

### 5. Summarization
```
Full History: [M1-M40] + [M41-M50]
              ↓             ↓
         AI Summary    Recent Msgs
              ↓             ↓
Sent: [System] + [Summary] + [M41-M50]
```

## 🤖 Summarization Details

### When Summaries Are Generated

1. **Automatically** when conversation reaches 30 messages (threshold)
2. **Auto-update** every 20 new messages
3. **Manually** via "Generate Summary Now" button

### Summary Prompt

The AI uses this prompt to create summaries:

```
Please provide a concise summary of the following conversation.
Focus on:
1. Main topics and questions discussed
2. Key information or solutions provided
3. Important context for continuing the conversation

Keep the summary brief (under 150 words) but informative.
```

### Viewing Summaries

When using summarization strategy:
- Sidebar shows "✅ Summary: X msgs"
- Click "View Summary" expander to see full summary
- Summary automatically included in model context

## 🎨 UI Features

### Sidebar Controls
- **Strategy Selector** - Choose from 5 strategies
- **Parameter Sliders** - Adjust strategy settings
- **Statistics Display** - Real-time metrics
- **Summary Viewer** - View AI-generated summaries
- **New Chat Button** - Start fresh conversation
- **Chat List** - Switch between conversations
- **Delete Buttons** - Remove unwanted chats

### Main Chat Area
- **Message History** - Full conversation display
- **Streaming Responses** - Real-time AI generation
- **Error Handling** - Graceful error messages
- **User Input** - Chat input at bottom

## 🔍 Advanced Usage

### Custom Model Configuration

```python
# In backend.py
model = ChatOllama(
    model="llama3:8b",      # Change model
    temperature=0.7,        # Adjust creativity
)
```

### Custom System Prompt

```python
# In frontend.py
history_manager = ChatHistoryManager(
    system_prompt="You are a Python expert assistant specialized in data science."
)
```

### Programmatic Summary Generation

```python
from history import ConversationSummarizer
from backend import model, DB_URI
from database import ChatDatabase

db = ChatDatabase(DB_URI)
summarizer = ConversationSummarizer(model=model, db=db)

# Force generate summary
summary = summarizer.update_summary_if_needed(
    thread_id="your-thread-id",
    all_messages=messages,
    force=True
)
```

## 📊 Performance Optimization

### For Small Models (2K-4K context)
```python
strategy="token_based"
max_tokens=2000
```

### For Medium Models (8K context)
```python
strategy="hybrid"
max_tokens=4000
```

### For Large Models (32K+ context)
```python
strategy="message_count"
max_messages=30
# Or
strategy="summarization"
summarize_threshold=50
```

## 🐛 Troubleshooting

### Database Connection Error
```bash
# Check PostgreSQL is running
pg_isready

# Verify database exists
psql -U postgres -l | grep langgraph_memory
```

### Summary Not Generating
```python
# Check threshold
print(f"Messages: {len(chat_history)}")
print(f"Threshold: {history_manager.summarize_threshold}")

# Force generation
summarizer.update_summary_if_needed(thread_id, messages, force=True)
```

### Model Not Found
```bash
# List available models
ollama list

# Pull required model
ollama pull qwen2.5:0.5b
```

### Import Errors
```bash
# Reinstall dependencies
pip install --upgrade streamlit langgraph langchain-ollama psycopg
```

## 📚 File Descriptions

### `backend.py`
- LangGraph workflow setup
- ChatOllama model configuration
- PostgreSQL checkpoint integration
- Exports: `chatbot`, `model`, `DB_URI`

### `database.py`
- Database connection management
- Table creation (threads, messages, summaries)
- CRUD operations for chats
- Summary storage methods

### `history.py`
- `ChatHistoryManager` class - 5 strategies
- `ConversationSummarizer` class - AI summarization
- Token estimation
- Message conversion utilities

### `frontend.py`
- Streamlit UI setup
- Session state management
- Strategy selection interface
- Chat display and input handling

## 🎯 Best Practices

1. **Start with Hybrid** - Works for 80% of use cases
2. **Switch to Summarization** - When chats exceed 50 messages
3. **Monitor Metrics** - Check token reduction percentage
4. **Adjust Thresholds** - Based on your model's context limit
5. **Use System Prompts** - For better AI behavior

## 🔐 Security Notes

- Summaries stored in same database as messages
- No external API calls (local model only)
- Database credentials in code (use env vars in production)
- Consider encryption for sensitive data

## 📈 Future Enhancements

- [ ] Environment variable configuration
- [ ] Multi-user support with authentication
- [ ] Export conversations to PDF/JSON
- [ ] Custom summary prompts per conversation
- [ ] Incremental summary updates
- [ ] Vector database integration for semantic search

## 📄 License

MIT License - feel free to use and modify!

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review the code comments
3. Check Streamlit/LangGraph documentation

---

**Happy Chatting! 🚀**