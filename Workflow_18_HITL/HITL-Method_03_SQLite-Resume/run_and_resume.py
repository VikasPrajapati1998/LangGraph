from langgraph.types import Command
from graph_flow import graph

THREAD_ID = "deployment-123"

print("▶ Running graph (will pause at approval)...")

# FIRST RUN — will hit interrupt() and pause
result = graph.invoke(
    {},
    config={
        "configurable": {
            "thread_id": THREAD_ID
        }
    }
)

# The interrupt payload is stored under the key "__interrupt__".
# Print it so the human knows what they are approving.
interrupts = result.get("__interrupt__", [])
if interrupts:
    print(f"⏸ Graph paused. Interrupt payload: {interrupts[0].value}")
else:
    print("⏸ Graph paused. Approval required.")

# ---- simulate human approval later ----
print("▶ Resuming graph after approval...")

graph.invoke(
    Command(resume={"approved": True}),
    config={
        "configurable": {
            "thread_id": THREAD_ID
        }
    }
)

print("✔ Graph completed.")

