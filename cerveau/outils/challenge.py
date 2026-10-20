"""SIMULATEUR DE CHALLENGE FTMO pour une façon de trader (20/10/2026) : à partir des résultats de trades en R (tirés d'un
replay, d'un journal, ou d'hypothèses), donne la chance de réussir chaque phase, d'aller jusqu'au 1er retrait, et
l'espérance en € d'un challenge, pour plusieurs risques par trade. Règles FTMO 2 étapes vérifiées
(docs/FTMO_REGLES_VERIFIEES.md) : phase 1 +10 %, phase 2 +5 %, perte du jour -5 % du capital de départ (jour = suite de
trades du même jour), perte maximale -10 % fixe ; compte financé : on trade jusqu'à +X % puis 1er retrait (80 % du gain,
frais du challenge remboursés). Simplifications (dites) : pas de latent dans la journée (un trade = son résultat final),
pas de règle des 4 jours (respectée si >= 1 trade/jour), pas de clause « jeu de hasard » (7.4 : à risque élevé, FTMO
peut refuser : non modélisé).

    venv_gpu\\Scripts\\python.exe -m cerveau.outils.challenge --gagnants 0.36 --gain 2 --perte 1
    venv_gpu\\Scripts\\python.exe -m cerveau.outils.challenge --replay etudes\\replay_manuel\\replay_trades.csv
"""
from __future__ import annotations

import argparse

import numpy as np

PRIX_EUR = {10_000: 89, 25_000: 199, 50_000: 299, 100_000: 540, 200_000: 1_080}   # prix publics FTMO (à vérifier)
EUR_USD = 1.08


def simuler(R: np.ndarray, risque_pct: float, trades_par_jour: int = 1, cible_retrait_pct: float = 5.0,
            n: int = 100_000, jours_max: int = 400, graine: int = 0) -> dict:
    """R : échantillon de résultats de trades en R (après frais). Rend les chances de chaque phase."""
    rng = np.random.default_rng(graine)

    def phase(cible):
        valeur = np.zeros(n)
        reussi = np.zeros(n, bool)
        fini = np.zeros(n, bool)
        jours = np.zeros(n)
        for _ in range(jours_max):
            jour = rng.choice(R, size=(n, trades_par_jour)) * risque_pct
            cumul = np.cumsum(jour, axis=1)
            mur_jour = (cumul.min(axis=1) <= -5.0)                    # -5 % du capital de départ dans la journée
            pire = valeur + np.minimum(cumul.min(axis=1), 0)
            fin = valeur + cumul[:, -1]
            mort = ~fini & (mur_jour | (pire <= -10.0))
            gagne = ~fini & ~mort & (fin >= cible)
            valeur = np.where(fini, valeur, fin)
            jours += ~fini
            reussi |= gagne
            fini |= mort | gagne
            if fini.all():
                break
        return float(reussi.mean()), float(np.median(jours[reussi])) if reussi.any() else float("nan")

    p1, j1 = phase(10.0)
    p2, j2 = phase(5.0)
    p3, j3 = phase(cible_retrait_pct)
    return {"risque_pct": risque_pct, "phase1": p1, "phase2": p2, "finance_jusqu_au_retrait": p3,
            "jusqu_au_1er_retrait": p1 * p2 * p3, "jours_medians": (j1, j2, j3)}


def esperance(res: dict, capital: int = 100_000, cible_retrait_pct: float = 5.0) -> dict:
    prix = PRIX_EUR[capital] * EUR_USD
    gain = 0.8 * capital * cible_retrait_pct / 100 + prix
    p = res["jusqu_au_1er_retrait"]
    return {"esperance_dollars": p * gain - prix, "challenges_moyens_pour_1_retrait": 1 / p if p > 0 else float("inf"),
            "proba_10_echecs_de_suite": (1 - p) ** 10}


def lire_replay(fichier: str) -> np.ndarray:
    import pandas as pd
    df = pd.read_csv(fichier, sep=";", dtype=str).dropna(how="all")
    e, s, x = (pd.to_numeric(df[c].str.replace(",", "."), errors="coerce") for c in ("prix_entree", "stop", "prix_sortie"))
    sens = df["sens"].str.upper().map({"A": 1, "V": -1})
    R = (sens * (x - e) / (e - s).abs()).dropna().to_numpy()
    return R - 0.04                                                    # frais FTMO moyens ~0,04 R (or, stop ~0,5 %)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gagnants", type=float, help="part de trades gagnants (0-1)")
    ap.add_argument("--gain", type=float, default=2.0, help="gain moyen d'un gagnant, en R")
    ap.add_argument("--perte", type=float, default=1.0, help="perte moyenne d'un perdant, en R")
    ap.add_argument("--replay", help="fichier de trades (format replay manuel)")
    ap.add_argument("--trades-par-jour", type=int, default=1)
    ap.add_argument("--capital", type=int, default=100_000)
    a = ap.parse_args()
    if a.replay:
        R = lire_replay(a.replay)
        print(f"{len(R)} trades lus : {100 * (R > 0).mean():.0f} % gagnants, R moyen {R.mean():+.3f}")
    else:
        R = np.r_[np.full(int(round(1000 * a.gagnants)), a.gain), np.full(1000 - int(round(1000 * a.gagnants)), -a.perte)] - 0.04
    for r in (0.5, 1, 2, 3, 4.5):
        res = simuler(R, r, a.trades_par_jour)
        e = esperance(res, a.capital)
        print(f"risque {r:>3} % : phase 1 {100 * res['phase1']:4.1f} %, phase 2 {100 * res['phase2']:4.1f} %, financé "
              f"jusqu'au retrait {100 * res['finance_jusqu_au_retrait']:4.1f} % -> 1er retrait {100 * res['jusqu_au_1er_retrait']:4.1f} % ; "
              f"espérance {e['esperance_dollars']:+6.0f} $ ; ~{e['challenges_moyens_pour_1_retrait']:.1f} challenges par retrait ; "
              f"10 échecs de suite : {100 * e['proba_10_echecs_de_suite']:.0f} %")


if __name__ == "__main__":
    main()
