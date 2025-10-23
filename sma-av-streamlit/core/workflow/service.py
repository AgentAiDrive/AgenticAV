# core/workflow/service.py
from __future__ import annotations

from typing import Optional, Tuple, Set
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from .engine import execute_recipe_run
from core.runstore_factory import make_runstore  # shared store


# ---------- Resolve the Workflow model dynamically (no hard-coded class name) ----------
def _resolve_workflow_model() -> Tuple[type, Set[str]]:
    """
    Locate a workflow-like SQLAlchemy model in core.db.models by inspecting columns.
    Required columns: id, name, agent_id, recipe_id
    Prefer models that also have: trigger_type, trigger_value, next_run_at, last_run_at, enabled, status
    """
    from ..db import models as M  # lazy import

    # Try common names first (fast path)
    for cand in ("WorkflowDef", "Workflow", "WorkflowDefinition"):
        cls = getattr(M, cand, None)
        if cls is not None and getattr(cls, "__table__", None) is not None:
            cols = set(cls.__table__.columns.keys())
            if {"id", "name", "agent_id", "recipe_id"}.issubset(cols):
                return cls, cols

    # Fallback: inspect all SQLAlchemy models in the module
    best = None
    best_cols: Set[str] = set()
    best_score = -1
    for _, cls in vars(M).items():
        if not isinstance(cls, type):
            continue
        table = getattr(cls, "__table__", None)
        if table is None or not hasattr(table, "columns"):
            continue
        cols = set(table.columns.keys())
        if not {"id", "name", "agent_id", "recipe_id"}.issubset(cols):
            continue
        extras = {"trigger_type", "trigger_value", "next_run_at", "last_run_at", "enabled", "status"}
        score = len(extras & cols)
        if score > best_score:
            best, best_cols, best_score = cls, cols, score

    if best is None:
        raise ImportError(
            "Could not resolve a workflow model from core.db.models. "
            "Expected a SQLAlchemy class with columns: id, name, agent_id, recipe_id "
            "and ideally trigger_type/trigger_value/next_run_at/last_run_at/enabled/status."
        )
    return best, best_cols


WorkflowDef, _WF_COLS = _resolve_workflow_model()
# --------------------------------------------------------------------------------------


def list_workflows(db: Session):
    """Return all workflows ordered by id (ascending)."""
    return db.query(WorkflowDef).order_by(WorkflowDef.id.asc()).all()


def _workflow_name_exists(
    db: Session,
    name: str,
    *,
    exclude_id: Optional[int] = None,
) -> bool:
    q = db.query(WorkflowDef.id).filter(func.lower(WorkflowDef.name) == name.lower())
    if exclude_id is not None:
        q = q.filter(WorkflowDef.id != exclude_id)
    return q.first() is not None


def create_workflow(
    db: Session,
    name: str,
    agent_id: int,
    recipe_id: int,
    trigger_type: str = "manual",
    trigger_value: Optional[int] = None,
):
    """Create a workflow and schedule its next run if interval-triggered."""
    clean = (name or "").strip()
    if not clean:
        raise ValueError("Workflow name cannot be empty.")
    if _workflow_name_exists(db, clean):
        raise ValueError(f"Workflow '{clean}' already exists.")

    wf = WorkflowDef(
        name=clean,
        agent_id=agent_id,
        recipe_id=recipe_id,
    )

    # Optional fields guarded by presence in model
    if "trigger_type" in _WF_COLS:
        setattr(wf, "trigger_type", trigger_type)
    if "trigger_value" in _WF_COLS:
        setattr(wf, "trigger_value", trigger_value)
    if "status" in _WF_COLS:
        setattr(wf, "status", "yellow")
    if "enabled" in _WF_COLS:
        setattr(wf, "enabled", 1)

    if (trigger_type == "interval" and trigger_value and "next_run_at" in _WF_COLS):
        setattr(wf, "next_run_at", datetime.utcnow() + timedelta(minutes=int(trigger_value)))

    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


def update_workflow(db: Session, wf_id: int, **kwargs):
    """Update fields on a workflow with name-uniqueness and schedule semantics."""
    wf = db.query(WorkflowDef).filter(WorkflowDef.id == wf_id).first()
    if not wf:
        return None

    # Normalize / validate name if provided
    if "name" in kwargs and kwargs["name"] is not None:
        new_name = (kwargs["name"] or "").strip()
        if not new_name:
            raise ValueError("Workflow name cannot be empty.")
        if new_name.lower() != wf.name.lower() and _workflow_name_exists(db, new_name, exclude_id=wf_id):
            raise ValueError(f"Workflow '{new_name}' already exists.")
        kwargs["name"] = new_name

    recipe_changed = False
    for k, v in kwargs.items():
        if v is None:
            continue
        if k in _WF_COLS:
            if k == "recipe_id" and v != getattr(wf, k):
                recipe_changed = True
            setattr(wf, k, v)

        # Adjust schedule when trigger changes (only if columns exist)
        if k == "trigger_type" and "next_run_at" in _WF_COLS:
            if v == "manual":
                setattr(wf, "next_run_at", None)
            elif v == "interval" and kwargs.get("trigger_value"):
                setattr(wf, "next_run_at", datetime.utcnow() + timedelta(minutes=int(kwargs["trigger_value"])))

    # Reset status/schedule when the recipe changes
    if recipe_changed:
        if "last_run_at" in _WF_COLS:
            setattr(wf, "last_run_at", None)
        if "next_run_at" in _WF_COLS:
            setattr(wf, "next_run_at", None)
        if "status" in _WF_COLS:
            setattr(wf, "status", "yellow")

    db.commit()
    db.refresh(wf)
    return wf


def delete_workflow(db: Session, wf_id: int) -> bool:
    """Delete a workflow by id."""
    wf = db.query(WorkflowDef).filter(WorkflowDef.id == wf_id).first()
    if not wf:
        return False
    db.delete(wf)
    db.commit()
    return True


def compute_status(wf: WorkflowDef) -> str:
    """
    Return a traffic-light status string:
      - 'green'  if last run within 24h
      - 'yellow' if last run within 7 days or never run
      - 'red'    otherwise
    If the model lacks last_run_at, default to 'yellow'.
    """
    if "last_run_at" not in _WF_COLS:
        return "yellow"
    last = getattr(wf, "last_run_at", None)
    if not last:
        return "yellow"
    delta = datetime.utcnow() - last
    if delta.total_seconds() <= 24 * 3600:
        return "green"
    if delta.total_seconds() <= 7 * 24 * 3600:
        return "yellow"
    return "red"


def run_now(db: Session, wf_id: int):
    """
    Trigger a workflow immediately and record it in the shared RunStore.
    Safe for schema variants: only touches columns that exist.
    """
    wf = db.query(WorkflowDef).filter(WorkflowDef.id == wf_id).first()
    if not wf:
        return None

    store = make_runstore()
    with store.workflow_run(
        workflow_id=str(wf.id),
        name=getattr(wf, "name", f"wf-{wf.id}"),
        agent_id=getattr(wf, "agent_id"),
        recipe_id=getattr(wf, "recipe_id"),
        trigger="manual",
        meta={"workflow_name": getattr(wf, "name", f"wf-{wf.id}")},
    ) as rec:
        # Execute the recipe (primary DB run)
        run = execute_recipe_run(db, agent_id=getattr(wf, "agent_id"), recipe_id=getattr(wf, "recipe_id"))
        # Optional: log a step in runstore
        rec.step(
            phase="act",
            message=f"Executed recipe {getattr(run, 'recipe_id', getattr(wf, 'recipe_id', None))}",
            payload=None,
            result={"status": "completed"},
        )

    # Success path: update workflow timestamps/status if columns exist
    if "last_run_at" in _WF_COLS:
        setattr(wf, "last_run_at", datetime.utcnow())
    if "status" in _WF_COLS:
        setattr(wf, "status", compute_status(wf))
    if {"trigger_type", "trigger_value", "next_run_at"}.issubset(_WF_COLS):
        if getattr(wf, "trigger_type", None) == "interval" and getattr(wf, "trigger_value", None):
            setattr(wf, "next_run_at", datetime.utcnow() + timedelta(minutes=int(getattr(wf, "trigger_value"))))
    db.commit()
    db.refresh(wf)
    return run


def tick(db: Session) -> int:
    """
    Run all due interval-triggered workflows.
    If the model lacks scheduling columns, returns 0 (nothing to do).
    """
    sched_cols = {"enabled", "trigger_type", "next_run_at"}
    if not sched_cols.issubset(_WF_COLS):
        return 0

    now = datetime.utcnow()
    due = (
        db.query(WorkflowDef)
        .filter(
            getattr(WorkflowDef, "enabled") == 1,
            getattr(WorkflowDef, "trigger_type") == "interval",
            getattr(WorkflowDef, "next_run_at") != None,  # noqa: E711
            getattr(WorkflowDef, "next_run_at") <= now,
        )
        .all()
    )
    count = 0
    for wf in due:
        run_now(db, wf.id)
        count += 1
    return count
