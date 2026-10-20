"""Ses yeux : pour chaque échelle (15 min -> mois), les 64 dernières bougies TERMINÉES, cadrées comme MT5 cadre
l'écran (le prix actuel au centre, la hauteur de l'écran = la taille moyenne des bougies affichées).

Aucun indicateur tout fait : seulement ouverture, plus haut, plus bas, clôture, volume, et un repère « bougie
présente » (au début de l'historique, l'écran n'est pas encore plein). En plus : la taille réelle des bougies de chaque
échelle (comme on lit l'axe des prix) et l'heure / le jour de la semaine.

TOUT L'HISTORIQUE (13/10/2026, demande du chef de projet : « donne-lui tout ») : avant le début des bougies de
15 minutes (~2010), on ajoute les bougies HORAIRES (Dukascopy, jusqu'à ~1999-2004) : sur ces années-là, elle voit les
échelles 1 h -> mois et sa case « 15 minutes » est vide (elle le sait : bougie présente = 0). Chaque ligne de base est
donc soit une bougie de 15 minutes, soit une bougie d'une heure (`pas` en minutes) ; elle décide à sa clôture.

Tout est rangé sur la carte graphique ; une fenêtre se fabrique au moment où elle est regardée (rien n'est recopié
64 fois en mémoire).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from collapsar.donnees import marches as dm

LARGEUR = 64                       # bougies par échelle, comme la largeur d'un écran
N_TRAITS = 6                       # ouverture, haut, bas, clôture, volume, bougie présente
N_EXTRA = len(dm.ECHELLES) + 4     # taille des bougies par échelle + heure et jour (sinus / cosinus)


class Graphique:
    def __init__(self, donnees: dict[str, pd.DataFrame], appareil: str | torch.device = "cpu",
                 horaires: dict[str, pd.DataFrame] | None = None):
        """`donnees` : bougies de 15 minutes ; `horaires` (facultatif) : bougies d'une heure d'AVANT les 15 minutes."""
        self.appareil = torch.device(appareil)
        self.noms = list(donnees)
        horaires = horaires or {}
        temps, marche, debut_marche, pas_base, n_h1 = [], [], [], [], {}
        base_prix = {"lc": [], "lh": [], "ll": [], "lo": []}
        par_echelle = {e: {"lo": [], "lh": [], "ll": [], "lc": [], "lv": [], "dernier": [], "depart": []}
                       for e in dm.ECHELLES}
        n = 0
        for m, (nom, df15) in enumerate(donnees.items()):
            h1 = horaires.get(nom)
            if h1 is not None and len(h1) and len(df15):
                h1 = h1[h1["time"] < df15["time"].iloc[0]]
            if h1 is None or not len(h1):
                h1 = df15.iloc[:0]
            base = pd.concat([h1, df15], ignore_index=True)
            n_h1[nom] = len(h1)
            t = base["time"].values.astype("datetime64[ns]")
            pas = np.r_[np.full(len(h1), 60), np.full(len(df15), 15)].astype(np.int16)
            decision = t + pas.astype("timedelta64[m]")
            ref = float(base["close"].iloc[0])
            for cle, k in (("lc", "close"), ("lh", "high"), ("ll", "low"), ("lo", "open")):
                base_prix[cle].append(np.log(base[k].to_numpy(np.float64) / ref).astype(np.float32))
            for e in dm.ECHELLES:
                ech = dm.echelle(df15 if e == "15 min" else base, e)
                p = par_echelle[e]
                decalage = sum(len(x) for x in p["lc"])
                for k, cle in (("open", "lo"), ("high", "lh"), ("low", "ll"), ("close", "lc")):
                    p[cle].append(np.log(ech[k] / ref).astype(np.float32))
                p["lv"].append(np.log1p(np.maximum(ech["volume"], 0)).astype(np.float32))
                d = dm.dernieres_terminees(t, ech, decision)
                p["dernier"].append(np.where(d >= 0, d + decalage, -1).astype(np.int32))
                p["depart"].append(np.full(len(t), decalage, np.int32))
            temps.append(t)
            marche.append(np.full(len(t), m, np.int16))
            pas_base.append(pas)
            debut_marche.append(n)
            n += len(t)
        self.temps = np.concatenate(temps)
        self.marche = np.concatenate(marche)
        self.pas = np.concatenate(pas_base)                              # minutes par ligne : 15 ou 60
        self.n_h1 = n_h1                                                 # lignes horaires en tête de chaque marché
        self.debut_marche = np.array(debut_marche + [n], np.int64)       # bornes de chaque marché (indices de base)
        self.n = n
        dev = self.appareil
        self.ech = []
        for e in dm.ECHELLES:
            p = par_echelle[e]
            self.ech.append({k: torch.from_numpy(np.concatenate(p[k])).to(dev)
                             for k in ("lo", "lh", "ll", "lc", "lv", "dernier", "depart")})
        # prix de chaque ligne de base (pour le centre de l'écran et les réponses des exercices ; l'ouverture sert au
        # chemin du prix de la vision du trader : un stop sauté par un trou de cotation se paie au prix d'ouverture)
        self.lc15, self.lh15, self.ll15, self.lo15 = (torch.from_numpy(np.concatenate(base_prix[k])).to(dev)
                                                      for k in ("lc", "lh", "ll", "lo"))
        decision = pd.DatetimeIndex(self.temps + self.pas.astype("timedelta64[m]"))
        heure = (decision.hour + decision.minute / 60).to_numpy(np.float32)
        jour = decision.dayofweek.to_numpy(np.float32)
        cal = np.stack([np.sin(2 * np.pi * heure / 24), np.cos(2 * np.pi * heure / 24),
                        np.sin(2 * np.pi * jour / 7), np.cos(2 * np.pi * jour / 7)], 1)
        self.calendrier = torch.from_numpy(cal.astype(np.float32)).to(dev)
        self._decal = torch.arange(-(LARGEUR - 1), 1, device=dev)

    def voir(self, idx: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Ce qu'elle voit à la clôture des lignes de base `idx`.
        Rend (fenetres [B, échelles, 64, 6], extra [B, N_EXTRA])."""
        idx = idx.to(self.appareil).long()
        actuel = self.lc15[idx]                                         # le prix actuel (en log) = centre de l'écran
        fenetres, tailles = [], []
        for ech in self.ech:
            dernier = ech["dernier"][idx].long()
            pos = dernier[:, None] + self._decal[None, :]               # les 64 dernières bougies terminées
            present = (pos >= ech["depart"][idx].long()[:, None]) & (dernier[:, None] >= 0)
            pos = pos.clamp(min=0)
            o, h, l, c = (ech[k][pos] for k in ("lo", "lh", "ll", "lc"))
            v = ech["lv"][pos]
            pf = present.float()
            nb = pf.sum(1).clamp(min=1)
            taille = ((h - l) * pf).sum(1) / nb                         # hauteur de l'écran = taille moyenne
            taille = taille.clamp(min=1e-6)
            centre = actuel[:, None]
            prix = [((x - centre) / taille[:, None]).clamp(-30, 30) * pf for x in (o, h, l, c)]
            vmoy = (v * pf).sum(1, keepdim=True) / nb[:, None]
            vol = ((v - vmoy) * pf).clamp(-10, 10)
            fenetres.append(torch.stack(prix + [vol, pf], -1))
            vide = pf.sum(1) == 0
            tailles.append(torch.where(vide, torch.zeros_like(taille), (torch.log(taille) + 6) / 3))
        extra = torch.cat([torch.stack(tailles, 1), self.calendrier[idx]], 1)
        return torch.stack(fenetres, 1), extra
