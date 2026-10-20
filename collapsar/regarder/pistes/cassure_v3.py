"""LABORATOIRE CASSURE V3 (16/10/2026) — applique À LA LETTRE la liste fermée de collapsar/docs/CASSURE_AMELIORATION.md
(améliorations 1 à 6 puis 8 ; la 7 « COLLAPSAR aux commandes » est faite par un autre agent avec le moteur
collapsar/strategies/cassure.py : `faits_signaux` ci-dessous lui rend les faits connus à l'entrée de chaque signal).

PRÉCISIONS ÉCRITES AVANT TOUT RÉSULTAT (le cahier ne les fixait pas) :
- Départ = la version en démo : C2 (N = 24 h, lundi -> vendredi, sortie au milieu, agitation 14 j) + arrêt de la journée
  -3 % + compte BTC + ETH à budget partagé (cible / racine(2) x 1,25 chacun), cible 1 %.
- Développement = BTCUSD et ETHUSD (Dukascopy) + groupe A (Binance : symboles hors BTC / ETH, ordre alphabétique,
  1 sur 2 en commençant par le 1er). Période 2017 -> 10/2026 ; moitiés 2017-2021 et 2022-2026.
- Frais par aller-retour : BTC = max(0,03 %, frais FTMO fidèles) (comme cassure_crypto) ; ETH = frais FTMO fidèles
  (mains/frais_ftmo.py) ; groupe A = 0,05 %.
- Note d'une période = R + C :
  R = moyenne, sur les marchés du développement ayant >= 60 jours tradés dans la période, du rapport gain / risque
      (gain moyen par jour / agitation des gains journaliers x racine(jours tradés par an)) ; chaque marché est un compte
      à lui seul (exposition min(1, cible / agitation), arrêt de la journée compris) ;
  C = (% de challenges FTMO réussis - % morts) / 100 sur le compte BTC + ETH (frais FTMO, départ tous les 10 jours tradés
      dans la période).
- Une variante est gardée si sa note 2017-2026 dépasse celle de la version en cours ET si sa note n'est plus basse sur
  aucune des deux moitiés ; entre plusieurs variantes admises (améliorations 5 et 8), la meilleure note 2017-2026.
- Amélioration 2 (week-end) : R sur le groupe A seulement (Binance) et C sur le compte BTC + ETH de Binance (BTCUSDT,
  ETHUSDT, frais FTMO) s'ils existent. Si le week-end est gardé, BTC et ETH viennent ensuite de Binance (Dukascopy n'a
  presque pas de week-end).
- Amélioration 8, réduction près du mur : taille x 1 si la distance au mur des -10 % de la phase >= 6 %, x 0,5 si >= 4 %,
  x 0,25 sinon (décidée chaque matin) ; grille 4 cibles x (avec / sans réduction).
- Binance, filtre imposé par le coordinateur (identique pour tous) : 7 premiers jours de chaque paire ignorés ; bougie
  avec bas < 0,5 x clôture ou haut > 2 x clôture -> bas / haut ramenés à min / max(ouverture, clôture) ; krach éclair
  réel du 10/10/2025 gardé tel quel ; MATICUSDT et POLUSDT restent deux symboles séparés.
- Jumeaux : 20 (sens au hasard, mêmes moments, même taille) pour les challenges ; force contre le jumeau par marché.
- Groupe B : JAMAIS lu par `main` ; `confirmation()` l'évalue une seule fois (verrou vie/cassure_v3/confirmation.json).

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.cassure_v3 [controle | confirmation]
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, replace
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mains.frais_ftmo import frais as frais_ftmo
from collapsar.strategies import cassure as cs

VIE = dm.RACINE / "collapsar" / "vie" / "cassure_v3"
JOURNAL = VIE / "journal.txt"
VERROU = VIE / "confirmation.json"
PERIODES = {"2017-2026": ("2017-01-01", "2027-01-01"), "2017-2021": ("2017-01-01", "2022-01-01"),
            "2022-2026": ("2022-01-01", "2027-01-01")}
DEPART = cs.Reglages()                       # version en démo + compte BTC + ETH
ENSEMBLE = (12, 18, 24, 30, 36, 48)
N_JUMEAUX = 20


def log(txt: str) -> None:
    print(txt, flush=True)
    VIE.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(txt + "\n")


# ---------------------------------------------------------------- marchés et frais
def frais_de(sym: str):
    base = sym.replace("USDT", "").replace("USD", "")
    if base == "BTC":
        return lambda p: np.maximum(0.0003, frais_ftmo("BTCUSD", p))
    if base == "ETH":
        return lambda p: frais_ftmo("ETHUSD", p)
    return 0.0005


def binance_dispo() -> list[str]:
    return sorted(p.name[:-len("_M15.csv")] for p in cs.BINANCE.glob("*_M15.csv"))


def groupes() -> tuple[list[str], list[str]]:
    if not (cs.BINANCE / "LISEZMOI.md").exists():
        raise RuntimeError("data/binance/LISEZMOI.md absent : téléchargement Binance pas fini")
    autres = [s for s in binance_dispo() if s.replace("USDT", "") not in ("BTC", "ETH")]
    return autres[0::2], autres[1::2]


def source_btc_eth(reg: cs.Reglages) -> tuple[tuple[str, str], tuple[str, str]]:
    if reg.week_end and {"BTCUSDT", "ETHUSDT"} <= set(binance_dispo()):
        return ("BTCUSDT", "binance"), ("ETHUSDT", "binance")
    return ("BTCUSD", "dukascopy"), ("ETHUSD", "dukascopy")


# ---------------------------------------------------------------- évaluation
def eval_marche(sym: str, source: str, reg: cs.Reglages) -> dict:
    mk = cs.Marche(sym, source, reg, frais_de(sym))
    jours = mk.jours
    W = cs.additionner([mk.chemin(reg.cible)], jours)
    g, _ = cs.serie_jour(W, jours, reg.arret_jour)
    out = {}
    for p, (de, a) in PERIODES.items():
        gp = g[(g.index >= de) & (g.index < a)]
        x = cs.mesures(gp) if len(gp) >= 60 else {"jours": int(len(gp))}
        x["force"] = mk.force(reg.cible, de, a)
        x["trades"] = int(((mk.t["jour"] >= de) & (mk.t["jour"] < a)).sum())
        out[p] = x
    del mk, W
    return out


def eval_compte(reg: cs.Reglages, paires) -> dict:
    """Compte FTMO : BTC + ETH (budget partagé) ou BTC seul ; challenges contre 20 jumeaux."""
    if reg.compte == "btc":
        paires, poids = paires[:1], reg.cible
    else:
        poids = reg.cible / math.sqrt(2) * 1.25
    chem, chem_j, jours = [], [[] for _ in range(N_JUMEAUX)], None
    for i, (sym, src) in enumerate(paires):
        mk = cs.Marche(sym, src, reg, frais_de(sym))
        jours = mk.jours if jours is None else jours.union(mk.jours)
        chem.append(mk.chemin(poids))
        for k, sg in enumerate(mk.signes_jumeaux(N_JUMEAUX, 7 + i)):
            chem_j[k].append(mk.chemin(poids, sg))
        del mk
    W = cs.additionner(chem, jours)
    Wj = [cs.additionner(c, jours) for c in chem_j]
    del chem, chem_j
    out = {}
    for p, (de, a) in PERIODES.items():
        sel = np.asarray((jours >= de) & (jours < a))
        g, _ = cs.serie_jour(W[sel], jours[sel], reg.arret_jour)
        x = cs.mesures(g)
        x["challenge"] = cs.challenge(W[sel], reg.arret_jour, reg.reduction_mur)
        jj = [cs.challenge(w[sel], reg.arret_jour, reg.reduction_mur) for w in Wj]
        x["jumeaux_reussis_pct"] = float(np.mean([c["reussis_pct"] for c in jj]))
        x["jumeaux_morts_pct"] = float(np.mean([c["morts_pct"] for c in jj]))
        out[p] = x
    return out


def evaluer(reg: cs.Reglages, marches_R: list[tuple[str, str]], paires) -> dict:
    res = {"reglages": asdict(reg), "marches": {}, "compte": None, "note": {}, "R": {}, "C": {}}
    for sym, src in marches_R:
        res["marches"][sym] = eval_marche(sym, src, reg)
    res["compte"] = eval_compte(reg, paires) if paires else None
    for p in PERIODES:
        r = [x[p].get("rapport", np.nan) for x in res["marches"].values()]
        r = [v for v in r if v is not None and np.isfinite(v)]
        R = float(np.mean(r)) if r else 0.0
        if res["compte"]:
            ch = res["compte"][p]["challenge"]
            C = (ch["reussis_pct"] - ch["morts_pct"]) / 100
        else:
            C = 0.0
        res["R"][p], res["C"][p], res["note"][p] = R, C, R + C
    return res


def resume(nom: str, x: dict) -> str:
    n, R, C = x["note"], x["R"], x["C"]
    s = " | ".join(f"{p}: note {n[p]:+.3f} (R {R[p]:+.3f}, C {C[p]:+.3f})" for p in PERIODES)
    if x["compte"]:
        c = x["compte"]["2017-2026"]
        s += (f" | compte {c['pct_mois']:+.2f} %/mois, baisse {c['baisse_max_pct']:.1f} %, challenges "
              f"{c['challenge']['reussis_pct']:.0f} % réussis / {c['challenge']['morts_pct']:.0f} % morts "
              f"(jumeaux {c['jumeaux_reussis_pct']:.0f} / {c['jumeaux_morts_pct']:.0f})")
    return f"  {nom:28s} {s}"


def decider(courant: str, essais: dict) -> str:
    """Meilleure variante admise : note 2017-2026 plus haute que la version en cours ET aucune moitié plus basse."""
    ref = essais[courant]["note"]
    admis = [k for k, x in essais.items() if k != courant and x["note"]["2017-2026"] > ref["2017-2026"]
             and x["note"]["2017-2021"] >= ref["2017-2021"] and x["note"]["2022-2026"] >= ref["2022-2026"]]
    return max(admis, key=lambda k: essais[k]["note"]["2017-2026"]) if admis else courant


def main():
    VIE.mkdir(parents=True, exist_ok=True)
    groupe_a, _ = groupes()                      # le groupe B n'est jamais chargé ici
    log(f"\n===== {datetime.now():%d/%m %H:%M} laboratoire cassure v3 ; groupe A = {groupe_a}")
    reg = DEPART
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "groupe_A": groupe_a, "etapes": []}

    def dev(r):
        b, e = source_btc_eth(r)
        return [b, e] + [(s, "binance") for s in groupe_a], [b, e]

    etapes = [
        ("1 ensemble de canaux", lambda r: {"actuel": r, "ensemble 12-48 h": replace(r, N=ENSEMBLE)}, None),
        ("2 week-end", lambda r: {"actuel": r, "week-end": replace(r, week_end=True)}, "binance"),
        ("3 sortie", lambda r: {"actuel": r, "canal opposé N/2": replace(r, sortie="oppose" if r.sortie == "milieu"
                                                                          else "milieu")}, None),
        ("4 taille", lambda r: {"actuel": r, "agitation 24 h": replace(r, taille="24h")}, None),
        ("5 arrêt du jour", lambda r: {"actuel": r, **{f"arrêt {lbl}": replace(r, arret_jour=v) for lbl, v in
                                       (("-3 %", 0.03), ("-2 %", 0.02), ("aucun", None)) if v != r.arret_jour}}, None),
        ("6 compte", lambda r: {"actuel": r, "BTC seul": replace(r, compte="btc")}, None),
        ("8 risque du challenge", lambda r: {"actuel": r, **{
            f"cible {c * 100:.2f} %{' + réduction' if red else ''}": replace(r, cible=c, reduction_mur=red)
            for c in (0.0075, 0.01, 0.0125, 0.015) for red in (False, True)
            if not (c == r.cible and red == r.reduction_mur)}}, None),
    ]
    for titre, variantes, juge in etapes:
        log(f"\n--- amélioration {titre}")
        essais = {}
        for nom, rv in variantes(reg).items():
            if juge == "binance":
                paires = [(s, "binance") for s in ("BTCUSDT", "ETHUSDT") if s in binance_dispo()]
                marches = [(s, "binance") for s in groupe_a]
                paires = paires if len(paires) == 2 else []
            else:
                marches, paires = dev(rv)
            essais[nom] = evaluer(rv, marches, paires)
            log(resume(nom, essais[nom]))
        choix = decider("actuel", essais)
        reg = cs.Reglages(**{**essais[choix]["reglages"], "N": tuple(essais[choix]["reglages"]["N"])})
        log(f"  => {'GARDÉE : ' + choix if choix != 'actuel' else 'REJETÉE (on garde la version en cours)'}")
        sortie["etapes"].append({"amelioration": titre, "juge": juge or "développement", "choix": choix,
                                 "essais": essais})
        (VIE / "resultats.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=float),
                                            encoding="utf-8")
    sortie["version_retenue"] = asdict(reg)
    (VIE / "resultats.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=float),
                                        encoding="utf-8")
    log(f"\nVERSION RETENUE : {asdict(reg)}")
    rapport()


def _texte_reglages(r: dict) -> str:
    arret = "aucun" if not r["arret_jour"] else f"-{r['arret_jour'] * 100:.0f} %"
    return (f"canaux {'/'.join(str(n) for n in r['N'])} h ; {'7 j / 7' if r['week_end'] else 'lundi -> vendredi'} ; "
            f"sortie {'milieu du canal' if r['sortie'] == 'milieu' else 'canal opposé N/2'} ; agitation "
            f"{'14 jours' if r['taille'] == '14j' else '24 heures'} ; arrêt du jour {arret} ; "
            f"cible {r['cible'] * 100:.2f} % ; {'réduction près du mur' if r['reduction_mur'] else 'sans réduction'} ; "
            f"compte {'BTC + ETH' if r['compte'] == 'btc_eth' else 'BTC seul'}")


def rapport() -> None:
    res = json.loads((VIE / "resultats.json").read_text(encoding="utf-8"))
    L = ["# Cassure crypto v3 : amélioration pas à pas (liste fermée du 16/10/2026)", "",
         "Règles du juge : `collapsar/docs/CASSURE_AMELIORATION.md` (figé) ; précisions écrites avant les résultats dans "
         "l'en-tête de `collapsar/regarder/pistes/cassure_v3.py`. Moteur : `collapsar/strategies/cassure.py` (redonne "
         "exactement les trades de C2).", "",
         "**Note** d'une période = R + C. R = rapport gain / risque moyen des marchés du développement (BTC, ETH et "
         f"groupe A : {', '.join(res['groupe_A'])}), chacun seul à la cible choisie ; C = (challenges FTMO réussis - "
         "morts) / 100 sur le compte BTC + ETH. Une idée est gardée si la note 2017-2026 monte sans baisser sur aucune "
         "des deux moitiés (2017-2021, 2022-2026).", ""]
    for e in res["etapes"]:
        L += [f"## Amélioration {e['amelioration']} — {'GARDÉE : ' + e['choix'] if e['choix'] != 'actuel' else 'rejetée'}",
              f"(jugée sur : {e['juge']})", "",
              "| variante | note 2017-2026 | note 2017-2021 | note 2022-2026 | R 17-26 | compte %/mois | baisse max | "
              "challenges réussis / morts | jumeaux réussis / morts |", "|---|---|---|---|---|---|---|---|---|"]
        for nom, x in e["essais"].items():
            n = x["note"]
            c = x["compte"]["2017-2026"] if x["compte"] else None
            cc = (f"{c['pct_mois']:+.2f} % | {c['baisse_max_pct']:.1f} % | {c['challenge']['reussis_pct']:.0f} % / "
                  f"{c['challenge']['morts_pct']:.0f} % | {c['jumeaux_reussis_pct']:.0f} % / {c['jumeaux_morts_pct']:.0f} %"
                  if c else "— | — | — | —")
            L.append(f"| {nom} | {n['2017-2026']:+.3f} | {n['2017-2021']:+.3f} | {n['2022-2026']:+.3f} | "
                     f"{x['R']['2017-2026']:+.3f} | {cc} |")
        L.append("")
    if "version_retenue" in res:
        r = res["version_retenue"]
        L += ["## Version retenue", "", _texte_reglages(r), ""]
        dern = res["etapes"][-1]["essais"][res["etapes"][-1]["choix"]]
        L += ["| marché | période | trades | %/mois | rapport gain/risque | baisse max | force contre le jumeau |",
              "|---|---|---|---|---|---|---|"]
        for sym, x in dern["marches"].items():
            for p in PERIODES:
                y = x[p]
                if "pct_mois" in y:
                    L.append(f"| {sym} | {p} | {y['trades']} | {y['pct_mois']:+.2f} % | {y['rapport']:+.2f} | "
                             f"{y['baisse_max_pct']:.1f} % | {y['force']:+.1f} |")
        if dern["compte"]:
            L += ["", "Compte FTMO BTC + ETH :", "", "| période | %/mois | baisse max | pire jour | challenges réussis / "
                  "morts | jumeaux | durée médiane (jours tradés) |", "|---|---|---|---|---|---|---|"]
            for p in PERIODES:
                c = dern["compte"][p]
                L.append(f"| {p} | {c['pct_mois']:+.2f} % | {c['baisse_max_pct']:.1f} % | {c['pire_jour_pct']:.1f} % | "
                         f"{c['challenge']['reussis_pct']:.0f} % / {c['challenge']['morts_pct']:.0f} % | "
                         f"{c['jumeaux_reussis_pct']:.0f} % / {c['jumeaux_morts_pct']:.0f} % | "
                         f"{c['challenge']['jours_median']} |")
        L += ["", "Groupe B (confirmation) : PAS ENCORE OUVERT — `python -m collapsar.regarder.pistes.cassure_v3 "
              "confirmation`, une seule fois, à la demande du coordinateur.",
              "", "Amélioration 7 (COLLAPSAR aux commandes) : laissée à l'autre agent ; `cassure_v3.faits_signaux(reglages)` "
              "rend pour chaque signal les faits connus à l'entrée.", "",
              "Prudence : tout ce développement a déjà été regardé ; seul le groupe B et la démo diront si ces gains "
              "tiennent."]
    (VIE / "rapport.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- amélioration 7 (autre agent)
def faits_signaux(reg: cs.Reglages, sym: str = "BTCUSD", source: str = "dukascopy",
                  autre: tuple[str, str] | None = ("ETHUSD", "dukascopy")) -> pd.DataFrame:
    """Trades de la version `reg` sur `sym` + faits connus à l'entrée de chaque signal (cahier, amélioration 7)."""
    mk = cs.Marche(sym, source, reg, frais_de(sym))
    ma = cs.matrice(autre[0], autre[1], reg.week_end) if autre else None
    faits = cs.faits_entree(mk.m, mk.t, ma)
    exp = cs.expositions(mk.t, reg.cible, reg.plafond)
    faits["expo"] = exp
    faits["gain_net"] = exp * (mk.t["sens"].to_numpy() * mk.t["r_prix"].to_numpy() - mk.t["frais"].to_numpy())
    faits["pire_point"] = exp * (np.minimum(np.where(mk.t["sens"] > 0, mk.t["adv_achat"], mk.t["adv_vente"]), 0)
                                 - mk.t["frais"].to_numpy())
    return faits


# ---------------------------------------------------------------- groupe B (une seule fois)
def confirmation() -> dict:
    """Évalue UNE fois la version retenue (et la version de départ, pour comparaison) sur le groupe B."""
    if VERROU.exists():
        print("Confirmation DÉJÀ faite :", VERROU.read_text(encoding="utf-8")[:3000])
        return json.loads(VERROU.read_text(encoding="utf-8"))
    res = json.loads((VIE / "resultats.json").read_text(encoding="utf-8"))
    if "version_retenue" not in res:
        raise RuntimeError("le laboratoire n'a pas fini : pas de version retenue")
    v = res["version_retenue"]
    finale = cs.Reglages(**{**v, "N": tuple(v["N"])})
    _, groupe_b = groupes()
    VERROU.write_text(json.dumps({"quand": datetime.now().isoformat(timespec="seconds"), "etat": "en cours"}),
                      encoding="utf-8")                                   # verrou posé AVANT de regarder
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "groupe_B": groupe_b,
              "version_finale": asdict(finale), "version_depart": asdict(DEPART)}
    for nom, reg in (("finale", finale), ("depart", DEPART)):
        x = evaluer(reg, [(s, "binance") for s in groupe_b], [])
        sortie[nom] = {"R": x["R"], "marches": x["marches"]}
        log(f"CONFIRMATION groupe B | {nom}: " + " | ".join(f"{p}: R {x['R'][p]:+.3f}" for p in PERIODES))
    VERROU.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return sortie


def controle():
    """Le moteur redonne exactement C2 (bitcoin_journee.var_C, N = 24, sans week-end)."""
    from collapsar.regarder.pistes import bitcoin_journee as bj
    bj.SYM = "BTCUSD"
    bj.VIE = VIE / "controle_bj"                 # cache à part : aucun fichier existant touché
    m0 = bj.matrice("2027-01-01")
    t_ref = bj.trades(m0, bj.var_C(m0, 24), bj.agitation(m0))
    mk = cs.Marche("BTCUSD", "dukascopy", cs.Reglages(arret_jour=None), 0.0003)
    egal = all(np.array_equal(t_ref[c].to_numpy(), mk.t[c].to_numpy()) for c in ("d", "sens", "m_entree", "m_sortie"))
    ecart = max(float(np.abs(t_ref[c].to_numpy() - mk.t[c].to_numpy()).max())
                for c in ("r_prix", "adv_achat", "adv_vente", "agitation"))
    g_ref, w_ref = bj.journalier(t_ref, 0.0003, 0.01)
    W = mk.chemin(0.01)
    g, w = cs.apres_arret(W.to_numpy(), None)
    eg = float(max(np.abs(g_ref.to_numpy() - g).max(), np.abs(w_ref.to_numpy() - w).max()))
    log(f"CONTRÔLE C2 : {len(t_ref)} trades / {len(mk.t)} ; mêmes trades = {egal} ; écart max prix {ecart:.1e} ; "
        f"écart max gains / pires points du jour {eg:.1e}")
    return egal and ecart == 0 and eg < 1e-12


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "labo"
    if arg == "controle":
        controle()
    elif arg == "confirmation":
        confirmation()
    else:
        controle()
        main()
