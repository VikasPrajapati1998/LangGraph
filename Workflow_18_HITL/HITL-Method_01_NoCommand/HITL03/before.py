"""
before.py
---------
Runs the graph until it reaches the human approval step.
State is saved to SQLite.
"""

from graph import build_graph

# Build shared graph
graph = build_graph()

# Shared thread ID
thread = {"configurable": {"thread_id": "approval-flow"}}

# Initial input
initial_input = {"input": "Hello World"}

print("\n--- FIRST RUN (before human approval) ---\n")

# Run graph until interruption
for event in graph.stream(initial_input, thread, stream_mode="values"):
    print(event)

# Inspect paused state
print("\n--- Graph paused ---")
print("State:", graph.get_state(thread).values)
print("Next node:", graph.get_state(thread).next)

