"""L'AVIS SUR LES MARCHÉS (18/10/2026, idée validée par le chef de projet : « une IA dotée de son propre sens et avis
sur les marchés »). L'AVIS est séparé de l'exécution : chaque jour de semaine à 08h00 heure du serveur (avant
l'ouverture européenne), pour chaque marché, un sens (hausse / baisse / rien), une CONVICTION en % (calibrée : quand il
dit 70 %, ça doit arriver ~70 %), un horizon (1, 5, 20 jours) et les 3 RAISONS qui pèsent le plus ce jour-là.

Ce que l'avis voit (SANS FUTUR, plan figé `vie/hypernova/avis/plan_fige.md`) : tendance de fond 20 / 60 / 120 j,
mouvement des derniers jours, ses zones journalières et 4 h (distance, prix dedans), structure journalière, agitation et
compression, peur des marchés et tension du monde (valeur du jour J lue à J+1 08h00), foule crypto (C1), jour de la
semaine et annonces, famille du marché.
Modèles PETITS : régression logistique régularisée ou arbres boostés de profondeur 2, un par horizon, entraînés sur le
panel des 66 marchés (cibles terminées avant 2022), calibrés sur 2022.

Depuis Test_IA :
  venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.precision.avis construire   (tables des 66 marchés)
  ...                                                         apprendre    (modèles + calibration, <= 2022)
  ...                                                         mesurer      (2023 = mesure, 2024-09/2025 = lecture)
  ...                                                         matin [--date AAAA-MM-JJ] [--marches A,B]  (l'avis du jour)
L'exécution (avis + ses zones) est dans `regarder/pistes/avis_execution.py`. Aucun direct n'est lancé ici.
Rien n'est lu à partir de reglages.periodes.fin_donnees (12 mois cachés).
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.ecole.precision import direction as DI
from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision.reglages import VIE

SORTIE = VIE / "avis"
QUINZE_NS = 15 * 60 * 10 ** 9
HEURE_NS = 3600 * 10 ** 9
JOUR_NS = 86400 * 10 ** 9
SEMAINE_NS = 7 * JOUR_NS
HEURE_AVIS = 8                                  # 08h00 heure du serveur
VIEUX_MAX_J = 3                                 # dernière bougie plus vieille que 3 jours : pas d'avis ce jour
HORIZONS = (1, 5, 20)
CONVICTION_MIN = 0.55                           # sous 55 % : « rien »
COUPE_APPRENTISSAGE = pd.Timestamp("2022-01-01")
COUPE_REGLAGE = pd.Timestamp("2023-01-01")
COUPE_MESURE = pd.Timestamp("2024-01-01")
FIN = pd.Timestamp("2025-10-01")
FAMILLES = ("crypto", "metal", "energie", "indice", "devise", "autre")
NOM_FAM = {"crypto": "cryptos", "metal": "métaux", "energie": "énergie", "indice": "indices", "devise": "devises",
           "autre": "autres (obligation)"}
NOM_MARCHE = {"XAUUSD": "Or", "XAUUSD@M1": "Or (minute)", "XAGUSD": "Argent", "LIGHTCMDUSD": "Pétrole (WTI)",
              "BRENTCMDUSD": "Pétrole (Brent)", "GASCMDUSD": "Gaz", "USA500IDXUSD": "S&P 500", "US500@M1": "S&P 500 (minute)",
              "USATECHIDXUSD": "Nasdaq", "US100@M1": "Nasdaq (minute)", "USA30IDXUSD": "Dow Jones", "DEUIDXEUR": "DAX",
              "FRAIDXEUR": "CAC 40", "EUSIDXEUR": "Euro Stoxx 50", "GBRIDXGBP": "FTSE 100", "JPNIDXJPY": "Nikkei",
              "AUSIDXAUD": "ASX 200", "USTBONDTRUSD": "Obligation US", "BTCUSDT": "Bitcoin", "ETHUSDT": "Ether",
              "EURUSD": "Euro/dollar", "EURUSD@M1": "Euro/dollar (minute)", "USDJPY": "Dollar/yen", "GBPUSD": "Livre/dollar",
              "USDCHF": "Dollar/franc", "AUDUSD": "Dollar australien", "USDCAD": "Dollar/canadien"}

# ---------------------------------------------------------------------------------------------- ce que l'avis voit
BASE = ("t20", "t60", "t120", "mv1", "mv5", "struct_d1", "place_d1",
        "zdem_d1", "zsup_d1", "zdem_h4", "zsup_h4", "dans_dem", "dans_sup",
        "compression", "agit_pct", "vix_niveau", "vix_saut", "ovx_saut", "gvz_saut", "courbe_peur", "tension",
        "c1", "lundi", "vendredi", "annonce")
FAM_COLS = tuple(f"fam_{f}" for f in FAMILLES)
CROISES = (("vix_saut", "energie"), ("vix_saut", "indice"), ("vix_saut", "crypto"), ("vix_saut", "metal"),
           ("gvz_saut", "metal"), ("ovx_saut", "energie"), ("t60", "crypto"), ("t60", "devise"), ("t60", "indice"),
           ("courbe_peur", "indice"), ("tension", "metal"), ("tension", "energie"))
CROISES_COLS = tuple(f"{a}*{f}" for a, f in CROISES)
ENTREES = BASE + FAM_COLS + CROISES_COLS


def famille(nom: str) -> str:
    f = D.famille(nom)
    return f if f in FAMILLES else "autre"


def nom_lisible(nom: str) -> str:
    return NOM_MARCHE.get(nom, nom.replace("USDT", "").replace("@M1", " (minute)"))


# ============================================================================================== 1. table d'un marché
def instants(t15: np.ndarray, heure: int = HEURE_AVIS) -> tuple[np.ndarray, np.ndarray]:
    """(instant de l'avis, ligne de 15 min connue) pour chaque jour de semaine : la dernière bougie FERMÉE à J 08h00."""
    t15 = np.asarray(t15, np.int64)
    j0, j1 = t15[0] - t15[0] % JOUR_NS, t15[-1] - t15[-1] % JOUR_NS
    J = np.arange(j0, j1 + JOUR_NS, JOUR_NS, dtype=np.int64)
    J = J[((J // JOUR_NS) + 3) % 7 < 5]
    inst = J + heure * HEURE_NS
    r = np.searchsorted(t15 + QUINZE_NS, inst, side="right") - 1
    ok = (r >= 0) & (inst - (t15[np.clip(r, 0, None)] + QUINZE_NS) <= VIEUX_MAX_J * JOUR_NS)
    inst, r = inst[ok], r[ok]
    garde = np.r_[True, r[1:] != r[:-1]]
    return inst[garde], r[garde]


def _zone_proche(x: dict, u: str, rows: np.ndarray, cote: int, c: np.ndarray):
    """(haut, bas) de la zone vivante la plus proche (cote 0 = demande, 1 = offre) de l'unité u à la ligne `rows`."""
    lg = np.asarray(x[u]["ligne"]).astype(np.int64)[rows]
    knn = np.asarray(x[u]["knn"])
    ok = lg >= 0
    z = np.where(ok, knn[np.clip(lg, 0, None), cote, 0], -1).astype(np.int64)
    ok &= z >= 0
    top = np.where(ok, np.asarray(x[u]["top"], np.float64)[np.clip(z, 0, None)], np.nan)
    bot = np.where(ok, np.asarray(x[u]["bot"], np.float64)[np.clip(z, 0, None)], np.nan)
    return top, bot


def table_marche(nom: str, x: dict | None = None) -> pd.DataFrame:
    """Une ligne par jour d'avis : ce que l'avis voit à 08h00 (sans futur) et les mouvements des 1 / 5 / 20 jours
    d'avis suivants (cibles, futur : servent seulement à apprendre et à juger)."""
    from collapsar.ecole.precision import monde as MP
    from collapsar.ecole.precision import structure as S
    from collapsar.regarder.pistes import mouvements as M
    if x is None:
        x = S.lire(nom, False)
    t15 = np.asarray(x["t15"], np.int64)
    c = np.asarray(x["c"], np.float64)
    A = np.asarray(x["A"], np.float64)
    inst, r = instants(t15)
    n = len(r)
    p, a = c[r], A[r]
    df = pd.DataFrame({"marche": nom, "inst": inst, "ligne": r, "prix": p, "A": a})
    jours, clo = DI.clotures_jour(t15, c)
    _, forces = DI.tendance_aux(jours, clo, inst)
    df["t20"], df["t60"], df["t120"] = forces[:, 0], forces[:, 1], forces[:, 2]
    with np.errstate(invalid="ignore", divide="ignore"):
        for k, nm in ((1, "mv1"), (5, "mv5")):
            prev = np.r_[np.full(k, np.nan), p[:-k]] if n > k else np.full(n, np.nan)
            df[nm] = np.clip(np.nan_to_num((p - prev) / a), -6, 6)
    # structure journalière
    lg = np.asarray(x["D1"]["ligne"]).astype(np.int64)[r]
    sw = np.asarray(x["D1"]["sw"], np.float64)[np.clip(lg, 0, None)]
    sw[lg < 0] = np.nan
    with np.errstate(invalid="ignore", divide="ignore"):
        st = np.nan_to_num(np.sign(sw[:, 0] - sw[:, 1])) + np.nan_to_num(np.sign(sw[:, 2] - sw[:, 3]))
        place = (p - sw[:, 2]) / (sw[:, 0] - sw[:, 2])
    df["struct_d1"] = st
    df["place_d1"] = np.clip(np.nan_to_num(place, nan=0.5), -1, 2)
    df["sommet_d1"], df["creux_d1"] = sw[:, 0], sw[:, 2]
    lg4 = np.asarray(x["H4"]["ligne"]).astype(np.int64)[r]
    sw4 = np.asarray(x["H4"]["sw"], np.float64)[np.clip(lg4, 0, None)]
    sw4[lg4 < 0] = np.nan
    df["sommet_h4"], df["creux_h4"] = sw4[:, 0], sw4[:, 2]
    # ses zones
    dans_d, dans_s = np.zeros(n, bool), np.zeros(n, bool)
    for u in ("D1", "H4"):
        dt, db = _zone_proche(x, u, r, 0, c)
        st_, sb = _zone_proche(x, u, r, 1, c)
        with np.errstate(invalid="ignore", divide="ignore"):
            zd = (p - dt) / a
            zs = (sb - p) / a
        dans_d |= (p <= dt) & (p >= db)
        dans_s |= (p >= sb) & (p <= st_)
        df[f"zdem_{u.lower()}"] = np.clip(np.nan_to_num(zd, nan=10.0), -3, 10)
        df[f"zsup_{u.lower()}"] = np.clip(np.nan_to_num(zs, nan=10.0), -3, 10)
        df[f"dem_haut_{u}"], df[f"dem_bas_{u}"], df[f"off_bas_{u}"], df[f"off_haut_{u}"] = dt, db, sb, st_
    df["dans_dem"], df["dans_sup"] = dans_d.astype(float), dans_s.astype(float)
    # agitation
    df["compression"] = np.clip(np.nan_to_num(M.compression(x, r), nan=1.0), 0, 4)
    df["agit_pct"] = np.clip(np.nan_to_num(a / p * 100, nan=1.0), 0, 30)
    # monde (J+1 08h00) et foule
    W = MP.valeurs_a(inst)
    ix = {k: i for i, k in enumerate(MP.NOMS)}
    for col, src in (("vix_niveau", "vix_niveau"), ("vix_saut", "vix_saut"), ("ovx_saut", "ovx_saut"),
                     ("gvz_saut", "gvz_saut"), ("courbe_peur", "courbe_peur"), ("tension", "tension_gpr")):
        df[col] = W[:, ix[src]].astype(float)
    df["c1"] = DI.c1(nom, inst).astype(float)
    # calendrier
    dow = ((inst // JOUR_NS) + 3) % 7
    df["lundi"], df["vendredi"] = (dow == 0).astype(float), (dow == 4).astype(float)
    df["annonce"] = np.isin(inst - inst % JOUR_NS, M.jours_annonces(nom)).astype(float)
    fam = famille(nom)
    for f in FAMILLES:
        df[f"fam_{f}"] = float(fam == f)
    for a_, f in CROISES:
        df[f"{a_}*{f}"] = df[a_] * df[f"fam_{f}"]
    df["age_j"] = (inst - t15[0]) / JOUR_NS
    # cibles (le FUTUR : seulement pour apprendre et juger)
    for h in HORIZONS:
        k = np.arange(n) + h
        okh = k < n
        kk = np.clip(k, 0, n - 1)
        with np.errstate(invalid="ignore", divide="ignore"):
            df[f"ret{h}"] = np.where(okh, p[kk] / p - 1, np.nan) * 100
            df[f"mvA{h}"] = np.where(okh, (p[kk] - p) / a, np.nan)
        df[f"fin{h}"] = np.where(okh, inst[kk], -1)
    return df


def construire(dire=print) -> pd.DataFrame:
    import time
    t0 = time.time()
    parts = []
    for nom in D.univers():
        try:
            parts.append(table_marche(nom))
        except Exception as e:                                   # un marché sans données ne doit pas tout arrêter
            dire(f"{nom} : IMPOSSIBLE ({type(e).__name__}: {e})")
            continue
        dire(f"{nom} : {len(parts[-1])} jours ({time.time() - t0:.0f} s)")
    P = pd.concat(parts, ignore_index=True)
    SORTIE.mkdir(parents=True, exist_ok=True)
    P.to_pickle(SORTIE / "panel.pkl")
    return P


def panel() -> pd.DataFrame:
    return pd.read_pickle(SORTIE / "panel.pkl")


# ============================================================================================== 2. modèles
def lignes(P: pd.DataFrame, h: int, de: pd.Timestamp | None, a: pd.Timestamp) -> np.ndarray:
    """Avis dont la cible à h jours est TERMINÉE avant `a` (et l'avis donné à partir de `de`), assez d'historique."""
    fin = P[f"fin{h}"].to_numpy(np.int64)
    ok = (fin > 0) & (fin < a.value) & np.isfinite(P[f"ret{h}"].to_numpy()) & (P[f"ret{h}"].to_numpy() != 0)
    ok &= (P["age_j"].to_numpy() >= 130) & np.isfinite(P["A"].to_numpy()) & (P["A"].to_numpy() > 0)
    if de is not None:
        ok &= P["inst"].to_numpy(np.int64) >= de.value
    return ok


class Avis:
    """Les modèles d'un horizon : logistique (toujours, pour les raisons) + éventuellement arbres ; calibration."""

    def __init__(self, h: int):
        self.h = h

    def _X(self, P):
        return P[list(ENTREES)].to_numpy(np.float64)

    def apprendre(self, P: pd.DataFrame, dire=print):
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import log_loss
        h = self.h
        tr = lignes(P, h, None, COUPE_APPRENTISSAGE)
        rg = lignes(P, h, COUPE_APPRENTISSAGE, COUPE_REGLAGE)
        X, y = self._X(P), (P[f"ret{h}"].to_numpy() > 0).astype(int)
        self.mu, self.sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        Z = (X - self.mu) / self.sd
        res = {}
        for C in (0.01, 0.1, 1.0):
            m = LogisticRegression(C=C, max_iter=2000).fit(Z[tr], y[tr])
            res[f"logistique C={C}"] = (m, log_loss(y[rg], m.predict_proba(Z[rg])[:, 1]))
        gb = HistGradientBoostingClassifier(max_depth=2, max_iter=200, learning_rate=0.05, min_samples_leaf=500,
                                            l2_regularization=1.0, random_state=0).fit(X[tr], y[tr])
        res["arbres profondeur 2"] = (gb, log_loss(y[rg], gb.predict_proba(X[rg])[:, 1]))
        base = float(y[tr].mean())
        res_base = log_loss(y[rg], np.full(rg.sum(), base))
        self.choix_pertes = {k: v[1] for k, v in res.items()} | {"base (taux de hausse <= 2021)": res_base}
        lg = {k: v for k, v in res.items() if k.startswith("logistique")}
        self.cle_log = min(lg, key=lambda k: lg[k][1])
        self.log = lg[self.cle_log][0]
        self.cle = min(res, key=lambda k: res[k][1])
        self.modele = res[self.cle][0]
        # calibration sur 2022 : pente seule sur le logit brut (SANS décalage : un décalage appris sur une seule année
        # importe le sens de CETTE année — 1er essai du 18/10 : 2022 baissière -> l'avis disait « baisse » partout)
        self.cal, self.pente_libre = calibrer(self.brut(P[rg]), y[rg])
        self.n_app, self.n_reg = int(tr.sum()), int(rg.sum())
        dire(f"horizon {h} j : {self.n_app} avis d'apprentissage, {self.n_reg} de réglage ; pertes 2022 : "
             + ", ".join(f"{k} {v:.5f}" for k, v in self.choix_pertes.items()) + f" -> {self.cle}")
        return self

    def brut(self, P: pd.DataFrame) -> np.ndarray:
        X = self._X(P)
        if self.cle.startswith("logistique"):
            return self.modele.predict_proba((X - self.mu) / self.sd)[:, 1]
        return self.modele.predict_proba(X)[:, 1]

    def proba(self, P: pd.DataFrame) -> np.ndarray:
        """Probabilité CALIBRÉE de hausse à h jours."""
        return self.cal.predict_proba(_logit(self.brut(P))[:, None])[:, 1]

    def contributions(self, P: pd.DataFrame) -> np.ndarray:
        """[n, len(ENTREES)] poids x valeur (centrée-réduite) de la régression logistique : ce qui pousse à la hausse (>0)
        ou à la baisse (<0)."""
        Z = (self._X(P) - self.mu) / self.sd
        return Z * self.log.coef_[0][None, :]


def _logit(p):
    p = np.clip(np.asarray(p, np.float64), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def calibrer(p_brut: np.ndarray, y: np.ndarray):
    """Calibration sur l'année de réglage : p = sigmoïde(pente x logit(p_brut)), SANS décalage (un décalage appris sur une
    seule année importe le sens de cette année : 1er essai du 18/10, 2022 baissière -> « baisse » partout) et pente
    bornée à 0 (une pente NÉGATIVE retournerait le modèle : un avis ne retourne jamais son propre modèle, il n'a
    simplement pas d'avis -> 50 % -> « rien » ; 2e essai du 18/10). Rend (calibrateur, pente libre)."""
    from sklearn.linear_model import LogisticRegression
    cal = LogisticRegression(C=1e6, max_iter=1000, fit_intercept=False).fit(_logit(p_brut)[:, None], np.asarray(y))
    libre = float(cal.coef_[0, 0])
    if libre < 0:
        cal.coef_[:] = 0.0
    return cal, libre


def apprendre(dire=print) -> dict:
    P = panel()
    mods = {h: Avis(h).apprendre(P, dire) for h in HORIZONS}
    with open(SORTIE / "modeles.pkl", "wb") as f:
        pickle.dump(mods, f)
    return mods


def modeles() -> dict:
    with open(SORTIE / "modeles.pkl", "rb") as f:
        return pickle.load(f)


def avis_table(P: pd.DataFrame, mods: dict) -> pd.DataFrame:
    """Ajoute pour chaque horizon : p (hausse, calibrée), sens (+1 / -1 / 0 = rien), conviction (%)."""
    out = P.copy()
    for h, m in mods.items():
        p = m.proba(P)
        conv = np.maximum(p, 1 - p)
        pb = m.brut(P)
        out[f"praw{h}"] = pb
        out[f"convraw{h}"] = np.maximum(pb, 1 - pb) * 100
        out[f"p{h}"] = p
        out[f"conv{h}"] = conv * 100
        out[f"sens{h}"] = np.where(conv >= CONVICTION_MIN, np.where(p > 0.5, 1, -1), 0)
    return out


# ============================================================================================== 3. mesures
TRANCHES = (55, 60, 65, 70)
GROUPES = ("tous",) + FAMILLES
N_DEJA = 1257
N_AVIS = len(HORIZONS) * len(TRANCHES) * len(GROUPES)
N_EXEC = 3 * 4 + 2
N_TOTAL = N_DEJA + N_AVIS + N_EXEC
SEUIL = max(3.0, math.sqrt(2 * math.log(N_TOTAL)))


def _inc(x: np.ndarray, grappes: np.ndarray) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    r = x - x.mean()
    _, inv = np.unique(grappes, return_inverse=True)
    s = np.bincount(inv, weights=r)
    return float(np.sqrt((s ** 2).sum()) / n)


def stats_sens(sens: np.ndarray, ret: np.ndarray, mvA: np.ndarray, inst: np.ndarray, h: int) -> dict:
    m = sens != 0
    n = int(m.sum())
    if n < 20:
        return {"n": n}
    s, rt, mv, t = sens[m], ret[m], mvA[m], inst[m]
    juste = (np.sign(rt) == s).astype(float)
    cap = s * mv
    gr = t // (SEMAINE_NS * max(1, math.ceil(h / 5)))
    inc_j, inc_c = _inc(juste, gr), _inc(cap, gr)
    return {"n": n, "justes_pct": float(juste.mean() * 100), "inc_justes": inc_j * 100,
            "force_justes": float((juste.mean() - 0.5) / inc_j) if inc_j > 0 else float("nan"),
            "capture_A": float(cap.mean()), "inc_A": inc_c,
            "force_A": float(cap.mean() / inc_c) if inc_c > 0 else float("nan"),
            "capture_pct": float((s * rt).mean()), "hausses_pct": float((s > 0).mean() * 100)}


def mesurer_periode(T: pd.DataFrame, de: pd.Timestamp, a: pd.Timestamp, brut: bool = False,
                    tranches=TRANCHES) -> dict:
    """Mesures d'une période ; `brut` : l'avis AVANT calibration (pour information : ce que le modèle a appris <= 2021)."""
    out = {}
    fam = T["marche"].map(famille).to_numpy()
    for h in HORIZONS:
        ok = lignes(T, h, de, a)
        X = T[ok]
        f = fam[ok]
        ret, mv, inst = X[f"ret{h}"].to_numpy(), X[f"mvA{h}"].to_numpy(), X["inst"].to_numpy(np.int64)
        p, conv = X[f"{'praw' if brut else 'p'}{h}"].to_numpy(), X[f"{'convraw' if brut else 'conv'}{h}"].to_numpy()
        sens_tout = np.where(p > 0.5, 1, -1)
        t60 = np.sign(X["t60"].to_numpy()).astype(int)
        r = {"n_avis": int(ok.sum()), "taux_hausse_pct": float((ret > 0).mean() * 100)}
        for g in GROUPES:
            mg = np.ones(len(X), bool) if g == "tous" else (f == g)
            rg = {"tout (>= 50 %)": stats_sens(np.where(mg, sens_tout, 0), ret, mv, inst, h)}
            for tr in tranches:
                rg[f">= {tr} %"] = stats_sens(np.where(mg & (conv >= tr), sens_tout, 0), ret, mv, inst, h)
            rg["repère : toujours la tendance 60 j"] = stats_sens(np.where(mg, t60, 0), ret, mv, inst, h)
            rg["repère : toujours hausse"] = stats_sens(np.where(mg, 1, 0), ret, mv, inst, h)
            r[g] = rg
        # calibration
        y = (ret > 0).astype(float)
        bins = np.arange(0, 101, 5)
        cal = []
        for lo in bins[:-1]:
            mm = (p * 100 >= lo) & (p * 100 < lo + 5)
            if mm.sum() >= 30:
                cal.append({"tranche": f"{lo}-{lo + 5} %", "n": int(mm.sum()), "annonce": float(p[mm].mean() * 100),
                            "arrive": float(y[mm].mean() * 100)})
        w = np.array([c_["n"] for c_ in cal], float)
        ecart = float(np.sum(w * np.abs([c_["annonce"] - c_["arrive"] for c_ in cal])) / w.sum()) if len(w) else float("nan")
        r["calibration"] = cal
        r["ecart_calibration"] = ecart
        r["brier"] = float(np.mean((p - y) ** 2))
        r["brier_base"] = float(np.mean((y.mean() - y) ** 2))
        r["conviction_mediane"] = float(np.median(conv))
        r["part_ge60"] = float((conv >= 60).mean() * 100)
        r["part_ge70"] = float((conv >= 70).mean() * 100)
        out[h] = r
    return out


def mesurer(dire=print) -> dict:
    P = panel()
    mods = modeles()
    T = avis_table(P, mods)
    T.drop(columns=[c for c in T.columns if c.startswith(("dem_", "off_"))]).to_pickle(SORTIE / "avis_panel.pkl")
    res = {"date": datetime.now().isoformat(timespec="seconds"), "seuil": SEUIL, "n_total": N_TOTAL,
           "choix_modeles": {h: {"retenu": m.cle, "pertes_2022": m.choix_pertes, "n_app": m.n_app, "n_reg": m.n_reg}
                             for h, m in mods.items()},
           "poids": {h: dict(zip(ENTREES, map(float, m.log.coef_[0]))) for h, m in mods.items()},
           "reglage_2022": mesurer_periode(T, COUPE_APPRENTISSAGE, COUPE_REGLAGE),
           "mesure_2023": mesurer_periode(T, COUPE_REGLAGE, COUPE_MESURE),
           "lecture_2024_25": mesurer_periode(T, COUPE_MESURE, FIN),
           "pentes_libres_2022": {h: m.pente_libre for h, m in mods.items()},
           "brut": {k: mesurer_periode(T, de, a, brut=True, tranches=(52, 55, 60))
                    for k, (de, a) in (("reglage_2022", (COUPE_APPRENTISSAGE, COUPE_REGLAGE)),
                                       ("mesure_2023", (COUPE_REGLAGE, COUPE_MESURE)),
                                       ("lecture_2024_25", (COUPE_MESURE, FIN)))}}
    (SORTIE / "mesure.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    dire("mesure écrite")
    return res


# ============================================================================================== 3 bis. années glissantes
ANNEES_OOS = tuple(range(2014, 2023))
COUPE_FINALE = pd.Timestamp("2023-01-01")


def calibrer_moyenne(p_brut: np.ndarray, y: np.ndarray):
    """Calibration sur PLUSIEURS années hors échantillon : pente + décalage (= tendance moyenne de ces années), pente
    bornée à 0 (si la pente est négative : décalage seul, le modèle ne sert à rien). Rend (calibrateur, pente libre)."""
    from sklearn.linear_model import LogisticRegression
    z = _logit(p_brut)[:, None]
    cal = LogisticRegression(C=1e6, max_iter=1000).fit(z, np.asarray(y))
    libre = float(cal.coef_[0, 0])
    if libre < 0:
        cal = LogisticRegression(C=1e6, max_iter=1000).fit(np.zeros_like(z), np.asarray(y))
    return cal, libre


class AvisGlissant(Avis):
    """Essai 3 : modèle final appris <= 2022, calibré sur 9 années hors échantillon (2014-2022)."""

    def _ajuster(self, P, tr, cle):
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        X, y = self._X(P), (P[f"ret{self.h}"].to_numpy() > 0).astype(int)
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        if cle == "logistique":
            m = LogisticRegression(C=0.01, max_iter=2000).fit(((X - mu) / sd)[tr], y[tr])
        else:
            m = HistGradientBoostingClassifier(max_depth=2, max_iter=200, learning_rate=0.05, min_samples_leaf=500,
                                               l2_regularization=1.0, random_state=0).fit(X[tr], y[tr])
        return m, mu, sd

    def _predire(self, m, mu, sd, cle, P):
        X = self._X(P)
        return m.predict_proba((X - mu) / sd if cle == "logistique" else X)[:, 1]

    def apprendre(self, P: pd.DataFrame, dire=print):
        from sklearn.metrics import log_loss
        h = self.h
        y = (P[f"ret{h}"].to_numpy() > 0).astype(int)
        oos = {c: np.full(len(P), np.nan) for c in ("logistique", "arbres", "base")}
        masque_oos = np.zeros(len(P), bool)
        for Y in ANNEES_OOS:
            tr = lignes(P, h, None, pd.Timestamp(f"{Y}-01-01"))
            te = lignes(P, h, pd.Timestamp(f"{Y}-01-01"), pd.Timestamp(f"{Y + 1}-01-01"))
            if tr.sum() < 5000 or te.sum() == 0:
                continue
            masque_oos |= te
            oos["base"][te] = y[tr].mean()
            for cle in ("logistique", "arbres"):
                m, mu, sd = self._ajuster(P, tr, cle)
                oos[cle][te] = self._predire(m, mu, sd, cle, P[te])
            dire(f"horizon {h} j : année {Y} prédite ({int(te.sum())} avis, appris sur {int(tr.sum())})")
        self.pertes_oos = {c: float(log_loss(y[masque_oos], oos[c][masque_oos])) for c in oos}
        self.cle = min(("logistique", "arbres"), key=lambda c: self.pertes_oos[c])
        self.cal, self.pente_libre = calibrer_moyenne(oos[self.cle][masque_oos], y[masque_oos])
        self.oos_brut = np.where(masque_oos, oos[self.cle], np.nan)
        tr = lignes(P, h, None, COUPE_FINALE)
        self.modele, self.mu_m, self.sd_m = self._ajuster(P, tr, self.cle)
        self.log, self.mu, self.sd = self._ajuster(P, tr, "logistique")          # pour les raisons
        self.cle_log = "logistique C=0.01"
        self.n_app = int(tr.sum())
        self.choix_pertes = self.pertes_oos
        dire(f"horizon {h} j : pertes hors échantillon 2014-2022 {self.pertes_oos} -> {self.cle} ; pente libre "
             f"{self.pente_libre:.3f}")
        return self

    def brut(self, P: pd.DataFrame) -> np.ndarray:
        return self._predire(self.modele, self.mu_m, self.sd_m, self.cle, P)


def apprendre_glissant(dire=print) -> dict:
    P = panel()
    mods = {h: AvisGlissant(h).apprendre(P, dire) for h in HORIZONS}
    T = avis_table(P, mods)
    for h, m in mods.items():                       # 2014-2022 : les avis HORS ÉCHANTILLON (ce qu'il aurait dit)
        oo = np.isfinite(m.oos_brut)
        pc = m.cal.predict_proba(_logit(np.where(oo, m.oos_brut, 0.5))[:, None])[:, 1]
        T.loc[oo, f"p{h}"] = pc[oo]
        T.loc[oo, f"conv{h}"] = np.maximum(pc, 1 - pc)[oo] * 100
        T.loc[oo, f"sens{h}"] = np.where(np.maximum(pc, 1 - pc)[oo] >= CONVICTION_MIN, np.where(pc[oo] > 0.5, 1, -1), 0)
        T.loc[oo, f"praw{h}"] = m.oos_brut[oo]
        T.loc[oo, f"convraw{h}"] = np.maximum(m.oos_brut, 1 - m.oos_brut)[oo] * 100
    for m in mods.values():
        m.oos_brut = None
    with open(SORTIE / "modeles_v2.pkl", "wb") as f:
        pickle.dump(mods, f)
    T.drop(columns=[c for c in T.columns if c.startswith(("dem_", "off_"))]).to_pickle(SORTIE / "avis_panel_v2.pkl")
    res = {"date": datetime.now().isoformat(timespec="seconds"),
           "choix_modeles": {h: {"retenu": m.cle, "pertes_oos_2014_2022": m.pertes_oos, "pente_libre": m.pente_libre,
                                 "pente": float(m.cal.coef_[0, 0]), "decalage": float(m.cal.intercept_[0])}
                             for h, m in mods.items()},
           "hors_echantillon_2014_2022": mesurer_periode(T, pd.Timestamp("2014-01-01"), COUPE_FINALE),
           "lecture_2023": mesurer_periode(T, COUPE_REGLAGE, COUPE_MESURE),
           "lecture_2024_25": mesurer_periode(T, COUPE_MESURE, FIN),
           "poids": {h: dict(zip(ENTREES, map(float, m.log.coef_[0]))) for h, m in mods.items()}}
    (SORTIE / "mesure_v2.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    dire("essai 3 écrit")
    return mods


def modeles_v2() -> dict:
    with open(SORTIE / "modeles_v2.pkl", "rb") as f:
        return pickle.load(f)


# ============================================================================================== 4. l'avis du matin
PHRASES = {
    "t20": ("tendance 20 j haussière", "tendance 20 j baissière"),
    "t60": ("tendance de fond 60 j haussière", "tendance de fond 60 j baissière"),
    "t120": ("tendance de fond 120 j haussière", "tendance de fond 120 j baissière"),
    "mv1": ("forte hausse hier", "forte baisse hier"),
    "mv5": ("hausse sur 5 jours", "baisse sur 5 jours"),
    "struct_d1": ("sommets et creux journaliers montants", "sommets et creux journaliers descendants"),
    "place_d1": ("prix haut entre son dernier creux et son dernier sommet journaliers",
                 "prix bas entre son dernier creux et son dernier sommet journaliers"),
    "zdem_d1": ("prix loin au-dessus de sa zone de demande journalière", "prix proche de sa zone de demande journalière"),
    "zsup_d1": ("prix loin sous sa zone d'offre journalière", "prix proche de sa zone d'offre journalière"),
    "zdem_h4": ("prix loin au-dessus de sa zone de demande 4 h", "prix proche de sa zone de demande 4 h"),
    "zsup_h4": ("prix loin sous sa zone d'offre 4 h", "prix proche de sa zone d'offre 4 h"),
    "dans_dem": ("prix dans une zone de demande", "prix hors des zones de demande"),
    "dans_sup": ("prix dans une zone d'offre", "prix hors des zones d'offre"),
    "compression": ("marché agité (3 j / 14 j)", "marché comprimé (3 j / 14 j)"),
    "agit_pct": ("agitation forte", "agitation faible"),
    "vix_niveau": ("peur des marchés (VIX) élevée", "peur des marchés (VIX) basse"),
    "vix_saut": ("peur des marchés (VIX) en hausse", "peur des marchés (VIX) en baisse"),
    "ovx_saut": ("peur sur le pétrole en hausse", "peur sur le pétrole en baisse"),
    "gvz_saut": ("peur sur l'or en hausse", "peur sur l'or en baisse"),
    "courbe_peur": ("peur immédiate au-dessus de la peur à 3 mois", "peur immédiate sous la peur à 3 mois"),
    "tension": ("tension géopolitique en cours", "pas de tension géopolitique"),
    "c1": ("foule crypto vendeuse à l'excès (contre la foule : achat)", "foule crypto acheteuse à l'excès (contre la foule : vente)"),
    "lundi": ("on est lundi", "on n'est pas lundi"), "vendredi": ("on est vendredi", "on n'est pas vendredi"),
    "annonce": ("annonce majeure aujourd'hui", "pas d'annonce majeure"),
}


def _phrase(k: str, z: float) -> str | None:
    base_k = k.split("*")[0]
    if base_k.startswith("fam_"):
        return None                                           # « c'est un indice » n'est pas une raison du jour
    pos, neg = PHRASES.get(base_k, (base_k, base_k))
    ph = pos if z > 0 else neg
    if "*" in k:
        ph += f" ({NOM_FAM[k.split('*')[1]]})"
    return ph


def raisons(m: Avis, ligne: pd.DataFrame, sens: int, k: int = 3) -> list[str]:
    """Les k informations qui poussent le plus dans le sens de l'avis ce jour-là (régression logistique : poids x valeur,
    une même information n'est citée qu'une fois)."""
    ct = m.contributions(ligne)[0]
    Z = ((m._X(ligne) - m.mu) / m.sd)[0]
    o = np.argsort(-ct * sens)
    out, vus = [], set()
    for i in o:
        if ct[i] * sens <= 0:
            break
        k_ = ENTREES[i]
        ph = _phrase(k_, Z[i] if "*" not in k_ else ligne[k_.split("*")[0]].iloc[0] - m.mu[ENTREES.index(k_.split("*")[0])])
        cle = ph[: -len(f" ({NOM_FAM[k_.split('*')[1]]})")] if (ph and "*" in k_) else ph
        if not ph or cle in vus:                       # « peur en baisse » et « peur en baisse (indices) » : une fois
            continue
        vus.add(cle)
        out.append(ph)
        if len(out) == k:
            break
    return out


def _fmt(v: float, p: float) -> str:
    if not np.isfinite(v):
        return "?"
    d = 0 if p >= 1000 else (2 if p >= 10 else (4 if p >= 0.1 else 6))
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def _destination(p: float, sens: int, zone: float, sommet_creux: float) -> str:
    """Destination = la zone journalière opposée la plus proche, sinon le dernier sommet / creux journalier ; seulement
    si elle est AU-DELÀ du prix dans le sens du trade (sinon : pas de destination, le stop suiveur décide)."""
    for v, quoi in ((zone, "sa zone journalière"), (sommet_creux, "dernier sommet" if sens > 0 else "dernier creux")):
        if np.isfinite(v) and sens * (v - p) > 0:
            return f"destination {_fmt(v, p)} ({quoi})"
    return "pas de destination visible"


def plan_trade(r: pd.Series, sens: int) -> str:
    """Le plan d'exécution lisible : entrée sur ses zones dans le sens de l'avis, stop derrière, destination, laisser
    courir (stop suiveur 1 h). Ce n'est pas un ordre : l'exécution est jugée à part."""
    p, A = float(r["prix"]), float(r["A"])
    marge = 0.1 * A
    if sens < 0:
        for u, nu in (("H4", "4 h"), ("D1", "journalière")):
            bas, haut = r[f"off_bas_{u}"], r[f"off_haut_{u}"]
            if np.isfinite(bas) and bas >= p - 0.3 * A and (bas - p) <= 3 * A:
                dest = _destination(p, -1, r["dem_haut_D1"], r["creux_d1"])
                return (f"vente si réaction sur sa zone d'offre {nu} {_fmt(bas, p)}-{_fmt(haut, p)}, stop {_fmt(haut + marge, p)}, "
                        f"{dest}, je laisse courir (stop suiveur 1 h)")
        stop = r["sommet_h4"] + marge if np.isfinite(r["sommet_h4"]) and r["sommet_h4"] > p else p + A
        return f"pas de zone d'offre proche : vente au marché ~{_fmt(p, p)}, stop {_fmt(stop, p)} (dernier sommet 4 h), je laisse courir"
    for u, nu in (("H4", "4 h"), ("D1", "journalière")):
        haut, bas = r[f"dem_haut_{u}"], r[f"dem_bas_{u}"]
        if np.isfinite(haut) and haut <= p + 0.3 * A and (p - haut) <= 3 * A:
            dest = _destination(p, 1, r["off_bas_D1"], r["sommet_d1"])
            return (f"achat si réaction sur sa zone de demande {nu} {_fmt(bas, p)}-{_fmt(haut, p)}, stop {_fmt(bas - marge, p)}, "
                    f"{dest}, je laisse courir (stop suiveur 1 h)")
    stop = r["creux_h4"] - marge if np.isfinite(r["creux_h4"]) and r["creux_h4"] < p else p - A
    return f"pas de zone de demande proche : achat au marché ~{_fmt(p, p)}, stop {_fmt(stop, p)} (dernier creux 4 h), je laisse courir"


_TABLES: dict = {}


def avis_du_jour(date: str | None = None, marches=None, mods: dict | None = None, horizon: int = 5,
                 tous: bool = False, brut: bool = False) -> list[dict]:
    """L'avis tel qu'il aurait été publié à 08h00 serveur le jour `date` (par défaut : le dernier jour disponible),
    calculé à partir des seules données connues à cet instant. Rend une liste triée par conviction."""
    mods = mods or modeles()
    marches = list(marches or D.univers())
    out = []
    for nom in marches:
        try:
            if nom not in _TABLES:
                _TABLES[nom] = table_marche(nom)
            T = _TABLES[nom]
        except Exception:
            continue
        if not len(T):
            continue
        if date is None:
            i = len(T) - 1
        else:
            j = pd.Timestamp(date).value - pd.Timestamp(date).value % JOUR_NS + HEURE_AVIS * HEURE_NS
            w = np.flatnonzero(T["inst"].to_numpy(np.int64) == j)
            if not len(w):
                continue
            i = int(w[0])
        L = T.iloc[[i]]
        if L["age_j"].iloc[0] < 130:
            continue
        av = {"marche": nom, "nom": nom_lisible(nom), "instant": str(pd.Timestamp(int(L["inst"].iloc[0]))),
              "prix": float(L["prix"].iloc[0])}
        for h, m in mods.items():
            p = float((m.brut(L) if brut else m.proba(L))[0])
            conv = max(p, 1 - p) * 100
            av[h] = {"p_hausse": p * 100, "conviction": conv,
                     "sens": (1 if p > 0.5 else -1) if conv >= CONVICTION_MIN * 100 else 0}
        s = av[horizon]["sens"]
        if s == 0 and not tous:
            continue
        sd = s if s != 0 else (1 if av[horizon]["p_hausse"] > 50 else -1)
        av["raisons"] = raisons(mods[horizon], L, sd)
        av["plan"] = plan_trade(L.iloc[0], sd) if s != 0 else "rien à faire"
        out.append(av)
    out.sort(key=lambda a: -a[horizon]["conviction"])
    return out


def texte_telephone(av: dict, horizon: int = 5) -> str:
    s = av[horizon]["sens"]
    mot = {1: "HAUSSE", -1: "BAISSE", 0: "RIEN"}[s]
    autres = ", ".join(f"{h} j : {({1: 'hausse', -1: 'baisse', 0: 'rien'})[av[h]['sens']]} {av[h]['conviction']:.0f} %"
                       for h in sorted(k for k in av if isinstance(k, int)) if h != horizon)
    return (f"{av['nom']} : {mot}, conviction {av[horizon]['conviction']:.0f} % ({horizon} jours). "
            f"Pourquoi : {' ; '.join(av['raisons'])}. Plan : {av['plan']}. (Autres horizons : {autres}.)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("etape", choices=["construire", "apprendre", "mesurer", "glissant", "matin"])
    ap.add_argument("--v2", action="store_true", help="modèles de l'essai 3 (années glissantes)")
    ap.add_argument("--date", default=None)
    ap.add_argument("--marches", default=None)
    ap.add_argument("--horizon", type=int, default=5)
    ap.add_argument("--max", type=int, default=12)
    ap.add_argument("--brut", action="store_true", help="avis AVANT calibration (pour information, non validé)")
    a = ap.parse_args(argv)
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    from collapsar.ecole.precision import avis as moi          # classes rangées sous leur vrai nom de module (pickle)
    if a.etape == "construire":
        moi.construire()
    elif a.etape == "apprendre":
        moi.apprendre()
    elif a.etape == "mesurer":
        moi.mesurer()
    elif a.etape == "glissant":
        moi.apprendre_glissant()
    else:
        mods = moi.modeles_v2() if a.v2 else None
        print(moi.texte_matin(a.date, a.marches.split(",") if a.marches else None, a.horizon, a.max, mods=mods,
                              brut=a.brut))


def texte_matin(date=None, marches=None, horizon: int = 5, nmax: int = 12, mods=None, brut: bool = False) -> str:
    """Le message du matin (téléphone) : les avis ayant une conviction >= 55 %, sinon « rien à faire »."""
    avs = avis_du_jour(date, marches, mods=mods, horizon=horizon, tous=True, brut=brut)
    if not avs:
        return f"AVIS DU MATIN ({date or 'dernier jour'}) : aucune donnée."
    tete = f"AVIS DU MATIN du {avs[0]['instant'][:10]} (08h00 heure du serveur), horizon {horizon} jours"
    actifs = [av for av in avs if av[horizon]["sens"] != 0]
    L = [tete]
    if not actifs:
        m = max(avs, key=lambda av: av[horizon]["conviction"])
        L.append(f"Rien à faire : aucune conviction >= {CONVICTION_MIN * 100:.0f} % sur {len(avs)} marchés "
                 f"(la plus forte : {m['nom']} {m[horizon]['conviction']:.1f} %).")
    for av in actifs[:nmax]:
        L.append("- " + texte_telephone(av, horizon))
    return "\n".join(L)


if __name__ == "__main__":
    main()
