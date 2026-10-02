# Financial Analysis & Rating - Topics and Tools

| Topic | Behavior |
|---|---|
| Extract statements | Read received documents and populate `mag_financialworkingpaper` rows per fiscal year or interim. Mark extraction confidence. |
| Compute metrics | Derive the metric columns and anomaly flags from the working paper. |
| Compile non-financial risks | Create `mag_nonfinancialriskitem` rows with severity, source URL and event date. |
| Preliminary rating | Apply `mag_riskscoringrule` per dimension, total the points, write the preliminary rating. |
| Draft narrative | Write the AI narrative draft covering quantitative and qualitative findings. |
| Explain a rating | Show which rules produced which points. |

## Planned tools (not built)

| Tool | Type | Writes |
|---|---|---|
| Extract statements into working paper | Agent flow with AI Builder document extraction | Working paper, ledger |
| Compute metrics and flags | Agent flow | Working paper |
| Compile non-financial risks | Agent flow | Non-financial items, ledger |
| Score and draft | Agent flow with a prompt action | Preliminary rating, narrative, ledger |

Source: slides 8-11. Requirement IDs for areas `FIN` and `NFR` are not yet allocated.

Open decision: the scoring thresholds and points. They are not in the source. The table
`mag_riskscoringrule` holds demo placeholders that must be marked as such.
