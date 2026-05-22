param(
    [string]$TaskName = "codex-feishu-cc-connect",
    [string]$ConfigPath = (Join-Path $env:USERPROFILE ".cc-connect\config.toml"),
    [string]$LogPath = ""
)

$ErrorActionPreference = "Continue"

if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = Join-Path (Split-Path -Parent $PSScriptRoot) "cc-connect-watchdog.log"
}

function Write-WatchLog($message) {
    Add-Content -LiteralPath $LogPath -Value "$(Get-Date -Format o) $message"
}

$ccProcess = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -eq "cc-connect.exe" -and
        $_.CommandLine -like "*$ConfigPath*"
    } |
    Select-Object -First 1

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-WatchLog "task missing: $TaskName"
    exit 1
}

if ($ccProcess) {
    Write-WatchLog "ok pid=$($ccProcess.ProcessId) task_state=$($task.State)"
    exit 0
}

Write-WatchLog "cc-connect missing; task_state=$($task.State); restarting task"

if ($task.State -eq "Running") {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

Start-ScheduledTask -TaskName $TaskName
