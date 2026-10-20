"""Mesures sur NOS données 2010-2019 de ce que la science a établi (rapports du 14-15/10/2026, reports/) :

1. AGITATION : se prévoit-elle sur nos marchés ? Modèle simple appris sur 2010-2014, jugé sur 2015-2019 (jamais
   vues par le modèle) : rythme heure x jour + agitation des 4, 96 et 480 dernières bougies de 15 minutes. Part
   expliquée de l'agitation de la prochaine bougie et de l'heure qui vient. Rythme de la journée (heure la plus
   agitée / la plus calme).
2. TENDANCE : signe de la variation des 1, 5, 20 et 60 derniers jours, position dosée par l'agitation (comme
   Moskowitz, Ooi, Pedersen 2012), frais réels FTMO estimés (mains/fiches.py) et frais de nuit, AVEC et SANS fermeture
   le vendredi soir. Rapport gain/agitation par marché et pour l'ensemble, sur 2010-2014 et 2015-2019 séparément.
3. PARIS INDÉPENDANTS : combien de paris vraiment différents parmi nos marchés (nombre effectif tiré des liens entre
   leurs variations).
Seulement les données d'avant 2020 : les années d'examen et les 12 mois cachés ne sont jamais lus ici.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.regarder.mesures_science
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche
from collapsar.mains.nuit import taux_nuit

DEBUT, COUPURE, FIN = pd.Timestamp("2010-01-01"), pd.Timestamp("2015-01-01"), pd.Timestamp("2020-01-01")
SORTIE = dm.RACINE / "collapsar" / "vie" / "mesures_science_2010_2019.json"
CIBLE_AGITATION = 0.10                      # agitation annuelle visée par marché (dosage de la tendance)


def charger(m: str) -> pd.DataFrame | None:
    try:
        df = dm.charger(m, jusqua=FIN)
    except Exception:
        return None
    df = df[df["time"] >= DEBUT].reset_index(drop=True)
    if len(df) < 96 * 250 * 4 or df["time"].iloc[0] > pd.Timestamp("2012-01-01"):
        return None
    return df


# ---------------------------------------------------------------------- 1. agitation
def agitation(df: pd.DataFrame) -> dict:
    t = pd.DatetimeIndex(df["time"])
    rng = np.log(df["high"].to_numpy() / df["low"].to_numpy())
    rng = np.where(rng > 0, rng, np.nan)
    s = pd.Series(np.log(rng + 1e-7), index=t)
    s = s.where(np.isfinite(s))
    m4, m96, m480 = (s.rolling(k, min_periods=max(2, k // 2)).mean().shift(1) for k in (4, 96, 480))
    case = (t.dayofweek * 24 + t.hour).to_numpy()
    apprend = (t < COUPURE)
    profil = pd.Series(s[apprend].to_numpy(), index=case[apprend]).groupby(level=0).mean()
    p = pd.Series(case).map(profil).to_numpy()
    X = np.column_stack([np.ones(len(s)), p, m4.to_numpy(), m96.to_numpy(), m480.to_numpy()])
    resultats = {}
    for nom, y in (("bougie", s.to_numpy()), ("heure", s.rolling(4).mean().shift(-3).to_numpy())):
        ok = np.isfinite(X).all(1) & np.isfinite(y)
        a, j = ok & apprend, ok & ~apprend
        coef, *_ = np.linalg.lstsq(X[a], y[a], rcond=None)
        pred = X[j] @ coef
        resultats[f"part_expliquee_{nom}"] = float(1 - ((y[j] - pred) ** 2).sum() / ((y[j] - y[j].mean()) ** 2).sum())
    heures = pd.Series(np.exp(s.to_numpy()), index=t.hour).groupby(level=0).mean()
    heures = heures[heures > 0]
    resultats["rythme_journee"] = float(heures.max() / heures.min())
    resultats["heure_la_plus_agitee_serveur"] = int(heures.idxmax())
    return resultats


# ---------------------------------------------------------------------- 2. tendance
def jours(df: pd.DataFrame) -> pd.DataFrame:
    """Bougies d'un jour (heure serveur) : ouverture, clôture ; et le jour de la semaine."""
    t = pd.DatetimeIndex(df["time"])
    g = df.groupby(t.normalize())
    j = pd.DataFrame({"open": g["open"].first(), "close": g["close"].last()})
    return j[j.index.dayofweek < 5]


def tendance(j: pd.DataFrame, f, lookback: int, vendredi: bool) -> pd.Series:
    """Gain net par jour (part du compte) d'une position = signe(variation sur `lookback` jours) dosée à 10 %/an.
    `vendredi` : fermée le vendredi soir et rouverte le lundi à l'ouverture (le trou du week-end n'est pas couru,
    un aller-retour de frais de plus par semaine)."""
    c = np.log(j["close"])
    r = c.diff()
    agit = r.ewm(span=60, min_periods=40).std() * np.sqrt(252)
    taille = (CIBLE_AGITATION / agit).clip(upper=20.0)
    signe = np.sign(c.diff(lookback))
    pos = (signe * taille).shift(1)                             # décidée la veille au soir
    lundi = j.index.dayofweek == 0
    if vendredi:
        # le lundi : le trou entre la clôture du vendredi et l'ouverture du lundi n'est pas couru
        r_jour = np.where(lundi, np.log(j["close"] / j["open"]), r)
    else:
        r_jour = r.to_numpy()
    brut = pos * r_jour
    changement = pos.diff().abs().fillna(pos.abs())
    frais = changement * f.frais / 2
    if vendredi:
        frais = frais + np.where(lundi, pos.abs() * f.frais, 0.0)    # fermer vendredi + rouvrir lundi
    nuits = np.where(j.index.dayofweek == 2, 3, 1)                     # triples dans la nuit du mercredi
    # frais de nuit de l'époque (écart de taux du moment + marge, mains/nuit.py) ; négatif = reçu
    achat, vente = taux_nuit(f, j.index)
    taux = np.where(pos > 0, achat, vente) / 360
    # la nuit du mercredi paie le week-end (comme le simulateur) ; fermé le vendredi : pas de nuit ce soir-là
    nuit = pos.abs() * taux * (np.where(j.index.dayofweek == 4, 0, nuits) if vendredi else nuits)
    nuit = nuit.fillna(0.0)
    return (brut - frais - nuit).dropna()


def qualite(g: pd.Series) -> dict:
    if len(g) < 100 or g.std() == 0:
        return {"rapport": float("nan"), "pct_mois": float("nan"), "t": float("nan")}
    rap = g.mean() / g.std() * np.sqrt(252)
    return {"rapport": float(rap), "pct_mois": float(g.mean() * 21 * 100), "t": float(rap * np.sqrt(len(g) / 252))}


def main():
    marches = sys.argv[1:] or dm.liste_marches()
    res_agit, res_tend, series = {}, {}, {}
    for m in marches:
        df = charger(m)
        if df is None:
            continue
        try:
            f = fiche(m)
        except ValueError:
            continue
        res_agit[m] = agitation(df)
        j = jours(df)
        res_tend[m] = {}
        for L in (1, 5, 20, 60):
            for ven in (True, False):
                g = tendance(j, f, L, ven)
                cle = f"{L}j_{'ferme_vendredi' if ven else 'garde_week_end'}"
                res_tend[m][cle] = {"2010-2014": qualite(g[g.index < COUPURE]),
                                    "2015-2019": qualite(g[g.index >= COUPURE])}
                series.setdefault(cle, {})[m] = g
        print(f"{m:14s} agitation prochaine heure {res_agit[m]['part_expliquee_heure']*100:5.1f} % | tendance 20 j "
              f"(ferme vendredi) {res_tend[m]['20j_ferme_vendredi']['2010-2014']['rapport']:+.2f} / "
              f"{res_tend[m]['20j_ferme_vendredi']['2015-2019']['rapport']:+.2f}", flush=True)
    # l'ensemble : chaque marché au même risque, moyenne des gains
    ensemble = {}
    for cle, d in series.items():
        tab = pd.DataFrame(d)
        g = tab.mean(axis=1, skipna=True)
        ensemble[cle] = {"2010-2014": qualite(g[g.index < COUPURE]), "2015-2019": qualite(g[g.index >= COUPURE])}
    # paris indépendants : nombre effectif à partir des liens entre variations journalières dosées
    variations = pd.DataFrame({m: np.log(jours(charger(m))["close"]).diff() for m in res_agit}).dropna(how="all")
    variations = variations / variations.std()
    corr = variations.corr().fillna(0).to_numpy()
    vp = np.clip(np.linalg.eigvalsh(corr), 0, None)
    effectif = float(vp.sum() ** 2 / (vp ** 2).sum())
    lien_moyen = float((corr.sum() - len(corr)) / (len(corr) * (len(corr) - 1)))
    rapport = {"agitation": res_agit, "tendance": res_tend, "ensemble": ensemble,
               "paris_independants": {"marches": len(corr), "nombre_effectif": effectif,
                                      "lien_moyen_absolu": float(np.abs(corr - np.eye(len(corr))).sum()
                                                                 / (len(corr) * (len(corr) - 1))),
                                      "lien_moyen": lien_moyen}}
    SORTIE.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nENSEMBLE (même risque sur chaque marché) : rapport gain/agitation  2010-2014 | 2015-2019")
    for cle, v in ensemble.items():
        print(f"  {cle:24s} {v['2010-2014']['rapport']:+.2f} ({v['2010-2014']['pct_mois']:+.2f} %/mois) | "
              f"{v['2015-2019']['rapport']:+.2f} ({v['2015-2019']['pct_mois']:+.2f} %/mois)")
    print(f"\nparis indépendants : {effectif:.1f} sur {len(corr)} marchés (lien moyen {lien_moyen:+.2f})")
    ag = pd.DataFrame(res_agit).T
    print(f"agitation : part expliquée bougie {ag['part_expliquee_bougie'].median()*100:.0f} % (médiane), heure "
          f"{ag['part_expliquee_heure'].median()*100:.0f} % ; rythme journée {ag['rythme_journee'].min():.1f} -> "
          f"{ag['rythme_journee'].max():.1f}")


if __name__ == "__main__":
    main()
