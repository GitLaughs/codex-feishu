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
$ccConnect = Join-Path $env:APPDATA "npm\cc-connect.cmd"
$ackText = -join ([char[]](0x6536, 0x5230))

if ($eventName -ne "message.received") { exit 0 }
if ([string]::IsNullOrWhiteSpace($project) -or [string]::IsNullOrWhiteSpace($session)) { exit 0 }
if (!(Test-Path -LiteralPath $ccConnect)) { exit 0 }

$shouldAck = $false
if ($project -eq $DeepProject) {
    $shouldAck = $true
} elseif ($project -eq $MiniProject) {
    $deepMention = $false
    if (![string]::IsNullOrWhiteSpace($messageText)) {
        $deepMention = $messageText -match $DeepMentionPattern
    }
    $shouldAck = -not $deepMention
}

if (!$shouldAck) { exit 0 }

& $ccConnect send --project $project --session $session --message $ackText | Out-Null
exit 0
