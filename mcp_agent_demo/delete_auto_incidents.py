"""Find and delete incidents whose short_description starts with "Auto-generated incident".

The script queries ServiceNow for incidents with short_description STARTSWITH 'Auto-generated incident'
and deletes each found incident via the REST API. Results are written to
`mcp_agent_demo/deleted_auto_incidents.json`.

Use with caution: deletion is permanent depending on your instance configuration.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import quote_plus


def load_env():
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    instance = os.getenv('SERVICENOW_INSTANCE_URL')
    user = os.getenv('SERVICENOW_USERNAME')
    pwd = os.getenv('SERVICENOW_PASSWORD')
    if not instance or not user or not pwd:
        raise RuntimeError('Please set SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, SERVICENOW_PASSWORD in the .env file')
    return instance.rstrip('/'), user, pwd


def find_auto_incidents(instance_url: str, auth: HTTPBasicAuth):
    # Use STARTSWITH operator to find incidents whose short_description starts with 'Auto-generated incident'
    q = "short_descriptionSTARTSWITHAuto-generated incident"
    url = f"{instance_url}/api/now/table/incident?sysparm_query={quote_plus(q)}&sysparm_fields=sys_id,number,short_description"
    r = requests.get(url, auth=auth, headers={'Accept': 'application/json'})
    r.raise_for_status()
    data = r.json()
    return data.get('result', [])


def delete_incident(instance_url: str, auth: HTTPBasicAuth, sys_id: str):
    url = f"{instance_url}/api/now/table/incident/{sys_id}"
    r = requests.delete(url, auth=auth)
    return r.status_code, r.text


def main():
    instance, user, pwd = load_env()
    auth = HTTPBasicAuth(user, pwd)

    print("Querying for incidents with short_description starting 'Auto-generated incident'...")
    incidents = find_auto_incidents(instance, auth)
    print(f"Found {len(incidents)} incidents to delete.")

    results = []
    for inc in incidents:
        sys_id = inc.get('sys_id')
        number = inc.get('number')
        short = inc.get('short_description')
        print(f"Deleting {number} ({sys_id}) - {short}")
        code, text = delete_incident(instance, auth, sys_id)
        success = 200 <= code < 300
        results.append({'sys_id': sys_id, 'number': number, 'short_description': short, 'status_code': code, 'deleted': success, 'response': text})

    out_path = Path(__file__).parent / 'deleted_auto_incidents.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    print(f"Done. Results written to {out_path}")


if __name__ == '__main__':
    main()
