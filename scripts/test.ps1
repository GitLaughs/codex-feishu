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

Write-Host "== Bash parse check =="
$bash = Get-Command bash -ErrorAction SilentlyContinue
$bashUsable = $false
if ($bash) {
    try {
        $null = & $bash.Source --version 2>$null
        $bashUsable = ($LASTEXITCODE -eq 0)
    } catch {
        $bashUsable = $false
    }
}
function ConvertTo-BashPath {
    param(
        [string]$Path,
        [string]$BashSource
    )

    $full = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    if ($BashSource -like "*\System32\bash.exe") {
        if ($full -match "^([A-Za-z]):\\(.*)$") {
            $drive = $Matches[1].ToLowerInvariant()
            $rest = $Matches[2].Replace("\", "/")
            return "/mnt/$drive/$rest"
        }
    }
    return $full.Replace("\", "/")
}

function Quote-Bash {
    param([string]$Value)
    return "'" + $Value.Replace("'", "'\''") + "'"
}

if ($bashUsable) {
    $rootBash = ConvertTo-BashPath -Path $Root -BashSource $bash.Source
    $shFiles = Get-ChildItem -LiteralPath $Root -Recurse -Filter *.sh |
        Where-Object { $_.FullName -notlike "*\.git\*" -and $_.FullName -notlike "*\.tmp\*" }
    foreach ($file in $shFiles) {
        $rel = $file.FullName.Substring($Root.Length).TrimStart("\").Replace("\", "/")
        $cmd = "cd $(Quote-Bash $rootBash) && bash -n $(Quote-Bash $rel)"
        $output = & $bash.Source -lc $cmd 2>&1
        if ($LASTEXITCODE -ne 0) {
            Add-Failure "Bash parser errors in $($file.FullName): $($output | Out-String)"
            Write-Host "FAIL $($file.FullName)" -ForegroundColor Red
        } else {
            Write-Host "OK   $($file.FullName)"
        }
    }
} else {
    Write-Host "SKIP bash not found or not usable"
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
        -MiniIgnoreBotMentions "feishu-deep,ou_deep" `
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
        if ($config -notmatch 'ignore_bot_mentions = \["feishu-deep", "ou_deep"\]') {
            Add-Failure "Install smoke did not generate mini ignored bot mention routing guard."
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

if ($bashUsable) {
    Write-Host "== Linux install smoke test =="
    $linuxTmp = Join-Path $Root ".tmp\linux-install"
    $linuxTmpBash = ConvertTo-BashPath -Path $linuxTmp -BashSource $bash.Source
    $rootBash = ConvertTo-BashPath -Path $Root -BashSource $bash.Source
    $cmd = @(
        "cd $(Quote-Bash $rootBash)",
        "rm -rf $(Quote-Bash $linuxTmpBash)",
        "mkdir -p $(Quote-Bash $linuxTmpBash)",
        "bash scripts/install-linux.sh --install-root $(Quote-Bash $rootBash) --config-path $(Quote-Bash "$linuxTmpBash/config.toml") --workspace-path $(Quote-Bash "$linuxTmpBash/workspace") --group-chat-id oc_test --mini-project feishu-mini --deep-project feishu-deep --admin-open-id '*' --mini-model gpt-5.4-mini --mini-effort medium --mini-ignore-bot-mentions feishu-deep,ou_deep --mini-trigger-threshold strict --deep-model gpt-5.5 --deep-effort high --dream-model gpt-5.5 --dream-effort xhigh --codex-mode yolo --mini-app-id cli_mini --mini-app-secret fake-mini-secret --deep-app-id cli_deep --deep-app-secret fake-deep-secret --no-systemd >/dev/null",
        "test -f $(Quote-Bash "$linuxTmpBash/config.toml")",
        "grep -q 'name = `"help`"' $(Quote-Bash "$linuxTmpBash/config.toml")",
        "grep -q 'name = `"dream`"' $(Quote-Bash "$linuxTmpBash/config.toml")",
        "grep -q 'disabled_commands = \[`"dir`", `"shell`", `"restart`", `"upgrade`", `"cron`", `"commands`", `"provider`"\]' $(Quote-Bash "$linuxTmpBash/config.toml")",
        "! grep -q 'admin_from = `"\\*`"' $(Quote-Bash "$linuxTmpBash/config.toml")",
        "grep -q 'ignore_bot_mentions = \[`"feishu-deep`", `"ou_deep`"\]' $(Quote-Bash "$linuxTmpBash/config.toml")",
        "test -f $(Quote-Bash "$linuxTmpBash/workspace/AGENTS.md")",
        "test -f $(Quote-Bash "$linuxTmpBash/workspace/scripts/dream_prompt.md")",
        "test -f $(Quote-Bash "$linuxTmpBash/workspace/local_files/docs/help-guide.md")",
        "test -f $(Quote-Bash "$linuxTmpBash/workspace/scripts/import-local-file.sh")",
        "rm -rf $(Quote-Bash $linuxTmpBash)"
    ) -join " && "
    $output = & $bash.Source -lc $cmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        Add-Failure "Linux install smoke failed: $($output | Out-String)"
    }
    Remove-Item -LiteralPath $linuxTmp -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failures.Count -gt 0) {
    Write-Host "== Failures ==" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    exit 1
}

Write-Host "All checks passed." -ForegroundColor Green
