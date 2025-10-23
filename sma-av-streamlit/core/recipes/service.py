
# sma-av-streamlit/core/recipes/service.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import os

from core.db.session import get_session
from core.db.models import Recipe

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

_APP_RECIPES_DIR = Path(__file__).resolve().parents[2] / "recipes"
_USER_RECIPES_DIR = Path.home() / ".sma_avops" / "recipes"

def _read_file_if_exists(path: Path) -> Optional[str]:
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return None

def _candidate_paths(yaml_path: str | None) -> List[Path]:
    paths: List[Path] = []
    if not yaml_path:
        return paths
    p = Path(yaml_path)
    if p.is_absolute():
        paths.append(p)
    paths.append(_APP_RECIPES_DIR / p)
    paths.append(_USER_RECIPES_DIR / p.name)
    extra_roots = os.getenv("AVOPS_RECIPES_DIRS", "")
    for root in [r.strip() for r in extra_roots.split(",") if r.strip()]:
        paths.append(Path(root) / p.name)
    # dedupe
    seen = set(); uniq: List[Path] = []
    for x in paths:
        s = str(x)
        if s not in seen:
            seen.add(s); uniq.append(x)
    return uniq

def load_recipe_yaml_text(recipe: Recipe) -> str:
    y_inline: Optional[str] = getattr(recipe, "yaml", None)
    if y_inline and str(y_inline).strip():
        return y_inline
    for p in _candidate_paths(getattr(recipe, "yaml_path", None)):
        txt = _read_file_if_exists(p)
        if txt is not None:
            return txt
    raise FileNotFoundError(f"Recipe YAML not found for '{getattr(recipe, 'name', '?')}'. Tried: {[str(p) for p in _candidate_paths(getattr(recipe, 'yaml_path', None))]}")

def _resolve_recipe(db, recipe_or_id: Recipe | int) -> Recipe:
    if isinstance(recipe_or_id, Recipe):
        return recipe_or_id
    db_get = getattr(db, 'get', None)
    if callable(db_get):
        obj = db.get(Recipe, int(recipe_or_id))
    else:
        obj = db.query(Recipe).filter(Recipe.id == int(recipe_or_id)).first()
    if not obj:
        raise LookupError(f"Recipe id {recipe_or_id} not found")
    return obj

def _parse_yaml(text: str) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to parse recipe YAML (package 'pyyaml' missing).")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Recipe YAML must parse to a mapping/dict, got {type(data).__name__}")
    return data

def load_recipe_dict(recipe_or_id_or_path: Union[Recipe, int, str], db=None) -> Dict[str, Any]:
    """Universal loader used by engine:
    - Recipe instance → parse YAML from DB inline or file
    - int id → resolve then parse
    - str path → treat as yaml_path and search in app/user dirs
    """
    if isinstance(recipe_or_id_or_path, str):
        # path-like
        for p in _candidate_paths(recipe_or_id_or_path):
            txt = _read_file_if_exists(p)
            if txt is not None:
                return _parse_yaml(txt)
        raise FileNotFoundError(f"Recipe YAML not found for path '{recipe_or_id_or_path}'. Tried: {[str(p) for p in _candidate_paths(recipe_or_id_or_path)]}")
    if db is None:
        with get_session() as _db:
            rec = _resolve_recipe(_db, recipe_or_id_or_path)  # type: ignore[arg-type]
            return _parse_yaml(load_recipe_yaml_text(rec))
    else:
        rec = _resolve_recipe(db, recipe_or_id_or_path)  # type: ignore[arg-type]
        return _parse_yaml(load_recipe_yaml_text(rec))
