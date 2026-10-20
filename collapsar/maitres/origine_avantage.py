"""D'OÙ VIENT L'AVANTAGE DES MAÎTRES ? (15/10/2026)

Pour chaque trade d'un maître retenu (critère strict, maitres/juge.py), sur nos vrais prix de 15 minutes :
- SENS : ce qu'aurait rapporté son entrée si on était sorti après un temps FIXE (1 h, 4 h, 1 jour, 3 jours),
  en part du prix d'entrée, dans son sens. Si c'est positif, ses entrées « voient » la direction ;
- SORTIE : son vrai résultat (prix de sortie) comparé à une sortie au même endroit mais à un moment tiré au hasard
  entre son entrée et deux fois sa durée. Si son vrai résultat est meilleur, il sait sortir ;
- tout est rapporté à l'agitation du jour du marché (une bougie du jour = 1) pour pouvoir additionner or et euro.
Les maîtres sont choisis sur leur PASSÉ (80 % les plus anciens) ; on mesure sur tout et sur leur futur séparément.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.maitres.origine_avantage
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.maitres.lancer_imitation import _rang, choisir
from collapsar.maitres.trades import lire_tous

HORIZONS = {"1 h": 4, "4 h": 16, "1 jour": 96, "3 jours": 288}


def _prix(marche: str) -> pd.DataFrame:
    d = dm.charger(marche, jusqua=pd.Timestamp("2026-12-31"))
    d = d[["time", "close", "high", "low"]].reset_index(drop=True)
    # agitation du jour : moyenne sur 20 jours de l'écart haut-bas d'une journée, en part du prix
    j = d.set_index("time").resample("1D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    agit = ((j["high"] - j["low"]) / j["close"]).rolling(20, min_periods=5).mean().shift(1)
    d["agitation"] = agit.reindex(d["time"].dt.floor("1D")).to_numpy()
    return d


def mesurer(tr: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    lignes = []
    for marche, g in tr.dropna(subset=["marche"]).groupby("marche"):
        try:
            d = _prix(marche)
        except Exception:
            continue
        temps = pd.DatetimeIndex(d["time"]).values
        c, ag = d["close"].to_numpy(), d["agitation"].to_numpy()
        fins = temps + np.timedelta64(15, "m")
        e = np.searchsorted(fins, pd.DatetimeIndex(pd.to_datetime(g["debut"])).values, side="right") - 1
        s = np.searchsorted(fins, pd.DatetimeIndex(pd.to_datetime(g["fin"])).values, side="right") - 1
        ok = (e >= 0) & (s > e) & (s < len(c) - 300) & np.isfinite(ag[np.clip(e, 0, len(c) - 1)])
        g, e, s = g[ok], e[ok], s[ok]
        sens = g["sens"].to_numpy(float)
        a = ag[e]
        ligne = {"marche": np.full(len(g), marche), "maitre": g["maitre"].to_numpy(), "futur": g["futur"].to_numpy(),
                 "sens": sens,
                 "duree_h": (s - e) / 4.0}
        for nom, h in HORIZONS.items():
            ligne[nom] = sens * (c[e + h] / c[e] - 1) / a
        ligne["vrai"] = sens * (c[s] / c[e] - 1) / a
        hasard = e + (rng.random(len(e)) * 2 * (s - e)).astype(int).clip(1)
        hasard = np.minimum(hasard, len(c) - 1)
        ligne["sortie_au_hasard"] = sens * (c[hasard] / c[e] - 1) / a
        lignes.append(pd.DataFrame(ligne))
    return pd.concat(lignes, ignore_index=True) if lignes else pd.DataFrame()


def resume(m: pd.DataFrame) -> dict:
    r = {"trades": int(len(m))}
    for k in list(HORIZONS) + ["vrai", "sortie_au_hasard"]:
        x = m[k].dropna()
        r[k] = {"moyenne": round(float(x.mean()), 3), "force": round(float(x.mean() / x.std() * np.sqrt(len(x))), 2),
                "positifs_pct": round(float((x > 0).mean() * 100))}
    # LE MOMENT, penchant mis à part : même maître, même marché, même part d'achats et de ventes, mais sens
    # redistribués au hasard entre ses trades (300 fois). Acheter l'or pendant que l'or monte ne compte plus.
    rng = np.random.default_rng(7)
    groupes = [np.flatnonzero(((m["maitre"] == a) & (m["marche"] == b)).to_numpy())
               for a, b in m[["maitre", "marche"]].drop_duplicates().itertuples(index=False)]
    for k in ("1 jour", "3 jours", "vrai"):
        x = m[k].to_numpy()
        ok = np.isfinite(x)
        long_ = x * m["sens"].to_numpy()
        obs = float(np.nanmean(x))
        sim = []
        for _ in range(300):
            s = m["sens"].to_numpy().copy()
            for gi in groupes:
                s[gi] = rng.permutation(s[gi])
            sim.append(float(np.mean((long_ * s)[ok])))
        sim = np.array(sim)
        r[k]["moment_au_dela_du_penchant"] = {"surplus": round(obs - float(sim.mean()), 3),
                                               "force": round((obs - float(sim.mean())) / max(float(sim.std()), 1e-12), 2)}
    gain_sortie = (m["vrai"] - m["sortie_au_hasard"]).dropna()
    r["sortie_contre_hasard"] = {"moyenne": round(float(gain_sortie.mean()), 3),
                                 "force": round(float(gain_sortie.mean() / gain_sortie.std() * np.sqrt(len(gain_sortie))), 2)}
    return r


def main():
    tr = lire_tous()
    poids, _ = choisir(tr)
    tr = tr.assign(futur=_rang(tr) >= 0.8)
    tr = tr[tr["maitre"].isin(poids)]
    m = mesurer(tr, np.random.default_rng(0))
    sortie = {"tous": resume(m), "futur_seulement": resume(m[m["futur"]]),
              "par_marche": {k: resume(g) for k, g in m.groupby("marche") if len(g) >= 50}}
    f = dm.RACINE / "collapsar" / "vie" / "ecole_maitres" / "origine_avantage.json"
    f.write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    for nom in ("tous", "futur_seulement"):
        r = sortie[nom]
        print(f"{nom} ({r['trades']} trades) : " + " | ".join(f"{k} {r[k]['moyenne']:+.3f} (force {r[k]['force']:+.1f})"
                                                            for k in list(HORIZONS) + ["vrai", "sortie_au_hasard"])
              + f" | SORTIE contre hasard {r['sortie_contre_hasard']['moyenne']:+.3f} (force {r['sortie_contre_hasard']['force']:+.1f})")
        print("   MOMENT au-delà du penchant acheteur/vendeur : " + " | ".join(
            f"{k} {r[k]['moment_au_dela_du_penchant']['surplus']:+.3f} (force {r[k]['moment_au_dela_du_penchant']['force']:+.1f})"
            for k in ("1 jour", "3 jours", "vrai")))
    for k, r in sortie["par_marche"].items():
        print(f"  {k:14s} {r['trades']:5d} : 1 jour {r['1 jour']['moyenne']:+.3f} ({r['1 jour']['force']:+.1f}) | vrai "
              f"{r['vrai']['moyenne']:+.3f} ({r['vrai']['force']:+.1f}) | sortie contre hasard "
              f"{r['sortie_contre_hasard']['moyenne']:+.3f} ({r['sortie_contre_hasard']['force']:+.1f})")
    print(f"(enregistré : {f})")


if __name__ == "__main__":
    main()
