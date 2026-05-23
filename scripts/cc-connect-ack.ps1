param(
    [string]$MiniProject = "feishu-mini",
    [string]$DeepProject = "feishu-deep",
    [string]$DeepMentionPattern = "(@_user_|deep|codex)",
    [switch]$AckMiniAllMessages
)

$ErrorActionPreference = "Stop"

$project = $env:CC_HOOK_PROJECT
$session = $env:CC_HOOK_SESSION_KEY
$eventName = $env:CC_HOOK_EVENT
$messageText = @(
    $env:CC_HOOK_TEXT,
    $env:CC_HOOK_CONTENT,
    $env:CC_HOOK_MESSAGE,
    $env:CC_HOOK_MESSAGE_TEXT
) -join "`n"
$ccConnectExe = Join-Path $env:APPDATA "npm\node_modules\cc-connect\bin\cc-connect.exe"
$ccConnectCmd = Join-Path $env:APPDATA "npm\cc-connect.cmd"
$ccConnect = if (Test-Path -LiteralPath $ccConnectExe) { $ccConnectExe } else { $ccConnectCmd }
$ackText = "workingonit"

if ($eventName -ne "message.received") { exit 0 }
if ([string]::IsNullOrWhiteSpace($project) -or [string]::IsNullOrWhiteSpace($session)) { exit 0 }
if (!(Test-Path -LiteralPath $ccConnect)) { exit 0 }

$shouldAck = ($env:CODEX_FEISHU_TEXT_ACK_FALLBACK -eq "1")

if (!$shouldAck) { exit 0 }

for ($i = 0; $i -lt 8; $i++) {
    & $ccConnect send --project $project --session $session --message $ackText *> $null
    if ($LASTEXITCODE -eq 0) { exit 0 }
    Start-Sleep -Milliseconds 250
}

exit 0
