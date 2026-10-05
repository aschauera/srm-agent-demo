"""Wire the existing draft-save agent flow into the existing SRM Orchestrator.

The script is repeatable: it creates the supported botcomponent WorkflowTool record only
when absent, links that record to the existing agent flow, and adds it to SRMAgentDemo.
It never creates or renames a bot, publishes, or exports/unpacks a solution.
Requirements: SRM-FIN-001, SRM-NFR-001, SRM-GOV-004; source slides 8-12.

Usage:
    python scripts/15-wire-analysis-draft-agent-tool.py [--dry-run]
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
ENVIRONMENT = "https://org5b55c88b.crm.dynamics.com"
SOLUTION = "SRMAgentDemo"
BOT_ID = "80878fd0-37b0-48d9-9d71-8526e0b19135"
BOT_SCHEMA = "cr6a3_srmorchestrator_VBnLJG"
BOT_NAME = "SRM Orchestrator"
WORKFLOW_ID = "f9150906-1e0e-4bd0-9213-0f8bb53646fb"
WORKFLOW_NAME = "SRM - Save review analysis draft"
TOOL_SCHEMA = "cr6a3_srmorchestrator_VBnLJG.tool.SRM-Savereviewanalysisdraft_VwqL7s"
BOTCOMPONENT_TYPE = 9
BOTCOMPONENT_SOLUTION_TYPE = 10186
TOOL_SOURCE = (
    ROOT
    / "agents"
    / "srm-orchestrator"
    / "copilot"
    / "srm-orchestrator"
    / "capabilities"
    / "tools"
    / "SRM-Savereviewanalysisdraft_VwqL7s.mcs.yml"
)


def command_run(executable: str, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    executable_path = shutil.which(executable)
    if not executable_path:
        raise RuntimeError(f"{executable} CLI was not found on PATH.")
    command = subprocess.list2cmdline([executable_path, *arguments])
    return subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command],
        check=False,
        capture_output=True,
        text=True,
    )


def dataverse_run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    shim = shutil.which("dataverse.cmd")
    node = shutil.which("node.exe")
    if not shim or not node:
        raise RuntimeError("Dataverse CLI and node.exe are required to wire the agent tool.")
    entrypoint = Path(shim).parent / "node_modules" / "@microsoft" / "dataverse" / "bin" / "dataverse.js"
    if not entrypoint.is_file():
        raise RuntimeError(f"Dataverse CLI installation is incomplete under {entrypoint.parent.parent}.")
    return subprocess.run(
        [node, str(entrypoint), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def require_demo_pre_profiles() -> None:
    target = ENVIRONMENT.rstrip("/")
    pac = command_run("pac.cmd", ["auth", "list"])
    if pac.returncode or not any(
        re.search(r"\*\s+UNIVERSAL\s+DemoPRE\b", line) and target in line
        for line in pac.stdout.splitlines()
    ):
        raise RuntimeError(f"Select the approved PAC DemoPRE profile for {ENVIRONMENT}.")
    dv = dataverse_run(["auth", "list"])
    if dv.returncode or not any(
        re.search(r"\*\s+UNIVERSAL\b", line) and target in line
        for line in dv.stdout.splitlines()
    ):
        raise RuntimeError(f"Select the Dataverse CLI profile targeting DemoPRE at {ENVIRONMENT}.")


def web_api(method: str, path: str, body: dict | None = None) -> dict | None:
    arguments = [
        "api",
        "request",
        "--target",
        "dataverse",
        "--method",
        method,
        "--path",
        urllib.parse.quote(f"/api/data/v9.2/{path}", safe="/?=&(),;$'%"),
        "--environment",
        ENVIRONMENT,
    ]
    temporary_body: Path | None = None
    if body is not None:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False, newline="\n"
        ) as handle:
            json.dump(body, handle, ensure_ascii=False, separators=(",", ":"))
            temporary_body = Path(handle.name)
        arguments.extend(["--body-file", str(temporary_body)])
    try:
        result = dataverse_run(arguments)
    finally:
        if temporary_body is not None:
            temporary_body.unlink(missing_ok=True)
    if result.returncode:
        message = (result.stderr or result.stdout).strip()[:1200]
        raise RuntimeError(f"Dataverse {method} {path} failed: {message}")
    output = result.stdout.strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Dataverse {method} {path} returned a non-JSON response.") from error


def get_rows(path: str) -> list[dict]:
    result = web_api("GET", path)
    if not isinstance(result, dict) or not isinstance(result.get("value"), list):
        raise RuntimeError(f"Dataverse GET {path} did not return a row collection.")
    return result["value"]


def post(path: str, body: dict, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY RUN: POST {path}")
        return
    web_api("POST", path, body)


def add_to_solution(component_id: str, dry_run: bool) -> None:
    body = {
        "ComponentId": component_id,
        "ComponentType": BOTCOMPONENT_SOLUTION_TYPE,
        "SolutionUniqueName": SOLUTION,
        "AddRequiredComponents": False,
        "DoNotIncludeSubcomponents": False,
    }
    post("AddSolutionComponent", body, dry_run)


def load_tool_source() -> tuple[str, str, str]:
    text = TOOL_SOURCE.read_text(encoding="utf-8")
    match = re.search(r"(?m)^kind: WorkflowTool\s*$", text)
    if not match:
        raise RuntimeError(f"{TOOL_SOURCE} does not contain a WorkflowTool definition.")
    data = text[match.start() :].replace("\r\n", "\n").strip() + "\r\n"
    if f"workflowId: {WORKFLOW_ID}" not in data:
        raise RuntimeError("The local WorkflowTool source references a different workflow ID.")
    component_name = re.search(r"(?m)^\s+componentName:\s*(.+?)\s*$", text)
    description = re.search(r"(?m)^\s+description:\s*(.+?)\s*$", text)
    if not component_name or not description:
        raise RuntimeError("The local WorkflowTool source is missing its component name or description.")
    return component_name.group(1).strip().strip('"'), description.group(1).strip().strip('"'), data


def verify_solution() -> str:
    rows = get_rows(
        "solutions?$select=solutionid,uniquename&$filter=uniquename%20eq%20%27"
        + SOLUTION
        + "%27"
    )
    if len(rows) != 1 or rows[0].get("uniquename") != SOLUTION:
        raise RuntimeError(f"Expected exactly one {SOLUTION} solution; found {len(rows)}.")
    return rows[0]["solutionid"].lower()


def verify_bot() -> None:
    rows = get_rows(
        f"bots?$select=botid,schemaname,name,ismanaged&$filter=botid%20eq%20{BOT_ID}"
    )
    if len(rows) != 1:
        raise RuntimeError(f"Expected the existing Orchestrator bot {BOT_ID}; found {len(rows)}.")
    bot = rows[0]
    if (bot.get("schemaname"), bot.get("name"), bot.get("ismanaged")) != (
        BOT_SCHEMA,
        BOT_NAME,
        False,
    ):
        raise RuntimeError(f"Existing Orchestrator identity mismatch: {bot!r}")


def verify_workflow() -> None:
    rows = get_rows(
        "workflows?$select=workflowid,name,category,modernflowtype,statecode"
        f"&$filter=workflowid%20eq%20{WORKFLOW_ID}"
    )
    if len(rows) != 1:
        raise RuntimeError(f"Expected existing agent flow {WORKFLOW_ID}; found {len(rows)}.")
    workflow = rows[0]
    if (
        workflow.get("name") != WORKFLOW_NAME
        or workflow.get("category") != 5
        or workflow.get("modernflowtype") != 1
        or workflow.get("statecode") != 1
    ):
        raise RuntimeError(f"Existing agent-flow identity/state mismatch: {workflow!r}")


def component_rows() -> list[dict]:
    escaped = urllib.parse.quote(TOOL_SCHEMA, safe=".-_")
    return get_rows(
        "botcomponents?$select=botcomponentid,name,schemaname,componenttype,description,data,"
        f"_parentbotid_value&$filter=schemaname%20eq%20%27{escaped}%27"
    )


def verify_component(component: dict, component_name: str, description: str, data: str) -> None:
    expected = {
        "name": component_name,
        "schemaname": TOOL_SCHEMA,
        "componenttype": BOTCOMPONENT_TYPE,
        "description": description,
        "data": data,
        "_parentbotid_value": BOT_ID,
    }
    mismatches = {
        key: (component.get(key), value)
        for key, value in expected.items()
        if component.get(key) != value
    }
    if mismatches:
        raise RuntimeError(
            "WorkflowTool component readback differs from the local source: "
            f"{mismatches!r}"
        )


def membership_rows(solution_id: str, component_id: str) -> list[dict]:
    return get_rows(
        "solutioncomponents?$select=solutioncomponentid,componenttype,objectid,"
        f"_solutionid_value&$filter=_solutionid_value%20eq%20{solution_id}"
        f"%20and%20componenttype%20eq%20{BOTCOMPONENT_SOLUTION_TYPE}"
        f"%20and%20objectid%20eq%20{component_id}"
    )


def linked_workflows(component_id: str) -> list[dict]:
    record = web_api(
        "GET",
        f"botcomponents({component_id})?$select=botcomponentid"
        "&$expand=botcomponent_workflow($select=workflowid,name,category,modernflowtype,statecode)",
    )
    if not isinstance(record, dict):
        raise RuntimeError("Dataverse did not return the botcomponent workflow association.")
    workflows = record.get("botcomponent_workflow")
    if not isinstance(workflows, list):
        raise RuntimeError("The botcomponent_workflow relationship was not returned.")
    return workflows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Check prerequisites without writing.")
    args = parser.parse_args()

    require_demo_pre_profiles()
    configured_url = os.environ.get("DATAVERSE_URL")
    if configured_url and configured_url.rstrip("/") != ENVIRONMENT.rstrip("/"):
        raise RuntimeError(f"DATAVERSE_URL points to {configured_url!r}; refusing non-DemoPRE access.")
    os.environ["DATAVERSE_URL"] = ENVIRONMENT

    component_name, description, data = load_tool_source()
    if component_name != WORKFLOW_NAME:
        raise RuntimeError(f"Tool component name mismatch: {component_name!r}.")
    solution_id = verify_solution()
    verify_bot()
    verify_workflow()

    rows = component_rows()
    if len(rows) > 1:
        raise RuntimeError(f"Duplicate botcomponent schema names exist: {rows!r}")
    if rows:
        component = rows[0]
        verify_component(component, component_name, description, data)
        component_id = component["botcomponentid"].lower()
        print(f"Verified existing WorkflowTool component: {component_id}.")
    else:
        print("Verified no existing WorkflowTool component uses the requested schema.")
        if args.dry_run:
            print("DRY RUN: would create the component, workflow association, and solution membership.")
            return
        post(
            "botcomponents",
            {
                "name": component_name,
                "schemaname": TOOL_SCHEMA,
                "componenttype": BOTCOMPONENT_TYPE,
                "description": description,
                "data": data,
                "statecode": 0,
                "statuscode": 1,
                "parentbotid@odata.bind": f"/bots({BOT_ID})",
            },
            dry_run=False,
        )
        rows = component_rows()
        if len(rows) != 1:
            raise RuntimeError(f"Tool component create did not verify; found {len(rows)} rows.")
        verify_component(rows[0], component_name, description, data)
        component_id = rows[0]["botcomponentid"].lower()
        print(f"Created and read back WorkflowTool component: {component_id}.")

    links = linked_workflows(component_id)
    target_links = [link for link in links if link.get("workflowid", "").lower() == WORKFLOW_ID]
    if len(target_links) > 1:
        raise RuntimeError(f"Duplicate workflow associations exist: {target_links!r}")
    if not target_links:
        if args.dry_run:
            print("DRY RUN: would associate the component with the existing agent flow.")
        else:
            post(
                f"botcomponents({component_id})/botcomponent_workflow/$ref",
                {
                    "@odata.id": (
                        f"{ENVIRONMENT}/api/data/v9.2/workflows({WORKFLOW_ID})"
                    )
                },
                dry_run=False,
            )
            links = linked_workflows(component_id)
            target_links = [
                link for link in links if link.get("workflowid", "").lower() == WORKFLOW_ID
            ]
            if len(target_links) != 1:
                raise RuntimeError(
                    "Workflow association was not verified after write; "
                    f"found {len(target_links)} matching links."
                )
        print("Verified existing flow association." if target_links else "Flow association pending.")
    else:
        print(f"Verified existing association with {WORKFLOW_ID}.")

    membership = membership_rows(solution_id, component_id)
    if len(membership) > 1:
        raise RuntimeError(f"Duplicate solution membership rows exist: {membership!r}")
    if not membership:
        if args.dry_run:
            print("DRY RUN: would add the existing botcomponent as solution component type 10186.")
        else:
            add_to_solution(component_id, dry_run=False)
            membership = membership_rows(solution_id, component_id)
            if len(membership) != 1:
                raise RuntimeError(
                    "Solution membership was not verified after AddSolutionComponent; "
                    f"found {len(membership)} rows."
                )
        print("Added existing WorkflowTool to SRMAgentDemo." if membership else "Solution membership pending.")
    else:
        if membership[0].get("componenttype") != BOTCOMPONENT_SOLUTION_TYPE:
            raise RuntimeError(f"Unexpected solution component type: {membership[0]!r}")
        print(f"Verified existing SRMAgentDemo membership: {membership[0]!r}")

    if args.dry_run:
        return
    if len(target_links) != 1 or len(membership) != 1:
        raise RuntimeError("Tool wiring is incomplete; no success result is reported.")
    print(
        f"Verified {component_name} on {BOT_NAME}, linked to active agent flow "
        f"{WORKFLOW_ID}, in {SOLUTION}."
    )
    print("No publish or solution export/unpack was performed.")


if __name__ == "__main__":
    main()
