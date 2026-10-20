param([string]$Until = "08:15")
# Sentinelle : s'arrête (et réveille Claude) au premier problème, sinon à l'heure $Until (le lendemain si déjà passée).
$code = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
$end = [datetime]::Today.Add([timespan]::Parse($Until)); if ($end -lt (Get-Date)) { $end = $end.AddDays(1) }
$start = Get-Date
$seen = $null
while ((Get-Date) -lt $end) {
    $log = (Get-ChildItem "$code\logs\stderr_*.txt" | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
    $bad = Select-String -Path $log -Pattern "Erreur pendant le cycle|BrokenProcess|MemoryError|out of memory|OutOfMemory" -Encoding utf8 |
        Where-Object { $_.Line.Length -ge 19 -and ([datetime]::ParseExact($_.Line.Substring(0,19), "yyyy-MM-dd HH:mm:ss", $null) -gt $start) }
    if ($bad) { "PROBLÈME (cycle) : " + ($bad | Select-Object -Last 1).Line; exit 2 }
    $last = Select-String -Path (Get-ChildItem "$code\logs\stderr_*.txt" | Sort-Object LastWriteTime | Select-Object -Last 3 | ForEach-Object FullName) -Pattern "Cycle d'.volution continue #" -Encoding utf8 | Select-Object -Last 1
    if ($last) { $t = [datetime]::ParseExact($last.Line.Substring(0,19), "yyyy-MM-dd HH:mm:ss", $null)
        if ((Get-Date) - $t -gt [timespan]::FromMinutes(50)) { "PROBLÈME : aucun nouveau cycle depuis $([int]((Get-Date) - $t).TotalMinutes) min"; exit 2 } }
    $os = Get-CimInstance Win32_OperatingSystem
    if ($os.FreeVirtualMemory / 1MB -lt 1.5) { "PROBLÈME : mémoire virtuelle libre {0:N1} Go" -f ($os.FreeVirtualMemory / 1MB); exit 2 }
    $alive = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*autonomous_agent*" } | Measure-Object).Count
    if ($alive -eq 0) { Start-Sleep 600; if ((Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*autonomous_agent*" } | Measure-Object).Count -eq 0) { "PROBLÈME : entraînement arrêté depuis plus de 10 min"; exit 2 } }
    # 10/10 : carte graphique inutilisée pendant l'apprentissage (incident de 13h46 : cycle 2x plus lent)
    $tr = Select-String -Path $log -Pattern "Entraînement de \d+ candidats" -Encoding utf8 | Select-Object -Last 1
    if ($tr) { $tt = [datetime]::ParseExact($tr.Line.Substring(0,19), "yyyy-MM-dd HH:mm:ss", $null)
        $age = ((Get-Date) - $tt).TotalMinutes
        if ($age -gt 2 -and $age -lt 9 -and $tt -gt $start) {
            $mem = [int]((& "C:\Windows\System32\nvidia-smi.exe" --query-gpu=memory.used --format=csv,noheader,nounits) | Select-Object -First 1)
            if ($mem -lt 800) { "PROBLÈME : la carte graphique n'est pas utilisée pendant l'apprentissage ($mem Mo)"; exit 2 } } }
    $d = "$code\logs\aurexis_direct.txt"
    if (Test-Path $d) { $tb = (Select-String -Path $d -Pattern "Traceback" -Encoding utf8 | Measure-Object).Count
        if ($null -eq $seen) { $seen = $tb } elseif ($tb -gt $seen) { "PROBLÈME : erreur dans AUREXIS à blanc"; exit 2 } }
    Start-Sleep 120
}
"OK : aucun problème détecté jusqu'à $Until"
exit 0
