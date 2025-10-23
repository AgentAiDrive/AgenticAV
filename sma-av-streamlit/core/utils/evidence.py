# core/utils/evidence.py
from __future__ import annotations

from typing import Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import json

def _resolve_evidence_model():
    """
    Try to find a suitable evidence-like model in core.db.models.
    Accepts common variants and validates it has a run_id and some JSON/text column.
    """
    try:
        from ..db import models as M  # import lazily to avoid hard failures at import time
    except Exception:
        return None

    candidates = [
        "Evidence",          # common
        "RunEvidence",       # variant
        "EvidenceRec",       # variant
        "Artifact",          # some repos use this name
        "RunArtifact",       # variant
    ]

    for name in candidates:
        cls = getattr(M, name, None)
        if cls is None:
            continue
        table = getattr(cls, "__table__", None)
        cols = set(table.columns.keys()) if table is not None and hasattr(table, "columns") else set()
        if "run_id" in cols and ({"data", "payload", "json", "content"} & cols):
            return cls
    return None

_EVIDENCE_MODEL = None

def _get_model():
    global _EVIDENCE_MODEL
    if _EVIDENCE_MODEL is not None:
        return _EVIDENCE_MODEL
    _EVIDENCE_MODEL = _resolve_evidence_model()
    return _EVIDENCE_MODEL

def _coerce_json(obj: Any) -> Any:
    # Best effort to serialize arbitrary objects
    if isinstance(obj, (dict, list, str, int, float, bool)) or obj is None:
        return obj
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return str(obj)

def attach_json(
    db: Session,
    run_id: int,
    obj: Any,
    *,
    label: Optional[str] = None,
    kind: str = "json",
) -> Optional[int]:
    """
    Attach a JSON-like payload as evidence for a run. If no compatible model
    is found, this function is a no-op and returns None.
    """
    EV = _get_model()
    if EV is None:
        # Graceful no-op when the schema doesn't include an evidence table.
        return None

    rec = EV()
    # Required/likely fields
    if hasattr(rec, "run_id"):
        setattr(rec, "run_id", run_id)
    if hasattr(rec, "kind"):
        setattr(rec, "kind", kind)
    if hasattr(rec, "label"):
        setattr(rec, "label", label or "")

    # Choose a payload column
    payload_field = None
    for f in ("data", "payload", "json", "content"):
        if hasattr(rec, f):
            payload_field = f
            break
    if payload_field:
        setattr(rec, payload_field, _coerce_json(obj))

    # Stamp time if model has created_at
    if hasattr(rec, "created_at") and getattr(rec, "created_at") is None:
        setattr(rec, "created_at", datetime.utcnow())

    db.add(rec)
    db.commit()
    try:
        db.refresh(rec)
    except Exception:
        pass
    return getattr(rec, "id", None)
