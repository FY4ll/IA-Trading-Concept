"""Relevé des VRAIS écarts de prix (achat - vente) de chaque marché, sur le compte démo Tradeco. LECTURE SEULE : aucun
ordre, aucune connexion forcée (on lit le compte déjà ouvert dans MetaTrader ; si ce n'est pas un compte démo, rien).

Deux usages :
- `main()` (ancienne tâche Windows « TestIA_CollapsarEcarts », désactivée) : UN relevé de tous les marchés, ajouté à
  collapsar/vie/ecarts/releve_AAAAMMJJ.csv (heure serveur, marché, prix moyen, écart en part du prix) ;
- `seance` (16/10/2026, audit des frais, défaut 5) : relevé toutes les 5 minutes pendant la séance de New York
  (15h30 -> 22h00 heure de Paris, toutes les minutes pendant le premier quart d'heure pour mesurer l'écart de
  l'ouverture), médiane par marché dans collapsar/vie/releves/ecarts_tradeco_AAAAMMJJ.json (réécrit après chaque
  relevé), relevés bruts dans ecarts_tradeco_AAAAMMJJ_brut.csv. Sert à comparer au relevé FTMO de 03h34 serveur
  (heures creuses, mains/conditions_ftmo.json) : on n'applique RIEN automatiquement aux fiches.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.surveillance.releve_ecarts seance [--debut 15:30]
[--fin 22:00] [--pas 5]
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta

import MetaTrader5 as mt5
import numpy as np

from collapsar.donnees import marches as dm

SYMBOLES = dm.RACINE / "runs" / "20260919_envv2" / "code" / "data" / "aurexis_live" / "symboles.json"
DOSSIER = dm.RACINE / "collapsar" / "vie" / "ecarts"
DOSSIER_SEANCE = dm.RACINE / "collapsar" / "vie" / "releves"
FTMO = dm.RACINE / "collapsar" / "mains" / "conditions_ftmo.json"
FRAIS_PERIME = 120                     # secondes : un prix plus vieux que le plus récent de ~2 min = marché fermé


def main():
    if not mt5.initialize():
        return                                   # MetaTrader fermé : on réessaiera dans 15 minutes
    DOSSIER.mkdir(parents=True, exist_ok=True)
    noms = json.loads(SYMBOLES.read_text(encoding="utf-8"))
    lignes = []
    for marche, sym in noms.items():
        if not sym or not mt5.symbol_select(sym, True):
            continue
        t = mt5.symbol_info_tick(sym)
        if not t or t.bid <= 0 or t.ask <= 0:
            continue
        milieu = (t.bid + t.ask) / 2
        heure = datetime.utcfromtimestamp(t.time).strftime("%Y-%m-%d %H:%M:%S")   # heure serveur du dernier prix
        lignes.append(f"{heure},{marche},{milieu:.6g},{(t.ask - t.bid) / milieu:.8f}")
    mt5.shutdown()
    fichier = DOSSIER / f"releve_{datetime.now():%Y%m%d}.csv"
    neuf = not fichier.exists()
    with open(fichier, "a", encoding="utf-8") as f:
        if neuf:
            f.write("heure_serveur,marche,prix,ecart\n")
        f.write("\n".join(lignes) + "\n")


# ---------------------------------------------------------------------------------------- séance de New York
def dire(t: str) -> None:
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {t}", flush=True)


def _a_l_heure(jour: datetime, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return jour.replace(hour=h, minute=m, second=0, microsecond=0)


def instants(debut: datetime, fin: datetime, pas: int, ouverture_min: int = 15) -> list[datetime]:
    """Heures des relevés : chaque minute pendant les `ouverture_min` premières minutes, puis tous les `pas`."""
    out, t = [], debut
    while t <= fin:
        out.append(t)
        t += timedelta(minutes=1 if t < debut + timedelta(minutes=ouverture_min) else pas)
    return out


def un_releve(noms: dict) -> list[dict]:
    """Un relevé de tous les marchés ouverts (prix frais), en part du prix moyen."""
    ticks = {}
    for marche, sym in noms.items():
        if not sym or not mt5.symbol_select(sym, True):
            continue
        t = mt5.symbol_info_tick(sym)
        if t and t.bid > 0 and t.ask > 0:
            ticks[marche] = (sym, t)
    if not ticks:
        return []
    recent = max(t.time for _, t in ticks.values())
    lignes = []
    for marche, (sym, t) in ticks.items():
        if recent - t.time > FRAIS_PERIME:
            continue                                         # marché fermé (dernier prix trop vieux)
        milieu = (t.bid + t.ask) / 2
        lignes.append({"local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                       "serveur": datetime.utcfromtimestamp(t.time).strftime("%Y-%m-%d %H:%M:%S"),
                       "marche": marche, "symbole": sym, "bid": t.bid, "ask": t.ask,
                       "ecart": (t.ask - t.bid) / milieu})
    return lignes


def resumer(lignes: list[dict], debut: datetime, ouverture_min: int = 15) -> dict:
    """Médiane par marché (toute la séance) + médiane du premier quart d'heure (l'ouverture de New York)."""
    try:
        ftmo = json.loads(FTMO.read_text(encoding="utf-8"))["marches"]
    except Exception:
        ftmo = {}
    fin_ouv = (debut + timedelta(minutes=ouverture_min)).strftime("%Y-%m-%d %H:%M:%S")
    par = {}
    for l in lignes:
        par.setdefault(l["marche"], []).append(l)
    res = {}
    for m, ls in sorted(par.items()):
        e = np.array([l["ecart"] for l in ls]) * 100
        ouv = np.array([l["ecart"] for l in ls if l["local"] < fin_ouv]) * 100
        med = float(np.median(e))
        f = ftmo.get(m, {}).get("ecart_pct")
        res[m] = {"symbole": ls[0]["symbole"], "releves": int(len(e)), "ecart_median_pct": med,
                  "ecart_p10_pct": float(np.percentile(e, 10)), "ecart_p90_pct": float(np.percentile(e, 90)),
                  "ecart_ouverture_pct": float(np.median(ouv)) if len(ouv) else None,
                  "facteur_ouverture": float(np.median(ouv) / med) if len(ouv) and med > 0 else None,
                  "ftmo_03h34_pct": f, "tradeco_sur_ftmo": (med / f) if f else None}
    return res


def ecrire_json(chemin, contenu: dict) -> None:
    tmp = chemin.with_suffix(".tmp")
    tmp.write_text(json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, chemin)


def seance(debut_hhmm: str = "15:30", fin_hhmm: str = "22:00", pas: int = 5) -> None:
    DOSSIER_SEANCE.mkdir(parents=True, exist_ok=True)
    jour = datetime.now()
    debut, fin = _a_l_heure(jour, debut_hhmm), _a_l_heure(jour, fin_hhmm)
    noms = json.loads(SYMBOLES.read_text(encoding="utf-8"))
    sortie = DOSSIER_SEANCE / f"ecarts_tradeco_{jour:%Y%m%d}.json"
    brut = DOSSIER_SEANCE / f"ecarts_tradeco_{jour:%Y%m%d}_brut.csv"
    lignes: list[dict] = []
    compte = None
    dire(f"relevé des écarts Tradeco de {debut:%H:%M} à {fin:%H:%M} (heure de Paris), toutes les {pas} min")
    for quand in instants(debut, fin, pas):
        attente = (quand - datetime.now()).total_seconds()
        if attente < -60:
            continue                                         # instant déjà passé (lancement tardif)
        if attente > 0:
            time.sleep(attente)
        if not mt5.initialize():
            dire(f"MetaTrader injoignable ({mt5.last_error()}) : relevé sauté")
            continue
        a = mt5.account_info()
        if a is None or a.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            dire("compte ouvert dans MetaTrader absent ou non démo : relevé sauté (aucune connexion forcée)")
            continue
        compte = a.server
        nouv = un_releve(noms)
        lignes += nouv
        neuf = not brut.exists()
        with open(brut, "a", encoding="utf-8") as f:
            if neuf:
                f.write("local,serveur,marche,symbole,bid,ask,ecart\n")
            for l in nouv:
                f.write(f"{l['local']},{l['serveur']},{l['marche']},{l['symbole']},{l['bid']},{l['ask']},"
                        f"{l['ecart']:.8f}\n")
        ecrire_json(sortie, {"source": f"compte démo Tradeco ({compte}), lecture seule",
                             "seance_paris": f"{debut:%Y-%m-%d %H:%M} -> {fin:%H:%M}", "pas_minutes": pas,
                             "dernier_releve": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                             "comparaison": "ftmo_03h34_pct = écart relevé sur le compte d'essai FTMO le 15/10 à "
                                            "03h34 serveur (mains/conditions_ftmo.json)",
                             "marches": resumer(lignes, debut)})
        dire(f"{quand:%H:%M} : {len(nouv)} marchés relevés")
    mt5.shutdown()
    dire(f"fin du relevé : {sortie}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", nargs="?", default="un")
    p.add_argument("--debut", default="15:30")
    p.add_argument("--fin", default="22:00")
    p.add_argument("--pas", type=int, default=5)
    a = p.parse_args()
    if a.mode == "seance":
        seance(a.debut, a.fin, a.pas)
    else:
        main()
