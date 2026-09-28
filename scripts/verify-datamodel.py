"""Verify DemoPRE SRM schema membership and seeded records against local fixtures."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from auth import get_client

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schema" / "tables"
DATA_DIR = ROOT / "data"
SOLUTION = "SRMAgentDemo"
SEED_FILES = {
    "mag_supplier": "suppliers.csv",
    "mag_financialreviewrequest": "review_requests.csv",
    "mag_documentrequest": "document_requests.csv",
    "mag_supplierdocument": "supplier_documents.csv",
    "mag_financialworkingpaper": "working_papers.csv",
    "mag_nonfinancialriskitem": "nonfinancial_risks.csv",
    "mag_communicationlog": "communications.csv",
    "mag_earlywarning": "early_warnings.csv",
    "mag_reviewaudittrail": "audit_trail.csv",
    "mag_gsaratingrecord": "gsa_ratings.csv",
    "mag_cofacecreditrecord": "coface_records.csv",
    "mag_dnbprofile": "dnb_profiles.csv",
    "mag_archiverecord": "archive_records.csv",
    "mag_adversenewsevent": "adverse_news.csv",
    "mag_ratingconversionrule": "rating_conversion_rules.csv",
    "mag_riskscoringrule": "risk_scoring_rules.csv",
    "mag_supplieronepagesummary": "supplier_one_page_summaries.csv",
}
PREFIX = "mag"


def read_csv_keys(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return {row["DemoKey"] for row in csv.DictReader(stream)}


def main() -> None:
    client = get_client("dv-query")
    solution_rows = list(client.records.list(
        "solution",
        filter=f"uniquename eq '{SOLUTION}'",
        select=["solutionid"],
        top=2,
    ))
    if len(solution_rows) != 1:
        raise RuntimeError(f"Expected one {SOLUTION} solution, found {len(solution_rows)}")
    solution_id = solution_rows[0]["solutionid"]
    components = list(client.records.list(
        "solutioncomponent",
        filter=f"_solutionid_value eq {solution_id}",
        select=["componenttype", "objectid"],
        top=5000,
    ))
    table_component_ids = {
        row["objectid"].lower()
        for row in components
        if row["componenttype"] == 1
    }

    expected_total = 0
    for table_name, filename in SEED_FILES.items():
        spec_path = SCHEMA_DIR / f"{table_name.removeprefix('mag_')}.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        info = client.tables.get(table_name)
        if info is None:
            raise RuntimeError(f"Missing Dataverse table {table_name}")
        if info.metadata_id.lower() not in table_component_ids:
            raise RuntimeError(f"{table_name} is not a root component in {SOLUTION}")

        actual_columns = {
            column["LogicalName"].lower()
            for column in client.tables.list_columns(table_name, select=["LogicalName"])
        }
        expected_columns = {f"{PREFIX}_{column['name']}".lower() for column in spec["columns"]}
        expected_columns.add("mag_name")
        expected_columns.update(
            f"{PREFIX}_{lookup['name']}id".lower()
            for lookup in spec.get("lookups", [])
        )
        missing_columns = expected_columns - actual_columns
        if missing_columns:
            raise RuntimeError(f"{table_name} is missing columns: {', '.join(sorted(missing_columns))}")

        expected_keys = read_csv_keys(DATA_DIR / filename)
        rows = list(client.records.list(
            table_name,
            select=[f"{table_name}id", "mag_demokey"],
            top=5000,
        ))
        actual_keys = {row["mag_demokey"] for row in rows if row.get("mag_demokey")}
        if actual_keys != expected_keys:
            missing = sorted(expected_keys - actual_keys)
            unexpected = sorted(actual_keys - expected_keys)
            raise RuntimeError(
                f"{table_name} key mismatch; missing={missing}, unexpected={unexpected}"
            )
        expected_total += len(expected_keys)
        print(f"PASS {table_name}: {len(actual_keys)} seeded rows, solution member, columns present.")

    choice_spec = json.loads((ROOT / "schema" / "choices.json").read_text(encoding="utf-8"))
    choice_values = {
        key: dict(zip(value["options"], value["values"]))
        for key, value in choice_spec.items()
    }
    request_rows = list(client.records.list(
        "mag_financialreviewrequest",
        select=["mag_reviewpath", "mag_gsaprecheckresult", "mag_cofacewithin18months", "mag_finalrating"],
        top=5000,
    ))
    path_field = choice_values["review_path"]
    expected_paths = {
        path_field["GSA Reuse"]: 3,
        path_field["Coface Fast-Track"]: 2,
        path_field["Full Review"]: 7,
    }
    for value, expected in expected_paths.items():
        actual = sum(row.get("mag_reviewpath") == value for row in request_rows)
        if actual != expected:
            raise RuntimeError(f"Review path {value} expected {expected} rows, found {actual}")

    no_duns = [
        row for row in request_rows
        if row.get("mag_gsaprecheckresult") == choice_values["gsa_precheck"]["Skip - no DUNS"]
    ]
    if len(no_duns) != 2 or any(row.get("mag_cofacewithin18months") for row in no_duns):
        raise RuntimeError("No-DUNS requests do not preserve the full-review disclaimer path")
    finalized = [row for row in request_rows if row.get("mag_finalrating") is not None]
    if len(finalized) != 3:
        raise RuntimeError(f"Expected only 3 GSA-reuse final ratings; found {len(finalized)}")

    print(
        f"PASS end-to-end verification: {len(SEED_FILES)} tables, "
        f"{expected_total} rows, 17 solution table roots, expected branch counts."
    )


if __name__ == "__main__":
    main()
