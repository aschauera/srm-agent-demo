"""Read-only hosted MCP contract and SUP-012 smoke test; SRM-OPS-001/GOV-001."""

import argparse
import asyncio
import json
from pathlib import Path

import httpx2
from azure.identity import AzureCliCredential
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

UI_URI = "ui://srm/supplier-risk-dashboard.html"


async def verify(state: dict, result_path: Path | None, expected_ui: Path | None = None) -> None:
    url = state["endpoint"]
    if url != "https://srm-risk-mcp.wittyglacier-6d770dc4.westeurope.azurecontainerapps.io/mcp":
        raise ValueError("Refusing an endpoint outside the approved SRM deployment.")
    with AzureCliCredential(tenant_id=state["tenantId"]) as credential:
        token = credential.get_token(f"api://{state['apiAppId']}/.default").token
    async with httpx2.AsyncClient(timeout=120) as anonymous:
        response = await anonymous.get(url)
        if response.status_code != 401:
            raise RuntimeError("Unauthenticated MCP request was not rejected.")
        response = await anonymous.get(url, headers={"Authorization": "Bearer invalid-token"})
        if response.status_code != 401:
            raise RuntimeError("Invalid bearer token was not rejected.")
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=120) as http:
        async with streamable_http_client(url, http_client=http) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = await client.list_tools()
                if len(tools.tools) != 1 or tools.tools[0].name != "get_supplier_risk_dashboard":
                    raise RuntimeError("Unexpected MCP tool inventory.")
                tool = tools.tools[0]
                if tool.meta["ui"]["resourceUri"] != UI_URI or not tool.annotations.read_only_hint:
                    raise RuntimeError("Tool UI metadata or read-only annotation is missing.")
                result = await client.call_tool(tool.name, {
                    "supplier_code": "SUP-012", "request_ref": "REQ-2026-012"})
                if result.is_error or result.structured_content is None:
                    raise RuntimeError(f"Hosted dashboard read failed: {result.content}")
                data = result.structured_content
                if (data["supplier"]["code"] != "SUP-012" or
                    data["supplier"]["name"] != "Lumen Forge Industrial Systems Ltd" or
                    data["review"]["ref"] != "REQ-2026-012" or len(data["financials"]) < 4):
                    raise RuntimeError("Hosted dashboard did not return the expected supplier/review/periods.")
                if not data["review"]["confirmed"] and data["review"]["finalRating"] != "Not rated":
                    raise RuntimeError("Unapproved request was presented as a final rating.")
                resource = await client.read_resource(UI_URI)
                if resource.contents[0].mime_type != "text/html;profile=mcp-app":
                    raise RuntimeError("MCP App MIME type is incorrect.")
                if len(resource.contents[0].text) < 1000:
                    raise RuntimeError("MCP App HTML is incomplete.")
                if resource.contents[0].meta["ui"]["csp"]["connectDomains"] != []:
                    raise RuntimeError("The widget unexpectedly declares direct network access.")
                if expected_ui and resource.contents[0].text != expected_ui.read_text(encoding="utf-8"):
                    raise RuntimeError("The hosted MCP App HTML differs from the locally tested production artifact.")
                if result_path:
                    result_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                print(json.dumps({
                    "endpoint": url, "supplier": data["supplier"]["name"],
                    "request": data["review"]["ref"], "masterRating": data["supplier"]["masterRating"],
                    "preliminaryRating": data["review"]["preliminaryRating"],
                    "finalRating": data["review"]["finalRating"], "confirmed": data["review"]["confirmed"],
                    "cofaceCurrent": data["coface"]["current"], "financialPeriods": len(data["financials"]),
                    "sensitiveVisible": data["sensitiveVisible"],
                    "uiResourceBytes": len(resource.contents[0].text.encode("utf-8")),
                    "uiMatchesTestedArtifact": True if expected_ui else None,
                    "unauthenticatedRequestsRejected": True,
                }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment-state", type=Path, required=True)
    parser.add_argument("--result-path", type=Path)
    parser.add_argument("--expected-ui", type=Path, help="Require the hosted HTML to match the tested local artifact.")
    args = parser.parse_args()
    asyncio.run(verify(json.loads(args.deployment_state.read_text(encoding="utf-8-sig")),
                      args.result_path, args.expected_ui))
