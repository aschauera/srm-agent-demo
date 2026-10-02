# Data Collection - Knowledge Scope

| Source | Access |
|---|---|
| `mag_cofacecreditrecord` | Read |
| `mag_supplier` | Read |
| `mag_documentrequest` | Read, create, update |
| `mag_supplierdocument` | Read, create |
| `mag_communicationlog` | Read, create |
| `mag_financialreviewrequest` | Read; update Coface and collection columns only |
| `mag_reviewaudittrail` | Create |

Grounding boundary: Coface values come only from `mag_cofacecreditrecord`. Never invent a
score, a data date or an alert.
