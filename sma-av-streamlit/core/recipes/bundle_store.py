from __future__ import annotations

"""
Bundle store for Fixed Workflows.
- JSON-backed index under data/bundles/index.json
- Minimal dataclass model + CRUD helpers
- Flexible record_bundle: accepts a BundleMetadata OR keyword args (incl. legacy 'name')
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DATA_DIR = Path("data/bundles")
INDEX_PATH = DATA_DIR / "index.json"


# -------------------- Model -------------------- #
@dataclass
class BundleMetadata:
    bundle_id: str
    orchestrator_path: str
    display_name: Optional[str] = None
    fixed_agents: Dict[str, str] = field(default_factory=dict)
    context_hints: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "display_name": self.display_name,
            "orchestrator_path": self.orchestrator_path,
            "fixed_agents": dict(self.fixed_agents or {}),
            "context_hints": dict(self.context_hints or {}),
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BundleMetadata":
        return BundleMetadata(
            bundle_id=d.get("bundle_id") or d.get("id") or "",
            display_name=d.get("display_name"),
            orchestrator_path=d.get("orchestrator_path") or "",
            fixed_agents=d.get("fixed_agents") or {},
            context_hints=d.get("context_hints") or {},
            created_at=d.get("created_at")
            or datetime.utcnow().isoformat(timespec="seconds")
            + "Z",
        )


# -------------------- Storage -------------------- #
def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> Dict[str, Any]:
    _ensure_dirs()
    if not INDEX_PATH.exists():
        return {"bundles": []}
    try:
        raw = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"bundles": []}
        raw.setdefault("bundles", [])
        return raw
    except Exception:
        return {"bundles": []}


def _save_index(index: Dict[str, Any]) -> None:
    _ensure_dirs()
    INDEX_PATH.write_text(json.dumps(index, indent=2), encoding="utf-8")


# -------------------- Utils -------------------- #
def _slug(s: Optional[str]) -> str:
    if not s:
        return "bundle"
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "bundle"


def _gen_bundle_id(display_name: Optional[str]) -> str:
    return f"{_slug(display_name)}-{uuid.uuid4().hex[:8]}"


def _upsert(index: Dict[str, Any], md: BundleMetadata) -> BundleMetadata:
    bundles: List[Dict[str, Any]] = index.get("bundles", [])
    for i, raw in enumerate(bundles):
        if raw.get("bundle_id") == md.bundle_id:
            bundles[i] = md.to_dict()
            index["bundles"] = bundles
            _save_index(index)
            return md
    bundles.append(md.to_dict())
    index["bundles"] = bundles
    _save_index(index)
    return md


# -------------------- API -------------------- #
def record_bundle(
    md_or: Optional[BundleMetadata] = None,
    /,
    **kwargs: Any,
) -> BundleMetadata:
    """
    Flexible entry point to record (upsert) a bundle.

    Usage A (object):
        record_bundle(BundleMetadata(...))

    Usage B (kwargs):
        record_bundle(
            name="My SOP bundle",                # alias for display_name
            orchestrator_path="data/recipes/.../orchestrator.yaml",
            fixed_agents={"kb": "data/recipes/.../fixed_kb.yaml"},
            context_hints={"topic": "Zoom Rooms"}
            # optional: bundle_id="my-sop-1234"
            # optional: context=... (alias for context_hints)
            # optional: fixed_agent_paths=... (alias for fixed_agents)
            # optional: display_name=... (canonical)
        )
    """
    index = _load_index()

    # Case A: caller provided a dataclass
    if isinstance(md_or, BundleMetadata):
        return _upsert(index, md_or)

    # Case B: kwargs normalization
    display_name = kwargs.get("display_name") or kwargs.get("name")
    orchestrator_path = kwargs.get("orchestrator_path")
    if not orchestrator_path:
        raise ValueError("record_bundle: 'orchestrator_path' is required")

    bundle_id = kwargs.get("bundle_id") or _gen_bundle_id(display_name)
    fixed_agents = kwargs.get("fixed_agents") or kwargs.get("fixed_agent_paths") or {}
    context_hints = kwargs.get("context_hints") or kwargs.get("context") or {}

    md = BundleMetadata(
        bundle_id=bundle_id,
        display_name=display_name,
        orchestrator_path=str(orchestrator_path),
        fixed_agents=dict(fixed_agents or {}),
        context_hints=dict(context_hints or {}),
    )
    return _upsert(index, md)


def record_bundle_metadata(md: BundleMetadata) -> BundleMetadata:
    """
    Back-compat alias: some older modules import record_bundle_metadata(md).
    """
    return record_bundle(md)


def list_bundles() -> List[BundleMetadata]:
    index = _load_index()
    bundles: Iterable[Dict[str, Any]] = index.get("bundles", [])
    return [BundleMetadata.from_dict(item) for item in bundles]


def get_bundle(bundle_id: str) -> Optional[BundleMetadata]:
    for b in list_bundles():
        if b.bundle_id == bundle_id:
            return b
    return None


def update_bundle(
    bundle_id: str,
    *,
    display_name: Optional[str] = None,
    orchestrator_path: Optional[str] = None,
    fixed_agents: Optional[Dict[str, str]] = None,
    context_hints: Optional[Dict[str, Any]] = None,
) -> Optional[BundleMetadata]:
    index = _load_index()
    bundles: List[Dict[str, Any]] = index.get("bundles", [])
    for i, raw in enumerate(bundles):
        if raw.get("bundle_id") == bundle_id:
            md = BundleMetadata.from_dict(raw)
            if display_name is not None:
                md.display_name = display_name
            if orchestrator_path is not None:
                md.orchestrator_path = orchestrator_path
            if fixed_agents is not None:
                md.fixed_agents = fixed_agents
            if context_hints is not None:
                md.context_hints = context_hints
            bundles[i] = md.to_dict()
            index["bundles"] = bundles
            _save_index(index)
            return md
    return None


def delete_bundle(bundle_id: str, *, remove_files: bool = True) -> bool:
    """
    Delete a bundle from the index, optionally removing referenced YAML files.
    Returns True if deleted, False if not found.
    """
    index = _load_index()
    bundles: List[Dict[str, Any]] = index.get("bundles", [])
    keep: List[Dict[str, Any]] = []
    deleted = False

    for raw in bundles:
        if raw.get("bundle_id") != bundle_id:
            keep.append(raw)
            continue

    # remove files if requested
        deleted = True
        if remove_files:
            try:
                orch = Path(raw.get("orchestrator_path", ""))
                if orch.is_file():
                    orch.unlink(missing_ok=True)
            except Exception:
                pass
            for p in (raw.get("fixed_agents") or {}).values():
                try:
                    pp = Path(p)
                    if pp.is_file():
                        pp.unlink(missing_ok=True)
                except Exception:
                    pass

    if deleted:
        index["bundles"] = keep
        _save_index(index)

    return deleted
