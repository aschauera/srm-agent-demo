# Agent-Led PDF Analysis Demo Plan

Status: approved for implementation; PDF fixtures and local fixture validation are implemented.
Initial harness Preview extraction checks passed; persisted analysis and end-to-end human approval
remain unverified.
Date: 2026-10-05.

## Implementation checkpoint

The existing SRM Orchestrator Draft instructions now permit native document processing and require
source-backed extraction, an extraction-review pause, reproducible calculations, collateral
contradiction handling, and a separate human final-rating gate. PAC pack/push succeeded; no
publication occurred. Digital and image-only Draft Preview runs returned the requested expected
financial values and paused before calculations or rating. A subsequent canonical-filename
instruction change was pushed but not revalidated after the shared client disconnected.

The unreadable and collateral fixtures passed earlier exploratory tests, not the latest Draft
regression. Post-review calculations, final recommendation behavior, durable persistence, and
authenticated approval actions remain incomplete/unverified. The existing orchestrator was added
to `SRMAgentDemo` with the repeatable
[membership script](../../scripts/12-add-orchestrator-to-solution.py). Live membership and an
idempotent second run were verified; the solution was exported/unpacked with its Draft instructions
and read-only status tool included. Previously changed Intake source files were backed up and
preserved byte-for-byte. No publication occurred.

## Demo anchor and approved direction

Users submit financial-review requests. Copilot Studio agents analyze financial PDFs and
supporting collateral, explain evidence-backed findings, and surface human approvals.
The user initially selected a document-input prompt proof and then requested direct multimodal-only
recognition. On 2026-10-05, that restriction was superseded by the explicit decision to **let the
existing Copilot Studio harness agent select and use its native capabilities** for all document
recognition, extraction, and analysis. Built-in PDF skills, page rendering, and OCR corroboration
are allowed; a separately provisioned OCR/model backend is not needed for the demo.

Use actual uploaded PDFs, including image-only scans, not seeded outputs masquerading as extraction.
The agent may use its supported computation capabilities to calculate reproducible metrics and
explain the formulas. No new financial final rating may be written autonomously. Report the native
processing approach accurately; do not claim LLM-only OCR or hidden implementation details.

This is a focused delivery slice of the
[implementation plan](./implementation-plan.md), not a replacement architecture. Preserve:

- DemoPRE, `SRMAgentDemo`, the `mag` publisher, and fictional data only;
- the five-stage BPF and existing GSA reuse/Coface fast-track paths;
- one orchestrator and six connected specialists;
- human accountability for every new final rating;
- auditable actions and role-sensitive evidence.

## Current baseline

- Stage 1: five GSA pre-check branches have live smoke-test evidence.
- Stage 2: document filing and other collection flows are active, but attachment byte readback,
  financial completeness, and Stage 3 movement still need end-to-end proof.
- PDF extraction, financial-analysis tools, and the complete connected-agent journey are unbuilt.
- Working-paper fields, file storage, source-document linkage, preliminary outputs, and demo
  scoring rules already exist.
- The original attachment fixtures are plain text. The new
  [PDF proof package](../demo-materials/pdf-analysis/README.md) includes digital, image-only,
  unreadable-value, and collateral PDFs; fixture validation alone is not live OCR proof.

See [Stage 1 evidence](../06-agent-flows-and-actions.md),
[Stage 2 status](../07-stage-2-coface-and-collection.md), and
[agent topology](../05-agent-topology.md).

## Proposed vertical slice

Use the fictional Lumen Forge supplier (`SUP-012`) and a separate new full-review request, not a
mutation of the prepared `REQ-2026-012` scenario.

```text
Submit request
  -> Data Collection: store and classify PDFs/collateral
  -> Financial Analysis & Rating: extract draft financial facts with evidence
  -> Human gate 1: review/correct extracted facts
  -> Agent computation capabilities: calculate reproducible metrics and apply available demo rules
  -> Financial Analysis & Rating: synthesize collateral and draft analysis
  -> Human gate 2: confirm or override final rating
  -> Communication & Closure: prepare approved outcome communication
```

The orchestrator owns routing and user-facing status. Specialists retain their existing stage
ownership and return results through the orchestrator. Do not create an eighth agent to implement
document recognition. Agent tools perform controlled retrieval, extraction, calculations,
persistence, and auditing.

Treat document instructions as untrusted evidence, not commands to the agent. Never let uploaded
content authorize tool calls, suppress citations, or bypass human approval.

## Implementation sequence and acceptance gates

### 1. Prove native harness document processing

Create a small fictional PDF package and manually authored expected extraction results:

- one digital PDF with tables;
- one image-only scanned PDF;
- one ambiguous/unreadable value;
- one collateral document with an assertion that conflicts with another document.

Use the existing harness Preview and verify real PDF inputs, native skill behavior, available
capacity, file limits, and observable execution time. Preserve the current harness and model.
No new Azure endpoint, external connector, or separately provisioned OCR service is approved.

**Pass:** actual bytes/images reach the extraction action; the clean fixture's designated critical
values exactly match expected amounts, signs, currency, units, and periods; every extracted fact
has document/page evidence; the unreadable value remains missing and is flagged. Measure latency.
Model-reported confidence is not calibrated accuracy and cannot replace these checks.

**Stop gate:** if actual scans or document input are unsupported or unreliable, report the result.
Do not substitute expected fixture values for extraction or route documents to an external service.

### Initial Preview evidence and engine qualification

The existing SRM Orchestrator Preview processed actual fictional fixtures. The digital run
returned the 19 designated critical facts correctly; the image-only scan returned the 11 FY2025
facts correctly. Unreadable net income remained missing, and contradictory collateral assertions
remained unresolved. These are observed Preview results, not deployed analysis-tool behavior.

The visible scan/unreadable responses reported page rendering and OCR corroboration through
the built-in `analyzing-pdf` skill. The processing order and underlying implementation were not
exposed, so this is not evidence of LLM-only recognition. The user's latest decision allows
this native agent-selected approach. Latency, durable original-document provenance, and
production tool integration remain unverified acceptance items.

### 2. Prove storage and evidence coverage

Upload real fictional PDFs using the existing file flow, retrieve them, and compare SHA-256 hashes.
Keep the present 4 MiB per-call limit unless a separate change is justified and tested.

Expand to three completed fiscal years plus interim balance sheet, income statement, and cash
flow coverage. A PDF may contain several statements/periods; twelve metadata-labelled rows alone
do not prove the evidence is readable or financially complete.

**Pass:** bytes match and files reopen; source request/supplier links and audit entries exist;
missing coverage or failed uploads do not count as analysis-ready; duplicate uploads do not
substitute for missing statement coverage.

### 3. Persist draft extraction and implement human gate 1

Define an extraction output contract with original and normalized values, currency/unit,
fiscal period, document/version, page, supporting evidence, and uncertainty/missing-value state.
Add field-level provenance and extraction-review lifecycle metadata as necessary; the current
single working-paper source link cannot fully represent multiple statement sources.

Provide a reviewer surface for opening PDFs beside draft figures, correcting values, and approving
the facts used for computation. Confirmed values remain attributable to the reviewer and source.

**Pass:** demonstrate correction of an uncertain value. That correction invalidates dependent
metrics, scoring, and narrative until recomputation. Missing values are never silently zero.

### 4. Calculate and explain the financial analysis

Use reproducible computations through the agent's supported capabilities, not unexplained
free-form LLM arithmetic. Define and version the exact
formula conventions for leverage, liquidity, gross margin, turnover, and year-over-year changes.
Keep interim/full-year comparisons explicitly comparable; handle zero denominators and missing
inputs as visible exceptions.

Apply only the existing configurable, clearly labelled demo scoring rules. Generate the narrative
from the validated figures, calculated results, and rule outcomes.

**Pass:** computed results match independent expected calculations at declared precision; every
score contribution identifies its rule/version; missing rules block scoring rather than generate
an authoritative rating. AI writes preliminary outputs only.

### 5. Analyze collateral and surface human gate 2

Use fictional audit notes, non-financial questionnaire, lease/ownership evidence, customer
concentration, guarantees, and arbitration disclosures. Supporting collateral here means
evidence documents, not pledged-security valuation.

Distinguish supplier assertions from verified facts; show conflicting statements and unresolved
questions. Prepare a targeted clarification draft where evidence is insufficient.

The reviewer confirms or overrides the final rating with a recorded rationale. Approval must be
authenticated and enforced through controlled tool/server-side writes, not a conversational
"yes" or prompt instructions alone.

**Pass:** risk claims cite evidence; contradictions remain visible; unauthorized approval fails;
no AI tool can assign a new final rating or confirmation flag. Audit extraction, correction,
recalculation, recommendation, and the final human decision separately.

### 6. Wire and rehearse the agent journey

Select one supported authenticated demo channel. Verify its document-upload, citations, progress,
and reviewer-handoff experience rather than assume parity across Teams, web, and M365 Copilot.
Keep the model-driven app as the review surface when the channel cannot provide a suitable one.

Implement agent flows code-first from `flows/` using repeatable deployment scripts. Validate,
deploy only with authorization, and synchronize the exported solution after successful deployment.
Make retries idempotent and show processing failures explicitly.

**Pass:** run the full request-to-human-decision journey on a new fictional request. Show real
tool runs and persisted evidence, not seeded outputs posing as fresh analysis.

## Target presenter flow

Recommended target: 15-20 minutes, subject to the measured extraction latency.

| Beat | Action | Visible proof |
|---|---|---|
| 1. Request | Buyer submits a full-review-eligible supplier request | Saved reference, pre-check outcome, assigned reviewer |
| 2. Evidence | Submit digital and scanned financial PDFs plus collateral | Stored files, document identities, statement coverage |
| 3. Agent analysis | Ask the orchestrator to analyze the request | Specialist handoff, processing status, extraction tool run |
| 4. Review facts | Reviewer opens a flagged figure and resolves it | PDF/page evidence, correction history, extraction approval |
| 5. Explain findings | Agent recomputes and explains the financial trend and collateral | Deterministic metrics, cited discrepancies, demo-rule contributions |
| 6. Decide | Reviewer confirms or overrides the proposal | Human identity/rationale, final decision audit; no autonomous rating |
| 7. Close | Agent prepares the buyer outcome for review | Evidence-backed draft and request status |

Until the above gates pass, the [current-status guide](../09-demo-script.md) remains the
accurate demo script. Do not market this target flow as implemented.

## Scope boundaries and remaining decisions

Defer live external risk crawling, real supplier outreach, call transcription, multilingual
breadth, Early Warning automation, full archive automation, and dashboards from this slice.
Preserve those requirements in the overall backlog.

Decisions remaining:

- Supported authenticated presenter channel and upload surface.
- Review UI and authorized reviewer identity/role enforcement.
- PDF layouts, maximum package size, processing behavior, and measured latency budget.
- Exact formula conventions and configurable extraction-review criteria.

No new business-policy threshold is approved here. Conversion/scoring placeholders remain
explicitly demo-only, and any unavailable or unreliable extraction capability is a blocker.

## Traceability

| Source slides | Requirement anchors | Planned proof |
|---|---|---|
| 1-3 | `SRM-INT-002`, `SRM-INT-008` through `SRM-INT-010` | Request submission; preserve reuse and full-review routing |
| 7 | `SRM-COL-001`, `SRM-COL-004`, `SRM-COL-005`, `SRM-COL-012` | Readable files, statement coverage, auditable collection |
| 8 | `SRM-FIN-001` | PDF/scanned extraction, validated working papers, metrics and anomalies |
| 9 | `SRM-NFR-001` | Cited collateral analysis with uncertainty and contradictions |
| 10-12 | Refine financial/non-financial and communication requirements during implementation | Clarifications, draft analysis, human final decision, closing draft |
| 13-16 | `SRM-ARC-001`, governance refinements | Evidence classification, provenance, deduplication, audit history |

The FIN/NFR schemas already reference umbrella IDs while agent topics say those IDs are not
allocated; reconcile this documentation when refining the Stage 3 requirements.
