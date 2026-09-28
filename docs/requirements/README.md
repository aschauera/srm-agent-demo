# Requirements Guide

## Purpose

This directory separates original source material from requirements and specifications derived by
implementation agents.

## Authoritative Inputs

| Artifact | Role | Editing policy |
|---|---|---|
| `source/fy27-magna-srm-use-case-extracted.txt` | Verbatim text extracted from the FY27 MAGNA SRM Agent Use Case presentation | Preserve as source evidence; correct only demonstrable extraction errors |
| `../planning/implementation-plan.md` | Approved interpretation, target architecture, deliverables, and work breakdown | Update only when an approved design decision changes the plan |
| Future requirement catalogs in this directory | Structured, testable requirements derived from the source | Maintain IDs, source citations, status, and acceptance criteria |

The presentation itself is not stored in this repository. The extracted text is therefore the
available primary business-requirement evidence. It is raw extraction output: repeated passages,
run-together text, and incomplete punctuation do not by themselves alter business intent.

## Interpretation Rules

1. Cite the slide marker shown in the source extract, for example `slide6`.
2. Preserve explicit branching conditions, timings, roles, data fields, notifications, audit needs,
   and access restrictions.
3. Distinguish a stated requirement from an implementation choice introduced by the plan.
4. Do not convert examples into mandatory thresholds unless the source states that they are rules.
5. Do not invent missing policy values. Record them as open decisions and design for configuration.
6. When the source describes SharePoint, GSA, Coface, D&B, or eRFX behavior, map that behavior to
   the plan's mocked Dataverse system while retaining the observable outcome.
7. A summary is not complete if it omits an exception, fallback, approval gate, audit event, or
   role-based restriction from the cited source.

## Requirement IDs

Use stable IDs in the form `SRM-<AREA>-<NNN>`.

Recommended area codes:

| Code | Area |
|---|---|
| `INT` | Request intake and GSA pre-check |
| `COF` | Coface lookup and fast-track |
| `COL` | Information and document collection |
| `FIN` | Financial extraction, metrics, and quantitative analysis |
| `NFR` | Non-financial risk |
| `COM` | Communications and closure |
| `ARC` | Archive and retention behavior |
| `OPS` | Supplier one-page summary and monitoring |
| `EWS` | Early Warning System |
| `GOV` | Governance, audit, security, and human approval |
| `PLT` | Cross-cutting platform and demo constraints |

Allocate IDs sequentially within an area. Never renumber an established ID; mark superseded
requirements and link their replacements.

## Minimum Requirement Record

Each structured requirement should include:

| Field | Content |
|---|---|
| ID | Stable `SRM-<AREA>-<NNN>` identifier |
| Title | Concise capability name |
| Statement | Testable required behavior |
| Source | Slide marker or explicit plan section |
| Rationale | Business outcome or control intent |
| Acceptance criteria | Observable completion conditions |
| Implementation artifacts | Paths or component identifiers |
| Verification | Planned or completed validation evidence |
| Status | Proposed, confirmed, implemented, verified, deferred, or superseded |
| Notes | Assumptions, dependencies, and open decisions |

## Traceability Expectations

Future work should create `10-deck-traceability.md` as planned and use it as the coverage index. It
must map every substantive source capability to one or more requirement IDs and implementation
artifacts. Each detailed specification must cite the requirement IDs it realizes.

Coverage review must explicitly include:

- the five process stages and workload priorities;
- all GSA pre-check outcomes and the no-DUNS fallback;
- Coface data retrieval, data-age check, conversion, and fast-track;
- full-review collection, analysis, communication, and human decision;
- archive creation, classification, deduplication, completeness, locking, metadata, and history;
- the supplier one-page summary, refresh, export, spend gating, and role restrictions;
- Early Warning risk judgment, prompting, request creation, linking, synchronization, and reminders;
- audit-trail and human-accountability controls.

## Open Decisions

Record unresolved decisions in the specification most closely related to the requirement and link
them from the traceability index. Include:

- the decision required;
- why source material is insufficient;
- affected requirement IDs and artifacts;
- available options and their consequences;
- owner and status.

Do not bury unresolved policy choices in code, seed data, or prose examples.

