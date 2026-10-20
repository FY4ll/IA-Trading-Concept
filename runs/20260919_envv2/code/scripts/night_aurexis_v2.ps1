# NUIT AUREXIS v2 (06/10/2026 21h45) : les 4 premiers entraînements longs ont appris à ne plus trader (pénalité de
# drawdown 2,0 dans la récompense). 4 nouveaux avec une pénalité réduite (récompense d'entraînement seulement),
# puis la même évaluation en parallèle (scripts/night_eval.ps1). Run A reste en démo seule.
$code = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
Set-Location $code
$py = "C:\Users\utilisateur\AppData\Local\Programs\Python\Python311\python.exe"
$env:PYTHONIOENCODING = "utf-8"
$status = Join-Path $code "logs\night_aurexis.txt"
function Log($m) { Add-Content -Path $status -Value ("{0:yyyy-MM-dd HH:mm} {1}" -f (Get-Date), $m) -Encoding utf8 }
$runs = @(@("r5","0.2",""), @("r6","0.5",""), @("r7","1.0",""), @("r8","0.2","0.01"))
$i = 5
foreach ($r in $runs) {
    $a = @("-u","scripts\train_long.py","--style","AUREXIS","--steps","600000","--ckpt","100000","--run",$r[0],"--lr","0.0001","--seed","$i","--threads","3","--dd",$r[1])
    if ($r[2]) { $a += @("--ent",$r[2]) }
    $p = Start-Process $py -ArgumentList $a -WorkingDirectory $code -RedirectStandardOutput "logs\long_$($r[0]).txt" `
        -RedirectStandardError "logs\long_$($r[0])_err.txt" -WindowStyle Hidden -PassThru
    Log "entraînement long $($r[0]) lancé (pénalité drawdown $($r[1]), exploration $($r[2]), pid $($p.Id))"
    $i += 1
    Start-Sleep 30
}
Start-Process powershell -ArgumentList @("-ExecutionPolicy","Bypass","-File","scripts\night_eval.ps1") -WindowStyle Hidden -WorkingDirectory $code
Log "attente d'évaluation relancée"
