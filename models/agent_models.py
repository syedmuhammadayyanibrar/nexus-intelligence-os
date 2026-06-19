from pydantic import AnyHttpUrl , BaseModel ,Field , field_validator , model_validator , computed_field
from typing import Literal , List , Annotated , Union


class SearchResults(BaseModel):
    url : AnyHttpUrl
    title : str = Field(min_length=2 , max_length=200)
    snippet : str 
    relevance : float = Field(ge=0,le=1)
    source_type : Literal["web","academic","news","docs"]
    @field_validator("snippet")
    @classmethod
    def white_space(cls,v:str)->str:
        return v.replace("\n", " ").strip()
    
class Insights(BaseModel):
    claim :str
    confidence : float
    source : List[str] = Field(min_length=1)
    contradictions : List[str] = Field(default_factory=list)
    @model_validator(mode= "after")
    def my_check(self):
        if self.confidence>0.8 and len(self.source)<2:
            raise ValueError("resources are not enough to support this")
        return self
class CritiqueResult(BaseModel):
    passed : bool
    evidence_score : float = Field(ge=0,le=1)
    coherence_score : float = Field(ge=0,le=1)
    coverage_score : float = Field(ge=0,le=1)
    feedback : str
    @model_validator(mode="after")
    def ifpassed(self):
        if self.passed == True and (self.evidence_score < 0.6 or self.coherence_score<0.6 or self.coverage_score<0.6):
            raise ValueError("scores are weak")
        return self

class ReportSection(BaseModel):
    heading : str
    body : str = Field(min_length=50)
    sources : List[AnyHttpUrl]

class FinalReport(BaseModel):
    title:str
    summary:str = Field(max_length=500)
    sections : List[ReportSection] = Field(min_length=1)
    insights : List[Insights]
    overall_confidence : float = Field(ge=0,le=1)

    @computed_field
    @property
    def total_sources(self)->int:
        unique_sources = {
            str(url).strip()
            for source in self.sections 
            for url in source.sources 
            if str(url).strip()
        }
        return len(unique_sources)
    
class DeepAnalysis(BaseModel):
    action : Literal["deep"] = "deep"
    focus : List[str]

class QuickScan(BaseModel):
    action: Literal["quick"] = "quick"
    max_result : int

Analyst_task = Annotated[Union[DeepAnalysis , QuickScan],Field(discriminator='action')]


class CodeResults(BaseModel):
    code : str
    stdout: str
    stderr : str
    success : bool
    execution_time_ms : int = Field(ge=0)