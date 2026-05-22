param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [string]$Workspace = (Split-Path -Parent $PSScriptRoot),
    [string]$SourceMessage = "",
    [string]$Notes = "",
    [switch]$Move
)

$ErrorActionPreference = "Stop"

$localFiles = Join-Path $Workspace "local_files"
$indexPath = Join-Path $localFiles "INDEX.md"

function Get-SafeName {
    param([string]$Name)

    $invalid = [Regex]::Escape(([IO.Path]::GetInvalidFileNameChars() -join ""))
    $safe = [Regex]::Replace($Name, "[$invalid]", "_")
    $safe = [Regex]::Replace($safe, "\s+", " ").Trim()
    if ([string]::IsNullOrWhiteSpace($safe)) { return "unnamed" }
    return $safe
}

function Get-TargetFolder {
    param([IO.FileSystemInfo]$Item)

    if ($Item.PSIsContainer) { return "code" }

    $ext = $Item.Extension.ToLowerInvariant()
    switch -Regex ($ext) {
        '\.(pdf|doc|docx|md|txt|rtf)$' { return "docs" }
        '\.(csv|tsv|xlsx|xls|json|jsonl|yaml|yml|xml|parquet)$' { return "data" }
        '\.(png|jpg|jpeg|gif|webp|bmp|svg|mp4|mov|avi|mkv|mp3|wav|m4a)$' { return "media" }
        '\.(py|js|ts|tsx|jsx|c|cpp|h|hpp|ino|ipynb|ps1|sh|bat|zip|7z|rar|tar|gz)$' { return "code" }
        default { return "incoming" }
    }
}

New-Item -ItemType Directory -Force -Path $localFiles | Out-Null
if (!(Test-Path -LiteralPath $indexPath)) {
    Set-Content -LiteralPath $indexPath -Encoding UTF8 -Value @(
        "# Local File Index",
        "",
        "| Date | Name | Path | Type | Notes |",
        "|---|---|---|---|---|"
    )
}

$item = Get-Item -LiteralPath $Path
$folder = Get-TargetFolder -Item $item
$destDir = Join-Path $localFiles $folder
New-Item -ItemType Directory -Force -Path $destDir | Out-Null

$safeName = Get-SafeName -Name $item.Name
$dest = Join-Path $destDir $safeName
if (Test-Path -LiteralPath $dest) {
    $stem = [IO.Path]::GetFileNameWithoutExtension($safeName)
    $ext = [IO.Path]::GetExtension($safeName)
    $dest = Join-Path $destDir ("{0}_{1:yyyyMMdd_HHmmss}{2}" -f $stem, (Get-Date), $ext)
}

if ($Move) {
    Move-Item -LiteralPath $item.FullName -Destination $dest
} else {
    if ($item.PSIsContainer) {
        Copy-Item -LiteralPath $item.FullName -Destination $dest -Recurse
    } else {
        Copy-Item -LiteralPath $item.FullName -Destination $dest
    }
}

$destItem = Get-Item -LiteralPath $dest
$sizeText = ""
$hashText = ""
if (!$destItem.PSIsContainer) {
    $sizeMb = [Math]::Round($destItem.Length / 1MB, 2)
    $sizeText = ", about $sizeMb MB"
    $hashText = ", sha256 " + ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.Substring(0, 12).ToLowerInvariant())
}

$relativePath = Resolve-Path -LiteralPath $dest -Relative
$relativePath = $relativePath.TrimStart(".", "\")
$date = Get-Date -Format "yyyy-MM-dd"
$type = if ($destItem.PSIsContainer) { "code/project" } else { "$folder/$($destItem.Extension.TrimStart('.').ToLowerInvariant())" }
$sourceText = if ($SourceMessage) { "source '$SourceMessage'" } else { "source pending" }
$noteText = if ($Notes) { "$Notes$sizeText$hashText. $sourceText." } else { "summary pending$sizeText$hashText. $sourceText." }

Add-Content -LiteralPath $indexPath -Encoding UTF8 -Value "| $date | $($destItem.Name) | ``$relativePath`` | $type | $noteText |"

Write-Output "Imported: $relativePath"
