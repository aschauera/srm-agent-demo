# Stage 1 Agent Flows and Actions

## Scope and traceability

Stage 1 implements the request and GSA pre-check paths described on slides 1-3 of the
source extract. The D&B field-completion requirement is on slide 2. These flows use seeded
Dataverse records for GSA and D&B; no third-party services are called. The reviewer keeps
responsibility for any **new** financial rating. The GSA reuse shortcut copies an existing,
human-issued GSA rating and records that provenance in the ledger; it is not an AI rating.

| Requirement | Flow source | Acceptance evidence | Status |
|---|---|---|---|
| `SRM-INT-008` GSA lookup by DUNS with four outcomes | `flows/intake-precheck-on-submit/` | Five-branch live smoke test, 2026-10-02 | Verified |
| `SRM-INT-009` valid GSA reuse: auto-complete, ledger entry, buyer and reviewer notices, no supplier contact | `flows/intake-precheck-on-submit/` | Request Completed with the GSA rating, ledger "Completed - Reuse Existing GSA DUNS Rating", two notices, BPF on *Archiving & Publication* | Verified |
| `SRM-INT-010` expired, no match, mandatory re-review and no-DUNS full-review paths | `flows/intake-precheck-on-submit/` | Each request stays Not Started on *Full Review* with no final rating, one ledger row and one reviewer to-do notice | Verified |
| `SRM-INT-011` D&B completion of supplier fields | `flows/intake-precheck-on-submit/`, `flows/intake-lookup-dnb-profile/` | Fills empty supplier fields only and logs them; the seeded suppliers are complete, so the smoke test exercised the no-op path | Partially verified |
| `SRM-INT-012` agent-assisted request submission | `flows/intake-submit-review-request/` | Invoke as a tool from the Intake & Pre-Check agent | Deployed, not verified |
| `SRM-GOV-004` auditable agent activity | All intake flows | Every smoke-test ledger row is attributed to actor type Agent | Verified for the pre-check flow |

The orchestrator's status tool is `flows/srm-get-request-status/`. The deploy script is
`scripts/08-deploy-flows.py`, and the branch smoke test is
`scripts/09-smoke-test-stage1-flows.py`. The three agent-callable flows use the
**When an agent calls the flow** trigger. They can only be verified once they are added as
tools to the Copilot Studio agents.

## Notifications

As decided by the user, each notification is sent to the single demo mailbox in the
`mag_SRMDemoMailbox` environment variable. The intended recipient is named in the
subject. Each notification is also logged in `mag_communicationlog`.

| Path | Notices |
|---|---|
| GSA reuse | Buyer: "Financial review not required", with the GSA rating. Reviewer: "Filing only, no action needed". |
| Full review (all four reasons) | Reviewer: "New financial review request" to-do, sent once. |

## DemoPRE deployment and verification

The four definitions are deployed to the unmanaged `SRMAgentDemo` solution as agent flows
(category 5, modernflowtype 1). Their Dataverse and Outlook connection references are bound,
and all four flows are on. The intake flow's stable ID is
`5a7e1c02-3f41-4d8b-9c6e-0b2f8d4a1e01`.

### Trigger registration (root cause found 2026-10-02)

After code-first deployment, the intake flow showed as **On** but never ran. Two smoke tests
and two minimal Contact-create probe flows also produced no runs. After the flow was opened and
saved once in the Power Automate designer, the trigger fired and all five smoke-test branches
passed. **A Dataverse-triggered flow written through the Web API needs one designer save before
its trigger fires.** `08-deploy-flows.py` now prints an *ACTION REQUIRED* line whenever it
creates or updates such a flow.

The designer save rewrites the stored definition. It removes empty `runAfter` blocks, adds a
description, and copies the environment variable values into the parameter defaults. None of
these changes behavior. The deploy script ignores them when it compares the environment with
`flows/`, so a rerun reports *already up to date* and does not undo the save.

The Flow checker's two "circular loop" warnings, on *Complete with GSA reuse* and *Route to
full review*, are false positives. Both actions update the request, but neither writes the
trigger's filtering columns (`mag_dunsnumber`, `mag_noduns`, `mag_supplierid`). The trigger
condition also skips Completed requests.

### Smoke test evidence (2026-10-02, DemoPRE)

`python scripts/09-smoke-test-stage1-flows.py --keep --timeout 420` reported
`All 5 pre-check outcomes passed.`

| Case | Supplier DUNS | Ledger action | BPF stage |
|---|---|---|---|
| reuse | 900000001 | Completed - Reuse Existing GSA DUNS Rating | Archiving & Publication |
| expired | 900000004 | GSA pre-check: Rating expired - full review required | Request & Pre-Check |
| mandatory | 900000006 | GSA pre-check: Valid active rating - full review required | Request & Pre-Check |
| nomatch | 900000008 | GSA pre-check: No matching supplier - full review required | Request & Pre-Check |
| skip | none (No DUNS) | GSA pre-check: Skip - no DUNS - full review required | Request & Pre-Check |

The test rows were then removed with `--cleanup-only`. The diagnostic probe workflow and its
two Contact rows were deleted. The twelve seeded review requests are unchanged.

## Running the smoke test

Set `DATAVERSE_URL`, `TENANT_ID` and `PYTHONPATH` for the repository's Python authentication
helper, then run `python scripts/09-smoke-test-stage1-flows.py`. The test creates five
requests tagged with division `SMOKE-TEST` and removes them afterwards unless `--keep` is
given. `--cleanup-only` removes leftover test rows.

## Open items

- Verify `intake-submit-review-request`, `intake-lookup-dnb-profile` and
  `srm-get-request-status` by calling them from the SRM Orchestrator and Intake & Pre-Check
  agents. This depends on the agent topology and specs (plan todos 7-8).
- Exercise the D&B fill path with a supplier that has empty profile fields.
- The mandatory re-review ledger text reads "Valid active rating - full review required". The
  request's `mag_mandatoryrereview` flag records the reason; consider naming it in the ledger
  text.
