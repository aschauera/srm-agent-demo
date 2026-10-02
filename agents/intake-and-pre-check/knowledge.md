# Intake & Pre-Check - Knowledge Scope

| Source | Access | Used for |
|---|---|---|
| `mag_supplier` | Read and create (through the submit flow) | Supplier identity |
| `mag_dnbprofile` | Read | Profile for buyer confirmation |
| `mag_gsaratingrecord` | Read, by the pre-check flow only | Pre-check outcome |
| `mag_financialreviewrequest` | Create (through the submit flow) | The request |
| `mag_reviewaudittrail` | Create (through flows) | Ledger |
| `mag_communicationlog` | Create (through the pre-check flow) | Notifications |

No document knowledge sources.

Grounding boundary: describe a GSA or D&B result only from tool output. Never state a rating
the tools did not return.
