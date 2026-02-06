from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from deep_translator import GoogleTranslator

llm = ChatOllama(
    model="qwen3:0.6b",  # llama3.2:1b, qwen2.5:0.5b, mistral:latest
    temperature=0.7,
)


# ================== Sub Graph ========================
# --- State ---
class SubState(TypedDict):
    input_text: str
    translated_text: str


# --- Node ---
def translate_text(state: SubState) -> SubState:
    translated = GoogleTranslator(
        source="en",
        target="hi"
    ).translate(state["input_text"])

    return {
        "translated_text": translated
    }


# --- Graph ---
subgraph_builder = StateGraph(SubState)

subgraph_builder.add_node("translate_text", translate_text)
subgraph_builder.add_edge(START, "translate_text")
subgraph_builder.add_edge("translate_text", END)

subgraph = subgraph_builder.compile()

# ====================== Parent Graph ===============================
# --- State ---
class ParentState(TypedDict):
    question: str
    answer_english: str
    answer_hindi: str


# --- Nodes ---
def generate_answer(state: ParentState) -> ParentState:
    answer = llm.invoke(
        f"You are a helpful assistant. Answer clearly.\n\n"
        f"Question: {state['question']}"
    ).content

    return {
        "answer_english": answer
    }


def translate_answer(state: ParentState) -> ParentState:
    result = subgraph.invoke(
        {"input_text": state["answer_english"]}
    )

    return {
        "answer_hindi": result["translated_text"]
    }


# --- Parent Graph ---
parent_builder = StateGraph(ParentState)

parent_builder.add_node("answer", generate_answer)
parent_builder.add_node("translate", translate_answer)

parent_builder.add_edge(START, "answer")
parent_builder.add_edge("answer", "translate")
parent_builder.add_edge("translate", END)

graph = parent_builder.compile()

# --- Invoke ---
response = graph.invoke(
    {"question": "What is quantum physics?"}
)

print(response)
