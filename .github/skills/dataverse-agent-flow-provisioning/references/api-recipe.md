# Dataverse workflow API recipe

## Stored representation

This is a structural example, not a runnable flow definition. Replace placeholders
using approved project metadata and supply a complete, validated definition.
Sending this example unchanged is not a deployment step.

```json
{
  "name": "<approved display name>",
  "description": "<purpose and requirement IDs>",
  "workflowid": "<stable workflow GUID>",
  "category": 5,
  "modernflowtype": 1,
  "type": 1,
  "primaryentity": "none",
  "statecode": 0,
  "statuscode": 1,
  "clientdata": "<JSON-encoded string of the inner document below>"
}
```

The value of `clientdata` is a string encoding this inner structure, not an object
assigned directly to the outer payload:

```json
{
  "properties": {
    "connectionReferences": {
      "shared_commondataserviceforapps": {
        "runtimeSource": "embedded",
        "connection": {
          "connectionReferenceLogicalName": "<prefix>_Dataverse"
        },
        "api": {
          "name": "shared_commondataserviceforapps"
        }
      }
    },
    "definition": {
      "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
      "contentVersion": "1.0.0.0",
      "parameters": {},
      "triggers": {},
      "actions": {}
    }
  },
  "schemaVersion": "1.0.0.0"
}
```

In Python, construct the inner document and use `json.dumps(inner)` once when
assigning `clientdata`; then let the HTTP client serialize the outer payload.

## Request sequence

Use the authenticated Dataverse Web API for the approved environment:

| Purpose | Method and relative API path |
|---|---|
| Find existing flow | `GET /api/data/v9.2/workflows(<workflow-guid>)` |
| Create absent flow | `POST /api/data/v9.2/workflows` |
| Update existing flow | `PATCH /api/data/v9.2/workflows(<workflow-guid>)` |
| Deactivate before an approved update | PATCH with `statecode: 0`, `statuscode: 1` |
| Activate after approved binding | PATCH with `statecode: 1`, `statuscode: 2` |

Distinguish a genuine not-found response from authentication, permission, and
network failures before creating a record. Use:

```text
Content-Type: application/json
Accept: application/json
OData-Version: 4.0
OData-MaxVersion: 4.0
MSCRM.SolutionUniqueName: <approved solution unique name>
```

Authentication comes from the approved managed tool, never a token pasted into
source. Inspect current `dataverse api request --help` before composing CLI calls.
The SRM implementation passes a temporary body file and explicit environment,
method, path, and solution header to that command, deleting the body file afterward.

Workflow solution components use component type `29`. Query the intended solution
and its `solutioncomponents`, checking the workflow GUID against `objectid`.
Similarly verify dependency membership, rather than assuming a header alone is
proof. Reuse an existing connection reference without overwriting its user binding.

## Comparison and retries

The designer may remove empty `runAfter` objects, add descriptions, and copy
environment-variable values into parameter defaults. The SRM deployment helper
normalizes those observed changes before comparing definitions, avoiding repeated
updates that invalidate the designer-save step.

Do not generalize normalization into ignoring all defaults or metadata. Confirm
which differences are non-behavioral for the current project; preserve meaningful
changes and review source/environment disagreements explicitly.

Stable workflow IDs prevent duplicate provisioning. They do not automatically
make the business actions inside a flow idempotent.

## Solution synchronization

After approved successful deployment and metadata validation, with a matching PAC
profile and no generated-source edits at risk, run export and unpack as separate
commands. Substitute approved values; do not guess an environment.

```powershell
pac solution export --name <solution> --path <temporary-zip> --managed false --environment <approved-url>
```

```powershell
pac solution unpack --zipfile <temporary-zip> --folder <generated-source-folder> --packagetype Unmanaged --allowDelete true
```

The SRM PAC 2.10.1 export produced classic `Workflows/*.json` definitions and
`.json.data.xml` metadata with Category 5 and ModernFlowType 1. Native Dataverse
Git integration's `modernflows/` layout is different; do not assume PAC export
will produce it or change the project's format without approval.

## Historical provenance

The following paths are relative to the SRM repository root. They document the
learning; they are not dependencies bundled in this portable skill.

| Evidence | Repository artifact |
|---|---|
| Authoring and synchronization rules | `AGENTS.md`, Cloud Flow Generation and Solution Source Synchronization |
| Repeatable deployment | `scripts/08-deploy-flows.py` |
| Stage 1 live five-branch test and designer-save discovery | `docs/06-agent-flows-and-actions.md` |
| Stage 2 readiness and pending tests | `docs/07-stage-2-coface-and-collection.md` |
| Document-flow JSON generation | `scripts/10-generate-stage2-document-flows.py` |
| Separate orchestrator tool association | `scripts/15-wire-analysis-draft-agent-tool.py` |

Implementation chronology:

- `9e553dd`, September 28, 2026: adopted code-first Dataverse provisioning.
- `446842c`, October 2: four Stage 1 flows, deployment, smoke tests, solution sync.
- `e0560da`, October 2: two Coface flows.
- `126fc46`, October 5: three document-collection flows.
- `a440319`, October 5: analysis-draft saving and agent-tool integration.

These commits demonstrate the historical mechanism, not present-day runtime
health. Later demo draft-save calls encountered HTTP 502 polling failures.

## Microsoft Copilot Cowork packaging

Microsoft documents skill upload under **Customize > Skills > Add > Upload skill**.
A ZIP must have `SKILL.md` at its root, with any companion files alongside it;
do not wrap the entire archive in an extra parent folder.

Both `name` and `description` are required in YAML frontmatter. This package uses
only those portable fields and contains no credentials or deployment script.
Uploading it teaches the workflow; it does not install CLIs, authenticate an
environment, grant permissions, or create a flow.

Source: [Customize Copilot Cowork](https://learn.microsoft.com/en-us/copilot/cowork/cowork-customize),
checked November 4, 2026. Runtime and tenant capabilities may differ.
