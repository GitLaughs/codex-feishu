param(
    [string]$EventKey = "im.message.receive_v1",
    [ValidateSet("bot", "user")]
    [string]$As = "bot",
    [string]$Timeout = "10m",
    [int]$MaxEvents = 0,
    [string]$Jq = "",
    [string]$OutputFile = ""
)

$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $workspace "memory\lark-events"
$auditPath = Join-Path $workspace "memory\lark-audit.jsonl"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $auditPath) | Out-Null

$larkCommand = Get-Command lark-cli -ErrorAction SilentlyContinue
if (!$larkCommand) {
    throw "lark-cli not found. Install with: npx @larksuite/cli@latest install"
}
$larkExe = $larkCommand.Source
$cmdShim = Join-Path $env:APPDATA "npm\lark-cli.cmd"
if (Test-Path -LiteralPath $cmdShim -PathType Leaf) {
    $larkExe = $cmdShim
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $runDir "$stamp-$($EventKey -replace '[^a-zA-Z0-9._-]', '_').ndjson"
}
$stderrFile = Join-Path $runDir "$stamp.stderr.log"

$args = @("event", "consume", $EventKey, "--as", $As, "--timeout", $Timeout)
if ($MaxEvents -gt 0) {
    $args += @("--max-events", [string]$MaxEvents)
}
if (![string]::IsNullOrWhiteSpace($Jq)) {
    $args += @("--jq", $Jq)
}

function Join-ProcessArguments {
    param([string[]]$Items)

    ($Items | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + ($_ -replace '"', '\"') + '"'
        } else {
            $_
        }
    }) -join " "
}

$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $larkExe
$psi.Arguments = Join-ProcessArguments -Items $args
$psi.WorkingDirectory = $workspace
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true

$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $psi

$stdoutWriter = [System.IO.StreamWriter]::new($OutputFile, $false, [System.Text.UTF8Encoding]::new($false))
$stderrWriter = [System.IO.StreamWriter]::new($stderrFile, $false, [System.Text.UTF8Encoding]::new($false))
$stdoutWriter.AutoFlush = $true
$stderrWriter.AutoFlush = $true

$outputAction = {
    if ($EventArgs.Data -ne $null) {
        $Event.MessageData.WriteLine($EventArgs.Data)
    }
}
$stdoutSub = Register-ObjectEvent -InputObject $process -EventName OutputDataReceived -Action $outputAction -MessageData $stdoutWriter
$stderrSub = Register-ObjectEvent -InputObject $process -EventName ErrorDataReceived -Action $outputAction -MessageData $stderrWriter

[void]$process.Start()
$process.BeginOutputReadLine()
$process.BeginErrorReadLine()

$ready = $false
$deadline = (Get-Date).AddSeconds(30)
while (!$process.HasExited -and (Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $stderrFile) {
        $stderr = Get-Content -LiteralPath $stderrFile -Raw
        if ($stderr -match "\[event\] ready event_key=") {
            $ready = $true
            break
        }
    }
    Start-Sleep -Milliseconds 500
}

while (!$process.HasExited) {
    Start-Sleep -Milliseconds 500
}

Unregister-Event -SourceIdentifier $stdoutSub.Name -ErrorAction SilentlyContinue
Unregister-Event -SourceIdentifier $stderrSub.Name -ErrorAction SilentlyContinue
$stdoutWriter.Dispose()
$stderrWriter.Dispose()

$auditEvent = @{
    time = Get-Date -Format o
    action = "event_consume"
    ok = ($process.ExitCode -eq 0)
    event_key = $EventKey
    as = $As
    ready = $ready
    exit_code = $process.ExitCode
    output_file = $OutputFile
    stderr_file = $stderrFile
}
$auditEvent | ConvertTo-Json -Compress | Add-Content -LiteralPath $auditPath -Encoding UTF8

[ordered]@{
    ok = ($process.ExitCode -eq 0)
    event_key = $EventKey
    as = $As
    ready = $ready
    pid = $process.Id
    exit_code = $process.ExitCode
    output_file = (Resolve-Path -LiteralPath $OutputFile).Path
    stderr_file = (Resolve-Path -LiteralPath $stderrFile).Path
    note = "Bounded listener started. It exits by timeout/max-events. Do not kill -9."
} | ConvertTo-Json -Depth 4
