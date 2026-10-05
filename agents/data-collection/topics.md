# Data Collection - Topics and Tools

| Topic | Behavior |
|---|---|
| Retrieve Coface | Look up `mag_cofacecreditrecord` by DUNS. Return score, tier, payment record, alerts, credit limit, data date, within-18-months flag. |
| Fuzzy match (no DUNS) | Search by legal name and country. Return a shortlist for the reviewer. Write nothing until the reviewer chooses. |
| Risk brief | Format the Coface data with traffic-light labels and a short interpretation. Attach it to the reviewer notice. |
| Send document request | Build the checklist, send it, create a `mag_documentrequest`, set the reminder dates. |
| Reminders | Day 3 reminder, day 7 escalation copied to the buyer. Scheduled flow. |
| File reply | Create a `mag_supplierdocument`, upload attachment bytes to `mag_file` using `UpdateEntityFileImageFieldContent`, and link the document to the request. Deployed; byte-readback test pending. |

## Tools (flow deployment status)

| Tool | Type | Writes |
|---|---|---|
| Retrieve Coface record | Agent flow | Coface columns on the request, ledger; deployed and active, end-to-end test pending |
| Propose Magna rating | Agent flow | Preliminary rating only, review path, ledger and Shortcut B BPF move; deployed and active, end-to-end test pending |
| Send document request | Agent flow | `mag_documentrequest`, `mag_communicationlog`, ledger; deployed and active, test pending |
| Reminder cadence | Scheduled flow | `mag_documentrequest`, `mag_communicationlog`, ledger; deployed and active, test pending |
| File supplier reply | Agent flow | `mag_supplierdocument` file upload and audit; active, byte-readback test pending |

Source: slides 4-7 (Coface and document collection). Requirements: `SRM-COF-001..012` and
`SRM-COL-001..005, SRM-COL-012`; deployment and verification status is tracked in
[`07-stage-2-coface-and-collection.md`](../../docs/07-stage-2-coface-and-collection.md).
