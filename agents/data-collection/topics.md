# Data Collection - Topics and Tools

| Topic | Behavior |
|---|---|
| Retrieve Coface | Look up `mag_cofacecreditrecord` by DUNS. Return score, tier, payment record, alerts, credit limit, data date, within-18-months flag. |
| Fuzzy match (no DUNS) | Search by legal name and country. Return a shortlist for the reviewer. Write nothing until the reviewer chooses. |
| Risk brief | Format the Coface data with traffic-light labels and a short interpretation. Attach it to the reviewer notice. |
| Send document request | Build the checklist, send it, create a `mag_documentrequest`, set the reminder dates. |
| Reminders | Day 3 reminder, day 7 escalation copied to the buyer. Scheduled flow. |
| File reply | Create a `mag_supplierdocument` for each attachment and link it to the request. |

## Planned tools (not built)

| Tool | Type | Writes |
|---|---|---|
| Retrieve Coface record | Agent flow | Coface columns on the request, ledger |
| Send document request | Agent flow | `mag_documentrequest`, `mag_communicationlog`, ledger |
| Reminder cadence | Scheduled flow | `mag_documentrequest`, `mag_communicationlog`, ledger |
| File supplier reply | Agent flow | `mag_supplierdocument`, ledger |

Source: slides 4-5 (Coface), 7 (document collection). Requirement IDs for areas `COF` and `COL`
are not yet allocated.
