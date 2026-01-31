# 📝 Quick Reference Card

## 🚀 Getting Started

```bash
# 1. Install dependencies
pip install streamlit langgraph langchain-ollama psycopg

# 2. Create database
createdb langgraph_memory

# 3. Pull Ollama model
ollama pull qwen2.5:0.5b

# 4. Run application
streamlit run frontend.py
```

## 📁 Complete File Structure

```
project/
├── backend.py          # LangGraph + Model + Checkpoint
├── database.py         # PostgreSQL operations
├── history.py          # 5 strategies + Summarization
├── frontend.py         # Streamlit UI
└── README.md          # Documentation
```

## 🎯 Strategy Quick Selection

| Your Situation | Use This |
|----------------|----------|
| Chat < 20 messages | Message Count |
| Chat 20-50 messages | Hybrid ⭐ |
| Chat 50-100 messages | Summarization |
| Chat 100+ messages | Summarization |
| Need exact control | Token-Based |
| Q&A bot | Sliding Window |

## ⚙️ Configuration Cheat Sheet

### Message Count Strategy
```python
strategy="message_count"
max_messages=20
```
**Use when**: Short conversations, simple bots

### Token-Based Strategy
```python
strategy="token_based"
max_tokens=3000
```
**Use when**: API cost control, strict limits

### Sliding Window Strategy
```python
strategy="sliding_window"
max_messages=20  # 10 exchanges
```
**Use when**: Q&A, customer support

### Hybrid Strategy ⭐
```python
strategy="hybrid"
max_tokens=3000
```
**Use when**: General chatbots, 20-50 msgs

### Summarization Strategy
```python
strategy="summarization"
summarize_threshold=30
recent_messages_count=10
```
**Use when**: Long conversations, 50+ msgs

## 📊 Understanding Metrics

```
Total Messages: 50        ← All messages in DB
Sent to Model: 12         ← Messages actually sent
Token Reduction: 76%      ← Efficiency gain
```

**Good Token Reduction:**
- 0-30%: Light optimization
- 30-60%: Good efficiency
- 60-80%: Excellent efficiency
- 80%+: Maximum compression

## 🗄️ Database Tables

```sql
chat_threads              -- Conversations
chat_messages             -- Individual messages
conversation_summaries    -- AI summaries
checkpoints              -- LangGraph state
```

## 🎨 UI Components

### Sidebar
- Strategy dropdown
- Parameter sliders
- Metrics display
- Summary viewer
- New chat button
- Chat list
- Delete buttons

### Main Area
- Chat history
- Message input
- Streaming responses

## 🔧 Common Tasks

### Change Strategy in UI
1. Open sidebar
2. Select from "Memory Strategy" dropdown
3. Adjust sliders if needed
4. Continue chatting

### View Summary
1. Use "Summarization" strategy
2. Chat until 30+ messages
3. Sidebar shows "✅ Summary"
4. Click "View Summary" to expand

### Force Summary Generation
1. Select "Summarization" strategy
2. Sidebar shows "⚠️ Summary needed"
3. Click "Generate Summary Now"
4. Wait 2-5 seconds

### Switch Conversations
1. Sidebar → "My Conversations"
2. Click conversation preview
3. History loads automatically

### Delete Conversation
1. Find conversation in sidebar
2. Click 🗑️ button
3. Confirms deletion

### Create New Chat
1. Click "🆕 New Chat" in sidebar
2. New empty conversation starts
3. Old chats preserved

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Database error | Check PostgreSQL running: `pg_isready` |
| Model not found | Pull model: `ollama pull qwen2.5:0.5b` |
| Import error | Reinstall: `pip install -r requirements.txt` |
| Summary not generating | Check message count > threshold |
| Slow responses | Use smaller model or reduce tokens |

## 💡 Pro Tips

1. **Start Simple**: Begin with Message Count, upgrade as needed
2. **Monitor Metrics**: Watch token reduction percentage
3. **Use Hybrid**: Best default for most cases
4. **Summarization for Scale**: Switch when > 50 messages
5. **Adjust Thresholds**: Based on your model's limits

## 🎯 Recommended Settings by Model

### Small Models (2K-4K context)
```python
strategy="token_based"
max_tokens=2000
```

### Medium Models (8K context)
```python
strategy="hybrid"
max_tokens=4000
```

### Large Models (32K+ context)
```python
strategy="summarization"
summarize_threshold=50
recent_messages_count=15
```

## 📈 Performance Expectations

| Strategy | Processing Time | Token Efficiency |
|----------|----------------|------------------|
| Message Count | Instant | ⭐⭐ Medium |
| Token-Based | Instant | ⭐⭐⭐⭐ High |
| Sliding Window | Instant | ⭐⭐⭐ Good |
| Hybrid | < 1 second | ⭐⭐⭐⭐ High |
| Summarization | 2-5 seconds (first) | ⭐⭐⭐⭐⭐ Excellent |

## 🔍 Code Snippets

### Check Message Count
```python
print(f"Messages: {len(st.session_state.chat_history)}")
```

### Get Statistics
```python
stats = history_manager.get_history_stats(chat_history)
print(stats)
```

### Force Summary
```python
summarizer.update_summary_if_needed(
    thread_id, 
    messages, 
    force=True
)
```

### Change Model
```python
# In backend.py
model = ChatOllama(
    model="llama3:8b",
    temperature=0.7
)
```

## 📚 Import Guide

```python
# frontend.py
from backend import chatbot, DB_URI, model
from database import ChatDatabase
from history import ChatHistoryManager, ConversationSummarizer, create_summary_callback
from langchain_core.messages import HumanMessage, AIMessage
```

## 🎨 Color Codes in UI

- 🔵 Blue dot: Active conversation
- 💬 Speech bubble: Inactive conversation
- ✅ Green checkmark: Summary exists
- ⚠️ Warning: Summary needed
- 🗑️ Trash: Delete button
- 🆕 New icon: Create chat
- ⚙️ Gear: Settings/controls

## 🔑 Key Files to Edit

**Change database credentials:**
→ `backend.py` line 11

**Adjust default strategy:**
→ `frontend.py` line 15

**Modify summary prompt:**
→ `history.py` line 267

**Change model:**
→ `backend.py` line 17

## 📊 File Sizes (Approximate)

```
backend.py       ~2 KB
database.py      ~6 KB
history.py       ~15 KB
frontend.py      ~8 KB
Total            ~31 KB
```

## ⚡ Keyboard Shortcuts

**Streamlit Default:**
- `Ctrl/Cmd + R` - Refresh app
- `Ctrl/Cmd + K` - Clear cache
- `Esc` - Exit fullscreen

## 🎓 Learning Path

1. **Week 1**: Use Message Count
2. **Week 2**: Try Hybrid
3. **Week 3**: Experiment with Token-Based
4. **Week 4**: Enable Summarization
5. **Week 5**: Optimize for your use case

---

**Keep this card handy for quick reference! 📌**
