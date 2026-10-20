"""Relevé QUOTIDIEN de la position manuelle du chef de projet (achat 1 lot XAUUSD, compte démo Tradeco, ouverte le
20/10/2026 17:18 serveur). LECTURE SEULE : jamais de connexion à un autre compte, jamais d'ordre. Cette position ne
compte dans AUCUN résultat de recherche.

Écrit une ligne par jour dans etudes/experience_acheteur_manuel.md : gain latent, pire baisse subie depuis l'ouverture
(plus bas des bougies d'une minute), frais de nuit réellement prélevés (cumul et du jour), et, pour vérifier le
simulateur : le taux de nuit affiché par Tradeco et celui du modèle FTMO (core.ftmo.nuit) à la même date.

    venv_gpu\\Scripts\\python.exe etudes\\experience_acheteur_manuel\\releve.py
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))

JOURNAL = RACINE / "etudes" / "experience_acheteur_manuel.md"
ETAT = ICI / "etat.json"
TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"
OUVERTURE_SERVEUR = dt.datetime(2026, 10, 20, 17, 18, 48)
PRIX_OUVERTURE = 4137.99

ENTETE = """# Expérience personnelle du chef de projet : achat manuel d'1 lot d'or (démo Tradeco)

Position ouverte À LA MAIN le 20/10/2026 à 17:18:48 (heure du serveur) à 4 137,99, compte démo Tradeco. Ni touchée, ni
comptée dans un résultat de recherche. Relevé automatique chaque jour (`etudes/experience_acheteur_manuel/releve.py`,
lecture seule). Frais de nuit : « réel » = prélevé par Tradeco ; « affiché » = taux Tradeco du jour ; « modèle FTMO » =
ce que notre simulateur compterait chez FTMO (autre courtier : sert de repère, pas d'égalité attendue).

| date (Paris) | cours | gain latent $ | pire baisse depuis l'ouverture $ (au plus bas) | nuits prélevées cumul $ | nuits du jour $ | taux affiché achat (points/lot) | modèle FTMO achat %/an | remarque |
|---|---|---|---|---|---|---|---|---|
"""


def terminal_ouvert() -> bool:
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq terminal64.exe"], capture_output=True, text=True)
    return "terminal64.exe" in r.stdout


def main():
    if not JOURNAL.exists():
        JOURNAL.write_text(ENTETE, encoding="utf-8")
    etat = json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else {}
    jour = dt.datetime.now().strftime("%d/%m/%Y")
    if etat.get("dernier_jour") == jour and "--forcer" not in sys.argv:
        return
    if not terminal_ouvert():
        ligne = f"| {jour} | | | | | | | | MetaTrader fermé : pas de relevé |\n"
        JOURNAL.write_text(JOURNAL.read_text(encoding="utf-8") + ligne, encoding="utf-8")
        return
    import MetaTrader5 as mt5
    if not mt5.initialize(path=TERMINAL, timeout=60000):           # s'attache au terminal ouvert, sans connexion
        raise SystemExit(f"MetaTrader injoignable : {mt5.last_error()}")
    try:
        ps = [p for p in (mt5.positions_get(symbol="XAUUSD") or [])
              if p.magic == 0 and p.type == mt5.POSITION_TYPE_BUY and abs(p.price_open - PRIX_OUVERTURE) < 0.01]
        info = mt5.symbol_info("XAUUSD")
        tick = mt5.symbol_info_tick("XAUUSD")
        modele = ""
        try:
            import pandas as pd
            from core.ftmo.fiches import fiche
            from core.ftmo.nuit import taux_nuit
            a, _ = taux_nuit(fiche("XAUUSD"), pd.DatetimeIndex([pd.Timestamp.now().normalize()]))
            modele = f"{100 * a[0]:.2f}"
        except Exception as e:                                       # repère seulement
            modele = f"? ({type(e).__name__})"
        if not ps:
            remarque = "position introuvable sur le compte connecté (fermée ? autre compte ?)"
            ligne = f"| {jour} | {tick.bid if tick else ''} | | | | | {info.swap_long if info else ''} | {modele} | {remarque} |\n"
        else:
            p = ps[0]
            # bougies d'1 min depuis l'ouverture (même horloge que p.time : celle du serveur)
            r = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M1, 0, 50_000)
            r = r[r["time"] >= p.time] if r is not None else None
            plus_bas = float(min(r["low"])) if r is not None and len(r) else float("nan")
            contrat = info.trade_contract_size
            pire = (plus_bas - p.price_open) * contrat * p.volume
            jour_nuit = p.swap - float(etat.get("swap_cumul", 0.0))
            ligne = (f"| {jour} | {tick.bid:.2f} | {p.profit:+.2f} | {pire:+.2f} (plus bas {plus_bas:.2f}) | "
                     f"{p.swap:+.2f} | {jour_nuit:+.2f} | {info.swap_long} | {modele} | |\n")
            etat["swap_cumul"] = p.swap
        JOURNAL.write_text(JOURNAL.read_text(encoding="utf-8") + ligne, encoding="utf-8")
        etat["dernier_jour"] = jour
        ETAT.write_text(json.dumps(etat), encoding="utf-8")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
