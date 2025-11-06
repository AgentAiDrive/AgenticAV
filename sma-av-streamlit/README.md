<img width="120" height="89" alt="ipav_agentic av -blue" src="https://github.com/user-attachments/assets/00c68a1d-224f-4170-b44f-9982bf4b5e8d" />
**Agentic AV Ops is designed to  provides a suite of features for creating AI-driven operational workflows converting SOP's using NLP, into agentic recipes exectued by Agents through MCP's and the IPAV framework.**

Go to Runbook.md to view the user manual explaining each feature page and how to use it, step by step. (The features correspond to the pages in the app’s sidebar navigation.)

**Agentic AV Ops** Streamlit Application
🏁 Setup Wizard
💬 Chat
🤖 Agents
📜 Recipes
🧰 MCP Tools
⚙️ Settings
🧩 Workflows
🧩 Fixed Workflows (IPAV Orchestrator)
📊 Dashboard
❓ Help & Runbook
🔎 Run Details

**Try Demo Now:**
https://agenticav.streamlit.app/
**Do NOT Save Keys in Online Demo!**

**Local Development Tips**
To run the application locally:

**Clone the repository:**
# Make sure IPAV-Agents branch selected
git clone https://github.com/AgentAiDrive/AgenticAV/sma-av-streamlit.git
cd AV-AIops

Create a virtual environment and install dependencies:
python3 -m venv venv
source venv/bin/activate
pip install -r sma-av-streamlit/requirements.txt

**Run the app:**
streamlit run sma-av-streamlit/app.py --server.port 8501

Open http://localhost:8501 in your browser. Follow the steps described in the runbook to seed the database, create agents, author recipes and test connectors.

For development, use core/mcp/scaffold.py to generate new connectors and ensure the template functions are defined.

### Bundle metadata storage

Orchestrator/fixed-agent bundles generated via the `/sop` flow are recorded in
`data/recipes/bundles/index.json`. Each entry stores:

- `bundle_id`: slug derived from the orchestrator name.
- `display_name`: user-facing label shown on the 🧩 Fixed Workflows page.
- `orchestrator_path`: relative path to the orchestrator recipe YAML.
- `fixed_agents`: mapping of agent name → recipe YAML path.
- `context_hints`: optional JSON object with extra context captured during bundle creation.
- `created_at`: UTC timestamp when the bundle metadata was recorded.

This index powers the Fixed Workflows browser and can be reused for future
import/export tooling.

--- a/sma-av-streamlit/README.md
+++ b/sma-av-streamlit/README.md
@@
+## Page ↔ Core Module Map
+> Quick navigation for contributors. Paths are relative to `sma-av-streamlit/`.
+
+| UI Page (Streamlit) | Purpose | Primary Modules (logic & data) |
+|---|---|---|
+| `app.py` (Home) | Logo, Runbook viewer, global tips | `core/ui/page_tips.py`, `RUNBOOK.md` |
+| `pages/1_Setup_Wizard.py` | One-click seed/init (DB, demo data) | `core/db/seed.py`, `core/db/models.py`, `core/db/session.py`, `data/`, `recipes/`, `core/recipes/service.py`, `core/recipes/validator.py`, `core/mcp/scaffold.py` |
+| `pages/2_Chat.py` | Chat + slash commands (`/sop`, JSON mode) | `core/chat/service.py`, `core/utils/slash_commands.py`, `core/llm/client.py`, `core/llm/llm_provider.py`, `core/llm/providers/openai_client.py`, `core/llm/providers/anthropic_client.py`, `core/recipes/from_sop.py` |
+| `pages/3_Agents.py` | Agent catalog & CRUD; attach recipes; trigger runs | `core/agents/fixed/registry.py`, `core/agents/kb_publisher.py`, `core/recipes/attach.py`, `core/recipes/service.py`, `core/policies/default-guardrails.json` |
+| `pages/4_Recipes.py` | Orchestrator & Fixed-Agent recipes (validate/version) | `core/recipes/schema.py`, `core/recipes/validator.py`, `core/recipes/storage.py`, `core/recipes/service.py`, `core/recipes/sop_compiler.py` |
+| `pages/5_MCP_Tools.py` | Discover/scaffold MCP tools; health checks | `core/mcp/scaffold.py`, `core/mcp/from_sop_tools.py`, `core/mcp/tools/**` |
+| `pages/6_Settings.py` | Model/provider selection; keys | `core/llm/llm_provider.py`, `core/llm/client.py` |
+| `pages/7_Workflows.py` | Orchestrated workflows (manual/cron) | `core/workflow/orchestrator.py`, `core/workflow/engine.py`, `core/workflow/service.py`, `core/orchestrator/runner.py`, `workflows/*.json` |
+| `pages/7_Fixed_Workflows.py` | Fixed-workflow pipeline (bundle → run) | `core/recipes/bundle_store.py`, `core/recipes/sop_compiler.py`, `core/workflow/service.py`, `data/recipes/fixed/**` |
+| `pages/8_Dashboard.py` | KPIs & run metrics; drilldowns | `core/db/models.py` (Run/Step), `core/utils/evidence.py`, `core/orchestrator/runner.py` |
+| `pages/9_Help.py` | Help & quick links | `core/ui/page_tips.py` |
+| `pages/Run_Detail.py` | Single run detail (via `?run_id=`) | `core/orchestrator/runner.py`, `core/utils/evidence.py`, `core/db/models.py` |
+
+### Key Integrations
+- **ServiceNow KB:** `core/tools/servicenow.py` (expects `SERVICENOW_BASE_URL`, optional `SERVICENOW_BOT_TOKEN`), used by KB publish flows.
+- **Recipes & Data:** authoring in `recipes/**` (project-level) and seeds in `data/recipes/**` (fixed/orchestrator templates).
+- **MCP Tools:** sample packs in `core/mcp/tools/**` (e.g., `incident_ticketing/` with `manifest.json` + `connector.py`).
+
+### How it flows (at a glance)
+**`/sop` in Chat → runnable workflow**
+`pages/2_Chat.py` → `core/utils/slash_commands.py` → `core/recipes/from_sop.py` → `core/recipes/sop_compiler.py` → (optional) `core/mcp/scaffold.py` → `core/workflow/orchestrator.py` → `core/orchestrator/runner.py`
+
+**KB publish (ServiceNow)**
+Agent/recipe step → `core/agents/kb_publisher.py` → `core/tools/servicenow.py` (`/api/now/table/kb_knowledge`) → evidence stored via `core/utils/evidence.py`
+
+### Developer tips
+- **DB & Seeds:** Start in `pages/1_Setup_Wizard.py` to create the demo DB and load example agents/recipes.
+- **Validating Recipes:** Use `core/recipes/validator.py` (same logic the UI calls) during CI.
+- **Run Details:** Open `pages/Run_Detail.py?run_id=<id>` to inspect steps, artifacts, and evidence.
