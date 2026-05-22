$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $PSScriptRoot
$guidePath = Join-Path $workspace "local_files\docs\help-guide.md"
$auditPath = Join-Path $workspace "memory\lark-audit.jsonl"

if (!(Test-Path -LiteralPath $guidePath -PathType Leaf)) {
    throw "help guide missing: $guidePath"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $auditPath) | Out-Null
@{
    time = Get-Date -Format o
    action = "help_display"
    project = $env:CC_HOOK_PROJECT
    session = $env:CC_HOOK_SESSION_KEY
} | ConvertTo-Json -Compress | Add-Content -LiteralPath $auditPath -Encoding UTF8

Get-Content -LiteralPath $guidePath -Raw -Encoding UTF8
