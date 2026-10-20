"""PISTE « foule_devises » : la foule des petits traders, prise à contre-pied, sur les marchés BON MARCHÉ chez FTMO
(devises, or, argent, indices, pétrole) — 16/10/2026.

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (liste fermée de 6 variantes, rien d'ajouté après coup).

Pourquoi cette donnée (voir research_notes/Foule devises/notes.md)
- Aucune source GRATUITE et LÉGALE ne donne >= 3 ans d'historique du positionnement des clients particuliers des
  courtiers (Dukascopy : historique abandonné et robots interdits ; IG, Myfxbook : valeur actuelle seulement, avec un
  compte ; FXCM : 1 mois d'exemple, le reste payant ; OANDA : compte nécessaire ; FXSSI : payant).
- La seule source longue, gratuite et libre : la CFTC, rapport « Engagements des traders » (anciens rapports, contrats
  à terme seuls), colonnes « positions non déclarables » = les traders trop petits pour être déclarés (petits
  spéculateurs, souvent des particuliers). C'est le COUSIN HEBDOMADAIRE de l'information C1 de crypto_flux, pas la
  même chose : à lire comme tel.

Donnée (data/foule_devises/cot_petits.csv, fabriquée par `preparer` depuis data/foule_devises/cftc_brut/deacot<AN>.zip,
https://www.cftc.gov/files/dea/history/)
- part_acheteurs = positions non déclarables acheteuses / (acheteuses + vendeuses), photo du MARDI (date T).
- Sens du marché FTMO : pour USDJPY, USDCHF, USDCAD (contrat à terme = la devise contre le dollar), part des petits
  acheteurs du marché FTMO = 1 - part acheteurs du contrat.

Heures (tout ce qui décide est connu AVANT l'entrée)
- Publication normale : vendredi 15h30 New York (= 22h30 serveur) ; lundi si jour férié. Règle PRUDENTE : la photo du
  mardi T n'est utilisée qu'à partir de T + 7 jours, 00h00 serveur (= lundi 17h00 New York, après une publication du
  lundi ; une photo datée d'un lundi, semaine à mardi férié, attend 1 jour de plus). Fermetures de l'État américain (publications rattrapées des semaines plus tard) : photos ignorées
  (T du 01/10/2013 au 05/11/2013, du 24/12/2018 au 01/03/2019, du 30/09/2025 au 23/12/2025).
- Décision chaque jour ouvré D (lundi -> vendredi, heure serveur) à 01h00 serveur, avec la dernière photo connue
  (plus vieille que 13 jours -> rien). Entrée au prix d'ouverture de la 1re bougie 15 min >= D 01h00 (le même jour,
  sinon rien) ; sortie au prix d'ouverture de la 1re bougie >= entrée + tenue (le week-end est porté s'il tombe dedans).
- « Extrême » = centile calculé sur les photos PASSÉES seulement (dates dans [T - fenêtre, T[ ; au moins
  max(3, fenêtre / 21 jours) photos).

Variantes (liste fermée ; sens +1 achat / -1 vente ; une position à la fois par marché et par variante : un signal
pendant une position ouverte est ignoré)
- V1 C1_IDENTIQUE : part >= centile 95 des 90 j passés -> vendre ; <= centile 5 -> acheter ; tenue 24 h.
- V2 FENETRE_30 : idem, fenêtre 30 j ; tenue 24 h.
- V3 FENETRE_180 : idem, fenêtre 180 j ; tenue 24 h.
- V4 SORTIE_3J : fenêtre 90 j ; tenue 72 h.
- V5 SORTIE_5J : fenêtre 90 j ; tenue 120 h.
- V6 SEUIL_ABSOLU : part > 70 % -> vendre ; < 30 % -> acheter ; tenue 24 h.
Source : sentiment de la foule comme indicateur contraire (Kumar & Lee 2006, J. Finance ; petits spéculateurs du COT,
p. ex. Wang 2001 « Investor sentiment, market timing, and futures returns », Applied Financial Economics) ; règle C1
de crypto_flux recopiée telle quelle.

Coûts (obligatoires)
- Aller-retour : collapsar.mains.frais_ftmo.frais(sym, prix d'entrée) (relevé FTMO, glissement x MARGE_PRUDENCE (1,25 jusqu'au 16/10, 1 depuis l'audit) compris).
- Nuit : collapsar.mains.nuit.taux_nuit(fiche(sym), heure d'entrée) -> taux annuel du sens joué / 360 par nuit
  CALENDAIRE serveur franchie (un week-end = 3 nuits ; sur une semaine, même total que « mercredi x 3 »).

Compte
- Taille : exposition = min(5, 0,5 % / (agitation journalière x racine(tenue en jours))), agitation = écart type des
  rendements journaliers (clôtures serveur) des 20 jours ouvrés PASSÉS. Gain compté le jour serveur de la sortie ;
  jours ouvrés (lundi -> vendredi) ; mois = 21 jours ouvrés.
- Challenges : bande_bruit.challenge (départ tous les 10 jours ouvrés) ; contre 20 jumeaux (sens tiré à pile ou
  face, mêmes moments, même taille).

Juge (BRIEF + demande du coordinateur)
- Marchés (14, ceux qui ont un contrat CFTC et sont bon marché chez FTMO), par ordre alphabétique : AUDUSD, EURUSD,
  GBPUSD, JPNIDXJPY, LIGHTCMDUSD, NZDUSD, USA30IDXUSD, USA500IDXUSD, USATECHIDXUSD, USDCAD, USDCHF, USDJPY, XAGUSD,
  XAUUSD. Groupe A = 1 sur 2 en commençant par le 1er (AUDUSD, GBPUSD, LIGHTCMDUSD, USA30IDXUSD, USATECHIDXUSD,
  USDCHF, XAGUSD) ; groupe B = les autres.
- DÉVELOPPEMENT = groupe A, entrées 2010-01-01 -> 2023-12-31. CONTRÔLE = groupe A, 2024-01-01 -> 2026-10-01, UNE fois
  (verrou vie/pistes/foule_devises/controle.json), variante retenue seulement. CONFIRMATION = groupe B, toutes
  années (et coupé <= 2023 / >= 2024), UNE fois (verrou confirmation.json), seulement si le contrôle est positif.
- Force contre le jumeau = moyenne((R - R_inverse)/2) / écart type x racine(n) ; « force jour » = même calcul sur les
  sommes par jour (les marchés en dollar bougent ensemble : mesure honnête). Seuil max(3, racine(2 ln 6)) = 3.
- RETENUE (mécanique, en développement) : gain %/mois après frais et nuits > 0 ET force >= 3 ET force jour >= 3 ;
  parmi elles, la plus forte force jour. Aucune -> contrôle et confirmation NE SONT PAS ouverts.
- CONTRÔLE positif si gain après frais > 0 et force > 0. CONFIRMATION : confirmée si gain > 0 et force > 0 ; prouvée
  si force >= 3.
- Recherche du défaut (variante retenue, ou la meilleure force jour si aucune, en développement seulement) : photo
  utilisée 1 jour plus tôt (lundi, T + 6 j) ; 1 semaine plus tard (T + 14 j) ; meilleure année retirée ; achats /
  ventes séparés ; marché par marché.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.foule_devises preparer|alignement|developpement|controle|confirmation
"""
from __future__ import annotations

import json
import math
import sys
import zipfile
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mains import frais_ftmo
from collapsar.mains.fiches import fiche
from collapsar.mains.nuit import taux_nuit
from collapsar.regarder import bande_bruit as bb

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "foule_devises"
DONNEES = dm.RACINE / "data" / "foule_devises"
BRUT = DONNEES / "cftc_brut"
COT = DONNEES / "cot_petits.csv"

# marché FTMO -> (code CFTC, signe : +1 contrat dans le sens du marché FTMO, -1 inversé)
MARCHES = {"AUDUSD": ("232741", 1), "EURUSD": ("099741", 1), "GBPUSD": ("096742", 1), "JPNIDXJPY": ("240743", 1),
           "LIGHTCMDUSD": ("067651", 1), "NZDUSD": ("112741", 1), "USA30IDXUSD": ("124603", 1),
           "USA500IDXUSD": ("13874A", 1), "USATECHIDXUSD": ("209742", 1), "USDCAD": ("090741", -1),
           "USDCHF": ("092741", -1), "USDJPY": ("097741", -1), "XAGUSD": ("084691", 1), "XAUUSD": ("088691", 1)}
ORDRE = sorted(MARCHES)
GROUPE_A, GROUPE_B = ORDRE[0::2], ORDRE[1::2]

VARIANTES = ("V1", "V2", "V3", "V4", "V5", "V6")
FENETRE = {"V1": 90, "V2": 30, "V3": 180, "V4": 90, "V5": 90, "V6": None}
TENUE = {"V1": 24, "V2": 24, "V3": 24, "V4": 72, "V5": 120, "V6": 24}
NOMS = {"V1": "C1 à l'identique (90 j, 24 h)", "V2": "fenêtre 30 j (24 h)", "V3": "fenêtre 180 j (24 h)",
        "V4": "90 j, sortie 3 j", "V5": "90 j, sortie 5 j", "V6": "seuil absolu 70 / 30 % (24 h)"}
SEUIL = max(3.0, math.sqrt(2 * math.log(len(VARIANTES))))
RISQUE = 0.005
EXPO_MAX = 5.0
DELAI = 7                                           # jours après la photo du mardi (règle prudente)
FERMETURES = [("2013-10-01", "2013-11-05"), ("2018-12-24", "2019-03-01"), ("2025-09-30", "2025-12-23")]
DEBUT_DEV, FIN_DEV = pd.Timestamp("2010-01-01"), pd.Timestamp("2024-01-01")
FIN_TOUT = pd.Timestamp("2026-10-01")


# ---------------------------------------------------------------- données CFTC
def _col(cols, debut):
    for c in cols:
        if c.strip().lower().startswith(debut.lower()):
            return c
    raise KeyError(debut)


def preparer() -> pd.DataFrame:
    """Fichiers annuels CFTC -> data/foule_devises/cot_petits.csv (une ligne par marché et par mardi)."""
    codes = {c for c, _ in MARCHES.values()}
    parts = []
    for z in sorted(BRUT.glob("deacot*.zip")):
        with zipfile.ZipFile(z) as f:
            d = pd.read_csv(f.open(f.namelist()[0]), dtype=str, low_memory=False)
        c_code = _col(d.columns, "CFTC Contract Market Code")
        c_date = _col(d.columns, "As of Date in Form YYYY-MM-DD")
        c_nom = _col(d.columns, "Market and Exchange Names")
        c_l, c_s = _col(d.columns, "Nonreportable Positions-Long (All)"), _col(d.columns,
                                                                                "Nonreportable Positions-Short (All)")
        c_oi = _col(d.columns, "Open Interest (All)")
        d[c_code] = d[c_code].str.strip()
        d = d[d[c_code].isin(codes)]
        parts.append(pd.DataFrame({"code": d[c_code], "nom": d[c_nom].str.strip(), "date": pd.to_datetime(d[c_date]),
                                   "petits_achat": pd.to_numeric(d[c_l]), "petits_vente": pd.to_numeric(d[c_s]),
                                   "positions_totales": pd.to_numeric(d[c_oi]), "fichier": z.name}))
    c = pd.concat(parts, ignore_index=True).drop_duplicates(["code", "date"], keep="last")
    c["part_acheteurs"] = c["petits_achat"] / (c["petits_achat"] + c["petits_vente"])
    c = c.sort_values(["code", "date"]).reset_index(drop=True)
    DONNEES.mkdir(parents=True, exist_ok=True)
    c.to_csv(COT, index=False)
    return c


def cot() -> pd.DataFrame:
    if not COT.exists():
        return preparer()
    c = pd.read_csv(COT, dtype={"code": str}, parse_dates=["date"])
    return c


def part_marche(c: pd.DataFrame, sym: str) -> pd.Series:
    """Part des petits ACHETEURS du marché FTMO, indexée par la date de la photo (mardi), fermetures retirées."""
    code, signe = MARCHES[sym]
    x = c[c["code"] == code].set_index("date")["part_acheteurs"].sort_index()
    x = x if signe > 0 else 1.0 - x
    for a, b in FERMETURES:
        x = x[(x.index < pd.Timestamp(a)) | (x.index > pd.Timestamp(b))]
    return x[np.isfinite(x)]


def sens_photos(p: pd.Series, v: str) -> pd.Series:
    """Sens voulu à chaque photo (0 = rien), seuils sur les photos passées seulement."""
    w = FENETRE[v]
    val, dates = p.to_numpy(), p.index
    s = np.zeros(len(p), np.int8)
    if w is None:
        s[val > 0.70], s[val < 0.30] = -1, 1
        return pd.Series(s, index=dates)
    mini = max(3, math.ceil(w / 21))
    for k in range(len(p)):
        m = (dates < dates[k]) & (dates >= dates[k] - pd.Timedelta(days=w))
        passe = val[m]
        if len(passe) < mini:
            continue
        hi, lo = np.quantile(passe, .95), np.quantile(passe, .05)
        if val[k] >= hi:
            s[k] = -1
        elif val[k] <= lo:
            s[k] = 1
    return pd.Series(s, index=dates)


def sens_jours(sp: pd.Series, jours: pd.DatetimeIndex, delai: int = DELAI) -> np.ndarray:
    """Pour chaque jour de décision D (00h00 serveur) : sens de la dernière photo CONNUE (T + délai <= D, âge < 7 j
    après sa connaissance)."""
    # une photo datée d'un LUNDI (semaine avec mardi férié, 9 cas) n'est connue qu'au même moment que celle du mardi
    retard = np.maximum(0, 1 - sp.index.dayofweek.to_numpy())
    connu = (pd.DatetimeIndex(sp.index) + pd.to_timedelta(delai + retard, unit="D")).astype("datetime64[ns]")
    conn = pd.DataFrame({"connu": connu, "s": sp.to_numpy()}).sort_values("connu")
    g = pd.DataFrame({"D": pd.DatetimeIndex(jours).astype("datetime64[ns]")})
    m = pd.merge_asof(g, conn, left_on="D", right_on="connu", direction="backward", tolerance=pd.Timedelta(days=6))
    return m["s"].fillna(0).to_numpy(np.int8)


# ---------------------------------------------------------------- trades
def trades_marche(sym: str, c: pd.DataFrame, delai: int = DELAI, variantes=VARIANTES) -> pd.DataFrame:
    df = dm.charger(sym, pd.Timestamp("2100-01-01"))
    tm = pd.DatetimeIndex(df["time"]).astype("datetime64[ns]")
    t_ns = tm.asi8
    op = df["open"].to_numpy(float)
    jour = tm.normalize()
    clo = pd.Series(df["close"].to_numpy(float), index=jour).groupby(level=0).last()
    clo = clo[clo.index.dayofweek < 5]
    agit = np.log(clo).diff().rolling(20, min_periods=15).std().shift(1)        # jours < D seulement
    del df
    p = part_marche(c, sym)
    jours = pd.bdate_range(max(DEBUT_DEV - pd.Timedelta(days=10), tm[0].normalize()), FIN_TOUT)
    f = fiche(sym)
    out = []
    for v in variantes:
        sj = sens_jours(sens_photos(p, v), jours, delai)
        h = pd.Timedelta(hours=TENUE[v])
        libre = 0
        for i in np.flatnonzero(sj):
            D = jours[i]
            cible = (D + pd.Timedelta(hours=1)).value
            e = int(np.searchsorted(t_ns, cible))
            if e >= len(t_ns) or t_ns[e] < libre or t_ns[e] >= (D + pd.Timedelta(days=1)).value:
                continue
            ci = t_ns[e] + h.value
            x = int(np.searchsorted(t_ns, ci))
            if x >= len(t_ns) or t_ns[x] - ci > pd.Timedelta(days=4).value:
                continue
            a = agit.get(D, np.nan)
            if not (np.isfinite(a) and a > 0 and np.isfinite(op[e]) and np.isfinite(op[x])):
                continue
            out.append((v, sym, tm[e], tm[x], int(sj[i]), op[x] / op[e] - 1.0, op[e],
                        min(EXPO_MAX, RISQUE / (a * math.sqrt(TENUE[v] / 24)))))
            libre = t_ns[x]
    t = pd.DataFrame(out, columns=["variante", "marche", "entree", "sortie", "sens", "r", "prix", "expo"])
    if not len(t):
        return t
    t["jour_sortie"] = t["sortie"].dt.normalize()
    t["nuits"] = (t["sortie"].dt.normalize() - t["entree"].dt.normalize()).dt.days
    t["frais"] = np.asarray(frais_ftmo.frais(sym, t["prix"].to_numpy()), float)
    na, nv = taux_nuit(f, pd.DatetimeIndex(t["entree"]))
    nuit_joue = np.where(t["sens"] > 0, na, nv) * t["nuits"] / 360.0
    nuit_inverse = np.where(t["sens"] > 0, nv, na) * t["nuits"] / 360.0
    t["nuit"] = nuit_joue
    t["R"] = t["expo"] * (t["sens"] * t["r"] - t["frais"] - nuit_joue)
    t["R_inverse"] = t["expo"] * (-t["sens"] * t["r"] - t["frais"] - nuit_inverse)
    t["R_sans_frais"] = t["expo"] * t["sens"] * t["r"]
    return t


def tous_trades(marches, delai: int = DELAI) -> pd.DataFrame:
    c = cot()
    parts = []
    for sym in marches:
        cache = VIE / "cache" / f"{sym}_d{delai}.pkl"
        if cache.exists():
            t = pd.read_pickle(cache)
        else:
            t = trades_marche(sym, c, delai)
            cache.parent.mkdir(parents=True, exist_ok=True)
            t.to_pickle(cache)
        print(f"  {sym} (délai {delai} j) : " + ", ".join(f"{v} {int((t['variante'] == v).sum())}" for v in VARIANTES),
              flush=True)
        parts.append(t)
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------- juge
def compte(t: pd.DataFrame, de, a, signes=None, col="R") -> pd.Series:
    R = t[col].to_numpy() if signes is None else np.where(signes > 0, t["R"], t["R_inverse"])
    g = pd.Series(R, index=pd.DatetimeIndex(t["jour_sortie"])).groupby(level=0).sum()
    jours = pd.bdate_range(pd.Timestamp(de), pd.Timestamp(a) - pd.Timedelta(days=1))
    g = g.reindex(pd.DatetimeIndex(g.index).union(jours), fill_value=0.0)
    # une sortie un samedi/dimanche (n'arrive pas, marchés fermés) serait gardée
    return g[(g.index >= jours[0]) & (g.index <= jours[-1])]


def note(t: pd.DataFrame, de, a, challenges=True) -> dict:
    t = t[(t["entree"] >= de) & (t["entree"] < a)]
    n = len(t)
    if n < 20:
        return {"trades": n}
    de = max(pd.Timestamp(de), pd.Timestamp(t["entree"].min()).normalize())
    a = min(pd.Timestamp(a), pd.Timestamp(t["jour_sortie"].max()) + pd.Timedelta(days=1))
    d = (t["R"] - t["R_inverse"]).to_numpy() / 2
    g = compte(t, de, a)
    g0 = compte(t, de, a, col="R_sans_frais")
    dj = (pd.Series(d, index=pd.DatetimeIndex(t["jour_sortie"])).groupby(level=0).sum()
          .reindex(g.index, fill_value=0.0))
    mois = len(g) / 21.0
    courbe = g.cumsum()
    x = {"trades": n, "marches": int(t["marche"].nunique()), "achats_pct": float((t["sens"] > 0).mean() * 100),
         "gagnants_pct": float((t["R"] > 0).mean() * 100),
         "brut_pct_prix": float((t["sens"] * t["r"]).mean() * 100),
         "frais_pct_prix": float(t["frais"].mean() * 100), "nuit_pct_prix": float(t["nuit"].mean() * 100),
         "force": float(d.mean() / d.std(ddof=1) * math.sqrt(n)),
         "force_jour": float(dj.mean() / dj.std(ddof=1) * math.sqrt(len(dj))) if dj.std() > 0 else 0.0,
         "pct_mois": float(g.sum() / mois * 100), "pct_mois_sans_frais": float(g0.sum() / mois * 100),
         "baisse_max_pct": float((courbe - courbe.cummax()).min() * 100), "pire_jour_pct": float(g.min() * 100),
         "expo_moy": float(t["expo"].mean()), "nuits_moy": float(t["nuits"].mean()),
         "debut": str(de.date()), "fin": str(a.date())}
    if challenges:
        ch = bb.challenge(g)
        rng = np.random.default_rng(7)
        jum = [bb.challenge(compte(t, de, a, rng.choice([-1, 1], n))) for _ in range(20)]
        x.update({"chall_reussis_pct": ch["reussis_pct"], "chall_morts_pct": ch["morts_pct"],
                  "jum_reussis_pct": float(np.mean([j["reussis_pct"] for j in jum])),
                  "jum_morts_pct": float(np.mean([j["morts_pct"] for j in jum]))})
    return x


def ligne(nom, x):
    if "force" not in x:
        return f"{nom} | {x}"
    s = (f"{nom} | {x['trades']:5d} tr | brut {x['brut_pct_prix']:+.3f} % (frais {x['frais_pct_prix']:.3f}, nuit "
         f"{x['nuit_pct_prix']:+.3f}) | force {x['force']:+.2f} (jour {x['force_jour']:+.2f}) | {x['pct_mois']:+.2f} "
         f"%/mois (sans frais {x['pct_mois_sans_frais']:+.2f}) | baisse {x['baisse_max_pct']:.1f} % | pire j "
         f"{x['pire_jour_pct']:.2f} %")
    if "chall_reussis_pct" in x:
        s += (f" | chall {x['chall_reussis_pct']:.0f}/{x['chall_morts_pct']:.0f} (jum {x['jum_reussis_pct']:.0f}/"
              f"{x['jum_morts_pct']:.0f})")
    return s


def _ecrire(f, obj):
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


# ---------------------------------------------------------------- étapes
def alignement():
    """Contrôle des heures et de la couverture (aucun résultat de trading)."""
    c = cot()
    res = {}
    for sym in ORDRE:
        code, signe = MARCHES[sym]
        x = c[c["code"] == code]
        jours_sem = x["date"].dt.dayofweek.value_counts().to_dict()
        ecarts = x["date"].diff().dt.days.value_counts().sort_index().to_dict()
        p = part_marche(c, sym)
        res[sym] = {"code": code, "noms": sorted(x["nom"].unique().tolist()), "photos": int(len(x)),
                    "premiere": str(x["date"].min().date()), "derniere": str(x["date"].max().date()),
                    "jours_semaine (0=lundi)": {int(k): int(v) for k, v in jours_sem.items()},
                    "ecarts_jours": {int(k): int(v) for k, v in ecarts.items() if np.isfinite(k)},
                    "part_moy": float(p.mean()), "part_min": float(p.min()), "part_max": float(p.max()),
                    "pct_au_dessus_70": float((p > .7).mean() * 100), "pct_sous_30": float((p < .3).mean() * 100)}
        print(sym, res[sym], flush=True)
    # exemple concret d'alignement
    p = part_marche(c, "EURUSD")
    sp = sens_photos(p, "V1")
    jours = pd.bdate_range("2024-03-01", "2024-03-31")
    sj = sens_jours(sp, jours)
    ex = [{"jour_decision": str(d.date()), "photo_utilisee": str(p.index[p.index + pd.Timedelta(days=DELAI) <= d].max()
                                                                       .date()), "sens": int(s)}
          for d, s in zip(jours, sj)]
    res["exemple_EURUSD_03_2024"] = ex
    for e in ex[:10]:
        print(e)
    _ecrire(VIE / "alignement.json", res)


def developpement():
    t = tous_trades(GROUPE_A)
    res, retenues = {}, []
    for v in VARIANTES:
        x = note(t[t["variante"] == v], DEBUT_DEV, FIN_DEV)
        res[v] = x
        print(ligne(f"{v} {NOMS[v]}", x), flush=True)
        if "force" in x and x["pct_mois"] > 0 and x["force"] >= SEUIL and x["force_jour"] >= SEUIL:
            retenues.append(v)
    choix = max(retenues, key=lambda v: res[v]["force_jour"]) if retenues else None
    meilleure = max((v for v in VARIANTES if "force_jour" in res[v]), key=lambda v: res[v]["force_jour"])
    print(f"Retenue : {choix} (meilleure force jour : {meilleure})", flush=True)
    diag = defauts(choix or meilleure, GROUPE_A, DEBUT_DEV, FIN_DEV)
    _ecrire(VIE / "developpement.json", {"date": datetime.now().isoformat(timespec="seconds"), "marches": GROUPE_A,
                                         "seuil": SEUIL, "variantes": res, "retenue": choix,
                                         "meilleure_force_jour": meilleure, "diagnostic": diag})


def defauts(v: str, marches, de, a) -> dict:
    out = {"variante": v}
    for delai in (6, 14):
        t = tous_trades(marches, delai)
        out[f"photo_delai_{delai}j"] = note(t[t["variante"] == v], de, a, challenges=False)
        print(ligne(f"  {v} délai {delai} j", out[f"photo_delai_{delai}j"]), flush=True)
    t = tous_trades(marches)
    t = t[(t["variante"] == v) & (t["entree"] >= de) & (t["entree"] < a)]
    ans = t.groupby(t["entree"].dt.year)["R"].sum()
    out["gain_par_annee_pct"] = {int(k): float(x * 100) for k, x in ans.items()}
    best = int(ans.idxmax())
    out["sans_meilleure_annee"] = {"annee": best, **note(t[t["entree"].dt.year != best], de, a, challenges=False)}
    out["achats"] = note(t[t["sens"] > 0], de, a, challenges=False)
    out["ventes"] = note(t[t["sens"] < 0], de, a, challenges=False)
    out["par_marche"] = {}
    for m, tm in t.groupby("marche"):
        d = (tm["R"] - tm["R_inverse"]) / 2
        out["par_marche"][m] = {"trades": int(len(tm)), "gain_total_pct": float(tm["R"].sum() * 100),
                                "force": float(d.mean() / d.std(ddof=1) * math.sqrt(len(d))) if len(d) > 2 else None}
    for k in ("sans_meilleure_annee", "achats", "ventes"):
        print(ligne(f"  {v} {k}", out[k]), flush=True)
    print("  par marché :", {m: round(x["gain_total_pct"], 2) for m, x in out["par_marche"].items()}, flush=True)
    return out


def controle():
    f = VIE / "controle.json"
    if f.exists():
        print("VERROU : contrôle déjà ouvert ->", f.read_text(encoding="utf-8")[:3000])
        return
    dev = json.loads((VIE / "developpement.json").read_text(encoding="utf-8"))
    v = dev["retenue"]
    if v is None:
        print("Aucune variante retenue en développement : le contrôle n'est PAS ouvert.")
        return
    t = tous_trades(GROUPE_A)
    x = note(t[t["variante"] == v], FIN_DEV, FIN_TOUT)
    print(ligne(f"CONTRÔLE {v}", x), flush=True)
    _ecrire(f, {"date": datetime.now().isoformat(timespec="seconds"), "variante": v, "resultat": x,
                "positif": bool("force" in x and x["pct_mois"] > 0 and x["force"] > 0)})


def confirmation():
    f = VIE / "confirmation.json"
    if f.exists():
        print("VERROU : confirmation déjà ouverte ->", f.read_text(encoding="utf-8")[:3000])
        return
    fc = VIE / "controle.json"
    if not fc.exists() or not json.loads(fc.read_text(encoding="utf-8"))["positif"]:
        print("Contrôle absent ou négatif : la confirmation n'est PAS ouverte.")
        return
    v = json.loads(fc.read_text(encoding="utf-8"))["variante"]
    t = tous_trades(GROUPE_B)
    t = t[t["variante"] == v]
    res = {"tout": note(t, DEBUT_DEV, FIN_TOUT), "jusqu_2023": note(t, DEBUT_DEV, FIN_DEV),
           "depuis_2024": note(t, FIN_DEV, FIN_TOUT)}
    for k, x in res.items():
        print(ligne(f"CONFIRMATION {v} {k}", x), flush=True)
    x = res["tout"]
    res["verdict"] = ("prouvée" if x.get("force", 0) >= SEUIL and x.get("pct_mois", 0) > 0 else
                      "confirmée" if x.get("force", 0) > 0 and x.get("pct_mois", 0) > 0 else "non confirmée")
    _ecrire(f, {"date": datetime.now().isoformat(timespec="seconds"), "variante": v, "marches": GROUPE_B, **res})


if __name__ == "__main__":
    etape = sys.argv[1] if len(sys.argv) > 1 else "alignement"
    {"preparer": preparer, "alignement": alignement, "developpement": developpement, "controle": controle,
     "confirmation": confirmation}[etape]()
