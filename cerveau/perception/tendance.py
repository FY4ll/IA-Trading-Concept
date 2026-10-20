"""TENDANCE DE FOND (couche perception, 20/10/2026) : sens = signe du rendement sur N mois, à la clôture de chaque jour.
Rien n'est appris. Une instance par N (1, 3, 6, 12 mois). Plan figé : etudes/2026-10-20_couche1_tendance/PLAN_FIGE.md.
Fonctionne sur n'importe quel marché (bougies de 15 min).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from cerveau.socle import COLONNES_AVIS, ModulePerception, enregistrer
from core import donnees as D

FENETRE_VOL = 60          # rendements journaliers pour la volatilité
ATR_JOURS = 20
STOP_ATR = 3.0


def atr_n(h, l, c, n):
    tr = np.maximum.reduce([h - l, np.abs(h - np.r_[c[0], c[:-1]]), np.abs(l - np.r_[c[0], c[:-1]])])
    return pd.Series(tr).rolling(n, min_periods=n).mean().to_numpy()


class TendanceFond(ModulePerception):
    def __init__(self, mois: int):
        self.mois = mois
        self.nom = f"tendance_{mois}m"

    def jours(self, bougies15: pd.DataFrame) -> pd.DataFrame:
        """Bougies journalières (jour du serveur) avec, à chaque clôture : sens, rendement sur N mois, volatilité
        journalière (60 jours), ATR 20 jours. Tout est connu à la clôture du jour."""
        b = D.echelle(bougies15, "jour")
        j = pd.DataFrame({"debut": pd.to_datetime(b["debut"]), "fin": pd.to_datetime(b["fin"]), "open": b["open"],
                          "high": b["high"], "low": b["low"], "close": b["close"]})
        ref_date = j["debut"] - pd.DateOffset(months=self.mois)
        k = np.searchsorted(j["debut"].to_numpy(), ref_date.to_numpy(), side="right") - 1
        ok = k >= 0
        ref = np.where(ok, j["close"].to_numpy()[np.clip(k, 0, None)], np.nan)
        j["rendement"] = j["close"] / ref - 1
        j["sens"] = np.sign(j["rendement"]).fillna(0).astype(int)
        r = np.log(j["close"]).diff()
        j["vol_jour"] = r.rolling(FENETRE_VOL, min_periods=FENETRE_VOL).std()
        j["atr"] = atr_n(j["high"].to_numpy(), j["low"].to_numpy(), j["close"].to_numpy(), ATR_JOURS)
        jours_n = max(1.0, 21.0 * self.mois)
        j["confiance"] = np.clip((j["rendement"].abs() / (j["vol_jour"] * np.sqrt(jours_n))) / 2, 0, 1)
        return j

    def avis(self, bougies15: pd.DataFrame) -> pd.DataFrame:
        j = self.jours(bougies15)
        j = j[(j["sens"] != 0) & j["vol_jour"].notna()]
        return pd.DataFrame({
            "module": self.nom, "temps": j["fin"], "expire": j["fin"] + pd.Timedelta(days=1), "sens": j["sens"],
            "confiance": j["confiance"], "zone_haut": np.nan, "zone_bas": np.nan, "entree": np.nan,
            "stop": j["close"] - j["sens"] * STOP_ATR * j["atr"], "objectif": np.nan, "atr": j["atr"],
        })[list(COLONNES_AVIS)].reset_index(drop=True)


TENDANCES = {n: enregistrer(TendanceFond(n)) for n in (1, 3, 6, 12)}
