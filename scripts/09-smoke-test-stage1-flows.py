"""Smoke-test the Stage 1 GSA pre-check agent flow in DemoPRE, one request per outcome.

Creates five temporary review requests (division SMOKE-TEST) against seeded fictional suppliers,
waits for 'SRM Intake - GSA pre-check on submit' to process them, and checks the request fields,
ledger rows, communication log rows and BPF stage for each branch:

    reuse      valid GSA rating           -> completed, Final Rating copied, BPF on Archiving & Publication
    expired    expired GSA rating         -> Full Review, reviewer to-do
    mandatory  valid, mandatory re-review -> Full Review, mandatory flag, reviewer to-do
    nomatch    DUNS without GSA record    -> Full Review, reviewer to-do
    skip       supplier without DUNS      -> pre-check skipped, Full Review, reviewer to-do

The test rows (requests, their ledger and communication rows, and BPF instances) are deleted
afterwards unless --keep is given. Requires the flows to be on (08-deploy-flows.py --activate).

Requirements: SRM-INT-008, SRM-INT-009, SRM-INT-010, SRM-INT-011, SRM-GOV-004.
"""

from __future__ import annotations

import argparse
import importlib.util
import time
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "configure_form", Path(__file__).with_name("06-configure-review-request-form.py"))
_form = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_form)
web_api = _form.web_api

MARKER = "SMOKE-TEST"
VALID, EXPIRED, NO_MATCH, SKIP = 100000000, 100000001, 100000002, 100000003
NOT_STARTED, COMPLETED = 100000000, 100000002
GSA_REUSE, FULL_REVIEW = 100000000, 100000002
CASES = {
    # case: (supplier DUNS or None for the No DUNS supplier, expectations)
    "reuse": ("900000001", {"mag_gsaprecheckresult": VALID, "mag_reviewpath": GSA_REUSE,
                            "mag_reviewstatus": COMPLETED, "mag_finalrating": 100000000, "mag_currentstage": 5,
                            "stage": "Archiving & Publication", "mails": 2}),
    "expired": ("900000004", {"mag_gsaprecheckresult": EXPIRED, "mag_reviewpath": FULL_REVIEW,
                              "mag_reviewstatus": NOT_STARTED, "mag_finalrating": None, "mails": 1}),
    "mandatory": ("900000006", {"mag_gsaprecheckresult": VALID, "mag_reviewpath": FULL_REVIEW,
                                "mag_mandatoryrereview": True, "mag_finalrating": None, "mails": 1}),
    "nomatch": ("900000008", {"mag_gsaprecheckresult": NO_MATCH, "mag_reviewpath": FULL_REVIEW,
                              "mag_finalrating": None, "mails": 1}),
    "skip": (None, {"mag_gsaprecheckresult": SKIP, "mag_reviewpath": FULL_REVIEW,
                    "mag_finalrating": None, "mails": 1}),
}
SELECT = ("mag_financialreviewrequestid,mag_name,mag_requestref,mag_gsaprecheckresult,mag_reviewpath,mag_reviewstatus,"
          "mag_finalrating,mag_currentstage,mag_mandatoryrereview,mag_reviewernotified,mag_buyernotified")


def supplier(duns: str | None) -> tuple[str, str | None]:
    query = f"mag_duns eq '{duns}'" if duns else "mag_duns eq null"
    row = web_api("GET", f"mag_suppliers?$select=mag_supplierid,mag_duns&$filter={query}&$orderby=mag_name&$top=1")["value"][0]
    return row["mag_supplierid"], row["mag_duns"]


def create(case: str, duns: str | None) -> str:
    supplier_id, supplier_duns = supplier(duns)
    created = web_api("POST", "mag_financialreviewrequests", {
        "mag_SupplierId@odata.bind": f"/mag_suppliers({supplier_id})",
        "mag_buyername": f"Smoke Test Buyer ({case})",
        "mag_buyeremail": "smoke.buyer@example.com",
        "mag_division": MARKER,
        "mag_dunsnumber": supplier_duns,
        "mag_noduns": supplier_duns is None,
    }, {"Prefer": "return=representation"})
    return created["mag_financialreviewrequestid"]


def related(entity_set: str, request_id: str, select: str) -> list[dict]:
    return web_api("GET", f"{entity_set}?$select={select}&$filter=_mag_reviewrequestid_value eq {request_id}")["value"]


def bpf_stage(request_id: str) -> str | None:
    rows = web_api("GET", "new_supplierfinancialreviews?$select=businessprocessflowinstanceid"
                          f"&$filter=_bpf_mag_financialreviewrequestid_value eq {request_id}"
                          "&$expand=activestageid($select=stagename)")["value"]
    return rows[0]["activestageid"]["stagename"] if rows and rows[0].get("activestageid") else None


def check(case: str, request_id: str, expected: dict) -> list[str]:
    row = web_api("GET", f"mag_financialreviewrequests({request_id})?$select={SELECT}")
    problems = []
    for field, value in expected.items():
        if field.startswith("mag_") and row.get(field) != value:
            problems.append(f"{field} = {row.get(field)!r}, expected {value!r}")
    audits = related("mag_reviewaudittrails", request_id, "mag_action,mag_actortype")
    mails = related("mag_communicationlogs", request_id, "mag_subject,mag_direction,mag_channel")
    if not any(a["mag_action"].startswith(("Completed", "GSA pre-check")) for a in audits):
        problems.append(f"no pre-check ledger row (actions: {[a['mag_action'] for a in audits]})")
    if any(a["mag_actortype"] != 100000001 for a in audits):
        problems.append("ledger row not attributed to the agent")
    if len(mails) != expected["mails"]:
        problems.append(f"{len(mails)} communication log rows, expected {expected['mails']}")
    if not row["mag_name"]:
        problems.append("request name not backfilled")
    stage = bpf_stage(request_id)
    if "stage" in expected and stage != expected["stage"]:
        problems.append(f"BPF stage {stage!r}, expected {expected['stage']!r}")
    print(f"{case:9} {row['mag_requestref']}  ledger: {[a['mag_action'] for a in audits]}")
    print(f"{'':9} mails: {[m['mag_subject'] for m in mails]}  stage: {stage}")
    return problems


def _delete(path: str) -> None:
    """Delete one row, retrying Dataverse's transient concurrent-delete conflict (0x80048105)."""
    for attempt in range(4):
        try:
            web_api("DELETE", path)
            return
        except RuntimeError as error:
            if "0x80040217" in str(error):  # already gone
                return
            if "0x80048105" not in str(error) or attempt == 3:
                raise
            time.sleep(5)


def cleanup() -> None:
    requests = web_api("GET", f"mag_financialreviewrequests?$select=mag_financialreviewrequestid"
                              f"&$filter=mag_division eq '{MARKER}'")["value"]
    for request in requests:
        request_id = request["mag_financialreviewrequestid"]
        for entity_set, key in (("mag_reviewaudittrails", "mag_reviewaudittrailid"),
                                ("mag_communicationlogs", "mag_communicationlogid")):
            for row in related(entity_set, request_id, key):
                _delete(f"{entity_set}({row[key]})")
        for row in web_api("GET", "new_supplierfinancialreviews?$select=businessprocessflowinstanceid"
                                  f"&$filter=_bpf_mag_financialreviewrequestid_value eq {request_id}")["value"]:
            _delete(f"new_supplierfinancialreviews({row['businessprocessflowinstanceid']})")
        _delete(f"mag_financialreviewrequests({request_id})")
    print(f"Removed {len(requests)} smoke-test requests and their related rows.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--keep", action="store_true", help="Keep the test rows for inspection.")
    parser.add_argument("--cleanup-only", action="store_true", help="Only remove leftover smoke-test rows.")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds to wait for the flow runs.")
    args = parser.parse_args()
    cleanup()
    if args.cleanup_only:
        return
    ids = {case: create(case, duns) for case, (duns, _) in CASES.items()}
    print(f"Created {len(ids)} requests; waiting for the pre-check flow...")
    deadline = time.time() + args.timeout
    pending = dict(ids)
    while pending and time.time() < deadline:
        time.sleep(20)
        for case, request_id in list(pending.items()):
            row = web_api("GET", f"mag_financialreviewrequests({request_id})?$select=mag_gsaprecheckresult")
            communications = related("mag_communicationlogs", request_id, "mag_communicationlogid")
            if row["mag_gsaprecheckresult"] is not None and len(communications) >= CASES[case][1]["mails"]:
                del pending[case]
    time.sleep(20)  # let the D&B auto-fill step finish after the last notification
    failures = {case: [f"not processed within {args.timeout}s"] for case in pending}
    for case, request_id in ids.items():
        if case not in pending:
            problems = check(case, request_id, CASES[case][1])
            if problems:
                failures[case] = problems
    if not args.keep:
        cleanup()
    if failures:
        raise SystemExit("Smoke test failed:\n" + "\n".join(f"  {c}: {p}" for c, ps in failures.items() for p in ps))
    print(f"All {len(CASES)} pre-check outcomes passed.")


if __name__ == "__main__":
    main()
