import os
import re
import textwrap
from typing import Optional

import streamlit as st
from sqlalchemy import func

from core.db.models import Agent, Recipe
from core.db.session import get_session
from core.llm.client import chat  # your existing chat() function
from core.mcp.from_sop_tools import ensure_tools_for_sop
from core.recipes.attach import attach_recipe_to_agent
from core.recipes.from_sop import sop_to_recipe_yaml
from core.recipes.service import save_recipe_yaml
from core.recipes.validator import validate_yaml_text
from core.recipes.sop_compiler import compile_sop_to_bundle  # Import the bundle compiler for orchestrator & fixed-agent recipes
from core.ui.page_tips import show as show_tip
from core.workflow.engine import execute_recipe_run
from core.secrets import get_active_key, is_mock_enabled
from core.utils.slash_commands import SlashCommand, SlashCommandError, parse_slash_command, usage_hint
from core.chat.service import create_thread, list_threads, add_message, get_messages, archive_thread, clear_thread


# Back-compat: older code may import _usage_hint
_usage_hint = usage_hint

__all__ = [
    "SlashCommand",
    "SlashCommandError",
    "parse_slash_command",
    "usage_hint",
    "_usage_hint",  # temporary back-compat
]

# -----------------------------------------------------------------------------
# Page setup
#
PAGE_KEY = "Chat"  # identifies this page in the page tips helper
show_tip(PAGE_KEY)

st.title("💬 Chat")

# --- Sidebar helpers ---------------------------------------------------------
with st.sidebar:
    st.subheader("Task helpers")
    st.markdown("Use **/sop** to convert text → recipe → attach → run. Example:")
    st.code(
        "/sop agent=Support name=\"Projector Reset\"\n"
        "Steps:\n"
        "- Gather_room\n"
        "- Reset projector\n"
        "- Verify image via ServiceNow KB"
    )
    json_mode = st.checkbox("JSON mode (raw tool payloads)", value=False)
    # Present a set of example slash commands for users to copy/paste.  A raw
    # triple-quoted string keeps backslashes and quotes intact.
    st.markdown(
        r"""
**Slash commands (copy/paste)**
```text
/sop agent=Support name="Projector Reset"
Steps:
- Gather room_id
- Reset projector via Q-SYS
- Verify image via Slack

/recipe new "Projector Reset"

/recipe attach agent="Support" recipe="Projector Reset"

/agent run "Support" recipe="Projector Reset"

/tool health calendar_scheduler

/tool action incident_ticketing '{"action":"create","args":{"title":"Zoom HDMI Black","description":"HDMI input shows black screen"}}'

/kb scout "zoom room hdmi black" allow=support.zoom.com,logitech.com
```
"""
    )
    st.caption(
        "Tip: Wrap multi-word names in quotes. Key/value pairs accept agent=, "
        "recipe=, etc."
    )
    # NEW: Surface that /sop now also emits an orchestrator + fixed-agent bundle
    st.markdown(
        "<small>New:</small> <em>/sop</em> also compiles an **Orchestrator** recipe and **Fixed-Agent** recipes (Intake/Plan/Act/Verify/Learn) from the same SOP. See the collapsible output after a run.",
        unsafe_allow_html=True,
    )

# --- Resolve active provider + key (NO silent fallback) ----------------------
# Determine which LLM provider and key are active.  These values are pulled
# from Streamlit secrets or environment variables.  If no key is available
# the chat helper will raise an exception when invoked.
provider_key, provider_name, key_source = get_active_key()  # ("openai"|"anthropic"), key, and source
mcp_mock = is_mock_enabled()  # for MCP tools only; chat will not auto-mock


def _mask(k: str | None) -> str:
    """Mask API keys for display in the UI."""
    if not k:
        return "missing"
    if len(k) <= 8:
        return "••••"
    return f"••••{k[-4:]}"


st.caption(
    f"Model: {('🟢' if provider_name == 'openai' else '🔵')} {provider_name} • "
    f"key source: {key_source} • MCP mock: {mcp_mock}"
)

# Export the chosen provider and API key to the environment so that
# core.llm.client.chat() reads them without further configuration.  We do
# NOT store secrets in st.session_state.
os.environ["LLM_PROVIDER"] = provider_name
if provider_name == "openai":
    if provider_key:
        os.environ["OPENAI_API_KEY"] = provider_key
else:
    if provider_key:
        os.environ["ANTHROPIC_API_KEY"] = provider_key

st.divider()
persist = st.toggle("Persist chat history", value=st.session_state.get("persist_chat", False), help="Store this conversation in the database so it survives refresh/restart.")
st.session_state["persist_chat"] = persist

thread_id = st.session_state.get("chat_thread_id")
if persist:
    with get_session() as db:
        threads = list_threads(db)
        choices = {t.id: f"{t.title} (#{t.id})" for t in threads}
        new_title = st.text_input("New thread title", value="Conversation")
        colA, colB, colC = st.columns([2,1,1])
        with colA:
            thread_id = st.selectbox("Thread", [None] + list(choices.keys()), format_func=lambda x: "— select —" if x is None else choices[x], index=0)
        with colB:
            if st.button("New thread"):
                t = create_thread(db, new_title or "Conversation")
                st.session_state["chat_thread_id"] = t.id
                thread_id = t.id
                st.rerun()
        with colC:
            if thread_id and st.button("Archive"):
                archive_thread(db, thread_id); st.session_state["chat_thread_id"] = None; st.rerun()
    st.session_state["chat_thread_id"] = thread_id

# NEW (5): Clear thread history control
if persist and thread_id and st.button("Clear thread history"):
    with get_session() as db:
        clear_thread(db, thread_id)
        st.success("Cleared.")
    st.rerun()

# --- Conversation state helpers ---------------------------------------------
SYSTEM_PROMPT = {"role": "system", "content": "You are an AV operations assistant."}

def _ensure_ephemeral_seed() -> None:
    """Create an ephemeral message buffer if it doesn't exist."""
    if "messages" not in st.session_state or not st.session_state["messages"]:
        st.session_state["messages"] = [SYSTEM_PROMPT]

def _load_messages_for_llm(persist_on: bool, tid: Optional[int]) -> list[dict]:
    """
    (3) Load messages for the LLM call.
    If persistence is enabled and a thread is selected, fetch from DB.
    Otherwise, use ephemeral session-state messages.
    Always make sure a system prompt is present as the first message.
    """
    if persist_on and tid:
        with get_session() as db:
            msgs = get_messages(db, tid) or []
        # Ensure there is a system prompt at the top for fresh threads
        if not msgs or msgs[0].get("role") != "system":
            msgs = [SYSTEM_PROMPT, *msgs]
        return msgs
    # Ephemeral
    _ensure_ephemeral_seed()
    return list(st.session_state["messages"])

def _save_turn_if_needed(persist_on: bool, tid: Optional[int], user_text: Optional[str], assistant_text: Optional[str]) -> None:
    """(4) On persisted threads, write user/assistant turns into the DB."""
    if not (persist_on and tid):
        return
    with get_session() as db:
        if user_text:
            add_message(db, tid, "user", user_text)
        if assistant_text:
            add_message(db, tid, "assistant", assistant_text)

def _render_messages(messages: list[dict]) -> None:
    """Render the conversation history in the chat interface."""
    for m in messages:
        role = m["role"] if m["role"] != "system" else "assistant"
        with st.chat_message(role):
            if m["role"] == "system":
                st.write(f"_{m['content']}_")
            else:
                st.write(m["content"])

def _extract_option(cmd: SlashCommand, text: str, key: str, default: Optional[str] = None) -> str:
    """Extract an option value from a SlashCommand or a fallback from the raw text."""
    value = cmd.option(key)
    if value:
        return value
    match = re.search(rf"{key}\s*=([^\n]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return default or ""

def _handle_sop(cmd: SlashCommand) -> tuple[str, str, list, list, str, Optional[int]]:
    """Convert an SOP into a recipe, attach it to an agent, and run it."""
    agent_name = _extract_option(cmd, cmd.raw, "agent", "Support")
    recipe_name = _extract_option(cmd, cmd.raw, "name", "Generated Recipe")

    sop_body = cmd.body or (cmd.raw.split("\n", 1)[1] if "\n" in cmd.raw else cmd.raw)

    ok, yml = sop_to_recipe_yaml(sop_body, name_hint=recipe_name)
    if not ok:
        raise RuntimeError("Failed to generate recipe YAML from SOP.")

    tools, created = ensure_tools_for_sop(os.getcwd(), sop_body)

    with get_session() as db:  # type: ignore
        a, r = attach_recipe_to_agent(db, agent_name, recipe_name, yml)
        run = execute_recipe_run(db, agent_id=a.id, recipe_id=r.id)
        return a.name, r.name, tools, created, yml, getattr(run, "id", None)

def _render_bundle_for_sop(cmd: SlashCommand, orchestrator_name: str) -> None:
    """
    NEW: Build and display the orchestrator + fixed-agent recipes derived from the same SOP.
    This is additive and does not change the legacy /sop flow.
    """
    try:
        sop_text = cmd.body or (cmd.raw.split("\n", 1)[1] if "\n" in cmd.raw else cmd.raw)
        ctx = {"name": orchestrator_name or "Workflow_From_SOP"}
        artifacts = compile_sop_to_bundle(sop_text, ctx)
        with st.expander("Generated Orchestrator & Fixed-Agent Recipes (bundle)", expanded=False):
            st.success("Created orchestrator and fixed-agent recipes from SOP.")
            for k, p in artifacts.items():
                st.write(f"**{k}** → `{p}`")
        st.caption("Tip: Attach the orchestrator recipe to a workflow or run it from the Dashboard.")
    except Exception as e:
        st.warning(f"Bundle generation skipped: {type(e).__name__}: {e}")

def _slugify(name: str) -> str:
    """Normalize a name into a slug suitable for filenames."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-")
    return cleaned.lower() or "recipe"

def _handle_recipe_new(cmd: SlashCommand) -> str:
    """Create a new recipe scaffold with guardrails from a slash command."""
    name = cmd.option("name") or (cmd.args[0] if cmd.args else None)
    if not name:
        raise SlashCommandError(usage_hint("recipe", "new"))

    yaml_filename = f"{_slugify(name)}.yaml"
    guardrail_template = textwrap.dedent(
        f"""
        name: {name}
        description: Auto-generated from chat command
        guardrails:
          timeout_minutes: 30
          rollback_actions:
            - Notify incident commander
        success_metrics:
          - metric: resolution_time_seconds
            target: 1800
        intake: []
        plan: []
        act: []
        verify: []
        """
    ).strip()

    ok, msg = validate_yaml_text(guardrail_template)
    if not ok:
        raise SlashCommandError(msg)

    save_recipe_yaml(yaml_filename, guardrail_template)

    with get_session() as db:  # type: ignore
        existing = (
            db.query(Recipe)
            .filter(func.lower(Recipe.name) == name.lower())
            .first()
        )
        if existing:
            return (
                f"Recipe **{existing.name}** already exists. Updated YAML file {yaml_filename}."
            )
        recipe = Recipe(name=name, yaml_path=yaml_filename)
        db.add(recipe)
        db.commit()
    return (
        f"Recipe **{name}** scaffolded with guardrails → `{yaml_filename}`. Review it under 📜 Recipes."
    )

def _handle_recipe_attach(cmd: SlashCommand) -> str:
    """Attach an existing recipe to an agent from a slash command."""
    agent_name = cmd.option("agent") or (cmd.args[0] if cmd.args else None)
    recipe_name = cmd.option("recipe") or (cmd.args[1] if len(cmd.args) > 1 else None)
    if not agent_name or not recipe_name:
        raise SlashCommandError(usage_hint("recipe", "attach"))

    with get_session() as db:  # type: ignore
        agent = (
            db.query(Agent)
            .filter(func.lower(Agent.name) == agent_name.lower())
            .first()
        )
        if not agent:
            raise SlashCommandError(
                f"Agent '{agent_name}' does not exist. Create it from the 🤖 Agents page first."
            )

        recipe = (
            db.query(Recipe)
            .filter(func.lower(Recipe.name) == recipe_name.lower())
            .first()
        )
        if not recipe:
            raise SlashCommandError(
                f"Recipe '{recipe_name}' does not exist. Use /recipe new or the 📜 Recipes page to create it."
            )

    return (
        f"Agent **{agent.name}** can now run recipe **{recipe.name}**. "
        "Use `/agent run` or the Workflows page to execute it."
    )

def _handle_agent_run(cmd: SlashCommand) -> str:
    """Trigger a recipe run on a given agent from a slash command."""
    agent_name = cmd.option("agent") or (cmd.args[0] if cmd.args else None)
    recipe_name = cmd.option("recipe") or (cmd.args[1] if len(cmd.args) > 1 else None)
    if not agent_name or not recipe_name:
        raise SlashCommandError(usage_hint("agent", "run"))

    with get_session() as db:  # type: ignore
        agent = (
            db.query(Agent)
            .filter(func.lower(Agent.name) == agent_name.lower())
            .first()
        )
        if not agent:
            raise SlashCommandError(f"Agent '{agent_name}' was not found.")

        recipe = (
            db.query(Recipe)
            .filter(func.lower(Recipe.name) == recipe_name.lower())
            .first()
        )
        if not recipe:
            raise SlashCommandError(f"Recipe '{recipe_name}' was not found.")

        with st.spinner("Running workflow..."):
            run = execute_recipe_run(db, agent_id=agent.id, recipe_id=recipe.id)
    rid = getattr(run, "id", None)
    if rid is None:
        return f"Triggered run for **{agent.name}** using recipe **{recipe.name}**."
    detail_url = f"/Run_Detail?run_id={rid}"
    return (
        f"Triggered run **#{rid}** for **{agent.name}** using recipe **{recipe.name}**. "
        f"[View details]({detail_url})."
    )

def _dispatch_command(cmd: SlashCommand) -> Optional[str]:
    """Dispatch slash commands to the appropriate handlers."""
    if cmd.name == "sop":
        agent_name, recipe_name, tools, created, yml, run_id = _handle_sop(cmd)
        detail_url = f"/Run_Detail?run_id={run_id}" if run_id else None
        st.success(
            f"Recipe **{recipe_name}** attached to agent **{agent_name}**. "
            f"Run {run_id or '—'} completed."
        )
        if detail_url:
            st.markdown(f"[Open run details]({detail_url})")
        if tools:
            st.write("Tools referenced:", tools)
        if created:
            st.write("New tools scaffolded:", created)
        with st.expander("Generated YAML", expanded=False):
            st.code(yml, language="yaml")
        # NEW: Also compile and show the orchestrator + fixed-agent bundle derived from the same SOP
        _render_bundle_for_sop(cmd, orchestrator_name=recipe_name)
        return (
            f"Attached recipe '{recipe_name}' to '{agent_name}' and executed run {run_id or '—'}."
        )

    if cmd.name == "agent" and cmd.action == "run":
        message = _handle_agent_run(cmd)
        st.success(message)
        return message

    if cmd.name == "recipe" and cmd.action == "new":
        message = _handle_recipe_new(cmd)
        st.success(message)
        return message

    if cmd.name == "recipe" and cmd.action == "attach":
        message = _handle_recipe_attach(cmd)
        st.info(message)
        return message

    raise SlashCommandError(
        f"Unsupported command '/{cmd.name}{(' ' + cmd.action) if cmd.action else ''}'."
    )

def _llm_reply(messages: list[dict], json_mode: bool) -> str:
    """Call the LLM provider with the accumulated conversation and return its reply."""
    if not provider_key:
        raise RuntimeError(
            f"No API key available for {provider_name}. "
            f"Set Streamlit secrets or provide an env var. (source tried: {key_source})"
        )
    # core.llm.client.chat should read provider from env or session.
    return chat(messages, json_mode=json_mode)

# --- Render current history --------------------------------------------------
_current_messages = _load_messages_for_llm(persist, thread_id)
_render_messages(_current_messages)

# --- Chat input / dispatch ---------------------------------------------------
prompt = st.chat_input("Type your message (/sop ... to build & run from SOP)")
if prompt:
    # Work on a local copy of the message list used for the upcoming LLM call
    messages_for_call = _load_messages_for_llm(persist, thread_id)
    # Append the user's message locally (ephemeral or pre-DB)
    messages_for_call.append({"role": "user", "content": prompt})

    # Slash-commands branch
    if prompt.strip().startswith("/"):
        with st.chat_message("assistant"):
            try:
                cmd = parse_slash_command(prompt)
                with st.spinner("Processing command..."):
                    summary = _dispatch_command(cmd)
                if summary:
                    # Show in UI and keep local transcript consistent
                    st.write(summary)
                    messages_for_call.append({"role": "assistant", "content": summary})

                    # (4) Persist both user & assistant turns to DB if enabled
                    _save_turn_if_needed(persist, thread_id, user_text=prompt, assistant_text=summary)

                    # For ephemeral sessions, mirror into session_state
                    if not (persist and thread_id):
                        _ensure_ephemeral_seed()
                        st.session_state["messages"] = messages_for_call
            except SlashCommandError as e:
                st.error(str(e))
                hint_source = locals().get("cmd") if "cmd" in locals() else None
                st.caption(
                    usage_hint(hint_source) if hint_source else usage_hint(prompt.split()[0].lstrip("/"))
                )
            except Exception as e:
                st.error(f"Command failed: {type(e).__name__}: {e}")

    # Regular chat branch
    else:
        with st.chat_message("assistant"):
            try:
                with st.spinner("Thinking..."):
                    reply = _llm_reply(messages_for_call, json_mode=json_mode)
                st.write(reply)
                messages_for_call.append({"role": "assistant", "content": reply})

                # (4) Persist both user & assistant turns to DB if enabled
                _save_turn_if_needed(persist, thread_id, user_text=prompt, assistant_text=reply)

                # For ephemeral sessions, mirror into session_state
                if not (persist and thread_id):
                    _ensure_ephemeral_seed()
                    st.session_state["messages"] = messages_for_call

            except Exception as e:
                # Show the reason (keys missing, network error, quota, etc.)
                st.error(f"LLM call failed: {type(e).__name__}: {e}")
                # Provide troubleshooting tips
                with st.expander("Troubleshoot", expanded=False):
                    st.markdown(
                        "- Confirm **Settings → provider** matches your intended model\n"
                        "- In Streamlit Cloud, set secrets as either:\n"
                        "  - `OPENAI_API_KEY = sk-...` **or** `[openai] api_key='sk-...'`\n"
                        "  - `ANTHROPIC_API_KEY = ...` **or** `[anthropic] api_key='...'`\n"
                        "- Make sure you didn’t save blank overrides in Settings\n"
                        "- Check network egress and org policy for outbound API calls"
                    )
                with st.expander("LLM self-test (temporary)"):
                    try:
                        t = chat(
                            [
                                {"role": "system", "content": "You are test."},
                                {"role": "user", "content": "Say 'real' if this is a real provider call."},
                            ],
                            json_mode=False,
                        )
                        st.success("Provider call succeeded.")
                        st.code(t)
                    except Exception as e2:
                        st.error(f"Provider call failed: {type(e2).__name__}: {e2}")

# ---------------------------------------------------------------------------
# NOTE: Do not remove or override the existing UI flow.
# The new bundle compiler is invoked in _dispatch_command('/sop') via _render_bundle_for_sop.
# The chat persistence hook-in points (3, 4, 5) are implemented above.
# ---------------------------------------------------------------------------
