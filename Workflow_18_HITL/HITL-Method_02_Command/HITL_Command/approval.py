from langgraph.types import Command
from graph_app import app


# ===============================
# HUMAN APPROVAL SERVICE
# ===============================
if __name__ == "__main__":
    """
    This file simulates a human approval system.
    It can be CLI, UI, API, etc.
    """

    thread_id = "chat-thread-001"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    # ---- Human Decision ----
    decision = input("Approve the response? (yes/no): ").strip().lower()

    # ---- Resume Graph ----
    final_result = app.invoke(
        Command(
            resume={
                "approved": decision
            }
        ),
        config=config
    )

    print("\n--- FINAL GRAPH OUTPUT ---")
    for msg in final_result["messages"]:
        print(f"{msg.type.upper()}: {msg.content}")
