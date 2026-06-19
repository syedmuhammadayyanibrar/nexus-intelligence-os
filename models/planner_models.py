from pydantic import BaseModel , Field , field_validator
from enum import Enum
from typing import List , Literal

class Priority(str,Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SubQuestion(BaseModel):
    title : str = Field(min_length=1 ,max_length=300)
    priority : Priority
    search_items : List[str] = Field(min_length=1, max_length=5)

class ResearchPlan(BaseModel):
    original_query : str
    sub_questions : List[SubQuestion] = Field(min_length=2)
    depth : Literal["shallow" , "medium" ,"deep"]


    @field_validator('sub_questions')
    @classmethod
    def duplicate_subqestion(cls , v : List[SubQuestion])->List[SubQuestion]:
        lowercased = [q.title.lower().strip() for q in v]
        if len(lowercased) != len(set(lowercased)) :
            raise ValueError("there are some identical subquestions")
        return v

