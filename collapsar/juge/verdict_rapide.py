"""Verdict RAPIDE de la vision du trader (14/10/2026) : est-ce que ce que voient les yeux rapporte de l'argent ?

- Toutes les heures, sur chacun des ~45 marchés, les yeux de la cime évaluent les coups possibles (sens, stop,
  objectif) et choisissent celui au meilleur gain par rapport à son incertitude ; elle ne trade que si ce choix lui
  semble assez bon, et jamais deux coups en même temps sur un même marché.
- Chaque coup est rejoué sur le VRAI chemin du prix (même moteur que l'apprentissage : stop d'abord dans une même
  bougie, trou payé à l'ouverture, fermeture avant toute pause de plus de 2 h, une semaine au plus), frais réels retirés.
- Sa prudence (à partir de quelle confiance elle trade) se règle sur 2020-2022 (années de l'école, jamais apprises
  par les yeux) ; le verdict est 2023 -> 09/2025, réglage FIGÉ. Les 12 mois cachés ne sont jamais lus.
- Risque fixe de 0,25 % du compte par coup, gains additionnés : PAS encore le compte FTMO fidèle (murs, frais de
  nuit, compte partagé : ce sera le grand examen), seulement : « le signal rapporte-t-il ? ».
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.juge.verdict_rapide
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import torch
import yaml

from collapsar.arbre.jardinier import Arbre
from collapsar.cerveau.trader import CerveauTrader
from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche
from collapsar.regarder.vision_trader import VisionTrader
from collapsar.yeux.graphique import Graphique

VIE = dm.RACINE / "collapsar" / "vie"
RISQUE = 0.0025
DEBUT_REGLAGE, DEBUT_VERDICT = pd.Timestamp("2020-01-01"), pd.Timestamp("2023-01-01")
PARTS = (0.5, 0.3, 0.2, 0.1, 0.05, 0.02, 0.01)       # elle trade ses x % de situations les plus sûres


def dire(t):
    print(f"[{datetime.now():%H:%M:%S}] {t}", flush=True)


def charger_cime(appareil) -> tuple[CerveauTrader, str]:
    reglages = yaml.safe_load((dm.RACINE / "collapsar" / "reglages.yaml").read_text(encoding="utf-8")) or {}
    arbre = Arbre.charger(VIE / "arbre.json")
    nom = os.environ.get("VERDICT_BRANCHE", arbre.cime)
    f = VIE / "branches" / f"{nom}_meilleur.pt"
    if not f.exists():
        f = VIE / "branches" / f"{nom}.pt"
    c = CerveauTrader(largeur=float(reglages.get("largeur_trader", 1.0))).to(appareil)
    c.load_state_dict(torch.load(f, map_location=appareil, weights_only=True)["cerveau"])
    c.eval()
    return c, f"{nom} ({f.name})"


def jouer(lignes: pd.DataFrame, seuil: float) -> pd.DataFrame:
    """Les coups pris : qualité >= seuil, un seul coup à la fois par marché (le suivant attend la sortie)."""
    pris = []
    for _, d in lignes[lignes["qualite"] >= seuil].groupby("marche", sort=False):
        libre = -1
        for i, fin, r, t in zip(d["idx"].to_numpy(), d["fin"].to_numpy(), d["R"].to_numpy(), d["temps"].to_numpy()):
            if i > libre:
                pris.append((t, r))
                libre = fin
    out = pd.DataFrame(pris, columns=["temps", "R"])
    out["marche"] = None
    return out


def bilan(coups: pd.DataFrame, debut: pd.Timestamp, fin: pd.Timestamp) -> dict:
    mois = pd.period_range(debut, fin - pd.Timedelta(days=1), freq="M")
    if not len(coups):
        return {"coups_par_mois": 0.0, "gain_mois_pct": 0.0}
    par_mois = (coups.set_index(pd.DatetimeIndex(coups["temps"]))["R"] * RISQUE * 100).groupby(
        pd.Grouper(freq="ME")).sum()
    par_mois = par_mois.reindex(pd.date_range(debut, fin, freq="ME"), fill_value=0.0)
    cumul = par_mois.cumsum()
    return {"coups_par_mois": len(coups) / len(mois), "gagnants_pct": float((coups["R"] > 0).mean() * 100),
            "R_moyen": float(coups["R"].mean()), "gain_mois_pct": float(par_mois.mean()),
            "mois_positifs_pct": float((par_mois > 0).mean() * 100), "pire_mois_pct": float(par_mois.min()),
            "baisse_max_pct": float((cumul.cummax().clip(lower=0) - cumul).max())}


@torch.no_grad()
def main():
    torch.set_num_threads(int(os.environ.get("VERDICT_FILS", "8")))
    appareil = torch.device(os.environ.get("VERDICT_APPAREIL", "cpu"))
    cerveau, quelle = charger_cime(appareil)
    dire(f"yeux de la cime : {quelle}")
    donnees = {}
    choisis = [m for m in os.environ.get("VERDICT_MARCHES", "").split(",") if m] or dm.liste_marches()
    for m in choisis:
        if len(dm.charger(m)) >= dm.MIN_BOUGIES:                 # mêmes marchés que l'arbre
            donnees[m] = dm.charger(m, jusqua=dm.FIN_EXAMEN)      # jamais au-delà de 09/2025
    g = Graphique(donnees, appareil)
    del donnees
    vt = VisionTrader(g, n_controle=1)
    t = pd.DatetimeIndex(g.temps)
    heure_pile = np.asarray((t + pd.Timedelta(minutes=15)).minute == 0)
    ok = heure_pile & vt.utilisable & np.asarray(t >= DEBUT_REGLAGE) & (g.pas == 15)
    idx_all = np.flatnonzero(ok)
    dire(f"{len(g.noms)} marchés, {len(idx_all):,} décisions (une par heure, 2020 -> 09/2025)".replace(",", " "))
    sens_s, stop_s, obj_s = vt.sondes()
    lots = []
    for d in range(0, len(idx_all), 2048):
        idx = torch.from_numpy(idx_all[d:d + 2048]).to(appareil)
        moyen, ecart = vt.evaluer(cerveau, idx)
        q = moyen / ecart.clamp(min=1e-3)
        qualite, choix = q.max(1)
        sv, st, ob = sens_s[choix], stop_s[choix], obj_s[choix]
        res, _, k = vt.resultat(idx, sv, st, ob[:, None], avec_sortie=True)
        r = (res[:, 0] - vt.cout[idx]) / st
        lots.append(pd.DataFrame({"idx": idx.cpu().numpy(), "qualite": qualite.cpu().numpy(),
                                  "R": r.cpu().numpy(), "fin": (idx + k[:, 0]).cpu().numpy(),
                                  "sens": sv.cpu().numpy(), "stop": st.cpu().numpy(),
                                  "objectif": ob.cpu().numpy()}))
        if d % (2048 * 100) == 0:
            dire(f"  {d + len(idx):,} / {len(idx_all):,}".replace(",", " "))
    lignes = pd.concat(lots, ignore_index=True)
    lignes["temps"] = g.temps[lignes["idx"].to_numpy()]
    lignes["marche"] = g.marche[lignes["idx"].to_numpy()]
    reglage = lignes[pd.DatetimeIndex(lignes["temps"]) < DEBUT_VERDICT]
    verdict = lignes[pd.DatetimeIndex(lignes["temps"]) >= DEBUT_VERDICT]

    # 1. régler la prudence sur 2020-2022 : la part de situations tradées qui donne le résultat le plus SÛR
    #    (gain moyen rapporté à sa dispersion, sur les coups réellement pris)
    essais = {}
    for p in PARTS:
        seuil = float(np.quantile(reglage["qualite"], 1 - p))
        coups = jouer(reglage, seuil)
        b = bilan(coups, DEBUT_REGLAGE, DEBUT_VERDICT)
        surete = coups["R"].mean() / coups["R"].std() * np.sqrt(len(coups)) if len(coups) > 30 else -1e9
        essais[p] = {"seuil": seuil, "surete": float(surete), **b}
        dire(f"réglage 2020-2022, ses {p:.0%} plus sûres : {b['coups_par_mois']:.0f} coups/mois, "
             f"{b.get('gagnants_pct', 0):.0f} % gagnants, {b['gain_mois_pct']:+.2f} %/mois, baisse max "
             f"{b.get('baisse_max_pct', 0):.1f} %")
    p_choisi = max(essais, key=lambda p: essais[p]["surete"])
    seuil = essais[p_choisi]["seuil"]
    dire(f"prudence retenue : ses {p_choisi:.0%} de situations les plus sûres (seuil {seuil:.3f})")

    # 2. le verdict, réglage figé
    coups = jouer(verdict, seuil)
    v = bilan(coups, DEBUT_VERDICT, dm.FIN_EXAMEN)
    dire(f"VERDICT 2023 -> 09/2025 : {v['coups_par_mois']:.0f} coups/mois, {v.get('gagnants_pct', 0):.0f} % gagnants, "
         f"{v.get('R_moyen', 0):+.3f} fois le risque par coup, {v['gain_mois_pct']:+.2f} %/mois (risque "
         f"{RISQUE:.2%} par coup), mois positifs {v.get('mois_positifs_pct', 0):.0f} %, pire mois "
         f"{v.get('pire_mois_pct', 0):+.2f} %, baisse max {v.get('baisse_max_pct', 0):.1f} %")
    # par famille de marchés
    familles = {}
    pris = verdict[verdict["qualite"] >= seuil]
    for m, d in pris.groupby("marche"):
        try:
            fam = fiche(g.noms[m]).famille
        except ValueError:
            fam = "autre"
        familles.setdefault(fam, []).append(jouer(d, seuil))
    par_famille = {}
    for fam, liste in familles.items():
        c = pd.concat(liste, ignore_index=True)
        par_famille[fam] = bilan(c, DEBUT_VERDICT, dm.FIN_EXAMEN)
        dire(f"   {fam:10s} : {par_famille[fam]['coups_par_mois']:.0f} coups/mois, "
             f"{par_famille[fam].get('R_moyen', 0):+.3f} R/coup, {par_famille[fam]['gain_mois_pct']:+.2f} %/mois")
    # pour la transparence : les autres prudences sur le verdict (on ne choisit PAS avec)
    autres = {}
    for p in PARTS:
        s = float(np.quantile(reglage["qualite"], 1 - p))
        autres[p] = bilan(jouer(verdict, s), DEBUT_VERDICT, dm.FIN_EXAMEN)
    sortie = {"yeux": quelle, "risque_par_coup": RISQUE, "reglage": {str(k): v_ for k, v_ in essais.items()},
              "prudence": p_choisi, "verdict": v, "par_famille": par_famille,
              "autres_prudences_sur_verdict": {str(k): v_ for k, v_ in autres.items()}}
    (VIE / f"verdict_rapide_{datetime.now():%Y%m%d_%H%M}.json").write_text(
        json.dumps(sortie, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
