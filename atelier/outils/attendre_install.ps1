param([string]$Marker, [int]$Minutes = 100)
# Attend la fin de la DERNIÈRE installation programmée (lignes après la dernière « attente des tests préparés ») :
# sortie 0 = installée (FIN), 2 = ABANDON (tests en échec ou délai) ; affiche les lignes concernées.
$s = "C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code\logs\boundary_apply_status.txt"
$deadline = (Get-Date).AddMinutes($Minutes)
while ((Get-Date) -lt $deadline) {
    $lines = @(Get-Content $s -Encoding utf8)
    $start = -1
    for ($k = 0; $k -lt $lines.Count; $k++) { if ($lines[$k] -like "*attente des tests pr*") { $start = $k } }
    if ($start -ge 0) {
        $tail = $lines[$start..($lines.Count - 1)]
        if (($tail | Where-Object { $_ -like "*ABANDON*" }).Count -gt 0) { $tail; exit 2 }
        if ((($tail | Where-Object { $_ -like "*$Marker*" }).Count -gt 0) -and (($tail | Where-Object { $_ -match " FIN$" }).Count -gt 0)) { $tail; exit 0 }
    }
    Start-Sleep 30
}
"DÉLAI DÉPASSÉ"
exit 2
