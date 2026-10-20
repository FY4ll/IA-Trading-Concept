# Au début du cycle <NextCycle> : pause du gardien, arrêt de Run A, greffe de la gestion de trade sur AUREX,
# redémarrage. Si la greffe échoue, learn_trade_management est remis à false (AUREX garde ses poids).
param([string]$Log, [int]$NextCycle)
$code = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
Set-Location $code
$py = "C:\Users\utilisateur\AppData\Local\Programs\Python\Python311\python.exe"
$env:PYTHONIOENCODING = "utf-8"
$status = Join-Path $code "logs\boundary_graft_status.txt"
function Log($m) { Add-Content -Path $status -Value ("{0:yyyy-MM-dd HH:mm} {1}" -f (Get-Date), $m) }
Log "attente du cycle #$NextCycle"
$deadline = (Get-Date).AddHours(4)
while (-not (Select-String -Path $Log -Pattern "continue #$NextCycle " -Quiet)) {
    if ((Get-Date) -gt $deadline) { Log "ABANDON : cycle jamais atteint"; exit 1 }
    Start-Sleep 20
}
New-Item -ItemType File -Force "data\maintenance.lock" | Out-Null
$agent = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*autonomous_agent*" }
foreach ($a in $agent) {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.ParentProcessId -eq $a.ProcessId } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $a.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep 5
Log "Run A arrêté, greffe en cours"
$out = & $py scripts\graft_aurex_management.py 2>&1 | Select-Object -Last 3
Log ("greffe : " + ($out -join " | "))
if (-not (($out -join " ") -match "OK : gestion")) {
    & $py -c "import pathlib; p=pathlib.Path('../run_config_A.yaml'); s=p.read_text(encoding='utf-8'); p.write_text(s.replace('      learn_trade_management: true', '      learn_trade_management: false'), encoding='utf-8')"
    Log "greffe NON appliquée -> learn_trade_management remis à false"
}
# amplitude de mutation d'AUREX ramenée à 0,3 (perfectionnement doux, voir run_config continuous.mutation_scale_max)
& $py -c "import json; p='models/champion_AUREX/search_state.json'; s=json.load(open(p,encoding='utf-8')); s['sigma']=0.3; json.dump(s,open(p,'w',encoding='utf-8'),indent=2); print('sigma', s['sigma'])" | ForEach-Object { Log "état de recherche : $_" }
$stamp = "{0:HHmm}" -f (Get-Date)
Start-Process $py -ArgumentList "-u","autonomous_agent.py","--config","../run_config_A.yaml" -WorkingDirectory $code `
    -RedirectStandardOutput "logs\stdout_$stamp.txt" -RedirectStandardError "logs\stderr_$stamp.txt" -WindowStyle Hidden
Start-Sleep 180
$alive = (Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*autonomous_agent*" } | Measure-Object).Count
$tb = (Select-String -Path "logs\stderr_$stamp.txt" -Pattern "Traceback" | Measure-Object).Count
$ws = (Select-String -Path "logs\stderr_$stamp.txt" -Pattern "Warm start r" | Measure-Object).Count
Log "redémarré (logs stderr_$stamp.txt) : vivant=$alive, Traceback=$tb, warm starts réussis=$ws"
Remove-Item "data\maintenance.lock" -ErrorAction SilentlyContinue
Log "FIN"
