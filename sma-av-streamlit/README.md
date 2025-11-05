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
