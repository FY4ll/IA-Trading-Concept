"""LA CARTE DE LA FOULE annonce-t-elle le prix ? (15/10/2026, idée du chef de projet : « qu'elle bouffe de
l'information », apprendre de la MASSE des traders, pas seulement des bons)

Avec TOUS les trades d'Ostium (chaîne publique : ~15 000 traders, morts compris), on reconstruit à chaque heure et
pour chaque marché ce que la foule a en cours :
- son déséquilibre : (acheteurs - vendeurs) / total, en dollars engagés ;
- sa CARTE DES LIQUIDATIONS : chaque position à levier L est liquidée si le prix va contre elle d'environ PERTE / L ;
  les acheteurs sont liquidés SOUS le prix (ventes forcées), les vendeurs AU-DESSUS (achats forcés). On compare les
  dollars à liquider à moins d'une bougie du jour au-dessus et au-dessous du prix.
Deux idées connues (Osler 2005 sur les paquets d'ordres stop ; la « chasse aux liquidités » des réseaux) : le prix
irait vers le plus gros paquet (aimant), ou s'emballerait quand un paquet saute (cascade).
Mesure, SANS rien ajuster (donc sans risque d'apprendre par cœur) : lien de rang entre chaque information et le
mouvement des 1 h, 4 h et 1 jour suivants (rapporté à l'agitation), par marché, séparément sur 2024-2025 et sur 2026
(pour voir si ça tient dans le temps). Force = lien moyen x racine(nombre d'heures indépendantes).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.maitres.carte_foule
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.maitres.trades import lire_ostium

FICHIER = dm.RACINE / "data" / "maitres" / "ostium" / "ordres.csv"
PERTE = 0.8                        # part de la mise perdue à la liquidation (approximation : le seuil exact varie)
HORIZONS = {"1 h": 4, "4 h": 16, "1 jour": 96}
COUPURE = pd.Timestamp("2026-01-01")


def mesures_marche(t: pd.DataFrame, prix: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par heure : déséquilibre, carte des liquidations proches, mouvements suivants."""
    p = prix.set_index("time")
    jour = p.resample("1D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    agit = ((jour["high"] - jour["low"]) / jour["close"]).rolling(20, min_periods=5).mean().shift(1)
    debut = pd.to_datetime(t["debut"]).values
    fin = pd.to_datetime(t["fin"]).values
    sens = t["sens"].to_numpy(float)
    dollars = t["volume"].to_numpy(float)
    liq = t["prix_entree"].to_numpy(float) * (1 - sens * PERTE / t["levier"].clip(lower=1).to_numpy(float))
    heures = p.index[(p.index >= pd.Timestamp(debut.min()) + pd.Timedelta(days=30)) & (p.index.minute == 0)]
    c = p["close"]
    lignes = []
    for h in heures:
        a = (debut <= h.to_datetime64()) & (fin > h.to_datetime64())
        if a.sum() < 5:
            continue
        ag = agit.asof(h)
        if not np.isfinite(ag):
            continue
        px = c.asof(h)
        long_, court = dollars[a & (sens > 0)].sum(), dollars[a & (sens < 0)].sum()
        d = (liq[a] - px) / px / ag                          # distance de chaque liquidation, en bougies du jour
        dessous = dollars[a][(d < 0) & (d > -1)].sum()        # acheteurs à liquider sous le prix
        dessus = dollars[a][(d > 0) & (d < 1)].sum()          # vendeurs à liquider au-dessus
        ligne = {"heure": h, "positions": int(a.sum()), "desequilibre": (long_ - court) / (long_ + court),
                 "carte": (dessus - dessous) / (dessus + dessous) if dessus + dessous > 0 else 0.0,
                 "proches_pct": (dessus + dessous) / (long_ + court)}
        i = c.index.searchsorted(h)
        for nom, k in HORIZONS.items():
            j = i + k
            ligne[nom] = (c.iloc[j] / px - 1) / ag if j < len(c) else np.nan
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def main():
    t = lire_ostium(FICHIER).dropna(subset=["marche", "volume", "levier", "prix_entree"])
    resultats, toutes = {}, []
    for marche, g in t.groupby("marche"):
        try:
            prix = dm.charger(marche, jusqua=pd.Timestamp("2100-01-01"))
        except Exception:
            continue
        m = mesures_marche(g, prix).dropna()
        if len(m) < 500:
            continue
        m["marche"] = marche
        toutes.append(m)
        print(f"{marche} : {len(m)} heures, {int(m['positions'].median())} positions ouvertes en médiane", flush=True)
    m = pd.concat(toutes, ignore_index=True)
    m.to_csv(dm.RACINE / "collapsar" / "vie" / "ecole_maitres" / "carte_foule.csv", index=False)
    bilan = {}
    for periode, sel in (("2024-2025 (apprendre)", m["heure"] < COUPURE), ("2026 (jamais vu)", m["heure"] >= COUPURE)):
        x = m[sel]
        bilan[periode] = {}
        for info in ("desequilibre", "carte"):
            for nom, k in HORIZONS.items():
                liens = x.groupby("marche").apply(lambda g: g[info].rank().corr(g[nom].rank()), include_groups=False)
                n_indep = sum(len(g) / max(k / 4, 1) for _, g in x.groupby("marche"))
                force = float(liens.mean() * np.sqrt(n_indep))
                bilan[periode][f"{info} -> {nom}"] = {"lien_moyen": round(float(liens.mean()), 4), "force": round(force, 1),
                                                      "marches_positifs": int((liens > 0).sum()), "marches": int(len(liens))}
    f = dm.RACINE / "collapsar" / "vie" / "ecole_maitres" / "carte_foule.json"
    f.write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    for periode, b in bilan.items():
        print(f"== {periode}")
        for k, v in b.items():
            print(f"  {k:24s} lien moyen {v['lien_moyen']:+.4f}  force {v['force']:+.1f}  "
                  f"(positif sur {v['marches_positifs']}/{v['marches']} marchés)")
    print(f"(enregistré : {f})")


if __name__ == "__main__":
    main()
