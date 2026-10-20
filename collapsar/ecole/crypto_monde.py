"""L'ÉCOLE DE COLLAPSAR SUR LES CRYPTOS (16/10/2026) : le même trader humain numérique (cerveau/humain.py), la même
école « elle choisit quand revenir regarder » (ecole/regard.py) et le même simulateur FTMO fidèle (mains/), nourris
avec les bougies de 15 min de Binance (data/binance, heure du serveur = New York + 7 h, 7 jours sur 7).

FIXÉ AVANT TOUT RÉSULTAT (cahier de la séance) :
- Données : `strategies.cassure._binance` (filtre commun : 7 premiers jours de chaque paire ignorés, mèches > 2 x / < 0,5 x
  de la clôture ramenées à min / max(ouverture, clôture), krach du 10/10/2025 gardé). MATIC et POL séparés.
- Marchés : groupe A = symboles Binance hors BTC / ETH, ordre alphabétique, 1 sur 2 en commençant par le 1er ;
  + BTCUSDT et ETHUSDT. Groupe B (l'autre moitié) = confirmation, UNE seule fois à la fin.
- Années : apprentissage <= 2021 (les parties finissent avant le 01/01/2022 et les mondes d'école ne contiennent AUCUNE
  bougie de 2022 ou après) ; contrôle = mêmes marchés, 2022-01 -> 2026-10 ; témoin du par cœur = 2018-2021.
- Conditions (consigne du coordinateur, corrigée le 16/10 avant tout apprentissage : commission FTMO comprise) : frais
  aller-retour BTC 0,083 %, ETH 0,112 %, autres 0,12 % (cassure de référence recalculée avec ces frais) ; frais de nuit
  30 %/an achat comme vente, payés CHAQUE nuit (7 / 7, pas de nuit triple : les cryptos cotent le week-end) ; levier
  1:1 (argent engagé <= valeur du compte). Murs FTMO, règle d'inactivité et 4 jours de trading : ceux du simulateur.
- Ce qu'elle voit EN PLUS (des faits connus à l'instant de décision, PAS des règles ; consigne du coordinateur, les
  repères qui ont montré quelque chose sur les cryptos) : position du prix dans le canal des 12, 18, 24, 30, 36, 48
  dernières heures (bougie en cours exclue du canal ; 0 = milieu, +-1 = bord, au-delà = cassure), largeur du canal
  24 h en agitation, distance aux zones zones supply and demand ACTIVES les plus proches (indicateur du chef de projet, traduction
  exacte `regarder/smc/nono.zones_nono`, effacées à la 1re clôture de 15 min au-delà de leur milieu) en 4 h et en 1 h :
  support (zone acheteuse) et résistance (zone vendeuse), en agitation du jour, 0 = dans la zone.
  Unité d'agitation = moyenne sur 14 jours du « plus haut - plus bas des 24 dernières heures » / prix.
- Calendrier : annonces importantes du dollar (heures justes de MetaTrader) ; séances Tokyo / Londres / New York.
- Les mondes miroirs (prix retournés) sont dans l'école (contre le par cœur de la hausse 2017-2021).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from numba import njit
from torch import nn

from collapsar.cerveau.humain import ACHETER, FERMER, VENDRE, N_VUE_MARCHE_H, TraderHumain
from collapsar.donnees import marches as dm
from collapsar.ecole.regard import ClasseRegard, Etat
from collapsar.mains.fiches import Fiche, MIROIR
from collapsar.mains.horloge import Horloge
from collapsar.mains.simulateur import CAPITAL, INACTIVITE_JOURS
from collapsar.regarder.smc.nono import effacement, zones_nono
from collapsar.strategies import cassure as cs
from collapsar.yeux.faits import calendrier, seances
from collapsar.yeux.graphique import Graphique

VIE = dm.RACINE / "collapsar" / "vie" / "ecole_crypto"
CACHE = VIE / "cache"
FIN_APPRENTISSAGE = pd.Timestamp("2022-01-01")
CONTROLE_DE, CONTROLE_JUSQUA = pd.Timestamp("2022-01-01"), pd.Timestamp("2026-10-15")
TEMOIN_DE, TEMOIN_JUSQUA = pd.Timestamp("2018-03-01"), pd.Timestamp("2022-01-01")
UN_MOIS = 96 * 30                       # bougies de 15 min dans un mois de crypto (7 / 7)
DUREE = 2 * UN_MOIS                     # une partie = un challenge de 2 mois
NUIT = 0.30
CANAUX = (12, 18, 24, 30, 36, 48)
N_REPERES = len(CANAUX) + 1 + 4


def frais_crypto(sym: str) -> float:
    """16/10 (correction du coordinateur, vérifiée sur ftmo.com) : commission FTMO 0,0325 % par côté sur les cryptos
    depuis le 28/07/2025, en plus de l'écart. 16/10 soir (audit) : x 1,25 retiré, même source que les pistes
    (crypto_flux.frais) -> BTC 0,066 %, ETH 0,090 %, autres ~0,096 % par aller-retour (avant 0,083 / 0,112 / 0,12)."""
    from collapsar.regarder.pistes.crypto_flux import frais
    base = sym.replace(MIROIR, "").replace("USDT", "")
    return float(frais(base + "USDT"))


def fiche_crypto(sym: str) -> Fiche:
    return Fiche(sym, sym, "crypto", "USD", frais_crypto(sym), 1.0, NUIT, NUIT, 0.0, 0.0)


def groupes() -> tuple[list[str], list[str]]:
    dispo = sorted(p.name[:-len("_M15.csv")] for p in cs.BINANCE.glob("*_M15.csv"))
    autres = [s for s in dispo if s.replace("USDT", "") not in ("BTC", "ETH")]
    return autres[0::2], autres[1::2]


def charger(sym: str, jusqua: pd.Timestamp | None = None) -> pd.DataFrame:
    """Bougies Binance filtrées (filtre commun), en cache .npz dans vie/ecole_crypto/cache."""
    base = sym[:-len(MIROIR)] if sym.endswith(MIROIR) else sym
    f = cs.BINANCE / f"{base}_M15.csv"
    cle = CACHE / f"{base}_{int(f.stat().st_mtime)}_filtre.npz"
    if cle.exists():
        z = np.load(cle)
        df = pd.DataFrame({"time": pd.to_datetime(z["time"]), **{k: z[k] for k in ("open", "high", "low", "close", "volume")}})
    else:
        df = cs._binance(base)
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez(cle, time=df["time"].values.astype("datetime64[ns]"),
                 **{k: df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close", "volume")})
    if jusqua is not None:
        df = df[df["time"] < jusqua].reset_index(drop=True)
    return dm.miroir(df) if sym.endswith(MIROIR) else df


# ---------------------------------------------------------------------------------------------- les repères (faits)
@njit(cache=True)
def _proches(dec, c, unite, zc, zf, zh, zb, zs, sens):
    """Distance signée (en agitation du jour) à la zone ACTIVE la plus proche du sens donné, à chaque décision.
    Zones triées par heure de confirmation. 3 = aucune zone."""
    n = len(dec)
    out = np.full(n, 3.0)
    act = np.empty(len(zc), np.int64)
    na, p = 0, 0
    for k in range(n):
        while p < len(zc) and zc[p] <= dec[k]:
            if zs[p] == sens:
                act[na] = p
                na += 1
            p += 1
        best = 3.0
        m = 0
        u = c[k] * unite[k]
        for q in range(na):
            z = act[q]
            if zf[z] <= dec[k]:
                continue
            act[m] = z
            m += 1
            if sens > 0:
                d = (c[k] - zh[z]) if c[k] >= zh[z] else ((c[k] - zb[z]) if c[k] < zb[z] else 0.0)
            else:
                d = (zb[z] - c[k]) if c[k] <= zb[z] else ((zh[z] - c[k]) if c[k] > zh[z] else 0.0)
            if u > 0:
                d = d / u
                if abs(d) < abs(best):
                    best = d
        na = m
        out[k] = best
    return out


def reperes(df: pd.DataFrame) -> np.ndarray:
    """[n, N_REPERES] pour chaque bougie de `df` (décision à sa clôture), tout connu à cet instant."""
    h, l, c = (df[k].to_numpy(np.float64) for k in ("high", "low", "close"))
    H, L = pd.Series(h), pd.Series(l)
    r24 = (H.rolling(96, min_periods=8).max() - L.rolling(96, min_periods=8).min()).to_numpy() / c
    unite = pd.Series(r24).rolling(96 * 14, min_periods=96).mean().bfill().to_numpy()
    unite = np.where(np.isfinite(unite) & (unite > 0), unite, np.nanmedian(r24))
    sortie = []
    for N in CANAUX:
        hi = H.rolling(4 * N, min_periods=4 * N).max().shift(1).to_numpy()
        lo = L.rolling(4 * N, min_periods=4 * N).min().shift(1).to_numpy()
        demi = (hi - lo) / 2
        pos = np.where(demi > 0, (c - (hi + lo) / 2) / np.where(demi > 0, demi, 1), 0.0)
        sortie.append(np.clip(np.nan_to_num(pos), -3, 3) / 3)
        if N == 24:
            largeur = np.clip(np.nan_to_num((hi - lo) / c / unite), 0, 3) / 3
    sortie.append(largeur)
    t = df["time"].values.astype("datetime64[ns]")
    dec = (t + np.timedelta64(15, "m")).astype(np.int64)
    bt = t.astype(np.int64)
    quinze = np.int64(15 * 60 * 10 ** 9)
    for nom in ("4 h", "1 h"):
        e = dm.echelle(df, nom)
        zh, zb, zm, zs, zi = zones_nono(e["open"], e["high"], e["low"], e["close"])
        zc = e["fin"][zi].astype(np.int64)
        zf = effacement(zm, zs, zc, bt, quinze, c)
        o = np.argsort(zc, kind="stable")
        zh, zb, zs, zc, zf = zh[o], zb[o], zs[o], zc[o], zf[o]
        for sens in (1, -1):
            d = _proches(dec, c, unite, zc, zf, zh, zb, zs.astype(np.int64), sens)
            sortie.append(np.clip(d, -1, 3) / 3)
    return np.stack(sortie, 1).astype(np.float32)


# ---------------------------------------------------------------------------------------------- la classe crypto
class ClasseCrypto(ClasseRegard):
    """ClasseRegard pour des cryptos Binance : fiches crypto (frais, nuit 30 %/an chaque nuit, levier 1:1), calendrier
    du dollar, et les repères ajoutés à la vue de chaque marché."""

    def __init__(self, marches: list[str], appareil="cpu", jusqua: pd.Timestamp | None = None):
        self.dev = torch.device(appareil)
        self.marches = list(marches)
        donnees = {m: charger(m, jusqua) for m in self.marches}
        fiches = {m: fiche_crypto(m) for m in self.marches}
        self.h = Horloge(donnees, self.marches, appareil, fiches)
        self.h.nuit = (self.h.nuit > 0).double()                  # une nuit payée chaque jour, jamais triple
        self.g = Graphique(donnees, appareil)
        self.offset = torch.tensor(self.g.debut_marche[:len(self.marches)], device=self.dev)
        self.seances = torch.from_numpy(seances(self.h.temps)).to(self.dev)
        self.cal = torch.from_numpy(calendrier(self.h.temps, ["BTCUSD"] * len(self.marches))).to(self.dev)
        self.i_jour = dm.ECHELLES.index("jour")
        local = self.h.local.cpu().numpy()
        rep = np.zeros((self.h.T, len(self.marches), N_REPERES), np.float32)
        for j, m in enumerate(self.marches):
            r = reperes(donnees[m])
            ok = local[:, j] >= 0
            rep[ok, j] = r[local[ok, j]]
            rep[~ok, j, len(CANAUX) + 1:] = 1.0                    # aucune zone connue
        self.reperes = torch.from_numpy(rep).to(self.dev)
        self.premier = {m: donnees[m]["time"].iloc[0] for m in self.marches}
        del donnees

    def voir(self, e: Etat, qui: torch.Tensor):
        idx, vm, vc = super().voir(e, qui)
        return idx, torch.cat([vm, self.reperes[e.comptes.t][qui]], -1), vc


class TraderCrypto(TraderHumain):
    """Le même trader humain ; ses mains lisent en plus les repères (colonnes ajoutées à zéro : au départ, il ne s'en
    sert pas ; à l'école de décider si ces faits l'aident)."""

    def __init__(self):
        super().__init__()
        d = self.decisions.marche[0].out_features
        self.decisions.marche = nn.Sequential(nn.Linear(256 + N_VUE_MARCHE_H + N_REPERES, d), nn.LayerNorm(d), nn.GELU())

    def charger(self, etat: dict):
        etat = dict(etat)
        k = "decisions.marche.0.weight"
        actuel = self.state_dict()
        if k in etat and etat[k].shape != actuel[k].shape:
            w = torch.zeros_like(actuel[k])
            n = etat[k].shape[1]
            w[:, :n] = etat[k].to(w)
            w[:, n:] = 0.0
            etat[k] = w
        super().charger(etat)


# ---------------------------------------------------------------------------------------------- jouer et mesurer
@torch.no_grad()
def jouer(c: ClasseCrypto, agent, departs: torch.Tensor, duree: int = DUREE, jumeau: bool = False,
          graine: int = 0) -> dict:
    """Comptes FTMO de 100 000 $ partant aux instants `departs`, `duree` bougies (arrêt à +10 % avec 4 jours de trading,
    ou à un mur). Comme regard.jouer_comptes, avec en plus l'argent de CHAQUE marché (approché : la perte au moment
    d'un mur n'est pas répartie par marché) et les mois de crypto (30 jours)."""
    appareils = [c.dev] if c.dev.type == "cuda" else []
    with torch.random.fork_rng(devices=appareils):
        torch.manual_seed(graine)
        return _jouer(c, agent, departs.to(c.dev), duree, jumeau)


def _jouer(c, agent, departs, duree, jumeau):
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
    taux = torch.stack([h.nuit_vente, h.nuit_achat])           # [2, M]
    z = lambda: torch.zeros(n, dtype=torch.float64, device=c.dev)
    regards, en_pos, avec_stop, tenue_somme, tenue_n = z(), z(), z(), z(), z()
    for _ in range(duree):
        qui = ((cpt.t >= e.prochain) | e.reveil) & vivant
        rg = None
        if qui.any():
            rg = c.decider(agent, e, qui, sur=True)
            if jumeau is not False:
                # jumeau : True (tous) ou masque [n] (comptes jumeaux joués dans le même paquet que les siens)
                s = rg.choix["sens"]
                hasard = torch.where(torch.rand(s.shape, device=s.device) < 0.5, VENDRE, ACHETER)
                lui = torch.ones_like(qui) if jumeau is True else jumeau.to(qui.device)
                rg.choix["sens"] = torch.where((s == FERMER) | ~lui[qui][:, None], s, hasard)
            c.noter_regard(e, rg)
            regards += qui.double()
        t0 = cpt.t.clone()
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
            "tenue_somme": np_(tenue_somme), "tenue_n": np_(tenue_n)}


def agreger(brut: dict, sel=None) -> dict:
    """Résumé d'un groupe de comptes (sel = indices) d'un résultat de `jouer`."""
    sel = np.arange(len(brut["gains_pct"])) if sel is None else np.asarray(sel)
    b = {k: (v[sel] if isinstance(v, np.ndarray) else v) for k, v in brut.items()}
    duree = b["duree"]
    mois = duree / UN_MOIS
    n = len(sel)
    tr = b["ouvertures"].sum()
    return {"gains_comptes_pct_mois": (b["gains_pct"] / mois).tolist(), "gain_moyen_pct": float(b["gains_pct"].mean() / mois),
            "pnl_marche_pct_mois": (b["pnl"] / mois).mean(0).tolist(), "pnl_comptes_marche": (b["pnl"] / mois).tolist(),
            "trades_marche_par_mois": (b["ouvertures"].sum(0) / n / mois).tolist(),
            "reussis_comptes": b["reussi"].tolist(), "morts_comptes": b["mort"].tolist(),
            "challenges_reussis_pct": float(b["reussi"].mean() * 100), "murs_touches_pct": float(b["mort"].mean() * 100),
            "inactifs_pct": float(b["inactif"].mean() * 100), "baisse_max_moyenne_pct": float(b["baisse"].mean()),
            "regards_par_jour": float(b["regards"].sum() / (n * duree / 96)), "trades_par_mois": float(tr / n / mois),
            "avec_stop_pct": float(b["avec_stop"].sum() / max(tr, 1) * 100),
            "tenue_moyenne_h": float(b["tenue_somme"].sum() / max(b["tenue_n"].sum(), 1)),
            "temps_en_position_pct": float(b["en_pos"].mean() / duree * 100)}


def departs(c: ClasseCrypto, de, jusqua, tous_les_jours: int = 10, duree: int = DUREE) -> torch.Tensor:
    lo, hi = c.instant(de), min(c.instant(jusqua), c.h.T - 1) - duree - 1
    pas = 96 * tous_les_jours
    return torch.arange(lo, max(hi, lo + 1), pas, device=c.dev).long()


# ---------------------------------------------------------------------------------------------- la référence : cassure v3
CASSURE = cs.Reglages(N=(12, 18, 24, 30, 36, 48), week_end=False, sortie="milieu", taille="24h", arret_jour=0.03,
                      cible=0.0075, plafond=1.0, reduction_mur=True, compte="btc_eth")


@dataclass
class CompteCassure:
    """Le compte de la cassure v3 (version retenue) sur des marchés Binance, budget partagé cible / racine(M) x 1,25
    (sa règle BTC + ETH, étendue telle quelle à M marchés), frais de la consigne ; et 20 jumeaux."""
    marches: list
    jours: pd.DatetimeIndex = None
    W: np.ndarray = None
    Wj: list = None
    par_marche: dict = None

    def construire(self, n_jumeaux: int = 20):
        reg = CASSURE
        poids = reg.cible / math.sqrt(len(self.marches)) * 1.25
        chem, chem_j, jours = [], [[] for _ in range(n_jumeaux)], None
        self.par_marche = {}
        for i, sym in enumerate(self.marches):
            mk = cs.Marche(sym, "binance", reg, frais_crypto(sym), cache=CACHE / "cassure")
            jours = mk.jours if jours is None else jours.union(mk.jours)
            chem.append(mk.chemin(poids))
            for k, sg in enumerate(mk.signes_jumeaux(n_jumeaux, 7 + i)):
                chem_j[k].append(mk.chemin(poids, sg))
            seul = cs.additionner([mk.chemin(reg.cible)], mk.jours)
            g, _ = cs.serie_jour(seul, mk.jours, reg.arret_jour)
            gp = g[(g.index >= CONTROLE_DE) & (g.index < CONTROLE_JUSQUA)]
            x = cs.mesures(gp) if len(gp) >= 60 else {}
            x["force"] = mk.force(reg.cible, CONTROLE_DE, CONTROLE_JUSQUA)
            gt = g[(g.index >= TEMOIN_DE) & (g.index < TEMOIN_JUSQUA)]
            x["avant_2022"] = cs.mesures(gt) if len(gt) >= 60 else {}
            self.par_marche[sym] = x
            del mk
        self.jours = jours
        self.W = cs.additionner(chem, jours)
        self.Wj = [cs.additionner(cc, jours) for cc in chem_j]
        return self

    @staticmethod
    def _fenetres(W, jours, dates, arret=CASSURE.arret_jour, reduction=True):
        niv = {mu: cs.apres_arret(W, arret, mu) for mu in cs.MULTS}
        actif = (np.abs(W).max(1) > 0)
        gains, R, Mo = [], 0, 0
        for D in dates:
            i0, i1 = jours.searchsorted(D), jours.searchsorted(D + pd.Timedelta(days=60))
            v, jt, etat = 0.0, 0, "fini"
            for i in range(i0, i1):
                mu = cs.mult_mur(v) if reduction else 1.0
                g, w = niv[mu][0][i], niv[mu][1][i]
                if w <= -0.05 or v + w <= -0.10:
                    v, etat = v + w, "mort"
                    break
                v += g
                jt += int(actif[i])
                if v >= 0.10 and jt >= 4:
                    etat = "reussi"
                    break
            gains.append(v * 100 / 2)
            R += etat == "reussi"
            Mo += etat == "mort"
        n = max(len(dates), 1)
        return {"gain_moyen_pct": float(np.mean(gains)), "gains_comptes_pct_mois": gains,
                "challenges_reussis_pct": 100 * R / n, "murs_touches_pct": 100 * Mo / n}

    def fenetres(self, dates) -> dict:
        x = self._fenetres(self.W, self.jours, dates)
        jj = [self._fenetres(w, self.jours, dates) for w in self.Wj]
        x["jumeaux_gain_pct"] = float(np.mean([j["gain_moyen_pct"] for j in jj]))
        x["jumeaux_reussis_pct"] = float(np.mean([j["challenges_reussis_pct"] for j in jj]))
        x["jumeaux_murs_pct"] = float(np.mean([j["murs_touches_pct"] for j in jj]))
        d = np.array(x["gains_comptes_pct_mois"]) - np.mean([j["gains_comptes_pct_mois"] for j in jj], 0)
        x["avantage_pct_mois"] = float(d.mean())
        return x
