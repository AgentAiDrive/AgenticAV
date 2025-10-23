# core/recipes/service.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any, List
import os

from core.db.session import get_session
from core.db.models import Recipe

# Try to import PyYAML once at module load
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # We'll raise a clear error if parsing is requested

# Default app recipes dir (repo checkout)
_APP_RECIPES_DIR = Path(__file__).resolve().parents[2] / "recipes"
# User-writable fallback (where imports go when repo is read-only)
_USER_RECIPES_DIR = Path.home() / ".sma_avops" / "recipes"


# ----------------------- helpers -----------------------

def _read_file_if_exists(path: Path) -> Optional[str]:
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


def _candidate_paths(yaml_path: str | None) -> List[Path]:
    """
    Given a recipe.yaml_path (usually 'slug.yaml'), return plausible places
    it might live, in priority order.
    """
    paths: List[Path] = []
    if not yaml_path:
        return paths

    p = Path(yaml_path)

    # Absolute path stored? try it first
    if p.is_absolute():
        paths.append(p)

    # repo recipes/
    paths.append(_APP_RECIPES_DIR / p)

    # user-writable imports directory (import UI writes here)
    paths.append(_USER_RECIPES_DIR / p.name)

    # optional extra search roots via env var (comma-separated)
    extra_roots = os.getenv("AVOPS_RECIPES_DIRS", "")
    for root in [r.strip() for r in extra_roots.split(",") if r.strip()]:
        paths.append(Path(root) / p.name)

    # de-dup while preserving order
    seen: set[str] = set()
    uniq: List[Path] = []
    for x in paths:
        sx = str(x)
        if sx not in seen:
            uniq.append(x)
            seen.add(sx)
    return uniq


# ----------------------- public API -----------------------

def load_recipe_yaml_text(recipe: Recipe) -> str:
    """
    Return the YAML text for a Recipe.
    Prefers inline DB text (recipe.yaml) when present; otherwise searches common file locations.
    Raises FileNotFoundError if nothing can be resolved.
    """
    # 1) Inline YAML stored in DB takes precedence (most robust)
    yaml_inline: Optional[str] = getattr(recipe, "yaml", None)
    if yaml_inline and str(yaml_inline).strip():
        return yaml_inline

    # 2) Try candidate file locations
    for fp in _candidate_paths(getattr(recipe, "yaml_path", None) or ""):
        txt = _read_file_if_exists(fp)
        if txt is not None:
            return txt

    raise FileNotFoundError(
        f"Recipe YAML not found for '{getattr(recipe, 'name', '?')}'. "
        f"Tried: {[str(p) for p in _candidate_paths(getattr(recipe, 'yaml_path', None) or '')]}"
    )


def _resolve_recipe(db, recipe_or_id: Recipe | int) -> Recipe:
    """Get a Recipe instance from an id or pass-through an instance."""
    if isinstance(recipe_or_id, Recipe):
        return recipe_or_id
    # SQLAlchemy 1.4/2.x compatibility
    db_get = getattr(db, "get", None)
    if callable(db_get):
        obj = db.get(Recipe, int(recipe_or_id))
    else:
        obj = db.query(Recipe).filter(Recipe.id == int(recipe_or_id)).first()
    if not obj:
        raise LookupError(f"Recipe id {recipe_or_id} not found")
    return obj


def load_recipe_dict(recipe_or_id: Recipe | int, db=None) -> Dict[str, Any]:
    """
    Engine-facing API expected by core/workflow/engine.py.

    Returns a parsed YAML dict for the given recipe id or Recipe object.
    Looks in DB inline YAML first, then in repo recipes/, then in ~/.sma_avops/recipes/.
    """
    if yaml is None:
        raise RuntimeError("PyYAML is required to parse recipe YAML (package 'pyyaml' missing).")

    if db is None:
        with get_session() as _db:
            rec = _resolve_recipe(_db, recipe_or_id)
            text = load_recipe_yaml_text(rec)
    else:
        rec = _resolve_recipe(db, recipe_or_id)
        text = load_recipe_yaml_text(rec)

    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Recipe '{getattr(rec, 'name', '?')}' YAML must parse to a mapping/dict, got {type(data).__name__}"
        )
    return data


def list_recipes(db) -> list[Recipe]:
    return db.query(Recipe).order_by(Recipe.name).all()


def save_recipe_yaml(recipe: Recipe, yaml_text: str, write_file: bool = True) -> None:
    """
    Save YAML back into the DB inline and (optionally) to disk.
    When writing to disk, prefer the user-writable directory; create a slug if needed.
    """
    # Always store inline (robust even if filesystem is read-only)
    setattr(recipe, "yaml", yaml_text)

    if not write_file:
        return

    # Ensure user directory and write the latest copy
    _USER_RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    fname = getattr(recipe, "yaml_path", None)
    if not fname:
        # very safe slug from recipe name
        base = (getattr(recipe, "name", "") or "recipe").lower().strip().replace(" ", "-")
        base = "".join(ch for ch in base if ch.isalnum() or ch in ("-", "_"))
        fname = f"{base}.yaml"
        setattr(recipe, "yaml_path", fname)

    out = _USER_RECIPES_DIR / Path(fname).name
    out.write_text(yaml_text, encoding="utf-8")
    

RECIPES_DIR = Path("recipes")

__all__ = [
    "ensure_recipes_dir",
    "save_recipe_yaml",
    "save_recipe_yaml_for_name",
    "load_recipe_dict",
]

def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-")
    return cleaned.lower() or "recipe"

def ensure_recipes_dir() -> Path:
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    return RECIPES_DIR

def save_recipe_yaml(yaml_filename: str, yaml_text: str) -> Path:
    """
    Write YAML content under ./recipes and return the full path.
    Accepts a filename (e.g., 'projector-reset.yaml').
    """
    ensure_recipes_dir()
    p = RECIPES_DIR / yaml_filename
    p.write_text(yaml_text, encoding="utf-8")
    return p

def save_recipe_yaml_for_name(recipe_name: str, yaml_text: str) -> Path:
    """
    Convenience: build a filename from the recipe name and save it.
    """
    fname = f"{_slugify(recipe_name)}.yaml"
    return save_recipe_yaml(fname, yaml_text)

def _read_text_from_path(p: Path) -> str:
    if not p.exists():
        raise FileNotFoundError(f"Recipe file not found: {p}")
    return p.read_text(encoding="utf-8")

def load_recipe_dict(source: Union[dict, str, Path, Any]) -> dict:
    """
    Load a recipe into a Python dict from several possible inputs:
      - dict: returned as-is
      - SQLAlchemy Recipe model (has .yaml_path): read file
      - Path or str path to a YAML file
      - str containing YAML text
    Raises ValueError if parsing fails or the result is not a mapping.
    """
    # 1) Already a dict
    if isinstance(source, dict):
        return source

    # 2) SQLAlchemy model with yaml_path
    yaml_text: str | None = None
    if hasattr(source, "yaml_path"):
        try:
            p = Path(getattr(source, "yaml_path"))
            yaml_text = _read_text_from_path(p)
        except Exception as e:
            raise ValueError(f"Unable to read recipe from model.yaml_path: {e}") from e

    # 3) Path-like or string path
    if yaml_text is None and isinstance(source, (str, Path)):
        p = Path(str(source))
        if p.exists():
            yaml_text = _read_text_from_path(p)

    # 4) If still None, treat string as YAML content
    if yaml_text is None and isinstance(source, str):
        # Heuristic: treat as inline YAML if it looks like YAML (has a colon or newline)
        if (":" in source) or ("\n" in source):
            yaml_text = source

    if yaml_text is None:
        raise ValueError(
            "load_recipe_dict: could not resolve recipe source. "
            "Provide a dict, a model with .yaml_path, a file path, or YAML text."
        )

    try:
        data = yaml.safe_load(yaml_text) or {}
    except Exception as e:
        raise ValueError(f"Invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Recipe YAML must load to a mapping (dict).")

    return data
