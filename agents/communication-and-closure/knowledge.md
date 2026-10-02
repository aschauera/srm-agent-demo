# Communication & Closure - Knowledge Scope

| Source | Access |
|---|---|
| `mag_communicationlog` | Read, create |
| `mag_ratingconversionrule` | Read |
| `mag_cofacecreditrecord` | Read |
| `mag_gsaratingrecord` | Read; update by DUNS in the sync flow only |
| `mag_financialreviewrequest` | Read; update sync columns only after human confirmation |
| `mag_reviewaudittrail` | Create |

Grounding boundary: converted ratings come only from the rule table.
