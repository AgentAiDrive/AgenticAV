# app.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import runpy
from functools import lru_cache
from pathlib import Path
from io import BytesIO
from typing import Optional, Dict, Any, Iterable

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

# ---------- Utilities for robust path discovery ----------
def _unique(seq: Iterable[Path]) -> list[Path]:
    out, seen = [], set()
    for p in seq:
        p = p.resolve()
        if p not in seen:
            out.append(p); seen.add(p)
    return out

def _candidate_roots() -> list[Path]:
    # cover app dir, its parent (repo root), working dir, and their parents
    roots = [
        APP_ROOT,
        APP_ROOT.parent,
        CWD,
        CWD.parent,
        Path(__file__).resolve().parent,
    ]
    return _unique([p for p in roots if p.exists()])

def _discover_dir(name: str) -> Optional[Path]:
    # find a directory named `name` under any candidate root
    for r in _candidate_roots():
        d = r / name
        if d.is_dir():
            return d.resolve()
    return None

def _ensure_on_syspath(paths: Iterable[Path]):
    for p in paths:
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)

# add all candidate roots to import path so packages next to or above app are importable
_ensure_on_syspath(_candidate_roots())

# ---------- Query params helpers ----------
def _get_query_params_dict() -> Dict[str, Any]:
    try:
        qp = st.query_params  # Mapping[str, str] (modern)
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
    st.image(LOGO_URL, caption="", width=190)
    st.title("Agentic AV Ops - SOP Workflow Orchestration")
    st.write("Use the sidebar to navigate.")

    def model_light():
        p = st.session_state.get("llm_provider") or "OpenAI"
        dot = "🟢" if p == "OpenAI" else "🔵"
        st.sidebar.markdown(f"**Model**: {dot} {p}")
    model_light()

    try:
        from core.db.seed import init_db as _imported_init_db
        _imported_init_db()
        st.success("Database seeded & initialized.")
    except ImportError as import_error:
        st.warning(f"⚠️ init_db unavailable: {import_error}. Using fallback.")
    except Exception as db_exception:
        st.error(f"❌ init_db failed to execute: {db_exception}")

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

    with st.expander("Global Page Tips (quick reference)", expanded=False):
        cols = st.columns(2)
        for i, k in enumerate(PAGE_TIPS):
            with cols[i % 2]:
                st.markdown(f"**{k}**")
                st.caption(PAGE_TIPS[k])

    st.divider()

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

    debug_val = (_get_qp("debug") or "0").strip().lower()
    debug_on = debug_val in ("1", "true", "yes")
    if debug_on:
        with st.expander("Debug: Path discovery", expanded=True):
            st.caption(f"APP_ROOT: `{APP_ROOT}`")
            st.caption(f"CWD: `{CWD}`")
            st.caption(f"Candidate roots: {', '.join(str(p) for p in _candidate_roots())}")
            st.caption(f"nav_pages found at: `{_discover_dir('nav_pages')}`")
            st.caption(f"pages found at: `{_discover_dir('pages')}`")

# ---------- Navigation helpers ----------
def _wrap_script(path: Path):
    def _render():
        runpy.run_path(str(path), run_name="__main__")
    return _render

def _resolve_page_file(key: str) -> Path:
    """
    Return an existing file for the page key by searching in:
      1) nav_pages/ (lowercase)
      2) pages/ (several common casings)
    Raises FileNotFoundError with a helpful message if nothing matches.
    """
    NAV = _discover_dir("nav_pages")
    PAGES = _discover_dir("pages")

    # candidate filenames per key (ordered by preference)
    name_sets: Dict[str, list[str]] = {
        "setupwizard":      ["setupwizard.py", "SetupWizard.py", "Setup_Wizard.py", "setup_wizard.py"],
        "chat":             ["chat.py", "Chat.py"],
        "agents":           ["agents.py", "Agents.py"],
        "recipes":          ["recipes.py", "Recipes.py"],
        "mcp_tools":        ["mcp_tools.py", "MCP_Tools.py", "mcp-tools.py"],
        "settings":         ["settings.py", "Settings.py"],
        "workflows":        ["workflows.py", "Workflows.py"],
        "fixed_workflows":  ["fixed_workflows.py", "Fixed_Workflows.py", "fixed-workflows.py"],
        "dashboard":        ["dashboard.py", "Dashboard.py"],
        "help":             ["help.py", "Help.py"],
        "run_detail":       ["run_detail.py", "Run_Detail.py", "run-detail.py"],
    }
    candidates: list[Path] = []

    fnames = name_sets[key]
    if NAV:
        candidates += [NAV / f for f in fnames]
    if PAGES:
        candidates += [PAGES / f for f in fnames]

    for p in candidates:
        if p.exists():
            return p

    searched = "\n  ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"No file found for page '{key}'. Searched:\n  {searched}")

# ---------- Try package imports first (prefer lowercase modules) ----------
try:
    import nav_pages.setupwizard as _pg_setupwizard
    import nav_pages.chat as _pg_chat
    import nav_pages.agents as _pg_agents
    import nav_pages.recipes as _pg_recipes
    import nav_pages.mcp_tools as _pg_mcp_tools
    import nav_pages.settings as _pg_settings
    import nav_pages.workflows as _pg_workflows
    import nav_pages.fixed_workflows as _pg_fixed_workflows
    import nav_pages.dashboard as _pg_dashboard
    import nav_pages.help as _pg_help
    import nav_pages.run_detail as _pg_run_detail
except Exception as e:
    st.warning(f"nav_pages import failed ({e}). Falling back to direct file execution.")
    # Build lightweight wrappers that run the discovered files
    class _FB:
        def __init__(self, key: str):
            self.render = _wrap_script(_resolve_page_file(key))
    _pg_setupwizard      = _FB("setupwizard")
    _pg_chat             = _FB("chat")
    _pg_agents           = _FB("agents")
    _pg_recipes          = _FB("recipes")
    _pg_mcp_tools        = _FB("mcp_tools")
    _pg_settings         = _FB("settings")
    _pg_workflows        = _FB("workflows")
    _pg_fixed_workflows  = _FB("fixed_workflows")
    _pg_dashboard        = _FB("dashboard")
    _pg_help             = _FB("help")
    _pg_run_detail       = _FB("run_detail")

# ---------- Pages ----------
def _pages_list():
    return [
        st.Page(home,                       title="Home",            url_path="home"),
        st.Page(_pg_setupwizard.render,     title="Setup Wizard",    url_path="setupwizard"),
        st.Page(_pg_chat.render,            title="Chat",            url_path="chat"),
        st.Page(_pg_agents.render,          title="Agents",          url_path="agents"),
        st.Page(_pg_recipes.render,         title="Recipes",         url_path="recipes"),
        st.Page(_pg_mcp_tools.render,       title="MCP Tools",       url_path="mcp-tools"),
        st.Page(_pg_settings.render,        title="Settings",        url_path="settings"),
        st.Page(_pg_workflows.render,       title="Workflows",       url_path="workflows"),
        st.Page(_pg_fixed_workflows.render, title="Fixed-Workflows", url_path="fixed-workflows"),
        st.Page(_pg_dashboard.render,       title="Dashboard",       url_path="dashboard"),
        st.Page(_pg_help.render,            title="Help",            url_path="help"),
        st.Page(_pg_run_detail.render,      title="Run Detail",      url_path="run-detail"),
    ]

# ---------- Run with navigation (legacy fallback supported) ----------
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
            "Setup Wizard": _pg_setupwizard.render,
            "Chat": _pg_chat.render,
            "Agents": _pg_agents.render,
            "Recipes": _pg_recipes.render,
            "MCP Tools": _pg_mcp_tools.render,
            "Settings": _pg_settings.render,
            "Workflows": _pg_workflows.render,
            "Fixed-Workflows": _pg_fixed_workflows.render,
            "Dashboard": _pg_dashboard.render,
            "Help": _pg_help.render,
            "Run Detail": _pg_run_detail.render,
        }
        dispatch[choice]()
except FileNotFoundError as e:
    st.error(f"Navigation failed: {e}")
    with st.expander("Troubleshooting — searched paths", expanded=True):
        st.code(str(e), language="text")
    home()
except Exception as nav_ex:
    st.error(f"Navigation failed: {nav_ex}")
    home()
