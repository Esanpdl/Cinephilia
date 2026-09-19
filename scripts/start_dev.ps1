# Start only Cinephilia's local development services; keep their windows hidden.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $projectRoot 'data/phase6'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

function Test-LocalPort([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try { $client.Connect('127.0.0.1', $Port); return $true }
    catch { return $false }
    finally { $client.Dispose() }
}

if (-not (Test-LocalPort 8000)) {
    $backendProcess = Start-Process -FilePath (Join-Path $projectRoot '.venv/Scripts/python.exe') -ArgumentList @('-u', 'backend/manage.py', 'runserver', '127.0.0.1:8000', '--noreload') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'backend.stdout.log') -RedirectStandardError (Join-Path $logDirectory 'backend.stderr.log') -PassThru
    $backendProcess.Id | Set-Content (Join-Path $logDirectory 'backend.pid')
}
if (-not (Test-LocalPort 5173)) {
    $nodePath = (Get-Command node.exe).Source
    $frontendProcess = Start-Process -FilePath $nodePath -ArgumentList @('node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'frontend.stdout.log') -RedirectStandardError (Join-Path $logDirectory 'frontend.stderr.log') -PassThru
    $frontendProcess.Id | Set-Content (Join-Path $logDirectory 'frontend.pid')
}
Write-Output 'Frontend: http://127.0.0.1:5173/'
Write-Output 'API docs: http://127.0.0.1:8000/api/docs/'
Write-Output ('Logs: ' + $logDirectory)
