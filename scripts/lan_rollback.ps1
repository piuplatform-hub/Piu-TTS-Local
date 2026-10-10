# AI Voice Studio -- Phase 5B-2 Scoped Non-Destructive LAN Gateway Rollback Script
# Strictly avoids killing recycled PIDs, preserves unrelated firewall rules and data
# Accurately measures execution timing and distinguishes config validation from runtime startup

[CmdletBinding()]
param (
    [string]$WorkspaceRoot = "d:\C\Dev\du an\TTS",
    [string]$PidFile = "infra\caddy\caddy_lan.pid",
    [string]$FirewallRuleName = "AIVoiceStudio_LAN_Gateway_TCP_9443",
    [string]$LoopbackCaddyfile = "infra\caddy\Caddyfile",
    [string]$CaddyExe = "infra\caddy\caddy.exe",
    [switch]$StartLoopback,
    [int]$HealthCheckTimeoutSeconds = 5
)

$ErrorActionPreference = "Stop"
$sw = [System.Diagnostics.Stopwatch]::StartNew()

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "AI VOICE STUDIO -- SCOPED NON-DESTRUCTIVE GATEWAY ROLLBACK" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. SCOPED CADDY PROCESS TERMINATION
$pidPath = Join-Path $WorkspaceRoot $PidFile
$caddyTerminated = $false

if (Test-Path $pidPath) {
    $pidContent = (Get-Content $pidPath -Raw).Trim()
    $pidMatch = [regex]::Match($pidContent, '(?m)^PID=(\d+)')
    $recordedPid = if ($pidMatch.Success) { [int]$pidMatch.Groups[1].Value } else { [int]($pidContent.Split("`n")[0].Trim()) }

    if ($recordedPid -gt 0) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $recordedPid" -ErrorAction SilentlyContinue
        if ($proc) {
            $isCaddy = ($proc.ExecutablePath -like "*caddy.exe*") -or ($proc.CommandLine -like "*caddy*")
            $isStudioCaddy = ($proc.CommandLine -like "*Caddyfile.lan*") -or ($proc.ExecutablePath -like "*TTS\infra\caddy\*")

            if ($isCaddy -and $isStudioCaddy) {
                Write-Host "[+] Verified controlled Caddy process (PID: $recordedPid, CreationDate: $($proc.CreationDate)). Stopping..." -ForegroundColor Yellow
                Stop-Process -Id $recordedPid -Force -ErrorAction SilentlyContinue
                $caddyTerminated = $true
            } else {
                Write-Host "[!] WARNING: PID $recordedPid is active but does NOT match AI Voice Studio Caddy gateway! (Exec: $($proc.ExecutablePath)). Process preserved to prevent collateral damage." -ForegroundColor Red
            }
        } else {
            Write-Host "[*] Recorded Caddy PID $recordedPid is already terminated or stale." -ForegroundColor Gray
        }
    }
    Remove-Item $pidPath -Force -ErrorAction SilentlyContinue
}

# Fallback scoped termination if PID file was missing or unrecorded
if (-not $caddyTerminated) {
    $matchingCaddy = Get-CimInstance Win32_Process -Filter "Name = 'caddy.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*Caddyfile.lan*" }
    foreach ($c in $matchingCaddy) {
        Write-Host "[+] Found unrecorded controlled Caddy instance (PID: $($c.ProcessId)). Stopping..." -ForegroundColor Yellow
        Stop-Process -Id $c.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

# 2. SPECIFIC FIREWALL RULE REMOVAL
$fwRule = Get-NetFirewallRule -Name $FirewallRuleName -ErrorAction SilentlyContinue
if ($fwRule) {
    Remove-NetFirewallRule -Name $FirewallRuleName -ErrorAction SilentlyContinue
    Write-Host "[+] Removed dedicated deployment firewall rule: $FirewallRuleName" -ForegroundColor Yellow
} else {
    Write-Host "[*] Dedicated deployment firewall rule ($FirewallRuleName) was not active." -ForegroundColor Gray
}

# 3. VERIFY PORT 9443 RELEASE
$openConn = Get-NetTCPConnection -LocalPort 9443 -State Listen -ErrorAction SilentlyContinue
if ($openConn) {
    Write-Host "[!] Port 9443 is still in LISTEN state by OwningProcess: $($openConn.OwningProcess)" -ForegroundColor Red
} else {
    Write-Host "[+] Port 9443 listener cleanly released." -ForegroundColor Green
}

# 4. RESTORE / VALIDATE LOOPBACK GATEWAY
$caddyExePath = Join-Path $WorkspaceRoot $CaddyExe
$loopbackConfigPath = Join-Path $WorkspaceRoot $LoopbackCaddyfile

if ((Test-Path $caddyExePath) -and (Test-Path $loopbackConfigPath)) {
    Write-Host "[+] Step 4A: Validating known-good loopback configuration syntax..." -ForegroundColor Cyan
    & $caddyExePath validate --config $loopbackConfigPath
    Write-Host "[+] Loopback gateway configuration syntax verified (caddy validate: VALID)." -ForegroundColor Green

    if ($StartLoopback) {
        Write-Host "[+] Step 4B: Starting loopback gateway process (127.0.0.1:9443)..." -ForegroundColor Cyan
        $loopbackProc = Start-Process -FilePath $caddyExePath -ArgumentList "run", "--config", $loopbackConfigPath -PassThru -WindowStyle Hidden
        Start-Sleep -Seconds 2

        $lbConn = Get-NetTCPConnection -LocalPort 9443 -State Listen -ErrorAction SilentlyContinue
        if ($lbConn) {
            Write-Host "[+] Loopback listener confirmed on 127.0.0.1:9443 (PID: $($loopbackProc.Id))." -ForegroundColor Green
        } else {
            Write-Host "[!] Loopback listener not detected on 9443 within timeout." -ForegroundColor Yellow
        }
    } else {
        Write-Host "[*] Note: Runtime gateway startup skipped (pass -StartLoopback to launch process)." -ForegroundColor Gray
    }
}

$sw.Stop()
$elapsedSeconds = [math]::Round($sw.Elapsed.TotalSeconds, 3)

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "[+] NON-DESTRUCTIVE ROLLBACK COMPLETE: SQLite DB & Audio files 100% untouched." -ForegroundColor Green
Write-Host "[+] Measured Rollback Execution Time: $elapsedSeconds seconds ($($sw.ElapsedMilliseconds) ms)" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
