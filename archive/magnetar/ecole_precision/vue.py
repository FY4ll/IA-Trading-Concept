"""CE QU'ELLE VOIT à un regard (carte graphique), pour chaque marché de son panier :
- ses zones d'offre et de demande vivantes de chaque unité (journalier -> 3 min) : les 2 plus proches de chaque côté,
  leur distance au prix (bord proche, bord lointain) en agitations, leur hauteur, leur âge, touchées ou non, réaction
  ou non, et si elles sont DANS une zone du même côté d'une unité plus grande (zone dans la zone) ;
- les derniers sommets et creux confirmés de chaque unité et la tendance qu'ils dessinent (sommets / creux montants ou
  descendants) ;
- les 8 dernières clôtures en journalier, 4 h, 1 h, 15 min (prix brut, en agitations) ;
- l'agitation, le coût d'un aller-retour en agitations, l'heure, le jour, les séances, les heures avant la fermeture ;
- sa position, son ordre en attente, son compte (fournis par jeu.py).
Et les NIVEAUX DE STRUCTURE parmi lesquels ses mains choisissent (cerveau.py).
"""
from __future__ import annotations

import torch

from collapsar.ecole.precision.reglages import R, UNITES, UNITES_BRUTES

NU = len(UNITES)
I_BRUTES = [UNITES.index(u) for u in UNITES_BRUTES]


def nan0(x):
    return torch.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)


class Vue:
    def __init__(self, U):
        self.U = U
        self.K = R().yeux.zones_par_cote
        self.nb = R().yeux.bougies_brutes
        dev = U.dev
        self.ar = torch.arange(self.nb, device=dev)
        self.i_brutes = torch.tensor(I_BRUTES, device=dev)
        self.plus_grande = (torch.arange(NU, device=dev)[None, :] < torch.arange(NU, device=dev)[:, None])
        self.signe = torch.tensor([1.0, -1.0], device=dev)

    @torch.no_grad()
    def structure(self, t: torch.Tensor, cols: torch.Tensor) -> dict:
        """t [n] (lignes du monde), cols [n, J] (colonnes, -1 = place vide)."""
        U, K = self.U, self.K
        n, J = cols.shape
        cc = cols.clamp(min=0)
        tt = t[:, None].expand(n, J)
        slot = cols >= 0
        p = U.tC[tt, cc]
        A = U.tA[tt, cc].clamp(min=1e-12)
        loc = U.tLOC[tt, cc].long()
        demi = U.tDEMI[tt, cc]
        rows = U.tLIGNES[tt, cc].long()                                  # [n,J,U]
        okr = (rows >= 0) & slot[..., None]
        r0 = rows.clamp(min=0)
        dn = U.tDONNEES[r0]                                              # [n,J,U,2K+5]
        ids = dn[..., :2 * K].long().reshape(n, J, NU, 2, K)
        okz = (ids >= 0) & okr[..., None, None]
        z = U.tZONES[ids.clamp(min=0)]                                   # [n,J,U,2,K,5]
        l5 = loc[:, :, None, None, None]
        top, bot = z[..., 0], z[..., 1]
        tou = okz & (z[..., 3] <= l5)
        rea = okz & (z[..., 4] <= l5)
        age = torch.where(okz, (l5 - z[..., 2]).clamp(min=0) / 4, 0.0)
        sw = torch.where(okr[..., None], dn[..., 2 * K:2 * K + 4], float("nan"))     # [n,J,U,4]
        rb = r0[..., self.i_brutes]                                      # [n,J,4]
        idx = torch.maximum(rb[..., None] - self.ar, U.tRDEBUT[cc][..., self.i_brutes][..., None])
        cl = U.tDONNEES[idx, 2 * K + 4]                                  # [n,J,4,8]
        brut = torch.where(okr[..., self.i_brutes][..., None], (cl - p[..., None, None]) / A[..., None, None], 0.0)
        # zone dans une zone du même côté d'une unité PLUS GRANDE (chevauchement de prix)
        a_t, a_b = top[..., None, None], bot[..., None, None]
        b_t = top.permute(0, 1, 3, 2, 4)[:, :, None, :, None]           # [n,J,1,2,1,U',K']
        b_b = bot.permute(0, 1, 3, 2, 4)[:, :, None, :, None]
        b_ok = okz.permute(0, 1, 3, 2, 4)[:, :, None, :, None]
        chev = (a_t >= b_b) & (a_b <= b_t) & b_ok & self.plus_grande[None, None, :, None, None, :, None]
        dans = chev.flatten(-2).any(-1) & okz
        out = {"p": p, "A": A, "demi": demi, "loc": loc, "slot": slot, "top": top, "bot": bot, "ok": okz,
               "tou": tou, "rea": rea, "age": age, "dans": dans, "sw": sw, "brut": brut, "t": t, "cc": cc}
        if hasattr(U, "tSV_DISPO"):                     # stop suiveur (suiveur.py) : unités connues de chaque marché
            out["sv_dispo"] = U.tSV_DISPO[cc] & slot[..., None]
        return out

    def caracteristiques(self, s: dict) -> torch.Tensor:
        """[n, J, F] : tout ce qu'elle voit d'un marché, en agitations (bornes -10 / +10)."""
        U = self.U
        p, A = s["p"][..., None, None, None], s["A"][..., None, None, None]
        top, bot = s["top"], s["bot"]
        sg = self.signe[None, None, None, :, None]
        proche = torch.stack([top[:, :, :, 0], bot[:, :, :, 1]], 3)
        loin = torch.stack([bot[:, :, :, 0], top[:, :, :, 1]], 3)
        okf = s["ok"].float()
        z = torch.stack([okf, sg * (p - proche) / A * okf, sg * (p - loin) / A * okf, (top - bot) / A * okf,
                         torch.log1p(s["age"]) / 5 * okf, s["tou"].float(), s["rea"].float(), s["dans"].float()], -1)
        n, J = z.shape[:2]
        sw = s["sw"]
        pp, AA = s["p"][..., None], s["A"][..., None]
        swd = torch.stack([sw[..., 0] - pp, sw[..., 1] - pp, pp - sw[..., 2], pp - sw[..., 3]], -1) / AA[..., None]
        swok = torch.isfinite(sw).float()
        tend = (nan0(torch.sign(sw[..., 0] - sw[..., 1])) + nan0(torch.sign(sw[..., 2] - sw[..., 3]))) / 2
        swf = torch.cat([nan0(swd) * swok, swok, tend[..., None]], -1)                     # [n,J,U,9]
        tt = s["t"][:, None].expand(n, J)
        cc = s["cc"]
        divers = torch.stack([(torch.log(s["A"] / s["p"]) + 4.5) / 1.5, 2 * s["demi"] * s["p"] / s["A"] * 10,
                              U.tPAUSE[tt, cc] / 48, U.tOUVERT[tt, cc].float()], -1)
        temps = U.tTEMPS[s["t"]][:, None, :].expand(n, J, -1)
        parts = [z.reshape(n, J, -1), swf.reshape(n, J, -1), s["brut"].reshape(n, J, -1), U.tDISPO[cc], divers, temps]
        if foule_active():                                  # yeux de la foule (foule.py), en DERNIER : greffe simple
            parts.append(U.tFOULE[tt, U.tFOULE_IDX[cc]])
        if juge_active():                                   # notes du juge (juge_trade.py), après la foule
            parts.append(U.tJUGE[tt, cc])
        if monde_active():                                  # yeux du monde (monde.py), en DERNIER
            parts.append(U.tMONDE[tt, U.tMONDE_IDX[cc]])
        f = torch.cat(parts, -1)
        return nan0(f).clamp(-10, 10) * s["slot"][..., None]


def foule_active() -> bool:
    """Yeux de la foule allumés ? (réglage yeux.foule, false par défaut ; ou arbre greffé, voir foule.py)"""
    return bool(getattr(R().yeux, "foule", False))


N_JUGE = 8                                                  # = juge_trade.NJ (vérifié par tests/test_juge_trade.py)


def juge_active() -> bool:
    """Notes du juge allumées ? (réglage yeux.juge, false par défaut ; ou arbre greffé, voir juge_trade.py)"""
    return bool(getattr(R().yeux, "juge", False))


N_MONDE = 36                                                # = monde.NM (vérifié par tests/test_monde.py)


def monde_active() -> bool:
    """Yeux du monde allumés ? (réglage yeux.monde, false par défaut ; ou arbre greffé, voir monde.py)"""
    return bool(getattr(R().yeux, "monde", False))


def taille_caracteristiques() -> int:
    K = R().yeux.zones_par_cote
    nb = R().yeux.bougies_brutes
    n_foule = 19 if foule_active() else 0                  # = foule.NF (vérifié par tests/test_foule.py)
    n_juge = N_JUGE if juge_active() else 0
    n_monde = N_MONDE if monde_active() else 0
    return NU * 2 * K * 8 + NU * 9 + len(UNITES_BRUTES) * nb + NU + 4 + 7 + n_foule + n_juge + n_monde
