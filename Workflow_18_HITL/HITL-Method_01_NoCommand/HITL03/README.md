# Human-in-the-Loop (HITL) Workflow with LangGraph

This project demonstrates a human-in-the-loop workflow using LangGraph with persistent state management via SQLite checkpointing.

## Overview

The workflow splits graph execution across three separate scripts, pausing for human input before resuming. This pattern is useful for approval workflows, quality control processes, or any scenario requiring human intervention mid-execution.

## Project Structure

```
HITL/
│
├── graph.py          # Shared state, nodes, and graph builder
├── before.py         # Run until human approval checkpoint
├── human.py          # Human updates the paused state
├── after.py          # Resume execution after approval
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## How It Works

### 1. Graph Definition (`graph.py`)

Defines:
- **State**: Pydantic model with `input` and `user_feedback` fields
- **Nodes**: 
  - `step_A`: Initial processing
  - `human_feedback`: Interrupt point for human input
  - `step_B`: Post-approval processing
  - `step_C`: Final processing
- **SQLite Checkpointer**: Persists state to `graph_state.db`
- **Graph Builder**: Compiles the graph with `interrupt_before=["human_feedback"]`

### 2. Initial Execution (`before.py`)

Runs the graph until it hits the `human_feedback` interrupt:
```bash
python before.py
```

**What happens:**
- Executes `step_A`
- Pauses at `human_feedback` node
- Saves state to SQLite
- Displays current state and next node

### 3. Human Input (`human.py`)

Loads the paused state and updates it with human feedback:
```bash
python human.py
```

**What happens:**
- Prompts user for approval feedback
- Updates state with `user_feedback` field
- Saves updated state as if `human_feedback` node executed
- Displays updated state and next node

### 4. Resume Execution (`after.py`)

Resumes from the saved state:
```bash
python after.py
```

**What happens:**
- Loads state from SQLite
- Continues from `step_B`
- Executes remaining nodes (`step_B` → `step_C`)
- Displays final state

## Installation

```bash
pip install -r requirements.txt
```

Key dependencies:
- `langgraph` - Graph orchestration framework
- `langgraph-checkpoint-sqlite` - SQLite state persistence
- `pydantic` - State schema validation

## Usage Example

```bash
# Step 1: Run until interrupt
python before.py

# Output:
# --- FIRST RUN (before human approval) ---
# Step_A executed
# {'input': 'Hello World', 'user_feedback': None}
# --- Graph paused ---
# State: {'input': 'Hello World', 'user_feedback': None}
# Next node: ('human_feedback',)

# Step 2: Provide human feedback
python human.py

# Enter human approval feedback: Looks good, proceed!
# --- State updated ---
# State: {'input': 'Hello World', 'user_feedback': 'Looks good, proceed!'}
# Next node: ('step_B',)

# Step 3: Resume execution
python after.py

# Output:
# --- FINAL RUN (after human approval) ---
# Step_B executed
# User feedback: Looks good, proceed!
# Step_C executed
# User feedback: Looks good, proceed!
# --- Final State ---
# {'input': 'Hello World', 'user_feedback': 'Looks good, proceed!'}
```

## Key Concepts

### Thread ID
All three scripts use the same `thread_id` (`"approval-flow"`) to maintain continuity across executions.

### Checkpointing
The SQLite checkpointer persists state to disk, allowing:
- Cross-process state sharing
- Recovery from failures
- Audit trails of state changes

### `update_state` with `as_node`
The `human.py` script uses `as_node="human_feedback"` to update state as if the `human_feedback` node executed, ensuring proper graph progression.

### `interrupt_before`
The graph compiles with `interrupt_before=["human_feedback"]`, which pauses execution before that node and waits for external intervention.

## Important Notes

1. **SQLite Connection**: The checkpointer uses a real SQLite connection with `check_same_thread=False` to enable multi-process access.

2. **State Persistence**: The `graph_state.db` file persists between runs. Delete it to reset state.

3. **Thread Isolation**: Different thread IDs create separate execution contexts. Use the same ID to continue a workflow.

## Customization

To adapt this pattern:

1. **Modify State**: Update the `State` class in `graph.py`
2. **Add Nodes**: Define new functions and add them to the graph
3. **Change Interrupt Point**: Modify `interrupt_before` parameter
4. **Multiple Interrupts**: Add multiple nodes to `interrupt_before` list

## Use Cases

- Approval workflows (document review, expense approval)
- Quality control (manual inspection before proceeding)
- Data validation (human verification of ML outputs)
- Interactive debugging (pause and inspect intermediate results)
- Multi-stage processes with human checkpoints

## License

This is a demonstration project for educational purposes.