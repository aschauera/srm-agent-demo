# Model-Driven App and Business Process Flow

## Scope and provenance

This slice delivers the `Supplier Financial Risk Review` model-driven app, the five-stage
`Supplier Financial Review` business process flow (BPF), and the forms for **Stage 1 — Request &
Pre-Check**. It was built in DemoPRE into the unmanaged `SRMAgentDemo` solution. The build used
the app-builder engine from the declarative spec
[app-spec.json](../apps/supplier-financial-risk-review/app-spec.json). The rendered design document
is [model-app-plan.md](../apps/supplier-financial-risk-review/model-app-plan.md).

Later work items will add the forms for Stages 2–5, the other planned areas and views, the
dashboards, security roles, and the branch automation.

| Requirement ID | Requirement | Source |
|---|---|---|
| `SRM-INT-002` | A buyer submits a financial review request for a supplier, identified by DUNS or flagged as having no DUNS. | Slides 2-3 |
| `SRM-INT-003` | D&B-sourced supplier profile data is shown on the request so the buyer can confirm the auto-fill. | Slide 2 |
| `SRM-INT-004` | The GSA pre-check result and the existing GSA rating, date, expiry, and mandatory re-review flag are visible on the request and read-only. | Slides 2-3 |
| `SRM-INT-005` | The financial review follows the five-stage process: Request & Pre-Check, Information Collection, Analysis & Rating, Communication & Decision, Archiving & Publication. | Slides 1-3; implementation plan, BPF |
| `SRM-GOV-002` | The BPF can only finish Stage 4 when a final rating exists and a human reviewer has confirmed it. | Slide 1; implementation plan, Governance principle |

## Business process flow

The BPF is named `Supplier Financial Review` and runs on `mag_financialreviewrequest`. Every step
is bound to a column; the 18 step flag columns are defined in
[02-create-tables.py](../scripts/02-create-tables.py). Steps marked **required** block stage exit.

| Stage | Steps (column) | Required |
|---|---|---|
| 1. Request & Pre-Check | DUNS Number (`mag_dunsnumber`), No DUNS (`mag_noduns`), D&B Autofill Confirmed (`mag_dnbautofillconfirmed`), GSA Pre-Check Result (`mag_gsaprecheckresult`), Mandatory Re-Review (`mag_mandatoryrereview`), Reviewer Notified (`mag_reviewernotified`) | GSA Pre-Check Result |
| 2. Information Collection | Coface Retrieved, Doc Request Sent, Reminder Count, Docs Received | — |
| 3. Analysis & Rating | Working Paper Complete, Metrics Computed, Non-Financial Risks Logged, Preliminary Rating | — |
| 4. Communication & Decision | Clarifications Closed, Final Rating, Final Rating Confirmed, Buyer Notified | Final Rating, Final Rating Confirmed |
| 5. Archiving & Publication | Archive Complete, Record Locked, GSA Push-Back Complete, Summary Refreshed | — |

### Design decisions

- **Linear BPF with stage skipping (approved).** The app-builder engine supports linear BPFs only.
  The plan's shortcuts will be carried out later by automation that moves the active stage:
  - Shortcut A, GSA reuse: Stage 1 → Stage 5.
  - Shortcut B, Coface fast-track: Stage 2 → Stage 4.

  The review path is recorded in `mag_reviewpath`, so traceability is preserved.
- **BPF backing table `new_supplierfinancialreview` (accepted exception).** The engine hard-codes
  the `new_` prefix for the BPF instance table. This is the only non-`mag_` table in the solution.
- **Human accountability.** Final Rating and Final Rating Confirmed are required steps. AI output
  goes into `mag_preliminaryrating`, a separate column, so a reviewer must still act before
  Stage 4 can close.

## App

| Area | Group | Subareas |
|---|---|---|
| Supplier Risk | Review Desk | Financial Review Requests |
| | Suppliers | Suppliers |
| | External Sources (Mock) | D&B Profiles, GSA Rating Records |

The app uses the modern shell (`newLook`).

### Forms

| Table | Form | Type | Purpose |
|---|---|---|---|
| `mag_financialreviewrequest` | Financial Review Request | Main | BPF host, with two tabs. **Request** holds request details, supplier identification (DUNS), and the Supplier D&B Profile quick view. **Pre-Check** holds the read-only GSA auto-check result and the financial risk team information. |
| `mag_financialreviewrequest` | Financial Review Request Quick Create | Quick Create | Buyer submission. |
| `mag_supplier` | Supplier D&B Profile | Quick View | Read-only D&B identity and location fields for buyer confirmation. Quick views allow only one tab column and single-column sections. |
| `mag_supplier` | Supplier | Main | Supplier master, with a Financial Review Requests subgrid. |
| `mag_dnbprofile` | D&B Profile | Main | Mock D&B source record. |
| `mag_gsaratingrecord` | GSA Rating Record | Main | Mock GSA source record. |

### Views

On `mag_financialreviewrequest`:

- My Open Reviews
- New Requests - Not Started
- Auto-Closed (GSA Reuse)
- Full Review Required
- Supplier Review History (used by the Supplier form subgrid)

Default views of the four app tables are enriched with key columns.

### Supplier lookup by DUNS

`SRM-INT-002` requires buyers to identify suppliers by DUNS, so the Supplier lookup on the request
searches both the supplier name and DUNS. [05-configure-supplier-lookup.py](../scripts/05-configure-supplier-lookup.py)
applies and checks this configuration. It is idempotent.

| Artifact | Configuration |
|---|---|
| `mag_supplier` columns `mag_name`, `mag_duns`, `mag_legalname`, `mag_country` | Searchable (`IsValidForAdvancedFind`). The SDK had created custom columns as non-searchable. |
| Quick Find Active Suppliers (Quick Find view) | Find columns: Name and DUNS. Result columns: Name, DUNS, Legal Name, Country. |
| Supplier Lookup View (Lookup view) | Columns: Name, DUNS, Country. The lookup dropdown shows DUNS under each supplier name. |

DemoPRE rejects Web API updates to a Quick Find view's `fetchxml` with `0x80040216`, even when the
fetch is unchanged. The find columns are therefore applied through the solution:

1. Export the solution fresh.
2. Edit `Entities/mag_Supplier/SavedQueries/{ffdfa154-…}.xml`.
3. Pack and import the solution.

The script only updates the Lookup view through the Web API. It verifies that the Quick Find
columns are present and fails with this guidance if they are missing.

## Build and verification

1. Provision schema columns and labels with `python scripts/02-create-tables.py`, or with
   `--labels-only` to converge display names only.
2. Lint the spec with the app-builder `lint-app-spec.js`.
3. Build it with `build-model-app.js --apply --verify --publish`. Put the workspace outside the
   repo; `.maker-workspace/` is git-ignored.
4. Run the standalone `verify-model-app.js` check later, for example after a Maker edit.

Evidence (2026-09-28, DemoPRE):

- `build complete — 22 created, 99 skipped, 0 failed (121 steps)`
- `verify PASS (136/136 present)`

The build is additive. It does not re-apply edits to existing views, forms, or BPF structure. To
apply a structural change, tear down the affected artifact and rebuild.

## Deferred and open items

- Stage 2–5 forms and tabs: Coface, Working Paper, Non-Financial, Communications, Archive, Audit.
- Remaining planned views: Awaiting Supplier Documents, Pending Rating Decision, Fast-Track
  (Coface), Completed This Quarter, High-Materiality Early Warnings.
- Remaining planned areas: Early Warnings, Reference Data, Archive.
- Dashboards: Risk Team and Supplier Risk. The generative-page approach is still to be decided.
- Security roles for the Buyer and Financial Risk Reviewer personas. The app currently opens for
  system administrators only.
- Branch automation that moves the BPF active stage for Shortcut A and Shortcut B.
- Seeded review requests carry step-flag values consistent with their path. They do not yet have
  BPF instances or an aligned active stage.
- Most custom columns on the other tables are still non-searchable, as the SDK created them. Make
  them searchable table by table, as Quick Find or lookup needs arise.
