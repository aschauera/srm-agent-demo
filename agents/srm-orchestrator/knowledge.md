# SRM Orchestrator - Knowledge Scope

| Source | Access | Used for |
|---|---|---|
| `mag_financialreviewrequest` | Read, through the status flow only | Status answers |
| `new_supplierfinancialreview` (BPF instance) | Read, through the status flow only | Active stage |
| `mag_reviewaudittrail` | Read | "What happened to this request" answers |

No document knowledge sources. No write access to any table: the orchestrator delegates every
write to a specialist.

Grounding boundary: answer only from tool output. If a tool returns nothing, say so.
