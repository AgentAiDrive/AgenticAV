# sma-av-streamlit/pages/7_Fixed_Workflows.py
from __future__ import annotations

import json
import streamlit as st
from datetime import datetime  # noqa: F401 (kept if you log timestamps)
from sqlalchemy.exc import SQLAlchemyError

from core.db.models import Base, Agent, Recipe
from core.db.session import get_session
from core.workflow.orchestrator import run_ipav_pipeline

PAGE_KEY = "FixedWorkflows"
st.title("🧩 Fixed Agent Orchestrator")


def _safe_init_db_once():
    """Initialize DB exactly once per Streamlit session.

    Strategy:
      1) Try the project's real seeder (core.db.seed.init_db)
      2) If unavailable, create tables directly from SQLAlchemy models
    """
    if st.session_state.get("_db_init_done"):
        return

    # Try real seeder (if available)
    real_seeder_err = None
    try:
        from core.db.seed import init_db as real_init_db  # type: ignore
    except Exception as e:  # noqa: BLE001
        real_seeder_err = e
        real_init_db = None  # type: ignore

    try:
        if real_init_db:
            real_init_db()
        else:
            # Fallback: create tables directly from models
            with get_session() as s:
                bind = s.get_bind()
                Base.metadata.create_all(bind=bind)

        st.session_state["_db_init_done"] = True

        if real_seeder_err is not None:
            st.info(
                "DB seeding module not available; created tables from models instead. "
                "If you expect sample data, run your project's seeding command."
            )

    except Exception as err:  # noqa: BLE001
        st.session_state["_db_init_done"] = False
        st.error("Database initialization failed. Running in limited mode.")
        with st.expander("DB init error (details)"):
            if real_seeder_err:
                st.write("Seeder import error:")
                st.exception(real_seeder_err)
            st.write("Initialization error:")
            st.exception(err)


# Initialize (once)
_safe_init_db_once()

# ---- Load selectable options (guarded) ----
agent_opts: dict[int, str] = {}
recipe_opts: dict[int, str] = {}

try:
    with get_session() as db:
        agents = db.query(Agent).order_by(Agent.name).all()
        recipes = db.query(Recipe).order_by(Recipe.name).all()
        agent_opts = {a.id: a.name for a in agents}
        recipe_opts = {r.id: r.name for r in recipes}
except SQLAlchemyError as e:
    st.error("Failed to query the database. See details below.")
    with st.expander("DB query error"):
        st.exception(e)

if not agent_opts or not recipe_opts:
    st.warning(
        "No Agents or Recipes found. Create them first (or run your project's seeding step) "
        "then return to this page."
    )

st.subheader("Run Orchestrator")

a = (
    st.selectbox(
        "Orchestrator Agent",
        options=list(agent_opts.keys()),
        format_func=lambda i: agent_opts[i],
    )
    if agent_opts
    else None
)
r = (
    st.selectbox(
        "Recipe",
        options=list(recipe_opts.keys()),
        format_func=lambda i: recipe_opts[i],
    )
    if recipe_opts
    else None
)

ctx = st.text_area("Context (JSON)", value="{}")
run_btn = st.button("Run pipeline", type="primary", disabled=not (a and r))

if run_btn and a and r:
    try:
        ctx_obj = json.loads(ctx) if ctx.strip() else {}
    except Exception as e:  # noqa: BLE001
        st.error(f"Context JSON error: {e}")
        ctx_obj = {}

    with st.spinner("Running IPAV pipeline..."):
        try:
            with get_session() as db2:
                run = run_ipav_pipeline(
                    db2,
                    agent_id=int(a),
                    recipe_id=int(r),
                    context=ctx_obj,
                )
            st.success(f"Run #{getattr(run, 'id', '?')} completed.")
        except Exception as e:  # noqa: BLE001
            st.error("Pipeline execution failed.")
            with st.expander("Run error (details)"):
                st.exception(e)
