# Agent Guide

## Mission

Build the complete Supplier Risk Management (SRM) demo described by the project plan and the
extracted source requirements. The intended deliverable is a self-contained Power Platform solution
centered on Dataverse, a model-driven app, a five-stage business process flow, and one Copilot Studio
orchestrator with six connected agents.

This file is the canonical operating guide for every coding or authoring agent working in this
repository.

## Start Here

Read these files before planning or changing the solution:

1. `docs/requirements/README.md` - source hierarchy, interpretation, and traceability rules.
2. `docs/planning/implementation-plan.md` - approved solution direction, architecture, deliverables,
   and work breakdown.
3. `docs/requirements/source/fy27-magna-srm-use-case-extracted.txt` - verbatim text extracted from
   the source presentation.

Read the source extract selectively by relevant slide, but review every applicable slide before
declaring a capability complete.

## Source of Truth and Conflict Handling

Use this precedence order:

1. The user's current request.
2. Explicit business requirements in the source extract.
3. The implementation plan.
4. Derived specifications and implementation artifacts.

The source extract defines business intent. The implementation plan defines the approved demo
architecture used to realize that intent. Do not silently discard a source requirement because the
plan summarizes it differently. When sources conflict or leave a consequential design decision
open, document the conflict and ask for a decision before implementing that part.

Do not edit the source extract except to correct a demonstrable extraction or transcription error.
Record any such correction in the relevant traceability documentation.

## Non-Negotiable Product Rules

- Use the Power Platform environment **DemoPRE** for this project. Do not create or modify project
  resources in another environment unless the user explicitly changes this instruction.
- Use the unmanaged Dataverse solution **SRM Agent Demo** (`SRMAgentDemo`), owned by the dedicated
  SRM Agent Demo publisher with customization prefix `mag`.
- Keep the demo self-contained. Represent SharePoint, GSA, Coface, D&B, eRFX, and other external
  systems with seeded Dataverse data unless the user explicitly changes the architecture.
- Use fictional supplier identities, identifiers, financials, adverse events, and third-party data.
- Never add real credentials, connection strings, customer records, or proprietary third-party
  datasets.
- Preserve the five-stage financial review process and its GSA reuse, Coface fast-track, and full
  review paths.
- Preserve the planned topology of one SRM orchestrator and six connected specialist agents unless
  an approved design change says otherwise.
- AI may prepare, extract, summarize, recommend, pre-fill, and flag. A human reviewer remains
  accountable for the final financial rating and can override an AI recommendation.
- Make consequential automated activity auditable. Agent actions, rating conversions, overrides,
  synchronization, and archival outcomes must be traceable.
- Enforce role-sensitive access, especially for adverse legal information and read-only audit
  evidence.
- Do not provision or modify a live Power Platform environment unless the user explicitly requests
  it. For this project, that authorization is limited to DemoPRE.

## Scope Discipline

- Implement only the requested work item and its necessary dependencies.
- Do not replace the planned Power Platform architecture with a conventional custom application.
- Treat external integrations as mocks for this demo unless explicitly instructed otherwise.
- Do not invent Magna scoring thresholds, rating mappings, legal rules, retention periods, or other
  policy values absent from the sources. Make them configurable and clearly mark unresolved values.
- Keep version-sensitive maker-portal instructions intent-focused and note where UI labels may vary.
- Do not hand-author unpacked Power Platform solution XML. Unpacked solution source must be generated
  by exporting and unpacking `SRMAgentDemo` from DemoPRE, as described in
  [Solution Source Synchronization](#solution-source-synchronization).

## Repository Organization

Follow the target structure in the implementation plan. Use these ownership boundaries:

- `docs/` - architecture, specifications, traceability, security, build, and demo guidance.
- `docs/planning/` - approved plans and work breakdowns.
- `docs/requirements/` - requirement catalogs and traceability material.
- `docs/requirements/source/` - immutable source extracts.
- `schema/` - machine-readable Dataverse definitions.
- `scripts/` - repeatable provisioning, import, validation, and teardown automation.
- `data/` - fictional seed data aligned exactly with the schema.
- `agents/` - deployable agent instructions, topics, knowledge definitions, and handoff contracts.
- `flows/` - code-first Power Automate cloud flow definitions and metadata, deployed through the
  Dataverse API. See [Cloud Flow Generation](#cloud-flow-generation).
- `solutions/SRMAgentDemo/` - unmanaged solution source exported from DemoPRE and unpacked with PAC.
  Treat it as generated; change it only through the synchronization workflow.

Place generated or temporary local output outside tracked source paths. Never commit credentials,
environment-specific tokens, exports containing real data, or tool caches.

## Naming and Authoring Conventions

- Use kebab-case for directories and documentation file names.
- Use ordered numeric prefixes for the planned document sequence where ordering adds value.
- Use logical names beginning with `mag_` for Dataverse tables, columns, relationships, and choices.
- Give agent folders stable role-based names rather than display-name abbreviations.
- Keep identifiers consistent across documentation, schemas, scripts, seed data, and agent actions.
- Use UTF-8 Markdown, concise headings, tables for structured specifications, and Mermaid only when
  it improves architectural clarity.
- Separate confirmed requirements from assumptions, recommendations, and unresolved decisions.
- Prefer configuration and reference data over hard-coded business rules.

## Required Work Pattern

For each implementation task:

1. Identify the relevant plan item and source slides.
2. Inspect existing specifications and artifacts before making changes.
3. Define or update requirement traceability for the capability.
4. Implement the smallest complete vertical slice, including directly related documentation.
5. Validate internal consistency across all affected artifacts.
6. Report what was completed, what was validated, and any unresolved decisions.

Do not mark a work item complete merely because documentation exists. A deliverable is complete only
when its required artifacts are present, mutually consistent, and validated at the appropriate
level.

## Traceability

Every derived specification should identify:

- source slide or slide range;
- capability or requirement ID;
- implementing artifact;
- verification method or acceptance evidence;
- status and any open decision.

Maintain bidirectional traceability: requirements must point to implementation artifacts, and
implementation specifications must cite their requirement IDs. Follow the conventions in
`docs/requirements/README.md`.

## Validation Expectations

Choose validation appropriate to the artifact:

- Markdown: check links, headings, terminology, requirement coverage, and contradictions.
- JSON: parse it and validate it against any repository schema.
- PowerShell: parse it, run static analysis when available, and test safe paths without targeting a
  live environment.
- CSV: verify headers, types, foreign keys, choice values, encoding, and branch-coverage scenarios.
- Dataverse definitions: verify logical-name consistency, relationships, required fields, and
  publisher prefix.
- Agent definitions: verify tool contracts, inputs and outputs, handoffs, grounding boundaries,
  audit behavior, human approval gates, and failure paths.
- End-to-end specifications: verify every source capability is represented in the traceability map.

Use targeted checks while authoring, then run the repository-wide validation defined by the plan
before declaring the complete solution ready.

## Solution Source Synchronization

After every successful deployment or live change to `SRMAgentDemo` in DemoPRE, keep the repository
in sync with the environment. This applies to changes made by scripts, the Web API, MCP tools, PAC,
or maker portals, including tables, columns, relationships, keys, forms, views, BPFs, apps, flows,
security roles, and Copilot Studio components.

1. Confirm that the deployment and its post-deployment validation succeeded. Never pull after a
   failed or partial deployment; report the failure instead.
2. Determine whether `solutions/SRMAgentDemo/` already represents the deployed state:
   - If the folder does not exist, or any deployed component is not represented in it, pull.
   - If the deployment was made directly in DemoPRE, not by packing and importing the current local
     folder, pull.
   - If the deployment imported a package packed from the current, unmodified local folder, the
     source is already in sync; do not pull merely to create churn.
3. Before pulling, confirm the active PAC profile targets DemoPRE
   (`https://org5b55c88b.crm.dynamics.com/`), and ensure there are no uncommitted edits in
   `solutions/SRMAgentDemo/` that would be overwritten. If there are, stop and ask the user.
4. Export the unmanaged solution to a temporary location outside tracked source paths or to
   `solutions/SRMAgentDemo.zip`, which is ignored by Git:

   ```powershell
   pac solution export --name SRMAgentDemo --path .\solutions\SRMAgentDemo.zip --managed false --environment https://org5b55c88b.crm.dynamics.com
   ```

5. As a separate command, unpack it into the source folder:

   ```powershell
   pac solution unpack --zipfile .\solutions\SRMAgentDemo.zip --folder .\solutions\SRMAgentDemo --packagetype Unmanaged --allowDelete true
   ```

6. Verify the unpacked folder contains the expected deployed components, such as every `mag_` table
   under `Entities/`, each table's `DemoKey` alternate key (`<EntityKey>`), and
   `Other/Solution.xml` with publisher prefix `mag`. Then delete the ZIP.
7. Review the diff for unexpected components, environment-specific values, credentials, or real
   data. Remove nothing silently; report anything suspicious before committing.
8. Report the pull in the task summary. Commit the unpacked source only when the user has asked for
   commits.

Unpacked source is the exported record of deployed metadata; `schema/`, `data/`, and `scripts/`
remain the design and provisioning sources. Keep both consistent. If they disagree, fix the source
artifact and redeploy rather than editing the unpacked XML by hand.

## Cloud Flow Generation

Generate every flow for this project as a Copilot Studio **agent flow**, code-first through the
Dataverse API (research option 3: "Dataverse API/code-first provisioning"). Do not build flows in
the maker portal, hand-author solution source for them, or derive them from a template solution tree
unless the user approves a different approach.

### Source layout

Each flow lives in `flows/<flow-name>/` (kebab-case, role-based name) with:

- `flow.json` - metadata: display name, description, stable `workflowid` GUID (generated once and
  never changed), requirement IDs, owning agent or process step, trigger summary, and the connection
  references and environment variables the flow uses.
- `definition.json` - the flow definition (`definition`) and its `connectionReferences` map, as
  stored in the `clientdata` payload.

Connection references and environment variables are declared once in `flows/connection-references.json`
and `flows/environment-variables.json`, using `mag_` schema names.

### Deployment rules

1. Deploy with a repeatable script in `scripts/`, never ad hoc calls. The script must:
   - create or update the flow as a `workflow` record with `category = 5` (modern flow),
     `modernflowtype = 1` (CopilotStudioFlow, i.e. an agent flow; use `0` only for a plain Power
     Automate cloud flow the user explicitly approves), `type = 1`, `primaryentity = none`, the
     stable `workflowid`, and `clientdata` set to the string-encoded JSON
     `{"properties": {"connectionReferences": ..., "definition": ...}, "schemaVersion": "1.0.0.0"}`;
   - create or update it inside `SRMAgentDemo` (for example with the `MSCRM.SolutionUniqueName`
     header), and verify the resulting `solutioncomponent` membership;
   - create connection references (`connectionreference`) and environment variable definitions
     before the flows that use them, and add them to `SRMAgentDemo`;
   - be idempotent: rerunning updates existing records by `workflowid` rather than duplicating them.
2. Keep flows solution-aware and use connection references only. Never embed connections,
   credentials, tokens, tenant-specific IDs, or personal connection bindings in flow source.
3. Put environment-specific values (URLs, record IDs, email addresses, thresholds) in environment
   variables, not in flow definitions.
4. Prefer the Dataverse connector (`shared_commondataserviceforapps`) so the demo stays
   self-contained. External systems remain Dataverse-seeded mocks. Any other connector requires an
   explicit user decision.
5. Validate before deploying: parse all JSON, check every `connectionReferences` entry maps to a
   declared connection reference, every referenced table and column exists in `schema/`, and every
   environment variable is declared.
6. Create flows in draft (`statecode = 0`). Binding connections in DemoPRE is a manual, user-owned
   step; activate a flow (`statecode = 1`) only after its connection references are bound, and
   report which flows remain inactive and why.
7. Flows that make consequential changes, such as rating conversions, synchronization, or archival,
   must write to `mag_ReviewAuditTrail` and must not set the final financial rating.
8. After a successful deployment, run [Solution Source Synchronization](#solution-source-synchronization).
   The exported flow source is a generated record; `flows/` remains the authoring source.

### Flow type and source format (verified in DemoPRE, 2026-09-28)

- **Agent flows are the flow type for this project.** In Dataverse they are ordinary `workflow`
  records with `category = 5` and `modernflowtype = 1` (`CopilotStudioFlow`); `0` is
  `PowerAutomateFlow` and `2` is `M365CopilotAgentFlow`. `clientdata` holds the same JSON
  definition and `connectionReferences` map as a Power Automate cloud flow, so code-first
  provisioning through the `workflow` table applies unchanged. Agent flows run on Copilot Studio
  capacity, and only flows with the **When an agent calls the flow** trigger can be added to an
  agent as a tool.
- **Agent flows are not YAML.** With PAC CLI 2.10.1, `pac solution export`/`unpack` and
  `pac solution clone` both produce the classic XML layout. Each agent flow is exported losslessly
  as `Workflows/<Name>-<WORKFLOWID>.json` (the flow definition) plus a `.json.data.xml` metadata file
  containing `<Category>5</Category>` and `<ModernFlowType>1</ModernFlowType>`. The YAML
  source-control layout (`modernflows/`) is only produced by native Dataverse Git integration; do
  not switch the sync format without a user decision.
- **Copilot Studio Workflows (GitHub Copilot harness) are out of scope.** Microsoft documentation
  does not describe how these newer Workflows are stored or packaged, and none exist in DemoPRE to
  inspect. Do not generate them or assume they share the agent-flow storage; ask the user before
  using them.

## Change Management

- Keep changes focused; do not reformat unrelated files.
- Update dependent documentation when an approved design changes.
- Preserve historical source material and record why derived decisions changed.
- Surface blockers and ambiguity explicitly rather than hiding them behind defaults.
- Never claim deployment, execution, or validation that was not actually performed.
