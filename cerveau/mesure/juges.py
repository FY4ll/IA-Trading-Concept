"""Les deux JUGES (20/10/2026) : jumeau pile ou face (espérance exacte = (trade + trade inversé) / 2) et jumeau
toujours acheteur. Avantage mois par mois, incertitude = écart type des moyennes mensuelles / racine(nombre de mois)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

SEUIL = 2.0
SEUIL_PRUDENT = math.sqrt(2 * math.log(16))          # 16 comparaisons (4 unités × 2 mesures × 2 juges)


def _avantage(diff: pd.Series, mois: pd.Series) -> tuple[float, float]:
    m = diff.groupby(mois).mean()
    if len(m) < 2:
        return float(diff.mean()) if len(diff) else float("nan"), float("nan")
    return float(diff.mean()), float(m.std(ddof=1) / math.sqrt(len(m)))


def juger(t: pd.DataFrame, mesure: str) -> dict:
    """`mesure` = "a" (le sens seul, en ATR) ou "b" (signal + gestion, en R)."""
    sig, inv, ach = t[f"{mesure}_signal"], t[f"{mesure}_inverse"], t[f"{mesure}_achat"]
    pile = (sig + inv) / 2
    av_p, inc_p = _avantage(sig - pile, t["mois"])
    av_a, inc_a = _avantage(sig - ach, t["mois"])
    mois_span = max(1, (t["heure_entree"].max() - t["heure_entree"].min()).days / 30.44) if len(t) else 1
    gain = float(sig.mean()) if len(t) else float("nan")
    bat_p = bool(inc_p > 0 and av_p > SEUIL * inc_p)
    bat_a = bool(inc_a > 0 and av_a > SEUIL * inc_a)
    return {"trades": int(len(t)), "trades_mois": float(len(t) / mois_span), "achats_pct": float(100 * (t["sens"] > 0).mean()) if len(t) else float("nan"),
            "gagnants_pct": float(100 * (sig > 0).mean()) if len(t) else float("nan"),
            "gain_moyen": gain, "pile_ou_face": float(pile.mean()) if len(t) else float("nan"),
            "toujours_achat": float(ach.mean()) if len(t) else float("nan"),
            "avantage_pile": av_p, "incertitude_pile": inc_p, "avantage_achat": av_a, "incertitude_achat": inc_a,
            "bat_pile": bat_p, "bat_achat": bat_a, "net": bool(bat_p and bat_a and gain > 0),
            "prouve": bool(inc_p > 0 and inc_a > 0 and av_p > SEUIL_PRUDENT * inc_p and av_a > SEUIL_PRUDENT * inc_a
                           and gain > 0),
            "cout_moyen_R": float(t["cout_R"].mean()) if len(t) else float("nan")}
