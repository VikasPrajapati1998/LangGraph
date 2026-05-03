from __future__ import annotations

import re
import json
from pathlib import Path
from typing import List, Literal, TypedDict

from pydantic import BaseModel

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
# from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_tavily import TavilySearch
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

from config import OLLAMA_MODEL, OLLAMA_TEMPERATURE, EMBEDDING_MODEL, TAVILY_API_KEY
from logger import get_logger

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

log = get_logger("CRAG")

BOOKS_DIR     = Path("./Books")
VECTOR_DIR    = Path("./VectorDB")
MANIFEST_FILE = VECTOR_DIR / "manifest.json"

BOOK_FILES = [
    BOOKS_DIR / "Bishop-on-ML.pdf",
    BOOKS_DIR / "Hands-on-ML.pdf",
    BOOKS_DIR / "IGF-DL.pdf",
]


# ──────────────────────────────────────────────────────────────
# Change-detection helpers
# ──────────────────────────────────────────────────────────────

def _file_fingerprint(path: Path) -> str:
    """Return 'mtime:size' string for a file — fast, no hashing needed."""
    stat = path.stat()
    return f"{stat.st_mtime:.6f}:{stat.st_size}"


def _build_manifest() -> dict[str, str]:
    return {
        str(p): _file_fingerprint(p)
        for p in BOOK_FILES
        if p.exists()
    }


def _load_saved_manifest() -> dict[str, str]:
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning(f"Could not read manifest, will rebuild. Reason: {exc}")
    return {}


def _save_manifest(manifest: dict[str, str]) -> None:
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.debug("Manifest saved.")


def _vector_store_needs_rebuild() -> bool:
    """Return True when the VectorDB is missing or any book has changed."""
    faiss_index = VECTOR_DIR / "index.faiss"
    if not faiss_index.exists():
        log.info("VectorDB not found — will build from scratch.")
        return True

    saved   = _load_saved_manifest()
    current = _build_manifest()

    if saved != current:
        added   = [k for k in current if k not in saved]
        removed = [k for k in saved   if k not in current]
        changed = [k for k in current if k in saved and current[k] != saved[k]]

        if added:   log.info(f"New books detected:     {[Path(p).name for p in added]}")
        if removed: log.info(f"Removed books detected: {[Path(p).name for p in removed]}")
        if changed: log.info(f"Changed books detected: {[Path(p).name for p in changed]}")

        return True

    log.info("VectorDB is up-to-date — skipping rebuild.")
    return False


# ──────────────────────────────────────────────────────────────
# Vector store — build or load
# ──────────────────────────────────────────────────────────────

embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)


def _build_vector_store() -> FAISS:
    """Load PDFs → chunk → embed → save to VectorDB."""
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    docs: list[Document] = []
    for pdf_path in BOOK_FILES:
        if not pdf_path.exists():
            log.warning(f"Book not found, skipping: {pdf_path}")
            continue
        log.info(f"Loading: {pdf_path.name}")
        docs.extend(PyPDFLoader(str(pdf_path)).load())

    log.info(f"Total pages loaded: {len(docs)}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
    chunks   = splitter.split_documents(docs)

    for chunk in chunks:
        chunk.page_content = (
            chunk.page_content.encode("utf-8", "ignore").decode("utf-8", "ignore")
        )

    log.info(f"Total chunks created: {len(chunks)}")
    log.info("Creating embeddings — this may take a while…")

    store = FAISS.from_documents(chunks, embeddings)
    store.save_local(str(VECTOR_DIR))
    log.info(f"VectorDB saved to: {VECTOR_DIR}")

    _save_manifest(_build_manifest())
    return store


def _load_vector_store() -> FAISS:
    log.info(f"Loading VectorDB from: {VECTOR_DIR}")
    store = FAISS.load_local(
        str(VECTOR_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    log.info("VectorDB loaded successfully.")
    return store


def get_vector_store() -> FAISS:
    if _vector_store_needs_rebuild():
        return _build_vector_store()
    return _load_vector_store()


# ──────────────────────────────────────────────────────────────
# RAG graph
# ──────────────────────────────────────────────────────────────

vector_store = get_vector_store()
retriever    = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 4}
)

llm = ChatOllama(model=OLLAMA_MODEL, temperature=OLLAMA_TEMPERATURE)
log.info(f"LLM ready: model={OLLAMA_MODEL}, temperature={OLLAMA_TEMPERATURE}")

# Tavily web-search tool (used only when retrieved docs are not relevant)
# web_search_tool = TavilySearchResults(
#     api_key=TAVILY_API_KEY,
#     max_results=3,
# )
web_search_tool = TavilySearch(
    api_key=TAVILY_API_KEY,
    max_results=3,
)
log.info("Tavily web-search tool ready.")


# ──────────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────────

class State(TypedDict):
    question:        str
    docs:            List[Document]
    web_search:      str            # "Yes" → fall back to Tavily; "No" → use docs
    strips:          List[str]
    kept_answers:    List[str]
    refined_context: str
    answer:          str


# ──────────────────────────────────────────────────────────────
# Structured-output schemas
# ──────────────────────────────────────────────────────────────

class GradeDoc(BaseModel):
    """Relevance score for a single retrieved document."""
    score: Literal["yes", "no"]


class KeepOrDrop(BaseModel):
    """Sentence-level relevance decision."""
    keep: bool


# ──────────────────────────────────────────────────────────────
# Node 1 — Retrieve
# ──────────────────────────────────────────────────────────────

def retrieve(state: State) -> dict:
    question = state["question"]
    log.info(f"[Retrieve] Fetching docs for: {question!r}")
    retrieved = retriever.invoke(question)
    log.info(f"[Retrieve] Got {len(retrieved)} chunks from VectorDB.")
    return {"docs": retrieved}


# ──────────────────────────────────────────────────────────────
# Node 2 — Grade Documents  (CRAG core)
# ──────────────────────────────────────────────────────────────

grade_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a relevance grader.\n"
            "Does the document contain information that helps answer the question?\n"
            "Reply with score='yes' or score='no'. Output JSON only."
        ),
        ("human", "Question: {question}\n\nDocument:\n{document}"),
    ]
)
grade_chain = grade_prompt | llm.with_structured_output(GradeDoc)


def grade_documents(state: State) -> dict:
    """
    Grade each retrieved doc.
    If ANY doc is relevant  → use VectorDB context  (web_search = 'No').
    If ALL docs irrelevant  → fall back to Tavily   (web_search = 'Yes').
    """
    question = state["question"]
    docs     = state["docs"]
    log.info(f"[Grade] Grading {len(docs)} retrieved chunks…")

    relevant_docs: List[Document] = []
    for i, doc in enumerate(docs):
        result = grade_chain.invoke(
            {"question": question, "document": doc.page_content}
        )
        label = result.score
        log.debug(f"  Chunk {i+1}/{len(docs)} → {label.upper()}: {doc.page_content[:80]}…")
        if label == "yes":
            relevant_docs.append(doc)

    if relevant_docs:
        log.info(f"[Grade] {len(relevant_docs)}/{len(docs)} chunks relevant — using VectorDB context.")
        return {"docs": relevant_docs, "web_search": "No"}
    else:
        log.info("[Grade] No relevant chunks — falling back to web search.")
        return {"docs": [], "web_search": "Yes"}


# ──────────────────────────────────────────────────────────────
# Conditional edge — decide after grading
# ──────────────────────────────────────────────────────────────

def decide_after_grade(state: State) -> str:
    if state["web_search"] == "Yes":
        log.info("[Route] → web_search")
        return "web_search"
    log.info("[Route] → refine")
    return "refine"


# ──────────────────────────────────────────────────────────────
# Node 3 — Web Search  (Tavily fallback)
# ──────────────────────────────────────────────────────────────

def web_search(state: State) -> dict:
    question = state["question"]
    log.info(f"[WebSearch] Searching Tavily for: {question!r}")
    results = web_search_tool.invoke({"query": question})

    web_docs = [
        Document(page_content=r["content"], metadata={"source": r["url"]})
        for r in results
        if "content" in r
    ]
    log.info(f"[WebSearch] Retrieved {len(web_docs)} web results.")
    for i, d in enumerate(web_docs):
        log.debug(f"  Web result {i+1}: {d.metadata.get('source', 'unknown')}")
    return {"docs": web_docs}


# ──────────────────────────────────────────────────────────────
# Node 4 — Refine  (sentence-level filter)
# ──────────────────────────────────────────────────────────────

def decompose_to_sentences(text: str) -> List[str]:
    text      = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


filter_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a strict relevance filter.\n"
            "Return keep=true ONLY if the sentence directly helps answer the question.\n"
            "Output JSON only."
        ),
        ("human", "Question: {question}\n\nSentence:\n{sentence}"),
    ]
)
filter_chain = filter_prompt | llm.with_structured_output(KeepOrDrop)


def refine(state: State) -> dict:
    question = state["question"]
    context  = "\n\n".join(d.page_content for d in state["docs"]).strip()

    # 1. Decompose into sentences
    strips = decompose_to_sentences(context)
    log.info(f"[Refine] Sentences decomposed: {len(strips)}")

    # 2. Filter with LLM judge
    kept: List[str] = []
    for i, s in enumerate(strips):
        decision = filter_chain.invoke({"question": question, "sentence": s}).keep
        log.debug(f"  Sentence {i+1}/{len(strips)} {'KEPT' if decision else 'DROPPED'}: {s[:80]}…")
        if decision:
            kept.append(s)

    log.info(f"[Refine] Kept: {len(kept)} / {len(strips)} sentences.")

    # 3. Recompose
    refined_context = "\n".join(kept).strip()
    log.debug(f"[Refine] Refined context length: {len(refined_context)} chars.")

    return {
        "strips":          strips,
        "kept_answers":    kept,
        "refined_context": refined_context,
    }


# ──────────────────────────────────────────────────────────────
# Node 5 — Generate
# ──────────────────────────────────────────────────────────────

generate_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful Machine Learning tutor.\n"
            "Use the context below to answer the question clearly and concisely.\n"
            "If the context does not contain enough information, say so briefly "
            "and answer from your general knowledge."
        ),
        ("human", "Question: {question}\n\nContext:\n{context}"),
    ]
)


def generate(state: State) -> dict:
    context = state["refined_context"]
    log.info("[Generate] Generating answer…")
    out = (generate_prompt | llm).invoke(
        {"question": state["question"], "context": context}
    )
    log.info("[Generate] Answer ready.")
    return {"answer": out.content}


# ──────────────────────────────────────────────────────────────
# Build graph
# ──────────────────────────────────────────────────────────────

graph = StateGraph(State)

graph.add_node("retrieve",        retrieve)
graph.add_node("grade_documents", grade_documents)
graph.add_node("web_search",      web_search)
graph.add_node("refine",          refine)
graph.add_node("generate",        generate)

graph.add_edge(START,             "retrieve")
graph.add_edge("retrieve",        "grade_documents")
graph.add_conditional_edges(
    "grade_documents",
    decide_after_grade,
    {"refine": "refine", "web_search": "web_search"},
)
graph.add_edge("web_search",      "refine")
graph.add_edge("refine",          "generate")
graph.add_edge("generate",        END)

app = graph.compile()
log.info("CRAG graph compiled and ready.")


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Save graph visualization
    log.info("Saving CRAG graph flow visualization to PNG…")
    png_bytes = app.get_graph().draw_mermaid_png()
    Path("crag-graph01.png").write_bytes(png_bytes)
    log.info("Graph flow saved as 'crag-graph01.png'.")

    question = "What is gradient descent?"
    log.info(f"Running query: {question!r}")

    res = app.invoke({
        "question":        question,
        "docs":            [],
        "web_search":      "No",
        "strips":          [],
        "kept_answers":    [],
        "refined_context": "",
        "answer":          "",
    })

    log.info("Query complete.")

    # ── Source label ───────────────────────────────────────────
    source_label = "Web Search (Tavily)" if res["web_search"] == "Yes" else "VectorDB"
    log.info(f"Context source used: {source_label}")

    # ── Graded chunks ──────────────────────────────────────────
    log.info(f"Total chunks after grading: {len(res['docs'])}")
    print("\n" + "=" * 60)
    print(f"Graded Chunks  [source: {source_label}]")
    print("=" * 60)
    for i, doc in enumerate(res["docs"]):
        log.debug(f"Printing chunk {i+1}")
        print(f"\n--- Chunk {i+1} ---")
        print(doc.page_content)

    # ── Kept sentences after refine ────────────────────────────
    kept = res["kept_answers"]
    log.info(f"Total sentences kept after refine: {len(kept)} / {len(res['strips'])}")
    print("\n" + "=" * 60)
    print(f"Kept Sentences After Refine  ({len(kept)} of {len(res['strips'])})")
    print("=" * 60)
    for i, sentence in enumerate(kept):
        log.debug(f"Printing kept sentence {i+1}")
        print(f"\n[{i+1}] {sentence}")

    # ── Final answer ───────────────────────────────────────────
    log.info("Printing final answer.")
    print("\n" + "=" * 60)
    print(f"Answer  [source: {source_label}]")
    print("=" * 60)
    print(res["answer"])
    log.info("Done.")
