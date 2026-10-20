"""QUELLES HABITUDES ANNONCENT UN TRADER QUI RESTE BON ? (15/10/2026)

Pour chaque trader (au moins 100 trades), on mesure ses habitudes sur la PREMIÈRE moitié de son historique (levier,
durée de tenue, part de gagnants, gain moyen / perte moyenne, liquidations, sorties sur stop, nombre de marchés,
trades par jour…) et sa force sur la SECONDE moitié (gain rapporté à la taille, maitres/persistance.py).
Lien de rang (Spearman) entre chaque habitude et la force future, avec sa force statistique (lien x racine(n)) ;
puis la même chose à force passée égale (on retire ce que la force passée explique déjà).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.maitres.habitudes
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from collapsar.donnees.marches import RACINE
from collapsar.maitres.trades import lire_tous

MIN_TRADES = 100


def _force(x: pd.Series) -> float:
    s = float((x ** 2).sum())
    return float(x.sum() / np.sqrt(s)) if s > 0 else 0.0


def habitudes(a: pd.DataFrame) -> dict:
    r = a["gain"] / a["volume"]
    duree = (pd.to_datetime(a["fin"]) - pd.to_datetime(a["debut"])).dt.total_seconds() / 3600
    jours = max((pd.to_datetime(a["fin"]).max() - pd.to_datetime(a["debut"]).min()).days, 1)
    g, p = r[r > 0], r[r < 0]
    return {"force_passee": _force(r), "levier": float(a["levier"].median()) if "levier" in a else np.nan,
            "duree_mediane_h": float(duree.median()), "gagnants_pct": float((r > 0).mean() * 100),
            "gain_sur_perte": float(g.mean() / -p.mean()) if len(g) and len(p) else np.nan,
            "liquides_pct": float(a["liquide"].fillna(False).astype(float).mean() * 100) if "liquide" in a else np.nan,
            "sorties_sur_stop_pct": float(a["stop"].notna().mean() * 100),
            "sorties_sur_objectif_pct": float(a["objectif"].notna().mean() * 100),
            "marches": float(a["marche"].nunique()), "trades_par_jour": float(len(a) / jours),
            "achats_pct": float((a["sens"] > 0).mean() * 100),
            "metaux_petrole_pct": float(a["marche"].isin(["XAUUSD", "XAGUSD", "LIGHTCMDUSD", "BRENTCMDUSD"]).mean() * 100)}


def main():
    t = lire_tous().dropna(subset=["gain", "volume"])
    t = t[t["volume"] > 0].sort_values("fin")
    lignes = []
    for maitre, g in t.groupby("maitre"):
        if len(g) < MIN_TRADES:
            continue
        a, b = g.iloc[: len(g) // 2], g.iloc[len(g) // 2:]
        lignes.append({"maitre": maitre, "source": g["source"].iloc[0], **habitudes(a),
                       "force_future": _force(b["gain"] / b["volume"])})
    m = pd.DataFrame(lignes)
    n = len(m)
    rangs = m.drop(columns=["maitre", "source"]).rank()
    res = {}
    # à force passée égale : on retire de chaque habitude et de la force future la part expliquée par la force passée
    def residu(col):
        x, y = rangs["force_passee"], rangs[col]
        return y - np.polyval(np.polyfit(x, y, 1), x)
    fut_res = residu("force_future")
    for col in rangs.columns:
        if col == "force_future":
            continue
        ok = rangs[col].notna()
        lien = float(rangs.loc[ok, col].corr(rangs.loc[ok, "force_future"]))
        lien_res = float(residu(col)[ok].corr(fut_res[ok])) if col != "force_passee" else float("nan")
        res[col] = {"lien": round(lien, 3), "force": round(lien * np.sqrt(ok.sum()), 1),
                    "lien_a_force_passee_egale": round(lien_res, 3),
                    "force_a_force_passee_egale": round(lien_res * np.sqrt(ok.sum()), 1)}
    f = RACINE / "collapsar" / "vie" / "ecole_maitres" / "habitudes.json"
    f.write_text(json.dumps({"traders": n, "liens": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    m.to_csv(f.with_suffix(".csv"), index=False)
    print(f"{n} traders (>= {MIN_TRADES} trades) ; lien de rang avec la force FUTURE :")
    for col, r in sorted(res.items(), key=lambda kv: -abs(kv[1]["force"])):
        print(f"  {col:26s} lien {r['lien']:+.3f} (force {r['force']:+.1f})   à force passée égale "
              f"{r['lien_a_force_passee_egale']:+.3f} (force {r['force_a_force_passee_egale']:+.1f})")
    print(f"(enregistré : {f})")


if __name__ == "__main__":
    main()
