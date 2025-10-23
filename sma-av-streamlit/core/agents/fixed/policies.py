# sma-av-streamlit/core/agents/fixed/policies.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import datetime, time
from typing import Iterable, Optional
import os

try:
    import streamlit as st  # for secrets & user info
except Exception:
    st = None

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class RBACRoles(str, Enum):
    SUPPORT = "support"
    AUDITOR = "auditor"
    ADMIN = "admin"
    BUILDS = "builds"
    
@dataclass
class MaintenanceWindow:
    name: str
    start: time
    end: time
    days: tuple[int, ...]  # 0=Mon ... 6=Sun

    def is_open_now(self, when: Optional[datetime] = None) -> bool:
        when = when or datetime.now()
        if when.weekday() not in self.days:
            return False
        return self.start <= when.time() <= self.end

# Default policy windows (08:00–20:00 Mon–Fri) and Anytime window
STANDARD_MAINTENANCE = MaintenanceWindow("standard", time(8, 0), time(20, 0), (0, 1, 2, 3, 4))
ANYTIME = MaintenanceWindow("anytime", time(0, 0), time(23, 59), (0, 1, 2, 3, 4, 5, 6))

# Per-agent policy map
AGENT_POLICIES = {
    "BaselineAgent": dict(risk=RiskLevel.LOW, roles=(RBACRoles.SUPPORT, RBACRoles.AUDITOR, RBACRoles.ADMIN), window=ANYTIME),
    "EventFormAgent": dict(risk=RiskLevel.LOW, roles=(RBACRoles.SUPPORT, RBACRoles.ADMIN), window=ANYTIME),
    "IntakeAgent": dict(risk=RiskLevel.LOW, roles=(RBACRoles.SUPPORT,), window=ANYTIME),
    "PlanAgent": dict(risk=RiskLevel.MEDIUM, roles=(RBACRoles.SUPPORT, RBACRoles.ADMIN), window=STANDARD_MAINTENANCE),
    "ActAgent": dict(risk=RiskLevel.HIGH, roles=(RBACRoles.ADMIN,), window=STANDARD_MAINTENANCE),
    "VerifyAgent": dict(risk=RiskLevel.MEDIUM, roles=(RBACRoles.SUPPORT, RBACRoles.AUDITOR, RBACRoles.ADMIN), window=ANYTIME),
    "LearnAgent": dict(risk=RiskLevel.LOW, roles=(RBACRoles.SUPPORT, RBACRoles.ADMIN), window=ANYTIME),
    "KBPublisher": dict(risk=RiskLevel.LOW, roles=(RBACRoles.SUPPORT, RBACRoles.ADMIN), window=ANYTIME),
}

def _current_roles() -> set[RBACRoles]:
    # Prefer st.secrets["USER_ROLES"] = "support,auditor" or env USER_ROLES
    raw = None
    if st and hasattr(st, "secrets"):
        try:
            raw = st.secrets.get("USER_ROLES")
        except Exception:
            raw = None
    raw = raw or os.getenv("USER_ROLES", "support")
    roles: set[RBACRoles] = set()
    for token in str(raw).split(","):
        token = token.strip().lower()
        if not token:
            continue
        try:
            roles.add(RBACRoles(token))
        except Exception:
            pass
    return roles or {RBACRoles.SUPPORT}

def assert_allowed(agent_name: str) -> None:
    """Raise if RBAC or maintenance windows deny access to the fixed agent."""
    p = AGENT_POLICIES.get(agent_name)
    if not p:
        return
    # maintenance window
    win: MaintenanceWindow = p["window"]
    if not win.is_open_now():
        raise PermissionError(f"{agent_name}: outside of maintenance window '{win.name}'.")
    # RBAC
    have = _current_roles()
    want = set(p["roles"])
    if have.isdisjoint(want):
        raise PermissionError(f"{agent_name}: caller roles {sorted([r.value for r in have])} not permitted; requires one of {sorted([r.value for r in want])}.")
