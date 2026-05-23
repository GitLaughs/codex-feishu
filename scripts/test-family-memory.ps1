param(
    [string]$Workspace = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$capture = Join-Path $Workspace "scripts\family-memory-capture.ps1"
$testWorkspace = Join-Path $Workspace ".tmp\memory-test"

if (!(Test-Path -LiteralPath $capture)) {
    throw "family-memory-capture.ps1 not found: $capture"
}

if (Test-Path -LiteralPath $testWorkspace) {
    Remove-Item -LiteralPath $testWorkspace -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $testWorkspace | Out-Null

$sender = "ou_fake_mom"
$name = "妈妈"
$cases = @(
    @{ id = "fake_001"; text = "记住：妈妈不太吃辣，推荐菜单时优先清淡"; expect = "profile_memory_added" },
    @{ id = "fake_002"; text = "购物：牛奶、鸡蛋、洗衣液"; expect = "shopping_added" },
    @{ id = "fake_003"; text = "待办：周末检查空调滤网"; expect = "task_added" },
    @{ id = "fake_004"; text = "你记得什么"; expect = "memory_read" }
)

$results = @()
foreach ($case in $cases) {
    $raw = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $capture `
        -Workspace $testWorkspace `
        -SenderOpenId $sender `
        -SenderName $name `
        -MessageId $case.id `
        -Text $case.text
    $obj = $raw | ConvertFrom-Json
    $pass = $obj.actions -contains $case.expect
    $results += [pscustomobject]@{
        id = $case.id
        text = $case.text
        expect = $case.expect
        pass = $pass
        reply = $obj.reply
    }
}

$failed = @($results | Where-Object { -not $_.pass })
[pscustomobject]@{
    ok = ($failed.Count -eq 0)
    workspace = $testWorkspace
    results = $results
} | ConvertTo-Json -Depth 8

if ($failed.Count -gt 0) {
    exit 1
}
