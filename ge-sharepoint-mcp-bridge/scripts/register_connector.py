# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He
"""Creates the Gemini Enterprise app, binds the egress Agent Gateway, and
registers the MCP server as a private custom_mcp connector.

The Terraform provider doesn't cover these Discovery Engine settings yet.
Order matters: a connector with Agent Gateway egress can only be linked to an
app that already has a default egress gateway.

Entra credentials are read from Secret Manager in memory; nothing is printed.
The tool catalog (names, descriptions, read-only flags) comes straight from the
server code, so it can't drift from what Cloud Run actually serves.

    uv run python scripts/register_connector.py \
      --project-id "$PROJECT_ID" \
      --mcp-server-url "$(terraform -chdir=terraform output -raw mcp_server_url)" \
      --agent-gateway  "$(terraform -chdir=terraform output -raw agent_gateway)"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys

import httpx

from sharepoint_mcp_bridge.server import mcp

SCOPES = (
    "https://graph.microsoft.com/Files.ReadWrite.All "
    "https://graph.microsoft.com/Sites.ReadWrite.All offline_access"
)


def gcloud(*args: str) -> str:
    return subprocess.run(["gcloud", *args], capture_output=True, text=True, check=True).stdout.strip()


def secret(project: str, name: str) -> str:
    return gcloud("secrets", "versions", "access", "latest", f"--secret={name}", f"--project={project}")


def call(method: str, url: str, token: str, project: str, **kw) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}", "X-Goog-User-Project": project}
    resp = httpx.request(method, url, headers=headers, timeout=120.0, **kw)
    if resp.status_code >= 400 and not (method == "GET" and resp.status_code == 404):
        sys.exit(f"[ERROR] {method} {url} -> HTTP {resp.status_code}: {resp.text}")
    return resp


def tool_catalog() -> list[dict]:
    tools = asyncio.run(mcp.list_tools())
    return [
        {
            "name": t.name,
            "description": " ".join((t.description or "").split("\n\n")[0].split()),
            "readonly": bool(t.annotations and t.annotations.read_only_hint),
        }
        for t in tools
    ]


def api(location: str) -> str:
    host = "discoveryengine.googleapis.com" if location == "global" else f"{location}-discoveryengine.googleapis.com"
    return f"https://{host}/v1alpha"


def ensure_app(project: str, location: str, app_id: str, gateway: str, token: str) -> None:
    base = (
        f"{api(location)}/projects/{project}"
        f"/locations/{location}/collections/default_collection/engines"
    )
    if call("GET", f"{base}/{app_id}", token, project).status_code == 404:
        call("POST", base, token, project, params={"engineId": app_id}, json={
            "displayName": app_id,
            "solutionType": "SOLUTION_TYPE_SEARCH",
            "industryVertical": "GENERIC",
            "appType": "APP_TYPE_INTRANET",
            "searchEngineConfig": {
                "searchTier": "SEARCH_TIER_ENTERPRISE",
                "searchAddOns": ["SEARCH_ADD_ON_LLM"],
            },
        })
        print(f"Created Gemini Enterprise app {app_id}")
    call("PATCH", f"{base}/{app_id}", token, project,
         params={"updateMask": "agentGatewaySetting.defaultEgressAgentGateway"},
         json={"agentGatewaySetting": {"defaultEgressAgentGateway": {"name": gateway}}})
    print(f"Bound egress gateway to {app_id}")


def connector_payload(args: argparse.Namespace, tools: list[dict], creds: dict[str, str]) -> dict:
    tenant = creds["tenant-id"]
    names = [t["name"] for t in tools]
    return {
        "name": f"projects/{args.project_id}/locations/{args.location}/collections/{args.connector_id}/dataConnector",
        "dataSource": "custom_mcp",
        "dataSourceVersion": 1,
        # Must be a non-empty placeholder; the real token comes from the user's OAuth sign-in.
        "params": {"oauth_access_token": "unused"},
        "refreshInterval": "86400s",
        "entities": [{"entityName": "mcp_data"}],
        "actionConfig": {
            "actionParams": {
                # Keep the canonical *.run.app URL: it's what makes Gemini Enterprise
                # attach a Google ID token, so Cloud Run can keep IAM enforcement on.
                "instance_uri": args.mcp_server_url,
                "auth_type": "OAUTH",
                "auth_key": "OAuth",
                "auth_uri": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
                # Query parameters go here, not in auth_uri.
                "auth_uri_params": "&prompt=consent",
                "token_uri": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                "client_id": creds["client-id"],
                "client_secret": creds["client-secret"],
                "scopes": SCOPES,
                "pkce_support_enabled": False,
                "client_secret_basic_override": False,
                "use_agent_gateway_egress": True,
                "agent_gateway_engine": (
                    f"projects/{args.project_id}/locations/{args.location}"
                    f"/collections/default_collection/engines/{args.app_id}"
                ),
                "mcp_server_description": (
                    "Microsoft SharePoint Online and OneDrive: search, read, compare, "
                    "draft, edit, organise and share documents and lists as the signed-in user."
                ),
                "mcp_agent_instructions": (
                    "Use these tools whenever the user asks about files, folders, lists or "
                    "sharing in SharePoint or OneDrive. Pass drive='onedrive' or 'sharepoint' "
                    "and the file name; the server resolves IDs. Prefer one call with all "
                    "edits over several calls. Tools: " + ", ".join(names)
                ),
            },
            "createBapConnection": True,
            "isActionConfigured": True,
        },
        "bapConfig": {"enabledActions": names},
        "dynamicTools": [
            {"name": t["name"], "displayName": t["name"], "description": t["description"], "enabled": True}
            for t in tools
        ],
        # Read-only tools run without a click; anything that writes asks the user first.
        "connectorTools": [
            {"toolName": t["name"], "toolPermission": "TOOL_PERMISSION_ALLOW" if t["readonly"] else "TOOL_PERMISSION_ASK"}
            for t in tools
        ],
        "connectorType": "THIRD_PARTY_FEDERATED",
        "connectorModes": ["FEDERATED"],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project-id", required=True)
    p.add_argument("--mcp-server-url", required=True, help="Terraform output mcp_server_url")
    p.add_argument("--agent-gateway", required=True, help="Terraform output agent_gateway")
    p.add_argument("--location", default="global", choices=["global", "us", "eu"])
    p.add_argument("--app-id", default="spmcp-app")
    p.add_argument("--connector-id", default="spmcp-sharepoint",
                   help="If a run fails after the data store was created, the ID stays reserved for a few hours; pick a new one.")
    p.add_argument("--secret-prefix", default="spmcp", help="Terraform var.prefix")
    p.add_argument("--dry-run", action="store_true", help="Print the payload (secret redacted) and stop.")
    args = p.parse_args()

    tools = tool_catalog()
    creds = {k: secret(args.project_id, f"{args.secret_prefix}-entra-{k}") for k in ("client-id", "client-secret", "tenant-id")}
    payload = connector_payload(args, tools, creds)

    if args.dry_run:
        payload["actionConfig"]["actionParams"]["client_secret"] = "***"
        print(json.dumps(payload, indent=2))
        return

    token = gcloud("auth", "print-access-token")
    ensure_app(args.project_id, args.location, args.app_id, args.agent_gateway, token)

    resp = call(
        "POST", f"{api(args.location)}/projects/{args.project_id}/locations/{args.location}:setUpDataConnectorV2",
        token, args.project_id,
        params={"collectionId": args.connector_id, "collectionDisplayName": "SharePoint & OneDrive (private MCP)"},
        json=payload,
    )
    print(f"Connector {args.connector_id} registered with {len(tools)} tools "
          f"({sum(t['readonly'] for t in tools)} read-only).")
    print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    main()
