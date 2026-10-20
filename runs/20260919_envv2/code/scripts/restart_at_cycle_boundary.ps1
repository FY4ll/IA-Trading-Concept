# Redémarre Run A au DÉBUT du prochain cycle (aucun travail d'entraînement perdu) pour appliquer une config.
# Usage : powershell -ExecutionPolicy Bypass -File scripts\restart_at_cycle_boundary.ps1 <log stderr actuel> <numéro du cycle attendu>
param([string]$Log, [int]$NextCycle)
$code = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
Set-Location $code
$py = "C:\Users\utilisateur\AppData\Local\Programs\Python\Python311\python.exe"
$status = Join-Path $code "logs\restart_boundary_status.txt"
function Log($m) { Add-Content -Path $status -Value ("{0:yyyy-MM-dd HH:mm} {1}" -f (Get-Date), $m) }
Log "attente du cycle #$NextCycle dans $Log"
$deadline = (Get-Date).AddHours(6)
while (-not (Select-String -Path $Log -Pattern "continue #$NextCycle " -Quiet)) {
    if ((Get-Date) -gt $deadline) { Log "ABANDON : cycle #$NextCycle jamais atteint en 6 h"; exit 1 }
    Start-Sleep 20
}
$agent = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*autonomous_agent*" }
foreach ($a in $agent) {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.ParentProcessId -eq $a.ProcessId } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $a.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep 5
$stamp = "{0:HHmm}" -f (Get-Date)
Start-Process $py -ArgumentList "-u","autonomous_agent.py","--config","../run_config_A.yaml" -WorkingDirectory $code `
    -RedirectStandardOutput "logs\stdout_$stamp.txt" -RedirectStandardError "logs\stderr_$stamp.txt" -WindowStyle Hidden
Start-Sleep 180
$alive = (Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*autonomous_agent*" } | Measure-Object).Count
$tb = (Select-String -Path "logs\stderr_$stamp.txt" -Pattern "Traceback" | Measure-Object).Count
Log "redémarré (logs stderr_$stamp.txt) : Run A vivant=$alive, Traceback=$tb"
if ($alive -lt 1) {
    Start-Process $py -ArgumentList "-u","autonomous_agent.py","--config","../run_config_A.yaml" -WorkingDirectory $code `
        -RedirectStandardOutput "logs\stdout_retry.txt" -RedirectStandardError "logs\stderr_retry.txt" -WindowStyle Hidden
    Log "ÉCHEC -> nouvelle tentative (logs stderr_retry.txt)"
}
