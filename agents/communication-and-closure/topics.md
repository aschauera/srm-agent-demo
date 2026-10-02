# Communication & Closure - Topics and Tools

| Topic | Behavior |
|---|---|
| Clarification email | Detect inconsistencies, draft a targeted email, wait for approval. |
| Call summary | Summarize a transcript (customer share, lease terms, litigation, plans). Store in `mag_communicationlog`. |
| Translate | Translate inbound or outbound correspondence. Keep the original. |
| Coface fast-track | Check data age, apply `mag_ratingconversionrule`, propose the rating, move the BPF to Stage 4 for confirmation. |
| Closing email | Draft from the final rating and narrative. Send after approval. |
| System sync | After confirmation: update the request, tag the record, write the GSA record by DUNS, ledger every step. |

## Tools (retrieval and proposal flows deployed; others planned)

| Tool | Type | Writes |
|---|---|---|
| Convert Coface rating | Agent flow | Proposed rating, ledger |
| Send approved email | Agent flow | `mag_communicationlog`, ledger |
| Sync final rating | Agent flow | Request, GSA record, ledger |

Source: slides 6, 10, 12. Requirement IDs for areas `COF` and `COM` are not yet allocated.

Open decisions: the Coface-to-Magna mapping values, and whether the GSA push-back needs an
approval step. Neither is in the source.
