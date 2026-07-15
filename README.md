# NEXUS Intelligence OS

An autonomous multi-agent research system. Give it any question — it plans, searches, extracts, analyses, critiques, and delivers a structured cited report. Entirely on its own.

---

## What it does

Most AI tools give you one LLM response to your question. NEXUS runs a coordinated pipeline of seven specialised agents that each do one job well. The Planner breaks your question into sub-questions. The Searcher hits the web in parallel. The Extractor validates every claim with Pydantic before it touches anything else. The Synthesiser writes the report. The Critic scores it — and if quality is too low, the entire pipeline loops back and tries again automatically.

It also remembers. Every session writes extracted knowledge to a persistent vector database. Future sessions on related topics start with that knowledge already available.

---

## Architecture

```
User query
    │
    ▼
┌─────────────┐
│ Memory Read │  ← checks ChromaDB for prior knowledge on this topic
└──────┬──────┘
       │
    ▼
┌─────────────┐
│   Planner   │  ← LLM breaks query into typed SubQuestion objects (Pydantic validated)
└──────┬──────┘
       │
    ▼
┌──────────────────────────────────┐
│  Searcher + RAG  (parallel)      │  ← Tavily web search + ChromaDB hybrid query
└──────────────────┬───────────────┘
                   │
    ▼
┌─────────────┐
│  Extractor  │  ← pulls Insight objects, validates confidence vs source count
└──────┬──────┘
       │
    ▼
┌─────────────┐
│ Code Agent  │  ← decides if Python calculation needed, runs it in sandboxed subprocess
└──────┬──────┘
       │
    ▼
┌──────────────┐
│ Synthesiser  │  ← merges everything into typed FinalReport with computed source count
└──────┬───────┘
       │
    ▼
┌─────────────┐
│    Critic   │  ← scores evidence, coherence, coverage — loops back if any < 0.6
└──────┬──────┘
       │
    ├── passed → Memory Write → END
    └── failed → back to Planner (max 3 retries)
```

---

## Tech stack

| Layer | Technology | Purpose |
|---|---|---|
| Validation | Pydantic v2 | Every LLM output parsed and validated before use |
| Orchestration | LangGraph | Agent graph with conditional edges and reflection loop |
| LLM | Groq (Llama 3) | Fast inference for all agent calls |
| Web search | Tavily API | Structured search built for agents |
| Knowledge base | ChromaDB | Persistent vector store for semantic memory |
| Session memory | SQLite | Episodic log of past research sessions |
| API | FastAPI | REST endpoints with Server-Sent Events streaming |
| UI | Streamlit | Live agent progress and report display |
| Infrastructure | Docker + Redis | Containerised deployment |

---

## Pydantic concepts demonstrated

This project uses Pydantic v2 as the typed backbone of the entire pipeline — not just for data validation but as the architectural contract between every agent.

| Concept | Where used |
|---|---|
| `BaseModel` + `Field` constraints | Every agent I/O schema |
| `field_validator` | Snippet cleaning, duplicate sub-question detection |
| `model_validator` | High-confidence claims require 2+ sources |
| Discriminated unions | `AnalystTask` routing between `DeepAnalysis` and `QuickScan` |
| `computed_field` | `total_sources` auto-calculated from all report sections |
| `model_dump_json` / `model_validate_json` | State persistence and restoration |
| `AnyHttpUrl` | URL validation on all source fields |
| `Enum` | Priority levels with strict value constraints |
| `Literal` types | Depth and status fields with exact allowed values |

---

## File structure

```
NEXUS/
│
├── models/
│   ├── planner_models.py    ← ResearchPlan, SubQuestion, Priority enum
│   ├── agent_models.py      ← SearchResults, Insights, FinalReport, CritiqueResult
│   └── state.py             ← AgentState TypedDict flowing through LangGraph
│
├── agents/
│   ├── memory.py            ← ChromaDB read/write + SQLite session logging
│   ├── planner.py           ← query decomposition with retry on ValidationError
│   ├── rag.py               ← semantic search over knowledge base
│   ├── searcher.py          ← parallel async web search via Tavily
│   ├── extractor.py         ← insight extraction with Pydantic validation
│   ├── code_agent.py        ← LLM-written Python in sandboxed subprocess
│   ├── synthesiser.py       ← final report generation with source injection
│   └── critic.py            ← quality scoring with automatic reflection loop
│
├── graph/
│   └── nexus_graph.py       ← LangGraph pipeline with conditional edges
│
├── api/
│   └── server.py            ← FastAPI + SSE streaming endpoints
│
├── ui/
│   └── app.py               ← Streamlit live research interface
│
├── .env                     ← API keys (never commit)
├── docker-compose.yml       ← Redis + ChromaDB infrastructure
└── requirements.txt
```

---

## Setup

**1. Clone the repository**
```bash
git clone https://github.com/SyedMuhammadAyyanIbrar/nexus-intelligence-os.git
cd nexus-intelligence-os
```

**2. Create virtual environment**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Set up API keys**

Create a `.env` file in the project root:
```
GROQ_API_KEY=your_groq_key
TAVILY_API_KEY=your_tavily_key
```

Get your keys:
- Groq (free): https://console.groq.com
- Tavily (free): https://tavily.com

**5. Run the server**
```bash
python -m api.server
```

**6. Run the UI** (separate terminal)
```bash
streamlit run ui/app.py
```

Open `http://localhost:8501` in your browser.

---

## Example queries

```
What are the long-term effects of social media on teenagers?

Analyze AI adoption trends from 2020 to 2024 and calculate year-over-year growth.

What does current research say about intermittent fasting and longevity?

Compare the economic impact of remote work before and after COVID-19.
```

---

## How the reflection loop works

The Critic agent scores every report on three axes — evidence quality, coherence, and coverage — each between 0 and 1. If any score falls below 0.6, the report fails. The LangGraph conditional edge routes back to the Planner, which receives the Critic's specific feedback and generates refined sub-questions. The pipeline reruns. This continues until the report passes or the retry limit (3) is reached. The user always receives a report that passed a quality gate.

---

## Key design decisions

**Why Pydantic on every LLM output?**
LLMs hallucinate field names, return wrong types, and skip required fields. Pydantic catches all of this at the boundary — not silently 10 steps later when something explodes deep in the pipeline. Every agent in NEXUS produces a typed output that the next agent can trust.

**Why LangGraph instead of a simple chain?**
The reflection loop cannot be expressed as a linear chain. LangGraph's conditional edges make the loop explicit and controllable — the graph decides where to go next based on state, not hardcoded logic.

**Why ChromaDB for memory?**
Each session writes extracted knowledge as embeddings. The RAG agent retrieves semantically relevant knowledge before web search — so if you researched social media last week, that knowledge is available for a related question today. The system compounds knowledge over time.

**Why sandbox the code agent?**
LLM-generated code is untrusted. Running it in a subprocess with a 10-second timeout means a runaway loop or crash cannot affect the main pipeline. stdout and stderr are captured and returned as structured `CodeResult` objects.

---

## Requirements

```
pydantic>=2.0
langgraph
groq
tavily-python
chromadb
fastapi
uvicorn
sse-starlette
streamlit
python-dotenv
requests
sqlite3
```

---

## Author

**Syed Muhammad Ayyan Ibrar**
Built as a deep-dive into production agentic AI patterns — Pydantic structured outputs, LangGraph orchestration, RAG, reflection loops, human-in-the-loop, async parallelism, and SSE streaming.

GitHub: https://github.com/SyedMuhammadAyyanIbrar/nexus-intelligence-os
