# core/recipes/service.py
from __future__ import annotations

from pathlib import Path
import re
from typing import Tuple

RECIPES_DIR = Path("recipes")

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
