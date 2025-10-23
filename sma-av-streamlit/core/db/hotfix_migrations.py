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

if __name__ == "__main__":
    ensure_recipes_yaml_column()
    print("Checked/added recipes.yaml column.")
