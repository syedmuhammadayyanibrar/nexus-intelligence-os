import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from groq import AsyncGroq 
import os
import json
import asyncio
from pydantic import ValidationError
from models.state import AgentState
from models.planner_models import ResearchPlan
from dotenv import load_dotenv


load_dotenv()

async def run_planner(state:AgentState) -> dict:
    client = AsyncGroq()

    prompt = (
        """you are a research planning agent you can only provide valid json response 
        the json must match the exant structure
        {
            "original_query": "the user's question here",
            "sub_questions": [
                {
                "title": "a specific sub-question",
                "priority": "high",
                "search_items": ["term1", "term2", "term3"]
                },
                {
                "title": "another sub-question",
                "priority": "medium",
                "search_items": ["term1", "term2"]
                }
            ],
            "depth": "medium"
            }
            constraints:
            priority must be one of :'high','medium','low' nothing else 
            depth must be one of : 'shallow','medium','deep' nothing else
            sub_question must have atleast 2 items
            searach_items must have 1-5 items per subquestion       
        """
    )
    user_message = state["original_query"]
    i = 0
    validated_plan = None
    while i < 3:
        try:
            response = await client.chat.completions.create(
                model="llama-3.1-8b-instant",
                max_tokens=1000,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            text = response.choices[0].message.content
            validated_plan = ResearchPlan.model_validate_json(text)
            break
        except (ValidationError , json.JSONDecodeError) as e:
            i += 1
            if i >=3:
                return {
                    "status": "failed",
                    "error" : f"failed to generate valid response. Error: {str(e)}"
                }
            user_message = (
                f"Original query: {state['original_query']}\n\n"
                f"Your previous JSON response failed validation with this error:\n"
                f"----------------------------------------\n"
                f"{str(e)}\n"
                f"----------------------------------------\n"
                f"Please fix your structural/formatting constraints and try again."
            )

            await asyncio.sleep(1)
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Fatal error: {str(e)}"
            }


    return {
        "research_plan": validated_plan,
        "status": "planning"
    }

