"""Generate the source JSON for Stage 2 document-collection agent flows."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOWS = ROOT / "flows"
DV = "shared_commondataserviceforapps"
OL = "shared_office365"
MAILBOX = "SRM demo notification mailbox (mag_SRMDemoMailbox)"
RECORD_URL = "SRM app record URL (mag_SRMAppRecordUrl)"
ACTOR = "Data Collection (agent flow)"
NIL = "00000000-0000-0000-0000-000000000000"
APP_SCHEMA = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"


def host(api: str, operation: str) -> dict:
    return {
        "apiId": f"/providers/Microsoft.PowerApps/apis/{api}",
        "operationId": operation,
        "connectionName": api,
    }


def action(api: str, operation: str, parameters: dict, after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": after or {},
        "inputs": {"parameters": parameters, "host": host(api, operation)},
    }


def dv(operation: str, parameters: dict, after: dict | None = None) -> dict:
    return action(DV, operation, parameters, after)


def compose(expression: str, after: dict | None = None) -> dict:
    return {"type": "Compose", "runAfter": after or {}, "inputs": expression}


def ok(*names: str) -> dict:
    return {name: ["Succeeded"] for name in names}


def condition(expression: dict, yes: dict, no: dict | None = None, after: dict | None = None) -> dict:
    return {
        "type": "If",
        "runAfter": after or {},
        "expression": expression,
        "actions": yes,
        "else": {"actions": no or {}},
    }


def skills_trigger(properties: dict, required: list[str]) -> dict:
    return {"manual": {"type": "Request", "kind": "Skills", "inputs": {
        "schema": {"type": "object", "properties": properties, "required": required}}}}


def text_input(title: str, description: str, required: bool = False) -> dict:
    return {"title": title, "type": "string", "description": description,
            "x-ms-content-hint": "TEXT", "x-ms-dynamically-added": True}


def trigger_requestref() -> dict:
    return skills_trigger(
        {"requestref": text_input("Request reference", "Review request reference, for example REQ-2026-008")},
        ["requestref"])


def connection_refs(outlook: bool = True) -> dict:
    refs = {DV: {"runtimeSource": "embedded", "connection": {"connectionReferenceLogicalName": "mag_SRMDataverse"},
                 "api": {"name": DV}}}
    if outlook:
        refs[OL] = {"runtimeSource": "embedded",
                    "connection": {"connectionReferenceLogicalName": "mag_SRMOutlook"},
                    "api": {"name": OL}}
    return refs


def definition(triggers: dict, actions: dict, with_mailbox: bool = True,
              extra_parameters: list[tuple[str, str, str]] | None = None) -> dict:
    parameters = {
        "$connections": {"defaultValue": {}, "type": "Object"},
        "$authentication": {"defaultValue": {}, "type": "SecureObject"},
    }
    if with_mailbox:
        parameters[MAILBOX] = {
            "defaultValue": "",
            "type": "String",
            "metadata": {"schemaName": "mag_SRMDemoMailbox",
                         "description": "Mailbox for simulated SRM supplier and buyer messages"},
        }
        parameters[RECORD_URL] = {
            "defaultValue": "",
            "type": "String",
            "metadata": {"schemaName": "mag_SRMAppRecordUrl",
                         "description": "Review request URL prefix; the record ID is appended"},
        }
    for display, schema, description in extra_parameters or []:
        parameters[f"{display} ({schema})"] = {
            "defaultValue": "", "type": "String",
            "metadata": {"schemaName": schema, "description": description},
        }
    return {"$schema": APP_SCHEMA, "contentVersion": "1.0.0.0",
            "parameters": parameters, "triggers": triggers, "actions": actions}


def create_record(table: str, fields: dict, after: dict | None = None) -> dict:
    return dv("CreateRecord", {"entityName": table, **fields}, after)


def update_record(table: str, record_id: str, fields: dict, after: dict | None = None) -> dict:
    return dv("UpdateRecord", {"entityName": table, "recordId": record_id, **fields}, after)


def request_lookup(select: str) -> dict:
    return {
        "Requested_ref": compose("@trim(coalesce(triggerBody()?['requestref'], ''))"),
        "List_request": dv("ListRecords", {
            "entityName": "mag_financialreviewrequests", "$select": select,
            "$filter": "@{concat('mag_requestref eq ''', replace(outputs('Requested_ref'), '''', ''''''), "
                       "''' or mag_name eq ''', replace(outputs('Requested_ref'), '''', ''''''), '''')}",
            "$top": 1}, ok("Requested_ref")),
        "Request": compose("@first(outputs('List_request')?['body/value'])", ok("List_request")),
        "Request_id": compose("@coalesce(outputs('Request')?['mag_financialreviewrequestid'], '')",
                              ok("Request")),
        "Request_ref": compose("@coalesce(outputs('Request')?['mag_requestref'], outputs('Requested_ref'))",
                              ok("Request_id")),
        "List_supplier": dv("ListRecords", {
            "entityName": "mag_suppliers", "$select": "mag_name,mag_contactname,mag_contactemail,mag_duns",
            "$filter": f"mag_supplierid eq @{{coalesce(outputs('Request')?['_mag_supplierid_value'], '{NIL}')}}",
            "$top": 1}, ok("Request_ref")),
        "Supplier": compose("@first(outputs('List_supplier')?['body/value'])", ok("List_supplier")),
    }


def audit(action_name: str, details: str, after: dict | None = None) -> dict:
    return create_record("mag_reviewaudittrails", {
        "item/mag_name": action_name,
        "item/mag_action": action_name,
        "item/mag_actor": ACTOR,
        "item/mag_actortype": 100000001,
        "item/mag_occurredon": "@utcNow()",
        "item/mag_systemtouched": "Dataverse; SRM demo mailbox",
        "item/mag_details": details,
        "item/mag_ReviewRequestId@odata.bind": "mag_financialreviewrequests(@{outputs('Request_id')})",
        "item/mag_SupplierId@odata.bind": "mag_suppliers(@{outputs('Request')?['_mag_supplierid_value']})",
    }, after)


def communication(subject: str, body: str, direction: int, after: dict | None = None) -> dict:
    return create_record("mag_communicationlogs", {
        "item/mag_name": subject,
        "item/mag_subject": subject,
        "item/mag_body": body,
        "item/mag_direction": direction,
        "item/mag_channel": 100000000,
        "item/mag_language": 100000000,
        "item/mag_occurredon": "@utcNow()",
        "item/mag_actorname": ACTOR,
        "item/mag_ReviewRequestId@odata.bind": "mag_financialreviewrequests(@{outputs('Request_id')})",
        "item/mag_SupplierId@odata.bind": "mag_suppliers(@{outputs('Request')?['_mag_supplierid_value']})",
    }, after)


def send_email(subject: str, body: str, after: dict) -> dict:
    return action(OL, "SendEmailV2", {
        "emailMessage/To": f"@parameters('{MAILBOX}')",
        "emailMessage/Subject": subject,
        "emailMessage/Body": body,
        "emailMessage/Importance": "Normal",
    }, after)


def write_flow(name: str, meta: dict, definition_: dict, refs: dict) -> None:
    folder = FLOWS / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "flow.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (folder / "definition.json").write_text(
        json.dumps({"connectionReferences": refs, "definition": definition_}, indent=2) + "\n",
        encoding="utf-8")


def doc_request() -> None:
    actions = request_lookup(
        "mag_financialreviewrequestid,mag_name,mag_requestref,_mag_supplierid_value,mag_reviewpath,"
        "mag_docrequestsent,mag_noduns,mag_division,mag_buyername,mag_buyeremail")
    actions["Eligible"] = compose(
        "@and(not(equals(outputs('Request'), null)), equals(outputs('Request')?['mag_reviewpath'], 100000002), "
        "not(equals(outputs('Request')?['mag_docrequestsent'], true)), "
        "not(empty(outputs('Supplier')?['mag_contactemail'])))", ok("Supplier"))
    actions["Checklist"] = compose(
        "@concat('Audited balance sheet, income statement, and cash flow statement for each of the latest three "
        "completed fiscal years; the latest interim balance sheet, income statement, and cash flow statement; "
        "and a non-financial questionnaire covering litigation, arbitration, off-balance-sheet guarantees, "
        "customer concentration, owned or leased assets, and key management changes.', "
        "if(equals(outputs('Request')?['mag_noduns'], true), ' Additional supplier credentials are requested "
        "because no DUNS number was provided.', ''))", ok("Eligible"))
    subject = "[SRM demo, intended for supplier] Financial review documents - @{outputs('Request_ref')}"
    body = ("<p>To: @{outputs('Supplier')?['mag_contactname']} "
            "(@{outputs('Supplier')?['mag_contactemail']})</p>"
            "<p>Supplier: @{outputs('Supplier')?['mag_name']} | Division: @{outputs('Request')?['mag_division']}</p>"
            "<p>Please provide: @{outputs('Checklist')}</p>"
            "<p>This is a simulated message. It was sent only to the configured SRM demo mailbox; "
            "no email was sent to the supplier.</p>"
            "<p><a href=\"@{parameters('SRM app record URL (mag_SRMAppRecordUrl)')}@{outputs('Request_id')}\">"
            "Open the review request</a></p>")
    request_row = {
        "item/mag_name": "@{concat(outputs('Request_ref'), ' - Financial document collection')}",
        "item/mag_requesttype": 100000000,
        "item/mag_senton": "@utcNow()",
        "item/mag_responsereceived": False,
        "item/mag_requeststatus": 100000001,
        "item/mag_recipientemail": "@outputs('Supplier')?['mag_contactemail']",
        "item/mag_checklistsummary": "@outputs('Checklist')",
        "item/mag_ReviewRequestId@odata.bind": "mag_financialreviewrequests(@{outputs('Request_id')})",
    }
    actions["Create_document_request"] = create_record("mag_documentrequests", request_row)
    actions["Log_notice"] = communication(subject, body, 100000001, ok("Create_document_request"))
    actions["Email_demo_mailbox"] = send_email(subject, body, ok("Log_notice"))
    actions["Write_sent_flag"] = update_record(
        "mag_financialreviewrequests", "@outputs('Request_id')", {"item/mag_docrequestsent": True},
        ok("Email_demo_mailbox"))
    actions["Audit_request"] = audit(
        "Supplier Document Request Sent",
        "@{concat('Created one financial statement request with questionnaire', "
        "if(equals(outputs('Request')?['mag_noduns'], true), ' and supplemental credential', ''), "
        "' for ', outputs('Request_ref'), '. Message addressed to the supplier contact in the body "
        "but delivered only to the configured SRM demo mailbox.')}", ok("Write_sent_flag"))
    actions["Send_request"] = condition(
        {"equals": ["@outputs('Eligible')", True]},
        {name: actions.pop(name) for name in
         ["Create_document_request", "Log_notice", "Email_demo_mailbox", "Write_sent_flag", "Audit_request"]},
        {}, ok("Checklist"))
    actions["Status"] = compose(
        "@if(equals(outputs('Request'), null), 'notfound', "
        "if(not(outputs('Eligible')), 'ineligible', 'sent'))", ok("Send_request"))
    actions["Respond_to_the_agent"] = {
        "type": "Response", "kind": "Skills", "runAfter": ok("Status"),
        "inputs": {"schema": {"type": "object", "properties": {
            "status": {"title": "Status", "type": "string", "x-ms-content-hint": "TEXT",
                       "x-ms-dynamically-added": True},
            "message": {"title": "Message", "type": "string", "x-ms-content-hint": "TEXT",
                        "x-ms-dynamically-added": True},
            "requestref": {"title": "Request reference", "type": "string", "x-ms-content-hint": "TEXT",
                           "x-ms-dynamically-added": True}},
            "additionalProperties": {}},
            "statusCode": 200, "body": {
                "status": "@{outputs('Status')}",
                "message": "@if(equals(outputs('Status'), 'sent'), 'Checklist request prepared and logged; "
                           "notification delivered to the SRM demo mailbox only.', "
                           "if(equals(outputs('Status'), 'notfound'), 'Request not found.', "
                           "'Request is not eligible for document collection or has already been requested.'))",
                "requestref": "@{outputs('Request_ref')}"}}}
    write_flow("document-request", {
        "displayName": "SRM Data Collection - Prepare document request",
        "description": "Creates financial, non-financial and (when no DUNS) supplemental credential request rows, logs the simulated supplier checklist, and emails only the SRM demo mailbox.",
        "workflowId": "5a7e1c02-3f41-4d8b-9c6e-0b2f8d4a1e07",
        "owningAgent": "data-collection", "processStep": "Stage 2 - Information Collection",
        "requirements": ["SRM-COL-002", "SRM-COL-012", "SRM-GOV-001"],
        "trigger": "When an agent calls the flow (input: requestref).",
        "connectionReferences": ["mag_SRMDataverse", "mag_SRMOutlook"],
        "environmentVariables": ["mag_SRMDemoMailbox", "mag_SRMAppRecordUrl"],
    }, definition(trigger_requestref(), actions), connection_refs())


def reminder_flow() -> None:
    trigger = {"Recurrence": {"type": "Recurrence", "recurrence": {"frequency": "Day", "interval": 1}}}
    actions = {
        "List_due_requests": dv("ListRecords", {
            "entityName": "mag_documentrequests",
            "$select": "mag_documentrequestid,mag_name,mag_senton,mag_day3remindersenton,"
                       "mag_day7escalationsenton,mag_responsereceived,mag_requeststatus,"
                       "mag_recipientemail,_mag_reviewrequestid_value",
            "$filter": "(mag_requeststatus eq 100000001 or mag_requeststatus eq 100000002) "
                       "and mag_responsereceived eq false",
            "$top": 5000}),
        "For_each_request": {
            "type": "Foreach", "runAfter": ok("List_due_requests"),
            "foreach": "@outputs('List_due_requests')?['body/value']",
            "actions": {
                "Get_parent_request": dv("ListRecords", {
                    "entityName": "mag_financialreviewrequests",
                    "$select": "mag_financialreviewrequestid,mag_name,mag_requestref,mag_buyername,mag_buyeremail,"
                               "_mag_supplierid_value",
                    "$filter": "mag_financialreviewrequestid eq @{items('For_each_request')?['_mag_reviewrequestid_value']}",
                    "$top": 1}),
                "Parent_request": compose("@first(outputs('Get_parent_request')?['body/value'])",
                                          ok("Get_parent_request")),
                "Request": compose("@outputs('Parent_request')", ok("Parent_request")),
                "Request_id": compose("@coalesce(outputs('Request')?['mag_financialreviewrequestid'], '')",
                                      ok("Request")),
                "Days_waiting": compose(
                    "@div(sub(ticks(utcNow()), ticks(items('For_each_request')?['mag_senton'])), 864000000000)",
                    ok("Request_id")),
                "Escalation_due": condition(
                    {"and": [
                        {"greaterOrEquals": ["@outputs('Days_waiting')",
                                             "@int(parameters('SRM buyer escalation day (mag_EscalationDay)'))"]},
                        {"equals": ["@items('For_each_request')?['mag_day7escalationsenton']", None]},
                    ]},
                    {
                        "Email_buyer_demo": send_email(
                            "[SRM demo, buyer escalation] Supplier response overdue - @{outputs('Parent_request')?['mag_requestref']}",
                            "<p>Escalation due for supplier request @{outputs('Parent_request')?['mag_requestref']}.</p>"
                            "<p>Buyer: @{outputs('Parent_request')?['mag_buyername']} "
                            "(@{outputs('Parent_request')?['mag_buyeremail']}). No response is recorded.</p>"
                            "<p>Simulated notice: delivered only to the SRM demo mailbox.</p>", {}),
                        "Log_escalation": communication(
                            "[SRM demo, buyer escalation] Supplier response overdue - @{outputs('Parent_request')?['mag_requestref']}",
                            "<p>Escalation due for supplier request @{outputs('Parent_request')?['mag_requestref']}.</p>"
                            "<p>Intended supplier contact: @{items('For_each_request')?['mag_recipientemail']}. "
                            "Buyer: @{outputs('Parent_request')?['mag_buyername']} "
                            "(@{outputs('Parent_request')?['mag_buyeremail']}).</p>"
                            "<p>This simulated escalation was sent only to the SRM demo mailbox.</p>",
                            100000001, ok("Email_buyer_demo")),
                        "Audit_escalation": audit(
                            "Supplier Response Escalated",
                            "@{concat('Day-7 escalation sent for ', outputs('Parent_request')?['mag_requestref'], "
                            "'; no response had been recorded. Delivered only to demo mailbox.')}", ok("Log_escalation")),
                        "Mark_escalated": update_record(
                            "mag_documentrequests", "@items('For_each_request')?['mag_documentrequestid']",
                            {"item/mag_day7escalationsenton": "@utcNow()", "item/mag_requeststatus": 100000003},
                            ok("Email_buyer_demo")),
                    }, {
                        "Reminder_due": condition(
                            {"and": [
                                {"greaterOrEquals": ["@outputs('Days_waiting')",
                                                     "@int(parameters('SRM supplier reminder day (mag_ReminderDay)'))"]},
                                {"equals": ["@items('For_each_request')?['mag_day3remindersenton']", None]},
                            ]},
                            {
                                        "Email_supplier_demo": send_email(
                                    "[SRM demo, supplier reminder] Documents requested - @{outputs('Parent_request')?['mag_requestref']}",
                                    "<p>Gentle reminder for request @{outputs('Parent_request')?['mag_requestref']}.</p>"
                                    "<p>Intended supplier contact: @{items('For_each_request')?['mag_recipientemail']}.</p>"
                                            "<p>Simulated notice: delivered only to the SRM demo mailbox.</p>", {}),
                                        "Log_reminder": communication(
                                            "[SRM demo, supplier reminder] Documents requested - @{outputs('Parent_request')?['mag_requestref']}",
                                            "<p>Gentle reminder for request @{outputs('Parent_request')?['mag_requestref']}.</p>"
                                            "<p>Intended supplier contact: @{items('For_each_request')?['mag_recipientemail']}.</p>"
                                            "<p>This simulated reminder was sent only to the SRM demo mailbox.</p>",
                                            100000001, ok("Email_supplier_demo")),
                                        "Audit_reminder": audit(
                                            "Supplier Document Reminder Sent",
                                            "@{concat('Day-3 reminder sent for ', outputs('Parent_request')?['mag_requestref'], "
                                            "'; no response had been recorded. Delivered only to demo mailbox.')}", ok("Log_reminder")),
                                "Mark_reminded": update_record(
                                    "mag_documentrequests", "@items('For_each_request')?['mag_documentrequestid']",
                                    {"item/mag_day3remindersenton": "@utcNow()", "item/mag_requeststatus": 100000002},
                                    ok("Audit_reminder")),
                            }, {}),
                    }, ok("Days_waiting")),
            },
        },
    }
    params = [
        ("SRM demo notification mailbox", "mag_SRMDemoMailbox", "Mailbox for simulated SRM messages"),
        ("SRM app record URL", "mag_SRMAppRecordUrl", "Review request URL prefix; the record ID is appended"),
        ("SRM supplier reminder day", "mag_ReminderDay", "Days before the supplier reminder is sent"),
        ("SRM buyer escalation day", "mag_EscalationDay", "Days before the buyer escalation is sent"),
    ]
    write_flow("document-reminder-cadence", {
        "displayName": "SRM Data Collection - Supplier reminder cadence",
        "description": "Runs daily and prepares one day-3 supplier reminder and one day-7 buyer escalation for unanswered document requests; all demo notices go only to the SRM demo mailbox.",
        "workflowId": "5a7e1c02-3f41-4d8b-9c6e-0b2f8d4a1e08",
        "owningAgent": "data-collection", "processStep": "Stage 2 - Information Collection",
        "requirements": ["SRM-COL-003", "SRM-COL-012", "SRM-GOV-001"],
        "trigger": "Daily recurrence (one run per day).",
        "connectionReferences": ["mag_SRMDataverse", "mag_SRMOutlook"],
        "environmentVariables": ["mag_SRMDemoMailbox", "mag_ReminderDay", "mag_EscalationDay"],
    }, definition(trigger, actions, with_mailbox=False, extra_parameters=[
        ("SRM demo notification mailbox", "mag_SRMDemoMailbox", "Mailbox for simulated SRM messages"),
        ("SRM supplier reminder day", "mag_ReminderDay", "Days before the supplier reminder is sent"),
        ("SRM buyer escalation day", "mag_EscalationDay", "Days before the buyer escalation is sent"),
    ]), connection_refs())


def reply_filing() -> None:
    properties = {
        "requestref": text_input("Request reference", "Review request reference"),
        "filename": text_input("File name", "Name including extension"),
        "filecontent": {**text_input("File content (base64)", "Base64-encoded attachment bytes"),
                        "format": "byte", "maxLength": 5592408},
        "documenttype": {"title": "Document type", "type": "integer", "description": "Dataverse document_type option value",
                         "x-ms-content-hint": "NUMBER", "x-ms-dynamically-added": True},
        "fiscalyear": {"title": "Fiscal year", "type": "integer", "description": "Fiscal year on the attachment",
                       "x-ms-content-hint": "NUMBER", "x-ms-dynamically-added": True},
        "period": text_input("Period", "Use Annual for completed fiscal years or Interim for the current interim period"),
        "latestcompletedfiscalyear": {"title": "Latest completed fiscal year", "type": "integer",
                                      "description": "Fiscal year used to evaluate the three annual statement sets",
                                      "x-ms-content-hint": "NUMBER", "x-ms-dynamically-added": True},
        "archivefolder": {"title": "Archive subfolder", "type": "integer",
                          "description": "Dataverse archive_subfolder option value",
                          "x-ms-content-hint": "NUMBER", "x-ms-dynamically-added": True},
    }
    actions = request_lookup(
        "mag_financialreviewrequestid,mag_name,mag_requestref,_mag_supplierid_value,mag_reviewpath,mag_noduns,"
        "mag_docsreceived,mag_currentstage")
    actions["Create_document"] = create_record("mag_supplierdocuments", {
        "item/mag_name": "@triggerBody()?['filename']",
        "item/mag_demokey": "@{concat(outputs('Request_ref'), '|', triggerBody()?['filename'], '|', string(ticks(utcNow())))}",
        "item/mag_documenttype": "@triggerBody()?['documenttype']",
        "item/mag_fiscalyear": "@triggerBody()?['fiscalyear']",
        "item/mag_period": "@triggerBody()?['period']",
        "item/mag_ocrstatus": 100000000,
        "item/mag_filename": "@triggerBody()?['filename']",
        "item/mag_archivesubfolder": "@triggerBody()?['archivefolder']",
        "item/mag_duplicate": False,
        "item/mag_metadatatags": "@{concat('reply;request=', outputs('Request_ref'))}",
        "item/mag_sourcesystem": "Supplier reply (simulated)",
        "item/mag_ReviewRequestId@odata.bind": "mag_financialreviewrequests(@{outputs('Request_id')})",
        "item/mag_SupplierId@odata.bind": "mag_suppliers(@{outputs('Request')?['_mag_supplierid_value']})",
    }, ok("Supplier"))
    actions["Upload_file_content"] = action(DV, "UpdateEntityFileImageFieldContent", {
        "entityName": "mag_supplierdocuments",
        "recordId": "@outputs('Create_document')?['body/mag_supplierdocumentid']",
        "fileImageFieldName": "mag_file",
        "item": "@base64ToBinary(triggerBody()?['filecontent'])",
        "x-ms-file-name": "@triggerBody()?['filename']",
    }, ok("Create_document"))
    actions["Log_reply"] = communication(
        "[SRM demo, inbound supplier reply] @{triggerBody()?['filename']} - @{outputs('Request_ref')}",
        "<p>Attachment recorded from the simulated supplier reply: @{triggerBody()?['filename']}.</p>"
        "<p>Fiscal year: @{triggerBody()?['fiscalyear']}; period: @{triggerBody()?['period']}.</p>"
        "<p>Fictional demo content; attachment stored in Dataverse.</p>",
        100000000, ok("Upload_file_content"))
    actions["Audit_file_received"] = audit(
        "Supplier Reply Attachment Filed",
        "@{concat('Stored attachment ', triggerBody()?['filename'], ' as a Dataverse supplier document for ', "
        "outputs('Request_ref'), '; fiscal year ', string(triggerBody()?['fiscalyear']), ', period ', "
        "triggerBody()?['period'], '.')}", ok("Log_reply"))
    actions["List_request_documents"] = dv("ListRecords", {
        "entityName": "mag_supplierdocuments",
        "$select": "mag_documenttype,mag_fiscalyear,mag_period",
        "$filter": "_mag_reviewrequestid_value eq @{outputs('Request_id')}",
        "$top": 5000,
    }, ok("Audit_file_received"))
    actions["Document_keys"] = {
        "type": "Select", "runAfter": ok("List_request_documents"),
        "inputs": {
            "from": "@outputs('List_request_documents')?['body/value']",
            "select": "@concat(string(item()?['mag_documenttype']), '|', string(item()?['mag_fiscalyear']), '|', "
                      "toLower(item()?['mag_period']))",
        },
    }
    keys = "body('Document_keys')"
    required = []
    for year_offset in range(3):
        for doc_type in (100000000, 100000001, 100000002):
            required.append(
                f"contains({keys}, concat('{doc_type}|', string(sub(triggerBody()?['latestcompletedfiscalyear'], "
                f"{year_offset})), '|annual'))")
    for doc_type in (100000000, 100000001, 100000002):
        required.append(
            f"contains({keys}, concat('{doc_type}|', string(add(triggerBody()?['latestcompletedfiscalyear'], 1)), "
            "'|interim'))")
    complete_expr = "@and(" + ", ".join(required) + ")"
    actions["Documents_complete"] = compose(complete_expr, ok("Document_keys"))
    actions["Mark_documents_received"] = condition(
        {"equals": ["@outputs('Documents_complete')", True]},
        {
            "Update_request": update_record("mag_financialreviewrequests", "@outputs('Request_id')",
                                            {"item/mag_docsreceived": True}),
            "Mark_collection_requests_received": {
                "type": "Foreach", "runAfter": ok("Update_request"),
                "foreach": "@outputs('List_collection_requests')?['body/value']",
                "actions": {
                    "Update_collection_request": update_record(
                        "mag_documentrequests",
                        "@items('Mark_collection_requests_received')?['mag_documentrequestid']",
                        {"item/mag_responsereceived": True, "item/mag_requeststatus": 100000004}),
                },
            },
            "Audit_complete": audit(
                "Required Financial Statements Filed",
                "@{concat('All 12 required annual and interim balance sheet, income statement, and cash flow "
                "statement files are present for fiscal years ', string(sub(triggerBody()?['latestcompletedfiscalyear'], "
                "2)), '-', string(triggerBody()?['latestcompletedfiscalyear']), ' and interim ', "
                "string(add(triggerBody()?['latestcompletedfiscalyear'], 1)), '. Non-financial questionnaire and "
                "audit verification remain manual.')}", ok("Mark_collection_requests_received")),
            "Move_BPF_to_analysis": {
                "type": "Scope", "runAfter": ok("Audit_complete"),
                "actions": {
                    "Get_BPF_instance": dv("ListRecords", {
                        "entityName": "new_supplierfinancialreviews",
                        "$select": "businessprocessflowinstanceid,traversedpath,activestageid,bpf_name",
                        "$filter": "_bpf_mag_financialreviewrequestid_value eq @{outputs('Request_id')} and statecode eq 0",
                        "$top": 1}),
                    "BPF_instance": compose("@first(outputs('Get_BPF_instance')?['body/value'])",
                                             ok("Get_BPF_instance")),
                    "List_BPF_stages": dv("ListRecords", {
                        "entityName": "processstages", "$select": "processstageid,stagename",
                        "$filter": "stagename eq 'Request & Pre-Check' or stagename eq 'Information Collection' "
                                   "or stagename eq 'Analysis & Rating'", "$top": 20}, ok("BPF_instance")),
                    "Stage1": {"type": "Query", "runAfter": ok("List_BPF_stages"),
                               "inputs": {"from": "@outputs('List_BPF_stages')?['body/value']",
                                          "where": "@equals(item()?['stagename'], 'Request & Pre-Check')"}},
                    "Stage2": {"type": "Query", "runAfter": ok("Stage1"),
                               "inputs": {"from": "@outputs('List_BPF_stages')?['body/value']",
                                          "where": "@equals(item()?['stagename'], 'Information Collection')"}},
                    "Stage3": {"type": "Query", "runAfter": ok("Stage2"),
                               "inputs": {"from": "@outputs('List_BPF_stages')?['body/value']",
                                          "where": "@equals(item()?['stagename'], 'Analysis & Rating')"}},
                    "Stage1_id": compose("@first(body('Stage1'))?['processstageid']", ok("Stage3")),
                    "Stage2_id": compose("@first(body('Stage2'))?['processstageid']", ok("Stage1_id")),
                    "Stage3_id": compose("@first(body('Stage3'))?['processstageid']", ok("Stage2_id")),
                    "Update_BPF": condition(
                        {"not": {"equals": ["@outputs('BPF_instance')", None]}},
                        {
                            "Advance_to_analysis": update_record(
                                "new_supplierfinancialreviews",
                                "@outputs('BPF_instance')?['businessprocessflowinstanceid']",
                                {"item/activestageid@odata.bind": "/processstages(@{outputs('Stage3_id')})",
                                 "item/traversedpath": "@{concat(outputs('Stage1_id'), ',', outputs('Stage2_id'), ',', "
                                                       "outputs('Stage3_id'))}"}),
                            "Update_request_stage": update_record(
                                "mag_financialreviewrequests", "@outputs('Request_id')",
                                {"item/mag_currentstage": 3}, ok("Advance_to_analysis")),
                            "Audit_stage3_movement": audit(
                                "Documents Received - Stage 3 Movement",
                                "@{concat('Advanced ', outputs('Request_ref'), ' to Analysis & Rating after all 12 "
                                "required annual and interim statements were filed. Questionnaire and audit "
                                "verification remain manual.')}", ok("Update_request_stage")),
                        },
                        {}, ok("Stage3_id")),
                },
            },
        }, {}, ok("Documents_complete"))
    actions["List_collection_requests"] = dv("ListRecords", {
        "entityName": "mag_documentrequests",
        "$select": "mag_documentrequestid,mag_requeststatus,mag_responsereceived",
        "$filter": "_mag_reviewrequestid_value eq @{outputs('Request_id')} and "
                   "(mag_requeststatus eq 100000001 or mag_requeststatus eq 100000002 or mag_requeststatus eq 100000003)",
        "$top": 100,
    }, ok("Documents_complete"))
    actions["Mark_documents_received"]["runAfter"] = ok("List_collection_requests")
    fields = {
        "status": ("Status", "string", "@if(outputs('Documents_complete'), 'complete', 'filed')"),
        "message": ("Message", "string",
                    "@if(outputs('Documents_complete'), 'The 12 required statement files are present. "
                    "The BPF moved to Analysis & Rating; questionnaire and audit verification remain manual.', "
                    "'Attachment filed. The required 12 statement files are not yet complete.')"),
        "documentid": ("Supplier document ID", "string", "@{outputs('Create_document')?['body/mag_supplierdocumentid']}"),
    }
    actions["Respond_to_the_agent"] = {
        "type": "Response", "kind": "Skills", "runAfter": ok("Mark_documents_received"),
        "inputs": {"schema": {"type": "object", "properties": {
            key: {"title": title, "type": kind, "description": "", "x-ms-content-hint": "TEXT",
                  "x-ms-dynamically-added": True}
            for key, (title, kind, _) in fields.items()}, "additionalProperties": {}},
            "statusCode": 200, "body": {key: value for key, (_, _, value) in fields.items()}},
    }
    trigger = skills_trigger(properties, ["requestref", "filename", "filecontent", "documenttype",
                                          "fiscalyear", "period", "latestcompletedfiscalyear", "archivefolder"])
    write_flow("document-reply-filing", {
        "displayName": "SRM Data Collection - File supplier reply attachment",
        "description": "Creates a supplier document row and uploads one attachment through the Dataverse connector's Upload a file or an image action. Marks collection complete and advances the BPF when all 12 annual/interim statements are present; questionnaire and audit verification remain manual.",
        "workflowId": "5a7e1c02-3f41-4d8b-9c6e-0b2f8d4a1e09",
        "owningAgent": "data-collection", "processStep": "Stage 2 - Information Collection",
        "requirements": ["SRM-COL-004", "SRM-COL-005", "SRM-COL-012", "SRM-GOV-001"],
        "trigger": "When an agent calls the flow (requestref and one base64 attachment up to 4 MiB per call).",
        "connectionReferences": ["mag_SRMDataverse"],
        "environmentVariables": [],
    }, definition(trigger, actions, with_mailbox=False), connection_refs(outlook=False))


def augment_coface_stage_move() -> None:
    path = FLOWS / "coface-propose-rating" / "definition.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    actions = payload["definition"]["actions"]
    actions.pop("Advance_fast_track_BPF", None)
    stage_move = {
        "Get_BPF_instance": dv("ListRecords", {
            "entityName": "new_supplierfinancialreviews",
            "$select": "businessprocessflowinstanceid,traversedpath,activestageid,bpf_name",
            "$filter": "_bpf_mag_financialreviewrequestid_value eq @{outputs('Request_id')}",
            "$top": 1}),
        "BPF_instance": compose("@first(outputs('Get_BPF_instance')?['body/value'])",
                                 ok("Get_BPF_instance")),
        "List_BPF_stages": dv("ListRecords", {
            "entityName": "processstages", "$select": "processstageid,stagename",
            "$filter": "stagename eq 'Request & Pre-Check' or stagename eq 'Information Collection' "
                       "or stagename eq 'Communication & Decision'", "$top": 20}, ok("BPF_instance")),
        "Stage1": {"type": "Query", "runAfter": ok("List_BPF_stages"),
                   "inputs": {"from": "@outputs('List_BPF_stages')?['body/value']",
                              "where": "@equals(item()?['stagename'], 'Request & Pre-Check')"}},
        "Stage2": {"type": "Query", "runAfter": ok("Stage1"),
                   "inputs": {"from": "@outputs('List_BPF_stages')?['body/value']",
                              "where": "@equals(item()?['stagename'], 'Information Collection')"}},
        "Stage4": {"type": "Query", "runAfter": ok("Stage2"),
                   "inputs": {"from": "@outputs('List_BPF_stages')?['body/value']",
                              "where": "@equals(item()?['stagename'], 'Communication & Decision')"}},
        "Stage1_id": compose("@first(body('Stage1'))?['processstageid']", ok("Stage4")),
        "Stage2_id": compose("@first(body('Stage2'))?['processstageid']", ok("Stage1_id")),
        "Stage4_id": compose("@first(body('Stage4'))?['processstageid']", ok("Stage2_id")),
        "Advance_if_instance_exists": condition(
            {"not": {"equals": ["@outputs('BPF_instance')", None]}},
            {
                "Update_BPF": update_record(
                    "new_supplierfinancialreviews",
                    "@outputs('BPF_instance')?['businessprocessflowinstanceid']",
                    {"item/activestageid@odata.bind": "/processstages(@{outputs('Stage4_id')})",
                     "item/traversedpath": "@{concat(outputs('Stage1_id'), ',', outputs('Stage2_id'), ',', "
                                           "outputs('Stage4_id'))}"},
                    {}),
                "Update_request_stage": update_record(
                    "mag_financialreviewrequests", "@outputs('Request_id')",
                    {"item/mag_currentstage": 4}, ok("Update_BPF")),
                "Audit_stage_move": audit(
                    "Coface Fast-Track Stage Movement",
                    "@{concat('Advanced ', outputs('Request_ref'), ' from Information Collection to Communication "
                    "& Decision through the Coface Fast-Track shortcut. The reviewer remains responsible for the "
                    "final financial rating.')}", ok("Update_request_stage")),
            }, {}, ok("Stage4_id")),
    }
    actions["Advance_fast_track_BPF"] = condition(
        {"equals": ["@outputs('Outcome')", "proposed"]},
        stage_move, {}, ok("Apply_full_review"))
    actions["Respond_to_the_agent"]["runAfter"] = ok("Advance_fast_track_BPF")
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    doc_request()
    reminder_flow()
    reply_filing()
    augment_coface_stage_move()


if __name__ == "__main__":
    main()
