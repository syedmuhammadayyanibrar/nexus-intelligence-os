import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from itertools import combinations
from typing import List

from dotenv import load_dotenv
from groq import AsyncGroq, RateLimitError
from pydantic import ValidationError

from models.state import AgentState
from models.agent_models import ContradictionEdge

load_dotenv()
client = AsyncGroq()

# Max insight pairs to check to avoid O_2 explosion
MAX_PAIRS = 20

_SYSTEM="""You are a logical-consistency analyst. You will be given two research claims.
Decide whether they genuinely contradict each other - not just address different aspects,

but actually conflict: if one is true, the other must be false or unlikely.

Return ONLY a JSON object - no markdown fences:
{
  "contradicts": true,
  "severity": 0.8,
  "explanation": "Claim A says X while Claim B says not-X"
}
or
{
  "contradicts": false,
  "severity": 0.0,
  "explanation": "claims address different aspects"
}

Severity scale: 0.0-0.3 = minor tension, 0.3-0.7 = moderate, 0.7-1.0 = direct contradiction.
Only set contradicts true if severity > 0.3."""


async def _check_pair(ida: int, claim_a: str, idb: int, claim_b: str) -> ContradictionEdge | None:
    """Call the LLM for one pair; return ContradictionEdge or None."""
    user_msg = (
        f"Claim A (index {ida}): {claim_a}\n\n"
        f"Claim B (index {idb}): {claim_b}"
    )
    for attempt in range(3):
        try:
            resp = await client.chat.completions.create(
                model="openai/gpt-oss-20b",
                max_tokens=300,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            d = json.loads(raw)
            if not d.get("contradicts"):
                return None
            edge = ContradictionEdge(
                insight_a_index=ida,
                insight_b_index=idb,
                severity=min(1.0, max(0.0, float(d["severity"]))),
                explanation=str(d.get("explanation", "")),
            )
            return edge
        except RateLimitError:
            await asyncio.sleep(15)
        except (json.JSONDecodeError, KeyError, ValidationError):
            if attempt == 2:
                return None
            await asyncio.sleep(1)
    return None


async def run_contradiction_agent(state: AgentState) -> dict:
    insights = state.get("insights") or []
    if len(insights) < 2:
        # need at least two insights to find anything
        return {"contradiction_edges": []}

    # Build all pairs, then sample down to MAX_PAIRS
    all_pairs = list(combinations(range(len(insights)), 2))
    if len(all_pairs) > MAX_PAIRS:
        import random
        all_pairs = random.sample(all_pairs, MAX_PAIRS)

    edges: List[ContradictionEdge] = []

    for ida, idb in all_pairs:
        edge = await _check_pair(ida, insights[ida].claim, idb, insights[idb].claim)
        if edge is not None:
            edges.append(edge)
            # fill the contradictions field on both Insights objects
            insights[ida].contradictions.append(insights[idb].claim)
            insights[idb].contradictions.append(insights[ida].claim)

    return {
        "insights": insights,          # pass back mutated insights
        "contradiction_edges": edges,
        "status": "extracting",
    }


if __name__ == "__main__":
    from models.agent_models import Insights

    async def _test():
        fake_insights = [
            Insights(claim="Social media use strongly increases depression in teenagers", confidence=0.7, source=["https://a.com", "https://b.com"]),
            Insights(claim="Multiple studies found no significant link between social media and teen depression", confidence=0.6, source=["https://c.com", "https://d.com"]),
        ]
        result = await run_contradiction_agent({"insights": fake_insights, "status": "extracting"})
        print("edges:", result["contradiction_edges"])

    asyncio.run(_test())
