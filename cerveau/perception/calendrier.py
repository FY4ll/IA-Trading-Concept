"""Hypothèses d'HORAIRE et de CALENDRIER (couche perception, compétition 1 du 20/10/2026) : règles fixes, rien n'est
appris. Chaque module émet ses avis comme des FENÊTRES : `temps` = entrée, `expire` = sortie, `sens`.
Heures du serveur MetaTrader (New York + 7 h). Plan figé : etudes/2026-10-20_competition1/PLAN_FIGE.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from cerveau.socle import COLONNES_AVIS, ModulePerception, enregistrer

H = pd.Timedelta


def _avis(nom: str, entrees, sorties, sens) -> pd.DataFrame:
    n = len(entrees)
    return pd.DataFrame({"module": nom, "temps": pd.to_datetime(list(entrees)), "expire": pd.to_datetime(list(sorties)),
                         "sens": np.asarray(sens, int), "confiance": 1.0, "zone_haut": np.nan, "zone_bas": np.nan,
                         "entree": np.nan, "stop": np.nan, "objectif": np.nan, "atr": np.nan})[list(COLONNES_AVIS)] \
        if n else pd.DataFrame(columns=COLONNES_AVIS)


def jours_de_bourse(b15: pd.DataFrame) -> pd.DatetimeIndex:
    """Jours du serveur avec des cotations entre 16:30 et 23:00 (séance de New York)."""
    t = pd.DatetimeIndex(b15["time"])
    h = t - t.normalize()
    m = (h >= H(hours=16, minutes=30)) & (h < H(hours=23))
    return pd.DatetimeIndex(sorted(set(t[m].normalize())))


def prix_a(b15: pd.DataFrame, quand) -> np.ndarray:
    """Prix d'ouverture de la 1re bougie qui commence à `quand` ou après (NaN au-delà des données)."""
    t = b15["time"].to_numpy("datetime64[ns]")
    k = np.searchsorted(t, pd.DatetimeIndex(quand).as_unit("ns").to_numpy(), side="left")
    o = b15["open"].to_numpy(float)
    return np.where(k < len(o), o[np.minimum(k, len(o) - 1)], np.nan)


class SeanceAsie(ModulePerception):
    """H1 : achat de 01:00 à 09:00 serveur (18:00 -> 02:00 New York), chaque jour avec des cotations."""
    nom = "seance_asie"

    def avis(self, b15):
        t = pd.DatetimeIndex(b15["time"])
        h = t - t.normalize()
        jours = pd.DatetimeIndex(sorted(set(t[(h >= H(hours=1)) & (h < H(hours=9))].normalize())))
        return _avis(self.nom, jours + H(hours=1), jours + H(hours=9), np.ones(len(jours)))


class NuitIndice(ModulePerception):
    """H2 : achat de la clôture américaine (23:00 serveur) à l'ouverture suivante (16:30 serveur)."""
    nom = "nuit_indice"

    def avis(self, b15):
        j = jours_de_bourse(b15)
        return _avis(self.nom, j[:-1] + H(hours=23), j[1:] + H(hours=16, minutes=30), np.ones(len(j) - 1))


class TournantDuMois(ModulePerception):
    """H3 : achat à 23:00 serveur de l'avant-dernier jour de bourse du mois -> 23:00 du 3e jour de bourse suivant."""
    nom = "tournant_du_mois"

    def avis(self, b15):
        j = jours_de_bourse(b15)
        s = pd.Series(j, index=j)
        par_mois = [g for _, g in s.groupby(j.to_period("M"))]
        e, x = [], []
        for a, b in zip(par_mois[:-1], par_mois[1:]):
            if len(a) >= 2 and len(b) >= 3:
                e.append(a.iloc[-2] + H(hours=23))
                x.append(b.iloc[2] + H(hours=23))
        return _avis(self.nom, e, x, np.ones(len(e)))


class ElanJournee(ModulePerception):
    """H4 : à 22:30 serveur, sens = signe du rendement veille 23:00 -> jour 17:00 ; position 22:30 -> 23:00."""
    nom = "elan_journee"

    def avis(self, b15):
        j = jours_de_bourse(b15)
        avant = prix_a_cloture(b15, j[:-1] + H(hours=23))
        matin = prix_a_cloture(b15, j[1:] + H(hours=17))
        r = matin / avant - 1
        ok = np.isfinite(r) & (r != 0)
        jours = j[1:][ok]
        return _avis(self.nom, jours + H(hours=22, minutes=30), jours + H(hours=23), np.sign(r[ok]))


class TrouOuverture(ModulePerception):
    """N2 : à 16:30 serveur (09:30 NY), trou = prix 16:30 / prix de la veille 23:00 - 1 ; si |trou| >= 0,25 × écart type
    journalier (60 rendements journaliers jusqu'à la veille), position de sens OPPOSÉ de 16:30 à 23:00 serveur."""
    nom = "trou_ouverture"
    SEUIL = 0.25

    def avis(self, b15):
        j = jours_de_bourse(b15)
        veille = prix_a_cloture(b15, j[:-1] + H(hours=23))
        ouverture = prix_a(b15, j[1:] + H(hours=16, minutes=30))
        trou = ouverture / veille - 1
        cl = pd.Series(prix_a_cloture(b15, j + H(hours=23)), index=j).dropna()
        # écart type des 60 derniers rendements journaliers DISPONIBLES, connu la veille (un prix manquant ne vide pas
        # la fenêtre)
        vol = np.log(cl).diff().rolling(60, min_periods=60).std().shift(1).reindex(j).ffill().to_numpy()[1:]
        ok = np.isfinite(trou) & np.isfinite(vol) & (np.abs(trou) >= self.SEUIL * vol) & (trou != 0)
        jours = j[1:][ok]
        return _avis(self.nom, jours + H(hours=16, minutes=30), jours + H(hours=23), -np.sign(trou[ok]))


def prix_a_cloture(b15: pd.DataFrame, quand) -> np.ndarray:
    """Prix À l'instant (ouverture de la bougie qui commence dans les 30 min, sinon clôture de la bougie qui finit à
    l'instant) ; NaN sinon. Même lecture que cerveau.mesure.fenetres.Marche.instants."""
    t = b15["time"].to_numpy("datetime64[ns]").astype(np.int64)
    x = pd.DatetimeIndex(quand).as_unit("ns").asi8
    k = np.searchsorted(t, x, side="left")
    n = len(t)
    kc = np.minimum(k, n - 1)
    o, c = b15["open"].to_numpy(float), b15["close"].to_numpy(float)
    ouvre = (k < n) & (t[kc] - x <= 30 * 60 * 10**9)
    kp = np.maximum(k - 1, 0)
    finit = (k > 0) & (t[kp] + 15 * 60 * 10**9 == x)
    return np.where(ouvre, o[kc], np.where(finit, c[kp], np.nan))


HYPOTHESES = {m.nom: enregistrer(m) for m in (SeanceAsie(), NuitIndice(), TournantDuMois(), ElanJournee(),
                                                TrouOuverture())}
