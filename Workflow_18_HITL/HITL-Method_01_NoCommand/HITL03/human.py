"""
human.py
--------
Loads paused graph state and updates it with human approval.
"""

from graph import build_graph

# Build shared graph
graph = build_graph()

# Same thread ID
thread = {"configurable": {"thread_id": "approval-flow"}}

# Collect human input
approval = input("\nEnter human approval feedback: ")

# Update state as if human_feedback node ran
graph.update_state(
    thread,
    {"user_feedback": approval},
    as_node="human_feedback"
)

print("\n--- State updated ---")
print("State:", graph.get_state(thread).values)
print("Next node:", graph.get_state(thread).next)
