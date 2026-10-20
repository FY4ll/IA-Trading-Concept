"""PISTE « SCALPING DE L'OR » (20/10/2026) : test honnête des 3 méthodes courtes de docs/SCALPING_QUI_MARCHE.md (§ 5).

Plan figé AVANT tout résultat : collapsar/vie/scalping_or/plan_fige.md (règles exactes, frais, juge, périodes, verdict).
A1 cassure plus haut / plus bas de la veille (08h Londres -> 12h New York, stop 0,35 x A14, stop à l'entrée à +1 R puis
suiveur 0,5 x A14, fermé 16h45 New York) ; A2 même chose sur les niveaux de la séance asiatique ; A3 = ventes de A1
(sens imposé par l'heure) ; B boîte asiatique du testeur (03h-08h serveur, 2,5 R, stop à l'entrée à 1,5 R, fermé 21h
serveur) ; C fausse cassure de la veille (bougies de 15 min, objectif = milieu de la veille si >= 3 x les frais).
Juge : jumeau (même minute, même prix, mêmes distances, sens opposé), seuil max(3, racine(2 ln 1305)) = 3,79.
Données : or à la minute, heure du serveur = New York + 7 h ; rien après le 30/09/2025.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.regarder.pistes.scalping_or choix|verification|controle|rapport
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[3]
VIE = RACINE / "collapsar" / "vie" / "scalping_or"
SRC = RACINE / "data" / "kaggle_gold" / "XAU_1m_data.csv"
CACHE = VIE / "or_m1_ny_2014_2025.npz"
LECTURE_DEBUT = "2014.10.01"
FIN_DONNEES = pd.Timestamp("2025-10-01")          # heure de New York, exclue : rien après 09/2025
SERVEUR_MOINS_NY = 7 * 60                          # minutes (toute la période est après 06/2011)
PERIODES = {"choix": ("2015-01-01", "2021-01-01"), "verification": ("2021-01-01", "2023-01-01"),
            "controle": ("2023-01-01", "2025-10-01"), "tout": ("2015-01-01", "2025-10-01")}
N_ESSAIS = 1300 + 5
SEUIL = max(3.0, math.sqrt(2 * math.log(N_ESSAIS)))
JOUR_MIN = int(0.6 * 1380)
# écart Tradeco médian par heure de New York / écart médian (bougies de 5 min 07/2025 -> 10/2026), bas plafonné à 1
FACTEUR_HEURE = np.ones(24)
FACTEUR_HEURE[[16, 17, 18]] = 2.0
FACTEUR_HEURE[[19, 20, 21, 22, 23, 0, 14, 15]] = 1.08
HEURE_RELEVE_FTMO = 20                             # relevé FTMO à 03h34 serveur = 20h34 New York
COMMISSION = 0.000014                              # métaux FTMO, aller-retour, part du prix (prudence)
GLISSEMENT, GLISSEMENT_ANNONCE = 0.10, 0.30        # $/once
ECART_FIXE = 0.40
ECART_FTMO_DEFAUT, PRIX_RELEVE_DEFAUT = 0.463, 4171.95
PRIX_2025 = 3200.0                                 # échelle de prix « 2025 » pour le gain brut par once
K_MIROIR = 2000.0 ** 2
METHODES = ("A1", "A2", "A3", "B", "C")
VERSIONS = ("modele", "fixe", "pourcent", "doux", "miroir")


# ---------------------------------------------------------------------------------------------- données
def charger_minutes() -> dict:
    """Minutes de l'or, heure de NEW YORK en minutes depuis 1970 (sans fuseau), jusqu'au 30/09/2025 inclus."""
    if CACHE.exists():
        z = np.load(CACHE)
        return {k: z[k] for k in z.files}
    parts = []
    for c in pd.read_csv(SRC, sep=";", chunksize=2_000_000):
        c = c[(c["Date"] >= LECTURE_DEBUT) & (c["Date"] < "2025.10.02")]
        if len(c):
            parts.append(c)
    df = pd.concat(parts)
    serveur = pd.to_datetime(df["Date"], format="%Y.%m.%d %H:%M").values.astype("datetime64[m]").astype(np.int64)
    t = serveur - SERVEUR_MOINS_NY
    o = np.argsort(t, kind="stable")
    t = t[o]
    garde = np.r_[True, t[1:] != t[:-1]] & (t < minute(FIN_DONNEES))
    d = {"t": t[garde]}
    for k, col in (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close")):
        d[k] = df[col].to_numpy(float)[o][garde]
    VIE.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE, **d)
    return d


def minute(ts) -> int:
    return int(pd.Timestamp(ts).value // 60_000_000_000)


def annonces_ny() -> np.ndarray:
    """Minutes (heure de New York) des annonces majeures du dollar : importance forte du calendrier MT5 + déclaration,
    projections, procès-verbal et conférence de presse de la banque centrale américaine."""
    from collapsar.donnees import calendrier as cal
    d = cal._lire_mt5(cal.MT5_HISTOIRE)
    fomc = d["annonce"].str.contains("FOMC", na=False) & ~d["annonce"].str.contains("Discours", na=False)
    u = d[(d["devise"] == "USD") & ((d["importance"] == 3) | fomc)]
    t = u["temps"].values.astype("datetime64[m]").astype(np.int64) - SERVEUR_MOINS_NY
    return np.unique(t)


def ecart_ftmo() -> tuple[float, float]:
    """Écart FTMO relevé de l'or en $/once (constant en dollars, `mains/frais_ftmo.py`) et le prix au relevé."""
    try:
        from collapsar.mains import frais_ftmo
        p = frais_ftmo._prix_au_releve("XAUUSD")
        return float((frais_ftmo.frais("XAUUSD", p) - COMMISSION) * p), float(p)
    except Exception:
        return ECART_FTMO_DEFAUT, PRIX_RELEVE_DEFAUT


def proximite_annonces(t: np.ndarray, news: np.ndarray):
    """(facteur d'écart dû aux annonces, annonce à 15 min près, annonce à 2 min près) pour chaque minute."""
    grand = 10 ** 9
    k = np.searchsorted(news, t, side="right")
    dprev = np.where(k > 0, t - news[np.clip(k - 1, 0, None)], grand)
    dnext = np.where(k < len(news), news[np.clip(k, None, len(news) - 1)] - t, grand)
    f = np.ones(len(t))
    f[(dprev > 5) & (dprev <= 15)] = 2.0
    f[(dnext <= 2) | (dprev <= 5)] = 5.0
    return f, (dprev <= 15) | (dnext <= 15), (dprev <= 2) | (dnext <= 2)


class Monde:
    """Les prix (réels ou retournés), les frais minute par minute d'une version, et les journées de l'or."""

    def __init__(self, m: dict, version: str, jusqua, news: np.ndarray, ecart_base=None):
        t = m["t"]
        garde = t < minute(jusqua)
        self.t = t[garde]
        o, h, l, c = (m[k][garde] for k in "ohlc")
        self.version = version
        self.dur = version != "doux"
        miroir = version == "miroir"
        if miroir:
            self.o, self.h, self.l, self.c = K_MIROIR / o, K_MIROIR / l, K_MIROIR / h, K_MIROIR / c
            esc = self.c / c
        else:
            self.o, self.h, self.l, self.c = o, h, l, c
            esc = np.ones(len(c))
        f_ann, self.p15, self.p2 = proximite_annonces(self.t, news)
        heure = (self.t % 1440) // 60
        s0, p_rel = ecart_base or ecart_ftmo()
        base = s0 / FACTEUR_HEURE[HEURE_RELEVE_FTMO]
        fac = FACTEUR_HEURE[heure] * f_ann
        if version == "fixe":
            e = np.full(len(c), ECART_FIXE)
            self.fac = np.ones(len(c))
        elif version == "pourcent":
            e = base * fac * c / p_rel
            self.fac = fac
        else:
            e = base * fac
            self.fac = fac
        self.e = e * esc
        self.g = np.where(self.p15, GLISSEMENT_ANNONCE, GLISSEMENT) * esc
        self._jours()

    def _jours(self):
        t = self.t
        lab = (t + 360) // 1440                                    # journée de l'or : 18h New York -> 17h
        debut = np.flatnonzero(np.r_[True, lab[1:] != lab[:-1]])
        fin = np.r_[debut[1:], len(t)]
        jour = lab[debut]
        sem = (jour + 3) % 7                                       # 0 = lundi
        garde = ((fin - debut) >= JOUR_MIN) & (sem < 5)
        self.jour, self.deb, self.fin, self.sem = jour[garde], debut[garde], fin[garde], sem[garde]
        self.H = np.array([self.h[a:b].max() for a, b in zip(self.deb, self.fin)])
        self.L = np.array([self.l[a:b].min() for a, b in zip(self.deb, self.fin)])
        rng = pd.Series(self.H - self.L)
        self.a14 = rng.rolling(14).mean().shift(1).to_numpy()
        dates = pd.to_datetime(self.jour, unit="D")
        lon = (dates + pd.Timedelta(hours=8)).tz_localize("Europe/London").tz_convert("America/New_York")
        self.lon8 = (lon.tz_localize(None).values.astype("datetime64[m]").astype(np.int64))

    def tranche(self, k: int):
        a, b = self.deb[k], min(self.fin[k] + 30, len(self.t))     # + 30 min : sortie à la réouverture (jour court)
        return Tranche(self, a, b)


class Tranche:
    def __init__(self, mo: Monde, a: int, b: int):
        self.ta = mo.t[a:b]
        self.T = self.ta.tolist()
        self.O, self.H, self.L, self.C = (x[a:b].tolist() for x in (mo.o, mo.h, mo.l, mo.c))
        self.E, self.G, self.F = mo.e[a:b].tolist(), mo.g[a:b].tolist(), mo.fac[a:b].tolist()
        self.P15, self.P2 = mo.p15[a:b].tolist(), mo.p2[a:b].tolist()

    def ss(self, x: int) -> int:
        return int(np.searchsorted(self.ta, x))


# ---------------------------------------------------------------------------------------------- une position
def suivre(s: Tranche, i0: int, sens: int, entree: float, ref: float, Rd: float, tp, be, trail, t_fin: int,
           dur: bool, sans_objectif_i0: bool):
    """Suit une position (prix du milieu) depuis la minute i0 incluse. Rend (prix exécuté de sortie, i, motif, pire prix
    du milieu atteint, prix idéal de sortie). Stop vérifié avant l'objectif dans chaque minute (prudence) ; stop à
    l'entrée et suiveur mis à jour en fin de minute, actifs à la minute suivante."""
    T, O, Hh, Ll, E, G = s.T, s.O, s.H, s.L, s.E, s.G
    stop = ref - sens * Rd
    meilleur = pire = entree
    arme = False
    for i in range(i0, len(T)):
        if T[i] >= t_fin:
            return O[i] - sens * E[i] / 2, i, "heure", pire, O[i]
        a, f = (Ll[i], Hh[i]) if sens > 0 else (Hh[i], Ll[i])
        if (a - stop) * sens <= 0:
            if dur:
                x = a
            else:
                x = O[i] if (O[i] - stop) * sens < 0 else stop
            x -= sens * G[i]
            if (x - pire) * sens < 0:
                pire = x
            return x - sens * E[i] / 2, i, "stop", pire, stop
        if (a - pire) * sens < 0:
            pire = a
        if i == i0 and sans_objectif_i0:
            continue
        if tp is not None and (f - tp) * sens >= E[i] / 2:
            return tp, i, "objectif", pire, tp
        if (f - meilleur) * sens > 0:
            meilleur = f
        if be is not None and not arme and (meilleur - entree) * sens >= be * Rd:
            arme = True
            if (entree - stop) * sens > 0:
                stop = entree
        if arme and trail:
            cand = meilleur - sens * trail
            if (cand - stop) * sens > 0:
                stop = cand
    i = len(T) - 1
    return s.C[i] - sens * E[i] / 2, i, "fin", pire, s.C[i]


def une(s: Tranche, i0, sens, ref, entree, Rd, tp_dist, be, trail, t_fin, dur, sans_obj) -> dict:
    tp = None if tp_dist is None else ref + sens * tp_dist
    sortie, i, motif, pire, ideal = suivre(s, i0, sens, entree, ref, Rd, tp, be, trail, t_fin, dur, sans_obj)
    e_in = s.E[i0]
    entree_exec = entree + sens * e_in / 2
    comm = COMMISSION * ref
    net = (sortie - entree_exec) * sens - comm
    flottant = (pire - sens * e_in / 2 - entree_exec) * sens - comm
    return {"R": net / Rd, "net": net, "brut": (ideal - ref) * sens, "pire_R": min(flottant / Rd, net / Rd),
            "motif": motif, "t_sortie": s.T[i]}


def couple(s: Tranche, j, sens, ref, entree, Rd, tp_dist, be, trail, t_fin, dur, sans_obj, jour, methode) -> dict:
    """Le trade et son jumeau inverse (même minute, même référence, même glissement contre lui, mêmes distances)."""
    g = (entree - ref) * sens
    x = une(s, j, sens, ref, entree, Rd, tp_dist, be, trail, t_fin, dur, sans_obj)
    y = une(s, j, -sens, ref, ref - sens * g, Rd, tp_dist, be, trail, t_fin, dur, sans_obj)
    return {"jour": int(jour), "methode": methode, "sens": sens, "t_entree": s.T[j], "ref": ref, "Rd": Rd,
            **x, "R_inv": y["R"], "frais": x["brut"] - x["net"]}


# ---------------------------------------------------------------------------------------------- les méthodes
def jour_A(mo: Monde, k: int, asie: bool) -> list:
    A14 = mo.a14[k]
    if not np.isfinite(A14) or k < 1:
        return []
    D = int(mo.jour[k])
    s = mo.tranche(k)
    j0, j1 = s.ss(int(mo.lon8[k])), s.ss(D * 1440 + 720)
    t_fin = D * 1440 + 1005
    if asie:
        if j0 < 30:
            return []
        Hn, Bn = max(s.H[:j0]), min(s.L[:j0])
    else:
        Hn, Bn = mo.H[k - 1], mo.L[k - 1]
    tamp, Rd, trail = 0.05 * A14, 0.35 * A14, 0.5 * A14
    sortie = []
    for sens, niv in ((1, Hn + tamp), (-1, Bn - tamp)):
        if not asie and j0 > 0:
            pre = max(s.H[:j0]) if sens > 0 else min(s.L[:j0])
            if (pre - niv) * sens >= 0:
                continue
        j = next((j for j in range(j0, j1) if ((s.H[j] if sens > 0 else s.L[j]) - niv) * sens >= 0), None)
        if j is None or s.P15[j] or s.F[j] > 2:
            continue
        if mo.sem[k] == 4 and s.T[j] % 1440 >= 14 * 60:
            continue
        if mo.dur:
            em = (s.H[j] if sens > 0 else s.L[j]) + sens * s.G[j]
        else:
            em = (max(niv, s.O[j]) if sens > 0 else min(niv, s.O[j])) + sens * s.G[j]
        sortie.append(couple(s, j, sens, niv, em, Rd, None, 1.0, trail, t_fin, mo.dur, True, D,
                             "A2" if asie else "A1"))
    return sortie


def jour_B(mo: Monde, k: int) -> list:
    D = int(mo.jour[k])
    s = mo.tranche(k)
    i0, i1 = s.ss(D * 1440 - 240), s.ss(D * 1440 + 60)        # 03h00 -> 08h00 serveur
    t_fin = D * 1440 + 840                                       # 21h00 serveur = 14h New York
    if i1 - i0 < 150:
        return []
    BH, BL = max(s.H[i0:i1]), min(s.L[i0:i1])
    mid = (BH + BL) / 2
    taille = (BH - BL) / mid
    if taille < 0.003 or taille > 0.016:
        return []
    tamp = 0.0002 * mid
    nb, ns = BH + tamp, BL - tamp
    sens = None
    for j in range(i1, s.ss(t_fin)):
        hb, hs = s.H[j] >= nb, s.L[j] <= ns
        if not (hb or hs):
            continue
        sens = (1 if abs(s.O[j] - nb) <= abs(s.O[j] - ns) else -1) if (hb and hs) else (1 if hb else -1)
        break
    if sens is None or s.P2[j]:
        return []
    niv = nb if sens > 0 else ns
    Rd = min((niv - BL) if sens > 0 else (BH - niv), 0.006 * niv)
    if mo.dur:
        em = (s.H[j] if sens > 0 else s.L[j]) + sens * s.G[j]
    else:
        em = (max(niv, s.O[j]) if sens > 0 else min(niv, s.O[j])) + sens * s.G[j]
    return [couple(s, j, sens, niv, em, Rd, 2.5 * Rd, 1.5, None, t_fin, mo.dur, True, D, "B")]


def jour_C(mo: Monde, k: int) -> list:
    A14 = mo.a14[k]
    if not np.isfinite(A14) or k < 1:
        return []
    D = int(mo.jour[k])
    s = mo.tranche(k)
    w0, w1, t_fin = int(mo.lon8[k]), D * 1440 + 720, D * 1440 + 1005
    Hn, Bn = mo.H[k - 1], mo.L[k - 1]
    tamp, milieu = 0.05 * A14, (Hn + Bn) / 2
    sortie = []
    for u, niv in ((1, Hn), (-1, Bn)):                 # u = +1 : fausse cassure du haut -> VENTE (sens = -u)
        commence, ext = False, None
        for b0 in range(w0, w1, 15):
            a, b = s.ss(b0), s.ss(b0 + 15)
            if a >= b:
                continue
            bh, bl, bc = max(s.H[a:b]), min(s.L[a:b]), s.C[b - 1]
            x = bh if u > 0 else bl
            if not commence:
                if (x - (niv + u * tamp)) * u < 0:
                    continue
                commence, ext = True, x
            elif (x - ext) * u > 0:
                ext = x
            if (bc - niv) * u >= 0:
                continue
            # signal : la bougie clôture de nouveau à l'intérieur -> marché à l'ouverture de la bougie suivante
            j = s.ss(b0 + 15)
            if j >= len(s.T) or s.T[j] >= w1 or s.T[j] >= b0 + 30:
                break
            ref = s.O[j]
            stop = ext + u * tamp
            Rd = (stop - ref) * u
            dist = (ref - milieu) * u
            frais_rt = s.E[j] + COMMISSION * ref + s.G[j]
            if Rd <= 0 or dist < 3 * frais_rt or s.P15[j] or s.F[j] > 2:
                break
            sortie.append(couple(s, j, -u, ref, ref, Rd, dist, 1.0, None, t_fin, mo.dur, False, D, "C"))
            break
    return sortie


def simuler(mo: Monde) -> pd.DataFrame:
    lignes = []
    for k in range(len(mo.jour)):
        lignes += jour_A(mo, k, False) + jour_A(mo, k, True) + jour_B(mo, k) + jour_C(mo, k)
    t = pd.DataFrame(lignes)
    if len(t):
        a3 = t[(t["methode"] == "A1") & (t["sens"] < 0)].assign(methode="A3")
        t = pd.concat([t, a3], ignore_index=True)
        t["date"] = pd.to_datetime(t["jour"], unit="D")
    return t


# ---------------------------------------------------------------------------------------------- le juge
def force(t: pd.DataFrame) -> float:
    if len(t) < 5:
        return float("nan")
    d = (t["R"] - t["R_inv"]) / 2
    sd = d.std(ddof=1)
    return float(d.mean() / sd * math.sqrt(len(d))) if sd > 0 else float("nan")


def compte(t: pd.DataFrame, debut, fin, risque: float) -> dict:
    """Compte FTMO 100 000 $ : risque en % du capital de départ par trade ; perte du jour = pire flottant (prudent)."""
    jours = pd.bdate_range(debut, pd.Timestamp(fin) - pd.Timedelta(days=1))
    g = t.groupby("date")
    s = pd.DataFrame({"r": g["R"].sum() * risque, "p": g["pire_R"].sum() * risque}).reindex(jours, fill_value=0.0)
    r, p = s["r"].to_numpy(), s["p"].to_numpy()
    bal = np.cumsum(r)
    avant = np.r_[0.0, bal[:-1]]
    pic = np.maximum.accumulate(np.r_[0.0, bal])[:-1]
    baisse = float(np.max(pic - (avant + np.minimum(p, 0)))) if len(r) else 0.0
    mois = max(1, len(pd.period_range(debut, pd.Timestamp(fin) - pd.Timedelta(days=1), freq="M")))
    res = {"gain_par_mois_pct": float(bal[-1] / mois) if len(r) else 0.0, "pire_jour_pct": float(p.min()) if len(p) else 0,
           "baisse_max_pct": baisse}
    reussis, morts, en_cours, duree = 0, 0, 0, []
    for m0 in pd.date_range(debut, pd.Timestamp(fin) - pd.Timedelta(days=1), freq="MS"):
        i = int(np.searchsorted(jours.values, np.datetime64(m0)))
        b, fini = 0.0, False
        for x in range(i, len(jours)):
            if p[x] <= -5 or b + p[x] <= -10:
                morts += 1
                fini = True
                break
            b += r[x]
            if b >= 10:
                reussis += 1
                duree.append(x - i + 1)
                fini = True
                break
        en_cours += not fini
    res.update({"challenges": reussis + morts + en_cours, "reussis": reussis, "morts": morts, "non_finis": en_cours,
                "jours_pour_10pct_mediane": float(np.median(duree)) if duree else None})
    return res


def bilan(t: pd.DataFrame, debut, fin, argent: bool = True) -> dict:
    t = t[(t["date"] >= pd.Timestamp(debut)) & (t["date"] < pd.Timestamp(fin))]
    mois = max(1, len(pd.period_range(debut, pd.Timestamp(fin) - pd.Timedelta(days=1), freq="M")))
    if len(t) == 0:
        return {"trades": 0}
    r = t["R"]
    gag, per = t[r > 0], t[r <= 0]
    brut_sum = float(t["brut"].sum())
    res = {"trades": int(len(t)), "trades_par_mois": len(t) / mois, "R_moyen": float(r.mean()),
           "net_par_once": float(t["net"].mean()), "brut_par_once": float(t["brut"].mean()),
           "brut_par_once_prix_2025": float((t["brut"] / t["ref"] * PRIX_2025).mean()),
           "frais_par_once": float(t["frais"].mean()),
           "frais_part_du_brut_pct": (float(t["frais"].sum()) / brut_sum * 100) if brut_sum > 0 else None,
           "gagnants_pct": float((r > 0).mean() * 100),
           "gain_moyen_gagnant_R": float(gag["R"].mean()) if len(gag) else None,
           "perte_moyenne_perdant_R": float(per["R"].mean()) if len(per) else None,
           "trades_3R": int((r >= 3).sum()), "trades_5R": int((r >= 5).sum()),
           "jumeau_R": float(((t["R"] + t["R_inv"]) / 2).mean()), "force": force(t),
           "motifs": t["motif"].value_counts().to_dict()}
    for nom, sens in (("achats", 1), ("ventes", -1)):
        x = t[t["sens"] == sens]
        res[nom] = {"trades": int(len(x)), "R_moyen": float(x["R"].mean()) if len(x) else None, "force": force(x)}
    an = t.groupby(t["date"].dt.year)["R"].agg(["size", "mean", "sum"])
    res["annees"] = {int(y): {"trades": int(v["size"]), "R_moyen": float(v["mean"]), "R_total": float(v["sum"])}
                     for y, v in an.iterrows()}
    res["annees_positives"] = f"{int((an['sum'] > 0).sum())}/{len(an)}"
    if argent:
        res["ftmo_0_5"] = compte(t, debut, fin, 0.5)
        res["ftmo_1"] = compte(t, debut, fin, 1.0)
    return res


def etiquette(modele: dict, fixe: dict) -> str:
    f, rm, rf = modele.get("force", float("nan")), modele.get("R_moyen", -1), fixe.get("R_moyen", -1)
    f = -99 if f is None or not np.isfinite(f) else f
    if rm > 0 and rf > 0 and f >= SEUIL:
        return "🟢"
    if (rm > 0 and f >= 2) or f >= SEUIL:
        return "🟡"
    return "⚪"


# ---------------------------------------------------------------------------------------------- phases
def lancer(phase: str):
    VIE.mkdir(parents=True, exist_ok=True)
    verrou = VIE / "controle.json"
    if phase == "controle" and verrou.exists():
        print("Le contrôle 2023 -> 09/2025 a DÉJÀ été ouvert (une seule fois) :", verrou)
        return json.loads(verrou.read_text(encoding="utf-8"))
    if phase == "verification" and not (VIE / "choix.json").exists():
        raise SystemExit("Faire d'abord la phase choix.")
    if phase == "controle" and not (VIE / "verification.json").exists():
        raise SystemExit("Faire d'abord la phase verification.")
    jusqua = PERIODES[phase][1]
    m = charger_minutes()
    news = annonces_ny()
    base = ecart_ftmo()
    print(f"écart FTMO relevé {base[0]:.3f} $/once (prix au relevé {base[1]:.0f}) ; seuil de preuve {SEUIL:.2f}", flush=True)
    trades = {}
    for v in VERSIONS:
        mo = Monde(m, v, jusqua, news, base)
        trades[v] = simuler(mo)
        print(f"  version {v} : {len(trades[v])} trades simulés", flush=True)
    periodes = [phase] + (["tout"] if phase == "controle" else [])
    res = {"_quand": datetime.now().isoformat(timespec="seconds"), "seuil": SEUIL, "ecart_ftmo": base[0]}
    for per in periodes:
        de, a = PERIODES[per]
        bloc = {}
        for meth in METHODES:
            x = {}
            for v in VERSIONS:
                t = trades[v][trades[v]["methode"] == meth]
                x[v] = bilan(t, de, a, argent=v in ("modele", "fixe"))
            x["etiquette"] = etiquette(x["modele"], x["fixe"])
            bloc[meth] = x
            mm = x["modele"]
            print(f"[{per}] {meth} {x['etiquette']} : {mm.get('trades')} trades, R net {mm.get('R_moyen', 0):+.3f} "
                  f"(0,40 $ : {x['fixe'].get('R_moyen', 0):+.3f} ; doux {x['doux'].get('R_moyen', 0):+.3f} ; "
                  f"retourné {x['miroir'].get('R_moyen', 0):+.3f}), force {mm.get('force', float('nan')):+.2f}, "
                  f"brut {mm.get('brut_par_once', 0):.2f} $/once", flush=True)
        res[per] = bloc
    if phase == "choix":
        fa = {k: res["choix"][k]["modele"].get("force", -99) for k in ("A1", "A2")}
        res["A_choisie"] = max(fa, key=lambda k: -99 if not np.isfinite(fa[k]) else fa[k])
        print("  -> version de A choisie :", res["A_choisie"])
    else:
        res["A_choisie"] = json.loads((VIE / "choix.json").read_text(encoding="utf-8"))["A_choisie"]
    for v in ("modele",):
        tt = trades[v]
        tt.to_pickle(VIE / f"trades_{phase}_{v}.pkl")
    sortie = verrou if phase == "controle" else VIE / f"{phase}.json"
    sortie.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("(enregistré :", sortie, ")")
    return res


NOMS = {"A1": "A1 cassure veille", "A2": "A2 cassure Asie", "A3": "A3 ventes seules", "B": "B boîte asiatique",
        "C": "C fausse cassure"}
NOMS_PER = {"choix": "2015-2020 (choix)", "verification": "2021-2022 (vérif.)", "controle": "2023-09/2025 (contrôle)",
            "tout": "2015-09/2025 (tout)"}


def _f(x, n=2, signe=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    return f"{x:+.{n}f}".replace(".", ",") if signe else f"{x:.{n}f}".replace(".", ",")


def rapport():
    blocs = {}
    for ph, fichier in (("choix", "choix.json"), ("verification", "verification.json"), ("controle", "controle.json")):
        blocs[ph] = json.loads((VIE / fichier).read_text(encoding="utf-8"))
    res = {"choix": blocs["choix"]["choix"], "verification": blocs["verification"]["verification"],
           "controle": blocs["controle"]["controle"], "tout": blocs["controle"]["tout"]}
    L = ["# Scalping de l'or : les 3 méthodes de la recherche, testées honnêtement",
         "",
         f"Test du 20/10/2026, plan figé avant tout résultat (`plan_fige.md`). Or à la minute 01/2015 -> 12/09/2025, "
         f"frais FTMO (écart relevé {_f(blocs['choix']['ecart_ftmo'], 2, False)} $/once x facteur de l'heure, commission "
         f"métaux, glissement), seuil de preuve {_f(SEUIL, 2, False)} (1 305 cases jugées). Version de A choisie sur "
         f"2015-2020 : **{blocs['choix']['A_choisie']}** (plus grande force contre le jumeau).",
         "", "## Verdict par période (frais modèle ; 🟢 prouvé / 🟡 prometteur / ⚪ bruit)", "",
         "| Méthode | 2015-2020 | 2021-2022 | 2023-09/2025 | tout |", "|---|---|---|---|---|"]
    for m in METHODES:
        cel = []
        for per in ("choix", "verification", "controle", "tout"):
            x = res[per][m]
            cel.append(f"{x['etiquette']} {_f(x['modele'].get('R_moyen'))} R, force {_f(x['modele'].get('force'), 1)}")
        L.append(f"| {NOMS[m]} | " + " | ".join(cel) + " |")
    for per in ("choix", "verification", "controle", "tout"):
        L += ["", f"## {NOMS_PER[per]}", "",
              "| | " + " | ".join(METHODES) + " |", "|---|" + "---|" * len(METHODES)]
        r = res[per]
        lignes = [
            ("trades (par mois)", lambda x: f"{x['modele'].get('trades')} ({_f(x['modele'].get('trades_par_mois'), 1, False)})"),
            ("gain net / trade (R)", lambda x: _f(x["modele"].get("R_moyen"))),
            ("idem écart fixe 0,40 $", lambda x: _f(x["fixe"].get("R_moyen"))),
            ("idem glissement doux", lambda x: _f(x["doux"].get("R_moyen"))),
            ("idem écart en % (info)", lambda x: _f(x["pourcent"].get("R_moyen"))),
            ("or retourné (R)", lambda x: _f(x["miroir"].get("R_moyen"))),
            ("gain net $/once", lambda x: _f(x["modele"].get("net_par_once"))),
            ("gain brut $/once", lambda x: _f(x["modele"].get("brut_par_once"))),
            ("brut à l'échelle 3 200 $", lambda x: _f(x["modele"].get("brut_par_once_prix_2025"))),
            ("frais $/once", lambda x: _f(x["modele"].get("frais_par_once"), 2, False)),
            ("frais / gain brut", lambda x: (f"{x['modele']['frais_part_du_brut_pct']:.0f} %" if x["modele"].get("frais_part_du_brut_pct") else "brut <= 0")),
            ("gagnants", lambda x: f"{x['modele'].get('gagnants_pct', 0):.0f} %"),
            ("gain moyen gagnant (R)", lambda x: _f(x["modele"].get("gain_moyen_gagnant_R"))),
            ("perte moyenne perdant (R)", lambda x: _f(x["modele"].get("perte_moyenne_perdant_R"))),
            ("trades >= 3R / >= 5R", lambda x: f"{x['modele'].get('trades_3R')} / {x['modele'].get('trades_5R')}"),
            ("force contre le jumeau", lambda x: _f(x["modele"].get("force"), 2)),
            ("achats : R (force)", lambda x: f"{_f(x['modele']['achats']['R_moyen'])} ({_f(x['modele']['achats']['force'], 1)})"),
            ("ventes : R (force)", lambda x: f"{_f(x['modele']['ventes']['R_moyen'])} ({_f(x['modele']['ventes']['force'], 1)})"),
            ("années gagnantes", lambda x: x["modele"].get("annees_positives")),
        ]
        for risque in ("0_5", "1"):
            k = f"ftmo_{risque}"
            nom = risque.replace("_", ",")
            lignes += [
                (f"FTMO {nom} % : gain/mois", lambda x, k=k: _f(x["modele"][k]["gain_par_mois_pct"]) + " %"),
                (f"FTMO {nom} % : pire jour", lambda x, k=k: _f(x["modele"][k]["pire_jour_pct"]) + " %"),
                (f"FTMO {nom} % : baisse max", lambda x, k=k: _f(x["modele"][k]["baisse_max_pct"], 1, False) + " %"),
                (f"FTMO {nom} % : réussis / morts / en cours", lambda x, k=k: f"{x['modele'][k]['reussis']} / {x['modele'][k]['morts']} / {x['modele'][k]['non_finis']}"),
                (f"FTMO {nom} % : jours pour +10 %", lambda x, k=k: str(x["modele"][k]["jours_pour_10pct_mediane"] or "-")),
            ]
        for nom, fn in lignes:
            L.append(f"| {nom} | " + " | ".join(str(fn(r[m])) for m in METHODES) + " |")
    L += ["", "## Année par année (gain net moyen par trade en R, frais modèle)", "",
          "| Année | " + " | ".join(METHODES) + " |", "|---|" + "---|" * len(METHODES)]
    an = res["tout"]
    annees = sorted({int(y) for m in METHODES for y in an[m]["modele"].get("annees", {})})
    for y in annees:
        L.append(f"| {y} | " + " | ".join(
            _f(an[m]["modele"]["annees"].get(str(y), {}).get("R_moyen")) for m in METHODES) + " |")
    (VIE / "rapport.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("(rapport :", VIE / "rapport.md", ")")


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "choix"
    rapport() if phase == "rapport" else lancer(phase)
