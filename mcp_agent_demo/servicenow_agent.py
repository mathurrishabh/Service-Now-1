"""ServiceNow Agent (wrapper for creating incidents)

Provides a single function `create_incident(short_description, description)` that
calls the ServiceNow table API. Keep this separate so Supervisor can call it.
"""
from pathlib import Path
import os
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
import requests


BASE = Path(__file__).parent


def load_env():
    load_dotenv(BASE / '.env')
    inst = os.getenv('SERVICENOW_INSTANCE_URL')
    user = os.getenv('SERVICENOW_USERNAME')
    pwd = os.getenv('SERVICENOW_PASSWORD')
    return inst.rstrip('/') if inst else None, user, pwd


def create_incident(short_description: str, description: str) -> dict:
    instance, user, pwd = load_env()
    if not instance or not user or not pwd:
        raise RuntimeError('ServiceNow credentials not configured in .env')
    url = f"{instance}/api/now/table/incident"
    auth = HTTPBasicAuth(user, pwd)
    payload = {'short_description': short_description, 'description': description}
    r = requests.post(url, json=payload, auth=auth)
    r.raise_for_status()
    return r.json().get('result', {})


if __name__ == '__main__':
    print('ServiceNow Agent: call create_incident(short_description, description)')
