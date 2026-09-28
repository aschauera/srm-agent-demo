# Copilot Repository Instructions

Read and follow `/AGENTS.md` before planning, editing, or generating artifacts in this repository.
It is the canonical agent guide.

The authoritative project inputs are:

- `/docs/requirements/README.md`
- `/docs/planning/implementation-plan.md`
- `/docs/requirements/source/fy27-magna-srm-use-case-extracted.txt`

Keep work traceable to the source presentation, preserve the human final-rating decision, use only
fictional demo data, and do not target a live Power Platform environment without explicit user
authorization.

After each successful DemoPRE deployment, export and unpack the `SRMAgentDemo` solution into
`solutions/SRMAgentDemo/` if the local source does not already represent the deployed state. Follow
the Solution Source Synchronization section of `/AGENTS.md`.

Generate flows as Copilot Studio agent flows, code-first through the Dataverse API from source in
`/flows`, as defined in the Cloud Flow Generation section of `/AGENTS.md`.

