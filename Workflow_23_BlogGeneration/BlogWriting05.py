# Blog Gen with Image


from __future__ import annotations

import re
import logging
import operator
from datetime import datetime
from typing import TypedDict, List, Annotated, Literal, Optional
from pydantic import BaseModel, Field
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_tavily import TavilySearch
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

#------------------------------
# Logger Setup
#------------------------------

def setup_logger() -> logging.Logger:
    """Create a logger that writes to both console and a timestamped log file.

    Log files are saved under the 'logs/' directory with the naming format:
        log_{YYYYMMDD}_{HHMMSS}.log
    The directory is created automatically if it does not exist.
    """
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = logs_dir / f"log_{timestamp}.log"

    logger = logging.getLogger("BlogWriter")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if setup_logger is called more than once
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — DEBUG and above saved to log file
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler — INFO and above printed to stdout
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logger initialised. Log file: {log_filename}")
    return logger

logger = setup_logger()


#------------------------------
# Schemas
#------------------------------

class Task(BaseModel):
    id: int
    title: str
    goal: str = Field(
        ...,
        description="One sentence describing what the reader should be able to do/understand after this section."
    )
    bullets: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="3-6 concrete, non-overlapping subpoints to cover in this section."
    )
    target_words: int = Field(
        ...,
        description="Target word count for this section (120-450)."
    )
    tags: List[str] = Field(default_factory=list)
    requires_research: bool = False
    requires_citations: bool = False
    requires_code: bool = False


class Plan(BaseModel):
    blog_title: str
    audience: str
    tone: str
    blog_kind: Literal["explainer", "tutorial", "news_roundup", "comparison", "system_design"] = "explainer"
    constraints: List[str] = Field(default_factory=list)
    tasks: List[Task] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    title: str
    url: str
    published_at: Optional[str] = None
    snippet: Optional[str] = None
    source: Optional[str] = None


class RouterDecision(BaseModel):
    needs_research: bool = False
    mode: Literal["closed_book", "hybrid", "open_book"] = "closed_book"
    queries: List[str] = Field(default_factory=list)


class EvidencePack(BaseModel):
    evidence: List[EvidenceItem] = Field(default_factory=list)

class ImageSpec(BaseModel):
    placeholder: str = Field(
        ...,
        description=(
            "Exact placeholder token to insert. MUST be one of: "
            "[[IMAGE_1]], [[IMAGE_2]], [[IMAGE_3]]. "
            "No extra text, colons, or spaces inside the brackets."
        )
    )
    insert_after_heading: str = Field(
        ...,
        description=(
            "The exact ## heading text (without the '## ' prefix) of the section "
            "after whose first paragraph this image should be inserted. "
            "Must match a heading that exists in the blog."
        )
    )
    filename: str = Field(..., description="Save under images/, e.g. qkv_flow.png")
    alt: str
    caption: str
    prompt: str = Field(..., description="Prompt to send to the image model.")
    size: Literal["1024x1024", "1024x1536", "1536x1024"] = "1024x1024"
    quality: Literal["low", "medium", "high"] = "medium"

class GlobalImagePlan(BaseModel):
    images: List[ImageSpec] = Field(default_factory=list)


#------------------------------
# State
#------------------------------

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

    # reducer/image
    merged_md: str
    md_with_placeholders: str
    image_specs: List[dict]
    
    final: str


#------------------------------
# LLM
#------------------------------

logger.debug("[SETUP] Initialising LLMs...")
blog_llm = ChatOllama(model="llama3.2:3b", temperature=0.5)
# qwen3:0.6b emits <think> tokens which break structured output — use llama3.2:3b here too
decision_llm = ChatOllama(model="llama3.2:3b", temperature=0.7)
logger.debug("[SETUP] LLMs ready. blog_llm=llama3.2:3b | decision_llm=llama3.2:3b")


#------------------------------
# Router
#------------------------------

ROUTER_SYSTEM = """You are a routing module for a technical blog planner.

Decide whether web research is needed BEFORE planning.

Modes:
- closed_book (needs_research=false):
  Evergreen topic where correctness does not depend on recent facts (concepts, fundamentals).
- hybrid (needs_research=true):
  Mostly evergreen but needs up-to-date examples/tools/models to be useful.
- open_book (needs_research=true):
  Mostly volatile: weekly roundups, "this week", "latest", ranking, pricing, policy/regulation.

If needs_research=true:
- Output 3-10 high-signal queries.
- Queries should be scoped and specific (avoid generic queries like just "AI" or "LLM").
- If user asked for "last week/this week/latest", reflect that constraint IN THE QUERIES.
"""

def router_node(state: State) -> dict:
    topic = state["topic"]
    logger.info(f"[ROUTER] ── Entering router node ──────────────────────────")
    logger.debug(f"[ROUTER]   Topic: '{topic}'")
    logger.debug(f"[ROUTER]   Invoking decision LLM for routing decision...")

    decider = decision_llm.with_structured_output(RouterDecision)

    try:
        decision = decider.invoke(
            [
                SystemMessage(content=ROUTER_SYSTEM),
                HumanMessage(content=f"Topic: {topic}"),
            ]
        )
    except Exception as e:
        logger.error(f"[ROUTER] LLM invocation failed: {e}", exc_info=True)
        raise

    needs_research = decision.needs_research or bool(decision.queries)

    logger.info(f"[ROUTER]   Decision   : mode='{decision.mode}' | needs_research={needs_research}")
    logger.debug(f"[ROUTER]   Queries ({len(decision.queries)}): {decision.queries}")
    logger.info(f"[ROUTER] ── Router node complete ────────────────────────────")

    return {
        "needs_research": needs_research,
        "mode": decision.mode,
        "queries": decision.queries,
    }

def route_next(state: State) -> str:
    next_node = "research" if state["needs_research"] else "orchestrator"
    logger.info(f"[ROUTER] Routing graph → '{next_node}' (needs_research={state['needs_research']})")
    return next_node


#------------------------------
# Research
#------------------------------

def _tavily_search(query: str, max_results: int = 5) -> List[dict]:
    logger.debug(f"[RESEARCH] Tavily search — query='{query}' | max_results={max_results}")
    tool = TavilySearch(max_results=max_results)

    try:
        response = tool.invoke({"query": query})
    except Exception as e:
        logger.error(f"[RESEARCH] Tavily search failed for query='{query}': {e}", exc_info=True)
        return []

    if isinstance(response, dict):
        results = response.get("results") or []
    elif isinstance(response, list):
        results = response  # legacy / alternative wrapper — keep working
    else:
        logger.warning(f"[RESEARCH] Unexpected Tavily response type: {type(response)}. Returning empty.")
        results = []

    normalized: List[dict] = []
    for r in results or []:
        normalized.append(
            {
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "snippet": r.get("content") or r.get("snippet") or "",
                "published_at": r.get("published_date") or r.get("published_at"),
                "source": r.get("source"),
            }
        )

    logger.debug(f"[RESEARCH] Tavily returned {len(normalized)} results for query='{query}'")
    return normalized


RESEARCH_SYSTEM = """You are a research synthesizer for technical writing.

Given raw web search results, produce a deduplicated list of EvidenceItem objects.

Rules:
- Only include items with a non-empty url.
- Prefer relevant + authoritative sources (company blogs, docs, reputable outlets).
- If a published date is explicitly present in the result payload, keep it as YYYY-MM-DD.
  If missing or unclear, set published_at=null. Do NOT guess.
- Keep snippets short.
- Deduplicate by URL.
"""

def research_node(state: State) -> dict:
    queries = (state.get("queries", []) or [])
    max_results = 6

    logger.info(f"[RESEARCH] ── Entering research node ─────────────────────────")
    logger.info(f"[RESEARCH]   Queries to process : {len(queries)}")
    logger.debug(f"[RESEARCH]   Query list         : {queries}")

    raw_results: List[dict] = []
    for i, q in enumerate(queries, start=1):
        logger.debug(f"[RESEARCH]   Running query {i}/{len(queries)}: '{q}'")
        results = _tavily_search(q, max_results=max_results)
        raw_results.extend(results)
        logger.debug(f"[RESEARCH]   Cumulative raw results so far: {len(raw_results)}")

    logger.info(f"[RESEARCH]   Total raw results fetched: {len(raw_results)}")

    if not raw_results:
        logger.warning("[RESEARCH]   No raw results returned from any query. Returning empty evidence.")
        return {"evidence": []}

    logger.debug(f"[RESEARCH]   Invoking LLM to synthesize and deduplicate evidence...")
    extractor = blog_llm.with_structured_output(EvidencePack)

    try:
        pack = extractor.invoke(
            [
                SystemMessage(content=RESEARCH_SYSTEM),
                HumanMessage(content=f"Raw results:\n{raw_results}"),
            ]
        )
    except Exception as e:
        logger.error(f"[RESEARCH] LLM evidence extraction failed: {e}", exc_info=True)
        raise

    dedup = {}
    for e in pack.evidence:
        if e.url:
            dedup[e.url] = e

    deduped_count = len(dedup)
    logger.info(f"[RESEARCH]   Evidence after deduplication: {deduped_count} items")
    logger.debug(f"[RESEARCH]   Evidence URLs: {list(dedup.keys())}")
    if deduped_count == 0:
        logger.warning(
            f"[RESEARCH]   All {len(raw_results)} raw results were discarded during "
            "LLM synthesis (empty URLs, low relevance, or model hallucination). "
            "Pipeline will continue without evidence (closed-book fallback)."
        )
    logger.info(f"[RESEARCH] ── Research node complete ───────────────────────────")

    return {"evidence": list(dedup.values())}



#------------------------------
# Orchestrator
#------------------------------

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
    },
    {
      "id": 2,
      "title": "Implementing Gradient Descent in Python",
      "goal": "Show a minimal working implementation of gradient descent from scratch.",
      "bullets": [
        "Define a simple quadratic loss function",
        "Implement the gradient update loop",
        "Plot the loss curve to verify convergence"
      ],
      "target_words": 300,
      "tags": ["code"],
      "requires_research": false,
      "requires_citations": false,
      "requires_code": true
    }
  ]
}

Output must strictly match the Plan schema.
"""

def orchestrator_node(state: State) -> dict:
    """Planner — generates a structured blog outline."""
    logger.info(f"[ORCH] ── Entering orchestrator node ──────────────────────")
    logger.debug(f"[ORCH]   Topic          : '{state['topic']}'")
    logger.debug(f"[ORCH]   Mode           : '{state.get('mode', 'closed_book')}'")
    logger.debug(f"[ORCH]   Evidence items : {len(state.get('evidence', []))}")

    planner = blog_llm.with_structured_output(Plan)

    evidence = state.get("evidence", [])
    mode = state.get("mode", "closed_book")

    messages = [
        SystemMessage(content=ORCH_SYSTEM),
        HumanMessage(
            content=(
                f"Topic: {state['topic']}\n"
                f"Mode: {mode}\n\n"
                f"Evidence (ONLY use for fresh claims; may be empty):\n"
                f"{[e.model_dump() for e in evidence][:16]}"
            )
        ),
    ]

    plan = None
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        logger.info(f"[ORCH]   Planning attempt {attempt}/{max_attempts}...")
        try:
            plan = planner.invoke(messages)
        except Exception as e:
            logger.error(f"[ORCH]   LLM invocation failed on attempt {attempt}: {e}", exc_info=True)
            if attempt == max_attempts:
                raise
            continue

        task_count = len(plan.tasks) if plan else 0
        logger.debug(f"[ORCH]   Attempt {attempt} returned {task_count} tasks")

        if plan and plan.tasks:
            logger.info(f"[ORCH]   Plan accepted on attempt {attempt} — {task_count} tasks generated")
            break

        logger.warning(f"[ORCH]   Attempt {attempt} returned empty tasks list. Retrying with stricter prompt...")
        # Escalate on subsequent retries
        messages = [
            SystemMessage(content=ORCH_SYSTEM),
            HumanMessage(
                content=(
                    f"Topic: {state['topic']}\n"
                    f"Mode: {mode}\n\n"
                    f"IMPORTANT: You returned an empty tasks list. This is invalid.\n"
                    f"You MUST include at least 5 task objects in the tasks array.\n"
                    f"Follow the example in the system prompt exactly.\n\n"
                    f"Evidence (ONLY use for fresh claims; may be empty):\n"
                    f"{[e.model_dump() for e in evidence][:16]}"
                )
            ),
        ]

    if plan and plan.tasks:
        logger.info(f"[ORCH]   Blog title : '{plan.blog_title}'")
        logger.info(f"[ORCH]   Audience   : '{plan.audience}' | Tone: '{plan.tone}' | Kind: '{plan.blog_kind}'")
        logger.debug(f"[ORCH]   Task breakdown:")
        for t in plan.tasks:
            logger.debug(
                f"[ORCH]     Task {t.id:02d} | '{t.title}' | "
                f"~{t.target_words}w | code={t.requires_code} | "
                f"research={t.requires_research} | citations={t.requires_citations}"
            )
    else:
        logger.error(f"[ORCH]   All {max_attempts} attempts returned empty tasks. Plan may be unusable.")

    logger.info(f"[ORCH] ── Orchestrator node complete ─────────────────────────")
    return {"plan": plan}


#------------------------------
# Sub-worker dispatcher
#------------------------------

def sub_worker(state: State):
    logger.info(f"[DISPATCHER] ── Entering sub-worker dispatcher ───────────────")

    if not state.get("plan") or not state["plan"].tasks:
        logger.error("[DISPATCHER] Orchestrator produced no tasks after all retries. Cannot dispatch workers.")
        raise ValueError(
            "Orchestrator produced no tasks after all retries. "
            "Cannot generate blog sections. Try a more capable model."
        )

    task_count = len(state["plan"].tasks)
    logger.info(f"[DISPATCHER]   Dispatching {task_count} parallel worker(s)...")

    sends = []
    for task in state["plan"].tasks:
        logger.debug(
            f"[DISPATCHER]   → Send worker for Task {task.id}: '{task.title}'"
        )
        sends.append(
            Send(
                "worker",
                {
                    "task": task.model_dump(),
                    "topic": state["topic"],
                    "mode": state["mode"],
                    "plan": state["plan"].model_dump(),
                    "evidence": [e.model_dump() for e in state.get("evidence", [])]
                },
            )
        )

    logger.info(f"[DISPATCHER]   All {len(sends)} worker Send objects created")
    logger.info(f"[DISPATCHER] ── Dispatcher complete ───────────────────────────")
    return sends


#------------------------------
# Worker
#------------------------------

WORKER_SYSTEM = """You are a senior technical writer and developer advocate.
Write ONE section of a technical blog post in Markdown.

Hard constraints:
- Follow the provided Goal and cover ALL Bullets in order (do not skip or merge bullets).
- Stay close to Target words (±15%).
- Output ONLY the section content in Markdown (no blog title H1, no extra commentary).
- Start with a '## <Section Title>' heading.

Scope guard:
- If blog_kind == "news_roundup": do NOT turn this into a tutorial/how-to guide.
  Focus on summarizing events and implications.

Grounding policy:
- If mode == open_book:
  - Do NOT introduce any specific event/company/model/funding/policy claim unless it is
    supported by a provided Evidence URL.
  - For each event claim, attach a source as a Markdown link: ([Source](URL)).
  - Only use URLs provided in Evidence. If not supported, write: "Not found in provided sources."
- If requires_citations == true:
  - For outside-world claims, cite Evidence URLs the same way.
- Evergreen reasoning is OK without citations unless requires_citations is true.

Code:
- If requires_code == true, include at least one minimal, correct code snippet.

Style:
- Short paragraphs, bullets where helpful, code fences for code.
- Avoid fluff/marketing. Be precise and implementation-oriented.
"""


def worker_node(payload: dict) -> dict:
    """Writes one blog section in parallel with other workers."""
    task = Task(**payload["task"])
    plan = Plan(**payload["plan"])
    evidence = [EvidenceItem(**e) for e in payload.get("evidence", [])]
    topic = payload["topic"]
    mode = payload.get("mode", "closed_book")

    logger.info(f"[WORKER] ── Task {task.id}: '{task.title}' ─────────────────")
    logger.debug(f"[WORKER]   Goal           : {task.goal}")
    logger.debug(f"[WORKER]   Target words   : {task.target_words}")
    logger.debug(f"[WORKER]   requires_code  : {task.requires_code}")
    logger.debug(f"[WORKER]   requires_cit.  : {task.requires_citations}")
    logger.debug(f"[WORKER]   Bullets ({len(task.bullets)})   : {task.bullets}")
    logger.debug(f"[WORKER]   Evidence items : {len(evidence)}")
    logger.debug(f"[WORKER]   Blog kind      : {plan.blog_kind} | Mode: {mode}")

    bullets_text = "\n- " + "\n- ".join(task.bullets)

    evidence_text = ""
    if evidence:
        evidence_text = "\n".join(
            f"- {e.title} | {e.url} | {e.published_at or 'date:unknown'}".strip()
            for e in evidence[:20]
        )
        logger.debug(f"[WORKER]   Injecting {min(len(evidence), 20)} evidence items into prompt")
    else:
        logger.debug(f"[WORKER]   No evidence to inject (closed_book or empty research)")

    logger.debug(f"[WORKER]   Invoking blog LLM to write section...")

    try:
        section_md = blog_llm.invoke(
            [
                SystemMessage(content=WORKER_SYSTEM),
                HumanMessage(
                    content=(
                        f"Blog title: {plan.blog_title}\n"
                        f"Audience: {plan.audience}\n"
                        f"Tone: {plan.tone}\n"
                        f"Blog kind: {plan.blog_kind}\n"
                        f"Constraints: {plan.constraints}\n"
                        f"Topic: {topic}\n"
                        f"Mode: {mode}\n\n"
                        f"Section title: {task.title}\n"
                        f"Goal: {task.goal}\n"
                        f"Target words: {task.target_words}\n"
                        f"Tags: {task.tags}\n"
                        f"requires_research: {task.requires_research}\n"
                        f"requires_citations: {task.requires_citations}\n"
                        f"requires_code: {task.requires_code}\n"
                        f"Bullets:{bullets_text}\n\n"
                        f"Evidence (ONLY use these URLs when citing):\n{evidence_text}\n"
                    )
                )
            ],
        ).content.strip()
    except Exception as e:
        logger.error(f"[WORKER] Task {task.id} — LLM invocation failed: {e}", exc_info=True)
        raise

    word_count = len(section_md.split())
    target = task.target_words
    deviation_pct = abs(word_count - target) / max(target, 1) * 100

    logger.info(
        f"[WORKER] Task {task.id} done — '{task.title}' | "
        f"~{word_count} words written (target={target}, deviation={deviation_pct:.1f}%)"
    )

    if deviation_pct > 20:
        logger.warning(
            f"[WORKER] Task {task.id} word count deviation > 20%: "
            f"got {word_count}, target {target}"
        )

    logger.info(f"[WORKER] ── Task {task.id} complete ─────────────────────────")
    return {"sections": [(task.id, section_md)]}


#------------------------------
# Reducer: Merge Content
#------------------------------

def merge_content(state: State) -> dict:
    logger.info(f"[MERGE] ── Entering merge_content node ──────────────────────")

    plan = state["plan"]
    sections = state.get("sections", [])

    logger.info(f"[MERGE]   Sections received : {len(sections)}")
    logger.debug(f"[MERGE]   Section IDs      : {sorted(sid for sid, _ in sections)}")

    ordered_sections = [md for _, md in sorted(sections, key=lambda x: x[0])]
    body = "\n\n".join(ordered_sections).strip()
    merged_md = f"# {plan.blog_title}\n\n{body}\n"

    total_words = len(merged_md.split())
    logger.info(f"[MERGE]   Blog title       : '{plan.blog_title}'")
    logger.info(f"[MERGE]   Total word count : ~{total_words} words")
    logger.debug(f"[MERGE]   Merged markdown length: {len(merged_md)} chars")
    logger.info(f"[MERGE] ── merge_content node complete ───────────────────────")

    return {"merged_md": merged_md}


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
   after which this image should appear. Must match a heading in the blog exactly.

3. filename  — e.g. "qkv_attention_flow.png"
4. alt       — short alt text
5. caption   — one-sentence caption
6. prompt    — detailed image generation prompt

DO NOT return the blog markdown. Only return the GlobalImagePlan JSON.
"""

# Matches both [[IMAGE_1]] and [IMAGE_1] and verbose forms like [[IMAGE_1: desc]]
_PLACEHOLDER_RE = re.compile(r'\[{1,2}IMAGE_(\d+)[^\]]*\]{1,2}')

def _inject_placeholders(merged_md: str, images: list) -> str:
    """
    Insert [[IMAGE_N]] placeholders into merged_md by locating each heading
    specified in ImageSpec.insert_after_heading, then placing the token after
    the first paragraph that follows that heading.

    Strategy: rebuild the heading index from scratch after every insertion so
    line numbers are always accurate regardless of how many images are placed.
    """
    def _build_heading_index(lines: list) -> dict:
        return {
            line[3:].strip(): i
            for i, line in enumerate(lines)
            if line.startswith("## ")
        }

    # Sort by placeholder number ascending so IMAGE_1 is placed before IMAGE_2
    ordered = sorted(
        images,
        key=lambda x: int(_PLACEHOLDER_RE.search(x.placeholder).group(1))
        if _PLACEHOLDER_RE.search(x.placeholder) else 999
    )

    result = merged_md.split("\n")

    for img in ordered:
        target_heading = img.insert_after_heading.strip()
        # Strip "## " prefix if the LLM accidentally included it in insert_after_heading
        if target_heading.startswith("## "):
            target_heading = target_heading[3:].strip()
        canonical = f"[[IMAGE_{_PLACEHOLDER_RE.search(img.placeholder).group(1)}]]" \
            if _PLACEHOLDER_RE.search(img.placeholder) else img.placeholder

        # Rebuild index each iteration so previous insertions are reflected
        heading_index = _build_heading_index(result)

        # Exact match first, then case-insensitive fallback
        idx = heading_index.get(target_heading)
        if idx is None:
            for h, i in heading_index.items():
                if h.lower() == target_heading.lower():
                    idx = i
                    break

        if idx is None:
            logger.warning(
                f"[IMAGES]   Could not find heading '{target_heading}' for "
                f"placeholder '{canonical}'. Appending at end of blog."
            )
            result.append("")
            result.append(canonical)
            continue

        # Walk forward past the heading line itself, then past the first paragraph
        insert_at = idx + 1
        while insert_at < len(result) and result[insert_at].strip():
            insert_at += 1

        result.insert(insert_at, canonical)
        result.insert(insert_at, "")   # blank line before placeholder
        logger.debug(
            f"[IMAGES]   Injected '{canonical}' after line {insert_at} "
            f"(heading: '{target_heading}')"
        )

    return "\n".join(result)


def decide_images(state: State) -> dict:
    logger.info(f"[IMAGES] ── Entering decide_images node ──────────────────────")

    planner = decision_llm.with_structured_output(GlobalImagePlan)
    merged_md = state["merged_md"]
    plan = state["plan"]
    assert plan is not None

    merged_word_count = len(merged_md.split())
    logger.debug(f"[IMAGES]   Blog kind        : '{plan.blog_kind}'")
    logger.debug(f"[IMAGES]   Topic            : '{state['topic']}'")
    logger.debug(f"[IMAGES]   Markdown length  : ~{merged_word_count} words / {len(merged_md)} chars")

    # Send only headings + first sentence of each section to the LLM — not the
    # full markdown — so small models cannot truncate the blog content.
    headings_summary = []
    for line in merged_md.split("\n"):
        if line.startswith("## "):
            headings_summary.append(line)
    headings_block = "\n".join(headings_summary)
    logger.debug(f"[IMAGES]   Sections found   : {len(headings_summary)}")
    logger.debug(f"[IMAGES]   Invoking decision LLM to plan image placement...")

    try:
        image_plan = planner.invoke(
            [
                SystemMessage(content=DECIDE_IMAGE_SYSTEM),
                HumanMessage(
                    content=(
                        f"Blog kind: {plan.blog_kind}\n"
                        f"Topic: {state['topic']}\n\n"
                        f"Section headings available for image placement:\n"
                        f"{headings_block}\n\n"
                        "Decide which sections need images and fill in the ImageSpec list."
                    )
                ),
            ]
        )
    except Exception as e:
        logger.error(f"[IMAGES] LLM invocation failed in decide_images: {e}", exc_info=True)
        raise

    image_count = len(image_plan.images)
    logger.info(f"[IMAGES]   Images planned   : {image_count}")

    # Normalise placeholder tokens (handle [IMAGE_1], [[IMAGE_1: desc]], etc.)
    fixed_images = []
    for img in image_plan.images:
        m = _PLACEHOLDER_RE.search(img.placeholder)
        canonical = f"[[IMAGE_{m.group(1)}]]" if m else img.placeholder
        if canonical != img.placeholder:
            logger.warning(
                f"[IMAGES]   Non-canonical placeholder: '{img.placeholder}' "
                f"→ normalised to '{canonical}'"
            )
            img = img.model_copy(update={"placeholder": canonical})
        fixed_images.append(img)

    for i, img in enumerate(fixed_images, start=1):
        logger.debug(
            f"[IMAGES]   Image {i}: placeholder='{img.placeholder}' | "
            f"insert_after='{img.insert_after_heading}' | "
            f"filename='{img.filename}' | size='{img.size}' | quality='{img.quality}'"
        )
        logger.debug(f"[IMAGES]   Image {i} alt     : '{img.alt}'")
        logger.debug(f"[IMAGES]   Image {i} caption : '{img.caption}'")
        logger.debug(f"[IMAGES]   Image {i} prompt  : '{img.prompt[:80]}...'")

    if image_count == 0:
        logger.info(f"[IMAGES]   No images deemed necessary for this blog.")
        md_with_placeholders = merged_md
    else:
        logger.info(f"[IMAGES]   {image_count} image(s) will be generated and placed.")
        # Inject placeholders into the full merged_md ourselves — never trust the
        # LLM to echo back the complete document without truncating it.
        md_with_placeholders = _inject_placeholders(merged_md, fixed_images)
        injected_chars = len(md_with_placeholders)
        logger.debug(
            f"[IMAGES]   md_with_placeholders length after injection: {injected_chars} chars "
            f"(original: {len(merged_md)} chars)"
        )

    logger.info(f"[IMAGES] ── decide_images node complete ────────────────────────")

    return {
        "md_with_placeholders": md_with_placeholders,
        "image_specs": [img.model_dump() for img in fixed_images],
    }

import os
from google import genai
import google.genai.types as types

def _gemini_generate_image_bytes(prompt: str) -> bytes:
    """
    Returns raw image bytes generated by Gemini.
    Requires: google-genai
              Google API Key
    """
    IMAGE_MODEL = "gemini-2.5-flash-image"
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

    logger.debug(f"[IMGGEN] Gemini image generation — model='{IMAGE_MODEL}'")
    logger.debug(f"[IMGGEN] Prompt (first 100 chars): '{prompt[:100]}...'")

    if not GOOGLE_API_KEY:
        logger.error("[IMGGEN] GOOGLE_API_KEY environment variable is not set.")
        raise RuntimeError("GOOGLE API KEY is not set.")

    logger.debug(f"[IMGGEN] Initialising Gemini client...")
    client = genai.Client(api_key=GOOGLE_API_KEY)

    try:
        response = client.models.generate_content(
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
    except Exception as e:
        logger.error(f"[IMGGEN] Gemini API call failed: {e}", exc_info=True)
        raise

    # Depending on SDK version, parts may hang off resp.candidates[0].content.parts
    parts = getattr(response, "parts", None)

    if not parts and getattr(response, "candidates", None):
        logger.debug(f"[IMGGEN] Falling back to candidates[0].content.parts")
        try:
            parts = response.candidates[0].content.parts
        except Exception as e:
            logger.warning(f"[IMGGEN] Could not access candidates[0].content.parts: {e}")
            parts = None

    if not parts:
        logger.error("[IMGGEN] No image content returned (safety block / quota / SDK change).")
        raise RuntimeError("No image content returned (safety/quota/SDK change).")

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            data_len = len(inline.data)
            logger.debug(f"[IMGGEN] Inline image bytes received: {data_len} bytes")
            return inline.data

    logger.error("[IMGGEN] Iterated all parts but found no inline image bytes.")
    raise RuntimeError("No inline image bytes found in response.")


def _sanitize_filename(name: str) -> str:
    """Replace characters that are invalid in Windows/Unix filenames.

    On Windows a colon triggers Alternate Data Stream (ADS) behaviour —
    content written to 'foo: bar.md' lands in an invisible ADS while the
    visible 'foo' file stays empty.  Strip / replace the full set of
    reserved characters to prevent this.
    """
    # Characters illegal on Windows: \ / : * ? " < > |
    sanitized = re.sub(r'[\\/:*?"<>|]', '-', name)
    # Collapse runs of dashes and trim surrounding whitespace / dashes
    sanitized = re.sub(r'-+', '-', sanitized).strip(' -')
    return sanitized


def generate_and_place_images(state: State) -> dict:
    logger.info(f"[IMGPLACE] ── Entering generate_and_place_images node ──────────")

    plan = state["plan"]
    assert plan is not None

    md = state.get("md_with_placeholders") or state["merged_md"]
    image_specs = state.get("image_specs", []) or []

    logger.info(f"[IMGPLACE]   Image specs to process : {len(image_specs)}")

    # Output dirs
    output_dir = Path("output")
    images_dir = output_dir / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"[IMGPLACE]   Output directory : '{output_dir.resolve()}'")
    logger.debug(f"[IMGPLACE]   Images directory : '{images_dir.resolve()}'")

    # If no images requested, just write merged markdown
    if not image_specs:
        out_md_path = output_dir / f"{_sanitize_filename(plan.blog_title)}.md"
        logger.info(f"[IMGPLACE]   No images to generate. Writing markdown directly → '{out_md_path}'")
        try:
            out_md_path.write_text(md, encoding="utf-8")
            logger.info(f"[IMGPLACE]   File written: '{out_md_path}' ({len(md)} chars)")
        except Exception as e:
            logger.error(f"[IMGPLACE]   Failed to write markdown file '{out_md_path}': {e}", exc_info=True)
            raise
        return {"final": md}

    success_count = 0
    failure_count = 0

    for i, spec in enumerate(image_specs, start=1):
        placeholder = spec["placeholder"]
        filename = spec["filename"]
        out_path = images_dir / filename

        logger.info(
            f"[IMGPLACE]   Processing image {i}/{len(image_specs)}: "
            f"placeholder='{placeholder}' | filename='{filename}'"
        )

        # generate only if needed
        if out_path.exists():
            logger.info(f"[IMGPLACE]   Image already exists on disk, skipping generation: '{out_path}'")
        else:
            logger.debug(f"[IMGPLACE]   Generating image via Gemini...")
            try:
                img_bytes = _gemini_generate_image_bytes(spec["prompt"])
                out_path.write_bytes(img_bytes)
                logger.info(
                    f"[IMGPLACE]   Image {i} saved: '{out_path}' "
                    f"({len(img_bytes)} bytes)"
                )
                success_count += 1
            except Exception as e:
                logger.error(
                    f"[IMGPLACE]   Image {i} generation FAILED for placeholder='{placeholder}': {e}",
                    exc_info=True
                )
                failure_count += 1
                # graceful fallback: keep doc usable
                prompt_block = (
                    f"> **[IMAGE GENERATION FAILED]** {spec.get('caption', '')}\n>\n"
                    f"> **Alt:** {spec.get('alt', '')}\n>\n"
                    f"> **Prompt:** {spec.get('prompt', '')}\n\n"
                    f"> **Error:** {e}\n"
                )
                md = md.replace(placeholder, prompt_block)
                logger.debug(f"[IMGPLACE]   Replaced placeholder '{placeholder}' with failure block.")
                continue

        # Image ref path is relative to the output/ folder where the .md lives
        img_md = f"![{spec['alt']}](images/{filename})\n*{spec['caption']}*"
        md = md.replace(placeholder, img_md)
        logger.debug(f"[IMGPLACE]   Replaced placeholder '{placeholder}' with image markdown.")

    logger.info(
        f"[IMGPLACE]   Image processing summary — "
        f"success={success_count} | failed={failure_count} | skipped (cached)={len(image_specs) - success_count - failure_count}"
    )

    out_md_path = output_dir / f"{_sanitize_filename(plan.blog_title)}.md"
    logger.info(f"[IMGPLACE]   Writing final markdown → '{out_md_path}'")

    try:
        out_md_path.write_text(md, encoding="utf-8")
        logger.info(f"[IMGPLACE]   File written: '{out_md_path}' ({len(md)} chars, ~{len(md.split())} words)")
    except Exception as e:
        logger.error(f"[IMGPLACE]   Failed to write final markdown file '{out_md_path}': {e}", exc_info=True)
        raise

    logger.info(f"[IMGPLACE] ── generate_and_place_images node complete ───────────")
    return {"final": md}


#------------------------------
# Reducer: Sub-Graph
#------------------------------
reducer_graph = StateGraph(State)
reducer_graph.add_node("merge_content", merge_content)
reducer_graph.add_node("decide_images", decide_images)
reducer_graph.add_node("generate_and_place_images", generate_and_place_images)

reducer_graph.add_edge(START, "merge_content")
reducer_graph.add_edge("merge_content", "decide_images")
reducer_graph.add_edge("decide_images", "generate_and_place_images")
reducer_graph.add_edge("generate_and_place_images", END)

reducer_subgraph = reducer_graph.compile()


#------------------------------
# Graph
#------------------------------

g = StateGraph(State)

g.add_node("router", router_node)
g.add_node("research", research_node)
g.add_node("orchestrator", orchestrator_node)
g.add_node("worker", worker_node)
g.add_node("reducer", reducer_subgraph)

g.add_edge(START, "router")
g.add_conditional_edges("router", route_next, {"research": "research", "orchestrator": "orchestrator"})
g.add_edge("research", "orchestrator")
g.add_conditional_edges("orchestrator", sub_worker, ["worker"])
g.add_edge("worker", "reducer")
g.add_edge("reducer", END)

app = g.compile()

#------------------------------
# Runner
#------------------------------

def run(topic: str):
    logger.info("=" * 65)
    logger.info("[RUN] Blog generation pipeline STARTING")
    logger.info(f"[RUN] Topic : '{topic}'")
    logger.info("=" * 65)

    start_time = datetime.now()
    logger.debug(f"[RUN] Start timestamp: {start_time.isoformat()}")

    try:
        out = app.invoke(
            {
                "topic": topic,
                "mode": "",
                "needs_research": False,
                "queries": [],
                "evidence": [],
                "plan": None,
                "sections": [],
                "final": "",
            }
        )
    except Exception as e:
        logger.critical(f"[RUN] Pipeline FAILED with unhandled exception: {e}", exc_info=True)
        raise

    elapsed = (datetime.now() - start_time).total_seconds()
    final_word_count = len((out.get("final") or "").split())

    logger.info("=" * 65)
    logger.info("[RUN] Pipeline COMPLETE")
    logger.info(f"[RUN] Elapsed time    : {elapsed:.2f}s")
    logger.info(f"[RUN] Final word count: ~{final_word_count} words")
    logger.info(f"[RUN] Mode used       : '{out.get('mode', 'N/A')}'")
    logger.info(f"[RUN] Evidence items  : {len(out.get('evidence', []))}")
    logger.info(f"[RUN] Sections written: {len(out.get('sections', []))}")
    logger.info("=" * 65)

    return out


query = "Write a blog on the Requirements of 6th Generation Fighter Jet."
response = run(query)
logger.info("[RESPONSE] Blog Generation Complete.")
