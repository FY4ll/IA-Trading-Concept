# Migration de l'arbre (13/10/2026 : + horizon « 1 mois ») : à la FIN du prochain battement, arrête le cœur,
# étend le cerveau de chaque branche (collapsar.arbre.migration_horizons), puis le gardien relance le cœur.
$ErrorActionPreference = 'Continue'
$racine = 'C:\Users\utilisateur\Documents\Test_IA'
$vie = Join-Path $racine 'collapsar\vie'
$journal = Get-ChildItem (Join-Path $vie 'logs\coeur_*.txt') | Where-Object { $_.Name -notmatch 'erreurs' } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
$avant = (Select-String -Path $journal.FullName -Pattern '\] battement \d+' | Measure-Object).Count
$fin = (Get-Date).AddMinutes(40)
while ((Get-Date) -lt $fin) {
    if ((Select-String -Path $journal.FullName -Pattern '\] battement \d+' | Measure-Object).Count -gt $avant) { break }
    Start-Sleep 5
}
Start-Sleep 8
$arret = Join-Path $vie 'ARRET'
New-Item -ItemType File $arret -Force | Out-Null
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'collapsar\.arbre\.coeur' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
Start-Sleep 3
Push-Location $racine
$env:CUDA_VISIBLE_DEVICES = '-1'
& (Join-Path $racine 'venv_gpu\Scripts\python.exe') -m collapsar.arbre.migration_horizons
Remove-Item Env:CUDA_VISIBLE_DEVICES
Pop-Location
Remove-Item -LiteralPath $arret
Start-ScheduledTask -TaskName TestIA_CollapsarGardien
Add-Content -Path (Join-Path $vie 'logs\gardien.txt') -Encoding utf8 -Value ("[{0}] migration 1 mois faite, cœur relancé" -f (Get-Date -Format 'dd/MM HH:mm'))
