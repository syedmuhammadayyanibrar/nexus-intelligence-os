import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from groq import AsyncGroq , RateLimitError
from dotenv import load_dotenv
from models.state import AgentState
from models.agent_models import CritiqueResult
import json
import asyncio
from pydantic import ValidationError

load_dotenv()
client = AsyncGroq()


async def run_critic(state: AgentState)->dict:
    if state.get("retry_count", 0) >= 3:
        print("Max retries reached, passing report as-is")
        return {
        "status": "approved",
        "critique": None
    }
    report = state['final_report']
    if report is None:
        return {
            "status":"failed",
            "error" : "no final report present"
        }
    formatted = f"Title: {report.title}\n\n"
    formatted += f"Summary: {report.summary}\n\n"
    for section in report.sections:
        formatted += f"Section: {section.heading}\n"
        formatted += f"{section.body}\n\n"

    prompt = """You are a research quality critic. Evaluate the research report provided and return only a valid JSON object with no markdown.

    Score the report on three axes:
    - evidence_score: how well claims are supported by sources (0.0 to 1.0)
    - coherence_score: how logical and well-structured the writing is (0.0 to 1.0)  
    - coverage_score: how thoroughly the original question was answered (0.0 to 1.0)

    Rules:
    - All scores must be floats between 0.0 and 1.0
    - passed must be true only if ALL three scores are above 0.6
    - passed must be false if ANY score is 0.6 or below
    - feedback must be one specific sentence about the weakest area, not generic praise it shold be thorough to understand the outcomes of research about the question

    Return this exact shape:
    {
    "passed": true,
    "evidence_score": 0.85,
    "coherence_score": 0.80,
    "coverage_score": 0.75,
    "feedback": "necessary feedback"
    }"""
    user_message = f"Evaluate this research report:\n\n{formatted}"

    i = 0
    while (i<3):
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
            validated_critique = CritiqueResult.model_validate(raw)
            if validated_critique.passed:
                return {
                    "critique": validated_critique,
                    "status":"approved"
                }
            else:
                return {
                    "critique": validated_critique,
                    "retry_count":state['retry_count']+1,
                    "status":"critiquing"
                }
        except RateLimitError:
            print("rate limit hit waiting for 15 seaconds")
            await asyncio.sleep(15)
            continue
        except (ValidationError , json.JSONDecodeError):
            i+=1
            if i>=3:
                return{
                    "status":"failed"
                }
            



if __name__ == "__main__":
    async def test():
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from agents.planner import run_planner
        from agents.searcher import run_searcher
        from agents.extractor import run_extractor
        from agents.synthesiser import run_synthesiser

        state = {
            "original_query": "What are the long term effects of social media on teenagers?",
            "research_plan": None,
            "search_results": None,
            "insights": None,
            "final_report": None,
            "retry_count": 0,
            "status": "planning"
        }

        state.update(await run_planner(state))
        await asyncio.sleep(3)
        state.update(await run_searcher(state))
        await asyncio.sleep(3)
        state.update(await run_extractor(state))
        await asyncio.sleep(5)
        state.update(await run_synthesiser(state))
        await asyncio.sleep(3)
        result = await run_critic(state)
        print(f"Status: {result['status']}")
        print(f"Critique: {result.get('critique')}")
        print(f"Retry count: {result.get('retry_count', 0)}")

    asyncio.run(test())