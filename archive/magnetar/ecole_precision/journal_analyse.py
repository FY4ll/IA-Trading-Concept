"""RÉSUMÉ DU JOURNAL DE TRADING (18/10/2026) : lit les fichiers historiques écrits à chaque génération
(<vie>/journal_trades/gNNNNN/<branche>_<phase>_historique.csv) et dit, en tableaux simples, ce qui gagne et ce qui
perd : par catégorie (achat / vente x rebond / cassure), heure, tendance, unité de la zone, durée, raison de sortie,
marché (réel / retourné), et la différence moyenne entre ses trades gagnants et perdants.

Depuis Test_IA :
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.journal_analyse [--dossier collapsar/vie/arbre_or]
      [--derniers 10] [--branche G] [--phase examen|ecole|tout]
Le résumé est aussi écrit dans <vie>/journal_trades/analyse.txt.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[3]


def lire(dossier: Path, derniers: int = 10, branche: str | None = None, phase: str = "examen") -> pd.DataFrame:
    racine = Path(dossier) / "journal_trades"
    gens = sorted(p for p in racine.glob("g[0-9]*") if p.is_dir())[-derniers:]
    morceaux = []
    for g in gens:
        for f in g.glob("*_historique.csv"):
            br, ph = f.stem.split("_")[0], f.stem.split("_")[1]
            if (branche and br != branche) or (phase != "tout" and ph != phase):
                continue
            d = pd.read_csv(f)
            if len(d):
                morceaux.append(d.assign(generation=int(g.name[1:]), phase=ph, branche=br))
    return pd.concat(morceaux, ignore_index=True) if morceaux else pd.DataFrame()


def _bloc(d: pd.DataFrame, cle: str, titre: str) -> list[str]:
    g = d.groupby(cle, observed=True)["r"]
    t = pd.DataFrame({"trades": g.size(), "gagnants_pct": g.apply(lambda x: 100 * (x > 0).mean()),
                      "r_moyen": g.mean(), "r_total": g.sum(),
                      "meilleur_r_moyen": d.groupby(cle, observed=True)["meilleur_r"].mean()})
    L = [f"## {titre}", "", "| " + titre.split(" (")[0] + " | trades | gagnants | R moyen | R total | meilleur R moyen |",
         "|---|---|---|---|---|---|"]
    for k, x in t.iterrows():
        L.append(f"| {k} | {int(x.trades)} | {x.gagnants_pct:.0f} % | {x.r_moyen:+.2f} | {x.r_total:+.1f} | "
                 f"{x.meilleur_r_moyen:+.2f} |")
    return L + [""]


def resumer(d: pd.DataFrame) -> str:
    if d.empty:
        return "Aucun trade fermé dans les fichiers lus."
    d = d[~d["raison"].astype(str).str.startswith("fin du challenge")].copy()
    if d.empty:
        return "Aucun trade fermé dans les fichiers lus."
    d["marche_sens"] = np.where(d["marche"].astype(str).str.endswith("_MIROIR"), "retourné", "réel")
    h = pd.to_numeric(d["situation_heure"].astype(str).str[:2], errors="coerce")
    d["heure"] = pd.cut(h, [-1, 3, 7, 11, 15, 19, 23], labels=["00-04 h", "04-08 h", "08-12 h", "12-16 h", "16-20 h",
                                                              "20-24 h"])
    d["tendance"] = pd.cut(d["situation_tendance"], [-9, -0.3, 0.3, 9], labels=["contre la tendance", "sans tendance",
                                                                             "avec la tendance"])
    d["duree"] = pd.cut(d["duree_h"], [-1, 1, 4, 24, 72, 1e9], labels=["< 1 h", "1-4 h", "4-24 h", "1-3 jours",
                                                                     "> 3 jours"])
    n, gp = len(d), 100 * (d["r"] > 0).mean()
    L = [f"# Journal de trading : {n} trades fermés (générations {d['generation'].min()} -> {d['generation'].max()}, "
         f"branches {', '.join(sorted(d['branche'].unique()))})", "",
         f"- gagnants {gp:.0f} %, R moyen {d['r'].mean():+.3f}, meilleur R moyen {d['meilleur_r'].mean():+.2f}, "
         f"durée médiane {d['duree_h'].median():.1f} h", ""]
    for cle, titre in (("categorie", "Catégorie (achat / vente x rebond / cassure)"), ("marche_sens", "Marché (réel / retourné)"),
                       ("heure", "Heure de la décision (serveur)"), ("tendance", "Tendance au moment d'entrer"),
                       ("situation_unite_zone", "Unité de la zone la plus proche"), ("duree", "Durée du trade"),
                       ("raison", "Raison de sortie"), ("entree", "Type d'entrée")):
        L += _bloc(d, cle, titre)
    num = ["risque_pct", "situation_distance_zone_agit", "situation_part_cassure", "situation_tendance",
           "situation_agitation_pct", "duree_h", "meilleur_r", "pire_r", "heures_jusqu_au_meilleur"]
    num = [c for c in num if c in d]
    g, p = d[d["r"] > 0], d[d["r"] <= 0]
    L += ["## Gagnants contre perdants (moyennes)", "", "| valeur | gagnants | perdants |", "|---|---|---|"]
    for c in num:
        L.append(f"| {c} | {g[c].mean():.3f} | {p[c].mean():.3f} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="résumé du journal de trading")
    ap.add_argument("--dossier", default=str(RACINE / "collapsar" / "vie" / "arbre_or"))
    ap.add_argument("--derniers", type=int, default=10)
    ap.add_argument("--branche", default=None)
    ap.add_argument("--phase", default="examen", choices=["examen", "ecole", "tout"])
    a = ap.parse_args(argv)
    texte = resumer(lire(Path(a.dossier), a.derniers, a.branche, a.phase))
    print(texte)
    f = Path(a.dossier) / "journal_trades" / "analyse.txt"
    if f.parent.exists():
        f.write_text(texte, encoding="utf-8")
    return texte


if __name__ == "__main__":
    main()
