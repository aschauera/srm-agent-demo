# Financial Analysis & Rating - Knowledge Scope

| Source | Access |
|---|---|
| `mag_supplierdocument` | Read |
| `mag_financialworkingpaper` | Read, create, update |
| `mag_nonfinancialriskitem` | Read, create |
| `mag_riskscoringrule` | Read |
| `mag_adversenewsevent` | Read |
| `mag_financialreviewrequest` | Read; update preliminary rating and narrative columns only |
| `mag_reviewaudittrail` | Create |

Grounding boundary: every metric traces to a working paper row, and every risk item to a
source. The agent does not read or write the final rating columns.
