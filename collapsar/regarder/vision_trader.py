"""La vision du trader (14/10/2026, demande du chef de projet : « pas de menu, il doit pouvoir mettre un stop de
1 500 sur un coup de folie s'il le juge bon »).

On ne demande plus « ça monte ou ça descend ? » (pile ou face : ~51 %) mais, comme un trader devant MT5 :
« CE coup-là — tel sens, stop à telle distance, objectif à telle distance — qu'est-ce qu'il rapporte ? ».
- Aucun menu : à chaque exercice, des coups sont tirés AU HASARD sur toute l'étendue possible (stop d'un quart de
  bougie à plusieurs centaines de bougies, ou pas de stop du tout ; objectif d'un tiers du risque à 20 fois le risque,
  ou pas d'objectif). Les yeux apprennent une fonction continue : n'importe quel coup se demande ensuite.
- La correction est le VRAI chemin du prix, bougie par bougie, avec les seules règles réelles :
  * si stop et objectif tombent dans la même bougie, on compte le stop (pessimiste) ;
  * un stop sauté par un trou de cotation se paie au prix d'ouverture ;
  * fermeture forcée avant toute pause de plus de 2 h (week-end compris : compte FTMO Normal), et au plus une semaine.
- Les frais réels de chaque marché sont retirés ensuite (calcul exact, les yeux n'ont pas à les deviner).
Unité de distance : la taille habituelle d'une bougie de 15 minutes du marché à ce moment-là (« taille »).
"""
from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

from collapsar.mains.fiches import fiche
from collapsar.regarder.exercices import DEBUT_CONTROLE, DEBUT_RACINES, ECART, N_CONTROLE
from collapsar.yeux.graphique import Graphique

DUREE_MAX = 480                     # bougies de 15 minutes : une semaine au plus
PAUSE_MAX = np.timedelta64(2, "h")
STOP_MIN, STOP_MAX = 0.25, 300.0    # distance du stop, en tailles de bougie
SANS_STOP = 1000.0                  # bien au-delà de tout mouvement d'une semaine : « pas de stop »
OBJ_MIN, OBJ_MAX = 0.3, 20.0        # objectif, en multiples du risque
PART_SANS_STOP, PART_SANS_OBJECTIF = 0.1, 0.2
QUESTIONS = 8                       # coups tirés au hasard par situation, à chaque exercice
ECHELLE_MAX = 20.0                  # le résultat est appris en multiples de min(stop, 20 tailles)
LOIN = 1e9
FRAIS_INCONNU = 0.0006              # marché sans fiche : frais prudents
# coups utilisés SEULEMENT pour noter les yeux (jamais pour les limiter) : de quoi comparer les branches entre elles
SONDE_STOPS = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0)
SONDE_OBJECTIFS = (0.5, 1.0, 2.0, 3.0, 5.0, math.inf)
PART_SURE = 0.10                    # la note : les 10 % de situations où ses meilleurs coups lui semblent les meilleurs
_N_SONDES_SENS = len(SONDE_STOPS) * len(SONDE_OBJECTIFS)
ACHATS, VENTES = list(range(_N_SONDES_SENS)), list(range(_N_SONDES_SENS, 2 * _N_SONDES_SENS))
# 14/10 07h20 : CONTRE LE PAR CŒUR (mesuré : +85 à +97 % du risque par coup et 100 % de gagnants sur ses années
# apprises, -3 à -5 % sur 2020-2022) : elle reconnaissait chaque moment et récitait la suite. On l'empêche de
# reconnaître le moment exact : un léger flou sur les prix (en tailles de bougie) et des échelles cachées au hasard.
BRUIT = 0.15
MASQUE = 0.25                       # chance qu'une échelle soit cachée (jamais toutes)


def _correlation_par_colonne(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Corrélation entre a[:, k] et b[:, k] pour chaque colonne k."""
    a = a - a.mean(0)
    b = b - b.mean(0)
    return (a * b).sum(0) / (a.norm(dim=0) * b.norm(dim=0)).clamp(min=1e-9)


def requete(sens: torch.Tensor, stop: torch.Tensor, objectif: torch.Tensor) -> torch.Tensor:
    """Ce que les yeux reçoivent pour décrire un coup (5 nombres)."""
    sans_obj = ~torch.isfinite(objectif)
    sans_stop = stop >= SANS_STOP
    lo = torch.where(sans_obj, torch.zeros_like(objectif), torch.log(objectif.clamp(min=1e-3)) / 3)
    return torch.stack([sens, torch.log(stop.clamp(min=1e-3)) / 3, lo, sans_obj.float(), sans_stop.float()], -1)


def echelle(stop: torch.Tensor) -> torch.Tensor:
    return stop.clamp(max=ECHELLE_MAX)


class VisionTrader:
    unite = "% du risque gagné par coup choisi, frais compris"

    def __init__(self, g: Graphique, debut_controle: pd.Timestamp = DEBUT_CONTROLE, graine: int = 0,
                 debut_apprentissage: pd.Timestamp = DEBUT_RACINES, n_controle: int = N_CONTROLE):
        self.g = g
        # ce qu'elle regarde : le graphique brut (g.voir) par défaut ; une autre vue peut la remplacer (même question)
        self.voir = g.voir
        dev = g.appareil
        n = g.n
        lh = g.lh15.cpu().numpy().astype(np.float64)
        ll = g.ll15.cpu().numpy().astype(np.float64)
        temps = g.temps.astype("datetime64[ns]")
        pas = g.pas.astype("timedelta64[m]").astype("timedelta64[ns]")
        taille = np.full(n, np.nan)
        duree = np.zeros(n, np.int64)
        frais = np.full(n, FRAIS_INCONNU)
        for m, nom in enumerate(g.noms):
            a, b = int(g.debut_marche[m]), int(g.debut_marche[m + 1])
            try:
                frais[a:b] = fiche(nom).frais
            except ValueError:
                pass
            nh1 = int(getattr(g, "n_h1", {}).get(nom, 0))
            for x, y, div in ((a, a + nh1, 4), (a + nh1, b, 1)):
                if y <= x:
                    continue
                # taille d'une bougie de 15 minutes (une bougie d'1 heure mesure ~2 fois plus : racine de 4)
                t = pd.Series(lh[x:y] - ll[x:y]).rolling(64, min_periods=16).mean().to_numpy() / math.sqrt(div)
                taille[x:y] = t
                # dernière bougie avant une pause de plus de 2 h (ou fin du morceau) : fermeture forcée
                tt, pp = temps[x:y], pas[x:y]
                derniere = np.r_[(tt[1:] - (tt[:-1] + pp[:-1])) > PAUSE_MAX, True]
                fins = np.flatnonzero(derniere)
                i = np.arange(y - x)
                prochaine = fins[np.searchsorted(fins, i, side="left")]
                duree[x:y] = np.where(prochaine == i, 0, np.minimum(prochaine - i, DUREE_MAX // div))
        utilisable = np.isfinite(taille) & (taille > 0) & (duree >= 1)
        self.utilisable = utilisable
        taille = np.where(utilisable, taille, 1.0)
        self.taille = torch.from_numpy(taille.astype(np.float32)).to(dev)
        self.cout = torch.from_numpy((frais / taille).astype(np.float32)).to(dev)     # frais en tailles de bougie
        self.duree = torch.from_numpy(duree).to(dev)
        t = pd.DatetimeIndex(g.temps)
        apprend = utilisable & (t >= debut_apprentissage) & (t < debut_controle - ECART)
        controle = utilisable & (t >= debut_controle)
        self.idx_apprend = torch.from_numpy(np.flatnonzero(apprend)).to(dev)
        rng = np.random.default_rng(graine)
        ctrl = np.flatnonzero(controle)
        if len(ctrl) > n_controle:
            ctrl = np.sort(rng.choice(ctrl, n_controle, replace=False))
        self.idx_controle = torch.from_numpy(ctrl).to(dev)
        # témoin du PAR CŒUR : des situations APPRISES (les 4 dernières années avant le contrôle), notées pareil ; une
        # note très au-dessus de celle du contrôle = elle récite au lieu de comprendre
        temoin = np.flatnonzero(apprend & (t >= debut_controle - pd.Timedelta(days=4 * 365)))
        if len(temoin) > n_controle // 3:
            temoin = np.sort(rng.choice(temoin, n_controle // 3, replace=False))
        self.idx_temoin = torch.from_numpy(temoin).to(dev)
        self._sondes = {}                        # résultats réels des coups-sondes (calculés une fois par ensemble)

    # ---- le vrai chemin du prix ----
    @torch.no_grad()
    def resultat(self, idx: torch.Tensor, sens: torch.Tensor, stop: torch.Tensor,
                 objectifs: torch.Tensor, avec_sortie: bool = False):
        """Pour chaque situation `idx` (décision à la clôture de sa bougie), un coup de sens `sens` (+1 achat, -1 vente)
        avec un stop à `stop` tailles et un ou plusieurs objectifs `objectifs` [N, K] en multiples du risque (inf =
        pas d'objectif). Rend (résultat AVANT frais en tailles de bougie [N, K], objectif atteint [N, K]) et, si
        `avec_sortie`, le nombre de bougies jusqu'à la sortie [N, K]."""
        g = self.g
        idx = idx.long()
        d = self.duree[idx]
        H = max(1, int(d.max()))
        s = torch.arange(H, device=idx.device)
        j = (idx[:, None] + 1 + s[None, :]).clamp(max=g.n - 1)
        ok = s[None, :] < d[:, None]
        e = g.lc15[idx][:, None]
        u = self.taille[idx][:, None]
        achat = (sens > 0)[:, None]
        hh, ll = g.lh15[j], g.ll15[j]
        fav = torch.where(achat, hh - e, e - ll) / u
        adv = torch.where(achat, e - ll, hh - e) / u
        fav = torch.where(ok, fav, torch.full_like(fav, -LOIN)).cummax(1).values
        adv = torch.where(ok, adv, torch.full_like(adv, -LOIN)).cummax(1).values
        k_stop = torch.searchsorted(adv, stop[:, None].float().contiguous()).squeeze(1)        # H : jamais touché
        cible = torch.where(torch.isfinite(objectifs), objectifs * stop[:, None], torch.full_like(objectifs, LOIN))
        k_obj = torch.searchsorted(fav, cible.float().contiguous())
        atteint = k_obj < k_stop[:, None]                    # même bougie que le stop : compté comme stop
        stoppe = k_stop < d
        ks = k_stop.clamp(max=H - 1)
        ouv = g.lo15[j.gather(1, ks[:, None]).squeeze(1)]
        ouv = torch.where(sens > 0, ouv - e[:, 0], e[:, 0] - ouv) / u[:, 0]
        perte = torch.minimum(ouv, -stop)                     # trou de cotation : payé au prix d'ouverture
        kf = (d - 1).clamp(min=0)
        cf = g.lc15[j.gather(1, kf[:, None]).squeeze(1)]
        fin = torch.where(sens > 0, cf - e[:, 0], e[:, 0] - cf) / u[:, 0]
        sortie = torch.where(stoppe, perte, fin)
        res = torch.where(atteint, cible, sortie[:, None])
        if avec_sortie:
            k_sortie = torch.where(atteint, k_obj, torch.where(stoppe, k_stop, kf)[:, None]) + 1
            return res, atteint, k_sortie
        return res, atteint

    # ---- apprendre ----
    def _tirer(self, n: int, dev) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        sens = torch.where(torch.rand(n, device=dev) < 0.5, -1.0, 1.0)
        stop = torch.exp(torch.empty(n, device=dev).uniform_(math.log(STOP_MIN), math.log(STOP_MAX)))
        stop = torch.where(torch.rand(n, device=dev) < PART_SANS_STOP, torch.full_like(stop, SANS_STOP), stop)
        obj = torch.exp(torch.empty(n, device=dev).uniform_(math.log(OBJ_MIN), math.log(OBJ_MAX)))
        obj = torch.where(torch.rand(n, device=dev) < PART_SANS_OBJECTIF, torch.full_like(obj, math.inf), obj)
        return sens, stop, obj

    @staticmethod
    def brouiller(f: torch.Tensor, x: torch.Tensor, bruit: float, masque: float) -> tuple[torch.Tensor, torch.Tensor]:
        """Flou sur les prix et échelles cachées au hasard (apprentissage seulement)."""
        b, e = f.shape[0], f.shape[1]
        if bruit > 0:
            present = f[..., 5:6]
            f = torch.cat([f[..., :4] + torch.randn_like(f[..., :4]) * bruit * present, f[..., 4:]], -1)
        if masque > 0:
            cache = torch.rand(b, e, device=f.device) < masque
            cache[cache.all(1)] = False                                  # jamais l'écran entier
            f = f * (~cache)[:, :, None, None].float()
            x = torch.cat([x[:, :e] * (~cache).float(), x[:, e:]], 1)
        return f, x

    def perte(self, cerveau, idx: torch.Tensor, miroir: float = 0.0, bruit: float | None = None,
              masque: float | None = None) -> torch.Tensor:
        f, x = self.voir(idx)
        graphique = f.dim() == 4
        if graphique:
            f, x = self.brouiller(f, x, BRUIT if bruit is None else bruit, MASQUE if masque is None else masque)
        b = len(idx)
        dev = f.device
        sens, stop, obj = self._tirer(b * QUESTIONS, dev)
        retourne = torch.zeros(b, dtype=torch.bool, device=dev)
        if miroir > 0 and graphique:                          # graphique à l'envers : la vente devient l'achat
            retourne = torch.rand(b, device=dev) < miroir
            r = retourne[:, None, None, None]
            o, h, l, c = f[..., 0], f[..., 1], f[..., 2], f[..., 3]
            inv = torch.stack([-o, -l, -h, -c], -1)
            f = torch.cat([torch.where(r, inv, f[..., :4]), f[..., 4:]], -1)
        rep = idx.repeat_interleave(QUESTIONS)
        sens_vrai = torch.where(retourne.repeat_interleave(QUESTIONS), -sens, sens)
        res, atteint = self.resultat(rep, sens_vrai, stop, obj[:, None])
        res, atteint = res[:, 0], atteint[:, 0]
        logit, valeur, log_var = cerveau(f, x, requete(sens, stop, obj).reshape(b, QUESTIONS, -1))
        logit, valeur, log_var = logit.reshape(-1), valeur.reshape(-1), log_var.reshape(-1)
        cible = (res / echelle(stop)).clamp(-10, 20)
        a_obj = torch.isfinite(obj).float()
        # 14/10 04h30 : écart quadratique (il apprend le GAIN MOYEN du coup, ce qui compte pour un trader) ; l'ancien
        # écart « amorti » apprenait le résultat le plus fréquent (-1 pour un stop serré) : coups mal classés
        l_val = F.mse_loss(valeur, cible) / 4
        # 05h15 : son incertitude (variance du résultat), apprise sans toucher au gain moyen
        l_var = 0.5 * (log_var + (cible - valeur.detach()) ** 2 * torch.exp(-log_var)).mean()
        l_reussi = (F.binary_cross_entropy_with_logits(logit, atteint.float(), reduction="none") * a_obj).sum() \
            / a_obj.sum().clamp(min=1)
        return l_val + 0.5 * l_reussi + 0.1 * l_var

    def entrainer(self, cerveau, optimiseur, minutes: float, lot: int, generateur: torch.Generator,
                  miroir: float = 0.0, bruit: float | None = None, masque: float | None = None) -> dict:
        """`bruit`, `masque` : traits de la branche (None = valeurs par défaut du module)."""
        cerveau.train()
        fin = time.time() + minutes * 60
        pas, somme = 0, 0.0
        n = len(self.idx_apprend)
        while time.time() < fin:
            choix = torch.randint(0, n, (lot,), generator=generateur, device="cpu").to(self.g.appareil)
            perte = self.perte(cerveau, self.idx_apprend[choix], miroir, bruit, masque)
            optimiseur.zero_grad(set_to_none=True)
            perte.backward()
            torch.nn.utils.clip_grad_norm_(cerveau.parameters(), 1.0)
            optimiseur.step()
            pas += 1
            somme += float(perte.detach())
        return {"exercices": pas * lot * QUESTIONS, "perte": somme / max(pas, 1)}

    # ---- noter ----
    def sondes(self) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Les coups-sondes (2 sens x 9 stops x 6 objectifs = 108) : (sens, stop, objectif) [108] chacun."""
        grille = [(s, st, ob) for s in (1.0, -1.0) for st in SONDE_STOPS for ob in SONDE_OBJECTIFS]
        dev = self.g.appareil
        t = lambda k: torch.tensor([x[k] for x in grille], dtype=torch.float32, device=dev)
        return t(0), t(1), t(2)

    @torch.no_grad()
    def resultats_sondes(self, ensemble: str = "controle", lot: int = 512) -> torch.Tensor:
        """Résultat réel APRÈS frais, en multiples du risque, de chaque coup-sonde dans chaque situation de
        l'ensemble (« controle » ou « temoin ») [N, 108] (calculé une fois)."""
        if ensemble in self._sondes:
            return self._sondes[ensemble]
        situations = self.idx_controle if ensemble == "controle" else self.idx_temoin
        sens, stop, obj = self.sondes()
        n_st, n_ob = len(SONDE_STOPS), len(SONDE_OBJECTIFS)
        objs = torch.tensor(SONDE_OBJECTIFS, dtype=torch.float32, device=sens.device)
        sorties = []
        for d in range(0, len(situations), lot):
            idx = situations[d:d + lot]
            b = len(idx)
            par = []
            for sv in (1.0, -1.0):
                rep = idx.repeat_interleave(n_st)
                st = torch.tensor(SONDE_STOPS, device=idx.device).repeat(b)
                res, _ = self.resultat(rep, torch.full_like(st, sv), st, objs.expand(len(rep), n_ob))
                net = (res - self.cout[rep][:, None]) / st[:, None]
                par.append(net.reshape(b, n_st * n_ob))
            sorties.append(torch.cat(par, 1).half())
        self._sondes[ensemble] = torch.cat(sorties) if sorties else torch.zeros(0, n_st * n_ob * 2,
                                                                                device=sens.device).half()
        return self._sondes[ensemble]

    @torch.no_grad()
    def evaluer(self, cerveau, idx: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Ce que les yeux pensent de chaque coup-sonde, APRÈS frais, en multiples du risque : (gain moyen,
        incertitude = écart type du résultat) [N, 108] chacun."""
        sens, stop, obj = self.sondes()
        f, x = self.voir(idx)
        q = requete(sens, stop, obj)[None].expand(len(idx), -1, -1)
        _, valeur, log_var = cerveau(f, x, q)
        e = echelle(stop)[None] / stop[None]
        moyen = valeur.clamp(-10, 20) * e - self.cout[idx][:, None] / stop[None]   # jamais au-delà de l'appris
        return moyen, torch.exp(log_var / 2) * e

    @torch.no_grad()
    def controler(self, cerveau, lot: int = 256) -> dict:
        """La note : elle choisit dans chaque situation de 2020-2022 (jamais apprise) le coup au meilleur gain par
        rapport à son incertitude (comme un trader : un billet de loterie ne vaut rien) ; dans les 10 % de situations
        où ce choix lui semble le meilleur, ce que le coup a VRAIMENT rapporté, frais compris, en % du risque.
        Repères : le meilleur coup fixe joué sans regarder, et un coup au hasard. « par_coeur » : la même note sur des
        situations APPRISES (si elle est bien plus haute, elle récite)."""
        res = self._noter(cerveau, self.idx_controle, self.resultats_sondes("controle"), lot)
        if len(self.idx_temoin):
            appris = self._noter(cerveau, self.idx_temoin, self.resultats_sondes("temoin"), lot)
            res["par_coeur"] = appris["score"]
            res["lien_appris"] = appris["lien"]
        return res

    @torch.no_grad()
    def _noter(self, cerveau, situations: torch.Tensor, reel: torch.Tensor, lot: int) -> dict:
        cerveau.eval()
        moyens, ecarts = [], []
        for d in range(0, len(situations), lot):
            m, s = self.evaluer(cerveau, situations[d:d + lot])
            moyens.append(m)
            ecarts.append(s)
        cerveau.train()
        moyen, ecart = torch.cat(moyens), torch.cat(ecarts).clamp(min=1e-3)
        reel = reel.float()
        cout = self.cout[situations][:, None] / self.sondes()[1][None]          # frais de chaque coup-sonde
        qualite = moyen / ecart
        meilleur, choix = qualite.max(1)
        prevu = moyen.gather(1, choix[:, None]).squeeze(1)
        obtenu = reel.gather(1, choix[:, None]).squeeze(1)
        k = max(1, int(len(qualite) * PART_SURE))
        sur = torch.topk(meilleur, k).indices
        k1 = max(1, len(qualite) // 100)
        tres_sur = torch.topk(meilleur, k1).indices
        sens, stop, obj = self.sondes()
        c = choix[sur]
        res = {
            "score": float(obtenu[sur].mean() * 100),
            "bonnes": float((obtenu[sur] > 0).float().mean() * 100),
            "tres_sur": float(obtenu[tres_sur].mean() * 100),
            "prevu": float(prevu[sur].mean() * 100),
            "veut_trader": float((meilleur > 0).float().mean() * 100),
            "si_positif": float(obtenu[meilleur > 0].mean() * 100) if bool((meilleur > 0).any()) else 0.0,
            "objectif_median": float(obj[c][torch.isfinite(obj[c])].median()) if bool(torch.isfinite(obj[c]).any())
            else 0.0,
            "sans_objectif": float((~torch.isfinite(obj[c])).float().mean() * 100),
            # « lien » (14/10 09h) : corrélation, coup-sonde par coup-sonde, entre le gain prévu et le gain réel, sur
            # TOUTES les situations (en %) ; bien moins bruitée que la note des 10 % les plus sûrs, qui ne repose que
            # sur quelques centaines de moments vraiment indépendants (les coups sûrs se groupent : mars 2020...)
            # 14/10 14h40 : ATTENTION, ce lien-là contient les FRAIS, connus d'avance des deux côtés (2,7 points sur 2,8
            # mesurés) ; la vraie lecture du graphique se mesure SANS les frais (« lien_brut ») et sur le SENS
            # (« lien_sens » : achat moins vente, même stop et même objectif)
            "lien_frais_compris": float(_correlation_par_colonne(moyen, reel).mean() * 100),
            "lien": float(_correlation_par_colonne(moyen + cout, reel + cout).mean() * 100),
            "lien_sens": float(_correlation_par_colonne((moyen + cout)[:, ACHATS] - (moyen + cout)[:, VENTES],
                                                        (reel + cout)[:, ACHATS] - (reel + cout)[:, VENTES]).mean() * 100),
            "repere": float(reel.mean(0).max() * 100),
            "hasard": float(reel.mean() * 100),
            "stop_median": float(stop[c].median()),
            "achats": float((sens[c] > 0).float().mean() * 100),
        }
        return res


def details(note: dict) -> dict:
    return {k: round(v, 3) for k, v in note.items() if k not in ("score", "bonnes")}
