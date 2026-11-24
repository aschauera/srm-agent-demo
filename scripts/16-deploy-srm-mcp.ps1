<#
Provision and deploy the read-only SRM MCP App in the approved demo subscription.
SRM-OPS-001, SRM-GOV-001/002. Requires prior approval of cloud/security changes.
Run Security first, validate it, then Deploy. Export/unpack SRMAgentDemo separately
after successful changes; never hand-author generated solution source.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Security', 'Deploy')][string]$Phase,
    [Parameter(Mandatory)][string]$StatePath,
    [Parameter(Mandatory)][string]$Subscription,
    [string]$ResourceGroup = 'mcpservers',
    [string]$AppName = 'srm-risk-mcp',
    [string]$EnvironmentName = 'mcp',
    [Parameter(Mandatory)][string]$RegistryName,
    [string]$OwnedRoleId,
    [string]$ReaderRoleId,
    [string]$LegalRoleId,
    [string]$ScopeId,
    [string]$AzureCliClientId,
    [string]$ExistingImageTag
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Source = Join-Path $Root 'agents\srm-orchestrator\mcp-server'
$Environment = 'https://org5b55c88b.crm.dynamics.com'
$RoleName = 'SRM MCP Dashboard Reader'
$AzPython = Join-Path (Split-Path (Split-Path (Get-Command az).Source)) 'python.exe'
$Tables = @('Supplier', 'FinancialReviewRequest', 'FinancialWorkingPaper', 'CofaceCreditRecord',
    'SupplierOnePageSummary', 'AdverseNewsEvent', 'NonFinancialRiskItem')

function Invoke-Azure([string[]]$Arguments) {
    $text = & $AzPython -X utf8 -IBm azure.cli @Arguments --output json
    if ($LASTEXITCODE) { throw "Azure CLI failed: $($Arguments[0..1] -join ' ')" }
    if ($text) { return ($text -join "`n" | ConvertFrom-Json) }
}

function Invoke-Dataverse([string]$Path, [string]$Method = 'GET', $Body = $null) {
    $args = @('api', 'request', '--target', 'dataverse', '--environment', $Environment,
        '--path', $Path, '--method', $Method,
        '--header', 'MSCRM.SolutionUniqueName:SRMAgentDemo',
        '--context', 'app=dataverse-skills/1.16.1;skill=dv-security;agent=unknown')
    $bodyFile = Join-Path ([IO.Path]::GetTempPath()) ("srm-mcp-body-" + [guid]::NewGuid() + '.json')
    try {
        if ($null -ne $Body) {
            $Body | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $bodyFile -Encoding utf8
            $args += @('--body-file', $bodyFile)
        }
        $text = & dataverse @args
        if ($LASTEXITCODE) { throw "Dataverse $Method failed: $Path`n$($text -join "`n")" }
        if ($text) {
            $result = $text -join "`n" | ConvertFrom-Json
            if ($result.error) { throw "Dataverse $Method failed: $($result.error.message)" }
            return $result
        }
    } finally {
        if (Test-Path -LiteralPath $bodyFile) { Remove-Item -LiteralPath $bodyFile }
    }
}

function Invoke-Graph([string]$Path, [string]$Method = 'GET', $Body = $null) {
    $args = @('rest', '--url', "https://graph.microsoft.com/v1.0/$Path", '--method', $Method)
    $bodyFile = Join-Path ([IO.Path]::GetTempPath()) ("srm-mcp-graph-" + [guid]::NewGuid() + '.json')
    try {
        if ($null -ne $Body) {
            $Body | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $bodyFile -Encoding utf8
            $args += @('--body', "@$bodyFile", '--headers', 'Content-Type=application/json')
        }
        Invoke-Azure $args
    } finally {
        if (Test-Path -LiteralPath $bodyFile) { Remove-Item -LiteralPath $bodyFile }
    }
}

function Get-OrCreateApp([string]$Name) {
    $matches = @(Invoke-Azure @('ad', 'app', 'list', '--display-name', $Name) |
        Where-Object displayName -eq $Name)
    if ($matches.Count -gt 1) { throw "Ambiguous Entra registration: $Name" }
    if ($matches.Count -eq 1) { return $matches[0] }
    Invoke-Azure @('ad', 'app', 'create', '--display-name', $Name, '--sign-in-audience', 'AzureADMyOrg')
}

function Get-OrCreateServicePrincipal([string]$ApplicationId) {
    $found = Invoke-Graph "servicePrincipals?`$filter=appId eq '$ApplicationId'"
    if ($found.value.Count -gt 1) { throw 'Ambiguous service principal.' }
    if ($found.value.Count -eq 1) { return $found.value[0] }
    Invoke-Graph 'servicePrincipals' 'POST' @{appId = $ApplicationId}
}

if (-not $env:SRM_APPROVED_SUBSCRIPTION_ID -or $Subscription -ne $env:SRM_APPROVED_SUBSCRIPTION_ID -or
    -not $env:SRM_APPROVED_REGISTRY_NAME -or $RegistryName -ne $env:SRM_APPROVED_REGISTRY_NAME -or
    $ResourceGroup -ne 'mcpservers' -or $AppName -ne 'srm-risk-mcp' -or $EnvironmentName -ne 'mcp') {
    throw 'Refusing a target outside the explicitly approved demo scope.'
}
$StatePath = [IO.Path]::GetFullPath($StatePath)
if ($StatePath.StartsWith($Root, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Deployment state must be outside tracked source paths.'
}
$account = Invoke-Azure @('account', 'show', '--subscription', $Subscription)
$profile = & pac org who 2>&1 | Out-String
if ($profile -notmatch [regex]::Escape($Environment)) { throw 'Active PAC connection is not DemoPRE.' }

if ($Phase -eq 'Security') {
    foreach ($value in @($OwnedRoleId, $ReaderRoleId, $LegalRoleId, $ScopeId, $AzureCliClientId)) {
        $parsed = [guid]::Empty
        if (-not [guid]::TryParse($value, [ref]$parsed) -or $parsed -eq [guid]::Empty) {
            throw 'Security requires non-empty GUIDs for the owned role, API roles, scope, and Azure CLI client.'
        }
    }
    if (@($ReaderRoleId, $LegalRoleId, $ScopeId | Select-Object -Unique).Count -ne 3) {
        throw 'API role and scope IDs must be distinct.'
    }
    if (-not $env:SRM_APPROVED_AZURE_CLI_CLIENT_ID -or
        $AzureCliClientId -ne $env:SRM_APPROVED_AZURE_CLI_CLIENT_ID) {
        throw 'Azure CLI client ID does not match the independently approved ID.'
    }
    if (git --no-pager status --porcelain -- (Join-Path $Root 'solutions\SRMAgentDemo')) {
        throw 'Uncommitted solution source would prevent safe post-deployment synchronization.'
    }
    $identities = @(Invoke-Azure @('identity', 'list', '--resource-group', $ResourceGroup,
        '--subscription', $Subscription) | Where-Object name -eq $AppName)
    $identity = if ($identities.Count -eq 1) { $identities[0] } else {
        Invoke-Azure @('identity', 'create', '--name', $AppName, '--resource-group', $ResourceGroup,
            '--subscription', $Subscription, '--location', 'westeurope')
    }
    $roles = Invoke-Dataverse "/api/data/v9.2/roles?%24select=roleid,name&%24filter=name eq '$RoleName'"
    if ($roles.value.Count -gt 1) { throw 'Ambiguous Dataverse role.' }
    $units = Invoke-Dataverse '/api/data/v9.2/businessunits?%24select=businessunitid&%24filter=_parentbusinessunitid_value eq null'
    if ($units.value.Count -ne 1) { throw 'Expected one root business unit.' }
    $unitId = $units.value[0].businessunitid
    if ($roles.value.Count -eq 0) {
        $roleId = $OwnedRoleId
        Invoke-Dataverse '/api/data/v9.2/roles' 'POST' @{
            roleid = $roleId; name = $RoleName; 'businessunitid@odata.bind' = "/businessunits($unitId)"
        } | Out-Null
    } else {
        $roleId = $roles.value[0].roleid
        if ($roleId -ne $OwnedRoleId) { throw 'Existing role does not match the supplied owned role ID.' }
    }
    $privileges = Invoke-Dataverse '/api/data/v9.2/privileges?%24select=privilegeid,name&%24filter=startswith(name,%27prvReadmag_%27)'
    $expected = @($Tables | ForEach-Object { "prvReadmag_$_" })
    $selected = @($privileges.value | Where-Object name -in $expected)
    if ($selected.Count -ne $expected.Count) { throw 'Required read privileges are missing.' }
    $current = Invoke-Dataverse "/api/data/v9.2/RetrieveRolePrivilegesRole(RoleId=$roleId)"
    $unexpected = @($current.RolePrivileges | Where-Object {
        $_.PrivilegeId -notin $selected.privilegeid
    })
    $platformDefaults = @('prvReadSdkMessage', 'prvReadSdkMessageProcessingStep',
        'prvReadSdkMessageProcessingStepImage', 'prvReadPluginType', 'prvReadPluginAssembly',
        'prvReadSharePointDocument', 'prvReadSharePointData', 'prvWriteSharePointData',
        'prvCreateSharePointData', 'prvReadEntity')
    if ($unexpected.Count -and ($roleId -ne $OwnedRoleId -or @($unexpected |
        Where-Object PrivilegeName -notin $platformDefaults).Count)) {
        throw 'Existing role contains unexpected privileges; refusing to modify or grant it.'
    }
    if ($current.RolePrivileges.Count -ne $selected.Count -or @($current.RolePrivileges |
        Where-Object {
            $_.PrivilegeId -notin $selected.privilegeid -or
            $_.Depth -ne 'Global'
        }).Count) {
        Invoke-Dataverse "/api/data/v9.2/roles($roleId)/Microsoft.Dynamics.CRM.ReplacePrivilegesRole" 'POST' @{
            Privileges = @($selected | ForEach-Object { @{
                PrivilegeId = $_.privilegeid
                Depth = 'Global'
                BusinessUnitId = $unitId
            } })
        } | Out-Null
        $afterReplace = Invoke-Dataverse "/api/data/v9.2/RetrieveRolePrivilegesRole(RoleId=$roleId)"
        foreach ($privilege in @($afterReplace.RolePrivileges | Where-Object {
            $_.PrivilegeId -notin $selected.privilegeid
        })) {
            if ($roleId -ne $OwnedRoleId -or $privilege.PrivilegeName -notin $platformDefaults) {
                throw 'Unexpected privilege after replacement; refusing to remove it.'
            }
            Invoke-Dataverse "/api/data/v9.2/roles($roleId)/Microsoft.Dynamics.CRM.RemovePrivilegeRole" 'POST' @{
                Privilege = @{ '@odata.type' = 'Microsoft.Dynamics.CRM.privilege'; privilegeid = $privilege.PrivilegeId }
            } | Out-Null
        }
    }
    Invoke-Dataverse '/api/data/v9.2/AddSolutionComponent' 'POST' @{
        ComponentId = $roleId; ComponentType = 20; SolutionUniqueName = 'SRMAgentDemo'; AddRequiredComponents = $false
    } | Out-Null
    $assignment = & pac admin assign-user --user $identity.clientId --role $RoleName `
        --application-user --business-unit $unitId --environment $Environment 2>&1 | Out-String
    if ($assignment -match '(?im)^\s*(Error:|\[ERROR\])') { throw $assignment }
    $users = Invoke-Dataverse "/api/data/v9.2/systemusers?%24select=systemuserid&%24filter=applicationid eq $($identity.clientId)"
    if ($users.value.Count -ne 1) { throw 'Managed identity application user not found.' }
    $userId = $users.value[0].systemuserid
    $assigned = Invoke-Dataverse "/api/data/v9.2/systemusers($userId)/systemuserroles_association?%24select=roleid,name"
    if ($assigned.value.Count -ne 1 -or $assigned.value[0].roleid -ne $roleId) {
        throw 'Application user does not have exactly the intended read-only role.'
    }
    $verified = Invoke-Dataverse "/api/data/v9.2/RetrieveRolePrivilegesRole(RoleId=$roleId)"
    if ($verified.RolePrivileges.Count -ne $selected.Count -or @($verified.RolePrivileges |
        Where-Object {
            $_.PrivilegeId -notin $selected.privilegeid -or
            $_.Depth -ne 'Global'
        }).Count) {
        throw 'Read-only role verification failed.'
    }
    $api = Get-OrCreateApp 'SRM MCP Risk Dashboard API'
    $client = Get-OrCreateApp 'SRM MCP Copilot Client'
    foreach ($expected in @(
        @{value = 'SRM.Reader'; id = $ReaderRoleId; entries = @($api.appRoles)}
        @{value = 'SRM.LegalReader'; id = $LegalRoleId; entries = @($api.appRoles)}
        @{value = 'SRM.Read'; id = $ScopeId; entries = @($api.api.oauth2PermissionScopes)}
    )) {
        $existing = @($expected.entries | Where-Object value -eq $expected.value)
        if ($existing.Count -gt 1 -or ($existing.Count -eq 1 -and $existing[0].id -ne $expected.id)) {
            throw "Existing $($expected.value) ID does not match the supplied ID."
        }
    }
    Invoke-Graph "applications/$($api.id)" 'PATCH' @{
        identifierUris = @("api://$($api.appId)")
        api = @{
            requestedAccessTokenVersion = 2
            oauth2PermissionScopes = @(@{
                id = $ScopeId; value = 'SRM.Read'; type = 'Admin'; isEnabled = $true
                adminConsentDisplayName = 'Read fictional SRM dashboard'
                adminConsentDescription = 'Read SRM dashboard records; no write or approval permissions.'
            })
        }
        appRoles = @(
            @{id = $ReaderRoleId; value = 'SRM.Reader'; displayName = 'SRM Dashboard Reader'
              description = 'Read non-sensitive fictional SRM dashboard records.'
              allowedMemberTypes = @('User', 'Application'); isEnabled = $true}
            @{id = $LegalRoleId; value = 'SRM.LegalReader'; displayName = 'SRM Legal Reader'
              description = 'Read fictional sensitive narratives and adverse legal details.'
              allowedMemberTypes = @('User', 'Application'); isEnabled = $true}
        )
    } | Out-Null
    Invoke-Graph "applications/$($api.id)" 'PATCH' @{
        api = @{ preAuthorizedApplications = @(
            @{appId = $client.appId; delegatedPermissionIds = @($ScopeId)}
            @{appId = $AzureCliClientId; delegatedPermissionIds = @($ScopeId)}
        ) }
    } | Out-Null
    $apiSp = Get-OrCreateServicePrincipal $api.appId
    $clientSp = Get-OrCreateServicePrincipal $client.appId
    Invoke-Graph "servicePrincipals/$($apiSp.id)" 'PATCH' @{appRoleAssignmentRequired = $true} | Out-Null
    Invoke-Graph "applications/$($client.id)" 'PATCH' @{
        requiredResourceAccess = @(@{resourceAppId = $api.appId
            resourceAccess = @(@{id = $ScopeId; type = 'Scope'})})
    } | Out-Null
    $operator = Invoke-Azure @('ad', 'signed-in-user', 'show')
    $existingGrants = Invoke-Graph "servicePrincipals/$($apiSp.id)/appRoleAssignedTo"
    foreach ($appRole in @($ReaderRoleId, $LegalRoleId)) {
        if (-not @($existingGrants.value | Where-Object {
            $_.principalId -eq $operator.id -and $_.appRoleId -eq $appRole
        }).Count) {
            Invoke-Graph "servicePrincipals/$($apiSp.id)/appRoleAssignedTo" 'POST' @{
                principalId = $operator.id; resourceId = $apiSp.id; appRoleId = $appRole
            } | Out-Null
        }
    }
    $registry = Invoke-Azure @('acr', 'show', '--name', $RegistryName, '--resource-group', $ResourceGroup,
        '--subscription', $Subscription)
    $pull = Invoke-Azure @('role', 'assignment', 'list', '--assignee-object-id', $identity.principalId,
        '--scope', $registry.id)
    if (-not @($pull | Where-Object roleDefinitionName -eq 'AcrPull').Count) {
        Invoke-Azure @('role', 'assignment', 'create', '--assignee-object-id', $identity.principalId,
            '--assignee-principal-type', 'ServicePrincipal', '--role', 'AcrPull', '--scope', $registry.id) | Out-Null
    }
    $state = @{
        tenantId = $account.tenantId; subscription = $Subscription; resourceGroup = $ResourceGroup
        identityId = $identity.id; identityClientId = $identity.clientId
        apiAppId = $api.appId; apiObjectId = $api.id; apiPrincipalId = $apiSp.id
        clientAppId = $client.appId; clientObjectId = $client.id; clientPrincipalId = $clientSp.id
        roleId = $roleId; applicationUserId = $userId
    }
    if (Test-Path -LiteralPath $StatePath) {
        $previous = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
        foreach ($property in @('endpoint', 'image')) {
            if ($previous.$property) { $state[$property] = $previous.$property }
        }
    }
    $state | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding utf8
    Write-Host "Security provisioned and validated. Non-secret deployment state: $StatePath"
    return
}

$state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
if ($state.subscription -ne $Subscription -or $state.resourceGroup -ne $ResourceGroup) {
    throw 'Deployment state does not match approved target.'
}
Push-Location (Join-Path $Source 'ui')
try {
    & npm run build
    if ($LASTEXITCODE) { throw 'MCP UI build failed.' }
} finally { Pop-Location }
$imageTag = if ($ExistingImageTag) { $ExistingImageTag } else { Get-Date -Format 'yyyyMMddHHmmss' }
if ($imageTag -notmatch '^\d{14}$') { throw 'Expected a timestamp image tag.' }
if (-not $ExistingImageTag) {
$buildContext = Join-Path ([IO.Path]::GetTempPath()) ("srm-mcp-build-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path (Join-Path $buildContext 'ui') | Out-Null
try {
    foreach ($file in @('Dockerfile', 'requirements.txt', 'server.py', 'dashboard.py', '.dockerignore')) {
        Copy-Item -LiteralPath (Join-Path $Source $file) -Destination (Join-Path $buildContext $file) -Force
    }
    foreach ($file in @('package.json', 'package-lock.json', 'index.html', 'app.ts', 'build.mjs', 'tsconfig.json')) {
        Copy-Item -LiteralPath (Join-Path $Source "ui\$file") -Destination (Join-Path $buildContext "ui\$file")
    }
    $buildLog = & $AzPython -X utf8 -IBm azure.cli acr build --registry $RegistryName --subscription $Subscription `
        --image "$AppName`:$imageTag" --platform linux/amd64 $buildContext 2>&1
    if ($LASTEXITCODE) { throw ($buildLog | Out-String) }
} finally {
    Remove-Item -LiteralPath $buildContext -Recurse
}
}
$registry = Invoke-Azure @('acr', 'show', '--name', $RegistryName, '--subscription', $Subscription)
$managed = Invoke-Azure @('containerapp', 'env', 'show', '--name', $EnvironmentName,
    '--resource-group', $ResourceGroup, '--subscription', $Subscription)
$fqdn = "$AppName.$($managed.properties.defaultDomain)"
$image = "$($registry.loginServer)/$AppName`:$imageTag"
$apps = @(Invoke-Azure @('containerapp', 'list', '--resource-group', $ResourceGroup,
    '--subscription', $Subscription) | Where-Object name -eq $AppName)
$vars = @("DATAVERSE_URL=$Environment", "AZURE_CLIENT_ID=$($state.identityClientId)",
    "ENTRA_TENANT_ID=$($state.tenantId)", "ENTRA_API_CLIENT_ID=$($state.apiAppId)",
    "MCP_PUBLIC_URL=https://$fqdn/mcp")
if ($apps.Count -eq 0) {
    Invoke-Azure (@('containerapp', 'create', '--name', $AppName, '--resource-group', $ResourceGroup,
        '--subscription', $Subscription, '--environment', $managed.id, '--image', $image,
        '--user-assigned', $state.identityId, '--registry-server', $registry.loginServer,
        '--registry-identity', $state.identityId, '--ingress', 'external', '--target-port', '8000',
        '--transport', 'http', '--min-replicas', '1', '--max-replicas', '1', '--cpu', '0.5', '--memory', '1Gi',
        '--env-vars') + $vars) | Out-Null
} else {
    if ($apps.Count -ne 1 -or $apps[0].properties.environmentId -ne $managed.id) {
        throw 'Existing SRM app is ambiguous or in another managed environment.'
    }
    Invoke-Azure (@('containerapp', 'update', '--name', $AppName, '--resource-group', $ResourceGroup,
        '--subscription', $Subscription, '--image', $image, '--set-env-vars') + $vars) | Out-Null
}
$health = Invoke-RestMethod "https://$fqdn/healthz"
if ($health.service -ne 'srm-risk-mcp') { throw 'Deployed health check failed.' }
$metadata = Invoke-RestMethod "https://$fqdn/.well-known/oauth-protected-resource/mcp"
if ($metadata.resource -ne "https://$fqdn/mcp") { throw 'OAuth resource metadata mismatch.' }
$state | Add-Member -NotePropertyName endpoint -NotePropertyValue "https://$fqdn/mcp" -Force
$state | Add-Member -NotePropertyName image -NotePropertyValue $image -Force
$state | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding utf8
Write-Host "SRM container deployed. Endpoint: https://$fqdn/mcp"
