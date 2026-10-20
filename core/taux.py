"""Les taux d'intérêt à 3 mois des 8 grandes devises, mois par mois (OECD via FRED), pour des frais de nuit FIDÈLES
à chaque époque (15/10/2026).

Pourquoi : les frais de nuit d'un CFD suivent les taux d'intérêt (devises : écart de taux entre les deux devises ;
indices, or, pétrole : taux de la devise de cotation), plus la marge du courtier. Appliquer aux années 2010-2019
(taux proches de zéro) les frais relevés en 2026 (taux élevés) surfacturait lourdement le fait de garder une position
plusieurs jours (mesure du 15/10 : la tendance de 60 jours, +0,4 de rapport gain/agitation avant frais sur 23 marchés,
tombait à -0,6 avec ces frais de nuit).
Clé FRED lue dans la config de Run A (fred.api_key), jamais affichée. Fichiers : data/taux/<DEVISE>.csv.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m core.taux   (core, 20/10/2026 : copie de collapsar/donnees/taux.py)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests
import yaml

from core.donnees import RACINE

DOSSIER = RACINE / "data" / "taux"
SERIES = {"USD": "IR3TIB01USM156N", "EUR": "IR3TIB01EZM156N", "JPY": "IR3TIB01JPM156N", "GBP": "IR3TIB01GBM156N",
          "CHF": "IR3TIB01CHM156N", "AUD": "IR3TIB01AUM156N", "CAD": "IR3TIB01CAM156N", "NZD": "IR3TIB01NZM156N"}
CONFIGS = [RACINE / "runs" / "20260919_envv2" / "code" / "config" / "autonomous.yaml",
           RACINE / "runs" / "20260919_envv2" / "run_config_A.yaml"]


def _cle() -> str:
    for f in CONFIGS:
        try:
            cfg = yaml.safe_load(Path(f).read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        cle = (cfg.get("fred") or {}).get("api_key")
        if cle:
            return cle
    raise RuntimeError("pas de clé FRED dans la config")


def telecharger():
    DOSSIER.mkdir(parents=True, exist_ok=True)
    cle = _cle()
    for devise, serie in SERIES.items():
        r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                         params={"series_id": serie, "api_key": cle, "file_type": "json",
                                 "observation_start": "1999-01-01"}, timeout=60)
        r.raise_for_status()
        obs = r.json()["observations"]
        df = pd.DataFrame({"date": [o["date"] for o in obs], "taux_pct": [o["value"] for o in obs]})
        df = df[df["taux_pct"] != "."]
        df.to_csv(DOSSIER / f"{devise}.csv", index=False)
        print(f"{devise} : {len(df)} mois, {df['date'].iloc[0]} -> {df['date'].iloc[-1]}", flush=True)


def charger() -> pd.DataFrame:
    """Taux à 3 mois en part annuelle (0,05 = 5 %), une colonne par devise, un jour par ligne (valeur du mois
    PRÉCÉDENT, publiée : jamais l'avenir)."""
    cols = {}
    for devise in SERIES:
        f = DOSSIER / f"{devise}.csv"
        if not f.exists():
            raise FileNotFoundError(f"{f} : lancer python -m core.taux")
        d = pd.read_csv(f, parse_dates=["date"]).set_index("date")["taux_pct"].astype(float) / 100
        cols[devise] = d
    mois = pd.DataFrame(cols).sort_index().ffill()
    jours = pd.date_range(mois.index[0], pd.Timestamp.today().normalize() + pd.Timedelta(days=1), freq="D")
    return mois.shift(1).reindex(jours, method="ffill")


if __name__ == "__main__":
    telecharger()
