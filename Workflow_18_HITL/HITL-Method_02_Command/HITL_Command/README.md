# Human-in-the-Loop (HITL) Approval System

## How It Works

This system implements a human approval workflow using LangGraph:

1. **graph_app.py** - Starts the graph, interrupts, and waits for human approval
2. **approval.py** - Resumes the graph after human decision

## Prerequisites

**IMPORTANT: Ollama must be running!**

The system uses Ollama to run the `qwen3:0.6b` model. Before running approval.py, you must:

1. Install Ollama: https://ollama.ai
2. Pull the model: `ollama pull qwen3:0.6b`
3. Start Ollama server: `ollama serve`

## How to Run

### Step 1: Start the Graph
```bash
python graph_app.py
```

This will:
- Initialize the graph
- Trigger an interrupt
- Display the question waiting for approval
- Save state to SQLite database

Output:
```
--- GRAPH PAUSED (HITL) ---
Thread ID   : chat-thread-001
Question    : Explain gradient descent in very simple terms.
Instruction : Approve this response? (yes/no)

Waiting for approval...
```

### Step 2: Make Sure Ollama is Running

In a **separate terminal**, start Ollama:
```bash
ollama serve
```

Keep this running in the background.

### Step 3: Provide Approval
```bash
python approval.py
```

This will:
- Prompt you for approval (yes/no)
- Resume the graph from where it was interrupted
- Call the LLM if approved
- Display the final output

Example:
```
Approve the response? (yes/no): yes

--- FINAL GRAPH OUTPUT ---
HUMAN: Explain gradient descent in very simple terms.
AI: [LLM response here]
```

## Workflow Diagram

```
graph_app.py                    approval.py
     │                               │
     ├─→ Create initial state        │
     ├─→ Start graph execution       │
     ├─→ Hit interrupt() ─────────→  │
     ├─→ Save state to SQLite        │
     └─→ Display waiting message     │
                                     ├─→ Get human decision
                                     ├─→ Resume graph with Command
                                     ├─→ Call LLM (needs Ollama!)
                                     └─→ Display final result
```

## Troubleshooting

### Error: "No connection could be made"
**Cause**: Ollama is not running
**Solution**: 
1. Open a new terminal
2. Run `ollama serve`
3. Try approval.py again

### Error: "Model not found"
**Cause**: qwen3:0.6b model not downloaded
**Solution**: Run `ollama pull qwen3:0.6b`

### Change the Model
Edit `graph_app.py` line 15-18:
```python
llm = ChatOllama(
    model="llama2",  # Change to any Ollama model
    temperature=0.5
)
```

## Database

The system uses SQLite to persist state between runs:
- Database file: `langgraph_state.db`
- Thread ID: `chat-thread-001`

To start fresh, delete the database file:
```bash
rm langgraph_state.db
```
