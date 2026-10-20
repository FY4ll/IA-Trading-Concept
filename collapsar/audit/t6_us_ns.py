"""AUDIT 6 : effet de l'unité des heures (pandas 3 lit les dates en MICROsecondes, le labo SMC compte en NANOsecondes).
1) dm.charger : premier appel (sans cache) -> µs ; appels suivants (cache .npz) -> ns : résultats non reproductibles.
2) labo SMC (concepts) sur EURUSD H1 2015-2023 : heures en µs (tel quel) contre ns (corrigé).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.audit.t6_us_ns
"""
import json
import math

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.regarder.smc import labo
from collapsar.regarder.smc.bougies import bougies, minutes

OUT = dm.RACINE / "collapsar" / "vie" / "audit"
res = {}
a = dm.charger("EURUSD", pd.Timestamp("2024-01-01"), cache=False)
b = dm.charger("EURUSD", pd.Timestamp("2024-01-01"), cache=True)
res["dm_charger_dtype"] = {"sans_cache (= 1er appel)": str(a["time"].dtype), "avec_cache": str(b["time"].dtype)}
print(res["dm_charger_dtype"], flush=True)

m1 = minutes("EURUSD")
m1 = m1[m1["ny"] < pd.Timestamp("2024-01-01")]
print("minutes :", m1["ny"].dtype, flush=True)
out = {}
for nom, m in (("µs (tel quel)", m1), ("ns (corrigé)", m1.assign(ny=m1["ny"].astype("datetime64[ns]")))):
    bg = bougies("EURUSD", "H1", pd.Timestamp("2024-01-01"), m)
    tr, _ = labo.tout(bg)
    for c, g in tr.groupby("concept"):
        dd = (g["R"] - g["R_inverse"]) / 2
        out.setdefault(c, {})[nom] = {"trades": len(g), "R": float(g["R"].mean()),
                                      "force": float(dd.mean() / dd.std() * math.sqrt(len(g))) if len(g) > 2 else None}
    print(nom, "fini", flush=True)
df = pd.DataFrame({c: {f"{k} {n}": v for n, x in d.items() for k, v in x.items()} for c, d in out.items()}).T
print(df.round(3).to_string(), flush=True)
res["labo_EURUSD_H1"] = df.round(4).to_dict("index")
d_r = (df["R ns (corrigé)"] - df["R µs (tel quel)"])
res["labo_EURUSD_H1_ecart_R_moyen"] = float(d_r.mean())
res["labo_EURUSD_H1_ecart_R_max_abs"] = float(d_r.abs().max())
print("écart moyen de R (ns - µs) :", d_r.mean(), "max", d_r.abs().max())
(OUT / "t6_us_ns.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
