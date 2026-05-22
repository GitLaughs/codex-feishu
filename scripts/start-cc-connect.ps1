param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$ConfigPath = (Join-Path $env:USERPROFILE ".cc-connect\config.toml"),
    [string]$LogPath = "",
    [int]$RestartDelaySeconds = 10
)

$ErrorActionPreference = "Continue"

if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = Join-Path $Root "cc-connect-run.log"
}

$ccConnectExe = Join-Path $env:APPDATA "npm\node_modules\cc-connect\bin\cc-connect.exe"
$ccConnectCmd = Join-Path $env:APPDATA "npm\cc-connect.cmd"
$ccConnect = if (Test-Path -LiteralPath $ccConnectExe) { $ccConnectExe } else { $ccConnectCmd }
$gitPaths = @("C:\Program Files\Git\bin", "C:\Program Files\Git\usr\bin")

Set-Location -LiteralPath $Root

foreach ($gitPath in $gitPaths) {
    if ((Test-Path -LiteralPath (Join-Path $gitPath "sh.exe")) -and ($env:Path -notlike "*$gitPath*")) {
        $env:Path = "$gitPath;$env:Path"
    }
}

while ($true) {
    Add-Content -LiteralPath $LogPath -Value ""
    Add-Content -LiteralPath $LogPath -Value "==== cc-connect start $(Get-Date -Format o) ===="

    try {
        & $ccConnect --config $ConfigPath --force 2>&1 | Tee-Object -FilePath $LogPath -Append
        $exitCode = $LASTEXITCODE
    }
    catch {
        $exitCode = -1
        Add-Content -LiteralPath $LogPath -Value "cc-connect launch error: $($_.Exception.Message)"
    }

    Add-Content -LiteralPath $LogPath -Value "==== cc-connect exited code=$exitCode $(Get-Date -Format o); restart in ${RestartDelaySeconds}s ===="
    Start-Sleep -Seconds $RestartDelaySeconds
}
