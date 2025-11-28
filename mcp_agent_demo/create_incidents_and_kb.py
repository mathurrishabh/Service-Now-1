"""Create 10 random incidents via ServiceNow MCP, resolve 4 with steps, and add KB articles.

Behavior:
- Creates 10 incidents with random short descriptions and callers.
- Selects 4 incidents to resolve. For each resolved incident:
  - Adds a comment containing step-by-step resolution steps.
  - Calls the `resolve_incident` tool to mark it resolved.
  - Ensures a Knowledge Base exists (`Auto Resolutions KB`) and creates an article with the
    incident details and resolution steps.
- Saves results to `created_incidents.json` and `created_kb_articles.json` in the demo folder.

NOTE: This script uses your ServiceNow credentials from `mcp_agent_demo/.env`.
Run from repo root with TOOL_PACKAGE_CONFIG_PATH and MCP_TOOL_PACKAGE set (see README).
"""

import json
import random
import time
from typing import Dict, Any, List

from mcp_agent_demo.mcp_helper import create_mcp, list_tools, build_params_from_schema, call_tool_sync
import asyncio


CALLER_POOL = [
    "alice@example.com",
    "bob@example.com",
    "carol@example.com",
    "dave@example.com",
    "eve@example.com",
]

RESOLUTION_STEPS_SAMPLES = [
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

SAMPLE_DESCRIPTIONS = [
    "Demo: VPN outage - users cannot connect to corporate VPN",
    "Oracle Database is not available - connection timeout errors",
    "Email delivery failures for sales@example.com domain",
    "Slow response time on the reporting dashboard",
    "Unable to mount NFS share on app servers",
    "Authentication failures for SSO login",
    "High CPU usage on database server db-prod-01",
    "Printer queue is failing for Finance department",
    "Certificate expired on web-gateway.example.com",
    "Backup job failed for application backups",
]


def find_tool_schema(tools, name: str):
    for t in tools:
        if getattr(t, "name", None) == name:
            return t.inputSchema
    return None


def pick_id_field(schema: Dict[str, Any], prefer_sys_id=True) -> str:
    # Choose a property name likely used to identify the incident.
    props = schema.get("properties", {})
    candidates = [p for p in props.keys() if any(k in p.lower() for k in ("sys_id", "id", "number", "incident"))]
    # prefer sys_id-like
    for c in candidates:
        if "sys_id" in c.lower() and prefer_sys_id:
            return c
    if candidates:
        return candidates[0]
    # fallback: maybe parameter is 'random_string' for no-arg tools
    return None


def serialize_result(result_list):
    # result_list is list of TextContent objects; return parsed JSON if possible
    outputs = []
    for item in result_list:
        txt = item.text
        try:
            outputs.append(json.loads(txt))
        except Exception:
            outputs.append(txt)
    return outputs


def main():
    print("Creating MCP instance...")
    mcp = create_mcp()

    # get enabled tools via list_tools
    tools = asyncio.run(list_tools(mcp))

    # needed tool names
    need_tools = ["create_incident", "add_comment", "resolve_incident", "create_knowledge_base", "create_article", "get_incident_by_number"]
    for nt in need_tools:
        if nt not in [t.name for t in tools]:
            print(f"Warning: tool {nt} not enabled in current package. Proceeding may fail.")

    create_inc_schema = find_tool_schema(tools, "create_incident")
    add_comment_schema = find_tool_schema(tools, "add_comment") or {}
    resolve_schema = find_tool_schema(tools, "resolve_incident") or {}
    create_kb_schema = find_tool_schema(tools, "create_knowledge_base") or {}
    create_article_schema = find_tool_schema(tools, "create_article") or {}

    created = []
    kb_articles = []

    # Create or ensure KB exists
    kb_params = build_params_from_schema(create_kb_schema) if create_kb_schema else {}
    # name the KB
    kb_params_key = None
    if create_kb_schema:
        # pick a suitable field for KB name
        props = create_kb_schema.get("properties", {})
        for key in props:
            if any(s in key.lower() for s in ("name", "title", "short")):
                kb_params_key = key
                break
    if kb_params_key:
        kb_params[kb_params_key] = "Auto Resolutions KB"

    print("Creating Knowledge Base (if not present)...")
    try:
        kb_res = call_tool_sync(mcp, "create_knowledge_base", kb_params)
        kb_out = serialize_result(kb_res)[0]
        # try to extract sys_id
        kb_sys_id = None
        if isinstance(kb_out, dict):
            kb_sys_id = kb_out.get("sys_id") or kb_out.get("id")
        print("Knowledge base created/returned:", kb_out)
    except Exception as e:
        print("Failed to create knowledge base:", e)
        kb_sys_id = None

    # choose 4 indices to be resolved
    resolved_indices = set(random.sample(range(10), 4))

    for i in range(10):
        # pick a realistic short description
        short = random.choice(SAMPLE_DESCRIPTIONS)
        caller = random.choice(CALLER_POOL)
        # build basic params
        params = build_params_from_schema(create_inc_schema) if create_inc_schema else {}
        # set common fields if available
        for f in ("short_description", "description", "caller", "caller_id", "caller_name"):
            if f in params:
                params[f] = params[f]  # keep sample
        # overwrite short_description and caller if present in schema properties
        if create_inc_schema:
            props = create_inc_schema.get("properties", {})
            if "short_description" in props:
                params["short_description"] = short
            if "description" in props:
                params["description"] = f"{short} - created by automation for testing and triage."
            # find caller field
            for cf in ("caller_id", "caller", "caller_name"):
                if cf in props:
                    params[cf] = caller
                    break

        print(f"Creating incident {i+1}/10: {short}")
        try:
            res = call_tool_sync(mcp, "create_incident", params)
            parsed = serialize_result(res)[0]
        except Exception as e:
            print("create_incident failed:", e)
            parsed = {"error": str(e)}

        incident_number = None
        incident_sys_id = None
        if isinstance(parsed, dict):
            incident_sys_id = parsed.get("incident_id") or parsed.get("sys_id") or parsed.get("id")
            incident_number = parsed.get("incident_number") or parsed.get("number")

        created.append({"index": i, "short_description": short, "caller": caller, "result": parsed})

        # if this incident should be resolved, add comment with steps and resolve
        if i in resolved_indices:
            steps = random.choice(RESOLUTION_STEPS_SAMPLES)
            comment_text = "Resolution steps:\n" + "\n".join([f"{idx+1}. {s}" for idx, s in enumerate(steps)])

            # add comment
            add_comment_params = build_params_from_schema(add_comment_schema) if add_comment_schema else {}
            # find id field in add_comment_schema
            id_field = pick_id_field(add_comment_schema or {})
            if id_field and incident_sys_id:
                add_comment_params[id_field] = incident_sys_id
            # find text field
            for k in ("comment", "text", "body", "message"):
                if add_comment_schema and k in (add_comment_schema.get("properties", {}) or {}):
                    add_comment_params[k] = comment_text
                    break
            # fallback param names
            if not any(k in add_comment_params for k in ("comment", "text", "body", "message")):
                add_comment_params["comment"] = comment_text

            print("Adding resolution comment to incident", incident_number or incident_sys_id)
            try:
                add_res = call_tool_sync(mcp, "add_comment", add_comment_params)
                add_out = serialize_result(add_res)
            except Exception as e:
                print("add_comment failed:", e)
                add_out = [{"error": str(e)}]

            # resolve incident
            resolve_params = build_params_from_schema(resolve_schema) if resolve_schema else {}
            # set id field
            id_field_res = pick_id_field(resolve_schema or {})
            if id_field_res and incident_sys_id:
                resolve_params[id_field_res] = incident_sys_id
            # some tools expect 'resolution' or 'close_notes'
            for k in ("resolution", "close_notes", "close_notes_text", "resolution_notes"):
                if resolve_schema and k in (resolve_schema.get("properties", {}) or {}):
                    resolve_params[k] = "; ".join(steps)
                    break

            print("Resolving incident", incident_number or incident_sys_id)
            try:
                res_resolve = call_tool_sync(mcp, "resolve_incident", resolve_params)
                resolve_out = serialize_result(res_resolve)
            except Exception as e:
                print("resolve_incident failed:", e)
                resolve_out = [{"error": str(e)}]

            # create knowledge base article for this incident
            article_params = build_params_from_schema(create_article_schema) if create_article_schema else {}
            # try to detect title/body fields
            props = create_article_schema.get("properties", {}) if create_article_schema else {}
            title_field = None
            body_field = None
            kb_field = None
            for key in props:
                lk = key.lower()
                if any(x in lk for x in ("title", "short_description", "name")) and not title_field:
                    title_field = key
                if any(x in lk for x in ("text", "body", "article", "content")) and not body_field:
                    body_field = key
                if any(x in lk for x in ("kb", "knowledge", "knowledge_base", "kb_sys_id")) and not kb_field:
                    kb_field = key

            if title_field:
                article_params[title_field] = f"Resolution: {incident_number or incident_sys_id} - {short}"
            if body_field:
                article_params[body_field] = f"Incident: {incident_number or incident_sys_id}\nCaller: {caller}\n\nSteps:\n" + "\n".join([f"- {s}" for s in steps])
            if kb_field and kb_sys_id:
                article_params[kb_field] = kb_sys_id

            print("Creating KB article for incident", incident_number or incident_sys_id)
            try:
                article_res = call_tool_sync(mcp, "create_article", article_params)
                art_out = serialize_result(article_res)[0]
            except Exception as e:
                print("create_article failed:", e)
                art_out = {"error": str(e)}

            kb_articles.append({"incident_number": incident_number, "incident_sys_id": incident_sys_id, "article_result": art_out})

        # small delay to avoid overwhelming API
        time.sleep(0.5)

    # save outputs
    with open("mcp_agent_demo/created_incidents.json", "w", encoding="utf-8") as f:
        json.dump(created, f, indent=2)
    with open("mcp_agent_demo/created_kb_articles.json", "w", encoding="utf-8") as f:
        json.dump(kb_articles, f, indent=2)

    print("Done. Created incidents saved to mcp_agent_demo/created_incidents.json")
    print("KB articles saved to mcp_agent_demo/created_kb_articles.json")


if __name__ == "__main__":
    main()
