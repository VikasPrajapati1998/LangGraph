# Stage 2: Retrieval Evolution
from __future__ import annotations

import re
import json
from pathlib import Path
from typing import List, TypedDict

from pydantic import BaseModel

from langchain_community.document_loaders import PDFPlumberLoader
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

log = get_logger("CRAG05")

BOOKS_DIR     = Path("./Books")
VECTOR_DIR    = Path("./VectorDB")
MANIFEST_FILE = VECTOR_DIR / "manifest.json"

BOOK_FILES = [
    BOOKS_DIR / "Bishop-on-ML.pdf",
    BOOKS_DIR / "Hands-on-ML.pdf",
    BOOKS_DIR / "IGF-DL.pdf",
]

SEP  = "─" * 60   # thin separator  (node internals)
SEP2 = "═" * 60   # thick separator (node entry/exit)


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
    """Load PDFs → chunk → embed → save to VectorDB.
    Uses PDFPlumberLoader (preserves tables and layout far better than PyPDFLoader)."""
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    docs: list[Document] = []
    for pdf_path in BOOK_FILES:
        if not pdf_path.exists():
            log.warning(f"Book not found, skipping: {pdf_path}")
            continue
        log.info(f"Loading: {pdf_path.name}")
        docs.extend(PDFPlumberLoader(str(pdf_path)).load())

    log.info(f"Total pages loaded: {len(docs)}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=100)
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
    search_type="similarity",
    search_kwargs={"k": 8}
)

llm = ChatOllama(model=OLLAMA_MODEL, temperature=OLLAMA_TEMPERATURE)
log.info(f"LLM ready: model={OLLAMA_MODEL}, temperature={OLLAMA_TEMPERATURE}")

UPPER_LIMIT = 0.7
LOWER_LIMIT = 0.3
log.info(f"Relevance thresholds set: UPPER_LIMIT={UPPER_LIMIT}, LOWER_LIMIT={LOWER_LIMIT}")


# ──────────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────────

class State(TypedDict):
    question: str
    docs: List[Document]

    good_docs: List[Document]  # docs whose score is more than LOWER_LIMIT
    verdict: str               # CORRECT, INCORRECT, or AMBIGUOUS
    reason: str                # reason for the verdict

    strips: List[str]
    kept_strips: List[str]
    refined_context: str

    answer: str


# ──────────────────────────────────────────────────────────────
# Node 1 — Retrieve
# ──────────────────────────────────────────────────────────────

def retrieve_node(state: State) -> State:
    question = state["question"]

    log.info(SEP2)
    log.info("NODE  ▶  retrieve")
    log.info(SEP2)
    log.info(f"  Question : {question!r}")
    log.info(f"  Fetching top-{retriever.search_kwargs['k']} chunks from VectorDB…")

    retrieved = retriever.invoke(question)

    log.info(f"  Chunks retrieved : {len(retrieved)}")
    for i, doc in enumerate(retrieved, 1):
        source = doc.metadata.get("source", "unknown")
        page   = doc.metadata.get("page",   "?")
        preview = doc.page_content[:120].replace("\n", " ")
        log.info(f"  [{i:02d}] source={Path(source).name}  page={page}  "
                 f"chars={len(doc.page_content)}  preview={preview!r}…")

    log.info(SEP)
    return {"docs": retrieved}


# ──────────────────────────────────────────────────────────────
# Node 2 — Eval (per-doc scoring + verdict)
# ──────────────────────────────────────────────────────────────

class DocEvalScore(BaseModel):
    score: float
    reason: str


doc_eval_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a strict retrieval evaluator for RAG.\n"
            "You will be given ONE retrieved chunk and a question.\n"
            "Return a relevance score in [0.0, 1.0]\n"
            "- 1.0: chunk alone is sufficient to answer fully/mostly\n"
            "- 0.0: chunk is irrelevant\n"
            "Be conservative with high scores.\n"
            "Also return a short reason.\n"
            "Output JSON only.",
        ),
        ("human", "Question: {question}\n\nChunk:\n{chunk}"),
    ]
)

doc_eval_chain = doc_eval_prompt | llm.with_structured_output(DocEvalScore)


def eval_each_doc_node(state: State) -> State:
    question = state["question"]

    log.info(SEP2)
    log.info("NODE  ▶  eval")
    log.info(SEP2)
    log.info(f"  Evaluating {len(state['docs'])} retrieved chunks…")
    log.info(f"  Thresholds — UPPER: {UPPER_LIMIT}  LOWER: {LOWER_LIMIT}")
    log.info(SEP)

    scores: List[float] = []
    reasons: List[str]  = []
    good:   List[Document] = []

    for i, doc in enumerate(state["docs"], 1):
        out = doc_eval_chain.invoke({"question": question, "chunk": doc.page_content})
        scores.append(out.score)
        reasons.append(out.reason)

        # Classify this individual chunk
        if out.score > UPPER_LIMIT:
            tag = "✅ HIGH  (> UPPER)"
        elif out.score > LOWER_LIMIT:
            tag = "🟡 MID   (> LOWER)"
        else:
            tag = "❌ LOW   (< LOWER)"

        is_good = out.score > LOWER_LIMIT
        if is_good:
            good.append(doc)

        source  = doc.metadata.get("source", "unknown")
        page    = doc.metadata.get("page",   "?")
        log.info(
            f"  Chunk [{i:02d}]  score={out.score:.3f}  {tag}\n"
            f"           source={Path(source).name}  page={page}\n"
            f"           reason={out.reason}"
        )

    # ── Summary table ─────────────────────────────────────────
    log.info(SEP)
    log.info("  EVAL SUMMARY")
    log.info(f"  Total chunks evaluated : {len(scores)}")
    log.info(f"  Chunks > UPPER ({UPPER_LIMIT}) : "
             f"{sum(s > UPPER_LIMIT for s in scores)}")
    log.info(f"  Chunks > LOWER ({LOWER_LIMIT}) : "
             f"{sum(s > LOWER_LIMIT for s in scores)}  ← will be used as good_docs")
    log.info(f"  Chunks < LOWER ({LOWER_LIMIT}) : "
             f"{sum(s < LOWER_LIMIT for s in scores)}")
    if scores:
        log.info(f"  Score range            : {min(scores):.3f} – {max(scores):.3f}")
        log.info(f"  Score avg              : {sum(scores)/len(scores):.3f}")
    log.info(f"  Good docs collected    : {len(good)}")

    # ── Verdict ───────────────────────────────────────────────
    if any(s > UPPER_LIMIT for s in scores):
        verdict = "CORRECT"
        reason  = (
            f"At least one retrieved chunk scored > {UPPER_LIMIT} "
            "and is sufficient to answer."
        )
    elif len(scores) == 0 or all(s < LOWER_LIMIT for s in scores):
        verdict = "INCORRECT"
        reason  = f"All retrieved chunks scored < {LOWER_LIMIT}."
        good    = []
    else:
        verdict = "AMBIGUOUS"
        reason  = (
            f"No chunk scored > {UPPER_LIMIT}, but not all were below {LOWER_LIMIT}. "
            "Mixed relevance signals."
        )

    log.info(SEP)
    log.info(f"  VERDICT ▶  {verdict}")
    log.info(f"  Reason  ▶  {reason}")
    log.info(SEP)

    return {
        "good_docs": good,
        "verdict":   verdict,
        "reason":    reason,
    }


# ──────────────────────────────────────────────────────────────
# Router — after eval
# ──────────────────────────────────────────────────────────────

def route_after_eval(state: State) -> str:
    verdict = state["verdict"]

    log.info(SEP2)
    log.info("ROUTER  ▶  route_after_eval")
    log.info(SEP2)

    if verdict == "CORRECT":
        next_node = "refine"
    elif verdict == "INCORRECT":
        next_node = "fail_node"
    else:
        next_node = "ambiguous_node"

    log.info(f"  Verdict received : {verdict}")
    log.info(f"  Routing to node  : {next_node}")
    log.info(SEP)
    return next_node


# ──────────────────────────────────────────────────────────────
# Node 3a — Refine (Decompose → Filter → Recompose)
# ──────────────────────────────────────────────────────────────

class KeepOrDrop(BaseModel):
    keep: bool


filter_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a strict relevance filter.\n"
            "Return keep=true only if the sentence directly helps answer the question.\n"
            "Use ONLY the sentence. Output JSON only."
        ),
        ("human", "Question: {question}\n\nSentence: \n{sentence}")
    ]
)

filter_chain = filter_prompt | llm.with_structured_output(KeepOrDrop)


def decompose_to_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def refine(state: State) -> State:
    question  = state["question"]
    good_docs = state["good_docs"]

    log.info(SEP2)
    log.info("NODE  ▶  refine")
    log.info(SEP2)
    log.info(f"  Good docs entering refine : {len(good_docs)}")
    for i, doc in enumerate(good_docs, 1):
        source = doc.metadata.get("source", "unknown")
        page   = doc.metadata.get("page",   "?")
        log.info(f"  [{i:02d}] source={Path(source).name}  page={page}  "
                 f"chars={len(doc.page_content)}")

    context = "\n\n".join(d.page_content for d in good_docs).strip()
    log.info(f"  Combined context length   : {len(context)} chars")
    log.info(SEP)

    # 1. Decompose into sentences
    strips = decompose_to_sentences(context)
    log.info(f"  Step 1 — Decompose: {len(strips)} sentences extracted")
    log.info(SEP)

    # 2. Filter with LLM judge
    kept:    List[str] = []
    dropped: List[str] = []

    log.info("  Step 2 — LLM Sentence Filter:")
    for i, s in enumerate(strips, 1):
        decision = filter_chain.invoke({"question": question, "sentence": s}).keep
        label    = "KEPT   ✅" if decision else "DROPPED ❌"
        log.info(f"    [{i:03d}/{len(strips):03d}] {label} | {s[:100]}…")
        if decision:
            kept.append(s)
        else:
            dropped.append(s)

    log.info(SEP)
    log.info(f"  Step 2 Summary:")
    log.info(f"    Sentences total   : {len(strips)}")
    log.info(f"    Sentences KEPT    : {len(kept)}")
    log.info(f"    Sentences DROPPED : {len(dropped)}")
    keep_pct = (len(kept) / len(strips) * 100) if strips else 0
    log.info(f"    Keep rate         : {keep_pct:.1f}%")

    # 3. Recompose
    refined_context = "\n".join(kept).strip()
    log.info(SEP)
    log.info(f"  Step 3 — Recomposed context length: {len(refined_context)} chars")
    log.info(SEP)

    return {
        "strips":          strips,
        "kept_strips":     kept,
        "refined_context": refined_context,
    }


# ──────────────────────────────────────────────────────────────
# Node 3b — Generate
# ──────────────────────────────────────────────────────────────

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful ML tutor. Answer ONLY using the provided refined bullets.\n"
            "If the bullets are empty or insufficient, say: 'I don't know based on the provided book.'",
        ),
        ("human", "Question: {question}\n\nContext:\n{context}"),
    ]
)


def generate(state: State) -> dict:
    log.info(SEP2)
    log.info("NODE  ▶  generate")
    log.info(SEP2)

    context = state["refined_context"]
    log.info(f"  Refined context length : {len(context)} chars")
    log.info(f"  Refined sentence count : {len(state.get('kept_strips', []))}")

    if not context.strip():
        log.warning("  ⚠️  Refined context is EMPTY — LLM will likely say 'I don't know'.")

    log.info("  Calling LLM to generate answer…")
    out = (prompt | llm).invoke(
        {"question": state["question"], "context": context}
    )

    answer = out.content
    log.info(f"  Answer length : {len(answer)} chars")
    log.info(f"  Answer preview: {answer[:200].replace(chr(10), ' ')!r}…")
    log.info(SEP)

    return {"answer": answer}


# ──────────────────────────────────────────────────────────────
# Node 4 — Fail / Ambiguous terminals
# ──────────────────────────────────────────────────────────────

def fail_node(state: State) -> State:
    log.info(SEP2)
    log.info("NODE  ▶  fail_node")
    log.info(SEP2)
    log.warning(f"  ❌ RETRIEVAL FAILED")
    log.warning(f"  Reason : {state['reason']}")
    log.info(SEP)
    return {"answer": f"FAIL : {state['reason']}"}


def ambiguous_node(state: State) -> State:
    log.info(SEP2)
    log.info("NODE  ▶  ambiguous_node")
    log.info(SEP2)
    log.warning(f"  🟡 RETRIEVAL AMBIGUOUS")
    log.warning(f"  Reason      : {state['reason']}")
    log.warning(f"  Good docs   : {len(state.get('good_docs', []))}")
    log.info(SEP)
    return {"answer": f"AMBIGUOUS : {state['reason']}"}


# ──────────────────────────────────────────────────────────────
# Build graph
# ──────────────────────────────────────────────────────────────

graph = StateGraph(State)

graph.add_node("retrieve",       retrieve_node)
graph.add_node("eval",           eval_each_doc_node)
graph.add_node("refine",         refine)
graph.add_node("generate",       generate)
graph.add_node("fail_node",      fail_node)
graph.add_node("ambiguous_node", ambiguous_node)

graph.add_edge(START, "retrieve")
graph.add_edge("retrieve", "eval")
graph.add_conditional_edges(
    "eval",
    route_after_eval,
    {
        "refine":         "refine",
        "fail_node":      "fail_node",
        "ambiguous_node": "ambiguous_node",
    },
)
graph.add_edge("refine",         "generate")
graph.add_edge("generate",       END)
graph.add_edge("fail_node",      END)
graph.add_edge("ambiguous_node", END)

app = graph.compile()
log.info("RAG graph compiled and ready.")


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def run():
    # Save the RAG graph/flow visualization as PNG
    log.info("Saving RAG graph flow visualization to PNG…")
    png_bytes = app.get_graph().draw_mermaid_png()
    Path("crag-refine.png").write_bytes(png_bytes)
    log.info("Graph flow saved successfully as 'crag-refine.png'")

    question = "What are attention mechanisms and why are they important in current models ?"
    log.info(f"Running query: {question!r}")

    res = app.invoke({
        "question":        question,
        "docs":            [],
        "good_docs":       [],
        "verdict":         "",
        "reason":          "",
        "strips":          [],
        "kept_strips":     [],
        "refined_context": "",
        "answer":          "",
    })

    log.info("Query complete.")

    # ════════════════════════════════════════════════════════════
    # Final printed report
    # ════════════════════════════════════════════════════════════
    docs        = res.get("docs",         [])
    good_docs   = res.get("good_docs",    [])
    strips      = res.get("strips",       [])
    kept        = res.get("kept_strips",  [])
    verdict     = res.get("verdict",      "N/A")
    reason      = res.get("reason",       "N/A")

    print("\n" + "=" * 60)
    print("  PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  Question          : {question}")
    print(f"  Chunks retrieved  : {len(docs)}")
    print(f"  Good docs (>LOWER): {len(good_docs)}")
    print(f"  Verdict           : {verdict}")
    print(f"  Reason            : {reason}")
    print(f"  Sentences total   : {len(strips)}")
    print(f"  Sentences kept    : {len(kept)}")
    keep_pct = (len(kept) / len(strips) * 100) if strips else 0
    print(f"  Keep rate         : {keep_pct:.1f}%")

    # ── Retrieved raw chunks ──────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  RETRIEVED CHUNKS  ({len(docs)} total)")
    print("=" * 60)
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        page   = doc.metadata.get("page",   "?")
        print(f"\n--- Chunk {i:02d} | source={Path(source).name} | page={page} "
              f"| chars={len(doc.page_content)} ---")
        print(doc.page_content)

    # ── Good docs ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  GOOD DOCS  ({len(good_docs)} passed LOWER threshold {LOWER_LIMIT})")
    print("=" * 60)
    for i, doc in enumerate(good_docs, 1):
        source = doc.metadata.get("source", "unknown")
        page   = doc.metadata.get("page",   "?")
        print(f"\n--- Good Doc {i:02d} | source={Path(source).name} | page={page} ---")
        print(doc.page_content)

    # ── Verdict banner ────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  VERDICT: {verdict}")
    print(f"  {reason}")
    print("=" * 60)

    # ── Kept sentences ────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  KEPT SENTENCES AFTER REFINE  ({len(kept)} of {len(strips)})")
    print("=" * 60)
    for i, sentence in enumerate(kept, 1):
        print(f"\n  [{i:03d}] {sentence}")

    # ── Final answer ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  FINAL ANSWER")
    print("=" * 60)
    print(res["answer"])
    print("=" * 60)

    log.info("Done.")


if __name__ == "__main__":
    run()




# Bias variance tradeoff.
# AI news from last week.
# What are attention mechanisms and why are they important in current models?
