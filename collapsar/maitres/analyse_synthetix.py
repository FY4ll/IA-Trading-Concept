"""QUI SONT LES VRAIS TRADERS DE SYNTHETIX ? (19/10/2026)

Lit tous les trades collectés (maitres/synthetix.py, format commun trades.lire_synthetix) et :
1. statistiques par marché (comme pour Ostium) : traders, trades, dates, durées, part d'achats, liquidations,
   levier, part des trades avec un stop connu ;
2. profil de chaque trader (un compte = un trader ; V1 et V2 sont des comptes différents) ;
3. filtre « durable » : (≥ 100 trades ou ≥ 6 mois d'activité), au moins 30 trades, durée médiane ≥ 2 h,
   pas de martingale (≤ 85 % de gagnants et gain moyen ≥ 0,3 fois la perte moyenne), ≤ 3 % de liquidations ;
4. le juge du projet sur les durables : force contre son jumeau (chaque trade pris dans l'autre sens), gain
   rapporté à la taille du trade ; persistance sur deux moitiés dans le temps ; origine de l'avantage sur nos vrais
   prix (sens à 1 jour, « moment au-delà du penchant » acheteur/vendeur, sortie contre sortie au hasard) ; part du
   gain faite par les achats.
Écrit collapsar/vie/maitres_synthetix/ (traders.csv, candidats.csv, resultats.json).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.maitres.analyse_synthetix
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from collapsar.donnees.marches import RACINE
from collapsar.maitres.persistance import bilan, moities
from collapsar.maitres.synthetix import DOSSIER
from collapsar.maitres.trades import lire_synthetix

SORTIE = RACINE / "collapsar" / "vie" / "maitres_synthetix"


def _force(x: pd.Series) -> float:
    x = x.dropna()
    s = float((x ** 2).sum())
    return float(x.sum() / np.sqrt(s)) if s > 0 else 0.0


def tous_les_trades() -> pd.DataFrame:
    morceaux = [lire_synthetix(f) for f in sorted(DOSSIER.glob("evenements_*.csv"))]
    t = pd.concat([m for m in morceaux if len(m)], ignore_index=True)
    t["duree_h"] = (t["fin"] - t["debut"]).dt.total_seconds() / 3600
    t["rendement"] = t["gain"] / t["volume"].where(t["volume"] > 0)          # gain en part de la taille du trade
    return t


def par_marche(t: pd.DataFrame) -> pd.DataFrame:
    lignes = []
    for m, g in t.groupby("marche"):
        lignes.append({"marche": m, "traders": g["maitre"].nunique(), "trades": len(g),
                       "debut": str(g["debut"].min())[:10], "fin": str(g["fin"].max())[:10],
                       "duree_mediane_h": g["duree_h"].median(), "moins_de_4h_pct": (g["duree_h"] < 4).mean() * 100,
                       "achats_pct": (g["sens"] > 0).mean() * 100, "liquides_pct": g["liquide"].mean() * 100,
                       "levier_median": g["levier"].median(), "avec_stop_pct": g["stop"].notna().mean() * 100,
                       "sortie_stop_pct": (g["sortie"] == "stop").mean() * 100,
                       "taille_totale_M$": g["volume"].sum() / 1e6, "gain_total_k$": g["gain"].sum() / 1e3,
                       "gagnants_trades_pct": (g["gain"] > 0).mean() * 100,
                       "traders_gagnants_pct": (g.groupby("maitre")["gain"].sum() > 0).mean() * 100})
    return pd.DataFrame(lignes)


def profil(g: pd.DataFrame) -> dict:
    g = g.sort_values("fin")
    net, r = g["gain"], g["rendement"]
    gagn, perd = net[net > 0], net[net < 0]
    a, b = g.iloc[: len(g) // 2], g.iloc[len(g) // 2:]
    achats, ventes = g[g["sens"] > 0], g[g["sens"] < 0]
    mois = (g["fin"].max() - g["debut"].min()).days / 30.4
    return {"trades": len(g), "debut": str(g["debut"].min())[:10], "fin": str(g["fin"].max())[:10],
            "mois": round(mois, 1), "mois_actifs": int(g["debut"].dt.to_period("M").nunique()),
            "marches": ",".join(f"{k[:3]}:{v}" for k, v in g["marche"].value_counts().items()),
            "duree_mediane_h": float(g["duree_h"].median()), "achats_pct": float((g["sens"] > 0).mean() * 100),
            "gagnants_pct": float((net > 0).mean() * 100),
            "gain_moyen_sur_perte_moyenne": float(gagn.mean() / -perd.mean()) if len(gagn) and len(perd) else np.nan,
            "liquides_pct": float(g["liquide"].mean() * 100), "levier_median": float(g["levier"].median()),
            "avec_stop_pct": float(g["stop"].notna().mean() * 100),
            "marge_mediane_$": float(g["marge_entree"].median()), "taille_mediane_$": float(g["volume"].median()),
            "gain_net_$": float(net.sum()), "gain_achats_$": float(achats["gain"].sum()),
            "gain_ventes_$": float(ventes["gain"].sum()),
            "rendement_moyen_pct": float(r.mean() * 100),
            "force_dollars": _force(net), "force_taille": _force(r),
            "force_taille_achats": _force(achats["rendement"]), "force_taille_ventes": _force(ventes["rendement"]),
            "force_taille_1": _force(a["rendement"]), "force_taille_2": _force(b["rendement"]),
            "part_5_meilleurs_pct": float(net.nlargest(5).sum() / net.sum() * 100) if net.sum() > 0 else np.nan}


def durables(p: pd.DataFrame) -> pd.Series:
    return (((p["trades"] >= 100) | (p["mois"] >= 6)) & (p["trades"] >= 30) & (p["duree_mediane_h"] >= 2)
            & (p["gagnants_pct"] <= 85) & (p["gain_moyen_sur_perte_moyenne"] >= 0.3) & (p["liquides_pct"] <= 3))


def origine(t: pd.DataFrame, maitres: list[str]) -> dict:
    """Origine de l'avantage (maitres/origine_avantage.py) pour chaque candidat, sur nos vrais prix."""
    from collapsar.maitres.origine_avantage import mesurer, resume
    sortie = {}
    for m in maitres:
        g = t[t["maitre"] == m].sort_values("fin")
        g = g.assign(futur=np.arange(len(g)) >= len(g) // 2)
        try:
            x = mesurer(g, np.random.default_rng(0))
            if len(x) >= 20:
                sortie[m] = resume(x)
        except Exception as e:
            sortie[m] = {"erreur": f"{type(e).__name__}: {e}"}
    return sortie


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    t = tous_les_trades()
    marches = par_marche(t)
    print(marches.round(1).to_string())
    resultats = {"trades": int(len(t)), "traders": int(t["maitre"].nunique()), "par_marche": marches.to_dict("records")}
    profils = {}
    for nom, sel in (("or", t[t["marche"] == "XAUUSD"]), ("hors_or", t[t["marche"] != "XAUUSD"]), ("tout", t)):
        p = pd.DataFrame([{"maitre": m, **profil(g)} for m, g in sel.groupby("maitre") if len(g) >= 10])
        p["durable"] = durables(p)
        p["prouve"] = p["force_taille"] > 3
        p["talent_qui_dure"] = p["durable"] & (p["trades"] >= 200) & p["prouve"]
        p["deux_moities_positives"] = (p["force_taille_1"] > 0) & (p["force_taille_2"] > 0)
        p.to_csv(SORTIE / f"traders_{nom}.csv", index=False)
        profils[nom] = p
        d = p[p["durable"]]
        resultats[nom] = {"traders_10_trades_ou_plus": int(len(p)), "durables": int(len(d)),
                          "durables_gagnants": int((d["gain_net_$"] > 0).sum()),
                          "durables_prouves_force_taille_3": int(d["prouve"].sum()),
                          "durables_200_trades": int((d["trades"] >= 200).sum()),
                          "talent_qui_dure": int(p["talent_qui_dure"].sum()),
                          "durables_deux_moities_positives": int(d["deux_moities_positives"].sum()),
                          "achats_pct_median_des_durables": float(d["achats_pct"].median()) if len(d) else None}
        # persistance sur tous les traders de ce groupe (choisis sur la 1re moitié, jugés sur la 2de)
        m = moities(sel.assign(volume=sel["volume"]), min_trades=60)
        resultats[nom]["persistance_en_dollars"] = bilan(m, "force")
        resultats[nom]["persistance_rapporte_a_la_taille"] = bilan(m, "force_taille")
        print(nom, json.dumps(resultats[nom], ensure_ascii=False, default=float)[:900])
    # candidats : durables avec force rapportée à la taille > 2 sur tout, ou les 15 meilleurs durables
    p = profils["tout"]
    d = p[p["durable"]].sort_values("force_taille", ascending=False)
    cand = d[(d["force_taille"] > 2) | (d.index.isin(d.head(15).index))]
    ori = origine(t, list(cand["maitre"]))
    cand = cand.assign(
        sens_1_jour=[ori.get(m, {}).get("1 jour", {}).get("moyenne") for m in cand["maitre"]],
        moment_hors_penchant_force=[ori.get(m, {}).get("vrai", {}).get("moment_au_dela_du_penchant", {}).get("force")
                                    for m in cand["maitre"]],
        sortie_contre_hasard_force=[ori.get(m, {}).get("sortie_contre_hasard", {}).get("force") for m in cand["maitre"]])
    cand.to_csv(SORTIE / "candidats.csv", index=False)
    resultats["candidats"] = cand.to_dict("records")
    resultats["origine"] = ori
    (SORTIE / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1, default=float),
                                           encoding="utf-8")
    cols = ["maitre", "trades", "mois", "marches", "duree_mediane_h", "achats_pct", "gagnants_pct", "levier_median",
            "gain_net_$", "gain_achats_$", "gain_ventes_$", "force_taille", "force_taille_1", "force_taille_2",
            "moment_hors_penchant_force", "sortie_contre_hasard_force"]
    print(cand[cols].round(2).to_string())
    print(f"(enregistré : {SORTIE})")


if __name__ == "__main__":
    main()
