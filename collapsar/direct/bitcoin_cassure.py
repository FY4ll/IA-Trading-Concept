"""DÉMO EN DIRECT de la stratégie « cassure 24 h du bitcoin » (C2, regarder/pistes/bitcoin_cassure.py) sur le compte
DÉMO Tradeco (16/10/2026, carte blanche du chef de projet). Mêmes règles que le test, rien de choisi en direct :
- lundi -> vendredi (jour du serveur), à chaque heure pleine h = 1h ... 23h : c = clôture de l'heure écoulée ;
  canal = plus haut / plus bas des 24 heures précédentes (heures des jours de semaine bout à bout, week-end sauté) ;
  en achat et c < milieu du canal -> fermer ; en vente et c > milieu -> fermer ; à plat et h <= 22 : c > haut ->
  acheter, c < bas -> vendre ;
- 23h45 serveur : tout est fermé (pas de frais de nuit) ; rien le samedi ni le dimanche ;
- taille : exposition = min(1, 1 % / agitation journalière des 14 jours précédents) x capitaux du compte ;
- arrêt de la journée si NOS trades du jour perdent 3 % du compte (perte latente comprise) : tout fermé, plus rien
  jusqu'au lendemain ;
- numéro magique 16102027 (jamais touché par COLLAPSAR), compte réel refusé ; arrêt volontaire : fichier
  vie/direct/BITCOIN_ARRET.
Résultats attendus (test, période cachée 2024-2026, frais 0,03 %) : ~+0,95 %/mois, baisse max ~15 %. L'écart Tradeco
(~30 $ = 0,036 %) est proche de ce scénario.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.direct.bitcoin_cassure [--essai]
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from collapsar.direct import tradeco
from collapsar.donnees import marches as dm

SYM = "BTCUSD"
MAGIC = 16102027
N_HEURES, JOURS_AGIT, CIBLE, ARRET_JOUR = 24, 14, 0.01, 0.03
DOSSIER = dm.RACINE / "collapsar" / "vie" / "direct"
ETAT = DOSSIER / "bitcoin_cassure.json"
ARRET = DOSSIER / "BITCOIN_ARRET"
JOURNAL = dm.RACINE / "collapsar" / "vie" / "logs" / "bitcoin_cassure.txt"
TRADES = DOSSIER / "bitcoin_cassure_trades.csv"


def log(texte: str) -> None:
    ligne = f"[{datetime.now():%d/%m %H:%M:%S}] {texte}"
    print(ligne, flush=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def telephone(titre: str, texte: str) -> None:
    try:
        from collapsar.surveillance.telephone import envoyer_texte
        envoyer_texte(titre, texte)
    except Exception as e:                                   # le trading ne dépend jamais du téléphone
        log(f"téléphone indisponible ({type(e).__name__})")


# ---------------------------------------------------------------- données du serveur
def maintenant_serveur() -> pd.Timestamp:
    t = mt5.symbol_info_tick(SYM)
    return pd.Timestamp(t.time, unit="s")


def bougies(maintenant: pd.Timestamp) -> pd.DataFrame:
    r = mt5.copy_rates_from_pos(SYM, mt5.TIMEFRAME_M15, 0, 96 * 35)
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df[df["time"] + pd.Timedelta(minutes=15) <= maintenant]          # bougies TERMINÉES seulement


def signal(df: pd.DataFrame, maintenant: pd.Timestamp) -> dict:
    """Canal des 24 heures (jours de semaine bout à bout) et agitation, comme dans le test."""
    df = df[df["time"].dt.dayofweek < 5].copy()
    df["jour"] = df["time"].dt.normalize()
    df["k"] = df["time"].dt.hour * 4 + df["time"].dt.minute // 15
    aujourd_hui = maintenant.normalize()
    lignes = []
    for j, g in df.groupby("jour"):
        if j < aujourd_hui and len(g) < 92:
            continue                                                         # jour incomplet : ignoré (comme le test)
        C = np.full(96, np.nan)
        H, L = C.copy(), C.copy()
        C[g["k"]], H[g["k"]], L[g["k"]] = g["close"], g["high"], g["low"]
        Cf = pd.Series(C).ffill().bfill().to_numpy()
        H = np.where(np.isfinite(H), H, Cf)
        L = np.where(np.isfinite(L), L, Cf)
        heures = 24 if j < aujourd_hui else maintenant.hour
        for h in range(heures):
            lignes.append((j, h, H[4 * h:4 * h + 4].max(), L[4 * h:4 * h + 4].min(), Cf[4 * h + 3]))
    hr = pd.DataFrame(lignes, columns=["jour", "h", "H", "L", "C"])
    passe = hr.iloc[:-1]
    fen = passe.iloc[-N_HEURES:]
    clo = hr[hr["jour"] < aujourd_hui].groupby("jour")["C"].last()
    agit = clo.pct_change().iloc[-JOURS_AGIT:].std()
    derniere = hr.iloc[-1]
    return {"c": float(derniere["C"]), "heure_vue": f"{derniere['jour'].date()} {int(derniere['h'])}h",
            "haut": float(fen["H"].max()), "bas": float(fen["L"].min()), "agitation": float(agit),
            "assez": len(passe) >= N_HEURES and len(clo) > JOURS_AGIT}


# ---------------------------------------------------------------- ordres (numéro magique propre)
def nos_positions() -> list:
    return [p for p in (mt5.positions_get(symbol=SYM) or []) if p.magic == MAGIC]


def envoyer(sens: int, volume: float, position=None) -> tuple[bool, str, float]:
    t = mt5.symbol_info_tick(SYM)
    prix = t.ask if sens > 0 else t.bid
    d = {"action": mt5.TRADE_ACTION_DEAL, "symbol": SYM, "volume": volume, "price": prix,
         "type": mt5.ORDER_TYPE_BUY if sens > 0 else mt5.ORDER_TYPE_SELL, "deviation": 200, "magic": MAGIC,
         "comment": "BTC cassure 24h", "type_filling": tradeco._remplissage(SYM)}
    if position is not None:
        d["position"] = position
    ok, info = tradeco._envoyer(d)
    return ok, info, prix


def fermer_tout(raison: str, etat: dict) -> None:
    for p in nos_positions():
        sens = -1 if p.type == mt5.POSITION_TYPE_BUY else 1
        ok, info, prix = envoyer(sens, p.volume, p.ticket)
        gain = p.profit
        log(f"FERMETURE ({raison}) {p.volume} lot à {prix:.2f} : {'ok' if ok else 'ÉCHEC ' + info}, résultat {gain:+.2f} $")
        if ok:
            with TRADES.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M},{'achat' if sens < 0 else 'vente'},{p.volume},"
                        f"{p.price_open},{prix},{gain:.2f},{raison}\n")
            telephone("Bitcoin : position fermée", f"{raison} — résultat {gain:+.0f} $")


def gain_du_jour(jour_serveur: pd.Timestamp) -> float:
    """Résultat de NOS trades depuis minuit serveur (fermés + perte latente), en $."""
    deals = mt5.history_deals_get(jour_serveur.to_pydatetime(), datetime(2100, 1, 1)) or []
    ferme = sum(d.profit + d.commission + d.swap for d in deals if d.magic == MAGIC)
    return ferme + sum(p.profit for p in nos_positions())


# ---------------------------------------------------------------- une heure
def agir(etat: dict, essai: bool) -> None:
    now = maintenant_serveur()
    jour = now.normalize()
    if etat.get("jour") != str(jour.date()):
        etat.update({"jour": str(jour.date()), "heures": [], "arret": False, "ferme_soir": False})
    if now.dayofweek >= 5:
        return
    capitaux = mt5.account_info().equity
    if not etat["arret"] and nos_positions() and gain_du_jour(jour) <= -ARRET_JOUR * capitaux:
        etat["arret"] = True
        if not essai:
            fermer_tout("arrêt de la journée à -3 %", etat)
    if (now.hour, now.minute) >= (23, 45):
        if not etat["ferme_soir"]:
            etat["ferme_soir"] = True
            if not essai:
                fermer_tout("fin de journée 23h45", etat)
        return
    h = now.hour
    if h < 1 or now.minute > 10 or h in etat["heures"]:
        return
    s = signal(bougies(now), now)
    if s["heure_vue"] != f"{jour.date()} {h - 1}h":                 # historique pas encore synchronisé : on réessaie
        log(f"{h}h : données en retard (dernière heure vue {s['heure_vue']}), nouvel essai dans 30 s")
        return
    etat["heures"].append(h)
    if not s["assez"] or not (s["agitation"] > 0):
        log(f"{h}h : historique insuffisant")
        return
    milieu = (s["haut"] + s["bas"]) / 2
    ps = nos_positions()
    pos = 0 if not ps else (1 if ps[0].type == mt5.POSITION_TYPE_BUY else -1)
    texte = (f"{h}h serveur : clôture {s['c']:.0f} ({s['heure_vue']}), canal {s['bas']:.0f} - {s['haut']:.0f}, "
             f"agitation {s['agitation'] * 100:.2f} %/jour, position {pos:+d}")
    if pos > 0 and s["c"] < milieu or pos < 0 and s["c"] > milieu:
        log(texte + " -> sortie (retour au milieu du canal)")
        if not essai:
            fermer_tout("retour au milieu du canal", etat)
        pos = 0
    if pos == 0 and h <= 22 and not etat["arret"] and (s["c"] > s["haut"] or s["c"] < s["bas"]):
        sens = 1 if s["c"] > s["haut"] else -1
        expo = min(1.0, CIBLE / s["agitation"]) * capitaux
        info = mt5.symbol_info(SYM)
        vol = math.floor(expo / s["c"] / info.trade_contract_size / info.volume_step) * info.volume_step
        vol = round(min(vol, info.volume_max), 2)
        log(texte + f" -> {'ACHAT' if sens > 0 else 'VENTE'} {vol} lot (exposition {expo / capitaux * 100:.0f} % du compte)")
        if not essai and vol >= info.volume_min:
            ok, rep, prix = envoyer(sens, vol)
            log(f"   ordre {'ok' if ok else 'ÉCHEC ' + rep} à {prix:.2f}")
            if ok:
                telephone(f"Bitcoin : {'achat' if sens > 0 else 'vente'}",
                          f"Cassure du canal 24 h ({s['bas']:.0f} - {s['haut']:.0f}) : {vol} BTC à {prix:.0f} ; "
                          f"sortie au retour au milieu ({milieu:.0f}) ou 23h45 serveur.")
    else:
        log(texte + " -> rien")


def main():
    essai = "--essai" in sys.argv
    DOSSIER.mkdir(parents=True, exist_ok=True)
    tradeco.connecter()
    mt5.symbol_select(SYM, True)
    etat = json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else {}
    log(f"démarrage {'(ESSAI, aucun ordre)' if essai else '(démo Tradeco)'} ; capitaux {mt5.account_info().equity:.0f} $")
    if essai:
        now = maintenant_serveur()
        s = signal(bougies(now), now)
        log(f"essai : {json.dumps(s)}")
        return
    while True:
        if ARRET.exists():
            time.sleep(60)
            continue
        try:
            agir(etat, essai)
            ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            log(f"erreur {type(e).__name__}: {e}")
            try:
                tradeco.connecter()
            except Exception:
                pass
        time.sleep(30)


if __name__ == "__main__":
    main()
