# Lance le relevé des vrais frais FTMO (7 jours) dès que le chef de projet a écrit Test_IA\.env. Tâche Windows
# « TestIA_ReleveFraisFTMO », toutes les heures. Ne fait rien si .env manque, si le relevé tourne déjà ou s'il est fini.
$racine = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $racine 'venv_gpu\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'releve.py'
$fini = Join-Path $PSScriptRoot 'resultats\FINI.txt'
if (-not (Test-Path (Join-Path $racine '.env'))) { exit 0 }
if (Test-Path $fini) { exit 0 }
$enCours = Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'frais_ftmo_reels\\releve.py' }
if ($enCours) { exit 0 }
$logs = Join-Path $PSScriptRoot 'journaux'
New-Item -ItemType Directory -Force $logs | Out-Null
$h = Get-Date -Format 'yyyyMMdd_HHmm'
$env:CUDA_VISIBLE_DEVICES = '-1'
Start-Process -FilePath $python -ArgumentList '-u', "`"$script`"", '--jours', '7' -WorkingDirectory $racine `
    -RedirectStandardOutput (Join-Path $logs "releve_$h.txt") -RedirectStandardError (Join-Path $logs "releve_${h}_erreurs.txt") -WindowStyle Hidden
