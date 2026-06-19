import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import asyncio
from models.agent_models import FinalReport 
from models.state import AgentState
from groq import AsyncGroq
from dotenv import load_dotenv
import json
from pydantic import ValidationError

load_dotenv()
client = AsyncGroq()

async def run_synthesiser(state:AgentState)->dict:
    check_insight = state.get('insights', [])
    if not check_insight:
        return {
            'status':'failed',
            'error':'no insights found'
        }
    original_query = state['original_query']
    formatted = ""
    for i , insight in enumerate(check_insight):
        formatted += f"Insight {i+1}: {insight.claim}\n"
        formatted += f"Confidence: {insight.confidence}\n"
        formatted += f"Sources: {', '.join(insight.source)}\n\n"
    user_message = (
        f"Original User Query: {original_query}\n\n"
        f"Extracted Insights Database:\n"
        f"========================================\n"
        f"{formatted}"
        f"========================================\n"
        f"Synthesize the research insights above into the final JSON structural schema."
    )
    prompt = """you are a researching assistant and you can only give json output
                output shape must be 
                {
                    "title": "report title here",
                    "summary": must be strictly under 500 characters. Count carefully. Cut words if needed.",
                    "sections": [
                        {
                        "heading": "section heading",
                        "body": "minimum 50 characters of content",
                        "sources": ["https://source-url.com"]
                        }
                    ],"overall_confidence":0.85
                    }"""
    i = 0
    while i<3:
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
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            raw = json.loads(text)
            raw["insights"] = [insight.model_dump() for insight in state["insights"]]
            for section in raw.get("sections", []):
                section["sources"] = [
                    s for s in section.get("sources", [])
                    if s.startswith("http")
                ]
            if len(raw.get("summary", "")) > 490:
                raw["summary"] = raw["summary"][:490] + "..."
            validated_report = FinalReport.model_validate(raw)
            return  {
                        "final_report": validated_report,
                        "status": "synthesising"
            }
        except (ValidationError, json.JSONDecodeError) as e:
            print(f"failed as : {str(e)}")
            i += 1
            if i >= 3:
                return {
                "status":"failed",
                "error":f"validation error {str(e)}"
            }
            user_message = (
                f"Original User Query: {original_query}\n\n"
                f"Your last synthesis attempt failed validation with this error:\n"
                f"----------------------------------------\n"
                f"{str(e)}\n"
                f"----------------------------------------\n"
                f"Please regenerate the report JSON, ensuring formatting guidelines and lengths are precisely met."
            )
            await asyncio.sleep(1)
            continue
        except Exception as e:
            return {
                "status":"failed",
                "error" : f"this is the problem {str(e)}"
            }
        
