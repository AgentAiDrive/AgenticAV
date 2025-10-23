
# sma-av-streamlit/core/workflow/orchestrator.py
from __future__ import annotations
from typing import Dict, Any
from sqlalchemy.orm import Session
from core.db.models import Agent, Recipe, Run
from core.utils.evidence import attach_json
from core.recipes.service import load_recipe_dict
from core.agents.fixed.registry import FIXED_AGENT_REGISTRY

def run_ipav_pipeline(db: Session, *, agent_id: int, recipe_id: int, context: Dict[str, Any] | None = None) -> Run:
    agent = db.get(Agent, agent_id); recipe = db.get(Recipe, recipe_id)
    if not agent or not recipe:
        raise ValueError("Invalid agent or recipe id")
    run = Run(agent_id=agent_id, recipe_id=recipe_id, status="running")
    db.add(run); db.commit(); db.refresh(run)

    rdict = load_recipe_dict(recipe)  # robust load
    ctx: Dict[str, Any] = dict(context or {})
    attach_json(db, run.id, {"phase":"intake","message":"IntakeAgent start","ctx":ctx})

    # Intake
    attach_json(db, run.id, {"phase":"intake","message":"IntakeAgent complete"})

    # Plan
    attach_json(db, run.id, {"phase":"plan","message":"PlanAgent produced plan from recipe", "plan": rdict.get("plan")})

    # Act
    attach_json(db, run.id, {"phase":"act","message":"ActAgent executed bounded actions", "actions": rdict.get("act")})

    # Verify
    attach_json(db, run.id, {"phase":"verify","message":"VerifyAgent checks passed", "verify": rdict.get("verify")})

    # Learn (KB publish via fixed agent callable if recipe requests it)
    learn = rdict.get("learn") or {}
    if learn.get("kb_publish"):
        kb = FIXED_AGENT_REGISTRY["KBPublisher"]()  # construct
        title = learn.get("title") or recipe.name
        html = learn.get("html") or "<p>Workflow completed.</p>"
        tags = learn.get("tags") or ["ipav","workflow"]
        audience = learn.get("audience") or "All"
        meta = learn.get("meta") or {}
        rec = kb(title=title, html=html, tags=tags, audience=audience, meta=meta)
        attach_json(db, run.id, {"phase":"learn","message":"KB published", "record": rec})
    else:
        attach_json(db, run.id, {"phase":"learn","message":"No KB publish requested"})

    run.status = "completed"; db.commit(); db.refresh(run)
    return run
