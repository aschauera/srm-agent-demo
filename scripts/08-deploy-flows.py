"""Deploy the code-first SRM agent flows in flows/ to the SRMAgentDemo solution in DemoPRE.

Follows AGENTS.md, Cloud Flow Generation. Idempotently:

1. validates every flow source: JSON parses, connection references and environment variables are
   declared, and every Dataverse table and column the definitions touch exists in schema/;
2. creates or updates the declared environment variable definitions (in the solution) and sets
   their current values (outside the solution, because the values are environment-specific);
3. creates the declared connection references (in the solution) without a connection; binding a
   connection is a manual, user-owned step in the maker portal;
4. creates or updates each flow as a workflow record (category 5, modernflowtype 1 = agent flow,
   stable workflowid) in the solution, in draft unless --activate is given;
5. verifies solution membership, and with --activate turns flows on once their connection
   references are bound, reporting any flow that stays off and why.

Usage:
    python scripts/08-deploy-flows.py --validate-only
    python scripts/08-deploy-flows.py [--demo-mailbox you@contoso.com] [--activate] [--only <flow>]

Requirements: SRM-INT-008..012, SRM-PLT-002, SRM-GOV-004 (docs/06-agent-flows-and-actions.md).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOWS = ROOT / "flows"
SCHEMA = ROOT / "schema" / "tables"
ENVIRONMENT = "https://org5b55c88b.crm.dynamics.com"
SOLUTION = "SRMAgentDemo"
SOLUTION_HEADER = {"MSCRM.SolutionUniqueName": SOLUTION}
WORKFLOW_COMPONENT = 29
CONNECTION_REFERENCE_COMPONENT = 10132
ENV_VAR_COMPONENT = 380
# Platform tables the flows read or write besides the schema/ tables, with the columns they use.
SYSTEM_TABLES = {
    "processstages": {"processstageid", "stagename", "primaryentitytypecode"},
    "new_supplierfinancialreviews": {"businessprocessflowinstanceid", "activestageid", "traversedpath", "bpf_name",
                                     "bpf_mag_financialreviewrequestid", "_bpf_mag_financialreviewrequestid_value"},
}
COMMON_COLUMNS = {"mag_name", "modifiedon", "createdon"}
# Flows created or updated in this run.
WRITTEN: set[str] = set()


def _load_web_api():
    def run_cli(arguments: list[str]) -> subprocess.CompletedProcess[str]:
        shim = shutil.which("dataverse.cmd")
        node = shutil.which("node.exe")
        if not shim or not node:
            raise RuntimeError("Dataverse CLI and node.exe are required to deploy SRM flows.")
        entrypoint = Path(shim).parent / "node_modules" / "@microsoft" / "dataverse" / "bin" / "dataverse.js"
        if not entrypoint.is_file():
            raise RuntimeError(f"Dataverse CLI installation is incomplete under {entrypoint.parent.parent}.")
        return subprocess.run(
            [node, str(entrypoint), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    pac_shim = shutil.which("pac.cmd")
    if not pac_shim:
        raise RuntimeError("Power Platform CLI is required to deploy SRM flows.")
    pac_command = subprocess.list2cmdline([pac_shim, "auth", "list"])
    pac = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", pac_command],
        check=False,
        capture_output=True,
        text=True,
    )
    if pac.returncode or not any(
        re.search(r"\*\s+UNIVERSAL\s+DemoPRE\b", line) and ENVIRONMENT in line
        for line in pac.stdout.splitlines()
    ):
        raise RuntimeError(f"Select the approved PAC DemoPRE profile for {ENVIRONMENT} before deploying flows.")
    dataverse_profiles = run_cli(["auth", "list"])
    if dataverse_profiles.returncode or not any(
        re.search(r"\*\s+UNIVERSAL\b", line) and ENVIRONMENT in line
        for line in dataverse_profiles.stdout.splitlines()
    ):
        raise RuntimeError(f"Select the approved Dataverse CLI profile for {ENVIRONMENT} before deploying flows.")

    configured_url = os.environ.get("DATAVERSE_URL")
    if configured_url and configured_url.rstrip("/") != ENVIRONMENT:
        raise RuntimeError(f"DATAVERSE_URL points to {configured_url!r}; refusing non-DemoPRE access.")
    os.environ["DATAVERSE_URL"] = ENVIRONMENT

    def web_api(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> dict | None:
        arguments = [
            "api", "request", "--target", "dataverse", "--method", method,
            "--path", urllib.parse.quote(f"/api/data/v9.2/{path}", safe="/?=&(),;:'"),
            "--environment", ENVIRONMENT,
        ]
        temporary_body = None
        if body is not None:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json",
                                             delete=False, newline="\n") as handle:
                json.dump(body, handle, ensure_ascii=False, separators=(",", ":"))
                temporary_body = Path(handle.name)
            arguments.extend(["--body-file", str(temporary_body)])
        for name, value in (headers or {}).items():
            arguments.extend(["--header", f"{name}:{value}"])
        try:
            result = run_cli(arguments)
        finally:
            if temporary_body is not None:
                temporary_body.unlink(missing_ok=True)
        if result.returncode:
            message = (result.stderr or result.stdout).strip()[:1000]
            raise RuntimeError(f"Dataverse {method} {path} failed: {message}")
        output = result.stdout.strip()
        if not output:
            return None
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Dataverse {method} {path} returned a non-JSON response.") from error

    def app_module_id() -> str:
        rows = web_api("GET", "appmodules?$select=appmoduleid&$filter=uniquename eq 'mag_supplierfinancialriskreview'")["value"]
        if len(rows) != 1:
            raise RuntimeError(f"Expected one SRM app module in DemoPRE; found {len(rows)}.")
        return rows[0]["appmoduleid"]

    return web_api, app_module_id


# ---- source loading and validation -----------------------------------------------------------

def load_sources() -> tuple[list[dict], list[dict], list[dict]]:
    references = json.loads((FLOWS / "connection-references.json").read_text(encoding="utf-8"))
    variables = json.loads((FLOWS / "environment-variables.json").read_text(encoding="utf-8"))
    flows = []
    for folder in sorted(p for p in FLOWS.iterdir() if p.is_dir()):
        meta = json.loads((folder / "flow.json").read_text(encoding="utf-8"))
        source = json.loads((folder / "definition.json").read_text(encoding="utf-8"))
        contract_path = folder / "contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8")) if contract_path.exists() else None
        flows.append({"folder": folder.name, "meta": meta, "contract": contract, **source})
    return references, variables, flows


def schema_tables() -> dict[str, set[str]]:
    """Entity set name -> logical column names (plus lookup value/navigation names) from schema/."""
    tables = {}
    for path in SCHEMA.glob("*.json"):
        spec = json.loads(path.read_text(encoding="utf-8"))
        logical = spec["logicalName"]
        columns = {f"mag_{c['name']}".lower() for c in spec["columns"]} | COMMON_COLUMNS | {f"{logical}id"}
        for lookup in spec.get("lookups", []):
            attribute = f"mag_{lookup['name']}Id"
            columns |= {attribute.lower(), attribute, f"_{attribute.lower()}_value"}
        tables[f"{logical}s"] = columns
    return tables


def walk_actions(actions: dict):
    for name, action in actions.items():
        yield name, action
        for key in ("actions",):
            if isinstance(action.get(key), dict):
                yield from walk_actions(action[key])
        if isinstance(action.get("else"), dict):
            yield from walk_actions(action["else"].get("actions", {}))


def validate(references: list[dict], variables: list[dict], flows: list[dict]) -> list[str]:
    errors = []
    declared_refs = {r["logicalName"] for r in references}
    declared_vars = {v["schemaName"] for v in variables}
    tables = schema_tables() | SYSTEM_TABLES
    workflow_ids = set()
    for flow in flows:
        label = flow["folder"]
        meta, definition = flow["meta"], flow["definition"]
        if meta["workflowId"] in workflow_ids:
            errors.append(f"{label}: duplicate workflowId")
        workflow_ids.add(meta["workflowId"])
        used_refs = {v["connection"]["connectionReferenceLogicalName"] for v in flow["connectionReferences"].values()}
        errors += [f"{label}: undeclared connection reference {r}" for r in used_refs - declared_refs]
        if used_refs != set(meta["connectionReferences"]):
            errors.append(f"{label}: flow.json connectionReferences {meta['connectionReferences']} != {sorted(used_refs)}")
        text = json.dumps(definition)
        used_vars = set(re.findall(r"parameters\('[^']*\((mag_[A-Za-z0-9]+)\)'\)", text))
        errors += [f"{label}: undeclared environment variable {v}" for v in used_vars - declared_vars]
        params = {p["metadata"]["schemaName"] for k, p in definition["parameters"].items() if not k.startswith("$")}
        errors += [f"{label}: parameter for {v} missing from definition.parameters" for v in used_vars - params]
        if used_vars != set(meta["environmentVariables"]):
            errors.append(f"{label}: flow.json environmentVariables {meta['environmentVariables']} != {sorted(used_vars)}")
        steps = list(walk_actions(definition["actions"])) + list(definition["triggers"].items())
        for name, step in steps:
            inputs = step.get("inputs")
            if not isinstance(inputs, dict) or "host" not in inputs:
                continue
            api = inputs["host"]["apiId"].rsplit("/", 1)[-1]
            if api not in flow["connectionReferences"]:
                errors.append(f"{label}.{name}: connector {api} has no connection reference")
            params_ = inputs.get("parameters", {})
            entity = params_.get("entityName") or params_.get("subscriptionRequest/entityname")
            if not entity:
                continue
            entity_set = entity if entity.endswith("s") else f"{entity}s"
            if entity_set not in tables:
                errors.append(f"{label}.{name}: unknown table {entity}")
                continue
            if inputs["host"].get("operationId") in {"PerformBoundAction", "PerformUnboundAction"}:
                continue
            columns = set()
            for key, value in params_.items():
                if key.startswith("item/"):
                    columns.add(key[5:].split("@")[0])
                elif key in ("$select", "subscriptionRequest/filteringattributes") and isinstance(value, str):
                    columns |= {c.strip() for c in value.split(",")}
            unknown = {c for c in columns if c not in tables[entity_set] and c.lower() not in tables[entity_set]}
            errors += [f"{label}.{name}: unknown column {entity}.{c}" for c in sorted(unknown)]
        if label == "save-review-analysis-draft":
            errors.extend(validate_analysis_draft(flow))
    return errors


def validate_analysis_draft(flow: dict) -> list[str]:
    """Keep the save tool's write surface and embedded JSON schema aligned to its contract."""
    errors = []
    label = flow["folder"]
    contract = flow["contract"]
    definition = flow["definition"]
    embedded_schema = (definition.get("actions", {}).get("Parse_analysis", {})
                       .get("inputs", {}).get("schema"))
    if not isinstance(contract, dict) or embedded_schema != contract:
        errors.append(f"{label}: Parse_analysis schema must exactly match contract.json")
        return errors

    trigger_schema = (definition.get("triggers", {}).get("manual", {})
                      .get("inputs", {}).get("schema", {}))
    analysis_input = trigger_schema.get("properties", {}).get("analysisjson", {})
    if analysis_input.get("maxLength") != 3000:
        errors.append(f"{label}: analysisjson trigger must enforce the 3,000-character memo-field limit")
    # Request triggers do not enforce schema maxLength, so the pre-write gate must check it explicitly.
    gate = (definition.get("actions", {}).get("Validate_payload_and_call", {})
            .get("expression", {}).get("and", []))
    required_guards = [
        {"lessOrEquals": ["@length(triggerBody()?['analysisjson'])", 3000]},
        {"lessOrEquals": ["@length(string(body('Parse_analysis')))", 3000]},
    ]
    if any(guard not in gate for guard in required_guards):
        errors.append(f"{label}: Validate_payload_and_call must check analysisjson length before writes")

    allowed_writes = {
        "mag_financialreviewrequests": {"mag_narrativedraft"},
        "mag_financialworkingpapers": {
            "mag_name", "mag_demokey", "mag_fiscalyear", "mag_period", "mag_currency",
            "mag_revenue", "mag_costofgoodssold", "mag_grossprofit", "mag_netincome",
            "mag_operatingcashflow", "mag_currentassets", "mag_currentliabilities",
            "mag_totalassets", "mag_totaldebt", "mag_accountsreceivable", "mag_inventory",
            "mag_leverageratio", "mag_liquidityratio", "mag_grossmargin", "mag_assetturnover",
            "mag_yearoveryeardelta", "mag_anomalyflags", "mag_reviewrequestid", "mag_supplierid",
        },
        "mag_nonfinancialriskitems": {
            "mag_name", "mag_demokey", "mag_risktype", "mag_details", "mag_verified",
            "mag_reviewrequestid", "mag_supplierid",
        },
        "mag_reviewaudittrails": {
            "mag_name", "mag_demokey", "mag_action", "mag_actor", "mag_actortype",
            "mag_occurredon", "mag_systemtouched", "mag_details", "mag_reviewrequestid",
            "mag_supplierid",
        },
    }
    write_operations = {"CreateRecord", "UpdateRecord", "DeleteRecord"}
    update_operations = {"UpdateRecord", "DeleteRecord"}
    for name, action in walk_actions(definition.get("actions", {})):
        inputs = action.get("inputs")
        if not isinstance(inputs, dict):
            continue
        operation = inputs.get("host", {}).get("operationId")
        if operation not in write_operations:
            continue
        entity = inputs.get("parameters", {}).get("entityName", "")
        entity = entity.lower()
        written = {
            key[5:].split("@", 1)[0].lower()
            for key in inputs.get("parameters", {})
            if key.startswith("item/")
        }
        unexpected = written - allowed_writes.get(entity, set())
        errors += [f"{label}.{name}: prohibited write to {entity}.{column}" for column in sorted(unexpected)]
        if operation in update_operations and entity != "mag_financialreviewrequests":
            errors.append(f"{label}.{name}: child and audit records must not be updated or deleted")

    text = json.dumps(definition).lower()
    for protected in ("mag_finalrating", "mag_finalratingconfirmed", "mag_preliminaryrating",
                      "mag_reviewstatus", "mag_currentstage", "sourcedocumentid"):
        if protected in text:
            errors.append(f"{label}: definition references protected field {protected}")
    return errors


# ---- deployment ------------------------------------------------------------------------------

def solution_component_ids(web_api, component_type: int) -> set[str]:
    solution_id = web_api("GET", f"solutions?$select=solutionid&$filter=uniquename eq '{SOLUTION}'")["value"][0]["solutionid"]
    rows = web_api("GET", "solutioncomponents?$select=objectid"
                          f"&$filter=_solutionid_value eq {solution_id} and componenttype eq {component_type}")["value"]
    return {row["objectid"].lower() for row in rows}


def add_to_solution(web_api, component_id: str, component_type: int) -> None:
    web_api("POST", "AddSolutionComponent", {
        "ComponentId": component_id, "ComponentType": component_type, "SolutionUniqueName": SOLUTION,
        "AddRequiredComponents": False, "DoNotIncludeSubcomponents": False,
    })


def ensure_environment_variables(web_api, variables: list[dict], values: dict[str, str], dry_run: bool) -> None:
    for variable in variables:
        schema = variable["schemaName"]
        rows = web_api("GET", "environmentvariabledefinitions?$select=environmentvariabledefinitionid,displayname"
                              f"&$filter=schemaname eq '{schema}'"
                              "&$expand=environmentvariabledefinition_environmentvariablevalue($select=value,environmentvariablevalueid)")["value"]
        body = {"displayname": variable["displayName"], "description": variable["description"], "type": 100000000}
        if dry_run:
            print(f"{'Update' if rows else 'Create'} environment variable {schema} = {values[schema]!r}")
            continue
        if rows:
            definition_id = rows[0]["environmentvariabledefinitionid"]
            web_api("PATCH", f"environmentvariabledefinitions({definition_id})", body, SOLUTION_HEADER)
        else:
            created = web_api("POST", "environmentvariabledefinitions", {**body, "schemaname": schema},
                              {**SOLUTION_HEADER, "Prefer": "return=representation"})
            definition_id = created["environmentvariabledefinitionid"]
            print(f"Created environment variable {schema}")
        existing = rows[0]["environmentvariabledefinition_environmentvariablevalue"] if rows else []
        if existing:
            # Configurable constants keep any value the user changed in the environment.
            if "defaultValue" not in variable and existing[0]["value"] != values[schema]:
                web_api("PATCH", f"environmentvariablevalues({existing[0]['environmentvariablevalueid']})",
                        {"value": values[schema]})
                print(f"Updated value of {schema}")
        else:
            # Values are environment-specific, so they are created outside the solution.
            web_api("POST", "environmentvariablevalues", {
                "schemaname": f"{schema}_value", "value": values[schema],
                "EnvironmentVariableDefinitionId@odata.bind": f"/environmentvariabledefinitions({definition_id})",
            })
            print(f"Set value of {schema}")


def ensure_connection_references(web_api, references: list[dict], dry_run: bool) -> dict[str, bool]:
    bound = {}
    for reference in references:
        name = reference["logicalName"]
        rows = web_api("GET", "connectionreferences?$select=connectionreferenceid,connectionid"
                              f"&$filter=connectionreferencelogicalname eq '{name}'")["value"]
        if rows:
            bound[name] = bool(rows[0]["connectionid"])
            continue
        bound[name] = False
        if dry_run:
            print(f"Create connection reference {name}")
            continue
        web_api("POST", "connectionreferences", {
            "connectionreferencelogicalname": name,
            "connectionreferencedisplayname": reference["displayName"],
            "connectorid": reference["connectorId"],
            "description": reference["description"],
        }, SOLUTION_HEADER)
        print(f"Created connection reference {name} (bind a connection in the maker portal)")
    return bound


def _normalized(properties: dict) -> dict:
    """Drop what the flow designer rewrites on save, so a designer-saved flow compares equal to source.

    The designer removes empty runAfter blocks, adds a definition description, and copies environment
    variable current values and descriptions into the parameter defaults. None of these change behavior.
    """
    properties = json.loads(json.dumps(properties))
    definition = properties.get("definition", {})
    definition.pop("description", None)
    for name, parameter in definition.get("parameters", {}).items():
        if not name.startswith("$"):
            parameter.pop("defaultValue", None)
            parameter.get("metadata", {}).pop("description", None)

    def strip(node):
        if isinstance(node, dict):
            if node.get("runAfter") == {}:
                del node["runAfter"]
            for value in node.values():
                strip(value)
        elif isinstance(node, list):
            for value in node:
                strip(value)
    strip(definition)
    return properties


def has_dataverse_trigger(flow: dict) -> bool:
    return any(t.get("inputs", {}).get("host", {}).get("operationId") == "SubscribeWebhookTrigger"
               for t in flow["definition"]["triggers"].values())


def ensure_flow(web_api, flow: dict, dry_run: bool) -> tuple[str, bool]:
    meta = flow["meta"]
    workflow_id = meta["workflowId"]
    clientdata = json.dumps({
        "properties": {"connectionReferences": flow["connectionReferences"], "definition": flow["definition"]},
        "schemaVersion": "1.0.0.0",
    }, separators=(",", ":"))
    body = {"name": meta["displayName"], "description": meta["description"], "clientdata": clientdata}
    rows = web_api("GET", f"workflows?$select=workflowid,statecode,clientdata,name,description"
                          f"&$filter=workflowid eq {workflow_id}")["value"]
    if rows:
        current = rows[0]
        same = (_normalized(json.loads(current["clientdata"])["properties"])
                == _normalized(json.loads(clientdata)["properties"])
                and current["name"] == body["name"] and current["description"] == body["description"])
        if same:
            print(f"Flow '{meta['displayName']}' already up to date")
            return workflow_id, current["statecode"] == 1
        if dry_run:
            print(f"Update flow '{meta['displayName']}'")
            return workflow_id, current["statecode"] == 1
        was_on = current["statecode"] == 1
        if was_on:
            web_api("PATCH", f"workflows({workflow_id})", {"statecode": 0, "statuscode": 1})
        web_api("PATCH", f"workflows({workflow_id})", body, SOLUTION_HEADER)
        print(f"Updated flow '{meta['displayName']}'")
        WRITTEN.add(workflow_id)
        return workflow_id, was_on
    if dry_run:
        print(f"Create flow '{meta['displayName']}'")
        return workflow_id, False
    web_api("POST", "workflows", {
        **body, "workflowid": workflow_id, "category": 5, "modernflowtype": 1, "type": 1,
        "primaryentity": "none", "statecode": 0, "statuscode": 1,
    }, SOLUTION_HEADER)
    print(f"Created flow '{meta['displayName']}' (draft)")
    WRITTEN.add(workflow_id)
    return workflow_id, False


def activate(web_api, workflow_id: str, name: str) -> str | None:
    try:
        web_api("PATCH", f"workflows({workflow_id})", {"statecode": 1, "statuscode": 2})
        return None
    except RuntimeError as error:
        return f"{name}: {str(error)[:3000]}"


def default_values(web_api, app_module_id, mailbox: str | None) -> dict[str, str]:
    if not mailbox:
        user_id = web_api("GET", "WhoAmI")["UserId"]
        mailbox = web_api("GET", f"systemusers({user_id})?$select=internalemailaddress")["internalemailaddress"]
    base = os.environ["DATAVERSE_URL"].rstrip("/")
    return {
        "mag_SRMDemoMailbox": mailbox,
        "mag_SRMAppRecordUrl": (f"{base}/main.aspx?appid={app_module_id()}"
                                "&pagetype=entityrecord&etn=mag_financialreviewrequest&id="),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--validate-only", action="store_true", help="Validate flows/ without contacting Dataverse.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing.")
    parser.add_argument("--activate", action="store_true", help="Turn flows on when their connections are bound.")
    parser.add_argument("--demo-mailbox", help="Mailbox for demo notifications (default: the deploying user).")
    parser.add_argument("--only", action="append", help="Deploy only the named flow folder (repeatable).")
    args = parser.parse_args()

    references, variables, flows = load_sources()
    errors = validate(references, variables, flows)
    if errors:
        raise SystemExit("Flow validation failed:\n  " + "\n  ".join(errors))
    print(f"Validated {len(flows)} flows, {len(references)} connection references, {len(variables)} environment variables.")
    if args.validate_only:
        return
    if args.only:
        flows = [f for f in flows if f["folder"] in args.only]
        unknown = set(args.only) - {f["folder"] for f in flows}
        if unknown:
            raise SystemExit(f"Unknown flow folder(s): {', '.join(sorted(unknown))}")
    required_references = {name for flow in flows for name in flow["meta"]["connectionReferences"]}
    required_variables = {name for flow in flows for name in flow["meta"]["environmentVariables"]}
    references = [reference for reference in references if reference["logicalName"] in required_references]
    variables = [variable for variable in variables if variable["schemaName"] in required_variables]

    web_api, app_module_id = _load_web_api()
    values = {}
    if variables:
        values = {**default_values(web_api, app_module_id, args.demo_mailbox),
                  **{v["schemaName"]: v["defaultValue"] for v in variables if "defaultValue" in v}}
    ensure_environment_variables(web_api, variables, values, args.dry_run)
    bound = ensure_connection_references(web_api, references, args.dry_run)
    deployed = [(flow, *ensure_flow(web_api, flow, args.dry_run)) for flow in flows]
    if args.dry_run:
        return

    members = solution_component_ids(web_api, WORKFLOW_COMPONENT)
    missing = [f["meta"]["displayName"] for f, workflow_id, _ in deployed if workflow_id.lower() not in members]
    if missing:
        raise SystemExit(f"Flows missing from {SOLUTION}: {missing}")
    print(f"Verified {len(deployed)} flows in {SOLUTION}.")

    off = []
    for flow, workflow_id, was_on in deployed:
        name = flow["meta"]["displayName"]
        unbound = [r for r in flow["meta"]["connectionReferences"] if not bound.get(r)]
        if not (args.activate or was_on):
            off.append(f"{name}: draft (rerun with --activate)")
        elif unbound:
            off.append(f"{name}: connection reference(s) not bound: {', '.join(unbound)}")
        else:
            problem = activate(web_api, workflow_id, name)
            if problem:
                off.append(problem)
            else:
                print(f"Flow '{name}' is on")
    if off:
        print("Flows left off:\n  " + "\n  ".join(off))
    # Verified in DemoPRE (2026-10-02): a Dataverse-triggered flow written through the Web API shows
    # as On but its trigger does not fire until the flow is opened and saved once in the designer.
    resave = [f["meta"]["displayName"] for f, workflow_id, _ in deployed
              if workflow_id in WRITTEN and has_dataverse_trigger(f)]
    if resave:
        print("ACTION REQUIRED - open each flow in the Power Automate designer and Save it once, then run "
              "09-smoke-test-stage1-flows.py; until then its Dataverse trigger will not fire:\n  "
              + "\n  ".join(resave))


if __name__ == "__main__":
    main()
