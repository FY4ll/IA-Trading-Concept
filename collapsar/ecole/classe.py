"""Une classe de l'école : des centaines de comptes FTMO jouent en même temps, elle apprend par essais et erreurs.

Récompense (CONCEPTION, section 6) :
- à chaque bougie de 15 minutes : ce que son compte a gagné ou perdu (en % du capital), positions ouvertes comprises ;
- toucher un mur FTMO (-5 % sur le jour, -10 % au total) : la partie s'arrête, grosse punition (-20) ;
- réussir le challenge (+10 %) : bonus modéré (+5), plus petit que la punition.
Ses horloges : elle estime l'avenir à 3 horizons (1 jour, 1 semaine, 1 mois) ; ses décisions écoutent les trois.
Méthode : apprentissage par renforcement « PPO » (essais, puis renforcement des décisions qui ont mieux marché
que prévu, par petites touches).

Honnêteté : elle apprend sur les données d'avant juillet 2022 ; elle est contrôlée sur juillet-décembre 2022, jamais
appris. Les examens 2023-2025 et les 12 mois cachés restent au juge.
"""
from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd
import torch

from collapsar.cerveau.agent import Agent
from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche, taux_vers_dollar
from collapsar.mains.horloge import Horloge
from collapsar.mains.simulateur import CAPITAL, Comptes, Ordres
from collapsar.yeux.graphique import Graphique

PUNITION_MUR = 20.0
BONUS_REUSSITE = 5.0
PEUR_DU_MUR = 4.0                  # décision du chef de projet (13/10) : elle doit « sentir le danger »


def danger(valeur: torch.Tensor, solde_minuit: torch.Tensor, capital: float = CAPITAL) -> torch.Tensor:
    """Part de la perte permise déjà consommée (0 = loin des murs, 1 = au mur) : la plus grande entre le mur du jour
    (-5 % depuis minuit) et le mur total (-10 %)."""
    jour = (solde_minuit - valeur) / (0.05 * capital)
    total = (capital - valeur) / (0.10 * capital)
    return torch.maximum(jour, total).clamp(0, 1)


def ressenti(gain: torch.Tensor, d: torch.Tensor) -> torch.Tensor:
    """Ce qu'elle ressent d'un gain ou d'une perte : un gain compte tel quel ; une perte fait d'autant plus mal que le
    compte est déjà près d'un mur (x2 à mi-chemin, x3,6 aux 4/5, x5 au mur), comme un trader humain à -4 % sur sa
    journée. Ne change rien au compte, seulement à ce qu'elle apprend."""
    return torch.where(gain < 0, gain * (1 + PEUR_DU_MUR * d * d), gain)
DEBUT_CONTROLE = pd.Timestamp("2022-07-01")
ECART = pd.Timedelta(days=10)
UN_MOIS = 2100                     # bougies de 15 minutes dans un mois de marché (environ)
CURIOSITE_MIN = 0.02               # à l'école, au moins 2 % de chances d'agir à chaque bougie (contre la paresse)


def donnees_classe(marches: list[str]) -> dict[str, pd.DataFrame]:
    """Les marchés de la classe + ceux qui servent à convertir leurs devises en dollars (tout avant 2023)."""
    besoin = list(marches)
    for m in marches:
        source, _ = taux_vers_dollar(fiche(m).cotation)
        if source and source not in besoin:
            besoin.append(source)
    return {m: dm.charger(m) for m in besoin}


class Classe:
    def __init__(self, marches: list[str], parties: int, appareil="cpu", donnees=None, graine: int = 0,
                 avis=None, apprendre_de: pd.Timestamp | None = None, apprendre_jusqua: pd.Timestamp | None = None):
        """`avis` : son avis calculé d'avance (yeux/avis.py) au lieu des graphiques ; `apprendre_de` / `apprendre_jusqua` :
        la fenêtre où les parties d'entraînement commencent (par défaut : tout avant le contrôle de mi-2022)."""
        donnees = donnees or donnees_classe(marches)
        self.dev = torch.device(appareil)
        self.h = Horloge(donnees, marches, appareil)
        self.avis = avis
        if avis is None:
            self.g = Graphique({m: donnees[m] for m in marches}, appareil)
            self.offset = torch.tensor(self.g.debut_marche[:len(marches)], device=self.dev)
        else:
            self.g = None
            self.offset = torch.tensor([avis.debut[m] for m in marches], device=self.dev)
        t = self.h.temps
        jusqua = apprendre_jusqua if apprendre_jusqua is not None else DEBUT_CONTROLE
        self.fin_apprentissage = int(np.searchsorted(t.values, (jusqua - ECART).to_datetime64()))
        self.debut_controle = int(np.searchsorted(t.values, DEBUT_CONTROLE.to_datetime64()))
        self.debut_possible = (int(np.searchsorted(t.values, apprendre_de.to_datetime64())) if apprendre_de is not None
                               else min(96 * 30, self.fin_apprentissage // 4))
        self.debut_possible = max(self.debut_possible, 96 * 30)    # un mois d'historique avant la première partie
        self.B = parties
        self.comptes = Comptes(self.h, parties)
        self.gen = torch.Generator(device=self.dev).manual_seed(graine)
        # une partie = un challenge d'un mois, comme l'examen (constaté le 13/10 : des parties de plusieurs mois
        # laissaient un compte en perte « près du mur » pour toujours, et elle finissait paralysée)
        self.duree_partie = UN_MOIS
        self.debut_partie = torch.zeros(parties, dtype=torch.int64, device=self.dev)
        self.recommencer(torch.ones(parties, dtype=torch.bool, device=self.dev))

    def recommencer(self, masque):
        departs = self._departs(self.B)
        self.comptes.recommencer(masque, departs)
        self.debut_partie = torch.where(masque, departs, self.debut_partie)

    def _departs(self, n):
        return torch.randint(self.debut_possible, self.fin_apprentissage - UN_MOIS, (n,), device=self.dev,
                             generator=self.gen)

    def regarder(self, comptes: Comptes):
        """Indices de ce qu'elle voit (graphique) + la vue de son compte, à l'instant de chaque partie."""
        vm, vc = comptes.vue()
        local = self.h.local[comptes.t].clamp(min=0)
        idx = (self.offset[None, :] + local).reshape(-1)
        return idx, vm, vc

    def lire(self, agent: Agent, idx, b: int, m: int):
        """Ce qu'elle a sous les yeux : son avis calculé d'avance, ou ce que ses yeux lisent des graphiques."""
        if getattr(agent, "par_avis", False):
            return self.avis.voir(idx).reshape(b, m, -1)
        f, x = self.g.voir(idx)
        return agent.lire(f, x, b, m)

    def agir(self, agent: Agent, idx, vm, vc, deterministe=False):
        lu = self.lire(agent, idx, vm.shape[0], vm.shape[1])
        logit, moyenne, valeurs = agent.decider(lu, vm, vc)
        loi_agir, loi_pos = agent.lois(logit, moyenne, 0.0 if deterministe else CURIOSITE_MIN)
        if deterministe:                       # contrôle : QUAND agir reste tiré au sort (elle n'agit qu'une
            agir, z = loi_agir.sample(), moyenne   # bougie sur plusieurs), la position voulue est sa meilleure idée
        else:
            agir, z = loi_agir.sample(), loi_pos.sample()
        return agir, z, Agent.log_prob(loi_agir, loi_pos, agir, z), valeurs, lu

    def ordres(self, comptes: Comptes, agir, z) -> Ordres:
        valeur = comptes.valeur(self.h.c[comptes.t], self.h.fx[comptes.t])
        cible = Agent.position_voulue(z.double(), valeur)
        return Ordres(cible=torch.where(agir.bool(), cible, torch.full_like(cible, float("nan"))))


class Professeur:
    """Fait jouer la classe, puis renforce les décisions qui ont mieux marché que prévu (PPO à plusieurs horloges).
    Plusieurs « mondes » peuvent jouer ensemble (le marché et son miroir) : leurs parties sont mises en commun."""

    def __init__(self, classe: Classe | list[Classe], agent: Agent, pas: int = 64, vitesse=3e-4, vitesse_yeux=3e-5,
                 lambda_=0.95, coupe=0.2, epoques=4, paquet=4096, curiosite=0.01, reference: Agent | None = None,
                 laisse: float = 0.0):
        """`reference` + `laisse` : après l'imitation, une laisse (divergence avec ce qu'elle a appris en imitant)
        l'empêche de dériver vers le casino ou la paralysie pendant que la récompense l'améliore."""
        self.reference, self.laisse = reference, laisse
        if reference is not None:
            for p in reference.parameters():
                p.requires_grad_(False)
        self.mondes = list(classe) if isinstance(classe, (list, tuple)) else [classe]
        assert len(self.mondes) == 1 or agent.yeux_figes, "plusieurs mondes : seulement avec les yeux figés"
        assert len({c.h.M for c in self.mondes}) == 1, "tous les mondes ont le même nombre de marchés"
        self.c, self.agent = self.mondes[0], agent
        self.pas, self.lam, self.coupe, self.epoques, self.paquet, self.curiosite = (pas, lambda_, coupe, epoques,
                                                                                     paquet, curiosite)
        yeux_tous = list(agent.cerveau.parameters()) if agent.cerveau is not None else []
        yeux = [p for p in yeux_tous if p.requires_grad]
        ids = {id(p) for p in yeux_tous}
        reste = [p for p in agent.parameters() if id(p) not in ids]
        groupes = [{"params": reste, "lr": vitesse}] + ([{"params": yeux, "lr": vitesse_yeux}] if yeux else [])
        self.opt = torch.optim.AdamW(groupes, weight_decay=1e-5)
        self.gammas = torch.tensor(agent.gammas, device=self.c.dev)
        self.B = sum(c.B for c in self.mondes)
        self.opt_horloges = torch.optim.AdamW(agent.horloges.parameters(), lr=vitesse)

    def _un_pas(self, c: Classe, a: Agent, stats: dict) -> dict:
        idx, vm, vc = c.regarder(c.comptes)
        agir, z, lp, v, lu = c.agir(a, idx, vm, vc)
        avant = c.comptes.valeur(c.h.c[c.comptes.t], c.h.fx[c.comptes.t])
        d = danger(avant, c.comptes.solde_minuit).float()
        r = c.comptes.pas(c.ordres(c.comptes, agir, z))
        gain = ((r["valeur"] - avant) / CAPITAL * 100).float()
        rec = ressenti(gain, d) - PUNITION_MUR * r["mort"].float() + BONUS_REUSSITE * r["reussi"].float()
        fin = (r["mort"] | r["reussi"] | r["fin_histoire"] | (c.comptes.t >= c.fin_apprentissage)
               | (c.comptes.t - c.debut_partie >= c.duree_partie))
        stats["danger"] += float(d.mean())
        stats["morts"] += int(r["mort"].sum())
        stats["reussis"] += int(r["reussi"].sum())
        stats["frais"] += float(r["frais"].sum())
        stats["agit"] += float(agir.mean())
        stats["en_position"] += float((c.comptes.u != 0).float().mean())
        stats["expo"] += float(vm[..., 0].abs().mean() * 10)
        if fin.any():
            c.recommencer(fin)
        return {"idx": idx.reshape(c.B, -1), "lu": lu if a.yeux_figes else lu[:0], "vm": vm, "vc": vc,
                "agir": agir, "z": z, "lp": lp, "v": v, "r": rec, "fin": fin.float()}

    def jouer(self) -> dict:
        a, T = self.agent, self.pas
        mem = {k: [] for k in ("idx", "lu", "vm", "vc", "agir", "z", "lp", "v", "r", "fin")}
        stats = {"morts": 0, "reussis": 0, "frais": 0.0, "agit": 0.0, "en_position": 0.0, "expo": 0.0, "danger": 0.0}
        a.eval()
        with torch.no_grad():
            for _ in range(T):
                parts = [self._un_pas(c, a, stats) for c in self.mondes]
                for k in mem:
                    mem[k].append(torch.cat([p[k] for p in parts], 0))
            fins = []
            for c in self.mondes:
                idx, vm, vc = c.regarder(c.comptes)
                fins.append(a.decider(c.lire(a, idx, vm.shape[0], vm.shape[1]), vm, vc)[2])
        mem = {k: torch.stack(v) for k, v in mem.items()}
        mem["v_fin"] = torch.cat(fins, 0)
        for k in ("agit", "en_position", "expo", "danger"):
            stats[k] /= T * len(self.mondes)
        stats["recompense"] = float(mem["r"].sum(0).mean())
        self.memoire = mem
        return stats

    def avantages(self):
        m = self.memoire
        T = self.pas
        v = torch.cat([m["v"], m["v_fin"][None]], 0)                     # [T+1, B, H]
        r, fin = m["r"][..., None], m["fin"][..., None]
        g = self.gammas[None, None, :]
        av = torch.zeros_like(m["v"])
        suite = torch.zeros_like(m["v"][0])
        for t in reversed(range(T)):
            delta = r[t] + g * v[t + 1] * (1 - fin[t]) - v[t]
            suite = delta + g * self.lam * (1 - fin[t]) * suite
            av[t] = suite
        retours = av + m["v"]
        norm = (av - av.mean((0, 1))) / (av.std((0, 1)) + 1e-8)          # chaque horloge à la même échelle
        return norm.mean(-1), retours                                     # elle écoute les trois horloges

    def echauffer(self) -> dict:
        """Échauffement : seules ses horloges (son estimation de l'avenir) apprennent, ses décisions ne bougent pas."""
        c, a, m = self.c, self.agent, self.memoire
        _, retours = self.avantages()
        T, B = self.pas, self.B
        plat = lambda x: x.reshape(T * B, *x.shape[2:])
        lu, vm, vc, retours = plat(m["lu"]), plat(m["vm"]), plat(m["vc"]), plat(retours)
        total, n = 0.0, 0
        for _ in range(self.epoques):
            ordre = torch.randperm(T * B, device=c.dev)
            for d in range(0, T * B, self.paquet):
                i = ordre[d:d + self.paquet]
                with torch.no_grad():
                    x = a.encodeur(lu[i]) if hasattr(a, "encodeur") else lu[i]
                    b_, m_ = vm[i].shape[0], vm[i].shape[1]
                    par_marche = a.marche(torch.cat([x, vm[i]], -1))
                    cc = a.compte(vc[i])
                    xx = a.ensemble(torch.cat([par_marche, cc[:, None, :].expand(b_, m_, -1)], -1))
                    entree = torch.cat([xx.mean(1), cc], -1)
                perte = torch.nn.functional.huber_loss(a.horloges(entree), retours[i])
                self.opt_horloges.zero_grad(set_to_none=True)
                perte.backward()
                self.opt_horloges.step()
                total += float(perte)
                n += 1
        return {"perte_horloges": total / max(n, 1)}

    @staticmethod
    def _divergence(ref_agir, ref_pos, loi_agir, loi_pos):
        p_r, p = ref_agir.probs.clamp(1e-6, 1 - 1e-6), loi_agir.probs.clamp(1e-6, 1 - 1e-6)
        kl_quand = p_r * torch.log(p_r / p) + (1 - p_r) * torch.log((1 - p_r) / (1 - p))
        s_r, s = ref_pos.stddev, loi_pos.stddev
        kl_pos = torch.log(s / s_r) + (s_r ** 2 + (ref_pos.mean - loi_pos.mean) ** 2) / (2 * s ** 2) - 0.5
        return (kl_quand + p_r * kl_pos).sum(-1).mean()

    def apprendre(self) -> dict:
        c, a, m = self.c, self.agent, self.memoire
        av, retours = self.avantages()
        T, B = self.pas, self.B
        plat = lambda x: x.reshape(T * B, *x.shape[2:])
        idx = plat(m["idx"])
        vm, vc, agir, z, lp = plat(m["vm"]), plat(m["vc"]), plat(m["agir"]), plat(m["z"]), plat(m["lp"])
        lu = plat(m["lu"]) if a.yeux_figes else None
        av, retours = plat(av), plat(retours)
        a.train()
        bilan = {"perte_decision": 0.0, "perte_horloges": 0.0, "hasard": 0.0, "n": 0}
        for _ in range(self.epoques):
            ordre = torch.randperm(T * B, device=c.dev)
            for d in range(0, T * B, self.paquet):
                i = ordre[d:d + self.paquet]
                if a.yeux_figes:                       # ses yeux ont déjà regardé : on réutilise ce qu'ils ont compris
                    logit, moyenne, valeurs = a.decider(lu[i], vm[i], vc[i])
                else:
                    f, x = c.g.voir(idx[i].reshape(-1))
                    logit, moyenne, valeurs = a(f, x, vm[i], vc[i])
                loi_agir, loi_pos = a.lois(logit, moyenne, CURIOSITE_MIN)
                nlp = Agent.log_prob(loi_agir, loi_pos, agir[i], z[i])
                ratio = (nlp - lp[i]).exp()
                p1 = ratio * av[i]
                p2 = ratio.clamp(1 - self.coupe, 1 + self.coupe) * av[i]
                perte_dec = -torch.min(p1, p2).mean()
                perte_h = torch.nn.functional.huber_loss(valeurs, retours[i])
                hasard = (loi_agir.entropy().sum(-1) + loi_pos.entropy().sum(-1)).mean()
                perte = perte_dec + 0.5 * perte_h - self.curiosite * hasard
                if self.reference is not None and self.laisse > 0:
                    with torch.no_grad():
                        r_logit, r_moy, _ = self.reference.decider(lu[i], vm[i], vc[i])
                        r_agir, r_pos = self.reference.lois(r_logit, r_moy, CURIOSITE_MIN)
                    perte = perte + self.laisse * self._divergence(r_agir, r_pos, loi_agir, loi_pos)
                self.opt.zero_grad(set_to_none=True)
                perte.backward()
                torch.nn.utils.clip_grad_norm_(a.parameters(), 0.5)
                self.opt.step()
                bilan["perte_decision"] += float(perte_dec)
                bilan["perte_horloges"] += float(perte_h)
                bilan["hasard"] += float(hasard)
                bilan["n"] += 1
        n = bilan.pop("n")
        return {k: v / n for k, v in bilan.items()}


@torch.no_grad()
def controler(classe: Classe, agent: Agent, comptes_n: int = 24, duree: int = UN_MOIS) -> dict:
    """Contrôle sur juillet-décembre 2022 (jamais appris) : des comptes partent à des dates étalées et jouent un mois.
    Tirages au sort figés (même contrôle à chaque fois, pour comparer). En %, comme un challenge FTMO d'un mois."""
    derniers = max(classe.debut_controle + 1, classe.h.T - 1 - duree)
    departs = torch.linspace(classe.debut_controle, derniers, comptes_n, device=classe.dev).long()
    return jouer_comptes(classe, agent, departs, duree, graine=12345)


@torch.no_grad()
def jouer_comptes(classe: Classe, agent: Agent, departs: torch.Tensor, duree: int = UN_MOIS, graine: int = 0) -> dict:
    """Des comptes FTMO de 100 000 $ partent aux instants `departs` et jouent `duree` bougies (un mois par défaut),
    comme un challenge : arrêt à +10 % (réussi) ou à un mur (perdu). Tirages au sort figés par `graine`."""
    appareils = [classe.dev] if classe.dev.type == "cuda" else []
    with torch.random.fork_rng(devices=appareils):
        torch.manual_seed(graine)
        return _jouer(classe, agent, departs.to(classe.dev), duree)


def _jouer(classe: Classe, agent: Agent, departs: torch.Tensor, duree: int) -> dict:
    c, h = classe, classe.h
    comptes_n = len(departs)
    cpt = Comptes(h, comptes_n)
    cpt.recommencer(torch.ones(comptes_n, dtype=torch.bool, device=c.dev), departs)
    vivant = torch.ones(comptes_n, dtype=torch.bool, device=c.dev)
    reussi = torch.zeros_like(vivant)
    mort = torch.zeros_like(vivant)
    pire = torch.full((comptes_n,), CAPITAL, dtype=torch.float64, device=c.dev)
    sommet = pire.clone()
    baisse_max = torch.zeros_like(pire)
    finale = pire.clone()
    agit = trades = en_position = 0.0
    if isinstance(agent, torch.nn.Module):
        agent.eval()
    for _ in range(duree):
        idx, vm, vc = c.regarder(cpt)
        if hasattr(agent, "actions"):                 # un modèle de démonstration (ecole/demonstration.py)
            agir, z = agent.actions(c, cpt, idx, vm, vc)
        else:
            agir, z, _, _, _ = c.agir(agent, idx, vm, vc, deterministe=True)
        agir = agir * vivant[:, None].float()
        r = cpt.pas(c.ordres(cpt, agir, z))
        v = torch.where(vivant, r["valeur"], finale)
        sommet = torch.maximum(sommet, v)
        baisse_max = torch.maximum(baisse_max, (sommet - v) / sommet)
        finale = v
        reussi |= vivant & r["reussi"]
        mort |= vivant & r["mort"]
        vivant &= ~(r["mort"] | r["reussi"] | r["fin_histoire"])
        agit += float(agir.mean())
        trades += float((r["frais"] > 0).float().sum())
        en_position += float((cpt.u != 0).float().mean())
        if not vivant.any():
            break
    gains = (finale / CAPITAL - 1) * 100
    return {"gain_moyen_mois_pct": float(gains.mean()), "comptes_positifs_pct": float((gains > 0).float().mean() * 100),
            "challenges_reussis_pct": float(reussi.float().mean() * 100),
            "murs_touches_pct": float(mort.float().mean() * 100),
            "baisse_max_moyenne_pct": float(baisse_max.mean() * 100),
            "trades_par_compte": trades / comptes_n, "temps_en_position_pct": en_position / duree * 100}
