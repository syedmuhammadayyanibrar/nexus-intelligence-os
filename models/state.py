from typing import TypedDict , Literal , Optional ,List
from models.planner_models import ResearchPlan
from models.agent_models import SearchResults, Insights, CritiqueResult, FinalReport


class AgentState(TypedDict):
    original_query :str
    research_plan : Optional[ResearchPlan]
    search_results : Optional[List[SearchResults]]
    insights : Optional[List[Insights]]
    critique : Optional[CritiqueResult]
    final_report : Optional[FinalReport]
    retry_count : int
    approved : Optional[bool]
    status : Literal["planning", "searching", "extracting","synthesising", "critiquing", "approved", "failed"]
    error : Optional[str]