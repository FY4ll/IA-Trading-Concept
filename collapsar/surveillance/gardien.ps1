# Gardien de COLLAPSAR (tâche Windows « TestIA_CollapsarGardien », toutes les 10 minutes).
# - Si le cœur ne bat plus : il le relance (l'arbre reprend où il en était) et prévient le téléphone.
# - Si le cœur tourne mais n'a rien écrit depuis 45 minutes : il prévient (sans rien tuer).
# - Arrêt volontaire : créer collapsar\vie\ARRET (le gardien ne relance plus tant que le fichier existe).
$ErrorActionPreference = 'Continue'
$racine = 'C:\Users\utilisateur\Documents\Test_IA'
$vie = Join-Path $racine 'collapsar\vie'
$python = Join-Path $racine 'venv_gpu\Scripts\python.exe'
$journal = Join-Path $vie 'logs\gardien.txt'
function Note($t) { Add-Content -Path $journal -Encoding utf8 -Value ("[{0}] {1}" -f (Get-Date -Format 'dd/MM HH:mm'), $t) }
function Alerte($titre, $msg) {
    Push-Location $racine
    & $python -m collapsar.surveillance.telephone $titre $msg
    Pop-Location
}
# ARRET (14/10/2026) : arrête seulement l'ARBRE (le cœur) ; l'école reste surveillée
$arret = Test-Path (Join-Path $vie 'ARRET')
$coeur = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match 'collapsar\.arbre\.coeur' }
if (-not $arret -and -not $coeur) {
    Remove-Item Env:CUDA_VISIBLE_DEVICES -ErrorAction SilentlyContinue
    $h = Get-Date -Format 'yyyyMMdd_HHmm'
    Start-Process -FilePath $python -ArgumentList '-u', '-m', 'collapsar.arbre.coeur' -WorkingDirectory $racine `
        -RedirectStandardOutput (Join-Path $vie "logs\coeur_$h.txt") `
        -RedirectStandardError (Join-Path $vie "logs\coeur_${h}_erreurs.txt") -WindowStyle Hidden
    Note 'cœur arrêté : relancé'
    Alerte 'COLLAPSAR : cœur relancé' "Le cœur ne battait plus, le gardien l'a relancé (l'arbre reprend où il en était)."
    exit 0
}
# L'école : une séance prévue (vie\ecole\seance.json) qui ne tourne plus avant son heure de fin est relancée
$seance = Join-Path $vie 'ecole\seance.json'
if (Test-Path $seance) {
    $s = Get-Content $seance -Raw | ConvertFrom-Json
    $reste = ([datetime]$s.fin - (Get-Date)).TotalMinutes
    $ecole = Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'collapsar\.ecole\.lancer' }
    if (-not $ecole -and $reste -gt 5) {
        $h = Get-Date -Format 'yyyyMMdd_HHmm'
        $arguments = if ($s.arguments) { @('-u', '-m', $s.lanceur) + @($s.arguments) + @('--minutes', ([int]$reste)) }
                     elseif ($s.lanceur) { @('-u', '-m', $s.lanceur, ([int]$reste)) }
                     else { @('-u', '-m', 'collapsar.ecole.lancer', ([int]$reste), $s.marches) }
        Start-Process -FilePath $python -ArgumentList $arguments `
            -WorkingDirectory $racine -RedirectStandardOutput (Join-Path $vie "logs\ecole_$h.txt") `
            -RedirectStandardError (Join-Path $vie "logs\ecole_${h}_erreurs.txt") -WindowStyle Hidden
        Note "école arrêtée avant l'heure : relancée pour $([int]$reste) min"
        Alerte 'COLLAPSAR : école relancée' "La séance d'école s'était arrêtée ; le gardien l'a relancée (l'élève reprend où il en était)."
    } elseif (-not $ecole) {
        Remove-Item -LiteralPath $seance
    }
}
# Le contrôleur de l'école des mille mondes (15/10/2026) : si l'école tourne en mode --sans-controle, il doit tourner
$ecoleSans = Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'lancer_mondes' -and $_.CommandLine -match 'sans-controle' }
$controleur = Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'controleur_mondes' }
if ($ecoleSans -and -not $controleur) {
    $h = Get-Date -Format 'yyyyMMdd_HHmm'
    Start-Process -FilePath $python -ArgumentList '-u', '-m', 'collapsar.ecole.controleur_mondes' -WorkingDirectory $racine `
        -RedirectStandardOutput (Join-Path $vie "logs\controleur_$h.txt") `
        -RedirectStandardError (Join-Path $vie "logs\controleur_${h}_erreurs.txt") -WindowStyle Hidden
    Note 'contrôleur de l''école absent : relancé'
}
# La démo à blanc (15/10/2026, le vrai juge : prix FTMO en direct, compte fictif, AUCUN ordre) et les collecteurs de
# maîtres (gTrade, Ostium) : relancés s'ils manquent. Arrêt volontaire de la démo : créer collapsar\vie\direct\ARRET.
$tous = Get-CimInstance Win32_Process -Filter "Name like 'python%'"
$aSurveiller = @(
    @{ motif = 'collapsar\.direct\.blanc'; module = 'collapsar.direct.blanc'; args = @(); nom = 'blanc';
       arret = (Join-Path $vie 'direct\ARRET'); texte = 'démo à blanc' },
    @{ motif = 'collapsar\.maitres\.gtrade'; module = 'collapsar.maitres.gtrade'; args = @('boucle'); nom = 'maitres_gtrade';
       arret = (Join-Path $vie 'direct\MAITRES_ARRET'); texte = 'collecteur gTrade' },
    # 18/10/2026 : collecteurs arrêtés par le chef de projet (Ostium / gTrade ne sont pas une référence) ;
    # arrêt volontaire : collapsar\vie\direct\MAITRES_ARRET
    @{ motif = 'collapsar\.maitres\.ostium'; module = 'collapsar.maitres.ostium'; args = @('boucle'); nom = 'ostium';
       arret = (Join-Path $vie 'direct\MAITRES_ARRET'); texte = 'collecteur Ostium' },
    # 16/10/2026 : démo Tradeco de la cassure 24 h du bitcoin (arrêt volontaire : collapsar\vie\direct\BITCOIN_ARRET)
    @{ motif = 'collapsar\.direct\.bitcoin_cassure'; module = 'collapsar.direct.bitcoin_cassure'; args = @();
       nom = 'bitcoin_cassure_proc'; arret = (Join-Path $vie 'direct\BITCOIN_ARRET'); texte = 'démo bitcoin cassure' },
    # 16/10/2026 : démo Tradeco des zones gigognes du chef de projet sur BTC et ETH (arrêt : collapsar\vie\direct\CHEF_ARRET)
    @{ motif = 'collapsar\.direct\.chef_zones(?!.*(rejouer|essai))'; module = 'collapsar.direct.chef_zones'; args = @();
       nom = 'chef_zones_proc'; arret = (Join-Path $vie 'direct\CHEF_ARRET'); texte = 'démo zones du chef' },
    # 16/10/2026 : suivi À BLANC de C1 « foule des comptes Binance » (aucun ordre ; arrêt : collapsar\vie\direct\FOULE_ARRET)
    @{ motif = 'collapsar\.direct\.foule_blanc(?!.*(rejouer|essai))'; module = 'collapsar.direct.foule_blanc'; args = @();
       nom = 'foule_blanc_proc'; arret = (Join-Path $vie 'direct\FOULE_ARRET'); texte = 'suivi à blanc foule C1' }
)
foreach ($p in $aSurveiller) {
    if ($p.arret -and (Test-Path $p.arret)) { continue }
    if ($tous | Where-Object { $_.CommandLine -match $p.motif }) { continue }
    $h = Get-Date -Format 'yyyyMMdd_HHmm'
    Start-Process -FilePath $python -ArgumentList (@('-u', '-m', $p.module) + $p.args) -WorkingDirectory $racine `
        -RedirectStandardOutput (Join-Path $vie "logs\$($p.nom)_$h.txt") `
        -RedirectStandardError (Join-Path $vie "logs\$($p.nom)_${h}_erreurs.txt") -WindowStyle Hidden
    Note "$($p.texte) absent : relancé"
}
# 20/10/2026 : HYPERNOVA et MAGNETAR (école de la précision) sont ARCHIVÉS (archive/magnetar/, tag git
# « magnetar-final ») : le gardien ne les relance plus (blocs retirés ; ils sont dans l'historique git).
$dernier = Get-ChildItem (Join-Path $vie 'logs\coeur_*.txt') | Where-Object { $_.Name -notmatch 'erreurs' } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $arret -and $dernier -and $dernier.LastWriteTime -lt (Get-Date).AddMinutes(-45) -and -not (Test-Path (Join-Path $vie 'PAUSE'))) {
    $marque = Join-Path $vie 'gardien_alerte_silence.txt'
    if (-not (Test-Path $marque) -or (Get-Item $marque).LastWriteTime -lt (Get-Date).AddHours(-2)) {
        Set-Content -Path $marque -Value (Get-Date) -Encoding utf8
        Note 'cœur silencieux depuis 45 min'
        Alerte 'COLLAPSAR : cœur silencieux' "Le cœur tourne mais n'a rien écrit depuis 45 minutes."
    }
}
