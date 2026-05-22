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
$ackText = -join ([char[]](0x6536, 0x5230))

if ($eventName -ne "message.received") { exit 0 }
if ([string]::IsNullOrWhiteSpace($project) -or [string]::IsNullOrWhiteSpace($session)) { exit 0 }
if (!(Test-Path -LiteralPath $ccConnect)) { exit 0 }

$shouldAck = $false
if ($project -eq $DeepProject) {
    $shouldAck = $true
} elseif ($project -eq $MiniProject) {
    # The mini project receives all group messages. By default it must stay
    # silent until the agent decides the message is actionable.
    if (!$AckMiniAllMessages) { exit 0 }

    $deepMention = $false
    if (![string]::IsNullOrWhiteSpace($messageText)) {
        $deepMention = $messageText -match $DeepMentionPattern
    }
    $shouldAck = -not $deepMention
}

if (!$shouldAck) { exit 0 }

& $ccConnect send --project $project --session $session --message $ackText | Out-Null
exit 0
