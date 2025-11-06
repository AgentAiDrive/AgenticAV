# sma-av-streamlit/core/recipes/bundle_store.py
from __future__ import annotations

"""
Bundle store for Fixed Workflows.
- JSON-backed index under data/bundles/index.json
- Minimal dataclass model + CRUD helpers
"""

import json
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


# -------------------- API -------------------- #
def record_bundle(md: BundleMetadata) -> BundleMetadata:
    """Insert (or upsert by bundle_id) a bundle entry."""
    index = _load_index()
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


def list_bundles() -> List[BundleMetadata]:
    """Return metadata for all stored bundles."""
    index = _load_index()
    bundles: Iterable[Dict[str, Any]] = index.get("bundles", [])
    return [BundleMetadata.from_dict(item) for item in bundles]


def get_bundle(bundle_id: str) -> Optional[BundleMetadata]:
    """Fetch a single bundle by id."""
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
    """Update fields on a bundle entry and save. Returns updated entry or None if not found."""
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

        deleted = True
        if remove_files:
            try:
                from pathlib import Path as _P  # local alias
                orch = _P(raw.get("orchestrator_path", ""))
                if orch.is_file():
                    orch.unlink(missing_ok=True)
            except Exception:
                pass

            for p in (raw.get("fixed_agents") or {}).values():
                try:
                    pp = _P(p)
                    if pp.is_file():
                        pp.unlink(missing_ok=True)
                except Exception:
                    pass

    if deleted:
        index["bundles"] = keep
        _save_index(index)

    return deleted

# --- Back-compat alias for older callers ---
def record_bundle_metadata(md: BundleMetadata) -> BundleMetadata:
    """Compatibility shim: older code imports record_bundle_metadata."""
    return record_bundle(md)
