"""Le JUGE DES MAÎTRES (15/10/2026) : un historique de trades réel -> ce trader bat-il le hasard, et survivrait-il
aux murs FTMO ? Seuls les vrais gagnants deviennent des maîtres pour l'école de COLLAPSAR.

Pour chaque marché, un TRADE = de la position nulle au retour à la position nulle (on peut entrer et sortir en
plusieurs morceaux, comme Paul Wei). Pour chaque trade : gain brut (avant frais), frais, durée.
- force contre le hasard : son jumeau prend chaque trade dans l'autre sens (le gain brut change de signe, les frais
  restent) ; force = somme des gains bruts / racine(somme des carrés) — au-dessus de 3 = prouvé (même seuil que
  pour notre IA, juge/note.py) ;
- profil : part de trades gagnants, gain moyen d'un gagnant / perte moyenne d'un perdant, part du total faite par
  les 5 meilleurs trades ;
- murs FTMO : pire journée et pire baisse depuis un sommet, rapportées à la taille du compte. La taille du compte
  dans le passé est reconstruite à partir de sa valeur actuelle moins les gains d'après (approximation : les dépôts
  et retraits ne sont pas comptés) -> « compatible FTMO » si, ramené à la même prise de risque, il n'aurait jamais
  perdu 5 % en un jour ni 10 % depuis le début.
Formats lus : Hyperliquid (coin, px, sz, side, time, startPosition, closedPnl, fee).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.maitres.juge
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from collapsar.maitres.hyperliquid import DOSSIER, hors_crypto


def trades_hyperliquid(df: pd.DataFrame) -> pd.DataFrame:
    """Les exécutions -> un trade par aller-retour complet, par marché."""
    # plusieurs exécutions d'un même ordre arrivent à la même milliseconde, dans le désordre : dans une même
    # milliseconde, la position avance dans le sens de l'ordre (vérifié : chaîne des positions cohérente à ~100 %)
    df = df.assign(_cle=df["startPosition"].astype(float) * np.where(df["side"] == "B", 1.0, -1.0))
    df = df.sort_values(["time", "_cle"])
    lignes = []
    for coin, g in df.groupby("coin"):
        signe = np.where(g["side"].to_numpy() == "B", 1.0, -1.0)
        sz = g["sz"].astype(float).to_numpy()
        avant = g["startPosition"].astype(float).to_numpy()
        apres = avant + signe * sz
        brut = g["closedPnl"].astype(float).to_numpy()
        frais = g["fee"].astype(float).to_numpy()
        t = g["time"].to_numpy()
        debut, b, f = None, 0.0, 0.0
        for i in range(len(g)):
            if debut is None and abs(avant[i]) < 1e-12:
                debut, b, f = t[i], 0.0, 0.0
            if debut is None:
                continue                      # position déjà ouverte avant le début de l'historique : ignorée
            b += brut[i]
            f += frais[i]
            if abs(apres[i]) < 1e-9 * max(1.0, abs(avant[i])):
                lignes.append({"marche": coin, "debut": debut, "fin": t[i], "brut": b, "frais": f, "net": b - f,
                               "hors_crypto": hors_crypto(coin)})
                debut = None
    tr = pd.DataFrame(lignes)
    if len(tr):
        tr["debut"] = pd.to_datetime(tr["debut"], unit="ms")
        tr["fin"] = pd.to_datetime(tr["fin"], unit="ms")
    return tr


def decisions_hyperliquid(df: pd.DataFrame) -> pd.DataFrame:
    """Unité de jugement pour TOUS les styles (15/10 : certains traders ne sont jamais à plat, ils agrandissent et
    réduisent une position permanente) : chaque ORDRE qui encaisse (gain ou perte réalisé) est une décision ; son
    gain brut change de signe chez le jumeau au hasard. « debut » = « fin » = l'heure de l'ordre."""
    d = df.assign(brut=df["closedPnl"].astype(float), frais=df["fee"].astype(float))
    g = d.groupby(["coin", "oid"]).agg(fin=("time", "max"), brut=("brut", "sum"), frais=("frais", "sum"))
    g = g[g["brut"] != 0].reset_index()
    g["net"] = g["brut"] - g["frais"]
    g["fin"] = pd.to_datetime(g["fin"], unit="ms")
    g["debut"] = g["fin"]
    g["hors_crypto"] = g["coin"].map(hors_crypto)
    return g.rename(columns={"coin": "marche"})


def juger(tr: pd.DataFrame, courbe: dict | None = None) -> dict:
    if len(tr) < 30:
        return {"trades": len(tr), "verdict": "trop peu de trades"}
    net, brut = tr["net"], tr["brut"]
    gagnants, perdants = net[net > 0], net[net < 0]
    force = float(brut.sum() / math.sqrt((brut ** 2).sum())) if (brut ** 2).sum() > 0 else 0.0
    duree_h = (tr["fin"] - tr["debut"]).dt.total_seconds() / 3600
    mois = max((tr["fin"].max() - tr["debut"].min()).days / 30.4, 1.0)
    risque = risque_courbe(courbe) if courbe else {}
    return {"trades": int(len(tr)), "mois": round(mois, 1), "gagnants_pct": float((net > 0).mean() * 100),
            "gain_moyen_sur_perte_moyenne": float(gagnants.mean() / -perdants.mean()) if len(perdants) and len(gagnants) else None,
            "gain_net": float(net.sum()), "frais": float(tr["frais"].sum()), "force": force, "prouve": force > 3,
            "part_5_meilleurs_pct": float(net.nlargest(5).sum() / net.sum() * 100) if net.sum() > 0 else None,
            "duree_mediane_h": float(duree_h.median()), "hors_crypto_pct": float(tr["hors_crypto"].mean() * 100),
            "marches": tr["marche"].value_counts().head(6).to_dict(), **risque}


def risque_courbe(courbe: dict) -> dict:
    """Le risque à partir des courbes OFFICIELLES de la bourse (valeur du compte, gains cumulés). Les gains et pertes
    sont rapportés à la TAILLE HABITUELLE du compte (sa valeur médiane) : robuste aux dépôts, retraits et transferts
    vers des sous-comptes (15/10 : rapportés à la valeur du moment, une semaine où le compte était presque vide
    donnait -100 %). Pire baisse, rendement mensuel, mois positifs sur tout l'historique ; pire journée sur le dernier
    mois (courbe fine) ; ramené à une taille compatible FTMO (pire baisse 8 %)."""
    def serie(fenetre):
        d = courbe.get(fenetre) or {}
        av = pd.DataFrame(d.get("accountValueHistory", []), columns=["t", "v"]).astype(float)
        pn = pd.DataFrame(d.get("pnlHistory", []), columns=["t", "p"]).astype(float)
        if len(av) < 3 or len(pn) < 3:
            return None
        x = av.merge(pn, on="t").sort_values("t")
        taille = float(x["v"][x["v"] > 100].median()) if (x["v"] > 100).any() else float("nan")
        return x, taille
    tout, mois = serie("perpAllTime"), serie("perpMonth")
    if tout is None or not np.isfinite(tout[1]):
        return {"courbe": "absente"}
    x, taille = tout
    jours = float((x["t"].iloc[-1] - x["t"].iloc[0]) / 86_400_000)
    if jours < 30:
        return {"courbe": "trop courte"}
    cumul = (x["p"] - x["p"].iloc[0]) / taille                     # gains cumulés en part du compte habituel
    baisse = float((cumul - cumul.cummax()).min())
    periodes = cumul.diff().dropna()
    mensuel = float(cumul.iloc[-1] / jours * 30.4 * 100)
    pire_jour = None
    if mois is not None and np.isfinite(mois[1]):
        xm, tm = mois
        jm = (xm.set_index(pd.to_datetime(xm["t"], unit="ms"))["p"].resample("1D").last().ffill().diff() / tm).dropna()
        pire_jour = float(jm.min() * 100) if len(jm) else None
    if periodes.abs().max() > 1.0:
        # une période qui gagne ou perd plus que le compte habituel entier : sous-comptes, coffres ou levier extrême ;
        # le risque n'est PAS mesurable de façon fiable (15/10, constaté sur de gros comptes Hyperliquid)
        return {"courbe": "incohérente : risque non mesurable", "jours_de_courbe": round(jours)}
    facteur = min(1.0, 0.08 / max(-baisse, 1e-9))
    return {"jours_de_courbe": round(jours), "taille_habituelle": taille, "rendement_mensuel_pct": mensuel,
            "pire_baisse_pct": baisse * 100, "pire_periode_pct": float(periodes.min() * 100),
            "pire_jour_mois_pct": pire_jour, "periodes_positives_pct": float((periodes > 0).mean() * 100),
            "taille_ftmo_facteur": facteur, "rendement_mensuel_taille_ftmo_pct": mensuel * facteur,
            "compatible_ftmo_tel_quel": bool(baisse > -0.10 and (pire_jour is None or pire_jour > -5))}

# 15/10, maitres/persistance.py sur 1 174 traders (Ostium, gTrade) : choisis sur la 1re moitié de leur historique
# avec force > 1,5, ils PERDENT ensuite (force -0,3, 37 % encore gagnants : des chanceux) ; avec au moins 200 trades
# et force > 3 (rapportée à la taille), ils RESTENT bons (force +1,3, 65 % encore gagnants, 20 traders).
MIN_TRADES_MAITRE = 200
# 15/10 : le meilleur « maître » gTrade (force 16) fermait ses trades dans la même seconde : un programme qui joue sur
# le retard du prix affiché par la bourse, pas un trader (impossible et interdit chez FTMO). Durée médiane minimale :
DUREE_MEDIANE_MIN_MINUTES = 5.0
FORCE_MAITRE = 3.0


def juger_standard(t: pd.DataFrame, rapporte_a_la_taille: bool = False) -> pd.DataFrame:
    """Juge chaque maître du FORMAT COMMUN (maitres/trades.py), toutes sources : un trade = une décision complète.
    Gain net (frais compris) ; le jumeau prend chaque trade dans l'autre sens -> force = somme / racine(somme des
    carrés). Retenus : au moins 200 trades, force > 3, au plus 3 % de trades liquidés (sinon un joueur, pas un maître).
    `rapporte_a_la_taille` : chaque gain divisé par la taille du trade (un gros trade chanceux ne pèse plus tout ;
    15/10, maitres/persistance.py : c'est ainsi que le talent choisi sur le passé DURE le mieux)."""
    lignes = []
    for maitre, g in t.groupby("maitre"):
        g = g.dropna(subset=["gain"])
        if rapporte_a_la_taille:
            g = g[g["volume"] > 0]
        n = len(g)
        if n == 0:
            continue
        net = g["gain"].astype(float) / (g["volume"].astype(float) if rapporte_a_la_taille else 1.0)
        force = float(net.sum() / np.sqrt((net ** 2).sum())) if (net ** 2).sum() > 0 else 0.0
        gagn, perd = net[net > 0], net[net < 0]
        duree_min = float(((pd.to_datetime(g["fin"]) - pd.to_datetime(g["debut"])).dt.total_seconds() / 60).median())
        liquide = float(g["liquide"].mean() * 100) if "liquide" in g and g["liquide"].notna().any() else 0.0
        hc = g["marche"].isin(["BTCUSD", "ETHUSD"]).map(lambda x: not x) & g["marche"].notna()
        lignes.append({"maitre": maitre, "source": g["source"].iloc[0], "trades": n,
                       "debut": str(g["debut"].min())[:10], "fin": str(g["fin"].max())[:10],
                       "gagnants_pct": float((net > 0).mean() * 100),
                       "gain_moyen_sur_perte_moyenne": float(gagn.mean() / -perd.mean()) if len(gagn) and len(perd) else None,
                       "force": force, "liquides_pct": liquide,
                       "levier_median": float(g["levier"].median()) if "levier" in g else None,
                       "hors_crypto_pct": float(hc.mean() * 100), "marches": g["marche"].value_counts().head(4).to_dict(),
                       "duree_mediane_min": duree_min,
                       "maitre_retenu": bool(n >= MIN_TRADES_MAITRE and liquide <= 3 and force > FORCE_MAITRE
                                             and duree_min >= DUREE_MEDIANE_MIN_MINUTES)})
    return pd.DataFrame(lignes).sort_values("force", ascending=False)


def juger_tous() -> pd.DataFrame:
    ap = {json.loads(l)["adresse"]: json.loads(l) for l in (DOSSIER / "apercu.jsonl").open(encoding="utf-8")}
    lignes = []
    for f in sorted((DOSSIER / "historiques").glob("0x*.csv")):
        a = f.stem
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if not len(df):
            continue
        fc = f.with_suffix(".courbe.json")
        courbe = json.loads(fc.read_text(encoding="utf-8")) if fc.exists() else None
        r = juger(decisions_hyperliquid(df), courbe)
        lignes.append({"adresse": a, **r})
    t = pd.DataFrame(lignes)
    t.to_json(DOSSIER / "verdicts.json", orient="records", force_ascii=False, indent=1)
    return t


if __name__ == "__main__":
    t = juger_tous()
    if len(t) and "force" in t:
        ok = t[(t["prouve"] == True)]
        print(f"{len(t)} traders jugés ; {len(ok)} battent le hasard (force > 3) ; dont hors crypto "
              f"{(ok['hors_crypto_pct'] >= 30).sum()}")
        cols = [c for c in ["adresse", "trades", "gagnants_pct", "gain_moyen_sur_perte_moyenne", "force", "hors_crypto_pct",
                "rendement_mensuel_pct", "pire_baisse_pct", "pire_jour_mois_pct", "rendement_mensuel_taille_ftmo_pct"] if c in t]
        print(t.sort_values("force", ascending=False)[cols].head(25).round(2).to_string())
