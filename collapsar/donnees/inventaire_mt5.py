"""Inventaire de TOUT ce que MetaTrader 5 peut fournir : pour chaque marché et chaque unité de temps (M1 -> MN1),
combien de bougies et depuis quand. Lecture seule.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.donnees.inventaire_mt5"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import MetaTrader5 as mt5

from collapsar.donnees import marches as dm

SYMBOLES = dm.RACINE / "runs" / "20260919_envv2" / "code" / "data" / "aurexis_live" / "symboles.json"
UNITES = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
          "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1,
          "MN1": mt5.TIMEFRAME_MN1}


def main():
    if not mt5.initialize():
        raise SystemExit("MetaTrader n'est pas joignable")
    info = mt5.terminal_info()
    print("bougies max par graphique (réglage MT5) :", info.maxbars)
    noms = json.loads(SYMBOLES.read_text(encoding="utf-8"))
    tous = sorted(s.name for s in (mt5.symbols_get() or []))
    print(f"symboles proposés par le courtier : {len(tous)}")
    rapport = {"maxbars": info.maxbars, "symboles_courtier": len(tous), "marches": {}}
    for nom, sym in noms.items():
        if not sym or not mt5.symbol_select(sym, True):
            continue
        ligne = {}
        for u, tf in UNITES.items():
            r = mt5.copy_rates_range(sym, tf, datetime(1990, 1, 1, tzinfo=timezone.utc), datetime.now(timezone.utc))
            if r is not None and len(r):
                ligne[u] = {"bougies": int(len(r)), "depuis": datetime.utcfromtimestamp(int(r["time"][0])).strftime("%Y-%m-%d")}
        rapport["marches"][nom] = ligne
        print(nom.ljust(8), " | ".join(f"{u} {v['depuis'][:7]} ({v['bougies']})" for u, v in ligne.items()), flush=True)
    mt5.shutdown()
    (dm.RACINE / "collapsar" / "vie" / "inventaire_mt5.json").write_text(json.dumps(rapport, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
