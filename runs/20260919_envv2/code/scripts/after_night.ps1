# Après la nuit AUREXIS : quand l'évaluation est finie (ligne FIN dans logs\night_aurexis.txt), relance Run A
# en mode normal (démo + entraînement continu). Ne promeut rien.
$code = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
Set-Location $code
$py = "C:\Users\utilisateur\AppData\Local\Programs\Python\Python311\python.exe"
$status = Join-Path $code "logs\night_aurexis.txt"
function Log($m) { Add-Content -Path $status -Value ("{0:yyyy-MM-dd HH:mm} {1}" -f (Get-Date), $m) -Encoding utf8 }
$deadline = (Get-Date).AddHours(10)
while (-not (Select-String -Path $status -Pattern "évaluation terminée" -Quiet)) {
    if ((Get-Date) -gt $deadline) { Log "after_night : évaluation jamais terminée, Run A laissé en démo seule"; exit 1 }
    Start-Sleep 60
}
New-Item -ItemType File -Force "data\maintenance.lock" | Out-Null
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
Log "Run A relancé en mode normal (logs stderr_$stamp.txt) : vivant=$alive"
Remove-Item "data\maintenance.lock" -ErrorAction SilentlyContinue
