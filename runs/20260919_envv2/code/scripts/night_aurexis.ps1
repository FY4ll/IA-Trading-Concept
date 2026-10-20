# NUIT AUREXIS (06/10/2026) : Run A passe en démo seule (--no-train), 4 entraînements longs d'AUREXIS en parallèle,
# puis évaluation automatique (scripts/eval_long.py) quand les 4 sont terminés. Journal : logs\night_aurexis.txt
$code = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
Set-Location $code
$py = "C:\Users\utilisateur\AppData\Local\Programs\Python\Python311\python.exe"
$env:PYTHONIOENCODING = "utf-8"
$status = Join-Path $code "logs\night_aurexis.txt"
function Log($m) { Add-Content -Path $status -Value ("{0:yyyy-MM-dd HH:mm} {1}" -f (Get-Date), $m) -Encoding utf8 }

# 1) Run A en démo seule
New-Item -ItemType File -Force "data\maintenance.lock" | Out-Null
$agent = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*autonomous_agent*" }
foreach ($a in $agent) {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.ParentProcessId -eq $a.ProcessId } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $a.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep 5
$stamp = "{0:HHmm}" -f (Get-Date)
Start-Process $py -ArgumentList "-u","autonomous_agent.py","--config","../run_config_A.yaml","--no-train" -WorkingDirectory $code `
    -RedirectStandardOutput "logs\stdout_$stamp.txt" -RedirectStandardError "logs\stderr_$stamp.txt" -WindowStyle Hidden
Start-Sleep 90
$alive = (Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*autonomous_agent*" } | Measure-Object).Count
Log "Run A relancé en démo seule (logs stderr_$stamp.txt) : vivant=$alive"
Remove-Item "data\maintenance.lock" -ErrorAction SilentlyContinue

# 2) 4 entraînements longs (taux d'apprentissage différents, 3 coeurs chacun)
$runs = @(@("r1","0.00005","1"), @("r2","0.0001","2"), @("r3","0.0002","3"), @("r4","0.0001","4"))
$procs = @()
foreach ($r in $runs) {
    $args = @("-u","scripts\train_long.py","--style","AUREXIS","--steps","600000","--ckpt","100000","--run",$r[0],"--lr",$r[1],"--seed",$r[2],"--threads","3")
    if ($r[0] -eq "r4") { $args += @("--ent","0.01") }
    $p = Start-Process $py -ArgumentList $args -WorkingDirectory $code -RedirectStandardOutput "logs\long_$($r[0]).txt" `
        -RedirectStandardError "logs\long_$($r[0])_err.txt" -WindowStyle Hidden -PassThru
    $procs += $p
    Log "entraînement long $($r[0]) lancé (lr=$($r[1]), pid $($p.Id))"
    Start-Sleep 30
}
foreach ($p in $procs) { $p.WaitForExit() }
Log "4 entraînements terminés -> évaluation"
& $py scripts\eval_long.py AUREXIS *>> "logs\eval_long.txt"
Log "évaluation terminée (reports\long_AUREXIS.json, logs\eval_long.txt)"
Log "FIN"
