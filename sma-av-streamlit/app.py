from __future__ import annotations
import re
from pathlib import Path
import streamlit as st
from io import BytesIO
import requests
from PIL import Image, UnidentifiedImageError

# Try to import DB init, warn if broken
try:
    from core.db.seed import init_db

LOGO_URL = "https://github.com/user-attachments/assets/00c68a1d-224f-4170-b44f-9982bf4b5e8d"
ICON_URL = "https://raw.githubusercontent.com/AgentAiDrive/AV-AIops/refs/heads/IPAV-Agents/sma-av-streamlit/ipav.ico"

def _fetch_pil_image(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        img.load()
        return img
    except (requests.RequestException, UnidentifiedImageError, OSError):
        return None

_icon_img = _fetch_pil_image(ICON_URL)
st.set_page_config(page_title="Agentic Ops IPAV", page_icon=_icon_img, layout="wide")
st.image(LOGO_URL, caption="", width=293)
st.title("Agentic Ops - IPAV SOP Workflow Orchestration")
st.write("Use sidebar to navigate.")

def model_light():
    p = (st.session_state.get("llm_provider") or "OpenAI")
    dot = "🟢" if p == "OpenAI" else "🔵"
    st.sidebar.markdown(f"**Model**: {dot} {p}")
model_light()

st.success("Database seeded & initialized.")
st.title("Support")

try:
    from core.ui.page_tips import PAGE_TIPS
except Exception:
    PAGE_TIPS = {
        "Setup Wizard": "Initialize DB and seed agents, recipes, MCP mock tools. Idempotent—safe to re-run.",
        "Settings": "Switch between OpenAI / Anthropic. Shows active LLM + key source.",
        "Chat": "Use slash commands. /sop compiles Orchestrator + Fixed recipes, binds MCP tools.",
        "Agents": "Manage agents and bound recipes. System agents fixed with guardrails.",
        "Recipes": "Create/validate Fixed + Orchestrator recipes. Supports YAML file or inline.",
        "MCP Tools": "Inspect MCP tool connectors. Autoscaffold from SOP. Run health checks.",
        "Workflows": "Connect agents + recipes + schedules. Gate sensitive actions via approvals.",
        "Dashboard": "View success %, MTTR, First-Time-Right. Inspect Run → Steps → Evidence.",
    }

APP_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "app.py").exists()), Path.cwd())
runbook_path = next((p for p in [APP_ROOT/"docs/RUNBOOK.md", APP_ROOT/"RUNBOOK.md"] if p.exists()), None)

runbook_md = runbook_path.read_text("utf-8") if runbook_path else (
    "# SMA AV-AI Ops — Runbook (Placeholder)\n\nPlease place `RUNBOOK.md` in `docs/` or root folder."
)

with st.expander("Global Page Tips", expanded=False):
    cols = st.columns(2)
    for i, (k, v) in enumerate(PAGE_TIPS.items()):
        with cols[i % 2]:
            st.markdown(f"**{k}**")
            st.caption(v)

def build_toc(md: str):
    lines = md.splitlines()
    items = []
    for ln in lines:
        m = re.match(r"^(#{1,3})\s+(.*)", ln)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        anchor = re.sub(r"[^\w\- ]", "", title).strip().lower().replace(" ", "-")
        items.append((level, title, anchor))
    return items

q = st.text_input("Search the runbook", value="", placeholder="type to filter headings & body...")
filtered_md = re.sub(re.escape(q), lambda m: f"**{m.group(0)}**", runbook_md, flags=re.IGNORECASE) if q.strip() else runbook_md

with st.expander("Table of Contents", expanded=False):
    for level, title, anchor in build_toc(runbook_md):
        indent = "&nbsp;" * (level - 1) * 4
        st.markdown(f"{indent}• [{title}](#{anchor})", unsafe_allow_html=True)

st.download_button("Download RUNBOOK.md", data=runbook_md, file_name="RUNBOOK.md", mime="text/markdown")
st.markdown(filtered_md, unsafe_allow_html=False)

init_db()
