param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string[]]$ExcludeDirs = @(".git", "backup", "work", "node_modules", ".tmp"),
    [switch]$Json
)

$ErrorActionPreference = "Stop"

$patterns = @(
    @{ name = "OpenAI-style key"; regex = 'sk-[A-Za-z0-9_\-]{20,}' },
    @{ name = "Feishu app secret"; regex = '"?appSecret"?\s*[:=]\s*"?[A-Za-z0-9_\-]{12,}' },
    @{ name = "Generic API key assignment"; regex = '"?(apiKey|OPENAI_API_KEY|FEISHU_IMAGE_API_KEY)"?\s*[:=]\s*"?[A-Za-z0-9_\-]{12,}' },
    @{ name = "Bearer token"; regex = 'Bearer\s+[A-Za-z0-9_\-\.]{20,}' },
    @{ name = "Lark open/chat id"; regex = '\b(o[cu]_[a-z0-9]{16,}|cli_[a-z0-9]{12,})\b' }
)

$allowedFiles = @(
    "docs\product-iteration-plan.md",
    "docs\cloud-deploy-and-update.md",
    "docs\feishu-jichuang-mini-fix.md",
    "scripts\audit-secrets.ps1"
)

function Is-ExcludedPath($Path) {
    $relative = Get-RelativePath $Root $Path
    foreach ($dir in $ExcludeDirs) {
        if ($relative -eq $dir -or $relative.StartsWith("$dir\")) {
            return $true
        }
    }
    return $false
}

function Get-RelativePath($Base, $Path) {
    $baseFull = [System.IO.Path]::GetFullPath($Base).TrimEnd('\')
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if ($pathFull.StartsWith($baseFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $pathFull.Substring($baseFull.Length).TrimStart('\')
    }
    return $pathFull
}

$findings = New-Object System.Collections.Generic.List[object]
$files = Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { -not (Is-ExcludedPath $_.FullName) } |
    Where-Object { $_.Length -lt 2MB }

foreach ($file in $files) {
    $relative = Get-RelativePath $Root $file.FullName
    $text = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($null -eq $text) { continue }

    foreach ($pattern in $patterns) {
        $matches = [regex]::Matches($text, $pattern.regex, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        foreach ($match in $matches) {
            $line = ($text.Substring(0, $match.Index) -split "`n").Count
            $allowed = $allowedFiles -contains $relative
            $findings.Add([ordered]@{
                file = $relative
                line = $line
                type = $pattern.name
                allowed_reference = $allowed
                sample = ($match.Value.Substring(0, [Math]::Min(10, $match.Value.Length)) + "***")
            }) | Out-Null
        }
    }
}

$blocking = @($findings | Where-Object { -not $_.allowed_reference })
$result = [ordered]@{
    ok = ($blocking.Count -eq 0)
    root = $Root
    checked_files = @($files).Count
    findings = @($findings.ToArray())
    blocking = @($blocking)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8
} else {
    if ($blocking.Count -eq 0) {
        Write-Host "OK secret audit passed. checked_files=$($result.checked_files)"
    } else {
        Write-Host "FAIL secret audit found blocking findings:"
        foreach ($item in $blocking) {
            Write-Host "- $($item.file):$($item.line) $($item.type)"
        }
    }
}

if ($blocking.Count -gt 0) {
    exit 1
}
