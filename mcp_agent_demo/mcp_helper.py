import json
import asyncio
from typing import Any, Dict
from dotenv import load_dotenv
import os

# Load .env before importing servicenow_mcp so environment variables
# (like TOOL_PACKAGE_CONFIG_PATH / MCP_TOOL_PACKAGE) are available
load_dotenv()

from servicenow_mcp.server import ServiceNowMCP
from servicenow_mcp.utils.config import (
    ServerConfig,
    AuthConfig,
    BasicAuthConfig,
    AuthType,
)


def build_server_config_from_env() -> ServerConfig:
    instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
    if not instance_url:
        raise RuntimeError("Please set SERVICENOW_INSTANCE_URL in .env")

    auth_type = os.getenv("SERVICENOW_AUTH_TYPE", "basic").lower()

    if auth_type == "basic":
        username = os.getenv("SERVICENOW_USERNAME")
        password = os.getenv("SERVICENOW_PASSWORD")
        if not username or not password:
            raise RuntimeError("Set SERVICENOW_USERNAME and SERVICENOW_PASSWORD in .env for basic auth")
        auth = AuthConfig(type=AuthType.BASIC, basic=BasicAuthConfig(username=username, password=password))
    else:
        raise RuntimeError(f"Auth type '{auth_type}' not implemented in this demo. Use 'basic'.")

    return ServerConfig(instance_url=instance_url, auth=auth, debug=True)


def create_mcp() -> ServiceNowMCP:
    config = build_server_config_from_env()
    mcp = ServiceNowMCP(config)
    return mcp


async def list_tools(mcp: ServiceNowMCP):
    # returns list of types.Tool objects
    return await mcp._list_tools_impl()


def sample_value_for_property(prop_schema: Dict[str, Any], name: str):
    t = prop_schema.get("type")
    if not t:
        return "sample"
    if isinstance(t, list):
        t = t[0]
    if t == "string":
        # Infer common fields
        if "short_description" in name or "summary" in name:
            return "Demo: VPN outage"
        if "description" in name:
            return "User cannot reach corporate VPN. Investigate and restore connectivity."
        if "caller" in name or "caller_id" in name or "user" in name:
            return "alice@example.com"
        return "sample"
    if t == "integer":
        return 3
    if t == "boolean":
        return True
    if t == "array":
        return []
    if t == "object":
        return {}
    return "sample"


def build_params_from_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    props = schema.get("properties", {})
    required = schema.get("required", [])
    params = {}
    for name in required:
        prop_schema = props.get(name, {})
        params[name] = sample_value_for_property(prop_schema, name)
    # also fill common optional fields if present
    for common in ["short_description", "description", "caller", "caller_id"]:
        if common in props and common not in params:
            params[common] = sample_value_for_property(props.get(common, {}), common)
    return params


def call_tool_sync(mcp: ServiceNowMCP, tool_name: str, arguments: Dict[str, Any]):
    # _call_tool_impl is async; run it via asyncio
    async def _call():
        return await mcp._call_tool_impl(tool_name, arguments)

    return asyncio.run(_call())
