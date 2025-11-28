"""Pick 4 incidents from `created_incidents_rest.json`, add resolution comments,
mark them Resolved (state=6), create KB articles and append to index.

Writes `resolved_and_kb.json` with per-incident results.
"""
import json
import random
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import os


def load_env():
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    instance = os.getenv('SERVICENOW_INSTANCE_URL')
    user = os.getenv('SERVICENOW_USERNAME')
    pwd = os.getenv('SERVICENOW_PASSWORD')
    if not instance or not user or not pwd:
        raise RuntimeError('Please set SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, SERVICENOW_PASSWORD in the .env file')
    return instance.rstrip('/'), user, pwd


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
    base = Path(__file__).parent
    created_file = base / 'created_incidents_rest.json'
    if not created_file.exists():
        print('No created_incidents_rest.json found; run create_incidents_and_kb_rest.py first')
        return

    incidents = json.loads(created_file.read_text())
    # pick 4 incidents that have a sys_id
    candidates = [i for i, it in enumerate(incidents) if it.get('sys_id')]
    if len(candidates) < 4:
        print('Not enough incidents with sys_id to pick 4; found', len(candidates))
        return
    chosen = random.sample(candidates, 4)

    instance, user, pwd = load_env()
    auth = HTTPBasicAuth(user, pwd)
    kb_sys_id = ensure_kb(instance, auth, 'Auto Resolutions KB')
    print('Using KB sys_id', kb_sys_id)

    results = []
    for idx in chosen:
        inc = incidents[idx]
        sys_id = inc.get('sys_id')
        number = inc.get('number') or inc.get('task_effective_number') or f'INC_IDX_{idx}'
        short = inc.get('short_description') or 'No short description'

        # generic resolution steps
        steps = [
            'Restart the affected service or process',
            'Clear transient caches and verify connectivity',
            'Confirm monitoring alerts are cleared and close the incident'
        ]
        steps_text = '\n'.join(f"{i+1}. {s}" for i, s in enumerate(steps))

        # add comment + set state to Resolved
        patch_url = f"{instance}/api/now/table/incident/{sys_id}"
        payload = {'comments': 'Resolution steps:\n' + steps_text, 'state': '6', 'close_notes': 'Resolved by automation: ' + '; '.join(steps[:2])}
        try:
            r = requests.patch(patch_url, json=payload, auth=auth)
            r.raise_for_status()
            patch_ok = True
            print('Patched incident', number, '-> Resolved')
        except Exception as e:
            patch_ok = False
            print('Failed to patch incident', number, e)

        # create KB article
        title = f"Resolution: {number} - {short[:60]}"
        body = f"Incident: {number}\n\nResolution steps:\n" + '\n'.join([f"- {s}" for s in steps])
        try:
            art = create_kb_article(instance, auth, kb_sys_id, title, body)
            art_sys = art.get('sys_id')
            print('Created KB article', art_sys, 'for', number)
        except Exception as e:
            art_sys = None
            print('Failed to create KB article for', number, e)

        # append to index
        entry = f"{number}: {title} - article {art_sys or 'unknown'}"
        try:
            append_to_index_article(instance, auth, kb_sys_id, entry)
        except Exception as e:
            print('Failed to append index entry for', number, e)

        results.append({'incident_number': number, 'sys_id': sys_id, 'patched': patch_ok, 'article_sys_id': art_sys})

    out = base / 'resolved_and_kb.json'
    out.write_text(json.dumps(results, indent=2))
    print('Done. Results saved to', out)


if __name__ == '__main__':
    main()
