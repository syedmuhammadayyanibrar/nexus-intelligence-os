import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import asyncio
import uuid
import json

app = FastAPI()

# store active jobs
jobs = {}

class ResearchRequest(BaseModel):
    query: str

class AgentProgressEvent(BaseModel):
    agent: str
    status: str
    message: str
    data: dict = {}


NODE_MESSAGES = {
    "read_memory": "Reading long-term memory for related past research",
    "planner": "Breaking the question into sub-questions",
    "search_and_rag": "Searching the web and querying the knowledge base",
    "extractor": "Extracting and validating key insights from sources",
    "code_agent": "Checking whether calculations are needed",
    "synthesiser": "Writing the structured research report",
    "critic": "Grading report quality and deciding on a rewrite",
    "write_memory": "Saving new insights to long-term memory",
}


@app.post("/research")
async def start_research(request: ResearchRequest):
    job_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    jobs[job_id] = queue

    # run pipeline in background
    asyncio.create_task(run_pipeline(request.query, queue))

    return {"job_id": job_id}


def serialize_report(report):
    if report is None:
        return None
    return {
        "title": report.title,
        "summary": report.summary,
        "overall_confidence": report.overall_confidence,
        "total_sources": report.total_sources,
        "sections": [
            {
                "heading": s.heading,
                "body": s.body,
                "sources": [str(u) for u in s.sources],
            }
            for s in report.sections
        ],
    }


async def run_pipeline(query: str, queue: asyncio.Queue):
    from graph.nexus_graph import nexus_app

    initial_state = {
        "original_query": query,
        "research_plan": None,
        "search_results": None,
        "insights": None,
        "final_report": None,
        "code_result": None,
        "rag_context": None,
        "critique": None,
        "retry_count": 0,
        "approved": None,
        "status": "planning",
        "error": None,
    }

    await queue.put(AgentProgressEvent(
        agent="system",
        status="started",
        message="Pipeline started",
    ).model_dump())

    final_report = None
    error_msg = None

    try:
        # astream yields {node_name: partial_update} after each node runs,
        # so we can stream real per-agent progress instead of one blocking call.
        async for chunk in nexus_app.astream(initial_state):
            for node_name, update in chunk.items():
                data = {}

                if isinstance(update, dict):
                    if update.get("final_report") is not None:
                        final_report = update["final_report"]

                    critique = update.get("critique")
                    if critique is not None:
                        data = {
                            "passed": critique.passed,
                            "evidence_score": critique.evidence_score,
                            "coherence_score": critique.coherence_score,
                            "coverage_score": critique.coverage_score,
                            "feedback": critique.feedback,
                        }

                    if update.get("status") == "failed":
                        error_msg = update.get("error", "unknown error")

                await queue.put(AgentProgressEvent(
                    agent=node_name,
                    status="running",
                    message=NODE_MESSAGES.get(node_name, f"{node_name} finished"),
                    data=data,
                ).model_dump())

        if final_report is None:
            await queue.put(AgentProgressEvent(
                agent="system",
                status="failed",
                message=error_msg or "Pipeline finished without producing a report",
            ).model_dump())
        else:
            await queue.put(AgentProgressEvent(
                agent="system",
                status="completed",
                message="Research complete",
                data=serialize_report(final_report),
            ).model_dump())

    except Exception as e:
        await queue.put(AgentProgressEvent(
            agent="system",
            status="failed",
            message=str(e),
        ).model_dump())
    finally:
        await queue.put(None)  # signal stream end


@app.get("/research/{job_id}/stream")
async def stream_progress(job_id: str):
    if job_id not in jobs:
        return {"error": "job not found"}

    queue = jobs[job_id]

    async def event_generator():
        try:
            while True:
                event = await queue.get()
                if event is None:  # end signal
                    break
                yield {"data": json.dumps(event)}
        finally:
            jobs.pop(job_id, None)  # clean up finished job

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)