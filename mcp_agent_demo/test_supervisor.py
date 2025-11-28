"""Test runner for supervisor_langgraph.

Runs several sample queries in dry-run mode (no ticket creation) and writes
`test_results.json` with the decisions and matches.
"""
import json
from pathlib import Path
import sys
# ensure current directory is on path so we can import supervisor module directly
sys.path.insert(0, str(Path(__file__).parent))
import supervisor_langgraph as sup


QUERIES = [
    'VPN outage users cannot connect',
    'Database connection timeout errors',
    'Printer queue failing for finance',
    'New request: install software on laptop',
    'Certificate expired on web gateway',
]


def main():
    results = []
    for q in QUERIES:
        print('Running test query:', q)
        res = sup.supervisor_decide_and_act(q, create_ticket_if_missing=False)
        results.append({'query': q, 'result': res})

    Path(__file__).parent.joinpath('test_results.json').write_text(json.dumps(results, indent=2))
    print('Done. Wrote test_results.json')


if __name__ == '__main__':
    main()
