# main.py
# FastAPI backend — Blog Generation + HITL Approval Workflow
# Endpoints: Generate, View, Approve, Reject, Update (manual edit), Delete, List

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

# ──────────────────────────────────────────────────────────────
# aiosqlite 0.22+ compatibility patch for LangGraph
# ──────────────────────────────────────────────────────────────
import aiosqlite

def _aiosqlite_is_alive_patch(self) -> bool:
    if getattr(self, "_closed", False) or getattr(self, "closed", False):
        return False
    return True

if not hasattr(aiosqlite.Connection, "is_alive"):
    aiosqlite.Connection.is_alive = _aiosqlite_is_alive_patch
    print("✅ Applied aiosqlite.Connection.is_alive patch (LangGraph compatibility)")

# ──────────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from config  import HITL_DB, BLOGS_DIR
from logger  import get_logger
from database import init_db, get_db, BlogPost, BlogStatus
from agent   import build_workflow, State

logger = get_logger("FastAPI")


# ──────────────────────────────────────────────────────────────
# App lifecycle
# ──────────────────────────────────────────────────────────────

workflow = None   # compiled LangGraph workflow — populated in lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    global workflow
    await init_db()
    logger.info("[STARTUP] PostgreSQL tables ready.")

    async with AsyncSqliteSaver.from_conn_string(HITL_DB) as checkpointer:
        workflow = build_workflow(checkpointer)
        logger.info(f"[STARTUP] LangGraph workflow compiled. Checkpointer DB: '{HITL_DB}'")
        yield

    logger.info("[SHUTDOWN] Application shutting down.")


app = FastAPI(
    title="Blog Generation API",
    description=(
        "AI-powered blog generation with Human-in-the-Loop approval.\n\n"
        "Generated blogs are saved as HTML/CSS/JS under the Blogs/ folder "
        "and listed on the home page only after human approval."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────
# Request / Response Schemas
# ──────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    topic: str


class GenerateResponse(BaseModel):
    thread_id: str
    blog_id:   int
    status:    str
    message:   str


class ApproveRequest(BaseModel):
    thread_id: str


class RejectRequest(BaseModel):
    thread_id:        str
    rejection_reason: Optional[str] = "No reason provided."


class UpdateBlogRequest(BaseModel):
    blog_title: Optional[str] = None
    content: str


class BlogResponse(BaseModel):
    id:               int
    thread_id:        str
    topic:            str
    blog_title:       Optional[str]
    content:          Optional[str]
    status:           str
    rejection_reason: Optional[str]
    created_at:       Optional[str]
    updated_at:       Optional[str]
    approved_at:      Optional[str]
    rejected_at:      Optional[str]


class StatusResponse(BaseModel):
    thread_id: str
    status:    str
    next:      list
    message:   str


# ──────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────

async def _update_blog(db: AsyncSession, thread_id: str, **values) -> None:
    """Single helper for all Postgres blog-post field updates."""
    values["updated_at"] = datetime.now(timezone.utc)
    await db.execute(
        update(BlogPost).where(BlogPost.thread_id == thread_id).values(**values)
    )
    await db.commit()


async def _validate_pending_blog(thread_id: str, db: AsyncSession):
    """
    Guard used by approve and reject endpoints.
    Returns (blog, config) when valid; raises HTTPException otherwise.
    """
    result = await db.execute(select(BlogPost).where(BlogPost.thread_id == thread_id))
    blog   = result.scalar_one_or_none()
    if blog is None:
        raise HTTPException(status_code=404, detail=f"Blog '{thread_id}' not found.")
    if blog.status != BlogStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Blog is not in PENDING state (current: {blog.status.value})."
        )
    config     = {"configurable": {"thread_id": thread_id}}
    state      = await workflow.aget_state(config)
    next_nodes = list(state.next) if state.next else []
    if "human_approval" not in next_nodes:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow is not paused at human_approval. next={next_nodes}"
        )
    return blog, config


# ──────────────────────────────────────────────────────────────
# Background tasks
# ──────────────────────────────────────────────────────────────

async def _run_workflow(thread_id: str, topic: str, db: AsyncSession) -> None:
    """
    Initial workflow run — executes until the HITL checkpoint pauses it.
    Updates blog title and content in Postgres as nodes produce them.
    """
    config = {"configurable": {"thread_id": thread_id}}
    try:
        logger.info(f"[BG] Starting workflow thread='{thread_id}' topic='{topic}'")

        async for event in workflow.astream(
            {
                "topic":            topic,
                "mode":             "",
                "needs_research":   False,
                "queries":          [],
                "evidence":         [],
                "plan":             None,
                "sections":         [],
                "final":            "",
                "approval_status":  None,
                "rejection_reason": None,
            },
            config=config,
            stream_mode="values",
        ):
            plan   = event.get("plan")
            merged = event.get("merged_md") or event.get("final") or ""
            if plan or merged:
                await _update_blog(
                    db, thread_id,
                    blog_title=plan.blog_title if plan else None,
                    content=merged or None,
                )

        state = await workflow.aget_state(config)
        logger.info(f"[BG] Workflow paused. next={state.next} thread='{thread_id}'")
        # Ensure status is PENDING (it should already be, but make it explicit)
        await _update_blog(db, thread_id, status=BlogStatus.PENDING)
        logger.info(f"[BG] Postgres → PENDING  thread='{thread_id}'")

    except Exception as e:
        logger.error(f"[BG] Workflow FAILED thread='{thread_id}': {e}", exc_info=True)
        # Keep status as PENDING so the operator can investigate;
        # a failed workflow won't be at the human_approval node so
        # approve/reject will gracefully reject it.


async def _resume_workflow(thread_id: str, db: AsyncSession) -> None:
    """
    Resume the workflow after human decision (approve or reject).
    Runs finalize_approved (publishes to Blogs/) or handle_rejection.
    """
    config = {"configurable": {"thread_id": thread_id}}
    try:
        logger.info(f"[BG] Resuming workflow thread='{thread_id}'")

        async for event in workflow.astream(None, config=config, stream_mode="values"):
            # handle_rejection returns a final rejection message; capture it
            final = event.get("final")
            if final:
                await _update_blog(db, thread_id, content=final)

        # Determine outcome from the stored approval status
        state           = await workflow.aget_state(config)
        approval_status = state.values.get("approval_status", "").lower()

        if approval_status == "approved":
            await _update_blog(db, thread_id, approved_at=datetime.now(timezone.utc))
            logger.info(f"[BG] Workflow finalized (approved) thread='{thread_id}'")
        else:
            logger.info(f"[BG] Workflow finalized (rejected) thread='{thread_id}'")

    except Exception as e:
        logger.error(f"[BG] Resume FAILED thread='{thread_id}': {e}", exc_info=True)


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────

@app.post("/blogs/generate", response_model=GenerateResponse, status_code=202)
async def generate_blog(
    request:          GenerateRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
):
    """
    Start blog generation for a given topic.
    Returns immediately with a thread_id; the workflow runs in the background
    and pauses at the HITL checkpoint waiting for human approval.
    """
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")

    thread_id = str(uuid.uuid4())

    blog = BlogPost(
        thread_id=thread_id,
        topic=request.topic.strip(),
        status=BlogStatus.PENDING,
    )
    db.add(blog)
    await db.commit()
    await db.refresh(blog)

    logger.info(f"[API] /blogs/generate — topic='{request.topic}' thread_id='{thread_id}'")
    background_tasks.add_task(_run_workflow, thread_id, request.topic.strip(), db)

    return GenerateResponse(
        thread_id=thread_id,
        blog_id=blog.id,
        status=BlogStatus.PENDING.value,
        message="Blog generation started. Workflow will pause for human approval.",
    )


@app.get("/blogs", response_model=list[BlogResponse])
async def list_blogs(
    status: Optional[str] = None,
    limit:  int           = 20,
    offset: int           = 0,
    db:     AsyncSession  = Depends(get_db),
):
    """
    List all blogs, optionally filtered by status (PENDING / APPROVED / REJECTED).
    Results are ordered newest-first.
    """
    query = select(BlogPost).order_by(BlogPost.created_at.desc()).limit(limit).offset(offset)

    if status:
        try:
            status_enum = BlogStatus(status.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {[s.value for s in BlogStatus]}"
            )
        query = query.where(BlogPost.status == status_enum)

    result = await db.execute(query)
    blogs  = result.scalars().all()
    return [BlogResponse(**b.to_dict()) for b in blogs]


@app.get("/blogs/{thread_id}", response_model=BlogResponse)
async def get_blog(thread_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch full blog record from Postgres by thread_id."""
    result = await db.execute(select(BlogPost).where(BlogPost.thread_id == thread_id))
    blog   = result.scalar_one_or_none()
    if blog is None:
        raise HTTPException(status_code=404, detail=f"Blog '{thread_id}' not found.")
    return BlogResponse(**blog.to_dict())


@app.get("/blogs/{thread_id}/content")
async def get_blog_content(thread_id: str, db: AsyncSession = Depends(get_db)):
    """Return only the markdown content of a blog (for preview before approval)."""
    result = await db.execute(select(BlogPost).where(BlogPost.thread_id == thread_id))
    blog   = result.scalar_one_or_none()
    if blog is None:
        raise HTTPException(status_code=404, detail=f"Blog '{thread_id}' not found.")
    if not blog.content:
        raise HTTPException(status_code=404, detail="Blog content not yet available.")
    return {"thread_id": thread_id, "blog_title": blog.blog_title, "content": blog.content}


@app.get("/blogs/{thread_id}/status", response_model=StatusResponse)
async def get_blog_status(thread_id: str):
    """Check the current LangGraph workflow state for a thread."""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await workflow.aget_state(config)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found or error: {e}")

    if state is None:
        raise HTTPException(status_code=404, detail=f"No state found for thread_id='{thread_id}'")

    next_nodes = list(state.next) if state.next else []

    if not next_nodes:
        msg = "Workflow completed."
    elif "human_approval" in next_nodes:
        msg = "Workflow paused — awaiting human approval."
    else:
        msg = f"Workflow running — next: {next_nodes}"

    return StatusResponse(
        thread_id=thread_id,
        status="paused" if next_nodes else "completed",
        next=next_nodes,
        message=msg,
    )


@app.post("/blogs/approve", status_code=200)
async def approve_blog(
    request:          ApproveRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
):
    """
    Approve a PENDING blog.
    Resumes the workflow which will publish the blog to Blogs/index.html.
    """
    thread_id = request.thread_id
    _, config = await _validate_pending_blog(thread_id, db)

    logger.info(f"[API] /blogs/approve — thread_id='{thread_id}'")

    await workflow.aupdate_state(
        config,
        {"approval_status": "approved", "rejection_reason": None},
        as_node="human_approval",
    )
    await _update_blog(db, thread_id, status=BlogStatus.APPROVED)
    background_tasks.add_task(_resume_workflow, thread_id, db)

    return {
        "thread_id": thread_id,
        "status":    BlogStatus.APPROVED.value,
        "message":   (
            "Blog approved. Workflow resuming — blog will be published "
            f"to {BLOGS_DIR}/index.html."
        ),
    }


@app.post("/blogs/reject", status_code=200)
async def reject_blog(
    request:          RejectRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
):
    """Reject a PENDING blog with an optional reason."""
    thread_id = request.thread_id
    reason    = request.rejection_reason or "No reason provided."
    _, config = await _validate_pending_blog(thread_id, db)

    logger.info(f"[API] /blogs/reject — thread_id='{thread_id}' reason='{reason}'")

    await workflow.aupdate_state(
        config,
        {"approval_status": "rejected", "rejection_reason": reason},
        as_node="human_approval",
    )
    await _update_blog(
        db, thread_id,
        status=BlogStatus.REJECTED,
        rejection_reason=reason,
        rejected_at=datetime.now(timezone.utc),
    )
    background_tasks.add_task(_resume_workflow, thread_id, db)

    return {
        "thread_id": thread_id,
        "status":    BlogStatus.REJECTED.value,
        "message":   f"Blog rejected. Reason: {reason}",
    }


@app.put("/blogs/{thread_id}", response_model=BlogResponse)
async def update_blog(
    thread_id: str,
    request:   UpdateBlogRequest,
    db:        AsyncSession = Depends(get_db),
):
    """Manually update blog title and/or content (editorial override)."""
    result = await db.execute(select(BlogPost).where(BlogPost.thread_id == thread_id))
    blog   = result.scalar_one_or_none()
    if blog is None:
        raise HTTPException(status_code=404, detail=f"Blog '{thread_id}' not found.")

    update_values = {"content": request.content}
    if request.blog_title:
        update_values["blog_title"] = request.blog_title

    await _update_blog(db, thread_id, **update_values)

    result       = await db.execute(select(BlogPost).where(BlogPost.thread_id == thread_id))
    updated_blog = result.scalar_one_or_none()

    logger.info(f"[API] Blog updated manually — thread_id='{thread_id}'")
    return BlogResponse(**updated_blog.to_dict())


@app.delete("/blogs/{thread_id}", status_code=200)
async def delete_blog(thread_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a blog post record from PostgreSQL."""
    result = await db.execute(select(BlogPost).where(BlogPost.thread_id == thread_id))
    blog   = result.scalar_one_or_none()
    if blog is None:
        raise HTTPException(status_code=404, detail=f"Blog '{thread_id}' not found.")

    await db.execute(delete(BlogPost).where(BlogPost.thread_id == thread_id))
    await db.commit()

    logger.info(f"[API] Blog deleted — thread_id='{thread_id}'")
    return {"message": f"Blog '{thread_id}' successfully deleted."}


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ──────────────────────────────────────────────────────────────
# Static file serving — Blogs/ website
# ──────────────────────────────────────────────────────────────
#
# The Blogs/ directory is mounted at /site so the generated website
# is browsable at:
#   http://localhost:8000/site/index.html
#   http://localhost:8000/site/contents/html/<slug>.html
#
# Note: /blogs is reserved for the REST API above.

_blogs_abs = os.path.join(os.path.dirname(os.path.abspath(__file__)), BLOGS_DIR)
os.makedirs(_blogs_abs, exist_ok=True)   # ensure dir exists before mounting

app.mount(
    "/site",
    StaticFiles(directory=_blogs_abs, html=True),
    name="blog_site",
)
logger.info(f"[STARTUP] Static site mounted: {_blogs_abs} → /site")
