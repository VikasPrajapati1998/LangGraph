from __future__ import annotations

import re
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


# ------------------------------
# Schemas
# ------------------------------

class Task(BaseModel):
    id: int
    title: str
    goal: str
    bullets: List[str] = Field(..., min_length=3, max_length=5)
    target_words: int
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


# ------------------------------
# State
# ------------------------------

class State(TypedDict):
    topic: str
    mode: str
    needs_research: bool
    queries: List[str]
    evidence: List[EvidenceItem]
    plan: Optional[Plan]
    sections: Annotated[List[tuple[int, str]], operator.add]
    final: str


# ------------------------------
# LLM
# ------------------------------

blog_llm = ChatOllama(model="llama3.2:3b", temperature=0.5)
decision_llm = ChatOllama(model="llama3.2:3b", temperature=0.7)


# ------------------------------
# Router
# ------------------------------

ROUTER_SYSTEM = """You are a routing module for a technical blog planner.

Decide whether web research is needed BEFORE planning.

Modes:
- closed_book (needs_research=false)
- hybrid (needs_research=true)
- open_book (needs_research=true)

If needs_research=true:
- Output 3-10 high-signal queries.
"""

def router_node(state: State) -> dict:
    topic = state["topic"]

    decider = decision_llm.with_structured_output(RouterDecision)
    decision = decider.invoke(
        [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=f"Topic: {topic}"),
        ]
    )

    needs_research = decision.needs_research or bool(decision.queries)

    return {
        "needs_research": needs_research,
        "mode": decision.mode,
        "queries": decision.queries,
    }


def route_next(state: State) -> str:
    return "research" if state["needs_research"] else "orchestrator"


# ------------------------------
# Research
# ------------------------------

def _tavily_search(query: str, max_results: int = 5) -> List[dict]:
    tool = TavilySearch(max_results=max_results)
    response = tool.invoke({"query": query})

    if isinstance(response, dict):
        results = response.get("results") or []
    elif isinstance(response, list):
        results = response
    else:
        results = []

    normalized = []
    for r in results:
        normalized.append(
            {
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "snippet": r.get("content") or r.get("snippet") or "",
                "published_at": r.get("published_date") or r.get("published_at"),
                "source": r.get("source"),
            }
        )
    return normalized


RESEARCH_SYSTEM = """You are a research synthesizer for technical writing."""

def research_node(state: State) -> dict:
    queries = state.get("queries", []) or []
    raw_results = []

    for q in queries:
        raw_results.extend(_tavily_search(q, max_results=6))

    if not raw_results:
        return {"evidence": []}

    extractor = blog_llm.with_structured_output(EvidencePack)
    pack = extractor.invoke(
        [
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(content=f"Raw results:\n{raw_results}"),
        ]
    )

    dedup = {}
    for e in pack.evidence:
        if e.url:
            dedup[e.url] = e

    return {"evidence": list(dedup.values())}


# ------------------------------
# Orchestrator
# ------------------------------

ORCH_SYSTEM = """You are a senior technical writer. Generate blog plan."""

def orchestrator_node(state: State) -> dict:
    planner = blog_llm.with_structured_output(Plan)
    evidence = state.get("evidence", [])
    mode = state.get("mode", "closed_book")

    messages = [
        SystemMessage(content=ORCH_SYSTEM),
        HumanMessage(
            content=(
                f"Topic: {state['topic']}\n"
                f"Mode: {mode}\n"
                f"Evidence:\n{[e.model_dump() for e in evidence][:16]}"
            )
        ),
    ]

    plan = None
    for _ in range(3):
        plan = planner.invoke(messages)
        if plan.tasks:
            break

    return {"plan": plan}


# ------------------------------
# Dispatcher
# ------------------------------

def sub_worker(state: State):
    if not state.get("plan") or not state["plan"].tasks:
        raise ValueError("No tasks generated.")

    return [
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
        for task in state["plan"].tasks
    ]


# ------------------------------
# Worker
# ------------------------------

WORKER_SYSTEM = """Write ONE section of a technical blog."""

def worker_node(payload: dict) -> dict:
    task = Task(**payload["task"])
    plan = Plan(**payload["plan"])
    evidence = [EvidenceItem(**e) for e in payload.get("evidence", [])]

    bullets_text = "\n- " + "\n- ".join(task.bullets)

    evidence_text = ""
    if evidence:
        evidence_text = "\n".join(
            f"- {e.title} | {e.url}" for e in evidence[:20]
        )

    section_md = blog_llm.invoke(
        [
            SystemMessage(content=WORKER_SYSTEM),
            HumanMessage(
                content=(
                    f"Blog title: {plan.blog_title}\n"
                    f"Section title: {task.title}\n"
                    f"Goal: {task.goal}\n"
                    f"Target words: {task.target_words}\n"
                    f"Bullets:{bullets_text}\n\n"
                    f"Evidence:\n{evidence_text}\n"
                )
            )
        ],
    ).content.strip()

    return {"sections": [(task.id, section_md)]}


# ------------------------------
# Reducer
# ------------------------------

def reducer_node(state: State) -> dict:
    plan = state["plan"]
    sections = state["sections"]

    ordered_sections = [md for _, md in sorted(sections, key=lambda x: x[0])]
    body = "\n\n".join(ordered_sections).strip()
    final_md = f"# {plan.blog_title}\n\n{body}\n"

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_title = re.sub(r"[^\w\s-]", "_", plan.blog_title).strip()
    filename = output_dir / f"{safe_title}.md"
    filename.write_text(final_md, encoding="utf-8")

    return {"final": final_md}


# ------------------------------
# Graph
# ------------------------------

g = StateGraph(State)

g.add_node("router", router_node)
g.add_node("research", research_node)
g.add_node("orchestrator", orchestrator_node)
g.add_node("worker", worker_node)
g.add_node("reducer", reducer_node)

g.add_edge(START, "router")
g.add_conditional_edges("router", route_next, {"research": "research", "orchestrator": "orchestrator"})
g.add_edge("research", "orchestrator")
g.add_conditional_edges("orchestrator", sub_worker, ["worker"])
g.add_edge("worker", "reducer")
g.add_edge("reducer", END)

app = g.compile()


# ------------------------------
# Runner
# ------------------------------

def run(topic: str):
    return app.invoke(
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


query = "Write a blog on the Claude AI."
response = run(query)
