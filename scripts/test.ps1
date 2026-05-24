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
    $source = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
    [System.Management.Automation.Language.Parser]::ParseInput($source, $file.FullName, [ref]$tokens, [ref]$errors) | Out-Null
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

Write-Host "== Python parse check =="
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $pyFiles = Get-ChildItem -LiteralPath (Join-Path $Root "scripts") -Filter *.py
    $pyArgs = @("-m", "py_compile") + ($pyFiles | ForEach-Object { $_.FullName })
    $output = & $python.Source @pyArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        Add-Failure "Python parser errors: $($output | Out-String)"
    } else {
        Write-Host "OK   Python scripts"
    }
} else {
    Add-Failure "python not found; deterministic command scripts require Python."
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
        -EnableFamilyMemory `
        -NoScheduledTasks | Out-Null

    if (!(Test-Path -LiteralPath $configPath)) { Add-Failure "Install smoke did not generate config." }
    if (Test-Path -LiteralPath $configPath) {
        $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8
        if (!$config.Contains('name = "help"')) { Add-Failure "Install smoke did not generate /help command." }
        if (!$config.Contains('name = "dream"')) { Add-Failure "Install smoke did not generate /dream command." }
        foreach ($commandName in "files","memfind","knowledge","tasks","workspace-info","status-index","health-codex-feishu") {
            if (!$config.Contains("name = `"$commandName`"")) {
                Add-Failure "Install smoke did not generate /$commandName command."
            }
        }
        if (!$config.Contains('disabled_commands = ["dir", "shell", "restart", "upgrade", "cron", "commands", "provider"]')) {
            Add-Failure "Install smoke did not disable privileged group commands."
        }
        if ($config.Contains('admin_from = "*"')) {
            Add-Failure "Install smoke should not grant wildcard group admin privileges."
        }
        if (!$config.Contains('ignore_bot_mentions = ["feishu-deep", "ou_deep"]')) {
            Add-Failure "Install smoke did not generate mini ignored bot mention routing guard."
        }
        if ($config.Contains("instant_ack_text = ")) {
            Add-Failure "Install smoke should not generate text instant ack by default."
        }
        if (($config | Select-String -Pattern 'reaction_emoji = "OnIt"' -AllMatches).Matches.Count -lt 2) {
            Add-Failure "Install smoke did not enable OnIt reaction emoji for both bot projects."
        }
        if (($config | Select-String -Pattern 'image_command_enabled = true' -AllMatches).Matches.Count -lt 2) {
            Add-Failure "Install smoke did not enable platform image commands for both bot projects."
        }
        if (!$config.Contains("generate-image.js")) {
            Add-Failure "Install smoke did not configure the image generation helper."
        }
        if ($config.Contains("cc-connect-ack-hidden.vbs")) {
            Add-Failure "Install smoke should not use the legacy ack hook for immediate acknowledgement."
        }
        if (!$config.Contains("cc-connect-memory-hook.ps1")) {
            Add-Failure "Install smoke did not generate optional family memory hook."
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
    if (!(Test-Path -LiteralPath (Join-Path $workspace "workspace_manifest.json"))) { Add-Failure "Install smoke did not generate workspace manifest." }
    if (!(Test-Path -LiteralPath (Join-Path $workspace "scripts\dream_prompt.md"))) { Add-Failure "Install smoke did not generate dream prompt." }
    if (!(Test-Path -LiteralPath (Join-Path $workspace "local_files\docs\help-guide.md"))) { Add-Failure "Install smoke did not generate help guide." }
    foreach ($scriptName in "lark-download-resource.ps1","lark-health.ps1","lark-event-listener.ps1","help.ps1","dream.ps1","generate-image.js") {
        if (!(Test-Path -LiteralPath (Join-Path $workspace "scripts\$scriptName"))) {
            Add-Failure "Install smoke did not copy $scriptName."
        }
    }
    foreach ($scriptName in "codex-feishu-index.py","codex-feishu-command.py","codex-feishu-health-command.py","codex-feishu-file-health.py","codex-feishu-memory-health.py","codex-feishu-manifest-health.py","codex-feishu-help-health.py","codex-feishu-redact-runs.py","codex-feishu-reindex.ps1") {
        if (!(Test-Path -LiteralPath (Join-Path $workspace "scripts\$scriptName"))) {
            Add-Failure "Install smoke did not copy deterministic command script $scriptName."
        }
    }
    foreach ($scriptName in "family-memory-capture.ps1","family-memory-capture.py","cc-connect-memory-hook.ps1","test-family-memory.ps1","test-family-memory-hook.ps1") {
        if (!(Test-Path -LiteralPath (Join-Path $workspace "scripts\$scriptName"))) {
            Add-Failure "Install smoke did not copy optional family memory script $scriptName."
        }
    }
    foreach ($folder in "memory\messages","memory\people","memory\family","memory\summaries") {
        if (!(Test-Path -LiteralPath (Join-Path $workspace $folder))) {
            Add-Failure "Install smoke did not create optional family memory folder $folder."
        }
    }
    if (Test-Path -LiteralPath (Join-Path $Root "scripts\cc-connect-ack-hidden.vbs")) { Add-Failure "Install smoke generated legacy hidden ack wrapper." }
    if ($python) {
        $reindexOutput = & $python.Source (Join-Path $workspace "scripts\codex-feishu-index.py") --root $workspace reindex 2>&1
        if ($LASTEXITCODE -ne 0) {
            Add-Failure "Install smoke deterministic reindex failed: $($reindexOutput | Out-String)"
        }
        $isolationOutput = & $python.Source (Join-Path $workspace "scripts\test-codex-feishu-command-isolation.py") --root $workspace 2>&1
        if ($LASTEXITCODE -ne 0) {
            Add-Failure "Install smoke command isolation failed: $($isolationOutput | Out-String)"
        } else {
            Write-Host "OK   deterministic command isolation"
        }
        foreach ($healthScript in "codex-feishu-manifest-health.py","codex-feishu-help-health.py","codex-feishu-file-health.py","codex-feishu-memory-health.py") {
            $healthOutput = & $python.Source (Join-Path $workspace "scripts\$healthScript") --root $workspace 2>&1
            if ($LASTEXITCODE -ne 0) {
                Add-Failure "$healthScript failed in install smoke: $($healthOutput | Out-String)"
            }
        }
        $healthCommandOutput = & $python.Source (Join-Path $workspace "scripts\codex-feishu-health-command.py") --root $workspace 2>&1
        if ($LASTEXITCODE -ne 0 -or (($healthCommandOutput | Out-String) -notmatch "codex-feishu 健康：OK")) {
            Add-Failure "codex-feishu health command failed in install smoke: $($healthCommandOutput | Out-String)"
        } else {
            Write-Host "OK   codex-feishu health command"
        }
    }
}
finally {
    Remove-Item -LiteralPath (Join-Path $Root "scripts\cc-connect-ack-hidden.vbs") -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Root "cc-connect-startup-hidden.vbs") -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "== Family memory smoke tests =="
foreach ($testScript in "test-family-memory.ps1","test-family-memory-hook.ps1") {
    $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\$testScript") -Workspace $Root 2>&1
    if ($LASTEXITCODE -ne 0) {
        Add-Failure "$testScript failed: $($output | Out-String)"
    } else {
        Write-Host "OK   scripts\$testScript"
    }
}

if ($bashUsable) {
    $rootBash = ConvertTo-BashPath -Path $Root -BashSource $bash.Source
    Write-Host "== Linux test wrapper =="
    $cmd = "cd $(Quote-Bash $rootBash) && bash scripts/test-linux.sh"
    $output = & $bash.Source -lc $cmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        Add-Failure "Linux test wrapper failed: $($output | Out-String)"
    } else {
        Write-Host "OK   scripts/test-linux.sh"
    }
}

if ($failures.Count -gt 0) {
    Write-Host "== Failures ==" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    exit 1
}

Write-Host "All checks passed." -ForegroundColor Green
