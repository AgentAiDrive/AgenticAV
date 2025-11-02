# core/db/hotfix_migrations.py
from __future__ import annotations
from sqlalchemy import inspect, text
from core.db.session import engine  # your existing engine

def ensure_recipes_yaml_column() -> None:
    insp = inspect(engine)
    if not insp.has_table('recipes'):
        return
    cols = {c['name'] for c in insp.get_columns('recipes')}
    if 'yaml' not in cols:
        with engine.begin() as conn:
            try:
                conn.execute(text("ALTER TABLE recipes ADD COLUMN yaml TEXT"))
            except Exception:
                # Some SQLite builds may not support ALTER ADD COLUMN in this context.
                # In that case, drop the DB or run a manual migration.
                pass

def ensure_agents_config_json_column() -> None:
    insp = inspect(engine)
    if not insp.has_table('agents'):
        return
    cols = {c['name'] for c in insp.get_columns('agents')}
    if 'config_json' in cols:
        return
    alter_statements = [
        "ALTER TABLE agents ADD COLUMN config_json JSON DEFAULT '{}' NOT NULL",
        "ALTER TABLE agents ADD COLUMN config_json TEXT DEFAULT '{}' NOT NULL",
    ]
    for stmt in alter_statements:
        with engine.begin() as conn:
            try:
                conn.execute(text(stmt))
                conn.execute(text("UPDATE agents SET config_json = '{}' WHERE config_json IS NULL"))
                break
            except Exception:
                continue

if __name__ == "__main__":
    ensure_recipes_yaml_column()
    ensure_agents_config_json_column()
    print("Checked/added hotfix columns.")
