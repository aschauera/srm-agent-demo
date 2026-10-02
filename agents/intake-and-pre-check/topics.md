# Intake & Pre-Check - Topics and Tools

| Topic | Trigger | Behavior |
|---|---|---|
| Look up supplier profile | "D&B", "look up DUNS", "who is DUNS ..." | Call **Look up D&B profile** with `duns`. Show legal name, address, country, category. Say whether the supplier already exists. If none, say "no profile found". |
| Submit review request | "submit", "new review", "request a rating" | Collect `duns` or (`noduns` + `suppliername`), `buyername`, `buyeremail`, optional `division`. Show the D&B profile for confirmation, set `dnbconfirmed`. Call **Submit review request**. Report ref, link and message. |
| Explain pre-check result | "why did it close", "why full review" | Ask for the request ref, call the orchestrator's status route, and explain the four outcomes. |
| OnRedirect | Called by orchestrator | Read the shared context from global variables and return the handoff envelope. |

## Tools

| Tool | Flow | Inputs | Status |
|---|---|---|---|
| Look up D&B profile | [intake-lookup-dnb-profile](../../flows/intake-lookup-dnb-profile/) | `duns` | Deployed, not yet tested as a tool |
| Submit review request | [intake-submit-review-request](../../flows/intake-submit-review-request/) | `duns`, `noduns`, `suppliername`, `buyername`, `buyeremail`, `division`, `dnbconfirmed` | Deployed, not yet tested as a tool |
| GSA pre-check on submit | [intake-precheck-on-submit](../../flows/intake-precheck-on-submit/) | none | Runs on its own; not an agent tool |

## Failure paths

- Missing or invalid buyer email or name: the submit flow refuses and returns a message. Relay
  it and ask for the value.
- Supplier not found by DUNS: the submit flow creates it from its D&B profile. With no profile,
  say that the supplier could not be created.

## Requirements

Slides 2-3, 5. `SRM-INT-002`, `SRM-INT-007`, `SRM-INT-008` to `SRM-INT-012`, `SRM-GOV-004`.
