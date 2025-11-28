"""Utility: list all available MCP tools (prints tool names and descriptions).

Run as module (recommended) so package imports resolve.

PowerShell example (use forward slashes or escape backslashes):
    $env:TOOL_PACKAGE_CONFIG_PATH='C:/abs/path/to/mcp_agent_demo/tool_packages.yaml'; $env:MCP_TOOL_PACKAGE='full'; C:/.../python.exe -m mcp_agent_demo.list_tools
"""

# When executed directly from the `mcp_agent_demo` folder (e.g. "python list_tools.py"),
# Python may not find the package imports. Add the repo root to sys.path so
# `from mcp_agent_demo.mcp_helper import ...` works when running the script directly.
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

import asyncio
import json
from mcp_agent_demo.mcp_helper import create_mcp, list_tools


def _plain_table(rows, headers):
    # compute column widths
    cols = list(zip(*rows)) if rows else [[] for _ in headers]
    widths = []
    for i, h in enumerate(headers):
        col = cols[i] if cols and i < len(cols) else []
        max_cell = max([len(str(x)) for x in col], default=0)
        widths.append(max(len(h), max_cell))

    # header
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * widths[i] for i in range(len(headers)))
    print(header_line)
    print(sep_line)
    for row in rows:
        print(" | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))))


def main():
    mcp = create_mcp()
    tools = asyncio.run(list_tools(mcp))

    rows = []
    for t in tools:
        name = getattr(t, "name", "<unknown>")
        desc = getattr(t, "description", "")
        schema = getattr(t, "inputSchema", None)
        try:
            if isinstance(schema, dict):
                required = schema.get("required", [])
                props = schema.get("properties", {})
                props_count = len(props)
                required_str = ",".join(required) if required else "-"
            else:
                required_str = "-"
                props_count = "-"
        except Exception:
            required_str = "-"
            props_count = "-"

        rows.append((name, desc, required_str, props_count))

    headers = ["Name", "Description", "Required", "#Props"]

    # Try to use rich for a prettier table
    try:
        from rich.table import Table
        from rich.console import Console

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Description")
        table.add_column("Required", style="yellow")
        table.add_column("#Props", justify="right")

        for r in rows:
            table.add_row(str(r[0]), str(r[1]), str(r[2]), str(r[3]))

        console = Console()
        console.print(table)
    except Exception:
        # Fallback to plain table
        _plain_table(rows, headers)


if __name__ == "__main__":
    main()
