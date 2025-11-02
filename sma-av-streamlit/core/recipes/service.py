# core/recipes/service.py
from __future__ import annotations

from pathlib import Path
import re
from typing import Union, Any

import yaml

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
    ensure_recipes_dir()
    p = RECIPES_DIR / yaml_filename
    p.write_text(yaml_text, encoding="utf-8")
    return p

def save_recipe_yaml_for_name(recipe_name: str, yaml_text: str) -> Path:
    fname = f"{_slugify(recipe_name)}.yaml"
    return save_recipe_yaml(fname, yaml_text)

def _read_text_from_path(p: Path) -> str:
    if not p.exists():
        raise FileNotFoundError(f"Recipe file not found: {p}")
    return p.read_text(encoding="utf-8")

def load_recipe_dict(source: Union[dict, str, Path, Any]) -> dict:
    """
    Load recipe data into a dict from:
      - dict: returned as-is
      - SQLAlchemy model with .yaml_path and/or .yaml
      - filesystem path
      - raw YAML text
    """
    if isinstance(source, dict):
        return source

    yaml_text: str | None = None

    # Model instance
    if hasattr(source, "yaml_path") or hasattr(source, "yaml"):
        # prefer file if path exists; else inline yaml text
        p_val = getattr(source, "yaml_path", None)
        if p_val:
            p = Path(str(p_val))
            if p.exists():
                yaml_text = _read_text_from_path(p)
        if yaml_text is None:
            y = getattr(source, "yaml", None)
            if y:
                yaml_text = str(y)

    # Path-like or string path
    if yaml_text is None and isinstance(source, (str, Path)):
        p = Path(str(source))
        candidate_paths = [p]
        if not p.is_absolute():
            candidate_paths.append(RECIPES_DIR / p)
        for candidate in candidate_paths:
            if candidate.exists():
                yaml_text = _read_text_from_path(candidate)
                break
    # If still None and it's a string, treat as YAML text
    if yaml_text is None and isinstance(source, str):
        if (":" in source) or ("\n" in source):
            yaml_text = source

    if yaml_text is None:
        raise ValueError(
            "load_recipe_dict: could not resolve recipe source. "
            "Provide a dict, a model with .yaml_path or .yaml, a file path, or YAML text."
        )

    try:
        data = yaml.safe_load(yaml_text) or {}
    except Exception as e:
        raise ValueError(f"Invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Recipe YAML must load to a mapping (dict).")
    return data
