# Wrapper de redémarrage automatique pour autonomous_agent.py -- lancé par
# la tâche planifiée Windows "TestIA_AutonomousAgent" au démarrage/logon.
# Relance le script indéfiniment s'il se termine (crash ou arrêt), pour
# garantir un fonctionnement 24/7 sans surveillance.
$ErrorActionPreference = "Continue"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)

# GARDE ANTI-DOUBLON DU WATCHDOG LUI-MÊME (18/09) : la tâche planifiée
# "TestIA_AutonomousAgent" a maintenant DEUX déclencheurs -- ouverture de
# session ET un rappel périodique de secours (voir le déclencheur de
# répétition ajouté à la tâche) -- pour que ce script soit relancé même si
# SEUL le watchdog meurt sans que la session ne se ferme (ex: le crash
# silencieux observé le 17/09 à 23:33, cause jamais identifiée avec
# certitude). Sans cette garde, le rappel périodique lancerait une DEUXIÈME
# boucle infinie en parallèle de celle déjà en vie, chacune surveillant
# indépendamment autonomous_agent.py -- inoffensif pour ce dernier (la
# vérification "déjà démarré ?" plus bas reste valide quel que soit le
# nombre de watchdogs), mais deux boucles qui journalisent/tournent pour
# rien est un gaspillage et une source de confusion en diagnostic. Sort
# immédiatement si un AUTRE run_forever.ps1 tourne déjà.
$myPid = $PID
$others = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*run_forever.ps1*" -and $_.ProcessId -ne $myPid }
if ($others) {
    exit 0
}

$python = "C:\Users\utilisateur\AppData\Local\Programs\Python\Python311\python.exe"
$logFile = "logs\autonomous_agent.log"
$mt5Path = "C:\Program Files\MetaTrader 5\terminal64.exe"
$ntfyTopic = "<ton-canal-ntfy>"
$ntfyServer = "https://ntfy.sh"

# ROTATION DES LOGS : ne garde que les 7 derniers jours -- sans ça, un
# système qui tourne H24 pendant des mois accumule un fichier log qui ne
# fait que grossir, jusqu'à saturer le disque.
function Rotate-Log {
    param([string]$LogPath)
    if (-not (Test-Path $LogPath)) { return }
    $item = Get-Item $LogPath
    if ($item.LastWriteTime -lt (Get-Date).AddDays(-1)) {
        $archived = "logs\autonomous_agent_{0}.log" -f $item.LastWriteTime.ToString("yyyy-MM-dd")
        if (-not (Test-Path $archived)) {
            Rename-Item -Path $LogPath -NewName (Split-Path -Leaf $archived) -ErrorAction SilentlyContinue
        }
    }
    Get-ChildItem -Path "logs" -Filter "autonomous_agent_*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

# ÉCRITURE UTF-8 SANS BOM (18/09) : `Out-File -Encoding utf8` en PowerShell
# 5.1 réencode parfois la chaîne via la page de code console active avant de
# l'écrire (double encodage observé : "é" -> "Ã©"), incohérent avec le UTF-8
# pur qu'écrit Python de son côté (voir autonomous_agent.py -- FileHandler).
# [System.IO.File]::AppendAllText avec un encodage UTF8 explicite (sans BOM,
# comme le fait `open(..., encoding="utf-8")` en Python) élimine cette
# réinterprétation intermédiaire -- même encodage, des deux côtés, tout le
# temps.
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function Write-Log {
    param([string]$Line)
    [System.IO.File]::AppendAllText($logFile, "$Line`r`n", $Utf8NoBom)
}

function Send-NtfyAlert {
    param([string]$Title, [string]$Message)
    try {
        Invoke-RestMethod -Uri "$ntfyServer/$ntfyTopic" -Method Post -Body $Message `
            -Headers @{ "Title" = $Title } -TimeoutSec 15 | Out-Null
    } catch {
        Write-Log "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [run_forever] Échec d'envoi de l'alerte ntfy : $_"
    }
}

while ($true) {
    Rotate-Log -LogPath $logFile

    if (-not (Test-Path $python)) {
        Write-Log "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [run_forever] Binaire Python introuvable ($python) -- impossible de démarrer autonomous_agent.py"
        Send-NtfyAlert -Title "TestIA : Python introuvable" -Message "Binaire Python introuvable ($python) -- run_forever.ps1 ne peut pas démarrer autonomous_agent.py."
        Start-Sleep -Seconds 60
        continue
    }

    # IDEMPOTENT : si un autonomous_agent.py tourne déjà (lancé manuellement,
    # ou par une exécution précédente de cette boucle), on ne relance JAMAIS
    # par-dessus -- deux instances en parallèle enverraient chacune leurs
    # propres ordres sur le MÊME compte MT5 (risque réel de doublons/ordres
    # conflictuels). On se contente de surveiller à distance et de ne
    # (re)lancer que si plus AUCUNE instance ne tourne.
    $already = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*autonomous_agent.py*" }
    if ($already) {
        Start-Sleep -Seconds 60
        continue
    }

    # Le terminal MT5 doit être ouvert et connecté AVANT autonomous_agent.py
    # (voir src/mt5_connector.py -- ce connecteur s'attache à un terminal déjà
    # connecté, il ne se connecte jamais lui-même avec un login/mot de passe).
    # Suppose que le compte a été connecté une fois manuellement avec "Enregistrer
    # les infos de connexion" coché dans MT5, pour un reconnexion auto silencieuse.
    if ((Test-Path $mt5Path) -and -not (Get-Process -Name "terminal64" -ErrorAction SilentlyContinue)) {
        Write-Log "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [run_forever] Terminal MT5 non lancé -- démarrage"
        Start-Process -FilePath $mt5Path
        Start-Sleep -Seconds 30
    }

    Write-Log "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [run_forever] Démarrage de autonomous_agent.py"

    # -u (unbuffered) : conservé même si Python écrit maintenant lui-même
    # dans logs\autonomous_agent.log (voir autonomous_agent.py -- FileHandler
    # explicite en UTF-8) -- garde aussi la console/stderr réactive pas à pas.
    #
    # CORRECTIF CORRUPTION D'ENCODAGE (18/09) : `*>> $logFile` mélangeait DEUX
    # écrivains différents dans le MÊME fichier -- tout le logging Python
    # (stderr, redirigé/reformaté par le pipeline PowerShell, avec un encodage
    # parfois incompatible, préfixe "python.exe : ..." observé) ET les
    # lignes de statut de ce script (Out-File -Encoding utf8 ci-dessus).
    # Python écrit maintenant DIRECTEMENT logs\autonomous_agent.log avec un
    # encodage explicite et cohérent (plus de shell intermédiaire pour ce
    # contenu) -- ce script ne capture plus ici que la console brute de
    # Python (utile seulement pour une erreur AVANT l'initialisation du
    # logging, ex: import qui échoue), dans un fichier SÉPARÉ pour ne plus
    # jamais mélanger deux écrivains dans le même fichier.
    #
    # PAS DE cmd.exe (18/09, corrige une fenêtre console VIDE qui s'ouvrait à
    # chaque (re)démarrage) : `cmd /c ...` crée son propre processus console,
    # qui n'hérite pas de la fenêtre CACHÉE de CE script (lancé avec
    # -WindowStyle Hidden) -- une fenêtre cmd.exe visible apparaissait donc à
    # chaque cycle, vide puisque tout le contenu part maintenant dans des
    # fichiers. Start-Process avec -WindowStyle Hidden sur Python DIRECTEMENT
    # (sans cmd.exe intermédiaire) évite ce problème -- redirections de flux
    # natives à .NET, jamais de fenêtre créée.
    $env:PYTHONIOENCODING = "utf-8"
    $consoleLog = "logs\autonomous_agent_console.log"
    $proc = Start-Process -FilePath $python -ArgumentList "-u", "autonomous_agent.py" `
        -WorkingDirectory (Get-Location) -WindowStyle Hidden `
        -RedirectStandardOutput $consoleLog -RedirectStandardError "$consoleLog.err" `
        -PassThru
    $proc.WaitForExit()
    $exitCode = $proc.ExitCode

    Write-Log "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [run_forever] Arrêt détecté (code $exitCode) -- redémarrage dans 30s"
    Start-Sleep -Seconds 30
}
