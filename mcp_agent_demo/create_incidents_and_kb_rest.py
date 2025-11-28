"""Create 10 incidents via ServiceNow REST API, resolve 4 with comments, create KB articles, and append index.

This script uses only REST API calls (no MCP) to avoid tool gating.
Requires `.env` with `SERVICENOW_INSTANCE_URL`, `SERVICENOW_USERNAME`, `SERVICENOW_PASSWORD`.
Outputs:
- `created_incidents_rest.json`
- `created_kb_articles_rest.json`
"""
import json
import random
import time
from pathlib import Path
from typing import List

import requests
from requests.auth import HTTPBasicAuth

from dotenv import load_dotenv
import os


SAMPLE_DESCRIPTIONS = [
    "Demo: VPN Outage - users cannot connect to corporate VPN",
    "Demo: Oracle Database is not available - connection timeout errors",
    "Demo: Email delivery failures for sales@example.com domain",
    "Demo: Slow response time on the reporting dashboard",
    "Demo: Unable to mount NFS share on app servers",
    "Demo: Authentication failures for SSO login",
    "Demo: High CPU usage on database server db-prod-01",
    "Demo: Printer queue is failing for Finance department",
    "Demo: Certificate expired on web-gateway.example.com",
    "Demo: Backup job failed for application backups",
]

RESOLUTION_TEMPLATES = [
    [
        "Restarted the affected service on the host.",
        "Cleared the corrupted cache.",
        "Verified connectivity and monitoring alerts are green.",
    ],
    [
        "Applied the missing configuration patch.",
        "Validated configuration syntax and reloaded the service.",
        "Confirmed functionality with a smoke test.",
    ],
    [
        "Removed stale session data from the database.",
        "Reindexed the search service.",
        "Confirmed successful searches and closed the incident.",
    ],
    [
        "Rolled back the last deployment causing the regression.",
        "Monitored for recurrence for 30 minutes.",
        "Created a follow-up change request to fix root cause.",
    ],
]


def load_env():
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    instance = os.getenv('SERVICENOW_INSTANCE_URL')
    user = os.getenv('SERVICENOW_USERNAME')
    pwd = os.getenv('SERVICENOW_PASSWORD')
    if not instance or not user or not pwd:
        raise RuntimeError('Please set SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, SERVICENOW_PASSWORD in the .env file')
    return instance.rstrip('/'), user, pwd


def create_incident(instance: str, auth: HTTPBasicAuth, short: str, desc: str, state: int = 1) -> dict:
    url = f"{instance}/api/now/table/incident"
    payload = {
        'short_description': short,
        'description': desc,
    }
    # create incident
    r = requests.post(url, json=payload, auth=auth)
    r.raise_for_status()
    res = r.json().get('result', {})

    # optionally set state; try but don't fail the whole creation on patch error
    if state != 1:
        sys_id = res.get('sys_id')
        if sys_id:
            try:
                patch = requests.patch(f"{url}/{sys_id}", json={'state': str(state)}, auth=auth)
                patch.raise_for_status()
                res = patch.json().get('result', res)
            except Exception as e:
                # Log but return the created record; caller may attempt later updates
                print(f"Warning: failed to set state for {sys_id}: {e}")

    return res


def ensure_kb(instance: str, auth: HTTPBasicAuth, kb_name: str) -> str:
    url = f"{instance}/api/now/table/kb_knowledge_base"
    params = {'sysparm_query': f"name={kb_name}", 'sysparm_limit': 1}
    r = requests.get(url, params=params, auth=auth)
    r.raise_for_status()
    res = r.json().get('result', [])
    if res:
        return res[0]['sys_id']

    payload = {'name': kb_name, 'description': 'Auto-created KB for incident resolutions'}
    r = requests.post(url, json=payload, auth=auth)
    r.raise_for_status()
    return r.json()['result']['sys_id']


def create_kb_article(instance: str, auth: HTTPBasicAuth, kb_sys_id: str, title: str, body: str) -> dict:
    url = f"{instance}/api/now/table/kb_knowledge"
    payload = {
        'short_description': title,
        'text': body,
        'kb_knowledge_base': kb_sys_id,
        'workflow_state': 'published'
    }
    r = requests.post(url, json=payload, auth=auth)
    r.raise_for_status()
    return r.json().get('result', {})


def append_to_index_article(instance: str, auth: HTTPBasicAuth, kb_sys_id: str, entry: str):
    url = f"{instance}/api/now/table/kb_knowledge"
    params = {'sysparm_query': f"short_description=Auto Resolutions Index^kb_knowledge_base={kb_sys_id}", 'sysparm_limit': 1}
    r = requests.get(url, params=params, auth=auth)
    r.raise_for_status()
    res = r.json().get('result', [])
    if res:
        art = res[0]
        sys_id = art['sys_id']
        current = art.get('text') or ''
        new_body = current + '\n\n' + entry
        patch = requests.patch(f"{url}/{sys_id}", json={'text': new_body}, auth=auth)
        patch.raise_for_status()
        return patch.json().get('result', {})
    else:
        body = 'Index of auto-generated resolutions:\n\n' + entry
        return create_kb_article(instance, auth, kb_sys_id, 'Auto Resolutions Index', body)


def main():
    instance, user, pwd = load_env()
    auth = HTTPBasicAuth(user, pwd)

    # prepare 10 incidents with random statuses; ensure exactly 4 resolved
    indices = list(range(10))
    resolved_indices = set(random.sample(indices, 4))

    created = []
    for i in indices:
        short = SAMPLE_DESCRIPTIONS[i % len(SAMPLE_DESCRIPTIONS)]
        desc = f"{short} - created by automation"
        state = 6 if i in resolved_indices else random.choice([1,2,3,4,7])
        print(f"Creating incident {i+1}: {short} (initial state {state})")
        try:
            res = create_incident(instance, auth, short, desc, state=state)
            created.append(res)
        except Exception as e:
            print('Failed to create incident', e)
        time.sleep(0.2)

    # For resolved incidents, ensure comments with steps and create KB articles
    kb_sys_id = ensure_kb(instance, auth, 'Auto Resolutions KB')
    print('Using KB sys_id:', kb_sys_id)

    created_kb = []
    for i in sorted(resolved_indices):
        inc = created[i]
        sys_id = inc.get('sys_id')
        number = inc.get('number')
        short = inc.get('short_description') or f'Incident {i+1}'
        steps = random.choice(RESOLUTION_TEMPLATES)
        steps_text = '\n'.join([f"{j+1}. {s}" for j, s in enumerate(steps)])

        # Add visible comment and ensure state=6 and close_notes
        patch_url = f"{instance}/api/now/table/incident/{sys_id}"
        patch_payload = {
            'comments': 'Resolution steps:\n' + steps_text,
            'state': '6',
            'close_notes': 'Resolved via automation: ' + '; '.join(steps[:2])
        }
        try:
            r = requests.patch(patch_url, json=patch_payload, auth=auth)
            r.raise_for_status()
            print(f'Patched incident {number} -> Resolved and added comment')
        except Exception as e:
            print('Failed to patch incident', number, e)

        # create KB article
        title = f"Resolution: {number} - {short[:60]}"
        body = f"Incident: {number}\n\nResolution steps:\n" + '\n'.join([f"- {s}" for s in steps])
        try:
            art = create_kb_article(instance, auth, kb_sys_id, title, body)
            created_kb.append({'incident_number': number, 'article_sys_id': art.get('sys_id')})
            print('Created KB article for', number)
        except Exception as e:
            print('Failed to create KB article for', number, e)

        # append to index
        entry = f"{number}: {title} - article {art.get('sys_id') if 'art' in locals() else 'unknown'}"
        try:
            append_to_index_article(instance, auth, kb_sys_id, entry)
        except Exception as e:
            print('Failed to append to index article', e)

    # Save outputs
    base = Path(__file__).parent
    base.joinpath('created_incidents_rest.json').write_text(json.dumps(created, indent=2))
    base.joinpath('created_kb_articles_rest.json').write_text(json.dumps(created_kb, indent=2))

    print('Done. Created incidents and KB articles (where possible).')


if __name__ == '__main__':
    main()
