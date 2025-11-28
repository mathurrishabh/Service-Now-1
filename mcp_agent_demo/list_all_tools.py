"""List all tool names available in the installed `servicenow_mcp` package.

This prints the keys of `ServiceNowMCP.tool_definitions` which represents all
tools the package defines (not just those enabled in a package).
"""

from mcp_agent_demo.mcp_helper import create_mcp
import json


def main():
    mcp = create_mcp()
    # tool_definitions is a dict: tool_name -> (impl_func, params_model, ...)
    tool_names = sorted(list(mcp.tool_definitions.keys()))
    print(json.dumps(tool_names, indent=2))


if __name__ == "__main__":
    main()
