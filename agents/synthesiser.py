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
client = AsyncGroq(timeout=180.0)

async def run_synthesiser(state: AgentState) -> dict:
    check_insight = state.get('insights', [])
    if not check_insight:
        return {
            'status': 'failed',
            'error': 'no insights found'
        }
    original_query = state['original_query']

    formatted = ""
    for i, insight in enumerate(check_insight[:15]):
        formatted += f"Insight {i+1}: {insight.claim[:400]}\\n"
        formatted += f"Confidence: {insight.confidence}\n"
        formatted += f"Sources: {', '.join(insight.source)}\n\n"

    # feed prior critic feedback back in on retries so the rewrite actually improves
    critique = state.get("critique")
    feedback_block = ""
    if critique is not None and getattr(critique, "feedback", None):
        feedback_block = (
            f"\nA previous version of this report was rejected by the quality critic.\n"
            f"Weakest area feedback: {critique.feedback}\n"
            f"Evidence: {critique.evidence_score}, Coherence: {critique.coherence_score}, "
            f"Coverage: {critique.coverage_score}\n"
            f"Directly address and fix these weaknesses in this new version.\n"
        )

    # inject chart reference so the LLM can cite it in the relevant section
    code_result = state.get("code_result")
    chart_block = ""
    if code_result and getattr(code_result, "chart_path", None):
        safe_path = code_result.chart_path.replace("\\", "/")
        chart_block = (
            f"\nA quantitative chart has been generated and saved to:\n"
            f"  {safe_path}\n"
            f"In the most relevant section body, include the sentence: "
            f"'[Chart available: {safe_path}]' so the UI can display it.\n"
        )
    if code_result and getattr(code_result, "stdout", "").strip():
        chart_block += f"\nCode execution result:\n{code_result.stdout.strip()}\n"

    user_message = (
        f"Original User Query: {original_query}\n\n"
        f"Extracted Insights Database:\n"
        f"========================================\n"
        f"{formatted}"
        f"========================================\n"
        f"{feedback_block}"
        f"{chart_block}\n"
        f"Synthesize the research insights above into the final JSON report."
    )

    prompt = """You are an expert research report writer. You MUST return only a single valid JSON object — no markdown, no code fences, no commentary before or after.

Write a thorough, well-structured report that FULLY answers the user's original query using the insights provided. It should read like a professional analyst briefing that a reader could learn from — not a list of one-line claims.

Return this exact shape:
{
    "title": "a clear, specific report title",
    "summary": "A substantive executive summary. Aim for 600-1500 characters and stay strictly under 2800 characters. Explain the overall findings, what the evidence shows, and the key takeaways — not a single sentence.",
    "sections": [
        {
            "heading": "descriptive section heading",
            "body": "At least 4-6 full sentences (aim for 400-900 characters). Explain, analyse and connect the insights: give reasoning, context, nuance, and note any contradictions or gaps. Do NOT just restate a claim.",
            "sources": ["https://source-url.com"]
        }
    ],
    "overall_confidence": 0.85
}

STRICT RULES:
- Produce 4 to 6 sections. Each section body MUST be at least 50 characters and should be a proper paragraph.
- Every section's "sources" must contain only URLs starting with http, taken from the insights above. Never invent sources.
- Base every statement on the provided insights. If evidence is thin, say so in the body and lower overall_confidence.
- overall_confidence is a float between 0.0 and 1.0.
- Return ONLY the JSON object."""

    i = 0
    while i < 3:
        try:
            response = await client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                max_tokens=2500,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            text = response.choices[0].message.content
            text = text.strip()
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                text = match.group(0)

            import json_repair
            raw = json_repair.loads(text)
            if not isinstance(raw, dict):
                raise ValueError("Parsed JSON is not a dictionary")
            raw["insights"] = [insight.model_dump() for insight in state["insights"]]

            for section in raw.get("sections", []):
                section["sources"] = [
                    s for s in section.get("sources", section.get("Sources", []))
                    if isinstance(s, str) and s.startswith("http")
                ]

            # keep under the model's 3000-char limit WITHOUT gutting the report
            if len(raw.get("summary", "")) > 2800:
                raw["summary"] = raw["summary"][:2797] + "..."

            validated_report = FinalReport.model_validate(raw)
            return {
                "final_report": validated_report,
                "status": "synthesising"
            }

        except (ValidationError, json.JSONDecodeError) as e:
            print(f"failed as : {str(e)}")
            i += 1
            if i >= 3:
                return {
                    "status": "failed",
                    "error": f"validation error {str(e)}"
                }
            user_message = (
                f"Original User Query: {original_query}\n\n"
                f"Your last synthesis attempt failed validation with this error:\n"
                f"----------------------------------------\n"
                f"{str(e)}\n"
                f"----------------------------------------\n"
                f"Regenerate the full report JSON. Keep 4-6 detailed sections, each body a proper "
                f"paragraph, summary under 2800 characters, and only http sources. Return ONLY JSON."
            )
            await asyncio.sleep(1)
            continue
        except Exception as e:
            return {
                "status": "failed",
                "error": f"this is the problem {str(e)}"
            }