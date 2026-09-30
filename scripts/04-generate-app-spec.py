"""Generate the Supplier Financial Risk Review app-builder spec from schema/ definitions."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apps" / "supplier-financial-risk-review" / "app-spec.json"
choices = json.loads((ROOT / "schema" / "choices.json").read_text(encoding="utf-8"))
TYPE = {"string": "Text", "text": "Memo", "boolean": "Boolean", "datetime": "DateTime",
        "integer": "Integer", "money": "Money", "decimal": "Decimal", "choice": "Choice"}

DESCRIPTIONS = {
    "mag_financialreviewrequest": "A buyer's request for a supplier financial rating; hosts the five-stage Supplier Financial Review process and the GSA pre-check outcome.",
    "mag_supplier": "Fictional supplier master; its D&B-sourced identity fields are shown on the review request so the buyer can confirm the auto-fill.",
    "mag_dnbprofile": "Mock D&B / public profile keyed by DUNS; the seeded source for Step 1 field auto-completion.",
    "mag_gsaratingrecord": "Mock GSA procurement rating keyed by DUNS; the seeded source for the Step 1 reuse pre-check.",
}
PLURAL = {
    "mag_financialreviewrequest": "Financial Review Requests",
    "mag_supplier": "Suppliers",
    "mag_dnbprofile": "D&B Profiles",
    "mag_gsaratingrecord": "GSA Rating Records",
}


def entity(file_stem):
    spec = json.loads((ROOT / "schema" / "tables" / f"{file_stem}.json").read_text(encoding="utf-8"))
    columns = []
    for column in spec["columns"]:
        entry = {"schemaName": f"mag_{column['name']}", "displayName": column["displayName"],
                 "type": TYPE[column["type"]]}
        if column["type"] == "choice":
            entry["options"] = choices[column["choice"]]["options"]
        columns.append(entry)
    return {
        "schemaName": spec["logicalName"],
        "displayName": spec["displayName"],
        "pluralName": PLURAL[spec["logicalName"]],
        "existing": True,
        "enrichDefaultViews": True,
        "description": DESCRIPTIONS[spec["logicalName"]],
        "primaryAttribute": {"schemaName": "mag_Name", "displayName": "Name"},
        "columns": columns,
    }


R = "mag_financialreviewrequest"
S = "mag_supplier"

spec = {
    "solution": {"uniqueName": "SRMAgentDemo", "displayName": "SRM Agent Demo", "publisherPrefix": "mag"},
    "app": {
        "name": "Supplier Financial Risk Review",
        "description": "Supplier Risk Management demo: buyers request supplier financial ratings and reviewers run the five-stage financial review. Step 1 (request and GSA/DUNS pre-check) slice.",
        "newLook": True,
    },
    "entities": [entity("financialreviewrequest"), entity("supplier"), entity("dnbprofile"), entity("gsaratingrecord")],
    "relationships": [
        {"type": "OneToMany", "referenced": S, "referencing": R,
         "schemaName": "mag_supplier_mag_financialreviewrequest_mag_SupplierId",
         "lookup": {"schemaName": "mag_SupplierId", "displayName": "Supplier"}},
        {"type": "OneToMany", "referenced": S, "referencing": "mag_dnbprofile",
         "schemaName": "mag_supplier_mag_dnbprofile_mag_SupplierId",
         "lookup": {"schemaName": "mag_SupplierId", "displayName": "Supplier"}},
        {"type": "OneToMany", "referenced": S, "referencing": "mag_gsaratingrecord",
         "schemaName": "mag_supplier_mag_gsaratingrecord_mag_SupplierId",
         "lookup": {"schemaName": "mag_SupplierId", "displayName": "Supplier"}},
    ],
    "views": [
        {"entity": R, "name": "My Open Reviews",
         "description": "Review requests I own that are not yet completed - the reviewer's Step 1 work queue.",
         "columns": ["mag_name", "mag_supplierid", "mag_gsaprecheckresult", "mag_reviewpath", "mag_reviewstatus", "mag_buyername", "createdon"],
         "sort": [{"attr": "createdon", "dir": "desc"}],
         "filters": [{"attr": "ownerid", "op": "eq-userid"},
                     {"attr": "mag_reviewstatus", "op": "ne", "value": "Completed"}]},
        {"entity": R, "name": "New Requests - Not Started",
         "description": "Submitted requests still at status Not Started: full review needed after the GSA pre-check (source slide 3).",
         "columns": ["mag_name", "mag_supplierid", "mag_dunsnumber", "mag_noduns", "mag_gsaprecheckresult", "mag_buyername", "createdon"],
         "sort": [{"attr": "createdon", "dir": "asc"}],
         "filters": [{"attr": "mag_reviewstatus", "op": "eq", "value": "Not Started"}]},
        {"entity": R, "name": "Auto-Closed (GSA Reuse)",
         "description": "Requests closed automatically by reusing a valid active GSA rating (Shortcut A, source slide 2).",
         "columns": ["mag_name", "mag_supplierid", "mag_gsarating", "mag_gsaratingdate", "mag_gsaratingexpiry", "mag_reviewername", "mag_buyernotified"],
         "sort": [{"attr": "mag_gsaratingdate", "dir": "desc"}],
         "filters": [{"attr": "mag_reviewpath", "op": "eq", "value": "GSA Reuse"}]},
        {"entity": R, "name": "Full Review Required",
         "description": "Open requests where GSA reuse criteria were not met (no match, expired, mandatory re-review, or no DUNS).",
         "columns": ["mag_name", "mag_supplierid", "mag_gsaprecheckresult", "mag_mandatoryrereview", "mag_noduns", "mag_reviewername", "mag_reviewstatus"],
         "sort": [{"attr": "mag_name", "dir": "asc"}],
         "filters": [{"attr": "mag_reviewpath", "op": "eq", "value": "Full Review"},
                     {"attr": "mag_reviewstatus", "op": "ne", "value": "Completed"}]},
        {"entity": R, "name": "Supplier Review History",
         "description": "All review requests for a supplier, newest first; used on the Supplier form.",
         "columns": ["mag_name", "mag_reviewpath", "mag_reviewstatus", "mag_finalrating", "mag_ratingdate", "createdon"],
         "sort": [{"attr": "createdon", "dir": "desc"}], "activeOnly": False},
    ],
    "webResources": [
        {"name": "mag_/srm/reviewrequest.js", "displayName": "SRM Review Request form logic",
         "type": "js", "contentPath": "webresources/reviewrequest.js"},
        {"name": "mag_/srm/reviewrequest-status.html", "displayName": "SRM Review Request status panel",
         "type": "html", "contentPath": "webresources/reviewrequest-status.html"},
    ],
    "forms": [
        {"entity": R, "type": "main", "formType": "Main", "name": "Financial Review Request", "isDefault": True,
         # prune=False keeps the status panel and form library added by 06-configure-review-request-form.py.
         "prune": False,
         "description": "Step 1 review request: buyer request details, DUNS identification with D&B auto-fill, and the GSA Financial Rating Auto-Check Result.",
         "events": [{"event": "onload", "library": "mag_/srm/reviewrequest.js",
                     "function": "SRM.ReviewRequest.onLoad"}],
         "quickViews": [{"lookup": "mag_supplierid", "targetEntity": S, "form": "Supplier D&B Profile",
                         "label": "Supplier Profile (D&B auto-fill)", "section": "sec_supplier_profile"}],
         "tabs": [
             {"name": "tab_request", "label": "Request", "sections": [
                 {"name": "sec_request", "label": "Request Details", "columns": 2, "fields": [
                     "mag_name", "mag_requestref", "mag_supplierid", "mag_division",
                     "mag_buyername", "mag_buyeremail",
                     {"name": "mag_reviewstatus", "readOnly": True}, {"name": "mag_reviewpath", "readOnly": True}]},
                 {"name": "sec_duns", "label": "Supplier Identification (DUNS)", "columns": 2, "fields": [
                     "mag_dunsnumber", "mag_noduns", "mag_dnbautofillconfirmed"]},
                 {"name": "sec_supplier_profile", "label": "Supplier Profile (D&B auto-fill)", "columns": 1, "fields": []},
             ]},
             {"name": "tab_precheck", "label": "Pre-Check", "sections": [
                 {"name": "sec_gsa_check", "label": "GSA Financial Rating Auto-Check Result", "columns": 2, "fields": [
                     {"name": "mag_gsaprecheckresult", "readOnly": True}, {"name": "mag_mandatoryrereview", "readOnly": True},
                     {"name": "mag_gsarating", "readOnly": True}, {"name": "mag_gsaratingdate", "readOnly": True},
                     {"name": "mag_gsaratingexpiry", "readOnly": True},
                     {"name": "mag_gsaremarks", "readOnly": True, "colspan": 2}]},
                 {"name": "sec_frt", "label": "Financial Risk Team Information", "columns": 2, "fields": [
                     "mag_reviewername", "mag_reviewernotified", "mag_finalrating", "mag_ratingdate",
                     "mag_ratingexpiry", "mag_buyernotified", {"name": "mag_remarks", "colspan": 2}]},
             ]},
         ]},
        {"entity": R, "name": "Financial Review Request Quick Create", "formType": "QuickCreate", "prune": False,
         "description": "Buyer submission form (replaces the SharePoint New Item form): supplier, DUNS and buyer details.",
         "events": [{"event": "onload", "library": "mag_/srm/reviewrequest.js",
                     "function": "SRM.ReviewRequest.onLoad"}],
         "tabs": [{"label": "Request", "sections": [{"label": "New Request", "columns": 1, "fields": [
             "mag_name", "mag_supplierid", "mag_dunsnumber", "mag_noduns",
             "mag_buyername", "mag_buyeremail", "mag_division",
             {"name": "mag_gsaprecheckresult", "hidden": True, "readOnly": True},
             {"name": "mag_reviewpath", "hidden": True, "readOnly": True},
             {"name": "mag_reviewstatus", "hidden": True, "readOnly": True}]}]}]},
        {"entity": S, "name": "Supplier D&B Profile", "formType": "QuickView",
         "description": "Read-only D&B-sourced identity fields shown on the review request for the buyer to confirm.",
         # QuickView forms allow a single tab column and single-column sections only.
         "tabs": [{"label": "Profile", "sections": [
             {"label": "Identity", "columns": 1, "fields": [
                 "mag_legalname", "mag_duns", "mag_website", "mag_businesscategory"]},
             {"label": "Location", "columns": 1, "fields": [
                 "mag_street", "mag_city", "mag_country", "mag_manufacturingzone"]}]}]},
        {"entity": S, "type": "main", "formType": "Main", "name": "Supplier", "isDefault": True,
         "description": "Supplier master record with identity, D&B-sourced address and category, spend, current ratings and review history.",
         "subgrids": [{"childEntity": R, "view": "Supplier Review History", "label": "Financial Review Requests"}],
         "tabs": [{"name": "tab_general", "label": "General", "sections": [
             {"name": "sec_identity", "label": "Identity", "columns": 2, "fields": [
                 "mag_name", "mag_suppliercode", "mag_legalname", "mag_duns", "mag_hasduns", "mag_magnadivision"]},
             {"name": "sec_address", "label": "Address and Profile (D&B)", "columns": 2, "fields": [
                 "mag_street", "mag_city", "mag_country", "mag_region", "mag_website",
                 "mag_businesscategory", "mag_manufacturingzone", "mag_factorylocation"]},
             {"name": "sec_risk", "label": "Spend and Current Ratings", "columns": 2, "fields": [
                 "mag_annualspend", "mag_hasactivespend", "mag_currentmagnarating", "mag_currentcofacescore"]},
             {"name": "sec_contact", "label": "Supplier Contact", "columns": 2, "fields": [
                 "mag_contactname", "mag_contactemail"]},
         ]}]},
        {"entity": "mag_dnbprofile", "type": "main", "formType": "Main", "name": "D&B Profile", "layout": "auto",
         "description": "Mock D&B profile record used as the auto-fill source; synthetic data only."},
        {"entity": "mag_gsaratingrecord", "type": "main", "formType": "Main", "name": "GSA Rating Record", "layout": "auto",
         "description": "Mock GSA rating record used by the reuse pre-check; synthetic data only."},
    ],
    "businessProcessFlows": [
        {"entity": R, "name": "Supplier Financial Review", "status": "Active",
         "description": "Five-stage supplier financial review. Linear by design; shortcut paths (GSA reuse 1->5, Coface fast-track 2->4) are applied by automation that moves the active stage.",
         "stages": [
             {"name": "Request & Pre-Check", "steps": [
                 {"name": "DUNS entered", "field": "mag_dunsnumber"},
                 {"name": "No DUNS / DUNS applying", "field": "mag_noduns"},
                 {"name": "D&B auto-fill confirmed", "field": "mag_dnbautofillconfirmed"},
                 {"name": "GSA pre-check result", "field": "mag_gsaprecheckresult", "required": True},
                 {"name": "Mandatory re-review triggered", "field": "mag_mandatoryrereview"},
                 {"name": "Reviewer notified", "field": "mag_reviewernotified"}]},
             {"name": "Information Collection", "steps": [
                 {"name": "Coface retrieved", "field": "mag_cofaceretrieved"},
                 {"name": "Document request sent", "field": "mag_docrequestsent"},
                 {"name": "Reminders sent", "field": "mag_remindercount"},
                 {"name": "Documents received", "field": "mag_docsreceived"}]},
             {"name": "Analysis & Rating", "steps": [
                 {"name": "Working paper complete", "field": "mag_workingpapercomplete"},
                 {"name": "Metrics computed", "field": "mag_metricscomputed"},
                 {"name": "Non-financial risks logged", "field": "mag_nonfinancialriskslogged"},
                 {"name": "AI preliminary rating", "field": "mag_preliminaryrating"}]},
             {"name": "Communication & Decision", "steps": [
                 {"name": "Clarifications closed", "field": "mag_clarificationsclosed"},
                 {"name": "Final rating (reviewer)", "field": "mag_finalrating", "required": True},
                 {"name": "Final rating confirmed by reviewer", "field": "mag_finalratingconfirmed", "required": True},
                 {"name": "Buyer notified", "field": "mag_buyernotified"}]},
             {"name": "Archiving & Publication", "steps": [
                 {"name": "Archive complete", "field": "mag_archivecomplete"},
                 {"name": "Record locked", "field": "mag_recordlocked"},
                 {"name": "GSA push-back complete", "field": "mag_gsapushbackcomplete"},
                 {"name": "One-page summary refreshed", "field": "mag_summaryrefreshed"}]},
         ]},
    ],
    "appShell": {"areas": [{"label": "Supplier Risk", "groups": [
        {"label": "Review Desk", "subAreas": [{"entity": R, "title": "Financial Review Requests"}]},
        {"label": "Suppliers", "subAreas": [{"entity": S, "title": "Suppliers"}]},
        {"label": "External Sources (Mock)", "subAreas": [
            {"entity": "mag_dnbprofile", "title": "D&B Profiles"},
            {"entity": "mag_gsaratingrecord", "title": "GSA Rating Records"}]},
    ]}]},
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(OUT)
