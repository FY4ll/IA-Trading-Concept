"""LA TENDANCE DE FOND, MAIS SANS LA NUIT ? (15/10/2026)

Seule source d'avantage mesurée du projet : la tendance de fond (+0,4 de qualité avant frais), mangée chez FTMO par
les frais de nuit (taux annuels de plusieurs % sur métaux et indices). Question : en suivant le même sens mais
SEULEMENT PENDANT LA JOURNÉE (entrée après la réouverture de 01h, sortie à 23h45 heure du serveur, avant le passage
de minuit qui coûte la nuit), garde-t-on l'avantage ? Ou bien la tendance se fait-elle surtout la nuit ?

Pour chaque marché, chaque jour : sens = signe de la tendance passée (20, 60 ou 120 jours, ou les trois moyennés),
taille réglée pour que le compte bouge d'environ 1 % par jour (agitation des 20 derniers jours) :
- GARDER : la position passe les nuits -> gain du jour + gain de la nuit - frais de nuit (taux de l'époque) - frais
  quand le sens change ;
- JOURNÉE : gain du jour seulement - frais d'un trade complet CHAQUE jour.
Qualité = rendement annuel / agitation annuelle. Années 2010 -> 2022 (apprentissage et école ; ni l'examen ni les mois
cachés). Portefeuille = moyenne des marchés à risque égal.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.regarder.tendance_sans_nuit
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mains.fiches import CRYPTOS, fiche
from collapsar.mains.nuit import taux_nuit

DEBUT, FIN = pd.Timestamp("2010-01-01"), pd.Timestamp("2023-01-01")
SIGNAUX = {"20 j": [20], "60 j": [60], "120 j": [120], "les trois": [20, 60, 120]}
RISQUE_JOUR = 0.01


def journees(marche: str) -> pd.DataFrame:
    d = dm.charger(marche, jusqua=FIN)
    d = d[d["time"] >= DEBUT - pd.Timedelta(days=200)]
    t = pd.DatetimeIndex(d["time"])
    d = d.assign(jour=t.floor("1D"), heure=t.hour)
    jour = d[d["heure"] >= 1].groupby("jour").agg(ouverture=("open", "first"), cloture=("close", "last"),
                                                   bougies=("close", "size"))
    return jour[jour["bougies"] >= 40]          # jours de marché complets (pas les dimanches ni jours fériés courts)


def mesurer(marche: str) -> dict | None:
    f = fiche(marche)
    j = journees(marche)
    if len(j) < 500:
        return None
    jour = j["cloture"] / j["ouverture"] - 1
    nuit = j["ouverture"].shift(-1) / j["cloture"] - 1                  # de la clôture à la réouverture suivante
    nuits = (j.index.to_series().shift(-1) - j.index.to_series()).dt.days  # 3 le vendredi
    vol = (j["cloture"] / j["cloture"].shift(1) - 1).rolling(20, min_periods=10).std()
    achat, vente = taux_nuit(f, pd.DatetimeIndex(j.index))
    sortie = {}
    for nom, longueurs in SIGNAUX.items():
        sens = sum(np.sign(j["cloture"].shift(1) / j["cloture"].shift(1 + L) - 1) for L in longueurs) / len(longueurs)
        w = (sens * RISQUE_JOUR / vol.shift(1)).clip(-20, 20)            # part du compte engagée (signée)
        ok = (j.index >= DEBUT) & w.notna() & nuit.notna()
        frais_nuit = np.where(w > 0, w.abs() * achat * nuits / 365, w.abs() * vente * nuits / 365)
        changement = (w - w.shift(1)).abs().fillna(0)
        garder = w * (jour + nuit) - frais_nuit - changement * f.frais
        journee = w * jour - w.abs() * f.frais
        brut = w * (jour + nuit)
        r = {}
        for cle, x in (("avant frais", brut), ("garder", garder), ("journée seulement", journee),
                       ("nuit seulement, avant frais", w * nuit)):
            x = pd.Series(x, index=j.index)[ok]
            r[cle] = {"rendement_an_pct": float(x.mean() * 252 * 100), "qualite": float(x.mean() / x.std() * np.sqrt(252))}
        sortie[nom] = r
    return {"jours": int(ok.sum()), "frais": f.frais, "signaux": sortie,
            "series": {nom: None for nom in SIGNAUX}}


def main():
    marches = [m for m in dm.liste_marches() if m not in CRYPTOS]
    res, series = {}, {}
    for m in marches:
        try:
            r = mesurer(m)
        except Exception as e:
            print(f"{m} : ignoré ({type(e).__name__}: {e})")
            continue
        if r:
            r.pop("series")
            res[m] = r
            s = r["signaux"]["les trois"]
            print(f"{m:14s} {r['jours']:5d} j | avant frais {s['avant frais']['qualite']:+.2f} | garder "
                  f"{s['garder']['qualite']:+.2f} | journée seulement {s['journée seulement']['qualite']:+.2f} | "
                  f"nuit seule {s['nuit seulement, avant frais']['qualite']:+.2f}", flush=True)
    bilan = {}
    for nom in SIGNAUX:
        bilan[nom] = {cle: round(float(np.mean([r["signaux"][nom][cle]["qualite"] for r in res.values()])), 3)
                      for cle in ("avant frais", "garder", "journée seulement", "nuit seulement, avant frais")}
    f = dm.RACINE / "collapsar" / "vie" / "tendance_sans_nuit.json"
    f.write_text(json.dumps({"bilan_qualite_moyenne": bilan, "par_marche": res}, ensure_ascii=False, indent=1),
                 encoding="utf-8")
    print("QUALITÉ MOYENNE PAR MARCHÉ (rendement / agitation, par an) :")
    for nom, b in bilan.items():
        print(f"  tendance {nom:10s} : " + " | ".join(f"{k} {v:+.2f}" for k, v in b.items()))
    print(f"(enregistré : {f})")


if __name__ == "__main__":
    main()
