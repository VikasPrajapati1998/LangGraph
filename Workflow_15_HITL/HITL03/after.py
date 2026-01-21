"""
last.py
-------
Resumes graph execution using updated state.
"""

from graph import build_graph

# Build shared graph
graph = build_graph()

# Same thread ID
thread = {"configurable": {"thread_id": "approval-flow"}}

print("\n--- FINAL RUN (after human approval) ---\n")

# Resume execution
for event in graph.stream(None, thread, stream_mode="values"):
    print(event)

# Final state
print("\n--- Final State ---")
print(graph.get_state(thread).values)
