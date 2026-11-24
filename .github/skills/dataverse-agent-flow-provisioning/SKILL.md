---
name: dataverse-agent-flow-provisioning
description: "Create, update, and troubleshoot solution-aware Power Automate cloud flows and Copilot Studio agent flows code-first through the Dataverse Web API. Use for workflow JSON, clientdata, connection references, repeatable deployment, agent-tool wiring, trigger registration, and solution export/unpack."
---

# Code-first Dataverse agent flows

## Purpose and boundaries

Turn source-controlled JSON definitions into solution-aware Copilot Studio agent flows
by creating or updating Dataverse `workflow` records. Do not mistake generating JSON,
creating a flow, activating it, linking it to an agent, and proving a successful run
for the same milestone.

This workflow was verified in the SRM demo repository. It does not rely on a built-in
Cowork Power Automate authoring tool. Tool availability and environment permissions
must be checked for each task.

Read [the API recipe and historical evidence](./references/api-recipe.md) when
implementing deployment or diagnosing the stored representation.

## 1. Establish scope and authorization

- Read the workspace's agent instructions, approved requirements, and existing flow
  sources and deployment helpers before generating or modifying artifacts.
- Confirm the target environment URL, unmanaged solution unique name, publisher
  prefix, flow purpose, trigger, inputs, outputs, and acceptance criteria.
- Ask for explicit approval before contacting or changing an environment. A request
  to explain, design, or package a skill is not deployment authorization.
- Separate permission to create or update flows from permission to activate them,
  send messages, change business records, or publish an agent.
- Do not choose an environment, connector, rating policy, retention period, or
  business threshold on the user's behalf.
- Keep credentials, connection bindings, real business data, and tokens out of
  source, archives, logs, and conversation output.

### SRM repository constraints

When working in `aschauera/srm-agent-demo`, follow the current `AGENTS.md`:

- Target only explicitly authorized DemoPRE operations and solution `SRMAgentDemo`,
  using publisher prefix `mag`.
- Keep integrations mocked in Dataverse and use fictional data.
- Write consequential activity to the review audit trail.
- Preserve human accountability for new final financial ratings; do not generate
  an automated final-rating decision.
- Treat `flows/` as authoring source and unpacked solution files as generated output.

These are project constraints, not defaults to apply to unrelated projects.

## 2. Check available execution capabilities

1. Discover the tools actually available in Cowork or the current host.
2. Prefer an existing, approved deployment script and managed authentication.
   The verified implementation uses Python orchestration with Dataverse Web API
   requests; its current transport is authenticated `dataverse api request`.
3. If terminal access is available, check the installed CLI help and active profile.
   Verify that both Dataverse and PAC commands target the approved URL before use.
4. If only a connector or MCP tool is available, verify that it supports the required
   workflow operations, exact payload, and solution header. Do not assume ordinary
   business-record CRUD tools can provision flows.
5. If Cowork lacks the required tools, produce the source and deployment handoff.
   State the missing capability and mark the result **not deployed**. Do not invent
   a tool, bypass authentication, or claim successful execution.

Use the platform's managed sign-in. Never read token caches or implement a custom
token-acquisition flow. Do not assume Cowork can use a developer machine's profiles.

## 3. Author durable source

Use an existing project layout, or this structure when none exists:

```text
flows/
  connection-references.json
  environment-variables.json
  <flow-name>/
    flow.json
    definition.json
scripts/
  <repeatable-deployment-script>
```

- `flow.json`: display name, description, stable `workflowId`, requirement IDs,
  owner/process, trigger summary, connection references, and environment variables.
- `definition.json`: `definition` and `connectionReferences`.
- Generate a workflow GUID once and retain it across updates and retries.
- Declare dependencies centrally; keep personal connection IDs and environment
  values out of the portable definition.
- Use environment variables for URLs, mailboxes, record IDs, and configurable policy.
- Implement failure paths, auditable writes, and business approval gates.
- Prefer Dataverse for self-contained demos; get approval for additional connectors.

For an agent-callable flow, use the platform's **When an agent calls the flow**
contract: a `Request` trigger with `kind: Skills`, typed inputs, and a response to
the caller. A Dataverse event trigger or recurrence trigger does not become an
agent-callable tool merely because the workflow is an agent flow.

## 4. Validate before any deployment

- Parse every source JSON file.
- Check unique, valid workflow GUIDs and consistent names.
- Resolve each connector reference and environment-variable reference.
- Verify every referenced table, column, relationship, and connector operation
  against the actual schema or an authoritative metadata source.
- Check action names, expressions, dependencies, trigger filters, required inputs,
  response shapes, error paths, and audit writes.
- Enforce safety-critical input checks before writes. Do not rely solely on schema
  annotations such as `maxLength` being enforced by a request trigger.
- Run the repository validator's offline mode if available.
- Present planned changes and obtain approval before making live changes.

## 5. Deploy through a repeatable script

1. Verify the approved environment profile and solution.
2. Ensure environment-variable definitions and connection references exist in the
   solution before deploying dependent flows.
3. Keep environment-variable current values separate from portable definitions.
4. Query `workflows` by stable GUID. Create when absent; compare and update when
   present. Do not create duplicates on retries.
5. Set the creation fields:

   ```text
   category       = 5     modern cloud flow
   modernflowtype = 1     CopilotStudioFlow
   type           = 1
   primaryentity  = "none"
   statecode      = 0     draft/inactive
   statuscode     = 1
   ```

6. Store `clientdata` as a JSON-encoded **string**, containing `properties` with
   `definition` and `connectionReferences`, plus `schemaVersion: "1.0.0.0"`.
7. Use the `MSCRM.SolutionUniqueName` header and verify `solutioncomponent`
   membership, rather than assuming creation put everything in the solution.
8. For changed active flows, explicitly report and authorize the interruption:
   deactivate before updating, and reactivate only when approved and ready.
9. If a call times out or returns an ambiguous error, read back state before
   retrying. Do not treat either a timeout or an HTTP acceptance as proof of
   completed provisioning.

Use `modernflowtype = 0` only for an explicitly requested ordinary Power Automate
flow. Do not confuse these flows with newer Copilot Studio harness Workflows.

## 6. Bind, activate, and connect agents separately

- Ask the user to bind connection references through the supported platform UI.
  Do not embed personal connection bindings in source.
- Activate only after dependencies are bound and the user has authorized activation.
- For Dataverse `SubscribeWebhookTrigger` flows, account for the observed SRM
  behavior: a Web API-created or updated flow showed On but did not fire until a
  user opened and saved it once in the Power Automate designer. This is a
  historically observed requirement, not a guarantee about all platform versions.
- Verify a real trigger event and run; an On label is insufficient evidence.
- Adding a flow as an agent tool is another operation. Use supported Copilot Studio
  tooling; verify tool input/output mappings and the workflow association.
- Obtain separate authorization to publish an agent when publishing is required.

## 7. Test outcomes, then synchronize source

- Exercise the intended invocation channel, not just record existence.
- Cover happy paths, alternative branches, missing data, invalid input, failures,
  retry behavior, audit records, and protected fields.
- For file operations, read bytes back; a document row alone does not prove upload.
- For errors such as HTTP 502 polling failures, distinguish an invocation/polling
  error from the underlying business result. Inspect run history and persisted
  records without assuming either success or rollback.
- Use stable business revision/idempotency keys when the operation supports them.
  Retry consequential writes only with authorization and verified retry semantics.
- Report exactly which tests ran and which remain pending.
- After successful deployment and metadata validation, export the unmanaged
  solution and unpack it with PAC into the approved generated-source folder.
  Check for local edits before overwriting anything.
- If deployment is partial or failed, report the failure and follow the project's
  recovery policy; do not label a source pull as a successful deployment.
- Inspect exported files for unexpected components or sensitive values. Never
  hand-edit exported solution metadata to manufacture deployment evidence.
- Commit or push only when requested.

## Completion report

Report separately:

| Milestone | Required evidence |
|---|---|
| Authored | Source paths, requirement coverage, stable IDs |
| Validated | Exact offline checks and results |
| Deployed | Target, workflow read-back, solution membership |
| Activated | Bound connections and active state |
| Agent-connected | Tool association and invocation contract |
| Runtime-tested | Actual runs and persisted outcomes |
| Synchronized | Export/unpack result and reviewed diff |

Use **not performed**, **blocked**, or **pending** where appropriate. Never compress
these distinct states into an unsupported claim that the flow "works."
