# SRM MCP supplier dashboard

## Scope and traceability

This user-approved extension adds a read-only MCP server and MCP App to the SRM
Orchestrator, without replacing the model-driven app or changing the seven-agent topology.
Only fictional seeded suppliers `SUP-001` through `SUP-012` are supported.

| Requirement | Source | Implementation and verification |
|---|---|---|
| `SRM-OPS-001` | Slides 17-19 | [Dashboard loader](../agents/srm-orchestrator/mcp-server/dashboard.py): spend gating, company profile, stored indicators, annual revenue trend, confirmed review history, adverse-event evidence. [Hosted smoke test](../scripts/17-smoke-test-srm-mcp.py) verifies SUP-012 / REQ-2026-012. |
| `SRM-FIN-001` | Slides 8, 11 | Existing working-paper metrics are displayed, not rescored. [Focused tests](../agents/srm-orchestrator/mcp-server/test_dashboard.py) validate column and choice alignment with `schema/`. |
| `SRM-GOV-001`, `SRM-GOV-002` | Slide 1; slide 19; approved plan | Final request rating requires the stored human-confirmation flag. AI preliminary and supplier-master ratings remain separate. Entra role gating withholds sensitive data at the server, not merely in CSS. |

This slice does **not** implement monthly generation, external monitoring, PDF export/archival,
new rating calculations, or approval/synchronization writes. It reads existing Dataverse records.
Stored final remarks are labelled as such; their equality with a closing email is not inferred.

## Architecture

```text
SRM Orchestrator / MCP Apps host
  -> authenticated Streamable HTTP /mcp
  -> Entra signature, issuer, audience, expiry and role validation
  -> user-assigned managed identity
  -> GET-only Dataverse Web API, DemoPRE, seven allowlisted SRM tables
  -> structured tool result + ui://srm/supplier-risk-dashboard.html
```

- [Server](../agents/srm-orchestrator/mcp-server/server.py):
  `get_supplier_risk_dashboard(supplier_code, request_ref?)`.
- Tool metadata declares `_meta.ui.resourceUri`; the HTML resource uses
  `text/html;profile=mcp-app`, with empty external-network/resource CSP allowlists.
- [UI](../agents/srm-orchestrator/mcp-server/ui/) uses the official MCP Apps SDK.
  Refresh calls the same MCP tool through the host. The iframe receives no Dataverse
  credentials and does not fetch Dataverse directly.
- Clawpilot light/dark variables are used throughout. Host theme takes precedence,
  then an explicit `scoutTheme=light|dark`, then OS preference. Theme changes are observed.
- Traffic lights include text labels. Missing/unconfirmed ratings are neutral, never Green.
  Stale Coface assessments are explicitly historical; the 18-month window comes from slide 6.
  No invented metric thresholds or composite ratings are used.

The user approved GET-only Web API reads instead of SDK metadata discovery. This removes the
need for schema-metadata privileges and keeps the application's Dataverse role limited to
seven table-read privileges. Authentication still uses `azure-identity`, not a bespoke token flow.
Tables, columns, entity sets, and choices were checked against source and live DemoPRE reads.
Unexpected redirects, partial pages, invalid choices, missing suppliers, and failed reads
produce explicit errors rather than a successful-looking fallback dashboard.

## Deployment

Endpoint:
`https://srm-risk-mcp.wittyglacier-6d770dc4.westeurope.azurecontainerapps.io/mcp`

The new `srm-risk-mcp` Container App uses the existing `mcp` environment and registry in
resource group `mcpservers`. `aschi-weather-mcp` is unchanged.

[16-deploy-srm-mcp.ps1](../scripts/16-deploy-srm-mcp.ps1) has separate `Security` and `Deploy`
phases. It is deliberately restricted to the user-approved subscription/resource group.
Deployment state must be kept outside tracked source. Example, after approval:

```powershell
.\scripts\16-deploy-srm-mcp.ps1 -Phase Security -StatePath C:\temp\srm-mcp-deployment.json
.\scripts\16-deploy-srm-mcp.ps1 -Phase Deploy -StatePath C:\temp\srm-mcp-deployment.json
python .\scripts\17-smoke-test-srm-mcp.py --deployment-state C:\temp\srm-mcp-deployment.json
```

Builds use a source-only staging directory: Windows `node_modules`, caches, tokens and
local credentials are never copied into the Linux image. A successful existing timestamp
image can be resumed with `-ExistingImageTag` if local build-log streaming was interrupted.
The public `/healthz` route contains no business data. `/mcp` requires Entra authorization.
The container runs as a non-root user with one replica for this demo.

### Security

The managed identity's application user has exactly one Dataverse role,
**SRM MCP Dashboard Reader**, with Global Read on:

`mag_supplier`, `mag_financialreviewrequest`, `mag_financialworkingpaper`,
`mag_cofacecreditrecord`, `mag_supplieronepagesummary`, `mag_adversenewsevent`,
`mag_nonfinancialriskitem`.

No create/write/delete/approval privileges are granted. The deployment verifies the full
privilege set, removing only identified defaults on the role owned by this deployment.
Unexpected pre-existing privileges cause a failure, not silent removal.

The separate Entra API registration exposes `SRM.Read` and requires `SRM.Reader`.
Sensitive narratives, aggregate free-text summaries, adverse events, and qualitative risk
details additionally require `SRM.LegalReader`. A caller cannot request that role through
tool arguments. Restricted callers never select those columns/tables. The initial approved
operator has both roles; other users must be explicitly assigned appropriate roles.

The server uses a service identity, **not** delegated Dataverse row-level access. Entra
roles gate the fictional demo dataset; do not use this deployment for real supplier data
without designing per-user/record authorization.

### Copilot Studio connection

Use the existing SRM Orchestrator in DemoPRE. In **Build -> Tools -> Add tool -> MCP**,
add the endpoint above as **SRM Supplier Risk Dashboard**.

Use manually configured Entra OAuth:

| Setting | Value |
|---|---|
| Client | `SRM MCP Copilot Client` registration created by the security phase |
| Authorization URL | `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize` |
| Token / refresh URL | `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token` |
| Scope | `api://<api-app-id>/SRM.Read` (plus `offline_access` if requested by the host) |
| Client secret | Create for the client registration and enter only in the protected connection; never in source |
| Redirect URI | Copy the actual URI shown by Copilot Studio and register it on the client app; do not guess it |

The deployment state contains non-secret tenant/application IDs. For the verified deployment:

- Tenant: `bfc167e5-797b-4253-af74-4a32b0533996`
- OAuth client ID: `02c513a9-5ab7-41f3-8ebe-637392bf9d4f`
- API ID: `8a785013-4dc8-4ec3-ae20-cf1c892d2d0a`
- Scope: `api://8a785013-4dc8-4ec3-ae20-cf1c892d2d0a/SRM.Read`

Client secrets belong in
the OAuth connection's vault. Entra does not support dynamic client registration.
Save the cloud draft, then test in preview before publishing. UI labels can vary.

Suggested routing instruction:

> For a supplier risk dashboard, use `get_supplier_risk_dashboard`. For Lumen Forge
> Industrial Systems Ltd, pass `supplier_code="SUP-012"` and
> `request_ref="REQ-2026-012"`. Keep supplier-master, AI-preliminary, and human-final
> ratings separate. Never use the dashboard to approve or change a rating.

Microsoft currently documents MCP Apps support in **Copilot Studio preview chat** and
**Microsoft 365 Copilot**, not Teams or web chat:
[Copilot Studio MCP Apps](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agents-experience/mcp-apps).

## Validation evidence

Verified against the hosted endpoint on 2026-11-23:

- unauthenticated and invalid-token requests rejected with HTTP 401;
- official MCP client initialization, tool listing/call, and HTML resource read succeeded;
- Lumen Forge Industrial Systems Ltd (`SUP-012`), `REQ-2026-012`, four working-paper periods;
- supplier master **Red**, AI preliminary **Green**, **no confirmed final rating**;
- Coface **2/10 / High**, assessment 2024-08-19, explicitly **not current**;
- sensitive data returned only to the approved LegalReader caller.

Local validation: TypeScript typecheck/bundle, eight focused Python tests, and five
UI tests passed. UI tests verify the actual production HTML's script syntax, real SDK
initialization and host-delivered tool results, traffic light and human-rating distinction,
light/dark host-theme changes, safe text rendering, exact refresh arguments, and stale-data
hiding on errors. The hosted smoke test's `--expected-ui` option compares the served HTML
byte-for-byte with that tested production artifact.
The MCP resource includes the required MIME type, UI metadata, and empty network CSP.
Do not treat this server-level verification as proof that the Orchestrator connection
or its light/dark preview has been completed; those need separate host-side verification.

The user configured the Orchestrator OAuth connection and confirmed successful tool
calls in Copilot Studio preview. After the startup fix below was deployed, the user
also confirmed that the graphical dashboard renders in Preview (2026-11-23).
No client secret was generated by repository scripts.

### Rendering startup regression

The initial widget displayed **Couldn't start the app** although the data tool succeeded.
The HTML bundler passed the JavaScript bundle directly as a string-replacement argument.
JavaScript `$&`, dollar-backtick, and dollar-apostrophe sequences were interpreted as
replacement patterns, injecting copies of the HTML template and breaking script syntax.
The original artifact contained 19 script blocks and could not initialize.

The bundler now inserts the JavaScript through a replacement callback, preserving those
characters literally. The corrected artifact has two executable script blocks (theme
detection and the MCP App bundle). Regression tests parse the final HTML and complete an
initialization/tool-result exchange using the real bundled SDK, rather than only testing
the application against a mocked SDK. For a cached failed widget, reload Preview and
invoke the dashboard again; no OAuth or redirect-URI changes are needed for this fix.

The hosted MCP smoke test verified that the deployed HTML exactly matches the tested
686,115-byte artifact, while authenticated SUP-012 reads and unauthenticated-request
rejection continue to work. Only the external Container App was redeployed for this fix;
no Dataverse metadata, agent settings, permissions, or ratings were changed.

After a successful DemoPRE metadata change, export/unpack `SRMAgentDemo` as required by
[AGENTS.md](../AGENTS.md#solution-source-synchronization). Asynchronous PAC export is a
supported alternative when synchronous export fails; never unpack a failed export.

The verified role deployment was exported and unpacked on 2026-11-23. The export contains
all 17 `mag_` tables with DemoKey keys, publisher prefix `mag`, and the exact seven-read
dashboard role. It also captures pre-existing cloud drift: newer platform dependency
versions, additional Orchestrator configuration (including its Dataverse query instruction
and conversation starters), and an environment-specific demo mailbox default. These were
not changed by the MCP deployment and were not silently removed from generated source.
