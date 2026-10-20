"""MOTEUR DE LA CASSURE HORAIRE (16/10/2026) — propre et réutilisable (laboratoire, démo, COLLAPSAR).

Règle de base = C2 (regarder/pistes/bitcoin_journee.py, en démo Tradeco : direct/bitcoin_cassure.py) :
- une journée = minuit serveur -> 23h45 serveur (heure du serveur MetaTrader = New York + 7 h) ; jours tradés = lundi ->
  vendredi (ou tous les jours si `week_end`), avec >= 92 bougies de 15 min sur 96 (trous bouchés au dernier prix) ;
- à chaque heure pleine h = 1h ... 23h : c = clôture de l'heure écoulée ; canal = plus haut / plus bas des N heures
  précédentes (heures des jours tradés bout à bout) ; à plat et h <= 22 : c > haut -> achat, c < bas -> vente ;
  sortie (h <= 23) : « milieu » = c repasse le milieu du canal de N heures, « oppose » = c casse le canal opposé de
  N/2 heures (sortie de Donchian) ; sortie forcée 23h45 (aucun frais de nuit) ;
- ENSEMBLE : liste de N -> un avis par N (chacun son état), chaque avis pèse 1/len(N) de la taille (taille totale identique) ;
- taille : exposition = poids x min(plafond, cible / agitation) ; agitation « 14j » = écart type des rendements journaliers
  des 14 jours tradés précédents, « 24h » = écart type des 96 derniers rendements de 15 min x racine(96) (connue à l'entrée) ;
- chemin du jour du compte, quart d'heure par quart d'heure : gains réalisés + positions ouvertes au pire point de la
  bougie (plus bas pour un achat, plus haut pour une vente ; le point d'entrée compte), frais aller-retour retirés dès
  l'entrée. Plusieurs positions ouvertes : leurs pires points d'une même bougie sont additionnés (prudent) ;
- arrêt de la journée : dès que le chemin touche -arrêt, tout est fermé à -(arrêt + 0,1 %) (glissement), plus rien ce jour ;
- challenge FTMO : départ tous les 10 jours tradés ; +10 % puis +5 % ; mort si le pire point d'un jour <= -5 % du matin
  ou si le compte touche -10 % du départ de la phase (perte latente comprise) ; option « réduction près du mur » :
  taille x 1 si distance au mur des -10 % >= 6 %, x 0,5 si >= 4 %, x 0,25 sinon (décidé chaque matin) ;
- jumeaux : mêmes moments, même taille, sens tiré à pile ou face (par avis).
Contrôle : avec N = (24,), sans week-end, sortie milieu, agitation 14 j, mêmes trades que bitcoin_journee.var_C(m, 24).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm

FIN = 1425                                   # 23h45 serveur en minutes
BARRES_MIN = 92
JOURS_AGIT = 14
BINANCE = dm.RACINE / "data" / "binance"
CACHE = dm.RACINE / "collapsar" / "vie" / "cassure_v3" / "cache"
GLISSEMENT_ARRET = 0.001


@dataclass(frozen=True)
class Reglages:
    N: tuple = (24,)
    week_end: bool = False
    sortie: str = "milieu"                   # "milieu" | "oppose"
    taille: str = "14j"                      # "14j" | "24h"
    arret_jour: float | None = 0.03          # None = aucun
    cible: float = 0.01
    plafond: float = 1.0
    reduction_mur: bool = False
    compte: str = "btc_eth"                  # "btc_eth" (budget partagé cible/racine(2) x 1,25) | "btc"


# ================================================================ données
def _binance(sym: str) -> pd.DataFrame:
    """Bougies Binance de data/binance/<SYM>_M15.csv, DÉJÀ à l'heure du serveur (New York + 7 h) : vérifié le 16/10
    (BTCUSDT contre BTCUSD Dukascopy : lien des rendements de 15 min 0,975 sans décalage, ~0 à +-1, 2, 3 h).
    Les rares heures en double (retour à l'heure d'hiver) : la dernière est gardée.
    Filtre imposé par le coordinateur (16/10, identique pour tous, avant tout résultat) : les 7 premiers jours de
    chaque paire sont ignorés ; une bougie dont le bas < 0,5 x sa clôture ou le haut > 2 x sa clôture a son bas / haut
    ramené à min / max(ouverture, clôture) (mèches fausses, ex. LINK 12/03/2020) ; le krach éclair RÉEL du 10/10/2025
    (bougies serveur des 10 et 11/10/2025) est gardé tel quel (prudent)."""
    df = pd.read_csv(BINANCE / f"{sym}_M15.csv")
    df.columns = [c.lower() for c in df.columns]
    serveur = pd.to_datetime(df["time"])
    out = pd.DataFrame({"time": serveur, **{k: pd.to_numeric(df[k], errors="coerce") for k in
                                              ("open", "high", "low", "close", "volume")}}).dropna()
    out = out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]
    out = out.sort_values("time", kind="stable").drop_duplicates("time", keep="last").reset_index(drop=True)
    out = out[out["time"] >= out["time"].iloc[0] + pd.Timedelta(days=7)].reset_index(drop=True)
    krach = (out["time"] >= "2025-10-10") & (out["time"] < "2025-10-12")
    faux = ((out["low"] < 0.5 * out["close"]) | (out["high"] > 2 * out["close"])) & ~krach
    out.loc[faux, "high"] = out.loc[faux, ["open", "close"]].max(axis=1)
    out.loc[faux, "low"] = out.loc[faux, ["open", "close"]].min(axis=1)
    out["high"] = out[["open", "high", "low", "close"]].max(axis=1)
    out["low"] = out[["open", "high", "low", "close"]].min(axis=1)
    return out


def _source_fichier(sym: str, source: str) -> Path:
    if source == "binance":
        return BINANCE / f"{sym}_M15.csv"
    return dm.DOSSIER_M15 / f"{sym}_M15.csv"


def matrice(sym: str, source: str = "dukascopy", week_end: bool = False, cache: Path | None = CACHE) -> dict:
    """Journées calendaires x 96 quarts d'heure (O, H, L, C, V) ; valide = jour tradé avec >= 92 bougies.
    Même construction que bitcoin_journee.matrice (bouchage identique)."""
    f = _source_fichier(sym, source)
    version = int(f.stat().st_mtime) if f.exists() else 0
    filtre = "_filtre7j" if source == "binance" else ""
    fichier = None if cache is None else cache / f"{source}_{sym}_{'7j' if week_end else '5j'}_{version}{filtre}.npz"
    if fichier is not None and fichier.exists():
        z = np.load(fichier)
        return {k: z[k] for k in z.files} | {"jours": pd.DatetimeIndex(z["jours"]), "sym": sym, "source": source}
    df = dm.charger(sym, pd.Timestamp("2100-01-01")) if source == "dukascopy" else _binance(sym)
    t = pd.to_datetime(df["time"])
    jour = t.dt.normalize()
    jours = pd.date_range(jour.min(), jour.max(), freq="D")
    i = ((jour - jours[0]).dt.days).to_numpy()
    k = (t.dt.hour * 4 + t.dt.minute // 15).to_numpy()
    O, H, L, C = (np.full((len(jours), 96), np.nan) for _ in range(4))
    V = np.zeros((len(jours), 96))
    for X, col in ((O, "open"), (H, "high"), (L, "low"), (C, "close")):
        X[i, k] = df[col].to_numpy()
    V[i, k] = np.nan_to_num(df["volume"].to_numpy(float))
    del df, t, jour
    nb = np.isfinite(C).sum(1)
    jt = (jours.dayofweek < 7) if week_end else (jours.dayofweek < 5)
    valide = np.asarray(jt) & (nb >= BARRES_MIN)
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
    V[~valide] = 0.0
    m = {"O": O, "H": H, "L": L, "C": C, "V": V, "valide": valide, "jours": jours, "sym": sym, "source": source}
    if fichier is not None:
        fichier.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(fichier, O=O, H=H, L=L, C=C, V=V, valide=valide, jours=jours.to_numpy())
    return m


def prix(m: dict, d, M):
    """Prix à la minute M (multiple de 15) du jour d (tableaux acceptés)."""
    d, M = np.asarray(d), np.asarray(M)
    return np.where(M == 0, m["O"][d, 0], m["C"][d, np.maximum(M // 15 - 1, 0)])


def agitation_14j(m: dict) -> np.ndarray:
    v = np.flatnonzero(m["valide"])
    r = pd.Series(m["C"][v, 95]).pct_change()
    a = np.full(len(m["jours"]), np.nan)
    a[v] = r.rolling(JOURS_AGIT).std().shift(1).to_numpy()
    return a


def agitation_24h(m: dict) -> np.ndarray:
    """[jour, k] = écart type des 96 rendements de 15 min se terminant à la clôture de la bougie k, x racine(96)."""
    v = np.flatnonzero(m["valide"])
    q = m["C"][v].ravel()
    s = pd.Series(q).pct_change().rolling(96).std().to_numpy() * math.sqrt(96)
    a = np.full((len(m["jours"]), 96), np.nan)
    a[v] = s.reshape(len(v), 96)
    return a


# ================================================================ signaux
def _heures(m: dict):
    v = np.flatnonzero(m["valide"])
    hH = m["H"][v].reshape(len(v), 24, 4).max(2).ravel()
    hL = m["L"][v].reshape(len(v), 24, 4).min(2).ravel()
    hC = m["C"][v].reshape(len(v), 24, 4)[:, :, 3].ravel()
    return v, hH, hL, hC


def canal(hH, hL, n: int):
    """Plus haut / plus bas des n heures AVANT chaque heure g."""
    return (pd.Series(hH).rolling(n).max().shift(1).to_numpy(), pd.Series(hL).rolling(n).min().shift(1).to_numpy())


def signaux(m: dict, N: int, sortie: str = "milieu") -> list:
    """Liste (jour d, sens, minute d'entrée, minute de sortie) ; identique à bitcoin_journee.var_C pour « milieu »."""
    v, hH, hL, hC = _heures(m)
    hautN, basN = canal(hH, hL, N)
    if sortie == "oppose":
        hautX, basX = canal(hH, hL, max(1, N // 2))
    out = []
    for j, d in enumerate(v):
        pos, m_in = 0, 0
        for h in range(1, 24):
            g = j * 24 + h - 1
            if not (np.isfinite(hautN[g]) and np.isfinite(basN[g])):
                continue
            c = hC[g]
            if sortie == "milieu":
                mil = (hautN[g] + basN[g]) / 2
                sort_achat, sort_vente = c < mil, c > mil
            else:
                sort_achat, sort_vente = c < basX[g], c > hautX[g]
            if pos > 0 and sort_achat:
                out.append((d, 1, m_in, h * 60)); pos = 0
            elif pos < 0 and sort_vente:
                out.append((d, -1, m_in, h * 60)); pos = 0
            if pos == 0 and h <= 22:
                if c > hautN[g]:
                    pos, m_in = 1, h * 60
                elif c < basN[g]:
                    pos, m_in = -1, h * 60
        if pos != 0:
            out.append((d, pos, m_in, FIN))
    return out


def trades(m: dict, reg: Reglages, frais) -> pd.DataFrame:
    """Trades (un par avis) : prix, rendement, pire point (adv_achat / adv_vente = pire écart en part du prix d'entrée,
    point d'entrée compris), agitation connue à l'entrée, frais aller-retour (part du montant). `frais` = nombre ou
    fonction(prix d'entrée) -> tableau."""
    ag14 = agitation_14j(m)
    ag24 = agitation_24h(m) if reg.taille == "24h" else None
    morceaux = []
    for N in reg.N:
        s = signaux(m, N, reg.sortie)
        if not s:
            continue
        a = np.array(s)
        d, sens, me, ms = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
        assert ((0 <= me) & (me < ms) & (ms <= FIN)).all()
        e, x = prix(m, d, me), prix(m, d, ms)
        k0, k1 = me // 15, ms // 15
        lo = np.array([m["L"][dd, a0:a1].min() for dd, a0, a1 in zip(d, k0, k1)])
        hi = np.array([m["H"][dd, a0:a1].max() for dd, a0, a1 in zip(d, k0, k1)])
        ag = ag14[d] if ag24 is None else ag24[d, k0 - 1]
        morceaux.append(pd.DataFrame({
            "jour": m["jours"][d], "d": d, "N": N, "poids": 1.0 / len(reg.N), "sens": sens, "m_entree": me,
            "m_sortie": ms, "e": e, "x": x, "r_prix": x / e - 1, "adv_achat": lo / e - 1, "adv_vente": 1 - hi / e,
            "agitation": ag, "quarts": k1 - k0}))
    if not morceaux:
        return pd.DataFrame(columns=["jour", "d", "N", "poids", "sens", "m_entree", "m_sortie", "e", "x", "r_prix",
                                     "adv_achat", "adv_vente", "agitation", "quarts", "frais"])
    t = pd.concat(morceaux, ignore_index=True)
    t = t[np.isfinite(t["agitation"]) & (t["agitation"] > 0) & np.isfinite(t["r_prix"])]
    t = t.sort_values(["d", "m_entree", "N"], kind="stable").reset_index(drop=True)
    t["frais"] = frais(t["e"].to_numpy()) if callable(frais) else float(frais)
    return t


def expositions(t: pd.DataFrame, cible: float, plafond: float = 1.0) -> np.ndarray:
    return t["poids"].to_numpy() * np.minimum(plafond, cible / t["agitation"].to_numpy())


def jours_tradables(m: dict) -> pd.DatetimeIndex:
    a = agitation_14j(m)
    return m["jours"][m["valide"] & np.isfinite(a)]


# ================================================================ chemins du jour
class Chemins:
    """Valeur du compte (part du compte, depuis le matin) au pire point de chaque quart d'heure, par jour."""

    def __init__(self, m: dict, t: pd.DataFrame):
        self.n = len(t)
        self.d = t["d"].to_numpy()
        self.sens = t["sens"].to_numpy()
        if self.n == 0:
            return
        k0, k1 = (t["m_entree"].to_numpy() // 15)[:, None], (t["m_sortie"].to_numpy() // 15)[:, None]
        e = t["e"].to_numpy()[:, None]
        K = np.arange(96)[None, :]
        Lr = m["L"][self.d] / e - 1
        Hr = 1 - m["H"][self.d] / e
        premier = K == k0
        Lr = np.where(premier, np.minimum(Lr, 0), Lr)
        Hr = np.where(premier, np.minimum(Hr, 0), Hr)
        ouvert, apres = (K >= k0) & (K < k1), K >= k1
        fin = t["r_prix"].to_numpy()[:, None]
        self.A = np.where(ouvert, Lr, 0.0) + np.where(apres, fin, 0.0)        # achat
        self.Vt = np.where(ouvert, Hr, 0.0) + np.where(apres, -fin, 0.0)      # vente
        self.F = (K >= k0) * t["frais"].to_numpy()[:, None]
        self.jours_d, self.idx = np.unique(self.d, return_index=True)
        self.dates = m["jours"][self.jours_d]

    def jour(self, expo: np.ndarray, signes: np.ndarray | None = None) -> pd.DataFrame:
        if self.n == 0:
            return pd.DataFrame(np.zeros((0, 96)))
        s = self.sens if signes is None else self.sens * signes
        val = (np.where((s > 0)[:, None], self.A, self.Vt) - self.F) * expo[:, None]
        W = np.add.reduceat(val, self.idx, axis=0)
        return pd.DataFrame(W, index=self.dates)


def additionner(chemins: list[pd.DataFrame], jours: pd.DatetimeIndex) -> np.ndarray:
    W = np.zeros((len(jours), 96))
    for c in chemins:
        if len(c):
            W += c.reindex(jours, fill_value=0.0).to_numpy()
    return W


def apres_arret(W: np.ndarray, arret: float | None, mult: float = 1.0):
    """(gain du jour, pire point du jour <= 0) après l'arrêt de la journée (taille x mult)."""
    W = W * mult
    g = W[:, 95].copy()
    pire = W.min(1)
    w = np.minimum(pire, 0.0)
    if arret:
        touche = pire <= -arret
        g[touche] = -(arret + GLISSEMENT_ARRET)
        w[touche] = g[touche]
    return g, w


def premiere_touche(W: np.ndarray, arret: float | None) -> np.ndarray:
    """Quart d'heure où l'arrêt du jour se déclenche (96 = jamais) : les signaux après ce moment n'existent pas."""
    if not arret:
        return np.full(len(W), 96)
    t = W <= -arret
    return np.where(t.any(1), t.argmax(1), 96)


# ================================================================ challenge FTMO
MULTS = (1.0, 0.5, 0.25)


def mult_mur(v_phase: float) -> float:
    dist = 0.10 + v_phase
    return 1.0 if dist >= 0.06 else (0.5 if dist >= 0.04 else 0.25)


def challenge(W: np.ndarray, arret: float | None, reduction: bool = False, pas: int = 10) -> dict:
    niv = {mu: apres_arret(W, arret, mu) for mu in (MULTS if reduction else (1.0,))}
    g1, w1 = niv[1.0]
    n = len(g1)
    R = M = I = 0
    jr = []
    if not reduction:
        cs = np.r_[0.0, np.cumsum(g1)]
        for d0 in range(0, n, pas):
            i, ok, fini = d0, True, False
            for but in (0.10, 0.05):
                base = cs[i]
                v_fin, v_deb = cs[i + 1:] - base, cs[i:-1] - base
                mort = (w1[i:] <= -0.05) | (v_deb + w1[i:] <= -0.10)
                gagne = v_fin >= but
                im = np.argmax(mort) if mort.any() else n
                ig = np.argmax(gagne) if gagne.any() else n
                if im == n and ig == n:
                    fini = False
                    break
                if im <= ig:
                    ok = False
                    break
                i, fini = i + ig + 1, True
            if not ok:
                M += 1
            elif fini:
                R += 1; jr.append(i - d0)
            else:
                I += 1
    else:
        G = {mu: niv[mu][0].tolist() for mu in niv}
        Wm = {mu: niv[mu][1].tolist() for mu in niv}
        for d0 in range(0, n, pas):
            i, ok, fini = d0, True, False
            for but in (0.10, 0.05):
                v, fini = 0.0, False
                while i < n:
                    mu = mult_mur(v)
                    ww = Wm[mu][i]
                    if ww <= -0.05 or v + ww <= -0.10:
                        ok, fini = False, True
                        break
                    v += G[mu][i]
                    i += 1
                    if v >= but:
                        fini = True
                        break
                if not ok or not fini:
                    break
            if not ok:
                M += 1
            elif fini:
                R += 1; jr.append(i - d0)
            else:
                I += 1
    tot = max(1, R + M + I)
    return {"reussis_pct": 100 * R / tot, "morts_pct": 100 * M / tot, "inacheves_pct": 100 * I / tot,
            "jours_median": float(np.median(jr)) if jr else None}


# ================================================================ un marché, un compte
class Marche:
    """Un marché préparé pour des réglages : trades, chemins, jours tradables."""

    def __init__(self, sym: str, source: str, reg: Reglages, frais, cache: Path | None = CACHE):
        self.sym, self.source, self.reg = sym, source, reg
        m = matrice(sym, source, reg.week_end, cache)
        self.jours = jours_tradables(m)
        self.t = trades(m, reg, frais)
        self.chemins = Chemins(m, self.t)
        self.m = m

    def liberer_matrice(self):
        self.m = None

    def chemin(self, cible: float, signes=None) -> pd.DataFrame:
        return self.chemins.jour(expositions(self.t, cible, self.reg.plafond), signes)

    def force(self, cible: float, de=None, a=None) -> float:
        t = self.t
        sel = np.ones(len(t), bool)
        if de is not None:
            sel = (t["jour"] >= de).to_numpy() & (t["jour"] < a).to_numpy()
        b = (expositions(t, cible, self.reg.plafond) * t["sens"].to_numpy() * t["r_prix"].to_numpy())[sel]
        return float(b.mean() / b.std(ddof=1) * math.sqrt(len(b))) if len(b) > 20 and b.std() > 0 else float("nan")

    def signes_jumeaux(self, k: int, graine: int = 7) -> list[np.ndarray]:
        rng = np.random.default_rng(graine)
        return [rng.choice([-1, 1], len(self.t)) for _ in range(k)]


def serie_jour(W: np.ndarray, jours: pd.DatetimeIndex, arret, mult: float = 1.0) -> tuple[pd.Series, pd.Series]:
    g, w = apres_arret(W, arret, mult)
    return pd.Series(g, index=jours), pd.Series(w, index=jours)


def rapport_gain_risque(g: pd.Series) -> float:
    """Gain moyen par jour / agitation des gains, ramené à l'année (jours tradés réels par an)."""
    if len(g) < 60 or g.std() == 0:
        return float("nan")
    ans = max((g.index[-1] - g.index[0]).days, 1) / 365.25
    par_an = len(g) / ans
    return float(g.mean() / g.std(ddof=1) * math.sqrt(par_an))


def mesures(g: pd.Series) -> dict:
    if len(g) == 0:
        return {}
    ans = max((g.index[-1] - g.index[0]).days, 1) / 365.25
    courbe = g.cumsum()
    return {"jours": int(len(g)), "pct_mois": float(g.sum() / (ans * 12) * 100), "rapport": rapport_gain_risque(g),
            "baisse_max_pct": float((courbe - courbe.cummax()).min() * 100), "pire_jour_pct": float(g.min() * 100)}


# ================================================================ faits connus à l'entrée (pour COLLAPSAR, amélioration 7)
def faits_entree(m: dict, t: pd.DataFrame, autre: dict | None = None, n_recent: int = 10) -> pd.DataFrame:
    """Pour chaque signal (ligne de `t`, sortie de `trades`), les faits CONNUS à l'entrée (rien d'après la clôture de
    la bougie qui précède l'entrée) listés dans le cahier (CASSURE_AMELIORATION.md, amélioration 7) :
    largeur du canal / agitation, heure, jour, tendance 1 j / 5 j / 20 j, accord avec l'autre marché (BTC <-> ETH),
    volume relatif, résultat récent de la stratégie (moyenne des 10 derniers trades déjà fermés du marché, par unité
    d'exposition, frais compris), résultat du jour avant l'entrée (trades fermés ce jour, pesés par le poids de l'avis).
    La distance aux murs FTMO dépend de l'état du challenge : `distance_murs(v_phase, v_jour)` à appeler dans la boucle
    du challenge."""
    v = np.flatnonzero(m["valide"])
    pos = np.full(len(m["jours"]), -1)
    pos[v] = np.arange(len(v))
    qC, qV = m["C"][v].ravel(), m["V"][v].ravel()
    _, hH, hL, hC = _heures(m)
    d, a = t["d"].to_numpy(), t["m_entree"].to_numpy()
    g = pos[d] * 96 + a // 15 - 1
    c = qC[g]
    ag14 = agitation_14j(m)[d]

    def recul(n):
        r = np.full(len(g), np.nan)
        ok = g - n >= 0
        r[ok] = c[ok] / qC[g[ok] - n] - 1
        return r

    larg = np.full(len(t), np.nan)
    gh = pos[d] * 24 + a // 60 - 1
    for N in np.unique(t["N"]):
        hN, bN = canal(hH, hL, int(N))
        s = (t["N"] == N).to_numpy()
        larg[s] = (hN[gh[s]] - bN[gh[s]]) / c[s] / ag14[s]
    cv = np.r_[0.0, np.cumsum(qV)]
    v_heure = cv[g + 1] - cv[np.maximum(g - 3, 0)]
    v_20j = (cv[g + 1] - cv[np.maximum(g - 1919, 0)]) / np.minimum(g + 1, 1920) * 4
    vol_rel = np.where(v_20j > 0, v_heure / np.where(v_20j > 0, v_20j, 1), np.nan)
    # résultat récent : trades du même marché FERMÉS avant l'entrée (par unité d'exposition, frais compris)
    net = t["sens"].to_numpy() * t["r_prix"].to_numpy() - t["frais"].to_numpy()
    t_in = d * 1440 + a
    t_out = d * 1440 + t["m_sortie"].to_numpy()
    ordre = np.argsort(t_out, kind="stable")
    cum = np.r_[0.0, np.cumsum(net[ordre])]
    nb = np.searchsorted(t_out[ordre], t_in, side="right")
    recent = (cum[nb] - cum[np.maximum(nb - n_recent, 0)]) / np.maximum(np.minimum(nb, n_recent), 1)
    debut_jour = np.searchsorted(t_out[ordre], d * 1440, side="left")
    cum_p = np.r_[0.0, np.cumsum((net * t["poids"].to_numpy())[ordre])]       # pesé par le poids de l'avis
    jour_avant = cum_p[nb] - cum_p[np.minimum(debut_jour, nb)]
    faits = pd.DataFrame({
        "jour": t["jour"].to_numpy(), "d": d, "N": t["N"].to_numpy(), "sens": t["sens"].to_numpy(), "m_entree": a,
        "largeur_canal_sur_agitation": larg, "heure": a // 60, "jour_semaine": m["jours"][d].dayofweek,
        "tendance_1j": recul(96), "tendance_5j": recul(480), "tendance_20j": recul(1920),
        "agitation_14j": ag14, "volume_relatif": vol_rel, "resultat_recent": recent, "resultat_jour_avant": jour_avant})
    if autre is not None:
        vo = np.flatnonzero(autre["valide"])
        po = pd.Series(np.arange(len(vo)), index=autre["jours"][vo])
        qo = autre["C"][vo].ravel()
        jo = po.reindex(m["jours"][d]).to_numpy()
        ok = np.isfinite(jo)
        go = np.where(ok, np.nan_to_num(jo).astype(int) * 96 + a // 15 - 1, 0)
        r = np.full(len(t), np.nan)
        ok2 = ok & (go - 96 >= 0)
        r[ok2] = qo[go[ok2]] / qo[go[ok2] - 96] - 1
        faits["autre_24h"] = r
        faits["accord_autre"] = np.sign(r) * faits["sens"].to_numpy()
    return faits


def distance_murs(v_phase: float, v_jour: float) -> tuple[float, float]:
    """(distance au mur des -10 % de la phase, distance au mur des -5 % du jour), en part du compte."""
    return 0.10 + v_phase, 0.05 + v_jour
