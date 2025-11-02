# core/recipes/attach.py
from __future__ import annotations

import re
from sqlalchemy import func
from core.db.models import Agent, Recipe

__all__ = ["attach_recipe_to_agent"]

def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-")
    return cleaned.lower() or "recipe"

def attach_recipe_to_agent(db, agent_name: str, recipe_name: str, yaml_text: str) -> tuple[Agent, Recipe]:
    from .service import save_recipe_yaml  # lazy import

    # Agent upsert
    agent = (
        db.query(Agent)
        .filter(func.lower(Agent.name) == agent_name.lower())
        .first()
    )
    if not agent:
        agent = Agent(name=agent_name, config_json={})
        db.add(agent)
        db.commit()
        db.refresh(agent)

    # Write YAML file AND store inline copy for importers that look at Recipe.yaml
    yaml_filename = f"{_slugify(recipe_name)}.yaml"
    yaml_path = save_recipe_yaml(yaml_filename, yaml_text)

    recipe = (
        db.query(Recipe)
        .filter(func.lower(Recipe.name) == recipe_name.lower())
        .first()
    )
    if not recipe:
        recipe = Recipe(name=recipe_name, yaml_path=str(yaml_path), yaml=yaml_text)
        db.add(recipe)
    else:
        recipe.yaml_path = str(yaml_path)
        recipe.yaml = yaml_text

    db.commit()
    db.refresh(recipe)
    return agent, recipe
