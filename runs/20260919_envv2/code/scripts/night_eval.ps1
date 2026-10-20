# FIN DE NUIT AUREXIS (06/10/2026) : attend la fin des 4 entraînements longs, puis 5 évaluations EN PARALLÈLE
# (référence AUREX + r1..r4), fusion et lockbox des 2 meilleurs. Journal : logs\night_aurexis.txt
$code = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
Set-Location $code
$py = "C:\Users\utilisateur\AppData\Local\Programs\Python\Python311\python.exe"
$env:PYTHONIOENCODING = "utf-8"
$status = Join-Path $code "logs\night_aurexis.txt"
function Log($m) { Add-Content -Path $status -Value ("{0:yyyy-MM-dd HH:mm} {1}" -f (Get-Date), $m) -Encoding utf8 }
Log "attente de la fin des entraînements longs"
while ((Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*train_long*" } | Measure-Object).Count -gt 0) {
    Start-Sleep 30
}
Log "entraînements terminés -> 5 évaluations en parallèle"
$procs = @()
foreach ($part in @("ref", "r1", "r2", "r3", "r4")) {
    $procs += Start-Process $py -ArgumentList "-u","scripts\eval_long.py","AUREXIS","--only",$part -WorkingDirectory $code `
        -RedirectStandardOutput "logs\eval_long_$part.txt" -RedirectStandardError "logs\eval_long_$($part)_err.txt" -WindowStyle Hidden -PassThru
    Start-Sleep 20
}
foreach ($p in $procs) { $p.WaitForExit() }
Log "évaluations partielles terminées -> fusion + lockbox"
& $py -u scripts\eval_long.py AUREXIS --merge *> "logs\eval_long.txt"
Log "évaluation terminée (reports\long_AUREXIS.json, logs\eval_long.txt)"
Log "FIN"
