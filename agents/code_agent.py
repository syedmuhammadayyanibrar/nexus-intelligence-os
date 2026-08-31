import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subprocess
import tempfile
from models.state import AgentState
import asyncio
from dotenv import load_dotenv
from groq import AsyncGroq, RateLimitError
import json
import time
from models.agent_models import CodeResults

load_dotenv()
client = AsyncGroq(timeout=180.0)


_SYSTEM_PROMPT = """You are a research data agent. Examine the insights and decide whether Python
code is needed for numerical calculations or visualisations.

If the research question involves numbers, comparisons, trends, statistics, or anything that
benefits from a chart, write Python code that:
  1. Performs the calculation.
  2. Builds a matplotlib chart (bar, line, or scatter - whichever fits best).
  3. Saves it with:  plt.savefig(CHART_PATH, dpi=150, bbox_inches='tight')
     where CHART_PATH is the exact string injected into the user message.
  4. Prints a one-line summary of the result to stdout.
  IMPORTANT: never call plt.show(). The script runs headless.

Return ONLY a JSON object - no markdown fences:
{
    "needs_code": true,
    "reason": "brief reason",
    "code": "...full python code..."
}

If no numerical analysis is needed:
{
    "needs_code": false,
    "reason": "research is qualitative",
    "code": ""
}"""


async def code_agent(state: AgentState) -> dict:
    insights = state.get("insights")
    if not insights:
        return {"code_result": None, "status": "extracting"}

    insights_text = ""
    for i, insight in enumerate(insights[:15]):
        insights_text += f"Insight {i+1}: {insight.claim[:400]}\\n"
        insights_text += f"Confidence: {insight.confidence}\n\n"

    # generate temp path BEFORE calling LLM so it can hardcode it
    chart_path = os.path.join(
        tempfile.gettempdir(),
        f"nexus_chart_{int(time.time())}.png"
    ).replace("\\", "/")

    user_message = (
        f"Research question: {state['original_query']}\n\n"
        f"Insights gathered:\n{insights_text}\n"
        f"CHART_PATH = \"{chart_path}\"\n\n"
        f"Does this research require Python code for data analysis or a chart?\n"
        f"If yes, write the actual Python code to run."
    )

    code = None
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                max_tokens=1500,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )

            raw_text = response.choices[0].message.content.strip()
            import re
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                raw_text = match.group(0)

            import json_repair
            parsed = json_repair.loads(raw_text)
            if isinstance(parsed, list) and len(parsed) > 0:
                parsed = parsed[0]
            if not isinstance(parsed, dict):
                parsed = {}

            if not parsed.get("needs_code"):
                return {"code_result": None, "status": "extracting"}

            code = parsed["code"]
            break

        except RateLimitError:
            await asyncio.sleep(65)
            if attempt == 2:
                return {"status": "failed", "error": "Rate limit hit, try again"}
        except (json.JSONDecodeError, KeyError) as e:
            await asyncio.sleep(2)
            if attempt == 2:
                return {"status": "failed", "error": f"LLM response error: {str(e)}"}

    # run the generated code in a subprocess
    start = time.time()
    try:
        proc = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "MPLBACKEND": "Agg"},
        )
        elapsed = int((time.time() - start) * 1000)

        # detect whether a chart was actually saved
        saved_chart = chart_path if os.path.exists(chart_path) else None

        result = CodeResults(
            code=code,
            stdout=proc.stdout,
            stderr=proc.stderr,
            success=proc.returncode == 0,
            execution_time_ms=elapsed,
            chart_path=saved_chart,
        )
    except subprocess.TimeoutExpired:
        result = CodeResults(
            code=code,
            stdout="",
            stderr="Timed out after 15 seconds",
            success=False,
            execution_time_ms=15000,
            chart_path=None,
        )

    return {"code_result": result, "status": "extracting"}


if __name__ == "__main__":
    async def _test():
        fake_state = {
            "original_query": "Compare average screen time across age groups: 13-17 avg 7h, 18-24 avg 5h, 25-34 avg 3h",
            "insights": [],
            "status": "extracting",
        }
        result = await code_agent(fake_state)
        cr = result.get("code_result")
        if cr:
            print("success:", cr.success)
            print("stdout:", cr.stdout)
            print("chart_path:", cr.chart_path)
        else:
            print("no code needed")

    asyncio.run(_test())
