Agentic AV Ops - IPAV Workflow Orchestration — Runbook

Agentic Ops IPAV application provides a suite of features for creating AI-driven operational workflows. Below is a user manual explaining each feature page and how to use it, step by step. (The features correspond to the pages in the app’s sidebar navigation.)

Goal
Operate AV workflows --> Convert SOP's to Agentic workflows inside the IPAV lifecycle: Intake → Plan → Act → Verify.  & Learn (auto - KB agent)  Create (Agents + Recipes + MCP Tools + Workflows that execute SOP's using Orchestrator, Intake, Plan, Act, Verify & Learn agents with access to tools, web, memory, uploads and special system, developer, user, tool prompts to turn ServiceNow into KnowledgeBase for AV Operations and observe results on a Dashboard.
Data & Persistence

Primary DB (agents, recipes, workflows): your existing SQLAlchemy models.
Run telemetry (runs, steps, artifacts): core/runs_store.py (SQLite file avops.db in app root).
Navigation
app
🏁 Setup Wizard
💬 Chat
🤖 Agents
📜 Recipes
🧰 MCP Tools
⚙️ Settings
🧩 Workflows
🧩 Fixed Workflows IPAV Orchestrator
📊 Dashboard
❓ Help & Runbook
🔎 Run Details
Tip: Streamlit orders pages by file name, but this runbook references the labels you see in the sidebar.

Agentic AV Ops Application Features & Usage Guide

Setup Wizard **
This page is used for initial setup of the application. It allows you to initialize the database and load sample data (agents, tools, recipes, and workflows) for demonstration purposes[3]. You can run the setup wizard multiple times if you need to reset the demo content. How to use the Setup Wizard:

Open the “Setup Wizard” page from the sidebar. (It may be labeled with a 📝 icon and the name Setup Wizard.)

INITIALIZE THE DATA (RESET THE SYSTEM DATA)

“Initialize Database” or “Seed Demo Data.”

Click the initialize/seed button. 
The app will create the necessary database tables and insert a set of default Agents, Recipes, Tools, and example Workflows. 
You should see a confirmation (e.g. a success message) once seeding is complete (the app also indicates that the database is seeded and initialized on the main page).

After running the wizard, you can proceed to other pages (Agents, Recipes, Workflows, etc.) to view or modify the newly added sample data. 
(The demo content might include a sample agent, some example recipes, and a scheduled workflow to illustrate the IPAV concept.) 

Tip: The Setup Wizard is safe to run multiple times – if you’ve made changes and want to revert to a clean demo state, you can run it again to re-create the default setup. 


SETTINGS
The Settings page allows you to configure the AI model and other global settings for the app. Choose which Large Language Model provider to use for the AI agent - default set to OpenAI or toggle to Anthropic. 
The app uses this setting for any features that involve AI (like the Chat and SOP generation). This page may also show whether the required API keys are loaded and let you toggle any test modes for tools. How to use the Settings page:

Navigate to the “Settings” page (⚙️ icon). You will see options related to the AI model and possibly API keys.

Select the LLM Provider: There will be a field or dropdown to choose the active model provider (e.g. OpenAI or Anthropic). Pick the provider you want the app to use for generating text and understanding commands.

Provide API Key (if required): The app typically reads API keys from a secure source (environment variables or Streamlit secrets). 
Ensure that you have set the API key for the chosen provider. For example, if you select OpenAI, the environment should have an OPENAI_API_KEY, and for Anthropic an ANTHROPIC_API_KEY. 

The Settings page display the status of the key (for instance, showing the last few characters of the key or indicating if it’s missing or loaded) 
If the page allows input, you can enter or update the key there; otherwise, you’ll need to set it in the config (per deployment instructions).

Confirm Active Model: Once a provider is selected (and a key is available), the app will indicate which model is active. 
You will see a small status line or badge – “Model: 🟢 OpenAI” or “🔵 Anthropic” – confirming the current selection. 

This confirmation is also shown on the main app sidebar for quick reference.

(Optional) Mock Tool Mode: The app supports a “mock mode” for MCP tools (to simulate external tool actions without real API calls), the Settings page has a toggle for it. Checkbox: “Enable Tool Mock Mode”. Turn this on if you want the integrated tools (Slack/Zoom/ServiceNow) to run in dummy mode (useful if you don’t have those services configured, or for demo purposes).

Changes on the Settings page typically take effect immediately. After configuring, you can go to the Chat or other pages to utilize the AI features with the chosen provider. 

Note: Always ensure the API key is correct and active; if not, the Chat page will show an error when you try to use the AI (the Settings page helps prevent this by highlighting missing keys or misconfiguration). 

CHAT

The Chat page (💬 Chat) provides more than just an interactive chat interface with the model used. 

OpenAI and Anthropic are defaults to choose from, though you can easily connect to others. 

Here you can ask questions or issue commands in natural language, and the AI assistant will respond. 

What makes this chat especially powerful is its support for slash commands that tie into the IPAV workflow system. 

Key capabilities on the Chat page: 

• Conversational Q&A: You can type messages to the AI like you would in a chat. The assistant has a persona of an “AV operations assistant,” so you can ask it things related to IT/AV operations or anything it’s been designed to help with. 
Simply enter your query or request in the text box at the bottom (labeled “Type your message…”). 

• History Display: The conversation history is shown as chat bubbles. Your messages and the assistant’s replies will accumulate in the chat window, allowing you to scroll and review context. (System messages, like the initial prompt, are shown in italic to provide context but are not labeled as user messages.) 

• Slash Commands: These are special instructions starting with a “/” that trigger specific actions: 
• /sop (Standard Operating Procedure): Convert a described procedure into a recipe and run it. For example, you can type:
/sop agent=KB_Agent name="SOP_to_SERVICENOW_KB_article" Steps: Intake
Gather SOP Plan
Convert to KB Article Act
Get ServiceNow MCP
Publish KB Article Verify
Get Artifacts – Print Article (PDF)

This command tells the app to create a new recipe with the given steps called SOP_to_SERVICENOW_KB_article , attach it to the agent KB_Agent, and execute it immediately.

The chat will then respond with a summary of what was done (and the Workflow/Run pages will reflect the new entries). 

• /recipe commands: Manage recipes via chat. 

For example: o /recipe new "KB_Article" – create a new recipe scaffold with the given name (the app will create a blank recipe with guardrail sections pre-filled). 
o /recipe attach agent="KB_Agent" recipe=" SOP_to_SERVICENOW_KB_article " – attach an existing recipe to an agent (creating a workflow or link between them). 

• /agent command: e.g. /agent run "KB_Agent" recipe=" SOP_to_SERVICENOW_KB_article " will immediately run the specified recipe with the specified agent (without setting up a saved workflow). 
This is similar to triggering a one-time run. 

• /tool commands: Interact with external tools integrated via MCP. 
For example: o /tool health calendar_scheduler – check the health status of the calendar_scheduler tool (the app will call its health endpoint and return the result).

SERVICENOW o /tool action incident_ticketing '{"action":"create","args":{...}}' – send an action to the incident_ticketing tool with a JSON payload (here, creating a new incident ticket with the given title/description). 
The response or confirmation will be shown. 
o /kb command: e.g. /kb scout "zoom room hdmi black" allow=support.zoom.com,logitech.com – (Knowledge Base scout) this might trigger a web search or knowledge base lookup for the given query, constrained to certain domains. The assistant would then return findings or a summary. 

• Task Helper Sidebar: On the left sidebar of the Chat page, you’ll find a “Task helpers” section with guidance on using slash commands[38]. It includes an example of the /sop command format and a list of all available slash commands with syntax, which you can copy/paste. This is a quick reference if you forget the exact format. 

• There is also a “JSON mode” checkbox in the sidebar. If you check “JSON mode (raw tool payloads)”[4][39], the assistant will include raw JSON outputs from tools in its responses. This is useful for debugging or if you want to see the exact data returned by a tool, rather than a formatted message. 

• Executing Commands: When you submit a slash command or any message: 

• If it’s a slash command (starts with /), the app will parse the command and execute the corresponding action. You’ll see a spinner and then either a success message or error in the chat. If successful, the assistant will typically summarize the result. For instance, for a /sop command, it might reply with something like “Created recipe X and ran it on agent Y, workflow run ID #Z completed.” Any errors (like a command formatting issue) will be shown as an error message along with a usage hint for the correct format 
• If it’s a normal message (not starting with /), the assistant will treat it as a question or request and generate a response using the LLM. You’ll see the assistant typing... and then an answer will appear. (For example, you can ask “What does IPAV stand for?” or “How do I automate and run an SOP using agentic workflows, Model Context Protocol and IPAV loop to execute? and it will respond.) 

• Troubleshooting: If the assistant fails to respond (for example, if no API key is set or the LLM service is unreachable), the chat will display an error with the reason and some troubleshooting tips. You can expand the “Troubleshoot” section to see suggestions (like checking that the API keys are configured in Settings, etc.)[42]. Using the Chat page:

Go to the Chat page from the sidebar.
In the text box at the bottom labeled “Type your message…”, you can either type a question/command or use one of the supported slash commands:
To ask a general question or issue a request to the AI, just type the message naturally and press Enter. (For example: “How do I troubleshoot a projector not turning on?”)
To use a slash command, start your input with / followed by the command name and parameters. Refer to the Task helpers on the sidebar for the exact syntax. For instance, try the provided example by copying it from the sidebar into the input area.
Press Enter or click the send icon to submit. The conversation will update with your query (as a user message). If it was a slash command, the assistant’s response will either confirm the action taken or display results; if it was a normal question, the assistant will reply with an answer or follow-up questions.
Continue the conversation by typing follow-up questions or commands. The assistant remembers the conversation context (all messages above) during the session, so you can ask iterative questions.
Use the slash commands to quickly accomplish tasks:
For example, after running the SOP command above, you can type /agent run "KB_Agent" recipe="SOP_to_SERVICENOW_KB_article " to rerun the same procedure. The assistant will execute it and inform you of the outcome. The chat will then respond with a summary of what was done (and the Workflow/Run pages will reflect the new entries).
Use /tool health ... to check if connectors are functioning (the result will appear in the chat as a short status message).
If you want to clear the conversation and start fresh, you can reload the page. (Note: The app may not have a “clear chat” button, but refreshing the browser will reinitialize the session state. Alternatively, there might be a command or button to reset the conversation.)
Monitor the Model indicator in the sidebar (it shows which model is being used and maybe the key source) to ensure you’re on the intended provider. If you need to switch providers, go to the Settings page, change it, and return to Chat. 
Example Workflow using Chat: You have an urgent incident where a conference room’s Display isn’t working. You can type a description in one message, or directly use a slash command: 

Step 1: In Chat, type a SOP command: /sop agent=Zoom_Room_Agent name="Display Fix" Steps: - Gather Room Details - Display status - Restart Display - Verify Display working – Check Display Status Zoom Health Dashboard – Confirm Status - Okay

When you send this, the app will create a new recipe “Display Fix” with those steps, create or use the agent “Zoom_Room_Agent”, and execute the procedure. The assistant will respond once it’s done, e.g., “Recipe Display Fix created and run on agent Zoom_Room_Agent – all steps completed successfully.” 

Step 2: You can ask follow-up questions like “Show me the results of each step.” The assistant, having the context, might detail what happened in Gather display status, etc., or you can check the Dashboard page for the run details. 

Step 3: If the fix needs to be recurring, you could go to Workflows page and formally create a workflow with the Support agent and Display Fix recipe on a schedule. The Chat interface thus serves both as an interactive assistant and a quick command console for one-off operations. 

AGENTS

The Agents page (🤖 Agents) is where you manage your AI agents. An Agent in this app represents a persona or context under which recipes run (for example, an agent might correspond to a domain like  “Support” or “NetworkOps” and could have specific configuration or tool access). On this page, you can create new agents, view and edit existing agents, and manually trigger agent runs with chosen recipes[6]. Using the Agents page:

Open the “Agents” page from the sidebar. You’ll see a form or section to add a new agent, and below that, a list of agents already in the system (if any exist).

Create a New Agent: In the New Agent form:
Enter the Name of the agent. Choose a descriptive name (e.g. “Support”, “Networking”, or a person’s name if appropriate). Agent names must be unique.

Optionally enter a Domain/Role or other metadata if the form asks for it. (For instance, the app might have a field for “domain” to categorize the agent’s scope, like “IT Support” or “AV Operations”.)

(Optional) Provide any configuration details. There may be a text area for JSON config or parameters that the agent uses. If you’re unsure, you can leave default or blank – by default an agent will use global settings.

Click Create Agent (or Add Agent). If the input is valid, the agent will be saved in the database and appear in the agents list. If the name was missing or a duplicate, you’ll get an error prompt to adjust and resubmit.

View Existing Agents: The page will list existing agents, each in a panel or row showing basic info (name, domain, etc.). This list might be in a table or just headings.

Some agents might be pre-loaded from the Setup Wizard (for example, an agent named “Support” might already exist as a demo).

Trigger a Run from Agents Page: For each agent, you likely have controls to quickly run a recipe with that agent:
Select an agent from the list (or the agent might have its own sub-section with actions).

Choose a Recipe to run with this agent. There might be a dropdown menu or button like “Run Recipe” next to the agent. If you click it, you’ll be prompted to pick one of the available recipes.

After selecting the recipe, click Run (or a similar action button). This will immediately execute the chosen recipe using the selected agent (essentially a one-off workflow run).

You should see a confirmation or status – perhaps the page will show “Running…” and then “Completed” or log output. 
The results (success or failure of each step) will be recorded in the system.

If the app does not show detailed output on the Agents page itself, you can switch to the Dashboard page to view the run details (the Dashboard collects all runs from any source). A note on the Agents page might remind you that run results appear on the Dashboard[6].

Edit or Remove Agents: If the UI allows, you can edit an agent’s details. For instance, clicking an agent name might let you update its config or rename it. Ensure that any changes you make keep the name unique. To delete an agent, look for a Delete button or icon on that agent’s entry – note that deleting an agent might also remove related workflows or runs.


Using Agents in Workflows: Remember that to automate runs, an agent by itself isn’t scheduled – you need to create a Workflow combining an agent with a recipe (on the Workflows page). 

The Agents page is primarily for management and manual triggers. So, after adding a new agent here, you can go to the Workflows page to include it in a scheduled task. 

Example: Suppose you have a new system called “DisplayAgent” that handles display issues. 
On the Agents page: - Add an agent Name: “DisplayAgent”, Domain: “AV Support”. Create it. - It appears in the list. 
Now you want to test it with an existing recipe “Display Reset”. 
Next to DisplayAgent, select recipe “Display Reset” and run it. 
The app will execute that recipe with DisplayAgent’s context immediately, and you’ll see a success message if all steps pass. 
The outcome (step logs) can be reviewed on the Dashboard. 
By managing agents in this way, you can segregate responsibilities – e.g., a “Zoom_Room_Agent” agent could be created for Zoom Room related recipes, and a “KB__Article_Agent” for ServiceNow KB Article recipes, “EventsAgent” for AV Event Support Steps, etc. Recipes The Recipes page (📜 Recipes) is where you can create, edit, and manage the procedural recipes that define the actions your agents will perform. A Recipe in IPAV format is essentially a YAML document outlining a series of steps divided into the four phases: Intake, Plan, Act, Verify (that’s what IPAV stands for). This page lets you author those recipes with proper structure, validate them, and save them to the system’s recipe library[6]. Using the Recipes page:
Open the “Recipes” page from the sidebar. You will typically see:
A form or input to create a New Recipe.
A list or selector of Existing Recipes that have been saved.
Possibly an editor area that shows the recipe YAML content for viewing or editing.
Create a New Recipe:
Look for a button or form labeled “New Recipe” or “Create Recipe.” When you initiate a new recipe, the interface might ask for a name and optionally create a template for you.
Enter a Recipe Name when prompted. Use a concise title that describes the procedure (e.g., “Zoom Room Reset” or “Network Port Diagnostics”).
After providing the name, the app might populate a YAML template in an editor, including placeholders for guardrails, success_metrics, and empty sections for intake, plan, act, verify. (If you started a recipe via the Chat /recipe new command, you may find it pre-populated here as well[43][16].)
Fill in each section of the YAML: o Under intake: list the steps or data gathering actions to take at the start. o Under plan: describe planning steps (if any, or leave empty if not needed). o Under act: list the main actions to perform (e.g., commands to execute, tool calls). o Under verify: list the checks or validations to confirm the outcome. o You can also edit description (what this recipe does) and add any relevant guardrails (like timeouts or rollback actions) or success_metrics (KPIs to measure success).
As you edit, use the provided syntax highlighting or linting – the app may underline errors or provide a Validate function.
Validate the Recipe: Click on a “Validate” button if available (or the app might auto-validate). This runs the YAML through a validator to ensure the format is correct and all required fields are present[16]. If there are issues (e.g., a missing colon or a mis-indented line), you’ll get an error message indicating what to fix.
Once validation passes, click “Save Recipe”. The recipe will be saved to the library (written to a YAML file in the recipes/ directory and recorded in the database). You may see a success message or the new recipe appear in the list of recipes.
View or Edit Existing Recipes:
On the page, you should see a sidebar or dropdown of existing recipe names. Select a recipe to load its content into the editor.
The YAML for the selected recipe will be displayed. You can now update it if needed (change steps, tweak parameters). After editing, validate and save again to update the stored version.
The system may keep versioning internally (for example, it might store a version number in the YAML or as a field). If so, each time you save, the version might increment, or it may overwrite – check if there’s a version field in the YAML and update it if you intend to track version changes.
Recipe Actions: Next to each recipe, there might be additional actions:
Run Recipe – This could allow you to test-run the recipe immediately with a chosen agent (similar to using the Agents page). If available, it will prompt for an agent or use a default agent, then execute the recipe’s steps. This is a quick way to verify your recipe works as expected.
Delete Recipe – Remove a recipe from the library (this might disable any workflows using it, so use with caution).
Export Recipe – Possibly export the YAML content (though generally the Export/Import on Workflows page handles all recipes).
Using Recipes in Workflows: Creating a recipe alone doesn’t schedule it. To have it run automatically or repeatedly, go to the Workflows page and create a workflow pairing this recipe with an agent and trigger. You can create multiple workflows using the same recipe with different agents or schedules if needed.
Tips for Authoring Recipes:
Keep steps clear and actionable. If a step involves an external tool or integration, ensure the agent or environment has access to that tool. For example, a step like “Verify image via Slack” implies the Slack tool is configured – the app’s MCP Tools page can show if it is.
Use the guardrails to define timeouts or rollback steps for safety. For instance, you might add a timeout_minutes to ensure a recipe doesn’t hang, and a rollback_actions list to specify what to do if the act phase fails (like notifying someone).
Leverage success_metrics to define what success looks like (the app doesn’t enforce these but can use them for reporting on the Dashboard).
Always validate after editing to catch YAML formatting errors. A common mistake is incorrect indentation or forgetting to put a dash - for list items. Example: Let’s say you want to add a recipe for rebooting a network switch port. - On Recipes page, create New Recipe, name it “Switch Port Reboot”. - The template appears. Fill it out: - Intake: maybe a step to get the port ID or device name from the user or system. - Plan: could be empty or something like “Schedule downtime notification”. - Act: steps: “Disable port”, “Enable port”. - Verify: step: “Ping device to confirm connectivity”. - Validate the YAML – the app says “Valid!”. - Save the recipe. Now “Switch Port Reboot” is in the library. - To test it, you might go to Agents page and pick an agent (like “NetworkAgent”), run this recipe and see the outcome. Or create a workflow to run it nightly on certain ports. By managing your library of recipes here, you create a knowledge base of operational procedures that can be executed by your AI agents. MCP Tools The MCP Tools page (🔌 MCP Tools) is dedicated to managing and testing the external integrations (tools) that the agents can use in their workflows. MCP stands for “Mission Control Platform” tools – these might include services like Slack for messaging, Zoom for controlling devices, ServiceNow for ticketing, etc. This page lets you discover which tools are available, check their connectivity (health), and perform actions on them for testing or setup purposes[7]. Using the MCP Tools page:
Open the “MCP Tools” page from the sidebar. You will see a list of tools/connectors that are configured in the system. Each tool might be represented by a name and perhaps an icon or description (e.g., “Slack,” “Zoom Room Controller,” “ServiceNow Incident API,” etc.).
For each listed tool, there are typically a couple of actions:
Health Check – a quick way to ping the tool and see if it’s responsive. In the UI, this might be a button like “Check Health” next to the tool name. For example, next to Slack connector, click Check Health; the app will call the Slack integration’s health endpoint (or attempt a simple API call) and return a status (such as “OK” or details of an error). The result might display inline (e.g., a green check or a message saying “Slack: healthy”) or in a pop-up.
Perform Action – a way to invoke a specific function of the tool. This might be a form where you can specify an action and parameters. For instance, for ServiceNow (incident_ticketing), there could be a small form to create an incident: fill in fields like Title and Description and click Create Incident (which under the hood sends a /tool action incident_ticketing {...} command). Or, more generally, there could be a text area where you can input a JSON payload for an action. o The UI may present common actions in a user-friendly way. For example, a “Send Test Message” for Slack (which might send a hello message to a default channel), or “Reboot Zoom Room” for a Zoom controller. o If not, you can still use the generic interface: select the tool, choose an action from a dropdown or type it (like “create” for a ticket, “mute” for a Zoom call, etc.), input any required arguments (the page might show a JSON template or individual fields), then press Execute.
Some tools might require configuration before use (like API keys or endpoints). If a tool is not configured, its health check will fail or it might be marked as unavailable. The page could indicate this (perhaps with a warning icon).
Review Tool Responses: After you trigger a health check or action, observe the response:
Health checks should return a status. If a tool is healthy, you might see a success message or a green indicator. If not, you might get error details (for example, “ServiceNow: authentication failed” if credentials are wrong).
Actions will likely show the result of the action. If you created a ticket via ServiceNow action, the page might display the new ticket ID or a success confirmation. If you sent a Slack message, it might say “Message sent to #channel”. Any returned data (JSON) could be shown, possibly formatted for readability.
Use Cases for MCP Tools page: This page is especially useful for:
Initial Setup: ensuring each integration is properly configured (all health checks pass before you rely on them in recipes).
Troubleshooting: if an agent’s workflow fails at a tool step, you can manually test that tool here to see if the issue is with the tool or the recipe logic.
Ad-hoc Actions: performing one-off tasks on tools without writing a full recipe or going through chat. For example, quickly creating an incident or fetching some data.
Mock Mode Note: If you enabled “mock mode” in Settings (for example, to simulate tools), the MCP Tools page might show that it’s in mock mode. In this mode, health checks and actions will not hit real external services but rather return dummy success responses. This is useful for demo or development when you don’t want to actually call, say, a real Slack or ServiceNow instance. The page might label tools as “[mock]” in this case.
Security: Some tools involve sensitive operations (like running a command on a device or creating a ticket). The page is accessible only to authorized users of your Streamlit app, so ensure proper access control if needed. Always double-check the parameters you send in an action to avoid unintended effects (especially in production environments). Example: On the MCP Tools page, suppose you see: - Slack – Click Check Health. It returns “Slack: OK”. Great, the Slack API is reachable with the provided token. - Zoom Room Controller – Click Check Health. Suppose it returns an error “Zoom controller not responding”. You might need to check network connectivity or credentials for that tool. - ServiceNow Incident – There is a simple form: “Title” and “Description”. You input “Test Ticket” and “This is a test via IPAV app” and hit Create Incident. The page shows “Incident INC12345 created successfully.” Now you know the connection works and you’ve created a test record. After verifying tools here, you can confidently use them in your recipes (for example, a recipe’s Act step might post a Slack message or create a ServiceNow ticket as part of a resolution plan). Workflows The Workflows page (🧩 Workflows) is where you orchestrate automated runs by combining an Agent with a Recipe on a specified trigger. A Workflow in this app ties together: which agent will execute which recipe, and when/under what conditions it should run. This page lets you create new workflows, manage existing ones (enable/disable or manual run), and import/export all workflow configurations[7]. Using the Workflows page:
Open the “Workflows” page from the sidebar. The layout is typically:
A New Workflow form at the top.
A list of Existing Workflows below, each with controls.
A section for Import / Export at the bottom.
Create a New Workflow:
Locate the New Workflow section or button. It will have input fields for at least: o Name: The name of the workflow (must be unique, not case-sensitive unique as well). Choose a descriptive name (e.g., “Nightly Projector Check” or “Auto-Reboot Switch Port 5”). o Agent: A dropdown or selector of available agents. Choose the agent that should perform the recipe. o Recipe: A dropdown of available recipes. Choose the recipe that defines the procedure to run. o Trigger: A selector for trigger type. The common options are manual or interval: o Manual means the workflow does not run on a schedule – you will trigger it manually (via the UI or API). Essentially it’s dormant until you click “Run now.” o Interval means it runs periodically. When you choose interval, another field appears:  Interval minutes: Input a number (e.g., 60 for hourly, 1440 for daily). This defines how often to run the workflow. o (If the app supported cron or specific schedule times, there might be more fields, but the UI here specifically mentions interval in minutes.)
Fill in all these fields. For example: Name: “Morning Systems Check”, Agent: SupportBot, Recipe: “Daily AV Systems Check”, Trigger: interval, Interval: 1440 (for daily).
Click Create Workflow (submit the form). If anything is missing or invalid, the app will display an error: o It will ensure name is not empty and not already in use[44]. o It will ensure you selected an agent and a recipe (if you forgot, it reminds you: “Select an agent/recipe” as needed)[45]. o If prerequisites are missing (no agents or no recipes in the system yet), it will show an info message guiding you to create those first (e.g., “Add an agent on the Agents page before creating workflows” if agent list is empty)[46].
Once you fix any issues and resubmit, the workflow is saved. You should see a success confirmation (“Workflow created.”)[47] and the new workflow will appear in the list of workflows.
View and Manage Existing Workflows:
Each workflow in the list will likely show: o Name of the workflow. o The Agent and Recipe it uses (maybe by ID or name)[48]. o The Trigger type and schedule (e.g., “manual” or “interval 60 min”). o Status indicator: A colored dot or icon indicating if the last run succeeded or if it’s currently enabled. For example, a green dot might mean the last run was successful, yellow for running or pending, red for a recent failure[49]. o Last run / Next run times: It may display the timestamp of the last execution and the next scheduled run if interval-based[50].
For each workflow, there will be action buttons: o Run now: Executes the workflow immediately on demand[8]. Use this to test or to manually trigger an interval workflow outside its schedule. When you click Run now, the app will run the associated recipe with the agent right away. You’ll see a spinner or message (“Executing workflow...”) and then a toast notification when done (e.g., “Run 42 completed ✅”)[51]. The page won’t show step-by-step outputs, but you can check the Dashboard for details of that run. o Enable/Disable: If a workflow is interval-based, you can toggle it on or off without deleting it[9]. For example, if you created a daily workflow but want to pause it, click Disable – the workflow will not run on schedule until you re-enable it (which toggles the button back to “Enable”). The UI will reflect the change immediately (and Next run might show “—” when disabled). o Rename: There might be a small option (perhaps a “✏️” icon or a popover) to rename the workflow[52]. Clicking that typically opens a text field where you can type a new name. When you save the rename, if the name is valid (not empty and not conflicting), it updates the workflow[53][54]. If there’s an issue (like duplicate name), it will show an error. o Delete: A button (often red or a trashcan icon) to remove the workflow[55]. You might be asked to confirm. Deleting will stop any future runs of that workflow and remove it from the list; it does not delete the underlying agent or recipe (you could recreate a workflow with them if needed).
Tick scheduler: At the top of the workflows list, there is a button labeled “⏱️ Tick scheduler”[56]. This is a manual trigger to advance the internal scheduler. Normally, the app’s engine will automatically schedule runs at the specified intervals (perhaps using an internal clock or Streamlit’s rerun mechanism). If you click “Tick scheduler,” the app will immediately evaluate all interval workflows to see if any should run now (as if time jumped forward) and execute them if due. It then reports how many workflows were triggered by the tick (e.g., a message “Ticked. Ran 2 workflow(s).” appears)[56]. This is particularly useful in development or demo: you don’t want to wait an hour to see your hourly workflow run, so you manually tick the scheduler to test it.
Import / Export Workflows: At the bottom of the page, you’ll find the Import / Export section:
Export a bundle: This allows you to download all current Agents, Recipes, and Workflows as a single ZIP file[11][57]. There will be a multiselect where you choose what to include (by default all three categories are selected: agents, recipes, workflows)[58]. After selecting, click the “Generate export” button. The app will package the data (you’ll see a success with counts, e.g., “Export ready • agents=3 recipes=5 workflows=4”[59]). A Download .zip button will appear – click it to save the file (named something like sma-avops-export-.zip) to your computer[60]. Keep this file as a backup or to migrate data to another deployment.
Import a bundle: You can upload a ZIP file of a previously exported bundle to load its contents into this app[12]. Use the file uploader to select the .zip file (ensure it’s from the correct source and not tampered). Next, choose a Merge strategy – skip (keep existing data, ignore duplicates), overwrite (if an agent/recipe/workflow name already exists, update it with the imported one), or rename (keep both by renaming the imported duplicates)[61]. By default, it might be “skip”. Also decide if you want a Dry run first (checkbox): in dry run, it will simulate the import and tell you what it would do without actually changing anything[62]. This is useful to see if there would be conflicts or a large number of changes.
Click Import bundle to proceed. The app will process the ZIP: create any new agents, recipes, workflows, and apply the merge strategy for conflicts[63]. You will then see a JSON report of what happened (or would happen, if dry run)[64] – e.g., how many agents created/updated/skipped, etc. If it was a dry run, nothing is actually saved and it tells you that (so you can then uncheck dry run and import for real). If not dry, the changes are now live – your lists of agents/recipes/workflows update accordingly. A success message will indicate completion and might prompt you to refresh the page to see all changes.
Use import carefully, especially with overwrite, as it can replace your current configurations. Import is great for deploying a set of workflows from one environment to another (say, from a staging environment to production) or restoring from a backup.
Monitoring Workflows: After you have workflows running on interval, the page itself doesn’t continuously update in real time unless you refresh it (Streamlit pages typically rerun on certain actions or intervals). However, you can usually rely on the Dashboard to see run outcomes, or use the tick button to manually drive runs. Make sure the Streamlit app itself is always running (if you close it or it times out on a cloud service, scheduled tasks won’t run until it’s active again due to the nature of Streamlit). Example Scenario: You want a daily workflow that checks all AV devices every morning: - Ensure you have an agent “SupportBot” and a recipe “Daily AV Systems Check” ready. - On Workflows page, fill New Workflow: Name “Daily AV Check”, Agent: SupportBot, Recipe: Daily AV Systems Check, Trigger: interval, Interval minutes: 1440. - Create Workflow. It appears in list as enabled (since interval is set). - The next run time is shown for tomorrow at the same time you created it (approximately). - Click “Run now” to test it immediately. It executes; you get a confirmation toast. Go to Dashboard, see that the run happened (with maybe success status). - Satisfied, you let it be. Tomorrow, if the app is running, the workflow will run on its own. (If you had the app open, you’d see nothing on the Workflows page, but on Dashboard a new run entry would appear.) - If you go on vacation, you could disable this workflow by clicking “Disable” – it won’t run until you re-enable it. - If you need to adjust it to run twice a day, you can rename it (if you want) and change the interval: currently, you cannot directly edit the interval via UI; you might delete and recreate, or if the app allowed editing trigger, do that. Alternatively, create a second workflow with same agent/recipe and a different schedule (though that could lead to overlapping runs). - Use export to back up your workflows. Say you set up 10 workflows and want to replicate in another organization’s instance of the app – just export and import on the other side, choosing merge strategy appropriately. The Workflows page is your automation hub – once configured, your “digital operators” (agents) will carry out the “playbooks” (recipes) at the times you’ve scheduled, without further manual intervention, freeing you to monitor outcomes on the Dashboard. Dashboard The Dashboard page (📊 Dashboard) provides a comprehensive view of your system’s operations. It aggregates data about workflow runs and agent activities, showing you metrics and allowing you to dig into the details of each execution. In essence, this is where you can monitor KPIs (Key Performance Indicators) like success rates and durations, see trends over time, and inspect the logs or artifacts of each run[7]. How to use the Dashboard page:
Open the “Dashboard” page from the sidebar. The dashboard typically contains several sections:
Summary KPIs: At the top, you may see big number widgets or metrics (using Streamlit metric or similar) showing statistics such as: o Total Runs: the total number of workflow runs executed. o Success Rate: percentage of runs that completed without errors (perhaps calculated as successful runs divided by total, displayed as a percentage). o P95 Duration: the 95th percentile of run duration (i.e., 95% of runs finish within this time, giving an idea of worst-case runtime). This could be labeled as “p95 run time” and shown in seconds or minutes. o Possibly Active Workflows: how many workflows are currently enabled.
Each of these might be accompanied by an icon or trend indicator (for example, an up/down arrow if comparing to a previous period).
Trends/Charts: Below the summary, there could be visualizations: o A line chart or area chart showing the number of runs over time (by day or hour). o A bar chart perhaps for success vs failure counts in the last N runs. o A line graph for average duration per day. o These help you spot patterns (e.g., an increase in failures on a certain day).
Recent Runs Table/List: A list of the most recent workflow runs, typically in reverse chronological order. Each entry might include: o Timestamp of the run, o Name of the workflow (or agent & recipe), o Result (Success/Failed), o Duration of the run, o Possibly a link or button to “view details” of that run.
If you have multiple workflows, you might also have a filter or dropdown to filter the dashboard to a specific workflow or agent.
Inspect Run Details: The key feature is being able to see what happened during each run:
If the dashboard lists runs, click on a particular run entry (or a “Details” button for it). This should expand or navigate to the detailed log: o You will see the breakdown of the run by IPAV phases. For example: o Intake: shows each intake step executed and its outcome (e.g., “Gathered room_id – OK”). o Plan: shows plan steps. o Act: shows act steps (these are usually the core actions; if they involve tools, you might see what was done, like “Sent Slack message to #alerts – Success”). o Verify: shows verification steps and whether they passed. o If any step failed or had an error, it would be indicated (with error messages or exception details). o The app might show checkmarks or red Xs next to each step for pass/fail. o It may also log any artifacts or outputs. For example, if a step produced a file or a data blob, there could be a link to that artifact, or if it’s a text result, it might be shown inline. o If the run triggered external systems (like created a ticket), the artifact might be a ticket ID or URL. o This information helps you verify that your workflows are doing what you expect, and troubleshoot where they aren’t.
Close or collapse the details when done, to return to the main dashboard view.
Using Dashboard for Monitoring:
Keep an eye on success %. A healthy system should have a high success rate. If you see this percentage drop, it means some workflows are failing. Scroll to recent runs to identify which ones failed (they’ll be marked in red or with a “Failed” status).
Use the p95 duration metric to gauge performance. If your p95 is creeping up over time, perhaps some workflows are taking longer (maybe an external API is slowing down or a device is not responding quickly). This can hint at capacity issues or need for optimization.
Look at trends: For instance, if a certain time of day has a spike of runs or failures, you might correlate that with specific scheduled tasks or external system downtime.
If provided, use any filter controls to drill down. E.g., filter by a particular workflow to see its history exclusively.
Real-time Updates: Depending on how the app is built, the dashboard might auto-refresh at intervals, or you might need to manually refresh the page to get the latest data (Streamlit typically reruns on interactions, but you can also use st.experimental_refresh or similar). If a workflow just ran and you don’t see it, try refreshing the page or triggering an interaction (like toggling a filter).
Maintaining the System: The insights from the Dashboard inform you if you need to take action:
If a workflow is failing often, click into it and see the error – maybe the recipe has a mistake or a tool is down. You might then edit the recipe or fix the integration and try again.
If runs are taking too long, consider adjusting the recipe (maybe reduce waiting times or split a heavy workflow into smaller parts), or check the external service performance.
If everything is green and quick – great! You can confidently rely on these autonomous workflows.
Audit and Records: The Dashboard acts as an audit log of what your AI agents did. In a production environment, this is important for accountability. You can show, for example, that “Yesterday, the Backup Verification workflow ran at 02:00 AM and verified all backups – here are the logs.” This helps in compliance and reviewing automated changes. Example: After running for a week, you check the Dashboard: - KPIs: 100 runs total, 95% success, p95 duration 120 seconds. The success rate is good, but not 100%. You see p95 is 2 minutes, which is fine for your tasks. - Trend: A chart shows that each night around 2 AM you have ~5 runs (these correspond to nightly maintenance workflows), and one of those nights had a failure spike (two fails). - Recent Runs: One entry from last night shows Failed for “Nightly Cleanup” workflow. You click it. - Details: In the Act phase of “Nightly Cleanup,” a step “Delete temp files on Server1” failed with an error “SSH connection refused.” Now you know the cause – maybe Server1 was offline. This might not need a change (could be a one-time issue), but you decide to keep an eye on it. You could even add a retry in the recipe guardrails for next time. - Another run shows a longer duration (p95). It was “Full Backup” took 300 seconds whereas normally it’s 100s. In details, you see it waited on a network copy. Could be transient, but it’s good to know. - Using this info, you might adjust schedules or step timeouts accordingly. The Dashboard thus closes the loop: you designed automation (recipes + workflows), the agents executed them, and now you verify and refine based on real data, ensuring a robust Agentic Ops system.
