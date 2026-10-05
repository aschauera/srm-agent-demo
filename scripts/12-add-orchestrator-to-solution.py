"""Add the existing SRM Orchestrator bot to SRMAgentDemo in DemoPRE.

The script is safe to rerun: it verifies the expected solution and bot, checks current
solutioncomponent membership, adds the existing bot only when absent, and verifies membership.
It uses Dataverse AddSolutionComponent with bot component type 10185; it never creates or
renames a bot and never exports/unpacks or publishes the solution.

Requirements: SRM-PLT-002, SRM-GOV-004; source slides 8-12.

Usage:
    python scripts/12-add-orchestrator-to-solution.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = "https://org5b55c88b.crm.dynamics.com"
SOLUTION = "SRMAgentDemo"
BOT_ID = "80878fd0-37b0-48d9-9d71-8526e0b19135"
BOT_SCHEMA = "cr6a3_srmorchestrator_VBnLJG"
BOT_NAME = "SRM Orchestrator"
BOT_COMPONENT_TYPE = 10185


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


def pac_run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return command_run("pac.cmd", arguments)


def dataverse_run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    shim = shutil.which("dataverse.cmd")
    if not shim:
        raise RuntimeError("Dataverse CLI (dataverse.cmd) was not found on PATH.")
    cli_root = Path(shim).parent
    node = shutil.which("node.exe")
    entrypoint = cli_root / "node_modules" / "@microsoft" / "dataverse" / "bin" / "dataverse.js"
    if not node or not entrypoint.is_file():
        raise RuntimeError(f"Dataverse CLI installation is incomplete under {cli_root}.")
    return subprocess.run(
        [node, str(entrypoint), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def active_demo_pre_profile() -> None:
    result = pac_run(["auth", "list"])
    if result.returncode:
        raise RuntimeError(f"pac auth list failed: {result.stderr or result.stdout}")
    target = ENVIRONMENT.rstrip("/")
    if not any(
        re.search(r"\*\s+UNIVERSAL\s+DemoPRE\b", line) and target in line
        for line in result.stdout.splitlines()
    ):
        raise RuntimeError(
            "No active PAC profile named DemoPRE targets "
            f"{ENVIRONMENT}; select the approved DemoPRE profile before running."
        )
    result = dataverse_run(["auth", "list"])
    if result.returncode:
        raise RuntimeError(f"dataverse auth list failed: {result.stderr or result.stdout}")
    if not any(
        re.search(r"\*\s+UNIVERSAL\b", line) and target in line
        for line in result.stdout.splitlines()
    ):
        raise RuntimeError(
            "No active Dataverse CLI profile targets "
            f"{ENVIRONMENT}; select the approved DemoPRE profile before running."
        )


def web_api_get(path: str) -> list[dict]:
    result = dataverse_run(
        [
            "api", "request",
            "--target", "dataverse",
            "--method", "GET",
            "--path", path,
            "--environment", ENVIRONMENT,
        ]
    )
    if result.returncode:
        raise RuntimeError(f"Dataverse GET failed: {(result.stderr or result.stdout).strip()}")
    try:
        return json.loads(result.stdout)["value"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeError(f"Dataverse GET returned an unexpected response for {path}.") from error


def solution_id() -> str:
    rows = web_api_get(
        "/api/data/v9.2/solutions?"
        "%24select=solutionid,uniquename&"
        "%24filter=uniquename%20eq%20%27SRMAgentDemo%27"
    )
    if len(rows) != 1 or rows[0].get("uniquename") != SOLUTION:
        raise RuntimeError(f"Expected exactly one solution named {SOLUTION}; found {len(rows)}.")
    return rows[0]["solutionid"].lower()


def verify_existing_bot() -> None:
    rows = web_api_get(
        "/api/data/v9.2/bots?"
        "%24select=botid,schemaname,name,componentstate,ismanaged&"
        f"%24filter=botid%20eq%20{BOT_ID}"
    )
    if len(rows) != 1:
        raise RuntimeError(f"Expected existing bot {BOT_ID}; found {len(rows)}.")
    bot = rows[0]
    actual = (bot.get("schemaname"), bot.get("name"), bot.get("ismanaged"))
    expected = (BOT_SCHEMA, BOT_NAME, False)
    if actual != expected:
        raise RuntimeError(f"Existing bot identity mismatch: {actual!r}; expected {expected!r}.")
    print(
        f"Verified existing bot {BOT_NAME}: {BOT_ID} "
        f"(schema {BOT_SCHEMA}, component state {bot.get('componentstate')})."
    )


def membership_rows(target_solution_id: str) -> list[dict]:
    return web_api_get(
        "/api/data/v9.2/solutioncomponents?"
        "%24select=solutioncomponentid,solutionid,componenttype,objectid,rootcomponentbehavior&"
        f"%24filter=_solutionid_value%20eq%20{target_solution_id}"
        f"%20and%20componenttype%20eq%20{BOT_COMPONENT_TYPE}"
        f"%20and%20objectid%20eq%20{BOT_ID}"
    )


def add_existing_bot() -> None:
    body = json.dumps(
        {
            "ComponentId": BOT_ID,
            "ComponentType": BOT_COMPONENT_TYPE,
            "SolutionUniqueName": SOLUTION,
            "AddRequiredComponents": False,
            "DoNotIncludeSubcomponents": False,
        }
    )
    result = dataverse_run(
        [
            "api", "request",
            "--target", "dataverse",
            "--method", "POST",
            "--path", "/api/data/v9.2/AddSolutionComponent",
            "--body", body,
            "--environment", ENVIRONMENT,
        ]
    )
    if result.returncode:
        raise RuntimeError(
            "Dataverse AddSolutionComponent failed: "
            + (result.stderr or result.stdout).strip()
        )
    print("Dataverse AddSolutionComponent request completed.")


def main() -> None:
    active_demo_pre_profile()
    configured_url = os.environ.get("DATAVERSE_URL")
    if configured_url and configured_url.rstrip("/") != ENVIRONMENT.rstrip("/"):
        raise RuntimeError(
            f"DATAVERSE_URL points to {configured_url!r}; refusing non-DemoPRE access."
        )
    os.environ["DATAVERSE_URL"] = ENVIRONMENT
    target_solution_id = solution_id()
    verify_existing_bot()
    rows = membership_rows(target_solution_id)
    if len(rows) > 1:
        raise RuntimeError(f"Unexpected duplicate bot membership rows: {rows!r}")
    if rows:
        print(f"Existing bot membership verified; no change needed: {rows[0]!r}")
        return

    print(
        f"Adding existing bot {BOT_ID} to {SOLUTION} "
        f"as solution component type {BOT_COMPONENT_TYPE}."
    )
    add_existing_bot()
    rows = membership_rows(target_solution_id)
    if len(rows) != 1:
        raise RuntimeError(
            f"Add operation returned without verified membership; found {len(rows)} rows."
        )
    print(f"Verified SRMAgentDemo membership after add: {rows[0]!r}")
    print("No publish or solution export/unpack was performed.")


if __name__ == "__main__":
    main()
