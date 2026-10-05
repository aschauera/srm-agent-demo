# 07 - Stage 2: Coface Fast-Track and Document Collection

Status: Coface and document-request/reminder flows are deployed and active in DemoPRE; end-to-end
tests and the reply-file byte upload remain open. The Data Collection Copilot agent is still a
specification.
Source: slides 4-7 of [the extracted deck](./requirements/source/fy27-magna-srm-use-case-extracted.txt).
Plan items: Stage 2 of the BPF, agents *Data Collection* and *Communication & Closure*
([topology](./05-agent-topology.md)).

## Requirements

`SRM-COF-001` and `SRM-COL-001` are the data-model requirements in
[02-dataverse-data-model.md](./02-dataverse-data-model.md). The rows below refine them.

| ID | Requirement | Slide | Artifact | Verification | Status |
|---|---|---|---|---|---|
| `SRM-COF-001` | Keep Coface response data, data age and configurable conversion rules. | 4-6 | `mag_cofacecreditrecord`, `mag_ratingconversionrule` | Data-model verification | Built |
| `SRM-COF-002` | Run the Coface retrieval only when the pre-check did not close the request (full review path). | 4-5 | Coface retrieval flow | Smoke test: reuse path writes no Coface data | Deployed; test pending |
| `SRM-COF-003` | Retrieve by DUNS: score, risk tier, payment record, negative alerts, recommended credit limit. | 4 | Retrieval flow, request Coface columns | Smoke test with `900000001` | Deployed; test pending |
| `SRM-COF-004` | Without a DUNS, match on legal name and country; with several matches show a shortlist the reviewer chooses from. Never auto-pick. | 4 | Shortlist view and form, Data Collection agent | Smoke test with SUP-010 and SUP-011 | Deployed; test pending |
| `SRM-COF-005` | Write all Coface data back to the request for permanent retention. | 4-5 | Request Coface columns | Field comparison | Deployed; test pending |
| `SRM-COF-006` | Show the score with colour-coded traffic-light labels and an AI risk interpretation. | 4-5 | Form indicators, notification email | Visual check | Form built; flow deployed; test pending |
| `SRM-COF-007` | Without a DUNS, the reviewer notice carries the disclaimer "No DUNS number provided; full Coface credit score unavailable." | 5 | Notice template | Smoke test | Deployed; test pending |
| `SRM-COF-008` | Check whether the Coface data is no older than 18 months. | 6 | Environment variable `mag_CofaceMaxDataAgeMonths`, retrieval flow | Seeded stale rows SUP-004 to SUP-007, SUP-012 | Deployed; test pending |
| `SRM-COF-009` | Convert a valid Coface score to a Magna rating with the rule table. The result is a proposal; a human confirms it. | 6 | `mag_ratingconversionrule`, conversion flow | Boundary scores 0, 3, 4, 7, 8, 10 | Rules seeded; flow deployed; test pending |
| `SRM-COF-010` | If no valid Coface score exists (no match, no DUNS, stale data), route to full review. | 6-7 | Retrieval flow, BPF | Smoke test | Deployed; test pending |
| `SRM-COF-011` | Email the buyer the supplier name, DUNS, converted rating and Coface source. Archive the Coface response as evidence. | 6 | Communication & Closure agent | Communication log row | Planned |
| `SRM-COF-012` | Log every query, conversion and upload to the review ledger. | 6 | `mag_ReviewAuditTrail` | Ledger row per action | Deployed; test pending |
| `SRM-COL-001` | Track document requests, reminders, files, OCR status and classification. | 7-8, 13-14 | Document tables | Data-model verification | Built |
| `SRM-COL-002` | Send the supplier a request for audited statements for the latest 3 fiscal years plus the interim period, and a non-financial questionnaire. | 7 | Document request flow | Communication log row | Deployed; test pending |
| `SRM-COL-003` | Reminder cadence: day 3 follow-up, day 7 escalation to the buyer when there is no response. | 7 | Environment variables, scheduled flow | Seeded day-3 and day-7 requests | Deployed and active; test pending |
| `SRM-COL-004` | Record supplier replies and file their attachments against the request. | 7 | Reply-filing flow | Document row with readable file bytes | Deployed and active; byte-readback test pending |
| `SRM-COL-005` | Move the BPF to Stage 3 once the required documents are received. | 7 | Reply-filing flow, BPF | Smoke test with all 12 annual/interim statements | Deployed; end-to-end test pending |
| `SRM-COL-012` | Audit document requests, reminders, received attachments and collection-completion stage changes in the review ledger. | 7 | Document collection flows, `mag_ReviewAuditTrail` | Verify an audit row for each event | Deployed; test pending |

## Rule values (demo placeholders)

Nothing below is approved Magna policy. Every row is marked `Draft - demo only` and stays
configurable. Bands are derived from public descriptions of the Coface Debtor Risk Assessment
(0 to 10, higher is safer) and common credit rules of thumb (current ratio below 1.0 weak,
Altman-style caution zones). They were researched on 2026-10-02.

### Coface to Magna conversion (`mag_ratingconversionrule`)

| Coface score | Coface meaning | Magna rating |
|---|---|---|
| 8-10 | Low risk | Green |
| 4-7 | Elevated to average risk | Yellow |
| 0-3 | High risk to defaulted | Red |

A score outside the 18-month window, or a missing score, produces no conversion (`SRM-COF-010`).

### Preliminary rating points (`mag_riskscoringrule`)

Each signal that fires adds its points. When two rules cover one metric, both fire for the
stricter value, so the points add.

| Dimension | Signal | Rule | Points |
|---|---|---|---|
| Leverage | Elevated / high debt to assets | > 0.60 / > 0.75 | 1 / +3 |
| Liquidity | Thin / weak current ratio | < 1.5 / < 1.0 | 1 / +3 |
| Cash flow | Negative operating cash flow | < 0 | 2 |
| Profitability | Revenue decline | year-on-year < -10% | 2 |
| Profitability | Low gross margin | < 15% | 1 |
| Non-financial | Customer concentration | > 60% | 2 |
| Overall | Preliminary Yellow | total points >= 2 | - |
| Overall | Preliminary Red | total points >= 5 | - |

Below 2 points the preliminary rating is Green. The preliminary rating is advisory; the reviewer
confirms the final rating (`SRM-GOV-004`).

### Timings

| Setting | Value | Where it lives |
|---|---|---|
| Maximum Coface data age | 18 months | Environment variable `mag_CofaceMaxDataAgeMonths` (planned) |
| Supplier reminder | Day 3 | Environment variable `mag_ReminderDay` (planned) |
| Buyer escalation | Day 7 | Environment variable `mag_EscalationDay` (planned) |

## Open decisions

- Approve or replace the placeholder bands above.
- Whether a Coface score of 4-7 may be fast-tracked at all, or only 8-10.
- Whether the converted rating needs a second approver before sync to the GSA record.

## Build order

1. Environment variables for the three timings.
2. Coface retrieval and 18-month check flow (agent-callable, with the Data Collection agent).
3. Stage 2 form sections, shortlist view and traffic-light indicators.
4. Conversion proposal flow and Shortcut B stage move.
5. Document request, reminder and reply-filing flows.

### DemoPRE deployment status

| Step | Status |
|---|---|
| 1. Environment variables | Deployed |
| 2. Retrieval flow (`coface-retrieve-and-check`) | Active; not yet run end to end |
| 3. Form tab, banners, cards | Built and deployed (Coface tab, stale and fast-track banners, Coface and Preliminary rating cards, Coface tier colors) |
| 4. Conversion flow (`coface-propose-rating`) | Active; includes Shortcut B BPF movement; not yet run end to end |
| 5. Document request and reminder | Active; not yet smoke-tested |
| 6. Reply filing and automatic Stage 3 movement | Active; uses the documented `UpdateEntityFileImageFieldContent` Dataverse connector action; byte-readback and completeness tests pending |

Agent-callable flows cannot be invoked outside an agent, so test them from the Power Automate designer (Test) with a seeded request, or from Copilot Studio after adding them as tools.

The reply-file content operation and flow activation are validated in DemoPRE, and the solution
was exported and unpacked to `solutions/SRMAgentDemo/`. The attachment byte round-trip and automatic
Stage 3 movement still require an end-to-end run before those behaviors can be considered verified.
The upload action follows Microsoft's
[Dataverse file/image upload guidance](https://learn.microsoft.com/en-us/power-automate/dataverse/upload-download-file).
