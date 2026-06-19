import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import asyncio
from tavily import AsyncTavilyClient
from models.state import AgentState
from models.agent_models import SearchResults
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
    tavily_client = AsyncTavilyClient()

    async def search_sub_questions(sub_q:SubQuestion)->List[SearchResults]:
        combined = f"{state['original_query']} {sub_q.title}"

        try:
            response = await tavily_client.search(
                query=combined,
                search_depth="advanced",
                max_results=5
            )
            parsed_results = []

            for raw in response.get("results",[]):
                parsed_results.append(
                    SearchResults(
                        url=raw.get("url"),
                        title=raw.get("title", "Untitled"),
                        snippet=raw.get("content", ""), 
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

