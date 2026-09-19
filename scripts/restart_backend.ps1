$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot 'data/phase6/backend.pid'
if (Test-Path -LiteralPath $pidFile) {
    $backendId = [int](Get-Content -LiteralPath $pidFile)
    $backendProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $backendId"
    if ($backendProcess) {
        $expectedPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
        if ($backendProcess.ExecutablePath -ne $expectedPython -or $backendProcess.CommandLine -notmatch 'backend/manage.py.*runserver') {
            throw 'Saved PID does not identify the expected project development server.'
        }
        Stop-Process -Id $backendId
    }
}
& (Join-Path $PSScriptRoot 'start_dev.ps1')
