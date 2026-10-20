"""Audit : les minutes (mt) et les bougies (bt) du labo SMC sont-elles dans la même unité ?"""
import numpy as np
import pandas as pd

from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.bougies import bougies, minutes

m1 = minutes("EURUSD")
m1 = m1[m1["ny"] < pd.Timestamp("2016-01-01")]
print("dtype ny :", m1["ny"].dtype)
b = bougies("EURUSD", "M15", pd.Timestamp("2016-01-01"), m1)
print("bt[100] :", b.bt[100], pd.Timestamp(b.bt[100]), "mt[0..2] :", b.mt[:3], [pd.Timestamp(x) for x in b.mt[:3]])
print("duree :", b.duree)
a, z = K._minutes_de_la_bougie(b.mt, b.bt[100], b.duree)
print("minutes de la bougie 100 :", a, z)
for i in (100, 5000, 20000):
    a, z = K._minutes_de_la_bougie(b.mt, b.bt[i], b.duree)
    f = K._remplissage(b.o, b.mt, b.ml, b.mh, b.bt, b.duree, i, 1, b.l[i] + 1e-9)
    print(i, pd.Timestamp(b.bt[i]), "minutes", a, z, "remplissage", f)
