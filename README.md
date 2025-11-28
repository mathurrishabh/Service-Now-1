ServiceNow MCP Agent Demo

Purpose: Minimal end-to-end Python demo that shows how to programmatically use the servicenow-mcp package as a library (instantiate the MCP server object, list tools, and call a tool). This demonstrates an "agentic" flow: plan (choose the tool) -> prepare inputs -> execute.

Files:

agent.py: CLI demo runner.
mcp_helper.py: helpers to build ServerConfig from .env, inspect tools, and call tools synchronously.
requirements.txt: Python deps for the demo (install into the same venv where servicenow-mcp is installed).
Prerequisites

Python 3.11+
A ServiceNow instance with credentials
The servicenow-mcp repo cloned and installed in editable mode (per upstream README)
Quick setup

Clone and install the upstream MCP package (do this in the workspace or somewhere you prefer):
git clone https://github.com/echelon-ai-labs/servicenow-mcp.git
cd servicenow-mcp
python -m venv .venv
.venv\Scripts\activate
pip install -e .
In the mcp_agent_demo folder create a .env file with your ServiceNow credentials (basic auth example):
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_AUTH_TYPE=basic
SERVICENOW_USERNAME=your-username
SERVICENOW_PASSWORD=your-password
Create and activate (or reuse) a virtualenv and install demo dependencies:
cd ..\mcp_agent_demo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Note: make sure the Python environment can import servicenow_mcp (i.e., the editable install from step 1 is in the same interpreter or installed into the same venv).

Run the demo

.venv\Scripts\activate
python agent.py
What the demo does

Instantiates the MCP server object with your ServiceNow credentials.
Calls list_tools (MCP introspection) and finds create_incident.
Builds sample parameters from the tool schema and calls create_incident.
