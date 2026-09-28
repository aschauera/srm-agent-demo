"""Generate fictional SRM CSV fixtures and optionally upsert them into Dataverse."""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schema" / "tables"
DATA_DIR = ROOT / "data"
PREFIX = "mag"
TABLE_FILES = {
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

SUPPLIERS = [
    ("SUP-001", "Asterion Precision Components GmbH", "900000001", "Germany", "Europe", "Green", 7200000, True),
    ("SUP-002", "Bluehaven Industrial Systems Ltd", "900000002", "United Kingdom", "Europe", "Yellow", 5100000, True),
    ("SUP-003", "Cedar Peak Manufacturing Inc", "900000003", "United States", "North America", "Green", 8300000, True),
    ("SUP-004", "Dovetail Motion Technologies GmbH", "900000004", "Germany", "Europe", "Not rated", 4600000, True),
    ("SUP-005", "Emberline Materials Co", "900000005", "United States", "North America", "Not rated", 3900000, True),
    ("SUP-006", "Fjordstone Industrial AB", "900000006", "Sweden", "Europe", "Not rated", 6100000, True),
    ("SUP-007", "Granite Harbor Components Sdn Bhd", "900000007", "Malaysia", "Asia", "Not rated", 2800000, True),
    ("SUP-008", "Hawthorn Ridge Automation SAS", "900000008", "France", "Europe", "Not rated", 9400000, True),
    ("SUP-009", "Ironwood Circuitry Sp z o.o.", "900000009", "Poland", "Europe", "Not rated", 3300000, True),
    ("SUP-010", "Juniper Vale Fabrication LLC", "", "United States", "North America", "Not rated", 1700000, True),
    ("SUP-011", "Kestrel Field Assemblies Pty Ltd", "", "Australia", "Asia Pacific", "Not rated", 0, False),
    ("SUP-012", "Lumen Forge Industrial Systems Ltd", "900000012", "United States", "North America", "Red", 12700000, True),
]


def utc_datetime(value: date | datetime) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def day_offset(days: int) -> str:
    return utc_datetime(datetime.now(timezone.utc) + timedelta(days=days))


def demo_rows() -> dict[str, list[dict]]:
    today = datetime.now(timezone.utc).date()
    rows: dict[str, list[dict]] = {table: [] for table in TABLE_FILES}
    suppliers_by_code: dict[str, dict] = {}

    for index, (code, legal_name, duns, country, region, rating, spend, active_spend) in enumerate(SUPPLIERS, 1):
        supplier = {
            "DemoKey": code,
            "Name": legal_name,
            "SupplierCode": code,
            "LegalName": legal_name,
            "DUNS": duns,
            "HasDUNS": bool(duns),
            "Street": f"{100 + index} Fictional Industrial Way",
            "City": ["Riverton", "Northpoint", "Lakeview"][index % 3],
            "Country": country,
            "Region": region,
            "Website": f"https://{code.lower()}.example.invalid",
            "BusinessCategory": ["Precision machining", "Electrical systems", "Industrial materials"][index % 3],
            "ManufacturingZone": f"{region} Demo Zone",
            "MagnaDivision": ["Powertrain", "Body & Chassis", "Electronics"][index % 3],
            "AnnualSpend": spend,
            "HasActiveSpend": active_spend,
            "CurrentMagnaRating": rating,
            "CurrentCofaceScore": 2 if code == "SUP-012" else (8 if code == "SUP-008" else 5),
            "ContactName": f"Contact {index:02d}",
            "ContactEmail": f"contact{index:02d}@example.com",
            "FactoryLocation": f"{country} manufacturing site {index:02d}",
        }
        rows["mag_supplier"].append(supplier)
        suppliers_by_code[code] = supplier

    # The first seven rows exercise GSA reuse, expiration, and mandatory re-review.
    for index in range(1, 8):
        code = f"SUP-{index:03d}"
        expired = index in (4, 5)
        mandatory = index in (6, 7)
        rows["mag_gsaratingrecord"].append({
            "DemoKey": f"GSA-{code}",
            "Name": f"GSA mock rating {code}",
            "SupplierDemoKey": code,
            "DUNS": suppliers_by_code[code]["DUNS"],
            "Rating": suppliers_by_code[code]["CurrentMagnaRating"] if index <= 3 else ("Yellow" if index == 6 else "Red"),
            "Remarks": "Synthetic GSA record for branch testing; no real procurement data.",
            "RatingDate": utc_datetime(today - timedelta(days=540 if expired else 120)),
            "ExpiryDate": utc_datetime(today - timedelta(days=30) if expired else today + timedelta(days=365)),
            "MandatoryRereview": mandatory,
            "ReviewerName": f"Demo Reviewer {index:02d}",
            "SyntheticData": True,
        })

    coface_profiles = {
        "SUP-001": (8, -240), "SUP-002": (5, -240), "SUP-003": (9, -240),
        "SUP-004": (4, -760), "SUP-005": (3, -760), "SUP-006": (6, -760),
        "SUP-007": (5, -760), "SUP-008": (8, -100), "SUP-009": (5, -150),
        "SUP-012": (2, -800),
    }
    for code, (score, age_days) in coface_profiles.items():
        supplier = suppliers_by_code[code]
        tier = "Low" if score >= 7 else ("Medium" if score >= 4 else "High")
        rows["mag_cofacecreditrecord"].append({
            "DemoKey": f"COF-{code}-EXACT",
            "Name": f"Coface mock response {code}",
            "SupplierDemoKey": code,
            "DUNS": supplier["DUNS"],
            "SupplierName": supplier["LegalName"],
            "Country": supplier["Country"],
            "Score": score,
            "RiskTier": tier,
            "PaymentTrackRecord": "Synthetic: regular payment history with isolated timing variance.",
            "NegativeAlerts": "Synthetic demo response; see linked adverse-event mock rows if present.",
            "RecommendedCreditLimit": 250000 + score * 100000,
            "AssessmentDate": utc_datetime(today + timedelta(days=age_days + 30)),
            "FinancialDataThrough": utc_datetime(today + timedelta(days=age_days)),
            "ReportLink": f"https://example.invalid/coface/{code}",
            "MatchConfidence": 1.0,
            "SyntheticData": True,
        })

    # No-DUNS cases return a fuzzy-match shortlist rather than a trusted score.
    for code, base_score, age in (("SUP-010", 6, -180), ("SUP-011", 7, -400)):
        supplier = suppliers_by_code[code]
        for match_index, confidence in ((1, 0.91), (2, 0.67)):
            rows["mag_cofacecreditrecord"].append({
                "DemoKey": f"COF-{code}-MATCH-{match_index}",
                "Name": f"Fuzzy Coface candidate {match_index} for {code}",
                "SupplierDemoKey": code,
                "DUNS": "",
                "SupplierName": supplier["LegalName"] if match_index == 1 else f"{supplier['LegalName']} Holdings",
                "Country": supplier["Country"],
                "Score": base_score if match_index == 1 else max(1, base_score - 2),
                "RiskTier": "Medium",
                "PaymentTrackRecord": "Synthetic fuzzy-match candidate; reviewer confirmation required.",
                "NegativeAlerts": "No identity-confirmed credit alerts; candidate is not an authoritative match.",
                "RecommendedCreditLimit": 350000,
                "AssessmentDate": utc_datetime(today + timedelta(days=age + 30)),
                "FinancialDataThrough": utc_datetime(today + timedelta(days=age)),
                "ReportLink": f"https://example.invalid/coface/fuzzy/{code}/{match_index}",
                "MatchConfidence": confidence,
                "SyntheticData": True,
            })

    for index, supplier in enumerate(rows["mag_supplier"], 1):
        if not supplier["HasDUNS"]:
            continue
        rows["mag_dnbprofile"].append({
            "DemoKey": f"DNB-{supplier['SupplierCode']}",
            "Name": f"Public profile for {supplier['SupplierCode']}",
            "SupplierDemoKey": supplier["SupplierCode"],
            "DUNS": supplier["DUNS"],
            "LegalName": supplier["LegalName"],
            "Street": supplier["Street"],
            "City": supplier["City"],
            "Country": supplier["Country"],
            "Region": supplier["Region"],
            "Website": supplier["Website"],
            "BusinessCategory": supplier["BusinessCategory"],
            "ManufacturingZone": supplier["ManufacturingZone"],
            "EstablishedYear": 1985 + index,
            "ShareholderSummary": "Synthetic placeholder profile; source attribution is illustrative only.",
            "ProductLines": f"Demo product family {index}; fictional content.",
            "SourceUrl": f"https://example.invalid/public-profile/{supplier['SupplierCode']}",
            "ProfileCheckedOn": utc_datetime(today),
            "SyntheticData": True,
        })

    warning_specs = [
        ("EW-2026-001", "SUP-012", "Potential liquidity stress and a reported large commercial arbitration.",
         "Unconfirmed market report", "Possible production interruption; investigate before rating.", 8500000,
         "liquidity crisis; arbitration; operating losses", "High", "Mandatory prompt", "Open", True),
        ("EW-2026-002", "SUP-004", "Supplier mentioned a temporary production scheduling disruption.",
         "Buyer observation", "Short-term delivery risk; no confirmed financial impact.", 250000,
         "production delay", "Medium", "Mandatory prompt", "Under review", False),
        ("EW-2026-003", "SUP-008", "Minor logistics delay reported by a plant contact.",
         "Operational note", "Limited short-term impact.", 50000,
         "logistics delay", "Low", "Soft reminder", "Resolved", False),
    ]
    for warning_ref, supplier_key, description, source, impact, volume, tags, level, prompt, status, reminder in warning_specs:
        rows["mag_earlywarning"].append({
            "DemoKey": warning_ref,
            "Name": warning_ref,
            "WarningRef": warning_ref,
            "SupplierDemoKey": supplier_key,
            "Description": description,
            "RumourSource": source,
            "PotentialImpact": impact,
            "AffectedVolume": volume,
            "RiskTags": tags,
            "Materiality": level,
            "PromptBehavior": prompt,
            "ResolutionStatus": status,
            "Reminder24HourSent": reminder,
            "SubmittedOn": utc_datetime(today - timedelta(days=2)),
        })

    gsa_precheck = {
        **{f"SUP-{n:03d}": "Valid active rating" for n in range(1, 4)},
        "SUP-004": "Rating expired", "SUP-005": "Rating expired",
        "SUP-006": "Valid active rating", "SUP-007": "Valid active rating",
        "SUP-008": "No matching supplier", "SUP-009": "No matching supplier",
        "SUP-010": "Skip - no DUNS", "SUP-011": "Skip - no DUNS",
        "SUP-012": "No matching supplier",
    }
    paths = {
        **{f"SUP-{n:03d}": ("GSA Reuse" if n <= 3 else "Full Review") for n in range(1, 8)},
        "SUP-008": "Coface Fast-Track", "SUP-009": "Coface Fast-Track",
        "SUP-010": "Full Review", "SUP-011": "Full Review", "SUP-012": "Full Review",
    }
    stages = {"SUP-008": 4, "SUP-009": 4, "SUP-012": 3}
    for index, supplier in enumerate(rows["mag_supplier"], 1):
        code = supplier["SupplierCode"]
        reuse = code in ("SUP-001", "SUP-002", "SUP-003")
        fast = code in ("SUP-008", "SUP-009")
        gsa = next((item for item in rows["mag_gsaratingrecord"] if item["SupplierDemoKey"] == code), None)
        coface = (
            next((item for item in rows["mag_cofacecreditrecord"] if item["SupplierDemoKey"] == code), None)
            if supplier["HasDUNS"] else None
        )
        age_months = max(0, (today - date.fromisoformat(coface["FinancialDataThrough"][:10])).days // 30) if coface else None
        rating = coface["RiskTier"] if coface else "Not rated"
        preliminary = (
            "Green" if coface and coface["Score"] >= 7 else
            "Yellow" if coface and coface["Score"] >= 4 else
            "Red" if coface else "Not rated"
        )
        request_key = f"REQ-2026-{index:03d}"
        warning_key = next((w["DemoKey"] for w in rows["mag_earlywarning"] if w["SupplierDemoKey"] == code), "")
        rows["mag_financialreviewrequest"].append({
            "DemoKey": request_key,
            "Name": request_key,
            "RequestRef": request_key,
            "SupplierDemoKey": code,
            "BuyerName": f"Buyer {index:02d}",
            "BuyerEmail": f"buyer{index:02d}@example.com",
            "ReviewerName": f"Reviewer {((index - 1) % 4) + 1:02d}",
            "Division": supplier["MagnaDivision"],
            "ReviewStatus": "Completed" if reuse else "In Progress",
            "ReviewPath": paths[code],
            "GSAPrecheckResult": gsa_precheck[code],
            "GSARating": gsa["Rating"] if gsa else "",
            "GSARemarks": gsa["Remarks"] if gsa else "",
            "GSARatingDate": gsa["RatingDate"] if gsa else "",
            "GSARatingExpiry": gsa["ExpiryDate"] if gsa else "",
            "CofaceScore": coface["Score"] if coface else "",
            "CofaceRiskTier": coface["RiskTier"] if coface else "Unavailable",
            "CofaceAssessmentDate": coface["AssessmentDate"] if coface else "",
            "CofaceDataAgeMonths": age_months if age_months is not None else "",
            "CofaceWithin18Months": age_months is not None and age_months <= 18,
            "PreliminaryRating": gsa["Rating"] if reuse else preliminary,
            "NarrativeDraft": (
                "No DUNS number provided; full Coface credit score unavailable. Assessment relies on "
                "self-submitted statements and supporting credentials. Fuzzy candidates require reviewer "
                "identity confirmation."
                if not supplier["HasDUNS"] else
                "Synthetic demo analysis only. The reviewer must confirm or override any preliminary rating."
                if not reuse else ""
            ),
            "FinalRating": gsa["Rating"] if reuse else "",
            "RatingDate": gsa["RatingDate"] if reuse else "",
            "RatingExpiry": gsa["ExpiryDate"] if reuse else "",
            "Remarks": gsa["Remarks"] if reuse else "",
            "ReviewerOverride": False,
            "ArchiveFolderLink": f"https://example.invalid/erfx/{request_key}" if code in ("SUP-008", "SUP-012") else "",
            "CurrentStage": 5 if reuse else stages.get(code, 2),
            "ClarificationsClosed": reuse,
            "DUNSNumber": supplier["DUNS"],
            "NoDUNS": not supplier["HasDUNS"],
            "DnBAutofillConfirmed": supplier["HasDUNS"],
            "MandatoryReReview": code in ("SUP-006", "SUP-007"),
            "ReviewerNotified": True,
            # Later-stage flags mirror CurrentStage; shortcut paths leave bypassed stages unset.
            "CofaceRetrieved": coface is not None and not reuse,
            "DocRequestSent": not reuse and not fast,
            "ReminderCount": 1 if code in ("SUP-004", "SUP-012") else 0,
            "DocsReceived": code == "SUP-012",
            "WorkingPaperComplete": False,
            "MetricsComputed": False,
            "NonFinancialRisksLogged": False,
            "FinalRatingConfirmed": False,
            "BuyerNotified": reuse,
            "ArchiveComplete": False,
            "RecordLocked": False,
            "GSAPushBackComplete": False,
            "SummaryRefreshed": False,
            "SourceEarlyWarningDemoKey": warning_key,
        })

    for request in rows["mag_financialreviewrequest"]:
        code = request["SupplierDemoKey"]
        if code in ("SUP-001", "SUP-002", "SUP-003"):
            continue
        rows["mag_documentrequest"].append({
            "DemoKey": f"DOCREQ-{request['RequestRef']}-FIN",
            "Name": f"Financial statement request for {request['RequestRef']}",
            "ReviewRequestDemoKey": request["DemoKey"],
            "RequestType": "Financial statements",
            "SentOn": utc_datetime(today - timedelta(days=8 if code == "SUP-012" else 2)),
            "Day3ReminderSentOn": utc_datetime(today - timedelta(days=5)) if code == "SUP-012" else "",
            "Day7EscalationSentOn": utc_datetime(today - timedelta(days=1)) if code == "SUP-012" else "",
            "ResponseReceived": code == "SUP-012",
            "RequestStatus": "Received" if code == "SUP-012" else "Sent",
            "RecipientEmail": suppliers_by_code[code]["ContactEmail"],
            "ChecklistSummary": "3 full fiscal years plus latest interim statements and non-financial questionnaire.",
        })

    for code in ("SUP-004", "SUP-005", "SUP-006", "SUP-007", "SUP-010", "SUP-011", "SUP-012"):
        request_key = f"REQ-2026-{int(code[-3:]):03d}"
        rows["mag_supplierdocument"].append({
            "DemoKey": f"DOC-{code}-2025-FS",
            "Name": f"Synthetic FY2025 financial statements - {code}",
            "ReviewRequestDemoKey": request_key,
            "SupplierDemoKey": code,
            "DocumentType": "Income statement",
            "FiscalYear": 2025,
            "Period": "Full year",
            "OCRStatus": "Complete" if code == "SUP-012" else "Needs review",
            "FileName": f"{code}-FY2025-financials-demo.pdf",
            "ArchiveSubfolder": "Supplier Submitted Financial Documents",
            "Duplicate": False,
            "MetadataTags": "synthetic;financial statement;FY2025",
            "SourceSystem": "Mock supplier submission",
        })

    working_paper_specs = {
        "SUP-004": [(2025, 45000000, 1800000, 4000000, 0.55, 1.25)],
        "SUP-005": [(2025, 38000000, -600000, -900000, 0.68, 0.98)],
        "SUP-006": [(2025, 64000000, 2100000, 1300000, 0.61, 1.12)],
        "SUP-007": [(2025, 29000000, 350000, 450000, 0.58, 1.05)],
        "SUP-010": [(2025, 19000000, 600000, 800000, 0.47, 1.4)],
        "SUP-011": [(2025, 16000000, 250000, 150000, 0.52, 1.16)],
        "SUP-012": [
            (2023, 100000000, 3000000, 8000000, 0.50, 1.33),
            (2024, 95000000, -2000000, -2000000, 0.69, 0.97),
            (2025, 88000000, -8000000, -12000000, 0.78, 0.82),
            (2026, 35000000, -5000000, -8000000, 0.83, 0.67),
        ],
    }
    for code, years in working_paper_specs.items():
        supplier = suppliers_by_code[code]
        request_key = f"REQ-2026-{int(code[-3:]):03d}"
        for year, revenue, income, cashflow, leverage, liquidity in years:
            assets = int(revenue * 1.8)
            debt = int(assets * leverage)
            gross_profit = int(revenue * (0.22 if code == "SUP-012" else 0.31))
            rows["mag_financialworkingpaper"].append({
                "DemoKey": f"WP-{code}-{year}",
                "Name": f"{code} working paper {year}",
                "ReviewRequestDemoKey": request_key,
                "SupplierDemoKey": code,
                "FiscalYear": year,
                "Period": "Interim" if year == 2026 else "Full year",
                "Currency": "USD",
                "Revenue": revenue,
                "CostOfGoodsSold": revenue - gross_profit,
                "GrossProfit": gross_profit,
                "NetIncome": income,
                "OperatingCashFlow": cashflow,
                "CurrentAssets": int(revenue * liquidity * 0.25),
                "CurrentLiabilities": int(revenue * 0.25),
                "TotalAssets": assets,
                "TotalDebt": debt,
                "AccountsReceivable": int(revenue * 0.21),
                "Inventory": int(revenue * (0.19 if code == "SUP-012" else 0.11)),
                "LeverageRatio": leverage,
                "LiquidityRatio": liquidity,
                "GrossMargin": round(gross_profit / revenue, 4),
                "AssetTurnover": round(revenue / assets, 4),
                "YearOverYearDelta": -0.08 if code == "SUP-012" and year >= 2024 else 0.03,
                "AnomalyFlags": "consecutive net losses;negative operating cash flow;high leverage"
                    if code == "SUP-012" and year >= 2024 else "",
                "ExtractionConfidence": 0.94 if code == "SUP-012" else 0.88,
            })

    risk_specs = [
        ("SUP-004", "Customer concentration", "Medium", "Largest customer is approximately 38% of sales.", 0.38, "Mixed"),
        ("SUP-005", "Litigation", "Medium", "Synthetic pending commercial dispute; verify with reviewer.", 0, "Owned"),
        ("SUP-006", "Off-balance-sheet guarantee", "Low", "Synthetic guarantee disclosure requires confirmation.", 0, "Owned"),
        ("SUP-007", "Management turnover", "Medium", "Synthetic report of recent finance leadership change.", 0, "Mixed"),
        ("SUP-010", "Owned vs leased assets", "Medium", "Manufacturing site ownership evidence requested.", 0, "Leased"),
        ("SUP-011", "Customer concentration", "Low", "Preliminary supplier response indicates diversified customers.", 0.22, "Unknown"),
        ("SUP-012", "Arbitration", "High", "Synthetic high-value arbitration disclosure; supporting evidence required.", 0, "Leased"),
        ("SUP-012", "Customer concentration", "High", "Top single customer is reported at 62% of revenue.", 0.62, "Leased"),
        ("SUP-012", "Off-balance-sheet guarantee", "Medium", "Synthetic contingent guarantee exposure needs analyst verification.", 0, "Leased"),
        ("SUP-012", "Management turnover", "Medium", "Synthetic report of two senior management changes.", 0, "Leased"),
    ]
    for index, (code, kind, severity, details, concentration, ownership) in enumerate(risk_specs, 1):
        rows["mag_nonfinancialriskitem"].append({
            "DemoKey": f"NFR-{index:03d}",
            "Name": f"{kind} - {code}",
            "ReviewRequestDemoKey": f"REQ-2026-{int(code[-3:]):03d}",
            "SupplierDemoKey": code,
            "RiskType": kind,
            "Severity": severity,
            "Details": details,
            "SourceUrl": f"https://example.invalid/risk-evidence/NFR-{index:03d}",
            "EventDate": utc_datetime(today - timedelta(days=25 + index)),
            "CustomerConcentration": concentration,
            "OwnershipStatus": ownership,
            "EstimatedExposure": 2200000 if code == "SUP-012" and kind == "Arbitration" else 0,
            "Verified": False,
        })

    for index, request in enumerate(rows["mag_financialreviewrequest"], 1):
        code = request["SupplierDemoKey"]
        reuse = request["ReviewPath"] == "GSA Reuse"
        rows["mag_communicationlog"].append({
            "DemoKey": f"COM-{request['RequestRef']}-NOTICE",
            "Name": f"{'GSA reuse filing notice' if reuse else 'Review initiation notice'} - {request['RequestRef']}",
            "ReviewRequestDemoKey": request["DemoKey"],
            "SupplierDemoKey": code,
            "Direction": "Outbound",
            "Channel": "Email",
            "Subject": "Synthetic SRM review status update",
            "Body": "Fictional demo message. Human reviewer remains accountable for any final rating.",
            "CallTranscript": "",
            "AISummary": "",
            "Language": "English",
            "TranslatedText": "",
            "OccurredOn": utc_datetime(today - timedelta(days=index)),
            "ActorName": "SRM Demo Workflow",
        })

    # Keep one audit ledger event for each request and explicit events for key mock integrations.
    for index, request in enumerate(rows["mag_financialreviewrequest"], 1):
        rows["mag_reviewaudittrail"].append({
            "DemoKey": f"AUD-{request['RequestRef']}-CREATED",
            "Name": f"Request created {request['RequestRef']}",
            "ReviewRequestDemoKey": request["DemoKey"],
            "SupplierDemoKey": request["SupplierDemoKey"],
            "Action": "Request created and branch evaluated",
            "Actor": "SRM Orchestrator (demo)",
            "ActorType": "Agent",
            "OccurredOn": utc_datetime(today - timedelta(days=index)),
            "SystemTouched": "Dataverse mock",
            "Details": f"Pre-check: {request['GSAPrecheckResult']}; path: {request['ReviewPath']}. Synthetic seed event.",
        })

    for warning in rows["mag_earlywarning"]:
        rows["mag_reviewaudittrail"].append({
            "DemoKey": f"AUD-{warning['DemoKey']}-TRIAGE",
            "Name": f"Early warning triaged {warning['DemoKey']}",
            "SupplierDemoKey": warning["SupplierDemoKey"],
            "Action": "Early warning materiality assessed",
            "Actor": "Early Warning Triage (demo)",
            "ActorType": "Agent",
            "OccurredOn": warning["SubmittedOn"],
            "SystemTouched": "eRFX mock",
            "Details": f"Materiality {warning['Materiality']}; prompt {warning['PromptBehavior']}. Synthetic seed event.",
        })

    for code, category, severity, title in [
        ("SUP-004", "Litigation or arbitration", "Medium", "Synthetic commercial dispute notice"),
        ("SUP-005", "Regulatory fine", "Low", "Synthetic compliance notice"),
        ("SUP-012", "Debt default", "High", "Synthetic payment default indicator"),
        ("SUP-012", "Litigation or arbitration", "High", "Synthetic arbitration filing notice"),
        ("SUP-008", "Production suspension", "Low", "Synthetic temporary production update"),
    ]:
        rows["mag_adversenewsevent"].append({
            "DemoKey": f"NEWS-{code}-{len(rows['mag_adversenewsevent']) + 1:02d}",
            "Name": title,
            "SupplierDemoKey": code,
            "Category": category,
            "Severity": severity,
            "Title": title,
            "Description": "Fictional monitoring result for demo flow testing; not a real adverse event.",
            "ReleaseDate": utc_datetime(today - timedelta(days=12)),
            "SourceUrl": "https://example.invalid/synthetic-news",
            "Resolved": False,
            "SyntheticData": True,
        })

    # Illustrative mappings and thresholds are deliberately unapproved and demo-only.
    for key, low, high, rating, guidance in [
        ("RULE-COF-RED", 1, 3, "Red", "Illustrative: tighter short-term purchasing limit; reviewer approval required."),
        ("RULE-COF-YELLOW", 4, 6, "Yellow", "Illustrative: standard monitoring; reviewer approval required."),
        ("RULE-COF-GREEN", 7, 10, "Green", "Illustrative: normal monitoring; reviewer approval required."),
    ]:
        rows["mag_ratingconversionrule"].append({
            "DemoKey": key,
            "Name": key,
            "RuleName": key,
            "MinimumScore": low,
            "MaximumScore": high,
            "MagnaRating": rating,
            "CreditLimitGuidance": guidance,
            "ApprovalStatus": "Draft - demo only",
            "EffectiveFrom": utc_datetime(today),
            "DemoOnly": True,
        })
    for key, metric, operator, threshold, points, dimension, signal in [
        ("RULE-RISK-LEV", "LeverageRatio", "Greater than", 0.75, 3, "Leverage", "High leverage signal"),
        ("RULE-RISK-LIQ", "LiquidityRatio", "Less than", 1.0, 3, "Liquidity", "Liquidity pressure signal"),
        ("RULE-RISK-CFO", "OperatingCashFlow", "Less than", 0, 2, "Cash flow", "Negative operating cash flow signal"),
        ("RULE-RISK-CONC", "CustomerConcentration", "Greater than", 0.6, 2, "Non-financial", "Customer concentration signal"),
    ]:
        rows["mag_riskscoringrule"].append({
            "DemoKey": key,
            "Name": key,
            "Metric": metric,
            "Operator": operator,
            "Threshold": threshold,
            "Points": points,
            "Dimension": dimension,
            "Signal": signal,
            "ApprovalStatus": "Draft - demo only",
            "DemoOnly": True,
        })

    summary_suppliers = [s for s in rows["mag_supplier"] if s["HasActiveSpend"]]
    for supplier in summary_suppliers:
        code = supplier["SupplierCode"]
        score = supplier["CurrentCofaceScore"]
        rows["mag_supplieronepagesummary"].append({
            "DemoKey": f"SUMMARY-{code}-V1",
            "Name": f"One-page summary {code} v1",
            "SupplierDemoKey": code,
            "SummaryVersion": "1",
            "CompanyProfile": f"Synthetic profile for {supplier['LegalName']} in {supplier['Country']}.",
            "SourceAttribution": "Synthetic D&B/public-registry mock; example.invalid links only.",
            "RiskMetricsPanel": f"Latest synthetic Coface score: {score}/10; Magna rating: {supplier['CurrentMagnaRating']}.",
            "TrendInterpretation": (
                "Synthetic illustration: declining revenue and negative operating cash flow across seeded "
                "fiscal periods; not validated financial data."
                if code == "SUP-012" else
                "No validated historical trend; display seed data as illustrative only."
            ),
            "AdverseEventDigest": "See linked synthetic adverse-news rows; no external source was queried.",
            "AlertBanner": "High materiality synthetic early warning" if code == "SUP-012" else "",
            "GeneratedOn": utc_datetime(today),
            "PDFExportUrl": "",
            "HasActiveSpend": True,
        })

    # Seed archive records in each fixed category for in-progress examples; keep folders unlocked.
    for code in ("SUP-008", "SUP-012"):
        request_key = f"REQ-2026-{int(code[-3:]):03d}"
        folder = f"{suppliers_by_code[code]['DUNS'] or code} - {suppliers_by_code[code]['LegalName']} - {request_key}"
        for index, subfolder in enumerate(CHOICES_LOCAL_ARCHIVE, 1):
            rows["mag_archiverecord"].append({
                "DemoKey": f"ARCH-{code}-{index}",
                "Name": f"{subfolder} placeholder for {request_key}",
                "SupplierDemoKey": code,
                "ReviewRequestDemoKey": request_key,
                "FolderIdentifier": folder,
                "Subfolder": subfolder,
                "ItemType": "Document" if index == 1 else "Risk extract" if index == 2 else "Email" if index == 3 else "Working paper",
                "ItemName": f"Synthetic supporting item {index} for {request_key}",
                "ArchiveUrl": f"https://example.invalid/erfx/archive/{request_key}/{index}",
                "Locked": False,
                "Version": 1,
                "SearchableMetadata": json.dumps({
                    "DUNS": suppliers_by_code[code]["DUNS"],
                    "reviewRef": request_key,
                    "division": suppliers_by_code[code]["MagnaDivision"],
                    "rating": suppliers_by_code[code]["CurrentMagnaRating"],
                    "synthetic": True,
                }),
                "SourceSystem": "eRFX mock",
                "UploadedOn": utc_datetime(today - timedelta(days=index)),
            })

    # Link Early Warning rows back to requests in the second import pass.
    warning_to_request = {
        warning["DemoKey"]: f"REQ-2026-{int(warning['SupplierDemoKey'][-3:]):03d}"
        for warning in rows["mag_earlywarning"]
        if warning["SupplierDemoKey"] in ("SUP-012", "SUP-004", "SUP-008")
    }
    for warning in rows["mag_earlywarning"]:
        warning["ReviewRequestDemoKey"] = warning_to_request.get(warning["DemoKey"], "")

    return rows


CHOICES_LOCAL_ARCHIVE = [
    "Supplier Submitted Financial Documents",
    "Third-Party Credit Records",
    "Communication Audit Trail",
    "Final Review Deliverables",
]


def export_csv(rows_by_table: dict[str, list[dict]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for table_name, filename in TABLE_FILES.items():
        schema_path = SCHEMA_DIR / f"{table_name.removeprefix('mag_')}.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        headers = ["DemoKey", "Name"]
        headers.extend(column["name"] for column in schema["columns"] if column["name"] not in headers)
        headers.extend(f"{lookup['name']}DemoKey" for lookup in schema.get("lookups", []))
        with (DATA_DIR / filename).open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows_by_table[table_name])
        print(f"Wrote {filename}: {len(rows_by_table[table_name])} rows")


def import_csv(rows_by_table: dict[str, list[dict]]) -> None:
    from auth import get_client
    from PowerPlatform.Dataverse.models.upsert import UpsertItem

    client = get_client("dv-data")
    specs = {
        table: json.loads((SCHEMA_DIR / f"{table.removeprefix('mag_')}.json").read_text(encoding="utf-8"))
        for table in TABLE_FILES
    }
    choices = json.loads((ROOT / "schema" / "choices.json").read_text(encoding="utf-8"))
    choice_values = {
        key: {label: value for label, value in zip(info["options"], info["values"])}
        for key, info in choices.items()
    }
    table_infos = {table: client.tables.get(table) for table in TABLE_FILES}
    if any(info is None for info in table_infos.values()):
        missing = [table for table, info in table_infos.items() if info is None]
        raise RuntimeError(f"Required tables are missing from Dataverse: {', '.join(missing)}")
    for table, spec in specs.items():
        expected_key = f"{spec['schemaName']}DemoKey".lower()
        for attempt in range(24):
            keys = client.tables.get_alternate_keys(table)
            key = next((item for item in keys if item.schema_name.lower() == expected_key), None)
            if key is None:
                raise RuntimeError(f"Missing DemoKey alternate key on {table}")
            if key.status == "Active":
                break
            if key.status == "Failed":
                raise RuntimeError(f"DemoKey alternate key failed to activate on {table}")
            print(f"Waiting for {table} DemoKey index ({key.status})...", flush=True)
            time.sleep(5)
        else:
            raise TimeoutError(f"Timed out waiting for DemoKey alternate key on {table}")

    records_by_table: dict[str, list[dict]] = {}
    for table, filename in TABLE_FILES.items():
        with (DATA_DIR / filename).open(newline="", encoding="utf-8-sig") as stream:
            records_by_table[table] = list(csv.DictReader(stream))
    ids_by_table: dict[str, dict[str, str]] = {}

    def load(table: str, rows: list[dict]) -> None:
        spec = specs[table]
        column_types = {column["name"]: column for column in spec["columns"]}
        payloads = []
        for row in rows:
            key = row["DemoKey"]
            payload = {"mag_name": row["Name"]}
            for field_name, definition in column_types.items():
                value = row.get(field_name, "")
                if value == "" or definition["type"] == "file":
                    continue
                logical_name = f"{PREFIX}_{field_name.lower()}"
                kind = definition["type"]
                if kind == "choice":
                    payload[logical_name] = choice_values[definition["choice"]][value]
                elif kind == "boolean":
                    payload[logical_name] = value.lower() == "true"
                elif kind in ("integer", "money", "decimal"):
                    payload[logical_name] = int(value) if kind == "integer" else float(value)
                else:
                    payload[logical_name] = value
            for lookup in spec.get("lookups", []):
                reference_key = row.get(f"{lookup['name']}DemoKey", "")
                if not reference_key:
                    continue
                target_ids = ids_by_table.get(lookup["target"], {})
                target_id = target_ids.get(reference_key)
                if not target_id:
                    raise RuntimeError(
                        f"Unresolved {lookup['name']} reference {reference_key!r} "
                        f"from {table}:{key}; load dependency {lookup['target']} first."
                    )
                target_info = table_infos[lookup["target"]]
                navigation_name = f"{PREFIX}_{lookup['name']}Id"
                payload[f"{navigation_name}@odata.bind"] = (
                    f"/{target_info.entity_set_name}({target_id})"
                )
            payloads.append(UpsertItem(
                alternate_key={f"{PREFIX}_demokey": key},
                record=payload,
            ))

        if payloads:
            for index, payload in enumerate(payloads, 1):
                client.records.upsert(table, [payload])
                if index == len(payloads) or index % 10 == 0:
                    print(f"Upserted {table}: {index}/{len(payloads)}", flush=True)
        info = table_infos[table]
        primary_id = info.primary_id_attribute or f"{table}id"
        existing = client.records.list(
            table,
            select=[primary_id, f"{PREFIX}_demokey"],
            top=5000,
        )
        ids_by_table[table] = {
            item[f"{PREFIX}_demokey"]: item[primary_id]
            for item in existing
            if item.get(f"{PREFIX}_demokey")
        }

    # Parent rows are loaded before their dependants. Early warnings are replayed
    # after requests exist to materialize their bidirectional relationship.
    order = [
        ("mag_supplier", records_by_table["mag_supplier"]),
        ("mag_ratingconversionrule", records_by_table["mag_ratingconversionrule"]),
        ("mag_riskscoringrule", records_by_table["mag_riskscoringrule"]),
        ("mag_earlywarning", [
            {**row, "ReviewRequestDemoKey": ""}
            for row in records_by_table["mag_earlywarning"]
        ]),
        ("mag_gsaratingrecord", records_by_table["mag_gsaratingrecord"]),
        ("mag_cofacecreditrecord", records_by_table["mag_cofacecreditrecord"]),
        ("mag_dnbprofile", records_by_table["mag_dnbprofile"]),
        ("mag_financialreviewrequest", records_by_table["mag_financialreviewrequest"]),
        ("mag_earlywarning", records_by_table["mag_earlywarning"]),
        ("mag_documentrequest", records_by_table["mag_documentrequest"]),
        ("mag_supplierdocument", records_by_table["mag_supplierdocument"]),
        ("mag_financialworkingpaper", records_by_table["mag_financialworkingpaper"]),
        ("mag_nonfinancialriskitem", records_by_table["mag_nonfinancialriskitem"]),
        ("mag_communicationlog", records_by_table["mag_communicationlog"]),
        ("mag_reviewaudittrail", records_by_table["mag_reviewaudittrail"]),
        ("mag_archiverecord", records_by_table["mag_archiverecord"]),
        ("mag_adversenewsevent", records_by_table["mag_adversenewsevent"]),
        ("mag_supplieronepagesummary", records_by_table["mag_supplieronepagesummary"]),
    ]
    for table, rows in order:
        load(table, rows)

    print("Demo data import complete.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-only", action="store_true", help="Generate the CSV fixtures without connecting.")
    args = parser.parse_args()
    rows = demo_rows()
    export_csv(rows)
    if not args.export_only:
        import_csv(rows)


if __name__ == "__main__":
    main()
