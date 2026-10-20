"""La « liquidité » de la Fed : bilan total, compte du Trésor à la Fed, prises en pension inversées (fournée 1, fiche
F006 ; 20/10/2026). Source : FRED / ALFRED (Banque fédérale de Saint-Louis, gratuit). Clé FRED lue dans la config de
Run A (comme core/taux.py), JAMAIS affichée ni écrite.

Séries (toutes rendues en MILLIONS de dollars) :
- WALCL     : bilan total de la Fed, niveau du MERCREDI (rapport H.4.1).
- WTREGEN   : compte général du Trésor à la Fed, MOYENNE de la semaine finissant le mercredi (H.4.1) — attention, ce
              n'est pas le niveau du mercredi.
- WDTGAL    : le même compte, niveau du MERCREDI (H.4.1) — ajouté pour aller avec WALCL (même jour, même nature).
- RRPONTSYD : prises en pension inversées du jour (opérations de la Fed de New York), quotidien.

PREMIÈRES PUBLICATIONS : chaque valeur est celle publiée la PREMIÈRE fois (ALFRED, `output_type=4`), quand ALFRED la
connaît : WALCL et WDTGAL depuis le 13/07/2011, WTREGEN depuis le 24/12/2008, RRPONTSYD depuis le 25/03/2016. Avant, la
valeur actuelle (révisions possibles mais petites : sur 2011-2023, WALCL 92 valeurs sur 651 révisées, toutes de
0,14 % au plus ; WTREGEN, WDTGAL : aucune ; RRPONTSYD : une, le 19/02/2020, publiée 5 149 puis corrigée à 95 milliards —
on garde 5 149, la valeur connue alors) ; colonne `premiere_publication` = False.

DATE DE PUBLICATION (`publie`, heure du serveur = New York + 7 h) :
- H.4.1 (WALCL, WTREGEN, WDTGAL) : le jeudi 16h30 New York pour le mercredi (le jour ouvré suivant si le jeudi est
  férié) ; si ALFRED date la première publication plus tard (retards de 2018 et de Noël 2020), c'est ALFRED qui compte.
- RRPONTSYD : le jour même 13h15 New York (fin de l'opération de la Fed de New York, résultats publiés aussitôt).

Fichiers : data/hors_prix/fred/<SERIE>.csv (date, valeur_actuelle, premiere_valeur, premiere_date ; millions $),
observations jusqu'au 31/12/2023 seulement.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m cerveau.donnees_hors_prix.fed_liquidite   (re-télécharge)
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import requests

from cerveau.donnees_hors_prix import DOSSIER, couper, feries_us, jour_ouvre_suivant, ny_vers_serveur

ICI = DOSSIER / "fred"
API = "https://api.stlouisfed.org/fred/series/observations"
FIN_OBS = "2023-12-31"
HEBDO = ("WALCL", "WTREGEN", "WDTGAL")              # rapport H.4.1, mercredi
SERIES = HEBDO + ("RRPONTSYD",)
HEURE_H41 = pd.Timedelta(hours=16, minutes=30)      # New York
HEURE_RRP = pd.Timedelta(hours=13, minutes=15)      # New York
# fenêtres de « temps réel » pour lire les premières publications de RRPONTSYD (ALFRED refuse plus de 2 000 versions
# par appel)
FENETRES_RRP = [("2016-03-25", "2019-12-31"), ("2020-01-01", "2023-12-31"), ("2024-01-01", "9999-12-31")]


def _cle() -> str:
    from core.taux import _cle as cle_fred
    return cle_fred()


def _lire(serie: str, cle: str, **params) -> pd.DataFrame:
    p = {"series_id": serie, "api_key": cle, "file_type": "json", "observation_end": FIN_OBS, **params}
    for essai in range(4):
        r = requests.get(API, params=p, timeout=120)
        if r.status_code == 429:
            time.sleep(20 * (essai + 1))
            continue
        if r.status_code != 200:                       # message d'erreur SANS l'adresse (elle contient la clé)
            raise RuntimeError(f"FRED {serie} : code {r.status_code} {r.json().get('error_message', '')[:200]}")
        d = pd.DataFrame(r.json()["observations"])
        if d.empty:
            return d
        d = d[d["value"] != "."].copy()
        d["date"] = pd.to_datetime(d["date"])
        d["value"] = d["value"].astype(float)
        return d
    raise RuntimeError(f"FRED {serie} : trop de refus (429)")


def telecharger():
    """Valeurs actuelles + premières publications (ALFRED), converties en millions de dollars."""
    ICI.mkdir(parents=True, exist_ok=True)
    cle = _cle()
    for s in SERIES:
        actuel = _lire(s, cle)[["date", "value"]].rename(columns={"value": "valeur_actuelle"})
        if s == "RRPONTSYD":
            morceaux = [_lire(s, cle, realtime_start=a, realtime_end=b, output_type=4) for a, b in FENETRES_RRP]
            prem = pd.concat([m for m in morceaux if not m.empty])
            # une valeur déjà publiée avant le début d'une fenêtre y réapparaît : on garde sa date la plus ancienne
            prem = prem.sort_values("realtime_start").drop_duplicates("date", keep="first")
        else:
            prem = _lire(s, cle, realtime_start="1776-07-04", realtime_end="9999-12-31", output_type=4)
        prem = prem[["date", "value", "realtime_start"]].rename(columns={"value": "premiere_valeur",
                                                                         "realtime_start": "premiere_date"})
        d = actuel.merge(prem, on="date", how="outer").sort_values("date").reset_index(drop=True)
        # unités : RRPONTSYD en milliards ; WTREGEN publié en milliards jusqu'au 12/11/2025 puis en millions
        if s == "RRPONTSYD":
            d["valeur_actuelle"] *= 1000.0
        both = d.dropna(subset=["valeur_actuelle", "premiere_valeur"])
        both = both[(both["premiere_valeur"] != 0) & (both["valeur_actuelle"] != 0)]
        rapport = float(np.median(both["valeur_actuelle"] / both["premiere_valeur"])) if len(both) else 1.0
        echelle = 1000.0 if 500 < rapport < 2000 else 1.0
        if not (0.9 < rapport / echelle < 1.1):
            raise ValueError(f"{s} : unités incohérentes (rapport {rapport:.3f})")
        d["premiere_valeur"] *= echelle
        d.to_csv(ICI / f"{s}.csv", index=False)
        n_prem = int(d["premiere_valeur"].notna().sum())
        print(f"{s} : {len(d)} valeurs {d['date'].min():%Y-%m-%d} -> {d['date'].max():%Y-%m-%d}, "
              f"premières publications {n_prem} (unités x{echelle:g})", flush=True)


def _publication(serie: str, d: pd.DataFrame) -> pd.Series:
    """Instant de publication, heure de New York (sans fuseau)."""
    if serie == "RRPONTSYD":
        return d["date"] + HEURE_RRP
    fer = set(feries_us("2002-01-01", "2026-12-31"))
    regle = pd.DatetimeIndex([jour_ouvre_suivant(x, fer) for x in d["date"]])
    alfred = pd.to_datetime(d["premiere_date"])
    jour = pd.Series(regle, index=d.index).where(~(alfred > regle), alfred)
    return jour + HEURE_H41


def charger(serie: str, limite=None) -> pd.DataFrame:
    """Une série : date (mesurée), valeur (millions $), premiere_publication, publie (heure du serveur), serie.
    Rien de publié à partir de `limite` (défaut et maximum : 2024-01-01)."""
    if serie not in SERIES:
        raise ValueError(f"série inconnue {serie} (connues : {SERIES})")
    f = ICI / f"{serie}.csv"
    if not f.exists():
        raise FileNotFoundError(f"{f} : lancer python -m cerveau.donnees_hors_prix.fed_liquidite")
    d = pd.read_csv(f, parse_dates=["date"])
    d["premiere_publication"] = d["premiere_valeur"].notna()
    d["valeur"] = d["premiere_valeur"].where(d["premiere_publication"], d["valeur_actuelle"])
    d = d[d["valeur"].notna()].reset_index(drop=True)
    d["publie"] = ny_vers_serveur(_publication(serie, d))
    d["serie"] = serie
    return couper(d[["date", "publie", "valeur", "premiere_publication", "serie"]], limite)


def charger_tout(limite=None) -> pd.DataFrame:
    """Les 4 séries empilées (colonne `serie`), triées par instant de publication."""
    return couper(pd.concat([charger(s, limite) for s in SERIES], ignore_index=True), limite)


if __name__ == "__main__":
    telecharger()
