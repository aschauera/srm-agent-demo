"""Provision the SRM demo Dataverse schema into the unmanaged solution."""

from __future__ import annotations

import json
import time
import re
import argparse
import os
import shutil
import subprocess
from collections.abc import Callable
from enum import IntEnum
from pathlib import Path
from typing import TypeVar

from auth import get_client

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schema" / "tables"
SOLUTION = "SRMAgentDemo"
PREFIX = "mag"
ENTITY_KEY_COMPONENT = 14
T = TypeVar("T")


def retry_metadata(operation: Callable[[], T], label: str, max_attempts: int = 5) -> T:
    for attempt in range(max_attempts):
        try:
            return operation()
        except Exception as error:
            message = str(error).lower()
            transient = (
                "another" in message and "running" in message
            ) or "entitycustomization" in message or "still being processed" in message
            if not transient or attempt == max_attempts - 1:
                raise
            delay = 10 * (attempt + 1)
            print(f"{label}: metadata lock; retrying in {delay}s.", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"{label} exhausted metadata retries.")

CHOICES: dict[str, list[str]] = {
    "rating": ["Green", "Yellow", "Red", "Not rated"],
    "review_status": ["Not Started", "In Progress", "Completed"],
    "review_path": ["GSA Reuse", "Coface Fast-Track", "Full Review"],
    "gsa_precheck": [
        "Valid active rating",
        "Rating expired",
        "No matching supplier",
        "Skip - no DUNS",
    ],
    "coface_tier": ["Low", "Medium", "High", "Unavailable"],
    "request_type": ["Financial statements", "Non-financial questionnaire", "Supplemental credentials"],
    "request_status": ["Draft", "Sent", "Reminder sent", "Escalated", "Received", "Closed"],
    "document_type": [
        "Balance sheet",
        "Income statement",
        "Cash flow statement",
        "Audit report",
        "Business license",
        "Asset or lease proof",
        "Shareholder structure",
        "Other",
    ],
    "ocr_status": ["Not started", "Queued", "Complete", "Needs review", "Failed"],
    "archive_subfolder": [
        "Supplier Submitted Financial Documents",
        "Third-Party Credit Records",
        "Communication Audit Trail",
        "Final Review Deliverables",
    ],
    "risk_type": [
        "Litigation",
        "Arbitration",
        "Off-balance-sheet guarantee",
        "Customer concentration",
        "Owned vs leased assets",
        "Management turnover",
        "Regulatory penalty",
        "Other",
    ],
    "severity": ["Low", "Medium", "High"],
    "ownership_status": ["Owned", "Leased", "Mixed", "Unknown"],
    "direction": ["Inbound", "Outbound"],
    "channel": ["Email", "Phone", "System"],
    "language": ["English", "German", "Chinese", "Other"],
    "actor_type": ["Human", "Agent", "System"],
    "materiality": ["Low", "Medium", "High"],
    "prompt_behavior": ["None", "Soft reminder", "Mandatory prompt"],
    "warning_status": ["Open", "Under review", "Resolved", "Dismissed"],
    "adverse_category": [
        "Litigation or arbitration",
        "Guarantee liability",
        "Regulatory fine",
        "Production suspension",
        "Equity freezing",
        "Debt default",
        "Other",
    ],
    "operator": ["Greater than", "Greater than or equal", "Less than", "Less than or equal", "Equals"],
    "dimension": ["Liquidity", "Leverage", "Profitability", "Cash flow", "Non-financial"],
    "approval_status": ["Draft - demo only", "Approved"],
    "archive_item_type": ["Document", "Email", "Working paper", "Risk extract", "Rating", "Call transcript"],
}


LABEL_OVERRIDES = {
    "DnBAutofillConfirmed": "D&B Auto-Fill Confirmed",
    "NoDUNS": "No DUNS / DUNS Applying",
    "MandatoryReReview": "Mandatory Re-Review Triggered",
    "FinalRatingConfirmed": "Final Rating Confirmed by Reviewer",
    "SummaryRefreshed": "One-Page Summary Refreshed",
    "GSAPushBackComplete": "GSA Push-Back Complete",
    "GSAPrecheckResult": "GSA Pre-Check Result",
    "CofaceWithin18Months": "Coface Within 18 Months",
    "NonFinancialRisksLogged": "Non-Financial Risks Logged",
    "MandatoryRereview": "Mandatory Re-Review",
}


def label_for(name: str) -> str:
    """Derive a readable display label from a PascalCase column name, keeping acronyms intact."""
    if name in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[name]
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[0-9])(?=[A-Za-z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    spaced = re.sub(r"\bUrl\b", "URL", spaced)
    return spaced.replace(" Of ", " of ").replace(" To ", " to ")


def c(
    name: str,
    kind: str = "string",
    *,
    choice: str | None = None,
    max_length: int | None = None,
    label: str | None = None,
) -> dict:
    column = {"name": name, "type": kind}
    if label:
        column["displayName"] = label
    if choice:
        column["choice"] = choice
    if max_length:
        column["maxLength"] = max_length
    return column


def l(name: str, target: str, required: bool = False) -> dict:
    return {"name": name, "target": target, "required": required}


TABLES = [
    {
        "logicalName": "mag_supplier",
        "schemaName": "mag_Supplier",
        "displayName": "Supplier",
        "description": "Fictional supplier master used by the SRM financial review demo.",
        "columns": [
            c("DemoKey"), c("SupplierCode"), c("LegalName"), c("DUNS", max_length=9),
            c("HasDUNS", "boolean"), c("Street"), c("City"), c("Country"), c("Region"),
            c("Website"), c("BusinessCategory"), c("ManufacturingZone"), c("MagnaDivision"),
            c("AnnualSpend", "money"), c("HasActiveSpend", "boolean"),
            c("CurrentMagnaRating", "choice", choice="rating"), c("CurrentCofaceScore", "integer"),
            c("ContactName"), c("ContactEmail"), c("FactoryLocation"),
        ],
    },
    {
        "logicalName": "mag_financialreviewrequest",
        "schemaName": "mag_FinancialReviewRequest",
        "displayName": "Financial Review Request",
        "description": "Review request and BPF host record for the five-stage SRM process.",
        "columns": [
            c("DemoKey"), c("RequestRef"), c("BuyerName"), c("BuyerEmail"), c("ReviewerName"),
            c("Division"), c("ReviewStatus", "choice", choice="review_status"),
            c("ReviewPath", "choice", choice="review_path"),
            c("GSAPrecheckResult", "choice", choice="gsa_precheck"),
            c("GSARating"), c("GSARemarks", "text"), c("GSARatingDate", "datetime"),
            c("GSARatingExpiry", "datetime"), c("CofaceScore", "integer"),
            c("CofaceRiskTier", "choice", choice="coface_tier"),
            c("CofaceAssessmentDate", "datetime"), c("CofaceDataAgeMonths", "integer"),
            c("CofaceWithin18Months", "boolean"),
            c("PreliminaryRating", "choice", choice="rating"), c("NarrativeDraft", "text"),
            c("FinalRating", "choice", choice="rating"), c("RatingDate", "datetime"),
            c("RatingExpiry", "datetime"), c("Remarks", "text"),
            c("ReviewerOverride", "boolean"), c("ArchiveFolderLink"),
            c("CurrentStage", "integer"), c("ClarificationsClosed", "boolean"),
            # BPF step flags; every business process flow step must bind a column.
            c("DUNSNumber", max_length=9), c("NoDUNS", "boolean"),
            c("DnBAutofillConfirmed", "boolean"), c("MandatoryReReview", "boolean"),
            c("ReviewerNotified", "boolean"),
            c("CofaceRetrieved", "boolean"), c("DocRequestSent", "boolean", label="Document Request Sent"),
            c("ReminderCount", "integer"), c("DocsReceived", "boolean", label="Documents Received"),
            c("WorkingPaperComplete", "boolean"), c("MetricsComputed", "boolean"),
            c("NonFinancialRisksLogged", "boolean"),
            c("FinalRatingConfirmed", "boolean"), c("BuyerNotified", "boolean"),
            c("ArchiveComplete", "boolean"), c("RecordLocked", "boolean"),
            c("GSAPushBackComplete", "boolean"), c("SummaryRefreshed", "boolean"),
        ],
        "lookups": [l("Supplier", "mag_supplier", True), l("SourceEarlyWarning", "mag_earlywarning")],
    },
    {
        "logicalName": "mag_documentrequest",
        "schemaName": "mag_DocumentRequest",
        "displayName": "Document Request",
        "description": "Supplier document outreach, reminder, and response tracking.",
        "columns": [
            c("DemoKey"), c("RequestType", "choice", choice="request_type"),
            c("SentOn", "datetime"), c("Day3ReminderSentOn", "datetime"),
            c("Day7EscalationSentOn", "datetime"), c("ResponseReceived", "boolean"),
            c("RequestStatus", "choice", choice="request_status"), c("RecipientEmail"),
            c("ChecklistSummary", "text"),
        ],
        "lookups": [l("ReviewRequest", "mag_financialreviewrequest", True)],
    },
    {
        "logicalName": "mag_supplierdocument",
        "schemaName": "mag_SupplierDocument",
        "displayName": "Supplier Document",
        "description": "Supplier-submitted evidence and extraction/archive metadata.",
        "columns": [
            c("DemoKey"), c("DocumentType", "choice", choice="document_type"),
            c("FiscalYear", "integer"), c("Period"), c("OCRStatus", "choice", choice="ocr_status"),
            c("File", "file"), c("FileName"), c("ArchiveSubfolder", "choice", choice="archive_subfolder"),
            c("Duplicate", "boolean"), c("MetadataTags", "text"), c("SourceSystem"),
        ],
        "lookups": [l("ReviewRequest", "mag_financialreviewrequest", True), l("Supplier", "mag_supplier", True)],
    },
    {
        "logicalName": "mag_financialworkingpaper",
        "schemaName": "mag_FinancialWorkingPaper",
        "displayName": "Financial Working Paper",
        "description": "Fiscal-year and interim financial inputs, derived metrics, and anomaly flags.",
        "columns": [
            c("DemoKey"), c("FiscalYear", "integer"), c("Period"), c("Currency"),
            c("Revenue", "money"), c("CostOfGoodsSold", "money"), c("GrossProfit", "money"),
            c("NetIncome", "money"), c("OperatingCashFlow", "money"), c("CurrentAssets", "money"),
            c("CurrentLiabilities", "money"), c("TotalAssets", "money"), c("TotalDebt", "money"),
            c("AccountsReceivable", "money"), c("Inventory", "money"),
            c("LeverageRatio", "decimal"), c("LiquidityRatio", "decimal"),
            c("GrossMargin", "decimal"), c("AssetTurnover", "decimal"), c("YearOverYearDelta", "decimal"),
            c("AnomalyFlags", "text"), c("ExtractionConfidence", "decimal"),
        ],
        "lookups": [
            l("ReviewRequest", "mag_financialreviewrequest", True),
            l("Supplier", "mag_supplier", True),
            l("SourceDocument", "mag_supplierdocument"),
        ],
    },
    {
        "logicalName": "mag_nonfinancialriskitem",
        "schemaName": "mag_NonFinancialRiskItem",
        "displayName": "Non-Financial Risk Item",
        "description": "Structured qualitative supplier risk observations and source evidence.",
        "columns": [
            c("DemoKey"), c("RiskType", "choice", choice="risk_type"),
            c("Severity", "choice", choice="severity"), c("Details", "text"), c("SourceUrl"),
            c("EventDate", "datetime"), c("CustomerConcentration", "decimal"),
            c("OwnershipStatus", "choice", choice="ownership_status"),
            c("EstimatedExposure", "money"), c("Verified", "boolean"),
        ],
        "lookups": [l("ReviewRequest", "mag_financialreviewrequest"), l("Supplier", "mag_supplier", True)],
    },
    {
        "logicalName": "mag_communicationlog",
        "schemaName": "mag_CommunicationLog",
        "displayName": "Communication Log",
        "description": "Inbound and outbound communications, transcripts, summaries, and translation.",
        "columns": [
            c("DemoKey"), c("Direction", "choice", choice="direction"),
            c("Channel", "choice", choice="channel"), c("Subject"), c("Body", "text"),
            c("CallTranscript", "text"), c("AISummary", "text"),
            c("Language", "choice", choice="language"), c("TranslatedText", "text"),
            c("OccurredOn", "datetime"), c("ActorName"),
        ],
        "lookups": [l("ReviewRequest", "mag_financialreviewrequest", True), l("Supplier", "mag_supplier")],
    },
    {
        "logicalName": "mag_earlywarning",
        "schemaName": "mag_EarlyWarning",
        "displayName": "Early Warning",
        "description": "Supplier early warning, AI materiality, prompt, and linked review request.",
        "columns": [
            c("DemoKey"), c("WarningRef"), c("Description", "text"), c("RumourSource"),
            c("PotentialImpact", "text"), c("AffectedVolume", "money"), c("RiskTags", "text"),
            c("Materiality", "choice", choice="materiality"),
            c("PromptBehavior", "choice", choice="prompt_behavior"),
            c("ResolutionStatus", "choice", choice="warning_status"),
            c("Reminder24HourSent", "boolean"), c("SubmittedOn", "datetime"), c("ReviewRequestLink"),
        ],
        "lookups": [l("Supplier", "mag_supplier", True), l("ReviewRequest", "mag_financialreviewrequest")],
    },
    {
        "logicalName": "mag_reviewaudittrail",
        "schemaName": "mag_ReviewAuditTrail",
        "displayName": "Review Audit Trail",
        "description": "Append-oriented ledger of human, agent, and system activity.",
        "columns": [
            c("DemoKey"), c("Action"), c("Actor"), c("ActorType", "choice", choice="actor_type"),
            c("OccurredOn", "datetime"), c("SystemTouched"), c("Details", "text"),
        ],
        "lookups": [l("ReviewRequest", "mag_financialreviewrequest"), l("Supplier", "mag_supplier")],
    },
    {
        "logicalName": "mag_gsaratingrecord",
        "schemaName": "mag_GSARatingRecord",
        "displayName": "GSA Rating Record",
        "description": "Synthetic GSA procurement rating records for pre-check and reuse scenarios.",
        "columns": [
            c("DemoKey"), c("DUNS", max_length=9), c("Rating", "choice", choice="rating"),
            c("Remarks", "text"), c("RatingDate", "datetime"), c("ExpiryDate", "datetime"),
            c("MandatoryRereview", "boolean"), c("ReviewerName"), c("SyntheticData", "boolean"),
        ],
        "lookups": [l("Supplier", "mag_supplier")],
    },
    {
        "logicalName": "mag_cofacecreditrecord",
        "schemaName": "mag_CofaceCreditRecord",
        "displayName": "Coface Credit Record",
        "description": "Synthetic Coface response records for exact and fuzzy-match lookup scenarios.",
        "columns": [
            c("DemoKey"), c("DUNS", max_length=9), c("SupplierName"), c("Country"),
            c("Score", "integer"), c("RiskTier", "choice", choice="coface_tier"),
            c("PaymentTrackRecord", "text"), c("NegativeAlerts", "text"),
            c("RecommendedCreditLimit", "money"), c("AssessmentDate", "datetime"),
            c("FinancialDataThrough", "datetime"), c("ReportLink"),
            c("MatchConfidence", "decimal"), c("SyntheticData", "boolean"),
        ],
        "lookups": [l("Supplier", "mag_supplier")],
    },
    {
        "logicalName": "mag_dnbprofile",
        "schemaName": "mag_DNBProfile",
        "displayName": "D&B Profile",
        "description": "Synthetic D&B/public-registry profile records for supplier prefill.",
        "columns": [
            c("DemoKey"), c("DUNS", max_length=9), c("LegalName"), c("Street"), c("City"),
            c("Country"), c("Region"), c("Website"), c("BusinessCategory"),
            c("ManufacturingZone"), c("EstablishedYear", "integer"),
            c("ShareholderSummary", "text"), c("ProductLines", "text"),
            c("SourceUrl"), c("ProfileCheckedOn", "datetime"), c("SyntheticData", "boolean"),
        ],
        "lookups": [l("Supplier", "mag_supplier", True)],
    },
    {
        "logicalName": "mag_archiverecord",
        "schemaName": "mag_ArchiveRecord",
        "displayName": "Archive Record",
        "description": "Synthetic eRFX archive folders, items, lock state, and searchable metadata.",
        "columns": [
            c("DemoKey"), c("FolderIdentifier"), c("Subfolder", "choice", choice="archive_subfolder"),
            c("ItemType", "choice", choice="archive_item_type"), c("ItemName"),
            c("ArchiveUrl"), c("Locked", "boolean"), c("Version", "integer"),
            c("SearchableMetadata", "text"), c("SourceSystem"), c("UploadedOn", "datetime"),
        ],
        "lookups": [l("Supplier", "mag_supplier", True), l("ReviewRequest", "mag_financialreviewrequest")],
    },
    {
        "logicalName": "mag_adversenewsevent",
        "schemaName": "mag_AdverseNewsEvent",
        "displayName": "Adverse News Event",
        "description": "Synthetic, source-attributed adverse-event monitoring results.",
        "columns": [
            c("DemoKey"), c("Category", "choice", choice="adverse_category"),
            c("Severity", "choice", choice="severity"), c("Title"),
            c("Description", "text"), c("ReleaseDate", "datetime"), c("SourceUrl"),
            c("Resolved", "boolean"), c("SyntheticData", "boolean"),
        ],
        "lookups": [l("Supplier", "mag_supplier", True)],
    },
    {
        "logicalName": "mag_ratingconversionrule",
        "schemaName": "mag_RatingConversionRule",
        "displayName": "Rating Conversion Rule",
        "description": "Configurable, draft-only illustrative Coface-to-Magna mapping for the demo.",
        "columns": [
            c("DemoKey"), c("RuleName"), c("MinimumScore", "integer"), c("MaximumScore", "integer"),
            c("MagnaRating", "choice", choice="rating"), c("CreditLimitGuidance", "text"),
            c("ApprovalStatus", "choice", choice="approval_status"),
            c("EffectiveFrom", "datetime"), c("EffectiveTo", "datetime"), c("DemoOnly", "boolean"),
        ],
    },
    {
        "logicalName": "mag_riskscoringrule",
        "schemaName": "mag_RiskScoringRule",
        "displayName": "Risk Scoring Rule",
        "description": "Configurable, draft-only illustrative thresholds for the demo scoring matrix.",
        "columns": [
            c("DemoKey"), c("Metric"), c("Operator", "choice", choice="operator"),
            c("Threshold", "decimal"), c("Points", "integer"),
            c("Dimension", "choice", choice="dimension"), c("Signal", "text"),
            c("ApprovalStatus", "choice", choice="approval_status"), c("DemoOnly", "boolean"),
        ],
    },
    {
        "logicalName": "mag_supplieronepagesummary",
        "schemaName": "mag_SupplierOnePageSummary",
        "displayName": "Supplier One-Page Summary",
        "description": "Generated supplier profile, consolidated risk metrics, trends, and alert banner.",
        "columns": [
            c("DemoKey"), c("SummaryVersion"), c("CompanyProfile", "text"),
            c("SourceAttribution", "text"), c("RiskMetricsPanel", "text"),
            c("TrendInterpretation", "text"), c("AdverseEventDigest", "text"),
            c("AlertBanner", "text"), c("GeneratedOn", "datetime"),
            c("PDFExportUrl"), c("HasActiveSpend", "boolean"),
        ],
        "lookups": [l("Supplier", "mag_supplier", True)],
    },
]

TABLE_TRACEABILITY = {
    "mag_supplier": ["SRM-INT-001", "SRM-OPS-001"],
    "mag_financialreviewrequest": ["SRM-INT-001", "SRM-COF-001", "SRM-GOV-001"],
    "mag_documentrequest": ["SRM-COL-001"],
    "mag_supplierdocument": ["SRM-COL-001", "SRM-ARC-001"],
    "mag_financialworkingpaper": ["SRM-FIN-001"],
    "mag_nonfinancialriskitem": ["SRM-NFR-001"],
    "mag_communicationlog": ["SRM-COM-001", "SRM-GOV-001"],
    "mag_earlywarning": ["SRM-EWS-001"],
    "mag_reviewaudittrail": ["SRM-GOV-001"],
    "mag_gsaratingrecord": ["SRM-INT-001"],
    "mag_cofacecreditrecord": ["SRM-COF-001"],
    "mag_dnbprofile": ["SRM-INT-001", "SRM-OPS-001"],
    "mag_archiverecord": ["SRM-ARC-001"],
    "mag_adversenewsevent": ["SRM-OPS-001"],
    "mag_ratingconversionrule": ["SRM-COF-001"],
    "mag_riskscoringrule": ["SRM-FIN-001"],
    "mag_supplieronepagesummary": ["SRM-OPS-001"],
}


def enum_for(name: str, labels: list[str]) -> type[IntEnum]:
    values = {}
    for index, label in enumerate(labels):
        member = re.sub(r"\W+", "_", label.upper()).strip("_")
        values[member] = 100000000 + index
    return IntEnum(name, values)


def schema_files() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    all_relationships = []
    all_choices: dict[str, list[str]] = {}
    for table in TABLES:
        path = SCHEMA_DIR / f"{table['logicalName'].removeprefix('mag_')}.json"
        spec = {
            **table,
            "primaryNameAttribute": f"{PREFIX}_Name",
            "columns": [
                {
                    **column,
                    "displayName": column.get("displayName") or label_for(column["name"]),
                    "alternateKey": column["name"] == "DemoKey",
                }
                for column in table["columns"]
            ],
            **({"lookups": [
                {**lookup, "displayName": label_for(lookup["name"])}
                for lookup in table["lookups"]
            ]} if table.get("lookups") else {}),
            "requirements": TABLE_TRACEABILITY[table["logicalName"]],
        }
        path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for column in table["columns"]:
            if "choice" in column:
                all_choices[column["choice"]] = CHOICES[column["choice"]]
        for lookup in table.get("lookups", []):
            relationship = {
                "schemaName": f"mag_{table['logicalName'].removeprefix('mag_')}_{lookup['name']}",
                "referencingTable": table["logicalName"],
                "lookupName": lookup["name"],
                "referencedTable": lookup["target"],
                "required": lookup["required"],
            }
            all_relationships.append(relationship)
    (ROOT / "schema" / "choices.json").write_text(
        json.dumps({key: {"options": values, "values": [100000000 + i for i in range(len(values))]}
                    for key, values in all_choices.items()}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (ROOT / "schema" / "relationships.json").write_text(
        json.dumps(all_relationships, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def dataverse_columns(table: dict) -> dict:
    result = {}
    for column in table["columns"]:
        schema_name = f"{PREFIX}_{column['name']}"
        kind = column["type"]
        if kind == "choice":
            result[schema_name] = enum_for(column["choice"], CHOICES[column["choice"]])
        else:
            result[schema_name] = {"text": "memo", "integer": "int", "boolean": "bool"}.get(kind, kind)
    return result


def add_solution_component(component_id: str, component_type: int, add_required: bool) -> None:
    environment_url = os.environ.get("DATAVERSE_URL")
    if not environment_url:
        raise RuntimeError("DATAVERSE_URL is required to add SRM solution components")
    body = json.dumps({
        "ComponentId": component_id,
        "ComponentType": component_type,
        "SolutionUniqueName": SOLUTION,
        "AddRequiredComponents": add_required,
    })
    dataverse_cli = shutil.which("dataverse")
    if not dataverse_cli:
        raise RuntimeError("The Dataverse CLI ('dataverse') is required to add solution components")
    result = subprocess.run(
        [
            dataverse_cli, "api", "request",
            "--target", "dataverse",
            "--method", "POST",
            "--path", "/api/data/v9.2/AddSolutionComponent",
            "--body", body,
            "--environment", environment_url,
            "--context", "app=dataverse-skills/1a0d2929b96;skill=dv-metadata;agent=copilot",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"AddSolutionComponent {component_id} failed: {result.stdout}{result.stderr}")


def solution_component_ids(client, component_type: int, full_roots_only: bool = False) -> set[str]:
    solutions = list(client.records.list(
        "solution",
        filter=f"uniquename eq '{SOLUTION}'",
        select=["solutionid"],
        top=2,
    ))
    if len(solutions) != 1:
        raise RuntimeError(f"Expected one solution named {SOLUTION}, found {len(solutions)}")
    components = client.records.list(
        "solutioncomponent",
        filter=f"_solutionid_value eq {solutions[0]['solutionid']} and componenttype eq {component_type}",
        select=["objectid", "rootcomponentbehavior"],
        top=5000,
    )
    return {
        component["objectid"].lower()
        for component in components
        if not full_roots_only or component.get("rootcomponentbehavior") == 0
    }


def key_in_solution(client, table: dict, key_id: str) -> bool:
    # Tables added with all subcomponents (rootcomponentbehavior 0) carry their keys implicitly.
    if key_id in solution_component_ids(client, ENTITY_KEY_COMPONENT):
        return True
    table_id = client.tables.get(table["logicalName"]).metadata_id.lower()
    return table_id in solution_component_ids(client, 1, full_roots_only=True)


def ensure_solution_keys(client) -> None:
    # Alternate keys created after the table are not added to the solution automatically.
    missing = []
    for table in TABLES:
        key_name = f"{table['schemaName']}DemoKey".lower()
        key = next(
            (k for k in client.tables.get_alternate_keys(table["logicalName"])
             if k.schema_name.lower() == key_name),
            None,
        )
        if key is None:
            raise RuntimeError(f"Alternate key is missing: {key_name}")
        if key_in_solution(client, table, key.metadata_id.lower()):
            continue
        add_solution_component(key.metadata_id, ENTITY_KEY_COMPONENT, add_required=False)
        print(f"Added alternate key {key.schema_name} to {SOLUTION}.", flush=True)
        if not key_in_solution(client, table, key.metadata_id.lower()):
            missing.append(key.schema_name)
    if missing:
        raise RuntimeError(f"Alternate keys missing from {SOLUTION}: {', '.join(missing)}")
    print(f"Verified {len(TABLES)} alternate keys in {SOLUTION}.", flush=True)


URL_SAFE = "/()?$=&,'.-_:"


def web_api(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> dict | None:
    from auth import get_token
    import urllib.error
    import urllib.parse
    import urllib.request

    request = urllib.request.Request(
        f"{os.environ['DATAVERSE_URL'].rstrip('/')}/api/data/v9.2/"
        f"{urllib.parse.quote(path, safe=URL_SAFE)}",
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
            break
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"{method} {path} failed with {error.code}: {error.read().decode('utf-8', 'replace')[:800]}") from error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            # Transient network failures: PUT/GET/POST calls here are idempotent label/metadata operations.
            if attempt == 6:
                raise
            print(f"{method} {path}: network error ({error}); retrying in {attempt * 15}s.", flush=True)
            time.sleep(attempt * 15)
    return json.loads(payload) if payload else None


def expected_labels(table: dict) -> dict[str, str]:
    labels = {
        f"{PREFIX}_{column['name']}".lower(): column.get("displayName") or label_for(column["name"])
        for column in table["columns"]
    }
    labels.update({
        f"{PREFIX}_{lookup['name']}Id".lower(): label_for(lookup["name"])
        for lookup in table.get("lookups", [])
    })
    return labels


def ensure_column_labels_and_membership() -> None:
    """Converge readable column labels and make every schema column a member of the solution."""
    solution_attributes = None
    changed = 0
    deferred: list[str] = []
    for table in TABLES:
        logical = table["logicalName"]
        wanted = expected_labels(table)
        attributes = web_api(
            "GET",
            f"EntityDefinitions(LogicalName='{logical}')/Attributes"
            "?$select=LogicalName,MetadataId,DisplayName&$filter=IsCustomAttribute eq true",
        )["value"]
        if solution_attributes is None:
            solution = web_api("GET", f"solutions?$select=solutionid&$filter=uniquename eq '{SOLUTION}'")["value"][0]
            solution_attributes = {
                row["objectid"].lower()
                for row in web_api(
                    "GET",
                    "solutioncomponents?$select=objectid"
                    f"&$filter=_solutionid_value eq {solution['solutionid']} and componenttype eq 2",
                )["value"]
            }
        full_root = client_table_is_full_root(logical)
        for attribute in attributes:
            name = attribute["LogicalName"]
            if name not in wanted:
                continue
            current = (attribute["DisplayName"].get("UserLocalizedLabel") or {}).get("Label")
            if current != wanted[name]:
                path = f"EntityDefinitions(LogicalName='{logical}')/Attributes(LogicalName='{name}')"
                try:
                    definition = web_api("GET", path)
                    definition["DisplayName"] = {
                        "@odata.type": "Microsoft.Dynamics.CRM.Label",
                        "LocalizedLabels": [{
                            "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                            "Label": wanted[name],
                            "LanguageCode": 1033,
                        }],
                    }
                    retry_metadata(
                        lambda: web_api("PUT", path, definition, {
                            "MSCRM.MergeLabels": "true",
                            "MSCRM.SolutionUniqueName": SOLUTION,
                        }),
                        f"Relabel {logical}.{name}",
                    )
                except RuntimeError as error:
                    if "still being processed" not in str(error):
                        raise
                    deferred.append(f"{logical}.{name}")
                    print(f"Deferred {logical}.{name}: platform metadata still being processed.", flush=True)
                    continue
                changed += 1
                # The MSCRM.SolutionUniqueName header on the PUT also adds the column to the solution.
                solution_attributes.add(attribute["MetadataId"].lower())
                print(f"Relabelled {logical}.{name}: {current!r} -> {wanted[name]!r}", flush=True)
            if not full_root and attribute["MetadataId"].lower() not in solution_attributes:
                try:
                    add_solution_component(attribute["MetadataId"], 2, add_required=False)
                except RuntimeError as error:
                    if "still being processed" not in str(error):
                        raise
                    deferred.append(f"{logical}.{name} (solution membership)")
                    print(f"Deferred adding {logical}.{name} to {SOLUTION}: metadata still being processed.", flush=True)
                    continue
                solution_attributes.add(attribute["MetadataId"].lower())
                print(f"Added column {logical}.{name} to {SOLUTION}.", flush=True)
    if deferred:
        raise RuntimeError(
            "Column labels not converged (platform still processing; rerun --labels-only later): "
            + ", ".join(deferred)
        )
    print(f"Verified column labels and solution membership ({changed} relabelled).", flush=True)


_FULL_ROOTS: set[str] | None = None


def client_table_is_full_root(logical_name: str) -> bool:
    global _FULL_ROOTS
    if _FULL_ROOTS is None:
        solution = web_api("GET", f"solutions?$select=solutionid&$filter=uniquename eq '{SOLUTION}'")["value"][0]
        roots = web_api(
            "GET",
            "solutioncomponents?$select=objectid,rootcomponentbehavior"
            f"&$filter=_solutionid_value eq {solution['solutionid']} and componenttype eq 1",
        )["value"]
        _FULL_ROOTS = {row["objectid"].lower() for row in roots if row.get("rootcomponentbehavior") == 0}
    metadata = web_api("GET", f"EntityDefinitions(LogicalName='{logical_name}')?$select=MetadataId")
    return metadata["MetadataId"].lower() in _FULL_ROOTS


def ensure_solution_table_roots(client) -> None:
    solutions = list(client.records.list(
        "solution",
        filter=f"uniquename eq '{SOLUTION}'",
        select=["solutionid"],
        top=2,
    ))
    if len(solutions) != 1:
        raise RuntimeError(f"Expected one solution named {SOLUTION}, found {len(solutions)}")
    solution_id = solutions[0]["solutionid"]
    components = list(client.records.list(
        "solutioncomponent",
        filter=f"_solutionid_value eq {solution_id}",
        select=["componenttype", "objectid"],
        top=5000,
    ))
    present = {
        component["objectid"].lower()
        for component in components
        if component["componenttype"] == 1
    }
    for table in TABLES:
        info = client.tables.get(table["logicalName"])
        if info is None:
            raise RuntimeError(f"Table is missing after creation: {table['logicalName']}")
        if info.metadata_id.lower() in present:
            continue
        add_solution_component(info.metadata_id, 1, add_required=True)
        print(f"Added missing table root {table['logicalName']} to {SOLUTION}.", flush=True)
        present.add(info.metadata_id.lower())

    verified = list(client.records.list(
        "solutioncomponent",
        filter=f"_solutionid_value eq {solution_id}",
        select=["componenttype", "objectid"],
        top=5000,
    ))
    verified_ids = {
        component["objectid"].lower()
        for component in verified
        if component["componenttype"] == 1
    }
    missing = [
        table["logicalName"]
        for table in TABLES
        if client.tables.get(table["logicalName"]).metadata_id.lower() not in verified_ids
    ]
    if missing:
        raise RuntimeError(f"Tables missing from {SOLUTION}: {', '.join(missing)}")
    print(f"Verified {len(TABLES)} table roots in {SOLUTION}.", flush=True)


def main() -> None:
    schema_files()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec-only",
        action="store_true",
        help="Regenerate machine-readable schema files without changing Dataverse.",
    )
    parser.add_argument(
        "--tables-only",
        action="store_true",
        help="Ensure tables and columns exist without touching relationships or keys.",
    )
    parser.add_argument(
        "--labels-only",
        action="store_true",
        help="Only converge column display labels and solution membership.",
    )
    args = parser.parse_args()
    if args.spec_only:
        print(f"Wrote schema definitions for {len(TABLES)} tables.")
        return
    if args.labels_only:
        ensure_column_labels_and_membership()
        return
    client = get_client("dv-metadata")
    for index, table in enumerate(TABLES):
        existing = client.tables.get(table["logicalName"])
        if existing:
            print(f"Reusing existing table {table['logicalName']}", flush=True)
            existing_columns = {
                column["SchemaName"].lower()
                for column in client.tables.list_columns(
                    table["logicalName"],
                    select=["SchemaName"],
                )
            }
            missing_columns = {
                name: kind
                for name, kind in dataverse_columns(table).items()
                if name.lower() not in existing_columns
            }
            if missing_columns:
                retry_metadata(
                    lambda: client.tables.add_columns(table["logicalName"], missing_columns),
                    f"Add missing columns to {table['logicalName']}",
                )
                print(
                    f"Added missing columns to {table['logicalName']}: {', '.join(missing_columns)}",
                    flush=True,
                )
            continue
        created = retry_metadata(
            lambda: client.tables.create(
                table["schemaName"],
                dataverse_columns(table),
                solution=SOLUTION,
                primary_column=f"{PREFIX}_Name",
                display_name=table["displayName"],
            ),
            f"Create {table['logicalName']}",
        )
        print(f"Created {table['logicalName']}: {created.schema_name}", flush=True)
        if index < len(TABLES) - 1:
            time.sleep(8)

    if args.tables_only:
        ensure_column_labels_and_membership()
        print("Table and column verification complete; skipped relationships and keys.")
        return

    print("Waiting for table metadata propagation before creating lookups...", flush=True)
    time.sleep(20)
    ensure_solution_table_roots(client)
    for table in TABLES:
        for lookup in table.get("lookups", []):
            field_name = f"{PREFIX}_{lookup['name']}Id"
            try:
                retry_metadata(
                    lambda: client.tables.create_lookup_field(
                        referencing_table=table["logicalName"],
                        lookup_field_name=field_name,
                        referenced_table=lookup["target"],
                        display_name=label_for(lookup["name"]),
                        required=lookup["required"],
                        solution=SOLUTION,
                    ),
                    f"Create lookup {table['logicalName']}.{field_name}",
                )
                print(f"Created lookup {table['logicalName']}.{field_name}", flush=True)
            except Exception as error:
                message = str(error).lower()
                if not any(marker in message for marker in ("already exists", "duplicate", "not unique")):
                    raise
                print(f"Reusing lookup {table['logicalName']}.{field_name}", flush=True)
            time.sleep(4)

    print("Waiting for lookup metadata propagation before creating alternate keys...", flush=True)
    time.sleep(20)
    for table in TABLES:
        key_name = f"{table['schemaName']}DemoKey"
        existing_keys = client.tables.get_alternate_keys(table["logicalName"])
        if any(key.schema_name.lower() == key_name.lower() for key in existing_keys):
            print(f"Reusing alternate key {key_name}", flush=True)
            continue
        key = retry_metadata(
            lambda: client.tables.create_alternate_key(
                table["logicalName"],
                key_name,
                [f"{PREFIX}_demokey"],
                display_name=f"{table['displayName']} Demo Key",
            ),
            f"Create alternate key {key_name}",
        )
        print(f"Created alternate key {key.schema_name}: {key.status}", flush=True)
        time.sleep(3)
    ensure_solution_keys(client)
    ensure_column_labels_and_membership()
    print("Datamodel metadata provisioning complete.", flush=True)


if __name__ == "__main__":
    main()
