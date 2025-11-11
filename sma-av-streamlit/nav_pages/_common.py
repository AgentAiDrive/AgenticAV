## sma-av-streamlit/nav_pages/_common.py

from __future__ import annotations
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent.parent  # points to sma-av-streamlit/

def exec_page(rel_path: str) -> None:
    target = ROOT / rel_path
    if not target.exists():
        raise FileNotFoundError(f"Page script not found: {target}")
    # Execute the target Streamlit script in-place
    runpy.run_path(str(target), run_name="__main__")

