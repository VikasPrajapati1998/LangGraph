from typing import TypedDict, Annotated, List

# ===============================
# LangChain / LangGraph Imports
# ===============================
from langchain_ollama import ChatOllama
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

# ===============================
# LLM Configuration
# ===============================
llm = ChatOllama(
    model="qwen3:0.6b",
    temperature=0.5
)

# ===============================
# Graph State Definition
# ===============================
class ChatState(TypedDict):
    """
    messages:
        - Maintains conversation history
        - add_messages automatically appends new messages
    """
    messages: Annotated[List[BaseMessage], add_messages]

# ===============================
# Chat Node with HITL
# ===============================
def chat_node(state: ChatState):
    """
    This node:
    1. Interrupts execution before model answers
    2. Waits for human approval
    3. Resumes execution based on approval
    """

    # ---- HITL Interrupt ----
    decision = interrupt({
        "type": "approval",
        "reason": "Model is about to answer a user question.",
        "question": state["messages"][-1].content,
        "instruction": "Approve this question? yes/no"
    })

    # ---- Resume Logic ----
    if decision["approved"].lower() != "yes":
        # Human rejected the question
        return {
            "messages": [
                AIMessage(content="❌ The response was not approved by a human reviewer.")
            ]
        }

    # Human approved → LLM can respond
    response = llm.invoke(state["messages"])

    return {
        "messages": [response]
    }

# ===============================
# Build the LangGraph
# ===============================
builder = StateGraph(ChatState)

builder.add_node("chat", chat_node)

builder.add_edge(START, "chat")
builder.add_edge("chat", END)

# ===============================
# Checkpointer (REQUIRED for HITL)
# ===============================
checkpointer = MemorySaver()

# Compile the graph
app = builder.compile(checkpointer=checkpointer)

# ===============================
# Thread / Session Config
# ===============================
config = {
    "configurable": {
        "thread_id": "hitl-demo-123"
    }
}

# ===============================
# STEP 1: Initial Invocation
# ===============================
initial_input = {
    "messages": [
        HumanMessage(content="Explain gradient descent in very simple terms.")
    ]
}

# This invocation WILL PAUSE at interrupt
result = app.invoke(initial_input, config=config)

# Extract interrupt payload
interrupt_payload = result["__interrupt__"][0].value

print("\n--- HITL INTERRUPT ---")
print(f"Reason      : {interrupt_payload['reason']}")
print(f"Question    : {interrupt_payload['question']}")
print(f"Instruction : {interrupt_payload['instruction']}")

# ===============================
# Human Decision (Simulated)
# ===============================
human_decision = input("\nApprove this question? (yes/no): ").strip()

# ===============================
# STEP 2: Resume Execution
# ===============================
final_result = app.invoke(
    Command(
        resume={
            "approved": human_decision
        }
    ),
    config=config
)

# ===============================
# Final Output
# ===============================
print("\n--- FINAL OUTPUT ---")
for msg in final_result["messages"]:
    print(f"{msg.type.upper()}: {msg.content}")
