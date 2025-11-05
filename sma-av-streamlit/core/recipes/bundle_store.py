"""Helpers for persisting and loading compiled SOP bundles.

A "bundle" groups a single orchestrator recipe with any fixed-agent
recipes generated alongside it.  Metadata is persisted to a JSON index so the
Fixed Workflows page can discover newly created bundles.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .storage import BASE


def _slugify(value: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in value).strip("-")


BUNDLE_DIR = BASE / "recipes" / "bundles"
INDEX_PATH = BUNDLE_DIR / "index.json"


@dataclass
class BundleMetadata:
    """Structured view of a stored bundle entry."""

    bundle_id: str
    display_name: str
    orchestrator_path: str
    fixed_agents: Dict[str, str]
    context_hints: Optional[Dict[str, Any]]
    created_at: str

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BundleMetadata":
        return cls(
            bundle_id=payload.get("bundle_id", ""),
            display_name=payload.get("display_name", ""),
            orchestrator_path=payload.get("orchestrator_path", ""),
            fixed_agents=dict(payload.get("fixed_agents", {})),
            context_hints=payload.get("context_hints") or None,
            created_at=payload.get("created_at", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.context_hints is None:
            data["context_hints"] = None
        return data


def _load_index() -> Dict[str, Any]:
    if INDEX_PATH.exists():
        try:
            with INDEX_PATH.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict) and "bundles" in payload:
                return payload
        except json.JSONDecodeError:
            # Fall through to reset the index if it's corrupted.
            pass
    return {"bundles": []}


def _save_index(index: Dict[str, Any]) -> None:
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_PATH.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2, ensure_ascii=False)


def record_bundle_metadata(
    name: str,
    ctx: Dict[str, Any],
    orchestrator_path: Path,
    fixed_agent_paths: Dict[str, Path],
) -> BundleMetadata:
    """Insert or update bundle metadata in the JSON index."""

    bundle_id = _slugify(name or "workflow-from-sop")
    display_name = ctx.get("display_name") or name

    # Strip known keys so we store only contextual hints.
    excluded = {"name", "display_name"}
    hints = ctx.get("context") or {
        k: v for k, v in ctx.items() if k not in excluded and v not in (None, "")
    }
    context_hints: Optional[Dict[str, Any]] = hints or None

    metadata = BundleMetadata(
        bundle_id=bundle_id,
        display_name=display_name,
        orchestrator_path=str(orchestrator_path),
        fixed_agents={agent: str(path) for agent, path in fixed_agent_paths.items()},
        context_hints=context_hints,
        created_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )

    index = _load_index()
    bundles: List[Dict[str, Any]] = list(index.get("bundles", []))

    existing_idx = next(
        (i for i, entry in enumerate(bundles) if entry.get("bundle_id") == bundle_id),
        None,
    )
    if existing_idx is None:
        bundles.append(metadata.to_dict())
    else:
        bundles[existing_idx] = metadata.to_dict()

    index["bundles"] = bundles
    _save_index(index)

    return metadata


def list_bundles() -> List[BundleMetadata]:
    """Return metadata for all stored bundles."""

    index = _load_index()
    bundles: Iterable[Dict[str, Any]] = index.get("bundles", [])
    return [BundleMetadata.from_dict(item) for item in bundles]
