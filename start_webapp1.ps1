$ErrorActionPreference = 'Stop'
$webapp1Root = $PSScriptRoot
$webapp1Python = 'C:\venvs\mysite_webapp1\Scripts\python.exe'
$webapp1Pg = 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe'
$webapp1Data = 'C:\venvs\postgres_webapp1'
& $webapp1Pg -D $webapp1Data status *> $null
if ($LASTEXITCODE -ne 0) {
    & $webapp1Pg -D $webapp1Data -l "$webapp1Data\server.log" -w start
    if ($LASTEXITCODE -ne 0) { throw 'webapp1 PostgreSQL startup failed.' }
}
try {
    $webapp1Response = Invoke-WebRequest 'http://127.0.0.1:8001/accounts/login/' -UseBasicParsing -TimeoutSec 2
    if ($webapp1Response.StatusCode -eq 200) {
        Write-Host 'Port 8001 is already serving. Verify it is webapp1 before using it.'
        exit 0
    }
} catch {}
New-Item -ItemType Directory -Path "$webapp1Root\logs" -Force | Out-Null
Start-Process -FilePath $webapp1Python -ArgumentList '-X','utf8',"$webapp1Root\ops\run_webapp1.py" -WorkingDirectory $webapp1Root -WindowStyle Hidden -RedirectStandardOutput "$webapp1Root\logs\server.log" -RedirectStandardError "$webapp1Root\logs\server-error.log"
for ($webapp1Attempt = 0; $webapp1Attempt -lt 20; $webapp1Attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $webapp1Response = Invoke-WebRequest 'http://127.0.0.1:8001/accounts/login/' -UseBasicParsing -TimeoutSec 2
        if ($webapp1Response.StatusCode -eq 200) {
            Write-Host 'webapp1 ready: http://127.0.0.1:8001'
            exit 0
        }
    } catch {}
}
throw 'Server did not become ready. Check webapp1\logs\server-error.log.'
