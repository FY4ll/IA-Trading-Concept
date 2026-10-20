"""Expérience du 14/10 : après une SURPRISE économique, le prix continue-t-il dans le même sens APRÈS les 15 premières
minutes (là où on peut encore entrer) ?

Pour chaque annonce importante chiffrée et chaque paire de devises qui la contient : la surprise z (dans le sens
« bon pour la devise ») contre
- la réaction pendant la bougie de 15 min de l'annonce (instantanée : NON tradable, sert à vérifier les heures) ;
- la suite APRÈS la clôture de cette bougie : 15 min, 1 h, 4 h, 1 jour (tradable).
Mouvements en « agitations » (taille habituelle de bougie x racine du nombre de bougies). Périodes : 2010-2019,
2020-2022, 2023 -> 04/2025 (fin des données du calendrier).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.experience_annonces
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from collapsar.donnees import calendrier
from collapsar.donnees import marches as dm
from collapsar.mains.fiches import DEVISES, fiche

SUITES = {"15 min": 1, "1 h": 4, "4 h": 16, "1 jour": 96}
PERIODES = {"2010-2019": ("2010", "2020"), "2020-2022": ("2020", "2023"), "2023-04/2025": ("2023", "2025-05"),
            "2023-09/2025": ("2023", "2025-10")}


def main():
    import os
    cal = calendrier.charger_mt5() if os.environ.get("COLLAPSAR_CALENDRIER", "ff") == "mt5" else calendrier.charger()
    print(f"{len(cal):,} annonces chiffrées, dont {cal['z'].notna().sum():,} avec surprise mesurable".replace(",", " "))
    lignes = []
    for m in dm.liste_marches():
        if not (len(m) == 6 and m[:3] in DEVISES and m[3:] in DEVISES):
            continue
        df = dm.charger(m, jusqua=dm.FIN_EXAMEN)
        if len(df) < 10_000:
            continue
        t = df["time"].values.astype("datetime64[ns]")
        o, h, l, c = (np.log(df[k].to_numpy(np.float64)) for k in ("open", "high", "low", "close"))
        u = pd.Series(h - l).rolling(64, min_periods=16).mean().shift(1).to_numpy()      # avant l'annonce
        frais = fiche(m).frais
        for cote, dev in ((1.0, m[:3]), (-1.0, m[3:])):
            ev = cal[(cal["devise"] == dev) & (cal["importance"] == "High") & cal["z"].notna()]
            i = np.searchsorted(t, ev["temps"].values.astype("datetime64[ns]"), side="right") - 1
            dedans = (i >= 0) & (i < len(t) - 100)
            ev, i = ev[dedans], i[dedans]
            # l'annonce doit tomber DANS la bougie trouvée (sinon marché fermé à ce moment-là)
            dans = (ev["temps"].values.astype("datetime64[ns]") - t[i]) < np.timedelta64(15, "m")
            ev, i = ev[dans], i[dans]
            for (_, e), k in zip(ev.iterrows(), i):
                if not np.isfinite(u[k]) or u[k] <= 0:
                    continue
                ligne = {"marche": m, "temps": e["temps"], "annonce": f"{dev} {e['annonce']}",
                         "z": cote * e["z"], "reaction": (c[k] - o[k]) / u[k], "frais": frais / u[k]}
                for nom, n in SUITES.items():
                    ligne[nom] = (c[k + n] - c[k]) / (u[k] * np.sqrt(n))
                lignes.append(ligne)
    r = pd.DataFrame(lignes)
    print(f"{len(r):,} réactions mesurées sur {r['marche'].nunique()} paires".replace(",", " "))
    for periode, (de, a) in PERIODES.items():
        p = r[(r["temps"] >= de) & (r["temps"] < a)]
        print(f"\n{periode} ({len(p):,} cas) — lien surprise / mouvement :".replace(",", " "))
        print(f"   pendant la bougie de l'annonce (non tradable) : {np.corrcoef(p['z'], p['reaction'])[0, 1] * 100:+.1f} %")
        for nom in SUITES:
            print(f"   APRÈS, sur {nom:7s} : {np.corrcoef(p['z'], p[nom])[0, 1] * 100:+.2f} %")
        # le coup simple : suivre la surprise forte (|z| > 1) pendant 1 h et 4 h, frais compris
        fort = p[p["z"].abs() > 1]
        for nom in ("1 h", "4 h", "1 jour"):
            n = SUITES[nom]
            gain = np.sign(fort["z"]) * fort[nom] * np.sqrt(n) - fort["frais"]
            print(f"   suivre une surprise forte {nom} : {len(fort)} cas, gain moyen {gain.mean():+.3f} taille "
                  f"de bougie par coup (frais compris), gagnants {(gain > 0).mean():.0%}")
        # par seuil de surprise, sur 1 jour, en multiples d'un risque d'« un jour d'agitation » (stop virtuel)
        for seuil in (0.5, 1.0, 2.0):
            s = p[p["z"].abs() > seuil]
            g1 = np.sign(s["z"]) * s["1 jour"] - s["frais"] / np.sqrt(96)
            par_an = len(s) / max(1e-9, (s["temps"].max() - s["temps"].min()).days / 365.25)
            print(f"   |surprise| > {seuil} : {len(s)} cas ({par_an:.0f}/an), gain moyen sur 1 jour {g1.mean():+.3f} "
                  f"agitation-jour par coup, gagnants {(g1 > 0).mean():.0%}")
        # par devise de l'annonce (d'où vient l'effet ?)
        if periode != "2010-2019":
            s = p[p["z"].abs() > 1].copy()
            s["g"] = np.sign(s["z"]) * s["1 jour"]
            s["dev"] = s["annonce"].str[:3]
            print("   par devise (|surprise| > 1, 1 jour) : " + ", ".join(
                f"{d} {v:+.2f} ({n})" for d, (v, n) in s.groupby("dev")["g"].agg(["mean", "size"]).iterrows()))


if __name__ == "__main__":
    main()
