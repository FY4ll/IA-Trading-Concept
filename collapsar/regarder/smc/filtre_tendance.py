"""Stratégie du chef de projet (« Gigogne H4 stop A plancher 0.2 ») + FILTRE DE TENDANCE DE FOND.
On ne garde que les trades dans le sens de la tendance des N derniers jours (fermés avant l'entrée).
Filtres figés d'avance : 20 / 60 / 120 jours, et « les trois d'accord ».
Choix 2015-2021, vérification 2022-2023 ; 2024-2026 déjà vue pour cette stratégie (donnée à titre indicatif).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.smc.filtre_tendance
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.regarder.smc.labo import VIE, note

SOURCE = VIE / "strategie_chef_trades_REPRISE_controle.csv"
NOMS_45 = {"NAS100": "USATECHIDXUSD", "US500": "USA500IDXUSD"}
DUREES = (20, 60, 120)
PERIODES = {"2015-2021 (choix)": (2015, 2021), "2022-2023 (vérif.)": (2022, 2023), "2024-2026 (déjà vue)": (2024, 2026)}


def clotures_jour(sym: str) -> pd.Series:
    df = dm.charger(sym, pd.Timestamp("2100-01-01"))
    return df.set_index(pd.to_datetime(df["time"]))["close"].resample("1D").last().dropna()


def tendances(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    t["entree"] = pd.to_datetime(t["entree"])
    for n in DUREES:
        t[f"t{n}"] = 0
    for m, g in t.groupby("marche"):
        c = clotures_jour(NOMS_45.get(m, m))
        jours = c.index.values
        for n in DUREES:
            k = np.searchsorted(jours, g["entree"].dt.normalize().values) - 1     # dernier jour FERMÉ avant l'entrée
            ok = k - n >= 0
            s = np.zeros(len(g))
            s[ok] = np.sign(c.values[k[ok]] - c.values[k[ok] - n])
            t.loc[g.index, f"t{n}"] = s
    return t


def ligne(g: pd.DataFrame) -> dict:
    x = note(g)
    if len(g) >= 20:
        r = g["R"].sort_values()
        x["R_median"] = float(r.median())
        x["R_sans_5_meilleurs"] = float(r.iloc[:-5].mean())
    return x


def main():
    t = tendances(pd.read_csv(SOURCE))
    filtres = {"sans filtre": np.ones(len(t), bool)}
    for n in DUREES:
        filtres[f"avec tendance {n} j"] = (t["sens"] == t[f"t{n}"]).values
        filtres[f"CONTRE tendance {n} j"] = (t["sens"] == -t[f"t{n}"]).values
    filtres["avec les 3 d'accord"] = ((t["sens"] == t["t20"]) & (t["sens"] == t["t60"]) & (t["sens"] == t["t120"])).values
    res = []
    an = t["entree"].dt.year
    for groupe, gg in t.groupby("groupe"):
        for nom, f in filtres.items():
            for p, (a, z) in PERIODES.items():
                g = t[f & (t["groupe"] == groupe).values & ((an >= a) & (an <= z)).values]
                x = ligne(g)
                res.append({"groupe": groupe, "filtre": nom, "periode": p, **x})
    r = pd.DataFrame(res)
    r.to_csv(VIE / "filtre_tendance_strategie_chef.csv", index=False)
    pd.set_option("display.width", 250)
    cols = ["groupe", "filtre", "periode", "trades", "R_moyen", "R_median", "R_sans_5_meilleurs", "gagnants_pct",
            "force"]
    print(r[[c for c in cols if c in r]].round(3).to_string())


if __name__ == "__main__":
    main()
