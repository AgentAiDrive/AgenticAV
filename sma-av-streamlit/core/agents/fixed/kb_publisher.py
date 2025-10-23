
# sma-av-streamlit/core/agents/fixed/kb_publisher.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, Optional
from urllib.parse import quote_plus

import requests
import streamlit as st

from .policies import assert_allowed

def _sn_cfg() -> dict[str, str]:
    # Pull from Streamlit secrets first, then env
    sec = getattr(st, "secrets", {})
    return {
        "instance": str(sec.get("SN_INSTANCE") or os.getenv("SN_INSTANCE") or "").strip(),
        "username": str(sec.get("SN_USERNAME") or os.getenv("SN_USERNAME") or "").strip(),
        "token": str(sec.get("SN_TOKEN") or os.getenv("SN_TOKEN") or "").strip(),
        "kb_name": str(sec.get("SN_KB_NAME") or os.getenv("SN_KB_NAME") or "Knowledge").strip(),
    }

class KBPublisher:
    """
    Callable used by fixed-agent registry. Creates or updates a ServiceNow KB article
    from inputs produced by a workflow (title, html body, tags, audience, meta).
    Authentication: either token (Bearer) or basic (username + token as password).
    """
    def __init__(self, *, base_url: Optional[str] = None, auth: Optional[dict] = None):
        cfg = _sn_cfg()
        inst = base_url or cfg["instance"]
        if not inst:
            raise RuntimeError("SN_INSTANCE not configured in Streamlit secrets or environment.")
        self.base = inst if inst.startswith("http") else f"https://{inst}.service-now.com"
        # Determine auth
        if auth:
            self.auth_kind = auth.get("kind") or "token"
            self.auth_value = auth.get("value")
        else:
            if cfg["username"]:
                self.auth_kind = "basic"
                self.auth_value = (cfg["username"], cfg["token"])
            else:
                self.auth_kind = "token"
                self.auth_value = cfg["token"]
        self.kb_name = cfg["kb_name"]

    # ---------- HTTP helpers ----------

    def _hdrs(self) -> dict:
        if self.auth_kind == "token":
            return {"Authorization": f"Bearer {self.auth_value}", "Content-Type": "application/json"}
        return {"Content-Type": "application/json"}

    def _request(self, method: str, path: str, *, params: Optional[dict] = None, json_body: Optional[dict] = None) -> dict:
        url = f"{self.base}{path}"
        auth = None
        headers = self._hdrs()
        if self.auth_kind == "basic":
            auth = self.auth_value
        r = requests.request(method.upper(), url, headers=headers, auth=auth, params=params, json=json_body, timeout=30)
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise RuntimeError(f"ServiceNow {method} {url} failed: {r.status_code} • {detail}")
        try:
            return r.json()
        except Exception:
            return {}

    # ---------- Domain helpers ----------

    def _resolve_kb_base(self, name: str) -> Optional[str]:
        data = self._request(
            "GET", "/api/now/table/kb_knowledge_base",
            params={"sysparm_query": f"name={name}", "sysparm_limit": "1", "sysparm_fields": "sys_id,name"}
        )
        rows = data.get("result") or []
        return rows[0]["sys_id"] if rows else None

    def _find_article_by_title(self, base_sys_id: str, title: str) -> Optional[dict]:
        q = f"kb_knowledge_base={base_sys_id}^short_description={quote_plus(title)}"
        data = self._request("GET", "/api/now/table/kb_knowledge", params={"sysparm_query": q, "sysparm_limit": "1"})
        rows = data.get("result") or []
        return rows[0] if rows else None

    def _create_article(self, base_sys_id: str, payload: dict) -> dict:
        payload = dict(payload)
        payload["kb_knowledge_base"] = base_sys_id
        return (self._request("POST", "/api/now/table/kb_knowledge", json_body=payload)).get("result") or {}

    def _update_article(self, sys_id: str, payload: dict) -> dict:
        return (self._request("PATCH", f"/api/now/table/kb_knowledge/{sys_id}", json_body=payload)).get("result") or {}

    # ---------- Public callable ----------

    def __call__(self, *, title: str, html: str, tags: Iterable[str] = (), audience: str = "All", meta: Optional[dict] = None) -> dict:
        assert_allowed("KBPublisher")
        meta = meta or {}
        base_sys_id = self._resolve_kb_base(self.kb_name)
        if not base_sys_id:
            raise RuntimeError(f"Knowledge base '{self.kb_name}' not found.")
        existing = self._find_article_by_title(base_sys_id, title)
        payload = {
            "short_description": title,
            "text": html,
            "u_audience": audience,
            "u_tags": ",".join(tags or []),
            **{f"u_{k}": v for k, v in meta.items()},
        }
        if existing:
            rec = self._update_article(existing["sys_id"], payload)
            rec["__op__"] = "update"
        else:
            rec = self._create_article(base_sys_id, payload)
            rec["__op__"] = "create"
        return rec
