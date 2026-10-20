# Redémarre le cœur de COLLAPSAR à la FIN du prochain battement (rien n'est perdu), pour qu'il prenne du code neuf.
# Le gardien le relance aussitôt. Usage : powershell -File redemarrer_coeur.ps1
$ErrorActionPreference = 'Continue'
$vie = 'C:\Users\utilisateur\Documents\Test_IA\collapsar\vie'
$journal = Get-ChildItem (Join-Path $vie 'logs\coeur_*.txt') | Where-Object { $_.Name -notmatch 'erreurs' } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
$avant = (Select-String -Path $journal.FullName -Pattern '\] battement \d+' | Measure-Object).Count
$fin = (Get-Date).AddMinutes(40)
while ((Get-Date) -lt $fin) {
    $n = (Select-String -Path $journal.FullName -Pattern '\] battement \d+' | Measure-Object).Count
    if ($n -gt $avant) { break }
    Start-Sleep 5
}
Start-Sleep 8                                   # le temps d'enregistrer l'arbre et les décisions du jardinier
$arret = Join-Path $vie 'ARRET'
New-Item -ItemType File $arret -Force | Out-Null
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'collapsar\.arbre\.coeur' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
Start-Sleep 2
Remove-Item -LiteralPath $arret
Start-ScheduledTask -TaskName TestIA_CollapsarGardien
Add-Content -Path (Join-Path $vie 'logs\gardien.txt') -Encoding utf8 -Value ("[{0}] redémarrage volontaire en fin de battement" -f (Get-Date -Format 'dd/MM HH:mm'))
