"""Le juge (CONCEPTION, section 8) : l'examen tournant sur 2023 -> septembre 2025.

- Jamais appris : l'école s'arrête en 2022. Les 12 mois cachés (octobre 2025 -> aujourd'hui) ne sont même pas chargés.
- Examen TOURNANT : à chaque examen, des dates de départ tirées au hasard (numéro d'examen = graine), pour ne jamais
  fabriquer une IA adaptée à une seule période (leçon d'AUREXIS, 09/10).
- Chaque compte est un challenge FTMO d'un mois sur le simulateur fidèle (même compte pour tous les marchés, murs
  exacts, frais réels, fermeture avant les pauses).
- La note : challenges réussis - murs touchés (en points de %), puis le gain par mois pour départager.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from collapsar.cerveau.agent import Agent
from collapsar.donnees import marches as dm
from collapsar.ecole.classe import UN_MOIS, Classe, jouer_comptes
from collapsar.mains.fiches import fiche, taux_vers_dollar
from collapsar.mains.simulateur import CAPITAL, Comptes

DEBUT_EXAMEN = pd.Timestamp("2023-01-01")


def donnees_examen(marches: list[str], fin: pd.Timestamp = dm.FIN_EXAMEN) -> dict[str, pd.DataFrame]:
    """Les marchés jusqu'à `fin` (au plus fin septembre 2025, STRICTEMENT : les 12 mois cachés ne sont jamais lus)."""
    fin = min(fin, dm.FIN_EXAMEN)
    besoin = list(marches)
    for m in marches:
        source, _ = taux_vers_dollar(fiche(m).cotation)
        if source and source not in besoin:
            besoin.append(source)
    return {m: dm.charger(m, jusqua=fin) for m in besoin}


class Juge:
    def __init__(self, marches: list[str], appareil="cpu", donnees=None, avis=None):
        donnees = donnees or donnees_examen(marches)
        assert all(df["time"].max() < dm.FIN_EXAMEN for df in donnees.values()), "les mois cachés restent cachés"
        self.marches = marches
        self.classe = Classe(marches, parties=1, appareil=appareil, donnees=donnees, avis=avis)
        t = self.classe.h.temps
        self.debut = int(np.searchsorted(t.values, DEBUT_EXAMEN.to_datetime64()))
        self.dernier_depart = self.classe.h.T - 1 - UN_MOIS
        assert self.dernier_depart > self.debut, "pas assez de données d'examen"

    def examiner(self, agent: Agent, numero: int, comptes_n: int = 48) -> dict:
        g = torch.Generator().manual_seed(100_000 + numero)
        departs = torch.randint(self.debut, self.dernier_depart, (comptes_n,), generator=g).sort().values
        res = jouer_comptes(self.classe, agent, departs, UN_MOIS, graine=numero)
        res["note"] = res["challenges_reussis_pct"] - res["murs_touches_pct"]
        res["numero"] = numero
        res["periode"] = (f"{self.classe.h.temps[int(departs[0])]:%m/%Y} -> "
                          f"{self.classe.h.temps[int(departs[-1]) + UN_MOIS]:%m/%Y}")
        return res


class JugeMarches:
    """L'examen sur PLUSIEURS marchés, un compte par marché (chaque marché examiné à ses propres dates tirées au
    hasard). L'avis ne contient pas le nom du marché : un élève qui réussit partout a appris à trader, pas un marché."""

    def __init__(self, marches: list[str], avis, appareil="cpu", debut: pd.Timestamp = DEBUT_EXAMEN,
                 fin: pd.Timestamp = dm.FIN_EXAMEN):
        """Tous les marchés avancent sur la même horloge (un seul passage du temps : ~10 x plus rapide qu'un marché
        après l'autre) ; chaque compte ne trade QUE son marché (les autres ordres sont ignorés) : c'est bien un
        challenge d'un mois par marché. Un mois = 30 jours de calendrier.
        Par défaut l'examen 2023 -> 09/2025 ; `debut`/`fin` : une autre période (ex. les années de l'école, pour la
        porte « observer -> école », sans jamais toucher à l'examen)."""
        donnees = donnees_examen(marches, fin)
        assert all(df["time"].max() < dm.FIN_EXAMEN for df in donnees.values()), "les mois cachés restent cachés"
        self.marches = [m for m in marches if (donnees[m]["time"] >= debut).sum() > 3 * UN_MOIS]
        self.classe = Classe(self.marches, parties=1, appareil=appareil, donnees=donnees, avis=avis)
        self.t = self.classe.h.temps
        self.debut = int(np.searchsorted(self.t.values, debut.to_datetime64()))
        self.dernier = int(np.searchsorted(self.t.values, (self.t[-1] - pd.Timedelta(days=31)).to_datetime64()))

    @torch.no_grad()
    def _jouer(self, agent, departs, marche_de, fins) -> list[dict]:
        c, h = self.classe, self.classe.h
        dev = c.dev
        n, M = len(departs), h.M
        cpt = Comptes(h, n)
        cpt.recommencer(torch.ones(n, dtype=torch.bool, device=dev), departs)
        sien = torch.zeros(n, M, dtype=torch.bool, device=dev)
        if marche_de is None:                                   # compte unique : chaque compte trade TOUS les marchés
            sien[:] = True
        else:
            sien[torch.arange(n, device=dev), marche_de] = True
        vivant = torch.ones(n, dtype=torch.bool, device=dev)
        reussi, mort = torch.zeros_like(vivant), torch.zeros_like(vivant)
        finale = torch.full((n,), CAPITAL, dtype=torch.float64, device=dev)
        sommet, baisse = finale.clone(), torch.zeros_like(finale)
        trades = torch.zeros(n, device=dev)
        en_pos = torch.zeros(n, device=dev)
        frais = torch.zeros(n, dtype=torch.float64, device=dev)
        nuits = torch.zeros(n, dtype=torch.float64, device=dev)
        forcees = torch.zeros(n, device=dev)
        pas = torch.zeros(n, device=dev)
        if isinstance(agent, torch.nn.Module):
            agent.eval()
        while vivant.any():
            idx, vm, vc = c.regarder(cpt)
            if hasattr(agent, "actions"):
                agir, z = agent.actions(c, cpt, idx, vm, vc)
            else:
                agir, z, _, _, _ = c.agir(agent, idx, vm, vc, deterministe=True)
            agir = agir * (sien & vivant[:, None]).float()
            r = cpt.pas(c.ordres(cpt, agir, z))
            v = torch.where(vivant, r["valeur"], finale)
            sommet = torch.maximum(sommet, v)
            baisse = torch.maximum(baisse, (sommet - v) / sommet)
            finale = v
            reussi |= vivant & r["reussi"]
            mort |= vivant & r["mort"]
            trades += (vivant & (r["frais"] > 0)).float()
            frais += torch.where(vivant, r["frais"], torch.zeros_like(r["frais"]))
            nuits += torch.where(vivant, r["nuit"], torch.zeros_like(r["nuit"]))
            forcees += (vivant & (r["forcees"] > 0)).float()
            en_pos += (vivant & (cpt.u != 0).any(1)).float()
            pas += vivant.float()
            vivant &= ~(r["mort"] | r["reussi"] | r["fin_histoire"]) & (cpt.t < fins)
        gains = (finale / CAPITAL - 1) * 100
        return [{"gain": float(gains[i]), "reussi": bool(reussi[i]), "mort": bool(mort[i]),
                 "baisse": float(baisse[i] * 100), "trades": float(trades[i]),
                 "ecart_paye": float(frais[i] / CAPITAL * 100), "nuits_payees": float(nuits[i] / CAPITAL * 100),
                 "fermetures_forcees": float(forcees[i]),
                 "en_position": float(en_pos[i] / pas[i].clamp(min=1) * 100)} for i in range(n)]

    def examiner(self, agent: Agent, numero: int, comptes_par_marche: int = 2, jours: int = 30) -> dict:
        """`jours` : durée de chaque challenge (30 = un mois ; 90 = trois mois, pour mesurer un petit avantage avec moins
        de hasard). Les gains sont rapportés PAR MOIS."""
        dev = self.classe.dev
        g = torch.Generator().manual_seed(100_000 + numero)
        M = len(self.marches)
        marche_de = torch.arange(M).repeat_interleave(comptes_par_marche)
        dernier = int(np.searchsorted(self.t.values, (self.t[-1] - pd.Timedelta(days=jours + 1)).to_datetime64()))
        departs = torch.randint(self.debut, dernier, (len(marche_de),), generator=g)
        fins = torch.from_numpy(np.searchsorted(self.t.values, (self.t[departs.numpy()] + pd.Timedelta(days=jours)).values))
        appareils = [dev] if dev.type == "cuda" else []
        with torch.random.fork_rng(devices=appareils):
            torch.manual_seed(numero)
            lignes = self._jouer(agent, departs.to(dev), marche_de.to(dev), fins.to(dev))
        par_marche = {}
        mois = jours / 30
        for i, l in enumerate(lignes):
            for k in ("gain", "trades", "ecart_paye", "nuits_payees", "fermetures_forcees"):
                l[k] /= mois
            par_marche.setdefault(self.marches[int(marche_de[i])], []).append(l)
        stats = {m: {"gain_moyen_mois_pct": np.mean([x["gain"] for x in ls]),
                     "challenges_reussis_pct": np.mean([x["reussi"] for x in ls]) * 100,
                     "murs_touches_pct": np.mean([x["mort"] for x in ls]) * 100,
                     "baisse_max_moyenne_pct": np.mean([x["baisse"] for x in ls]),
                     "trades_par_compte": np.mean([x["trades"] for x in ls]),
                     "temps_en_position_pct": np.mean([x["en_position"] for x in ls]),
                     "ecart_paye_pct_mois": np.mean([x["ecart_paye"] for x in ls]),
                     "nuits_payees_pct_mois": np.mean([x["nuits_payees"] for x in ls]),
                     "fermetures_forcees_mois": np.mean([x["fermetures_forcees"] for x in ls])} for m, ls in par_marche.items()}
        par_marche = stats
        cles = ("gain_moyen_mois_pct", "challenges_reussis_pct", "murs_touches_pct", "baisse_max_moyenne_pct",
                "trades_par_compte", "temps_en_position_pct", "ecart_paye_pct_mois", "nuits_payees_pct_mois",
                "fermetures_forcees_mois")
        res = {k: float(np.mean([r[k] for r in par_marche.values()])) for k in cles}
        res["marches_gagnants_pct"] = float(np.mean([r["gain_moyen_mois_pct"] > 0 for r in par_marche.values()]) * 100)
        res["note"] = res["challenges_reussis_pct"] - res["murs_touches_pct"]
        res["numero"], res["marches"] = numero, len(par_marche)
        res["periode"] = "01/2023 -> 09/2025"
        res["par_marche"] = {m: round(r["gain_moyen_mois_pct"], 3) for m, r in par_marche.items()}
        return res

    def examiner_compte_unique(self, agent: Agent, numero: int, comptes: int = 24, jours: int = 90) -> dict:
        """L'examen d'un vrai compte FTMO : UN compte de 100 000 $ qui trade tous les marchés en même temps, comme
        en réel. `comptes` challenges partent à des dates tirées au hasard ; gains rapportés par mois."""
        dev = self.classe.dev
        g = torch.Generator().manual_seed(200_000 + numero)
        dernier = int(np.searchsorted(self.t.values, (self.t[-1] - pd.Timedelta(days=jours + 1)).to_datetime64()))
        departs = torch.randint(self.debut, dernier, (comptes,), generator=g)
        fins = torch.from_numpy(np.searchsorted(self.t.values, (self.t[departs.numpy()] + pd.Timedelta(days=jours)).values))
        appareils = [dev] if dev.type == "cuda" else []
        with torch.random.fork_rng(devices=appareils):
            torch.manual_seed(numero)
            lignes = self._jouer(agent, departs.to(dev), None, fins.to(dev))
        mois = jours / 30
        for l in lignes:
            for k in ("gain", "trades", "ecart_paye", "nuits_payees", "fermetures_forcees"):
                l[k] /= mois
        moy = lambda k: float(np.mean([l[k] for l in lignes]))
        return {"gain_moyen_mois_pct": moy("gain"), "gain_median_mois_pct": float(np.median([l["gain"] for l in lignes])),
                "comptes_positifs_pct": float(np.mean([l["gain"] > 0 for l in lignes]) * 100),
                "challenges_reussis_pct": float(np.mean([l["reussi"] for l in lignes]) * 100),
                "murs_touches_pct": float(np.mean([l["mort"] for l in lignes]) * 100),
                "baisse_max_moyenne_pct": moy("baisse"), "pire_baisse_pct": float(max(l["baisse"] for l in lignes)),
                "trades_par_mois": moy("trades"), "temps_en_position_pct": moy("en_position"),
                "ecart_paye_pct_mois": moy("ecart_paye"), "nuits_payees_pct_mois": moy("nuits_payees"),
                "comptes": comptes, "jours": jours, "marches": len(self.marches), "numero": numero}
