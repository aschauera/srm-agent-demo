"""Validate schema JSON and generated SRM demo CSV fixtures without a Dataverse connection."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schema" / "tables"
DATA_DIR = ROOT / "data"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> None:
    table_specs = {}
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        logical_name = spec["logicalName"]
        if logical_name in table_specs:
            fail(f"duplicate schema for {logical_name}")
        if not logical_name.startswith("mag_") or not spec["schemaName"].startswith("mag_"):
            fail(f"incorrect publisher prefix in {path.name}")
        if not any(column["name"] == "DemoKey" for column in spec["columns"]):
            fail(f"{logical_name} is missing DemoKey")
        field_names = [column["name"] for column in spec["columns"]]
        if len(field_names) != len(set(field_names)):
            fail(f"duplicate column in {logical_name}")
        if any(name.lower().endswith("id") for name in field_names):
            fail(f"regular column with Id suffix in {logical_name}; use a lookup instead")
        table_specs[logical_name] = spec

    if len(table_specs) != 17:
        fail(f"expected 17 planned tables, found {len(table_specs)}")

    choices = json.loads((ROOT / "schema" / "choices.json").read_text(encoding="utf-8"))
    for choice_name, choice in choices.items():
        if len(choice["options"]) != len(choice["values"]):
            fail(f"choice values mismatch for {choice_name}")
        if len(choice["values"]) != len(set(choice["values"])):
            fail(f"duplicate numeric choice value in {choice_name}")

    all_rows = {}
    for logical_name, spec in table_specs.items():
        filename = spec.get("seedFile")
        if not filename:
            # The seed filenames are stable project artifacts, mapped by table in README.
            filename = {
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
            }[logical_name]
        path = DATA_DIR / filename
        if not path.exists():
            fail(f"missing seed file {path.name}")
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            headers = reader.fieldnames or []
        expected = ["DemoKey", "Name"]
        expected.extend(column["name"] for column in spec["columns"] if column["name"] not in expected)
        expected.extend(f"{lookup['name']}DemoKey" for lookup in spec.get("lookups", []))
        if headers != expected:
            fail(f"CSV headers do not match {logical_name}: expected {expected}, got {headers}")
        keys = [row["DemoKey"] for row in rows]
        if len(keys) != len(set(keys)):
            fail(f"duplicate DemoKey in {path.name}")
        all_rows[logical_name] = {row["DemoKey"]: row for row in rows}

        choice_by_field = {
            column["name"]: choices[column["choice"]]["options"]
            for column in spec["columns"]
            if "choice" in column
        }
        for row_number, row in enumerate(rows, 2):
            for field_name, options in choice_by_field.items():
                if row.get(field_name) and row[field_name] not in options:
                    fail(f"invalid {field_name} choice {row[field_name]!r} in {path.name}:{row_number}")

    relationships = json.loads((ROOT / "schema" / "relationships.json").read_text(encoding="utf-8"))
    for relation in relationships:
        child = relation["referencingTable"]
        parent = relation["referencedTable"]
        if child not in table_specs or parent not in table_specs:
            fail(f"relationship references unknown table: {relation}")
        reference_column = f"{relation['lookupName']}DemoKey"
        for key, row in all_rows[child].items():
            reference = row.get(reference_column, "")
            if reference and reference not in all_rows[parent]:
                fail(f"unresolved {child}.{reference_column}={reference!r} on {key}")

    suppliers = list(all_rows["mag_supplier"].values())
    if len(suppliers) != 12:
        fail(f"expected 12 supplier scenarios, found {len(suppliers)}")
    requests = list(all_rows["mag_financialreviewrequest"].values())
    expected_paths = {"GSA Reuse": 3, "Coface Fast-Track": 2, "Full Review": 7}
    for path, expected_count in expected_paths.items():
        count = sum(row["ReviewPath"] == path for row in requests)
        if count != expected_count:
            fail(f"expected {expected_count} {path!r} requests, found {count}")
    summaries = list(all_rows["mag_supplieronepagesummary"].values())
    active_supplier_keys = {row["SupplierCode"] for row in suppliers if row["HasActiveSpend"] == "True"}
    summary_supplier_keys = {row["SupplierDemoKey"] for row in summaries}
    if summary_supplier_keys != active_supplier_keys:
        fail("One-Page Summary seed rows must match suppliers with active spend")

    for table in ("mag_ratingconversionrule", "mag_riskscoringrule"):
        for row in all_rows[table].values():
            if row["DemoOnly"] != "True" or row["ApprovalStatus"] != "Draft - demo only":
                fail(f"{table} seed rules must be marked demo-only and draft")

    row_count = sum(len(rows) for rows in all_rows.values())
    print(f"PASS: {len(table_specs)} tables, {len(relationships)} lookups, {row_count} seed rows.")


if __name__ == "__main__":
    main()
