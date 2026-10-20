"""Mesure des trades du REPLAY MANUEL contre les juges (PROTOCOLE.md, figé le 20/10/2026, avant le 1er trade).

    venv_gpu\\Scripts\\python.exe etudes\\replay_manuel\\mesurer.py [--fichier autre.csv]
Point d'étape à tout moment ; rien n'est réglé dessus.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))

import numpy as np
import pandas as pd

from core import donnees as D
from core.ftmo import frais as F
from core.ftmo.fiches import fiche
from core.ftmo.horloge import nuits_payees
from core.ftmo.nuit import taux_nuit

TOLERANCE_PRIX = 2.0          # $ : écart toléré entre TradingView et nos données
TOLERANCE_MIN = 3             # minutes autour de l'heure notée
TIRAGES = 200


def utc_vers_serveur(t: pd.Series) -> pd.DatetimeIndex:
    """UTC -> heure du serveur (New York + 7 h), été comme hiver."""
    ny = pd.DatetimeIndex(pd.to_datetime(t)).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
    return (ny + pd.Timedelta(hours=7)).as_unit("ns")


def lire(fichier: Path) -> pd.DataFrame:
    df = pd.read_csv(fichier, sep=";", dtype=str).dropna(how="all")
    if df.empty:
        return df
    for c in ("prix_entree", "stop", "objectif", "prix_sortie"):
        df[c] = pd.to_numeric(df[c].str.replace(",", ".", regex=False), errors="coerce")
    df["s"] = df["sens"].str.strip().str.upper().map({"A": 1, "V": -1})
    df["te"] = utc_vers_serveur(df["entree_utc"])
    df["ts"] = utc_vers_serveur(df["sortie_utc"])
    return df


def chemin(m1, ke, ks, s, pe, stop_d, obj_d):
    """Sortie simulée sur nos minutes : stop d'abord dans une même minute, objectif ensuite, sinon à ks (sa sortie)."""
    h, l, c, o = m1["high"], m1["low"], m1["close"], m1["open"]
    stop = pe - s * stop_d
    obj = pe + s * obj_d if np.isfinite(obj_d) else np.nan
    for k in range(ke + 1, ks + 1):
        if (s > 0 and l[k] <= stop) or (s < 0 and h[k] >= stop):
            return stop if not ((s > 0 and o[k] < stop) or (s < 0 and o[k] > stop)) else o[k], k
        if np.isfinite(obj) and ((s > 0 and h[k] >= obj) or (s < 0 and l[k] <= obj)):
            return obj, k
    return c[ks], ks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fichier", default=str(ICI / "replay_trades.csv"))
    a = ap.parse_args()
    df = lire(Path(a.fichier))
    if df.empty:
        print("aucun trade noté pour l'instant")
        return
    sess = pd.read_csv(ICI / "sessions.csv", sep=";", dtype=str).set_index("seance")
    debut = df["te"].min() - pd.Timedelta(days=2)
    fin = df["ts"].max() + pd.Timedelta(days=16)
    m = D.charger_minutes_or(fin.ceil("D"), depuis=debut.floor("D"))
    t = pd.DatetimeIndex(m["time"]).as_unit("ns").asi8
    m1 = {k: m[k].to_numpy(float) for k in ("open", "high", "low", "close")}
    f = fiche("XAUUSD")
    lignes, rejets = [], []
    rng = np.random.default_rng(20261020)
    for i, r in df.iterrows():
        pb = []
        if r["s"] not in (1, -1):
            pb.append("sens")
        if not (np.isfinite(r["stop"]) and (r["prix_entree"] - r["stop"]) * r["s"] > 0):
            pb.append("stop du mauvais côté ou absent")
        ke = int(np.searchsorted(t, r["te"].value))
        ks = int(np.searchsorted(t, r["ts"].value))
        if ke >= len(t) or ks >= len(t) or ks <= ke:
            pb.append("heures hors données ou sortie avant entrée")
        else:
            fen = slice(max(ke - TOLERANCE_MIN, 0), ke + TOLERANCE_MIN + 1)
            if not (m1["low"][fen].min() - TOLERANCE_PRIX <= r["prix_entree"] <= m1["high"][fen].max() + TOLERANCE_PRIX):
                pb.append("prix d'entrée absent de nos données à cette minute")
        if pb:
            rejets.append((r["seance"], r["entree_utc"], "; ".join(pb)))
            continue
        s, pe = int(r["s"]), float(r["prix_entree"])
        d = abs(pe - r["stop"])
        od = abs(r["objectif"] - pe) if np.isfinite(r["objectif"]) else np.nan
        frais_R = float(F.frais("XAUUSD", np.array([pe]))[0]) * pe / d
        nuits = float(nuits_payees(pd.DatetimeIndex([r["te"], r["ts"]]), 2)[1])
        ach, ven = taux_nuit(f, pd.DatetimeIndex([r["te"]]))
        nuit_R = lambda sens: nuits * pe * (ach[0] if sens > 0 else ven[0]) / 360 / d
        note = s * (r["prix_sortie"] - pe) / d - frais_R - nuit_R(s)
        px, _ = chemin(m1, ke, ks, s, pe, d, od)
        sim = s * (px - pe) / d - frais_R - nuit_R(s)
        px_i, _ = chemin(m1, ke, ks, -s, pe, d, od)
        inv = -s * (px_i - pe) / d - frais_R - nuit_R(-s)
        achat = sim if s > 0 else inv
        # hasard d'horaire : même trade (sens, stop, objectif, durée) à une minute tirée dans les 10 jours de la séance
        dep = pd.Timestamp(sess.loc[r["seance"], "date_depart"]) if r["seance"] in sess.index else r["te"].normalize()
        lo = int(np.searchsorted(t, utc_vers_serveur(pd.Series([dep]))[0].value))
        hi = int(np.searchsorted(t, utc_vers_serveur(pd.Series([dep + pd.Timedelta(days=14)]))[0].value)) - (ks - ke) - 1
        hasard = []
        for k0 in rng.integers(lo, max(lo + 1, hi), size=TIRAGES):
            p0 = m1["close"][k0]
            px_h, _ = chemin(m1, k0, k0 + (ks - ke), s, p0, d, od)
            hasard.append(s * (px_h - p0) / d - frais_R - nuit_R(s))
        lignes.append({"seance": r["seance"], "sens": s, "R_note": note, "R_sim": sim, "pile": (sim + inv) / 2,
                       "achat": achat, "hasard": float(np.mean(hasard)), "frais_R": frais_R})
    res = pd.DataFrame(lignes)
    print(f"trades notés : {len(df)} ; retenus : {len(res)} ; rejetés : {len(rejets)}")
    for x in rejets:
        print("   rejet :", x)
    if res.empty:
        return
    def av(col):
        dif = (res["R_sim"] - res[col]).groupby(res["seance"]).mean()
        inc = dif.std(ddof=1) / math.sqrt(len(dif)) if len(dif) > 1 else float("nan")
        return float((res["R_sim"] - res[col]).mean()), float(inc)
    print(f"R moyen après frais : noté {res['R_note'].mean():+.3f} ; rejoué sur nos données {res['R_sim'].mean():+.3f} ; "
          f"gagnants {100 * (res['R_sim'] > 0).mean():.0f} % ; frais moyens {res['frais_R'].mean():.3f} R")
    for col, nom in (("pile", "pile ou face"), ("achat", "acheteur"), ("hasard", "hasard d'horaire")):
        x, e = av(col)
        print(f"   contre {nom} : {x:+.3f} ± {e:.3f} R")
    ok = (len(res) >= 100 and res["R_sim"].mean() > 0 and av("pile")[0] > 2 * av("pile")[1]
          and av("achat")[0] > 0 and av("hasard")[0] > 0)
    print("VERDICT :", "avantage mesurable" if ok else ("pas encore 100 trades" if len(res) < 100 else "pas d'avantage mesurable"))


if __name__ == "__main__":
    main()
