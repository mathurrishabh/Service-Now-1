"""Attempt to resolve incidents using MCP `resolve_incident` tool.

Reads `resolved_and_kb.json` to get the four incidents, then calls MCP's
`resolve_incident` tool for each. Saves results to `mcp_resolve_results.json`.
"""
import json
from pathlib import Path
from typing import Dict

from mcp_agent_demo.mcp_helper import create_mcp, list_tools, build_params_from_schema, call_tool_sync


def main():
    base = Path(__file__).parent
    src = base / 'resolved_and_kb.json'
    if not src.exists():
        print('No resolved_and_kb.json found; run finalize_resolve_and_create_kb.py first')
        return

    records = json.loads(src.read_text())
    mcp = create_mcp()
    import asyncio
    tools = asyncio.run(list_tools(mcp))
    tool_names = [getattr(t, 'name', None) for t in tools]
    print('Available MCP tools:', tool_names)

    if 'resolve_incident' not in tool_names:
        print("Tool 'resolve_incident' not available in MCP toolset.")
        out = base / 'mcp_resolve_results.json'
        out.write_text(json.dumps({'error': "resolve_incident not available", 'available_tools': tool_names}, indent=2))
        return

    # find the tool object to get schema
    resolve_tool = next(t for t in tools if t.name == 'resolve_incident')
    schema = getattr(resolve_tool, 'inputSchema', {})

    results = []
    for rec in records:
        sys_id = rec.get('sys_id')
        number = rec.get('incident_number')
        params = build_params_from_schema(schema) if schema else {}
        # common parameter names: sys_id, incident_id, number, comment, resolution
        if 'sys_id' in params:
            params['sys_id'] = sys_id
        elif 'incident_id' in params:
            params['incident_id'] = sys_id
        elif 'number' in params:
            params['number'] = number
        # add a resolution comment if possible
        if 'comment' in params:
            params['comment'] = 'Resolved via MCP automation; see KB article.'
        elif 'resolution' in params:
            params['resolution'] = 'Resolved via MCP automation; see KB article.'
        else:
            # include a best-effort field
            params['note'] = 'Resolved via MCP automation; see KB article.'

        print('Calling resolve_incident for', number, sys_id, 'with params', params)
        try:
            res = call_tool_sync(mcp, 'resolve_incident', params)
            # res is a list of content objects; record text
            results.append({'incident_number': number, 'sys_id': sys_id, 'success': True, 'response': [r.text for r in res]})
        except Exception as e:
            results.append({'incident_number': number, 'sys_id': sys_id, 'success': False, 'error': str(e)})

    out = base / 'mcp_resolve_results.json'
    out.write_text(json.dumps(results, indent=2))
    print('Done. Results saved to', out)


if __name__ == '__main__':
    main()
