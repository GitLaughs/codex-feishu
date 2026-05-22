param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath $Root).Path
$failures = New-Object System.Collections.Generic.List[string]

function Add-Failure {
    param([string]$Message)
    $script:failures.Add($Message) | Out-Null
}

Write-Host "== PowerShell parse check =="
$psFiles = Get-ChildItem -LiteralPath $Root -Recurse -Filter *.ps1 |
    Where-Object { $_.FullName -notlike "*\.git\*" -and $_.FullName -notlike "*\.tmp\*" }

foreach ($file in $psFiles) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors) {
        Add-Failure "Parser errors in $($file.FullName): $($errors[0].Message)"
        Write-Host "FAIL $($file.FullName)" -ForegroundColor Red
    } else {
        Write-Host "OK   $($file.FullName)"
    }
}

Write-Host "== Secret and local-data scan =="
$privateUserName = -join ([char[]](0x7528, 0x6237, 0x0033, 0x0030, 0x0039, 0x0032, 0x0032, 0x0034))
$privateGroupName = -join ([char[]](0x96C6, 0x521B, 0x8D5B))
$scanPatterns = @(
    ('aa' + '854'),
    ('aa' + '9afa'),
    ('9y' + 'OJ'),
    ('1Q' + 'Odx'),
    'ou_[a-z0-9]{10,}',
    ('oc_' + 'c175'),
    ('OPEN' + 'CLAW'),
    $privateUserName,
    $privateGroupName,
    ('mini_secret_' + 'test'),
    ('deep_secret_' + 'test')
)

$textFiles = Get-ChildItem -LiteralPath $Root -Recurse -File |
    Where-Object {
        $_.FullName -notlike "*\.git\*" -and
        $_.FullName -notlike "*\.tmp\*" -and
        $_.Extension -in ".md",".ps1",".toml",".yml",".yaml",".gitignore",".vbs"
    }

foreach ($pattern in $scanPatterns) {
    $matches = Select-String -Path $textFiles.FullName -Pattern $pattern -ErrorAction SilentlyContinue
    foreach ($match in $matches) {
        Add-Failure "Sensitive/local pattern '$pattern' found in $($match.Path):$($match.LineNumber)"
    }
}

Write-Host "== Install smoke test =="
$tmp = Join-Path $Root ".tmp\test-install"
if (Test-Path -LiteralPath $tmp) {
    Remove-Item -LiteralPath $tmp -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

try {
    $configPath = Join-Path $tmp "config.toml"
    $workspace = Join-Path $tmp "workspace"
    & (Join-Path $Root "scripts\install.ps1") `
        -InstallRoot $Root `
        -ConfigPath $configPath `
        -WorkspacePath $workspace `
        -GroupChatId "oc_test" `
        -MiniProject "feishu-mini" `
        -DeepProject "feishu-deep" `
        -AdminOpenId "*" `
        -MiniModel "gpt-5.4-mini" `
        -MiniEffort "medium" `
        -MiniTriggerThreshold "strict" `
        -DeepModel "gpt-5.5" `
        -DeepEffort "high" `
        -DreamModel "gpt-5.5" `
        -DreamEffort "xhigh" `
        -CodexMode "yolo" `
        -MiniAppId "cli_mini" `
        -MiniAppSecret "fake-mini-secret" `
        -DeepAppId "cli_deep" `
        -DeepAppSecret "fake-deep-secret" `
        -NoScheduledTasks | Out-Null

    if (!(Test-Path -LiteralPath $configPath)) { Add-Failure "Install smoke did not generate config." }
    if (Test-Path -LiteralPath $configPath) {
        $config = Get-Content -LiteralPath $configPath -Raw
        if ($config -notmatch 'name = "help"') { Add-Failure "Install smoke did not generate /help command." }
        if ($config -notmatch 'name = "dream"') { Add-Failure "Install smoke did not generate /dream command." }
        if ($config -notmatch 'disabled_commands = \["dir", "shell", "restart", "upgrade", "cron", "commands", "provider"\]') {
            Add-Failure "Install smoke did not disable privileged group commands."
        }
        if ($config -match 'admin_from = "\*"') {
            Add-Failure "Install smoke should not grant wildcard group admin privileges."
        }
    }
    $instructionsPath = Join-Path $workspace "INSTRUCTIONS.md"
    if (!(Test-Path -LiteralPath $instructionsPath)) {
        Add-Failure "Install smoke did not generate workspace instructions."
    } else {
        $instructions = Get-Content -LiteralPath $instructionsPath -Raw
        if ($instructions -notmatch "Mini reply trigger threshold: ``strict``") {
            Add-Failure "Install smoke did not write the mini trigger threshold."
        }
    }
    if (!(Test-Path -LiteralPath (Join-Path $workspace "AGENTS.md"))) { Add-Failure "Install smoke did not generate workspace AGENTS.md." }
    if (!(Test-Path -LiteralPath (Join-Path $workspace "scripts\dream_prompt.md"))) { Add-Failure "Install smoke did not generate dream prompt." }
    if (!(Test-Path -LiteralPath (Join-Path $workspace "local_files\docs\help-guide.md"))) { Add-Failure "Install smoke did not generate help guide." }
    foreach ($scriptName in "lark-download-resource.ps1","lark-health.ps1","lark-event-listener.ps1","help.ps1","dream.ps1") {
        if (!(Test-Path -LiteralPath (Join-Path $workspace "scripts\$scriptName"))) {
            Add-Failure "Install smoke did not copy $scriptName."
        }
    }
    if (!(Test-Path -LiteralPath (Join-Path $Root "scripts\cc-connect-ack-hidden.vbs"))) { Add-Failure "Install smoke did not generate hidden ack wrapper." }
}
finally {
    Remove-Item -LiteralPath (Join-Path $Root "scripts\cc-connect-ack-hidden.vbs") -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Root "cc-connect-startup-hidden.vbs") -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failures.Count -gt 0) {
    Write-Host "== Failures ==" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    exit 1
}

Write-Host "All checks passed." -ForegroundColor Green
