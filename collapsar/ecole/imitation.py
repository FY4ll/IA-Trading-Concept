"""D'abord imiter : l'élève regarde la démonstration (« tenir son avis ») jouer sur les années vierges et apprend à
faire pareil — QUAND agir, dans quel sens, combien. Ensuite (ecole/classe.py, Professeur avec une référence), la
récompense l'améliore sans la laisser dériver vers le casino ou la paralysie.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from collapsar.cerveau.agent import AgentAvis
from collapsar.ecole.classe import Classe


class Imitateur:
    def __init__(self, mondes: list[Classe], agent: AgentAvis, maitre, pas: int = 64, epoques: int = 2,
                 paquet: int = 4096, vitesse: float = 1e-3):
        self.mondes, self.agent, self.maitre = mondes, agent, maitre
        self.pas, self.epoques, self.paquet = pas, epoques, paquet
        self.opt = torch.optim.AdamW(agent.parameters(), lr=vitesse, weight_decay=1e-5)

    @torch.no_grad()
    def regarder_le_maitre(self) -> dict:
        mem = {k: [] for k in ("avis", "vm", "vc", "agir", "z")}
        for _ in range(self.pas):
            for c in self.mondes:
                idx, vm, vc = c.regarder(c.comptes)
                agir, z = self.maitre.actions(c, c.comptes, idx, vm, vc)
                mem["avis"].append(c.avis.voir(idx).reshape(vm.shape[0], vm.shape[1], -1))
                for k, v in (("vm", vm), ("vc", vc), ("agir", agir), ("z", z)):
                    mem[k].append(v)
                r = c.comptes.pas(c.ordres(c.comptes, agir, z))
                fin = (r["mort"] | r["reussi"] | r["fin_histoire"] | (c.comptes.t >= c.fin_apprentissage)
                       | (c.comptes.t - c.debut_partie >= c.duree_partie))
                if fin.any():
                    c.recommencer(fin)
        self.memoire = {k: torch.cat(v, 0) for k, v in mem.items()}
        return {"agit_maitre": float(self.memoire["agir"].mean())}

    def apprendre(self) -> dict:
        m, a = self.memoire, self.agent
        n = len(m["agir"])
        a.train()
        bilan = {"quand": 0.0, "combien": 0.0, "rappel": 0.0, "fausses": 0.0, "k": 0}
        for _ in range(self.epoques):
            ordre = torch.randperm(n, device=m["agir"].device)
            for d in range(0, n, self.paquet):
                i = ordre[d:d + self.paquet]
                logit, moyenne, _ = a.decider(m["avis"][i], m["vm"][i], m["vc"][i])
                quand = F.binary_cross_entropy_with_logits(logit, m["agir"][i])
                poids = m["agir"][i]
                combien = ((moyenne - m["z"][i]) ** 2 * poids).sum() / poids.sum().clamp(min=1)
                perte = quand + combien
                self.opt.zero_grad(set_to_none=True)
                perte.backward()
                torch.nn.utils.clip_grad_norm_(a.parameters(), 1.0)
                self.opt.step()
                with torch.no_grad():
                    p = torch.sigmoid(logit)
                    rappel = (p * poids).sum() / poids.sum().clamp(min=1)              # chance d'agir quand il faut
                    fausses = (p * (1 - poids)).sum() / (1 - poids).sum().clamp(min=1)  # ... quand il ne faut pas
                bilan["quand"] += float(quand)
                bilan["combien"] += float(combien)
                bilan["rappel"] += float(rappel)
                bilan["fausses"] += float(fausses)
                bilan["k"] += 1
        k = bilan.pop("k")
        return {x: v / k for x, v in bilan.items()}
