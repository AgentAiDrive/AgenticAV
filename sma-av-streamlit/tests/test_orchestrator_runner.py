from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.orchestrator.runner import run_orchestrated_workflow


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_run_orchestrated_workflow_minimal_bundle(tmp_path, monkeypatch):
    orch_payload = {
        "name": "Test Workflow",
        "version": "1.0",
        "agents": ["BaselineAgent", "VerifyAgent"],
    }
    orch_path = tmp_path / "orch.yaml"
    _write_yaml(orch_path, orch_payload)

    baseline_recipe = {
        "agent_name": "BaselineAgent",
        "steps": [
            {
                "id": "collect_context",
                "call": "context.collect",
                "args": {"foo": "bar"},
                "approvals": ["Support_L1"],
                "evidence": ["json:baseline"],
            },
            {
                "id": "leave_note",
                "kind": "note",
                "note": "Baseline complete",
            },
        ],
        "outcomes": {"success": "Baseline gathered."},
    }

    verify_recipe = {
        "agent_name": "VerifyAgent",
        "steps": [
            {
                "id": "ensure_ready",
                "kind": "verify",
                "expect": {"status": "ok"},
                "evidence": ["json:verify"],
            }
        ],
        "outcomes": {"success": "Verification completed."},
    }

    data_root = tmp_path / "data" / "recipes" / "fixed"
    _write_yaml(data_root / "test-workflow__BaselineAgent.yaml", baseline_recipe)
    _write_yaml(data_root / "test-workflow__VerifyAgent.yaml", verify_recipe)

    monkeypatch.chdir(tmp_path)

    result = run_orchestrated_workflow(orch_path, context={"room": "123"})

    assert result["context"] == {"room": "123"}
    assert len(result["history"]) == 3  # call + note + verify
    assert result["approvals"] == [
        {"agent": "BaselineAgent", "step": "collect_context", "role": "Support_L1"}
    ]
    assert {entry["artifact"] for entry in result["evidence"]} == {
        "json:baseline",
        "json:verify",
    }
    assert result["verdicts"] == [
        {
            "agent": "VerifyAgent",
            "step": "ensure_ready",
            "status": "pass",
            "expect": {"status": "ok"},
        }
    ]
    assert result["outcomes"] == {
        "BaselineAgent": {"success": "Baseline gathered."},
        "VerifyAgent": {"success": "Verification completed."},
    }
