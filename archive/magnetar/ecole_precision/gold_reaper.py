"""LA BRANCHE « GOLD REAPER » de MAGNETAR (20/10/2026, accord du chef de projet) : elle IMITE un vrai trader prouvé
(signal MQL5 2265877 « Gold Reaper New V2 2 », vie/maitres_mql5/rapport.md), puis apprend à le DÉPASSER par la
récompense « en laisse » (même méthode que le mentor et l'apprentie P2 : mentor.py).

HONNÊTETÉ (règles du chef de projet) :
- seuls ses trades FERMÉS AVANT le 01/10/2025 sont lus (les lignes d'après sont jetées à la lecture du fichier, jamais
  utilisées) ; l'or à la minute du projet s'arrête au 12/09/2025 : ses trades d'après ne peuvent pas être rejoués ;
- ces trades tombent DANS le contrôle 01/2024 -> 09/2025 de MAGNETAR : pour CETTE branche (et ses filles), le contrôle
  2024-2025 n'est PAS valable (marqué dans son tempérament, le journal, le rapport) ; elle est jugée sur l'examen
  tournant 2010-2023 (le même pour toutes les branches ; Gold Reaper n'existait pas avant 10/2024) et, plus tard, en direct.

1. SES GESTES (`positions`, `calendrier`, `Professeur`) : il ouvre souvent plusieurs morceaux au même prix ; les morceaux
   du même sens qui se chevauchent = UNE position (les mains de MAGNETAR : une idée à la fois par marché). Entrée = sa
   1re ouverture, au premier bord de 15 min APRÈS elle (ordre au marché décidé à la clôture de cette bougie, exécuté à
   l'ouverture suivante, comme le simulateur ; jamais avant lui : sinon le rejeu connaîtrait sa décision trop tôt) ;
   sortie = « fermer » au premier bord après le moment où la MOITIÉ de son volume est fermée.
   Pas de stop dans l'export : stop effectif déduit de ses positions (`STOP_CIBLE_A`, voir le rapport) : le niveau de
   structure + marge des mains le plus proche de 0,6 agitation (plafond 0,75). Risque : 0,5 % pour sa taille médiane
   (lots par 1 000 $ de son solde), proportionnel (0,1 / 0,25 / 0,5 / 1 / 2 %). Pas d'objectif (« laisser courir »),
   pas de stop suiveur, regard toutes les 15 min (un scalper regarde sans arrêt : aucune règle qui connaît l'avenir).
   Sur l'or RETOURNÉ (cerveau symétrique) : le même geste dans l'autre sens.
2. FIDÉLITÉ (`fidelite`) : ses positions rejouées par le simulateur de l'arbre (frais FTMO) contre ses vrais résultats.
3. IMITATION (`imiter`) : sur ses journées (et « ne rien faire » ailleurs), 20 % de ses jours gardés de côté.
4. EN LAISSE (`apprendre_en_laisse`, cœur de l'arbre) : son apprentissage habituel + le rappel de Gold Reaper sur SES
   regards (jours appris seulement), pesé par la laisse qui se relâche (0,8 par génération), protégée 12 générations.

Depuis Test_IA :
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.gold_reaper preparer   (copie de la cime, rien n'est greffé)
  ... appliquer   (arbre ARRÊTÉ, ARRET en place) ; retour : ... retirer (la branche seule) / ... defaire (vie d'avant)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if __name__ == "__main__" and not os.environ.get("COLLAPSAR_PRECISION_REGLAGES"):
    if "collapsar.ecole.precision.reglages" in sys.modules:
        raise SystemExit("gold_reaper : les réglages d'un autre arbre sont déjà chargés")
    os.environ["COLLAPSAR_PRECISION_REGLAGES"] = str(Path(__file__).with_name("reglages_or.yaml"))

import argparse  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402
from datetime import datetime  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

from collapsar.donnees.marches import RACINE  # noqa: E402
from collapsar.ecole.precision.reglages import CAPITAL, R, UNITES, VIE  # noqa: E402

VERSION = 1
NOM_MAITRE = "Gold Reaper"
SIGNAL = "MQL5 2265877 (Gold Reaper New V2 2)"
CSV = RACINE / "data" / "maitres" / "mql5" / "2265877.csv"
COUPURE = pd.Timestamp("2025-10-01")          # après : les 12 mois cachés (jamais lus)
ECART_COURTIER = 0.15                         # $/once rendus (ses prix contiennent l'écart de son courtier)
MARCHE = "XAUUSD@M1"
FICHIER = "gold_reaper.json"                  # écrit à la greffe (dossier de vie)
SOUS_DOSSIER = "gold_reaper"
LECONS = "lecons.pt"
NOM_BRANCHE = "gold_reaper"
STOP_CIBLE_A = 0.6                            # stop effectif déduit de ses positions (agitations)
PLAFOND_STOP_A = 0.75                         # plafond des stops de CETTE branche (les autres : 0,4)
RISQUE_CENTRE = 0.5                           # % pour sa taille médiane
RETARD_MAX = 1                                # bougies de retard tolérées pour ouvrir (regard manqué)
PART_TEST = 0.2
GRAINE = 20261020
LAISSE_DEPART = 1.0
LAISSE_RELACHE = 0.8
JEUNESSE = 12
QUART_NS = int(pd.Timedelta(minutes=15).value)
JOUR_NS = int(pd.Timedelta(days=1).value)
ROLES = ("rien", "ouvre", "ferme", "tient")
NOMS = ["t_open", "type", "vol", "sym", "p_open", "vol2", "t_close", "p_close", "comm", "swap", "profit"]


# ============================================================================================== ses trades
def charger_trades(fichier: Path = CSV, coupure: pd.Timestamp = COUPURE) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(ses trades d'or FERMÉS avant la coupure, ses dépôts avant la coupure). Les lignes d'après sont jetées ici."""
    df = pd.read_csv(fichier, sep=";", header=0, names=NOMS)
    bal = df[df.type == "Balance"].copy()
    bal["t"] = pd.to_datetime(bal.t_open, format="%Y.%m.%d %H:%M:%S")
    bal = bal[bal.t < coupure]
    t = df[df.type.isin(["Buy", "Sell"])].copy()
    t["to"] = pd.to_datetime(t.t_open, format="%Y.%m.%d %H:%M:%S")
    t["tc"] = pd.to_datetime(t.t_close, format="%Y.%m.%d %H:%M:%S")
    t = t[(t.tc < coupure) & (t.to < coupure)]                       # LES MOIS CACHÉS NE SONT JAMAIS GARDÉS
    t[["comm", "swap"]] = t[["comm", "swap"]].fillna(0.0)
    # solde (devise du compte) au moment d'ouvrir : dépôts + trades fermés avant (tous symboles, avant la coupure)
    ev_t = np.r_[bal.t.values, t.tc.values]
    ev_v = np.r_[bal.profit.values, (t.profit + t.comm + t.swap).values]
    o = np.argsort(ev_t, kind="stable")
    ev_t, ev_c = ev_t[o], np.cumsum(ev_v[o])
    i = np.searchsorted(ev_t, t.to.values, side="left") - 1
    t["solde"] = np.where(i >= 0, ev_c[np.clip(i, 0, None)], np.nan)
    t = t[t.sym == "XAUUSD"].sort_values(["to", "tc"], kind="stable").reset_index(drop=True)
    assert t.tc.max() < coupure and t.to.max() < coupure
    t["s"] = np.where(t.type == "Buy", 1, -1)
    t["oz"] = t.vol * 100
    t["move"] = (t.p_close - t.p_open) * t.s                             # $ par once (prix exécutés chez lui)
    return t, bal


def couts_ftmo(t: pd.DataFrame) -> np.ndarray:
    """$/once de frais FTMO de chaque morceau (écart + commission aller-retour, nuits FTMO triples le mercredi)."""
    from collapsar.mains.fiches import fiche
    from collapsar.mains.frais_ftmo import frais
    from collapsar.mains.nuit import taux_nuit
    p = t.p_open.to_numpy(float)
    cout = np.asarray(frais("XAUUSD", p), float) * p
    ach, ven = taux_nuit(fiche("XAUUSD"), pd.DatetimeIndex(t.to))
    d0 = (t.to.dt.normalize() - pd.Timestamp("2000-01-01")).dt.days.to_numpy()
    d1 = (t.tc.dt.normalize() - pd.Timestamp("2000-01-01")).dt.days.to_numpy()
    k = np.arange(d0.min(), d1.max() + 1)
    sem = (k + 5) % 7
    cum = np.r_[0.0, np.cumsum(np.where(sem == 2, 3.0, np.where(sem >= 5, 0.0, 1.0)))]
    nuits = cum[d1 - k[0]] - cum[d0 - k[0]]
    taux = np.where(t.s.to_numpy() > 0, ach, ven)
    return cout + taux * p / 360 * nuits


def positions(t: pd.DataFrame) -> pd.DataFrame:
    """Ses morceaux du même sens qui se chevauchent = UNE position (une idée à la fois par marché, comme les mains)."""
    g = np.zeros(len(t), np.int64)
    k, fin, sens = -1, None, None
    for i in range(len(t)):
        if fin is None or t.to.iloc[i] >= fin or t.s.iloc[i] != sens:
            k += 1
            fin, sens = t.tc.iloc[i], t.s.iloc[i]
        else:
            fin = max(fin, t.tc.iloc[i])
        g[i] = k
    t = t.assign(g=g, net=t.move + ECART_COURTIER - couts_ftmo(t))
    out = []
    for k_, x in t.groupby("g", sort=True):
        v = x.vol.to_numpy(float)
        xs = x.sort_values("tc", kind="stable")
        cum = np.cumsum(xs.vol.to_numpy(float)) / v.sum()
        out.append({"g": int(k_), "sens": int(x.s.iloc[0]), "t_ouv": x.to.min(), "t_ferm": xs.tc.iloc[int(np.argmax(cum >= 0.5 - 1e-9))],
                    "t_ferm_max": x.tc.max(), "morceaux": len(x), "lots": float(v.sum()),
                    "lots_1000": float(v.sum() / x.solde.iloc[0] * 1000) if x.solde.iloc[0] > 0 else np.nan,
                    "p_ouv": float((x.p_open * v).sum() / v.sum()),
                    "move_brut": float((x.move * v).sum() / v.sum()), "move_ftmo": float((x.net * v).sum() / v.sum())})
    p = pd.DataFrame(out)
    p["jour"] = p.t_ouv.dt.normalize()
    return p


def risques(p: pd.DataFrame, appris: np.ndarray | None = None) -> np.ndarray:
    """Numéro du risque (mains.risques_pct) de chaque position : RISQUE_CENTRE pour sa taille médiane (lots par
    1 000 $ de son solde, médiane des positions APPRISES), proportionnel, au plus proche (en rapport)."""
    rp = np.asarray(R().mains.risques_pct, float)
    x = p.lots_1000.to_numpy(float)
    ref = np.nanmedian(x[appris] if appris is not None and appris.any() else x)
    vise = RISQUE_CENTRE * np.where(np.isfinite(x), x / ref, 1.0)
    return np.abs(np.log(vise[:, None]) - np.log(rp[None, :])).argmin(1)


def jours_de_test(p: pd.DataFrame, de: pd.Timestamp, jusqua: pd.Timestamp, part: float = PART_TEST,
                  graine: int = GRAINE) -> tuple[set, set]:
    """(jours de test parmi SES jours de trading, jours de test parmi les autres) : ~20 % chacun, tirés une fois."""
    rng = np.random.default_rng(graine)
    tous = pd.date_range(pd.Timestamp(de).normalize(), pd.Timestamp(jusqua).normalize(), freq="D")
    siens = sorted(set(p.jour))
    autres = sorted(set(tous) - set(siens))
    a = set(rng.choice(np.asarray(siens, "datetime64[ns]"), int(round(part * len(siens))), replace=False).astype("datetime64[ns]"))
    b = set(rng.choice(np.asarray(autres, "datetime64[ns]"), int(round(part * len(autres))), replace=False).astype("datetime64[ns]"))
    return {pd.Timestamp(x) for x in a}, {pd.Timestamp(x) for x in b}


# ============================================================================================== son calendrier
def bord(ts: pd.Series) -> np.ndarray:
    """Le premier bord de 15 min À PARTIR de sa décision (ns) : jamais avant. (Mesuré le 20/10 : arrondi au bord le plus
    PROCHE, le rejeu « savait » sa décision quelques minutes trop tôt — il entre souvent quand le prix vient de partir —
    et gagnait 2,3 fois plus que lui ; arrondi après : 99 % de son résultat.)"""
    ns = ts.values.astype("datetime64[ns]").astype(np.int64)
    r = ns % QUART_NS
    return np.where(r == 0, ns, ns - r + QUART_NS)


def calendrier(U, p: pd.DataFrame) -> dict:
    """Pour chaque position : le regard où il ouvre (te : décidé à la clôture de te, exécuté à l'ouverture de te + 1) et
    celui où il ferme (tx >= te + 1), dans les lignes du monde U ; couverte = rejouable dans ce monde."""
    tn = np.asarray(U.t_ns, np.int64)
    be = bord(p.t_ouv)
    bx = np.maximum(bord(p.t_ferm), be + QUART_NS)
    te = np.searchsorted(tn, be, side="left") - 1
    tx = np.maximum(np.searchsorted(tn, bx, side="left") - 1, te + 1)
    ok = (te >= int(U.premier.min())) & (tx <= U.T - 2) & (p.t_ferm_max.values.astype("datetime64[ns]").astype(np.int64)
                                                           <= tn[-1] + QUART_NS)
    return {"te": te.astype(np.int64), "tx": tx.astype(np.int64), "couverte": ok, "sens": p.sens.to_numpy(np.int64)}


# ============================================================================================== ses numéros
def numeros() -> dict:
    """Ses choix fixes dans les listes des mains : laisser courir, pas d'objectif 1, pas de suiveur, regard 15 min."""
    from collapsar.ecole.precision import cerveau as C  # noqa: F401
    r = R().mains
    K, NU = R().yeux.zones_par_cote, len(UNITES)
    i_courir = NU * K + NU * 2
    proche = lambda liste, x: int(np.argmin([abs(float(v) - x) for v in liste]))
    return {"courir": i_courir, "tp1": i_courir + proche(r.tp1_en_r, 1.0), "part": proche(r.parts_tp1, 0.0),
            "validite": 0, "suiveur": 0, "delai": proche(r.delais_regard, 1)}


def choisir_stop(s: dict, cote: torch.Tensor, cible: float = STOP_CIBLE_A, plafond: float | None = PLAFOND_STOP_A):
    """Pour une ouverture AU MARCHÉ du côté `cote` [n] (0 achat, 1 vente ; J = 1) : le niveau de stop (bord lointain
    d'une zone ou sommet / creux, comme cerveau.politique) + la marge dont la distance à l'entrée est la plus proche de
    `cible` agitations, sans dépasser `plafond`. Rend (possible [n], numéro du stop [n], numéro de la marge [n],
    distance [n] en agitations)."""
    from collapsar.ecole.precision import cerveau as C
    nv = C.niveaux(s)
    n = cote.shape[0]
    ar = torch.arange(n, device=cote.device)
    sN = nv["stop"][ar, 0, cote]                                   # [n, Cn]
    ok = nv["stop_ok"][ar, 0, cote]
    p, A = s["p"][:, 0], s["A"][:, 0]
    frais = 2 * s["demi"][:, 0] * p
    sig = 1.0 - 2.0 * cote.float()
    d = sig[:, None] * (p[:, None] - sN)
    ok = ok & (d > frais[:, None]) & torch.isfinite(d)
    marges = C.constantes(cote.device)["marges"]
    dt = d[..., None] + marges[None, None, :] * A[:, None, None]   # [n, Cn, nm]
    ok2 = ok[..., None].expand_as(dt)
    if plafond is not None:
        ok2 = ok2 & (dt <= plafond * A[:, None, None])
        ok2 = ok2 & (d[..., None] <= plafond * A[:, None, None])
    score = torch.where(ok2, (dt - cible * A[:, None, None]).abs(), torch.full_like(dt, float("inf")))
    flat = score.reshape(n, -1)
    best = flat.argmin(1)
    possible = torch.isfinite(flat.gather(1, best[:, None]).squeeze(1))
    nm = dt.shape[-1]
    i_stop, i_marge = best // nm, best % nm
    dist = dt.reshape(n, -1).gather(1, best[:, None]).squeeze(1) / A.clamp(min=1e-12)
    return possible, i_stop, i_marge, dist


class Professeur:
    """Gold Reaper aux commandes de B comptes (J = 1) : son calendrier, son côté (retourné sur l'or retourné)."""

    def __init__(self, cal: dict, risque_idx: np.ndarray, miroir: np.ndarray, plafond: float | None = PLAFOND_STOP_A,
                 cible: float = STOP_CIBLE_A):
        self.te, self.tx = cal["te"], cal["tx"]
        self.sens, self.couverte = cal["sens"], cal["couverte"]
        self.ordre = np.argsort(self.te, kind="stable")
        self.te_tri = self.te[self.ordre]
        self.risque_idx = np.asarray(risque_idx, np.int64)
        self.miroir = np.asarray(miroir, bool)
        B = len(miroir)
        self.grp = np.full(B, -1, np.int64)       # position (de Gold Reaper) tenue par chaque compte
        self.fait = np.full(B, -1, np.int64)      # dernière position ouverte (jamais rouverte)
        self.plafond, self.cible = plafond, cible
        self.impossibles = 0

    def decider(self, tb, qui: np.ndarray, s: dict, net) -> tuple[dict, np.ndarray, np.ndarray]:
        """(choix [n, 1] comme cerveau.politique, rôle de chaque regard (ROLES), position de Gold Reaper concernée)."""
        from collapsar.ecole.precision import cerveau as C
        c = tb.cpt
        dev = s["p"].device
        n = len(qui)
        t = c.t[qui]
        a_pos = c.u[qui, 0] != 0
        a_att = c.att[qui, 0] != 0
        geste = np.full(n, C.GARDER, np.int64)
        role = np.zeros(n, np.int64)
        gid = np.full(n, -1, np.int64)
        # en position : fermer au regard de sa sortie, sinon tenir
        tenue = a_pos & (self.grp[qui] >= 0)
        g_t = self.grp[qui]
        ferme = tenue & (t >= self.tx[np.clip(g_t, 0, None)])
        geste[ferme] = C.FERMER
        role[tenue] = 3
        role[ferme] = 2
        gid[tenue] = g_t[tenue]
        self.grp[qui[~a_pos]] = -1                                      # position finie (stop, fin de challenge)
        # à plat : ouvrir s'il ouvre maintenant (au plus RETARD_MAX bougies de retard), jamais deux fois
        k = np.searchsorted(self.te_tri, t, side="right") - 1
        g_c = np.where(k >= 0, self.ordre[np.clip(k, 0, None)], -1)
        ouvrir = (~a_pos) & (~a_att) & (g_c >= 0)
        gc_ = np.clip(g_c, 0, None)
        ouvrir &= (t - self.te[gc_] <= RETARD_MAX) & (t < self.tx[gc_]) & (g_c > self.fait[qui]) & self.couverte[gc_]
        ix = numeros()
        z = lambda v=0: torch.full((n, 1), int(v), dtype=torch.long, device=dev)
        choix = {"geste": None, "entree": z(), "stop": z(), "marge": z(), "dest": z(), "tp1": z(), "part": z(),
                 "risque": z(), "validite": z(ix["validite"]), "delai": torch.full((n,), ix["delai"], dtype=torch.long, device=dev)}
        if getattr(net, "n_suiv", 0):
            choix["suiveur"] = z(ix["suiveur"])
        if ouvrir.any():
            sens = self.sens[gc_] * np.where(self.miroir[qui], -1, 1)
            cote = torch.as_tensor((sens < 0).astype(np.int64), device=dev)
            possible, i_stop, i_marge, _ = choisir_stop(s, cote, self.cible, self.plafond)
            pos_np = possible.cpu().numpy()
            self.impossibles += int((ouvrir & ~pos_np).sum())
            ouvrir &= pos_np
            o = torch.as_tensor(ouvrir, device=dev)
            geste = np.where(ouvrir, np.where(sens > 0, C.ACHAT_M, C.VENTE_M), geste)
            choix["stop"] = torch.where(o, i_stop, choix["stop"][:, 0])[:, None]
            choix["marge"] = torch.where(o, i_marge, choix["marge"][:, 0])[:, None]
            choix["dest"] = torch.where(o[:, None], z(ix["courir"]), choix["dest"])
            choix["tp1"] = torch.where(o[:, None], z(ix["tp1"]), choix["tp1"])
            choix["part"] = torch.where(o[:, None], z(ix["part"]), choix["part"])
            ri = torch.as_tensor(self.risque_idx[gc_], device=dev)
            choix["risque"] = torch.where(o, ri, choix["risque"][:, 0])[:, None]
            b_o = qui[ouvrir]
            self.grp[b_o] = g_c[ouvrir]
            self.fait[b_o] = g_c[ouvrir]
            role[ouvrir] = 1
            gid[ouvrir] = g_c[ouvrir]
        choix["geste"] = torch.as_tensor(geste, device=dev)[:, None]
        return choix, role, gid


# ============================================================================================== le rejeu
def univers(p: pd.DataFrame, appareil: str = "cpu", marche: str = MARCHE, de=None, jusqua=None):
    from collapsar.ecole.precision.univers import Univers
    de = pd.Timestamp(de) if de is not None else (p.t_ouv.min() - pd.Timedelta(days=7)).normalize()
    jusqua = pd.Timestamp(jusqua) if jusqua is not None else COUPURE
    return Univers([(marche, False), (marche, True)], de, jusqua, appareil)


@torch.no_grad()
def rejouer(U, net, p: pd.DataFrame, cal: dict, risque_idx: np.ndarray, B: int = 16, dire=print,
            plafond: float | None = PLAFOND_STOP_A, cible: float = STOP_CIBLE_A, garder: bool = True) -> dict:
    """Gold Reaper tient B comptes (moitié or réel, moitié or retourné, départs étalés sur 61 jours, challenges enchaînés
    jusqu'à la fin du monde). Rend ses regards (ce que la branche VOIT, ses choix, rôle, jour) et ses trades rejoués."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import journal_trading as JN
    from collapsar.ecole.precision import simulateur as SIM
    net.eval()
    tb = JEU.Table(U, B, 1)
    JN.equiper(tb, net, "ecole")
    c = tb.cpt
    h = B // 2
    cols = np.r_[np.zeros(h, np.int64), np.ones(B - h, np.int64)][:, None]
    miroir = cols[:, 0] == 1
    t0 = int(max(U.premier[0], U.premier[1]))
    d0 = pd.Timestamp(int(U.t_ns[t0]))
    dep = np.array([U.instant(d0 + pd.Timedelta(days=61.0 * (k % h) / h)) for k in range(B)], np.int64)
    tb.demarrer(np.ones(B, bool), cols, dep)
    prof = Professeur(cal, risque_idx, miroir, plafond, cible)
    mem, trades, ouverts = [], [], {}
    st = {"regards": 0, "ouvertures": 0, "fermer": 0, "refus": 0, "murs": 0, "coupees": 0, "lp_min": 0.0}
    fin = U.T - 2
    tdeb = time.time()
    k = 0
    while c.actif.any():
        qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
        if len(qui):
            t, cl, fc, pos = tb.entrees(qui)
            s = tb.vue.structure(t, cl)
            car, pos_plein, q = JEU.yeux_complets(tb, s, t, pos, torch.as_tensor(np.asarray(qui, np.int64), device=t.device), net)
            choix, role, gid = prof.decider(tb, qui, s, net)
            fm = torch.cat([car, pos_plein], -1)
            _, lp, *_, lv = C.politique(net, s, fm, fc, pos_plein, choix)
            st["lp_min"] = min(st["lp_min"], float(lp.min()))
            if tb.carnet is not None:
                tb.carnet.retenir(qui, choix, q, len(qui))
            g = JEU.niveaux_np(JEU.paquet_niveaux(lv))
            tb.appliquer(qui, g)
            st["regards"] += len(qui)
            st["ouvertures"] += int((role == 1).sum())
            st["fermer"] += int((role == 2).sum())
            if garder:
                mem.append({"t": t.cpu(), "cols": cl.cpu(), "fc": fc.cpu(), "pos": pos_plein.cpu(),
                            "choix": {kk: v.cpu() for kk, v in choix.items()}, "role": torch.as_tensor(role),
                            "gid": torch.as_tensor(gid), "b": torch.as_tensor(qui)})
        _, fini, actifs = tb.avancer()
        ev = c.evt[:, 0]
        for b in np.flatnonzero((ev & SIM.OUVERTE) != 0):
            ouverts[int(b)] = {"b": int(b), "g": int(prof.grp[b]), "miroir": bool(miroir[b]), "t_ouv": int(c.t[b]),
                               "entree": float(c.entree[b, 0]), "u": float(c.u[b, 0]), "risque": float(c.risque[b, 0]),
                               "stop": float(c.stop[b, 0]), "A": float(U.A[c.t[b], c.col[b, 0]])}
        for b in np.flatnonzero((ev & SIM.REFUS) != 0):
            st["refus"] += 1
            trades.append({"b": int(b), "g": int(prof.grp[b]), "miroir": bool(miroir[b]), "fin": "refus"})
            prof.grp[b] = -1
        for b in np.flatnonzero(np.isfinite(c.r_ferme[:, 0])):
            x = ouverts.pop(int(b), None)
            if x is None:
                continue
            e = int(ev[b])
            x.update({"r": float(c.r_ferme[b, 0]), "pnl": float(c.r_ferme[b, 0] * x["risque"]), "t_ferm": int(c.t[b]),
                      "fin": "main" if e & SIM.ELLE else "stop" if e & SIM.STOP else "autre"})
            trades.append(x)
        if fini.any():
            for b in np.flatnonzero(fini):
                x = ouverts.pop(int(b), None)
                if x is not None:                                        # mur ou fin de challenge en position
                    x["fin"] = "mur" if c.mort[b] and not c.inactif[b] else "coupee"
                    st["murs" if x["fin"] == "mur" else "coupees"] += 1
                    trades.append(x)
            i = np.flatnonzero(fini)
            prof.grp[i] = -1
            encore = i[c.t[i] < fin - 96]
            c.actif[np.setdiff1d(i, encore)] = False
            if len(encore):
                m = np.zeros(B, bool)
                m[encore] = True
                tb.demarrer(m, cols[encore], c.t[encore].copy())
        c.actif &= c.t < fin
        k += 1
        if k % 2000 == 0:
            dire(f"  rejeu : bougie {k} ({pd.Timestamp(int(U.t_ns[min(int(c.t.max()), U.T - 1)])):%d/%m/%Y}), "
                 f"{st['regards']} regards, {st['ouvertures']} ouvertures ({time.time() - tdeb:.0f} s)")
    st["impossibles"] = prof.impossibles
    out = {"stats": st, "trades": trades}
    if garder and mem:
        out["memoire"] = {kk: torch.cat([m_[kk] for m_ in mem]) for kk in ("t", "cols", "fc", "pos", "role", "gid", "b")}
        out["memoire"]["choix"] = {kk: torch.cat([m_["choix"][kk] for m_ in mem]) for kk in mem[0]["choix"]}
        out["memoire"]["miroir"] = out["memoire"]["cols"][:, 0] == 1
    return out


def etiqueter(m: dict, U, p: pd.DataFrame, test_siens: set, test_autres: set) -> torch.Tensor:
    """Regard de TEST ? Dans une de ses positions : la classe du jour où il l'a ouverte ; à plat : celle du jour."""
    tn = np.asarray(U.t_ns, np.int64)
    jour_regard = pd.DatetimeIndex(tn[m["t"].numpy()]).normalize()
    tests = test_siens | test_autres
    test = np.asarray([d in tests for d in jour_regard])
    gid = m["gid"].numpy()
    jg = np.asarray([d in test_siens for d in p.jour])
    dans = gid >= 0
    test[dans] = jg[gid[dans]]
    return torch.as_tensor(test)


def fidelite(rej: dict, p: pd.DataFrame, cal: dict, risque_idx: np.ndarray) -> dict:
    """Ses positions rejouées par le simulateur de l'arbre (or réel) contre ses vrais résultats (frais FTMO) :
    $/once, part gagnante, et à TAILLE ÉGALE (même risque, même stop) la somme en % d'un compte de 100 000 $."""
    rp = np.asarray(R().mains.risques_pct, float)
    tr = [x for x in rej["trades"] if not x["miroir"] and x.get("g", -1) >= 0]
    par_g = {}
    for x in tr:                                     # le premier compte qui l'a jouée jusqu'au bout
        if x["g"] not in par_g or (par_g[x["g"]]["fin"] not in ("main", "stop") and x["fin"] in ("main", "stop")):
            par_g[x["g"]] = x
    cov = np.flatnonzero(cal["couverte"])
    lignes = []
    for g in cov:
        x = par_g.get(int(g))
        y = {"g": int(g), "sens": int(p.sens.iloc[g]), "move_lui": float(p.move_ftmo.iloc[g]), "jour": str(p.jour.iloc[g].date()),
             "risque_pct": float(rp[risque_idx[g]]), "fin": x["fin"] if x else "absente"}
        if x and x["fin"] in ("main", "stop"):
            d = abs(x["entree"] - x["stop"])
            y.update({"move_rejeu": x["pnl"] / abs(x["u"]), "r_rejeu": x["r"], "stop_dist": d, "stop_A": d / x["A"],
                      "r_lui": float(p.move_ftmo.iloc[g]) / d})
        lignes.append(y)
    L = pd.DataFrame(lignes)
    j = L[L.fin.isin(["main", "stop"])]
    out = {"positions_rejouables": int(len(cov)), "rejouees": int(len(j)),
           "fins": L.fin.value_counts().to_dict(),
           "stoppees_avant_sa_sortie_pct": float(100 * (j.fin == "stop").mean()) if len(j) else float("nan")}
    if len(j):
        out.update({
            "move_lui_moyen": float(j.move_lui.mean()), "move_rejeu_moyen": float(j.move_rejeu.mean()),
            "gagnantes_lui_pct": float(100 * (j.move_lui > 0).mean()), "gagnantes_rejeu_pct": float(100 * (j.move_rejeu > 0).mean()),
            "meme_signe_pct": float(100 * (np.sign(j.move_lui) == np.sign(j.move_rejeu)).mean()),
            "lien": float(np.corrcoef(j.move_lui, j.move_rejeu)[0, 1]) if len(j) > 2 else float("nan"),
            "stop_A_median": float(j.stop_A.median()), "stop_dollars_median": float(j.stop_dist.median()),
            "somme_pct_lui": float((j.r_lui * j.risque_pct).sum()), "somme_pct_rejeu": float((j.r_rejeu * j.risque_pct).sum()),
            "r_moyen_lui": float(j.r_lui.mean()), "r_moyen_rejeu": float(j.r_rejeu.mean())})
        out["part_retrouvee_pct"] = (100 * out["somme_pct_rejeu"] / out["somme_pct_lui"]) if out["somme_pct_lui"] > 0 else float("nan")
        for nom, msk in (("avant_04_2025", pd.to_datetime(j.jour) < "2025-04-01"), ("depuis_04_2025", pd.to_datetime(j.jour) >= "2025-04-01")):
            x = j[msk]
            if len(x):
                out[nom] = {"positions": int(len(x)), "somme_pct_lui": float((x.r_lui * x.risque_pct).sum()),
                            "somme_pct_rejeu": float((x.r_rejeu * x.risque_pct).sum()),
                            "move_lui_moyen": float(x.move_lui.mean()), "move_rejeu_moyen": float(x.move_rejeu.mean())}
    out["detail"] = L.to_dict("records")
    return out


# ============================================================================================== imitation
def _vue(U):
    from types import SimpleNamespace
    from collapsar.ecole.precision.vue import Vue
    return SimpleNamespace(vue=Vue(U), dev=U.dev)


def lot(table, m: dict, i: torch.Tensor):
    """(structure, entrées du cerveau, choix, compte, position) pour les regards i (sur l'appareil du monde)."""
    dev = table.dev
    t, cl = m["t"][i].to(dev), m["cols"][i].to(dev)
    s = table.vue.structure(t, cl)
    pos = m["pos"][i].to(dev)
    fm = torch.cat([table.vue.caracteristiques(s), pos], -1)
    return s, fm, {k: v[i].to(dev) for k, v in m["choix"].items()}, m["fc"][i].to(dev), pos


@torch.no_grad()
def accord(net, table, m: dict, idx: torch.Tensor, paquet: int = 2048, graine: int = 0) -> dict:
    """Ce qu'elle ferait (ses tirages, et son geste le plus probable) aux regards `idx` de Gold Reaper, par rôle :
    à plat quand il ne fait rien / quand il ouvre (même geste, même sens), en position quand il tient / quand il ferme ;
    quand les deux ouvrent pareil : même stop, marge, risque, destination, part ; et combien d'ouvertures elle FERAIT
    (somme des probabilités d'ouvrir) contre les siennes."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import mentor as MT
    net.eval()
    tot: dict = {}
    add = lambda k, v: tot.__setitem__(k, tot.get(k, 0.0) + float(v))
    gen = torch.random.fork_rng(devices=[table.dev] if table.dev.type == "cuda" else [])
    with gen:
        torch.manual_seed(graine)
        net.voir_lois = True
        try:
            for d in range(0, len(idx), paquet):
                i = idx[d:d + paquet]
                s, fm, cm, fc, pos = lot(table, m, i)
                ch, _, _, _, _, lv = C.politique(net, s, fm, fc, pos, None)
                _, lpm, *_ = C.politique(net, s, fm, fc, pos, cm)
                role = m["role"][i].to(table.dev)
                gm, gt = cm["geste"][:, 0], ch["geste"][:, 0]
                lpg = lv["lp_geste"][:, 0]
                gp = lpg.argmax(-1)
                ouv = lambda g: (g >= C.ACHAT_M) & (g <= C.VENTE_L)
                vend = lambda g: (g == C.VENTE_M) | (g == C.VENTE_L)
                p_ouv = lpg.exp()[:, C.ACHAT_M:C.VENTE_L + 1].sum(-1)
                add("regards", len(i))
                add("geste_probable", (gp == gm).sum())
                add("geste_tire", (gt == gm).sum())
                add("nll", -lpm.clamp(min=MT.PLANCHER_LP).sum())
                for k, r_ in enumerate(ROLES):
                    w = role == k
                    add(f"n_{r_}", w.sum())
                    add(f"tire_{r_}", ((gt == gm) & w).sum())
                    add(f"probable_{r_}", ((gp == gm) & w).sum())
                plat = (role == 0) | (role == 1)
                add("p_ouvrir_plat", (p_ouv * plat).sum())
                w1 = role == 1
                add("meme_sens_ouvre", (w1 & ouv(gt) & (vend(gt) == vend(gm))).sum())
                deux = w1 & (gt == gm)
                add("deux", deux.sum())
                for k in ("stop", "marge", "risque", "dest", "part"):
                    add(f"m_{k}", ((ch[k][:, 0] == cm[k][:, 0]) & deux).sum())
        finally:
            net.voir_lois = False
    q = lambda a, b: 100.0 * tot.get(a, 0.0) / max(tot.get(b, 0.0), 1.0)
    out = {"regards": int(tot["regards"]), "geste_le_plus_probable_pct": q("geste_probable", "regards"),
           "geste_tire_pct": q("geste_tire", "regards"), "perte_par_regard": tot["nll"] / max(tot["regards"], 1.0),
           "ouvertures_lui": int(tot.get("n_ouvre", 0)), "ouvertures_elle_attendues": tot.get("p_ouvrir_plat", 0.0),
           "quand_il_ouvre_meme_sens_pct": q("meme_sens_ouvre", "n_ouvre")}
    for r_ in ROLES:
        out[f"quand_il_{r_}"] = {"regards": int(tot.get(f"n_{r_}", 0)), "tire_pct": q(f"tire_{r_}", f"n_{r_}"),
                                 "probable_pct": q(f"probable_{r_}", f"n_{r_}")}
    out["quand_les_deux_ouvrent_pareil"] = {"n": int(tot.get("deux", 0)),
                                            **{f"{k}_pct": q(f"m_{k}", "deux") for k in ("stop", "marge", "risque", "dest", "part")}}
    return out


def imiter(net, table, m: dict, appris: torch.Tensor, test: torch.Tensor, epoques: int = 4, paquet: int = 1024,
           vitesse: float = 1e-4, graine: int = GRAINE, dire=print) -> dict:
    """Phase (a) : elle apprend à donner la plus forte probabilité à ses gestes, sur les regards des jours APPRIS ;
    accord mesuré avant et après sur les jours de TEST (jamais appris) et après sur les jours appris."""
    from collapsar.ecole.precision import mentor as MT
    idx_a = torch.nonzero(appris).squeeze(1)
    idx_t = torch.nonzero(test).squeeze(1)
    avant = accord(net, table, m, idx_t)
    dire(f"  accord AVANT (jours de test) : {_ligne_accord(avant)}")
    opt = torch.optim.AdamW(net.parameters(), lr=vitesse, weight_decay=1e-4)
    g = torch.Generator().manual_seed(graine)
    hist = []
    for ep in range(epoques):
        net.train()
        ordre = idx_a[torch.randperm(len(idx_a), generator=g)]
        pertes, hors = [], 0
        t0 = time.time()
        for d in range(0, len(ordre), paquet):
            i = ordre[d:d + paquet]
            s, fm, cm, fc, pos = lot(table, m, i)
            perte, h = MT.perte_imitation(net, s, fm, fc, pos, cm)
            opt.zero_grad(set_to_none=True)
            perte.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            pertes.append(float(perte))
            hors += h
        x = accord(net, table, m, idx_t, graine=ep + 1)
        hist.append({"epoque": ep + 1, "perte_debut": pertes[0], "perte_fin": float(np.mean(pertes[-20:])),
                     "choix_impossibles": hors, "accord_test": x, "duree_s": time.time() - t0})
        dire(f"  époque {ep + 1}/{epoques} ({time.time() - t0:.0f} s) : perte {pertes[0]:.3f} -> {np.mean(pertes[-20:]):.3f}, "
             f"impossibles {hors} | test : {_ligne_accord(x)}")
    apres_a = accord(net, table, m, idx_a[torch.randperm(len(idx_a), generator=g)[:min(len(idx_a), 120_000)]], graine=99)
    return {"avant_test": avant, "apres_test": hist[-1]["accord_test"] if hist else avant, "apres_appris": apres_a,
            "epoques": hist, "regards_appris": int(len(idx_a)), "regards_test": int(len(idx_t)),
            "reglages": {"epoques": epoques, "paquet": paquet, "vitesse": vitesse, "graine": graine}}


def _ligne_accord(a: dict) -> str:
    return (f"geste {a['geste_le_plus_probable_pct']:.1f} % (tiré {a['geste_tire_pct']:.1f} %), il ouvre ({a['ouvertures_lui']}) -> "
            f"elle pareil {a['quand_il_ouvre']['tire_pct']:.0f} % / même sens {a['quand_il_ouvre_meme_sens_pct']:.0f} % ; "
            f"elle ouvrirait {a['ouvertures_elle_attendues']:.0f} fois ; il ferme -> {a['quand_il_ferme']['tire_pct']:.0f} % ; "
            f"rien -> {a['quand_il_rien']['tire_pct']:.1f} % ; tient -> {a['quand_il_tient']['tire_pct']:.1f} % ; "
            f"perte {a['perte_par_regard']:.3f}")


# ============================================================================================== la branche
def est_gold_reaper(temperament) -> bool:
    return isinstance(temperament, dict) and isinstance(temperament.get("maitre"), dict)


def laisse(temperament: dict, generation: int) -> float:
    m = (temperament or {}).get("maitre") if isinstance(temperament, dict) else None
    if not isinstance(m, dict):
        return 0.0
    k = max(0, int(generation) - int(m.get("nee_a", generation)))
    return float(m.get("laisse_depart", LAISSE_DEPART)) * float(m.get("relache", LAISSE_RELACHE)) ** k


def temperament_branche(t_mere: dict, mere: str, lecons: Path, nee_a: int, info: dict | None = None) -> dict:
    """Le tempérament de la mère (la cime) + cerveau symétrique + stops jusqu'à 0,75 agitation + Gold Reaper."""
    t = {k: v for k, v in dict(t_mere).items() if k not in ("alertes", "mentor")}
    t.update({"nom": NOM_BRANCHE,
              "symetrique": {"version": 1, "geste": "rien/fermer = moyenne x et miroir(x)"},
              "precision": {"stop_max_agitation": PLAFOND_STOP_A},
              "maitre": {"nom": NOM_MAITRE, "signal": SIGNAL, "version": VERSION, "laisse_depart": LAISSE_DEPART,
                         "relache": LAISSE_RELACHE, "nee_a": int(nee_a), "lecons": str(Path(lecons).resolve()),
                         "controle_2024_2025": "NON VALABLE (elle a appris ses trades 10/2024 -> 09/2025)",
                         **(info or {})},
              "jeunesse": JEUNESSE,
              "heritage": f"cime {mere}, imite Gold Reaper ({SIGNAL}) puis récompense en laisse ; cerveau symétrique ; "
                          f"stops <= {PLAFOND_STOP_A} agitation ; contrôle 2024-2025 non valable"})
    return t


def cerveau_branche(etat_mere: dict, t: dict, appareil: str = "cpu"):
    from collapsar.ecole.precision import cerveau as C
    net = C.cerveau_pour(etat_mere, _delai(t))
    C.regler_precision(net, t)
    C.regler_symetrie(net, t)
    return net.to(appareil)


def _delai(t: dict) -> str:
    from collapsar.ecole.precision import journal_trading as JN
    return JN.delai_branche(t)


# ============================================================================================== dans le cœur
_ECOLE: dict = {}


def ecole(t: dict, dev) -> dict:
    """Ses leçons (regards des jours APPRIS) et le monde 10/2024 -> 09/2025 qui va avec, chargés une fois par appareil."""
    f = Path(t["maitre"]["lecons"])
    cle = (str(f), str(dev))
    if cle not in _ECOLE:
        x = torch.load(f, map_location="cpu", weights_only=False)
        meta = x["meta"]
        from collapsar.ecole.precision.univers import Univers
        U = Univers([tuple(v) for v in meta["variantes"]], pd.Timestamp(meta["de"]), pd.Timestamp(meta["jusqua"]), str(dev))
        if U.T != meta["T"] or int(U.t_ns[0]) != meta["t0"] or int(U.t_ns[-1]) != meta["t1"]:
            raise ValueError("gold_reaper : le monde rebâti ne correspond pas à celui des leçons")
        m = x["memoire"]
        idx = torch.nonzero(~m["test"]).squeeze(1)
        _ECOLE.clear()
        _ECOLE[cle] = {"table": _vue(U), "m": m, "idx": idx, "U": U}
    return _ECOLE[cle]


def apprendre_en_laisse(br, table, m: dict, generation: int, e) -> dict:
    """Phase (b), dans le cœur : son apprentissage habituel (PPO, comme jeu.apprendre) + le rappel de Gold Reaper sur
    SES regards (jours appris seulement), pesé par la laisse de cette génération. Les tirages de ses lots de Gold Reaper
    ont leur propre générateur (le hasard des autres branches n'est pas touché)."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import mentor as MT
    net, opt = br.net, br.opt
    lam = laisse(br.t, generation)
    curiosite = br.t.get("curiosite", e.curiosite)
    N = len(m["lp"])
    adv = (m["adv"] - m["adv"].mean()) / (m["adv"].std() + 1e-8)
    sans = m["sans"].float()
    lp_vieux = m["lp"] - (m["lp_exec"] * sans).sum(-1)
    ec = ecole(br.t, table.dev) if lam > 1e-4 else None
    gen = torch.Generator().manual_seed(GRAINE + int(generation) * 1009 + int(N))
    net.train()
    b = {"perte_decision": 0.0, "perte_valeur": 0.0, "hasard": 0.0, "perte_mentor": 0.0}
    nb = 0
    dev = m["lp"].device
    for _ in range(e.epoques):
        ordre = torch.randperm(N, device=dev)
        for d in range(0, N, e.paquet):
            i = ordre[d:d + e.paquet]
            s = table.vue.structure(m["t"][i], m["cols"][i])
            fm = torch.cat([table.vue.caracteristiques(s), m["pos"][i]], -1)
            choix = {k: v[i] for k, v in m["choix"].items()}
            _, lp, lp_exec, hasard, valeur, _ = C.politique(net, s, fm, m["fc"][i], m["pos"][i], choix)
            lp = lp - (lp_exec * sans[i]).sum(-1)
            ratio = (lp - lp_vieux[i]).clamp(-20, 20).exp()
            p1, p2 = ratio * adv[i], ratio.clamp(1 - e.coupe, 1 + e.coupe) * adv[i]
            perte_dec = -torch.min(p1, p2).mean()
            perte_v = torch.nn.functional.huber_loss(valeur, m["ret"][i])
            perte = perte_dec + 0.5 * perte_v - curiosite * hasard.mean()
            if ec is not None:
                j = ec["idx"][torch.randint(len(ec["idx"]), (min(e.paquet, len(ec["idx"])),), generator=gen)]
                s2, fm2, cm2, fc2, pos2 = lot(ec["table"], ec["m"], j)
                pm, _ = MT.perte_imitation(net, s2, fm2, fc2, pos2, cm2)
                perte = perte + lam * pm
                b["perte_mentor"] += float(pm)
            opt.zero_grad(set_to_none=True)
            perte.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
            opt.step()
            b["perte_decision"] += float(perte_dec)
            b["perte_valeur"] += float(perte_v)
            b["hasard"] += float(hasard.mean())
            nb += 1
    out = {k: v / max(nb, 1) for k, v in b.items()} | {"regards_appris": N, "laisse": lam}
    out["accord_geste_pct"] = float("nan")
    if ec is not None:                               # accord du geste sur un lot fixe de ses regards appris
        j = ec["idx"][torch.randint(len(ec["idx"]), (min(2048, len(ec["idx"])),), generator=torch.Generator().manual_seed(GRAINE))]
        a = accord(net, ec["table"], ec["m"], j, graine=int(generation))
        out["accord_geste_pct"] = a["geste_le_plus_probable_pct"]
        out["accord_il_ouvre_pct"] = a["quand_il_ouvre"]["tire_pct"]
        net.train()
    return out


# ============================================================================================== préparation (rien n'est greffé)
def _allumer(dossier: Path):
    from collapsar.ecole.precision import mentor as MT
    MT._allumer(dossier)


def preparer(dossier: Path, sortie_dossier: Path, appareil: str, B: int = 16, epoques: int = 4, mere: str | None = None,
             trades: pd.DataFrame | None = None, marche: str = MARCHE, de=None, jusqua=None, dire=print) -> dict:
    """Une COPIE de la cime (fichier de l'arbre, jamais modifié) -> branche Gold Reaper : rejeu de ses positions par le
    simulateur (fidélité), leçons (regards de ses journées), imitation ; fichiers dans `sortie_dossier` :
    lecons.pt (ses regards), branche.pt (cerveau + tempérament), mesures.json."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.ecole.precision import cerveau as C
    sortie_dossier = Path(sortie_dossier)
    sortie_dossier.mkdir(parents=True, exist_ok=True)
    arbre = Arbre.charger(Path(dossier) / "arbre.json")
    mere = mere or arbre.cime
    e = torch.load(Path(dossier) / "branches" / f"{mere}.pt", map_location="cpu", weights_only=False)
    gen = arbre.battements
    if trades is None:
        trades, _ = charger_trades()
    p = positions(trades)
    t0 = time.time()
    U = univers(p, appareil, marche, de, jusqua)
    fin_or = pd.Timestamp(int(U.t_ns[-1])) + pd.Timedelta(minutes=15)
    dire(f"Gold Reaper : {len(trades)} trades d'or fermés avant le {COUPURE:%d/%m/%Y} -> {len(p)} positions ; monde "
         f"{U.de:%d/%m/%Y} -> {fin_or:%d/%m/%Y %H:%M} ({U.T} bougies, {time.time() - t0:.0f} s)")
    cal = calendrier(U, p)
    test_siens, test_autres = jours_de_test(p, U.de, fin_or)
    appris_g = np.asarray([d not in test_siens for d in p.jour]) & cal["couverte"]
    ri = risques(p, appris_g)
    t = temperament_branche(e.get("temperament") or arbre.branches[mere].temperament, mere,
                            sortie_dossier / LECONS, gen)
    torch.manual_seed(GRAINE)
    net = cerveau_branche(e["cerveau"], t, appareil)
    dire(f"branche née de {mere} (génération {gen}) : forme {C.forme(net.state_dict())}, symétrique {net.symetrique}, "
         f"stops <= {net.stop_max_agitation} agitation ; {int(cal['couverte'].sum())} positions rejouables "
         f"(or à la minute jusqu'au {fin_or:%d/%m/%Y}), jours de test : {len(test_siens)} des siens + {len(test_autres)} autres")
    rej = rejouer(U, net, p, cal, ri, B, dire)
    dire(f"rejeu fait : {json.dumps(rej['stats'], ensure_ascii=False)}")
    fid = fidelite(rej, p, cal, ri)
    dire("FIDÉLITÉ : " + json.dumps({k: v for k, v in fid.items() if k != "detail"}, ensure_ascii=False, default=float))
    m = rej["memoire"]
    m["test"] = etiqueter(m, U, p, test_siens, test_autres)
    meta = {"variantes": [list(v) for v in U.variantes], "de": str(U.de), "jusqua": str(U.jusqua), "T": int(U.T),
            "t0": int(U.t_ns[0]), "t1": int(U.t_ns[-1]), "version": VERSION, "mere": mere, "generation_mere": gen,
            "forme": {k: (list(v) if isinstance(v, tuple) else v) for k, v in C.forme(net.state_dict()).items()},
            "stop_cible_A": STOP_CIBLE_A, "plafond_stop_A": PLAFOND_STOP_A, "B": B,
            "jours_test_siens": sorted(str(d.date()) for d in test_siens)}
    torch.save({"memoire": m, "meta": meta}, sortie_dossier / LECONS)
    dire(f"leçons écrites : {sortie_dossier / LECONS} ({len(m['t'])} regards, dont test {int(m['test'].sum())})")
    tb = _vue(U)
    im = imiter(net, tb, m, ~m["test"], m["test"], epoques=epoques, dire=dire)
    resume = {"positions": int(len(p)), "positions_rejouables": int(cal["couverte"].sum()),
              "trades": int(len(trades)), "fin_or": str(fin_or), "jours_siens": int(p.jour.nunique()),
              "jours_test_siens": len(test_siens), "rejeu": rej["stats"], "fidelite": fid, "imitation": im,
              "risques_positions": {str(k): int(v) for k, v in zip(*np.unique(np.asarray(R().mains.risques_pct)[ri], return_counts=True))},
              "date": datetime.now().isoformat(timespec="seconds")}
    t["maitre"]["imitation_test"] = {"geste_pct": im["apres_test"]["geste_le_plus_probable_pct"],
                                     "il_ouvre_pct": im["apres_test"]["quand_il_ouvre"]["tire_pct"]}
    torch.save({"cerveau": {k: v.detach().cpu() for k, v in net.state_dict().items()}, "temperament": t, "mere": mere,
                "generation_mere": gen}, sortie_dossier / "branche.pt")
    (sortie_dossier / "mesures.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    dire(f"branche prête : {sortie_dossier / 'branche.pt'} ; mesures : {sortie_dossier / 'mesures.json'}")
    return resume


# ============================================================================================== la greffe
def appliquer(dossier: Path | None, fichier: Path, code_avant: Path | None = None, dire=print) -> dict:
    """La branche Gold Reaper (fichier `branche.pt` de `preparer`) remplace la branche la plus faible hors cime et hors
    apprenties du mentor (archivée). Sauvegarde complète d'abord. Arbre ARRÊTÉ, ARRET en place."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import mentor as MT
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if (dossier / FICHIER).exists():
        raise SystemExit(f"{dossier} : la branche Gold Reaper est déjà greffée ({FICHIER})")
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : créer ARRET et attendre sa fin")
    if not (dossier / "ARRET").exists():
        raise SystemExit(f"{dossier / 'ARRET'} doit être en place pendant la manipulation")
    x = torch.load(fichier, map_location="cpu", weights_only=False)
    t = dict(x["temperament"])
    if not (est_gold_reaper(t) and t.get("symetrique") and Path(t["maitre"]["lecons"]).exists()):
        raise SystemExit(f"{fichier} : pas une branche Gold Reaper prête (ou leçons absentes)")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_gold_reaper_{stamp}"
    shutil.copytree(dossier, sauve / "vie", ignore=shutil.ignore_patterns(
        "journal_trades", "sauvegardes", "precision", "contrefactuel", "symetrique", "mentor", "trois_changements",
        "images", SOUS_DOSSIER))
    if code_avant is not None and Path(code_avant).exists():
        shutil.copytree(code_avant, sauve / "code_avant")
    dire(f"sauvegarde complète : {sauve}")
    arbre = Arbre.charger(dossier / "arbre.json")
    cime = arbre.cime
    proteger = {cime} | {b.nom for b in arbre.vivantes() if MT.est_apprentie(b.temperament) or est_gold_reaper(b.temperament)}
    faible = SV.la_plus_faible(arbre, proteger)
    if faible is None:
        raise SystemExit("aucune branche à remplacer (hors cime et apprenties)")
    mere = x.get("mere") or cime
    if mere not in arbre.branches:
        mere = cime
    dire(f"cime {cime} ; mère {mere} ; protégées {sorted(proteger)} ; remplacée : {faible} (niveau "
         f"{arbre.branches[faible].score:+.2f})")
    journal = Journal(dossier / "journal_croissance.jsonl")
    arbre.mourir(faible, "coupée")
    (dossier / "archives").mkdir(exist_ok=True)
    for f in (f"{faible}.pt", f"{faible}_meilleur.pt"):
        if (dossier / "branches" / f).exists():
            shutil.move(str(dossier / "branches" / f), str(dossier / "archives" / f))
    journal.ecrire("coupe", branche=faible, raison="archivée (place pour la branche Gold Reaper, 20/10)")
    t["maitre"] = {**t["maitre"], "nee_a": int(arbre.battements)}
    net = C.cerveau_pour(x["cerveau"], _delai(t))
    opt = torch.optim.AdamW(net.parameters(), lr=float(t.get("vitesse", R().ecole.vitesse)), weight_decay=1e-4)
    b = arbre.naitre([mere], t)
    tmp = dossier / "branches" / f"{b.nom}.pt.tmp"
    torch.save({"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": t}, tmp)
    os.replace(tmp, dossier / "branches" / f"{b.nom}.pt")
    journal.ecrire("naissance", branche=b.nom, parents=[mere], temperament=t, heritage=t["heritage"])
    arbre._elire_cime()
    arbre.sauver(dossier / "arbre.json")
    fx = dossier / "derniers_examens.json"
    if fx.exists():
        ex = json.loads(fx.read_text(encoding="utf-8"))
        ex.pop(faible, None)
        fx.write_text(json.dumps(ex, ensure_ascii=False, default=float), encoding="utf-8")
    info = {"date": datetime.now().isoformat(timespec="seconds"), "version": VERSION, "branche": b.nom, "mere": mere,
            "cime": cime, "remplacee": faible, "sauvegarde": str(sauve), "fichier": str(fichier),
            "nee_a": int(arbre.battements), "controle_2024_2025": "NON VALABLE pour cette branche et ses filles"}
    journal.ecrire("gold_reaper", **{k: v for k, v in info.items() if k != "date"})
    (dossier / FICHIER).write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    dire(f"branche {b.nom} « {NOM_BRANCHE} » née de {mere} (génération {arbre.battements}) ; {faible} archivée")
    return info


def retirer(dossier: Path | None = None, dire=print):
    """Retour arrière léger (arbre arrêté) : la branche Gold Reaper (et ses filles) archivée(s), l'arbre continue."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : l'arrêter d'abord (fichier ARRET)")
    arbre = Arbre.charger(dossier / "arbre.json")
    journal = Journal(dossier / "journal_croissance.jsonl")
    gr = [b.nom for b in arbre.vivantes() if est_gold_reaper(b.temperament)]
    if gr and len(gr) == len(arbre.vivantes()):
        raise SystemExit("toutes les branches viennent de Gold Reaper : utiliser « defaire »")
    for n in gr:
        arbre.mourir(n, "coupée")
        for f in (f"{n}.pt", f"{n}_meilleur.pt"):
            if (dossier / "branches" / f).exists():
                shutil.move(str(dossier / "branches" / f), str(dossier / "archives" / f))
        journal.ecrire("coupe", branche=n, raison="branche Gold Reaper retirée (retour arrière)")
    arbre._elire_cime()
    arbre.sauver(dossier / "arbre.json")
    (dossier / FICHIER).unlink(missing_ok=True)
    dire(f"branches Gold Reaper archivées : {gr} ; cime {arbre.cime}")


def defaire(dossier: Path | None = None, dire=print):
    """Retour arrière complet (arbre arrêté) : la vie de l'arbre d'avant la greffe (sauvegarde)."""
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : l'arrêter d'abord (fichier ARRET)")
    info = json.loads((dossier / FICHIER).read_text(encoding="utf-8"))
    sauve = Path(info["sauvegarde"]) / "vie"
    shutil.rmtree(dossier / "branches")
    shutil.copytree(sauve / "branches", dossier / "branches")
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl", "note_cotes.json"):
        if (sauve / nom).exists():
            shutil.copy2(sauve / nom, dossier / nom)
    for f in (f"{info['remplacee']}.pt", f"{info['remplacee']}_meilleur.pt"):
        (dossier / "archives" / f).unlink(missing_ok=True)
    (dossier / FICHIER).unlink(missing_ok=True)
    dire(f"branche Gold Reaper défaite : vie remise depuis {sauve}")


# ============================================================================================== commandes
def main(argv=None):
    ap = argparse.ArgumentParser(description="la branche Gold Reaper de MAGNETAR (20/10)")
    ap.add_argument("quoi", choices=["preparer", "appliquer", "retirer", "defaire"])
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--dossier", default=None, help="dossier de vie de l'arbre (défaut : celui des réglages)")
    ap.add_argument("--sortie", default=None, help="dossier des fichiers préparés (défaut : <vie>/gold_reaper)")
    ap.add_argument("--fichier", default=None, help="branche préparée (défaut : <sortie>/branche.pt)")
    ap.add_argument("--code-avant", default=None)
    ap.add_argument("--comptes", type=int, default=16)
    ap.add_argument("--epoques", type=int, default=4)
    ap.add_argument("--carte-max-go", type=float, default=None)
    a = ap.parse_args(argv)
    if a.carte_max_go and a.appareil == "cuda":
        tot = torch.cuda.get_device_properties(0).total_memory / 1e9
        torch.cuda.set_per_process_memory_fraction(min(1.0, a.carte_max_go / tot), 0)
    d = Path(a.dossier) if a.dossier else VIE
    _allumer(d)
    sortie = Path(a.sortie) if a.sortie else d / SOUS_DOSSIER
    if a.quoi == "preparer":
        preparer(d, sortie, a.appareil, a.comptes, a.epoques)
    elif a.quoi == "appliquer":
        appliquer(d, Path(a.fichier) if a.fichier else sortie / "branche.pt", Path(a.code_avant) if a.code_avant else None)
    elif a.quoi == "retirer":
        retirer(d)
    else:
        defaire(d)


if __name__ == "__main__":
    main()
