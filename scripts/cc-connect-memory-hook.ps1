param(
    [string]$Workspace = $env:FAMILY_MEMORY_WORKSPACE,
    [string]$Projects = $env:FAMILY_MEMORY_PROJECTS
)

$ErrorActionPreference = "Stop"

if ($env:CC_HOOK_EVENT -ne "message.received") { exit 0 }
if ([string]::IsNullOrWhiteSpace($Projects)) {
    $Projects = "family-codex-at,family-group,family-deep"
}
$allowed = $Projects -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if ($allowed -notcontains $env:CC_HOOK_PROJECT) { exit 0 }

if ([string]::IsNullOrWhiteSpace($Workspace)) {
    $Workspace = (Split-Path -Parent $PSScriptRoot)
}
$script = Join-Path $Workspace "scripts\family-memory-capture.ps1"
if (!(Test-Path -LiteralPath $script)) { exit 0 }

$text = @(
    $env:CC_HOOK_TEXT,
    $env:CC_HOOK_CONTENT,
    $env:CC_HOOK_MESSAGE_TEXT,
    $env:CC_HOOK_MESSAGE
) | Where-Object { ![string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($text)) { exit 0 }

$senderId = @(
    $env:CC_HOOK_USER_ID,
    $env:CC_HOOK_SENDER_ID,
    $env:CC_HOOK_OPEN_ID,
    $env:CC_HOOK_USER_OPEN_ID,
    "unknown_open_id"
) | Where-Object { ![string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1
$senderName = @(
    $env:CC_HOOK_USER_NAME,
    $env:CC_HOOK_SENDER_NAME,
    $env:CC_HOOK_NAME,
    "未命名成员"
) | Where-Object { ![string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1
$messageId = @(
    $env:CC_HOOK_MESSAGE_ID,
    $env:CC_HOOK_MSG_ID,
    $env:CC_HOOK_EVENT_ID
) | Where-Object { ![string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1
$chatId = $env:CC_HOOK_CHAT_ID

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script `
    -Workspace $Workspace `
    -ChatId $chatId `
    -MessageId $messageId `
    -SenderOpenId $senderId `
    -SenderName $senderName `
    -Text $text *> $null
exit 0
