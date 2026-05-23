param(
    [string]$Workspace = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$testWorkspace = Join-Path $Workspace ".tmp\memory-hook-test"
if (Test-Path -LiteralPath $testWorkspace) {
    Remove-Item -LiteralPath $testWorkspace -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $testWorkspace "scripts") | Out-Null
Copy-Item -LiteralPath (Join-Path $Workspace "scripts\family-memory-capture.ps1") -Destination (Join-Path $testWorkspace "scripts\family-memory-capture.ps1")
Copy-Item -LiteralPath (Join-Path $Workspace "scripts\cc-connect-memory-hook.ps1") -Destination (Join-Path $testWorkspace "scripts\cc-connect-memory-hook.ps1")

$env:FAMILY_MEMORY_WORKSPACE = $testWorkspace
$env:FAMILY_MEMORY_PROJECTS = "family-group"
$env:CC_HOOK_EVENT = "message.received"
$env:CC_HOOK_PROJECT = "family-group"
$env:CC_HOOK_TEXT = "记住：爸爸喜欢喝无糖茶"
$env:CC_HOOK_USER_ID = "ou_fake_dad"
$env:CC_HOOK_USER_NAME = "爸爸"
$env:CC_HOOK_MESSAGE_ID = "fake_hook_001"
$env:CC_HOOK_CHAT_ID = "oc_test"

try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $testWorkspace "scripts\cc-connect-memory-hook.ps1") | Out-Null
}
finally {
    foreach ($name in "FAMILY_MEMORY_WORKSPACE","FAMILY_MEMORY_PROJECTS","CC_HOOK_EVENT","CC_HOOK_PROJECT","CC_HOOK_TEXT","CC_HOOK_USER_ID","CC_HOOK_USER_NAME","CC_HOOK_MESSAGE_ID","CC_HOOK_CHAT_ID") {
        Remove-Item -Path "Env:\$name" -ErrorAction SilentlyContinue
    }
}

$profile = Get-ChildItem -LiteralPath (Join-Path $testWorkspace "memory\people") -Filter "person_*.md" | Select-Object -First 1
if (!$profile) {
    throw "profile was not created"
}
$profileText = Get-Content -LiteralPath $profile.FullName -Raw
if ($profileText -notmatch "爸爸喜欢喝无糖茶") {
    throw "expected memory not found in profile"
}

[pscustomobject]@{
    ok = $true
    workspace = $testWorkspace
    profile = $profile.FullName
} | ConvertTo-Json -Depth 4
