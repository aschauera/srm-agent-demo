"""Read-only supplier dashboard. SRM-OPS-001, SRM-FIN-001, SRM-GOV-001/002."""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

RATINGS = {100000000: "Green", 100000001: "Yellow", 100000002: "Red",
           100000003: "Not rated"}
TIERS = {100000000: "Low", 100000001: "Medium", 100000002: "High",
         100000003: "Unavailable"}
STATUSES = {100000000: "Not Started", 100000001: "In Progress", 100000002: "Completed"}
PATHS = {100000000: "GSA Reuse", 100000001: "Coface Fast-Track", 100000002: "Full Review"}
STAGES = ["Request & Pre-Check", "Information Collection", "Analysis & Rating",
          "Communication & Decision", "Archiving & Publication"]
SEVERITIES = {100000000: "Low", 100000001: "Medium", 100000002: "High"}

# Select lists are also validated against schema/ by the focused test suite.
COLUMNS = {
    "mag_supplier": [
        "mag_supplierid", "mag_suppliercode", "mag_legalname", "mag_country",
        "mag_magnadivision", "mag_businesscategory", "mag_annualspend", "mag_hasactivespend",
        "mag_currentmagnarating", "mag_duns", "modifiedon"],
    "mag_financialreviewrequest": [
        "mag_financialreviewrequestid", "mag_requestref", "_mag_supplierid_value",
        "mag_reviewstatus", "mag_reviewpath", "mag_currentstage", "mag_preliminaryrating",
        "mag_finalrating", "mag_finalratingconfirmed", "mag_ratingdate", "mag_ratingexpiry",
        "mag_revieweroverride", "mag_cofacescore", "mag_cofacerisktier", "modifiedon"],
    "mag_financialworkingpaper": [
        "mag_fiscalyear", "mag_period", "mag_currency", "mag_revenue", "mag_netincome",
        "mag_operatingcashflow", "mag_leverageratio", "mag_liquidityratio", "mag_grossmargin"],
    "mag_cofacecreditrecord": [
        "mag_score", "mag_risktier", "mag_assessmentdate", "mag_financialdatathrough",
        "mag_recommendedcreditlimit", "mag_reportlink", "mag_syntheticdata"],
    "mag_supplieronepagesummary": [
        "mag_companyprofile", "mag_sourceattribution", "mag_trendinterpretation",
        "mag_generatedon", "mag_summaryversion"],
    "mag_adversenewsevent": [
        "mag_title", "mag_severity", "mag_releasedate", "mag_sourceurl"],
    "mag_nonfinancialriskitem": [
        "mag_risktype", "mag_severity", "mag_details", "mag_sourceurl", "mag_eventdate"],
}
SENSITIVE_REQUEST_COLUMNS = ["mag_narrativedraft", "mag_remarks"]


class Records(Protocol):
    def list(self, table: str, **kwargs: Any) -> Any: ...


class DashboardError(ValueError):
    """Expected input/data failure that must be reported to the caller."""


def choice(value: Any, options: dict[int, str], empty: str) -> str:
    if value is None:
        return empty
    if value not in options:
        raise DashboardError("Dataverse returned an unrecognized choice value.")
    return options[value]


def instant(value: str | None) -> datetime | None:
    if not value:
        return None
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date


def within_months(value: str | None, now: datetime, months: int) -> bool:
    date = instant(value)
    if date is None or date > now:
        return False
    total = date.year * 12 + date.month - 1 + months
    year, month = divmod(total, 12)
    month += 1
    expiry = date.replace(year=year, month=month,
                          day=min(date.day, calendar.monthrange(year, month)[1]))
    return now <= expiry


def load_dashboard(records: Records, supplier_code: str, request_ref: str | None = None,
                   *, sensitive: bool = False, now: datetime | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"SUP-(00[1-9]|01[0-2])", supplier_code):
        raise DashboardError("Use a fictional seeded supplier code SUP-001 through SUP-012.")
    if request_ref is not None and not re.fullmatch(r"REQ-\d{4}-\d{3,6}", request_ref):
        raise DashboardError("Request reference must have the form REQ-2026-012.")
    now = now or datetime.now(timezone.utc)

    def query(table: str, predicate: str, *, order: list[str] | None = None,
              limit: int = 100, extra: list[str] | None = None) -> list[dict[str, Any]]:
        rows = [dict(r) for r in records.list(
            table, select=COLUMNS[table] + (extra or []),
            filter=f"statecode eq 0 and ({predicate})", orderby=order, top=limit)]
        if limit == 100 and len(rows) == limit:
            raise DashboardError("Dashboard result limit reached; narrow the review data.")
        return rows

    suppliers = query("mag_supplier", f"mag_suppliercode eq '{supplier_code}'", limit=2)
    if len(suppliers) != 1:
        raise DashboardError("Supplier not found or supplier code is ambiguous.")
    supplier = suppliers[0]
    spend = supplier.get("mag_annualspend")
    if supplier.get("mag_hasactivespend") is not True or spend is None or spend <= 0:
        raise DashboardError("The one-page dashboard is unavailable for a zero-spend supplier.")
    supplier_id = str(UUID(supplier["mag_supplierid"]))
    predicate = f"_mag_supplierid_value eq {supplier_id}"
    requests = query("mag_financialreviewrequest", predicate,
                     order=["createdon desc", "mag_financialreviewrequestid asc"])
    if request_ref:
        matches = [r for r in requests if r["mag_requestref"] == request_ref]
    else:
        matches = requests[:1]
    if len(matches) != 1:
        raise DashboardError("Review request not found for this supplier or reference is ambiguous.")
    review = matches[0]
    request_id = str(UUID(review["mag_financialreviewrequestid"]))
    if sensitive:
        full = query("mag_financialreviewrequest",
                     f"mag_financialreviewrequestid eq {request_id} and {predicate}",
                     limit=2, extra=SENSITIVE_REQUEST_COLUMNS)
        if len(full) != 1:
            raise DashboardError("The review changed or became unavailable during the read.")
        review = full[0]

    working = query("mag_financialworkingpaper",
                    f"_mag_reviewrequestid_value eq {request_id} and {predicate}",
                    order=["mag_fiscalyear asc", "mag_period asc"])
    credits = query("mag_cofacecreditrecord", f"{predicate} and mag_syntheticdata eq true",
                    order=["mag_assessmentdate desc", "createdon desc"], limit=1)
    credit = credits[0] if credits else {}
    credit_current = within_months(credit.get("mag_assessmentdate"), now, 18)
    confirmed = review.get("mag_finalratingconfirmed") is True
    final = choice(review.get("mag_finalrating"), RATINGS, "Not rated")
    if confirmed and final == "Not rated":
        raise DashboardError("The review is marked confirmed but has no final rating.")
    preliminary = choice(review.get("mag_preliminaryrating"), RATINGS, "Not rated")
    current_rating = choice(supplier.get("mag_currentmagnarating"), RATINGS, "Not rated")
    stage = review.get("mag_currentstage")
    if stage not in range(1, 6):
        raise DashboardError("The review has an invalid or missing process stage.")
    expiry = instant(review.get("mag_ratingexpiry"))
    expired = bool(expiry and expiry.date() < now.date())
    warnings = []
    if not confirmed:
        warnings.append("Human final-rating decision pending. AI recommendation is not approval.")
    if confirmed and expired:
        warnings.append("The confirmed request rating has expired; do not treat it as current.")
    if not credit_current:
        warnings.append("No current Coface assessment within 18 months; any displayed score is historical.")
    if confirmed and current_rating != final:
        warnings.append("Supplier master and confirmed request ratings differ; synchronization needs review.")
    if preliminary != "Not rated" and current_rating != preliminary:
        warnings.append("Supplier master and AI preliminary rating differ; these are separate records.")

    summary: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    if sensitive:
        summaries = query("mag_supplieronepagesummary", predicate,
                          order=["mag_generatedon desc", "createdon desc"], limit=1)
        summary = summaries[0] if summaries else {}
        events = query("mag_adversenewsevent", predicate, order=["mag_releasedate desc"])
        risks = query("mag_nonfinancialriskitem",
                      f"_mag_reviewrequestid_value eq {request_id} and {predicate}")

    return {
        "supplier": {
            "code": supplier_code, "name": supplier["mag_legalname"],
            "country": supplier.get("mag_country"), "division": supplier.get("mag_magnadivision"),
            "category": supplier.get("mag_businesscategory"), "duns": supplier.get("mag_duns"),
            "annualSpend": supplier.get("mag_annualspend"), "masterRating": current_rating,
        },
        "review": {
            "ref": review["mag_requestref"], "status": choice(review.get("mag_reviewstatus"), STATUSES, "Unknown"),
            "path": choice(review.get("mag_reviewpath"), PATHS, "Unknown"), "stage": stage,
            "stageName": STAGES[stage - 1], "preliminaryRating": preliminary,
            "finalRating": final if confirmed else "Not rated", "confirmed": confirmed,
            "expired": expired, "ratingDate": review.get("mag_ratingdate"),
            "ratingExpiry": review.get("mag_ratingexpiry"),
            "overridden": review.get("mag_revieweroverride") is True,
            "narrativeDraft": review.get("mag_narrativedraft") if sensitive else None,
            "officialCommentary": review.get("mag_remarks") if sensitive and confirmed else None,
            "modifiedOn": review.get("modifiedon"),
        },
        "coface": {
            "score": credit.get("mag_score"), "tier": choice(credit.get("mag_risktier"), TIERS, "Unavailable"),
            "assessmentDate": credit.get("mag_assessmentdate"), "current": credit_current,
            "creditLimit": credit.get("mag_recommendedcreditlimit"), "reportUrl": credit.get("mag_reportlink"),
        },
        "financials": [{
            "year": r.get("mag_fiscalyear"), "period": r.get("mag_period"), "currency": r.get("mag_currency"),
            "revenue": r.get("mag_revenue"), "netIncome": r.get("mag_netincome"),
            "cashFlow": r.get("mag_operatingcashflow"), "leverage": r.get("mag_leverageratio"),
            "liquidity": r.get("mag_liquidityratio"), "grossMargin": r.get("mag_grossmargin"),
        } for r in working],
        "ratingHistory": [{
            "ref": r["mag_requestref"], "date": r.get("mag_ratingdate"),
            "rating": choice(r.get("mag_finalrating"), RATINGS, "Not rated"),
            "cofaceScore": r.get("mag_cofacescore"),
        } for r in requests if r.get("mag_finalratingconfirmed") is True],
        "profile": summary.get("mag_companyprofile"),
        "sourceAttribution": summary.get("mag_sourceattribution"),
        "trendInterpretation": summary.get("mag_trendinterpretation"),
        "summaryGeneratedOn": summary.get("mag_generatedon"),
        "summaryVersion": summary.get("mag_summaryversion"),
        "adverseEvents": [{
            "headline": r.get("mag_title"), "severity": choice(r.get("mag_severity"), SEVERITIES, "Unknown"),
            "date": r.get("mag_releasedate"), "sourceUrl": r.get("mag_sourceurl"),
        } for r in events],
        "nonFinancialRisks": [{
            "details": r.get("mag_details"), "severity": choice(r.get("mag_severity"), SEVERITIES, "Unknown"),
            "date": r.get("mag_eventdate"), "sourceUrl": r.get("mag_sourceurl"),
        } for r in risks],
        "sensitiveVisible": sensitive, "warnings": warnings, "fetchedAt": now.isoformat(),
        "source": "Live Dataverse / fictional SRM demo records",
    }
