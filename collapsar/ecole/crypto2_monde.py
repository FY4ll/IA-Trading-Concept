"""L'ÉCOLE CRYPTO n° 2 DE COLLAPSAR (16/10/2026) — question du chef de projet : « COLLAPSAR doit en être capable ».

FIXÉ AVANT TOUT RÉSULTAT (cahier de la séance) :
- Cerveau NEUF (TraderHumain, petit : aucun héritage des mille mondes ni de l'école crypto n° 1).
- Marchés : BTCUSDT et ETHUSDT seulement (bougies Binance 15 min, filtre commun du LISEZMOI = cs._binance via
  crypto_monde.charger) ; leurs MIROIRS (prix retournés) pour l'apprentissage seulement.
- Frais FTMO réels (crypto_monde.fiche_crypto) : BTC 0,083 %, ETH 0,112 % par aller-retour, nuit 30 %/an achat comme
  vente payée chaque nuit, levier 1:1. Murs FTMO, inactivité, 4 jours de trading : ceux du simulateur.
- Ce qu'elle voit EN PLUS des prix : des PROPOSITIONS (informations connues à l'instant de décision, jamais des
  règles ; à elle d'en faire ce qu'elle veut), par marché :
  0 position du prix dans le canal des 24 h (bougie en cours exclue ; 0 = milieu, +-1 = bord, au-delà = cassure ; /3) ;
  1 signal de la cassure C2 du moment (+1 = la cassure 24 h serait acheteuse maintenant, -1 vendeuse, 0 à plat) : règle
     C2 exacte (strategies/cassure.signaux N = 24, sortie au milieu, lun-ven, jours >= 92 bougies, sortie 23h45) ;
  2 part des comptes Binance acheteurs (count_long_short_ratio des perpétuels, retard de sécurité 15 min, comme C1),
     centrée : (part - 0,5) x 4 ;
  3 son rang sur les 90 jours passés (0 = plus bas, 1 = plus haut ; ramené à -1 / +1) ;
  4 signal C1 « contre la foule » du moment (+1 = C1 achèterait / tient un achat 24 h, -1 vente, 0 rien) ;
  5 donnée foule disponible (1) ou non (0) : BTC dès 10/2020, ETH dès 01/2022 seulement (données Binance) ;
  6-7 heure du serveur (sinus, cosinus) ; 8-9 jour de la semaine (sinus, cosinus).
  Sur un miroir : 0 et 1 sont calculés sur les prix retournés ; 2, 3, 4 sont retournés (la foule « inverse »).
- Contre l'habitude de trop trader : le coût de l'aller-retour est déjà dans la récompense (argent du compte, frais
  compris) ; REGARD MINIMUM 1 h : elle ne peut pas revenir regarder moins d'une heure après son dernier regard, même
  réveillée (le réveil attend l'heure). Stops, objectifs, ordres à l'avance et murs restent actifs entre deux regards.
  Rien d'autre d'imposé.
- Années : apprentissage 2018-2021 (mondes d'école SANS aucune bougie de 2022 ou après ; + un monde BTC 10/2020-2021
  où la foule est visible, et son miroir) ; contrôle 2022-2023 (données chargées jusqu'au 31/12/2023 seulement) ;
  évaluation finale 2024-01 -> 2026-09, UNE fois, du meilleur élève (verrou vie/ecole_crypto2/final.json).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import torch
from numba import njit
from torch import nn

from collapsar.cerveau.humain import ACHETER, CHANGER, FERMER, VENDRE, N_VUE_MARCHE_H, TraderHumain
from collapsar.donnees import marches as dm
from collapsar.ecole import crypto_monde as cm
from collapsar.ecole.regard import ClasseRegard, Etat
from collapsar.mains.fiches import MIROIR
from collapsar.mains.horloge import Horloge
from collapsar.mains.simulateur import CAPITAL
from collapsar.strategies import cassure as cs
from collapsar.yeux.faits import calendrier, seances
from collapsar.yeux.graphique import Graphique

VIE = dm.RACINE / "collapsar" / "vie" / "ecole_crypto2"
CACHE = VIE / "cache"
FUT = dm.RACINE / "data" / "binance_futures"
MARCHES = ["BTCUSDT", "ETHUSDT"]
APPRENDRE_DE, FIN_APPRENTISSAGE = pd.Timestamp("2018-01-01"), pd.Timestamp("2022-01-01")
FOULE_DE = pd.Timestamp("2020-10-15")                # monde d'école où la foule BTC est visible
CONTROLE_DE, CONTROLE_JUSQUA = pd.Timestamp("2022-01-01"), pd.Timestamp("2024-01-01")
TEMOIN_DE, TEMOIN_JUSQUA = pd.Timestamp("2018-03-01"), pd.Timestamp("2022-01-01")
FINAL_DE, FINAL_JUSQUA = pd.Timestamp("2024-01-01"), pd.Timestamp("2026-10-01")
DUREE, UN_MOIS = cm.DUREE, cm.UN_MOIS
REGARD_MIN_BOUGIES = 4                               # 1 heure
NOMS_PROP = ["canal 24 h", "cassure C2", "part acheteurs", "rang 90 j", "foule C1", "foule dispo",
             "heure sin", "heure cos", "jour sin", "jour cos"]
N_PROP = len(NOMS_PROP)
I_CANAL, I_C2, I_PART, I_RANG, I_C1, I_DISPO = range(6)
RETOURNES = (I_PART, I_RANG, I_C1)                   # retournés sur un miroir (0 et 1 : calculés sur les prix retournés)
W90 = 90 * 24


# ============================================================================== les propositions
def _matrice_df(df: pd.DataFrame) -> dict:
    """Journées x 96 quarts d'heure, lun-ven, jours >= 92 bougies : même construction que cassure.matrice, mais à
    partir d'un tableau déjà chargé (pour pouvoir la faire aussi sur les prix retournés)."""
    t = pd.to_datetime(df["time"])
    jour = t.dt.normalize()
    jours = pd.date_range(jour.min(), jour.max(), freq="D")
    i = ((jour - jours[0]).dt.days).to_numpy()
    k = (t.dt.hour * 4 + t.dt.minute // 15).to_numpy()
    O, H, L, C = (np.full((len(jours), 96), np.nan) for _ in range(4))
    for X, col in ((O, "open"), (H, "high"), (L, "low"), (C, "close")):
        X[i, k] = df[col].to_numpy(np.float64)
    nb = np.isfinite(C).sum(1)
    valide = np.asarray(jours.dayofweek < 5) & (nb >= cs.BARRES_MIN)
    Cf = pd.DataFrame(C).ffill(axis=1).to_numpy()
    prev = np.c_[np.full(len(jours), np.nan), Cf[:, :-1]]
    manque = ~np.isfinite(C)
    for X in (O, H, L):
        X[manque] = prev[manque]
    C[manque] = prev[manque]
    premier = pd.DataFrame(O).bfill(axis=1).to_numpy()[:, :1]
    for X in (O, H, L, C):
        X[:] = np.where(np.isfinite(X), X, premier)
    for X in (O, H, L, C):
        X[~valide] = np.nan
    return {"O": O, "H": H, "L": L, "C": C, "valide": valide, "jours": jours, "i": i, "k": k}


def etat_c2(df: pd.DataFrame) -> np.ndarray:
    """Pour chaque bougie (décision à sa clôture) : +1 / -1 si la cassure C2 (24 h) tient un achat / une vente à cet
    instant (entrée comprise, sortie exclue), 0 sinon. C2 décide à l'heure pleine h (clôture de la bougie h-1:45)."""
    m = _matrice_df(df)
    S = np.zeros((len(m["jours"]), 96), np.int8)
    for d, s, me, ms in cs.signaux(m, 24, "milieu"):
        S[d, me // 15 - 1: ms // 15 - 1] = s
    return S[m["i"], m["k"]].astype(np.float32)


def canal_24h(df: pd.DataFrame) -> np.ndarray:
    h, l, c = (df[k].to_numpy(np.float64) for k in ("high", "low", "close"))
    hi = pd.Series(h).rolling(96, min_periods=96).max().shift(1).to_numpy()
    lo = pd.Series(l).rolling(96, min_periods=96).min().shift(1).to_numpy()
    demi = (hi - lo) / 2
    pos = np.where(demi > 0, (c - (hi + lo) / 2) / np.where(demi > 0, demi, 1), 0.0)
    return (np.clip(np.nan_to_num(pos), -3, 3) / 3).astype(np.float32)


@njit(cache=True)
def _rang(x, w, mini):
    n = len(x)
    out = np.full(n, np.nan)
    for i in range(n):
        if not np.isfinite(x[i]):
            continue
        a = max(0, i - w)
        nb, bas, eg = 0, 0, 0
        for j in range(a, i):
            v = x[j]
            if np.isfinite(v):
                nb += 1
                if v < x[i]:
                    bas += 1
                elif v == x[i]:
                    eg += 1
        if nb >= mini:
            out[i] = (bas + 0.5 * eg) / nb
    return out


def foule_horaire(sym: str) -> pd.DataFrame:
    """Grille horaire UTC (fin d'heure h, information connue à h) : part des comptes acheteurs, son rang sur 90 jours
    passés, état du signal C1 (tenue 24 h, une position à la fois). Même source et mêmes heures que crypto_flux."""
    f = FUT / "metrics" / f"{sym}.csv"
    cle = CACHE / f"foule_{sym}_{int(f.stat().st_mtime)}.npz"
    if cle.exists():
        z = np.load(cle)
        return pd.DataFrame({k: z[k] for k in ("part", "rang", "c1")}, index=pd.DatetimeIndex(z["h"]))
    me = pd.read_csv(f, usecols=["utc_ms", "count_long_short_ratio"])
    me["t"] = pd.to_datetime(me["utc_ms"].to_numpy(np.int64), unit="ms") + pd.Timedelta(minutes=15)  # retard 15 min
    me = me[np.isfinite(me["count_long_short_ratio"]) & (me["count_long_short_ratio"] > 0)].sort_values("t")
    grille = pd.date_range(me["t"].min().ceil("h"), me["t"].max().floor("h"), freq="h")
    g = pd.merge_asof(pd.DataFrame({"h": grille}), me[["t", "count_long_short_ratio"]], left_on="h", right_on="t",
                      direction="backward", tolerance=pd.Timedelta(hours=1))
    r = g["count_long_short_ratio"].to_numpy(np.float64)
    part = r / (1 + r)
    c = pd.Series(r, index=grille)
    c95 = c.shift(1).rolling(W90, min_periods=W90 // 3).quantile(.95)
    c05 = c.shift(1).rolling(W90, min_periods=W90 // 3).quantile(.05)
    achat, vente = (c <= c05).to_numpy(), (c >= c95).to_numpy()
    s = np.where(achat & ~vente, 1, np.where(vente & ~achat, -1, 0))
    etat = np.zeros(len(s), np.float32)
    libre = 0
    for i in np.flatnonzero(s):
        if i < libre:
            continue
        etat[i:i + 24] = s[i]
        libre = i + 24
    rang = _rang(r, W90, W90 // 3)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(cle, h=grille.values.astype("datetime64[ns]"), part=part, rang=rang, c1=etat)
    return pd.DataFrame({"part": part, "rang": rang, "c1": etat}, index=grille)


def propositions(sym: str, df: pd.DataFrame) -> np.ndarray:
    """[len(df), N_PROP] : les propositions vues à la clôture de chaque bougie de `df` (déjà retourné si miroir)."""
    miroir = sym.endswith(MIROIR)
    base = sym[:-len(MIROIR)] if miroir else sym
    n = len(df)
    P = np.zeros((n, N_PROP), np.float32)
    P[:, I_CANAL] = canal_24h(df)
    P[:, I_C2] = etat_c2(df)
    from collapsar.regarder.pistes.crypto_flux import utc_depuis_serveur
    dec = utc_depuis_serveur(df["time"]) + pd.Timedelta(minutes=15)          # instant de décision (UTC)
    F = foule_horaire(base).rename_axis("h").reset_index()
    F["h"] = F["h"].astype("datetime64[ns]")
    gauche = pd.DataFrame({"t": np.asarray(dec.values).astype("datetime64[ns]")})
    x = pd.merge_asof(gauche, F, left_on="t", right_on="h", direction="backward", tolerance=pd.Timedelta(hours=2))
    part, rang, c1 = (x[k].to_numpy(np.float64) for k in ("part", "rang", "c1"))
    dispo = np.isfinite(part) & np.isfinite(rang)
    P[:, I_PART] = np.where(dispo, np.clip((part - 0.5) * 4, -2, 2), 0.0)
    P[:, I_RANG] = np.where(dispo, rang * 2 - 1, 0.0)
    P[:, I_C1] = np.where(dispo, np.nan_to_num(c1), 0.0)
    P[:, I_DISPO] = dispo
    if miroir:
        P[:, list(RETOURNES)] *= -1
    t = pd.to_datetime(df["time"]) + pd.Timedelta(minutes=15)                 # heure du serveur de la décision
    hh = (t.dt.hour + t.dt.minute / 60).to_numpy()
    wd = (t.dt.dayofweek + hh / 24).to_numpy()
    P[:, 6], P[:, 7] = np.sin(2 * np.pi * hh / 24), np.cos(2 * np.pi * hh / 24)
    P[:, 8], P[:, 9] = np.sin(2 * np.pi * wd / 7), np.cos(2 * np.pi * wd / 7)
    return P


# ============================================================================== la classe
class ClasseCrypto2(ClasseRegard):
    """BTC + ETH (ou leurs miroirs), frais FTMO crypto, propositions dans la vue de chaque marché, regard minimum 1 h."""

    def __init__(self, marches: list[str], appareil="cpu", jusqua: pd.Timestamp | None = None):
        self.dev = torch.device(appareil)
        self.marches = list(marches)
        donnees = {m: cm.charger(m, jusqua) for m in self.marches}
        fiches = {m: cm.fiche_crypto(m) for m in self.marches}
        self.h = Horloge(donnees, self.marches, appareil, fiches)
        self.h.nuit = (self.h.nuit > 0).double()                  # une nuit payée chaque jour, jamais triple
        self.g = Graphique(donnees, appareil)
        self.offset = torch.tensor(self.g.debut_marche[:len(self.marches)], device=self.dev)
        self.seances = torch.from_numpy(seances(self.h.temps)).to(self.dev)
        self.cal = torch.from_numpy(calendrier(self.h.temps, ["BTCUSD"] * len(self.marches))).to(self.dev)
        self.i_jour = dm.ECHELLES.index("jour")
        local = self.h.local.cpu().numpy()
        P = np.zeros((self.h.T, len(self.marches), N_PROP), np.float32)
        for j, m in enumerate(self.marches):
            p = propositions(m, donnees[m])
            ok = local[:, j] >= 0
            P[ok, j] = p[local[ok, j]]
        self.props = torch.from_numpy(P).to(self.dev)
        self.masque = False                     # True : propositions effacées (expérience « sans propositions »)
        del donnees

    def voir(self, e: Etat, qui: torch.Tensor):
        idx, vm, vc = super().voir(e, qui)
        p = self.props[e.comptes.t][qui]
        if self.masque:
            p = p.clone()
            p[..., :I_DISPO + 1] = 0.0
        return idx, torch.cat([vm, p], -1), vc

    # ------------------------------------------------------------------ regard minimum d'une heure
    def noter_regard(self, e: Etat, rg):
        super().noter_regard(e, rg)
        q = rg.qui
        t = e.comptes.t
        e.prochain = torch.where(q, torch.maximum(e.prochain, t + REGARD_MIN_BOUGIES), e.prochain)
        if hasattr(e, "attente"):
            e.attente = e.attente & ~q

    def avancer(self, e: Etat, ordres, rg):
        r, ferme_seul, d = super().avancer(e, ordres, rg)
        if not hasattr(e, "attente"):
            e.attente = torch.zeros_like(e.reveil)
        tot = e.reveil | e.attente
        trop_tot = tot & ((e.comptes.t - e.dernier) < REGARD_MIN_BOUGIES)
        e.attente = trop_tot
        e.reveil = tot & ~trop_tot
        return r, ferme_seul, d


class TraderCrypto2(TraderHumain):
    """Le trader humain, NEUF ; ses mains lisent aussi les propositions."""

    def __init__(self):
        super().__init__()
        d = self.decisions.marche[0].out_features
        self.decisions.marche = nn.Sequential(nn.Linear(256 + N_VUE_MARCHE_H + N_PROP, d), nn.LayerNorm(d), nn.GELU())


# ============================================================================== jouer, mesurer, suivre ses choix
@torch.no_grad()
def jouer(c: ClasseCrypto2, agent, departs: torch.Tensor, duree: int = DUREE, jumeau=False, graine: int = 0,
          suivi_masque: torch.Tensor | None = None) -> dict:
    """Comme crypto_monde.jouer, + regard minimum 1 h (par la classe) et SUIVI de ce qu'elle fait de ses propositions
    sur les comptes `suivi_masque` (ses comptes, pas ceux du jumeau)."""
    appareils = [c.dev] if c.dev.type == "cuda" else []
    with torch.random.fork_rng(devices=appareils):
        torch.manual_seed(graine)
        return _jouer(c, agent, departs.to(c.dev), duree, jumeau, suivi_masque)


def _jouer(c, agent, departs, duree, jumeau, suivi_masque):
    agent.eval()
    n, M = len(departs), c.h.M
    e = Etat(c.h, n)
    e.recommencer(torch.ones(n, dtype=torch.bool, device=c.dev), departs)
    cpt, h = e.comptes, c.h
    vivant = torch.ones(n, dtype=torch.bool, device=c.dev)
    reussi, mort, inactif = (torch.zeros_like(vivant) for _ in range(3))
    finale = torch.full((n,), CAPITAL, dtype=torch.float64, device=c.dev)
    sommet, baisse = finale.clone(), torch.zeros_like(finale)
    pnl = torch.zeros(n, M, dtype=torch.float64, device=c.dev)
    ouvertures = torch.zeros(n, M, dtype=torch.float64, device=c.dev)
    taux = torch.stack([h.nuit_vente, h.nuit_achat])
    z = lambda: torch.zeros(n, dtype=torch.float64, device=c.dev)
    regards, en_pos, avec_stop, tenue_somme, tenue_n = z(), z(), z(), z(), z()
    sm = torch.ones(n, dtype=torch.bool, device=c.dev) if suivi_masque is None else suivi_masque.to(c.dev)
    S = {k: torch.zeros((), dtype=torch.float64, device=c.dev) for k in ("bougies", "en_pos", "c2_actif", "c2_actif_en_pos", "c2_accord", "c2_contre",
                          "c1_actif", "c1_actif_en_pos", "c1_accord", "c1_contre", "canal_x_pos", "canal_abs",
                          "ouv", "ouv_c2_actif", "ouv_avec_c2", "ouv_contre_c2", "ouv_c1_actif", "ouv_avec_c1",
                          "ouv_contre_c1", "ouv_achat", "ouv_canal_haut", "ouv_canal_haut_achat",
                          "ouv_canal_bas", "ouv_canal_bas_achat", "dispo", "ouv_dispo")}
    for _ in range(duree):
        qui = ((cpt.t >= e.prochain) | e.reveil) & vivant
        rg = None
        if qui.any():
            rg = c.decider(agent, e, qui, sur=True)
            if jumeau is not False:
                s = rg.choix["sens"]
                hasard = torch.where(torch.rand(s.shape, device=s.device) < 0.5, VENDRE, ACHETER)
                lui = torch.ones_like(qui) if jumeau is True else jumeau.to(qui.device)
                rg.choix["sens"] = torch.where((s == FERMER) | ~lui[qui][:, None], s, hasard)
            c.noter_regard(e, rg)
            regards += qui.double()
        t0 = cpt.t.clone()
        P0 = c.props[t0]                                            # [n, M, N_PROP] vues à cette décision
        lat0 = cpt.u * (h.c[t0] - cpt.entree) * h.fx[t0]
        ouv_avant = e.ouverture.clone()
        r, _, _ = c.avancer(e, c.ordres(e, rg), rg)
        t1 = cpt.t
        lat1 = cpt.u * (h.c[t1] - cpt.entree) * h.fx[t1]
        nuit = cpt.u.abs() * h.o[t1] * h.fx[t1] * torch.where(cpt.u > 0, taux[1], taux[0]) / 360 * h.nuit[t1][:, None]
        pnl += torch.where(vivant[:, None], lat1 - lat0 + r["realise"] - nuit, 0.0)
        ouvre = (e.ouverture >= 0) & (e.ouverture != ouv_avant) & vivant[:, None]
        ouvertures += ouvre.double()
        avec_stop += (ouvre & ~torch.isnan(cpt.stop)).double().sum(1)
        ferme = (ouv_avant >= 0) & (e.ouverture != ouv_avant) & vivant[:, None]
        duree_h = (t0[:, None] + 1 - ouv_avant).double() / 4
        tenue_somme += torch.where(ferme, duree_h, 0.0).sum(1)
        tenue_n += ferme.double().sum(1)
        en_pos += ((cpt.u != 0).any(1) & vivant).double()
        # ---- suivi : sa position (après la bougie) face aux propositions qu'elle voyait
        w = (vivant & sm)[:, None].expand(-1, M)
        sg = torch.sign(cpt.u).float()
        c2, c1, ca, dispo = P0[..., I_C2], P0[..., I_C1], P0[..., I_CANAL], P0[..., I_DISPO] > 0.5
        f = lambda x: (x & w).sum()
        S["bougies"] += f(torch.ones_like(w))
        S["en_pos"] += f(sg != 0)
        S["dispo"] += f(dispo)
        for nom, x in (("c2", c2), ("c1", c1)):
            act = x != 0
            S[f"{nom}_actif"] += f(act)
            S[f"{nom}_actif_en_pos"] += f(act & (sg != 0))
            S[f"{nom}_accord"] += f(act & (sg == x))
            S[f"{nom}_contre"] += f(act & (sg == -x))
        S["canal_x_pos"] += (sg * ca * w).sum()
        S["canal_abs"] += (sg.abs() * ca.abs() * w).sum()
        o = ouvre & w
        S["ouv"] += f(o)
        S["ouv_dispo"] += f(o & dispo)
        S["ouv_achat"] += f(o & (sg > 0))
        for nom, x in (("c2", c2), ("c1", c1)):
            S[f"ouv_{nom}_actif"] += f(o & (x != 0))
            S[f"ouv_avec_{nom}"] += f(o & (x != 0) & (sg == x))
            S[f"ouv_contre_{nom}"] += f(o & (x != 0) & (sg == -x))
        haut, bas = ca > 1 / 3, ca < -1 / 3                         # au-dessus / au-dessous du canal (cassure)
        S["ouv_canal_haut"] += f(o & haut)
        S["ouv_canal_haut_achat"] += f(o & haut & (sg > 0))
        S["ouv_canal_bas"] += f(o & bas)
        S["ouv_canal_bas_achat"] += f(o & bas & (sg > 0))
        v = torch.where(vivant, r["valeur"], finale)
        sommet = torch.maximum(sommet, v)
        baisse = torch.maximum(baisse, (sommet - v) / sommet)
        finale = v
        reussi |= vivant & r["reussi"]
        mort |= vivant & r["mort"]
        inactif |= vivant & r["inactif"]
        vivant &= ~(r["mort"] | r["reussi"] | r["fin_histoire"])
        if not vivant.any():
            break
    np_ = lambda x: x.cpu().numpy()
    return {"duree": duree, "gains_pct": np_((finale / CAPITAL - 1) * 100), "pnl": np_(pnl / CAPITAL * 100),
            "ouvertures": np_(ouvertures), "reussi": np_(reussi), "mort": np_(mort & ~inactif), "inactif": np_(inactif),
            "baisse": np_(baisse * 100), "regards": np_(regards), "en_pos": np_(en_pos), "avec_stop": np_(avec_stop),
            "tenue_somme": np_(tenue_somme), "tenue_n": np_(tenue_n), "suivi": {k: float(v) for k, v in S.items()}}


def lire_suivi(S: dict) -> dict:
    """Ce qu'elle fait de ses propositions, en % lisibles."""
    p = lambda a, b: float(100 * S[a] / S[b]) if S[b] > 0 else float("nan")
    return {"temps_en_position_pct": p("en_pos", "bougies"),
            "c2_actif_pct_du_temps": p("c2_actif", "bougies"),
            "en_position_quand_c2_actif_pct": p("c2_actif_en_pos", "c2_actif"),
            "dans_le_sens_de_c2_pct": p("c2_accord", "c2_actif"), "contre_c2_pct": p("c2_contre", "c2_actif"),
            "c1_actif_pct_du_temps": p("c1_actif", "bougies"),
            "en_position_quand_c1_actif_pct": p("c1_actif_en_pos", "c1_actif"),
            "dans_le_sens_de_c1_pct": p("c1_accord", "c1_actif"), "contre_c1_pct": p("c1_contre", "c1_actif"),
            "lien_position_canal": float(S["canal_x_pos"] / S["canal_abs"]) if S["canal_abs"] > 0 else float("nan"),
            "foule_visible_pct_du_temps": p("dispo", "bougies"),
            "ouvertures": S["ouv"], "ouvertures_achat_pct": p("ouv_achat", "ouv"),
            "ouvertures_pendant_c2_pct": p("ouv_c2_actif", "ouv"),
            "ouvertures_avec_c2_pct": p("ouv_avec_c2", "ouv_c2_actif"),
            "ouvertures_contre_c2_pct": p("ouv_contre_c2", "ouv_c2_actif"),
            "ouvertures_pendant_c1_pct": p("ouv_c1_actif", "ouv"),
            "ouvertures_avec_c1_pct": p("ouv_avec_c1", "ouv_c1_actif"),
            "ouvertures_contre_c1_pct": p("ouv_contre_c1", "ouv_c1_actif"),
            "achat_quand_prix_haut_du_canal_pct": p("ouv_canal_haut_achat", "ouv_canal_haut"),
            "achat_quand_prix_bas_du_canal_pct": p("ouv_canal_bas_achat", "ouv_canal_bas")}


# ============================================================================== la référence : cassure C2 seule
C2 = cs.Reglages(N=(24,), week_end=False, sortie="milieu", taille="14j", arret_jour=0.03, cible=0.01, plafond=1.0,
                 reduction_mur=False, compte="btc_eth")


class CompteC2:
    """La cassure C2 seule (bitcoin_journee C2 = cassure.Reglages par défaut) sur BTC + ETH Binance, frais FTMO de la
    consigne, budget partagé cible / racine(2) x 1,25 (règle du compte BTC + ETH), arrêt du jour -3 %, + 20 jumeaux.
    Mêmes départs et même durée (60 jours) que les comptes de COLLAPSAR."""

    def __init__(self, marches=MARCHES, reg=C2, n_jumeaux: int = 20):
        self.reg = reg
        poids = reg.cible / math.sqrt(len(marches)) * 1.25
        chem, chem_j, jours = [], [[] for _ in range(n_jumeaux)], None
        for i, sym in enumerate(marches):
            mk = cs.Marche(sym, "binance", reg, cm.frais_crypto(sym), cache=CACHE / "cassure")
            jours = mk.jours if jours is None else jours.union(mk.jours)
            chem.append(mk.chemin(poids))
            for k, sg in enumerate(mk.signes_jumeaux(n_jumeaux, 7 + i)):
                chem_j[k].append(mk.chemin(poids, sg))
            del mk
        self.jours = jours
        self.W = cs.additionner(chem, jours)
        self.Wj = [cs.additionner(cc, jours) for cc in chem_j]

    def fenetres(self, dates) -> dict:
        f = lambda W: cm.CompteCassure._fenetres(W, self.jours, dates, arret=self.reg.arret_jour,
                                                  reduction=self.reg.reduction_mur)
        x = f(self.W)
        jj = [f(w) for w in self.Wj]
        x["jumeaux_gain_pct"] = float(np.mean([j["gain_moyen_pct"] for j in jj]))
        x["jumeaux_reussis_pct"] = float(np.mean([j["challenges_reussis_pct"] for j in jj]))
        x["jumeaux_murs_pct"] = float(np.mean([j["murs_touches_pct"] for j in jj]))
        d = np.array(x["gains_comptes_pct_mois"]) - np.mean([j["gains_comptes_pct_mois"] for j in jj], 0)
        x["avantage_pct_mois"] = float(d.mean())
        return x
