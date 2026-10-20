"""Les faits objectifs que voit le trader humain numérique en plus des graphiques (nouvelle école, 14/10/2026).

Comme un trader devant MetaTrader, elle sait :
- quelles séances sont ouvertes (Tokyo, Londres, New York), d'après l'heure locale de chaque place ;
- ce que dit le calendrier économique de MetaTrader (heures justes) pour les devises de chaque marché : dans combien
  d'heures tombe la prochaine annonce IMPORTANTE, depuis combien d'heures la dernière est passée, et combien
  d'annonces importantes tombent dans les 24 prochaines heures.
Seulement l'HEURE des annonces (connue d'avance, publiée par le calendrier), jamais leur résultat : aucune fuite
d'information. Pas de Forex Factory (heures fausses, voir REPRISE §5).
Tous les instants sont ceux de la décision : la clôture de la bougie de 15 minutes (ouverture + 15 min), à l'heure du
serveur (New York + 7 h).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from collapsar.donnees import calendrier as cal
from collapsar.mains.fiches import DEVISES, MIROIR, fiche

N_SEANCES = 3
N_CALENDRIER = 3
SEANCES = (("Asia/Tokyo", 9, 18), ("Europe/London", 8, 17), ("America/New_York", 8, 17))
QUINZE = pd.Timedelta(minutes=15)
HORIZON_H = 48.0                     # au-delà de 48 heures, « loin » (comme un trader qui regarde sa semaine)


def _utc(temps_serveur: pd.DatetimeIndex) -> pd.DatetimeIndex:
    ny = (temps_serveur - pd.Timedelta(hours=7)).tz_localize("America/New_York", ambiguous=True,
                                                             nonexistent="shift_forward")
    return ny.tz_convert("UTC")


def seances(temps_bougies: pd.DatetimeIndex) -> np.ndarray:
    """[T, 3] : 1 si la séance de Tokyo / Londres / New York est ouverte à la clôture de la bougie."""
    utc = _utc(pd.DatetimeIndex(temps_bougies) + QUINZE)
    sortie = np.zeros((len(utc), N_SEANCES), np.float32)
    for k, (zone, debut, fin) in enumerate(SEANCES):
        local = utc.tz_convert(zone)
        heure = local.hour + local.minute / 60
        sortie[:, k] = ((heure >= debut) & (heure < fin) & (local.dayofweek < 5)).astype(np.float32)
    return sortie


def devises(marche: str) -> list[str]:
    """Les devises dont les annonces touchent ce marché (les deux devises d'une paire, sinon sa devise de cotation)."""
    nom = marche[:-len(MIROIR)] if marche.endswith(MIROIR) else marche
    if nom.startswith("MONDE"):                          # marché inventé : ses annonces sont celles de son monde
        return ["MONDE"]
    if len(nom) == 6 and nom[:3] in DEVISES and nom[3:] in DEVISES:
        return [nom[:3], nom[3:]]
    return [fiche(nom).cotation]


def annonces_importantes(source: pd.DataFrame | None = None) -> pd.DataFrame:
    """Les annonces importantes (3 étoiles) du calendrier de MetaTrader : temps (heure serveur, hiver corrigé), devise."""
    d = source if source is not None else cal._lire_mt5(cal.MT5_HISTOIRE)
    d = d[d["importance"] == 3]
    return d[["temps", "devise"]].drop_duplicates().sort_values("temps").reset_index(drop=True)


def calendrier(temps_bougies: pd.DatetimeIndex, marches: list[str],
               annonces: pd.DataFrame | None = None) -> np.ndarray:
    """[T, M, 3] : heures avant la prochaine annonce importante (/48, 1 = loin ou aucune), heures depuis la dernière
    (/48), nombre d'annonces importantes dans les 24 prochaines heures (/10, au plus 1)."""
    annonces = annonces if annonces is not None else annonces_importantes()
    decision = (pd.DatetimeIndex(temps_bougies) + QUINZE).values.astype("datetime64[ns]")
    sortie = np.ones((len(decision), len(marches), N_CALENDRIER), np.float32)
    sortie[..., 2] = 0.0
    une_heure = np.timedelta64(1, "h")
    for j, m in enumerate(marches):
        e = np.sort(annonces.loc[annonces["devise"].isin(devises(m)), "temps"].values.astype("datetime64[ns]"))
        if not len(e):
            continue
        k = np.searchsorted(e, decision, side="left")              # première annonce à l'instant ou après
        a_venir = k < len(e)
        prochaine = e[np.minimum(k, len(e) - 1)]
        h_avant = np.where(a_venir, (prochaine - decision) / une_heure, HORIZON_H)
        passee = k > 0
        derniere = e[np.maximum(k - 1, 0)]
        h_depuis = np.where(passee, (decision - derniere) / une_heure, HORIZON_H)
        n24 = np.searchsorted(e, decision + np.timedelta64(24, "h"), side="left") - k
        sortie[:, j, 0] = np.clip(h_avant, 0, HORIZON_H) / HORIZON_H
        sortie[:, j, 1] = np.clip(h_depuis, 0, HORIZON_H) / HORIZON_H
        sortie[:, j, 2] = np.clip(n24, 0, 10) / 10
    return sortie
