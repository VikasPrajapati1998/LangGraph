# blog_agents.py
# LangGraph HITL workflow — BlogWriting05.py adapted for FastAPI + Human Approval

from __future__ import annotations

import os
import re
import time
import logging
import operator
from datetime import datetime
from pathlib import Path
from typing import TypedDict, List, Annotated, Literal, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, Field
from dotenv import load_dotenv, find_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, interrupt
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_tavily import TavilySearch

from google import genai
import google.genai.types as types

# Gemini client — created once at module level to avoid per-call init overhead
_GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
_gemini_client  = genai.Client(api_key=_GOOGLE_API_KEY) if _GOOGLE_API_KEY else None

load_dotenv(find_dotenv())

# ──────────────────────────────────────────────────────────────
# Logger
# ──────────────────────────────────────────────────────────────

def setup_logger() -> logging.Logger:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = logs_dir / f"log_{timestamp}.log"

    logger = logging.getLogger("BlogWriter")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(log_filename, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.info(f"Logger initialised. Log file: {log_filename}")
    return logger

logger = setup_logger()


# ──────────────────────────────────────────────────────────────
# LLMs
# ──────────────────────────────────────────────────────────────

logger.debug("[SETUP] Initialising LLMs...")
blog_llm     = ChatOllama(model="llama3.2:3b", temperature=0.5)
decision_llm = ChatOllama(model="llama3.2:3b", temperature=0.7)
logger.debug("[SETUP] LLMs ready.")


# ──────────────────────────────────────────────────────────────
# Pydantic Schemas  (unchanged from BlogWriting05.py)
# ──────────────────────────────────────────────────────────────

class Task(BaseModel):
    id: int
    title: str
    goal: str = Field(..., description="One sentence describing the section goal.")
    bullets: List[str] = Field(..., min_length=3, max_length=5)
    target_words: int
    tags: List[str]           = Field(default_factory=list)
    requires_research: bool   = False
    requires_citations: bool  = False
    requires_code: bool       = False


class Plan(BaseModel):
    blog_title: str
    audience: str
    tone: str
    blog_kind: Literal["explainer","tutorial","news_roundup","comparison","system_design"] = "explainer"
    constraints: List[str]    = Field(default_factory=list)
    tasks: List[Task]         = Field(default_factory=list)


class EvidenceItem(BaseModel):
    title: str
    url: str
    published_at: Optional[str] = None
    snippet: Optional[str]      = None
    source: Optional[str]       = None


class RouterDecision(BaseModel):
    needs_research: bool = False
    mode: Literal["closed_book","hybrid","open_book"] = "closed_book"
    queries: List[str] = Field(default_factory=list)


class EvidencePack(BaseModel):
    evidence: List[EvidenceItem] = Field(default_factory=list)


class ImageSpec(BaseModel):
    placeholder: str = Field(
        ...,
        description=(
            "Exact placeholder token. MUST be one of: "
            "[[IMAGE_1]], [[IMAGE_2]], [[IMAGE_3]]."
        )
    )
    insert_after_heading: str = Field(
        ...,
        description=(
            "The exact ## heading text (without '## ') after whose first "
            "paragraph this image is inserted."
        )
    )
    filename: str
    alt: str
    caption: str
    prompt: str
    size: Literal["1024x1024","1024x1536","1536x1024"] = "1024x1024"
    quality: Literal["low","medium","high"]            = "medium"


class GlobalImagePlan(BaseModel):
    images: List[ImageSpec] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────────

class State(TypedDict):
    topic: str

    # routing / research
    mode: str
    needs_research: bool
    queries: List[str]
    evidence: List[EvidenceItem]
    plan: Optional[Plan]

    # workers
    sections: Annotated[List[tuple[int, str]], operator.add]

    # reducer / image
    merged_md: str
    md_with_placeholders: str
    image_specs: List[dict]
    final: str

    # HITL fields
    approval_status: Optional[str]   # "approved" | "rejected"
    rejection_reason: Optional[str]


# ──────────────────────────────────────────────────────────────
# Prompts  (unchanged from BlogWriting05.py)
# ──────────────────────────────────────────────────────────────

ROUTER_SYSTEM = """You are a routing module for a technical blog planner.

Decide whether web research is needed BEFORE planning.

Modes:
- closed_book (needs_research=false):
  Evergreen topic where correctness does not depend on recent facts.
- hybrid (needs_research=true):
  Mostly evergreen but needs up-to-date examples/tools/models.
- open_book (needs_research=true):
  Mostly volatile: weekly roundups, "this week", "latest", ranking, pricing.

If needs_research=true:
- Output 3-10 high-signal queries.
- Queries should be scoped and specific.
- If user asked for "last week/this week/latest", reflect that in the queries.
"""

RESEARCH_SYSTEM = """You are a research synthesizer for technical writing.

Given raw web search results, produce a deduplicated list of EvidenceItem objects.

Rules:
- Only include items with a non-empty url.
- Prefer relevant + authoritative sources.
- Keep published_at as YYYY-MM-DD if present, else null.
- Keep snippets short.
- Deduplicate by URL.
"""

ORCH_SYSTEM = """You are a senior technical writer and developer advocate.
Your job is to produce a highly actionable outline for a technical blog post.

Hard requirements:
- Create 5-9 sections (tasks) suitable for the topic and audience.
- Each task must include:
  1) goal (1 sentence)
  2) 3-6 bullets that are concrete, specific, and non-overlapping
  3) target word count (120-550)
- You MUST populate the tasks array. An empty tasks list is invalid.

Quality bar:
- Assume the reader is a developer; use correct terminology.
- Bullets must be actionable: build/compare/measure/verify/debug.
- Ensure the overall plan includes at least 2 of these somewhere:
  * minimal code sketch / MWE (set requires_code=True for that section)
  * edge cases / failure modes
  * performance / cost considerations
  * security / privacy considerations (if relevant)
  * debugging / observability tips

Grounding rules:
- Mode closed_book: keep it evergreen; do not depend on evidence.
- Mode hybrid:
  - Use evidence for up-to-date examples (models/tools/releases) in bullets.
  - Mark sections using fresh info as requires_research=True and requires_citations=True.
- Mode open_book:
  - Set blog_kind = "news_roundup".
  - Every section is about summarizing events + implications.
  - DO NOT include tutorial/how-to sections unless user explicitly asked for that.
  - If evidence is empty or insufficient, create a plan that transparently says "insufficient sources".

Example of a valid filled output (use this structure, NOT these exact values):
{
  "blog_title": "Understanding Gradient Descent",
  "audience": "developers",
  "tone": "informative",
  "blog_kind": "explainer",
  "constraints": [],
  "tasks": [
    {
      "id": 1,
      "title": "What is Gradient Descent",
      "goal": "Explain what gradient descent is and why it matters for training ML models.",
      "bullets": [
        "Define the loss surface and what it means to minimize it",
        "Explain the role of the gradient as a direction of steepest ascent",
        "Describe the update rule: theta = theta - lr * grad"
      ],
      "target_words": 200,
      "tags": ["fundamentals"],
      "requires_research": false,
      "requires_citations": false,
      "requires_code": false
    }
  ]
}

Output must strictly match the Plan schema.
"""

WORKER_SYSTEM = """You are a senior technical writer and developer advocate.
Write ONE section of a technical blog post in Markdown.

Hard constraints:
- Follow the provided Goal and cover ALL Bullets in order.
- Stay close to Target words (±15%).
- Output ONLY the section content in Markdown (no blog title H1, no extra commentary).
- Start with a '## <Section Title>' heading.

Scope guard:
- If blog_kind == "news_roundup": focus on summarizing events and implications.

Grounding policy:
- If mode == open_book:
  - Do NOT introduce any specific claim unless supported by a provided Evidence URL.
  - For each event claim, attach a source as a Markdown link: ([Source](URL)).
- If requires_citations == true:
  - For outside-world claims, cite Evidence URLs the same way.

Code:
- If requires_code == true, include at least one minimal, correct code snippet.

Style:
- Short paragraphs, bullets where helpful, code fences for code.
- Avoid fluff/marketing. Be precise and implementation-oriented.
"""

DECIDE_IMAGE_SYSTEM = """You are an expert technical editor.
Decide if images/diagrams would materially improve understanding of THIS blog.

Rules:
- Max 3 images total.
- Only include images that add real value: diagrams, flows, comparisons, architecture.
- Avoid decorative images.
- If no images are needed, return images=[].

For each image you want to add, output an ImageSpec with:

1. placeholder — MUST be EXACTLY one of (no extra text, no colons, nothing else):
     [[IMAGE_1]]
     [[IMAGE_2]]
     [[IMAGE_3]]

2. insert_after_heading — the exact text of the ## section heading (without "## ")
   after which this image should appear.

3. filename  — e.g. "qkv_attention_flow.png"
4. alt       — short alt text
5. caption   — one-sentence caption
6. prompt    — detailed image generation prompt

DO NOT return the blog markdown. Only return the GlobalImagePlan JSON.
"""


# ──────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────

_PLACEHOLDER_RE = re.compile(r'\[{1,2}IMAGE_(\d+)[^\]]*\]{1,2}')


def _sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[\\/:*?"<>|]', '-', name)
    sanitized = re.sub(r'-+', '-', sanitized).strip(' -')
    return sanitized


def _tavily_search(query: str, max_results: int = 6) -> List[dict]:
    logger.debug(f"[RESEARCH] Tavily search — query='{query}'")
    tool = TavilySearch(max_results=max_results)
    try:
        response = tool.invoke({"query": query})
    except Exception as e:
        logger.error(f"[RESEARCH] Tavily search failed for query='{query}': {e}", exc_info=True)
        return []

    if isinstance(response, dict):
        results = response.get("results") or []
    elif isinstance(response, list):
        results = response
    else:
        logger.warning(f"[RESEARCH] Unexpected Tavily response type: {type(response)}")
        results = []

    return [
        {
            "title":        r.get("title") or "",
            "url":          r.get("url") or "",
            "snippet":      r.get("content") or r.get("snippet") or "",
            "published_at": r.get("published_date") or r.get("published_at"),
            "source":       r.get("source"),
        }
        for r in results
    ]


def _inject_placeholders(merged_md: str, images: list) -> str:
    """Insert [[IMAGE_N]] tokens into merged_md at the correct heading positions."""

    def _build_heading_index(lines: list) -> dict:
        return {
            line[3:].strip(): i
            for i, line in enumerate(lines)
            if line.startswith("## ")
        }

    ordered = sorted(
        images,
        key=lambda x: int(_PLACEHOLDER_RE.search(x.placeholder).group(1))
        if _PLACEHOLDER_RE.search(x.placeholder) else 999
    )

    result = merged_md.split("\n")

    for img in ordered:
        target_heading = img.insert_after_heading.strip()
        if target_heading.startswith("## "):
            target_heading = target_heading[3:].strip()

        canonical = (
            f"[[IMAGE_{_PLACEHOLDER_RE.search(img.placeholder).group(1)}]]"
            if _PLACEHOLDER_RE.search(img.placeholder) else img.placeholder
        )

        heading_index = _build_heading_index(result)
        idx = heading_index.get(target_heading)
        if idx is None:
            for h, i in heading_index.items():
                if h.lower() == target_heading.lower():
                    idx = i
                    break

        if idx is None:
            logger.warning(f"[IMAGES] Could not find heading '{target_heading}'. Appending at end.")
            result.append("")
            result.append(canonical)
            continue

        insert_at = idx + 1
        while insert_at < len(result) and result[insert_at].strip():
            insert_at += 1

        result.insert(insert_at, canonical)
        result.insert(insert_at, "")
        logger.debug(f"[IMAGES] Injected '{canonical}' after heading '{target_heading}'")

    return "\n".join(result)


def _gemini_generate_image_bytes(prompt: str) -> bytes:
    IMAGE_MODEL = "gemini-2.5-flash-image"
    if _gemini_client is None:
        raise RuntimeError("GOOGLE_API_KEY is not set.")

    response = _gemini_client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_ONLY_HIGH",
                )
            ],
        ),
    )

    parts = getattr(response, "parts", None)
    if not parts and getattr(response, "candidates", None):
        try:
            parts = response.candidates[0].content.parts
        except Exception:
            parts = None

    if not parts:
        raise RuntimeError("No image content returned (safety/quota/SDK change).")

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            return inline.data

    raise RuntimeError("No inline image bytes found in response.")


# ──────────────────────────────────────────────────────────────
# Graph Nodes
# ──────────────────────────────────────────────────────────────

def router_node(state: State) -> dict:
    topic = state["topic"]
    logger.info(f"[ROUTER] ── Entering router node ──────────────────────────")
    logger.debug(f"[ROUTER]   Topic: '{topic}'")

    decider = decision_llm.with_structured_output(RouterDecision)
    try:
        decision = decider.invoke([
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=f"Topic: {topic}"),
        ])
    except Exception as e:
        logger.error(f"[ROUTER] LLM invocation failed: {e}", exc_info=True)
        raise

    needs_research = decision.needs_research or bool(decision.queries)
    logger.info(f"[ROUTER]   Decision: mode='{decision.mode}' | needs_research={needs_research}")
    logger.debug(f"[ROUTER]   Queries ({len(decision.queries)}): {decision.queries}")
    logger.info(f"[ROUTER] ── Router node complete ────────────────────────────")

    return {
        "needs_research": needs_research,
        "mode":           decision.mode,
        "queries":        decision.queries,
    }


def route_next(state: State) -> str:
    next_node = "research" if state["needs_research"] else "orchestrator"
    logger.info(f"[ROUTER] Routing → '{next_node}'")
    return next_node


def research_node(state: State) -> dict:
    queries    = state.get("queries", []) or []
    logger.info(f"[RESEARCH] ── Entering research node ({len(queries)} queries) ──")

    raw_results: List[dict] = []
    search_start = datetime.now()

    with ThreadPoolExecutor(max_workers=min(len(queries), 10)) as pool:
        future_to_q = {pool.submit(_tavily_search, q): q for q in queries}
        for future in as_completed(future_to_q):
            q = future_to_q[future]
            try:
                results = future.result()
                raw_results.extend(results)
                logger.debug(f"[RESEARCH] Query done: '{q}' → {len(results)} results | cumulative: {len(raw_results)}")
            except Exception as e:
                logger.error(f"[RESEARCH] Query FAILED: '{q}': {e}", exc_info=True)

    elapsed = (datetime.now() - search_start).total_seconds()
    logger.info(f"[RESEARCH] Total raw results: {len(raw_results)} ({elapsed:.2f}s)")

    if not raw_results:
        logger.warning("[RESEARCH] No raw results — returning empty evidence.")
        return {"evidence": []}

    extractor = blog_llm.with_structured_output(EvidencePack)
    try:
        pack = extractor.invoke([
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(content=f"Raw results:\n{raw_results}"),
        ])
    except Exception as e:
        logger.error(f"[RESEARCH] LLM evidence extraction failed: {e}", exc_info=True)
        raise

    dedup = {e.url: e for e in pack.evidence if e.url}
    logger.info(f"[RESEARCH] Evidence after deduplication: {len(dedup)} items")
    if len(dedup) == 0:
        logger.warning(f"[RESEARCH] All {len(raw_results)} raw results discarded. Closed-book fallback.")
    logger.info(f"[RESEARCH] ── Research node complete ───────────────────────────")

    return {"evidence": list(dedup.values())}


def orchestrator_node(state: State) -> dict:
    logger.info(f"[ORCH] ── Entering orchestrator node ──────────────────────")
    planner  = blog_llm.with_structured_output(Plan)
    evidence = state.get("evidence", [])
    mode     = state.get("mode", "closed_book")

    # Build once — avoids repeated serialisation on every retry attempt
    evidence_dump = [e.model_dump() for e in evidence][:16]

    messages = [
        SystemMessage(content=ORCH_SYSTEM),
        HumanMessage(content=(
            f"Topic: {state['topic']}\n"
            f"Mode: {mode}\n\n"
            f"Evidence (ONLY use for fresh claims; may be empty):\n"
            f"{evidence_dump}"
        )),
    ]

    plan = None
    for attempt in range(1, 4):
        logger.info(f"[ORCH] Planning attempt {attempt}/3...")
        try:
            plan = planner.invoke(messages)
        except Exception as e:
            logger.error(f"[ORCH] LLM failed on attempt {attempt}: {e}", exc_info=True)
            if attempt == 3:
                raise
            continue

        if plan and plan.tasks:
            logger.info(f"[ORCH] Plan accepted — {len(plan.tasks)} tasks | title: '{plan.blog_title}'")
            break

        logger.warning(f"[ORCH] Attempt {attempt} returned empty tasks. Retrying...")
        messages = [
            SystemMessage(content=ORCH_SYSTEM),
            HumanMessage(content=(
                f"Topic: {state['topic']}\nMode: {mode}\n\n"
                "IMPORTANT: You returned an empty tasks list. This is invalid.\n"
                "You MUST include at least 5 task objects in the tasks array.\n\n"
                f"Evidence:\n{evidence_dump}"
            )),
        ]

    if not (plan and plan.tasks):
        logger.error("[ORCH] All 3 attempts returned empty tasks.")

    logger.info(f"[ORCH] ── Orchestrator node complete ─────────────────────────")
    return {"plan": plan}


def sub_worker(state: State):
    logger.info(f"[DISPATCHER] Dispatching workers...")
    if not state.get("plan") or not state["plan"].tasks:
        raise ValueError("Orchestrator produced no tasks. Cannot generate blog sections.")

    return [
        Send("worker", {
            "task":     task.model_dump(),
            "topic":    state["topic"],
            "mode":     state["mode"],
            "plan":     state["plan"].model_dump(),
            "evidence": [e.model_dump() for e in state.get("evidence", [])],
        })
        for task in state["plan"].tasks
    ]


def worker_node(payload: dict) -> dict:
    task     = Task(**payload["task"])
    plan     = Plan(**payload["plan"])
    evidence = [EvidenceItem(**e) for e in payload.get("evidence", [])]
    topic    = payload["topic"]
    mode     = payload.get("mode", "closed_book")

    logger.info(f"[WORKER] ── Task {task.id}: '{task.title}'")

    bullets_text  = "\n- " + "\n- ".join(task.bullets)
    evidence_text = "\n".join(
        f"- {e.title} | {e.url} | {e.published_at or 'date:unknown'}"
        for e in evidence[:20]
    ) if evidence else ""

    worker_start = datetime.now()
    try:
        section_md = blog_llm.invoke([
            SystemMessage(content=WORKER_SYSTEM),
            HumanMessage(content=(
                f"Blog title: {plan.blog_title}\nAudience: {plan.audience}\n"
                f"Tone: {plan.tone}\nBlog kind: {plan.blog_kind}\n"
                f"Constraints: {plan.constraints}\nTopic: {topic}\nMode: {mode}\n\n"
                f"Section title: {task.title}\nGoal: {task.goal}\n"
                f"Target words: {task.target_words}\nTags: {task.tags}\n"
                f"requires_research: {task.requires_research}\n"
                f"requires_citations: {task.requires_citations}\n"
                f"requires_code: {task.requires_code}\n"
                f"Bullets:{bullets_text}\n\n"
                f"Evidence (ONLY use these URLs when citing):\n{evidence_text}\n"
            ))
        ]).content.strip()
    except Exception as e:
        logger.error(f"[WORKER] Task {task.id} LLM failed: {e}", exc_info=True)
        raise

    elapsed      = (datetime.now() - worker_start).total_seconds()
    word_count   = len(section_md.split())
    deviation    = abs(word_count - task.target_words) / max(task.target_words, 1) * 100
    logger.info(f"[WORKER] Task {task.id} done — ~{word_count}w (dev={deviation:.1f}%, {elapsed:.2f}s)")
    if deviation > 20:
        logger.warning(f"[WORKER] Task {task.id} word count deviation > 20%: got {word_count}, target {task.target_words}")

    return {"sections": [(task.id, section_md)]}


def merge_content(state: State) -> dict:
    logger.info(f"[MERGE] ── Entering merge_content node ──────────────────────")
    plan     = state["plan"]
    sections = state.get("sections", [])

    # Deduplicate by task id before merging
    seen: dict = {}
    for task_id, md in sections:
        if task_id not in seen:
            seen[task_id] = md

    ordered   = [md for _, md in sorted(seen.items())]
    body      = "\n\n".join(ordered).strip()
    merged_md = f"# {plan.blog_title}\n\n{body}\n"

    logger.info(f"[MERGE] Blog title: '{plan.blog_title}' | ~{len(merged_md.split())} words")
    logger.info(f"[MERGE] ── merge_content node complete ───────────────────────")
    return {"merged_md": merged_md}


# ──────────────────────────────────────────────────────────────
# HITL Checkpoint Node
# ──────────────────────────────────────────────────────────────

def human_approval_node(state: State) -> dict:
    """
    Workflow pauses here via LangGraph interrupt().
    The FastAPI endpoint resumes it by calling:
        workflow.update_state(config, {"approval_status": "approved"/"rejected",
                                       "rejection_reason": "..."}, as_node="human_approval")
    """
    logger.info("[HITL] ── Workflow pausing for human approval ──────────────")
    logger.info(f"[HITL]   Blog title : '{state['plan'].blog_title if state.get('plan') else 'N/A'}'")
    logger.info(f"[HITL]   Content length: {len(state.get('merged_md', ''))} chars")

    # Pause workflow here — FastAPI will resume after human decision
    interrupt("Waiting for human approval")

    # Execution resumes here after update_state() is called externally
    logger.info(f"[HITL]   Resumed — approval_status='{state.get('approval_status')}'")
    logger.info("[HITL] ── human_approval_node complete ──────────────────────")
    return {}


def route_after_approval(state: State) -> str:
    status = state.get("approval_status", "").lower()
    logger.info(f"[HITL] Routing after approval — status='{status}'")
    if status == "approved":
        return "finalize_approved"
    return "handle_rejection"


# ──────────────────────────────────────────────────────────────
# Image Pipeline Nodes  (decide → generate)
# ──────────────────────────────────────────────────────────────

def decide_images(state: State) -> dict:
    logger.info(f"[IMAGES] ── Entering decide_images node ──────────────────────")
    planner   = decision_llm.with_structured_output(GlobalImagePlan)
    merged_md = state["merged_md"]
    plan      = state["plan"]
    assert plan is not None

    headings      = [l for l in merged_md.split("\n") if l.startswith("## ")]
    headings_block = "\n".join(headings)
    logger.debug(f"[IMAGES] Sections found: {len(headings)}")

    try:
        image_plan = planner.invoke([
            SystemMessage(content=DECIDE_IMAGE_SYSTEM),
            HumanMessage(content=(
                f"Blog kind: {plan.blog_kind}\nTopic: {state['topic']}\n\n"
                f"Section headings available for image placement:\n{headings_block}\n\n"
                "Decide which sections need images and fill in the ImageSpec list."
            )),
        ])
    except Exception as e:
        logger.error(f"[IMAGES] LLM failed in decide_images: {e}", exc_info=True)
        raise

    # Normalise placeholders
    fixed_images = []
    for img in image_plan.images:
        m         = _PLACEHOLDER_RE.search(img.placeholder)
        canonical = f"[[IMAGE_{m.group(1)}]]" if m else img.placeholder
        if canonical != img.placeholder:
            logger.warning(f"[IMAGES] Non-canonical placeholder '{img.placeholder}' → '{canonical}'")
            img = img.model_copy(update={"placeholder": canonical})
        fixed_images.append(img)

    logger.info(f"[IMAGES] Images planned: {len(fixed_images)}")

    if not fixed_images:
        md_with_placeholders = merged_md
    else:
        md_with_placeholders = _inject_placeholders(merged_md, fixed_images)

    logger.info(f"[IMAGES] ── decide_images node complete ────────────────────────")
    return {
        "md_with_placeholders": md_with_placeholders,
        "image_specs":          [img.model_dump() for img in fixed_images],
    }


def generate_and_place_images(state: State) -> dict:
    logger.info(f"[IMGPLACE] ── Entering generate_and_place_images node ──────────")
    plan       = state["plan"]
    md         = state.get("md_with_placeholders") or state["merged_md"]
    image_specs = state.get("image_specs", []) or []

    output_dir = Path("output")
    images_dir = output_dir / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    if not image_specs:
        out_md_path = output_dir / f"{_sanitize_filename(plan.blog_title)}.md"
        out_md_path.write_text(md, encoding="utf-8")
        logger.info(f"[IMGPLACE] No images. Written: '{out_md_path}'")
        return {"final": md}

    MAX_RETRIES     = 3
    RETRY_BACKOFF   = [2, 5, 10]

    def _generate_one(spec: dict, idx: int) -> dict:
        placeholder = spec["placeholder"]
        filename    = spec["filename"]
        out_path    = images_dir / filename

        logger.info(f"[IMGPLACE] Processing image {idx}: placeholder='{placeholder}' | file='{filename}'")

        if out_path.exists():
            logger.info(f"[IMGPLACE] Cached — skipping generation: '{out_path}'")
            return {"spec": spec, "status": "cached"}

        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                wait = RETRY_BACKOFF[attempt - 2]
                logger.warning(f"[IMGPLACE] Image {idx} retry {attempt}/{MAX_RETRIES} — waiting {wait}s...")
                time.sleep(wait)

            t0 = datetime.now()
            try:
                img_bytes = _gemini_generate_image_bytes(spec["prompt"])
                out_path.write_bytes(img_bytes)
                elapsed = (datetime.now() - t0).total_seconds()
                logger.info(f"[IMGPLACE] Image {idx} saved: '{out_path}' ({len(img_bytes)}b, {elapsed:.2f}s, attempt {attempt})")
                return {"spec": spec, "status": "success"}
            except Exception as e:
                last_exc = e
                logger.warning(f"[IMGPLACE] Image {idx} attempt {attempt}/{MAX_RETRIES} FAILED: {e}")

        logger.error(f"[IMGPLACE] Image {idx} PERMANENTLY FAILED after {MAX_RETRIES} attempts. Last: {last_exc}", exc_info=True)
        return {"spec": spec, "status": "failed", "error": last_exc}

    results_map: dict = {}
    t_all = datetime.now()
    with ThreadPoolExecutor(max_workers=min(len(image_specs), 3)) as pool:
        future_to_spec = {pool.submit(_generate_one, spec, i): spec
                          for i, spec in enumerate(image_specs, start=1)}
        for future in as_completed(future_to_spec):
            res = future.result()
            results_map[res["spec"]["placeholder"]] = res

    logger.info(f"[IMGPLACE] All futures done in {(datetime.now()-t_all).total_seconds():.2f}s")

    success_count = failure_count = cached_count = 0
    for spec in image_specs:
        placeholder = spec["placeholder"]
        filename    = spec["filename"]
        res         = results_map.get(placeholder, {})
        status      = res.get("status", "failed")

        if status in ("cached", "success"):
            if status == "cached":
                cached_count += 1
            else:
                success_count += 1
            img_md = f"![{spec['alt']}](images/{filename})\n*{spec['caption']}*"
            md = md.replace(placeholder, img_md)
        else:
            failure_count += 1
            err = res.get("error", "unknown error")
            md  = md.replace(placeholder, (
                f"> **[IMAGE GENERATION FAILED]** {spec.get('caption','')}\n>\n"
                f"> **Alt:** {spec.get('alt','')}\n>\n"
                f"> **Prompt:** {spec.get('prompt','')}\n\n"
                f"> **Error:** {err}\n"
            ))

    logger.info(f"[IMGPLACE] Summary — success={success_count} | failed={failure_count} | cached={cached_count}")

    out_md_path = output_dir / f"{_sanitize_filename(plan.blog_title)}.md"
    out_md_path.write_text(md, encoding="utf-8")
    logger.info(f"[IMGPLACE] Written: '{out_md_path}' (~{len(md.split())} words)")
    logger.info(f"[IMGPLACE] ── generate_and_place_images complete ───────────────")
    return {"final": md}


# ──────────────────────────────────────────────────────────────
# HITL Terminal Nodes
# ──────────────────────────────────────────────────────────────

def finalize_approved(state: State) -> dict:
    """Called after human approves — runs image pipeline then marks complete."""
    logger.info("[HITL] ── finalize_approved — blog approved by human ────────")
    # The actual image generation is handled by the reducer subgraph
    # which runs decide_images → generate_and_place_images.
    # This node just logs the approval.
    logger.info(f"[HITL]   Blog '{state['plan'].blog_title}' approved and finalised.")
    return {}


def handle_rejection(state: State) -> dict:
    """Called after human rejects — logs reason, no further processing."""
    reason = state.get("rejection_reason") or "No reason provided."
    logger.info(f"[HITL] ── handle_rejection ─────────────────────────────────")
    logger.info(f"[HITL]   Blog rejected. Reason: {reason}")
    return {"final": f"# Blog Rejected\n\n**Reason:** {reason}\n"}


# ──────────────────────────────────────────────────────────────
# Reducer Sub-graph  (merge → images — runs only on approval)
# ──────────────────────────────────────────────────────────────

reducer_graph = StateGraph(State)
reducer_graph.add_node("merge_content",              merge_content)
reducer_graph.add_node("decide_images",              decide_images)
reducer_graph.add_node("generate_and_place_images",  generate_and_place_images)

reducer_graph.add_edge(START,                       "merge_content")
reducer_graph.add_edge("merge_content",             "decide_images")
reducer_graph.add_edge("decide_images",             "generate_and_place_images")
reducer_graph.add_edge("generate_and_place_images", END)

reducer_subgraph = reducer_graph.compile()


# ──────────────────────────────────────────────────────────────
# Main Graph
# ──────────────────────────────────────────────────────────────
#
#  router ──► [research] ──► orchestrator ──► worker(×N)
#                                                  │
#                                              reducer (merge+images)
#                                                  │
#                                          human_approval  ◄── CHECKPOINT
#                                          /              \
#                               finalize_approved    handle_rejection
#

def build_workflow(checkpointer) -> StateGraph:
    graph = StateGraph(State)

    graph.add_node("router",            router_node)
    graph.add_node("research",          research_node)
    graph.add_node("orchestrator",      orchestrator_node)
    graph.add_node("worker",            worker_node)
    graph.add_node("reducer",           reducer_subgraph)
    graph.add_node("human_approval",    human_approval_node)
    graph.add_node("finalize_approved", finalize_approved)
    graph.add_node("handle_rejection",  handle_rejection)

    graph.add_edge(START,          "router")
    graph.add_conditional_edges(
        "router", route_next,
        {"research": "research", "orchestrator": "orchestrator"}
    )
    graph.add_edge("research",     "orchestrator")
    graph.add_conditional_edges("orchestrator", sub_worker, ["worker"])
    graph.add_edge("worker",       "reducer")
    graph.add_edge("reducer",      "human_approval")

    graph.add_conditional_edges(
        "human_approval", route_after_approval,
        {"finalize_approved": "finalize_approved", "handle_rejection": "handle_rejection"}
    )

    graph.add_edge("finalize_approved", END)
    graph.add_edge("handle_rejection",  END)

    return graph.compile(checkpointer=checkpointer)
