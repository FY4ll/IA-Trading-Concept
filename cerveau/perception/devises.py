"""N3 — RETOURNEMENT DE LA SEMAINE ENTRE DEVISES (couche perception, compétition 1, 20/10/2026) : chaque devise est
mesurée contre le dollar ; on achète les 2 qui ont le plus baissé la semaine passée et on vend les 2 qui ont le plus
monté, du lundi 02:00 au vendredi 21:00 serveur. Rien n'est appris. Plan : etudes/2026-10-20_competition1/PLAN_FIGE.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from cerveau.perception.calendrier import prix_a_cloture
from cerveau.socle import COLONNES_AVIS, ModulePerception, enregistrer

PAIRES = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD")
H = pd.Timedelta


def devise_contre_dollar(paire: str) -> int:
    """+1 si la paire monte quand la devise monte contre le dollar (EURUSD), -1 sinon (USDJPY)."""
    return -1 if paire.startswith("USD") else 1


class RetournementDevises(ModulePerception):
    nom = "retournement_devises"
    N_CHAQUE_COTE = 2

    def avis(self, b15):
        raise NotImplementedError("module multi-marchés : utiliser avis_multi({paire: bougies})")

    def semaines(self, bougies: dict) -> pd.DataFrame:
        """Rendement de chaque devise contre le dollar, vendredi 21:00 -> vendredi 21:00 serveur (une ligne par
        vendredi de décision)."""
        debut = max(b["time"].min() for b in bougies.values()).normalize()
        fin = min(b["time"].max() for b in bougies.values()).normalize()
        vendredis = pd.date_range(debut, fin, freq="W-FRI") + H(hours=21)
        r = {}
        for p, b in bougies.items():
            px = prix_a_cloture(b, vendredis)
            r[p] = devise_contre_dollar(p) * (px[1:] / px[:-1] - 1)
        return pd.DataFrame(r, index=vendredis[1:])

    def avis_multi(self, bougies: dict) -> pd.DataFrame:
        sem = self.semaines(bougies)
        lignes = []
        k = self.N_CHAQUE_COTE
        for vendredi, r in sem.iterrows():
            if r.isna().any():
                continue
            ordre = r.sort_values()
            entree = vendredi.normalize() + H(days=3, hours=2)              # lundi 02:00
            sortie = vendredi.normalize() + H(days=7, hours=21)             # vendredi suivant 21:00
            for p in ordre.index[:k]:                                        # les plus baissées : achat de la devise
                lignes.append((p, entree, sortie, devise_contre_dollar(p)))
            for p in ordre.index[-k:]:                                       # les plus montées : vente de la devise
                lignes.append((p, entree, sortie, -devise_contre_dollar(p)))
        df = pd.DataFrame(lignes, columns=["marche", "temps", "expire", "sens"])
        for c in COLONNES_AVIS:
            if c not in df:
                df[c] = self.nom if c == "module" else (1.0 if c == "confiance" else np.nan)
        return df[["marche"] + list(COLONNES_AVIS)]


RETOURNEMENT = enregistrer(RetournementDevises())
