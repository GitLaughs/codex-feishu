param(
    [switch]$Verify
)

$ErrorActionPreference = "Continue"

function Get-CommandStatus {
    param([string]$Name)

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (!$cmd) {
        return [ordered]@{
            name = $Name
            ok = $false
            source = $null
            version = $null
        }
    }

    $version = $null
    try {
        if ($Name -eq "node") {
            $version = (& node --version 2>$null)
        } elseif ($Name -eq "npm") {
            $version = (& npm --version 2>$null)
        } elseif ($Name -eq "lark-cli") {
            $version = (& lark-cli --version 2>$null)
        }
    } catch {
        $version = $_.Exception.Message
    }

    [ordered]@{
        name = $Name
        ok = $true
        source = $cmd.Source
        version = $version
    }
}

function Invoke-TextCommand {
    param([string[]]$CommandArgs)

    try {
        $exe = $CommandArgs[0]
        $rest = @()
        if ($CommandArgs.Count -gt 1) {
            $rest = $CommandArgs[1..($CommandArgs.Count - 1)]
        }
        $output = & $exe @rest 2>&1
        [ordered]@{
            ok = ($LASTEXITCODE -eq 0)
            exit_code = $LASTEXITCODE
            output = ($output | Out-String).Trim()
        }
    } catch {
        [ordered]@{
            ok = $false
            exit_code = $LASTEXITCODE
            output = $_.Exception.Message
        }
    }
}

function Redact-LarkStatus {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }

    try {
        $json = $Text | ConvertFrom-Json
        $bot = $json.identities.bot
        $user = $json.identities.user
        $scopeCount = 0
        if ($json.scope) {
            $scopeCount = @($json.scope -split "\s+" | Where-Object { $_ }).Count
        }

        return [ordered]@{
            app_id = if ($json.appId) { ($json.appId.Substring(0, [Math]::Min(10, $json.appId.Length)) + "...") } else { $null }
            brand = $json.brand
            default_as = $json.defaultAs
            active_identity = $json.identity
            bot_status = if ($bot) { $bot.status } else { $null }
            bot_available = if ($bot) { $bot.available } else { $null }
            user_status = if ($user) { $user.status } else { $null }
            user_available = if ($user) { $user.available } else { $null }
            token_status = $json.tokenStatus
            scope_count = $scopeCount
            expires_at = $json.expiresAt
            refresh_expires_at = $json.refreshExpiresAt
            note = $json.note
        }
    } catch {
        return [ordered]@{
            parse_error = $_.Exception.Message
            raw = ($Text -replace '(?i)("?(appSecret|accessToken|refreshToken|token)"?\s*:\s*")[^"]+', '$1<redacted>')
        }
    }
}

$commands = @(
    Get-CommandStatus -Name "node"
    Get-CommandStatus -Name "npm"
    Get-CommandStatus -Name "lark-cli"
)

$latest = $null
try {
    $latest = (& npm view "@larksuite/cli" version 2>$null).Trim()
} catch {
    $latest = $null
}

$authArgs = @("lark-cli", "auth", "status")
if ($Verify) {
    $authArgs += "--verify"
}
$auth = Invoke-TextCommand -CommandArgs $authArgs

$result = [ordered]@{
    checked_at = (Get-Date -Format o)
    commands = $commands
    lark_cli_latest_npm = $latest
    auth_ok = $auth.ok
    auth_exit_code = $auth.exit_code
    auth_status = Redact-LarkStatus -Text $auth.output
}

$current = ($commands | Where-Object { $_.name -eq "lark-cli" }).version
if ($current -and $latest -and $current -match '(\d+\.\d+\.\d+)' -and $Matches[1] -ne $latest) {
    $result.update_hint = "lark-cli current $($Matches[1]), latest $latest. Run: lark-cli update"
}

$result | ConvertTo-Json -Depth 8
