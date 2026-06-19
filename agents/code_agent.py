import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import subprocess
from models.state import AgentState
import asyncio
from dotenv import load_dotenv
from groq import AsyncGroq,RateLimitError
import json
import time
from models.agent_models import CodeResults


load_dotenv()
client = AsyncGroq()



async def code_agent(state: AgentState)->dict:
    insights = state['insights']
    if insights is None:
        return {
            "status" : "failed",
            "error" : "insight does not exist"
        }
    insights_text = ""
    for i, insight in enumerate(state["insights"]):
        insights_text += f"Insight {i+1}: {insight.claim}\n"
        insights_text += f"Confidence: {insight.confidence}\n\n"
    user_message = (
        f"Research question: {state['original_query']}\n\n"
        f"Insights gathered:\n{insights_text}\n\n"
        f"Does this research require Python code for data analysis or calculations?\n"
        f"If yes, write the actual Python code to run."
    )
    prompt="""you are a researching agent your work is to check insights provided 
    and tell me if it needs python calculation if yes provide with the python code too 
     your response should follow the exact fomat as bellow:
     if needs code:
        {
            "needs_code": true,
            "reason": "need to calculate average screen time across studies",
            "code": "data = [2.3, 4.1, 3.8, 2.9]\nprint(f'Average: {sum(data)/len(data):.2f} hours')"
            }
            
    if does not need code:
        {
        "needs_code": false,
        "reason": "research is qualitative, no calculations needed",
        "code": ""
        }"""

    try:
        response = await client.chat.completions.create(
            model= "llama-3.1-8b-instant",
            max_tokens= 1000,
            messages=[
                {"role":"system", "content":prompt},
                {"role":"user","content":user_message}
            ]
        )

        raw_text = response.choices[0].message.content
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        text = json.loads(raw_text)
        if not text["needs_code"]:
            return {
                "code_result": None,
                "status": "extracting"
            }
        code = text["code"]

    except RateLimitError:
        await asyncio.sleep(15)
        return {
            "status":"failed",
            "error": "Rate limit hit, try again"
        }
    except (json.JSONDecodeError, KeyError) as e:
        return {"status": "failed", "error": f"LLM response error: {str(e)}"}
    

    start = time.time()
    try:
        proc = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=10
        )
        elapsed = int((time.time() - start) * 1000)
        result = CodeResults(
            code=code,
            stdout=proc.stdout,
            stderr=proc.stderr,
            success=proc.returncode == 0,
            execution_time_ms=elapsed
        )
    except subprocess.TimeoutExpired:
        result = CodeResults(
            code=code,
            stdout="",
            stderr="Timed out after 10 seconds",
            success=False,
            execution_time_ms=10000
        )

    return {
        "code_result": result,
        "status": "extracting"
    }







# Quick subprocess test — run directly, not through the full pipeline
async def test_subprocess():
    from models.agent_models import CodeResults
    import time
    
    code = "data = [2.3, 4.1, 3.8, 2.9]\nprint(f'Average: {sum(data)/len(data):.2f} hours')"
    
    start = time.time()
    proc = subprocess.run(
        ["python", "-c", code],
        capture_output=True,
        text=True,
        timeout=10
    )
    elapsed = int((time.time() - start) * 1000)
    result = CodeResults(
        code=code,
        stdout=proc.stdout,
        stderr=proc.stderr,
        success=proc.returncode == 0,
        execution_time_ms=elapsed
    )
    print(f"Success: {result.success}")
    print(f"Output: {result.stdout}")
    print(f"Time: {result.execution_time_ms}ms")

asyncio.run(test_subprocess())