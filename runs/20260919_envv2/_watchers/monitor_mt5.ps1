$logPath = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\mt5_watch.log"
$scriptPath = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\_watchers\_mt5_snapshot.py"

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    try {
        $output = & "C:\Users\utilisateur\AppData\Local\Programs\Python\Python311\python.exe" $scriptPath 2>$null
        if ($output) {
            Add-Content -Path $logPath -Value "$timestamp | $output" -Encoding utf8
        } else {
            Add-Content -Path $logPath -Value "$timestamp | MT5_SNAPSHOT_VIDE" -Encoding utf8
        }
    } catch {
        Add-Content -Path $logPath -Value "$timestamp | MT5_SNAPSHOT_ERREUR: $_" -Encoding utf8
    }
    Start-Sleep -Seconds 1200
}
