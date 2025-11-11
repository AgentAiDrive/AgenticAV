# app.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
import runpy
from functools import lru_cache
from pathlib import Path
from io import BytesIO
from typing import Optional, Dict, Any, List

import requests
from PIL import Image, UnidentifiedImageError
import streamlit as st
import sys

# ---------- Constants ----------
LOGO_URL = "https://github.com/user-attachments/assets/00c68a1d-224f-4170-b44f-9982bf4b5e8d"
ICON_URL = "https://raw.githubusercontent.com/AgentAiDrive/AV-AIops/refs/heads/IPAV-Agents/sma-av-streamlit/ipav.ico"

# ---------- Icon fetch (pure Python; no Streamlit calls) ----------
def _fetch_pil_image(url: str) -> Optional[Image.Image]:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        img.load()
        return img
    except (requests.RequestException, UnidentifiedImageError, OSError):
        return None

@lru_cache(maxsize=2)
def _fetch_pil_image_cached(url: str) -> Optional[Image.Image]:
    return _fetch_pil_image(url)

_icon_img = _fetch_pil_image_cached(ICON_URL) or "🛠️"

# ---------- Page config (must be the first Streamlit command) ----------
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

# ---------- Query params helpers (robust to new/old APIs) ----------
def _get_query_params_dict() -> Dict[str, Any]:
    """
    Returns a simple dict of {str: str} for query params.
    Works with both modern st.query_params and older experimental API.
    """
    try:
        qp = st.query_params  # modern: Mapping[str, str]
        if hasattr(qp, "to_dict"):  # future-proof
            qp = qp.to_dict()
        if isinstance(qp, dict):
            # Normalize values to strings
            norm = {}
            for k, v in qp.items():
                if isinstance(v, list):
                    norm[k] = v[0] if v else ""
                else:
                    norm[k] = v
            return norm
        return dict(qp)
    except Exception:
        # Legacy fallback
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
# ---------- Navigation: import wrappers, with robust fallbacks ----------


def _wrap_script(path: Path):
    """Return a render() that executes a standalone page script via runpy."""
    def _render():
        runpy.run_path(str(path), run_name="__main__")
    return _render

# Try regular imports first (preferred when nav_pages is a package)
try:
    import nav_pages.SetupWizard as _pg_SetupWizard
    import nav_pages.Chat as _pg_Chat
    import nav_pages.Agents as _pg_Agents
    import nav_pages.Recipes as _pg_Recipes
    import nav_pages.MCP_Tools as _pg_MCP_Tools
    import nav_pages.Settings as _pg_Settings
    import nav_pages.Workflows as _pg_Workflows
    import nav_pages.Fixed_Workflows as _pg_Fixed_Workflows
    import nav_pages.Dashboard as _pg_Dashboard
    import nav_pages.Help as _pg_Help
    import nav_pages.Run_Detail as _pg_Run_Detail
except Exception as e:
    st.warning(f"nav_pages import failed ({e}). Trying direct file execution from /nav_pages.")

    NAV_ROOT = APP_ROOT / "nav_pages"
    PAGES_ROOT = APP_ROOT / "pages"

    # file names (case-sensitive!)
    nav_map = {
        "SetupWizard": "SetupWizard.py",
        "Chat": "Chat.py",
        "Agents": "Agents.py",
        "Recipes": "Recipes.py",
        "MCP_Tools": "MCP_Tools.py",
        "Settings": "Settings.py",
        "Workflows": "Workflows.py",
        "Fixed_Workflows": "Fixed_Workflows.py",
        "Dashboard": "Dashboard.py",
        "Help": "Help.py",
        "Run_Detail": "Run_Detail.py",
    }

    def _fb_from(root: Path, key: str):
        return _wrap_script(root / nav_map[key])

    def _exists_in(root: Path, key: str) -> bool:
        return (root / nav_map[key]).exists()

    # Prefer nav_pages/ if present; else fall back to pages/
    _pg_SetupWizard = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "SetupWizard") else PAGES_ROOT, "SetupWizard")})()
    _pg_Chat = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "Chat") else PAGES_ROOT, "Chat")})()
    _pg_Agents = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "Agents") else PAGES_ROOT, "Agents")})()
    _pg_Recipes = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "Recipes") else PAGES_ROOT, "Recipes")})()
    _pg_MCP_Tools = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "MCP_Tools") else PAGES_ROOT, "MCP_Tools")})()
    _pg_Settings = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "Settings") else PAGES_ROOT, "Settings")})()
    _pg_Workflows = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "Workflows") else PAGES_ROOT, "Workflows")})()
    _pg_Fixed_Workflows = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "Fixed_Workflows") else PAGES_ROOT, "Fixed_Workflows")})()
    _pg_Dashboard = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "Dashboard") else PAGES_ROOT, "Dashboard")})()
    _pg_Help = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "Help") else PAGES_ROOT, "Help")})()
    _pg_Run_Detail = type("FB", (), {"render":
        _fb_from(NAV_ROOT if _exists_in(NAV_ROOT, "Run_Detail") else PAGES_ROOT, "Run_Detail")})()

# ---------- Build pages list ----------
def _pages_list():
    # Prefer stable url_paths (avoid empty string for root in some Streamlit versions)
    return [
        st.Page(home,                       title="Home",            url_path="home"),
        st.Page(_pg_SetupWizard.render,     title="Setup Wizard",    url_path="SetupWizard"),
        st.Page(_pg_Chat.render,            title="Chat",            url_path="Chat"),
        st.Page(_pg_Agents.render,          title="Agents",          url_path="Agents"),
        st.Page(_pg_Recipes.render,         title="Recipes",         url_path="Recipes"),
        st.Page(_pg_MCP_Tools.render,       title="MCP Tools",       url_path="mcp-tools"),
        st.Page(_pg_Settings.render,        title="Settings",        url_path="Settings"),
        st.Page(_pg_Workflows.render,       title="Workflows",       url_path="Workflows"),
        st.Page(_pg_Fixed_Workflows.render, title="Fixed-Workflows", url_path="fixed-Workflows"),
        st.Page(_pg_Dashboard.render,       title="Dashboard",       url_path="Dashboard"),
        st.Page(_pg_Help.render,            title="Help",            url_path="Help"),
        st.Page(_pg_Run_Detail.render,      title="Run Detail",      url_path="run-detail"),
    ]

# ---------- Run app with navigation (with legacy fallback) ----------
try:
    if hasattr(st, "navigation") and hasattr(st, "Page"):
        st.navigation(_pages_list()).run()
    else:
        # Legacy fallback: simple sidebar select
        st.sidebar.info("Using legacy navigation fallback (update Streamlit to enable st.navigation).")
        options = [
            "Home", "Setup Wizard", "Chat", "Agents", "Recipes", "MCP Tools",
            "Settings", "Workflows", "Fixed-Workflows", "Dashboard", "Help", "Run Detail"
        ]
        choice = st.sidebar.selectbox("Navigate", options, index=0)
        dispatch = {
            "Home": home,
            "Setup Wizard": _pg_SetupWizard.render,
            "Chat": _pg_Chat.render,
            "Agents": _pg_Agents.render,
            "Recipes": _pg_Recipes.render,
            "MCP Tools": _pg_MCP_Tools.render,
            "Settings": _pg_Settings.render,
            "Workflows": _pg_Workflows.render,
            "Fixed-Workflows": _pg_Fixed_Workflows.render,
            "Dashboard": _pg_Dashboard.render,
            "Help": _pg_Help.render,
            "Run Detail": _pg_Run_Detail.render,
        }
        dispatch[choice]()
except Exception as nav_ex:
    st.error(f"Navigation failed: {nav_ex}")
    # As a last resort, show Home so the app still renders
    home()
