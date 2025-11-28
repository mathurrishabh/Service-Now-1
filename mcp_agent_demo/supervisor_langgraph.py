"""Supervisor Agent using LangGraph (fallback if langgraph not installed).

Flow description (logical):
Input -> SearchKB(Node) -> Decision(Node)
Decision: if any past ticket resolved -> ReturnKB(Node)
          else -> CreateTicket(Node)

This script prints the flow (attempts to use langgraph to construct a flow if available),
then executes the flow for a sample query. It uses local KB export (`kb_articles_export.json`)
as the knowledge source and falls back to ServiceNow REST to create incidents when needed.

Usage:
  python -u mcp_agent_demo\supervisor_langgraph.py "<user question or short description>"

Note: If you want the script to actually call ServiceNow to create tickets, ensure
`mcp_agent_demo/.env` contains `SERVICENOW_INSTANCE_URL`, `SERVICENOW_USERNAME`, `SERVICENOW_PASSWORD`.
"""
import sys
from pathlib import Path
import json
import os
from requests.auth import HTTPBasicAuth
import requests
from dotenv import load_dotenv


BASE = Path(__file__).parent


def load_env():
    load_dotenv(BASE / '.env')
    inst = os.getenv('SERVICENOW_INSTANCE_URL')
    user = os.getenv('SERVICENOW_USERNAME')
    pwd = os.getenv('SERVICENOW_PASSWORD')
    return inst.rstrip('/') if inst else None, user, pwd


def build_and_print_flow():
    # Build a serializable flow description and attempt to instantiate a langgraph.Flow
    flow_def = {
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

    # Try building a langgraph.Flow object if the package is available
    try:
        import langgraph as lg
        flow = lg.Flow()
        nodes = {}
        for n in flow_def['nodes']:
            nodes[n['id']] = flow.add_node(n['label'])
        for e in flow_def['edges']:
            cond = e.get('condition')
            if cond:
                flow.add_edge(nodes[e['from']], nodes[e['to']], condition=cond)
            else:
                flow.add_edge(nodes[e['from']], nodes[e['to']])
        print('LangGraph flow built (langgraph package detected):')
        print(flow)
    except Exception:
        # Fallback ASCII print and export flow JSON for LangGraph UI/import
        print('\nSupervisor Flow (fallback):')
        print('  [User Input]')
        print('        |')
        print('   [SearchKB Node]')
        print('        |')
        print('     [Decision]')
        print("       /   \\")
        print('  resolved   no match')
        print('    |           |')
        print(' [ReturnKB]  [CreateTicket]\n')
        # write a JSON flow definition so it can be imported into LangGraph or visualized
        try:
            Path(__file__).parent.joinpath('langgraph_flow.json').write_text(json.dumps(flow_def, indent=2))
            print('Wrote langgraph_flow.json (importable flow description)')
        except Exception:
            pass


def load_local_kb_index():
    kbfile = BASE / 'kb_articles_export.json'
    if not kbfile.exists():
        return []
    try:
        return json.loads(kbfile.read_text())
    except Exception:
        return []


def semantic_match(query: str, kb_entries: list, threshold: float = 0.25):
    """Very simple matching: check if any keyword from the query appears in article text.
    Returns list of matched kb entries (may be empty).
    """
    q = query.lower()
    tokens = [t for t in q.split() if len(t) > 3]
    matches = []
    for e in kb_entries:
        art = e.get('article') or {}
        text = (art.get('text') or '') + ' ' + (art.get('short_description') or '')
        text_l = text.lower()
        score = 0
        for t in tokens:
            if t in text_l:
                score += 1
        if tokens:
            score_norm = score / len(tokens)
        else:
            score_norm = 0
        if score_norm >= threshold:
            matches.append({'entry': e, 'score': score_norm})
    # sort by score descending
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches


def create_incident_rest(short_desc: str, description: str):
    instance, user, pwd = load_env()
    if not instance or not user or not pwd:
        raise RuntimeError('ServiceNow credentials not set in .env')
    url = f"{instance}/api/now/table/incident"
    auth = HTTPBasicAuth(user, pwd)
    payload = {
        'short_description': short_desc,
        'description': description
    }
    r = requests.post(url, json=payload, auth=auth)
    r.raise_for_status()
    return r.json().get('result', {})


def supervisor_decide_and_act(query: str, create_ticket_if_missing: bool = True):
    # 1. Build/print flow
    build_and_print_flow()

    # 2. Ask the Knowledge-Base Agent to search for matches
    import kb_agent
    print('Invoking Knowledge-Base Agent...')
    kb_matches = kb_agent.search_kb(query, top_k=3)
    print(f'KB Agent returned {len(kb_matches)} matches')
    if kb_matches:
        best = kb_matches[0]
        print('\nDecision: KB match found -> Return KB resolution')
        return {
            'action': 'return_kb',
            'incident_number': best.get('incident_number'),
            'article_sys_id': best.get('article_sys_id'),
            'title': best.get('title'),
            'body': best.get('body'),
            'score': best.get('score'),
        }

    # 3. No KB match -> call ServiceNow Agent to create an incident (unless dry-run)
    print('\nDecision: No KB match; will call ServiceNow Agent to create ticket' if create_ticket_if_missing else '\nDecision: No KB match; dry-run (no create)')
    if not create_ticket_if_missing:
        return {'action': 'no_action'}

    try:
        import servicenow_agent
        created = servicenow_agent.create_incident(short_description=query, description=query)
        return {'action': 'create_ticket', 'created': created}
    except Exception as e:
        return {'action': 'create_ticket_failed', 'error': str(e)}


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Supervisor Agent (LangGraph flow + decision)')
    parser.add_argument('query', nargs='?', help='User query or short description')
    parser.add_argument('--no-create', action='store_true', help="Don't create tickets; return no_action or create_ticket_failed instead")
    parser.add_argument('--show-flow-only', action='store_true', help='Only show the LangGraph flow and exit')
    args = parser.parse_args()

    if args.show_flow_only:
        build_and_print_flow()
        return

    if not args.query:
        print('Usage: python -u mcp_agent_demo\\supervisor_langgraph.py "<user question>"')
        return

    query = args.query
    print('Supervisor received query:', query)
    res = supervisor_decide_and_act(query, create_ticket_if_missing=(not args.no_create))
    print('\nResult:')
    print(json.dumps(res, indent=2))


if __name__ == '__main__':
    main()
