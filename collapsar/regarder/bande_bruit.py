"""PISTE « CHASSEUR DE JOURNÉES DE TENDANCE » + « BOUCLIER D'AGITATION » (16/10/2026, rapport
reports/Recherche daytrading rentable.md, pistes 3 et 1).

Méthode publiée de la BANDE DE BRUIT (Zarattini, Aziz, Barbon 2024, « Beat the Market », S&P 500 2007-2024),
réglages du papier, AUCUN réglage choisi par nous :
- bruit(t) = moyenne sur les 14 séances précédentes de |prix à la minute t / ouverture - 1| ;
- bande haute = max(ouverture, clôture de la veille) x (1 + bruit(t)), bande basse = min(...) x (1 - bruit(t)) ;
- regard toutes les 30 min (10h00 ... 15h30, heure de New York) : au-dessus de la bande haute -> acheteur,
  au-dessous de la bande basse -> vendeur ;
- stop suiveur vérifié aux mêmes regards : sortie d'un achat si le prix repasse sous max(bande haute, prix moyen de
  la séance), d'une vente au-dessus de min(bande basse, prix moyen) ; tout est fermé à 16h00 (rien la nuit) ;
- BOUCLIER : levier du jour = min(4, cible / agitation journalière des 14 dernières séances).
Écart : le papier utilise le VWAP ; nos données à la minute n'ont pas de volume -> prix moyen de la séance (moyenne des
prix typiques), indiqué comme tel.
Frais : fiche FTMO du marché x 1,25 (glissement) par aller-retour, écart de l'ouverture majoré (orb.FACTEUR_OUVERTURE).
Juge : force = gain AVANT frais / écart type x racine(n) (le jumeau au sens tiré à pile ou face a une espérance de
-frais) ; résultat après frais ; challenge FTMO simulé (départ tous les 10 jours : +10 % puis +5 %, mort à -5 % sur
un jour ou -10 % au total) contre 20 jumeaux.
Corrections de l'audit du 16/10/2026 (collapsar/vie/audit/rapport.md) :
- défaut 2 : la force se calcule sur les gains JOURNALIERS du compte taillé (taille = cible / agitation), avant frais,
  jours sans trade compris (comme crypto_flux « force_jour ») ; l'ancienne force (rendement brut non pondéré) reste
  publiée sous « force_brute » ;
- défaut 3 : séances avec plus de 5 % de minutes manquantes écartées (orb.seances) ;
- défaut 6 : « réussis parmi les challenges terminés » et nombre d'inachevés publiés ;
- défaut 7 : années du calendrier (durée réelle de la période), plus 252 jours ;
- défaut 8 : la règle des -5 % du jour se juge au PIRE point de la journée (pertes latentes, plus bas / plus haut des
  minutes tenues), comme bitcoin_journee ;
- point 4 : résultats aussi à la taille du challenge (cible 2 %) et « plafond du tricheur » (sens connu d'avance).
Protocole : 2015-2021 puis 2022-2023 ; 2024-2026 (cachée) UNE fois si les deux premières sont positives (verrou).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.bande_bruit [cachee]
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
from collapsar.mains.frais_ftmo import MARGE_PRUDENCE
from collapsar.regarder import orb

VIE = dm.RACINE / "collapsar" / "vie" / "bande_bruit"
MARCHES = ("US500", "NAS100", "XAUUSD")
JOURS_BRUIT, LEVIER_MAX, REGARD = 14, 4.0, 30
MODELE_FRAIS = "fiche"                                   # "ftmo" : écarts mesurés sur le compte FTMO (mains/frais_ftmo.py)
CIBLES = (0.005, 0.01, 0.015, 0.02)                      # agitation journalière visée (taille), pour le challenge
CIBLE_CHALLENGE = 0.02                                   # taille du papier / du challenge (audit, point 4)
JOURS_AN_CAL = 365.25
PERIODES = {"2015-2021": ("2015-01-01", "2022-01-01"), "2022-2023": ("2022-01-01", "2024-01-01"),
            "2024-2026 (cachée)": ("2024-01-01", "2027-01-01")}


def matrice(s: dict):
    """Jours complets -> tableaux [jour, minute 0..389] d'ouverture/haut/bas/clôture (trous comblés vers l'avant)."""
    jours = sorted(s)
    C = np.full((len(jours), 390), np.nan)
    H, L, O = C.copy(), C.copy(), C.copy()
    for k, j in enumerate(jours):
        a = s[j]
        m = a[:, 0].astype(int)
        O[k, m], H[k, m], L[k, m], C[k, m] = a[:, 1], a[:, 2], a[:, 3], a[:, 4]
    for X in (O, H, L, C):
        X[:] = pd.DataFrame(X).T.ffill().bfill().T.to_numpy()
    return pd.DatetimeIndex(jours), O, H, L, C


def simuler(instrument: str, jusqua: str, facteur_frais: float = MARGE_PRUDENCE,     # 16/10 : 1,25 -> 1 (audit)
            manque_max: float = orb.MANQUE_MAX) -> pd.DataFrame:
    """Un trade par ligne : jour, sens, minutes d'entrée/sortie, rendement brut du prix, frais (part du prix), levier
    par unité de cible (levier / cible), agitation du jour, pire écart défavorable pendant le trade (achat / vente)."""
    s = {j: a for j, a in orb.seances(orb.minutes(instrument), manque_max).items() if j < pd.Timestamp(jusqua)}
    jours, O, H, L, C = matrice(s)
    frais = fiche(orb.INSTRUMENTS[instrument]).frais * facteur_frais
    if MODELE_FRAIS == "ftmo":                                  # écart FTMO mesuré, en points, ramené au prix du jour
        from collapsar.mains.frais_ftmo import frais as frais_ftmo
        frais = frais_ftmo(orb.INSTRUMENTS[instrument], O[:, 0])  # tableau par jour (x MARGE_PRUDENCE inclus)
    t = trades_matrice(jours, O, H, L, C, frais, orb.FACTEUR_OUVERTURE[instrument])
    t["marche"] = instrument
    return t


def trades_matrice(jours, O, H, L, C, frais, f_ouv: float = 1.0) -> pd.DataFrame:
    """Le moteur de la bande de bruit sur des séances déjà en matrices [jour, minute 0..389] (voir simuler)."""
    ouv = O[:, 0]
    veille = np.r_[np.nan, C[:-1, -1]]
    mouv = np.abs(C / ouv[:, None] - 1)
    bruit = pd.DataFrame(mouv).rolling(JOURS_BRUIT).mean().shift(1).to_numpy()
    r_jour = pd.Series(C[:, -1]).pct_change()
    agit = r_jour.rolling(JOURS_BRUIT).std().shift(1).to_numpy()
    typique = (H + L + C) / 3
    moyen = np.cumsum(typique, axis=1) / np.arange(1, 391)
    frais = np.broadcast_to(np.asarray(frais, float), ouv.shape)
    regards = list(range(REGARD - 1, 390, REGARD))           # clôture des minutes 9h59, 10h29 ... 15h59 (= 389)
    assert regards[-1] == 389                                 # sinon les trades tenus jusqu'à la clôture disparaissent
    lignes = []
    for k in range(len(jours)):
        if not (np.isfinite(bruit[k]).all() and np.isfinite(veille[k]) and np.isfinite(agit[k]) and agit[k] > 0):
            continue
        haut = max(ouv[k], veille[k]) * (1 + bruit[k])
        bas = min(ouv[k], veille[k]) * (1 - bruit[k])
        pos, entree, m_in = 0, 0.0, 0
        for m in regards:
            c = C[k, m]
            fin = m >= 389
            if pos != 0 and ((pos > 0 and c < max(haut[m], moyen[k, m])) or (pos < 0 and c > min(bas[m], moyen[k, m]))
                             or fin):
                # pire point pendant le trade : minutes tenues après la clôture d'entrée, jusqu'à la sortie comprise
                lo, hi = L[k, m_in + 1:m + 1].min(), H[k, m_in + 1:m + 1].max()
                lignes.append((jours[k], pos, m_in, m, (c / entree - 1) * pos, entree, agit[k], frais[k],
                               min(lo / entree - 1, 0.0), min(1 - hi / entree, 0.0)))
                pos = 0
            if pos == 0 and not fin:
                if c > haut[m]:
                    pos, entree, m_in = 1, c, m
                elif c < bas[m]:
                    pos, entree, m_in = -1, c, m
    t = pd.DataFrame(lignes, columns=["jour", "sens", "m_entree", "m_sortie", "brut", "prix", "agitation", "frais_base",
                                      "adv_achat", "adv_vente"])
    t["frais"] = t["frais_base"] * np.where(t["m_entree"] < 60, 0.5 * f_ouv + 0.5, 1.0)
    t["levier_par_cible"] = np.minimum(LEVIER_MAX / 0.02, 1.0 / t["agitation"])   # x cible ; plafond 4 à cible 2 %
    return t


def levier(t: pd.DataFrame, cible: float) -> np.ndarray:
    """Levier de chaque trade pour la cible donnée (bouclier : cible / agitation, plafond LEVIER_MAX)."""
    return np.minimum(LEVIER_MAX, cible * t["levier_par_cible"].to_numpy())


def signes_tricheur(t: pd.DataFrame) -> np.ndarray:
    """Le « tricheur » connaît d'avance le résultat : il garde le sens d'un trade gagnant et retourne un perdant."""
    return np.where(t["brut"].to_numpy() >= 0, 1, -1)


def journalier(t: pd.DataFrame, cible: float, signes: np.ndarray | None = None) -> pd.Series:
    """Gain du compte par jour (en part du compte), taille = levier du bouclier pour la cible donnée."""
    lev = levier(t, cible)
    brut = t["brut"].to_numpy() * (1 if signes is None else signes)
    g = lev * (brut - t["frais"].to_numpy())
    return pd.Series(g, index=t["jour"]).groupby(level=0).sum()


def journalier_pire(t: pd.DataFrame, cible: float, signes: np.ndarray | None = None) -> tuple[pd.Series, pd.Series]:
    """(gain du jour, pire point du jour) en part du compte (audit, défaut 8). Pire point d'un marché dans la journée =
    min(gains déjà réalisés ce jour-là sur ce marché + pire point latent du trade en cours, 0) ; plusieurs marchés : les
    pires points sont ADDITIONNÉS comme s'ils arrivaient au même instant (prudent)."""
    lev = levier(t, cible)
    sg = 1 if signes is None else np.asarray(signes)
    brut = t["brut"].to_numpy() * sg
    frais = t["frais"].to_numpy()
    g = lev * (brut - frais)
    sens_eff = t["sens"].to_numpy() * sg
    adv = np.where(sens_eff > 0, t["adv_achat"].to_numpy(), t["adv_vente"].to_numpy())
    pire = lev * (np.minimum(adv, 0.0) - frais)
    marche = t["marche"].to_numpy() if "marche" in t else np.zeros(len(t))
    d = pd.DataFrame({"jour": pd.DatetimeIndex(t["jour"]), "marche": marche, "m": t["m_entree"].to_numpy(), "g": g,
                      "p": pire}).sort_values(["jour", "marche", "m"], kind="stable")
    avant = d.groupby(["jour", "marche"])["g"].cumsum() - d["g"]
    d["w"] = np.minimum(avant + d["p"], 0.0)
    w = d.groupby(["jour", "marche"])["w"].min().groupby(level=0).sum()
    return d.groupby("jour")["g"].sum(), w


def challenge(g: pd.Series, pas: int = 10, w=None) -> dict:
    """Challenges FTMO simulés sur la suite de jours (jours sans trade = 0) : phase 1 +10 %, phase 2 +5 %, mort à -5 %
    sur un jour ou -10 % du départ de la phase. Sans `w` : jugé à la clôture du jour seulement. Avec `w` (pire point du
    jour, même index que g, voir journalier_pire) : jugé au PIRE point de la journée (audit, défaut 8).
    En plus du % sur tous les départs : % réussis parmi les challenges TERMINÉS et nombre d'inachevés (défaut 6 : FTMO
    n'a pas de limite de temps, un challenge coupé par la fin des données n'est ni réussi ni raté)."""
    x = np.asarray(g, float)
    y = x if w is None else np.minimum(np.asarray(w, float), x)
    res = {"reussis": 0, "morts": 0, "en_cours": 0, "jours_reussite": []}
    for d in range(0, len(x), pas):
        i, ok = d, True
        for but in (0.10, 0.05):
            v, fini = 0.0, False
            while i < len(x):
                pire = v + y[i]                                     # au pire point de la journée (= clôture sans w)
                v += x[i]
                i += 1
                if y[i - 1] <= -0.05 or pire <= -0.10 or v <= -0.10:
                    ok, fini = False, True
                    break
                if v >= but:
                    fini = True
                    break
            if not ok or not fini:
                break
        if not ok:
            res["morts"] += 1
        elif fini and i <= len(x):
            res["reussis"] += 1
            res["jours_reussite"].append(i - d)
        else:
            res["en_cours"] += 1
    n = max(1, res["reussis"] + res["morts"] + res["en_cours"])
    termines = res["reussis"] + res["morts"]
    return {"reussis_pct": 100 * res["reussis"] / n, "morts_pct": 100 * res["morts"] / n,
            "inacheves_pct": 100 * res["en_cours"] / n,
            "jours_median": float(np.median(res["jours_reussite"])) if res["jours_reussite"] else None,
            "reussis_parmi_termines_pct": 100 * res["reussis"] / termines if termines else None,
            "termines_n": int(termines), "inacheves_n": int(res["en_cours"])}


def annees(jours: pd.DatetimeIndex) -> float:
    """Durée réelle de la période en années du calendrier (du premier au dernier jour compris) ; défaut 7."""
    jours = pd.DatetimeIndex(jours)
    return ((jours[-1] - jours[0]).days + 1) / JOURS_AN_CAL


def force_jour(x: pd.Series) -> float:
    """Force = moyenne / écart type x racine(n) des gains journaliers (jours sans trade compris)."""
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else 0.0
    return float(x.mean() / sd * math.sqrt(len(x))) if sd > 0 else 0.0


def bilan(t: pd.DataFrame, tous_jours: pd.DatetimeIndex, cible: float = 0.01) -> dict:
    if len(t) < 20:
        return {"trades": len(t)}
    brut = t["brut"] * 1.0
    force_brute = float(brut.mean() / brut.std(ddof=1) * math.sqrt(len(t)))     # ancienne force (non pondérée)
    # défaut 2 : gains journaliers du compte TAILLÉ, avant frais (le jumeau au sens tiré au hasard vaut -frais)
    brut_jour = pd.Series(levier(t, cible) * brut.to_numpy(), index=t["jour"]).groupby(level=0).sum()
    force = force_jour(brut_jour.reindex(tous_jours, fill_value=0.0))
    g = journalier(t, cible).reindex(tous_jours, fill_value=0.0)
    an = annees(tous_jours)                                   # défaut 7 : années du calendrier, pas len / 252
    jours_par_an = len(g) / an
    courbe = g.cumsum()
    baisse = float((courbe - courbe.cummax()).min())
    rapport = float(g.mean() / g.std(ddof=1) * math.sqrt(jours_par_an)) if g.std() > 0 else 0.0
    g2 = journalier(t, CIBLE_CHALLENGE).reindex(tous_jours, fill_value=0.0)       # point 4 : taille du challenge
    c2 = g2.cumsum()
    tr = signes_tricheur(t)
    g_tr1 = journalier(t, cible, tr).sum()
    g_tr2 = journalier(t, CIBLE_CHALLENGE, tr).sum()
    return {"trades": int(len(t)), "gagnants_pct": float(((t["brut"] - t["frais"]) > 0).mean() * 100),
            "gain_brut_moyen_pct_prix": float(brut.mean() * 100), "frais_moyen_pct_prix": float(t["frais"].mean() * 100),
            "force_avant_frais": force, "force_brute": force_brute, "annees": an,
            "gain_pct_an_cible1": float(g.sum() / an * 100),
            "gain_pct_mois_cible1": float(g.sum() / an / 12 * 100), "rapport_gain_risque": rapport,
            "pire_jour_pct": float(g.min() * 100), "pire_baisse_pct": float(baisse * 100),
            "gain_pct_an_cible2": float(g2.sum() / an * 100), "gain_pct_mois_cible2": float(g2.sum() / an / 12 * 100),
            "pire_jour_pct_cible2": float(g2.min() * 100),
            "pire_baisse_pct_cible2": float((c2 - c2.cummax()).min() * 100),
            "plafond_tricheur_pct_mois_cible1": float(g_tr1 / an / 12 * 100),
            "plafond_tricheur_pct_mois_cible2": float(g_tr2 / an / 12 * 100)}


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "apprentissage"
    VIE.mkdir(parents=True, exist_ok=True)
    verrou = VIE / "cachee.json"
    if phase == "cachee" and verrou.exists():
        print("Période cachée DÉJÀ évaluée :", verrou.read_text(encoding="utf-8"))
        return
    jusqua = "2027-01-01" if phase == "cachee" else "2024-01-01"
    periodes = {k: v for k, v in PERIODES.items() if (phase == "cachee") == ("cachée" in k)}
    T = {m: simuler(m, jusqua) for m in MARCHES}
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "phase": phase, "periodes": {}}
    for p, (de, a) in periodes.items():
        P = {}
        jours_communs = None
        for m, t in T.items():
            tp = t[(t["jour"] >= de) & (t["jour"] < a)]
            jours =pd.bdate_range(de, min(pd.Timestamp(a), tp["jour"].max() + pd.Timedelta(days=1)) if len(tp) else a)
            jours_communs = jours if jours_communs is None else jours_communs.union(jours)
            P[m] = bilan(tp, jours)
        # compte unique : les 3 marchés ensemble, chacun à la cible / racine(3)
        tt = pd.concat([t[(t["jour"] >= de) & (t["jour"] < a)] for t in T.values()])
        chal = {}

        def chal_jours(cible_m, signes=None):
            """Challenge au pire point de la journée (défaut 8)."""
            g, w = journalier_pire(tt, cible_m, signes)
            return challenge(g.reindex(jours_communs, fill_value=0.0), w=w.reindex(jours_communs, fill_value=0.0))

        for cible in CIBLES:
            elle = chal_jours(cible / math.sqrt(len(T)))
            rng = np.random.default_rng(7)
            jum = [chal_jours(cible / math.sqrt(len(T)), rng.choice([-1, 1], len(tt))) for _ in range(20)]
            chal[f"{cible * 100:.1f} %"] = {"elle": elle, "jumeaux_reussis_pct": float(np.mean([j["reussis_pct"] for j in jum])),
                                             "jumeaux_morts_pct": float(np.mean([j["morts_pct"] for j in jum])),
                                             "tricheur": chal_jours(cible / math.sqrt(len(T)), signes_tricheur(tt))}
        P["compte_3_marches"] = bilan(tt.assign(levier_par_cible=tt["levier_par_cible"] / math.sqrt(len(T))),
                                      jours_communs)
        P["challenges"] = chal
        sortie["periodes"][p] = P
        print(f"\n=== {p} ===")
        for m, x in P.items():
            if m == "challenges":
                continue
            print(f"{m:18s} {x.get('trades')} trades | gagnants {x.get('gagnants_pct', 0):.0f} % | brut "
                  f"{x.get('gain_brut_moyen_pct_prix', 0):+.4f} % - frais {x.get('frais_moyen_pct_prix', 0):.4f} % | force "
                  f"{x.get('force_avant_frais', 0):+.2f} (brute {x.get('force_brute', 0):+.2f}) | "
                  f"{x.get('gain_pct_mois_cible1', 0):+.2f} %/mois (cible 1 %), {x.get('gain_pct_mois_cible2', 0):+.2f} "
                  f"(cible 2 %), tricheur {x.get('plafond_tricheur_pct_mois_cible1', 0):+.2f} / "
                  f"{x.get('plafond_tricheur_pct_mois_cible2', 0):+.2f} | "
                  f"rapport {x.get('rapport_gain_risque', 0):+.2f} | pire jour {x.get('pire_jour_pct', 0):.2f} % | "
                  f"baisse max {x.get('pire_baisse_pct', 0):.1f} % (cible 2 % : {x.get('pire_baisse_pct_cible2', 0):.1f} %)")
        for c, x in chal.items():
            e = x["elle"]
            rt = e["reussis_parmi_termines_pct"]
            print(f"  challenge cible {c}: réussis {e['reussis_pct']:.0f} % (jumeaux {x['jumeaux_reussis_pct']:.0f} %, "
                  f"tricheur {x['tricheur']['reussis_pct']:.0f} %), morts {e['morts_pct']:.0f} % (jumeaux "
                  f"{x['jumeaux_morts_pct']:.0f} %), inachevés {e['inacheves_pct']:.0f} % ({e['inacheves_n']}) | réussis "
                  f"parmi les {e['termines_n']} terminés : {'-' if rt is None else f'{rt:.0f} %'} | jours médians "
                  f"{e['jours_median']}")
    f = verrou if phase == "cachee" else VIE / "apprentissage.json"
    f.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    pd.concat(T.values()).to_csv(VIE / f"trades_{phase}.csv", index=False)
    print(f"(enregistré : {f})")


if __name__ == "__main__":
    main()
