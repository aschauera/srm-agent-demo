# Archive & Insights - Topics and Tools

| Topic | Behavior |
|---|---|
| Create archive | Create folder records and the four subfolders in `mag_archiverecord`. |
| File and classify | Assign each document a subfolder, item type and metadata tags. Flag duplicates. |
| Completeness check | Compare the archive with the required items and report gaps. |
| Lock | Set the locked flag when the review is complete. |
| One-page summary | Generate or refresh `mag_supplieronepagesummary` with versioning. |
| Adverse news | Read `mag_adversenewsevent` and add digest items. |

## Planned tools (not built)

| Tool | Type | Writes |
|---|---|---|
| Create archive structure | Agent flow | `mag_archiverecord`, ledger |
| Classify and file | Agent flow | `mag_archiverecord`, `mag_supplierdocument` |
| Lock archive | Agent flow | `mag_archiverecord`, request, ledger |
| Generate one-page summary | Agent flow with a prompt action | `mag_supplieronepagesummary`, ledger |

Source: slides 13 onward. Requirement IDs for areas `ARC` and `OPS` are not yet allocated.

Open decisions: retention periods, and the four subfolder names if they are not in the data.
