param([switch]$StopDatabase)
$ErrorActionPreference = 'Stop'
$webapp1PidFile = Join-Path $PSScriptRoot 'logs\server.pid'
if (Test-Path -LiteralPath $webapp1PidFile) {
    $webapp1ServerId = [int](Get-Content -LiteralPath $webapp1PidFile)
    $webapp1Process = Get-CimInstance Win32_Process -Filter "ProcessId=$webapp1ServerId"
    if ($webapp1Process -and $webapp1Process.CommandLine -like '*webapp1*ops*run_webapp1.py*') {
        Stop-Process -Id $webapp1ServerId
        Write-Host 'webapp1 web server stopped.'
    } elseif ($webapp1Process) {
        throw 'PID belongs to another program; nothing was stopped.'
    }
}
if ($StopDatabase) {
    & 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D 'C:\venvs\postgres_webapp1' -m fast -w stop
    if ($LASTEXITCODE -ne 0) { throw 'Could not stop webapp1 PostgreSQL.' }
}
