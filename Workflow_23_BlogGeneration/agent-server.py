# langgraph_a2a/agent_server.py

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCard, AgentCapabilities, AgentSkill, Task, TaskState
from a2a.utils import new_task, new_agent_text_message

# Import your compiled LangGraph app
from your_langgraph_module.agent import app as langgraph_app  # adjust import path


# ─────────────────────────────────────────
# 1. AgentExecutor — bridge between A2A and LangGraph
# ─────────────────────────────────────────

class LangGraphBlogAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = langgraph_app  # your compiled LangGraph StateGraph

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = context.get_user_input()
        task: Task = context.current_task

        if not task:
            task = new_task(context.message)
            event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.contextId)
        updater.update_status(TaskState.working, message=updater.new_agent_message(
            parts=[{"kind": "text", "text": "Writing blog post..."}]
        ))

        try:
            # Invoke the LangGraph pipeline
            result = self.agent.invoke({
                "topic": query,
                "mode": "",
                "needs_research": False,
                "queries": [],
                "evidence": [],
                "plan": None,
                "sections": [],
                "final": "",
            })

            final_md = result.get("final", "No output generated.")

            updater.add_artifact(
                parts=[{"kind": "text", "text": final_md}],
                artifact_id="blog-output",
                name="Blog Post",
            )
            updater.complete()

        except Exception as e:
            updater.update_status(
                TaskState.failed,
                message=updater.new_agent_message(
                    parts=[{"kind": "text", "text": f"Error: {str(e)}"}]
                ),
            )
            raise


# ─────────────────────────────────────────
# 2. Agent Card — metadata for discovery
# ─────────────────────────────────────────

def get_agent_card(host: str = "localhost", port: int = 8002) -> AgentCard:
    return AgentCard(
        name="langgraph_blog_agent",
        description="LangGraph-powered agent that writes technical blog posts",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="write_blog",
                name="write_blog",
                description="Write a technical blog post on any topic",
                tags=["blog", "writing", "research"],
                examples=["Write a blog on Self Attention"],
            )
        ],
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
    )


# ─────────────────────────────────────────
# 3. Wire up the A2A server
# ─────────────────────────────────────────

def build_a2a_server(host: str = "localhost", port: int = 8002):
    agent_card = get_agent_card(host, port)

    request_handler = DefaultRequestHandler(
        agent_executor=LangGraphBlogAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    return server.build()


if __name__ == "__main__":
    uvicorn.run(build_a2a_server(), host="localhost", port=8002)
    # Run: python -m langgraph_a2a.agent_server
