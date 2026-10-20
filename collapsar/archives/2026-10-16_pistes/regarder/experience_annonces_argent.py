"""Expérience du 14/10 : la dérive après surprise économique, en ARGENT.

Chaque annonce importante avec une surprise forte (|z| > seuil) = UN coup, réparti à parts égales sur toutes les
paires de devises qui contiennent la devise de l'annonce (dans le sens « surprise bonne pour la devise ») ; entrée à la
clôture de la bougie de l'annonce, sortie un jour plus tard ou avant le week-end (règle FTMO), frais réels.
Risque : 0,5 % du compte par « journée d'agitation » de mouvement du coup (une journée habituelle contre nous = -0,5 %).
Aucun réglage n'est fait sur les années jugées (seuil fixé à l'avance, comparé à titre d'information).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.experience_annonces_argent
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from collapsar.donnees import calendrier
from collapsar.donnees import marches as dm
from collapsar.mains.fiches import DEVISES, fiche

RISQUE = 0.005
JOUR = 96
PERIODES = {"2010-2019": ("2010", "2020"), "2020-2022": ("2020", "2023"), "2023-04/2025": ("2023", "2025-04-08")}


def main():
    cal = calendrier.charger()
    cal = cal[(cal["importance"] == "High") & cal["z"].notna()].reset_index(drop=True)
    cal["id"] = np.arange(len(cal))
    coups = []
    for m in dm.liste_marches():
        if not (len(m) == 6 and m[:3] in DEVISES and m[3:] in DEVISES):
            continue
        df = dm.charger(m, jusqua=dm.FIN_EXAMEN)
        if len(df) < 10_000:
            continue
        t = df["time"].values.astype("datetime64[ns]")
        o, h, l, c = (np.log(df[k].to_numpy(np.float64)) for k in ("open", "high", "low", "close"))
        u = pd.Series(h - l).rolling(64, min_periods=16).mean().shift(1).to_numpy()
        # fermeture forcée : dernière bougie avant une pause de plus de 2 h (week-end)
        pause = np.r_[(t[1:] - (t[:-1] + np.timedelta64(15, "m"))) > np.timedelta64(2, "h"), True]
        fins = np.flatnonzero(pause)
        frais = fiche(m).frais
        for cote, dev in ((1.0, m[:3]), (-1.0, m[3:])):
            ev = cal[cal["devise"] == dev]
            i = np.searchsorted(t, ev["temps"].values.astype("datetime64[ns]"), side="right") - 1
            ok = (i >= 64) & (i < len(t) - JOUR - 1)
            ok &= (ev["temps"].values.astype("datetime64[ns]") - t[np.clip(i, 0, None)]) < np.timedelta64(15, "m")
            for (_, e), k in zip(ev[ok].iterrows(), i[ok]):
                if not np.isfinite(u[k]) or u[k] <= 0:
                    continue
                prochaine = fins[np.searchsorted(fins, k, side="left")]
                if prochaine == k:
                    continue
                sortie = min(k + JOUR, prochaine)
                agit_jour = u[k] * np.sqrt(JOUR)
                mouvement = cote * np.sign(e["z"]) * (c[sortie] - c[k]) / agit_jour
                coups.append({"id": e["id"], "temps": e["temps"], "devise": dev, "z": e["z"],
                              "gain": mouvement - frais / agit_jour})
    x = pd.DataFrame(coups)
    for seuil in (0.5, 1.0, 1.5, 2.0):
        par_annonce = x[x["z"].abs() > seuil].groupby("id").agg(temps=("temps", "first"), gain=("gain", "mean"),
                                                                devise=("devise", "first"))
        print(f"\nsurprises > {seuil} fois la taille habituelle :")
        for nom, (de, a) in PERIODES.items():
            p = par_annonce[(par_annonce["temps"] >= de) & (par_annonce["temps"] < a)]
            mois = (p.set_index("temps")["gain"] * RISQUE * 100).groupby(pd.Grouper(freq="ME")).sum()
            cumul = mois.cumsum()
            print(f"   {nom:13s} : {len(p) / max(1, len(mois)):4.1f} coups/mois, gain moyen {p['gain'].mean():+.3f}, "
                  f"gagnants {(p['gain'] > 0).mean():.0%} | {mois.mean():+.2f} %/mois, mois positifs "
                  f"{(mois > 0).mean():.0%}, pire mois {mois.min():+.2f} %, baisse max {(cumul.cummax() - cumul).max():.1f} %")


if __name__ == "__main__":
    main()
