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

Agentic AV Ops Application Features & Usage Guide
Navigation
🏁 Setup Wizard
💬 Chat
🤖 Agents
📜 Recipes
🧰 MCP Tools
⚙️ Settings
🧩 Workflows
📊 Dashboard
❓ Help & Runbook
🔎 Run Details
Tip: Streamlit organizes pages by file name; this runbook references the labels visible in the sidebar.

Setup Wizard
The Setup Wizard is designed for the initial configuration of the application. It allows you to initialize the database and load sample data (agents, tools, recipes, and workflows) for demonstration purposes. You can run the Setup Wizard multiple times to reset the demo content.

How to Use the Setup Wizard:

Open the “Setup Wizard” page from the sidebar (📝 icon).
Click the button to initialize or reset the system data (e.g., “Initialize Database” or “Seed Demo Data”).
After clicking, the app will create necessary database tables and insert default Agents, Recipes, Tools, and example Workflows. A confirmation message will appear once seeding is complete.
You can then navigate to other pages (Agents, Recipes, Workflows, etc.) to view or modify the newly added sample data.
Tip: The Setup Wizard can be safely run multiple times to revert to a clean demo state.

Settings
The Settings page allows you to configure the AI model and other global settings for the app, including selecting a Large Language Model (LLM) provider (e.g., OpenAI or Anthropic). This setting is crucial for AI-related features like Chat and SOP generation.

How to Use the Settings Page:

Navigate to the “Settings” page (⚙️ icon).
Select the LLM Provider from the dropdown menu.
Provide the required API Key for the selected provider, ensuring it is correctly set in the environment.
Confirm the active model, which will be indicated on the page.
(Optional) Enable Mock Tool Mode if you want to simulate external tool actions without real API calls.
Changes made on the Settings page typically take effect immediately.

Note: Ensure the API key is correct and active to avoid errors in the Chat page.

Chat
The Chat page (💬 Chat) offers an interactive interface to communicate with the AI model. You can ask questions or issue commands in natural language, and the AI assistant will respond. The chat supports slash commands that integrate with the IPAV workflow system.

Key Capabilities:

Conversational Q&A: Type messages to the AI, which acts as an “AV operations assistant.”
History Display: View conversation history as chat bubbles.
Slash Commands: Use commands starting with “/” to trigger specific actions (e.g., /sop, /recipe, /agent, /tool, /kb).
Task Helper Sidebar: Access guidance on using slash commands and examples.
Using the Chat Page:

Go to the Chat page from the sidebar.
Type a question or command in the text box labeled “Type your message…”.
Press Enter to submit. The assistant will respond accordingly.
Use slash commands for quick task execution.
Agents
The Agents page (🤖 Agents) is where you manage your AI agents, which represent personas or contexts under which recipes run.

Using the Agents Page:

Open the “Agents” page from the sidebar.
Create a New Agent by entering a unique name and optional metadata.
View existing agents and trigger runs with selected recipes.
Edit or remove agents as needed.
Example: To create a new agent named “DisplayAgent” for AV Support, fill in the details and click Create Agent.

Recipes
The Recipes page (📜 Recipes) allows you to create, edit, and manage procedural recipes that define the actions your agents will perform.

Using the Recipes Page:

Open the “Recipes” page from the sidebar.
Create a New Recipe by entering a name and filling out the YAML structure.
Validate the recipe and save it to the library.
View or edit existing recipes as needed.
Tip: Always validate after editing to catch YAML formatting errors.

MCP Tools
The MCP Tools page (🔌 MCP Tools) is dedicated to managing and testing external integrations (tools) that agents can use in their workflows.

Using the MCP Tools Page:

Open the “MCP Tools” page from the sidebar.
Check the health of each tool and perform actions for testing or setup.
Review tool responses for health checks and actions.
Note: If mock mode is enabled, actions will return dummy success responses.

Workflows
The Workflows page (🧩 Workflows) allows you to orchestrate automated runs by combining an Agent with a Recipe on a specified trigger.

Using the Workflows Page:

Open the “Workflows” page from the sidebar.
Create a New Workflow by filling in the required fields (name, agent, recipe, trigger).
View and manage existing workflows, including running them manually or enabling/disabling them.
Tip: Use the “Tick scheduler” button to manually trigger interval workflows.

Dashboard
The Dashboard page (📊 Dashboard) provides a comprehensive view of your system’s operations, aggregating data about workflow runs and agent activities.

Using the Dashboard Page:

Open the “Dashboard” page from the sidebar.
Monitor KPIs, trends, and recent runs.
Inspect run details by clicking on specific entries for breakdowns of each execution.
Tip: Use the dashboard to identify issues and maintain system performance.

This guide serves as a comprehensive overview of the Agentic AV Ops application, detailing how to navigate and utilize its features effectively.
