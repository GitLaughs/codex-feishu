param(
    [Parameter(Mandatory = $true)]
    [string]$MessageId,

    [Parameter(Mandatory = $true)]
    [string]$FileKey,

    [ValidateSet("file", "image")]
    [string]$Type = "file",

    [string]$OutputName = "",

    [ValidateSet("bot", "user")]
    [string]$As = "bot",

    [string]$Notes = ""
)

$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $PSScriptRoot
$incoming = Join-Path $workspace "local_files\incoming"
$auditPath = Join-Path $workspace "memory\lark-audit.jsonl"
$importScript = Join-Path $PSScriptRoot "import-local-file.ps1"

New-Item -ItemType Directory -Force -Path $incoming | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $auditPath) | Out-Null

function Write-Audit {
    param([hashtable]$Event)

    $Event.time = Get-Date -Format o
    Add-Content -LiteralPath $auditPath -Encoding UTF8 -Value (($Event | ConvertTo-Json -Depth 8 -Compress))
}

function Get-SafeOutputName {
    param([string]$Name, [string]$Fallback)

    if ([string]::IsNullOrWhiteSpace($Name)) {
        $Name = $Fallback
    }
    $leaf = Split-Path -Leaf $Name
    if ($leaf -ne $Name -or $Name -match '[/\\]' -or $Name -match '\.\.') {
        throw "OutputName must be a relative file name, not a path: $Name"
    }
    $invalid = [Regex]::Escape(([IO.Path]::GetInvalidFileNameChars() -join ""))
    $safe = [Regex]::Replace($Name, "[$invalid]", "_").Trim()
    if ([string]::IsNullOrWhiteSpace($safe)) {
        throw "OutputName resolved to empty"
    }
    $safe
}

if (!(Get-Command lark-cli -ErrorAction SilentlyContinue)) {
    throw "lark-cli not found. Install with: npx @larksuite/cli@latest install"
}
if (!(Test-Path -LiteralPath $importScript -PathType Leaf)) {
    throw "import script missing: $importScript"
}

$safeName = Get-SafeOutputName -Name $OutputName -Fallback $FileKey
$before = @{}
Get-ChildItem -LiteralPath $incoming -File -ErrorAction SilentlyContinue | ForEach-Object {
    $before[$_.FullName] = $true
}

$downloadArgs = @(
    "im", "+messages-resources-download",
    "--as", $As,
    "--message-id", $MessageId,
    "--file-key", $FileKey,
    "--type", $Type,
    "--output", $safeName
)

$stdout = ""
$exitCode = 0
Push-Location $incoming
try {
    $stdout = (& lark-cli @downloadArgs 2>&1 | Out-String).Trim()
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($exitCode -ne 0) {
    Write-Audit @{
        action = "download_resource"
        ok = $false
        exit_code = $exitCode
        message_id = $MessageId
        file_key = $FileKey
        type = $Type
        as = $As
        output_name = $safeName
        output = $stdout
    }
    Write-Output $stdout
    exit $exitCode
}

$downloaded = Get-ChildItem -LiteralPath $incoming -File |
    Where-Object { !$before.ContainsKey($_.FullName) -or $_.Name -eq $safeName } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (!$downloaded) {
    $candidate = Join-Path $incoming $safeName
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $downloaded = Get-Item -LiteralPath $candidate
    }
}
if (!$downloaded) {
    throw "Download succeeded but no output file found in local_files\incoming. lark-cli output: $stdout"
}

$noteText = if ($Notes) { $Notes } else { "Feishu message resource archived, message_id $MessageId, file_key $FileKey" }
$importOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $importScript -Path $downloaded.FullName -SourceMessage $MessageId -Notes $noteText -Move

Write-Audit @{
    action = "download_resource"
    ok = $true
    message_id = $MessageId
    file_key = $FileKey
    type = $Type
    as = $As
    output_name = $safeName
    downloaded_path = $downloaded.FullName
    import_output = ($importOutput | Out-String).Trim()
}

Write-Output ($importOutput | Out-String).Trim()
