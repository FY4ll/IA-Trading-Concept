"""LA FOULE SE TROMPE-T-ELLE DE FAÇON PRÉVISIBLE ? (15/10/2026)

Avec TOUS les trades d'Ostium (des milliers de petits traders, morts compris), on reconstruit, chaque jour et pour
chaque marché, la position nette de la foule (achats ouverts - ventes ouvertes, en dollars) et son changement du
jour. Question : ce penchant de la foule annonce-t-il le prix des jours suivants (dans le même sens = la foule a
raison ; à l'envers = la foule a tort, ce que disent beaucoup d'études sur les particuliers) ?
- mesure : lien de rang jour par jour entre le penchant (ou son changement) et le mouvement des 1 et 5 jours
  SUIVANTS, rapporté à l'agitation ; force = lien x racine(nombre de jours indépendants) ;
- on regarde aussi la tendance passée : si la foule achète simplement après une baisse, son « avis » n'est que la
  tendance à l'envers, déjà visible sur le graphique.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.maitres.foule
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.maitres.trades import lire_ostium

FICHIER = dm.RACINE / "data" / "maitres" / "ostium" / "ordres.csv"


def penchant_quotidien(t: pd.DataFrame, jours: pd.DatetimeIndex) -> pd.DataFrame:
    """Position nette ouverte de la foule à la fin de chaque jour (en dollars), par marché."""
    sortie = {}
    for marche, g in t.groupby("marche"):
        ouv = pd.Series(g["sens"].to_numpy() * g["volume"].to_numpy(), index=pd.to_datetime(g["debut"]).dt.floor("1D"))
        fer = pd.Series(-g["sens"].to_numpy() * g["volume"].to_numpy(), index=pd.to_datetime(g["fin"]).dt.floor("1D"))
        flux = pd.concat([ouv, fer]).groupby(level=0).sum().reindex(jours, fill_value=0.0)
        sortie[marche] = flux.cumsum()
    return pd.DataFrame(sortie)


def main():
    t = lire_ostium(FICHIER).dropna(subset=["marche", "volume"])
    jours = pd.date_range(pd.to_datetime(t["debut"]).min().floor("1D"), pd.to_datetime(t["fin"]).max().floor("1D"))
    net = penchant_quotidien(t, jours)
    brut = t.assign(v=t["volume"]).groupby("marche")["v"].median()
    resultats = {}
    lignes = []
    for marche in net.columns:
        try:
            d = dm.charger(marche, jusqua=pd.Timestamp("2026-12-31"))
        except Exception:
            continue
        j = d.set_index("time").resample("1D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
        agit = ((j["high"] - j["low"]) / j["close"]).rolling(20, min_periods=5).mean()
        r1 = (j["close"].shift(-1) / j["close"] - 1) / agit
        r5 = (j["close"].shift(-5) / j["close"] - 1) / agit
        passe5 = (j["close"] / j["close"].shift(5) - 1) / agit
        x = pd.DataFrame({"net": net[marche].reindex(j.index), "r1": r1, "r5": r5, "passe5": passe5}).dropna()
        x = x[x.index >= jours[0] + pd.Timedelta(days=30)]
        if len(x) < 120 or (x["net"] == 0).mean() > 0.5:
            continue
        x["penchant"] = x["net"] / x["net"].abs().rolling(60, min_periods=10).mean()
        x["changement"] = x["net"].diff(5) / x["net"].abs().rolling(60, min_periods=10).mean()
        x = x.dropna()
        x["marche"] = marche
        lignes.append(x)
        rang = lambda a, b: float(x[a].rank().corr(x[b].rank()))
        resultats[marche] = {"jours": len(x), "trades": int((t["marche"] == marche).sum()),
                             "penchant_vs_1j": rang("penchant", "r1"), "penchant_vs_5j": rang("penchant", "r5"),
                             "changement_vs_5j": rang("changement", "r5"), "penchant_vs_passe5": rang("penchant", "passe5"),
                             "changement_vs_passe5": rang("changement", "passe5")}
    tout = pd.concat(lignes)
    # ensemble : moyenne des liens par marché ; force approximative avec jours indépendants (5 jours se chevauchent)
    m = pd.DataFrame(resultats).T
    n_jours = m["jours"].sum()
    bilan = {k: {"lien_moyen": round(float(m[k].mean()), 3),
                 "force": round(float(m[k].mean() * np.sqrt(n_jours / (5 if "5j" in k else 1))), 1)}
             for k in ("penchant_vs_1j", "penchant_vs_5j", "changement_vs_5j", "penchant_vs_passe5", "changement_vs_passe5")}
    sortie = {"bilan": bilan, "par_marche": resultats}
    f = dm.RACINE / "collapsar" / "vie" / "ecole_maitres" / "foule.json"
    f.write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(m)} marchés, {n_jours} jours-marché")
    for k, b in bilan.items():
        print(f"  {k:22s} lien moyen {b['lien_moyen']:+.3f}  force {b['force']:+.1f}")
    print(m.round(3).to_string())
    print(f"(enregistré : {f})")


if __name__ == "__main__":
    main()
