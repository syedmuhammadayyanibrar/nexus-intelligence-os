import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



import asyncio
from langgraph.graph import StateGraph , END
from models.state import AgentState
from agents.planner import run_planner
from agents.searcher import run_searcher
from agents.extractor import run_extractor
from agents.code_agent import code_agent
from agents.synthesiser import run_synthesiser
from agents.critic import run_critic
from agents.memory import read_memory , write_memory
from agents.rag import run_rag

async def search_and_rag(state: AgentState) -> dict:
    search_result, rag_result = await asyncio.gather(
        run_searcher(state),
        run_rag(state)
    )
    return {
        **search_result,
        **rag_result
    }

def should_continue(state : AgentState)->str:
    if state["status"]=="approved":
        return "end"
    if state.get("retry_count",0)>=3:
        return "end"
    return "planner"


graph = StateGraph(AgentState)
graph.add_node("read_memory", read_memory)
graph.add_node("planner", run_planner)
graph.add_node("search_and_rag", search_and_rag)
graph.add_node("extractor", run_extractor)
graph.add_node("code_agent", code_agent)
graph.add_node("synthesiser", run_synthesiser)
graph.add_node("critic", run_critic)
graph.add_node("write_memory", write_memory)

graph.add_edge("read_memory", "planner")
graph.add_edge("planner", "search_and_rag")
graph.add_edge("search_and_rag", "extractor")
graph.add_edge("extractor", "code_agent")
graph.add_edge("code_agent", "synthesiser")
graph.add_edge("synthesiser", "critic")

def should_continue(state: AgentState) -> str:
    if state["status"] == "approved":
        return "write_memory"
    if state.get("retry_count", 0) >= 3:
        return "write_memory"
    return "planner"

graph.add_conditional_edges(
    "critic",
    should_continue,
    {
        "write_memory": "write_memory",
        "planner": "planner"
    }
)

graph.add_edge("write_memory", END)
graph.set_entry_point("read_memory")
nexus_app = graph.compile()




if __name__ == "__main__":
    async def test():
        initial_state = {
            "original_query": "What are the long term effects of social media on teenagers?",
            "research_plan": None,
            "search_results": None,
            "insights": None,
            "final_report": None,
            "code_result": None,
            "critique": None,
            "retry_count": 0,
            "approved": None,
            "status": "planning",
            "error": None
        }
        result = await nexus_app.ainvoke(initial_state)
        print(f"Final status: {result['status']}")
        report = result['final_report']
        print(f"Title: {report.title}")
        print(f"Sections: {len(report.sections)}")
        print(f"Total sources: {report.total_sources}")
        critique = result.get('critique')
        if critique:
            print(f"Evidence: {critique.evidence_score}")
            print(f"Coverage: {critique.coverage_score}")
            print(f"Feedback: {critique.feedback}")

    asyncio.run(test())