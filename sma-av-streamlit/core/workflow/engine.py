
from __future__ import annotations
from typing import Iterator, Dict, Any
from sqlalchemy.orm import Session
from ..db.models import Agent, Recipe, Run
from ..recipes.service import load_recipe_dict
# core/workflow/engine.py (top of file)
try:
    from ..utils.evidence import attach_json
except Exception:
    # Fallback: graceful no-op if evidence module can't import
    def attach_json(db, run_id, obj, **kwargs):
        return None


def run_workflow_phases(recipe: Dict[str, Any]) -> Iterator[tuple[str, str]]:
    for phase in ["intake", "plan", "act", "verify"]:
        steps = recipe.get(phase, []) or []
        yield phase, f"{phase} steps: {len(steps)}"

def execute_recipe_run(db: Session, agent_id: int, recipe_id: int) -> Run:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"Agent {agent_id} not found")

    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise ValueError(f"Recipe {recipe_id} not found")

    run = Run(agent_id=agent_id, recipe_id=recipe_id, status="running")
    db.add(run); db.commit(); db.refresh(run)
    recipe_dict = load_recipe_dict(recipe.yaml_path)
    for phase, message in run_workflow_phases(recipe_dict):
        attach_json(db, run_id=run.id, obj={"phase": phase, "message": f"{agent.name}: {message}"})
    run.status = "completed"; db.commit(); db.refresh(run)
    return run
