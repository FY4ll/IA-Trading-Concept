"""AUDIT 2 : frais et nuits recalculÃ©s Ã  la main, comparÃ©s aux fonctions du projet.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u collapsar\\audit\\t2_frais.py
"""
import json
import sqlite3

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mains import frais_ftmo, nuit
from collapsar.mains.fiches import fiche
from collapsar.regarder.pistes import chef_crypto as CCR
from collapsar.regarder.pistes import chef_compte_ftmo as CF
from collapsar.regarder.pistes import compte_combine as CC
from collapsar.regarder.smc import noyaux as K

OUT = dm.RACINE / "collapsar" / "vie" / "audit"
OUT.mkdir(parents=True, exist_ok=True)
res = {}

mes = json.loads((dm.RACINE / "collapsar" / "mains" / "conditions_ftmo.json").read_text(encoding="utf-8"))["marches"]

# ---------------------------------------------------------------- 10 trades Ã  la main
cas = [("BTCUSD", "2019-06-03"), ("BTCUSD", "2025-06-02"), ("ETHUSD", "2021-05-03"), ("ETHUSD", "2025-06-02"),
       ("XAUUSD", "2016-03-01"), ("XAUUSD", "2025-06-02"), ("USA500IDXUSD", "2016-03-01"),
       ("USA500IDXUSD", "2025-06-02"), ("EURUSD", "2016-03-01"), ("EURUSD", "2025-06-02")]
lignes = []
for sym, jour in cas:
    df = dm.charger(sym, pd.Timestamp("2100-01-01"), cache=False)
    p = float(df.loc[df["time"] >= pd.Timestamp(jour), "close"].iloc[0])
    f = fiche(sym)
    m = mes.get(f.nom)
    p_rel = frais_ftmo._prix_au_releve(sym)
    projet_ftmo = float(np.asarray(frais_ftmo.frais(sym, p)))
    if f.famille == "devise" or m is None:
        main_ftmo = f.frais * 1.25
        reel = None if m is None else m["ecart_pct"] / 100 + 0.00005   # FTMO : 2,5 $/lot/cÃ´tÃ© = 5 $ / 100 000
    else:
        ecart = m["ecart_pct"] / 100 * p_rel / p
        com = {"metal": 0.000014, "indice": 0.0, "crypto": 0.00065}[f.famille]
        main_ftmo = (ecart + com) * 1.25
        reel = m["ecart_pct"] / 100 + com                                # Ã©cart du relevÃ© (prix d'aujourd'hui) + commission
    lignes.append({"marche": sym, "date": jour, "prix": p, "prix_releve": p_rel,
                   "fiche_x1.25_pct": f.frais * 1.25 * 100, "frais_ftmo_projet_pct": projet_ftmo * 100,
                   "frais_ftmo_main_pct": main_ftmo * 100,
                   "ecart_double_compte": abs(projet_ftmo - main_ftmo) > 1e-12,
                   "ecart_releve_pct": None if m is None else m["ecart_pct"],
                   "cout_reel_sans_glissement_au_prix_du_releve_pct": None if reel is None else reel * 100})
res["dix_trades"] = lignes
print(pd.DataFrame(lignes).round(5).to_string())

# ---------------------------------------------------------------- coÃ»t effectif d'un trade dans les moteurs
# noyaux._cout : entrÃ©e limite = 0,5 x facteur ; sortie objectif = 0,5 ; stop = +0,5 ; entrÃ©e au marchÃ© = +0,5
fr = 0.00012
cases = {"limite -> objectif": K._cout(1.0, fr, 1.0, False, False) / fr,
         "limite -> stop": K._cout(1.0, fr, 1.0, True, False) / fr,
         "marchÃ© -> objectif": K._cout(1.0, fr, 1.0, False, True) / fr,
         "marchÃ© -> stop": K._cout(1.0, fr, 1.0, True, True) / fr,
         "marchÃ© -> stop, 1re heure NY US500 (x1,16)": K._cout(1.0, fr, 1.16, True, True) / fr}
res["noyaux_cout_en_fiches"] = cases
print("noyaux : coÃ»t en nombre de Â« fiches Â» (aller-retour) :", {k: round(v, 3) for k, v in cases.items()})
# trade_nono : entrÃ©e 0,5 x facteur, tiers Ã  l'objectif 0,5/3 chacun, stop = 1 par tiers -> 1,5 fiche si stop
print("trade_nono : objectif = 1,0 fiche ; stop = 1,5 fiche (pas de x1,25 dans le labo SMC : fiche brute)")
# chef_compte / trois_briques : frais crypto = (0,065 % + Ã©cart) x 1,25 ; stop = 1,5 x
for c in ("BTC", "ETH", "SOL"):
    print(f"crypto {c}: frais_rt projet {CC.frais_rt(c) * 100:.5f} % ; chef_compte {CF.frais(c) * 100:.5f} %")
res["crypto_frais_rt_pct"] = {c: CC.frais_rt(c) * 100 for c in ("BTC", "ETH", "SOL")}

# ---------------------------------------------------------------- nuits : compte Ã  la main
JOUR = 86400 * 10 ** 9
def ny(s):
    return np.array([pd.Timestamp(s).value], np.int64)
nuits_cas = [("lun 10h NY -> lun 16h NY", "2024-03-04 10:00", "2024-03-04 16:00", 0),
             ("lun 16h NY -> lun 17h NY (minuit serveur Ã  17h NY)", "2024-03-04 16:00", "2024-03-04 17:30", 1),
             ("lun 10h -> mar 10h", "2024-03-04 10:00", "2024-03-05 10:00", 1),
             ("mer 10h -> jeu 10h", "2024-03-06 10:00", "2024-03-07 10:00", 1),
             ("ven 10h -> lun 10h", "2024-03-08 10:00", "2024-03-11 10:00", 3),
             ("ven 10h -> sam 10h", "2024-03-08 10:00", "2024-03-09 10:00", 3),
             ("lun 10h -> lun suivant 10h", "2024-03-04 10:00", "2024-03-11 10:00", 7)]
nc = []
for nom, a, b, attendu in nuits_cas:
    v = int(CCR.nuits(ny(a), ny(b))[0])
    nc.append({"cas": nom, "projet": v, "attendu_ftmo_crypto (vendredi x3)": attendu, "ok": v == attendu})
res["nuits_chef_crypto"] = nc
print(pd.DataFrame(nc).to_string())

# horloge (Ã©cole) : triple le mercredi pour TOUS les marchÃ©s
t = pd.date_range("2024-03-04 23:45", periods=4 * 24 * 7, freq="15min")
js = (t.normalize() - pd.Timestamp("2000-01-01")).days.to_numpy()
n_ = np.zeros(len(t)); n_[1:] = (js[1:] != js[:-1]).astype(float)
n_[1:] *= np.where(t.dayofweek.to_numpy()[1:] == 3, 3.0, 1.0)
res["horloge_nuits_par_semaine_tous_marches"] = float(n_.sum())
print("horloge : nuits payÃ©es sur 7 jours glissants (tous marchÃ©s, triple mercredi) =", n_.sum(),
      "; FTMO indices/Ã©nergies/crypto : triple le VENDREDI (jour_triple=5 dans conditions_ftmo.json)")

# taux de nuit du modÃ¨le contre le relevÃ© FTMO (15/10/2026)
tn = []
for sym in ("USA500IDXUSD", "USATECHIDXUSD", "XAUUSD", "EURUSD", "USDJPY", "GBPUSD", "DEUIDXEUR"):
    f = fiche(sym)
    a, v = nuit.taux_nuit(f, pd.DatetimeIndex(["2026-10-14"]))
    m = mes.get(f.nom, {})
    tn.append({"marche": f.nom, "modele_achat_%an": a[0] * 100, "releve_achat_%an": m.get("nuit_achat", np.nan) * 100,
               "modele_vente_%an": v[0] * 100, "releve_vente_%an": m.get("nuit_vente", np.nan) * 100,
               "fiche_achat": f.nuit_achat * 100, "fiche_vente": f.nuit_vente * 100})
res["nuit_modele_contre_releve"] = tn
print(pd.DataFrame(tn).round(2).to_string())

# ---------------------------------------------------------------- glissement rÃ©el mesurÃ© (ancien direct AUREX, Tradeco)
c = sqlite3.connect(dm.RACINE / "runs/20260919_envv2/code/data/decision_journal.sqlite")
ex = pd.read_sql("select * from executions", c)
tr = pd.read_sql("select * from trades", c)
dec = pd.read_sql("select spread_pct, price, ts_utc from decisions where spread_pct is not null", c)
ex = ex[ex["price_req"] > 0]
gl = ((ex["price_filled"] - ex["price_req"]) * np.where(ex["direction"].astype(str).str.lower().str.startswith(("b", "l", "1")), 1, -1)
      / ex["price_req"] * 100)
print("exÃ©cutions AUREX (or, Tradeco) : glissement dÃ©favorable %", gl.round(4).tolist())
tr["sl_ok"] = tr["sl"] > 0
st = tr[tr["close_reason"].astype(str).str.contains("sl|stop", case=False) & tr["sl_ok"]]
sens = np.where(tr.loc[st.index, "direction"].astype(str).str.lower().str.startswith(("b", "l", "1")), 1, -1)
gls = (st["sl"] - st["close_price"]) * sens / st["close_price"] * 100
print("stops AUREX : glissement dÃ©favorable au stop (%) :", gls.round(4).tolist())
print("Ã©cart or relevÃ© dans les dÃ©cisions AUREX : mÃ©diane %", float(dec["spread_pct"].median()),
      "quantiles 10/90 %", dec["spread_pct"].quantile([0.1, 0.9]).round(5).tolist())
res["aurex_direct"] = {"glissement_entree_pct": gl.round(5).tolist(), "glissement_stop_pct": gls.round(5).tolist(),
                       "ecart_or_median_pct": float(dec["spread_pct"].median()),
                       "close_reasons": tr["close_reason"].astype(str).value_counts().to_dict()}
print(tr["close_reason"].astype(str).value_counts().to_dict())
(OUT / "t2_frais.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

