"""AUDIT 1 : réponses connues (acheter-garder, tricheuse, hasard) passées dans les MOTEURS du projet.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.audit.t1_reponses
"""
import json
import math

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche
from collapsar.regarder import bande_bruit as BB
from collapsar.regarder.pistes import bitcoin_journee as BJ
from collapsar.regarder.pistes import chef_compte_ftmo as CF
from collapsar.regarder.smc import noyaux as K

OUT = dm.RACINE / "collapsar" / "vie" / "audit"
VIE = dm.RACINE / "collapsar" / "vie"
res = {}


def p(*a):
    print(*a, flush=True)


# ================================================================ (a) acheter et garder
p("=== (a) acheter et garder")
ag = []
for sym, de, a in (("BTCUSD", "2018-01-01", "2024-01-01"), ("XAUUSD", "2015-01-01", "2024-01-01"),
                   ("USA500IDXUSD", "2015-01-01", "2024-01-01")):
    df = dm.charger(sym, pd.Timestamp(a), cache=False)
    df = df[df["time"] >= pd.Timestamp(de)].reset_index(drop=True)
    d = dm.echelle(df, "jour")
    o, h, l, c = (np.ascontiguousarray(d[k]) for k in ("open", "high", "low", "close"))
    fr = fiche(sym).frais
    e = 0
    entree = o[e]
    risque = 0.99 * entree                                   # stop à 1 % du prix : jamais touché
    tenue = len(c) - 1 - e
    r, cr = K._resultat_marche(o, h, l, c, e, 1, entree, risque, 1000 * entree, tenue, fr, 1.0)
    moteur = r * risque / entree
    main = c[-1] / o[0] - 1 - fr * 1.5                       # coût moteur = 0,5 entrée + 0,5 sortie + 0,5 marché
    ag.append({"marche": sym, "periode": f"{de} -> {a}", "rendement_prix_pct": (c[-1] / o[0] - 1) * 100,
               "moteur_noyaux_pct": moteur * 100, "main_moins_frais_pct": main * 100,
               "ecart": abs(moteur - main)})
p(pd.DataFrame(ag).to_string())
res["acheter_garder_noyaux"] = ag

# bande_bruit.journalier : un achat par séance d'ouverture à clôture (minutes HistData), levier 1
from collapsar.regarder import orb
s = {j: x for j, x in orb.seances(orb.minutes("US500")).items() if pd.Timestamp("2015-01-01") <= j < pd.Timestamp("2024-01-01")}
jours = sorted(s)
r_j = np.array([s[j][-1, 4] / s[j][0, 1] - 1 for j in jours])
fr = fiche("USA500IDXUSD").frais * 1.25
t = pd.DataFrame({"jour": jours, "brut": r_j, "frais": fr, "levier_par_cible": 1.0})
g = BB.journalier(t, 1.0)
res["bande_bruit_journalier_achat_seance"] = {"moteur_somme_pct": float(g.sum() * 100),
                                              "main_somme_pct": float((r_j - fr).sum() * 100),
                                              "seances": len(jours)}
p("bande_bruit.journalier, achat de chaque séance US500 2015-2023 :", res["bande_bruit_journalier_achat_seance"])

# bitcoin_journee.journalier : achat 00h00 -> 23h45 chaque jour tradé, exposition 1
m = BJ.matrice("2024-01-01")
agit = BJ.agitation(m)
liste = [(d, 1, 0, BJ.FIN) for d in np.flatnonzero(m["valide"])]
tb = BJ.trades(m, liste, agit)
g, w = BJ.journalier(tb, 0.0001, 100.0)                       # cible 100 -> exposition plafonnée à 1
main = (tb["r_prix"] - 0.0001).sum()
res["bitcoin_journalier_achat_jour"] = {"moteur_somme_pct": float(g.sum() * 100), "main_pct": float(main * 100),
                                        "pire_point_min_pct": float(w.min() * 100),
                                        "pire_point_main_min_pct": float(((tb["adv_achat"].clip(upper=0)) - 0.0001).min() * 100)}
p("bitcoin_journee.journalier achat chaque jour :", res["bitcoin_journalier_achat_jour"])

# chef_compte_ftmo.simuler : UN achat BTC 100 % du compte du 04/01/2021 au 01/03/2021, frais et nuits à la main
t_z, (L, H, C), poids_nuit, npas = CF.tout_charger()
cr_btc = CF.CRYPTOS.index("BTC")
k0, k1 = CF.pas_date("2021-01-04 10:00"), CF.pas_date("2021-03-01 10:00")
e0 = C[cr_btc, k0 - 1]
x1 = C[cr_btc, k1 - 1]
fr = CF.frais("BTC")
xs = np.full((1, 2, 3), k1, np.int64)
xp = np.full((1, 2, 3), x1)
xk = np.full((1, 2, 3), 2, np.int64)
jo = np.zeros((npas // 96 + 2, 4))
r = CF.simuler(L, H, C, poids_nuit, np.array([k0]), np.array([cr_btc]), np.array([1]), np.array([e0]),
               np.array([1.0]), np.array([fr]), xs, xp, xk, np.array([1.0, 0.0, 0.0]), np.array([1]), 1.0, 4, 10.0,
               k0, k1 + 96, 0, jo)
fin_moteur = jo[(k1 + 95) // 96, 0]
nuits = poids_nuit[k0 // 96 + 1: k1 // 96 + 1].sum()
montant = 100000.0
fin_main = 100000 + montant * (x1 / e0 - 1) - montant * fr * 0.5 - montant * (x1 / e0) * 0 - montant * fr * 0.5 \
    - montant * 0.30 / 360 * nuits
res["chef_compte_un_achat_btc"] = {"prix_entree": float(e0), "prix_sortie": float(x1), "nuits": float(nuits),
                                   "jours_calendaires": (k1 - k0) / 96, "solde_moteur": float(fin_moteur),
                                   "solde_main": float(fin_main), "ecart_usd": float(fin_moteur - fin_main),
                                   "baisse_max_moteur_pct": float(r[2] * 100)}
p("chef_compte_ftmo.simuler, 1 achat BTC :", res["chef_compte_un_achat_btc"])

# ================================================================ (b) tricheuse  (c) hasard
p("=== (b) tricheuse / (c) hasard")
tb_bb = pd.read_csv(VIE / "bande_bruit" / "trades_apprentissage.csv", parse_dates=["jour"])
out = {}
for mk in ("US500", "NAS100", "XAUUSD"):
    t = tb_bb[(tb_bb["marche"] == mk) & (tb_bb["jour"] < "2022-01-01")].reset_index(drop=True)
    tous = pd.bdate_range("2015-01-01", "2021-12-31")
    triche = np.sign(t["brut"].to_numpy()) * t["sens"].to_numpy() * t["sens"].to_numpy()
    g_vrai = BB.journalier(t, 0.01).reindex(tous, fill_value=0.0)
    g_tri = BB.journalier(t, 0.01, np.sign(t["brut"].to_numpy())).reindex(tous, fill_value=0.0)
    rng = np.random.default_rng(1)
    hasard = [BB.journalier(t, 0.01, rng.choice([-1, 1], len(t))).sum() for _ in range(400)]
    lev = np.minimum(BB.LEVIER_MAX, 0.01 * t["levier_par_cible"].to_numpy())
    attendu = -(lev * t["frais"].to_numpy()).sum()
    an = len(tous) / 252
    out[mk] = {"vrai_pct_an": g_vrai.sum() / an * 100, "tricheuse_pct_an": g_tri.sum() / an * 100,
               "tricheuse_challenge": BB.challenge(g_tri), "hasard_moyen_pct_an": float(np.mean(hasard)) / an * 100,
               "hasard_attendu_moins_frais_pct_an": attendu / an * 100,
               "hasard_ecart_type_pct_an": float(np.std(hasard)) / an * 100}
    p(mk, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out[mk].items()})
res["bande_bruit_triche_hasard"] = out

tb_bj = pd.read_csv(VIE / "pistes" / "bitcoin_journee" / "trades_apprentissage.csv", parse_dates=["jour"])
out = {}
for v in ("C2", "A3", "B1"):
    t = tb_bj[(tb_bj["variante"] == v) & (tb_bj["jour"] < "2022-01-01") & (tb_bj["jour"] >= "2017-05-01")].reset_index(drop=True)
    vrai, _ = BJ.journalier(t, 0.0008 * 1.25, 0.01)
    tri, _ = BJ.journalier(t, 0.0008 * 1.25, 0.01, np.sign(t["sens"] * t["r_prix"]).to_numpy())
    rng = np.random.default_rng(2)
    has = [BJ.journalier(t, 0.0008 * 1.25, 0.01, rng.choice([-1, 1], len(t)))[0].sum() for _ in range(200)]
    expo = np.minimum(1.0, 0.01 / t["agitation"].to_numpy())
    out[v] = {"vrai_somme_pct": vrai.sum() * 100, "tricheuse_somme_pct": tri.sum() * 100,
              "hasard_moyen_pct": float(np.mean(has)) * 100, "hasard_attendu_pct": float(-(expo * 0.001).sum() * 100),
              "hasard_ecart_type_pct": float(np.std(has)) * 100}
    p(v, {k: round(x, 2) for k, x in out[v].items()})
res["bitcoin_triche_hasard"] = out

# SMC gigogne : (R + R_inverse)/2 doit valoir à peu près -coût (le sens au hasard ne gagne rien avant frais)
gt = pd.read_csv(VIE / "smc" / "plancher_trades_2015_2023.csv")
out = {}
for (grp, cpt), g in gt.groupby(["groupe", "concept"]):
    moy = (g["R"] + g["R_inverse"]) / 2
    les_deux_stop = ((g["R"] < -0.999) & (g["R_inverse"] < -0.999)).mean() * 100
    out[f"{grp} | {cpt}"] = {"trades": len(g), "R_moyen": g["R"].mean(), "hasard_(R+Rinv)/2": moy.mean(),
                             "moins_cout_R": -g["cout_R"].mean(), "biais_execution_R": moy.mean() + g["cout_R"].mean(),
                             "tricheuse_max(R,Rinv)": np.maximum(g["R"], g["R_inverse"]).mean(),
                             "trade_ET_jumeau_stoppes_pct": les_deux_stop}
od = pd.DataFrame(out).T
p(od.round(3).to_string())
res["smc_plancher_hasard"] = od.round(4).to_dict("index")

# chef_compte : compte tricheur (sens = meilleur de R_A / R_A_inv) et compte au hasard, P1
t = t_z
fill = t["fill_pas"].to_numpy().astype(np.int64)
crr = t["crypto"].map({c: j for j, c in enumerate(CF.CRYPTOS)}).to_numpy().astype(np.int64)
sens = t["sens"].to_numpy().astype(np.int64)
e = t["prix"].to_numpy(float)
sf = t["stop_frac"].to_numpy(float)
frr = t["frais"].to_numpy(float)
w = CF.GESTIONS["A"][0]
xs, xp, xk = CF.tableaux_sortie(t, "A")
d0, d1 = CF.pas_date("2018-01-01"), CF.pas_date("2024-01-01")
mois = (d1 - d0) / 96 / 30.44


def compte(signes):
    jo = np.zeros((npas // 96 + 2, 4))
    rr = CF.simuler(L, H, C, poids_nuit, fill, crr, sens, e, sf, frr, xs, xp, xk, w, signes, 0.0025, 4, 0.02, d0, d1, 0, jo)
    jj = jo[d0 // 96:d1 // 96]
    jj = jj[jj[:, 0] > 0]
    fin = float(jj[-1, 1])
    return ((fin / 1e5) ** (1 / mois) - 1) * 100, rr


vrai_pm, _ = compte(np.ones(len(t), np.int64))
tri_pm, _ = compte(np.where(t["R_A"].to_numpy() >= t["R_A_inv"].to_numpy(), 1, -1).astype(np.int64))
rng = np.random.default_rng(3)
has = [compte(rng.choice(np.array([-1, 1], np.int64), len(t)))[0] for _ in range(10)]
res["chef_compte_triche_hasard_2018_2023"] = {"vrai_pct_mois": vrai_pm, "tricheuse_pct_mois": tri_pm,
                                              "hasard_pct_mois_moyenne": float(np.mean(has)),
                                              "hasard_pct_mois_min_max": [float(min(has)), float(max(has))]}
p("chef_compte P1 2018-2023 :", res["chef_compte_triche_hasard_2018_2023"])

(OUT / "t1_reponses.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
p("FINI")
