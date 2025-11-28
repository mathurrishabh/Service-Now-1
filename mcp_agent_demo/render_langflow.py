"""Render the LangGraph flow JSON to a visual graph (DOT + PNG).

This script reads `langgraph_flow.json` (created by the supervisor) and
renders `langgraph_flow.dot` and `langgraph_flow.png` using the `graphviz` python package.
If `langgraph_flow.json` is missing, it will build a default flow definition.
"""
from pathlib import Path
import json
import sys


BASE = Path(__file__).parent


def load_flow_def():
    jf = BASE / 'langgraph_flow.json'
    if jf.exists():
        try:
            return json.loads(jf.read_text())
        except Exception:
            pass
    # default fallback
    return {
        'nodes': [
            {'id': 'input', 'label': 'User Input'},
            {'id': 'search_kb', 'label': 'SearchKB'},
            {'id': 'decide', 'label': 'Decide'},
            {'id': 'return_kb', 'label': 'ReturnKB'},
            {'id': 'create_ticket', 'label': 'CreateTicket'},
        ],
        'edges': [
            {'from': 'input', 'to': 'search_kb'},
            {'from': 'search_kb', 'to': 'decide'},
            {'from': 'decide', 'to': 'return_kb', 'condition': 'resolved_found'},
            {'from': 'decide', 'to': 'create_ticket', 'condition': 'no_match'},
        ]
    }


def render_with_graphviz(flow_def):
    try:
        import graphviz
    except Exception as e:
        print('graphviz python package not available:', e)
        print('Install with: python -m pip install graphviz')
        sys.exit(1)

    dot = graphviz.Digraph('LangGraphFlow', format='png')
    dot.attr(rankdir='LR')

    # add nodes
    for n in flow_def.get('nodes', []):
        nid = n.get('id')
        label = n.get('label') or nid
        dot.node(nid, label)

    # add edges
    for e in flow_def.get('edges', []):
        frm = e.get('from')
        to = e.get('to')
        cond = e.get('condition')
        if cond:
            dot.edge(frm, to, label=cond)
        else:
            dot.edge(frm, to)

    # write dot source and render to png
    dot_path = BASE / 'langgraph_flow.dot'
    png_path = BASE / 'langgraph_flow.png'
    dot.save(str(dot_path))
    try:
        dot.render(filename=str(png_path.with_suffix('')), cleanup=True)
        print('Rendered', png_path)
    except Exception as e:
        print('Failed to render PNG (graphviz system binary may be missing):', e)
        print('DOT file written to', dot_path)


def main():
    flow_def = load_flow_def()
    render_with_graphviz(flow_def)


if __name__ == '__main__':
    main()
