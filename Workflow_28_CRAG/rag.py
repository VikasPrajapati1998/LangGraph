from __future__ import annotations

import json
from pathlib import Path
from typing import List, TypedDict

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

from config import OLLAMA_MODEL, OLLAMA_TEMPERATURE, EMBEDDING_MODEL
from logger import get_logger

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

log = get_logger("RAG")

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
    """Build a fingerprint dict for all existing book files."""
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

    # Sanitise encoding
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
    search_type="mmr",   # similarity
    search_kwargs={"k": 4}
)

llm = ChatOllama(model=OLLAMA_MODEL, temperature=OLLAMA_TEMPERATURE)
log.info(f"LLM ready: model={OLLAMA_MODEL}, temperature={OLLAMA_TEMPERATURE}")


class State(TypedDict):
    question: str
    docs: List[Document]
    answer: str


def retrieve(state: State) -> dict:
    question = state["question"]
    log.debug(f"Retrieving docs for question: {question!r}")
    retrieved = retriever.invoke(question)
    log.debug(f"Retrieved {len(retrieved)} chunks.")
    return {"docs": retrieved}


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Answer only from the context provided. "
            "If the answer is not in the context, say you don't know.",
        ),
        ("human", "Question: {question}\n\nContext:\n{context}"),
    ]
)


def generate(state: State) -> dict:
    context = "\n\n".join(d.page_content for d in state["docs"])
    log.debug("Generating answer…")
    out = (prompt | llm).invoke(
        {"question": state["question"], "context": context}
    )
    log.debug("Answer generated.")
    return {"answer": out.content}


# Build graph
graph = StateGraph(State)

graph.add_node("retrieve", retrieve)
graph.add_node("generate", generate)

graph.add_edge(START, "retrieve")
graph.add_edge("retrieve", "generate")
graph.add_edge("generate", END)

app = graph.compile()
log.info("RAG graph compiled and ready.")


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Save the RAG graph/flow visualization as PNG (uses built-in Mermaid renderer)
    log.info("Saving RAG graph flow visualization to PNG...")
    png_bytes = app.get_graph().draw_mermaid_png()
    Path("rag-graph.png").write_bytes(png_bytes)
    log.info("Graph flow saved successfully as 'rag-graph.png'")

    # question = "Explain the bias-variance tradeoff."
    # question="What are top AI news from last month?"
    # question = "What is a transformer in deep learning?"
    # question = "What is air pollution and how does it affect human health?"
    question = "What is gradient descent?"
    log.info(f"Running query: {question!r}")

    res = app.invoke({"question": question, "docs": [], "answer": ""})

    log.info("Query complete.")
    for i in range(4):
        print("-"*60)
        print(f"Page {i+1}: ")
        print(res["docs"][i].page_content)
        print("-"*60)
        print("\n"*2)
    
    print("\n" + "=" * 60)
    print("Answer:")
    print("=" * 60)
    print(res["answer"])
