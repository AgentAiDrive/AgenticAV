# sma-av-streamlit/pages/7_Fixed_Workflows.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from core.db.models import Agent, Recipe, Base
from core.db.session import get_session
from core.workflow.orchestrator import run_ipav_pipeline
from core.orchestrator.runner import run_orchestrated_workflow
from core.recipes.bundle_store import (
    BundleMetadata,
    delete_bundle,
    delete_bundle_context,
    export_bundle_zip,
    import_bundle_zip,
    list_bundles,
    list_bundle_contexts,
    load_bundle_context,
    save_bundle_context,
    update_bundle,
)

PAGE_KEY = "FixedWorkflows"
st.title("🧩 Fixed Agent Orchestrator")


def _resolve_path(path_like: str) -> Path:
    path = Path(path_like)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _context_presets(bundle: BundleMetadata) -> Dict[str, str]:
    presets: Dict[str, str] = {"Empty context": "{}"}
    if bundle.context_hints:
        presets["Bundle context hints"] = json.dumps(
            bundle.context_hints,
            indent=2,
            ensure_ascii=False,
        )

    for name in sorted(list_bundle_contexts(bundle.bundle_id).keys()):
        payload = load_bundle_context(bundle.bundle_id, name)
        presets[f"File: {name}"] = json.dumps(payload, indent=2, ensure_ascii=False)

    return presets


def _apply_context_choice(choice_key: str, text_key: str, presets: Dict[str, str]) -> None:
    choice = st.session_state.get(choice_key)
    st.session_state[text_key] = presets.get(choice, st.session_state.get(text_key, "{}"))


def _render_bundle_card(bundle: BundleMetadata) -> None:
    label = bundle.display_name or bundle.bundle_id
    presets = _context_presets(bundle)

    choice_key = f"{bundle.bundle_id}-ctx-choice"
    text_key = f"{bundle.bundle_id}-ctx-text"
    result_key = f"{bundle.bundle_id}-last-result"

    default_choice = next(iter(presets))
    if choice_key not in st.session_state:
        st.session_state[choice_key] = default_choice
        st.session_state[text_key] = presets[default_choice]
    else:
        if st.session_state[choice_key] not in presets:
            st.session_state[choice_key] = default_choice
        st.session_state.setdefault(text_key, presets[st.session_state[choice_key]])

    with st.container(border=True):
        header_cols = st.columns([4, 2])
        header_cols[0].markdown(f"### {label}")
        header_cols[1].markdown(
            f"<div style='text-align:right'>`{bundle.bundle_id}`</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"Recorded {bundle.created_at}")

        st.markdown(f"**Orchestrator recipe:** `{bundle.orchestrator_path}`")
        if bundle.fixed_agents:
            st.markdown("**Fixed agents:**")
            for agent_name, path in bundle.fixed_agents.items():
                st.write(f"- {agent_name}: `{path}`")

        tabs = st.tabs(["Run", "Artifacts", "Manage"])

        with tabs[0]:
            options = list(presets.keys())
            index = options.index(st.session_state.get(choice_key, default_choice))
            st.selectbox(
                "Preset context",
                options,
                key=choice_key,
                index=index,
                on_change=_apply_context_choice,
                args=(choice_key, text_key, presets),
                help="Choose a saved context payload or start from an empty JSON object.",
            )

            st.text_area(
                "Context JSON",
                key=text_key,
                height=220,
                help="Customize the context passed to the orchestrator run.",
            )

            ctx_name_key = f"{bundle.bundle_id}-ctx-name"
            ctx_cols = st.columns([2, 1, 1])
            ctx_cols[0].text_input(
                "Save as (filename)",
                key=ctx_name_key,
                placeholder="room-triage",
                help=f"Saved under data/recipes/bundles/{bundle.bundle_id}/contexts/.",
            )

            if ctx_cols[1].button("Save context", key=f"{bundle.bundle_id}-save-ctx"):
                raw = st.session_state.get(text_key, "{}")
                try:
                    payload: Dict[str, Any] = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError as exc:
                    st.error(f"Context JSON is invalid: {exc}")
                else:
                    name = st.session_state.get(ctx_name_key) or "context"
                    save_bundle_context(bundle.bundle_id, name, payload)
                    st.success("Context saved.")
                    st.rerun()

            zip_data, _ = export_bundle_zip(bundle)
            ctx_cols[2].download_button(
                "⬇️ Export bundle",
                data=zip_data,
                file_name=f"{bundle.bundle_id}.zip",
                mime="application/zip",
                help="Download orchestrator, fixed-agent recipes, metadata, and saved contexts.",
            )

            if st.button("▶️ Run bundle", key=f"{bundle.bundle_id}-run"):
                raw = st.session_state.get(text_key, "{}")
                try:
                    payload = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError as exc:
                    st.error(f"Context JSON is invalid: {exc}")
                else:
                    orch_path = _resolve_path(bundle.orchestrator_path)
                    if not orch_path.exists():
                        st.error(f"Orchestrator recipe not found: {orch_path}")
                    else:
                        with st.spinner("Executing orchestrated workflow..."):
                            result = run_orchestrated_workflow(orch_path, payload)
                        st.session_state[result_key] = result
                        st.success("Bundle execution complete.")

            if st.session_state.get(result_key):
                with st.expander("Last run output", expanded=False):
                    st.json(st.session_state[result_key])

        with tabs[1]:
            try:
                orch_text = _resolve_path(bundle.orchestrator_path).read_text(encoding="utf-8")
            except FileNotFoundError:
                orch_text = "# Orchestrator file missing"
            st.markdown("**Orchestrator YAML**")
            st.code(orch_text, language="yaml")

            if bundle.fixed_agents:
                st.markdown("**Fixed agents**")
                for agent_name, path in bundle.fixed_agents.items():
                    try:
                        agent_text = _resolve_path(path).read_text(encoding="utf-8")
                    except FileNotFoundError:
                        agent_text = "# Recipe file missing"
                    with st.expander(agent_name, expanded=False):
                        st.code(agent_text, language="yaml")

        with tabs[2]:
            st.markdown("### Metadata")
            with st.form(f"meta-{bundle.bundle_id}"):
                display_name = st.text_input("Display name", value=label)
                orchestrator_path = st.text_input(
                    "Orchestrator path",
                    value=bundle.orchestrator_path,
                    help="Path where the orchestrator YAML is stored.",
                )
                fixed_json = st.text_area(
                    "Fixed agents mapping (JSON)",
                    value=json.dumps(bundle.fixed_agents, indent=2, ensure_ascii=False),
                    height=180,
                )
                hints_json = st.text_area(
                    "Context hints (JSON)",
                    value=json.dumps(bundle.context_hints or {}, indent=2, ensure_ascii=False),
                    height=180,
                )
                save_meta = st.form_submit_button("Save metadata")

            if save_meta:
                try:
                    fixed_agents = json.loads(fixed_json or "{}")
                    if not isinstance(fixed_agents, dict):
                        raise TypeError("Fixed agents must be a JSON object mapping agent → path")
                except Exception as exc:
                    st.error(f"Fixed agent mapping invalid: {exc}")
                else:
                    try:
                        hints = json.loads(hints_json) if hints_json.strip() else None
                        if hints is not None and not isinstance(hints, dict):
                            raise TypeError("Context hints must be a JSON object")
                    except Exception as exc:
                        st.error(f"Context hints invalid: {exc}")
                    else:
                        metadata = BundleMetadata(
                            bundle_id=bundle.bundle_id,
                            display_name=display_name or label,
                            orchestrator_path=orchestrator_path or bundle.orchestrator_path,
                            fixed_agents={str(k): str(v) for k, v in fixed_agents.items()},
                            context_hints=hints,
                            created_at=bundle.created_at,
                        )
                        update_bundle(metadata)
                        st.success("Metadata updated.")
                        st.rerun()

            st.markdown("### Context files")
            contexts = list_bundle_contexts(bundle.bundle_id)
            if not contexts:
                st.info("No saved context files yet.")
            else:
                for name, path in sorted(contexts.items()):
                    cols = st.columns([3, 1])
                    cols[0].markdown(f"`{path}`")
                    if cols[1].button("Delete", key=f"delctx-{bundle.bundle_id}-{name}"):
                        delete_bundle_context(bundle.bundle_id, name)
                        st.success(f"Deleted context '{name}'.")
                        st.rerun()

            st.markdown("### Upload context JSON")
            up_cols = st.columns([3, 1])
            uploaded_ctx = up_cols[0].file_uploader(
                "Choose JSON file",
                type=["json"],
                key=f"upload-ctx-{bundle.bundle_id}",
            )
            ctx_label = up_cols[1].text_input(
                "Label",
                key=f"upload-ctx-name-{bundle.bundle_id}",
                placeholder="custom-context",
            )
            if uploaded_ctx is not None and st.button(
                "Import context", key=f"ctx-import-{bundle.bundle_id}"
            ):
                try:
                    payload = json.loads(uploaded_ctx.getvalue().decode("utf-8"))
                except Exception as exc:
                    st.error(f"Uploaded context invalid: {exc}")
                else:
                    name = ctx_label or Path(uploaded_ctx.name).stem
                    save_bundle_context(bundle.bundle_id, name, payload)
                    st.success("Context imported.")
                    st.rerun()

            st.markdown("### Replace artifacts")
            orch_upload = st.file_uploader(
                "Replace orchestrator YAML",
                type=["yaml", "yml"],
                key=f"orch-upload-{bundle.bundle_id}",
            )
            if orch_upload is not None and st.button(
                "Upload orchestrator", key=f"orch-save-{bundle.bundle_id}"
            ):
                target = _resolve_path(bundle.orchestrator_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(orch_upload.getvalue())
                st.success("Orchestrator updated.")

            if bundle.fixed_agents:
                for agent_name, path in bundle.fixed_agents.items():
                    with st.expander(f"Replace {agent_name}", expanded=False):
                        st.caption(f"Path: `{path}`")
                        agent_upload = st.file_uploader(
                            "Upload YAML",
                            type=["yaml", "yml"],
                            key=f"agent-upload-{bundle.bundle_id}-{agent_name}",
                        )
                        if agent_upload is not None and st.button(
                            "Save", key=f"agent-save-{bundle.bundle_id}-{agent_name}"
                        ):
                            target = _resolve_path(path)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(agent_upload.getvalue())
                            st.success(f"Updated recipe for {agent_name}.")

            st.markdown("### Danger zone")
            if st.button(
                "🗑️ Delete bundle",
                key=f"delete-{bundle.bundle_id}",
                help="Removes metadata, YAML artifacts, and saved contexts.",
            ):
                delete_bundle(bundle.bundle_id, remove_artifacts=True)
                st.success(f"Bundle '{label}' deleted.")
                st.rerun()


def _safe_init_db_once():
    """Initialize DB exactly once per Streamlit session.

    Strategy:
      1) Try the project's real seeder (core.db.seed.init_db)
      2) If unavailable, create tables directly from SQLAlchemy models
    """
    if st.session_state.get("_db_init_done"):
        return

    # Try real seeder (if available)
    real_seeder_err = None
    try:
        from core.db.seed import init_db as real_init_db  # type: ignore
    except Exception as e:  # noqa: BLE001
        real_seeder_err = e
        real_init_db = None  # type: ignore

    try:
        if real_init_db:
            real_init_db()
        else:
            # Fallback: create tables directly from models
            with get_session() as s:
                bind = s.get_bind()
                Base.metadata.create_all(bind=bind)

        st.session_state["_db_init_done"] = True

        if real_seeder_err is not None:
            st.info(
                "DB seeding module not available; created tables from models instead. "
                "If you expect sample data, run your project's seeding command."
            )

    except Exception as err:  # noqa: BLE001
        st.session_state["_db_init_done"] = False
        st.error("Database initialization failed. Running in limited mode.")
        with st.expander("DB init error (details)"):
            if real_seeder_err:
                st.write("Seeder import error:")
                st.exception(real_seeder_err)
            st.write("Initialization error:")
            st.exception(err)


# Initialize (once)
_safe_init_db_once()

# ---- Load selectable options (guarded) ----
agent_opts: dict[int, str] = {}
recipe_opts: dict[int, str] = {}

try:
    with get_session() as db:
        agents = db.query(Agent).order_by(Agent.name).all()
        recipes = db.query(Recipe).order_by(Recipe.name).all()
        agent_opts = {a.id: a.name for a in agents}
        recipe_opts = {r.id: r.name for r in recipes}
except SQLAlchemyError as e:
    st.error("Failed to query the database. See details below.")
    with st.expander("DB query error"):
        st.exception(e)

st.subheader("Saved Fixed-Workflow Bundles")
bundles = list_bundles()

if not bundles:
    st.info("No bundles recorded yet. Use /sop in Chat to generate orchestrator bundles.")
else:
    for bundle in bundles:
        _render_bundle_card(bundle)

st.divider()

st.subheader("Import bundle archive")
upload = st.file_uploader(
    "Upload a fixed-workflow bundle (.zip)",
    type=["zip"],
    key="bundle-upload",
)

if upload is not None and st.button("Import archive", key="import-bundle"):
    try:
        metadata = import_bundle_zip(upload.getvalue())
    except Exception as exc:  # noqa: BLE001
        st.error(f"Import failed: {exc}")
    else:
        st.success(
            f"Imported bundle '{metadata.display_name or metadata.bundle_id}'. Available in the list above."
        )
        st.rerun()

st.divider()

with st.expander("Ad-hoc IPAV run (legacy form)", expanded=False):
    if not agent_opts or not recipe_opts:
        st.info(
            "Agents and Recipes are required for the legacy runner. Create them first on the respective pages."
        )
    else:
        a = st.selectbox(
            "Orchestrator Agent",
            options=list(agent_opts.keys()),
            format_func=lambda i: agent_opts[i],
            key="legacy-agent",
        )
        r = st.selectbox(
            "Recipe",
            options=list(recipe_opts.keys()),
            format_func=lambda i: recipe_opts[i],
            key="legacy-recipe",
        )
        ctx_default = st.session_state.get("legacy-context", "{}")
        ctx_input = st.text_area(
            "Context (JSON)",
            value=ctx_default,
            key="legacy-context",
        )
        if st.button("Run pipeline", key="legacy-run", type="primary"):
            try:
                ctx_obj = json.loads(ctx_input) if ctx_input.strip() else {}
            except Exception as exc:  # noqa: BLE001
                st.error(f"Context JSON error: {exc}")
            else:
                with st.spinner("Running IPAV pipeline..."):
                    try:
                        with get_session() as db2:
                            run = run_ipav_pipeline(
                                db2,
                                agent_id=int(a),
                                recipe_id=int(r),
                                context=ctx_obj,
                            )
                        st.success(f"Run #{getattr(run, 'id', '?')} completed.")
                    except Exception as exc:  # noqa: BLE001
                        st.error("Pipeline execution failed.")
                        with st.expander("Run error (details)"):
                            st.exception(exc)
