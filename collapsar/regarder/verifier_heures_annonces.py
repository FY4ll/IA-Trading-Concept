"""Vérification des heures du calendrier : à quelle bougie (décalage en bougies de 15 min par rapport à l'heure
annoncée) le prix réagit-il à la surprise ? Par année et par saison (heure d'été / d'hiver). La réaction doit être
au décalage 0 ; sinon les heures du fichier sont fausses pour cette période.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.verifier_heures_annonces
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from collapsar.donnees import calendrier
from collapsar.donnees import marches as dm

DECALAGES = range(-8, 9)
PAIRES = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "USDCHF")


def main():
    import os
    cal = calendrier.charger_mt5() if os.environ.get("COLLAPSAR_CALENDRIER", "ff") == "mt5" else calendrier.charger()
    cal = cal[(cal["importance"] == "High") & cal["z"].notna()]
    lignes = []
    for m in PAIRES:
        df = dm.charger(m, jusqua=dm.FIN_EXAMEN)
        t = df["time"].values.astype("datetime64[ns]")
        o, c = np.log(df["open"].to_numpy()), np.log(df["close"].to_numpy())
        r = c - o
        for cote, dev in ((1.0, m[:3]), (-1.0, m[3:])):
            ev = cal[cal["devise"] == dev]
            i = np.searchsorted(t, ev["temps"].values.astype("datetime64[ns]"), side="right") - 1
            ok = (i > 10) & (i < len(t) - 10)
            for (_, e), k in zip(ev[ok].iterrows(), i[ok]):
                lignes.append({"temps": e["temps"], "z": cote * e["z"],
                               **{d: r[k + d] / (np.abs(r[k - 64:k]).mean() + 1e-12) for d in DECALAGES}})
    x = pd.DataFrame(lignes)
    x["annee"] = x["temps"].dt.year
    x["ete"] = x["temps"].dt.month.between(4, 10)
    for (an, ete), p in x.groupby(["annee", "ete"]):
        liens = {d: np.corrcoef(p["z"], p[d])[0, 1] * 100 for d in DECALAGES}
        pic = max(liens, key=lambda d: liens[d])
        print(f"{an} {'été ' if ete else 'hiver'} ({len(p):4d}) : réaction maximale au décalage {pic:+d} bougie(s) "
              f"({liens[pic]:+.0f} %) | décalage 0 : {liens[0]:+.0f} % | +4 : {liens[4]:+.0f} % | -4 : {liens[-4]:+.0f} %",
              flush=True)


if __name__ == "__main__":
    main()
