# GREFFE DU JOURNAL DE TRADING SUR UNE SEULE BRANCHE DE MAGNETAR (préparée le 18/10/2026 ; APPLIQUÉE le 19/10 vers
# 00h27 par la commande python équivalente : branche N née de la cime J, sauvegarde sauvegardes\avant_journal_20261019_002727).
# Depuis n'importe où :
#   powershell -ExecutionPolicy Bypass -File C:\Users\utilisateur\Documents\Test_IA\collapsar\ecole\precision\greffer_journal_magnetar.ps1
#   (retour arrière : ... greffer_journal_magnetar.ps1 -Defaire)
# Étapes : 1) arrêt PROPRE (fichier ARRET : le cœur finit sa génération puis s'arrête) ; 2) attente de la fin du
# processus ; 3) greffe (sauvegarde complète automatique dans vie\arbre_or\sauvegardes\avant_journal_<date>\ ; la
# branche la plus faible hors cime est archivée et remplacée par une branche « journal » née de la cime, journal à
# zéro) ou retour arrière ; 4) ARRET retiré et cœur relancé (même commande que le gardien).
param([switch]$Defaire, [string]$Delai = 'fermeture')
$ErrorActionPreference = 'Stop'
$racine = 'C:\Users\utilisateur\Documents\Test_IA'
$python = Join-Path $racine 'venv_gpu\Scripts\python.exe'
$dos = Join-Path $racine 'collapsar\vie\arbre_or'
$arret = Join-Path $dos 'ARRET'
$gen = 1000
try { $gen = [int]((Get-Content (Join-Path $dos 'EN_COURS') -Raw | ConvertFrom-Json).generations) } catch { }

# 1-2. arrêt propre et attente (au plus 30 min : une génération dure ~7-8 min)
New-Item -ItemType File -Force $arret | Out-Null
Write-Output "ARRET posé ; attente de la fin de la génération en cours..."
$t0 = Get-Date
while ($true) {
    $p = Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'collapsar\.ecole\.precision\.arbre_or' }
    if (-not $p) { break }
    if (((Get-Date) - $t0).TotalMinutes -gt 30) { throw "le cœur ne s'est pas arrêté en 30 min (ARRET laissé en place)" }
    Start-Sleep 10
}
Write-Output "cœur arrêté."

# 3. greffe ou retour arrière (refusés si le cœur bat encore)
Set-Location $racine
$env:COLLAPSAR_PRECISION_REGLAGES = Join-Path $racine 'collapsar\ecole\precision\reglages_or.yaml'
$ErrorActionPreference = 'Continue'          # un avertissement de python sur la sortie d'erreur n'est pas un échec
if ($Defaire) {
    & $python -m collapsar.ecole.precision.journal_trading defaire --dossier $dos
} else {
    & $python -m collapsar.ecole.precision.journal_trading greffer --nouvelle --delai $Delai --dossier $dos
}
if ($LASTEXITCODE -ne 0) { throw "greffe / retour arrière en échec (ARRET laissé en place, rien relancé)" }
Remove-Item Env:COLLAPSAR_PRECISION_REGLAGES

# 4. relance (comme le gardien)
Remove-Item $arret -Force
Remove-Item Env:CUDA_VISIBLE_DEVICES -ErrorAction SilentlyContinue
$h = Get-Date -Format 'yyyyMMdd_HHmm'
Start-Process -FilePath $python -ArgumentList '-u', '-m', 'collapsar.ecole.precision.arbre_or', '--generations', $gen `
    -WorkingDirectory $racine -RedirectStandardOutput (Join-Path $dos "logs\coeur_$h.txt") `
    -RedirectStandardError (Join-Path $dos "logs\coeur_${h}_erreurs.txt") -WindowStyle Hidden
Write-Output "cœur relancé (journal : $dos\logs\coeur_$h.txt). Vérifier que la génération suivante SE TERMINE."
