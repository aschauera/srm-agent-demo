# Early Warning Triage - Topics and Tools

| Topic | Behavior |
|---|---|
| Tag and score | Suggest risk tags and a materiality level for a `mag_earlywarning`. |
| Prompt | Mandatory or soft prompt to the buyer, by materiality. |
| Create linked request | Pre-populate a `mag_financialreviewrequest` with the source early warning and a direct link. |
| Sync | Keep entry status and request status consistent in both directions. |
| 24-hour reminder | Scheduled flow that reminds on prompted entries with no action. |

## Planned tools (not built)

| Tool | Type |
|---|---|
| Score early warning | Agent flow with a prompt action |
| Create review request from early warning | Agent flow |
| Early warning reminder | Scheduled flow |

Source: the Early Warning slides near the end of the extract. Requirement IDs for area `EWS`
are not yet allocated.

Open decisions: the materiality bands, and whether the agent is a direct entry point (see the
topology's open decisions).
