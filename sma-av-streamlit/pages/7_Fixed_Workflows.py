
# sma-av-streamlit/pages/7_Fixed_Workflows.py
from __future__ import annotations

import streamlit as st
from datetime import datetime
from core.db.models import Agent, Recipe
from core.workflow.orchestrator import run_ipav_pipeline
from core.db.session import get_session
try:
    from core.db.seed import init_db
except Exception as e:
    def init_db():
        st.warning(f"DB seeding unavailable: {e}. Continuing without seeding.")

PAGE_KEY = "FixedWorkflows"
st.title("🧩 Fixed Agent Orchestrator")

with get_session() as db:
    agent_opts = {a.id: a.name for a in db.query(Agent).order_by(Agent.name).all()}
    recipe_opts = {r.id: r.name for r in db.query(Recipe).order_by(Recipe.name).all()}

    st.subheader("Run Orchestrator")
    a = st.selectbox("Orchestrator Agent", options=list(agent_opts.keys()), format_func=lambda i: agent_opts[i]) if agent_opts else None
    r = st.selectbox("Recipe", options=list(recipe_opts.keys()), format_func=lambda i: recipe_opts[i]) if recipe_opts else None

    ctx = st.text_area("Context (JSON)", value="{}")
    run_btn = st.button("Run pipeline")

    if run_btn and a and r:
        try:
            import json
            ctx_obj = json.loads(ctx) if ctx.strip() else {}
        except Exception as e:
            st.error(f"Context JSON error: {e}")
            ctx_obj = {}
        with st.spinner("Running IPAV pipeline..."):
            with get_session() as db2:
                run = run_ipav_pipeline(db2, agent_id=int(a), recipe_id=int(r), context=ctx_obj)
            st.success(f"Run #{run.id} completed.")
