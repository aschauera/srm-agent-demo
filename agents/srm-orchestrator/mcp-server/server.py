"""SRM MCP Apps server with Entra authorization and read-only Dataverse access."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import jwt
import requests
from azure.core.exceptions import HttpResponseError
from azure.identity import AzureCliCredential, ManagedIdentityCredential
from mcp.server import MCPServer
from mcp.server.apps import Apps, ResourceCsp
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse

from dashboard import DashboardError, load_dashboard

LOG = logging.getLogger("srm.mcp")
UI_URI = "ui://srm/supplier-risk-dashboard.html"
DEMO_PRE = "https://org5b55c88b.crm.dynamics.com"
ENTITY_SETS = {
    "mag_supplier": "mag_suppliers",
    "mag_financialreviewrequest": "mag_financialreviewrequests",
    "mag_financialworkingpaper": "mag_financialworkingpapers",
    "mag_cofacecreditrecord": "mag_cofacecreditrecords",
    "mag_supplieronepagesummary": "mag_supplieronepagesummaries",
    "mag_adversenewsevent": "mag_adversenewsevents",
    "mag_nonfinancialriskitem": "mag_nonfinancialriskitems",
}


class ReadOnlyDataverse:
    """Explicit GET-only Web API surface: no metadata discovery or write API."""

    def __init__(self, credential: AzureCliCredential | ManagedIdentityCredential):
        self.credential = credential
        self.records = self
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 502, 503, 504],
            allowed_methods={"GET"})))

    def __enter__(self) -> ReadOnlyDataverse:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.session.close()
        self.credential.close()

    def list(self, table: str, *, select: list[str], filter: str,
             orderby: list[str] | None = None, top: int = 100) -> list[dict[str, Any]]:
        if table not in ENTITY_SETS:
            raise DashboardError("Table is outside the read-only SRM allowlist.")
        token = self.credential.get_token(f"{DEMO_PRE}/.default").token
        params = {"$select": ",".join(select), "$filter": filter, "$top": str(top)}
        if orderby:
            params["$orderby"] = ",".join(orderby)
        response = self.session.get(
            f"{DEMO_PRE}/api/data/v9.2/{ENTITY_SETS[table]}", params=params,
            headers={
                "Authorization": f"Bearer {token}", "Accept": "application/json",
                "OData-MaxVersion": "4.0", "OData-Version": "4.0",
                "User-Agent": "srm-risk-mcp/1.0 (app=dataverse-skills/1.16.1;skill=dv-query;agent=unknown)",
                "Prefer": "odata.maxpagesize=100",
            }, timeout=(10, 45), allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise DashboardError("Dataverse returned an unexpected status; redirects are not followed.")
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("value"), list):
            raise DashboardError("Dataverse returned an invalid record collection.")
        if body.get("@odata.nextLink"):
            raise DashboardError("Dataverse returned a partial page; narrow the dashboard data.")
        return body["value"]


class EntraVerifier(TokenVerifier):
    def __init__(self, tenant: str, audience: str, resource: str):
        self.tenant = str(UUID(tenant))
        self.audience = str(UUID(audience))
        self.resource = resource
        self.issuer = f"https://login.microsoftonline.com/{self.tenant}/v2.0"
        self.keys = jwt.PyJWKClient(
            f"https://login.microsoftonline.com/{self.tenant}/discovery/v2.0/keys",
            cache_keys=True, timeout=10)

    def decode(self, token: str) -> dict[str, Any] | None:
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=self.audience,
                                issuer=self.issuer, options={"require": ["exp", "iat", "nbf", "tid", "oid"]})
        except (jwt.InvalidTokenError, jwt.PyJWKClientError) as error:
            LOG.warning("Entra token rejected (%s)", type(error).__name__)
            return None
        roles = claims.get("roles", [])
        if claims["tid"] != self.tenant or "SRM.Reader" not in roles:
            LOG.warning("Entra token rejected: tenant or SRM.Reader role missing")
            return None
        if "scp" in claims and "SRM.Read" not in claims["scp"].split():
            LOG.warning("Entra token rejected: delegated SRM.Read scope missing")
            return None
        return claims

    async def verify_token(self, token: str) -> AccessToken | None:
        claims = await asyncio.to_thread(self.decode, token)
        if claims is None:
            return None
        return AccessToken(
            token=token, client_id=claims.get("azp", claims["oid"]),
            subject=claims["oid"], expires_at=claims["exp"],
            scopes=[f"api://{self.audience}/SRM.Read"], resource=self.resource, claims=claims)


def dataverse_client() -> ReadOnlyDataverse:
    url = os.environ.get("DATAVERSE_URL", DEMO_PRE).rstrip("/")
    if url != DEMO_PRE:
        raise RuntimeError("Refusing non-DemoPRE environment.")
    identity = os.environ.get("AZURE_CLIENT_ID")
    credential = ManagedIdentityCredential(client_id=identity) if identity else AzureCliCredential(
        tenant_id=os.environ["ENTRA_TENANT_ID"])
    return ReadOnlyDataverse(credential)


def create_server(*, http: bool = True) -> MCPServer:
    resource = os.environ["MCP_PUBLIC_URL"].rstrip("/") if http else "http://127.0.0.1:8000/mcp"
    verifier = EntraVerifier(os.environ["ENTRA_TENANT_ID"], os.environ["ENTRA_API_CLIENT_ID"], resource) if http else None
    apps = Apps()
    html = (Path(__file__).parent / "dist" / "dashboard.html").read_text(encoding="utf-8")
    apps.add_html_resource(
        UI_URI, html, name="supplier-risk-dashboard", title="Supplier Risk Dashboard",
        csp=ResourceCsp(connect_domains=[], resource_domains=[], frame_domains=[]),
        prefers_border=False)

    @apps.tool(
        resource_uri=UI_URI, visibility=["model", "app"],
        name="get_supplier_risk_dashboard",
        description=(
            "Show a read-only graphical SRM risk dashboard for a fictional seeded supplier "
            "(SUP-001 through SUP-012) and an optional review reference. For Lumen Forge "
            "Industrial Systems Ltd use supplier_code SUP-012, request_ref REQ-2026-012. "
            "Loads live Dataverse supplier status, human final rating, separate AI draft rating, "
            "Coface freshness and working papers. Never approves or modifies ratings."),
        annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                    idempotent_hint=True, open_world_hint=False))
    async def get_supplier_risk_dashboard(supplier_code: str, request_ref: str | None = None) -> CallToolResult:
        token = get_access_token()
        if http and token is None:
            raise DashboardError("Authenticated caller context is required.")
        roles = (token.claims or {}).get("roles", []) if token else []
        sensitive = "SRM.LegalReader" in roles

        def read() -> dict[str, Any]:
            with dataverse_client() as client:
                return load_dashboard(client.records, supplier_code, request_ref, sensitive=sensitive)

        try:
            data = await asyncio.to_thread(read)
        except DashboardError as error:
            LOG.warning("Dashboard read rejected: %s", error)
            return CallToolResult(is_error=True, content=[TextContent(type="text", text=str(error))])
        except (HttpResponseError, requests.RequestException) as error:
            LOG.error("Dataverse read failed (%s): %s", type(error).__name__, error)
            return CallToolResult(is_error=True, content=[TextContent(
                type="text", text="Dataverse read failed. Check the managed identity's read permissions and server logs.")])
        review = data["review"]
        LOG.info("Read-only dashboard loaded; sensitive content authorized=%s", sensitive)
        summary = (
            f"{data['supplier']['name']} ({supplier_code}), {review['ref']}: "
            f"supplier master {data['supplier']['masterRating']}; "
            f"human final rating {review['finalRating'] if review['confirmed'] else 'pending'}; "
            f"AI preliminary {review['preliminaryRating']}; "
            f"stage {review['stage']}/5. Coface {data['coface']['score'] or 'unavailable'}/10 "
            f"({'current' if data['coface']['current'] else 'historical, not current'}). "
            + " ".join(data["warnings"]))
        return CallToolResult(content=[TextContent(type="text", text=summary)], structured_content=data)

    mcp = MCPServer(
        "SRM Supplier Risk Dashboard", version="1.0.0", extensions=[apps],
        instructions="Read-only fictional demo. Never treat AI drafts or supplier master ratings as human approval of a review.",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(verifier.issuer), resource_server_url=AnyHttpUrl(resource),
            required_scopes=[f"api://{verifier.audience}/SRM.Read"], validate_token_resource=True) if verifier else None)

    @mcp.custom_route("/healthz", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "srm-risk-mcp", "version": "1.0.0"})

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdio", action="store_true", help="Local process transport; sensitive detail withheld.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("azure").setLevel(logging.WARNING)
    mcp = create_server(http=not args.stdio)
    if args.stdio:
        mcp.run()
    else:
        from urllib.parse import urlsplit
        hostname = urlsplit(os.environ["MCP_PUBLIC_URL"]).hostname
        if not hostname:
            raise RuntimeError("MCP_PUBLIC_URL requires a valid hostname.")
        mcp.run(
            transport="streamable-http", host="0.0.0.0", port=8000,
            stateless_http=True, json_response=True,
            transport_security=TransportSecuritySettings(
                allowed_hosts=[hostname, f"{hostname}:443", "127.0.0.1:*", "localhost:*"],
                allowed_origins=[f"https://{hostname}"]))


if __name__ == "__main__":
    main()
