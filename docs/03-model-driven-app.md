# Model-Driven App and Business Process Flow

## Scope and provenance

This slice delivers the `Supplier Financial Risk Review` model-driven app, the five-stage
`Supplier Financial Review` business process flow (BPF), and the forms for **Stage 1 — Request &
Pre-Check**. It was built in DemoPRE into the unmanaged `SRMAgentDemo` solution. The build used
the app-builder engine from the declarative spec
[app-spec.json](../apps/supplier-financial-risk-review/app-spec.json). The rendered design document
is [model-app-plan.md](../apps/supplier-financial-risk-review/model-app-plan.md).

Later work items will add the forms for Stages 2–5, the other planned areas and views,
dashboards, and security roles. The Stage 1 server automation is deployed and verified; see
[06-agent-flows-and-actions.md](./06-agent-flows-and-actions.md).

| Requirement ID | Requirement | Source |
|---|---|---|
| `SRM-INT-002` | A buyer submits a financial review request for a supplier, identified by DUNS or flagged as having no DUNS. | Slides 2-3 |
| `SRM-INT-003` | D&B-sourced supplier profile data is shown on the request so the buyer can confirm the auto-fill. | Slide 2 |
| `SRM-INT-004` | The GSA pre-check result and the existing GSA rating, date, expiry, and mandatory re-review flag are visible on the request and read-only. | Slides 2-3 |
| `SRM-INT-005` | The financial review follows the five-stage process: Request & Pre-Check, Information Collection, Analysis & Rating, Communication & Decision, Archiving & Publication. | Slides 1-3; implementation plan, BPF |
| `SRM-GOV-002` | The BPF can only finish Stage 4 when a final rating exists and a human reviewer has confirmed it. | Slide 1; implementation plan, Governance principle |
| `SRM-INT-006` | Request data checks: the DUNS is 9 digits and matches the selected supplier, or the buyer ticks No DUNS / DUNS applying; buyer name and email are required. | Slides 2-3 |
| `SRM-INT-007` | No DUNS / DUNS applying disables the GSA pre-check, shows a bypass notice, and routes the request to the full review with status Not Started. | Slide 3 |
| `SRM-GOV-003` | GSA auto-check results are read-only, and buyers cannot edit the Financial Risk Team information. | Slides 1-2 |
| `SRM-UX-001` | The request shows color-coded indicators for the pre-check outcome, rating validity, mandatory re-review, review path and status, and final rating, and banners explain the resulting branch. | Slides 1-3; user request (2026-09-29) |

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

## Stage 1 data checks, business rules and indicators

[06-configure-review-request-form.py](../scripts/06-configure-review-request-form.py) deploys this
configuration idempotently (`--dry-run` shows the plan). It applies three things:

- Choice option colors, from [indicator-colors.json](../apps/supplier-financial-risk-review/indicator-colors.json).
- The web resources `mag_/srm/reviewrequest.js` and `mag_/srm/reviewrequest-status.html`, sourced
  from [webresources/](../apps/supplier-financial-risk-review/webresources/).
- The form library and onload handler on the main and quick-create request forms, plus a
  **Review Status** panel section at the top of the Request tab on the main form. Quick Create
  includes hidden, disabled copies of the GSA result, review path and review status so the No DUNS
  branch can save its values on either form.

The rules run in form script, not as business rules. The SDK path for business rules writes every
literal as a string, which makes Boolean and choice conditions unreliable. The script resolves
choices by label, never by value. Server-side enforcement belongs to the Stage 1 automation flows
(see *Deferred and open items*).

### Data checks (`SRM-INT-006`)

| Check | Behavior | Blocks save |
|---|---|---|
| DUNS format | Spaces and dashes are removed (`12-345-6789` → `123456789`). Anything other than 9 digits shows a field error. | Yes |
| DUNS matches supplier | If the selected supplier has a DUNS and the request DUNS differs, a field error names the supplier's DUNS. | Yes |
| DUNS or No DUNS | On save, one of the two must be set. Entering a DUNS clears No DUNS; No DUNS is rejected when the selected supplier has a DUNS. | Yes |
| Supplier check | Save is blocked while the selected supplier is loading or if its DUNS cannot be read. | Yes |
| Supplier defaults | On a new request, selecting a supplier fills its DUNS. A supplier with no DUNS ticks No DUNS instead. | — |
| Required fields | Supplier, Buyer Name and Buyer Email are required on both forms. Buyer Email is also checked for a basic address shape. | Yes |

### Business rules (`SRM-INT-007`, `SRM-GOV-003`)

- **No DUNS / DUNS applying (slide 3).** The DUNS is cleared and locked. GSA Pre-Check Result is
  set to *Skip - no DUNS* and Review Path to *Full Review*. Review Status is set to *Not Started*
  when empty. A bypass banner is shown. Unticking the box removes the bypass values so the
  pre-check can run again.
- **Read-only sections.** The GSA Financial Rating Auto-Check Result section is read-only on the
  form. The Financial Risk Team Information section is locked unless the user holds
  `SRM Financial Risk Reviewer` or `System Administrator`. The role names are configured in
  `REVIEWER_ROLES` in the script. Security roles are not yet provisioned, so this is a form-level
  control only.

### Indicators (`SRM-UX-001`)

Banners use the platform notification levels: red for errors, amber for warnings, blue for
information.

| Banner | Level | Condition |
|---|---|---|
| Cannot save: DUNS check | Error | Save attempted with a failing data check. |
| GSA reuse qualifies | Info | Pre-check is *Valid active rating*, the expiry is today or later, and no mandatory re-review is triggered. |
| GSA rating expired | Warning | Pre-check is *Rating expired*, or it is *Valid active rating* but the expiry is in the past. |
| Mandatory re-review | Warning | Mandatory Re-Review Triggered is set. |
| No GSA match | Warning | Pre-check is *No matching supplier*. |
| No DUNS bypass | Warning | No DUNS / DUNS applying is ticked. |

The **Review Status** panel shows one card for each of the following:

- DUNS check
- GSA pre-check
- GSA rating details (only when the pre-check is *Valid active rating*)
- GSA rating validity (from the expiry date compared with today)
- Mandatory re-review
- Review path
- Review status
- Final rating, labelled as the human reviewer's decision

Choice cards take their color from the option metadata, so the same colors also appear in grids.
The **DUNS check**, **GSA rating validity**, and **Mandatory re-review** cards are computed, not
choices, so they use the same palette in code.

| Choice | Green `#107C10` | Blue `#0078D4` | Amber `#CA5010` | Red `#D13438` | Grey `#8A8886` |
|---|---|---|---|---|---|
| GSA pre-check | Valid active rating | — | Rating expired | No matching supplier | Skip - no DUNS |
| Review status | Completed | In Progress | — | — | Not Started |
| Review path | GSA Reuse | Coface Fast-Track | Full Review | — | — |
| Rating (all rating columns) | Green | — | — | Red | Not rated |

The Yellow rating uses `#F2C80F` with dark text. This palette is a demo visual convention, not a
Magna policy. To change it, edit `indicator-colors.json` and rerun the script. The source does not
define an "expiring soon" threshold, so rating validity only distinguishes valid from expired.

The form script pushes each model to the panel, retrying until the control and the panel script
are ready. The platform can reload the panel iframe after a push, for example when Quick Create
opens. The form script therefore also publishes the latest model on the app window, keyed by
record ID, and the panel pulls it on load. The Quick Create form has no panel and never replaces
the main form's model. Field errors for a missing supplier or DUNS appear only on save, so a new
form starts without errors. Review Status defaults to *Not Started* at save rather than on load, so
an untouched new form stays clean.

The deploy script also renders No DUNS / DUNS Applying with the platform toggle control
(`MscrmControls.FieldControls.ToggleControl`) on both forms, and sizes the panel cell to two form
rows.

### App components

A model-driven app shows only the business process flows and forms that are its app components.
The app-builder build does not add the BPF or the Quick Create form, and its verify does not flag
their absence. The deploy script adds both with `AddAppComponents` and publishes the app module.
Without them the stage bar and Quick Create do not appear.

### Verification

- `node --check` passed on the form script.
- A mock-`Xrm` harness passed 22 scenarios:
  - supplier defaulting;
  - DUNS normalization, format and mismatch errors;
  - save blocking, including a missing supplier, a failed supplier read and an invalid email;
  - applying and reverting the No DUNS bypass;
  - the FRT lock for non-reviewers;
  - each banner;
  - an untouched new form stays clean, and Review Status defaults to *Not Started* at save.
- The deploy script ran against DemoPRE and published the latest web resources, the Quick Create
  hidden system fields and the app components. XML verification confirmed the main-form status
  panel, the hidden, disabled Quick Create fields required to save the No DUNS route, and the BPF
  and Quick Create app components.
- The 12 seeded requests satisfy the data checks. No DUNS requests carry *Skip - no DUNS* and
  *Full Review*.
- Browser checks in the app (2026-09-30, DemoPRE; nothing was saved):
  - REQ-2026-001 (GSA reuse), -004 (expired), -008 (Coface fast-track) and -010 (No DUNS) show the
    expected banners and colored panel cards without making the form dirty.
  - The panel renders on first load, after a forced iframe reload, after switching records, and
    while Quick Create is open.
  - REQ-2026-004 shows the stage bar at *Request & Pre-Check*. After `07-align-bpf-stages.py`,
    REQ-2026-001 shows *Archiving & Publication*, -008 *Communication & Decision* and -012
    *Analysis & Rating*.
  - Quick Create opens without field errors. Setting No DUNS locks the DUNS, and saving without
    Supplier, Buyer Name and Buyer Email is blocked. Cancelling an untouched Quick Create closes it
    without an unsaved-changes prompt.
  - No DUNS / DUNS Applying renders as a toggle on both forms. Switching it on routes to *Full
    Review*, locks the DUNS and updates the panel.
  - The status panel occupies two form rows (98 px) for one row of cards.

The app-builder spec sets `prune: false` on both request forms, so a rebuild keeps the panel and
the library. The build does not redeploy web resource content; rerun the script after editing the
sources.

## Build and verification

1. Provision schema columns and labels with `python scripts/02-create-tables.py`, or with
   `--labels-only` to converge display names only.
2. Lint the spec with the app-builder `lint-app-spec.js`.
3. Build it with `build-model-app.js --apply --verify --publish`. Put the workspace outside the
   repo; `.maker-workspace/` is git-ignored.
4. Run the standalone `verify-model-app.js` check later, for example after a Maker edit.
5. Configure the supplier lookup with `05-configure-supplier-lookup.py`, then the Stage 1 checks
   and indicators with `06-configure-review-request-form.py`.
6. Align the seeded requests' BPF instances with `07-align-bpf-stages.py` (`--dry-run` previews
   the changes). It creates or updates each instance's active stage and traversed path for the
   request's review path: GSA reuse 1 → 5, Coface fast-track 1 → 2 → 4 → 5, otherwise 1 → 5 in
   order, stopping at the seed `CurrentStage`.

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
- Shortcut B (Coface fast-track) BPF stage movement remains deferred to Stage 2.
- The Stage 1 server automation runs in DemoPRE and passed a live five-branch smoke test
  (2026-10-02). It covers the GSA pre-check, the No DUNS skip, the GSA reuse auto-close with
  its ledger entry and Shortcut A stage move, the notifications, and the D&B fill. See
  [06-agent-flows-and-actions.md](./06-agent-flows-and-actions.md).
- The request form's list of required buyer fields is an assumption: Supplier, Buyer Name, and
  Buyer Email. Buyer Email's basic syntax check is also a client-side usability check, not a
  source-defined email policy. The source's attachment listing the SharePoint form fields was not
  extracted.
- Seeded review requests carry step-flag values consistent with their path.
  `07-align-bpf-stages.py` creates or updates their BPF instances from the seed `CurrentStage`, so
  completed GSA reuse requests rest active on *Archiving & Publication*. For new requests, the
  intake flow moves the stage; this was verified live.
- The Active view repeats the request reference in Name, Demo Key and Request Ref. Trim it when the
  planned views are built.
- No DUNS / DUNS Applying shows the Boolean labels *True* / *False* next to the toggle. Relabel the
  column options if Yes / No reads better in the demo.
- Most custom columns on the other tables are still non-searchable, as the SDK created them. Make
  them searchable table by table, as Quick Find or lookup needs arise.
