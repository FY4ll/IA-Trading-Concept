"""Les exercices de l'étage « regarder » (les racines de l'arbre).

À la clôture d'une bougie de 15 minutes, on lui demande, pour 1 h, 4 h, 1 jour et 1 semaine :
- le SENS : ça va monter ou baisser ?
- l'AMPLEUR : de combien (en tailles de bougies habituelles) ?
- l'AGITATION : quelle distance entre le plus haut et le plus bas d'ici là ?
La correction est la suite réelle du graphique. Personne ne lui donne de méthode.

ORGANISATION DU 13/10/2026 après-midi (validée par le chef de projet, après l'expérience « piste A ») :
- les racines apprennent sur 2010 -> 2019 (10 ans là où l'historique existe) ;
- elles sont notées sur 2020 -> 2022 : 3 ANS jamais appris (avant : 5 mois, trop court -> la cime était choisie
  presque au hasard ; « répondre toujours pareil » y battait même les branches à 1 semaine) ;
- l'école apprend sur ces mêmes 2020-2022 (jamais appris des racines) ; le juge : 2023 -> 09/2025 ; les 12 mois
  cachés restent cachés. Un écart de 35 jours sépare apprentissage et contrôle : aucune réponse ne déborde.
Expérience qui a décidé : même cerveau neuf, 25 min, noté sur 2020-2022 : 2 ans d'historique = 50,2 %, 10 ans = 50,9 %.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

from collapsar.yeux.graphique import Graphique

# 13/10 : + « 1 mois » (2 100 bougies) : la tendance de fond est la seule source d'avantage jamais mesurée dans tout
# le projet (AUREX, repère multi-marchés) ; les yeux voient 64 bougies mensuelles mais on ne posait jamais la question
HORIZONS = {"1 h": 4, "4 h": 16, "1 jour": 96, "1 semaine": 480, "1 mois": 2100}
# Rappel (13/10) : les racines apprennent PAR CŒUR leurs années (97-99 % à 1 jour / 1 semaine) : l'école ne doit
# jamais s'entraîner sur les années apprises par les racines (sinon ses yeux « voient l'avenir » : casino).
# 13/10 soir (« donne-lui tout ») : les racines apprennent sur TOUT l'historique disponible avant 2020, y compris les
# années en bougies d'1 heure (Dukascopy, dès ~1999-2004 selon les marchés)
DEBUT_RACINES = pd.Timestamp("1990-01-01")
DEBUT_CONTROLE = pd.Timestamp("2020-02-05")          # apprentissage jusqu'à fin 2019 (+ 35 jours d'écart)
# Poids de chaque horizon dans l'apprentissage. 13/10 midi : le « 1 mois » n'a montré AUCUN avantage sur 2023-2025
# (test de vérité : ~0 avant frais) et faisait baisser les horizons courts (52,3 -> 51,5 %) : il n'apprend plus
# (sa sortie reste en place, sans effet ; réessayer plus tard avec plus d'années d'historique).
POIDS_HORIZONS = {"1 mois": 0.0}
ECART = pd.Timedelta(days=35)          # plus long que le plus long horizon : aucune réponse ne déborde
N_CONTROLE = 300_000                   # tirés sur 3 ans, tous marchés


class Exercices:
    def __init__(self, g: Graphique, debut_controle: pd.Timestamp = DEBUT_CONTROLE, graine: int = 0,
                 debut_apprentissage: pd.Timestamp = DEBUT_RACINES):
        self.g = g
        n, nh = g.n, len(HORIZONS)
        lc = g.lc15.cpu().numpy().astype(np.float64)
        lh = g.lh15.cpu().numpy().astype(np.float64)
        ll = g.ll15.cpu().numpy().astype(np.float64)
        sens = np.zeros((n, nh), np.float32)
        ampleur = np.zeros((n, nh), np.float32)
        agitation = np.zeros((n, nh), np.float32)
        valide = np.zeros((n, nh), bool)
        utilisable = np.zeros(n, bool)
        # chaque marché = [années en bougies d'1 heure] puis [bougies de 15 minutes] : les réponses se calculent dans
        # le TEMPS (1 h, 4 h...), donc en nombre de bougies propre à chaque morceau, sans jamais enjamber la jonction
        segments = []
        for m, nom in enumerate(g.noms):
            a, b = int(g.debut_marche[m]), int(g.debut_marche[m + 1])
            nh1 = int(getattr(g, "n_h1", {}).get(nom, 0))
            if nh1:
                segments.append((a, a + nh1, 4))                 # 1 bougie d'1 h = 4 bougies de 15 min
            segments.append((a + nh1, b, 1))
        for a, b, div in segments:
            c, h, l = lc[a:b], lh[a:b], ll[a:b]
            taille = pd.Series(h - l).rolling(64, min_periods=16).mean().to_numpy()
            utilisable[a:b] = np.isfinite(taille) & (taille > 0)
            for j, pas15 in enumerate(HORIZONS.values()):
                pas = max(1, pas15 // div)
                if len(c) <= pas:
                    continue
                r = np.full(len(c), np.nan)
                r[:-pas] = c[pas:] - c[:-pas]
                haut = pd.Series(h).rolling(pas).max().shift(-pas).to_numpy()
                bas = pd.Series(l).rolling(pas).min().shift(-pas).to_numpy()
                norme = taille * np.sqrt(pas)
                ok = np.isfinite(r) & np.isfinite(norme) & (norme > 0) & np.isfinite(haut)
                with np.errstate(divide="ignore", invalid="ignore"):
                    amp = np.clip(r / norme, -5, 5)
                    agi = np.clip(np.log(np.clip((haut - bas) / norme, 1e-3, None)), -5, 3)
                sens[a:b, j] = np.where(ok, r > 0, 0)
                ampleur[a:b, j] = np.where(ok, amp, 0)
                agitation[a:b, j] = np.where(ok, agi, 0)
                valide[a:b, j] = ok & (r != 0)
        t = pd.DatetimeIndex(g.temps)
        apprend = utilisable & (t >= debut_apprentissage) & (t < debut_controle - ECART) & valide[:, 0]
        controle = utilisable & (t >= debut_controle) & valide.all(1)
        dev = g.appareil
        self.poids_horizons = torch.tensor([POIDS_HORIZONS.get(h, 1.0) for h in HORIZONS], device=dev)
        self.sens = torch.from_numpy(sens).to(dev)
        self.ampleur = torch.from_numpy(ampleur).to(dev)
        self.agitation = torch.from_numpy(agitation).to(dev)
        self.valide = torch.from_numpy(valide).to(dev)
        self.idx_apprend = torch.from_numpy(np.flatnonzero(apprend)).to(dev)
        rng = np.random.default_rng(graine)
        ctrl = np.flatnonzero(controle)
        if len(ctrl) > N_CONTROLE:
            ctrl = np.sort(rng.choice(ctrl, N_CONTROLE, replace=False))
        self.idx_controle = torch.from_numpy(ctrl).to(dev)

    def perte(self, cerveau, idx: torch.Tensor, miroir: float = 0.0) -> torch.Tensor:
        """`miroir` : part des exercices montrés RETOURNÉS (graphique à l'envers, question retournée) : elle ne peut
        plus retenir « à telle date, ça montait », elle doit lire la forme (13/10 : les racines apprenaient par cœur)."""
        f, x = self.g.voir(idx)
        sens, ampleur = self.sens[idx], self.ampleur[idx]
        if miroir > 0:
            retourne = torch.rand(len(idx), device=f.device) < miroir
            r = retourne[:, None, None, None]
            o, h, l, c = f[..., 0], f[..., 1], f[..., 2], f[..., 3]
            inv = torch.stack([-o, -l, -h, -c], -1)
            f = torch.cat([torch.where(r, inv, f[..., :4]), f[..., 4:]], -1)
            sens = torch.where(retourne[:, None], 1 - sens, sens)
            ampleur = torch.where(retourne[:, None], -ampleur, ampleur)
        p_sens, p_amp, p_agi = cerveau(f, x)
        v = self.valide[idx].float() * self.poids_horizons
        nb = v.sum().clamp(min=1)
        l_sens = (F.binary_cross_entropy_with_logits(p_sens, sens, reduction="none") * v).sum() / nb
        l_amp = (F.huber_loss(p_amp, ampleur, reduction="none") * v).sum() / nb
        l_agi = (F.mse_loss(p_agi, self.agitation[idx], reduction="none") * v).sum() / nb
        return l_sens + 0.5 * l_amp + 0.5 * l_agi

    def entrainer(self, cerveau, optimiseur, minutes: float, lot: int, generateur: torch.Generator,
                  miroir: float = 0.0) -> dict:
        """Apprend pendant `minutes`. Rend le nombre d'exercices faits et la perte moyenne."""
        cerveau.train()
        fin = time.time() + minutes * 60
        pas, somme = 0, 0.0
        n = len(self.idx_apprend)
        while time.time() < fin:
            choix = torch.randint(0, n, (lot,), generator=generateur, device="cpu").to(self.g.appareil)
            perte = self.perte(cerveau, self.idx_apprend[choix], miroir)
            optimiseur.zero_grad(set_to_none=True)
            perte.backward()
            torch.nn.utils.clip_grad_norm_(cerveau.parameters(), 1.0)
            optimiseur.step()
            pas += 1
            somme += float(perte.detach())
        return {"exercices": pas * lot, "perte": somme / max(pas, 1)}

    @torch.no_grad()
    def controler(self, cerveau, lot: int = 2048) -> dict:
        """Bonnes réponses sur les 6 mois de contrôle, en %, par horizon.
        - bonnes : % de sens bien devinés ;
        - ponderees : % de l'ampleur des mouvements bien devinée (un gros mouvement compte plus qu'un petit :
          c'est ce qui ressemble à de l'argent) ;
        - sure : % de bonnes réponses sur les 10 % de cas où elle est la plus sûre d'elle ;
        - meme_reponse : ce que ferait quelqu'un qui répond toujours la même chose (le repère à battre)."""
        cerveau.eval()
        idx_all = self.idx_controle
        logits = []
        for d in range(0, len(idx_all), lot):
            f, x = self.g.voir(idx_all[d:d + lot])
            logits.append(cerveau(f, x)[0])
        cerveau.train()
        p = torch.cat(logits)
        vrai = self.sens[idx_all]
        poids = self.ampleur[idx_all].abs()
        juste = ((p > 0).float() == vrai).float()
        res = {}
        for j, nom in enumerate(HORIZONS):
            k = max(1, len(p) // 10)
            sure = torch.topk(p[:, j].abs(), k).indices
            hausse = vrai[:, j].mean()
            res[nom] = {"bonnes": float(juste[:, j].mean() * 100),
                        "ponderees": float((juste[:, j] * poids[:, j]).sum() / poids[:, j].sum().clamp(min=1e-9) * 100),
                        "sure": float(juste[sure, j].mean() * 100),
                        "meme_reponse": float(torch.maximum(hausse, 1 - hausse) * 100)}
        # la note qui sert à CHOISIR (sève, cime, coupes) n'inclut pas « 1 mois » : sur 6 mois de contrôle, ses
        # réponses se recouvrent tant qu'elle est trop bruitée (~±3 points) ; elle est suivie à part
        choix = [n for n in HORIZONS if n != "1 mois"]
        res["score"] = float(np.mean([res[n]["ponderees"] for n in choix]))
        res["bonnes"] = float(np.mean([res[n]["bonnes"] for n in choix]))
        if "1 mois" in HORIZONS:
            res["score_mois"] = res["1 mois"]["ponderees"]
        return res
