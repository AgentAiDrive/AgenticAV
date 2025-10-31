# core/workflow/service.py — lazy model resolution + Core fallback (no import-time errors)
from __future__ import annotations

from typing import Optional, Tuple, Set, Literal, Union, List
from types import SimpleNamespace
from datetime import datetime, timedelta

from sqlalchemy import (
    Table, Column, Integer, String, DateTime, MetaData, select,
    update as sqla_update, insert as sqla_insert, delete as sqla_delete, inspect, func
)
from sqlalchemy.orm import Session

from .engine import execute_recipe_run
from core.runstore_factory import make_runstore  # shared store
from core.db.models import Base  # reuse project metadata/engine

# --------------------------------------------------------------------------------------
# Internal backend cache: ('orm', Model, cols) | ('core', Table, cols)
_BACKEND: Optional[Tuple[Literal['orm','core'], object, Set[str]]] = None


def _try_resolve_workflow_model() -> Optional[Tuple[type, Set[str]]]:
    """
    Try to locate a workflow-like SQLAlchemy ORM model in core.db.models by inspecting columns.
    Required columns: id, name, agent_id, recipe_id
    Prefer models that also have: trigger_type, trigger_value, next_run_at, last_run_at, enabled, status
    """
    try:
        from ..db import models as M  # lazy import
    except Exception:
        return None

    # Fast path: common class names
    for cand in ("WorkflowDef", "Workflow", "WorkflowDefinition"):
        cls = getattr(M, cand, None)
        table = getattr(cls, "__table__", None) if cls is not None else None
        if table is not None and hasattr(table, "columns"):
            cols = set(table.columns.keys())
            if {"id", "name", "agent_id", "recipe_id"}.issubset(cols):
                return cls, cols

    # Scan all ORM models in module
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
        return None
    return best, best_cols


def _ensure_core_table(session: Session) -> Tuple[Table, Set[str]]:
    """Ensure a portable Core table exists for workflows; return (table, cols)."""
    bind = session.get_bind()
    metadata: MetaData = Base.metadata
    insp = inspect(bind)

    if "workflows" in insp.get_table_names():
        tbl = Table("workflows", metadata, autoload_with=bind)
        return tbl, set(tbl.c.keys())

    # Create a schema that covers what the UI/service may touch
    tbl = Table(
        "workflows", metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("name", String(255), nullable=False, unique=True),
        Column("agent_id", Integer, nullable=False),
        Column("recipe_id", Integer, nullable=False),
        Column("trigger_type", String(32), nullable=False, default="manual"),
        Column("trigger_value", Integer, nullable=True),  # minutes
        Column("enabled", Integer, nullable=False, default=1),
        Column("status", String(16), nullable=True),  # 'green'/'yellow'/'red'
        Column("last_run_at", DateTime(timezone=False), nullable=True),
        Column("next_run_at", DateTime(timezone=False), nullable=True),
    )
    metadata.create_all(bind=bind, tables=[tbl])
    return tbl, set(tbl.c.keys())


def _get_backend(session: Session) -> Tuple[Literal['orm','core'], object, Set[str]]:
    """
    Lazily determine which backend to use:
      1) Prefer ORM model discovery
      2) Fallback to Core table (create if missing)
    Cached after first successful resolution.
    """
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND

    resolved = _try_resolve_workflow_model()
    if resolved is not None:
        model, cols = resolved
        _BACKEND = ('orm', model, cols)
        return _BACKEND

    tbl, cols = _ensure_core_table(session)
    _BACKEND = ('core', tbl, cols)
    return _BACKEND


# --------------------------------------------------------------------------------------
# Helpers

def _utcnow() -> datetime:
    # Keep naive UTC to match your previous compute_status logic
    return datetime.utcnow()


def _row_to_ns(row) -> SimpleNamespace:
    m = row._mapping if hasattr(row, "_mapping") else row
    return SimpleNamespace(**{k: m[k] for k in m.keys()})


def _getattr_or(row_or_obj, name, default=None):
    if hasattr(row_or_obj, name):
        return getattr(row_or_obj, name)
    if isinstance(row_or_obj, dict):
        return row_or_obj.get(name, default)
    # Row from SQLAlchemy Core
    try:
        m = row_or_obj._mapping  # type: ignore[attr-defined]
        return m.get(name, default) if hasattr(m, "get") else m[name]
    except Exception:
        return default


# --------------------------------------------------------------------------------------
# Public API (kept identical to your original signatures)

def list_workflows(db: Session):
    """Return all workflows ordered by id (ascending)."""
    kind, obj, _cols = _get_backend(db)
    if kind == 'orm':
        Model = obj  # type: ignore[assignment]
        return db.query(Model).order_by(Model.id.asc()).all()
    else:
        tbl: Table = obj  # type: ignore[assignment]
        rows = db.execute(select(tbl).order_by(tbl.c.id.asc())).all()
        return [_row_to_ns(r) for r in rows]


def _workflow_name_exists(
    db: Session,
    name: str,
    *,
    exclude_id: Optional[int] = None,
) -> bool:
    kind, obj, _cols = _get_backend(db)
    if kind == 'orm':
        Model = obj  # type: ignore[assignment]
        q = db.query(Model.id).filter(func.lower(Model.name) == name.lower())
        if exclude_id is not None:
            q = q.filter(Model.id != exclude_id)
        return q.first() is not None
    else:
        tbl: Table = obj  # type: ignore[assignment]
        cond = func.lower(tbl.c.name) == name.lower()
        if exclude_id is not None:
            cond = cond & (tbl.c.id != int(exclude_id))
        return db.execute(select(tbl.c.id).where(cond)).first() is not None


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

    kind, obj, cols = _get_backend(db)
    if kind == 'orm':
        Model = obj  # type: ignore[assignment]
        wf = Model(
            name=clean,
            agent_id=agent_id,
            recipe_id=recipe_id,
        )
        if "trigger_type" in cols:
            setattr(wf, "trigger_type", trigger_type)
        if "trigger_value" in cols:
            setattr(wf, "trigger_value", trigger_value)
        if "status" in cols:
            setattr(wf, "status", "yellow")
        if "enabled" in cols:
            setattr(wf, "enabled", 1)
        if (trigger_type == "interval" and trigger_value and "next_run_at" in cols):
            setattr(wf, "next_run_at", _utcnow() + timedelta(minutes=int(trigger_value)))

        db.add(wf)
        db.commit()
        db.refresh(wf)
        return wf
    else:
        tbl: Table = obj  # type: ignore[assignment]
        values = dict(
            name=clean,
            agent_id=int(agent_id),
            recipe_id=int(recipe_id),
            trigger_type=trigger_type,
            trigger_value=int(trigger_value) if trigger_value else None,
            enabled=1,
            status="yellow",
            last_run_at=None,
            next_run_at=(_utcnow() + timedelta(minutes=int(trigger_value)))
                       if (trigger_type == "interval" and trigger_value) else None,
        )
        row = db.execute(sqla_insert(tbl).values(**values).returning(tbl)).first()
        db.commit()
        return _row_to_ns(row)


def update_workflow(db: Session, wf_id: int, **kwargs):
    """Update fields on a workflow with name-uniqueness and schedule semantics."""
    kind, obj, cols = _get_backend(db)

    # Normalize name if provided
    if "name" in kwargs and kwargs["name"] is not None:
        new_name = (kwargs["name"] or "").strip()
        if not new_name:
            raise ValueError("Workflow name cannot be empty.")
        if _workflow_name_exists(db, new_name, exclude_id=int(wf_id)):
            raise ValueError(f"Workflow '{new_name}' already exists.")
        kwargs["name"] = new_name

    if kind == 'orm':
        Model = obj  # type: ignore[assignment]
        wf = db.query(Model).filter(Model.id == int(wf_id)).first()
        if not wf:
            return None

        recipe_changed = False
        for k, v in kwargs.items():
            if v is None:
                continue
            if k in cols:
                if k == "recipe_id" and v != getattr(wf, k):
                    recipe_changed = True
                setattr(wf, k, v)

            # Adjust schedule when trigger changes
            if k == "trigger_type" and "next_run_at" in cols:
                if v == "manual":
                    setattr(wf, "next_run_at", None)
                elif v == "interval" and kwargs.get("trigger_value"):
                    setattr(wf, "next_run_at", _utcnow() + timedelta(minutes=int(kwargs["trigger_value"])))

        if recipe_changed:
            if "last_run_at" in cols:
                setattr(wf, "last_run_at", None)
            if "next_run_at" in cols:
                setattr(wf, "next_run_at", None)
            if "status" in cols:
                setattr(wf, "status", "yellow")

        db.commit()
        db.refresh(wf)
        return wf

    else:
        tbl: Table = obj  # type: ignore[assignment]
        # Only update known columns
        allowed = cols
        data = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

        # Adjust schedule when trigger changes
        if data.get("trigger_type") == "manual" and "next_run_at" in cols:
            data["next_run_at"] = None
        elif (data.get("trigger_type") == "interval" and kwargs.get("trigger_value") and "next_run_at" in cols):
            data["next_run_at"] = _utcnow() + timedelta(minutes=int(kwargs["trigger_value"]))

        db.execute(sqla_update(tbl).where(tbl.c.id == int(wf_id)).values(**data))
        db.commit()
        # Return the updated row for symmetry
        row = db.execute(select(tbl).where(tbl.c.id == int(wf_id))).first()
        return _row_to_ns(row) if row else None


def delete_workflow(db: Session, wf_id: int) -> bool:
    """Delete a workflow by id."""
    kind, obj, _cols = _get_backend(db)
    if kind == 'orm':
        Model = obj  # type: ignore[assignment]
        wf = db.query(Model).filter(Model.id == int(wf_id)).first()
        if not wf:
            return False
        db.delete(wf)
        db.commit()
        return True
    else:
        tbl: Table = obj  # type: ignore[assignment]
        res = db.execute(sqla_delete(tbl).where(tbl.c.id == int(wf_id)))
        db.commit()
        return (res.rowcount or 0) > 0


def compute_status(wf) -> str:
    """
    Return a traffic-light status string:
      - 'green'  if last run within 24h
      - 'yellow' if last run within 7 days or never run
      - 'red'    otherwise
    If the model lacks last_run_at, default to 'yellow'.
    """
    # Determine available columns from cached backend (safe if not resolved yet)
    global _BACKEND
    cols: Set[str] = _BACKEND[2] if _BACKEND else set()
    if "last_run_at" not in cols:
        return "yellow"

    last = _getattr_or(wf, "last_run_at", None)
    if not last:
        return "yellow"
    delta = _utcnow() - last
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
    kind, obj, cols = _get_backend(db)

    # Fetch wf
    if kind == 'orm':
        Model = obj  # type: ignore[assignment]
        wf = db.query(Model).filter(Model.id == int(wf_id)).first()
        if not wf:
            return None
        agent_id = getattr(wf, "agent_id")
        recipe_id = getattr(wf, "recipe_id")
        wf_name = getattr(wf, "name", f"wf-{wf_id}")
    else:
        tbl: Table = obj  # type: ignore[assignment]
        row = db.execute(select(tbl).where(tbl.c.id == int(wf_id))).first()
        if not row:
            return None
        wf = _row_to_ns(row)
        agent_id = wf.agent_id
        recipe_id = wf.recipe_id
        wf_name = wf.name

    store = make_runstore()
    with store.workflow_run(
        workflow_id=str(wf_id),
        name=wf_name,
        agent_id=agent_id,
        recipe_id=recipe_id,
        trigger="manual",
        meta={"workflow_name": wf_name},
    ) as rec:
        run = execute_recipe_run(db, agent_id=agent_id, recipe_id=recipe_id)
        rec.step(
            phase="act",
            message=f"Executed recipe {getattr(run, 'recipe_id', recipe_id)}",
            payload=None,
            result={"status": "completed"},
        )

    # Update timestamps/status if present
    now = _utcnow()
    if kind == 'orm':
        if "last_run_at" in cols:
            setattr(wf, "last_run_at", now)
        if "status" in cols:
            setattr(wf, "status", compute_status(wf))
        if {"trigger_type", "trigger_value", "next_run_at"}.issubset(cols):
            if getattr(wf, "trigger_type", None) == "interval" and getattr(wf, "trigger_value", None):
                setattr(wf, "next_run_at", now + timedelta(minutes=int(getattr(wf, "trigger_value"))))
        db.commit()
        db.refresh(wf)
        return run
    else:
        tbl: Table = obj  # type: ignore[assignment]
        next_run_at = None
        if {"trigger_type", "trigger_value", "next_run_at"}.issubset(cols):
            ttype = _getattr_or(wf, "trigger_type")
            tval = _getattr_or(wf, "trigger_value")
            if ttype == "interval" and tval:
                next_run_at = now + timedelta(minutes=int(tval))

        data = {}
        if "last_run_at" in cols:
            data["last_run_at"] = now
        if "status" in cols:
            # recompute on the prospective new last_run_at
            data["status"] = "green"
        if "next_run_at" in cols:
            data["next_run_at"] = next_run_at

        if data:
            db.execute(sqla_update(tbl).where(tbl.c.id == int(wf_id)).values(**data))
            db.commit()
        return run


def tick(db: Session) -> int:
    """
    Run all due interval-triggered workflows.
    If the model lacks scheduling columns, returns 0 (nothing to do).
    """
    kind, obj, cols = _get_backend(db)
    sched_cols = {"enabled", "trigger_type", "next_run_at"}
    if not sched_cols.issubset(cols):
        return 0

    now = _utcnow()
    if kind == 'orm':
        Model = obj  # type: ignore[assignment]
        due = (
            db.query(Model)
            .filter(
                getattr(Model, "enabled") == 1,
                getattr(Model, "trigger_type") == "interval",
                getattr(Model, "next_run_at") != None,  # noqa: E711
                getattr(Model, "next_run_at") <= now,
            )
            .all()
        )
        count = 0
        for wf in due:
            run_now(db, int(getattr(wf, "id")))
            count += 1
        return count
    else:
        tbl: Table = obj  # type: ignore[assignment]
        due_rows = db.execute(
            select(tbl).where(
                (tbl.c.enabled == 1)
                & (tbl.c.trigger_type == "interval")
                & (tbl.c.next_run_at != None)  # noqa: E711
                & (tbl.c.next_run_at <= now)
            )
        ).all()
        count = 0
        for row in due_rows:
            wf_id = int(row._mapping["id"])
            try:
                run_now(db, wf_id)
                count += 1
            except Exception:
                db.rollback()
                continue
        return count
