"""Le rapport du laboratoire SMC : tableau verdict, fiches par concept, stratégie personnelle, annexes CSV.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.regarder.smc.rapport"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.regarder.smc.labo import SEUIL, VIE

SORTIE = dm.RACINE / "reports" / "Laboratoire SMC.md"


def force(t: pd.DataFrame) -> float:
    d = (t["R"] - t["R_inverse"]) / 2
    return float(d.mean() / d.std(ddof=1) * math.sqrt(len(d))) if len(d) > 2 and d.std(ddof=1) > 0 else 0.0


def reaction(t, h) -> tuple[float, float, float]:
    a, b = float(t["reaction"].mean() * 100), float(h["reaction"].mean() * 100) if len(h) else float("nan")
    p = (t["reaction"].sum() + h["reaction"].sum()) / max(len(t) + len(h), 1)
    se = math.sqrt(max(p * (1 - p) * (1 / max(len(t), 1) + 1 / max(len(h), 1)), 1e-12))
    return a, b, (a - b) / 100 / se


def main():
    tr = pd.read_csv(VIE / "trades_2015_2023.csv", parse_dates=["entree"])
    te = pd.read_csv(VIE / "temoins_hasard_2015_2023.csv", parse_dates=["entree"])
    var = pd.read_csv(VIE / "variantes_2015_2023.csv")
    cachee = json.loads((VIE / "cachee.json").read_text(encoding="utf-8"))
    retenus = {c["concept"] for c in cachee["candidats"]}
    tr["annee"] = tr["entree"].dt.year
    lignes, fiches = [], []
    familles = tr.drop_duplicates("concept")[["famille", "concept"]].values.tolist()
    for fam, nom in sorted(familles, key=lambda x: ({"perso": 0, "concept": 1, "combinaison": 2}[x[0]], x[1])):
        t = tr[tr["concept"] == nom]
        h = te[te["concept"] == nom]
        f = force(t)
        ra, rh, z = reaction(t, h)
        prouve = any(c["prouve"] for c in cachee["candidats"] if c["concept"] == nom)
        if prouve:
            verdict = "PROUVÉ"
        elif nom in retenus or (ra - rh >= 5 and z >= 3):
            verdict = "FAIBLE"
        else:
            verdict = "INUTILE"
        lignes.append({"famille": fam, "concept": nom, "verdict": verdict, "trades": len(t), "R_moyen": t["R"].mean(),
                       "gagnants_pct": (t["R"] > 0).mean() * 100, "cout_R": t["cout_R"].mean(),
                       "stop_pct_prix": t["stop_pct"].mean(), "force_jumeau": f, "reaction_pct": ra,
                       "reaction_hasard_pct": rh, "z_reaction": z,
                       "variantes_positives": int(((var["concept"] == nom) & (var["choix_R_moyen"] > 0)).sum()),
                       "variantes": int((var["concept"] == nom).sum())})
        par_an = t.groupby("annee").agg(trades=("R", "size"), R=("R", "mean")).round(3)
        par_an["force"] = [round(force(g), 2) for _, g in t.groupby("annee")]
        par_m = t.groupby(["marche", "unite"]).agg(trades=("R", "size"), R=("R", "mean")).round(3)
        par_m["force"] = [round(force(g), 2) for _, g in t.groupby(["marche", "unite"])]
        fiches.append((fam, nom, par_an, par_m))
    v = pd.DataFrame(lignes)
    v.to_csv(VIE / "verdict_concepts.csv", index=False)
    # la stratégie personnelle : effet du contact, du filtre FVG, de la marge (toutes unités et tous marchés)
    p = tr[tr["famille"] == "perso"].copy()
    p["contact"] = p["concept"].str.extract(r"contact (\d)").astype(int)
    p["filtre"] = p["concept"].str.contains("avec")
    p["marge"] = p["concept"].str.extract(r"marge ([\d.]+)").astype(float)
    perso = []
    for cle in ("contact", "filtre", "marge"):
        for val, g in p.groupby(cle):
            perso.append({"facteur": cle, "valeur": val, "trades": len(g), "R_moyen": g["R"].mean(),
                          "gagnants_pct": (g["R"] > 0).mean() * 100, "cout_R": g["cout_R"].mean(),
                          "stop_pct": g["stop_pct"].mean(), "force": force(g),
                          "reaction_pct": g["reaction"].mean() * 100})
    perso = pd.DataFrame(perso)
    perso.to_csv(VIE / "strategie_perso.csv", index=False)
    # le rapport
    f2 = lambda x: f"{x:+.3f}"
    out = ["# Laboratoire SMC — rapport (15/10/2026)", "",
           f"Seuil de preuve global : force ≥ {SEUIL:.2f} (366 variantes, ORB compris). Données 2015-2023 pour les mesures ;",
           "période cachée 2024-2026 évaluée une seule fois pour le seul candidat retenu.", "",
           "## Page 1 — verdict par concept (toutes unités et tous marchés réunis, 2015-2023)", "",
           "| Concept | Verdict | Trades | Gain moyen (R, après frais) | Coût des frais (R) | Stop (% du prix) | "
           "Force contre le jumeau | Réaction / hasard |", "|---|---|---|---|---|---|---|---|"]
    for r in lignes:
        out.append(f"| {r['concept']} | **{r['verdict']}** | {r['trades']} | {f2(r['R_moyen'])} | {r['cout_R']:.3f} | "
                   f"{r['stop_pct_prix']:.3f} | {r['force_jumeau']:+.1f} | {r['reaction_pct']:.0f} % / "
                   f"{r['reaction_hasard_pct']:.0f} % |")
    out += ["", "## Période cachée (2024-2026, une seule fois)", ""]
    for c in cachee["candidats"]:
        out.append(f"- {c['concept']} — {c['marche']} {c['unite']} : {c.get('trades')} trades, "
                   f"{c.get('R_moyen', 0):+.3f} R, force {c.get('force', 0):+.2f} -> "
                   f"{'PROUVÉ' if c['prouve'] else 'non prouvé'}")
    out += ["", "## Stratégie personnelle", "", "| Facteur | Valeur | Trades | Gain moyen (R) | Gagnants | Coût (R) | "
            "Stop (%) | Force | Réaction |", "|---|---|---|---|---|---|---|---|---|"]
    for _, r in perso.iterrows():
        out.append(f"| {r['facteur']} | {r['valeur']} | {r['trades']} | {f2(r['R_moyen'])} | {r['gagnants_pct']:.0f} % | "
                   f"{r['cout_R']:.3f} | {r['stop_pct']:.3f} | {r['force']:+.1f} | {r['reaction_pct']:.0f} % |")
    out += ["", "## Fiches par concept", ""]
    for fam, nom, par_an, par_m in fiches:
        r = next(x for x in lignes if x["concept"] == nom)
        out += [f"### {nom} ({fam}) — {r['verdict']}", "",
                f"{r['trades']} cas ; gain moyen {f2(r['R_moyen'])} R après frais ; gagnants {r['gagnants_pct']:.0f} % ; "
                f"frais {r['cout_R']:.3f} R ; stop {r['stop_pct_prix']:.3f} % du prix ; force contre le jumeau "
                f"{r['force_jumeau']:+.1f} ; réaction {r['reaction_pct']:.0f} % contre {r['reaction_hasard_pct']:.0f} % "
                f"pour des zones au hasard ; variantes positives sur 2015-2021 : {r['variantes_positives']} / {r['variantes']}.",
                "", "Par année : " + " · ".join(f"{a} {x['R']:+.3f} R ({int(x['trades'])})" for a, x in par_an.iterrows()),
                "", "Par marché et unité : " + " · ".join(f"{m} {u} {x['R']:+.3f} R (force {x['force']:+.1f})"
                                                        for (m, u), x in par_m.iterrows()), ""]
    out += ["## Annexes (CSV)", "", "- `collapsar/vie/smc/trades_2015_2023.csv` : chaque trade (2015-2023)",
            "- `collapsar/vie/smc/temoins_hasard_2015_2023.csv` : les zones et moments au hasard",
            "- `collapsar/vie/smc/variantes_2015_2023.csv` : chaque variante (marché x unité), choix et vérification",
            "- `collapsar/vie/smc/verdict_concepts.csv`, `strategie_perso.csv`",
            "- `collapsar/vie/smc/trades_cachee_2024_2026.csv` et `cachee.json` : la période cachée"]
    SORTIE.write_text("\n".join(out), encoding="utf-8")
    print(v[["concept", "verdict", "trades", "R_moyen", "cout_R", "stop_pct_prix", "force_jumeau", "reaction_pct",
             "reaction_hasard_pct", "z_reaction"]].round(3).to_string())
    print(perso.round(3).to_string())
    print(f"(rapport : {SORTIE})")


if __name__ == "__main__":
    main()
