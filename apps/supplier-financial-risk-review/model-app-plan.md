# Supplier Financial Risk Review — design

Supplier Risk Management demo: buyers request supplier financial ratings and reviewers run the five-stage financial review. Step 1 (request and GSA/DUNS pre-check) slice.

Generated from `app-spec.json` by `scripts/write-app-spec-doc.js`. **Regenerate rather than
hand-edit** — `app-spec.json` is the source of truth, so a manual edit here is lost on the next
run and silently disagrees with what actually builds.

## Environment

| Setting | Value |
|---|---|
| Environment | https://org5b55c88b.crm.dynamics.com |
| Solution | SRMAgentDemo |
| Publisher prefix | mag |

## Jobs to be done

> ⚠ No `personas[]` were captured, so this app has no recorded jobs-to-be-done and no security
> roles — it will open only for system administrators. Capture who uses the app and what each
> of them needs to get done, then regenerate this document.

## Data model

### Financial Review Request `mag_financialreviewrequest` _(existing table — reused, not created)_

A buyer's request for a supplier financial rating; hosts the five-stage Supplier Financial Review process and the GSA pre-check outcome.

| Column | Type | Notes |
|---|---|---|
| Name | Text | primary name |
| Demo Key | Text | — |
| Request Ref | Text | — |
| Buyer Name | Text | — |
| Buyer Email | Text | — |
| Reviewer Name | Text | — |
| Division | Text | — |
| Review Status | Choice | choices: Not Started, In Progress, Completed |
| Review Path | Choice | choices: GSA Reuse, Coface Fast-Track, Full Review |
| GSA Pre-Check Result | Choice | choices: Valid active rating, Rating expired, No matching supplier, Skip - no DUNS |
| GSA Rating | Text | — |
| GSA Remarks | Memo | — |
| GSA Rating Date | DateTime | — |
| GSA Rating Expiry | DateTime | — |
| Coface Score | Integer | — |
| Coface Risk Tier | Choice | choices: Low, Medium, High, Unavailable |
| Coface Assessment Date | DateTime | — |
| Coface Data Age Months | Integer | — |
| Coface Within 18 Months | Boolean | — |
| Preliminary Rating | Choice | choices: Green, Yellow, Red, Not rated |
| Narrative Draft | Memo | — |
| Final Rating | Choice | choices: Green, Yellow, Red, Not rated |
| Rating Date | DateTime | — |
| Rating Expiry | DateTime | — |
| Remarks | Memo | — |
| Reviewer Override | Boolean | — |
| Archive Folder Link | Text | — |
| Current Stage | Integer | — |
| Clarifications Closed | Boolean | — |
| DUNS Number | Text | — |
| No DUNS / DUNS Applying | Boolean | — |
| D&B Auto-Fill Confirmed | Boolean | — |
| Mandatory Re-Review Triggered | Boolean | — |
| Reviewer Notified | Boolean | — |
| Coface Retrieved | Boolean | — |
| Document Request Sent | Boolean | — |
| Reminder Count | Integer | — |
| Documents Received | Boolean | — |
| Working Paper Complete | Boolean | — |
| Metrics Computed | Boolean | — |
| Non-Financial Risks Logged | Boolean | — |
| Final Rating Confirmed by Reviewer | Boolean | — |
| Buyer Notified | Boolean | — |
| Archive Complete | Boolean | — |
| Record Locked | Boolean | — |
| GSA Push-Back Complete | Boolean | — |
| One-Page Summary Refreshed | Boolean | — |

### Supplier `mag_supplier` _(existing table — reused, not created)_

Fictional supplier master; its D&B-sourced identity fields are shown on the review request so the buyer can confirm the auto-fill.

| Column | Type | Notes |
|---|---|---|
| Name | Text | primary name |
| Demo Key | Text | — |
| Supplier Code | Text | — |
| Legal Name | Text | — |
| DUNS | Text | — |
| Has DUNS | Boolean | — |
| Street | Text | — |
| City | Text | — |
| Country | Text | — |
| Region | Text | — |
| Website | Text | — |
| Business Category | Text | — |
| Manufacturing Zone | Text | — |
| Magna Division | Text | — |
| Annual Spend | Money | — |
| Has Active Spend | Boolean | — |
| Current Magna Rating | Choice | choices: Green, Yellow, Red, Not rated |
| Current Coface Score | Integer | — |
| Contact Name | Text | — |
| Contact Email | Text | — |
| Factory Location | Text | — |

### D&B Profile `mag_dnbprofile` _(existing table — reused, not created)_

Mock D&B / public profile keyed by DUNS; the seeded source for Step 1 field auto-completion.

| Column | Type | Notes |
|---|---|---|
| Name | Text | primary name |
| Demo Key | Text | — |
| DUNS | Text | — |
| Legal Name | Text | — |
| Street | Text | — |
| City | Text | — |
| Country | Text | — |
| Region | Text | — |
| Website | Text | — |
| Business Category | Text | — |
| Manufacturing Zone | Text | — |
| Established Year | Integer | — |
| Shareholder Summary | Memo | — |
| Product Lines | Memo | — |
| Source URL | Text | — |
| Profile Checked On | DateTime | — |
| Synthetic Data | Boolean | — |

### GSA Rating Record `mag_gsaratingrecord` _(existing table — reused, not created)_

Mock GSA procurement rating keyed by DUNS; the seeded source for the Step 1 reuse pre-check.

| Column | Type | Notes |
|---|---|---|
| Name | Text | primary name |
| Demo Key | Text | — |
| DUNS | Text | — |
| Rating | Choice | choices: Green, Yellow, Red, Not rated |
| Remarks | Memo | — |
| Rating Date | DateTime | — |
| Expiry Date | DateTime | — |
| Mandatory Re-Review | Boolean | — |
| Reviewer Name | Text | — |
| Synthetic Data | Boolean | — |

### Relationships

| Kind | From | To | Lookup |
|---|---|---|---|
| 1:N | mag_supplier | mag_financialreviewrequest | mag_SupplierId |
| 1:N | mag_supplier | mag_dnbprofile | mag_SupplierId |
| 1:N | mag_supplier | mag_gsaratingrecord | mag_SupplierId |

## Surfaces

### Generative pages

> ⚠ No generative pages. Per the genpage-first policy, any non-record surface — an overview or
> landing page, a dashboard, an analytics view, a guided/wizard flow — should be a generative
> page rather than a classic dashboard. If this app genuinely has only record CRUD, that's
> fine; otherwise a surface is missing.

### Forms

| Form | Table | Type | Layout | Sub-grids |
|---|---|---|---|---|
| Financial Review Request | mag_financialreviewrequest | Main | explicit (2 tabs) | — |
| Financial Review Request Quick Create | mag_financialreviewrequest | QuickCreate | explicit (1 tab) | — |
| Supplier D&B Profile | mag_supplier | QuickView | explicit (1 tab) | — |
| Supplier | mag_supplier | Main | explicit (1 tab) | mag_financialreviewrequest |
| D&B Profile | mag_dnbprofile | Main | auto | — |
| GSA Rating Record | mag_gsaratingrecord | Main | auto | — |

Quick-view cards embedded on a form:

- **Financial Review Request** shows `Supplier D&B Profile` via lookup `mag_supplierid`

### Views

| View | Table | Columns | Filters | Sort |
|---|---|---|---|---|
| My Open Reviews | mag_financialreviewrequest | mag_name, mag_supplierid, mag_gsaprecheckresult, mag_reviewpath, mag_reviewstatus, mag_buyername, createdon | ownerid eq-userid; mag_reviewstatus ne Completed | createdon desc |
| New Requests - Not Started | mag_financialreviewrequest | mag_name, mag_supplierid, mag_dunsnumber, mag_noduns, mag_gsaprecheckresult, mag_buyername, createdon | mag_reviewstatus eq Not Started | createdon asc |
| Auto-Closed (GSA Reuse) | mag_financialreviewrequest | mag_name, mag_supplierid, mag_gsarating, mag_gsaratingdate, mag_gsaratingexpiry, mag_reviewername, mag_buyernotified | mag_reviewpath eq GSA Reuse | mag_gsaratingdate desc |
| Full Review Required | mag_financialreviewrequest | mag_name, mag_supplierid, mag_gsaprecheckresult, mag_mandatoryrereview, mag_noduns, mag_reviewername, mag_reviewstatus | mag_reviewpath eq Full Review; mag_reviewstatus ne Completed | mag_name asc |
| Supplier Review History | mag_financialreviewrequest | mag_name, mag_reviewpath, mag_reviewstatus, mag_finalrating, mag_ratingdate, createdon | all records | createdon desc |

## Navigation

- **Supplier Risk**
  - Review Desk
    - Financial Review Requests → table `mag_financialreviewrequest` — icon: the table's own
  - Suppliers
    - Suppliers → table `mag_supplier` — icon: the table's own
  - External Sources (Mock)
    - D&B Profiles → table `mag_dnbprofile` — icon: the table's own
    - GSA Rating Records → table `mag_gsaratingrecord` — icon: the table's own
