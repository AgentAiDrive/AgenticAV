from ._common import exec_page
def render():
    # Expects ?run_id=... from query params in the existing page
    exec_page("pages/Run_Detail.py")
