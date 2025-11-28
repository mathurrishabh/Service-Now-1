"""Recreate incidents listed in `created_incidents.json` by calling the MCP `create_incident` tool.

This script reads `mcp_agent_demo/created_incidents.json` and creates new incidents using
the `short_description` and `caller` fields. Results are saved to
`mcp_agent_demo/recreated_incidents.json`.
"""

import json
import asyncio
from pathlib import Path
from mcp_agent_demo.mcp_helper import create_mcp, list_tools, build_params_from_schema, call_tool_sync


def main():
    repo = Path(__file__).parent
    src = repo / 'created_incidents.json'
    if not src.exists():
        print(f"Source file not found: {src}")
        return

    data = json.loads(src.read_text(encoding='utf-8'))

    print("Creating MCP instance...")
    mcp = create_mcp()
    tools = asyncio.run(list_tools(mcp))
    create_schema = None
    for t in tools:
        if getattr(t, 'name', None) == 'create_incident':
            create_schema = t.inputSchema
            break

    results = []
    for entry in data:
        short = entry.get('short_description')
        caller = entry.get('caller')
        params = build_params_from_schema(create_schema) if create_schema else {}
        # set fields if present
        if create_schema and 'properties' in create_schema:
            props = create_schema['properties']
            if 'short_description' in props:
                params['short_description'] = short
            if 'description' in props and not params.get('description'):
                params['description'] = f"Recreated: {short}"
            # set caller-like field if available
            for cf in ('caller_id', 'caller', 'caller_name'):
                if cf in props:
                    params[cf] = caller
                    break
        else:
            # best-effort
            params['short_description'] = short
            params['caller'] = caller

        print(f"Creating incident: {short} (caller={caller})")
        try:
            res = call_tool_sync(mcp, 'create_incident', params)
            # res is list of TextContent
            results.append({'input': entry, 'output': [r.text for r in res]})
        except Exception as e:
            print('create_incident failed:', e)
            results.append({'input': entry, 'error': str(e)})

    out = repo / 'recreated_incidents.json'
    out.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('Done. Results saved to', out)


if __name__ == '__main__':
    main()
