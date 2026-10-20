"""DÉMO EN DIRECT de la stratégie DU CHEF DE PROJET, version figée « Gigogne H4 stop A plancher 0.2 » (V1 de
regarder/pistes/chef_crypto.py, docs/CASCADE_ZONES.md avenants 1 à 3) sur le bitcoin et l'ether, compte DÉMO Tradeco
(16/10/2026).

Rien n'est recopié : les zones zones supply and demand, leur effacement, la descente gigogne et l'entrée viennent de
regarder/smc/gigogne.py (preparer, entrees) appelés tels quels, sur les bougies de 15 min de MetaTrader (heure du
serveur = celle de nos données ; heure de New York = serveur - 7 h, comme le laboratoire).

Comment le test devient des ordres (à chaque bougie de 15 min terminée)
- Les entrées déjà faites = gigogne.entrees sur les bougies terminées.
- Les ordres à poser = gigogne.entrees sur les mêmes bougies PLUS une bougie fictive qui touche tous les prix au
  prochain quart d'heure : chaque entrée qui tomberait dans cette bougie (ou dans la bougie H1 / M30 en cours) est un
  ordre LIMITE au milieu de la plus petite zone qui doit être en place maintenant. On garde le même code pour tout :
  zone H4 vivante, contact du bord proche, descente H1 -> M30 -> M15, 200 bougies au plus, effacements.
- Une zone H4 pas encore touchée : l'ordre est posé d'avance (le prix doit passer le bord de la zone avant d'atteindre
  le milieu) ; si le milieu est au-delà du bord (cas rare), on ne peut pas le poser d'avance : entrée manquée.
- Stop A : bord opposé de la plus petite zone ± 0,2 x agitation (ATR) de son unité, au minimum 0,2 x ATR journalier
  (dernier jour complet). Tant que la bougie d'entrée n'est pas finie, l'ATR de la bougie précédente sert ; à la fin
  de la bougie d'entrée, stop et objectifs sont recalculés exactement comme le test (et le trade fermé si le test ne
  l'aurait pas pris).
- Sorties par tiers (trois positions) : TP1 = 2 R, TP2 = plus proche sommet / creux H1 confirmé entre TP1 et TP3
  (sinon le milieu), TP3 = bord proche de la plus proche zone H4 opposée vivante (au moins 2 R, sinon pas de trade) ;
  le stop et les objectifs sont posés dans MetaTrader ; fermeture au bout de 30 jours.
Règles du compte : risque 0,25 % des capitaux par trade ; un trade à la fois par marché (2 au plus : BTC + ETH) ;
arrêt de la journée (serveur) si NOS trades perdent 2 % (pertes latentes comprises) : tout fermé ; numéro magique
16102028 ; compte réel refusé ; arrêt volontaire : vie/direct/CHEF_ARRET (ordres en attente annulés, positions
gardées avec leur stop et leurs objectifs).

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.direct.chef_zones [--essai | --rejouer [BTCUSD ETHUSD]]
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
from collapsar.regarder.pistes import chef_crypto as CC
from collapsar.regarder.smc import gigogne as G
from collapsar.regarder.smc.nono import TENUE_JOURS

SYMBOLES = {"BTCUSD": ("le bitcoin", CC.FRAIS["BTC"]), "ETHUSD": ("l'ether", CC.FRAIS["ETH"])}
MAGIC = 16102028
RISQUE = 0.0025
ARRET_JOUR = 0.02
PLANCHER = CC.PLANCHER                    # 0,2 x ATR journalier (sa version figée)
DEPART = "H4"
JOURS_REJEU = 90
DOSSIER = dm.RACINE / "collapsar" / "vie" / "direct"
ETAT = DOSSIER / "chef_zones.json"
ARRET = DOSSIER / "CHEF_ARRET"
JOURNAL = dm.RACINE / "collapsar" / "vie" / "logs" / "chef_zones.txt"
TRADES = DOSSIER / "chef_zones_trades.csv"
QUART = pd.Timedelta(minutes=15)
H7 = pd.Timedelta(hours=7)
NOM_UNITE = {"H1": "H1", "M30": "M30", "M15": "M15"}


def log(texte: str) -> None:
    ligne = f"[{datetime.now():%d/%m %H:%M:%S}] {texte}"
    print(ligne, flush=True)
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def telephone(titre: str, texte: str) -> None:
    try:
        from collapsar.surveillance.telephone import envoyer_texte
        envoyer_texte(titre, texte)
    except Exception as e:                                   # le trading ne dépend jamais du téléphone
        log(f"téléphone indisponible ({type(e).__name__})")


def px(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ")


# ---------------------------------------------------------------- bougies MetaTrader
def bougies_mt5(sym: str) -> pd.DataFrame:
    """Toutes les bougies de 15 min disponibles (heure serveur), partie continue seulement (avant fin 2024, MetaTrader
    n'a que quelques bougies par jour : elles fabriqueraient de fausses zones)."""
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 99000)
    if r is None or not len(r):
        raise RuntimeError(f"pas de bougies {sym} ({mt5.last_error()})")
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s").astype("datetime64[ns]")
    df = df.rename(columns={"tick_volume": "volume"})[["time", "open", "high", "low", "close", "volume"]]
    trou = np.flatnonzero(df["time"].diff().to_numpy() > np.timedelta64(2, "D"))
    if len(trou):
        df = df.iloc[trou[-1]:]
    return df.reset_index(drop=True)


def terminees(df: pd.DataFrame, maintenant: pd.Timestamp) -> pd.DataFrame:
    return df[df["time"] + QUART <= maintenant].reset_index(drop=True)


# ---------------------------------------------------------------- l'analyse (sans MetaTrader : sert au direct ET au rejeu)
def preparer(sym: str, df: pd.DataFrame) -> dict:
    return G.preparer(CC.construire(sym, CC.en_ny(df), SYMBOLES[sym][1]), G.ECHELLE_45)


def avec_bougie_fictive(df: pd.DataFrame) -> pd.DataFrame:
    """La bougie suivante, qui toucherait tous les prix (clôture inchangée : n'efface aucune zone)."""
    c = float(df["close"].iloc[-1])
    f = {"time": df["time"].iloc[-1] + QUART, "open": c, "high": c * 10.0, "low": c * 0.01, "close": c, "volume": 0.0}
    return pd.concat([df, pd.DataFrame([f])], ignore_index=True)


def cle(P: dict, z: int) -> str:
    """Identité d'une zone H4 : sens + heure de confirmation (New York)."""
    zs, zc = P["Z"][DEPART][3][z], P["Z"][DEPART][4][z]
    return f"{'A' if zs > 0 else 'V'}{pd.Timestamp(int(zc)):%Y%m%d%H%M}"


def plan(P: dict, t_e: int, entree: float, loin: float, atr_y: float, d: int) -> dict | None:
    """Stop A avec plancher et objectifs par tiers, comme gigogne.trades (planchers) puis gigogne._un_trade."""
    BD = P["B"]["D1"]
    risque_zone = (entree - (loin - d * 0.2 * atr_y)) * d
    if not risque_zone > 0:
        return None
    jd = int(np.searchsorted(BD.bt, t_e, "right")) - 2                 # dernier jour COMPLET
    atr_jour = BD.atr[jd] if jd >= 0 else np.nan
    risque = max(risque_zone, PLANCHER * atr_jour)
    if not np.isfinite(risque):
        return None
    xh, xb, xm, xs, xconf, xfin = P["Z"][DEPART]
    okx = (xs == -d) & (xconf < t_e) & (xfin > t_e)
    dist3 = ((xb if d > 0 else xh)[okx] - entree) * d
    dist3 = dist3[dist3 >= 2 * risque]
    if not len(dist3):
        return None
    d3 = float(dist3.min())
    s_px, s_ty, s_t = P["sommets"]
    cand = (s_ty == d) & (s_t <= t_e)
    d2s = (s_px[cand] - entree) * d
    d2s = d2s[(d2s > 2 * risque) & (d2s < d3)]
    d2 = float(d2s.min()) if len(d2s) else (2 * risque + d3) / 2
    return {"entree": float(entree), "risque": float(risque), "stop": float(entree - d * risque),
            "tp": [float(entree + d * 2 * risque), float(entree + d * d2), float(entree + d * d3)],
            "tp3_R": d3 / risque, "plancher": bool(risque > risque_zone)}


def analyser(sym: str, df: pd.DataFrame) -> dict:
    """`df` = bougies TERMINÉES (heure serveur). Rend les entrées déjà faites (par zone H4) et les ordres à poser."""
    T = int((df["time"].iloc[-1] + QUART - H7).value)                   # maintenant, heure de New York (ns)
    P = preparer(sym, df)
    reel = {cle(P, e["z"]): e for e in G.entrees(P, DEPART)}
    Ps = preparer(sym, avec_bougie_fictive(df))
    xh, xb = Ps["Z"][DEPART][0], Ps["Z"][DEPART][1]
    candidats, manques = [], []
    for e in G.entrees(Ps, DEPART):
        u, i, d, z = e["unite"], e["i"], e["sens"], e["z"]
        BY = Ps["B"][u]
        if BY.bt[i] + BY.duree <= T:
            continue                                                     # entrée déjà passée
        k = cle(Ps, z)
        r = reel.get(k)
        if r is not None and r["unite"] == u and r["i"] == i:
            continue                                                     # déjà rempli dans la bougie en cours
        proche = xh[z] if d > 0 else xb[z]
        if e["t_in"] == T and (e["milieu"] - proche) * d > 0:
            manques.append(k)                                            # milieu au-delà du bord : pas d'avance
            continue
        zu = Ps["Z"][u]
        loin = float(zu[1][e["zi"]] if d > 0 else zu[0][e["zi"]])
        t_e = int(BY.bt[i])
        pl = plan(Ps, t_e, e["milieu"], loin, BY.atr[i - 1], d)
        if pl is None:
            continue
        candidats.append({"cle": k, "sens": d, "unite": u, "milieu": float(e["milieu"]), "loin": loin,
                          "t_in": int(e["t_in"]), "t_e": t_e, "contact": int(e["t_in"]) < T,
                          "profondeur": e["profondeur"], **pl})
    zh, zb, zm, zs, zconf, zfin = P["Z"][DEPART]
    base = P["base"]
    intactes = set()                                                     # zones H4 vivantes jamais touchées
    for z in np.flatnonzero((zconf <= T) & (zfin > T)):
        k0 = int(np.searchsorted(base.bt, zconf[z]))
        if not ((base.l[k0:] <= zh[z]).any() if zs[z] > 0 else (base.h[k0:] >= zb[z]).any()):
            intactes.add(cle(P, z))
    return {"T": T, "P": P, "reel": reel, "candidats": candidats, "manques": manques,
            "vivantes": int(((zconf <= T) & (zfin > T)).sum()), "intactes": intactes}


# ---------------------------------------------------------------- contrôle : rejouer les 3 derniers mois
def rejouer(sym: str, jours: int = JOURS_REJEU) -> dict:
    """Rejoue bougie par bougie le code du direct (ordres posés à chaque clôture, remplis par la bougie suivante) et le
    compare à gigogne.entrees sur toutes les bougies (même zone, même heure, même sens, même prix)."""
    df = bougies_mt5(sym)
    fin = df["time"].iloc[-1]
    df = df.iloc[:-1]                                                    # la dernière bougie peut être en cours
    debut = fin - pd.Timedelta(days=jours)
    P = preparer(sym, df)
    T_fin = int((df["time"].iloc[-1] + QUART - H7).value)
    T_debut = int((debut - H7).value)
    # les TRADES du test (chef_crypto.trades_chef : entrées gigogne qui ont un objectif 3 à 2 R au moins)
    tc, _ = CC.trades_chef(sym, CC.construire(sym, CC.en_ny(df), SYMBOLES[sym][1]), departs=(DEPART,))
    ref, sans_trade = {}, {}
    for e in G.entrees(P, DEPART):
        BY = P["B"][e["unite"]]
        if BY.bt[e["i"]] >= T_debut and BY.bt[e["i"]] + BY.duree <= T_fin:
            x = (e["unite"], int(BY.bt[e["i"]]), int(e["sens"]), float(e["entree"]))
            un_trade = len(tc) and ((tc["entree"] == pd.Timestamp(BY.t[e["i"]])) & (tc["sens"] == e["sens"])).any()
            (ref if un_trade else sans_trade)[cle(P, e["z"])] = x
    # niveaux de stop / objectifs : notre calcul exact contre le test
    niveaux = []
    for e in G.entrees(P, DEPART):
        BY = P["B"][e["unite"]]
        zu = P["Z"][e["unite"]]
        loin = float(zu[1][e["zi"]] if e["sens"] > 0 else zu[0][e["zi"]])
        pl = plan(P, int(BY.bt[e["i"]]), e["entree"], loin, BY.atr[e["i"]], e["sens"])
        t = tc[(tc["entree"] == pd.Timestamp(BY.t[e["i"]])) & (tc["sens"] == e["sens"])] if len(tc) else tc
        niveaux.append((pl is not None, len(t) > 0,
                        abs(pl["risque"] / pl["entree"] - t["stop_frac"].iloc[0]) if pl is not None and len(t) else 0.0,
                        abs(pl["tp3_R"] - t["tp3_R"].iloc[0]) if pl is not None and len(t) else 0.0))
    # simulation du direct
    k0 = int(np.searchsorted(df["time"].to_numpy(), np.datetime64(debut)))
    vus, t0 = {}, time.time()
    for k in range(k0, len(df)):
        A = analyser(sym, df.iloc[:k])
        b = df.iloc[k]
        for c in A["candidats"]:
            if c["cle"] in vus:
                continue
            d, m = c["sens"], c["milieu"]
            if (d > 0 and b["low"] <= m) or (d < 0 and b["high"] >= m):
                prix = float(b["open"]) if (d > 0 and b["open"] < m) or (d < 0 and b["open"] > m) else m
                vus[c["cle"]] = (c["unite"], int(c["t_e"]), int(d), prix)
        if (k - k0) % 500 == 0:
            log(f"[rejeu {sym}] {k - k0}/{len(df) - k0} bougies ({time.time() - t0:.0f} s)")
    pareils = [k for k in ref if k in vus and vus[k][:3] == ref[k][:3] and abs(vus[k][3] - ref[k][3]) < 1e-6]
    prix_diff = [k for k in ref if k in vus and vus[k][:3] == ref[k][:3] and abs(vus[k][3] - ref[k][3]) >= 1e-6]
    autre = [k for k in ref if k in vus and vus[k][:3] != ref[k][:3]]
    manquees = [k for k in ref if k not in vus]
    en_trop = [k for k in vus if k not in ref]
    fmt = lambda x: f"{x[0]} {pd.Timestamp(x[1]) + H7:%d/%m %H:%M} serveur {'achat' if x[2] > 0 else 'vente'} {x[3]:.2f}"
    res = {"symbole": sym, "du": str(debut), "au": str(fin), "trades_test": len(ref), "detectees": len(vus),
           "identiques": len(pareils), "prix_different": {k: [fmt(ref[k]), fmt(vus[k])] for k in prix_diff},
           "heure_ou_sens_different": {k: [fmt(ref[k]), fmt(vus[k])] for k in autre},
           "manquees": {k: fmt(ref[k]) for k in manquees},
           "en_trop (le calcul exact à la fin de la bougie d'entrée les ferme)": {k: fmt(vus[k]) for k in en_trop},
           "test": {k: fmt(v) for k, v in ref.items()},
           "entrees_sans_trade_dans_le_test (pas d'objectif 3 à 2 R)": {k: fmt(v) for k, v in sans_trade.items()},
           "niveaux": {"entrees": len(niveaux), "plan_ok": sum(a for a, *_ in niveaux),
                       "dans_le_test": sum(b for _, b, *_ in niveaux),
                       "ecart_stop_max": max([c for *_, c, _ in niveaux] or [0.0]),
                       "ecart_tp3_R_max": max([x for *_, x in niveaux] or [0.0])}}
    DOSSIER.mkdir(parents=True, exist_ok=True)
    (DOSSIER / f"chef_zones_rejeu_{sym}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                          encoding="utf-8")
    log(f"[rejeu {sym}] test {len(ref)} trades, programme {len(vus)} entrées : identiques {len(pareils)}, prix différent "
        f"{len(prix_diff)}, heure/sens différent {len(autre)}, manquées {len(manquees)}, en trop {len(en_trop)} ; "
        f"niveaux : {res['niveaux']}")
    return res


# ---------------------------------------------------------------- ordres (numéro magique propre)
def _envoyer(d: dict) -> tuple[bool, str, int]:
    r = mt5.order_send(d)
    if r is None:
        return False, f"pas de réponse ({mt5.last_error()})", 0
    ok = r.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED)
    return ok, f"code {r.retcode} {r.comment}", int(r.order)


def nos_positions(sym: str) -> dict:
    return {p.identifier: p for p in (mt5.positions_get(symbol=sym) or []) if p.magic == MAGIC}


def nos_ordres(sym: str) -> dict:
    return {o.ticket: o for o in (mt5.orders_get(symbol=sym) or []) if o.magic == MAGIC}


def annuler(ticket: int) -> tuple[bool, str]:
    ok, info, _ = _envoyer({"action": mt5.TRADE_ACTION_REMOVE, "order": int(ticket), "magic": MAGIC})
    return ok, info


def fermer(p, commentaire: str) -> tuple[bool, str]:
    t = mt5.symbol_info_tick(p.symbol)
    achat = p.type == mt5.POSITION_TYPE_BUY
    ok, info, _ = _envoyer({"action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": p.volume,
                            "position": p.ticket, "type": mt5.ORDER_TYPE_SELL if achat else mt5.ORDER_TYPE_BUY,
                            "price": t.bid if achat else t.ask, "deviation": 200, "magic": MAGIC,
                            "comment": commentaire[:31], "type_filling": tradeco._remplissage(p.symbol)})
    return ok, info


def volumes(sym: str, risque: float) -> tuple[float, bool]:
    """Volume de CHAQUE tiers pour risquer 0,25 % des capitaux (0 si trop petit) ; vrai si plafonné par le courtier."""
    s = mt5.symbol_info(sym)
    lots = mt5.account_info().equity * RISQUE / (risque * s.trade_contract_size)
    v = math.floor(lots / 3 / s.volume_step + 1e-9) * s.volume_step
    if v < s.volume_min:
        return 0.0, False
    return round(min(v, s.volume_max), 8), v > s.volume_max


def poser(sym: str, c: dict, vol: float) -> tuple[list[int], list[str], bool]:
    """Trois ordres limite (un par tiers) au milieu de la zone, stop et objectif posés ; au marché si le prix a déjà
    passé le milieu (comme le test : entrée à l'ouverture)."""
    s, t = mt5.symbol_info(sym), mt5.symbol_info_tick(sym)
    d = c["sens"]
    prix = round(c["milieu"], s.digits)
    marche = (d > 0 and t.ask <= prix) or (d < 0 and t.bid >= prix)
    tickets, infos = [], []
    for q in range(3):
        base = {"symbol": sym, "volume": vol, "sl": round(c["stop"], s.digits), "tp": round(c["tp"][q], s.digits),
                "magic": MAGIC, "comment": f"chef H4-{c['unite']} {q + 1}/3"}
        if marche:
            base.update({"action": mt5.TRADE_ACTION_DEAL, "price": t.ask if d > 0 else t.bid, "deviation": 200,
                         "type": mt5.ORDER_TYPE_BUY if d > 0 else mt5.ORDER_TYPE_SELL,
                         "type_filling": tradeco._remplissage(sym)})
        else:
            base.update({"action": mt5.TRADE_ACTION_PENDING, "price": prix,
                         "type": mt5.ORDER_TYPE_BUY_LIMIT if d > 0 else mt5.ORDER_TYPE_SELL_LIMIT,
                         "type_time": mt5.ORDER_TIME_SPECIFIED, "type_filling": mt5.ORDER_FILLING_RETURN,
                         "expiration": int(time.time()) + 9 * 86400})
        ok, info, ticket = _envoyer(base)
        infos.append(info)
        if ok and ticket:
            tickets.append(ticket)
    return tickets, infos, marche


def maintenant_serveur() -> pd.Timestamp:
    return max(pd.Timestamp(mt5.symbol_info_tick(s).time, unit="s") for s in SYMBOLES)


def gain_du_jour(jour_serveur: pd.Timestamp) -> float:
    debut = pd.Timestamp(jour_serveur).tz_localize("UTC").to_pydatetime()    # MetaTrader : heure serveur notée UTC
    deals = mt5.history_deals_get(debut, datetime(2100, 1, 1)) or []
    ferme = sum(d.profit + d.commission + d.swap + getattr(d, "fee", 0.0) for d in deals if d.magic == MAGIC)
    return ferme + sum(p.profit for s in SYMBOLES for p in nos_positions(s).values())


def resultat_position(ticket: int) -> tuple[float, float, str]:
    deals = mt5.history_deals_get(position=int(ticket)) or []
    gain = sum(d.profit + d.commission + d.swap + getattr(d, "fee", 0.0) for d in deals)
    sortie = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
    if not sortie:
        return gain, float("nan"), "inconnue"
    raison = {mt5.DEAL_REASON_SL: "stop", mt5.DEAL_REASON_TP: "objectif"}.get(sortie[-1].reason, "fermeture")
    return gain, float(sortie[-1].price), raison


def libelle(sym: str, c: dict) -> str:
    return (f"Zone {'d’achat' if c['sens'] > 0 else 'de vente'} H4 -> {c['unite']} sur {SYMBOLES[sym][0]}")


# ---------------------------------------------------------------- suivi des ordres et des trades
def suivre(sym: str, etat: dict, maintenant: pd.Timestamp) -> None:
    groupes = etat["groupes"].setdefault(sym, {})
    pos = nos_positions(sym)
    ordres = nos_ordres(sym)
    tr = etat["trades"].get(sym)
    # un ordre en attente rempli -> le trade est ouvert, les autres ordres du marché sont annulés
    if tr is None:
        for k, g in list(groupes.items()):
            remplis = [t for t in g["tickets"] if t in pos]
            if remplis:
                p = pos[remplis[0]]
                tr = {**g, "ouvert": str(pd.Timestamp(p.time, unit="s")), "prix_reel": p.price_open, "exact": False,
                      "fermes": []}
                etat["trades"][sym] = tr
                del groupes[k]
                log(f"{sym} : ordre EXÉCUTÉ ({k}) à {px(p.price_open)} ({len(remplis)}/3 tiers)")
                telephone(f"{SYMBOLES[sym][0].capitalize()} : ordre exécuté",
                          f"{libelle(sym, g)} : entrée à {px(p.price_open)}, stop {px(g['stop'])}, objectifs "
                          f"{px(g['tp'][0])} / {px(g['tp'][1])} / {px(g['tp'][2])}.")
                break
            if not any(t in ordres for t in g["tickets"]):
                log(f"{sym} : ordre {k} disparu sans exécution (expiré ou annulé à la main)")
                del groupes[k]
        if tr is not None:
            for k, g in list(groupes.items()):
                for t in g["tickets"]:
                    if t in ordres:
                        log(f"{sym} : ordre {k} annulé (un trade est ouvert) -> {annuler(t)[1]}")
                del groupes[k]
    if tr is None:
        return
    # positions fermées (stop, objectifs) et fin du trade
    ouverts = [t for t in tr["tickets"] if t in pos]
    for t in tr["tickets"]:
        if t not in pos and t not in ordres and t not in tr["fermes"]:
            deals = mt5.history_deals_get(position=int(t)) or []
            if not deals:                                                 # jamais rempli (annulé / expiré)
                tr["fermes"].append(t)
                continue
            gain, prix_sortie, raison = resultat_position(t)
            q = tr["tickets"].index(t) + 1
            tr["fermes"].append(t)
            if raison == "objectif":
                raison = f"objectif {q}"
            log(f"{sym} : tiers {q} FERMÉ ({raison}) à {px(prix_sortie)}, résultat {gain:+.2f} $")
            with TRADES.open("a", encoding="utf-8") as f:
                if TRADES.stat().st_size == 0:
                    f.write("fermeture,symbole,sens,zone,unite,tiers,volume,entree,sortie,stop,objectif,resultat_usd,raison\n")
                f.write(f"{datetime.now():%Y-%m-%d %H:%M},{sym},{'achat' if tr['sens'] > 0 else 'vente'},{tr['cle']},"
                        f"H4->{tr['unite']},{q},{tr['volume']},{tr['prix_reel']},{prix_sortie},{tr['stop']:.2f},"
                        f"{tr['tp'][q - 1]:.2f},{gain:.2f},{raison}\n")
            telephone(f"{SYMBOLES[sym][0].capitalize()} : tiers {q} fermé",
                      f"{libelle(sym, tr)} : {raison} à {px(prix_sortie)}, résultat {gain:+.0f} $.")
    if not ouverts:                                                      # tout ce qui a été rempli est fermé
        for t in tr["tickets"]:
            if t in ordres:
                log(f"{sym} : tiers jamais rempli, ordre annulé -> {annuler(t)[1]}")
        log(f"{sym} : trade {tr['cle']} terminé")
        del etat["trades"][sym]
        return
    # 30 jours au plus
    if maintenant >= pd.Timestamp(tr["ouvert"]) + pd.Timedelta(days=TENUE_JOURS):
        for t in ouverts:
            log(f"{sym} : 30 jours atteints, tiers fermé -> {fermer(pos[t], 'chef 30 jours')[1]}")
        for t in tr["tickets"]:
            if t in ordres:
                annuler(t)


def recalcul_exact(sym: str, etat: dict, A: dict) -> None:
    """À la fin de la bougie d'entrée : stop et objectifs exactement comme le test (ATR de la bougie d'entrée, prix
    d'entrée du test)."""
    tr = etat["trades"].get(sym)
    if tr is None or tr["exact"]:
        return
    P = A["P"]
    BY = P["B"][tr["unite"]]
    t_ny = int((pd.Timestamp(tr["ouvert"]) - H7).value)
    t_e = t_ny - t_ny % BY.duree
    if t_e + BY.duree > A["T"]:
        return                                                           # bougie d'entrée pas finie
    i = int(np.searchsorted(BY.bt, t_e))
    if i >= BY.n or BY.bt[i] != t_e:
        tr["exact"] = True
        log(f"{sym} : bougie d'entrée introuvable, stop et objectifs gardés")
        return
    r = A["reel"].get(tr["cle"])
    vu = r is not None and r["unite"] == tr["unite"] and r["i"] == i
    entree = float(r["entree"]) if vu else tr["milieu"]
    pl = plan(P, t_e, entree, tr["loin"], BY.atr[i], tr["sens"])
    tr["exact"] = True
    pos = nos_positions(sym)
    if pl is None:
        for t in tr["tickets"]:
            if t in pos:
                log(f"{sym} : le test n'aurait pas pris ce trade (pas d'objectif 3 à 2 R) -> {fermer(pos[t], 'chef hors regles')[1]}")
        telephone(f"{SYMBOLES[sym][0].capitalize()} : trade fermé",
                  "Calcul exact à la fin de la bougie d'entrée : le test n'aurait pas pris ce trade, il est fermé.")
        return
    s = mt5.symbol_info(sym)
    log(f"{sym} : calcul exact ({'remplissage vu par le test' if vu else 'remplissage NON vu par le test (écart)'}) : "
        f"stop {px(tr['stop'])} -> {px(pl['stop'])}, objectifs {' / '.join(px(x) for x in pl['tp'])}")
    for q, t in enumerate(tr["tickets"]):
        if t in pos:
            ok, info, _ = _envoyer({"action": mt5.TRADE_ACTION_SLTP, "symbol": sym, "position": pos[t].ticket,
                                    "sl": round(pl["stop"], s.digits), "tp": round(pl["tp"][q], s.digits),
                                    "magic": MAGIC})
            if not ok:
                log(f"{sym} : tiers {q + 1} stop / objectif non modifiés ({info})")
    tr.update({"stop": pl["stop"], "tp": pl["tp"], "risque": pl["risque"]})


def placer(sym: str, A: dict, etat: dict, essai: bool) -> None:
    """Les ordres voulus : aucun si un trade est ouvert sur ce marché ou la journée arrêtée ; sinon, dans chaque sens,
    l'ordre que le prix rencontrerait en premier (un trade à la fois par marché)."""
    groupes = etat["groupes"].setdefault(sym, {})
    voulus = {}
    jour_arrete = etat.get("arret_jour") == etat.get("jour")
    if sym not in etat["trades"] and not jour_arrete and len(etat["trades"]) < 2 and not ARRET.exists():
        pool = list(A["candidats"])
        cles = {c["cle"] for c in pool}
        for k, g in groupes.items():
            # ordre H1 / M30 posé d'avance sur une zone pas encore touchée : hors des débuts de bougie H1 / M30, le
            # test ne le compterait pas tout de suite ; on le laisse en place plutôt que de le retirer / reposer
            # tous les quarts d'heure (léger écart possible si le prix le remplit dans ce quart d'heure-là)
            if k not in cles and not g.get("contact", True) and k in A["intactes"] and \
                    A["T"] % A["P"]["B"][g["unite"]].duree != 0:
                pool.append(g)
        for d in (1, -1):
            cs = [c for c in pool if c["sens"] == d]
            if cs:
                c = max(cs, key=lambda c: c["milieu"] * d)
                voulus[c["cle"]] = c
    ordres = nos_ordres(sym)
    pos = nos_positions(sym)
    s = mt5.symbol_info(sym)
    for k, g in list(groupes.items()):
        if any(t in pos for t in g["tickets"]):
            continue                                                     # rempli à l'instant : suivre() s'en charge
        c = voulus.get(k)
        tol = 0.02 * g["risque"]                                         # niveaux provisoires : pas de remue-ménage
        meme = c is not None and abs(c["milieu"] - g["milieu"]) < 1e-9 and abs(c["stop"] - g["stop"]) < tol and \
            all(abs(a - b) < tol for a, b in zip(c["tp"], g["tp"]))
        if meme:
            voulus.pop(k)
            continue
        if c is not None and abs(c["milieu"] - g["milieu"]) < 1e-9 and volumes(sym, c["risque"])[0] == g["volume"] \
                and all(t in ordres for t in g["tickets"]):
            # même prix, même taille : on déplace seulement le stop et les objectifs
            for q, t in enumerate(g["tickets"]):
                if not essai:
                    _envoyer({"action": mt5.TRADE_ACTION_MODIFY, "order": int(t), "price": ordres[t].price_open,
                              "sl": round(c["stop"], s.digits), "tp": round(c["tp"][q], s.digits),
                              "type_time": mt5.ORDER_TIME_SPECIFIED, "expiration": int(time.time()) + 9 * 86400,
                              "magic": MAGIC})
            g.update({"stop": c["stop"], "tp": c["tp"], "risque": c["risque"]})
            log(f"{sym} : ordre {k} : stop {px(c['stop'])}, objectifs {' / '.join(px(x) for x in c['tp'])} (recalculés)")
            voulus.pop(k)
            continue
        for t in g["tickets"]:
            if t in ordres and not essai:
                annuler(t)
        del groupes[k]
        log(f"{sym} : ordre {k} {'remplacé (niveaux recalculés)' if c is not None else 'retiré (plus valable)'}")
        if c is not None:
            c["_remplace"] = True
        elif not essai:
            telephone(f"{SYMBOLES[sym][0].capitalize()} : ordre retiré",
                      f"{libelle(sym, g)} : l'ordre à {px(g['milieu'])} est retiré (zone effacée ou délai passé).")
    for k, c in voulus.items():
        vol, plafond = volumes(sym, c["risque"])
        texte = (f"{libelle(sym, c)} : ordre limite à {px(c['milieu'])}, stop {px(c['stop'])}, objectifs "
                 f"{px(c['tp'][0])} / {px(c['tp'][1])} / {px(c['tp'][2])} (3 x {vol} lot, risque "
                 f"{RISQUE * 100:.2f} % du compte{', plafonné par le courtier' if plafond else ''}).")
        if vol <= 0:
            log(f"{sym} : {k} taille trop petite, pas d'ordre")
            continue
        if essai:
            log(f"[essai] {sym} {k} : {texte}")
            continue
        tickets, infos, marche = poser(sym, c, vol)
        log(f"{sym} : {k} {'au marché' if marche else 'ordre limite'} -> {infos}")
        if not tickets:
            continue
        groupes[k] = {"cle": k, "sens": c["sens"], "unite": c["unite"], "milieu": c["milieu"], "loin": c["loin"],
                      "stop": c["stop"], "tp": c["tp"], "risque": c["risque"], "volume": vol, "tickets": tickets,
                      "contact": c["contact"], "pose": str(maintenant_serveur())}
        telephone(f"{SYMBOLES[sym][0].capitalize()} : ordre {'déplacé' if c.get('_remplace') else 'posé'}"
                  f"{' au marché' if marche else ''}", texte)


def tour(etat: dict, essai: bool) -> None:
    now = maintenant_serveur()
    jour = now.normalize()
    if etat.get("jour") != str(jour.date()):
        etat["jour"] = str(jour.date())
    if not essai:
        for sym in SYMBOLES:
            suivre(sym, etat, now)
    # arrêt de la journée : nos trades perdent 2 %
    capitaux = mt5.account_info().equity
    if etat.get("arret_jour") != etat["jour"] and gain_du_jour(jour) <= -ARRET_JOUR * capitaux:
        etat["arret_jour"] = etat["jour"]
        log("ARRÊT DE LA JOURNÉE : nos trades perdent 2 % -> tout est fermé")
        if not essai:
            for sym in SYMBOLES:
                for t in nos_ordres(sym):
                    annuler(t)
                for p in nos_positions(sym).values():
                    log(f"{sym} : fermeture -> {fermer(p, 'chef arret jour')[1]}")
                etat["groupes"][sym] = {}
        telephone("Zones du chef : arrêt de la journée", "Nos trades perdent 2 % aujourd'hui : tout est fermé jusqu'à demain.")
    attendu = now.floor("15min") - QUART
    for sym in SYMBOLES:
        if etat["vu"].get(sym) == str(attendu):
            continue
        df = terminees(bougies_mt5(sym), now)
        if df["time"].iloc[-1] != attendu:
            if etat.get("retard", {}).get(sym) != str(attendu):
                etat.setdefault("retard", {})[sym] = str(attendu)
                log(f"{sym} : données en retard (dernière bougie {df['time'].iloc[-1]}, attendue {attendu}), nouvel essai")
            continue
        A = analyser(sym, df)
        etat["vu"][sym] = str(attendu)
        if not essai:
            recalcul_exact(sym, etat, A)
        cs = "; ".join(f"{c['cle']} {'achat' if c['sens'] > 0 else 'vente'} H4->{c['unite']} à {px(c['milieu'])} "
                       f"(stop {px(c['stop'])}, {'contact fait' if c['contact'] else 'zone pas encore touchée'})"
                       for c in A["candidats"])
        log(f"{sym} bougie {attendu:%d/%m %H:%M} : {A['vivantes']} zones H4 vivantes, {len(A['candidats'])} ordre(s) "
            f"possible(s){' : ' + cs if cs else ''}{' ; non posables d’avance : ' + str(A['manques']) if A['manques'] else ''}")
        placer(sym, A, etat, essai)


def main():
    essai = "--essai" in sys.argv
    DOSSIER.mkdir(parents=True, exist_ok=True)
    tradeco.connecter()
    for s in SYMBOLES:
        mt5.symbol_select(s, True)
    if "--rejouer" in sys.argv:
        syms = [a for a in sys.argv[sys.argv.index("--rejouer") + 1:] if a in SYMBOLES] or list(SYMBOLES)
        jours = int(sys.argv[sys.argv.index("--jours") + 1]) if "--jours" in sys.argv else JOURS_REJEU
        for s in syms:
            rejouer(s, jours)
        return
    etat = json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() and not essai else {}
    for k in ("vu", "groupes", "trades"):
        etat.setdefault(k, {})
    log(f"démarrage {'(ESSAI, aucun ordre)' if essai else '(démo Tradeco)'} ; capitaux "
        f"{mt5.account_info().equity:.0f} $ ; numéro magique {MAGIC}")
    if essai:
        tour(etat, True)
        return
    arret_fait = False
    while True:
        if ARRET.exists():
            if not arret_fait:
                for sym in SYMBOLES:
                    for t in nos_ordres(sym):
                        log(f"{sym} : arrêt volontaire, ordre annulé -> {annuler(t)[1]}")
                    etat["groupes"][sym] = {}
                ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
                log("arrêt volontaire (CHEF_ARRET) : ordres en attente annulés, positions gardées")
                arret_fait = True
            time.sleep(60)
            continue
        arret_fait = False
        try:
            tour(etat, False)
            ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            log(f"erreur {type(e).__name__}: {e}")
            try:
                tradeco.connecter()
            except Exception:
                pass
        time.sleep(20)


if __name__ == "__main__":
    main()
