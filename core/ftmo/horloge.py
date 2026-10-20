"""L'horloge commune : tous les marchés d'un compte avancent ensemble, bougie de 15 minutes par bougie.

Un marché fermé à un instant (nuit des indices, week-end) garde son dernier prix et n'accepte pas d'ordre.
Pour chaque instant et chaque marché, l'horloge connaît aussi :
- la conversion de la devise de cotation en dollars (le compte est en dollars) ;
- la DERNIÈRE bougie avant une pause de plus de 2 heures (week-end compris) : règle FTMO du compte financé
  Normal, toute position est fermée à cette bougie (choix du chef de projet, 13/10/2026 : toujours, dès l'école) ;
- le jour FTMO (minuit heure de Prague, 1h du serveur la plupart de l'année) pour le mur de -5 % par jour ;
- le passage de minuit du serveur pour les frais de nuit (`nuits(n)`, par marché, 16/10/2026, audit défaut 11) : comme
  chez FTMO (jour_triple de mains/conditions_ftmo.json), la nuit triple est celle du MERCREDI pour les devises, les
  métaux et les obligations, celle du VENDREDI pour les indices, les énergies et les cryptos ; les nuits du samedi et
  du dimanche ne paient rien (le triple les couvre) : 7 nuits payées par semaine. Les marchés inventés (école des
  mille mondes) gardent l'ancienne règle (`nuit` : un minuit franchi = 1 nuit, triple vers le jeudi) ;
Toutes les heures des données sont à l'heure du serveur (New York + 7 h), comme sur MetaTrader.
- le nombre d'heures avant la prochaine fermeture forcée (elle le voit, comme un trader voit l'heure).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from core.ftmo.fiches import MIROIR, Fiche, fiche, taux_vers_dollar

PAUSE_MAX = pd.Timedelta(hours=2)
QUINZE = pd.Timedelta(minutes=15)
MESURE = Path(__file__).with_name("conditions_ftmo.json")
# nuit triple (jour de la semaine, lundi = 0) : FTMO, compte d'essai Swing (15/10/2026), mains/conditions_ftmo.json
TRIPLE_FAMILLE = {"devise": 2, "metal": 2, "obligation": 2, "indice": 4, "energie": 4, "crypto": 4}
REGLES_NUIT = ("ancienne", "mercredi", "vendredi")      # ligne de `nuits_regle`


@lru_cache(maxsize=1)
def _triples_ftmo() -> dict:
    """Nom FTMO -> jour de la nuit triple (lundi = 0), relevé sur le compte FTMO (MetaTrader : dimanche = 0)."""
    try:
        d = json.loads(MESURE.read_text(encoding="utf-8"))["marches"]
    except (FileNotFoundError, KeyError, ValueError):
        return {}
    return {nom: (int(m["jour_triple"]) - 1) % 7 for nom, m in d.items() if m.get("jour_triple") is not None}


def regle_nuit(f: Fiche) -> int:
    """0 = ancienne règle (marchés inventés), 1 = triple le mercredi, 2 = triple le vendredi."""
    nom = f.nom[:-len(MIROIR)] if f.nom.endswith(MIROIR) else f.nom
    jour = _triples_ftmo().get(nom, TRIPLE_FAMILLE.get(f.famille))
    return {2: 1, 4: 2}.get(jour, 0)


def nuits_payees(temps: pd.DatetimeIndex, jour_triple: int) -> np.ndarray:
    """Nombre de nuits payées entre chaque instant et le précédent (minuits du serveur franchis) : la nuit du jour
    `jour_triple` (lundi = 0) compte 3, celles du samedi et du dimanche 0, les autres 1 (7 par semaine)."""
    jour = (temps.normalize() - pd.Timestamp("2000-01-01")).days.to_numpy().astype(np.int64)
    if not len(jour):
        return np.zeros(0)
    d0 = int(jour.min())
    k = np.arange(d0, int(jour.max()) + 1)
    semaine = (k + 5) % 7                                   # 01/01/2000 = samedi (lundi = 0)
    poids = np.where(semaine == jour_triple, 3.0, np.where(semaine >= 5, 0.0, 1.0))
    cumul = np.r_[0.0, np.cumsum(poids)]                    # cumul[i] = nuits des jours d0 .. d0 + i - 1
    n = np.zeros(len(jour))
    n[1:] = cumul[jour[1:] - d0] - cumul[jour[:-1] - d0]
    return n


def heure_prague(temps_serveur: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Heure du serveur (New York + 7 h) -> heure de Prague (où tombe le minuit FTMO)."""
    new_york = (temps_serveur - pd.Timedelta(hours=7)).tz_localize("America/New_York", ambiguous=True,
                                                                     nonexistent="shift_forward")
    return new_york.tz_convert("Europe/Prague")


class Horloge:
    def __init__(self, donnees: dict[str, pd.DataFrame], marches: list[str], appareil="cpu",
                 fiches: dict[str, Fiche] | None = None, nuit_historique: bool = False):
        """`donnees` : bougies de 15 minutes de tous les marchés disponibles (pour les conversions) ;
        `marches` : ceux que ce compte peut trader ; `fiches` : fiches données à la main (marchés inventés de l'école
        des mille mondes), sinon celles des vrais marchés FTMO ; `nuit_historique` (15/10/2026) : frais de nuit de
        CHAQUE ÉPOQUE (écart de taux du moment + marge, mains/nuit.py) au lieu des taux fixes de la fiche."""
        self.appareil = torch.device(appareil)
        self.marches = list(marches)
        fiches = fiches or {}
        self.fiches: list[Fiche] = [fiches[m] if m in fiches else fiche(m) for m in self.marches]
        temps = pd.DatetimeIndex(sorted(set().union(*[set(donnees[m]["time"]) for m in self.marches])))
        self.temps = temps
        T, M = len(temps), len(self.marches)
        o, h, l, c = (np.empty((T, M)) for _ in range(4))
        ouvert = np.zeros((T, M), bool)
        derniere = np.zeros((T, M), bool)
        local = np.full((T, M), -1, np.int64)
        heures_pause = np.zeros((T, M), np.float32)
        fx = np.ones((T, M))
        for j, m in enumerate(self.marches):
            df = donnees[m].set_index("time")
            pos = temps.get_indexer(df.index)
            ouvert[pos, j] = True
            serie_c = pd.Series(np.nan, index=temps)
            serie_c.iloc[pos] = df["close"].to_numpy()
            ferme = serie_c.ffill().bfill().to_numpy()
            for arr, col in ((o, "open"), (h, "high"), (l, "low")):
                arr[:, j] = ferme
                arr[pos, j] = df[col].to_numpy()
            c[:, j] = ferme
            loc = np.full(T, -1, np.int64)
            loc[pos] = np.arange(len(pos))
            local[:, j] = pd.Series(loc).replace(-1, np.nan).ffill().fillna(-1).to_numpy(np.int64)
            # dernière bougie avant une pause de plus de 2 h (après sa fermeture, le marché reste fermé > 2 h)
            t_m = df.index
            pause = np.r_[(t_m[1:] - (t_m[:-1] + QUINZE)) > PAUSE_MAX, True]
            derniere[pos[pause], j] = True
            # heures avant la prochaine fermeture forcée, à chaque instant de l'horloge
            fins = temps[pos[pause]] + QUINZE
            k = np.searchsorted(fins.values, temps.values, side="right")
            k = np.minimum(k, len(fins) - 1)
            heures_pause[:, j] = np.clip((fins.values[k] - temps.values) / np.timedelta64(1, "h"), 0, 48)
            source, inverser = taux_vers_dollar(self.fiches[j].cotation)
            if source is not None:
                if source not in donnees:
                    raise ValueError(f"il faut {source} pour convertir {m} en dollars")
                taux = donnees[source].set_index("time")["close"].reindex(temps, method="ffill").bfill().to_numpy()
                fx[:, j] = 1 / taux if inverser else taux
        # Les données sont à l'HEURE DU SERVEUR (New York + 7 h, comme MetaTrader et FTMO ; vérifié le 13/10/2026 :
        # accord de 98 à 99,9 % avec les bougies du courtier sans aucun décalage). Minuit FTMO = minuit à Prague.
        prague = heure_prague(temps)
        jour = (prague.normalize().tz_localize(None) - pd.Timestamp("2000-01-01")).days.to_numpy()
        # minuit du serveur : frais de nuit quand on le franchit entre deux instants (triples vers le jeudi)
        jour_serveur = (temps.normalize() - pd.Timestamp("2000-01-01")).days.to_numpy()
        nuit = np.zeros(T)
        nuit[1:] = (jour_serveur[1:] != jour_serveur[:-1]).astype(float)
        mercredi = temps.dayofweek.to_numpy() == 3                      # minuit vers jeudi = nuit du mercredi
        nuit[1:] *= np.where(mercredi[1:], 3.0, 1.0)
        dev = self.appareil
        t64 = lambda a: torch.from_numpy(np.ascontiguousarray(a)).to(dev)
        self.o, self.h, self.l, self.c = (t64(a.astype(np.float64)) for a in (o, h, l, c))
        self.ouvert, self.derniere = t64(ouvert), t64(derniere)
        self.fx = t64(fx.astype(np.float64))
        self.jour = t64(jour.astype(np.int64))
        self.nuit = t64(nuit)                   # ancienne règle, commune (gardée : certaines écoles la remplacent)
        # 16/10 : nuits payées PAR MARCHÉ (triple du mercredi ou du vendredi, comme FTMO) : [3, T] + règle [M]
        self.nuits_regle = t64(np.stack([nuit, nuits_payees(temps, 2), nuits_payees(temps, 4)]).astype(np.float64))
        self.regle_nuit = torch.tensor([regle_nuit(f) for f in self.fiches], dtype=torch.int64, device=dev)
        self.local = t64(local)
        self.heures_pause = t64(heures_pause)
        self.demi_ecart = torch.tensor([f.demi_ecart for f in self.fiches], dtype=torch.float64, device=dev)
        self.levier = torch.tensor([f.levier for f in self.fiches], dtype=torch.float64, device=dev)
        vect = lambda attr: torch.tensor([getattr(f, attr) for f in self.fiches], dtype=torch.float64, device=dev)
        self.nuit_achat, self.nuit_vente = vect("nuit_achat"), vect("nuit_vente")         # [M] ou [T, M]
        if nuit_historique:
            from core.ftmo.nuit import taux_nuit
            paires = [taux_nuit(f, temps) for f in self.fiches]
            self.nuit_achat = torch.tensor(np.stack([p[0] for p in paires], 1), dtype=torch.float64, device=dev)
            self.nuit_vente = torch.tensor(np.stack([p[1] for p in paires], 1), dtype=torch.float64, device=dev)
        self.pas_unites, self.pas_dollars, self.min_unites = vect("pas_unites"), vect("pas_dollars"), vect("min_unites")
        self.T, self.M = T, M

    def nuits(self, n: torch.Tensor) -> torch.Tensor:
        """[B, M] : nuits payées par chaque marché en arrivant à l'instant n [B]."""
        return self.nuits_regle[:, n].T[:, self.regle_nuit]

    @property
    def nuit(self) -> torch.Tensor:
        return self._nuit

    @nuit.setter
    def nuit(self, valeur: torch.Tensor) -> None:
        """Une école qui REMPLACE `nuit` après coup (écoles crypto : une nuit chaque jour, jamais triple) impose sa
        règle à tous les marchés, comme avant le 16/10."""
        self._nuit = valeur
        if hasattr(self, "nuits_regle"):
            self.nuits_regle = valeur.reshape(1, -1).expand(len(REGLES_NUIT), -1)
