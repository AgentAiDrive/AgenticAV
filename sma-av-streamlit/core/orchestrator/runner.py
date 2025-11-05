from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import yaml

def load_orchestrator(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def bound_fixed_recipes(orch: dict) -> dict[str, dict]:
    name_slug = orch["name"].lower().replace(" ", "-")
    out = {}
    for agent in orch["agents"]:
        fp = Path(f"data/recipes/fixed/{name_slug}__{agent}.yaml")
        out[agent] = yaml.safe_load(fp.read_text(encoding="utf-8"))
    return out

def run_orchestrated_workflow(orch_path: Path, context: dict):
    orch = load_orchestrator(orch_path)
    fixed = bound_fixed_recipes(orch)

    # Sequence: Baseline → EventForm → Intake → Plan → Act → Verify → Learn
    order = ["BaselineAgent","EventFormAgent","IntakeAgent","PlanAgent","ActAgent","VerifyAgent","LearnAgent"]
    state = {"context": context, "evidence": [], "verdicts": []}

    for agent in order:
        if agent not in fixed:
            continue
        state = _execute_fixed_agent(fixed[agent], state)
        if agent == "VerifyAgent" and state.get("failed"):
            break  # stop early if verify fails

    return state


def _execute_fixed_agent(fixed_recipe: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate running a fixed-agent recipe and enrich *state* with results.

    The runner currently does not integrate with the underlying MCP services,
    so each step is treated as a no-op while still recording the structural
    information from the recipe.  This helper is responsible for capturing
    approvals, evidence handles, and declared outcomes so that downstream
    consumers (tests, UI, future executors) can reason over the workflow
    results.
    """

    agent_name = fixed_recipe.get("agent_name", "UnknownAgent")

    # Work on a shallow copy so callers do not observe partially-updated
    # structures if an exception is raised mid-execution.
    next_state: Dict[str, Any] = deepcopy(state)
    next_state.setdefault("history", [])
    next_state.setdefault("approvals", [])
    next_state.setdefault("outcomes", {})
    next_state.setdefault("verdicts", [])
    next_state.setdefault("evidence", [])

    for step in fixed_recipe.get("steps", []):
        step_id = step.get("id", f"{agent_name}_step_{len(next_state['history'])}")
        kind = step.get("kind", "call")

        entry = {
            "agent": agent_name,
            "id": step_id,
            "kind": kind,
            "call": step.get("call"),
            "args": step.get("args", {}),
        }

        if kind == "verify":
            verdict = {
                "agent": agent_name,
                "step": step_id,
                "status": "pass",
                "expect": step.get("expect", {}),
            }
            next_state["verdicts"].append(verdict)
        elif kind == "pause":
            entry["status"] = "paused"
        elif kind == "note":
            entry["note"] = step.get("note") or step.get("text")

        next_state["history"].append(entry)

        # Capture approvals so they can be surfaced to operators.
        for approval in step.get("approvals", []) or []:
            next_state["approvals"].append(
                {"agent": agent_name, "step": step_id, "role": approval}
            )

        # Persist evidence handles to support downstream retrieval.
        for evidence in step.get("evidence", []) or []:
            next_state["evidence"].append(
                {"agent": agent_name, "step": step_id, "artifact": evidence}
            )

    # Attach declared outcomes for the agent.
    outcomes = fixed_recipe.get("outcomes")
    if outcomes:
        next_state["outcomes"][agent_name] = outcomes

    return next_state
