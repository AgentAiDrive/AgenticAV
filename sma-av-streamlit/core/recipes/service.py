# core/recipes/service.py
from __future__ import annotations

from pathlib import Path
import re
from typing import Tuple, Union, Any

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
