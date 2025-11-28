"""Apply resolution comments to selected incidents and create KB articles.

Targets these incidents (sys_id taken from `created_incidents_rest.json`):
- INC0010042 (f511151cc3e132102878f8cc05013194)
- INC0010043 (a211591cc3e132102878f8cc050131c9)
- INC0010049 (78315d1cc3e132102878f8cc05013150)
- INC0010050 (a9319d1cc3e132102878f8cc0501312a)

Writes:
- `applied_comments_results.json` (PATCH results)
- `created_kb_from_comments.json` (created KB article ids)

Requires `.env` in the same folder with ServiceNow credentials.
"""

import json
from pathlib import Path
from requests.auth import HTTPBasicAuth
import requests
from dotenv import load_dotenv
import os


def load_env():
    load_dotenv(Path(__file__).parent / '.env')
    instance = os.getenv('SERVICENOW_INSTANCE_URL')
    user = os.getenv('SERVICENOW_USERNAME')
    pwd = os.getenv('SERVICENOW_PASSWORD')
    if not instance or not user or not pwd:
        raise RuntimeError('Set SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, SERVICENOW_PASSWORD in .env')
    return instance.rstrip('/'), user, pwd


INCIDENTS = [
    {"number": "INC0010042", "sys_id": "f511151cc3e132102878f8cc05013194"},
    {"number": "INC0010043", "sys_id": "a211591cc3e132102878f8cc050131c9"},
    {"number": "INC0010049", "sys_id": "78315d1cc3e132102878f8cc05013150"},
    {"number": "INC0010050", "sys_id": "a9319d1cc3e132102878f8cc0501312a"},
]

COMMENTS = {
    "INC0010042": (
        "Resolution steps:\n"
        "1. Verify network/connectivity from affected clients (ping, traceroute to VPN gateway) and check gateway logs.\n"
        "2. Restart VPN service/process or fail over to standby gateway; clear stale sessions if required.\n"
        "3. Validate successful user connections, close monitoring alerts, and add close notes referencing root cause and fix."
    ),
    "INC0010043": (
        "Resolution steps:\n"
        "1. Check DB host health (CPU, memory, I/O), and DB listener/status (tnsping, listener.log).\n"
        "2. Restart database listener/service or apply the validated DB patch; clear blocked sessions and run quick integrity checks.\n"
        "3. Verify application connections, run smoke tests, document root cause and remediation steps in close notes."
    ),
    "INC0010049": (
        "Resolution steps:\n"
        "1. Inspect printer server queue and spooler service; identify stuck jobs and offending documents.\n"
        "2. Restart print spooler service and clear or reprint stuck jobs; update drivers or permissions if needed.\n"
        "3. Confirm successful print job flow from Finance, notify affected users, and document steps taken and any follow-ups."
    ),
    "INC0010050": (
        "Resolution steps:\n"
        "1. Validate the certificate chain and expiration date; identify the cert to replace and the systems depending on it.\n"
        "2. Replace or renew the certificate (update keystore/load new cert on gateway), restart the gateway service if required.\n"
        "3. Test HTTPS access from clients, update inventory/KB with new expiration, and add close notes describing renewal and verification steps."
    ),
}


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

    applied = []
    created_kb = []

    kb_sys_id = ensure_kb(instance, auth, 'Auto Resolutions KB')
    print('Using KB sys_id:', kb_sys_id)

    for inc in INCIDENTS:
        num = inc['number']
        sys_id = inc['sys_id']
        comment = COMMENTS.get(num)
        if not comment:
            print('No comment template for', num)
            continue

        patch_url = f"{instance}/api/now/table/incident/{sys_id}"
        payload = {'comments': comment}
        try:
            r = requests.patch(patch_url, json=payload, auth=auth)
            r.raise_for_status()
            applied.append({'number': num, 'sys_id': sys_id, 'patched': True})
            print('Patched comments for', num)
        except Exception as e:
            applied.append({'number': num, 'sys_id': sys_id, 'patched': False, 'error': str(e)})
            print('Failed to patch comments for', num, e)

        # create KB article from comment
        title = f"Resolution: {num} - {comment.splitlines()[1][:60]}"
        body = f"Incident: {num}\n\nFull resolution steps:\n" + '\n'.join([f"- {line.strip()}" for line in comment.splitlines()[1:]])
        try:
            art = create_kb_article(instance, auth, kb_sys_id, title, body)
            created_kb.append({'incident_number': num, 'article_sys_id': art.get('sys_id')})
            print('Created KB article for', num, art.get('sys_id'))
            # append to index
            entry = f"{num}: {title} - article {art.get('sys_id')}"
            append_to_index_article(instance, auth, kb_sys_id, entry)
        except Exception as e:
            created_kb.append({'incident_number': num, 'article_sys_id': None, 'error': str(e)})
            print('Failed to create KB article for', num, e)

    base = Path(__file__).parent
    base.joinpath('applied_comments_results.json').write_text(json.dumps(applied, indent=2))
    base.joinpath('created_kb_from_comments.json').write_text(json.dumps(created_kb, indent=2))
    print('Done. Results written to applied_comments_results.json and created_kb_from_comments.json')


if __name__ == '__main__':
    main()
