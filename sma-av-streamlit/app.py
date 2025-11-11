# app.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import runpy
from pathlib import Path
from io import BytesIO
from typing import Optional, Dict, Any, List, Callable

import requests
from PIL import Image, UnidentifiedImageError
import streamlit as st

# ---------- Constants ----------
LOGO_URL = "https://github.com/user-attachments/assets/00c68a1d-224f-4170-b44f-9982bf4b5e8d"
ICON_URL = "https://raw.githubusercontent.com/AgentAiDrive/AV-AIops/refs/heads/IPAV-Agents/sma-av-streamlit/ipav.ico"

# ---------- Cached icon fetch ----------
def _fetch_pil_image(url: str) -> Optional[Image.Image]:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        img.load()
        return img
    except (requests.RequestException, UnidentifiedImageError, OSError):
        return None

@st.cache_data(show_spinner=False)
def _fetch_pil_image_cached(url: str) -> Optional[Image.Image]:
    return _fetch_pil_image(url)

_icon_img = _fetch_pil_image_cached(ICON_URL) or "🛠️"

# ---------- Page config (must be first Streamlit command) ----------
st.set_page_config(page_title="Agentic AV Ops", page_icon=_icon_img, layout="wide")

# ---------- Repo paths ----------
def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "app.py").exists() or (p / "core").is_dir():
            return p
    return Path.cwd()

APP_ROOT = find_repo_root()
CWD = Path.cwd()

# ---------- Query params helpers ----------
def _get_query_params_dict() -> Dict[str, Any]:
    """Return a simple dict {str: str} for query params (new/old API compatible)."""
    try:
        qp = st.query_params
        if hasattr(qp, "to_dict"):
            qp = qp.to_dict()
        if isinstance(qp, dict):
            norm = {}
            for k, v in qp.items():
                if isinstance(v, list):
                    norm[k] = v[0] if v else ""
                else:
                    norm[k] = v
            return norm
        return dict(qp)
    except Exception:
        qp_legacy = st.experimental_get_query_params()
        return {k: (v[0] if isinstance(v, list) and v else "") for k, v in qp_legacy.items()}

def _get_qp(key: str, default: Optional[str] = None) -> Optional[str]:
    return _get_query_params_dict().get(key, default)

# ---------- Main Home page ----------
def home():
    # Header / Identity
    st.image(LOGO_URL, caption="", width=190)
    st.title("Agentic AV Ops - SOP Workflow Orchestration")
    st.write("Use the sidebar to navigate.")

    # Model indicator (lightweight status in sidebar)
    def model_light():
        p = st.session_state.get("llm_provider") or "OpenAI"
        dot = "🟢" if p == "OpenAI" else "🔵"
        st.sidebar.markdown(f"**Model**: {dot} {p}")
    model_light()

    # Try to import and run DB seed idempotently
    try:
        from core.db.seed import init_db as _imported_init_db
        _imported_init_db()
        st.success("Database seeded & initialized.")
    except ImportError as import_error:
        st.warning(f"⚠️ init_db unavailable: {import_error}. Using fallback.")
    except Exception as db_exception:
        st.error(f"❌ init_db failed to execute: {db_exception}")

    # Page tips (safe default if import fails)
    try:
        from core.ui.page_tips import PAGE_TIPS  # type: ignore
    except Exception:
        PAGE_TIPS = {
            "Setup Wizard": (
                "Initialize DB and seed demo content: fixed system Agents (Baseline, EventForm, Intake, Plan, Act, Verify, Learn), "
                "sample Orchestrator + Fixed-Agent Recipes, and mock MCP tools. Idempotent—safe to run multiple times."
            ),
            "Settings": (
                "Select active LLM provider (OpenAI ↔ Anthropic). Shows key source and MCP mock status. "
                "No silent fallback—set a valid API key in secrets/env."
            ),
            "Chat": (
                "Use slash commands. **/sop** compiles an Orchestrator recipe plus bound Fixed-Agent Recipes from SOP, "
                "scaffolds required MCP tools, attaches to the chosen agent, and can execute the run. Toggle JSON mode to inspect payloads."
            ),
            "Agents": (
                "Manage Agents. Fixed system Agents are non-editable and enforce guardrails. "
                "Attach Recipes and trigger runs with approvals where required."
            ),
            "Recipes": (
                "Manage Recipes. Includes Orchestrator Recipes (workflow ‘what’) and Fixed-Agent Recipes (phase ‘how’). Validate and version them."
            ),
            "MCP Tools": (
                "Discover local connectors like Slack, Zoom, ServiceNow. Try `/health` or `/action`. "
                "SOP imports can auto-scaffold tools too."
            ),
            "Workflows": (
                "Wire Orchestrator + Agent + Trigger (manual or cron). Approvals can gate risky steps. "
                "Runs are recorded with artifacts and evidence."
            ),
            "Fixed-Workflows": (
                "Wire Fixed Agent Orchestrator + Recipe + JSON -> Run Pipeline (manual or cron). "
                "Runs are recorded with artifacts and evidence."
            ),
            "Dashboard": (
                "Metrics: run count, pass %, p95, MTTR, automation %. "
                "Drill into Run Details to inspect step logs, approvals, and generated KBs."
            ),
        }

    # RUNBOOK lookup
    candidates = [
        APP_ROOT / "docs" / "RUNBOOK.md",
        APP_ROOT / "RUNBOOK.md",
        CWD / "docs" / "RUNBOOK.md",
        CWD / "RUNBOOK.md",
    ]
    runbook_path = next((p for p in candidates if p.exists()), None)

    if not runbook_path:
        st.warning("RUNBOOK.md not found. Showing placeholder.")
        runbook_md = """# SMA AV-AI Ops — Runbook (Placeholder)

Please add your full runbook at `docs/RUNBOOK.md` (preferred) or project root `RUNBOOK.md`.
"""
    else:
        runbook_md = runbook_path.read_text(encoding="utf-8")
        st.success(f"Loaded runbook: `{runbook_path}`")

    # Global Page Tips
    with st.expander("Global Page Tips (quick reference)", expanded=False):
        cols = st.columns(2)
        for i, k in enumerate(PAGE_TIPS):
            with cols[i % 2]:
                st.markdown(f"**{k}**")
                st.caption(PAGE_TIPS[k])

    st.divider()

    # TOC builder
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

    toc = build_toc(runbook_md)

    q = st.text_input("Search the runbook", value="", placeholder="type to filter headings & body...")
    filtered_md = runbook_md
    if q.strip():
        pat = re.compile(re.escape(q), re.IGNORECASE)
        filtered_md = pat.sub(lambda m: f"**{m.group(0)}**", runbook_md)

    with st.expander("Table of Contents", expanded=False):
        if not toc:
            st.caption("No headings found.")
        else:
            for level, title, anchor in toc:
                indent = "&nbsp;" * (level - 1) * 4
                st.markdown(f"{indent}• [{title}](#{anchor})", unsafe_allow_html=True)

    st.download_button("Download RUNBOOK.md", data=runbook_md, file_name="RUNBOOK.md", mime="text/markdown")

    st.divider()
    st.markdown(filtered_md, unsafe_allow_html=False)

    # Optional debug
    debug_val = (_get_qp("debug") or "0").strip().lower()
    debug_on = debug_val in ("1", "true", "yes")

    with st.expander("Debug: RUNBOOK.md lookup paths", expanded=debug_on):
        st.caption(f"App root resolved to: `{APP_ROOT}`")
        st.caption(f"Working dir: `{CWD}`")
        st.code("\n".join(str(c) for c in candidates), language="text")

# ---------- Robust page discovery (works with your numbered pages/) ----------
PAGES_DIRS = [APP_ROOT / "nav_pages", APP_ROOT / "pages"]

def _find_script_by_keywords(keywords: List[str]) -> Optional[Path]:
    """
    Find a .py file in nav_pages/ or pages/ whose filename contains ALL keywords
    (case-insensitive). Handles numbered prefixes like '1_Setup_Wizard.py'.
    """
    kw = [k.lower() for k in keywords]
    for root in PAGES_DIRS:
        if not root.exists():
            continue
        for p in sorted(root.glob("*.py")):
            name = p.name.lower()
            if all(k in name for k in kw):
                return p
    return None

def _renderer_for(keywords: List[str]) -> Callable[[], None]:
    """
    Return a render() that executes the discovered script via runpy.
    If not found, render a user-friendly error.
    """
    target = _find_script_by_keywords(keywords)
    def _render():
        if target and target.exists():
            runpy.run_path(str(target), run_name="__main__")
        else:
            st.error(f"Page script not found for keywords={keywords}. "
                     f"Expected file in {', '.join(str(d) for d in PAGES_DIRS)}.")
    return _render

# Build renderers for each page using flexible filename matching
_pg_setupwizard      = _renderer_for(["setup", "wizard"])
_pg_chat             = _renderer_for(["chat"])
_pg_agents           = _renderer_for(["agents"])
_pg_recipes          = _renderer_for(["recipes"])
_pg_mcp_tools        = _renderer_for(["mcp", "tools"])
_pg_settings         = _renderer_for(["settings"])
_pg_workflows        = _renderer_for(["workflows"])
_pg_fixed_workflows  = _renderer_for(["fixed", "workflows"])
_pg_dashboard        = _renderer_for(["dashboard"])
_pg_help             = _renderer_for(["help"])
_pg_run_detail       = _renderer_for(["run", "detail"])

# ---------- Pages list (clean, lowercase URL slugs) ----------
def _pages_list():
    return [
        st.Page(home,                  title="Home",            url_path=""),
        st.Page(_pg_setupwizard,       title="Setup Wizard",    url_path="setupwizard"),
        st.Page(_pg_chat,              title="Chat",            url_path="chat"),
        st.Page(_pg_agents,            title="Agents",          url_path="agents"),
        st.Page(_pg_recipes,           title="Recipes",         url_path="recipes"),
        st.Page(_pg_mcp_tools,         title="MCP Tools",       url_path="mcp-tools"),
        st.Page(_pg_settings,          title="Settings",        url_path="settings"),
        st.Page(_pg_workflows,         title="Workflows",       url_path="workflows"),
        st.Page(_pg_fixed_workflows,   title="Fixed-Workflows", url_path="fixed-workflows"),
        st.Page(_pg_dashboard,         title="Dashboard",       url_path="dashboard"),
        st.Page(_pg_help,              title="Help",            url_path="help"),
        st.Page(_pg_run_detail,        title="Run Detail",      url_path="run-detail"),
    ]

# ---------- Run app with navigation (with legacy fallback) ----------
try:
    if hasattr(st, "navigation") and hasattr(st, "Page"):
        st.navigation(_pages_list()).run()
    else:
        st.sidebar.info("Using legacy navigation fallback (update Streamlit to enable st.navigation).")
        options = [
            "Home", "Setup Wizard", "Chat", "Agents", "Recipes", "MCP Tools",
            "Settings", "Workflows", "Fixed-Workflows", "Dashboard", "Help", "Run Detail"
        ]
        choice = st.sidebar.selectbox("Navigate", options, index=0)
        dispatch = {
            "Home": home,
            "Setup Wizard": _pg_setupwizard,
            "Chat": _pg_chat,
            "Agents": _pg_agents,
            "Recipes": _pg_recipes,
            "MCP Tools": _pg_mcp_tools,
            "Settings": _pg_settings,
            "Workflows": _pg_workflows,
            "Fixed-Workflows": _pg_fixed_workflows,
            "Dashboard": _pg_dashboard,
            "Help": _pg_help,
            "Run Detail": _pg_run_detail,
        }
        dispatch[choice]()
except Exception as nav_ex:
    st.error(f"Navigation failed: {nav_ex}")
    # Last resort, still render Home
    home()
