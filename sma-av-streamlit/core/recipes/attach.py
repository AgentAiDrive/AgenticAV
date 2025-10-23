# core/recipes/attach.py
from __future__ import annotations

import re
from typing import Tuple

from sqlalchemy import func

from core.db.models import Agent, Recipe

__all__ = ["attach_recipe_to_agent"]

def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-")
    return cleaned.lower() or "recipe"

def attach_recipe_to_agent(db, agent_name: str, recipe_name: str, yaml_text: str) -> Tuple[Agent, Recipe]:
    """
    Ensure Agent exists, write YAML for the recipe, upsert Recipe row, and return (agent, recipe).
    Lazy-imports the YAML writer to avoid module import cycles.
    """
    # Lazy import — prevents ImportError from top-level circular imports
    from .service import save_recipe_yaml  # noqa: WPS433

    # 1) Upsert Agent (case-insensitive)
    agent = (
        db.query(Agent)
        .filter(func.lower(Agent.name) == agent_name.lower())
        .first()
    )
    if not agent:
        agent = Agent(name=agent_name)
        db.add(agent)
        db.commit()
        db.refresh(agent)

    # 2) Persist YAML to disk under ./recipes
    yaml_filename = f"{_slugify(recipe_name)}.yaml"
    yaml_path = save_recipe_yaml(yaml_filename, yaml_text)

    # 3) Upsert Recipe (case-insensitive)
    recipe = (
        db.query(Recipe)
        .filter(func.lower(Recipe.name) == recipe_name.lower())
        .first()
    )
    if not recipe:
        recipe = Recipe(name=recipe_name, yaml_path=str(yaml_path))
        db.add(recipe)
    else:
        recipe.yaml_path = str(yaml_path)

    db.commit()
    db.refresh(recipe)
    return agent, recipe
