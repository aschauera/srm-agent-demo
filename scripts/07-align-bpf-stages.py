"""Align Supplier Financial Review BPF instances with the seeded review requests.

Model-driven apps show the BPF stage bar only for records with a process instance, and imported
seed rows have none. For every seeded request (mag_demokey set) this script, idempotently, in
DemoPRE:

1. creates the BPF instance if it is missing, and
2. sets its active stage from mag_currentstage (1-5) and its traversed path from mag_reviewpath:
   - GSA Reuse (Shortcut A) skips Stages 2-4: 1 -> 5.
   - Coface Fast-Track (Shortcut B) skips Stage 3: 1 -> 2 -> 4 -> 5.
   - Full Review, or no path yet, visits every stage in order.

Instances stay active, including completed GSA reuse requests, which rest on Archiving &
Publication. Stage movement for new requests is the deferred branch automation.

Requirements: SRM-INT-005 (docs/03-model-driven-app.md). Use --dry-run to show the planned changes.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "configure_form", Path(__file__).with_name("06-configure-review-request-form.py"))
_form = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_form)
web_api = _form.web_api
bpf_id = _form.bpf_id

INSTANCES = "new_supplierfinancialreviews"
REQUESTS = "mag_financialreviewrequests"
STAGES = [
    "Request & Pre-Check",
    "Information Collection",
    "Analysis & Rating",
    "Communication & Decision",
    "Archiving & Publication",
]
SHORTCUT_PATHS = {
    "GSA Reuse": [1, 5],
    "Coface Fast-Track": [1, 2, 4, 5],
}
FORMATTED = "@OData.Community.Display.V1.FormattedValue"


def stage_ids(process_id: str) -> dict[int, str]:
    rows = web_api("GET", "processstages?$select=stagename,processstageid"
                          f"&$filter=_processid_value eq {process_id}")["value"]
    by_name = {row["stagename"]: row["processstageid"] for row in rows}
    missing = [name for name in STAGES if name not in by_name]
    if missing:
        raise RuntimeError(f"BPF stages not found: {missing}")
    return {number: by_name[name] for number, name in enumerate(STAGES, start=1)}


def planned_stages(current: int, review_path: str | None) -> list[int]:
    route = SHORTCUT_PATHS.get(review_path or "", list(range(1, 6)))
    if current not in route:
        raise ValueError(f"stage {current} is not on the {review_path or 'full review'} path {route}")
    return route[:route.index(current) + 1]


def seeded_requests() -> list[dict]:
    return web_api(
        "GET",
        f"{REQUESTS}?$select=mag_demokey,mag_currentstage,mag_reviewpath"
        "&$filter=mag_demokey ne null&$orderby=mag_demokey",
        headers={"Prefer": 'odata.include-annotations="OData.Community.Display.V1.FormattedValue"'},
    )["value"]


def instances_by_request() -> dict[str, list[dict]]:
    rows = web_api("GET", f"{INSTANCES}?$select=_bpf_mag_financialreviewrequestid_value,"
                          "_activestageid_value,traversedpath,statecode")["value"]
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row["_bpf_mag_financialreviewrequestid_value"], []).append(row)
    return result


def plan(stages: dict[int, str]) -> list[tuple[dict, dict | None, str, str]]:
    """(request, existing instance or None, active stage id, traversed path) needing a change."""
    existing = instances_by_request()
    changes = []
    for request in seeded_requests():
        key = request["mag_demokey"]
        current = request.get("mag_currentstage")
        if current not in stages:
            print(f"Skip {key}: mag_currentstage {current!r} is not 1-5.")
            continue
        path = request.get(f"mag_reviewpath{FORMATTED}")
        visited = planned_stages(current, path)
        active = stages[current]
        traversed = ",".join(stages[n] for n in visited)
        instances = existing.get(request["mag_financialreviewrequestid"], [])
        if len(instances) > 1:
            raise RuntimeError(f"{key} has {len(instances)} BPF instances; resolve them manually")
        instance = instances[0] if instances else None
        if instance and instance["_activestageid_value"] == active and instance["traversedpath"] == traversed:
            continue
        action = "Update" if instance else "Create"
        print(f"{action} BPF instance for {key}: {' -> '.join(STAGES[n - 1] for n in visited)}")
        changes.append((request, instance, active, traversed))
    return changes


def apply(changes: list[tuple[dict, dict | None, str, str]]) -> None:
    for request, instance, active, traversed in changes:
        body = {"activestageid@odata.bind": f"/processstages({active})", "traversedpath": traversed}
        if instance:
            web_api("PATCH", f"{INSTANCES}({instance['businessprocessflowinstanceid']})", body)
        else:
            body["bpf_mag_financialreviewrequestid@odata.bind"] = \
                f"/{REQUESTS}({request['mag_financialreviewrequestid']})"
            web_api("POST", INSTANCES, body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing.")
    args = parser.parse_args()

    stages = stage_ids(bpf_id())
    changes = plan(stages)
    if not changes:
        print("All seeded requests have an aligned BPF instance.")
        return
    if args.dry_run:
        return
    apply(changes)
    remaining = plan(stages)
    if remaining:
        raise RuntimeError(f"{len(remaining)} BPF instances are still misaligned")
    print(f"Aligned {len(changes)} BPF instances; verified.")


if __name__ == "__main__":
    main()
