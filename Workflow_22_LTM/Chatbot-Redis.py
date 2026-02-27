import uuid
from typing import List
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.store.redis import RedisStore
from langgraph.store.base import BaseStore

# =========================
# 1. Initialize LLMs
# =========================
chat_llm = ChatOllama(model="llama3.2:3b", temperature=0.5)
memory_llm = ChatOllama(model="qwen3:1.7b", temperature=0.3)

# =========================
# 2. System Prompt
# =========================
SYSTEM_PROMPT_TEMPLATE = """You are a helpful assistant with memory capabilities.

Use stored memory naturally and personalize responses. Always:
- Address the user by name if known
- Suggest 3 relevant follow-up questions at the end

User Memory:
{user_details_content}
"""

# =========================
# 3. Pydantic Memory Models
# =========================
class MemoryItem(BaseModel):
    text: str
    is_new: bool

class MemoryDecision(BaseModel):
    should_write: bool
    memories: List[MemoryItem] = Field(default_factory=list)

memory_extractor = memory_llm.with_structured_output(MemoryDecision)

# =========================
# 4. Memory Extraction Prompt
# =========================
MEMORY_PROMPT = """You manage long-term user memory.

CURRENT MEMORY:
{user_details_content}

TASK:
- Extract stable facts (identity, job, preferences, projects)
- Keep atomic short sentences
- Mark is_new=True only if not already stored
- No guessing
- If nothing useful, return should_write=False
"""

# =========================
# 5. Remember Node
# =========================
def remember_node(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
    user_id = config["configurable"]["user_id"]
    ns = ("user", user_id, "details")

    items = list(store.search(ns))
    existing_memory = "\n".join(it.value["data"] for it in items) if items else "(empty)"
    last_message = state["messages"][-1].content

    decision: MemoryDecision = memory_extractor.invoke([
        SystemMessage(content=MEMORY_PROMPT.format(user_details_content=existing_memory)),
        {"role": "user", "content": last_message}
    ])

    if decision.should_write:
        for mem in decision.memories:
            if mem.is_new:
                store.put(ns, str(uuid.uuid4()), {"data": mem.text})

    return {}

# =========================
# 6. Chat Node
# =========================
def chat_node(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
    user_id = config["configurable"]["user_id"]
    ns = ("user", user_id, "details")

    items = list(store.search(ns))
    user_memory = "\n".join(it.value["data"] for it in items) if items else "(empty)"

    system_message = SystemMessage(
        content=SYSTEM_PROMPT_TEMPLATE.format(user_details_content=user_memory)
    )

    response = chat_llm.invoke([system_message] + state["messages"])
    return {"messages": [response]}

# =========================
# 7. Build Graph
# =========================
builder = StateGraph(MessagesState)
builder.add_node("remember", remember_node)
builder.add_node("chat", chat_node)
builder.add_edge(START, "remember")
builder.add_edge("remember", "chat")
builder.add_edge("chat", END)

# =========================
# 8. Connect to Redis
# =========================
REDIS_URI = "redis://localhost:6379"

with RedisStore.from_conn_string(REDIS_URI) as store:
    store.setup()  # Run once if fresh Redis

    graph = builder.compile(store=store)
    config = {"configurable": {"user_id": "u1"}}

    print("Interactive chatbot started! Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        response = graph.invoke({"messages": [{"role": "user", "content": user_input}]}, config)
        assistant_reply = response["messages"][-1].content
        print(f"\nAssistant:\n{assistant_reply}\n")

        # Show stored memories for debug (optional)
        print("-" * 20 + " Stored Memories " + "-" * 20)
        for item in store.search(("user", "u1", "details")):
            print(item.value["data"])
        print("-" * 60)

        print("\n"*2)
        print("="*80)


