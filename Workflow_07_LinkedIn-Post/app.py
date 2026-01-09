from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from workflow import workflow
from schemas import ApprovalRequest

app = FastAPI()

# ===================== CORS =====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

THREAD_ID = "linkedin-post-1"

# ===================== ROUTES =====================

@app.post("/start")
def start(topic: str):
    return workflow.invoke(
        {
            "topic": topic,
            "search": "",
            "post": "",
            "suggestion": "",
            "approved": False,
            "iteration": 0,
            "max_iteration": 4,
        },
        config={"configurable": {"thread_id": THREAD_ID}},
    )


@app.get("/pending")
def pending():
    state = workflow.get_state(
        {"configurable": {"thread_id": THREAD_ID}}
    )

    if not state.interrupts:
        return {"status": "No pending approval"}

    return state.interrupts[0]


@app.post("/approve")
def approve(data: ApprovalRequest):
    return workflow.invoke(
        {
            "approved": data.approved,
            "suggestion": data.suggestion or "",
        },
        config={"configurable": {"thread_id": THREAD_ID}},
    )
