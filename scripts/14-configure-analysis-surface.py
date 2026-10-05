"""Expose draft agent analysis on the existing DemoPRE review-request form.

Source: apps/supplier-financial-risk-review/analysis-surface.json.
Requirements SRM-FIN-001, SRM-NFR-001, SRM-GOV-001; slides 8-9, 11-12.
Adds a read-only narrative and related result grids without changing rating controls.
Uses SDK record CRUD and managed Dataverse CLI actions. No solution XML is edited.

Usage: python scripts/14-configure-analysis-surface.py [--validate-only | --dry-run]
Requires the shared Dataverse skills auth.py on PYTHONPATH for live operations.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps" / "supplier-financial-risk-review" / "analysis-surface.json"
FORM_ID = "dca725c5-6378-4ad7-9446-68e4bbd8af69"
TABLE = "mag_financialreviewrequest"
APP = "mag_supplierfinancialriskreview"
NAMESPACE = uuid.UUID("4bd302d4-a7ad-46fa-8b6e-ce0b2d274da3")
GRID_CLASS = "{E7A81278-8635-4D9E-8D4D-59480B391C5B}"
MEMO_CLASS = "{E0DECE4B-6FC8-4A8F-A065-082708572369}"


def identifier(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, name))


def labeled(parent: ET.Element, tag: str, name: str, label: str, **attrs) -> ET.Element:
    attributes = {"id": identifier(name), **attrs}
    if tag != "cell":
        attributes["name"] = name
    node = ET.SubElement(parent, tag, attributes)
    ET.SubElement(ET.SubElement(node, "labels"), "label",
                  {"description": label, "languagecode": "1033"})
    return node


def fetch_and_layout(view: dict, object_type: int) -> tuple[str, str]:
    table = view["table"]
    fetch = ET.Element("fetch", {"version": "1.0", "mapping": "logical"})
    entity = ET.SubElement(fetch, "entity", {"name": table})
    for column in [f"{table}id", *view["columns"]]:
        ET.SubElement(entity, "attribute", {"name": column})
    ET.SubElement(entity, "order", {"attribute": "createdon", "descending": "true"})
    ET.SubElement(ET.SubElement(entity, "filter"), "condition",
                  {"attribute": "statecode", "operator": "eq", "value": "0"})
    grid = ET.Element("grid", {"name": "resultset", "object": str(object_type),
                              "jump": "mag_name", "select": "1", "icon": "1", "preview": "1"})
    row = ET.SubElement(grid, "row", {"name": "result", "id": f"{table}id"})
    for column in view["columns"]:
        ET.SubElement(row, "cell", {"name": column,
                                   "width": "400" if column.endswith(("details", "flags")) else "150"})
    return ET.tostring(fetch, encoding="unicode"), ET.tostring(grid, encoding="unicode")


def normalized_xml(xml: str) -> str:
    root = ET.fromstring(xml)
    root.attrib.pop("savedqueryid", None)
    return ET.tostring(root, encoding="unicode")


def analysis_tab(config: dict) -> ET.Element:
    holder = ET.Element("tabs")
    tab = labeled(holder, "tab", config["tabName"], config["tabLabel"],
                  expanded="true", visible="true")
    sections = ET.SubElement(ET.SubElement(ET.SubElement(tab, "columns"), "column",
                                          {"width": "100%"}), "sections")
    section = labeled(sections, "section", "sec_agent_narrative",
                      "AI Narrative Draft - Not Approved", showlabel="true",
                      visible="true", columns="1")
    rows = ET.SubElement(section, "rows")
    cell = labeled(ET.SubElement(rows, "row"), "cell", "cell_agent_narrative",
                   "Narrative Draft", showlabel="true", visible="true", rowspan="8", colspan="1")
    ET.SubElement(cell, "control", {"id": identifier("control_agent_narrative"),
                                  "classid": MEMO_CLASS, "datafieldname": "mag_narrativedraft",
                                  "disabled": "true", "isrequired": "false"})
    for _ in range(7):
        ET.SubElement(rows, "row")
    for view in config["views"]:
        table = view["table"]
        section = labeled(sections, "section", f"sec_analysis_{table}", view["label"],
                          showlabel="true", visible="true", columns="1")
        rows = ET.SubElement(section, "rows")
        cell = labeled(ET.SubElement(rows, "row"), "cell", f"cell_analysis_{table}",
                       view["label"], showlabel="false", visible="true", rowspan="8", colspan="1")
        control = ET.SubElement(cell, "control", {"id": identifier(f"grid_{table}"),
                                                "classid": GRID_CLASS, "disabled": "false",
                                                "isrequired": "false"})
        params = ET.SubElement(control, "parameters")
        values = {
            "TargetEntityType": table,
            "ViewId": identifier(f"view_{table}"),
            "IsUserView": "false",
            "RelationshipName": f"{TABLE}_{table}_mag_ReviewRequestId",
            "ChartGridMode": "Grid",
            "RecordsPerPage": "5",
            "EnableViewPicker": "false",
        }
        for name, value in values.items():
            ET.SubElement(params, name).text = value
        for _ in range(7):
            ET.SubElement(rows, "row")
    return tab


def mutate_form(xml: str, config: dict) -> str:
    form = ET.fromstring(xml)
    tabs = form.find("tabs")
    if tabs is None:
        raise RuntimeError("Existing main form has no tabs.")
    desired = analysis_tab(config)
    existing = next((tab for tab in tabs if tab.get("name") == config["tabName"]), None)
    index = list(tabs).index(existing) if existing is not None else len(tabs)
    if existing is not None:
        tabs.remove(existing)
    tabs.insert(index, desired)
    return ET.tostring(form, encoding="unicode")


def validate(config: dict) -> None:
    for view in config["views"]:
        paths = list((ROOT / "schema" / "tables").glob("*.json"))
        schemas = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
        schema = next(s for s in schemas if s["logicalName"] == view["table"])
        columns = {f"mag_{c['name']}".lower() for c in schema["columns"]} | {"mag_name"}
        if set(view["columns"]) - columns:
            raise RuntimeError(f"Unknown surface columns: {view['table']}")
    tab = analysis_tab(config)
    ids = [node.get("id") for node in tab.iter() if node.get("id")]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate analysis surface IDs.")
    xml = "<form><tabs><tab name='original' /></tabs></form>"
    first = mutate_form(xml, config)
    if mutate_form(first, config) != first:
        raise RuntimeError("Form mutation is not idempotent.")
    for view in config["views"]:
        fetch, layout = fetch_and_layout(view, 10000)
        ET.fromstring(fetch)
        ET.fromstring(layout)
    print("Validated surface columns, XML, unique IDs, and idempotent form mutation.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = json.loads(SOURCE.read_text(encoding="utf-8"))
    validate(config)
    if args.validate_only:
        return
    spec = importlib.util.spec_from_file_location(
        "membership", ROOT / "scripts" / "12-add-orchestrator-to-solution.py")
    membership = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(membership)
    membership.active_demo_pre_profile()
    if os.environ.get("DATAVERSE_URL", membership.ENVIRONMENT).rstrip("/") != membership.ENVIRONMENT:
        raise RuntimeError("Refusing non-DemoPRE environment.")
    os.environ["DATAVERSE_URL"] = membership.ENVIRONMENT
    from auth import get_client
    client = get_client("dv-metadata")

    def action(name: str, body: dict) -> None:
        result = membership.dataverse_run([
            "api", "request", "--target", "dataverse", "--method", "POST",
            "--path", f"/api/data/v9.2/{name}", "--body", json.dumps(body),
            "--environment", membership.ENVIRONMENT])
        if result.returncode:
            raise RuntimeError(f"{name} failed: {result.stderr or result.stdout}")

    app = list(client.records.list("appmodule", select=["appmoduleid"],
                                   filter=f"uniquename eq '{APP}'"))
    form = list(client.records.list("systemform", select=["formxml", "objecttypecode"],
                                    filter=f"formid eq {FORM_ID}"))
    if len(app) != 1 or len(form) != 1 or form[0]["objecttypecode"] != TABLE:
        raise RuntimeError("Expected app/main form identity not found.")
    components = []
    for view in config["views"]:
        table = view["table"]
        result = membership.dataverse_run([
            "api", "request", "--target", "dataverse", "--method", "GET",
            "--path", f"/api/data/v9.2/EntityDefinitions(LogicalName='{table}')?%24select=ObjectTypeCode,MetadataId",
            "--environment", membership.ENVIRONMENT])
        if result.returncode:
            raise RuntimeError(f"Table metadata failed: {result.stderr or result.stdout}")
        metadata = json.loads(result.stdout)
        fetch, layout = fetch_and_layout(view, metadata["ObjectTypeCode"])
        view_id = identifier(f"view_{table}")
        existing = list(client.records.list("savedquery", select=["savedqueryid", "fetchxml", "layoutxml"],
                                             filter=f"savedqueryid eq {view_id}"))
        body = {"name": view["label"], "returnedtypecode": table, "querytype": 0,
                "fetchxml": fetch, "layoutxml": layout, "isdefault": False}
        if args.dry_run:
            print(f"Would ensure view {view_id}: {view['label']}")
            continue
        if existing:
            client.records.update("savedquery", view_id, body)
        else:
            client.records.create("savedquery", {"savedqueryid": view_id, **body})
        saved = list(client.records.list("savedquery", select=["fetchxml", "layoutxml"],
                                         filter=f"savedqueryid eq {view_id}"))
        if len(saved) != 1 or normalized_xml(saved[0]["fetchxml"]) != normalized_xml(fetch) \
                or normalized_xml(saved[0]["layoutxml"]) != normalized_xml(layout):
            raise RuntimeError(f"View readback failed: {table}")
        action("AddSolutionComponent", {"ComponentId": view_id, "ComponentType": 26,
                                       "SolutionUniqueName": membership.SOLUTION,
                                       "AddRequiredComponents": False})
        components += [{"@odata.type": "Microsoft.Dynamics.CRM.entity", "entityid": metadata["MetadataId"]},
                       {"@odata.type": "Microsoft.Dynamics.CRM.savedquery", "savedqueryid": view_id}]
    desired = mutate_form(form[0]["formxml"], config)
    if args.dry_run:
        print("Would update and publish Agent Analysis Draft tab and app components.")
        return
    client.records.update("systemform", FORM_ID, {"formxml": desired})
    action("AddSolutionComponent", {"ComponentId": FORM_ID, "ComponentType": 60,
                                   "SolutionUniqueName": membership.SOLUTION,
                                   "AddRequiredComponents": False})
    action("AddAppComponents", {"AppId": app[0]["appmoduleid"], "Components": components})
    entities = "".join(f"<entity>{t}</entity>" for t in [TABLE, *[v["table"] for v in config["views"]]])
    action("PublishXml", {"ParameterXml": f"<importexportxml><entities>{entities}</entities>"
                          f"<appmodules><appmodule>{app[0]['appmoduleid']}</appmodule></appmodules>"
                          "</importexportxml>"})
    present = membership.web_api_get(
        f"/api/data/v9.2/RetrieveAppComponents(AppModuleId={app[0]['appmoduleid']})")
    component_ids = {row["objectid"].lower() for row in present}
    missing = [identifier(f"view_{view['table']}") for view in config["views"]
               if identifier(f"view_{view['table']}") not in component_ids]
    if missing:
        raise RuntimeError(f"App component readback missing analysis views: {missing}")
    readback = list(client.records.list("systemform", select=["formxml"], filter=f"formid eq {FORM_ID}"))
    if mutate_form(readback[0]["formxml"], config) != ET.tostring(
            ET.fromstring(readback[0]["formxml"]), encoding="unicode"):
        raise RuntimeError("Form readback did not preserve the configured analysis tab.")
    print("Verified Agent Analysis Draft tab, three result views, app components and publication.")
    print("No final rating, approval, working-paper or risk records were changed.")


if __name__ == "__main__":
    main()
