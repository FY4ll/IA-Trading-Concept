"""AUDIT 8 : bitcoin_journee compte les mois = jours tradés / 261 x 12 ; part des jours ouvrés réellement « tradables »."""
import numpy as np
import pandas as pd

from collapsar.regarder.pistes import bitcoin_journee as BJ

m = BJ.matrice("2024-01-01")
agit = BJ.agitation(m)
j = m["jours"]
for de, a in (("2017-05-01", "2022-01-01"), ("2022-01-01", "2024-01-01")):
    jt = j[m["valide"] & (j >= pd.Timestamp(de)) & (j < pd.Timestamp(a)) & np.isfinite(agit)]
    bd = pd.bdate_range(de, pd.Timestamp(a) - pd.Timedelta(days=1))
    mois_cal = (pd.Timestamp(a) - pd.Timestamp(de)).days / 30.44
    mois_projet = len(jt) / BJ.JOURS_AN * 12
    print(de, a, "jours tradables", len(jt), "jours ouvrés", len(bd), "mois projet", round(mois_projet, 1),
          "mois calendaires", round(mois_cal, 1), "-> %/mois surestimé de", round((mois_cal / mois_projet - 1) * 100, 1), "%")
