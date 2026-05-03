# crag06-refine.py  —  Stage 6: Corrective RAG with Web-Search Fallback
#
# Flow:
#   START → retrieve → eval
#     ├─ CORRECT    → refine(good_docs) → generate                          → END
#     ├─ INCORRECT  → rewrite_query → web_search → generate(web only)       → END
#     └─ AMBIGUOUS  → rewrite_query → web_search → refine(good_docs)
#                                                → generate(refined + web)  → END
#
from __future__ import annotations

import os
import re
import json
from pathlib import Path
from typing import List, TypedDict

from pydantic import BaseModel

from langchain_community.document_loaders import PDFPlumberLoader
from langchain_community.vectorstores import FAISS
from langchain_community.tools.tavily_search import TavilySearchResults
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

log = get_logger("CRAG06")

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

UPPER_LIMIT = 0.7   # score threshold — chunk is fully relevant
LOWER_LIMIT = 0.3   # score threshold — chunk is worth keeping
MIN_QUERIES = 3     # minimum sub-questions to generate & search
MAX_QUERIES = 6     # maximum sub-questions to generate & search


# ──────────────────────────────────────────────────────────────
# Change-detection helpers
# ──────────────────────────────────────────────────────────────

def _file_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime:.6f}:{stat.st_size}"


def _build_manifest() -> dict[str, str]:
    return {str(p): _file_fingerprint(p) for p in BOOK_FILES if p.exists()}


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
        str(VECTOR_DIR), embeddings, allow_dangerous_deserialization=True
    )
    log.info("VectorDB loaded successfully.")
    return store


def get_vector_store() -> FAISS:
    if _vector_store_needs_rebuild():
        return _build_vector_store()
    return _load_vector_store()


# ──────────────────────────────────────────────────────────────
# LLM + Retriever + Tavily
# ──────────────────────────────────────────────────────────────

vector_store = get_vector_store()
retriever    = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 8},
)

llm = ChatOllama(model=OLLAMA_MODEL, temperature=OLLAMA_TEMPERATURE)
log.info(f"LLM ready: model={OLLAMA_MODEL}, temperature={OLLAMA_TEMPERATURE}")
log.info(f"Relevance thresholds: UPPER={UPPER_LIMIT}  LOWER={LOWER_LIMIT}")

# Expose the key so Tavily's client can pick it up from the environment
os.environ.setdefault("TAVILY_API_KEY", TAVILY_API_KEY)
tavily = TavilySearchResults(max_results=5)
log.info(f"Tavily search tool ready (max_results=5, queries={MIN_QUERIES}–{MAX_QUERIES})")


# ──────────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────────

class State(TypedDict):
    question:    str
    docs:        List[Document]   # raw chunks from VectorDB

    good_docs:   List[Document]   # chunks that scored > LOWER_LIMIT
    verdict:     str              # CORRECT | INCORRECT | AMBIGUOUS
    reason:      str

    # Web-search path
    sub_questions: List[str]      # K rewritten queries
    web_docs:      List[Document] # raw Tavily results as Documents

    # Shared refine path
    strips:          List[str]
    kept_strips:     List[str]
    refined_context: str

    answer: str


# ──────────────────────────────────────────────────────────────
# Node 1 — Retrieve  (VectorDB)
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
        source  = doc.metadata.get("source", "unknown")
        page    = doc.metadata.get("page",   "?")
        preview = doc.page_content[:120].replace("\n", " ")
        log.info(
            f"  [{i:02d}] source={Path(source).name}  page={page}  "
            f"chars={len(doc.page_content)}  preview={preview!r}…"
        )

    log.info(SEP)
    return {"docs": retrieved}


# ──────────────────────────────────────────────────────────────
# Node 2 — Eval  (per-doc scoring + verdict)
# ──────────────────────────────────────────────────────────────

class DocEvalScore(BaseModel):
    score:  float
    reason: str


doc_eval_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a strict retrieval evaluator for RAG.\n"
        "You will be given ONE retrieved chunk and a question.\n"
        "Return a relevance score in [0.0, 1.0]:\n"
        "  1.0 = chunk alone is sufficient to answer fully/mostly\n"
        "  0.0 = chunk is completely irrelevant\n"
        "Be conservative with high scores.\n"
        "Also return a short reason.\n"
        "Output JSON only.",
    ),
    ("human", "Question: {question}\n\nChunk:\n{chunk}"),
])

doc_eval_chain = doc_eval_prompt | llm.with_structured_output(DocEvalScore)


def eval_each_doc_node(state: State) -> State:
    question = state["question"]

    log.info(SEP2)
    log.info("NODE  ▶  eval")
    log.info(SEP2)
    log.info(f"  Evaluating {len(state['docs'])} retrieved chunks…")
    log.info(f"  Thresholds — UPPER: {UPPER_LIMIT}  LOWER: {LOWER_LIMIT}")
    log.info(SEP)

    scores: List[float]    = []
    good:   List[Document] = []

    for i, doc in enumerate(state["docs"], 1):
        out = doc_eval_chain.invoke({"question": question, "chunk": doc.page_content})
        scores.append(out.score)

        if out.score > UPPER_LIMIT:
            tag = "✅ HIGH  (> UPPER)"
        elif out.score > LOWER_LIMIT:
            tag = "🟡 MID   (> LOWER)"
        else:
            tag = "❌ LOW   (< LOWER)"

        if out.score > LOWER_LIMIT:
            good.append(doc)

        source = doc.metadata.get("source", "unknown")
        page   = doc.metadata.get("page",   "?")
        log.info(
            f"  Chunk [{i:02d}]  score={out.score:.3f}  {tag}\n"
            f"           source={Path(source).name}  page={page}\n"
            f"           reason={out.reason}"
        )

    # ── Summary ───────────────────────────────────────────────
    log.info(SEP)
    log.info("  EVAL SUMMARY")
    log.info(f"  Total chunks evaluated  : {len(scores)}")
    log.info(f"  Chunks > UPPER ({UPPER_LIMIT})   : {sum(s > UPPER_LIMIT for s in scores)}")
    log.info(f"  Chunks > LOWER ({LOWER_LIMIT})   : {sum(s > LOWER_LIMIT for s in scores)}  ← good_docs")
    log.info(f"  Chunks < LOWER ({LOWER_LIMIT})   : {sum(s < LOWER_LIMIT for s in scores)}")
    if scores:
        log.info(f"  Score range             : {min(scores):.3f} – {max(scores):.3f}")
        log.info(f"  Score avg               : {sum(scores)/len(scores):.3f}")
    log.info(f"  Good docs collected     : {len(good)}")

    # ── Verdict ───────────────────────────────────────────────
    if any(s > UPPER_LIMIT for s in scores):
        verdict = "CORRECT"
        reason  = (
            f"At least one chunk scored > {UPPER_LIMIT} "
            "and is sufficient to answer."
        )
    elif len(scores) == 0 or all(s < LOWER_LIMIT for s in scores):
        verdict = "INCORRECT"
        reason  = f"All retrieved chunks scored < {LOWER_LIMIT}."
        good    = []
    else:
        verdict = "AMBIGUOUS"
        reason  = (
            f"No chunk scored > {UPPER_LIMIT}, "
            f"but not all were below {LOWER_LIMIT}. "
            "Mixed relevance signals."
        )

    log.info(SEP)
    log.info(f"  VERDICT ▶  {verdict}")
    log.info(f"  Reason  ▶  {reason}")
    log.info(SEP)

    return {"good_docs": good, "verdict": verdict, "reason": reason}


# ──────────────────────────────────────────────────────────────
# Router — after eval
# ──────────────────────────────────────────────────────────────

def route_after_eval(state: State) -> str:
    verdict = state["verdict"]

    log.info(SEP2)
    log.info("ROUTER  ▶  route_after_eval")
    log.info(SEP2)

    next_node = "refine" if verdict == "CORRECT" else "rewrite_query"

    log.info(f"  Verdict received : {verdict}")
    log.info(f"  Routing to node  : {next_node}")
    if verdict == "CORRECT":
        log.info(f"  ↳ Will refine VectorDB good_docs → generate")
    elif verdict == "INCORRECT":
        log.info(f"  ↳ Will rewrite query → web search → generate (raw web, no refine)")
    else:
        log.info(f"  ↳ Will rewrite query → web search → refine good_docs → generate (refined + web)")
    log.info(SEP)
    return next_node


# ──────────────────────────────────────────────────────────────
# Node 3a — Rewrite Query  (INCORRECT / AMBIGUOUS path)
#
# Uses the LLM to decompose the original question into K
# focused sub-questions that are better suited for web search.
# ──────────────────────────────────────────────────────────────

class RewrittenQueries(BaseModel):
    sub_questions: List[str]


rewrite_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        f"You are an expert at query reformulation for web search.\n"
        f"Given a question that could not be answered from a local knowledge base,\n"
        f"generate between {MIN_QUERIES} and {MAX_QUERIES} distinct, specific sub-questions\n"
        f"that together cover the full scope of the original question.\n"
        f"Each sub-question must be self-contained and search-engine friendly.\n"
        f"Output JSON only."
    ),
    ("human", "Original question: {question}"),
])

rewrite_chain = rewrite_prompt | llm.with_structured_output(RewrittenQueries)


def rewrite_query_node(state: State) -> State:
    question = state["question"]

    log.info(SEP2)
    log.info("NODE  ▶  rewrite_query")
    log.info(SEP2)
    log.info(f"  Original question : {question!r}")
    log.info(f"  Verdict that triggered this path : {state['verdict']}")
    log.info(f"  Reason            : {state['reason']}")
    log.info(f"  Generating {MIN_QUERIES}–{MAX_QUERIES} sub-questions via LLM…")

    out = rewrite_chain.invoke({"question": question})

    # Guard: clamp to [MIN_QUERIES, MAX_QUERIES]
    sub_questions = out.sub_questions[:MAX_QUERIES]
    while len(sub_questions) < MIN_QUERIES:
        sub_questions.append(question)   # fallback: repeat original

    log.info(f"  Sub-questions generated : {len(sub_questions)}")
    for i, q in enumerate(sub_questions, 1):
        log.info(f"    [{i}] {q!r}")
    log.info(SEP)

    return {"sub_questions": sub_questions}


# ──────────────────────────────────────────────────────────────
# Node 3b — Web Search  (INCORRECT / AMBIGUOUS path)
#
# Runs each sub-question through Tavily and collects all
# results as LangChain Documents for the refine node.
# ──────────────────────────────────────────────────────────────

def web_search_node(state: State) -> State:
    sub_questions = state["sub_questions"]

    # Enforce search count within [MIN_QUERIES, MAX_QUERIES]
    sub_questions = sub_questions[:MAX_QUERIES]
    if len(sub_questions) < MIN_QUERIES:
        log.warning(
            f"  Only {len(sub_questions)} sub-question(s) available; "
            f"minimum is {MIN_QUERIES}. Proceeding with what is available."
        )

    log.info(SEP2)
    log.info("NODE  ▶  web_search")
    log.info(SEP2)
    log.info(f"  Running Tavily search for {len(sub_questions)} sub-question(s) "
             f"(limit: {MIN_QUERIES}–{MAX_QUERIES})…")

    web_docs: List[Document] = []

    for i, query in enumerate(sub_questions, 1):
        log.info(f"  [{i}/{len(sub_questions)}] Searching: {query!r}")

        try:
            results = tavily.invoke(query)   # returns List[dict]
        except Exception as exc:
            log.warning(f"  [{i}] Tavily search failed: {exc}")
            continue

        log.info(f"    → {len(results)} result(s) returned by Tavily")

        for j, r in enumerate(results, 1):
            url     = r.get("url",     "")
            title   = r.get("title",   "")
            content = r.get("content", "").strip()

            if not content:
                log.debug(f"      [{j}] Empty content, skipping — url={url}")
                continue

            # Sanitise encoding
            content = content.encode("utf-8", "ignore").decode("utf-8", "ignore")

            doc = Document(
                page_content=content,
                metadata={
                    "source":       url,
                    "title":        title,
                    "sub_question": query,
                    "search_rank":  j,
                },
            )
            web_docs.append(doc)

            preview = content[:100].replace("\n", " ")
            log.info(
                f"      [{j}] title={title!r}  chars={len(content)}\n"
                f"           url={url}\n"
                f"           preview={preview!r}…"
            )

    log.info(SEP)
    log.info(f"  Total web documents collected : {len(web_docs)}")
    log.info(SEP)

    return {"web_docs": web_docs}


# ──────────────────────────────────────────────────────────────
# Router — after web_search
#
#  INCORRECT  → generate   (raw web docs go straight to LLM)
#  AMBIGUOUS  → refine     (good_docs get refined; web docs pass through)
# ──────────────────────────────────────────────────────────────

def route_after_web_search(state: State) -> str:
    verdict = state["verdict"]

    log.info(SEP2)
    log.info("ROUTER  ▶  route_after_web_search")
    log.info(SEP2)
    log.info(f"  Verdict received : {verdict}")

    if verdict == "INCORRECT":
        log.info("  Routing to node  : generate")
        log.info("  ↳ Raw web docs passed directly to LLM (no refine)")
        log.info(SEP)
        return "generate"
    else:  # AMBIGUOUS
        log.info("  Routing to node  : refine")
        log.info("  ↳ Will refine good_docs; web docs will be merged at generate")
        log.info(SEP)
        return "refine"


# ──────────────────────────────────────────────────────────────
# Shared helpers — sentence decomposition + LLM filter
# ──────────────────────────────────────────────────────────────

def decompose_to_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


class KeepOrDrop(BaseModel):
    keep: bool


filter_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a strict relevance filter.\n"
        "Return keep=true ONLY if the sentence directly helps answer the question.\n"
        "Evaluate ONLY the sentence given. Output JSON only."
    ),
    ("human", "Question: {question}\n\nSentence:\n{sentence}"),
])

filter_chain = filter_prompt | llm.with_structured_output(KeepOrDrop)


# ──────────────────────────────────────────────────────────────
# Node 4 — Refine  (VectorDB good_docs only)
#
#  CORRECT path   → called after eval   — refines good_docs
#  AMBIGUOUS path → called after web    — refines good_docs
#                   (web_docs bypass refine and merge at generate)
#
#  Steps: Decompose → LLM filter → Recompose
# ──────────────────────────────────────────────────────────────

def refine(state: State) -> State:
    question  = state["question"]
    verdict   = state.get("verdict", "CORRECT")
    good_docs = state.get("good_docs", [])

    source_docs  = good_docs
    source_label = "VectorDB (good_docs)"

    log.info(SEP2)
    log.info("NODE  ▶  refine")
    log.info(SEP2)
    log.info(f"  Verdict path       : {verdict}")
    log.info(f"  Document source    : {source_label}")
    log.info(f"  Documents entering : {len(source_docs)}")

    for i, doc in enumerate(source_docs, 1):
        src   = doc.metadata.get("source", "unknown")
        page  = doc.metadata.get("page",   "")
        title = doc.metadata.get("title",  "")
        label = title if title else Path(src).name
        extra = f"  page={page}" if page else ""
        log.info(f"  [{i:02d}] {label}{extra}  chars={len(doc.page_content)}")

    # ── Step 1: Decompose into sentences ──────────────────────
    context = "\n\n".join(d.page_content for d in source_docs).strip()
    log.info(f"  Combined context length : {len(context)} chars")
    log.info(SEP)

    strips = decompose_to_sentences(context)
    log.info(f"  Step 1 — Decompose: {len(strips)} sentences extracted")
    log.info(SEP)

    # ── Step 2: LLM filter ────────────────────────────────────
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
    log.info("  Step 2 Summary:")
    log.info(f"    Sentences total   : {len(strips)}")
    log.info(f"    Sentences KEPT    : {len(kept)}")
    log.info(f"    Sentences DROPPED : {len(dropped)}")
    keep_pct = (len(kept) / len(strips) * 100) if strips else 0
    log.info(f"    Keep rate         : {keep_pct:.1f}%")

    # ── Step 3: Recompose ─────────────────────────────────────
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
# Node 5 — Generate
# ──────────────────────────────────────────────────────────────

generate_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a helpful ML tutor.\n"
        "Answer the question using ONLY the provided context.\n"
        "If the context is empty or insufficient, say: "
        "'I don't know based on the available sources.'\n"
        "Be clear, concise, and accurate.\n"
        "Always respond in English, regardless of the language of the context.",
    ),
    ("human", "Question: {question}\n\nContext:\n{context}"),
])


def generate(state: State) -> dict:
    log.info(SEP2)
    log.info("NODE  ▶  generate")
    log.info(SEP2)

    verdict       = state.get("verdict", "?")
    refined       = state.get("refined_context", "")
    web_docs      = state.get("web_docs", [])

    # ── Build context according to verdict path ───────────────
    if verdict == "CORRECT":
        # Refined VectorDB good_docs only
        context    = refined
        answer_src = "VectorDB (refined)"
        log.info("  Context source : VectorDB refined good_docs")

    elif verdict == "INCORRECT":
        # Raw web docs only — no refine was run
        context    = "\n\n".join(d.page_content for d in web_docs).strip()
        answer_src = "Web (Tavily) — raw"
        log.info(f"  Context source : raw web docs ({len(web_docs)} docs, no refine)")

    else:  # AMBIGUOUS
        # Refined good_docs  +  raw web docs merged together
        web_context = "\n\n".join(d.page_content for d in web_docs).strip()
        parts       = [p for p in [refined, web_context] if p]
        context     = "\n\n".join(parts)
        answer_src  = "VectorDB (refined) + Web (Tavily) — raw"
        log.info(
            f"  Context source : refined good_docs ({len(refined)} chars) "
            f"+ raw web docs ({len(web_docs)} docs)"
        )

    log.info(f"  Verdict path                  : {verdict}")
    log.info(f"  Answer source                 : {answer_src}")
    log.info(f"  Total context length          : {len(context)} chars")
    log.info(f"  Refined sentence count        : {len(state.get('kept_strips', []))}")

    if not context.strip():
        log.warning("  ⚠️  Context is EMPTY — LLM will say 'I don't know'.")

    log.info("  Calling LLM to generate answer…")
    out    = (generate_prompt | llm).invoke(
        {"question": state["question"], "context": context}
    )

    # Strip <think>…</think> reasoning traces (e.g. qwen3 leaks them into output)
    answer = re.sub(r"<think>.*?</think>", "", out.content, flags=re.DOTALL).strip()

    if len(answer) != len(out.content):
        log.info(f"  <think> block stripped  : {len(out.content) - len(answer)} chars removed")

    log.info(f"  Answer length  : {len(answer)} chars")
    log.info(f"  Answer preview : {answer[:200].replace(chr(10), ' ')!r}…")
    log.info(SEP)

    return {"answer": answer}


# ──────────────────────────────────────────────────────────────
# Build graph
# ──────────────────────────────────────────────────────────────
#
#   START
#     │
#     ▼
#   retrieve
#     │
#     ▼
#   eval
#     │
#     ├─── CORRECT ──────────────────────────────────────────┐
#     │                                                      │
#     └─── INCORRECT / AMBIGUOUS                             │
#            │                                              ▼
#            ▼                                           refine ◄──────────────┐
#        rewrite_query                               (good_docs only)          │
#            │                                              │                  │
#            ▼                                              ▼                  │
#        web_search                                      generate              │
#            │                                              │                  │
#            ├─── INCORRECT ──────────────────────────────► │                  │
#            │         (raw web → LLM, no refine)           │                  │
#            │                                              │                  │
#            └─── AMBIGUOUS ────────────────────────────────┘──────────────────┘
#                      (good_docs → refine, web → generate merged)
#                                              │
#                                             END

graph = StateGraph(State)

graph.add_node("retrieve",      retrieve_node)
graph.add_node("eval",          eval_each_doc_node)
graph.add_node("rewrite_query", rewrite_query_node)
graph.add_node("web_search",    web_search_node)
graph.add_node("refine",        refine)
graph.add_node("generate",      generate)

graph.add_edge(START,           "retrieve")
graph.add_edge("retrieve",      "eval")
graph.add_conditional_edges(
    "eval",
    route_after_eval,
    {
        "refine":        "refine",        # CORRECT path
        "rewrite_query": "rewrite_query", # INCORRECT / AMBIGUOUS path
    },
)
graph.add_edge("rewrite_query", "web_search")
graph.add_conditional_edges(
    "web_search",
    route_after_web_search,
    {
        "generate": "generate",  # INCORRECT — raw web straight to LLM
        "refine":   "refine",    # AMBIGUOUS — refine good_docs first
    },
)
graph.add_edge("refine",    "generate")
graph.add_edge("generate",  END)

app = graph.compile()
log.info("CRAG06 graph compiled and ready.")


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def run():
    log.info("Saving RAG graph flow visualization to PNG…")
    png_bytes = app.get_graph().draw_mermaid_png()
    Path("crag06-refine.png").write_bytes(png_bytes)
    log.info("Graph flow saved as 'crag06-refine.png'")

    question = "What is Principal Component Analysis (PCA) and how does it work?"
    log.info(f"Running query: {question!r}")

    res = app.invoke({
        "question":        question,
        "docs":            [],
        "good_docs":       [],
        "verdict":         "",
        "reason":          "",
        "sub_questions":   [],
        "web_docs":        [],
        "strips":          [],
        "kept_strips":     [],
        "refined_context": "",
        "answer":          "",
    })

    log.info("Query complete.")

    # ════════════════════════════════════════════════════════════
    # Final printed report
    # ════════════════════════════════════════════════════════════
    docs          = res.get("docs",          [])
    good_docs     = res.get("good_docs",     [])
    verdict       = res.get("verdict",       "N/A")
    reason        = res.get("reason",        "N/A")
    sub_questions = res.get("sub_questions", [])
    web_docs      = res.get("web_docs",      [])
    strips        = res.get("strips",        [])
    kept          = res.get("kept_strips",   [])
    keep_pct      = (len(kept) / len(strips) * 100) if strips else 0
    if verdict == "CORRECT":
        answer_src = "VectorDB (refined)"
    elif verdict == "INCORRECT":
        answer_src = "Web (Tavily) — raw"
    else:
        answer_src = "VectorDB (refined) + Web (Tavily) — raw"

    # ── Pipeline summary ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("  PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  Question              : {question}")
    print(f"  VectorDB chunks       : {len(docs)}")
    print(f"  Good docs (>LOWER)    : {len(good_docs)}")
    print(f"  Verdict               : {verdict}")
    print(f"  Reason                : {reason}")
    print(f"  Answer source         : {answer_src}")
    if sub_questions:
        print(f"  Sub-questions created : {len(sub_questions)}")
        print(f"  Web docs fetched      : {len(web_docs)}")
    print(f"  Sentences decomposed  : {len(strips)}")
    print(f"  Sentences kept        : {len(kept)}  ({keep_pct:.1f}%)")

    # ── VectorDB chunks ───────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  VECTORDB RETRIEVED CHUNKS  ({len(docs)} total)")
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
    print(f"  VERDICT : {verdict}")
    print(f"  {reason}")
    print("=" * 60)

    # ── Web search path details (only shown when triggered) ───
    if sub_questions:
        print("\n" + "=" * 60)
        print(f"  SUB-QUESTIONS GENERATED  ({len(sub_questions)})")
        print("=" * 60)
        for i, q in enumerate(sub_questions, 1):
            print(f"  [{i}] {q}")

        print("\n" + "=" * 60)
        print(f"  WEB DOCUMENTS FETCHED  ({len(web_docs)} total)")
        print("=" * 60)
        for i, doc in enumerate(web_docs, 1):
            url   = doc.metadata.get("source",       "")
            title = doc.metadata.get("title",         "")
            subq  = doc.metadata.get("sub_question",  "")
            rank  = doc.metadata.get("search_rank",   "")
            print(f"\n--- Web Doc {i:02d} | rank={rank} | chars={len(doc.page_content)}")
            print(f"    sub_q : {subq}")
            print(f"    title : {title}")
            print(f"    url   : {url}")
            print(doc.page_content)

    # ── Kept sentences ────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  KEPT SENTENCES AFTER REFINE  ({len(kept)} of {len(strips)}, {keep_pct:.1f}%)")
    print("=" * 60)
    for i, sentence in enumerate(kept, 1):
        print(f"\n  [{i:03d}] {sentence}")

    # ── Final answer ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  FINAL ANSWER  [source: {answer_src}]")
    print("=" * 60)
    print(res["answer"])
    print("=" * 60)

    log.info("Done.")


if __name__ == "__main__":
    run()
