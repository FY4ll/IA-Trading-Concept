"""AUDIT 4 : le compte (journalier / challenge de bande_bruit, conventions des comptes crypto).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.audit.t4_compte
"""
import json

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.regarder import bande_bruit as BB
from collapsar.regarder import orb
from collapsar.regarder.pistes import bitcoin_journee as BJ

OUT = dm.RACINE / "collapsar" / "vie" / "audit"
VIE = dm.RACINE / "collapsar" / "vie"
res = {}

# 1) la règle -5 % de bande_bruit.challenge ne voit que la clôture du jour : on ajoute le pire point de la journée
tb = pd.read_csv(VIE / "bande_bruit" / "trades_apprentissage.csv", parse_dates=["jour"])
s = {j: a for j, a in orb.seances(orb.minutes("US500")).items() if j < pd.Timestamp("2024-01-01")}
jours, O, H, L, C = BB.matrice(s)
pos = {j: k for k, j in enumerate(jours)}
t = tb[tb["marche"] == "US500"].reset_index(drop=True)
adv = []
for r in t.itertuples():
    k = pos[r.jour]
    seg = slice(r.m_entree + 1, r.m_sortie + 1)
    if r.sens > 0:
        adv.append(min(L[k, seg].min() / r.prix - 1, 0))
    else:
        adv.append(min(1 - H[k, seg].max() / r.prix, 0))
t["adv"] = adv
out = {}
for cible in (0.01, 0.02, 0.03):
    lev = np.minimum(BB.LEVIER_MAX, cible * t["levier_par_cible"].to_numpy())
    g_tr = lev * (t["brut"].to_numpy() - t["frais"].to_numpy())
    pire_tr = lev * (t["adv"].to_numpy() - t["frais"].to_numpy())
    gs = pd.Series(g_tr, index=t["jour"])
    avant = gs.groupby(level=0).cumsum().to_numpy() - g_tr
    w = pd.Series(np.minimum(avant + pire_tr, 0), index=t["jour"]).groupby(level=0).min()
    g = gs.groupby(level=0).sum()
    tous = pd.bdate_range("2015-01-01", "2023-12-31")
    g, w = g.reindex(tous, fill_value=0.0), w.reindex(tous, fill_value=0.0)
    clot = BJ.challenge(g.to_numpy(), np.minimum(g.to_numpy(), 0))
    intra = BJ.challenge(g.to_numpy(), w.to_numpy())
    bbc = BB.challenge(g)
    out[f"cible {cible * 100:.0f} %"] = {"BB.challenge (clôture)": bbc, "clôture seule": clot, "pire point compris": intra,
                                        "pire_point_jour_min_pct": float(w.min() * 100), "pire_cloture_jour_pct": float(g.min() * 100),
                                        "levier_moyen": float(lev.mean())}
    print(cible, json.dumps(out[f"cible {cible * 100:.0f} %"], default=float, ensure_ascii=False), flush=True)
res["bande_bruit_regle_5pct"] = out

# 2) les « inachevés » dans le dénominateur du % réussi
ap = json.loads((VIE / "bande_bruit" / "apprentissage.json").read_text(encoding="utf-8"))
inach = {}
for per, P in ap["periodes"].items():
    for c, x in P["challenges"].items():
        e = x["elle"]
        fini = e["reussis_pct"] + e["morts_pct"]
        inach[f"{per} cible {c}"] = {"reussis_pct_affiche": e["reussis_pct"], "inacheves_pct": e["inacheves_pct"],
                                    "reussis_parmi_termines_pct": 100 * e["reussis_pct"] / fini if fini else None}
res["inacheves"] = inach
print(json.dumps(inach, ensure_ascii=False, default=float), flush=True)

# 3) année = jours ouvrés / 252 alors que bdate_range compte ~261 jours par an (fériés compris)
bd = pd.bdate_range("2015-01-01", "2021-12-31")
res["facteur_annee_bande_bruit"] = {"jours_ouvres_par_an": len(bd) / 7, "an_compte": len(bd) / 252 / 7,
                                    "sous_estimation_gain_pct": (1 - 252 / (len(bd) / 7)) * 100}
print(res["facteur_annee_bande_bruit"], flush=True)

# 4) comptes crypto : les pires points de positions différentes sont additionnés comme s'ils arrivaient au même instant.
#    Ordre de grandeur : BTC + ETH achetés ensemble ; somme des pires points de chaque bougie de 1 h contre le pire point
#    réel du panier (lu sur les bougies de 15 min qui la composent).
b = dm.charger("BTCUSD", pd.Timestamp("2024-01-01"), cache=False).set_index("time")
e = dm.charger("ETHUSD", pd.Timestamp("2024-01-01"), cache=False).set_index("time")
idx = b.index.intersection(e.index)
b, e = b.loc[idx], e.loc[idx]
hr = idx.floor("1h")
ob, oe = b["open"].groupby(hr).transform("first"), e["open"].groupby(hr).transform("first")
somme = (b["low"] / ob - 1).groupby(hr).min() + (e["low"] / oe - 1).groupby(hr).min()
panier = ((b["low"] / ob - 1) + (e["low"] / oe - 1)).groupby(hr).min()       # pires des deux dans la MÊME bougie de 15 min
exces = (panier - somme)
res["somme_des_pires_points_BTC_ETH_1h"] = {"exces_moyen_pct_du_montant_par_heure": float(exces.mean() * 100 / 2),
                                            "exces_p99_pct": float(exces.quantile(0.99) * 100 / 2),
                                            "pire_point_moyen_somme_pct": float(somme.mean() * 100 / 2)}
print(res["somme_des_pires_points_BTC_ETH_1h"], flush=True)

# 5) BTC : bougies manquantes comblées « plates » dans les jours tradés
m = BJ.matrice("2024-01-01")
df = dm.charger("BTCUSD", pd.Timestamp("2024-01-01"), cache=False)
t_ = pd.to_datetime(df["time"])
par_jour = t_.dt.normalize().value_counts()
v = m["jours"][m["valide"]]
nb = par_jour.reindex(v).fillna(0)
res["btc_bougies_comblees_pct"] = float((96 - nb).clip(lower=0).sum() / (96 * len(v)) * 100)
print("BTC : part des bougies de 15 min comblées dans les jours tradés :", res["btc_bougies_comblees_pct"], flush=True)
(OUT / "t4_compte.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print("FINI")
