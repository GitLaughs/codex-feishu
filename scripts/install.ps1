param(
    [string]$InstallRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ConfigPath = (Join-Path $env:USERPROFILE ".cc-connect\config.toml"),
    [string]$WorkspacePath = "",
    [string]$TaskName = "codex-feishu-cc-connect",
    [string]$WatchdogTaskName = "codex-feishu-watchdog",
    [string]$GroupChatId = "",
    [string]$MiniProject = "",
    [string]$DeepProject = "",
    [string]$AdminOpenId = "",
    [string]$MiniModel = "",
    [string]$MiniEffort = "",
    [string]$MiniTriggerThreshold = "",
    [string]$DeepModel = "",
    [string]$DeepEffort = "",
    [string]$DreamModel = "",
    [string]$DreamEffort = "",
    [string]$CodexMode = "",
    [string]$MiniAppId = "",
    [string]$MiniAppSecret = "",
    [string]$DeepAppId = "",
    [string]$DeepAppSecret = "",
    [switch]$NoScheduledTasks
)

$ErrorActionPreference = "Stop"

function Read-Value {
    param(
        [string]$Prompt,
        [string]$Default = "",
        [switch]$Required
    )

    while ($true) {
        $suffix = if ($Default) { " [$Default]" } else { "" }
        $value = Read-Host "$Prompt$suffix"
        if ([string]::IsNullOrWhiteSpace($value)) {
            $value = $Default
        }
        if (!$Required -or ![string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
        Write-Host "Value is required." -ForegroundColor Yellow
    }
}

function Read-SecretValue {
    param([string]$Prompt)

    $secure = Read-Host $Prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Convert-ToTomlLiteral {
    param([string]$Value)
    return $Value.Replace("\", "\\").Replace('"', '\"')
}

function Convert-ToForwardSlash {
    param([string]$Path)
    return $Path.Replace("\", "/")
}

function Write-Utf8File {
    param(
        [string]$Path,
        [string]$Content
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

$InstallRoot = (Resolve-Path -LiteralPath $InstallRoot).Path
$workspaceWasProvided = $PSBoundParameters.ContainsKey("WorkspacePath") -and ![string]::IsNullOrWhiteSpace($WorkspacePath)
if ([string]::IsNullOrWhiteSpace($WorkspacePath)) {
    $WorkspacePath = Join-Path $InstallRoot "workspace"
}

Write-Host "codex-feishu installer" -ForegroundColor Cyan
Write-Host "Install root: $InstallRoot"
Write-Host "Config path:  $ConfigPath"
Write-Host ""

$groupChatId = if ($GroupChatId) { $GroupChatId } else { Read-Value -Prompt "Feishu group chat_id (oc_xxx)" -Required }
$miniProject = if ($MiniProject) { $MiniProject } else { Read-Value -Prompt "Mini project name" -Default "feishu-mini" -Required }
$deepProject = if ($DeepProject) { $DeepProject } else { Read-Value -Prompt "Deep project name" -Default "feishu-deep" -Required }
$adminOpenId = if ($AdminOpenId) { $AdminOpenId } else { Read-Value -Prompt "Admin open_id (optional; use * to allow configured platform users)" -Default "*" }
$miniModel = if ($MiniModel) { $MiniModel } else { Read-Value -Prompt "Mini model" -Default "gpt-5.4-mini" -Required }
$miniEffort = if ($MiniEffort) { $MiniEffort } else { Read-Value -Prompt "Mini reasoning effort" -Default "medium" -Required }
$miniTriggerThreshold = if ($MiniTriggerThreshold) { $MiniTriggerThreshold } else { Read-Value -Prompt "Mini reply trigger threshold (relaxed/medium/strict)" -Default "strict" -Required }
$deepModel = if ($DeepModel) { $DeepModel } else { Read-Value -Prompt "Deep model" -Default "gpt-5.5" -Required }
$deepEffort = if ($DeepEffort) { $DeepEffort } else { Read-Value -Prompt "Deep reasoning effort" -Default "high" -Required }
$dreamModel = if ($DreamModel) { $DreamModel } else { Read-Value -Prompt "Dream command model" -Default $deepModel -Required }
$dreamEffort = if ($DreamEffort) { $DreamEffort } else { Read-Value -Prompt "Dream command reasoning effort" -Default "xhigh" -Required }
$codexMode = if ($CodexMode) { $CodexMode } else { Read-Value -Prompt "Codex mode" -Default "yolo" -Required }
if (!$workspaceWasProvided) {
    $WorkspacePath = Read-Value -Prompt "Group workspace path" -Default $WorkspacePath -Required
}

Write-Host ""
Write-Host "Mini Feishu app credentials" -ForegroundColor Cyan
$miniAppId = if ($MiniAppId) { $MiniAppId } else { Read-Value -Prompt "Mini app_id" -Required }
$miniAppSecret = if ($MiniAppSecret) { $MiniAppSecret } else { Read-SecretValue -Prompt "Mini app_secret" }

Write-Host ""
Write-Host "Deep Feishu app credentials" -ForegroundColor Cyan
$deepAppId = if ($DeepAppId) { $DeepAppId } else { Read-Value -Prompt "Deep app_id" -Required }
$deepAppSecret = if ($DeepAppSecret) { $DeepAppSecret } else { Read-SecretValue -Prompt "Deep app_secret" }

$WorkspacePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($WorkspacePath)
$configDir = Split-Path -Parent $ConfigPath
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
New-Item -ItemType Directory -Force -Path $WorkspacePath | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $WorkspacePath "scripts") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $WorkspacePath "memory") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $WorkspacePath "memory\dreams") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $WorkspacePath "memory\lark-events") | Out-Null

foreach ($folder in "incoming","docs","data","media","code","assets") {
    New-Item -ItemType Directory -Force -Path (Join-Path $WorkspacePath "local_files\$folder") | Out-Null
}

$indexPath = Join-Path $WorkspacePath "local_files\INDEX.md"
if (!(Test-Path -LiteralPath $indexPath)) {
    Set-Content -LiteralPath $indexPath -Encoding UTF8 -Value @(
        "# Local File Index",
        "",
        "| Date | Name | Path | Type | Notes |",
        "|---|---|---|---|---|"
    )
}

$knowledgePath = Join-Path $WorkspacePath "KNOWLEDGE.md"
if (!(Test-Path -LiteralPath $knowledgePath)) {
    Set-Content -LiteralPath $knowledgePath -Encoding UTF8 -Value "# Knowledge`n"
}

$workspaceFwd = Convert-ToForwardSlash $WorkspacePath
$groupAdminLine = ""
if (![string]::IsNullOrWhiteSpace($adminOpenId) -and $adminOpenId -ne "*") {
    $groupAdminLine = "admin_from = `"$adminOpenId`""
}

foreach ($scriptName in "import-local-file.ps1","lark-download-resource.ps1","lark-health.ps1","lark-event-listener.ps1","help.ps1","dream.ps1") {
    Copy-Item -LiteralPath (Join-Path $InstallRoot "scripts\$scriptName") -Destination (Join-Path $WorkspacePath "scripts\$scriptName") -Force
}

$instructionsTemplate = Get-Content -LiteralPath (Join-Path $InstallRoot "templates\INSTRUCTIONS.md") -Raw
$instructions = $instructionsTemplate.
    Replace("__MINI_PROJECT__", $miniProject).
    Replace("__DEEP_PROJECT__", $deepProject).
    Replace("__MINI_MODEL__", $miniModel).
    Replace("__MINI_TRIGGER_THRESHOLD__", $miniTriggerThreshold).
    Replace("__DEEP_MODEL__", $deepModel)
Write-Utf8File -Path (Join-Path $WorkspacePath "INSTRUCTIONS.md") -Content $instructions

$agentsTemplate = Get-Content -LiteralPath (Join-Path $InstallRoot "templates\AGENTS.md") -Raw
$agents = $agentsTemplate.
    Replace("__WORKSPACE__", $WorkspacePath).
    Replace("__MINI_PROJECT__", $miniProject).
    Replace("__DEEP_PROJECT__", $deepProject).
    Replace("__MINI_MODEL__", $miniModel).
    Replace("__DREAM_MODEL__", $dreamModel).
    Replace("__DREAM_EFFORT__", $dreamEffort)
Write-Utf8File -Path (Join-Path $WorkspacePath "AGENTS.md") -Content $agents

$dreamPromptTemplate = Get-Content -LiteralPath (Join-Path $InstallRoot "templates\dream_prompt.md") -Raw
$dreamPrompt = $dreamPromptTemplate.Replace("__WORKSPACE__", $WorkspacePath)
Write-Utf8File -Path (Join-Path $WorkspacePath "scripts\dream_prompt.md") -Content $dreamPrompt

$helpGuideTemplate = Get-Content -LiteralPath (Join-Path $InstallRoot "templates\help-guide.md") -Raw
Write-Utf8File -Path (Join-Path $WorkspacePath "local_files\docs\help-guide.md") -Content $helpGuideTemplate

$ackScript = Join-Path $InstallRoot "scripts\cc-connect-ack.ps1"
$ackVbsPath = Join-Path $InstallRoot "scripts\cc-connect-ack-hidden.vbs"
$ackArgs = @(
    "-NoProfile",
    "-ExecutionPolicy Bypass",
    "-WindowStyle Hidden",
    "-File `"$ackScript`"",
    "-MiniProject `"$miniProject`"",
    "-DeepProject `"$deepProject`"",
    "-DeepMentionPattern `"(@_user_|$([Regex]::Escape($deepProject)))`""
) -join " "
$ackVbs = @"
Set shell = CreateObject("WScript.Shell")
cmd = "powershell.exe $ackArgs"
shell.Run cmd, 0, False
"@
Write-Utf8File -Path $ackVbsPath -Content $ackVbs

$startupVbsPath = Join-Path $InstallRoot "cc-connect-startup-hidden.vbs"
$watchScript = Join-Path $InstallRoot "scripts\watch-cc-connect.ps1"
$watchLog = Join-Path $InstallRoot "cc-connect-watchdog.log"
$startupVbs = @"
Set shell = CreateObject("WScript.Shell")
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""$watchScript"" -TaskName ""$TaskName"" -ConfigPath ""$ConfigPath"" -LogPath ""$watchLog"""
shell.Run cmd, 0, False
"@
Write-Utf8File -Path $startupVbsPath -Content $startupVbs

$template = Get-Content -LiteralPath (Join-Path $InstallRoot "templates\config.double-bot.toml") -Raw
$config = $template.
    Replace("__INSTALL_ROOT_FWD__", (Convert-ToForwardSlash $InstallRoot)).
    Replace("__WORKSPACE_FWD__", $workspaceFwd).
    Replace("__WORKSPACE__", (Convert-ToTomlLiteral $WorkspacePath)).
    Replace("__GROUP_CHAT_ID__", $groupChatId).
    Replace("__MINI_PROJECT__", $miniProject).
    Replace("__DEEP_PROJECT__", $deepProject).
    Replace("__ADMIN_OPEN_ID__", $adminOpenId).
    Replace("__CODEX_MODE__", $codexMode).
    Replace("__MINI_MODEL__", $miniModel).
    Replace("__MINI_EFFORT__", $miniEffort).
    Replace("__DEEP_MODEL__", $deepModel).
    Replace("__DEEP_EFFORT__", $deepEffort).
    Replace("__GROUP_ADMIN_LINE__", $groupAdminLine).
    Replace("__MINI_APP_ID__", $miniAppId).
    Replace("__MINI_APP_SECRET__", (Convert-ToTomlLiteral $miniAppSecret)).
    Replace("__DEEP_APP_ID__", $deepAppId).
    Replace("__DEEP_APP_SECRET__", (Convert-ToTomlLiteral $deepAppSecret))

if (Test-Path -LiteralPath $ConfigPath) {
    $backupPath = "$ConfigPath.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
    Copy-Item -LiteralPath $ConfigPath -Destination $backupPath
    Write-Host "Backed up existing config to $backupPath" -ForegroundColor Yellow
}

Write-Utf8File -Path $ConfigPath -Content $config
Write-Host "Wrote cc-connect config: $ConfigPath" -ForegroundColor Green

if (!$NoScheduledTasks) {
    $startScript = Join-Path $InstallRoot "scripts\start-cc-connect.ps1"
    $runLog = Join-Path $InstallRoot "cc-connect-run.log"

    $startAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startScript`" -Root `"$InstallRoot`" -ConfigPath `"$ConfigPath`" -LogPath `"$runLog`""
    $startTrigger = New-ScheduledTaskTrigger -AtLogOn
    $startSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $startSettings.Hidden = $true

    $watchAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$watchScript`" -TaskName `"$TaskName`" -ConfigPath `"$ConfigPath`" -LogPath `"$watchLog`""
    $watchTriggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $watchTriggerRepeating = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
    $watchSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $watchSettings.Hidden = $true

    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $WatchdogTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName -Action $startAction -Trigger $startTrigger -Settings $startSettings -Description "codex-feishu cc-connect runner" | Out-Null
    Register-ScheduledTask -TaskName $WatchdogTaskName -Action $watchAction -Trigger @($watchTriggerLogon, $watchTriggerRepeating) -Settings $watchSettings -Description "codex-feishu cc-connect watchdog" | Out-Null

    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Registered and started scheduled task: $TaskName" -ForegroundColor Green
    Write-Host "Registered watchdog task: $WatchdogTaskName" -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Confirm Feishu console permissions and event subscription."
Write-Host "2. Invite both bots to the group."
Write-Host "3. Send a normal group message to test mini monitoring."
Write-Host "4. @ the deep bot to test deep routing."
