"""Configure the Stage 1 Financial Review Request forms: data checks, business rules and indicators.

Applies, idempotently, in DemoPRE (SRMAgentDemo solution):

1. Choice option colors from apps/supplier-financial-risk-review/indicator-colors.json
   (OptionMetadata.Color), used by the status panel and the form script.
2. Web resources mag_/srm/reviewrequest.js (form logic) and mag_/srm/reviewrequest-status.html
   (status panel) from apps/supplier-financial-risk-review/webresources/.
3. The main and quick-create request forms: the form library and onload handler, No DUNS rendered
   as a toggle, and on the main form a "Review Status" section at the top of the Request tab
   hosting the status panel (rowspan 2, one row of cards).
4. App components: the Supplier Financial Review BPF and the quick-create form, which the app build
   does not add. Without them the app hides the BPF stage bar and the quick-create form.

Requirements: SRM-INT-006, SRM-INT-007, SRM-GOV-003, SRM-UX-001 (docs/03-model-driven-app.md).
Use --dry-run to show the planned changes without writing.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from auth import get_token

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "apps" / "supplier-financial-risk-review"
SOLUTION = "SRMAgentDemo"
TABLE = "mag_financialreviewrequest"
MAIN_FORM = "dca725c5-6378-4ad7-9446-68e4bbd8af69"
QUICK_CREATE_FORM = "61ec32ed-56a9-478b-84f1-a01d4d235214"
LIBRARY = "mag_/srm/reviewrequest.js"
PANEL = "mag_/srm/reviewrequest-status.html"
PANEL_CONTROL = "WebResource_srm_status"
PANEL_SECTION = "sec_status"
PANEL_TAB = "tab_request"
ONLOAD_HANDLER = "SRM.ReviewRequest.onLoad"
APP_MODULE = "mag_supplierfinancialriskreview"
BPF_NAME = "Supplier Financial Review"
WEB_RESOURCE_CONTROL = "{9FDF5F91-88B1-47f4-AD53-C11EFC01A01D}"
# Toggle markup as the platform writes it: a custom-control host cell over the Boolean base control.
CUSTOM_CONTROL_HOST = "{F9A8A302-114E-466A-B582-6771B2AE0D92}"
BOOLEAN_BASE_CONTROL = "{67FAC785-CD58-4F9F-ABB3-4B7DDC6ED5ED}"
TOGGLE_CONTROL = "MscrmControls.FieldControls.ToggleControl"
TOGGLE_FIELDS = {"mag_noduns"}
PANEL_ROWSPAN = 3
COFACE_TAB = "tab_coface"
CLASS_TEXT, CLASS_CHOICE, CLASS_DATE = "{4273EDBD-AC1D-40D3-9FB2-095C621B552D}", "{3EF39988-22BB-4F0B-BBBE-64B5A3748AEE}", "{5B773807-9FB2-42DB-97C3-7A91EFF8ADFF}"
CLASS_INT, CLASS_BOOL = "{C6D124CA-7EDA-4A60-AEA9-7FB8D318B68F}", "{67FAC785-CD58-4F9F-ABB3-4B7DDC6ED5ED}"
# Stage 2 read-only sections: (section name, label, [(column, label, classid)]). Flows write these.
COFACE_SECTIONS = [
    ("sec_coface_result", "Coface Retrieval (flow-populated)", [
        ("mag_cofaceretrieved", "Coface Retrieved", CLASS_BOOL),
        ("mag_cofacescore", "Coface Score (0-10, higher is safer)", CLASS_INT),
        ("mag_cofacerisktier", "Coface Risk Tier", CLASS_CHOICE),
        ("mag_cofaceassessmentdate", "Coface Assessment Date", CLASS_DATE),
        ("mag_cofacedataagemonths", "Data Age (months)", CLASS_INT),
        ("mag_cofacewithin18months", "Within 18 Months", CLASS_BOOL)]),
    ("sec_coface_proposal", "Rating Proposal (AI, reviewer decides)", [
        ("mag_preliminaryrating", "Preliminary Rating", CLASS_CHOICE),
        ("mag_reviewpath", "Review Path", CLASS_CHOICE)]),
]
WEB_RESOURCE_COMPONENT = 61
WEB_RESOURCES = [
    # (name, display name, file, webresourcetype: 1 = HTML, 3 = JScript)
    (LIBRARY, "SRM Review Request form logic", APP_DIR / "webresources" / "reviewrequest.js", 3),
    (PANEL, "SRM Review Request status panel", APP_DIR / "webresources" / "reviewrequest-status.html", 1),
]
# Deterministic ids keep the form XML stable across reruns.
NAMESPACE = uuid.UUID("7d3c2a4e-5b1f-4f7a-9a0e-2c6b8d1e4f10")
URL_SAFE = "/?$=&(),'"


def stable_id(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, name))


def web_api(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> dict | None:
    request = urllib.request.Request(
        f"{os.environ['DATAVERSE_URL'].rstrip('/')}/api/data/v9.2/{urllib.parse.quote(path, safe=URL_SAFE)}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {get_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            **(headers or {}),
        },
    )
    for attempt in range(1, 7):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
            return json.loads(payload) if payload else None
        except urllib.error.HTTPError as error:
            message = error.read().decode("utf-8", "replace")[:800]
            if "still being processed" in message and attempt < 6:
                time.sleep(attempt * 10)
                continue
            raise RuntimeError(f"{method} {path} failed with {error.code}: {message}") from error
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 6:
                raise
            time.sleep(attempt * 10)
    return None


# ---- choice colors ---------------------------------------------------------------------------

def choice_columns() -> list[tuple[str, str, str]]:
    """(table, column, choice) for every schema choice column."""
    result = []
    for path in sorted((ROOT / "schema" / "tables").glob("*.json")):
        table = json.loads(path.read_text(encoding="utf-8"))
        for column in table["columns"]:
            if column["type"] == "choice":
                result.append((table["logicalName"], f"mag_{column['name']}".lower(), column["choice"]))
    return result


def ensure_option_colors(dry_run: bool) -> set[str]:
    colors = json.loads((APP_DIR / "indicator-colors.json").read_text(encoding="utf-8"))["choices"]
    labels = {name: spec["options"] for name, spec in
              json.loads((ROOT / "schema" / "choices.json").read_text(encoding="utf-8")).items()}
    changed_tables: set[str] = set()
    for table, column, choice in choice_columns():
        if choice not in colors:
            continue
        options = web_api(
            "GET",
            f"EntityDefinitions(LogicalName='{table}')/Attributes(LogicalName='{column}')"
            "/Microsoft.Dynamics.CRM.PicklistAttributeMetadata?$select=LogicalName&$expand=OptionSet($select=Options)",
        )["OptionSet"]["Options"]
        for option in options:
            label = labels[choice][option["Value"] - 100000000]
            wanted = colors[choice].get(label)
            if not wanted or (option.get("Color") or "").upper() == wanted.upper():
                continue
            print(f"Color {table}.{column} '{label}': {option.get('Color')!r} -> {wanted}")
            if dry_run:
                continue
            web_api("POST", "UpdateOptionValue", {
                "EntityLogicalName": table,
                "AttributeLogicalName": column,
                "Value": option["Value"],
                "Label": {
                    "@odata.type": "Microsoft.Dynamics.CRM.Label",
                    "LocalizedLabels": [{
                        "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                        "Label": label,
                        "LanguageCode": 1033,
                    }],
                },
                "Color": wanted,
                "MergeLabels": True,
                "SolutionUniqueName": SOLUTION,
            })
            changed_tables.add(table)
    print(f"Option colors converged ({len(changed_tables)} tables changed).")
    return changed_tables


# ---- web resources ---------------------------------------------------------------------------

def solution_web_resources() -> set[str]:
    solution = web_api("GET", f"solutions?$select=solutionid&$filter=uniquename eq '{SOLUTION}'")["value"][0]
    rows = web_api(
        "GET",
        "solutioncomponents?$select=objectid"
        f"&$filter=_solutionid_value eq {solution['solutionid']} and componenttype eq {WEB_RESOURCE_COMPONENT}",
    )["value"]
    return {row["objectid"].lower() for row in rows}


def find_web_resource(name: str) -> dict | None:
    rows = web_api("GET", f"webresourceset?$select=webresourceid,content&$filter=name eq '{name}'")["value"]
    return rows[0] if rows else None


def ensure_web_resources(dry_run: bool) -> tuple[dict[str, str], list[str]]:
    ids: dict[str, str] = {}
    changed: list[str] = []
    members = solution_web_resources()
    for name, display, path, kind in WEB_RESOURCES:
        content = base64.b64encode(path.read_bytes()).decode("ascii")
        existing = find_web_resource(name)
        if existing is None:
            print(f"Create web resource {name}")
            if dry_run:
                ids[name] = "00000000-0000-0000-0000-000000000000"
                continue
            web_api("POST", "webresourceset", {
                "name": name,
                "displayname": display,
                "webresourcetype": kind,
                "content": content,
            }, {"MSCRM.SolutionUniqueName": SOLUTION})
            existing = find_web_resource(name)
            changed.append(existing["webresourceid"])
            members.add(existing["webresourceid"].lower())
        elif existing["content"] != content:
            print(f"Update web resource {name}")
            if not dry_run:
                web_api("PATCH", f"webresourceset({existing['webresourceid']})", {"content": content})
                changed.append(existing["webresourceid"])
        ids[name] = existing["webresourceid"]
        if existing["webresourceid"].lower() not in members:
            print(f"Add web resource {name} to {SOLUTION}")
            if not dry_run:
                web_api("POST", "AddSolutionComponent", {
                    "ComponentId": existing["webresourceid"],
                    "ComponentType": WEB_RESOURCE_COMPONENT,
                    "SolutionUniqueName": SOLUTION,
                    "AddRequiredComponents": False,
                })
    print(f"Web resources converged ({len(changed)} created or updated).")
    return ids, changed


# ---- forms -----------------------------------------------------------------------------------

def child(parent: ET.Element, tag: str, attrs: dict | None = None, index: int | None = None) -> ET.Element:
    element = ET.Element(tag, attrs or {})
    if index is None:
        parent.append(element)
    else:
        parent.insert(index, element)
    return element


def labels(parent: ET.Element, text: str) -> None:
    child(child(parent, "labels"), "label", {"description": text, "languagecode": "1033"})


def ensure_library_and_onload(form: ET.Element) -> bool:
    changed = False
    libraries = form.find("formLibraries")
    if libraries is None:
        libraries = child(form, "formLibraries", index=list(form).index(form.find("tabs")) + 1)
    if not any(lib.get("name") == LIBRARY for lib in libraries.findall("Library")):
        child(libraries, "Library", {"name": LIBRARY, "libraryUniqueId": "{" + stable_id(LIBRARY) + "}"})
        changed = True
    events = form.find("events")
    if events is None:
        events = child(form, "events", index=list(form).index(libraries) + 1)
    onload = next((e for e in events.findall("event") if e.get("name") == "onload"), None)
    if onload is None:
        onload = child(events, "event", {"name": "onload", "application": "false", "active": "false"})
    handlers = onload.find("Handlers")
    if handlers is None:
        handlers = child(onload, "Handlers")
    if not any(h.get("functionName") == ONLOAD_HANDLER for h in handlers.findall("Handler")):
        child(handlers, "Handler", {
            "functionName": ONLOAD_HANDLER,
            "libraryName": LIBRARY,
            "handlerUniqueId": "{" + stable_id(ONLOAD_HANDLER) + "}",
            "enabled": "true",
            "parameters": "",
            "passExecutionContext": "true",
        })
        changed = True
    return changed


def ensure_status_panel(form: ET.Element, panel_id: str) -> bool:
    tab = next(t for t in form.iter("tab") if t.get("name") == PANEL_TAB)
    sections = tab.find("columns/column/sections")
    existing = next((s for s in sections.findall("section") if s.get("name") == PANEL_SECTION), None)
    if existing is not None:
        return converge_panel_height(existing)
    section = child(sections, "section", {
        "id": stable_id(PANEL_SECTION), "name": PANEL_SECTION, "showlabel": "true",
        "visible": "true", "columns": "1",
    }, index=0)
    labels(section, "Review Status")
    rows = child(section, "rows")
    cell = child(child(rows, "row"), "cell", {
        "id": stable_id(PANEL_CONTROL), "showlabel": "false", "visible": "true",
        "colspan": "1", "rowspan": str(PANEL_ROWSPAN), "auto": "false",
    })
    labels(cell, "Review status indicators")
    control = child(cell, "control", {"id": PANEL_CONTROL, "classid": WEB_RESOURCE_CONTROL})
    parameters = child(control, "parameters")
    for tag, text in [
        ("Url", PANEL), ("PassParameters", "false"), ("ShowOnMobileClient", "true"),
        ("Security", "false"), ("Scrolling", "auto"), ("Border", "false"),
        ("WebResourceId", "{" + panel_id + "}"),
    ]:
        child(parameters, tag).text = text
    for _ in range(PANEL_ROWSPAN - 1):
        child(rows, "row")
    return True


def converge_panel_height(section: ET.Element) -> bool:
    """One row of cards needs a rowspan of 2; the spanned rows must exist as empty rows."""
    rows = section.find("rows")
    cell = next(c for c in rows.iter("cell") if c.get("id") == stable_id(PANEL_CONTROL))
    extra = [r for r in rows.findall("row") if not list(r)]
    if cell.get("rowspan") == str(PANEL_ROWSPAN) and len(extra) == PANEL_ROWSPAN - 1:
        return False
    cell.set("rowspan", str(PANEL_ROWSPAN))
    for row in extra:
        rows.remove(row)
    for _ in range(PANEL_ROWSPAN - 1):
        child(rows, "row")
    return True


def ensure_coface_tab(form: ET.Element) -> bool:
    tabs = form.find("tabs")
    if any(t.get("name") == COFACE_TAB for t in tabs.findall("tab")):
        return False
    anchor = next(i for i, t in enumerate(tabs.findall("tab")) if t.get("name") == "tab_precheck")
    tab = child(tabs, "tab", {"id": stable_id(COFACE_TAB), "name": COFACE_TAB, "expanded": "true", "visible": "true"},
                index=anchor + 1)
    labels(tab, "Coface")
    sections = child(child(child(tab, "columns"), "column", {"width": "100%"}), "sections")
    for name, title, fields in COFACE_SECTIONS:
        section = child(sections, "section", {"id": stable_id(name), "name": name, "showlabel": "true",
                                              "visible": "true", "columns": "2"})
        labels(section, title)
        rows = child(section, "rows")
        for start in range(0, len(fields), 2):
            row = child(rows, "row")
            for column, label, classid in fields[start:start + 2]:
                cell = child(row, "cell", {"id": stable_id(f"cell-{column}"), "showlabel": "true",
                                           "visible": "true", "colspan": "1", "rowspan": "1"})
                labels(cell, label)
                child(cell, "control", {"id": stable_id(f"control-{column}"), "classid": classid,
                                        "datafieldname": column, "disabled": "true", "isrequired": "false"})
    return True


def ensure_toggle_controls(form: ET.Element) -> bool:
    """Render Boolean check-offs such as No DUNS as a toggle instead of a True/False dropdown.

    Mirrors the platform's own toggle markup: the cell control uses the custom-control host
    classid plus a braced uniqueid, and a controlDescription for that uniqueid binds the platform
    ToggleControl for every form factor (0 = web, 1 = tablet, 2 = phone) over the Boolean base.
    """
    changed = False
    root = form.find("form") if form.find("form") is not None else form
    descriptions = root.find("controlDescriptions")
    for control in list(form.iter("control")):
        field = control.get("datafieldname")
        if field not in TOGGLE_FIELDS:
            continue
        unique_id = "{" + control.get("id").strip("{}").lower() + "}"
        if control.get("classid") != CUSTOM_CONTROL_HOST or control.get("uniqueid") != unique_id:
            control.set("classid", CUSTOM_CONTROL_HOST)
            control.set("uniqueid", unique_id)
            changed = True
        existing = [] if descriptions is None else [
            d for d in descriptions.findall("controlDescription")
            if d.get("forControl", "").strip("{}").lower() == unique_id.strip("{}")]
        if any(d.get("forControl") == unique_id
               and any(c.get("id") == BOOLEAN_BASE_CONTROL for c in d.findall("customControl"))
               for d in existing):
            continue
        for stale in existing:
            descriptions.remove(stale)
        if descriptions is None:
            descriptions = child(root, "controlDescriptions")
        description = child(descriptions, "controlDescription", {"forControl": unique_id})
        base = child(description, "customControl", {"id": BOOLEAN_BASE_CONTROL})
        child(child(base, "parameters"), "datafieldname").text = field
        for factor in ("0", "1", "2"):
            custom = child(description, "customControl", {"formFactor": factor, "name": TOGGLE_CONTROL})
            child(child(custom, "parameters"), "value", {"type": "TwoOptions"}).text = field
        changed = True
    return changed


def ensure_quickcreate_system_fields(form: ET.Element) -> bool:
    """Keep route/result attributes loaded for the quick-create No DUNS rule without showing them."""
    form_element = form.find("form")
    tabs = (form_element if form_element is not None else form).find("tabs")
    if tabs is None or not list(tabs):
        raise RuntimeError("Quick Create form has no tab to host system fields")
    tab = list(tabs)[0]
    sections = tab.find("columns/column/sections")
    if sections is None:
        raise RuntimeError("Quick Create tab has no sections")
    existing = {
        control.get("datafieldname")
        for control in form.iter("control")
        if control.get("datafieldname")
    }
    needed = [
        ("mag_gsaprecheckresult", "GSA Financial Rating Auto-Check Result", "{3EF39988-22BB-4F0B-BBBE-64B5A3748AEE}"),
        ("mag_reviewpath", "Review Path", "{3EF39988-22BB-4F0B-BBBE-64B5A3748AEE}"),
        ("mag_reviewstatus", "Review Status", "{3EF39988-22BB-4F0B-BBBE-64B5A3748AEE}"),
    ]
    missing = [entry for entry in needed if entry[0] not in existing]
    if not missing:
        return False
    section = next((s for s in sections.findall("section")
                    if s.get("name") == "sec_system_values"), None)
    if section is None:
        section = child(sections, "section", {
            "id": stable_id("quickcreate-system-fields"),
            "name": "sec_system_values",
            "showlabel": "false",
            "visible": "false",
            "columns": "1",
        })
        labels(section, "System values")
    rows = section.find("rows")
    if rows is None:
        rows = child(section, "rows")
    for name, label, classid in missing:
        row = child(rows, "row")
        cell = child(row, "cell", {
            "id": stable_id(name),
            "showlabel": "false",
            "visible": "false",
            "colspan": "1",
            "rowspan": "1",
        })
        labels(cell, label)
        child(cell, "control", {
            "id": stable_id("control-" + name),
            "classid": classid,
            "datafieldname": name,
            "disabled": "true",
            "isrequired": "false",
        })
    return True


def ensure_form(form_id: str, panel_id: str | None, dry_run: bool) -> bool:
    record = web_api("GET", f"systemforms({form_id})?$select=name,formxml")
    form = ET.fromstring(record["formxml"])
    changed = ensure_library_and_onload(form)
    changed = ensure_toggle_controls(form) or changed
    if panel_id:
        changed = ensure_status_panel(form, panel_id) or changed
        changed = ensure_coface_tab(form) or changed
    else:
        changed = ensure_quickcreate_system_fields(form) or changed
    if not changed:
        print(f"Form '{record['name']}' already configured.")
        return False
    print(f"Update form '{record['name']}'")
    if not dry_run:
        web_api("PATCH", f"systemforms({form_id})", {"formxml": ET.tostring(form, encoding="unicode")})
    return True


def verify_form(form_id: str, expect_panel: bool) -> None:
    formxml = web_api("GET", f"systemforms({form_id})?$select=formxml")["formxml"]
    expected = [f'name="{LIBRARY}"', f'functionName="{ONLOAD_HANDLER}"']
    if expect_panel:
        expected += [f'id="{PANEL_CONTROL}"', f"<Url>{PANEL}</Url>"]
    missing = [text for text in expected if text not in formxml]
    if missing:
        raise RuntimeError(f"Form {form_id} is missing {missing}")
    form = ET.fromstring(formxml)
    dropdowns = [c.get("datafieldname") for c in form.iter("control")
                 if c.get("datafieldname") in TOGGLE_FIELDS and c.get("classid") != CUSTOM_CONTROL_HOST]
    if dropdowns:
        raise RuntimeError(f"Form {form_id} does not render {dropdowns} as a toggle")
    if formxml.count(TOGGLE_CONTROL) < 3 * len(TOGGLE_FIELDS):
        raise RuntimeError(f"Form {form_id} is missing the toggle control description")
    if expect_panel:
        coface = {c.get("datafieldname") for tab in form.iter("tab") if tab.get("name") == COFACE_TAB for c in tab.iter("control")}
        needed = {c for _, _, fields in COFACE_SECTIONS for c, _, _ in fields}
        if needed - coface:
            raise RuntimeError(f"Form {form_id} Coface tab is missing {sorted(needed - coface)}")
        cell = next(c for c in form.iter("cell") if c.get("id") == stable_id(PANEL_CONTROL))
        if cell.get("rowspan") != str(PANEL_ROWSPAN):
            raise RuntimeError(f"Form {form_id} status panel rowspan is {cell.get('rowspan')}")
    if not expect_panel:
        section = next((s for s in form.iter("section")
                        if s.get("name") == "sec_system_values"), None)
        expected_fields = {"mag_gsaprecheckresult", "mag_reviewpath", "mag_reviewstatus"}
        if section is None or section.get("visible") != "false":
            raise RuntimeError(f"Quick Create form {form_id} is missing its hidden system-values section")
        controls = {c.get("datafieldname"): c for c in section.iter("control")}
        missing_fields = expected_fields - controls.keys()
        editable_fields = [name for name in expected_fields
                           if name in controls and controls[name].get("disabled") != "true"]
        if missing_fields or editable_fields:
            raise RuntimeError(
                f"Quick Create form {form_id} system fields are incomplete: "
                f"missing={sorted(missing_fields)}, editable={editable_fields}"
            )


# ---- app components --------------------------------------------------------------------------

def app_module_id() -> str:
    rows = web_api("GET", f"appmodules?$select=appmoduleid&$filter=uniquename eq '{APP_MODULE}'")["value"]
    if not rows:
        raise RuntimeError(f"App module {APP_MODULE} not found")
    return rows[0]["appmoduleid"]


def bpf_id() -> str:
    rows = web_api("GET", "workflows?$select=workflowid&$filter=category eq 4 and "
                          f"primaryentity eq '{TABLE}' and name eq '{BPF_NAME}' and type eq 1")["value"]
    if len(rows) != 1:
        raise RuntimeError(f"Expected one '{BPF_NAME}' business process flow, found {len(rows)}")
    return rows[0]["workflowid"]


def app_component_ids(app_id: str) -> set[str]:
    rows = web_api("GET", f"RetrieveAppComponents(AppModuleId={app_id})")["value"]
    return {row["objectid"].lower() for row in rows}


def ensure_app_components(dry_run: bool) -> str | None:
    """Model-driven apps only show BPFs and forms that are app components; the app build omits both."""
    app_id = app_module_id()
    present = app_component_ids(app_id)
    wanted = [("workflow", "workflowid", bpf_id(), "business process flow"),
              ("systemform", "formid", QUICK_CREATE_FORM, "quick-create form")]
    missing = [w for w in wanted if w[2].lower() not in present]
    if not missing:
        print("App components already include the BPF and quick-create form.")
        return None
    for _, _, _, label in missing:
        print(f"Add {label} to app {APP_MODULE}")
    if dry_run:
        return None
    web_api("POST", "AddAppComponents", {
        "AppId": app_id,
        "Components": [{"@odata.type": f"Microsoft.Dynamics.CRM.{t}", key: value}
                       for t, key, value, _ in missing],
    })
    return app_id


def verify_app_components() -> None:
    present = app_component_ids(app_module_id())
    missing = [name for name, cid in (("BPF", bpf_id()), ("quick-create form", QUICK_CREATE_FORM))
               if cid.lower() not in present]
    if missing:
        raise RuntimeError(f"App {APP_MODULE} is missing components {missing}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing.")
    args = parser.parse_args()

    color_tables = ensure_option_colors(args.dry_run)
    ids, changed_resources = ensure_web_resources(args.dry_run)
    forms_changed = ensure_form(MAIN_FORM, ids[PANEL], args.dry_run)
    forms_changed = ensure_form(QUICK_CREATE_FORM, None, args.dry_run) or forms_changed
    changed_app = ensure_app_components(args.dry_run)
    if args.dry_run:
        return

    entities = sorted(color_tables | ({TABLE} if forms_changed else set()))
    if entities or changed_resources or changed_app:
        xml = "<importexportxml>"
        xml += "<entities>" + "".join(f"<entity>{e}</entity>" for e in entities) + "</entities>"
        xml += "<webresources>" + "".join(f"<webresource>{{{i}}}</webresource>" for i in changed_resources) + "</webresources>"
        if changed_app:
            xml += f"<appmodules><appmodule>{{{changed_app}}}</appmodule></appmodules>"
        xml += "</importexportxml>"
        web_api("POST", "PublishXml", {"ParameterXml": xml})
        print(f"Published {', '.join(entities) or 'no entities'}, {len(changed_resources)} web resources"
              f"{' and the app' if changed_app else ''}.")

    verify_form(MAIN_FORM, expect_panel=True)
    verify_form(QUICK_CREATE_FORM, expect_panel=False)
    verify_app_components()
    print("Verified form libraries, onload handlers, the status panel and app components.")


if __name__ == "__main__":
    main()
