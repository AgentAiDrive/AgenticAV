"""Helpers for persisting and loading compiled SOP bundles.

A "bundle" groups a single orchestrator recipe with any fixed-agent
recipes generated alongside it.  Metadata is persisted to a JSON index so the
Fixed Workflows page can discover newly created bundles.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import io
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import zipfile

from core.io.port import export_zip, import_zip

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


def _resolve_path(path_like: str) -> Path:
    path = Path(path_like)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _relative_from_cwd(path: Path) -> str:
    try:
        rel = path.relative_to(Path.cwd())
        return rel.as_posix()
    except ValueError:
        pass

    # Fallback: keep only the filename to avoid leaking absolute paths into the bundle
    return path.name


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


def get_bundle(bundle_id: str) -> Optional[BundleMetadata]:
    return next((b for b in list_bundles() if b.bundle_id == bundle_id), None)


def update_bundle(metadata: BundleMetadata) -> BundleMetadata:
    index = _load_index()
    bundles: List[Dict[str, Any]] = list(index.get("bundles", []))

    for i, entry in enumerate(bundles):
        if entry.get("bundle_id") == metadata.bundle_id:
            bundles[i] = metadata.to_dict()
            break
    else:
        bundles.append(metadata.to_dict())

    index["bundles"] = bundles
    _save_index(index)
    return metadata


def delete_bundle(bundle_id: str, *, remove_artifacts: bool = True) -> bool:
    index = _load_index()
    bundles: List[Dict[str, Any]] = list(index.get("bundles", []))
    target_idx = next(
        (i for i, entry in enumerate(bundles) if entry.get("bundle_id") == bundle_id),
        None,
    )

    if target_idx is None:
        return False

    entry = bundles.pop(target_idx)
    index["bundles"] = bundles
    _save_index(index)

    if remove_artifacts:
        paths = [entry.get("orchestrator_path")]
        paths.extend((entry.get("fixed_agents") or {}).values())
        for ctx_path in list_bundle_contexts(bundle_id).values():
            paths.append(_relative_from_cwd(ctx_path))
        for path_like in filter(None, paths):
            try:
                path = _resolve_path(path_like)
                if path.exists() and path.is_file():
                    path.unlink()
            except Exception:
                # Intentionally swallow errors so deletion of metadata succeeds even
                # if the filesystem artifact was already removed.
                pass

        ctx_dir = bundle_context_dir(bundle_id)
        if ctx_dir.exists():
            try:
                for child in sorted(ctx_dir.glob("**/*"), reverse=True):
                    if child.is_file():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        child.rmdir()
            except Exception:
                pass

    return True


def bundle_context_dir(bundle_id: str) -> Path:
    return BUNDLE_DIR / bundle_id / "contexts"


def list_bundle_contexts(bundle_id: str) -> Dict[str, Path]:
    ctx_dir = bundle_context_dir(bundle_id)
    if not ctx_dir.exists():
        return {}
    out: Dict[str, Path] = {}
    for path in ctx_dir.glob("*.json"):
        out[path.stem] = path
    return out


def load_bundle_context(bundle_id: str, name: str) -> Dict[str, Any]:
    paths = list_bundle_contexts(bundle_id)
    if name not in paths:
        return {}
    try:
        return json.loads(paths[name].read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_bundle_context(
    bundle_id: str,
    name: str,
    payload: Dict[str, Any],
) -> Path:
    ctx_dir = bundle_context_dir(bundle_id)
    ctx_dir.mkdir(parents=True, exist_ok=True)
    path = ctx_dir / f"{_slugify(name or 'context')}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return path


def delete_bundle_context(bundle_id: str, name: str) -> bool:
    paths = list_bundle_contexts(bundle_id)
    target = paths.get(name)
    if not target or not target.exists():
        return False
    target.unlink()
    return True


def export_bundle_zip(metadata: BundleMetadata) -> Tuple[bytes, Dict[str, Any]]:
    base_bytes, report = export_zip(include=[], recipes_dir="data/recipes")
    existing_files: Dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(base_bytes), "r") as base_zip:
        for info in base_zip.infolist():
            existing_files[info.filename] = base_zip.read(info.filename)

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in existing_files.items():
            z.writestr(name, content)

        z.writestr(
            "bundle/metadata.json",
            json.dumps(metadata.to_dict(), indent=2, ensure_ascii=False),
        )

        def _write_artifact(path_like: str) -> None:
            if not path_like:
                return
            path = _resolve_path(path_like)
            if not path.exists() or not path.is_file():
                return
            rel = _relative_from_cwd(path)
            z.writestr(
                f"bundle/artifacts/{rel}",
                path.read_bytes(),
            )

        _write_artifact(metadata.orchestrator_path)
        for rel_path in metadata.fixed_agents.values():
            _write_artifact(rel_path)

        for name, ctx_path in list_bundle_contexts(metadata.bundle_id).items():
            rel = _relative_from_cwd(ctx_path)
            z.writestr(
                f"bundle/contexts/{rel}",
                ctx_path.read_bytes(),
            )

    return out.getvalue(), report


def import_bundle_zip(zip_bytes: bytes, *, merge: str = "overwrite") -> BundleMetadata:
    import_zip(zip_bytes, recipes_dir="data/recipes", merge=merge, dry_run=True)

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
        try:
            payload = json.loads(z.read("bundle/metadata.json").decode("utf-8"))
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Bundle archive missing bundle/metadata.json") from exc

        metadata = BundleMetadata.from_dict(payload)

        def _extract(path_like: str) -> None:
            if not path_like:
                return
            rel = Path(path_like)
            if rel.is_absolute():
                rel = rel.relative_to(Path(rel.anchor))
            target = _resolve_path(rel.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                data = z.read(f"bundle/artifacts/{rel.as_posix()}")
            except KeyError:
                return
            target.write_bytes(data)

        _extract(metadata.orchestrator_path)
        for rel_path in metadata.fixed_agents.values():
            _extract(rel_path)

        ctx_prefix = "bundle/contexts/"
        for name in z.namelist():
            if not name.startswith(ctx_prefix):
                continue
            rel = name[len(ctx_prefix) :]
            target = _resolve_path(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))

    return update_bundle(metadata)
