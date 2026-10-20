# GARDIEN de Run A (06/10/2026) -- lancé toutes les 5 minutes et à l'ouverture de session par le
# Planificateur de tâches Windows (tâches "TestIA_Watchdog" et "TestIA_Watchdog_Logon").
#  - MetaTrader 5 fermé -> relancé ;
#  - Run A (autonomous_agent.py) arrêté -> relancé (une seule instance : verrou système dans le programme) ;
#  - Run A figé (signal de vie logs\heartbeat.txt non écrit depuis 20 min) -> arrêté puis relancé ;
#  - nettoyage des journaux de lancement de plus de 14 jours.
# Pendant une maintenance, le fichier data\maintenance.lock (moins de 60 min) met le gardien en pause.
$code = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
$py = "C:\Users\utilisateur\AppData\Local\Programs\Python\Python311\python.exe"
# 07/10/2026 : calculs du cerveau sur la carte graphique (GTX 1060) -- Python du dossier venv_gpu (torch CUDA)
$gpuPy = "C:\Users\utilisateur\Documents\Test_IA\venv_gpu\Scripts\python.exe"
if (Test-Path $gpuPy) { $py = $gpuPy }
$mt5 = "C:\Program Files\MetaTrader 5\terminal64.exe"
Set-Location $code
$wlog = Join-Path $code "logs\watchdog.txt"
function Log($m) { Add-Content -Path $wlog -Value ("{0:yyyy-MM-dd HH:mm} {1}" -f (Get-Date), $m) }
function Notify($subject, $msg) {
    $env:PYTHONIOENCODING = "utf-8"
    & $py -c "import sys, yaml; sys.path.insert(0, '.'); from src.notifier import send_alert; send_alert(yaml.safe_load(open('../run_config_A.yaml', encoding='utf-8')), subject=sys.argv[1], message=sys.argv[2])" $subject $msg 2>$null | Out-Null
}
function AgentProcs { Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*autonomous_agent*" } }
function StopAgent {
    foreach ($a in AgentProcs) {
        Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.ParentProcessId -eq $a.ProcessId } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Stop-Process -Id $a.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
function StartAgent($why) {
    $stamp = "{0:MMdd_HHmm}" -f (Get-Date)
    Start-Process $py -ArgumentList "-u","autonomous_agent.py","--config","../run_config_A.yaml" -WorkingDirectory $code `
        -RedirectStandardOutput "logs\stdout_wd_$stamp.txt" -RedirectStandardError "logs\stderr_wd_$stamp.txt" -WindowStyle Hidden
    Log "Run A relancé ($why) -> logs\stderr_wd_$stamp.txt"
    Notify "Test_IA - gardien : Run A relancé" "Raison : $why. Journal : logs\stderr_wd_$stamp.txt"
}

$lock = Join-Path $code "data\maintenance.lock"
if ((Test-Path $lock) -and ((Get-Item $lock).LastWriteTime -gt (Get-Date).AddMinutes(-60))) { exit 0 }

# 1) MetaTrader 5
if (-not (Get-Process terminal64 -ErrorAction SilentlyContinue)) {
    Start-Process $mt5
    Log "MetaTrader 5 était fermé -> relancé"
    Notify "Test_IA - gardien : MT5 relancé" "Le terminal MetaTrader 5 était fermé, il a été relancé."
    Start-Sleep 60
}

# 2) Run A absent
$procs = @(AgentProcs)
if ($procs.Count -eq 0) { StartAgent "processus absent"; exit 0 }

# 3) Run A figé : la boucle de trading écrit logs\heartbeat.txt à chaque tour (toutes les ~60 s)
$main = Join-Path $code "logs\heartbeat.txt"
if ((Test-Path $main) -and ((Get-Item $main).LastWriteTime -lt (Get-Date).AddMinutes(-20))) {
    $started = ($procs | Sort-Object CreationDate | Select-Object -First 1).CreationDate
    if ($started -lt (Get-Date).AddMinutes(-20)) {
        StopAgent
        Start-Sleep 5
        StartAgent "journal muet depuis plus de 20 min (processus figé)"
        exit 0
    }
}

# 3b) ENTRAÎNEMENT EN ÉCHEC (07/10/2026, après 4 h de plantages non vus) : notification téléphone, au plus une
#     fois par heure, si un même tour redémarre en boucle, si des copies d'entraînement plantent, si aucun tour
#     ne se termine depuis 2 h, ou si Windows manque de mémoire.
$flag = Join-Path $code "logs\alerte_entrainement.txt"
$recentAlert = (Test-Path $flag) -and ((Get-Item $flag).LastWriteTime -gt (Get-Date).AddMinutes(-60))
$runLog = Get-ChildItem (Join-Path $code "logs") -Filter "stderr_*.txt" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($runLog -and -not $recentAlert) {
    $tail = Get-Content $runLog.FullName -Tail 5000 -Encoding utf8
    $problem = $null
    $cycles = @($tail | Select-String "=== Cycle d'.volution continue #(\d+) ===" | ForEach-Object { $_.Matches[0].Groups[1].Value })
    if ($cycles.Count -gt 0) {
        $lastCycle = $cycles[-1]
        $n = @($cycles | Where-Object { $_ -eq $lastCycle }).Count
        if ($n -ge 3) { $problem = "le tour d'entrainement $lastCycle a redemarre $n fois (copies qui plantent)" }
    }
    $broken = @($tail | Select-String "BrokenProcessPool").Count
    if (-not $problem -and $broken -ge 2) { $problem = "$broken plantages de copies d'entrainement" }
    $started = ($procs | Sort-Object CreationDate | Select-Object -First 1).CreationDate
    # 08/10 : en mode --no-train (entraînement mis en pause volontairement), aucun tour n'est attendu
    $noTrain = @($procs | Where-Object { $_.CommandLine -like "*--no-train*" }).Count -gt 0
    if (-not $problem -and -not $noTrain -and $started -lt (Get-Date).AddHours(-2)) {
        # début du dernier tour (un tour ne démarre qu'après la fin du précédent) ; 07/10 21h : l'ancien motif
        # « champion r.valu. » ne reconnaissait jamais « réévalué » (deux lettres accentuées) -> fausse alerte
        $lastEnd = $tail | Select-String "=== Cycle d'.volution continue #" | Select-Object -Last 1
        $lastTime = $null
        if ($lastEnd) { try { $lastTime = [datetime]::ParseExact($lastEnd.Line.Substring(0, 19), "yyyy-MM-dd HH:mm:ss", $null) } catch {} }
        if (-not $lastTime -or $lastTime -lt (Get-Date).AddHours(-2)) { $problem = "aucun tour d'entrainement termine depuis plus de 2 h" }
    }
    $lowMem = Get-WinEvent -FilterHashtable @{LogName='System'; Id=2004; StartTime=(Get-Date).AddMinutes(-10)} -MaxEvents 1 -ErrorAction SilentlyContinue
    if (-not $problem -and $lowMem) { $problem = "Windows manque de memoire (memoire virtuelle insuffisante)" }
    if ($problem) {
        Set-Content -Path $flag -Value ("{0:yyyy-MM-dd HH:mm} {1}" -f (Get-Date), $problem) -Encoding utf8
        Log "ALERTE entrainement : $problem"
        Notify "Test_IA - ALERTE entrainement" "Probleme detecte : $problem. Journal : $($runLog.Name)"
    }
}

# 4) ménage : journaux de lancement de plus de 14 jours
Get-ChildItem (Join-Path $code "logs") -File -Include "stdout_*.txt","stderr_*.txt" -Recurse |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } | Remove-Item -Force -ErrorAction SilentlyContinue
