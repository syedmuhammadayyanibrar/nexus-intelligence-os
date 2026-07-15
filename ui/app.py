import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import html
import json
import requests
import streamlit as st

st.set_page_config(page_title="NEXUS", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Serif:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root{
  --paper:#f5f2ec; --panel:#faf8f3; --ink:#23201b; --muted:#6f6a60;
  --faint:#a49d90; --rule:#ddd6c8; --accent:#9c4a2b; --link:#2d4a6b;
}

.stApp{ background:var(--paper); color:var(--ink); }
.block-container{ padding-top:2.4rem; max-width:1180px; }

header[data-testid="stHeader"]{ background:transparent; }
#MainMenu, footer{ visibility:hidden; }

/* ---- CATCH-ALL: anything injected as HTML is dark by default ---- */
[data-testid="stMarkdownContainer"]{ color:var(--ink); }
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] h5{ color:var(--ink) !important; }

/* masthead */
.nx-masthead{ border-bottom:2px solid var(--ink); padding-bottom:.5rem; margin-bottom:.2rem; }
.nx-title{ font-family:'IBM Plex Serif',serif; font-weight:600; font-size:2.1rem;
  letter-spacing:-.01em; color:var(--ink) !important; line-height:1; }
.nx-sub{ font-family:'IBM Plex Mono',monospace; font-size:.72rem; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted) !important; margin-top:.45rem; }

/* report prose: serif, generous measure */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li{
  font-family:'IBM Plex Serif',serif; font-size:1.02rem; line-height:1.62;
  color:var(--ink) !important; max-width:64ch;
}

/* report headings — direct classes, no wrapper dependency */
h2.nx-h2{ font-family:'IBM Plex Serif',serif; font-weight:600;
  color:var(--ink) !important; font-size:1.32rem; margin:1.6rem 0 .3rem; }
h3.nx-h3{ font-family:'IBM Plex Serif',serif; font-weight:600;
  color:var(--ink) !important; font-size:1.08rem; border-bottom:1px solid var(--rule);
  padding-bottom:.25rem; margin:1.5rem 0 .55rem; }

.nx-eyebrow{ font-family:'IBM Plex Mono',monospace; font-size:.68rem; letter-spacing:.16em;
  text-transform:uppercase; color:var(--faint) !important; margin:0 0 .2rem; }
.nx-meta{ font-family:'IBM Plex Mono',monospace; font-size:.74rem;
  color:var(--muted) !important; border-top:1px solid var(--rule);
  border-bottom:1px solid var(--rule); padding:.4rem 0; margin:.2rem 0 1.1rem; }
.nx-status{ font-family:'IBM Plex Mono',monospace; font-size:.8rem;
  color:var(--ink) !important; margin:.3rem 0 1rem; }
.nx-status .k{ color:var(--faint) !important; letter-spacing:.14em;
  text-transform:uppercase; font-size:.68rem; margin-right:.5rem; }
.nx-src{ font-family:'IBM Plex Mono',monospace; font-size:.78rem; }
.nx-src a{ color:var(--link) !important; text-decoration:none;
  border-bottom:1px solid #b9c4d1; }

/* right-hand activity rail */
.nx-rail{ position:sticky; top:1rem; background:var(--panel); border:1px solid var(--rule); }
.nx-rail-hd{ font-family:'IBM Plex Mono',monospace; font-size:.68rem; letter-spacing:.18em;
  text-transform:uppercase; color:var(--muted) !important; background:var(--paper);
  border-bottom:1px solid var(--rule); padding:.5rem .8rem; }
.nx-steps{ padding:.7rem .8rem; border-bottom:1px solid var(--rule); }
.nx-step{ font-family:'IBM Plex Mono',monospace; font-size:.8rem; line-height:1.85;
  color:var(--faint) !important; }
.nx-step .m{ display:inline-block; width:1.1em; }
.nx-step.done{ color:var(--muted) !important; }
.nx-step.active{ color:var(--accent) !important; font-weight:600; }
.nx-log{ padding:.6rem .8rem; max-height:420px; overflow-y:auto; }
.nx-line{ font-family:'IBM Plex Mono',monospace; font-size:.74rem; line-height:1.5;
  color:var(--muted) !important; margin-bottom:.5rem; }
.nx-line .t{ color:var(--faint) !important; }
.nx-line .a{ color:var(--ink) !important; font-weight:600; }
.nx-line.now .a{ color:var(--accent) !important; }
.nx-line.faded{ opacity:.45; }

/* text input — dark visible text, readable placeholder, autofill guard */
[data-testid="stTextInput"] input{ font-family:'IBM Plex Sans',sans-serif;
  background:var(--panel); border:1px solid var(--rule); border-radius:0;
  color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important; }
[data-testid="stTextInput"] input::placeholder{ color:var(--faint) !important; opacity:1; }
[data-testid="stTextInput"] label{ font-family:'IBM Plex Mono',monospace;
  font-size:.7rem; letter-spacing:.12em; text-transform:uppercase;
  color:var(--muted) !important; }

/* run button — semi-transparent by default, solid on hover */
.stButton button{ font-family:'IBM Plex Mono',monospace; font-size:.78rem;
  letter-spacing:.08em; text-transform:uppercase; border-radius:0;
  border:1px solid var(--ink); background:var(--ink); color:var(--paper) !important;
  opacity:.55; transition:opacity .18s ease, background .18s ease, border-color .18s ease; }
.stButton button:hover{ opacity:1; background:var(--accent); border-color:var(--accent);
  color:#fff !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- pipeline
AGENTS = [
    ("read_memory", "read memory"),
    ("planner", "planner"),
    ("search_and_rag", "searcher + rag"),
    ("extractor", "extractor"),
    ("code_agent", "code agent"),
    ("synthesiser", "synthesiser"),
    ("critic", "critic"),
    ("write_memory", "memory write"),
]
AGENT_IDS = [a[0] for a in AGENTS]


def build_rail(done, current, log_lines):
    steps = ""
    for aid, label in AGENTS:
        if aid in done:
            cls, mark = "done", "●"
        elif aid == current:
            cls, mark = "active", "▸"
        else:
            cls, mark = "", "○"
        steps += f'<div class="nx-step {cls}"><span class="m">{mark}</span>{label}</div>'

    lines = ""
    n = len(log_lines)
    for i, (ts, agent, msg) in enumerate(log_lines):
        now = "now" if i == n - 1 else ""
        faded = "faded" if i < n - 6 else ""
        lines += (
            f'<div class="nx-line {now} {faded}">'
            f'<span class="t">{ts}</span>  '
            f'<span class="a">{html.escape(agent)}</span><br>{html.escape(msg)}</div>'
        )
    if not lines:
        lines = '<div class="nx-line faded">idle — awaiting query</div>'

    return f"""
    <div class="nx-rail">
      <div class="nx-rail-hd">pipeline</div>
      <div class="nx-steps">{steps}</div>
      <div class="nx-rail-hd">activity log</div>
      <div class="nx-log">{lines}</div>
    </div>"""


def render_report(col, payload):
    with col:
        st.markdown('<div class="nx-eyebrow">research report</div>', unsafe_allow_html=True)
        st.markdown(f'<h2 class="nx-h2">{html.escape(payload.get("title", "Report"))}</h2>',
                    unsafe_allow_html=True)

        bits = []
        if payload.get("overall_confidence") is not None:
            bits.append(f'confidence {payload["overall_confidence"]:.0%}')
        if payload.get("total_sources") is not None:
            bits.append(f'{payload["total_sources"]} sources')
        if bits:
            st.markdown(f'<div class="nx-meta">{"   ·   ".join(bits)}</div>',
                        unsafe_allow_html=True)

        if payload.get("summary"):
            st.markdown('<h3 class="nx-h3">Summary</h3>', unsafe_allow_html=True)
            st.markdown(payload["summary"])

        for sec in payload.get("sections", []):
            st.markdown(f'<h3 class="nx-h3">{html.escape(sec.get("heading", ""))}</h3>',
                        unsafe_allow_html=True)
            st.markdown(sec.get("body", ""))
            srcs = sec.get("sources", [])
            if srcs:
                links = " · ".join(
                    f'<a href="{s}">{s.split("//")[-1][:38]}</a>' for s in srcs
                )
                st.markdown(f'<div class="nx-src">{links}</div>', unsafe_allow_html=True)

        if not payload.get("summary") and not payload.get("sections"):
            st.warning("Report payload had no body.")
            st.json(payload)


# ---------------------------------------------------------------- layout
st.markdown(
    '<div class="nx-masthead"><div class="nx-title">NEXUS</div>'
    '<div class="nx-sub">autonomous multi-agent research system</div></div>',
    unsafe_allow_html=True,
)

query = st.text_input(
    "Research question",
    placeholder="What are the long-term effects of social media on teenagers?",
)
run_btn = st.button("Run research")

left, right = st.columns([2, 1], gap="large")
rail_slot = right.empty()
rail_slot.markdown(build_rail(set(), None, []), unsafe_allow_html=True)


if run_btn and not query:
    st.warning("Enter a research question first.")

elif run_btn and query:
    done_agents = set()
    log_lines = []
    current = None
    completed = False

    status = left.empty()
    status.markdown(
        '<div class="nx-status"><span class="k">status</span> working…</div>',
        unsafe_allow_html=True,
    )

    def push(agent, msg):
        log_lines.append((time.strftime("%H:%M:%S"), agent, msg))
        rail_slot.markdown(
            build_rail(done_agents, current, log_lines[-30:]),
            unsafe_allow_html=True,
        )

    try:
        resp = requests.post(
            "http://localhost:8000/research",
            json={"query": query},
            timeout=10,
        )
        if resp.status_code != 200:
            status.error(f"Server error {resp.status_code}: {resp.text}")
            st.stop()

        job_id = resp.json()["job_id"]
        url = f"http://localhost:8000/research/{job_id}/stream"

        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                raw = line[len("data:"):].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                agent = data.get("agent", "")
                msg = data.get("message", "")
                st_ = data.get("status", "")

                if agent in AGENT_IDS:
                    done_agents.add(agent)
                    idx = AGENT_IDS.index(agent)
                    current = AGENT_IDS[idx + 1] if idx + 1 < len(AGENT_IDS) else None

                d = data.get("data") or {}
                if agent == "critic" and "coverage_score" in d:
                    push(agent, f"scores ev {d['evidence_score']} · "
                                f"coh {d['coherence_score']} · cov {d['coverage_score']}")
                elif agent or msg:
                    push(agent or "system", msg)

                if st_ in ("completed", "done", "success"):
                    current = None
                    rail_slot.markdown(
                        build_rail(set(AGENT_IDS), None, log_lines[-30:]),
                        unsafe_allow_html=True,
                    )
                    status.empty()
                    render_report(left, data.get("data") or {})
                    completed = True
                    break

                if st_ in ("failed", "error"):
                    status.markdown(
                        f'<div class="nx-status"><span class="k">failed</span> '
                        f'{html.escape(msg)}</div>',
                        unsafe_allow_html=True,
                    )
                    break

        if not completed:
            status.markdown(
                '<div class="nx-status"><span class="k">warning</span> '
                'stream ended without a completion event</div>',
                unsafe_allow_html=True,
            )

    except requests.exceptions.ConnectionError:
        status.error("Cannot connect to server. In a separate terminal run:")
        st.code("python -m api.server")
    except Exception as e:
        status.error(f"Error: {str(e)}")