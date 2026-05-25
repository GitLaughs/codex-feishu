param(
    [string]$Workspace = (Split-Path -Parent $PSScriptRoot),
    [string]$ChatId = "",
    [string]$MessageId = "",
    [string]$SenderOpenId = "fake_open_id",
    [string]$SenderName = "未命名成员",
    [Parameter(Mandatory = $true)]
    [string]$Text,
    [string]$Time = ""
)

$ErrorActionPreference = "Stop"

function Ensure-Dir($path) {
    if (!(Test-Path -LiteralPath $path)) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
    }
}

function Get-ShortHash($value) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($value)
        $hash = $sha.ComputeHash($bytes)
        -join ($hash[0..5] | ForEach-Object { $_.ToString("x2") })
    } finally {
        $sha.Dispose()
    }
}

function Escape-Md($value) {
    ($value -replace '\|', '\|') -replace "`r?`n", " "
}

function Append-UniqueLine($path, $line) {
    if (!(Test-Path -LiteralPath $path)) {
        Set-Content -LiteralPath $path -Value "" -Encoding UTF8
    }
    $existing = Get-Content -LiteralPath $path -ErrorAction SilentlyContinue
    if ($existing -notcontains $line) {
        Add-Content -LiteralPath $path -Value $line -Encoding UTF8
    }
}

function Ensure-Section($path, $heading) {
    $content = if (Test-Path -LiteralPath $path) { Get-Content -LiteralPath $path -Raw } else { "" }
    if ($content -notmatch [regex]::Escape($heading)) {
        Add-Content -LiteralPath $path -Value "`n$heading`n" -Encoding UTF8
    }
}

function New-PersonProfile($path, $personId, $name, $openId) {
    $body = @"
# $name

person_id: $personId
open_ids:
- $openId

## 称呼

- $name

## 明确记忆

## 偏好

## 近期关注

## 待确认

"@
    Set-Content -LiteralPath $path -Value $body -Encoding UTF8
}

function Ensure-TextFile($path, $content) {
    if (!(Test-Path -LiteralPath $path)) {
        Set-Content -LiteralPath $path -Value $content -Encoding UTF8
    }
}

function Ensure-MemoryFiles($workspace) {
    Ensure-TextFile -path (Join-Path $workspace "memory\family\tasks.md") -content "# 家庭待办`n`n| Status | Item | Owner | Source | Created |`n| --- | --- | --- | --- | --- |`n"
    Ensure-TextFile -path (Join-Path $workspace "memory\family\shopping.md") -content "# 购物清单`n`n| Status | Item | Source | Created |`n| --- | --- | --- | --- |`n"
    Ensure-TextFile -path (Join-Path $workspace "memory\family\decisions.md") -content "# 家庭决策`n`n记录长期协作群中已经形成的决定。`n`n| Date | Decision | Source |`n| --- | --- | --- |`n"
    Ensure-TextFile -path (Join-Path $workspace "memory\family\facts.md") -content "# 家庭事实`n`n记录家庭层面的长期事实。只写明确、可追溯、适合在当前群内使用的信息。`n"
    Ensure-TextFile -path (Join-Path $workspace "memory\family\preferences.md") -content "# 家庭偏好`n`n记录家庭共同偏好，例如饮食、采购、出行、沟通方式。`n"
    Ensure-TextFile -path (Join-Path $workspace "memory\family\files.md") -content "# 文件索引摘要`n`n重要文件的语义摘要放这里；具体路径仍以 ``local_files/INDEX.md`` 为准。`n"
}

function Resolve-Person($workspace, $openId, $name) {
    $peopleDir = Join-Path $workspace "memory\people"
    Ensure-Dir $peopleDir
    $indexPath = Join-Path $peopleDir "INDEX.md"
    if (!(Test-Path -LiteralPath $indexPath)) {
        Set-Content -LiteralPath $indexPath -Value "# 人物索引`n`n| person_id | display_name | open_ids | profile |`n| --- | --- | --- | --- |`n" -Encoding UTF8
    }

    $index = Get-Content -LiteralPath $indexPath -Raw
    $escapedOpenId = [regex]::Escape($openId)
    $personId = $null
    foreach ($line in ($index -split "`r?`n")) {
        if ($line -match "^\|\s*([^|]+?)\s*\|") {
            $candidatePersonId = $matches[1].Trim()
            if ($line -match $escapedOpenId) {
                $personId = $candidatePersonId
                break
            }
        }
    }

    if ($personId -in @("person_id", "---")) {
        $personId = $null
    }

    if (!$personId) {
        $personId = "person_" + (Get-ShortHash $openId)
        $profileRel = "memory/people/$personId.md"
        $profilePath = Join-Path $workspace ("memory\people\$personId.md")
        New-PersonProfile -path $profilePath -personId $personId -name $name -openId $openId
        $row = "| $personId | $(Escape-Md $name) | ``$openId`` | ``$profileRel`` |"
        Append-UniqueLine -path $indexPath -line $row
    } else {
        $profilePath = Join-Path $workspace ("memory\people\$personId.md")
        if (!(Test-Path -LiteralPath $profilePath)) {
            New-PersonProfile -path $profilePath -personId $personId -name $name -openId $openId
        }
    }

    [pscustomobject]@{
        PersonId = $personId
        ProfilePath = Join-Path $workspace ("memory\people\$personId.md")
    }
}

function Add-JsonLine($path, $obj) {
    $json = $obj | ConvertTo-Json -Depth 8 -Compress
    Add-Content -LiteralPath $path -Value $json -Encoding UTF8
}

function Add-ProfileMemory($profilePath, $text, $source, $time) {
    Ensure-Section -path $profilePath -heading "## 明确记忆"
    $line = "- $text。来源：$source。时间：$time。置信度：高。"
    $lines = [System.Collections.Generic.List[string]](Get-Content -LiteralPath $profilePath)
    if ($lines -contains $line) {
        return
    }

    $headingIndex = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -eq "## 明确记忆") {
            $headingIndex = $i
            break
        }
    }

    if ($headingIndex -lt 0) {
        $lines.Add("")
        $lines.Add("## 明确记忆")
        $lines.Add("")
        $lines.Add($line)
    } else {
        $insertAt = $headingIndex + 1
        while ($insertAt -lt $lines.Count -and [string]::IsNullOrWhiteSpace($lines[$insertAt])) {
            $insertAt++
        }
        $lines.Insert($insertAt, $line)
        if ($insertAt + 1 -lt $lines.Count -and -not [string]::IsNullOrWhiteSpace($lines[$insertAt + 1])) {
            $lines.Insert($insertAt + 1, "")
        }
    }

    Set-Content -LiteralPath $profilePath -Value $lines -Encoding UTF8
}

function Add-Task($workspace, $item, $source, $time) {
    $path = Join-Path $workspace "memory\family\tasks.md"
    $line = "| open | $(Escape-Md $item) | 未指定 | $source | $time |"
    Append-UniqueLine -path $path -line $line
}

function Add-Shopping($workspace, $item, $source, $time) {
    $path = Join-Path $workspace "memory\family\shopping.md"
    $line = "| open | $(Escape-Md $item) | $source | $time |"
    Append-UniqueLine -path $path -line $line
}

function Read-Remembered($workspace, $profilePath) {
    $parts = New-Object System.Collections.Generic.List[string]
    if (Test-Path -LiteralPath $profilePath) {
        $profile = Get-Content -LiteralPath $profilePath -Raw
        $parts.Add("人物档案：`n" + $profile.Trim())
    }
    foreach ($rel in @("memory\family\tasks.md", "memory\family\shopping.md", "memory\family\decisions.md")) {
        $path = Join-Path $workspace $rel
        if (Test-Path -LiteralPath $path) {
            $content = Get-Content -LiteralPath $path -Raw
            $parts.Add("${rel}:`n" + $content.Trim())
        }
    }
    $parts -join "`n`n---`n`n"
}

$workspaceRoot = (Resolve-Path -LiteralPath $Workspace).Path
foreach ($dir in @("memory\messages", "memory\people", "memory\family", "memory\summaries")) {
    Ensure-Dir (Join-Path $workspaceRoot $dir)
}
Ensure-MemoryFiles -workspace $workspaceRoot

if ([string]::IsNullOrWhiteSpace($Time)) {
    $Time = (Get-Date).ToString("o")
}
if ([string]::IsNullOrWhiteSpace($MessageId)) {
    $MessageId = "fake_" + (Get-Date -Format "yyyyMMddHHmmssfff")
}

$person = Resolve-Person -workspace $workspaceRoot -openId $SenderOpenId -name $SenderName
$date = ([DateTimeOffset]::Parse($Time)).ToString("yyyy-MM-dd")
$messageLog = Join-Path $workspaceRoot "memory\messages\$date.jsonl"
$source = "群消息 $MessageId / $SenderName"

$event = [pscustomobject]@{
    time = $Time
    chat_id = $ChatId
    message_id = $MessageId
    sender_open_id = $SenderOpenId
    sender_name = $SenderName
    person_id = $person.PersonId
    message_type = "text"
    text = $Text
    importance = "normal"
}
Add-JsonLine -path $messageLog -obj $event

$actions = New-Object System.Collections.Generic.List[string]
$reply = "NO_REPLY"

if ($Text -match "^(记住|帮我记住|请记住)[：:\s]*(.+)$") {
    $memoryText = $matches[2].Trim()
    Add-ProfileMemory -profilePath $person.ProfilePath -text $memoryText -source $source -time $Time
    Add-JsonLine -path (Join-Path $workspaceRoot "memory\review_queue.jsonl") -obj ([pscustomobject]@{
        time = $Time; action = "remember_committed"; person_id = $person.PersonId; text = $memoryText; source = $source
    })
    $actions.Add("profile_memory_added")
    $reply = "已记住。"
}
elseif ($Text -match "^(忘掉|删除记忆|以后别记)[：:\s]*(.+)$") {
    $forgetText = $matches[2].Trim()
    Add-JsonLine -path (Join-Path $workspaceRoot "memory\review_queue.jsonl") -obj ([pscustomobject]@{
        time = $Time; action = "forget_requested"; person_id = $person.PersonId; text = $forgetText; source = $source
    })
    $actions.Add("forget_requested")
    $reply = "已记录删除请求，等确认后清理对应记忆。"
}
elseif ($Text -match "^(待办|记一下|提醒一下|提醒)[：:\s]*(.+)$") {
    $task = $matches[2].Trim()
    Add-Task -workspace $workspaceRoot -item $task -source $source -time $Time
    $actions.Add("task_added")
    $reply = "已加入家庭待办。"
}
elseif ($Text -match "^(购物|购物清单|买|采购)[：:\s]*(.+)$") {
    $item = $matches[2].Trim()
    Add-Shopping -workspace $workspaceRoot -item $item -source $source -time $Time
    $actions.Add("shopping_added")
    $reply = "已加入购物清单。"
}
elseif ($Text -match "你记得.*什么|记得什么|查记忆|查看记忆") {
    $actions.Add("memory_read")
    $reply = Read-Remembered -workspace $workspaceRoot -profilePath $person.ProfilePath
}

[pscustomobject]@{
    ok = $true
    reply = $reply
    actions = @($actions)
    person_id = $person.PersonId
    profile = $person.ProfilePath
    message_log = $messageLog
} | ConvertTo-Json -Depth 6
