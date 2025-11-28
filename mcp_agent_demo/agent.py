"""Simple agentic demo that uses the ServiceNow MCP package programmatically.

This demo does three things:
- Instantiates the ServiceNowMCP server object (as a library) using credentials from `.env`.
- Lists available tools and inspects the input schema for `create_incident`.
- Builds sample parameters and calls `create_incident`, printing the output.

Prerequisites: clone and install the `servicenow-mcp` package in editable mode as described
in the upstream README, and create a `.env` file with your ServiceNow credentials.
"""

import json
import sys
from mcp_agent_demo.mcp_helper import create_mcp, list_tools, build_params_from_schema, call_tool_sync


def main():
    print("Creating MCP instance from environment...")
    mcp = create_mcp()

    print("Listing available tools (this may be filtered by MCP_TOOL_PACKAGE)...")
    tools = list_tools(mcp)
    # list_tools is async; helper returns a coroutine so accommodate
    import asyncio
    tools = asyncio.run(tools)

    tool_names = [t.name for t in tools]
    print("Loaded tools:")
    print(", ".join(tool_names[:50]))

    target = "create_incident"
    if target not in tool_names:
        print(f"Tool '{target}' not available in current package. Use MCP_TOOL_PACKAGE=full or check config.")
        sys.exit(1)

    # Find its input schema
    tool_obj = next(t for t in tools if t.name == target)
    schema = tool_obj.inputSchema

    print("Detected input schema for create_incident:")
    print(json.dumps(schema, indent=2)[:1000])

    params = build_params_from_schema(schema)
    print("Built sample params (you should replace these with real values):")
    print(json.dumps(params, indent=2))

    print("Calling create_incident...")
    result = call_tool_sync(mcp, target, params)
    # result is a list of TextContent objects; print their text
    for item in result:
        print("--- Tool output ---")
        print(item.text)


if __name__ == "__main__":
    main()
