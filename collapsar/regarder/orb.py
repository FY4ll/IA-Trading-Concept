"""PISTE « OUVERTURE DE NEW YORK » : cassure du range d'ouverture (15/10/2026, cahier des charges du chef de projet).

Stratégie (rien d'autre à régler que N et le filtre) :
- range = plus haut / plus bas des N premières minutes après 9h30 (heure de New York), N dans {5, 15, 30} ;
- entrée par ordre STOP à la cassure, dans le sens de la cassure ; UN trade par jour ;
- stop de l'autre côté du range ; sortie à 15h55 (avant la clôture de 16h) ou au stop ;
- version FILTRÉE : seulement les jours où la prévision d'agitation (méthode HAR de Corsi 2009 : agitation d'hier,
  de la semaine, du mois) est dans le tiers supérieur de l'année écoulée (seuil glissant : rien du futur).
Frais : ceux de la fiche FTMO du marché (aller-retour, écart + commission), l'écart plus large à l'ouverture
(mesuré à la minute sur les prix acheteur/vendeur Dukascopy du mercredi), et un glissement d'une demi-fiche sur
chaque ordre stop (entrée et stop touché). Un trou de prix au-delà d'un niveau est payé au prix d'ouverture.
Dans une même minute, si le prix touche l'entrée ET le stop, on compte la perte (prudence).
Juge à JUMEAU : même minute d'entrée, même prix, même distance de stop, même sortie, sens tiré à pile ou face ;
son espérance = moyenne du trade et du trade inverse -> écart = (R - R_inverse) / 2 ; force = moyenne / écart type
x racine(n). Seuil de preuve : max(3, racine(2 ln(variantes))).
Protocole : choix de N et du filtre sur 2015-2021 ; vérification 2022-2023 ; période CACHÉE 2024-2026 évaluée UNE
SEULE FOIS (verrou vie/orb/cachee.json).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.regarder.orb choix|verification|cachee
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche

VIE = dm.RACINE / "collapsar" / "vie" / "orb"
INSTRUMENTS = {"NAS100": "USATECHIDXUSD", "US500": "USA500IDXUSD", "XAUUSD": "XAUUSD"}
N_CHOIX = (5, 15, 30)
FILTRES = (False, True)
PERIODES = {"choix": ("2015-01-01", "2022-01-01"), "verification": ("2022-01-01", "2024-01-01"),
            "cachee": ("2024-01-01", "2026-12-31")}
OUVERTURE, SORTIE = (9, 30), (15, 55)
VARIANTES = len(INSTRUMENTS) * len(N_CHOIX) * len(FILTRES)
# écart pendant la 1re heure / écart médian de la séance, mesuré chez Tradeco (bougies de 5 min, 05/2025 -> 10/2026)
FACTEUR_OUVERTURE = {"NAS100": 1.07, "US500": 1.16, "XAUUSD": 1.0}
MANQUE_MAX = 0.05            # part maximale de minutes manquantes dans une séance gardée (audit 16/10, défaut 3)
MANQUE_ANCIEN = 90 / 390     # ancien réglage (séance gardée dès 300 minutes), pour comparaison seulement


def seuil(variantes: int = VARIANTES) -> float:
    return max(3.0, math.sqrt(2 * math.log(variantes)))


# ---------------------------------------------------------------------- les données à la minute, heure de New York
def minutes(instrument: str) -> pd.DataFrame:
    sym = INSTRUMENTS[instrument]
    if sym == "XAUUSD":                                   # or : 1 minute depuis 2004, heure du serveur = New York + 7 h
        df = pd.read_csv(dm.RACINE / "data" / "kaggle_gold" / "XAU_1m_data.csv", sep=";")
        df.columns = [c.lower() for c in df.columns]
        df["ny"] = pd.to_datetime(df["date"], format="%Y.%m.%d %H:%M") - pd.Timedelta(hours=7)
        df["ecart"] = np.nan
    else:                                                 # indices : HistData (Dukascopy bridé), heure de New York
        from collapsar.donnees.histdata import charger
        df = charger({"USATECHIDXUSD": "NSXUSD", "USA500IDXUSD": "SPXUSD"}[sym])
        df["ecart"] = np.nan
    df = df[["ny", "open", "high", "low", "close", "ecart"]].dropna(subset=["open", "close"])
    return df.drop_duplicates("ny").sort_values("ny").reset_index(drop=True)


def minutes_min(manque_max: float = MANQUE_MAX) -> int:
    """Nombre minimal de minutes (sur 390) pour garder une séance : au plus `manque_max` de minutes manquantes."""
    return 390 - int(math.floor(390 * manque_max + 1e-9))


def seances(df: pd.DataFrame, manque_max: float = MANQUE_MAX) -> dict:
    """{jour: tableau [minutes de 9h30 à 16h00] (minute depuis 9h30, open, high, low, close, écart)}.
    Audit du 16/10 (défaut 3) : une séance où plus de 5 % des minutes manquent est ÉCARTÉE (avant : gardée dès 300
    minutes sur 390 puis bouchée « à plat », ce qui fabriquait de faux signaux ; ancien réglage = manque_max 90/390).
    Les demi-journées sont écartées de la même façon."""
    m = df["ny"].dt.hour * 60 + df["ny"].dt.minute - (OUVERTURE[0] * 60 + OUVERTURE[1])
    rth = (m >= 0) & (m < 390)
    d = df[rth].assign(m=m[rth], jour=df.loc[rth, "ny"].dt.normalize())
    mini = minutes_min(manque_max)
    return {j: g[["m", "open", "high", "low", "close", "ecart"]].to_numpy(float) for j, g in d.groupby("jour")
            if len(g) >= mini}


def profil_ecart(s: dict) -> dict:
    """Écart médian de la séance et écart médian à chaque minute (mesuré les jours où on a le prix acheteur)."""
    rows = [a for a in s.values() if np.isfinite(a[:, 5]).any()]
    if not rows:
        return {}
    x = np.concatenate(rows)
    x = x[np.isfinite(x[:, 5]) & (x[:, 5] > 0)]
    if not len(x):
        return {}
    med = float(np.median(x[:, 5] / x[:, 4]))
    par_minute = pd.Series(x[:, 5] / x[:, 4]).groupby(x[:, 0].astype(int)).median()
    return {"median": med, "facteur": (par_minute / med).clip(lower=1.0).to_dict()}


# ---------------------------------------------------------------------- l'agitation prévue (HAR)
def har(s: dict, fin_reglage: str = PERIODES["choix"][1]) -> pd.Series:
    """Prévision de l'agitation du JOUR (faite la veille au soir) : log de la variance réalisée (rendements de 5 min
    de la séance) expliqué par celle d'hier, de la semaine et du mois ; réglée sur 2015-2021 seulement. Rend, pour
    chaque jour, True si la prévision est dans le tiers supérieur des 252 prévisions précédentes."""
    jours = sorted(s)
    rv = []
    for j in jours:
        c = s[j][:, 4][::5]
        r = np.diff(np.log(c))
        rv.append(np.log(max(float(np.sum(r * r)), 1e-12)))
    rv = pd.Series(rv, index=pd.DatetimeIndex(jours))
    x = pd.DataFrame({"j": rv.shift(1), "s": rv.shift(1).rolling(5).mean(), "m": rv.shift(1).rolling(22).mean(),
                      "y": rv}).dropna()
    reg = x[x.index < pd.Timestamp(fin_reglage)]
    A = np.c_[np.ones(len(reg)), reg[["j", "s", "m"]].to_numpy()]
    b = np.linalg.lstsq(A, reg["y"].to_numpy(), rcond=None)[0]
    prev = pd.Series(np.c_[np.ones(len(x)), x[["j", "s", "m"]].to_numpy()] @ b, index=x.index)
    tiers = prev.rolling(252, min_periods=120).quantile(2 / 3).shift(1)
    return (prev >= tiers) & tiers.notna()


# ---------------------------------------------------------------------- un jour de trading
def _sortie(a: np.ndarray, i0: int, sens: int, entree: float, stop: float, fin: int):
    """Suit la position minute par minute depuis la minute i0 (entrée comprise) : (prix de sortie, touché ?)."""
    for i in range(i0, len(a)):
        m, o, h, l, c = a[i, :5]
        if m >= fin:
            return o, False                               # sortie à 15h55 (ouverture de la minute de 15h55)
        if (sens > 0 and l <= stop) or (sens < 0 and h >= stop):
            if i == i0:
                return stop, True                         # même minute que l'entrée : la perte (prudence)
            return (min(stop, o) if sens > 0 else max(stop, o)), True
    return a[-1, 4], False


def jour_orb(a: np.ndarray, n: int, frais: float, facteur: dict) -> dict | None:
    rng = a[a[:, 0] < n]
    if len(rng) < max(1, int(0.6 * n)):
        return None
    H, L = rng[:, 2].max(), rng[:, 3].min()
    if H <= L:
        return None
    fin = SORTIE[0] * 60 + SORTIE[1] - (OUVERTURE[0] * 60 + OUVERTURE[1])
    apres = np.flatnonzero((a[:, 0] >= n) & (a[:, 0] < fin))
    for i in apres:
        m, o, h, l, c = a[i, :5]
        haut, bas = h >= H, l <= L
        if not (haut or bas):
            continue
        if haut and bas:                                   # les deux dans la même minute : le plus proche de l'ouverture
            sens = 1 if abs(o - H) <= abs(o - L) else -1
        else:
            sens = 1 if haut else -1
        niveau = H if sens > 0 else L
        entree = max(niveau, o) if sens > 0 else min(niveau, o)
        risque = abs(entree - (L if sens > 0 else H))
        if risque <= 0:
            return None
        prix = entree
        # frais en prix : demi-fiche à l'entrée (x écart de l'ouverture) + demi à la sortie + glissements des stops
        f_ouv = facteur.get(int(m), 1.0)

        def resultat(s_: int) -> float:
            stop = entree - s_ * risque
            sortie, touche = _sortie(a, i, s_, entree, stop, fin)
            cout = prix * frais * (0.5 * f_ouv + 0.5 + 0.5 + (0.5 if touche else 0.0))
            return ((sortie - entree) * s_ - cout) / risque

        r, r_inv = resultat(sens), resultat(-sens)
        return {"minute": int(m), "sens": sens, "R": r, "R_inverse": r_inv, "risque_pct": risque / prix * 100,
                "range_pct": (H - L) / prix * 100}
    return None


def simuler(s: dict, n: int, frais: float, facteur: dict) -> pd.DataFrame:
    lignes = []
    for j, a in s.items():
        r = jour_orb(a, n, frais, facteur)
        if r:
            lignes.append({"jour": j, **r})
    return pd.DataFrame(lignes)


def note(t: pd.DataFrame, variantes: int = VARIANTES) -> dict:
    if len(t) < 20:
        return {"trades": len(t)}
    d = (t["R"] - t["R_inverse"]) / 2                     # elle moins l'espérance de son jumeau
    force = float(d.mean() / d.std(ddof=1) * math.sqrt(len(d)))
    r = t["R"].to_numpy()
    cumul = np.cumsum(r)
    pire_baisse = float((cumul - np.maximum.accumulate(np.r_[0, cumul])[1:]).min())
    serie, pire_serie = 0, 0
    for x in r:
        serie = serie + 1 if x < 0 else 0
        pire_serie = max(pire_serie, serie)
    return {"trades": int(len(t)), "R_moyen_apres_frais": float(r.mean()), "gagnants_pct": float((r > 0).mean() * 100),
            "avantage_sur_jumeau_R": float(d.mean()), "force": force, "seuil": seuil(variantes),
            "prouve": bool(force >= seuil(variantes) and r.mean() > 0),
            "pire_serie_pertes": int(pire_serie), "pire_baisse_R": pire_baisse}


def periode(t: pd.DataFrame, nom: str) -> pd.DataFrame:
    de, a = PERIODES[nom]
    return t[(t["jour"] >= pd.Timestamp(de)) & (t["jour"] < pd.Timestamp(a))]


def preparer(instrument: str, jusqua: str) -> tuple[dict, pd.Series, float, dict]:
    """`jusqua` : les séances au-delà ne sont même pas lues (la période cachée reste fermée avant la phase finale)."""
    s = {j: a for j, a in seances(minutes(instrument)).items() if j < pd.Timestamp(jusqua)}
    filtre = har(s)
    frais = fiche(INSTRUMENTS[instrument]).frais
    prof = profil_ecart(s) or {"facteur": {m: FACTEUR_OUVERTURE[instrument] for m in range(60)}}
    return s, filtre, frais, prof


def variantes(instrument: str, jusqua: str) -> dict:
    s, filtre, frais, prof = preparer(instrument, jusqua)
    facteur = prof.get("facteur", {})
    sortie = {}
    for n in N_CHOIX:
        t = simuler(s, n, frais, facteur)
        t["filtre"] = t["jour"].map(filtre).fillna(False).astype(bool)
        for f in FILTRES:
            sortie[(n, f)] = t[t["filtre"]] if f else t
    return {"trades": sortie, "frais": frais, "ecart": prof, "jours": len(s)}


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "choix"
    VIE.mkdir(parents=True, exist_ok=True)
    verrou = VIE / "cachee.json"
    if phase == "cachee" and verrou.exists():
        print("La période cachée a DÉJÀ été évaluée (une seule fois) : résultat dans", verrou)
        print(verrou.read_text(encoding="utf-8"))
        return
    choix_f = VIE / "choix.json"
    resultats = {}
    for instrument in (sys.argv[2:] or INSTRUMENTS):
        try:
            v = variantes(instrument, PERIODES[phase][1])
        except Exception as e:
            print(f"{instrument} : données indisponibles ({type(e).__name__}: {e})")
            continue
        print(f"{instrument} : {v['jours']} séances, frais aller-retour {v['frais'] * 100:.3f} %, écart médian "
              f"{v['ecart'].get('median', float('nan')) * 100:.4f} %", flush=True)
        if phase == "choix":
            notes = {f"N={n} {'filtré' if f else 'non filtré'}": note(periode(t, "choix"))
                     for (n, f), t in v["trades"].items()}
            meilleur = max(notes, key=lambda k: notes[k].get("force", -9))
            resultats[instrument] = {"variantes": notes, "choisie": meilleur}
            for k, x in notes.items():
                print(f"  {k:22s} {x.get('trades')} trades, {x.get('R_moyen_apres_frais', 0):+.3f} R, force "
                      f"{x.get('force', 0):+.2f}")
            print(f"  -> choisie : {meilleur}")
        else:
            choix = json.loads(choix_f.read_text(encoding="utf-8"))[instrument]["choisie"]
            n = int(choix.split()[0][2:])
            f = "non" not in choix
            t = periode(v["trades"][(n, f)], phase)
            resultats[instrument] = {"variante": choix, **note(t)}
            if phase == "cachee":
                resultats[instrument]["trades_detail"] = t.assign(jour=t["jour"].astype(str)).to_dict("records")
            x = resultats[instrument]
            print(f"  {choix} sur {phase} : {x.get('trades')} trades, {x.get('R_moyen_apres_frais', 0):+.3f} R après frais, "
                  f"force {x.get('force', 0):+.2f} (seuil {seuil():.1f})")
    sortie = verrou if phase == "cachee" else VIE / f"{phase}.json"
    resultats["_quand"] = datetime.now().isoformat(timespec="seconds")
    sortie.write_text(json.dumps(resultats, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"(enregistré : {sortie})")


if __name__ == "__main__":
    main()
