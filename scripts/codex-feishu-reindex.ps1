param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [int]$MinIntervalSeconds = 300,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$stampDir = Join-Path $Root "memory\search"
$stampFile = Join-Path $stampDir "last-reindex.txt"
$lockFile = Join-Path $stampDir "reindex.lock"
$logFile = Join-Path $stampDir "reindex.log"
New-Item -ItemType Directory -Force -Path $stampDir | Out-Null

function Write-ReindexLog {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format o), $Message
    Add-Content -LiteralPath $logFile -Encoding UTF8 -Value $line
}

$lockStream = $null
try {
    $lockStream = [System.IO.File]::Open($lockFile, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
} catch {
    Write-Output "Skip reindex: lock is held."
    Write-ReindexLog "skip locked root=$Root"
    exit 0
}

try {

$now = Get-Date
if (!$Force -and (Test-Path -LiteralPath $stampFile)) {
    $lastText = Get-Content -LiteralPath $stampFile -Raw -Encoding UTF8
    $last = [datetime]::MinValue
    if ([datetime]::TryParse($lastText.Trim(), [ref]$last)) {
        $age = ($now - $last).TotalSeconds
        if ($age -lt $MinIntervalSeconds) {
            Write-Output "Skip reindex: last run $([int]$age)s ago (< ${MinIntervalSeconds}s)."
            Write-ReindexLog "skip interval age=$([int]$age) min=$MinIntervalSeconds root=$Root"
            exit 0
        }
    }
}

$index = Join-Path $PSScriptRoot "codex-feishu-index.py"
$started = Get-Date
Write-ReindexLog "start root=$Root force=$Force"
python $index --root $Root reindex
if ($LASTEXITCODE -ne 0) {
    Write-ReindexLog "failed exit=$LASTEXITCODE root=$Root"
    exit $LASTEXITCODE
}
$now.ToString("o") | Set-Content -LiteralPath $stampFile -Encoding UTF8
$elapsed = [int]((Get-Date) - $started).TotalSeconds
Write-ReindexLog "ok elapsed=${elapsed}s root=$Root"
} finally {
    if ($lockStream) {
        $lockStream.Dispose()
    }
}
