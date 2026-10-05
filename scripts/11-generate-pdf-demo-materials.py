"""Generate fictional PDF-input fixtures for SRM-FIN-001 and SRM-NFR-001."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import pymupdf
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "demo-materials" / "pdf-analysis"
STATEMENTS = {
    "Balance sheet": (
        ("TotalAssets", "Total assets"),
        ("TotalDebt", "Total debt"),
        ("CurrentAssets", "Current assets"),
        ("CurrentLiabilities", "Current liabilities"),
        ("AccountsReceivable", "Accounts receivable"),
        ("Inventory", "Inventory"),
    ),
    "Income statement": (
        ("Revenue", "Revenue"),
        ("CostOfGoodsSold", "Cost of goods sold"),
        ("GrossProfit", "Gross profit"),
        ("NetIncome", "Net income"),
    ),
    "Cash flow statement": (("OperatingCashFlow", "Net cash from operating activities"),),
}


def heading(pdf, title, subtitle):
    pdf.setTitle(title)
    pdf.setAuthor("SRM Agent Demo - fictional fixtures")
    pdf.setFillColor(colors.HexColor("#172B4D"))
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(42, 790, title)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(42, 768, subtitle)
    pdf.setFillColor(colors.HexColor("#9C2F15"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(42, 742, "FICTIONAL DEMO ONLY - NOT AUDITED - NO REAL SUPPLIER DATA")
    pdf.setFillColor(colors.black)


def footer(pdf, page):
    pdf.setFont("Helvetica", 9)
    pdf.drawString(42, 45, f"SUP-012 | Lumen Forge Industrial Systems Ltd | Page {page}")


def statement_page(pdf, row, kind, fields, page, ambiguous=False):
    year, period = row["FiscalYear"], row["Period"]
    heading(pdf, kind, f"FY{year} | {period} | USD, whole dollars (not thousands)")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(42, 712, "Selected working-paper balances; this is not a complete statutory statement.")
    pdf.drawString(42, 695, "Parentheses denote negative amounts. Interim results are not annualized.")
    y = 650
    for field, label in fields:
        value = int(row[field])
        display = f"({abs(value):,})" if value < 0 else f"{value:,}"
        if ambiguous and field == "NetIncome":
            display = "[ILLEGIBLE IN SUPPLIER COPY]"
        pdf.setFont("Helvetica", 11)
        pdf.drawString(42, y, label)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawRightString(552, y, display)
        y -= 40
    pdf.setFont("Helvetica", 9)
    pdf.drawString(42, y - 30, "Source: fictional SRM working-paper data. Reconciliation remains a reviewer task.")
    footer(pdf, page)
    pdf.showPage()


def rasterize(source):
    images = []
    with pymupdf.open(stream=source, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            images.append(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
    output = io.BytesIO()
    images[0].save(output, format="PDF", save_all=True, append_images=images[1:], resolution=108)
    return output.getvalue()


def collateral(title, lines):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=1)
    heading(pdf, title, "Lumen Forge Industrial Systems Ltd | FY2025 disclosure package")
    pdf.setFont("Helvetica", 11)
    y = 700
    for line in lines:
        pdf.drawString(42, y, line)
        y -= 24
    footer(pdf, 1)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def generate():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "data" / "working_papers.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["SupplierDemoKey"] == "SUP-012"]
    if [r["FiscalYear"] for r in rows] != ["2023", "2024", "2025", "2026"]:
        raise ValueError("Expected SUP-012 annual 2023-2025 and interim 2026 working papers.")
    bundle = io.BytesIO()
    pdf = canvas.Canvas(bundle, pagesize=A4, invariant=1)
    page = 1
    for row in rows:
        for kind, fields in STATEMENTS.items():
            statement_page(pdf, row, kind, fields, page)
            page += 1
    pdf.save()
    files = {"sup012-financial-package-digital.pdf": bundle.getvalue()}
    single = io.BytesIO()
    pdf = canvas.Canvas(single, pagesize=A4, invariant=1)
    for page, (kind, fields) in enumerate(STATEMENTS.items(), 1):
        statement_page(pdf, rows[2], kind, fields, page)
    pdf.save()
    files["sup012-fy2025-image-only.pdf"] = rasterize(single.getvalue())
    ambiguous = io.BytesIO()
    pdf = canvas.Canvas(ambiguous, pagesize=A4, invariant=1)
    statement_page(pdf, rows[2], "Income statement", STATEMENTS["Income statement"], 1, True)
    pdf.save()
    files["sup012-fy2025-unreadable-income.pdf"] = rasterize(ambiguous.getvalue())
    files["sup012-supplier-questionnaire.pdf"] = collateral("Supplier questionnaire", [
        "Supplier assertions only; not independently verified.",
        "Largest customer: 62% of FY2025 revenue.",
        "All production sites are leased; no ownership title supplied.",
        "Commercial arbitration is pending; outcome and amount are unconfirmed.",
        "Management says no off-balance-sheet guarantees exist.",
        "These are fictional scenario disclosures, not real legal allegations.",
    ])
    files["sup012-reviewer-collateral-note.pdf"] = collateral("Reviewer collateral note", [
        "Fictional internal working note; not an independent assurance report.",
        "Customer concentration schedule states 68% for the largest customer.",
        "This conflicts with the supplier questionnaire's 62% assertion.",
        "Request reconciliation before using either percentage as a verified fact.",
        "No guarantee register was provided: absence is not proof of no guarantees.",
        "Review current assets against receivables/inventory: balances may not reconcile.",
        "Interim cash flow is negative; do not compare interim revenue to a full year.",
    ])
    for name, content in files.items():
        (OUTPUT / name).write_bytes(content)
    manifest = {
        "fictional": True,
        "purpose": "Actual PDF-input proof, not proof of live extraction",
        "files": [
            {"filename": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in files.items()
        ],
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def validate():
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        content = (OUTPUT / item["filename"]).read_bytes()
        if len(content) != item["bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"Manifest mismatch: {item['filename']}")
        if len(content) > 4 * 1024 * 1024:
            raise ValueError(f"File exceeds flow transport limit: {item['filename']}")
        with pymupdf.open(stream=content, filetype="pdf") as doc:
            if item["filename"] == "sup012-financial-package-digital.pdf":
                if len(doc) != 12 or any(not p.get_text().strip() for p in doc):
                    raise ValueError("Digital package must have 12 text-bearing pages.")
            elif "image-only" in item["filename"] or "unreadable" in item["filename"]:
                if any(p.get_text().strip() or not p.get_images() for p in doc):
                    raise ValueError("Scan fixture must contain images and no PDF text layer.")
    expected = json.loads((OUTPUT / "expected-results.json").read_text(encoding="utf-8"))
    with pymupdf.open(OUTPUT / "sup012-financial-package-digital.pdf") as doc:
        for fact in expected["criticalFinancialFacts"]:
            text = doc[fact["page"] - 1].get_text()
            value = fact["value"]
            printed = f"({abs(value):,})" if value < 0 else f"{value:,}"
            if fact["label"] not in text or printed not in text:
                raise ValueError(f"Expected fixture fact not found: {fact}")
    print("Validated 5 PDFs, manifest hashes, 12 digital pages, image-only scans, and critical facts.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if not args.validate_only:
        generate()
    validate()
