"""Set `u_auto_resolve` = true and append the marker comment for the 4 selected incidents.

This patches only the four incidents we agreed to target. It does not modify other incidents.
Writes `set_flag_results.json` with the patch responses.
"""
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import os
import json


INCIDENTS = [
    {"number": "INC0010042", "sys_id": "f511151cc3e132102878f8cc05013194"},
    {"number": "INC0010043", "sys_id": "a211591cc3e132102878f8cc050131c9"},
    {"number": "INC0010049", "sys_id": "78315d1cc3e132102878f8cc05013150"},
    {"number": "INC0010050", "sys_id": "a9319d1cc3e132102878f8cc0501312a"},
]

MARKER = 'Resolved via MCP automation'

# You may set AUTO_RESOLVE_CALLED_ID in .env to control the called_id value that
# is written to each incident (defaults to 'MCP Automation')



def load_env():
    load_dotenv(Path(__file__).parent / '.env')
    inst = os.getenv('SERVICENOW_INSTANCE_URL')
    user = os.getenv('SERVICENOW_USERNAME')
    pwd = os.getenv('SERVICENOW_PASSWORD')
    if not inst or not user or not pwd:
        raise RuntimeError('Set credentials in .env')
    return inst.rstrip('/'), user, pwd


def main():
    instance, user, pwd = load_env()
    auth = HTTPBasicAuth(user, pwd)
    results = []
    # called_id can be set via .env as AUTO_RESOLVE_CALLED_ID, otherwise default
    called_id_value = os.getenv('AUTO_RESOLVE_CALLED_ID', 'MCP Automation')

    for inc in INCIDENTS:
        sys_id = inc['sys_id']
        num = inc['number']
        url = f"{instance}/api/now/table/incident/{sys_id}"
        # patch: set flag true, set called_id and append marker comment
        # Use the called_id value from env (or default)
        payload = {
            'u_auto_resolve': True,
            'called_id': called_id_value,
            'comments': MARKER + '\nCalled ID: ' + called_id_value,
        }
        try:
            r = requests.patch(url, json=payload, auth=auth)
            r.raise_for_status()
            results.append({'number': num, 'sys_id': sys_id, 'patched': True})
            print('Patched', num)
        except Exception as e:
            results.append({'number': num, 'sys_id': sys_id, 'patched': False, 'error': str(e)})
            print('Failed to patch', num, e)

    Path(__file__).parent.joinpath('set_flag_results.json').write_text(json.dumps(results, indent=2))
    print('Done. Results saved to set_flag_results.json')


if __name__ == '__main__':
    main()
