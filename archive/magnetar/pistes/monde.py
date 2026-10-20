"""LES YEUX DU MONDE : le contexte géopolitique et la peur donnent-ils le SENS ? (18/10/2026, chef de projet : sur son
compte FTMO validé, +10 % en une semaine à 1 % de risque par trade, le sens lui venait « de mes zones ET des tensions
géopolitiques qui couraient »).

Mesure SANS IA, liste FIGÉE (plan_fige.md écrit et daté AVANT toute mesure) :
A. ÉVÉNEMENTS : après une hausse brusque du risque géopolitique / de la peur (10 sources de collapsar/donnees/monde.py,
   2 déclencheurs figés), rendement des 1 / 5 / 20 jours suivants et probabilité que la tendance de fond 60 j CONTINUE,
   pour or, argent, pétrole, actions US, actions Europe, yen, franc suisse, cryptos ; contre le taux de base et contre
   des dates tirées au hasard.
B. COMBINAISON : sens (tendance de fond 60 j, et/ou contexte du monde) + endroit (ses zones : rebond ou cassure, stop
   juste derrière, élargi pour que les frais restent <= 0,03 R) + gestion (stop suiveur 1 h, sans plafond), moteur de la
   piste « mouvements » ; contre jumeau, fausses zones, plafond 2R ; compte FTMO 100 000 $.
Périodes : choix <= 2021 ; vérification 2022-2023 ; 2024 -> 09/2025 = LECTURE seulement (déjà regardée pour la piste
« mouvements »). Le vrai juge sera le suivi à blanc en direct. Rien après 09/2025.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.monde plan|choix|verification|lecture|rapport
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime
from functools import lru_cache

import numpy as np
import pandas as pd

from collapsar.donnees import monde as MW
from collapsar.ecole.precision import direction as DI
from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision import juge_trade as JT
from collapsar.ecole.precision.reglages import VIE, R
from collapsar.regarder.pistes import mouvements as M

SORTIE = VIE / "monde"
QUINZE_NS = 15 * 60 * 10 ** 9
HEURE_NS = 3600 * 10 ** 9
JOUR_NS = 86400 * 10 ** 9
SEMAINE_NS = 7 * JOUR_NS
MOIS_NS = 30.4375 * JOUR_NS

# ============================================================================================== LISTE FIGÉE
PERIODES = {"choix": (None, "2022-01-01"), "verification": ("2022-01-01", "2024-01-01"),
            "lecture": ("2024-01-01", "2025-10-01")}
NOM_P = {"choix": "<= 2021 (choix)", "verification": "2022-2023 (vérification)",
         "lecture": "01/2024 -> 09/2025 (lecture seulement : période déjà regardée pour « mouvements »)"}
# --- A. événements
SOURCES = ("gpr", "gpr_menaces", "gpr_actes", "epu", "vix", "vvix", "ovx", "gvz", "gdelt_noir", "gdelt_part")
DECLENCHEURS = {"haut30": "nouveau plus haut des 30 valeurs précédentes",
                "saut2": "saut de 2 écarts : (log x - moyenne des 60 valeurs précédentes) / leur écart >= 2"}
SIGNAUX = [f"{s}:{d}" for s in SOURCES for d in DECLENCHEURS]
ESPACEMENT_J = 10                  # un événement n'est gardé que si le même signal n'en a gardé aucun dans les 10 jours avant
HORIZONS = {1: 1, 5: 7, 20: 28}    # jours de Bourse -> jours calendaires (de l'entrée à la sortie)
GROUPES = {"or": [("XAUUSD", 1)], "argent": [("XAGUSD", 1)],
           "pétrole": [("LIGHTCMDUSD", 1), ("BRENTCMDUSD", 1)],
           "actions US": [("USA500IDXUSD", 1), ("USATECHIDXUSD", 1), ("USA30IDXUSD", 1)],
           "actions Europe": [("DEUIDXEUR", 1), ("EUSIDXEUR", 1), ("FRAIDXEUR", 1)],
           "yen": [("USDJPY", -1)], "franc suisse": [("USDCHF", -1)],
           "cryptos": [("BTCUSDT", 1), ("ETHUSDT", 1)]}
MESURES = ("rendement", "continuation")
TIRAGES_A = 2000
MIN_EVT = 15
FORCE_RETENUE = 2.0
RETENUES_MAX = 12
ENTREE_MAX_J = 4                   # l'entrée doit avoir lieu dans les 4 jours qui suivent l'instant connu
# --- B. combinaison
SENS = ("T60", "MONDE", "T60+MONDE", "T60+TENSION", "T60+CALME")
NOM_SENS = {"T60": "tendance de fond 60 j seule",
            "MONDE": "contexte du monde seul (cases de A retenues sur <= 2021)",
            "T60+MONDE": "tendance de fond 60 j ET contexte du monde du même sens",
            "T60+TENSION": "tendance de fond 60 j pendant une TENSION géopolitique (GPR moyen 7 j > son centile 80 "
                           "des 365 jours précédents)",
            "T60+CALME": "tendance de fond 60 j hors tension géopolitique"}
SCENARIOS = {"REB": "rebond sur ses zones", "CAS": "cassure de ses zones"}
VARIANTES = [(s, sc) for s in SENS for sc in SCENARIOS]
TENSION_MA, TENSION_FEN, TENSION_Q = 7, 365, 0.8
FRAIS_MAX_R = 0.03
RISQUE_MIN_A, RISQUE_MAX_A = 0.2, 6.0
MARGE_A = 0.1
SUIVEUR = "H1"
HORIZON = 2880
MIN_TRADES = 100
TIRAGES = 200
RISQUES = (1.0, 0.5)
# marchés de l'arbre auxquels s'applique le sens du monde d'un groupe (orientation : yen / franc = USDJPY / USDCHF en baisse)
MARCHES_GROUPE = {"or": [("XAUUSD", 1), ("XAUUSD@M1", 1)], "argent": [("XAGUSD", 1)],
                  "pétrole": [("LIGHTCMDUSD", 1), ("BRENTCMDUSD", 1)],
                  "actions US": [("USA500IDXUSD", 1), ("USATECHIDXUSD", 1), ("USA30IDXUSD", 1), ("US500@M1", 1),
                                 ("US100@M1", 1)],
                  "actions Europe": [("DEUIDXEUR", 1), ("EUSIDXEUR", 1), ("FRAIDXEUR", 1)],
                  "yen": [("USDJPY", -1)], "franc suisse": [("USDCHF", -1)], "cryptos": "TOUTES"}
# --- nombre de cases et seuil
N_DEJA = 255
N_A = len(SIGNAUX) * len(GROUPES) * len(HORIZONS) * len(MESURES)
N_B = len(VARIANTES) * 4
N_COMPTES = len(RISQUES)
N_TOTAL = N_DEJA + N_A + N_B + N_COMPTES
SEUIL = max(3.0, math.sqrt(2 * math.log(N_TOTAL)))


def vid(v) -> str:
    return "-".join(v)


def plan_texte() -> str:
    L = [f"# LES YEUX DU MONDE — plan FIGÉ avant toute mesure ({datetime.now():%d/%m/%Y %H:%M})", "",
         "Mesure SANS IA. Données : collapsar/donnees/monde.py (règle de publication : une valeur datée du jour J n'est "
         "utilisable qu'à J+1 08h00 heure du serveur = J+1 01h00 New York). Heure du serveur = New York + 7 h. Rien "
         "après 09/2025.", "",
         f"Périodes : choix {NOM_P['choix']} ; {NOM_P['verification']} ; {NOM_P['lecture']}. Le vrai juge sera le "
         "suivi à blanc en direct (données jamais vues).", "",
         "## A. Après une hausse brusque du risque géopolitique ou de la peur", "",
         f"- Sources ({len(SOURCES)}) : " + ", ".join(f"{s} = {MW.NOM_S[s]}" for s in SOURCES) + ". Débuts : GPR et "
         "EPU 1985, VIX 1990, VVIX 2006, OVX et GVZ 09/2009, GDELT 2017 (si son téléchargement, en cours, n'a pas "
         "abouti au moment du choix, ses 4 signaux restent vides et le rapport le dit ; N n'est pas réduit).",
         "- Déclencheurs (sur les valeurs publiées de la source, rien du futur) : "
         + " ; ".join(f"{k} = {v}" for k, v in DECLENCHEURS.items())
         + f". Un jour J déclenché n'est gardé que si le même signal n'a gardé aucun jour dans les {ESPACEMENT_J} jours "
           f"précédents (événements séparés). {len(SIGNAUX)} signaux.",
         "- Entrée : 1re bougie de 15 min qui s'ouvre à / après J+1 08h00 serveur (au plus "
         f"{ENTREE_MAX_J} jours après), à son ouverture. Sortie : dernière clôture au plus tard {', '.join(f'{c} j' for c in HORIZONS.values())} "
         f"calendaires après l'entrée (= {', '.join(str(h) for h in HORIZONS)} jours de Bourse). La sortie doit tomber "
         "dans la période.",
         "- Groupes (marché ; orientation) : " + " ; ".join(
             f"{g} = " + ", ".join(f"{m}{' (inversé : la devise refuge monte quand ' + m + ' baisse)' if o < 0 else ''}"
                                   for m, o in v) for g, v in GROUPES.items()) + ".",
         "- Mesure « rendement » : rendement logarithmique orienté / (écart des rendements quotidiens des 60 derniers "
         "jours de cotation terminés x racine(h)) ; moyenne des marchés du groupe ; aussi en % brut.",
         "- Mesure « continuation » : part des cas où le rendement brut a le signe de la tendance de fond 60 j à "
         "l'entrée (direction.tendance : jours terminés seulement) ; le reste = la tendance se retourne.",
         f"- Repères : taux de base = tous les jours J de la période (même calcul) ; dates au hasard = {TIRAGES_A} tirages "
         "de n jours J parmi ces jours. Force = (moyenne des événements - moyenne des tirages) / écart des tirages.",
         f"- {N_A} cases ({len(SIGNAUX)} signaux x {len(GROUPES)} groupes x {len(HORIZONS)} horizons x {len(MESURES)} "
         f"mesures). Choix sur <= 2021 : cases d'au moins {MIN_EVT} événements avec |force| >= {FORCE_RETENUE:g}, au "
         f"plus {RETENUES_MAX} (les plus fortes). Vérification 2022-2023 : CONFIRMÉE si même signe et |force| >= 2 ; "
         f"PROUVÉE si même signe et |force| >= seuil. Lecture 2024-2025 : signe affiché, sans décision.", "",
         "## B. Sens + ses zones + laisser courir", "",
         "- Endroit (moteur de regarder/pistes/mouvements.py, inchangé) : ses zones vivantes D1 / H4 / H1, 1er contact ; "
         "dans les 24 h, 1re clôture de 15 min hors de la zone du bon côté = REBOND (sens de la zone), au-delà du bord "
         "lointain = CASSURE (sens de la cassure). Entrée au marché à l'ouverture suivante.",
         f"- Stop : juste derrière la zone (+ {MARGE_A} agitation ; cassure : de l'autre côté de la zone), ÉLARGI si besoin "
         f"pour que les frais estimés (écart à l'entrée et à la sortie + glissement du stop) restent <= {FRAIS_MAX_R} R. "
         f"Risque entre {RISQUE_MIN_A} et {RISQUE_MAX_A} agitations, sinon pas de trade.",
         f"- Gestion : stop suiveur {SUIVEUR} (nouveau creux / sommet confirmé, - {MARGE_A} A), AUCUN objectif ; fermeture "
         "avant une pause > 2 h (règle du simulateur) ; un seul trade à la fois par variante et par marché.",
         "- Sens (le trade n'est pris que si le sens proposé à la décision = le sens du scénario) : "
         + " ; ".join(f"{k} = {v}" for k, v in NOM_SENS.items()) + ".",
         "- Contexte du monde (MONDE), figé par le choix de A : pour chaque case RETENUE sur <= 2021 et chaque événement "
         "de son signal, pendant h jours calendaires après l'instant connu : case « rendement » -> vote signe(effet) x "
         "orientation du marché ; case « continuation » -> vote signe(effet) x tendance 60 j du marché. Sens = signe de "
         "la somme des votes (0 = rien). Marchés : " + " ; ".join(
             f"{g} -> " + (", ".join(m for m, _ in v) if isinstance(v, list) else "les 19 cryptos")
             for g, v in MARCHES_GROUPE.items()) + ".",
         "", "| n° | variante | sens | scénario |", "|---|---|---|---|"]
    for i, v in enumerate(VARIANTES, 1):
        L.append(f"| {i} | {vid(v)} | {v[0]} | {SCENARIOS[v[1]]} |")
    L += ["", "Comparaisons de chaque variante : JUMEAU (sens à pile ou face : trade retourné autour du prix de décision ; "
          "avance = (R - R retourné) / 2) ; FAUSSES ZONES (même sens, même risque en A, instant tiré au hasard sur le même "
          "marché et la même période) ; PLAFOND 2R (même entrée, stop fixe, objectif 2R).",
          "Mesures : trades / mois, % gagnants, R moyen frais compris (force = R / incertitude, grappes = semaines), "
          "médiane, part des trades >= 5R / >= 10R et part des gains bruts venant d'eux, frais estimés en R.", "",
          "## Choix, jugement, compte", "",
          f"- Choix sur <= 2021 SEULEMENT : parmi les {len(VARIANTES)} variantes d'au moins {MIN_TRADES} trades, la plus "
          "grande force. Vérification 2022-2023 : toutes. Lecture 2024-2025 : la retenue seule.",
          f"- Compte FTMO 100 000 $ de la retenue à {' puis '.join(f'{r:g} %' for r in RISQUES)} de risque par trade "
          f"(un départ tous les 7 jours, +10 % / -5 % par jour / -10 % au total), contre {TIRAGES} jumeaux, 3 périodes.",
          f"- N = {N_DEJA} cases déjà jugées + {N_A} cases A + {N_B} cases B + {N_COMPTES} comptes = {N_TOTAL} -> seuil "
          f"de preuve max(3, racine(2 ln N)) = {SEUIL:.2f}.",
          "- PROMETTEUR si R moyen > 0 sur <= 2021 ET 2022-2023 avec force >= 2 en 2022-2023 (et > 0 en lecture) ; FORT "
          "si en plus force >= seuil en 2022-2023 ; sinon non. Aucune preuve définitive sans le suivi à blanc en direct."]
    return "\n".join(L) + "\n"


# ============================================================================================== outils
def _periode_ns(periode: str) -> tuple[int, int]:
    de, a = PERIODES[periode]
    return (pd.Timestamp(de).value if de else 0), pd.Timestamp(a).value


@lru_cache(maxsize=None)
def evenements_signal(signal: str) -> tuple[np.ndarray, np.ndarray]:
    """(jour J, instant connu) des événements gardés d'un signal (toutes dates < fin_donnees)."""
    src, dec = signal.split(":")
    tb = MW.tableau(src)
    if not len(tb):
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    trig = tb["haut30"].to_numpy() if dec == "haut30" else (tb["z60"].to_numpy() >= 2.0)
    j, c = tb["jour"].to_numpy()[trig], tb["connu"].to_numpy()[trig]
    garde = np.zeros(len(j), bool)
    dernier = -10 ** 19
    for i in range(len(j)):
        if j[i] - dernier > ESPACEMENT_J * JOUR_NS:
            garde[i] = True
            dernier = j[i]
    return j[garde], c[garde]


def tension_a(t_ns: np.ndarray) -> np.ndarray:
    """Vrai si une TENSION géopolitique court à l'instant t : moyenne des 7 dernières valeurs du GPR (connues) au-dessus
    du centile 80 de cette moyenne sur les 365 valeurs précédentes (même calcul que donnees/monde.tension_a)."""
    assert (MW.TENSION_MA, MW.TENSION_FEN, MW.TENSION_Q) == (TENSION_MA, TENSION_FEN, TENSION_Q)
    return MW.tension_a(t_ns)


_JOURNAL = {}


def table_marche(nom: str) -> pd.DataFrame:
    """Pour CHAQUE jour J (calendaire) : entrée (instant, prix) à J+1 08h00 serveur, sortie et rendement à 1 / 5 / 20
    jours de Bourse, écart quotidien des 60 derniers jours, tendance de fond 60 j à l'entrée."""
    if nom in _JOURNAL:
        return _JOURNAL[nom]
    q = D.quinze(nom)
    t = q["time"].values.astype("datetime64[ns]").astype(np.int64)
    o, c = q["open"].to_numpy(float), q["close"].to_numpy(float)
    jours, clo = DI.clotures_jour(t, c)
    r1 = np.r_[np.nan, np.diff(np.log(clo))]
    sd = pd.Series(r1).rolling(60, min_periods=30).std().to_numpy()
    J = np.arange(t[0] - t[0] % JOUR_NS, t[-1], JOUR_NS, dtype=np.int64)
    E = J + MW.DELAI_NS
    ie = np.searchsorted(t, E)
    ok = ie < len(t)
    iec = np.clip(ie, 0, len(t) - 1)
    ok &= (t[iec] - E) <= ENTREE_MAX_J * JOUR_NS
    te, pe = t[iec], o[iec]
    kd = np.searchsorted(jours, te - te % JOUR_NS) - 1                  # dernier jour terminé avant le jour d'entrée
    s60 = np.where(kd >= 0, sd[np.clip(kd, 0, None)], np.nan)
    sg, _ = DI.tendance_aux(jours, clo, te, (60,))
    df = pd.DataFrame({"J": J, "E": E, "te": te, "ok": ok, "t60": sg[:, 0], "s60": s60})
    for h, cal in HORIZONS.items():
        k = np.searchsorted(t + QUINZE_NS, te + cal * JOUR_NS, side="right") - 1
        okh = ok & (k >= iec)
        kc = np.clip(k, 0, len(t) - 1)
        ret = np.where(okh, np.log(c[kc] / pe), np.nan)
        df[f"ret{h}"] = ret
        df[f"z{h}"] = ret / (s60 * math.sqrt(h))
        df[f"sortie{h}"] = np.where(okh, t[kc] + QUINZE_NS, -1)
    _JOURNAL[nom] = df
    return df


def table_groupe(g: str) -> pd.DataFrame:
    """Par jour J : moyenne des marchés du groupe (rendement orienté normalisé, % brut orienté, continuation)."""
    parts = []
    for nom, ori in GROUPES[g]:
        d = table_marche(nom).set_index("J")
        x = pd.DataFrame(index=d.index)
        for h in HORIZONS:
            x[f"z{h}"] = d[f"z{h}"] * ori
            x[f"pct{h}"] = (np.exp(d[f"ret{h}"] * ori) - 1) * 100
            cont = np.where((d["t60"] != 0) & np.isfinite(d[f"ret{h}"]), (np.sign(d[f"ret{h}"]) == d["t60"]).astype(float), np.nan)
            x[f"cont{h}"] = cont
            x[f"sortie{h}"] = d[f"sortie{h}"]
        x["E"] = d["E"]
        parts.append(x)
    allj = sorted(set().union(*[p.index for p in parts]))
    parts = [p.reindex(allj) for p in parts]
    out = pd.DataFrame(index=pd.Index(allj, name="J"))
    out["E"] = np.nanmax(np.stack([p["E"].to_numpy(float) for p in parts]), 0)
    for h in HORIZONS:
        for k in ("z", "pct", "cont"):
            out[f"{k}{h}"] = np.nanmean(np.stack([p[f"{k}{h}"].to_numpy(float) for p in parts]), 0)
        out[f"sortie{h}"] = np.nanmax(np.stack([p[f"sortie{h}"].to_numpy(float) for p in parts]), 0)
    return out


def cases_A(periode: str, dire=print) -> list[dict]:
    de, a = _periode_ns(periode)
    rng = np.random.default_rng(20261018)
    evts = {s: evenements_signal(s) for s in SIGNAUX}
    out = []
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    for g in GROUPES:
        tg = table_groupe(g)
        Jg = tg.index.to_numpy(np.int64)
        for h in HORIZONS:
            for mes in MESURES:
                col = f"z{h}" if mes == "rendement" else f"cont{h}"
                y = tg[col].to_numpy(float)
                elig = np.isfinite(y) & (tg["E"].to_numpy() >= de) & (tg["E"].to_numpy() < a) \
                    & (tg[f"sortie{h}"].to_numpy() < a) & (tg[f"sortie{h}"].to_numpy() > 0)
                base_v = y[elig]
                pct = tg[f"pct{h}"].to_numpy(float)
                for s in SIGNAUX:
                    jj, _ = evts[s]
                    i = np.searchsorted(Jg, jj)
                    okj = (i < len(Jg)) & (Jg[np.clip(i, 0, len(Jg) - 1)] == jj)
                    i = i[okj]
                    i = i[elig[i]]
                    n = len(i)
                    r = {"signal": s, "groupe": g, "h": h, "mesure": mes, "n": int(n),
                         "base": float(base_v.mean()) if len(base_v) else float("nan"), "n_base": int(len(base_v))}
                    if n >= 3 and len(base_v) > n:
                        m_ev = float(y[i].mean())
                        tir = np.array([base_v[rng.choice(len(base_v), n, replace=False)].mean() for _ in range(TIRAGES_A)])
                        sd = float(tir.std())
                        r.update({"moy": m_ev, "hasard": float(tir.mean()), "hasard_sd": sd,
                                  "force": (m_ev - float(tir.mean())) / sd if sd > 0 else float("nan"),
                                  "pct": float(np.nanmean(pct[i])), "pct_base": float(np.nanmean(pct[elig]))})
                    out.append(r)
        dire(f"A {periode} : {g} fait")
    return out


def cle_A(r: dict) -> str:
    return f"{r['signal']}|{r['groupe']}|{r['h']}|{r['mesure']}"


# ============================================================================================== B. sens du monde
def sens_monde(nom: str, dec_ns: np.ndarray, retenues: list[dict]) -> np.ndarray:
    """Sens proposé par le contexte du monde (cases retenues sur <= 2021) à chaque instant de décision."""
    dec_ns = np.asarray(dec_ns, np.int64)
    vote = np.zeros(len(dec_ns))
    t60 = None
    for r in retenues:
        mg = MARCHES_GROUPE[r["groupe"]]
        if mg == "TOUTES":
            ori = 1 if D.source(nom) == "binance" else None
        else:
            ori = dict(mg).get(nom)
        if ori is None:
            continue
        _, c = evenements_signal(r["signal"])
        cal = HORIZONS[r["h"]] * JOUR_NS
        i = np.searchsorted(c, dec_ns, side="right") - 1
        actif = (i >= 0) & (dec_ns < c[np.clip(i, 0, None)] + cal) if len(c) else np.zeros(len(dec_ns), bool)
        sg = float(np.sign(r["effet"]))
        if r["mesure"] == "rendement":
            vote += actif * sg * ori
        else:
            if t60 is None:
                t60 = DI.tendance(nom, dec_ns)[0][:, 1].astype(float)
            vote += actif * sg * t60
    return np.sign(vote).astype(np.int8)


def sens_variante(sv: str, nom: str, dec_ns: np.ndarray, retenues: list[dict]) -> np.ndarray:
    t60 = DI.tendance(nom, dec_ns)[0][:, 1].astype(np.int8)
    if sv == "T60":
        return t60
    if sv == "MONDE":
        return sens_monde(nom, dec_ns, retenues)
    if sv == "T60+MONDE":
        mo = sens_monde(nom, dec_ns, retenues)
        return np.where(mo == t60, t60, 0).astype(np.int8)
    te = tension_a(dec_ns)
    if sv == "T60+TENSION":
        return np.where(te, t60, 0).astype(np.int8)
    return np.where(~te, t60, 0).astype(np.int8)


def geometrie(x: dict, ev: dict, fam: str, gl: float) -> dict:
    """Trades d'un scénario : sens, stop derrière la zone ÉLARGI pour frais <= 0,03 R."""
    c, A, demi = (np.asarray(x[k], np.float64) for k in ("c", "A", "demi"))
    j = ev["j"].astype(np.int64)
    reb = fam == "REB"
    idx = np.flatnonzero(ev["genre"] == (1 if reb else 2))
    side = ev["side"][idx]
    sens = side if reb else -side
    p, Aj = c[j[idx]], A[j[idx]]
    loin = np.where(sens > 0, ev["bot"][idx], ev["top"][idx])
    rd_z = sens * (p - (loin - sens * MARGE_A * Aj))
    rd_min = (2.0 + gl) * demi[j[idx]] * p / FRAIS_MAX_R
    rd = np.maximum(rd_z, rd_min)
    ok = np.isfinite(Aj) & (Aj > 0) & np.isfinite(rd) & (rd_z > 0) & (rd >= RISQUE_MIN_A * Aj) & (rd <= RISQUE_MAX_A * Aj)
    idx, sens, p, Aj, rd = idx[ok], sens[ok], p[ok], Aj[ok], rd[ok]
    return {"idx": idx, "sens": sens.astype(np.float64), "stop": p - sens * rd, "p": p, "A": Aj,
            "elargi": (rd > rd_z[ok] + 1e-12)}


def trades_marche(nom: str, x: dict, de_ns: int, a_ns: int, variantes: list, retenues: list, graine: int) -> dict:
    from collapsar.ecole.precision.univers import Univers
    from collapsar.regarder.pistes import logique_inversee as LI
    t15 = np.asarray(x["t15"], np.int64)
    debut = max(pd.Timestamp(int(t15[0])) + pd.Timedelta(days=45), pd.Timestamp(de_ns) - pd.Timedelta(days=5))
    if debut.value >= a_ns - 30 * JOUR_NS:
        return {}
    U = Univers([(nom, False)], debut, pd.Timestamp(a_ns) + pd.Timedelta(days=40), "cpu")
    ch = JT.chemin(U)
    gl = float(R().monde.frais_stop_glissement)
    m = np.searchsorted(t15, U.t_ns)
    assert np.array_equal(t15[np.clip(m, 0, len(t15) - 1)], U.t_ns), nom
    tv_l, tid_l, tv_s, tid_s = M.suiveur_lignes(x, SUIVEUR, m - 1)
    ev = M.evenements_marche(x)
    geo = {fam: geometrie(x, ev, fam, gl) for fam in SCENARIOS}
    rng = np.random.default_rng(graine)
    okf = np.zeros(U.T, bool)
    okf[:-2] = U.ouvert[1:-1, 0] & ~U.derniere[1:-1, 0]
    dec_u = U.t_ns + QUINZE_NS
    okf &= (dec_u >= de_ns) & (dec_u < a_ns) & (U.A[:, 0] > 0)
    lignes_f = np.flatnonzero(okf)
    out = {}
    jo = lambda tt, sg, st, ds, dr, sv, mm: M.jouer(*ch, tt.astype(np.int64), sg, st, ds, dr, sv, HORIZON, gl,
                                                    tv_l, tid_l, tv_s, tid_s, mm)
    for v in variantes:
        g = geo[v[1]]
        j = ev["j"][g["idx"]].astype(np.int64)
        dec = t15[j] + QUINZE_NS
        okp = (dec >= de_ns) & (dec < a_ns) & (t15[j] >= U.t_ns[0])
        if okp.any():
            sp = sens_variante(v[0], nom, dec[okp], retenues)
            o2 = np.zeros(len(okp), bool)
            o2[np.flatnonzero(okp)] = (sp == g["sens"][okp]) & (sp != 0)
            okp = o2
        sel = np.flatnonzero(okp)
        if not len(sel):
            continue
        tU = np.searchsorted(U.t_ns, t15[j[sel]])
        assert np.array_equal(U.t_ns[np.clip(tU, 0, U.T - 1)], t15[j[sel]])
        sens, stop, p, Aj, el = g["sens"][sel], g["stop"][sel], g["p"][sel], g["A"][sel], g["elargi"][sel]
        n = len(sel)
        nan = np.full(n, np.nan)
        mg = MARGE_A * Aj
        exe, ne, ns, rr, code, mfe = jo(tU, sens, stop, nan, np.zeros(n), np.ones(n, bool), mg)
        kg = LI.garder_un_a_la_fois(tU, exe, ns, code)
        tU, sens, stop, p, Aj, mg, el = tU[kg], sens[kg], stop[kg], p[kg], Aj[kg], mg[kg], el[kg]
        exe, ne, ns, rr, code, mfe = exe[kg], ne[kg], ns[kg], rr[kg], code[kg], mfe[kg]
        n = len(tU)
        nan = np.full(n, np.nan)
        rd = sens * (p - stop)
        tn = lambda k: np.where(k >= 0, U.t_ns[np.clip(k, 0, U.T - 1)], -1)
        z = {"dec_ns": U.t_ns[tU] + QUINZE_NS, "sens": sens.astype(np.int8),
             "unite": ev["unite"][g["idx"][sel][kg]].astype(np.int8), "risque_A": rd / Aj, "risque_pct": rd / p * 100,
             "elargi": el, "frais_R": (2.0 + gl) * U.demi[np.clip(tU + 1, 0, U.T - 1), 0] * p / rd,
             "exe": exe, "r": rr, "code": code, "ne_ns": tn(ne), "ns_ns": tn(ns), "mfe": mfe}
        if n:
            exe_j, ne_j, ns_j, rr_j, code_j, _ = jo(tU, -sens, 2 * p - stop, nan, np.zeros(n), np.ones(n, bool), mg)
            tf = rng.choice(lignes_f, n) if len(lignes_f) else tU
            pf, Af = U.c[tf, 0].astype(np.float64), U.A[tf, 0].astype(np.float64)
            rdf = rd / Aj * Af
            exe_f, _, ns_f, rr_f, code_f, _ = jo(tf, sens, pf - sens * rdf, nan, np.zeros(n), np.ones(n, bool), MARGE_A * Af)
            exe_c, _, ns_c, rr_c, code_c, _ = jo(tU, sens, stop, nan, np.full(n, 2.0), np.zeros(n, bool), mg)
            z.update({"exe_j": exe_j, "r_j": rr_j, "code_j": code_j, "ne_j_ns": tn(ne_j), "ns_j_ns": tn(ns_j),
                      "exe_f": exe_f, "r_f": rr_f, "code_f": code_f, "dec_f_ns": U.t_ns[tf] + QUINZE_NS,
                      "exe_c": exe_c, "r_c": rr_c, "code_c": code_c})
        out[vid(v)] = z
    del U, ch
    return out


def calculer_B(periode: str, variantes: list, retenues: list, dire=print) -> list:
    from collapsar.ecole.precision import structure as S
    de_ns, a_ns = _periode_ns(periode)
    dos = SORTIE / periode
    dos.mkdir(parents=True, exist_ok=True)
    acc = {vid(v): [] for v in variantes}
    marches = list(D.univers())
    t0 = time.time()
    for im, nom in enumerate(marches):
        x = S.lire(nom, False)
        tr = trades_marche(nom, x, de_ns, a_ns, variantes, retenues, 20261018 + im)
        for k, z in tr.items():
            z["marche"] = np.full(len(z["exe"]), im, np.int16)
            acc[k].append(z)
        dire(f"B {periode} {nom} : " + ", ".join(f"{k} {int(z['exe'].sum())}" for k, z in tr.items())
             + f" trades ({time.time() - t0:.0f} s)")
    for k, morceaux in acc.items():
        if morceaux:
            np.savez(dos / f"{k}.npz", **{c: np.concatenate([m_[c] for m_ in morceaux]) for c in morceaux[0]})
    (dos / "marches.json").write_text(json.dumps(marches), encoding="utf-8")
    return marches


def lire_trades(periode: str, k: str) -> dict | None:
    f = SORTIE / periode / f"{k}.npz"
    if not f.exists():
        return None
    z = np.load(f)
    return {c: z[c] for c in z.files}


def mois_periode(periode: str, dec_ns: np.ndarray) -> float:
    de_ns, a_ns = _periode_ns(periode)
    if not len(dec_ns):
        return float("nan")
    return (a_ns - max(de_ns, int(dec_ns.min()))) / MOIS_NS


def mesurer_variante(z: dict, periode: str, noms: list) -> dict:
    mois = mois_periode(periode, z["dec_ns"])
    res = {"variante": M.bloc(z, mois)}
    if "exe_j" in z and len(z["exe"]):
        res.update({"retourne": M.bloc(z, mois, "_j"), "fausses": M.bloc(z, mois, "_f"), "plafond2r": M.bloc(z, mois, "_c"),
                    "avance_jumeau": M.avance(z, "_j", True), "avance_fausses": M.avance(z, "_f", False),
                    "avance_plafond": M.avance(z, "_c", False)})
    ok = z["exe"] & (z["code"] != JT.FIN)
    res["variante"]["elargi_pct"] = float(z["elargi"][ok].mean() * 100) if ok.any() else float("nan")
    nm = np.asarray(noms)[z["marche"]] if len(z["marche"]) else np.zeros(0, str)
    grp = np.asarray([JT.groupe(n) for n in nm]) if len(nm) else np.zeros(0, str)
    res["groupes"] = {gname: M.bloc(z, mois, masque=(grp == gname)) for gname in ("cryptos", "minute", "45 marchés")}
    for g, mg in MARCHES_GROUPE.items():
        if mg == "TOUTES":
            continue
        res["groupes"][g] = M.bloc(z, mois, masque=np.isin(nm, [m for m, _ in mg]))
    return res


def compte_contre_jumeaux(z: dict, risque_pct: float, periode: str, tirages: int = TIRAGES, graine: int = 20261018) -> dict:
    from collapsar.regarder.pistes import logique_inversee as LI
    de_ns, a_ns = _periode_ns(periode)
    if len(z["dec_ns"]):
        d0 = int(z["dec_ns"].min())
        de_ns = max(de_ns, d0 - d0 % JOUR_NS)
    ok = z["exe"] & (z["code"] != JT.FIN)
    reel = LI.compte(z["ne_ns"][ok], z["ns_ns"][ok], z["r"][ok], risque_pct, de_ns, a_ns)
    rng = np.random.default_rng(graine)
    okj = z["exe_j"] & (z["code_j"] != JT.FIN)
    gains, reus, morts = [], [], []
    for _ in range(tirages):
        pile = rng.random(len(ok)) < 0.5
        mr, mj = ok & pile, okj & ~pile
        c = LI.compte(np.r_[z["ne_ns"][mr], z["ne_j_ns"][mj]], np.r_[z["ns_ns"][mr], z["ns_j_ns"][mj]],
                      np.r_[z["r"][mr], z["r_j"][mj]], risque_pct, de_ns, a_ns)
        gains.append(c["gain_mois_pct"])
        reus.append(c["reussis"])
        morts.append(c["morts"])
    gains = np.asarray(gains)
    return {"reel": reel, "jumeaux_gain_mois_moyen": float(gains.mean()), "jumeaux_gain_mois_sd": float(gains.std()),
            "jumeaux_au_moins_aussi_bien_pct": float((gains >= reel["gain_mois_pct"]).mean() * 100),
            "jumeaux_reussis_moyen": float(np.mean(reus)), "jumeaux_morts_moyen": float(np.mean(morts))}


# ============================================================================================== étapes
def _lire(nom):
    f = SORTIE / f"{nom}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def etape(periode: str, dire=print) -> dict:
    if periode == "lecture" and (SORTIE / "lecture.json").exists():
        raise SystemExit("la lecture 2024-2025 a déjà été faite (une seule fois)")
    res = {"periode": periode, "date": datetime.now().isoformat(timespec="seconds")}
    # --- A
    cas = cases_A(periode, dire)
    res["evenements"] = {s: int(((evenements_signal(s)[1] >= _periode_ns(periode)[0])
                                 & (evenements_signal(s)[1] < _periode_ns(periode)[1])).sum()) for s in SIGNAUX}
    if periode == "choix":
        elig = [r for r in cas if r.get("n", 0) >= MIN_EVT and np.isfinite(r.get("force", np.nan))
                and abs(r["force"]) >= FORCE_RETENUE]
        fortes = sorted(elig, key=lambda r: -abs(r["force"]))[:RETENUES_MAX]
        res["retenues"] = [{"signal": r["signal"], "groupe": r["groupe"], "h": r["h"], "mesure": r["mesure"],
                            "effet": r["moy"] - r["hasard"], "force": r["force"]} for r in fortes]
        dire(f"A : {len(fortes)} cases retenues sur <= 2021")
    else:
        ch = _lire("choix")
        res["retenues"] = ch["retenues"]
    res["cases"] = cas
    # --- B
    if periode == "lecture":
        ch = _lire("choix")
        variantes = [tuple(ch["retenue"].split("-", 1))]
    else:
        variantes = VARIANTES
    noms = calculer_B(periode, variantes, res["retenues"], dire)
    res["variantes"] = {}
    for v in variantes:
        z = lire_trades(periode, vid(v))
        if z is not None:
            res["variantes"][vid(v)] = mesurer_variante(z, periode, noms)
    if periode == "choix":
        elig = [(m_["variante"].get("force", -np.inf), k) for k, m_ in res["variantes"].items()
                if m_["variante"].get("n", 0) >= MIN_TRADES]
        elig = [(f_ if np.isfinite(f_) else -np.inf, k) for f_, k in elig]
        res["retenue"] = max(elig)[1] if elig else None
        dire(f"B : variante retenue sur <= 2021 : {res['retenue']}")
    else:
        res["retenue"] = _lire("choix")["retenue"]
    k = res["retenue"]
    if k:
        z = lire_trades(periode, k)
        if z is not None and len(z["exe"]):
            res["comptes"] = {str(rk): compte_contre_jumeaux(z, rk, periode) for rk in RISQUES}
    (SORTIE / f"{periode}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return res


def verdict_B(ch, ve, le) -> str:
    k = ch.get("retenue")
    if not k or not ve or k not in ve["variantes"]:
        return "non (aucune variante)"
    r1 = ch["variantes"][k]["variante"].get("r", np.nan)
    b2 = ve["variantes"][k]["variante"]
    r2, f2 = b2.get("r", np.nan), b2.get("force", np.nan)
    r3 = le["variantes"][k]["variante"].get("r", np.nan) if le and k in le.get("variantes", {}) else np.nan
    if r1 > 0 and r2 > 0 and f2 >= 2 and not (r3 <= 0):
        return "FORT (à juger en direct)" if f2 >= SEUIL else "PROMETTEUR (non prouvé)"
    return "non"


def verdict_A(r_ch: dict, r_ve: dict | None) -> str:
    if not r_ve or not np.isfinite(r_ve.get("force", np.nan)):
        return "—"
    meme = np.sign(r_ch["force"]) == np.sign(r_ve["force"])
    if meme and abs(r_ve["force"]) >= SEUIL:
        return "PROUVÉE"
    if meme and abs(r_ve["force"]) >= 2:
        return "confirmée"
    return "non" if not meme else "même signe, faible"


# ============================================================================================== rapport
def _f(x, n=3, signe=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:+.{n}f}" if signe else f"{x:.{n}f}"


def _fmt_case(r: dict | None) -> str:
    if not r or "moy" not in r:
        return "—"
    if r["mesure"] == "rendement":
        return (f"{r['moy']:+.2f} contre {r['hasard']:+.2f} ({r['pct']:+.2f} % contre {r['pct_base']:+.2f} %) ; "
                f"n {r['n']} ; force {_f(r['force'], 1)}")
    return f"{r['moy'] * 100:.0f} % contre {r['hasard'] * 100:.0f} % ; n {r['n']} ; force {_f(r['force'], 1)}"


ENT_V = ("| variante | trades | trades / mois | gagnants | R moyen ± incertitude (force) ; frais en R | médiane | >= 5R / "
         ">= 10R (part des gains) | stop élargi | jumeau : avance (force) | fausses zones : R ; avance (force) | plafond 2R : "
         "R ; avance (force) |\n|---|---|---|---|---|---|---|---|---|---|---|")


def ligne_v(k: str, m: dict) -> str:
    b = m["variante"]
    if b.get("n", 0) == 0:
        return f"| {k} | 0 | — | — | — | — | — | — | — | — | — |"
    fr = f" ; frais ≈ {b['frais_R']:.3f}" if "frais_R" in b else ""
    el = f"{b['elargi_pct']:.0f} %" if "elargi_pct" in b and np.isfinite(b.get("elargi_pct", np.nan)) else "—"
    s = (f"| {k} | {b['n']} | {b['trades_mois']:.1f} | {b['gagnants_pct']:.0f} % | {_f(b['r'])} ± {_f(b['inc'], 3, False)} "
         f"({_f(b['force'], 1)}){fr} | {_f(b['mediane'])} | {b['p5']:.1f} % / {b['p10']:.1f} % ({b['part5']:.0f} % / "
         f"{b['part10']:.0f} %) | {el} |")
    if "avance_jumeau" in m:
        aj, af, ac = m["avance_jumeau"], m["avance_fausses"], m["avance_plafond"]
        s += (f" {_f(aj['avance'])} ({_f(aj['force'], 1)}) | {_f(m['fausses'].get('r'))} ; {_f(af['avance'])} "
              f"({_f(af['force'], 1)}) | {_f(m['plafond2r'].get('r'))} ; {_f(ac['avance'])} ({_f(ac['force'], 1)}) |")
    else:
        s += " — | — | — |"
    return s


def lignes_compte(c: dict) -> list[str]:
    L = ["| risque / trade | gain / mois | baisse max | challenges : réussis / morts (terminés / départs) | jours médians "
         f"| {TIRAGES} jumeaux : gain / mois | jumeaux au moins aussi bons | jumeaux : réussis / morts |",
         "|---|---|---|---|---|---|---|---|"]
    for rk, x in c.items():
        r = x["reel"]
        L.append(f"| {rk} % | {r['gain_mois_pct']:+.2f} % | {r['baisse_max_pct']:.1f} % | {r['reussis']} / {r['morts']} "
                 f"({r['termines']} / {r['departs']}) | {_f(r['jours_median_termine'], 0, False)} | "
                 f"{x['jumeaux_gain_mois_moyen']:+.2f} % ± {x['jumeaux_gain_mois_sd']:.2f} | "
                 f"{x['jumeaux_au_moins_aussi_bien_pct']:.0f} % | {x['jumeaux_reussis_moyen']:.1f} / {x['jumeaux_morts_moyen']:.1f} |")
    return L


def ecrire_rapport():
    ch, ve, le = _lire("choix"), _lire("verification"), _lire("lecture")
    L = [f"# HYPERNOVA — LES YEUX DU MONDE : le contexte géopolitique et la peur donnent-ils le sens ? (rapport du "
         f"{datetime.now():%d/%m/%Y %H:%M})", "",
         "Mesure SANS IA. Données : collapsar/donnees/monde.py (valeur du jour J utilisable à J+1 08h00 heure du "
         "serveur). Trades joués par le moteur de la piste « mouvements » (frais FTMO, glissement, nuits, bougie au pire), "
         "stop suiveur 1 h, aucun plafond. R = résultat en multiples du risque, frais compris. Force = moyenne / "
         f"incertitude. N = {N_TOTAL} cases (dont {N_DEJA} déjà jugées) -> seuil de preuve = {SEUIL:.2f}.", ""]
    f_c = SORTIE / "conclusion.md"
    if f_c.exists():
        L.append(f_c.read_text(encoding="utf-8").strip() + "\n")
    if not ch:
        (SORTIE / "rapport.md").write_text("\n".join(L), encoding="utf-8")
        return
    # A. événements
    L.append("## A. Après une hausse brusque du risque géopolitique / de la peur\n")
    L.append("Nombre d'événements par signal (choix / vérification / lecture) :\n")
    L.append("| signal | <= 2021 | 2022-23 | 2024-25 |")
    L.append("|---|---|---|---|")
    for s in SIGNAUX:
        L.append(f"| {s} | {ch['evenements'].get(s, 0)} | {ve['evenements'].get(s, 0) if ve else '—'} | "
                 f"{le['evenements'].get(s, 0) if le else '—'} |")
    L.append("")
    idx = lambda res: {cle_A(r): r for r in res["cases"]} if res else {}
    ich, ive, ile = idx(ch), idx(ve), idx(le)
    L.append(f"### Cases retenues sur <= 2021 (|force| >= {FORCE_RETENUE:g}, au plus {RETENUES_MAX}) et leur suite\n")
    L.append("Rendement : moyenne normalisée (en écarts) contre dates au hasard, puis % brut contre taux de base. "
             "Continuation : part des cas où la tendance de fond 60 j continue, contre dates au hasard.\n")
    L.append("| signal | groupe | h (jours de Bourse) | mesure | <= 2021 | 2022-2023 | verdict | 2024-25 (lecture) |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in ch["retenues"]:
        k = cle_A(r)
        L.append(f"| {r['signal']} | {r['groupe']} | {r['h']} | {r['mesure']} | {_fmt_case(ich.get(k))} | "
                 f"{_fmt_case(ive.get(k))} | {verdict_A(ich[k], ive.get(k))} | {_fmt_case(ile.get(k))} |")
    if not ch["retenues"]:
        L.append("| aucune | | | | | | | |")
    L.append("")
    # tableau de synthèse : par groupe, la meilleure force (signe) sur <= 2021, rendement à 5 jours
    L.append("### Vue d'ensemble <= 2021 : force de chaque signal sur le rendement à 5 jours (orienté : + = or / argent / "
             "pétrole / actions / cryptos montent, yen / franc montent)\n")
    gs = list(GROUPES)
    L.append("| signal | " + " | ".join(gs) + " |")
    L.append("|---|" + "---|" * len(gs))
    for s in SIGNAUX:
        cells = []
        for g in gs:
            r = ich.get(f"{s}|{g}|5|rendement")
            cells.append(_f(r.get("force"), 1) if r and "force" in r else "—")
        L.append(f"| {s} | " + " | ".join(cells) + " |")
    L.append("")
    L.append("### Même vue en 2022-2023 (vérification)\n")
    L.append("| signal | " + " | ".join(gs) + " |")
    L.append("|---|" + "---|" * len(gs))
    for s in SIGNAUX:
        cells = []
        for g in gs:
            r = ive.get(f"{s}|{g}|5|rendement")
            cells.append(_f(r.get("force"), 1) if r and "force" in r else "—")
        L.append(f"| {s} | " + " | ".join(cells) + " |")
    L.append("")
    # B
    k = ch.get("retenue")
    L.append(f"## B. Sens + ses zones + laisser courir — retenue sur <= 2021 : **{k}** — verdict : "
             f"**{verdict_B(ch, ve, le)}**\n")
    if k:
        L.append(ENT_V)
        for nom_p, r in (("choix", ch), ("verification", ve), ("lecture", le)):
            if r and k in r.get("variantes", {}):
                L.append(ligne_v(f"{k} {NOM_P[nom_p]}", r["variantes"][k]))
        L.append("")
        for nom_p, r in (("choix", ch), ("verification", ve), ("lecture", le)):
            if r and "comptes" in r:
                L.append(f"### Compte FTMO 100 000 $ de {k} — {NOM_P[nom_p]}\n")
                L += lignes_compte(r["comptes"])
                L.append("")
    for nom_p, r in (("choix", ch), ("verification", ve)):
        if not r:
            continue
        L.append(f"### Les {len(VARIANTES)} variantes — {NOM_P[nom_p]}\n")
        L.append(ENT_V)
        for v in VARIANTES:
            if vid(v) in r["variantes"]:
                L.append(ligne_v(vid(v), r["variantes"][vid(v)]))
        L.append("")
        L.append("Par groupe de marchés (R moyen ; trades ; force) :\n")
        gn = ["cryptos", "minute", "45 marchés"] + [g for g, mg in MARCHES_GROUPE.items() if mg != "TOUTES"]
        L.append("| variante | " + " | ".join(gn) + " |")
        L.append("|---|" + "---|" * len(gn))
        for v in VARIANTES:
            m_ = r["variantes"].get(vid(v))
            if not m_:
                continue
            cells = [f"{b['r']:+.3f} ({b['n']} ; {_f(b['force'], 1)})" if b.get("n") else "—"
                     for b in (m_["groupes"].get(g, {}) for g in gn)]
            L.append(f"| {vid(v)} | " + " | ".join(cells) + " |")
        L.append("")
    f_plan = SORTIE / "plan_fige.md"
    if f_plan.exists():
        L.append(f_plan.read_text(encoding="utf-8").replace("# LES YEUX", "## LES YEUX").replace("\n## ", "\n### "))
    (SORTIE / "rapport.md").write_text("\n".join(L), encoding="utf-8")


def dire_(t):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {t}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("quoi", choices=["plan", "choix", "verification", "lecture", "rapport"])
    a = ap.parse_args(argv)
    SORTIE.mkdir(parents=True, exist_ok=True)
    if a.quoi == "plan":
        f = SORTIE / "plan_fige.md"
        if f.exists():
            raise SystemExit(f"{f} existe déjà : le plan est figé")
        f.write_text(plan_texte(), encoding="utf-8")
        dire_(f"plan figé : {f}")
        return
    if not (SORTIE / "plan_fige.md").exists():
        raise SystemExit("figer d'abord le plan (commande plan)")
    if a.quoi in ("choix", "verification", "lecture"):
        if a.quoi != "choix" and not (SORTIE / "choix.json").exists():
            raise SystemExit("faire d'abord le choix sur <= 2021")
        if a.quoi == "lecture" and not (SORTIE / "verification.json").exists():
            raise SystemExit("faire d'abord la vérification 2022-2023")
        etape(a.quoi, dire_)
    ecrire_rapport()
    dire_("rapport écrit : " + str(SORTIE / "rapport.md"))


if __name__ == "__main__":
    main()
