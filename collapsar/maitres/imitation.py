"""L'ÉCOLE AVEC MAÎTRES (15/10/2026) : COLLAPSAR apprend d'abord en regardant trader de bons traders, avec SA vision et
SES gestes (« on m'a d'abord montré de bons exemples », le chef de projet), puis s'améliore seule (école des mille
mondes, argent du compte).

Pour chaque trade d'un maître (format commun, maitres/trades.py), sur un marché que nous avons :
- ENTRÉE (la dernière bougie de 15 minutes close avant son entrée) : geste « changer », sens acheter/vendre,
  stop et objectif s'ils sont connus (en bougies du jour), et le moment de son prochain geste (sa sortie) ;
- TENUE (une bougie au hasard pendant le trade, position ouverte) : geste « garder », prochain geste = sa sortie ;
- SORTIE : geste « changer », sens « fermer » ;
- À PLAT (autant de bougies au hasard hors de ses trades) : geste « garder », prochain geste = sa prochaine entrée.
La taille n'est pas imitée (chaque maître a son compte et son levier ; la taille, c'est l'école et les murs FTMO).
Les maîtres sont pondérés par leur note du juge (maitres/juge.py) : un maître qui ne bat pas le hasard compte peu.

Honnêteté (option B du chef de projet, 15/10) : les trades des maîtres couvrent 2020-2026, donc nos périodes
d'examen et les 12 mois cachés ; un élève formé ici n'a plus de verdict honnête sur données passées : SON VERDICT,
C'EST LA DÉMO EN DIRECT. Contrôle de l'imitation : les 20 % de trades les plus récents de chaque maître, jamais vus.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from collapsar.cerveau.humain import (ACHETER, CHANGER, FERMER, GARDER, REGARD_MAX, VENDRE, TraderHumain)
from collapsar.ecole.regard import ClasseRegard, Etat, donnees_regard
from collapsar.mains.simulateur import CAPITAL

FIN_DONNEES = pd.Timestamp("2026-12-31")
QUINZE = pd.Timedelta(minutes=15)


def classe_marche(marche: str, appareil="cpu") -> ClasseRegard:
    return ClasseRegard([marche], appareil, donnees_regard([marche], jusqua=FIN_DONNEES))


def _bougie(c: ClasseRegard, quand: pd.Series) -> np.ndarray:
    """Indice de la dernière bougie de 15 minutes CLOSE avant l'instant (décision à sa clôture)."""
    fins = (c.h.temps + QUINZE).values
    return np.searchsorted(fins, pd.DatetimeIndex(quand).values, side="right") - 1


def exemples(c: ClasseRegard, tr: pd.DataFrame, rng: np.random.Generator, poids: float = 1.0) -> dict:
    """Les moments à apprendre pour UN marché : états vus par COLLAPSAR + gestes du maître."""
    T = c.h.T
    e_i, s_i = _bougie(c, tr["debut"]), _bougie(c, tr["fin"])
    ok = (e_i >= 96 * 30) & (s_i > e_i) & (s_i < T - 1)
    tr, e_i, s_i = tr[ok].reset_index(drop=True), e_i[ok], s_i[ok]
    lignes = []
    occupe = np.zeros(T, bool)
    for k in range(len(tr)):
        occupe[e_i[k]:s_i[k] + 1] = True
    entrees = np.sort(e_i)
    for k in range(len(tr)):
        sens = int(tr["sens"][k])
        p0 = float(c.h.c[e_i[k], 0])
        base = {"poids": poids, "sens_pos": sens, "entree_i": int(e_i[k]), "prix_entree": p0,
                "stop": tr["stop"][k], "objectif": tr["objectif"][k], "date": tr["debut"][k]}
        lignes.append({**base, "t": int(e_i[k]), "position": 0, "geste": CHANGER,
                       "sens": ACHETER if sens > 0 else VENDRE, "delai": int(s_i[k] - e_i[k])})
        if s_i[k] - e_i[k] >= 2:
            t = int(rng.integers(e_i[k] + 1, s_i[k]))
            lignes.append({**base, "t": t, "position": sens, "geste": GARDER, "sens": -1, "delai": int(s_i[k] - t)})
        lignes.append({**base, "t": int(s_i[k]), "position": sens, "geste": CHANGER, "sens": FERMER, "delai": -1})
    # à plat : seulement pendant la période où ce maître tradait (avant ou après, on ne sait pas ce qu'il aurait fait)
    lo, hi = (int(e_i.min()), int(s_i.max())) if len(tr) else (T, T)
    libres = np.flatnonzero(~occupe[lo:hi]) + lo
    if len(libres):
        for t in rng.choice(libres, size=min(len(tr), len(libres)), replace=False):
            prochaine = entrees[np.searchsorted(entrees, t)] if np.searchsorted(entrees, t) < len(entrees) else T
            lignes.append({"poids": poids, "sens_pos": 0, "entree_i": -1, "prix_entree": np.nan, "stop": np.nan,
                           "objectif": np.nan, "date": c.h.temps[t], "t": int(t), "position": 0, "geste": GARDER,
                           "sens": -1, "delai": int(prochaine - t)})
    return pd.DataFrame(lignes)


def etats(c: ClasseRegard, ex: pd.DataFrame):
    """Ce que COLLAPSAR voit à chaque moment : graphiques, calendrier, et SON compte avec la position du maître
    (1 x le compte, stop du maître s'il est connu)."""
    n = len(ex)
    e = Etat(c.h, n)
    t = torch.tensor(ex["t"].to_numpy(), device=c.dev)
    e.recommencer(torch.ones(n, dtype=torch.bool, device=c.dev), t)
    cpt = e.comptes
    pos = torch.tensor(ex["position"].to_numpy(float), device=c.dev, dtype=torch.float64)
    prix_e = torch.tensor(ex["prix_entree"].fillna(0).to_numpy(float), device=c.dev, dtype=torch.float64)
    fx = c.h.fx[t, 0]
    cpt.u[:, 0] = torch.where(pos != 0, pos * CAPITAL / (prix_e.clamp(min=1e-9) * fx), torch.zeros_like(pos))
    cpt.entree[:, 0] = torch.where(pos != 0, prix_e, torch.zeros_like(prix_e))
    stop = torch.tensor(ex["stop"].to_numpy(float), device=c.dev, dtype=torch.float64)
    cpt.stop[:, 0] = torch.where((pos != 0) & ~torch.isnan(stop), stop, torch.full_like(stop, float("nan")))
    e.ouverture[:, 0] = torch.where(pos != 0, torch.tensor(ex["entree_i"].to_numpy(), device=c.dev), -1)
    e.dernier = t - 16                                      # il a regardé il y a environ 4 heures
    cpt.jours_trades[:] = 4
    cpt.jour_dernier_trade = cpt.jour.clone()
    return c.voir(e, torch.ones(n, dtype=torch.bool, device=c.dev))


def cibles(c: ClasseRegard, ex: pd.DataFrame, taille_jour: torch.Tensor) -> dict:
    dev = c.dev
    f = lambda col, d=torch.float32: torch.tensor(ex[col].to_numpy(), device=dev, dtype=d)
    prix = c.h.c[torch.tensor(ex["t"].to_numpy(), device=dev), 0].float()
    tj = taille_jour[:, 0].clamp(min=1e-4)
    # distance inconnue (pas de stop chez ce maître) : 0, masquée ensuite (les lois refusent les valeurs vides)
    dist = lambda col: torch.nan_to_num(torch.log(((f(col) - prix).abs() / prix / tj).clamp(min=1e-3)), 0.0)
    entree = (f("geste", torch.long) == CHANGER) & (f("sens", torch.long) != FERMER)
    return {"geste": f("geste", torch.long), "sens": f("sens", torch.long).clamp(min=0),
            "avec_sens": f("geste", torch.long) == CHANGER,
            "regard": torch.log(f("delai").clamp(1, REGARD_MAX)), "avec_regard": f("delai") > 0,
            "stop": dist("stop"), "avec_stop": entree & ~torch.isnan(f("stop")),
            "objectif": dist("objectif"), "avec_objectif": entree & ~torch.isnan(f("objectif")),
            "poids": f("poids")}


def perte(agent: TraderHumain, c: ClasseRegard, idx, vm, vc, cib: dict) -> tuple[torch.Tensor, dict]:
    sortie, _ = c.sortie(agent, idx, vm, vc)
    lois = agent.lois(sortie)
    w = cib["poids"]
    moy = lambda x, m=None: (x * w * (m.float() if m is not None else 1)).sum() / (
        (w * (m.float() if m is not None else 1)).sum() + 1e-9)
    p_geste = -lois["geste"].log_prob(cib["geste"][:, None])[:, 0]
    p_sens = -lois["sens"].log_prob(cib["sens"][:, None])[:, 0]
    p_regard = -lois["regard"].log_prob(cib["regard"])
    p_stop = -(lois["stop_on"].log_prob(torch.ones_like(cib["stop"])[:, None])[:, 0]
               + lois["stop_dist"].log_prob(cib["stop"][:, None])[:, 0])
    p_obj = -(lois["obj_on"].log_prob(torch.ones_like(cib["objectif"])[:, None])[:, 0]
              + lois["obj_dist"].log_prob(cib["objectif"][:, None])[:, 0])
    total = (moy(p_geste) + moy(p_sens, cib["avec_sens"]) + 0.3 * moy(p_regard, cib["avec_regard"])
             + 0.3 * moy(torch.nan_to_num(p_stop), cib["avec_stop"]) + 0.3 * moy(torch.nan_to_num(p_obj), cib["avec_objectif"]))
    with torch.no_grad():
        g_ok = (sortie["geste"][:, 0].argmax(-1) == cib["geste"]).float()
        ls = sortie["sens"][:, 0]                       # à une entrée : acheter ou vendre (fermer exclu)
        s_ok = (torch.where(ls[:, ACHETER] > ls[:, VENDRE], ACHETER, VENDRE) == cib["sens"]).float()
        m = cib["avec_sens"] & (cib["sens"] != FERMER)
        achats, ventes = m & (cib["sens"] == ACHETER), m & (cib["sens"] == VENDRE)
        # équilibré : moyenne du juste sur ses achats et sur ses ventes (toujours dire « achat » = 50 %, pas plus)
        mesures = {"geste_juste": float(g_ok.mean()), "sens_entree_juste": float(s_ok[m].mean()) if m.any() else float("nan"),
                   "juste_achats": float(s_ok[achats].mean()) if achats.any() else float("nan"),
                   "juste_ventes": float(s_ok[ventes].mean()) if ventes.any() else float("nan"),
                   "achats": float(achats.sum()), "ventes": float(ventes.sum())}
    return total, mesures
