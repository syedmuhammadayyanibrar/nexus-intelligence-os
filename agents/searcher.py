import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import asyncio
from tavily import AsyncTavilyClient
from models.state import AgentState
from models.agent_models import SearchResults , QuickScan , DeepAnalysis
from typing import List
from models.planner_models import SubQuestion



load_dotenv()

async def run_searcher(state:AgentState)->dict:
    plan = state["research_plan"]

    if plan is None:
        return {
            "status":"failed",
            "error":"Exection Error:No valid research plan found"
        }
    if not os.getenv("TAVILY_API_KEY"):
        return {
            "status": "failed",
            "error": "Initialization Error: TAVILY_API_KEY is not set in the environment variables."
        }

    # --- Resolve search config from analyst_task ---
    analyst_task = state.get("analyst_task", None)
    max_results = 5          # default
    search_depth = "advanced"  # default
    focus_areas: List[str] = []

    if isinstance(analyst_task, QuickScan):
        max_results = analyst_task.max_result
        search_depth = "basic"
    elif isinstance(analyst_task, DeepAnalysis):
        max_results = 8
        search_depth = "advanced"
        focus_areas = analyst_task.focus

    tavily_client = AsyncTavilyClient()

    async def search_sub_questions(sub_q:SubQuestion)->List[SearchResults]:
        # For DeepAnalysis, append focus areas to the query to guide results
        focus_suffix = " ".join(focus_areas)
        search_terms = " ".join(sub_q.search_items)
        
        combined = f"{state['original_query']} {sub_q.title} {focus_suffix}".strip()

        try:
            response = await tavily_client.search(
                query=combined,
                search_depth=search_depth,
                max_results=max_results
            )
            parsed_results = []

            for raw in response.get("results",[]):
                parsed_results.append(
                    SearchResults(
                        url=raw.get("url"),
                        title=raw.get("title", "Untitled"),
                        snippet=raw.get("content", "")[:800], 
                        relevance=raw.get("score", 0.0),
                        source_type="web"
                    )
                )
            return parsed_results
        except Exception as e:
            print(f"worker thread failed for query {sub_q.title}")
            return []
        

    tasks = [search_sub_questions(sub_q) for sub_q in plan.sub_questions]
    results = await asyncio.gather(*tasks)

    flattened = [
        result
        for sublist in results
        for result in sublist
    ]


    return {
        "search_results" : flattened,
        "status":"searching"
    }
