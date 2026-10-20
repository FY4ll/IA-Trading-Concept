"""Nos bougies téléchargées (Dukascopy) sont-elles à la même heure que celles du serveur MetaTrader ? Par mois :
décalage (en bougies de 15 min) qui fait le mieux coïncider les deux séries. 0 = alignées.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.surveillance.comparer_heures_prix
"""
from __future__ import annotations

from datetime import datetime

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm

MARCHES = ("EURUSD", "GBPUSD", "USDJPY")


def main():
    if not mt5.initialize():
        raise SystemExit(f"MetaTrader injoignable : {mt5.last_error()}")
    for m in MARCHES:
        mt5.symbol_select(m, True)
        morceaux = []                                     # une demande par mois (une demande trop longue revient vide)
        for debut in pd.date_range("2023-01-01", "2026-10-01", freq="MS"):
            r = mt5.copy_rates_range(m, mt5.TIMEFRAME_M15, debut.to_pydatetime(),
                                     (debut + pd.offsets.MonthBegin(1)).to_pydatetime())
            if r is not None and len(r):
                morceaux.append(pd.DataFrame(r))
        if not morceaux:
            print(m, "pas d'historique chez le courtier")
            continue
        b = pd.concat(morceaux).drop_duplicates("time")
        b["time"] = pd.to_datetime(b["time"], unit="s")
        d = dm.charger(m, jusqua=pd.Timestamp("2026-10-01"), cache=False)
        for mois in pd.date_range("2023-01-01", "2026-09-01", freq="2MS"):
            fin = mois + pd.offsets.MonthBegin(1)
            x = d[(d["time"] >= mois) & (d["time"] < fin)].set_index("time")["close"]
            y = b[(b["time"] >= mois - pd.Timedelta(hours=3)) & (b["time"] < fin + pd.Timedelta(hours=3))] \
                .set_index("time")["close"]
            if len(x) < 500 or len(y) < 500:
                continue
            rx = np.log(x).diff()
            meilleur, lien = None, -1
            for k in range(-8, 9):
                ry = np.log(y).diff()
                ry.index = ry.index - pd.Timedelta(minutes=15 * k)
                commun = rx.index.intersection(ry.index)
                c = np.corrcoef(rx.loc[commun].fillna(0), ry.loc[commun].fillna(0))[0, 1]
                if c > lien:
                    meilleur, lien = k, c
            print(f"{m} {mois:%Y-%m} : décalage {meilleur:+d} bougie(s) (accord {lien:.0%})", flush=True)
    mt5.shutdown()


if __name__ == "__main__":
    main()
