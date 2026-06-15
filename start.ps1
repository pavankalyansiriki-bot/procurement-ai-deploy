# PowerShell equivalent of start.sh for Windows
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# Stop any previously running servers to avoid port conflicts
Write-Host "Stopping processes on ports 8000 and 4004 if present..."
foreach ($port in 8000, 4004) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        Write-Host "Killing process on port ${port}: $($conn.OwningProcess)"
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Also attempting to kill uvicorn and npm dev processes by name..."
Get-Process | Where-Object { $_.ProcessName -match 'uvicorn|node' } | ForEach-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        if ($cmdLine -match 'uvicorn' -or $cmdLine -match 'npm run dev' -or $cmdLine -match 'cds watch') {
            Write-Host "Killing process $($_.Id): $cmdLine"
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

if (-not (Test-Path "backend\.env")) {
    Write-Host "Missing backend\.env. Copy backend\.env.example and add GEMINI_API_KEY."
    exit 1
}

# Use venv python if available, else fall back to python on PATH
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $python = "python"
}

Set-Location "backend"
& $python -m pip install -r requirements.txt
Set-Location ..

Set-Location "cap_backend"
npm install
npm rebuild
npm run deploy:sqlite

$capProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" `
    -RedirectStandardOutput "..\cap_backend.log" -RedirectStandardError "..\cap_backend.err.log" `
    -NoNewWindow -PassThru
Set-Location ..

Start-Sleep -Seconds 2

Set-Location "backend"
$pythonProcess = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "main:app", "--reload", "--port", "8000" `
    -RedirectStandardOutput "..\backend.log" -RedirectStandardError "..\backend.err.log" `
    -NoNewWindow -PassThru
Set-Location ..

Write-Host ""
Write-Host "Python: http://localhost:8000"
Write-Host "CAP:    http://localhost:4004"
Write-Host "UI:     http://localhost:8000/ui"
Write-Host "Docs:   http://localhost:8000/docs"
Write-Host ""
Write-Host "Stop with Ctrl+C"

try {
    Wait-Process -Id $capProcess.Id, $pythonProcess.Id
} finally {
    Stop-Process -Id $capProcess.Id, $pythonProcess.Id -Force -ErrorAction SilentlyContinue
}
