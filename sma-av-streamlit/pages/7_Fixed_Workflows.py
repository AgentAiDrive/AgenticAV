# sma-av-streamlit/pages/7_Fixed_Workflows.py
from __future__ import annotations

"""
Fixed Workflows UI
- Loads persisted bundle metadata
- Renders each bundle as a "card" with context JSON selection/editor
- Preset JSON selector (ServiceNow KB samples) -> populates the editor
- Per-card actions: Run, Export, Edit (swap YAMLs / update context hints), Delete
- Sidebar: Import (.zip), Export ALL bundles (.zip-of-zips)
- Legacy ad-hoc run form preserved at bottom
"""

import io
import json
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

# --- Core imports (present per the completed tasks) ---
from core.orchestrator.runner import run_orchestrated_workflow
from core.recipes.bundle_store import (
    list_bundles,
    get_bundle,
    update_bundle,
    delete_bundle,
)

# Import tool: prefer core.io.port.import_zip; fall back gracefully
try:
    from core.io.port import import_zip as _import_zip  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _import_zip = None  # type: ignore[assignment]

# Export tool: prefer core.io.port.export_zip; else manual zip
try:
    from core.io.port import export_zip as _export_zip  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _export_zip = None  # type: ignore[assignment]

PAGE_KEY = "FixedWorkflows"
st.title("🧩 Fixed Workflows — Orchestrator + Fixed Agents")

RECIPES_BASE = Path("data/recipes")

# -------------------- Preset JSON Contexts (ServiceNow KB) -------------------- #
PRESET_CONTEXTS: Dict[str, Dict[str, Any]] = {
    "ServiceNow KB — Minimal Draft": {
        "servicenow": {
            "instance_url": "https://your-instance.service-now.com",
            "auth": {"type": "basic", "username": "svc_api", "password": "<SECRET>"}
        },
        "kb_article": {
            "kb_knowledge_base": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "short_description": "Resetting a Zoom Room Controller (AV)",
            "article_type": "html",
            "text": "<h2>Summary</h2><p>Steps to reset a Zoom Room controller…</p><ol><li>Hold the power …</li></ol>",
            "active": True
        },
        "metadata": {
            "tags": ["av", "zoom", "rooms", "controller"],
            "source": "SOP → compile_sop_to_bundle",
            "attachments": []
        }
    },
    "AV SOP → KB (Category + Validity)": {
        "servicenow": {
            "instance_url": "https://your-instance.service-now.com",
            "auth": {"type": "oauth", "profile": "snow_mcp_oauth_profile"}
        },
        "kb_article": {
            "kb_knowledge_base": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "kb_category": "cccccccccccccccccccccccccccccccc",
            "short_description": "AV: Mic Echo Troubleshooting Playbook (Rooms)",
            "article_type": "html",
            "text": "<h2>Scope</h2><p>This playbook covers echo …</p><h3>Checklist</h3><ul><li>DSP gain verify…</li></ul>",
            "valid_to": "2030-12-31",
            "active": True
        },
        "metadata": {
            "tags": ["av", "rooms", "echo", "dsp"],
            "approvals": {"required": True, "group": "Knowledge Managers"}
        }
    },
    "Publish-ready (Auto-Publish)": {
        "servicenow": {
            "instance_url": "https://your-instance.service-now.com",
            "auth": {"type": "basic", "username": "svc_api", "password": "<SECRET>"}
        },
        "kb_article": {
            "kb_knowledge_base": "dddddddddddddddddddddddddddddddd",
            "short_description": "Swap Q-SYS Core — Maintenance Window SOP",
            "article_type": "html",
            "text": "<p>Approved maintenance steps …</p>",
            "active": True
        },
        "metadata": {
            "publish_hint": "auto",
            "tags": ["q-sys", "maintenance", "sop"]
        }
    },
    "Update Existing Article (Upsert)": {
        "servicenow": {
            "instance_url": "https://your-instance.service-now.com",
            "auth": {"type": "oauth", "profile": "snow_mcp_oauth_profile"}
        },
        "update": {
            "lookup": {"sys_id": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"},
            "set": {
                "short_description": "Zoom Room Controller — Hard Reset (Updated 2025-11-05)",
                "text": "<p>Updated with new firmware steps …</p>"
            }
        }
    },
    "Attach Evidence + References": {
        "servicenow": {
            "instance_url": "https://your-instance.service-now.com",
            "auth": {"type": "basic", "username": "svc_api", "password": "<SECRET>"}
        },
        "kb_article": {
            "kb_knowledge_base": "ffffffffffffffffffffffffffffffff",
            "short_description": "Room Health Triage — SNMP & Zoom QoS",
            "article_type": "html",
            "text": "<p>Baseline checks with SNMP and Zoom QoS charts…</p>",
            "active": True
        },
        "metadata": {
            "attachments": [
                {"path": "evidence/zoom_qos_sample.png", "content_type": "image/png"},
                {"path": "evidence/snmp_poll.csv", "content_type": "text/csv"}
            ],
            "tags": ["monitoring", "triage", "zoom", "snmp"]
        }
    }
}

# -------------------- Helpers -------------------- #
def _container_with_border():
    """Streamlit <1.30 fallback for container(border=True)."""
    try:
        return st.container(border=True)
    except TypeError:
        return st.container()

def _load_json_candidates(near: Path) -> List[Path]:
    candidates: List[Path] = []
    roots = {near.parent, RECIPES_BASE, RECIPES_BASE / "contexts"}
    for root in roots:
        if root and root.exists():
            candidates.extend(p for p in root.glob("*.json") if p.is_file())
    seen: set[str] = set()
    uniq: List[Path] = []
    for p in candidates:
        sp = str(p.resolve())
        if sp not in seen:
            uniq.append(p)
            seen.add(sp)
    return uniq[:50]

def _safe_parse_json(s: str) -> Dict[str, Any]:
    try:
        o = json.loads(s) if s.strip() else {}
        return o if isinstance(o, dict) else {}
    except Exception:
        return {}

def _export_bundle_zip_bytes(bundle_id: str) -> bytes:
    md = get_bundle(bundle_id)
    if md is None:
        raise RuntimeError("Bundle not found")

    if _export_zip is not None:
        paths = []
        op = Path(md.orchestrator_path)
        if op.exists():
            paths.append(op)
        for p in (md.fixed_agents or {}).values():
            pp = Path(p)
            if pp.exists():
                paths.append(pp)
        return _export_zip(paths)  # type: ignore[misc]

    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        manifest: List[dict] = []
        orch_path = Path(md.orchestrator_path)
        if orch_path.exists():
            y = orch_path.read_text(encoding="utf-8")
            z.writestr(f"recipes/{orch_path.name}", y)
            manifest.append({"name": orch_path.stem, "yaml": f"recipes/{orch_path.name}"})
        for agent_name, p in (md.fixed_agents or {}).items():
            pp = Path(p)
            if not pp.exists():
                continue
            y = pp.read_text(encoding="utf-8")
            z.writestr(f"recipes/{pp.name}", y)
            manifest.append({"name": pp.stem, "yaml": f"recipes/{pp.name}", "meta": {"agent": agent_name}})
        z.writestr("recipes.json", json.dumps(manifest, indent=2))
    return buf.getvalue()

# -------------------- Sidebar: Import / Export ALL -------------------- #
with st.sidebar:
    st.subheader("Import / Export")
    uploaded = st.file_uploader("Import a Fixed Workflow bundle (.zip)", type=["zip"], key=f"{PAGE_KEY}:import")
    merge_policy = st.selectbox("On name conflicts", options=["skip", "rename", "overwrite"], index=0, key=f"{PAGE_KEY}:merge", help="Policy to apply when imported YAML names already exist.")
    if st.button("Import", use_container_width=True, disabled=(uploaded is None)):
        if _import_zip is None:
            st.error("Import not available: core.io.port.import_zip was not found.")
        else:
            try:
                payload = uploaded.read() if uploaded else b""
                report = _import_zip(payload, merge=merge_policy)  # type: ignore[misc]
                st.success(f"Imported: {report}" if isinstance(report, str) else f"Imported bundle(s). Summary: {report}")
                st.rerun()
            except Exception as e:
                st.error(f"Import failed: {e!r}")
    if st.button("Export ALL bundles", use_container_width=True):
        import zipfile
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as rootz:
            for md in list_bundles():
                try:
                    blob = _export_bundle_zip_bytes(md.bundle_id)
                    rootz.writestr(f"{md.bundle_id}.zip", blob)
                except Exception as ee:
                    rootz.writestr(f"{md.bundle_id}.error.txt", f"{type(ee).__name__}: {ee}")
        st.download_button("Download all bundles (.zip)", data=out.getvalue(), file_name="fixed-workflows-bundles.zip", mime="application/zip", use_container_width=True)

# -------------------- Main: Cards -------------------- #
bundles = list_bundles()
if not bundles:
    st.info("No bundles yet. Generate one from **Chat → /sop** to persist bundles here.")
else:
    for md in bundles:
        with _container_with_border():
            st.markdown(f"### {md.display_name or md.bundle_id}")
            st.caption(f"Bundle ID: `{md.bundle_id}` • Orchestrator: `{md.orchestrator_path}`")

            if md.fixed_agents:
                with st.expander("Fixed Agents", expanded=False):
                    for aname, apath in md.fixed_agents.items():
                        st.write(f"- **{aname}** → `{apath}`")

            if md.context_hints:
                st.caption(f"Context hints: `{md.context_hints}`")

            colA, colB, colC, colD = st.columns([1.5, 1, 1, 1])

            # --- A) Context editor/loader + PRESETS --- #
            with colA:
                st.subheader("Context")
                ctx_text_key = f"{PAGE_KEY}:ctx_text:{md.bundle_id}"
                if ctx_text_key not in st.session_state:
                    st.session_state[ctx_text_key] = json.dumps(md.context_hints or {}, indent=2)

                preset_key = f"{PAGE_KEY}:preset:{md.bundle_id}"
                preset_choice = st.selectbox("Preset", options=["(none)"] + list(PRESET_CONTEXTS.keys()), index=0, key=preset_key, help="Choose a sample to populate the JSON editor.")
                if st.button("Load preset", key=f"{PAGE_KEY}:apply_preset:{md.bundle_id}", use_container_width=True):
                    if preset_choice != "(none)":
                        st.session_state[ctx_text_key] = json.dumps(PRESET_CONTEXTS[preset_choice], indent=2)
                        st.success(f"Loaded preset: {preset_choice}")
                        st.rerun()

                candidates = _load_json_candidates(Path(md.orchestrator_path))
                file_pick = st.selectbox("…or load from JSON file", options=["(none)"] + [str(p) for p in candidates], index=0, key=f"{PAGE_KEY}:ctx_file:{md.bundle_id}")
                if st.button("Load selected file", key=f"{PAGE_KEY}:apply_file:{md.bundle_id}", use_container_width=True, disabled=(file_pick == "(none)")):
                    try:
                        st.session_state[ctx_text_key] = json.dumps(json.loads(Path(file_pick).read_text(encoding="utf-8")), indent=2)
                        st.success("Loaded context from file.")
                        st.rerun()
                    except Exception as e:
                        st.warning(f"Failed to load context: {e}")

                st.text_area("Inline JSON", value=st.session_state[ctx_text_key], key=ctx_text_key, height=200, label_visibility="collapsed")
                ctx_obj = _safe_parse_json(st.session_state[ctx_text_key])

            # --- B) Run + Export --- #
            with colB:
                st.subheader("Run")
                if st.button("▶️ Run bundle", key=f"{PAGE_KEY}:run:{md.bundle_id}", use_container_width=True):
                    try:
                        result = run_orchestrated_workflow(Path(md.orchestrator_path), context=ctx_obj)
                        st.success("Run complete.")
                        st.json(result)
                    except Exception as e:
                        st.error(f"Run failed: {e}")
                try:
                    bbytes = _export_bundle_zip_bytes(md.bundle_id)
                    st.download_button("⬇️ Export bundle", data=bbytes, file_name=f"{md.bundle_id}.zip", mime="application/zip", use_container_width=True, key=f"{PAGE_KEY}:dl:{md.bundle_id}")
                except Exception as e:
                    st.warning(f"Export not available: {e}")

            # --- C) Edit (swap YAMLs / update context) --- #
            with colC:
                st.subheader("Edit")
                yaml_opts = sorted([str(p) for p in RECIPES_BASE.rglob("*.yaml")])
                new_orch = st.selectbox("Orchestrator YAML", options=[md.orchestrator_path] + [p for p in yaml_opts if p != md.orchestrator_path], key=f"{PAGE_KEY}:orch:{md.bundle_id}")
                new_fixed = dict(md.fixed_agents or {})
                for aname, apath in (md.fixed_agents or {}).items():
                    new_fixed[aname] = st.selectbox(f"{aname} YAML", options=[apath] + [p for p in yaml_opts if p != apath], key=f"{PAGE_KEY}:fa:{md.bundle_id}:{aname}")
                if st.button("Save changes", use_container_width=True, key=f"{PAGE_KEY}:save:{md.bundle_id}"):
                    try:
                        update_bundle(md.bundle_id, orchestrator_path=new_orch, fixed_agents=new_fixed, context_hints=ctx_obj)
                        st.success("Bundle updated.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Update failed: {e}")

            # --- D) Delete --- #
            with colD:
                st.subheader("Danger zone")
                if st.button("🗑️ Delete bundle", type="secondary", use_container_width=True, key=f"{PAGE_KEY}:del:{md.bundle_id}"):
                    ok = delete_bundle(md.bundle_id, remove_files=True)
                    if ok:
                        st.success("Bundle deleted.")
                        st.rerun()
                    else:
                        st.warning("Bundle not found.")

# -------------------- Legacy Ad-Hoc Run (kept for back-compat) -------------------- #
st.divider()
with st.expander("Legacy Ad-Hoc Run (back-compat)", expanded=False):
    st.caption("Run an orchestrator YAML directly with a one-off context JSON.")
    orch_file = st.text_input("Path to orchestrator.yaml", value="", placeholder="data/recipes/.../orchestrator.yaml")
    ctx_text = st.text_area("Context JSON", value="{}", height=120)
    if st.button("Run (legacy)"):
        try:
            result = run_orchestrated_workflow(Path(orch_file), context=_safe_parse_json(ctx_text))
            st.success("Run complete.")
            st.json(result)
        except Exception as e:
            st.error(f"{type(e).__name__}: {e}")
