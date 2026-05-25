param(
    [Parameter(Mandatory = $true)][string]$Query,
    [string]$Workspace = (Split-Path -Parent $PSScriptRoot),
    [int]$Limit = 12
)

$ErrorActionPreference = "Stop"
$builder = Join-Path $PSScriptRoot "build-feishu-recall-packet.py"
if (!(Test-Path -LiteralPath $builder -PathType Leaf)) {
    throw "recall packet builder missing: $builder"
}

& python $builder --workspace $Workspace --query $Query --limit $Limit

