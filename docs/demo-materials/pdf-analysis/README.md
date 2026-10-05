# PDF Analysis Demo Package

Requirement anchors: `SRM-FIN-001` (source slide 8), `SRM-NFR-001` (slide 9), and human
accountability (slides 1, 11-12). All identities, balances, and disclosures are fictional.

These are actual PDF fixtures for the approved
[agent-led demo plan](../../planning/agent-led-pdf-demo-plan.md). Creating them does not verify
live LLM extraction, tool integration, human approvals, or working-paper persistence.

## Files and presenter order

| File | Purpose | Expected reviewer interaction |
|---|---|---|
| [Digital financial package](./sup012-financial-package-digital.pdf) | 12 pages: balance sheet, income statement, and operating cash flow excerpts for 2023-2025 annual and 2026 interim periods | Compare extracted signs, USD whole-dollar units, and fiscal periods with the source |
| [Image-only FY2025 package](./sup012-fy2025-image-only.pdf) | Three raster-only pages, with no PDF text layer; FY2025 counterpart of digital pages 7-9 | Demonstrate recognition from page images, not knowledge search or text-layer parsing |
| [Unreadable income statement](./sup012-fy2025-unreadable-income.pdf) | One raster-only page with net income deliberately unavailable | Keep the value missing; request readable evidence or explicitly cite a separate source |
| [Supplier questionnaire](./sup012-supplier-questionnaire.pdf) | Assertions about customer concentration, leased sites, arbitration, and guarantees | Distinguish disclosures from independently verified facts |
| [Reviewer collateral note](./sup012-reviewer-collateral-note.pdf) | Conflicting concentration percentage and missing guarantee evidence | Surface 62% versus 68%; request clarification rather than choose one silently |
| [Presenter request brief](./sup012-demo-request-brief.txt) | Copy-ready fictional case setup for an isolated request | Presenter only; not a financial evidence input |
| [Expected results](./expected-results.json) | Manually specified critical facts and review exceptions | Presenter/tester only; never upload as evidence or pass as model output |
| [Manifest](./manifest.json) | Sizes and SHA-256 hashes | Compare uploaded/downloaded bytes during the storage proof |

Each file is below the current 4 MiB attachment-flow limit. The files are selected working-paper
excerpts, not complete statutory accounts or auditor opinions. Receivables/inventory and current
assets in the existing seed can fail reconciliation; the demo deliberately surfaces this rather
than silently altering source balances. No ratio or final rating is printed in the package as a
substitute for live computation.

## Rebuild and validate locally

From the repository root:

```powershell
python -m pip install -r .\scripts\requirements-demo-pdf.txt
python .\scripts\11-generate-pdf-demo-materials.py
python .\scripts\11-generate-pdf-demo-materials.py --validate-only
```

The generator reads the existing fictional `SUP-012` working-paper rows. Validation checks hashes,
file sizes, PDF readability, twelve digital pages, image-only scans with no text layer, and the
manually specified critical values. This is fixture validation, not model evaluation.

## Proposed proof interaction

For the timed presentation, follow the copy-ready prompts, checkpoints, and fallbacks in the
[30-minute demo guide](../../09-demo-script.md). All five financial/collateral PDFs already exist;
no additional evidence document is needed for that run.

Use the existing Copilot Studio harness agent in DemoPRE with actual uploaded PDFs. Let it select
its built-in recognition, extraction, and analysis capabilities, including PDF skills and OCR
corroboration where appropriate. Do not send documents to an unapproved external model endpoint.

1. Analyze the digital package without supplying expected results. Ask for extracted financial
   facts, fiscal period, currency/unit, source filename, page, evidence excerpt, and missing state.
2. Run the same task on the FY2025 image-only package. Compare independently against expected
   FY2025 results; scanned pages are 1-3 rather than digital pages 7-9.
3. Analyze the unreadable fixture alone. Net income must remain missing; it must not be inferred.
4. Analyze the questionnaire and collateral note together. Ask for contradictions and evidence
   gaps, keeping assertions distinct from verified facts.
5. At the first human gate, correct or request clarification on evidence. Subsequent deterministic
   metrics and narratives must use the approved extraction revision.
6. At the final human gate, the reviewer decides the final rating. A chat reply alone must not
   count as an authenticated approval.

The Draft implements conversational extraction review and native computation instructions.
Post-review computations require rehearsal; persisted analysis and authenticated approvals remain
unimplemented. Step 6 is a boundary demonstration, not a completed approval transaction.
