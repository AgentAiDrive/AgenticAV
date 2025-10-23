# sma-av-streamlit/core/agents/fixed/registry.py
from __future__ import annotations

from typing import Dict, Any, Callable

from .kb_publisher import KBPublisher

# List of fixed agents (string ids)
FIXED_AGENTS: list[str] = [
    "BaselineAgent",
    "EventFormAgent",
    "IntakeAgent",
    "PlanAgent",
    "ActAgent",
    "VerifyAgent",
    "LearnAgent",
    "KBPublisher",
]

# Static capabilities per agent
CAPS: dict[str, dict[str, Any]] = {
    "BaselineAgent": {"allows": ["policy_check","time_window_check","role_check"]},
    "EventFormAgent": {"allows": ["parse_form","normalize_payload"]},
    "IntakeAgent": {"allows": ["read_zoom","qsys_state","dante_routes","snmp_read"]},
    "PlanAgent": {"allows": ["choose_recipe","insert_approvals","expand_params"]},
    "ActAgent": {"allows": ["mcp_call","rollback","redact"]},
    "VerifyAgent": {"allows": ["assert","collect_evidence","kpi_record"]},
    "LearnAgent": {"allows": ["kb_publish","cmdb_link","dash_update"]},
    "KBPublisher": {"allows": ["kb_publish"]},
}

# Factory registry for callables
FIXED_AGENT_REGISTRY: Dict[str, Callable[..., Any]] = {
    "KBPublisher": KBPublisher,  # class; construct per-call with config
}
