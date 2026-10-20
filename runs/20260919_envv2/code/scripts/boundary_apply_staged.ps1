# Au début du cycle <NextCycle> : applique des fichiers préparés et testés hors production (dossier <Stage>),
# met à jour la config, redémarre Run A. Rien n'est appliqué si les tests du dossier préparé ont échoué.
# Usage : powershell -ExecutionPolicy Bypass -File scripts\boundary_apply_staged.ps1 <log stderr> <cycle> <stage> <sortie pytest> <fichiers relatifs séparés par ;> [<script python de config>]
param([string]$Log, [int]$NextCycle, [string]$Stage, [string]$TestOutput, [string]$Files, [string]$ConfigScript = "", [string]$Python = "")
$code = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
Set-Location $code
$py = "C:\Users\utilisateur\AppData\Local\Programs\Python\Python311\python.exe"
# 07/10/2026 : -Python <chemin> = Python utilisé pour le script de config et le redémarrage (ex. venv carte graphique)
if ($Python -and (Test-Path $Python)) { $py = $Python }
$env:PYTHONIOENCODING = "utf-8"
$status = Join-Path $code "logs\boundary_apply_status.txt"
function Log($m) { Add-Content -Path $status -Value ("{0:yyyy-MM-dd HH:mm} {1}" -f (Get-Date), $m) -Encoding utf8 }
Log "attente des tests préparés ($TestOutput) et du cycle #$NextCycle"
$deadline = (Get-Date).AddHours(4)
while (-not ((Test-Path $TestOutput) -and (Select-String -Path $TestOutput -Pattern " in [0-9.]+s" -Quiet))) {
    if ((Get-Date) -gt $deadline) { Log "ABANDON : tests jamais terminés"; exit 1 }
    Start-Sleep 20
}
$summary = (Get-Content $TestOutput | Select-String -Pattern " in [0-9.]+s" | Select-Object -Last 1).Line
if ($summary -match "failed|error") { Log "ABANDON : tests préparés en échec -> $summary"; exit 1 }
Log "tests préparés : $summary"
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
$stamp = "{0:yyyyMMdd_HHmm}" -f (Get-Date)
foreach ($rel in ($Files -split ";")) {
    if (-not $rel) { continue }
    $dst = Join-Path $code $rel
    if (Test-Path $dst) { Copy-Item $dst "$dst.bak_$stamp" -Force }
    Copy-Item (Join-Path $Stage $rel) $dst -Force
    Log "appliqué : $rel (sauvegarde .bak_$stamp)"
}
if ($ConfigScript) {
    Copy-Item "..\run_config_A.yaml" "..\run_config_A.yaml.bak_$stamp" -Force
    $out = & $py $ConfigScript 2>&1 | Select-Object -Last 3
    Log ("config : " + ($out -join " | "))
}
$s2 = "{0:HHmm}" -f (Get-Date)
# 10/10/2026 : jamais hériter d'un réglage de test qui cache la carte graphique (incident de 13h46 : cycle 2x plus lent)
Remove-Item Env:CUDA_VISIBLE_DEVICES -ErrorAction SilentlyContinue
Start-Process $py -ArgumentList "-u","autonomous_agent.py","--config","../run_config_A.yaml" -WorkingDirectory $code `
    -RedirectStandardOutput "logs\stdout_$s2.txt" -RedirectStandardError "logs\stderr_$s2.txt" -WindowStyle Hidden
Start-Sleep 180
$alive = (Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*autonomous_agent*" } | Measure-Object).Count
$tb = (Select-String -Path "logs\stderr_$s2.txt" -Pattern "Traceback" | Measure-Object).Count
$ws = (Select-String -Path "logs\stderr_$s2.txt" -Pattern "Warm start r" | Measure-Object).Count
Log "redémarré (logs stderr_$s2.txt) : vivant=$alive, Traceback=$tb, warm starts réussis=$ws"
Remove-Item "data\maintenance.lock" -ErrorAction SilentlyContinue
Log "FIN"
