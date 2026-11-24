"""Parameterize the existing SRM MCP connector without changing resolved settings.

SRM-OPS-001, SRM-GOV-001/002; source slide 19 and the approved identifier cleanup.
Requires explicit DemoPRE authorization. Protected connection secrets are not available
through this metadata API; a connector update can require private credential re-entry.
Run with --dry-run first, then export/unpack SRMAgentDemo after successful readback.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "agents" / "srm-orchestrator" / "mcp-server" / "connector-environment-variables.json"
CONNECTOR_NAME = "mag_5Fsrm-20ui"
CONNECTOR_COMPONENT = 372


def reference(schema: str) -> str:
    return f'@environmentVariables("{schema}")'


def resolve(value, values: dict[str, str]):
    replacements = {reference(key): item for key, item in values.items()}
    if isinstance(value, dict):
        return {resolve(key, values): resolve(item, values) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, values) for item in value]
    return replacements.get(value, value) if isinstance(value, str) else value


def parameterize(api: dict, parameters: dict, current_values: dict[str, str]) -> tuple[dict, dict, dict[str, str]]:
    api, parameters = copy.deepcopy(api), copy.deepcopy(parameters)
    values = {}

    def bind(container, key, schema):
        original = container[key]
        if not isinstance(original, str) or not original:
            raise ValueError(f"Missing connector setting for {schema}.")
        if original.startswith("@environmentVariables("):
            if original != reference(schema) or not current_values.get(schema):
                raise ValueError(f"Unresolved or unexpected environment variable for {schema}.")
            value = current_values[schema]
        else:
            value = original
        if schema in values and values[schema] != value:
            raise ValueError(f"Conflicting connector settings for {schema}.")
        values[schema] = value
        container[key] = reference(schema)

    try:
        oauth = parameters["token"]["oAuthSettings"]
        if oauth["identityProvider"] not in {"oauth2", "oauth2pkce"} or len(oauth["scopes"]) != 1:
            raise ValueError("Expected an OAuth2 connector with one OAuth scope.")
        if oauth.get("clientSecret"):
            raise ValueError("A connection secret is present; refusing to copy it into configuration.")
        bind(api, "host", "mag_SRMMcpHost")
        bind(oauth, "clientId", "mag_SRMMcpOAuthClientId")
        for field, schema in [
            ("AuthorizationUrl", "mag_SRMMcpOAuthAuthorizeUrl"),
            ("TokenUrl", "mag_SRMMcpOAuthTokenUrl"),
            ("RefreshUrl", "mag_SRMMcpOAuthRefreshUrl"),
        ]:
            bind(oauth["customParameters"][field], "value", schema)
        bind(oauth["scopes"], 0, "mag_SRMMcpOAuthScope")
        security = api["securityDefinitions"]
        if ("oauth2-auth" not in security or
                not set(security) <= {"oauth2-auth", "oAuthClientCredentials"}):
            raise ValueError("Unexpected connector authentication schemes.")
        bind(security["oauth2-auth"], "authorizationUrl", "mag_SRMMcpOAuthAuthorizeUrl")
        for scheme in security.values():
            bind(scheme, "tokenUrl", "mag_SRMMcpOAuthTokenUrl")
            scopes = scheme["scopes"]
            if len(scopes) != 1:
                raise ValueError("Expected one scope per authentication scheme.")
            scope, description = next(iter(scopes.items()))
            holder = [scope]
            bind(holder, 0, "mag_SRMMcpOAuthScope")
            scheme["scopes"] = {holder[0]: holder[0] if description == scope else description}
        for requirement in api["security"]:
            for scheme, scopes in requirement.items():
                if scheme not in security or len(scopes) != 1:
                    raise ValueError("Unexpected connector security requirement.")
                bind(scopes, 0, "mag_SRMMcpOAuthScope")
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("The live connector no longer matches the expected SRM structure.") from error
    return api, parameters, values


def parameters_match(actual: dict, expected: dict) -> bool:
    actual = copy.deepcopy(actual)
    try:
        token, expected_token = actual["token"], expected["token"]
        if token["type"].lower() == expected_token["type"].lower():
            token["type"] = expected_token["type"]
        oauth, expected_oauth = token["oAuthSettings"], expected_token["oAuthSettings"]
        if "properties" not in expected_oauth and oauth.get("properties") == {
            "IsFirstParty": "False", "IsOnbehalfofLoginSupported": False,
        }:
            del oauth["properties"]
        if "redirectUrl" not in expected_oauth and "redirectUrl" in oauth:
            redirect = urlsplit(oauth["redirectUrl"])
            if (redirect.scheme == "https" and redirect.netloc == "global.consent.azure-apim.net"
                    and redirect.path.startswith("/redirect/") and not redirect.query and not redirect.fragment):
                del oauth["redirectUrl"]
    except (KeyError, TypeError, AttributeError, ValueError):
        return False
    return actual == expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--acknowledge-oauth-reconfiguration", action="store_true",
                        help="Acknowledge that updating connector metadata may require re-entering the protected OAuth secret.")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("deploy_flows", ROOT / "scripts" / "08-deploy-flows.py")
    deploy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deploy)
    web_api, _ = deploy._load_web_api()
    variables = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = web_api("GET", "connectors?$select=connectorid,openapidefinition,connectionparameters"
                         f"&$filter=name eq '{CONNECTOR_NAME}'")["value"]
    if len(rows) != 1:
        raise RuntimeError("Expected one existing SRM UI connector.")
    connector = rows[0]
    connector_id = connector["connectorid"]
    if connector_id.lower() not in deploy.solution_component_ids(web_api, CONNECTOR_COMPONENT):
        raise RuntimeError("The existing connector is not in SRMAgentDemo.")
    current_values = {}
    for variable in variables:
        existing = deploy.environment_variable_rows(web_api, variable["schemaName"])
        if existing:
            current = existing[0]["environmentvariabledefinition_environmentvariablevalue"]
            value = current[0].get("value") if current else existing[0].get("defaultvalue")
            if value:
                current_values[variable["schemaName"]] = value
    original_api = json.loads(connector["openapidefinition"])
    original_parameters = json.loads(connector["connectionparameters"])
    api, parameters, values = parameterize(original_api, original_parameters, current_values)
    if set(values) != {v["schemaName"] for v in variables}:
        raise RuntimeError("Connector bindings do not match the declared environment variables.")
    if (resolve(api, values) != resolve(original_api, current_values) or
            resolve(parameters, values) != resolve(original_parameters, current_values)):
        raise RuntimeError("Parameterization would change resolved connector settings.")
    changed = api != original_api or parameters != original_parameters
    if changed and not args.dry_run and not args.acknowledge_oauth_reconfiguration:
        raise RuntimeError(
            "Updating connector metadata may invalidate its protected OAuth secret. "
            "Arrange private credential re-entry and pass --acknowledge-oauth-reconfiguration.")
    deploy.ensure_environment_variables(web_api, variables, values, args.dry_run)
    if args.dry_run:
        print("Would parameterize the SRM UI connector; all resolved settings remain unchanged. Values withheld.")
        if changed:
            print("OAuth credential re-entry may be required after updating the connector.")
        return
    definition_ids = []
    current_ids = []
    for variable in variables:
        row = deploy.environment_variable_rows(web_api, variable["schemaName"])[0]
        current = row["environmentvariabledefinition_environmentvariablevalue"]
        if row.get("defaultvalue") is not None or len(current) != 1 or current[0].get("value") != values[variable["schemaName"]]:
            raise RuntimeError("Connector environment-variable readback failed; connector was not updated.")
        definition_ids.append(row["environmentvariabledefinitionid"].lower())
        current_ids.append(current[0]["environmentvariablevalueid"].lower())
    if set(definition_ids) - deploy.solution_component_ids(web_api, deploy.ENV_VAR_COMPONENT):
        raise RuntimeError("Connector environment-variable definitions are missing from SRMAgentDemo.")
    if set(current_ids) & deploy.solution_component_ids(web_api, 381):
        raise RuntimeError("Environment-specific current values must not be included in SRMAgentDemo.")
    desired = {"openapidefinition": json.dumps(api), "connectionparameters": json.dumps(parameters)}
    if changed:
        web_api("PATCH", f"connectors({connector_id})", desired, deploy.SOLUTION_HEADER)
    verified = web_api("GET", f"connectors({connector_id})?$select=openapidefinition,connectionparameters")
    if (json.loads(verified["openapidefinition"]) != api or
            not parameters_match(json.loads(verified["connectionparameters"]), parameters)):
        raise RuntimeError("Connector readback did not match the parameterized source.")
    print("Verified: connector uses six environment variables; resolved non-secret settings unchanged.")
    print("Protected OAuth credentials are not covered by metadata readback. Test new sign-in and the dashboard before exporting.")


if __name__ == "__main__":
    main()
