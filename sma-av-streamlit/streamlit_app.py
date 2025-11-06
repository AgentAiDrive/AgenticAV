# streamlit_app.py  (repo root)
import sys, pathlib
root = pathlib.Path(__file__).parent.resolve()
sys.path.insert(0, str(root / "sma-av-streamlit"))
from app import *  # imports and runs your app.py