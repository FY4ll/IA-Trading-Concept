"""PISTE « BITCOIN CASSURE » (BTCUSD, compte FTMO) — 16/10/2026, décision du coordinateur (carte blanche du chef).

2 candidats choisis après avoir vu 2017-2021 et 2022-2023 parmi 8 variantes -> seuil de preuve racine(2 ln 8) = 2,04
(le brief commun demande max(3, ...) = 3 : les deux seuils sont donnés) ; seul juge neuf = 2024-01 -> 2026-10, ouvert
UNE fois (verrou collapsar/vie/pistes/bitcoin_cassure/cachee.json : s'il existe, on ne recalcule jamais).

Réglages FIGÉS = EXACTEMENT ceux de collapsar/regarder/pistes/bitcoin_journee.py (importés, aucune modification) :
- C2 : à chaque heure pleine de 01h00 à 22h00 serveur, clôture de l'heure écoulée au-dessus du plus haut des 24 heures
  qui la précèdent -> achat (sous le plus bas -> vente) ; sortie si la clôture horaire repasse le milieu du canal,
  sinon à 23h45 serveur ;
- A3 : sens du mouvement 00h00 -> 12h00 serveur, position tenue de 12h00 à 23h45 serveur ;
- jours lundi -> vendredi serveur avec >= 92 bougies ; taille = min(1, cible / agitation des 14 jours précédents).

SURCOUCHE DE RISQUE décidée maintenant (avant la période cachée), sans toucher au sens : ARRÊT DE LA JOURNÉE si le compte
perd 3 % dans la journée (perte réalisée + perte latente, au plus bas / plus haut des bougies de 15 min) : la position
est fermée au niveau -3 % (ou à l'ouverture de la bougie si le prix a sauté au-delà), plus aucun trade avant le
lendemain. Résultats donnés AVEC et SANS la surcouche.

Mesures sur la période cachée, cibles 0,5 / 1 / 1,5 %, frais 0,01 / 0,03 / 0,1 % par aller-retour : trades, %/mois,
baisse max, pire jour / pire point dans la journée, force (non pesée et pesée par la taille), challenges réussis /
morts contre 20 jumeaux (sens à pile ou face, mêmes moments, même taille, même surcouche), survie d'un compte financé
12 mois (départ tous les 10 jours, mort à -5 % dans un jour ou -10 % du départ), espérance d'un challenge à 540 EUR
remboursé si réussi (-540 x (1 - part réussie)). En plus : part du gain venant des achats / des ventes, gain par année.
Les périodes 2017-2021 et 2022-2023 sont recalculées pour comparaison (déjà vues : ne prouvent rien).

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.bitcoin_cassure [essai | cachee]
  essai  = données coupées au 01/01/2024 (contrôle du code, la période cachée n'est pas lue) ;
  cachee = l'unique ouverture.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.regarder.pistes import bitcoin_journee as bj

VIE = bj.VIE.parent / "bitcoin_cassure"
CANDIDATS = ("C2", "A3")
CIBLES = (0.005, 0.01, 0.015)
FRAIS = {"0.01%": 0.0001, "0.03%": 0.0003, "0.1%": 0.001}
ARRET = 0.03
SEUILS = {"racine(2 ln 8)": math.sqrt(2 * math.log(8)), "brief max(3, ..)": 3.0}
JOURS_AN, FINANCE_JOURS = 261, 261


def chemins(m: dict, t: pd.DataFrame) -> list:
    """Pour chaque trade : (ouverture, plus haut, plus bas) des bougies tenues en rendement depuis l'entrée."""
    out = []
    for d, a, b in zip(t["d"], t["m_entree"], t["m_sortie"]):
        e = bj.prix(m, d, a)
        k0, k1 = a // 15, b // 15
        out.append((m["O"][d, k0:k1] / e - 1, m["H"][d, k0:k1] / e - 1, m["L"][d, k0:k1] / e - 1))
    return out


def simuler(t, ch, frais, cible, signes=None, arret=True):
    """Trade par trade, dans l'ordre : gain (part du compte), pire point, rendement réalisé, fait ou non."""
    n = len(t)
    s = t["sens"].to_numpy() * (1 if signes is None else signes)
    e = np.minimum(1.0, cible / t["agitation"].to_numpy())
    r_fin = t["r_prix"].to_numpy()
    jour = t["jour"].to_numpy()
    g, pire, r_eff, fait = np.zeros(n), np.zeros(n), np.full(n, np.nan), np.zeros(n, bool)
    avant, stop, j_prec = 0.0, False, None
    for i in range(n):
        if jour[i] != j_prec:
            avant, stop, j_prec = 0.0, False, jour[i]
        if stop:
            continue
        o, h, l = ch[i]
        adv = l if s[i] > 0 else -h                       # rendement le plus défavorable de chaque bougie
        so = s[i] * o
        r = s[i] * r_fin[i]
        pire_r = min(adv.min(), 0.0)
        if arret:
            r_star = (-ARRET - avant) / e[i] + frais       # rendement qui amène le compte à -3 % sur la journée
            touche = adv <= r_star
            if touche.any():
                k = int(np.argmax(touche))
                r = min(so[k], r_star)
                pire_r = r
                stop = True
        g[i] = e[i] * (r - frais)
        pire[i] = avant + e[i] * (pire_r - frais)
        r_eff[i], fait[i] = r, True
        avant += g[i]
    return g, pire, r_eff, fait


def par_jour(t, g, pire, fait, jours):
    gs = pd.Series(g[fait], index=t["jour"][fait]).groupby(level=0).sum().reindex(jours, fill_value=0.0)
    w = pd.Series(np.minimum(pire[fait], 0), index=t["jour"][fait]).groupby(level=0).min().reindex(jours, fill_value=0.0)
    return gs.to_numpy(), w.to_numpy()


def finance(g, w, pas=10):
    """Compte financé 12 mois : % de survie et gain moyen sur 12 mois (mort = -10 %)."""
    vie, gains = [], []
    for d0 in range(0, len(g) - FINANCE_JOURS + 1, pas):
        x, y = g[d0:d0 + FINANCE_JOURS], w[d0:d0 + FINANCE_JOURS]
        cs = np.cumsum(x)
        matin = np.r_[0.0, cs[:-1]]
        mort = (y <= -0.05) | (matin + y <= -0.10)
        vie.append(not mort.any())
        gains.append(cs[-1] if not mort.any() else -0.10)
    if not vie:
        return {"survie_pct": None, "gain_12m_pct": None, "departs": 0}
    return {"survie_pct": 100 * float(np.mean(vie)), "gain_12m_pct": 100 * float(np.mean(gains)), "departs": len(vie)}


def force(x):
    x = x[np.isfinite(x)]
    return float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))) if len(x) > 2 else 0.0


def mesurer(t, ch, jours, arret):
    res = {}
    mois = len(jours) / JOURS_AN * 12
    rng = np.random.default_rng(7)
    signes_j = [rng.choice([-1, 1], len(t)) for _ in range(20)]
    for nf, f in FRAIS.items():
        for c in CIBLES:
            g, pire, r_eff, fait = simuler(t, ch, f, c, None, arret)
            gj, wj = par_jour(t, g, pire, fait, jours)
            courbe = np.cumsum(gj)
            s = t["sens"].to_numpy()
            brut = r_eff                                   # déjà dans le sens du trade (ne pas re-multiplier par s)
            pese = brut / t["agitation"].to_numpy()
            elle_c = bj.challenge(gj, wj)
            elle_f = finance(gj, wj)
            J = []
            for sg in signes_j:
                gg, pp, _, ff = simuler(t, ch, f, c, sg, arret)
                a, b = par_jour(t, gg, pp, ff, jours)
                J.append((bj.challenge(a, b), finance(a, b)))
            ach = g[fait & (s > 0)].sum()
            ven = g[fait & (s < 0)].sum()
            an = pd.Series(gj, index=jours).groupby(jours.year).sum()
            mois_an = pd.Series(1, index=jours).groupby(jours.year).sum() / JOURS_AN * 12
            res[f"frais {nf} | cible {c * 100:.1f} %"] = {
                "trades": int(fait.sum()),
                "pct_mois": float(courbe[-1] / mois * 100),
                "baisse_max_pct": float((courbe - np.maximum.accumulate(np.r_[0, courbe])[1:]).min() * 100),
                "pire_jour_pct": float(gj.min() * 100), "pire_point_pct": float(wj.min() * 100),
                "force": force(brut), "force_pesee": force(pese),
                "gain_achats_pct": float(ach * 100), "gain_ventes_pct": float(ven * 100),
                "pct_mois_par_annee": {int(k): float(an[k] / mois_an[k] * 100) for k in an.index},
                "challenges": elle_c,
                "jumeaux_reussis_pct": float(np.mean([j[0]["reussis_pct"] for j in J])),
                "jumeaux_morts_pct": float(np.mean([j[0]["morts_pct"] for j in J])),
                "jumeaux_esperance_eur": float(np.mean([j[0]["esperance_eur"] for j in J])),
                "finance": elle_f,
                "jumeaux_survie_pct": (float(np.mean([j[1]["survie_pct"] for j in J]))
                                       if elle_f["survie_pct"] is not None else None)}
    return res


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "essai"
    VIE.mkdir(parents=True, exist_ok=True)
    verrou = VIE / "cachee.json"
    if phase == "cachee" and verrou.exists():
        print("Période cachée DÉJÀ évaluée :", verrou.read_text(encoding="utf-8")[:2000])
        return
    jusqua = "2027-01-01" if phase == "cachee" else "2024-01-01"
    periodes = {k: v for k, v in bj.PERIODES.items() if phase == "cachee" or "cachée" not in k}
    m = bj.matrice(jusqua)
    agit = bj.agitation(m)
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "phase": phase, "seuils": SEUILS, "periodes": {}}
    tous = []
    for v in CANDIDATS:
        t = bj.trades(m, bj.GENERATEURS[v](m), agit)
        t["variante"] = v
        tous.append(t)
        for p, (de, a) in periodes.items():
            tp = t[(t["jour"] >= de) & (t["jour"] < a)].reset_index(drop=True)
            j = m["jours"]
            jours = pd.DatetimeIndex(j[m["valide"] & (j >= pd.Timestamp(de)) & (j < pd.Timestamp(a)) & np.isfinite(agit)])
            ch = chemins(m, tp)
            for arret in (False, True):
                cle = f"{v} | {'avec' if arret else 'sans'} arrêt -3 %"
                x = mesurer(tp, ch, jours, arret)
                sortie["periodes"].setdefault(p, {})[cle] = x
                y = x["frais 0.01% | cible 1.0 %"]
                print(f"{p[:14]:14s} {cle:22s} | {y['trades']} trades | {y['pct_mois']:+.2f} %/mois | baisse "
                      f"{y['baisse_max_pct']:.1f} % | pire point {y['pire_point_pct']:.2f} % | force {y['force']:+.2f} / "
                      f"pesée {y['force_pesee']:+.2f} | challenges {y['challenges']['reussis_pct']:.0f}/"
                      f"{y['challenges']['morts_pct']:.0f} (jumeaux {y['jumeaux_reussis_pct']:.0f}/{y['jumeaux_morts_pct']:.0f})"
                      f" | financé {y['finance']['survie_pct']} | années {y['pct_mois_par_annee']}", flush=True)
    f = verrou if phase == "cachee" else VIE / "essai.json"
    f.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    pd.concat(tous).to_csv(VIE / f"trades_{phase}.csv", index=False)
    print(f"(enregistré : {f})")


if __name__ == "__main__":
    main()
