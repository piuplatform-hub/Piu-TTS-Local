$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$webRoot = Join-Path $root "apps\web"

function Test-UsablePython([string]$candidate) {
    if (-not (Test-Path -LiteralPath $candidate)) {
        return $false
    }
    try {
        & $candidate -c "import sys" 1>$null 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Test-Listening([int]$port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

$pythonCandidates = @(
    (Join-Path $root ".venv-run\Scripts\python.exe"),
    (Join-Path $root ".venv\Scripts\python.exe")
)
$python = $pythonCandidates | Where-Object { Test-UsablePython $_ } | Select-Object -First 1
if (-not $python) {
    Write-Host "Khong tim thay Python environment hop le (.venv-run hoac .venv)." -ForegroundColor Red
    Write-Host "Xem README.md de tao moi moi truong." -ForegroundColor Yellow
    Read-Host "Nhan Enter de dong"
    exit 1
}

if (-not (Test-Listening 8765)) {
    Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "apps.server.src.main") `
        -WorkingDirectory $root `
        -WindowStyle Normal
    Write-Host "Dang khoi dong API tai http://127.0.0.1:8765 ..."
    Start-Sleep -Seconds 3
} else {
    Write-Host "API da dang chay tai http://127.0.0.1:8765"
}

if (-not (Test-Listening 5173)) {
    Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
        -WorkingDirectory $webRoot `
        -WindowStyle Normal
    Write-Host "Dang khoi dong giao dien tai http://127.0.0.1:5173 ..."
    Start-Sleep -Seconds 3
} else {
    Write-Host "Giao dien da dang chay tai http://127.0.0.1:5173"
}

Start-Process "http://127.0.0.1:5173"
Write-Host "Piu TTS Local da san sang."
