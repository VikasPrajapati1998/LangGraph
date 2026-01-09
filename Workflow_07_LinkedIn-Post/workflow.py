import sqlite3
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools import DuckDuckGoSearchRun

# ===================== MODEL =====================
model = ChatOllama(
    model="qwen2.5:0.5b",
    temperature=0.3
)

search_tool = DuckDuckGoSearchRun(name="Search")

# ===================== STATE =====================
class PostState(TypedDict):
    topic: str
    search: str
    post: str
    suggestion: str
    approved: bool
    iteration: int
    max_iteration: int

# ===================== NODES =====================

def search_topic(state: PostState):
    topic = state["topic"]

    queries = [
        f"Latest developments about {topic}",
        f"History of {topic}",
        f"Current challenges of {topic}",
        f"Future trends of {topic}",
    ]

    results = []
    for q in queries:
        try:
            results.append(search_tool.run(q))
        except Exception:
            continue

    return {"search": "\n\n".join(results)}


def generate_post(state: PostState):
    prompt = [
        SystemMessage(content="You write professional LinkedIn posts."),
        HumanMessage(content=f"""
        TOPIC:
        {state['topic']}

        RESEARCH CONTEXT:
        {state['search']}

        USER FEEDBACK:
        {state['suggestion']}

        Write a professional LinkedIn post (120–180 words).
        Do not mention AI or tools.
        """)
    ]

    post = model.invoke(prompt).content.strip()

    return {
        "post": post,
        "approved": False,
        "iteration": state["iteration"] + 1,
    }


# 🔴 HITL WAIT NODE (ASYNC)
def human_review(state: PostState):
    return interrupt({
        "topic": state["topic"],
        "post": state["post"],
        "iteration": state["iteration"],
        "max_iteration": state["max_iteration"],
    })


def finalize_post(state: PostState):
    return state


# ===================== ROUTER =====================

def router(state: PostState):
    if state["approved"] or state["iteration"] >= state["max_iteration"]:
        return "finalize_post"
    else:
        return "generate_post"


# ===================== GRAPH =====================

graph = StateGraph(PostState)

graph.add_node("search_topic", search_topic)
graph.add_node("generate_post", generate_post)
graph.add_node("human_review", human_review)
graph.add_node("finalize_post", finalize_post)

graph.add_edge(START, "search_topic")
graph.add_edge("search_topic", "generate_post")
graph.add_edge("generate_post", "human_review")

graph.add_conditional_edges(
    "human_review",
    router,
    {
        "generate_post": "generate_post",
        "finalize_post": "finalize_post",
    }
)

graph.add_edge("finalize_post", END)

# ===================== COMPILE =====================

conn = sqlite3.connect("LinkedIn_Post.db", check_same_thread=False)
workflow = graph.compile(checkpointer=SqliteSaver(conn))

















'''
import sqlite3
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools import DuckDuckGoSearchRun

# ===================== MODEL =====================
model = ChatOllama(model="qwen2.5:0.5b", temperature=0.3)
search_tool = DuckDuckGoSearchRun(name="Search")

# ===================== STATE =====================
class PostState(TypedDict):
    topic: str
    search: str
    post: str
    suggestion: str
    approved: bool
    iteration: int
    max_iteration: int

# ===================== NODES =====================

def search_topic(state: PostState):
    topic = state["topic"]
    queries = [
        f"Latest developments about {topic}",
        f"History of {topic}",
        f"Current challenges of {topic}",
        f"Future trends of {topic}",
    ]
    results = [search_tool.run(q) for q in queries]
    return {"search": "\n\n".join(results)}

# 🔵 INITIAL GENERATION (runs only ONCE)
def initial_generate_post(state: PostState):
    prompt = [
        SystemMessage(content="You write professional LinkedIn posts."),
        HumanMessage(content=f"""
        TOPIC:
        {state['topic']}

        RESEARCH:
        {state['search']}

        Write a professional LinkedIn post (120–180 words).
        """)
    ]
    post = model.invoke(prompt).content.strip()

    return {
        "post": post,
        "approved": False,
        "iteration": 1,   # first version
    }

# 🔁 REGENERATION (runs ONLY after rejection)
def regenerate_post(state: PostState):
    prompt = [
        SystemMessage(content="You write professional LinkedIn posts."),
        HumanMessage(content=f"""
        TOPIC:
        {state['topic']}

        RESEARCH:
        {state['search']}

        USER FEEDBACK:
        {state['suggestion']}

        Improve the post based on feedback.
        """)
    ]
    post = model.invoke(prompt).content.strip()

    return {
        "post": post,
        "approved": False,
        "iteration": state["iteration"] + 1,
    }

# 🧍 HITL WAIT
def human_review(state: PostState):
    return interrupt({
        "topic": state["topic"],
        "post": state["post"],
        "iteration": state["iteration"],
        "max_iteration": state["max_iteration"],
    })

def finalize_post(state: PostState):
    return state

def review_router(state: PostState):
    if state["approved"]:
        return "finalize_post"

    if state["iteration"] >= state["max_iteration"]:
        return "finalize_post"

    return "regenerate_post"

# ===================== GRAPH =====================

graph = StateGraph(PostState)

graph.add_node("search_topic", search_topic)
graph.add_node("initial_generate_post", initial_generate_post)
graph.add_node("regenerate_post", regenerate_post)
graph.add_node("human_review", human_review)
graph.add_node("finalize_post", finalize_post)

graph.add_edge(START, "search_topic")
graph.add_edge("search_topic", "initial_generate_post")
graph.add_edge("initial_generate_post", "human_review")

graph.add_conditional_edges(
    "human_review",
    review_router,
    {
        "regenerate_post": "regenerate_post",
        "finalize_post": "finalize_post",
    }
)

graph.add_edge("regenerate_post", "human_review")
graph.add_edge("finalize_post", END)

# ===================== COMPILE =====================
conn = sqlite3.connect("LinkedIn_Post.db", check_same_thread=False)
workflow = graph.compile(checkpointer=SqliteSaver(conn))
'''
