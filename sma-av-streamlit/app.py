# app.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import runpy
from functools import lru_cache
from pathlib import Path
from io import BytesIO
from typing import Optional, Dict, Any, Iterable, Callable

import requests
from PIL import Image, UnidentifiedImageError
import streamlit as st
import sys
import importlib

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

# ---------- Utilities for robust path discovery ----------
def _unique(seq: Iterable[Path]) -> list[Path]:
    out, seen = [], set()
    for p in seq:
        p = p.resolve()
        if p not in seen:
            out.append(p); seen.add(p)
    return out

def _candidate_roots() -> list[Path]:
    # Cover app dir, its parent (repo root), working dir, and their parents
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

# Add all candidate roots to Python path so sibling packages are importable
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

# ---------- Home page ----------
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

# ---------- Page discovery / import helpers ----------
_SEARCH_CACHE: Dict[str, list[Path]] = {}

def _wrap_script(path: Path) -> Callable[[], None]:
    def _render():
        runpy.run_path(str(path), run_name="__main__")
    return _render

def _search_page_file(key: str) -> Optional[Path]:
    """
    Return an existing file for the page key by searching in:
      1) nav_pages/ (lowercase preferred)
      2) pages/ (common CamelCase/underscore variants)
    Returns None if not found. Records all searched paths in _SEARCH_CACHE[key].
    """
    NAV = _discover_dir("nav_pages")
    PAGES = _discover_dir("pages")

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

    searched: list[Path] = []
    candidates: list[Path] = []
    names = name_sets.get(key, [])

    if NAV:
        candidates += [NAV / f for f in names]
    if PAGES:
        candidates += [PAGES / f for f in names]

    for p in candidates:
        searched.append(p)
        if p.exists():
            _SEARCH_CACHE[key] = searched
            return p

    _SEARCH_CACHE[key] = searched
    return None

def _import_or_wrap(module_path: str, fallback_key: str) -> Optional[Callable[[], None]]:
    """
    Try to import nav_pages.<module>.render
    If that fails, search for a file and return a wrapper that runs it.
    Returns None if neither is available.
    """
    try:
        mod = importlib.import_module(module_path)
        render = getattr(mod, "render", None)
        if callable(render):
            return render
    except Exception:
        pass  # fall through to file search

    file_path = _search_page_file(fallback_key)
    if file_path:
        return _wrap_script(file_path)
    return None

# ---------- Build page registry ----------
# Each entry: (label, url_path, module_import, search_key)
_PAGE_SPECS = [
    ("Setup Wizard",    "setupwizard",     "nav_pages.setupwizard",     "setupwizard"),
    ("Chat",            "chat",            "nav_pages.chat",            "chat"),
    ("Agents",          "agents",          "nav_pages.agents",          "agents"),
    ("Recipes",         "recipes",         "nav_pages.recipes",         "recipes"),
    ("MCP Tools",       "mcp-tools",       "nav_pages.mcp_tools",       "mcp_tools"),
    ("Settings",        "settings",        "nav_pages.settings",        "settings"),
    ("Workflows",       "workflows",       "nav_pages.workflows",       "workflows"),
    ("Fixed-Workflows", "fixed-workflows", "nav_pages.fixed_workflows", "fixed_workflows"),
    ("Dashboard",       "dashboard",       "nav_pages.dashboard",       "dashboard"),
    ("Help",            "help",            "nav_pages.help",            "help"),
    ("Run Detail",      "run-detail",      "nav_pages.run_detail",      "run_detail"),
]

def _resolve_pages() -> list[tuple[str, str, Callable[[], None]]]:
    """
    Returns a list of (label, url_path, render_fn) for pages that are available.
    Missing pages are skipped.
    """
    resolved: list[tuple[str, str, Callable[[], None]]] = []
    for label, url_path, module_path, key in _PAGE_SPECS:
        render_fn = _import_or_wrap(module_path, key)
        if render_fn:
            resolved.append((label, url_path, render_fn))
    return resolved

# ---------- Pages ----------
def _pages_list():
    pages = [st.Page(home, title="Home", url_path="home")]
    for label, url_path, render_fn in _resolve_pages():
        pages.append(st.Page(render_fn, title=label, url_path=url_path))
    return pages

# ---------- Run with navigation (legacy fallback supported) ----------
try:
    if hasattr(st, "navigation") and hasattr(st, "Page"):
        st.navigation(_pages_list()).run()
    else:
        st.sidebar.info("Using legacy navigation fallback (update Streamlit to enable st.navigation).")
        options: list[tuple[str, Callable[[], None]]] = [("Home", home)]
        for label, _, render_fn in _resolve_pages():
            options.append((label, render_fn))

        labels = [l for (l, _) in options]
        choice = st.sidebar.selectbox("Navigate", labels, index=0)
        for label, fn in options:
            if label == choice:
                fn()
                break
except Exception as nav_ex:
    st.error(f"Navigation failed: {nav_ex}")
    home()

# ---------- Optional debug sidebar for page presence ----------
if (_get_qp("debug") or "0").strip().lower() in ("1", "true", "yes"):
    with st.sidebar.expander("Debug: Page availability", expanded=False):
        avail = [label for (label, _, _) in _resolve_pages()]
        st.write("Available:", ", ".join(avail) or "none")
        missing = [label for (label, _, _) in _PAGE_SPECS if label not in avail]
        if missing:
            st.write("Missing:", ", ".join(missing))
            # show searched paths for missing keys
            key_by_label = {label: key for (label, _, _, key) in _PAGE_SPECS}
            for label in missing:
                key = key_by_label[label]
                paths = _SEARCH_CACHE.get(key, [])
                if paths:
                    st.caption(f"Searched for '{label}' ({key}):")
                    st.code("\n".join(str(p) for p in paths), language="text")
st.divider()
st.markdown(filtered_md, unsafe_allow_html=False)

# ---------- Optional debug ----------
def _get_query_params():
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()  # for older versions

qp = _get_query_params()
debug_on = str(qp.get("debug", ["0"])[0]).lower() in ("1", "true", "yes")

with st.expander("Debug: RUNBOOK.md lookup paths", expanded=debug_on):
    st.caption(f"App root resolved to: `{APP_ROOT}`")
    st.caption(f"Working dir: `{CWD}`")
    st.code("\n".join(str(c) for c in candidates), language="text")
