# SRM Orchestrator - Topics and Tools

Generative orchestration. Topics are kept to the few that need fixed behavior.

| Topic | Trigger | Behavior |
|---|---|---|
| Request status | "where is", "status of", "who is reviewing" | Call **SRM - Get review request status** with `requestref`. Reply with stage, path, status, final rating state and link. If not found, say so and offer to search by supplier. |
| Hand off to specialist | Any non-status intent | Pick the specialist by the routing table in [05-agent-topology.md](../../docs/05-agent-topology.md). Pass the shared context. Relay the handoff envelope. |
| Rating requested | "set the rating", "approve", "confirm the rating" | Decline. Explain that the reviewer confirms in the app. Give the record link. |
| Fallback | Unrecognized | Ask one clarifying question. List what the agent can do. |

## Tools

| Tool | Type | Flow | Status |
|---|---|---|---|
| Get review request status | Agent flow | [srm-get-request-status](../../flows/srm-get-request-status/) | Deployed, not yet tested as a tool |
| Six specialist agents | Connected agents | See topology | Intake & Pre-Check exists; others to build |

## Connected-agent setup (called side)

Each specialist needs an `OnRedirect` topic, global variables for the shared context fields
with *Receive values from other agents* enabled, and `inputType: {}` / `outputType: {}` on the
topic. Publish each specialist before adding it to the orchestrator.

## Requirements

Slide 1 (governance note). `SRM-GOV-002`, `SRM-GOV-004`.
