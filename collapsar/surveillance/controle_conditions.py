"""Check-up de cohérence : le simulateur (mains/fiches.py) comparé aux VRAIES conditions du compte MetaTrader ouvert.

Pour chaque marché : écart réel, frais de nuit, pas de lot, levier, pauses de cotation, et ressemblance entre nos
données d'apprentissage et les prix du courtier. À relancer sur le compte FTMO dès qu'il existe.
Lecture seule : aucun ordre n'est passé. Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.surveillance.controle_conditions
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche, taux_vers_dollar

SYMBOLES = dm.RACINE / "runs" / "20260919_envv2" / "code" / "data" / "aurexis_live" / "symboles.json"
SORTIE = dm.RACINE / "collapsar" / "vie" / "controle_conditions.json"
CONDITIONS = dm.RACINE / "collapsar" / "mains" / "conditions_reelles.json"    # lu par mains/fiches.py


def _prix(sym):
    t = mt5.symbol_info_tick(sym)
    return (t.bid + t.ask) / 2 if t and t.bid > 0 else None


def main():
    if not mt5.initialize():
        raise SystemExit("MetaTrader n'est pas joignable")
    noms = json.loads(SYMBOLES.read_text(encoding="utf-8"))
    serveur = mt5.symbol_info_tick("EURUSD").time
    decalage = round((serveur - time.time()) / 3600)
    lignes, reelles = [], {}
    for fichier in dm.liste_marches():
        f = fiche(fichier)
        sym = noms.get(f.nom)
        ligne = {"marche": f.nom, "symbole": sym}
        if not sym or not mt5.symbol_select(sym, True) or mt5.symbol_info(sym) is None:
            ligne["absent"] = True
            lignes.append(ligne)
            continue
        si = mt5.symbol_info(sym)
        prix = _prix(sym)
        source, inverser = taux_vers_dollar(f.cotation)
        fx = 1.0 if source is None else (1 / _prix(source) if inverser else _prix(source))
        notionnel_lot = si.trade_contract_size * prix * fx
        marge = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, sym, 1.0, si.ask)
        ecart = (si.ask - si.bid) / prix if si.ask and si.bid else None
        nuit = {}
        for cote, val in (("achat", si.swap_long), ("vente", si.swap_short)):
            if si.swap_mode == 1:                                            # en points
                nuit[cote] = val * si.point / prix * 360
            elif si.swap_mode in (2, 3):                                      # en argent par lot
                nuit[cote] = val / notionnel_lot * 360
            elif si.swap_mode == 5:                                           # en % par an
                nuit[cote] = val / 100
        # pauses de cotation > 2 h sur les 3 000 dernières bougies (heure serveur)
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 3000)
        pauses = []
        if r is not None and len(r) > 10:
            t = pd.to_datetime(r["time"], unit="s")          # heure serveur, comme nos données
            ecarts = t[1:] - (t[:-1] + pd.Timedelta(minutes=15))
            for i in np.flatnonzero(ecarts > pd.Timedelta(hours=2)):
                if t[i].dayofweek < 4:                                        # pauses de semaine (hors week-end)
                    pauses.append(f"{t[i] + pd.Timedelta(minutes=15):%H:%M}->{t[i + 1]:%H:%M}")
        # ressemblance avec nos données (les dernières semaines communes)
        ressemblance = None
        try:
            df = dm._lire_brut(fichier).set_index("time")["close"]
            if r is not None and len(r):
                mt = pd.Series(r["close"], index=pd.to_datetime(r["time"], unit="s"))
                commun = df.index.intersection(mt.index)
                if len(commun) > 200:
                    a, b = df.loc[commun], mt.loc[commun]
                    ressemblance = {"bougies": int(len(commun)),
                                    "ecart_prix_median_pct": float(np.median(np.abs(a / b - 1)) * 100),
                                    "accord_mouvements": float(np.corrcoef(np.diff(np.log(a)), np.diff(np.log(b)))[0, 1])}
        except Exception:
            pass
        ligne.update({
            "frais_simules_pct": f.frais * 100, "ecart_reel_pct": None if ecart is None else ecart * 100,
            "levier_simule": f.levier, "levier_reel": None if not marge else notionnel_lot / marge,
            "nuit_simulee_pct_an": {"achat": f.nuit_achat * 100, "vente": f.nuit_vente * 100}, "nuit_reelle_pct_an": {k: v * 100 for k, v in nuit.items()},
            "pas_lot_simule": (f"{f.pas_unites:g} unités" if f.pas_unites else f"{f.pas_dollars:g} $"),
            "pas_lot_reel": f"{si.volume_step * si.trade_contract_size:g} unités ({si.volume_step * notionnel_lot:,.0f} $)",
            "lot_min_reel_dollars": si.volume_min * notionnel_lot, "pauses_semaine_serveur": sorted(set(pauses))[:4],
            "ressemblance": ressemblance})
        lignes.append(ligne)
        # conditions reprises par le simulateur : coût de nuit par sens (positif = payé ; valeur aberrante écartée)
        cout = {k: (-v if abs(v) <= 0.6 else None) for k, v in nuit.items()}
        reelles[f.nom] = {"pas_unites": si.volume_step * si.trade_contract_size,
                          "min_unites": si.volume_min * si.trade_contract_size,
                          "nuit_achat": cout.get("achat"), "nuit_vente": cout.get("vente")}
    mt5.shutdown()
    CONDITIONS.write_text(json.dumps({"source": "compte démo Tradeco (à remplacer par le compte FTMO)",
                                      "quand": datetime.now().isoformat(timespec="seconds"), "marches": reelles},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    rapport = {"quand": datetime.now(timezone.utc).isoformat(timespec="seconds"), "serveur_moins_utc_h": decalage,
               "compte": "démo Tradeco (pas FTMO)", "marches": lignes}
    SORTIE.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
