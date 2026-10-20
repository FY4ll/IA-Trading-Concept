"""LES YEUX DE LA FOULE de l'arbre HYPERNOVA (17/10/2026) : ce que font les autres traders de crypto, vu sur les données
publiques des contrats perpétuels Binance (data/binance_futures, voir son LISEZMOI). Ce sont des INFORMATIONS que
l'IA voit, jamais des règles : elle apprend seule si et quand s'en servir.

Ce qu'elle voit pour chacune des 19 cryptos de l'école (19 valeurs, mises à l'échelle une fois pour toutes) :
  0 part des comptes acheteurs (tous les clients Binance), (part - 0,5) x 4
  1 sa place dans sa fourchette des 90 derniers jours (-1 = au plus bas, +1 = au plus haut)
  2 sa place dans sa fourchette des 30 derniers jours
  3 son rang parmi les 90 derniers jours (-1 = jamais aussi peu d'acheteurs, +1 = jamais autant : l'information C1)
  4 financement (taux ramené à 8 h), niveau : asinh(taux / 0,01 %) / 2
  5 financement, rang parmi les 180 derniers jours (extrême)
  6-8 positions ouvertes : variation sur 4 h, 24 h, 7 jours (logarithme, x 20 / x 10 / x 5)
  9-11 flux des preneurs (acheteurs pressés - vendeurs pressés, part du volume) sur 1 h, 4 h, 24 h (x 10 / x 15 / x 25)
  12-13 prime du perpétuel sur le comptant : dernière heure, moyenne des 8 dernières heures (asinh(prime / 0,05 %) / 2)
  14 drapeau « foule absente » (1 = aucune de ces informations : marché non crypto, ou avant le début des données)
  15-18 présence de chaque bloc : comptes et positions, financement, flux, prime (1 = connu à cet instant)
Valeurs inconnues = 0 (neutre). Bornes -10 / +10 comme les autres yeux.

Marché retourné (miroir) : tout ce qui a un sens est retourné (acheteurs <-> vendeurs, financement, flux, prime) ;
les variations des positions ouvertes et les drapeaux ne changent pas.

SANS FUTUR (règles de la piste crypto_flux, mesurées) : à l'instant t (UTC), seulement
- comptes / positions (fichiers « metrics », 5 min) : ligne datée T utilisée si T + 15 min <= t (retard de sécurité ;
  la même valeur paraît sur l'API 5 à 10 min après T) ; plus vieille que 1 h -> inconnue ;
- financement : taux dont l'heure de RÈGLEMENT est <= t (le règlement de 08h00:00,002 n'est connu qu'à 08h15) ;
  plus vieux que 24 h -> inconnu ;
- flux : bougies de 15 min du perpétuel CLOSES (ouverture + 15 min <= t) ;
- prime : bougie de 1 h close (ouverture + 1 h <= t).
Les fourchettes, rangs et variations ne regardent que le passé. Testé : calcul coupé à t = calcul complet
(tests/test_foule.py). Rien n'est lu à partir de reglages.periodes.fin_donnees (12 mois cachés).

Activation : réglage `yeux.foule` (false par défaut, l'arbre actuel n'est pas touché) OU arbre greffé (fichier
`foule.json` dans son dossier de vie, écrit par la greffe : le cœur s'en aperçoit seul au démarrage).

GREFFE (non appliquée tant qu'on ne la lance pas) : arrêter le cœur (fichier ARRET), puis
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.foule greffer [--dossier <vie de l'arbre>]
Sauvegarde automatique de l'arbre, entrée du cerveau de chaque branche agrandie de 19 valeurs, poids des nouvelles
entrées à ZÉRO (décisions identiques au départ), mémoire de l'optimiseur agrandie de même.
Autres commandes : `preparer` (calcule le cache des 19 cryptos), `voir SYM` (dernières valeurs).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from collapsar.donnees import marches as dm
from collapsar.ecole.precision.reglages import CACHE, R, VIE

FUT = dm.RACINE / "data" / "binance_futures"
VERSION = 1
QUINZE_NS = int(pd.Timedelta(minutes=15).value)
HEURE_NS = 4 * QUINZE_NS
JOUR = 96                                         # pas de 15 min par jour
RETARD_METRICS = pd.Timedelta(minutes=15)

NOMS = ("part_acheteurs", "place_90j", "place_30j", "rang_90j", "financement", "financement_rang_180j",
        "positions_4h", "positions_24h", "positions_7j", "flux_1h", "flux_4h", "flux_24h", "prime_1h", "prime_8h",
        "foule_absente", "comptes_presents", "financement_present", "flux_present", "prime_presente")
NF = len(NOMS)
# ce qui change de signe pour un marché retourné
SENS = np.array([1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0], bool)
NEUTRE = np.zeros(NF, np.float32)
NEUTRE[NOMS.index("foule_absente")] = 1.0


# ============================================================================================== activation
def active() -> bool:
    return bool(getattr(R().yeux, "foule", False))


def activer(oui: bool = True):
    """Allume (ou éteint) les yeux de la foule pour tout le processus (le réglage lu est mis en mémoire)."""
    R().yeux.foule = bool(oui)


def greffee(dossier: Path) -> bool:
    return (Path(dossier) / "foule.json").exists()


def cryptos() -> tuple[str, ...]:
    return tuple(R().marches.cryptos_binance)


# ============================================================================================== lecture brute
def _fin_utc_ns() -> int:
    """Rien n'est lu à partir de fin_donnees (heure du serveur = UTC + 2 ou 3 h) : on coupe 1 jour plus tôt en UTC."""
    return int((R().periodes.fin_donnees - pd.Timedelta(days=1)).value)


def lire_brut(sym: str) -> dict:
    """Les 4 fichiers d'un symbole, avec l'instant (UTC, ns) où chaque ligne devient CONNUE."""
    fin = _fin_utc_ns()
    ms = lambda x: np.asarray(x, np.int64) * 1_000_000
    out = {}
    f = FUT / "metrics" / f"{sym}.csv"
    if f.exists():
        m = pd.read_csv(f, usecols=["utc_ms", "sum_open_interest", "count_long_short_ratio"])
        connu = ms(m["utc_ms"]) + int(RETARD_METRICS.value)
        k = connu < fin
        out["metrics"] = {"connu": connu[k], "oi": m["sum_open_interest"].to_numpy(float)[k],
                          "ratio": m["count_long_short_ratio"].to_numpy(float)[k]}
    f = FUT / "funding" / f"{sym}.csv"
    if f.exists():
        fu = pd.read_csv(f)
        connu = ms(fu["utc_ms"])
        k = connu < fin
        taux = (fu["taux"] * 8.0 / fu["intervalle_h"].clip(lower=1)).to_numpy(float)
        out["funding"] = {"connu": connu[k], "taux": taux[k]}
    f = FUT / "klines15m" / f"{sym}.csv"
    if f.exists():
        kl = pd.read_csv(f, usecols=["utc_ms", "volume", "taker_buy_volume"])
        connu = ms(kl["utc_ms"]) + QUINZE_NS
        k = connu < fin
        out["klines"] = {"connu": connu[k], "v": kl["volume"].to_numpy(float)[k],
                         "tb": kl["taker_buy_volume"].to_numpy(float)[k]}
    f = FUT / "premium1h" / f"{sym}.csv"
    if f.exists():
        pr = pd.read_csv(f, usecols=["utc_ms", "close"])
        connu = ms(pr["utc_ms"]) + HEURE_NS
        k = connu < fin
        out["prime"] = {"connu": connu[k], "p": pr["close"].to_numpy(float)[k]}
    return out


def couper(brut: dict, t_ns: int) -> dict:
    """Ce qui était connu à l'instant t (pour les tests « sans futur »)."""
    return {k: {c: v[d["connu"] <= t_ns] for c, v in d.items()} for k, d in brut.items()}


# ============================================================================================== calcul
def _asof(connu: np.ndarray, valeurs: np.ndarray, grille: np.ndarray, tolerance_ns: int) -> np.ndarray:
    """Dernière valeur CONNUE (finie, > 0 si demandé avant) à chaque instant de la grille ; NaN si trop vieille."""
    if not len(connu):
        return np.full(len(grille), np.nan)
    o = np.argsort(connu, kind="stable")
    connu, valeurs = connu[o], valeurs[o]
    i = np.searchsorted(connu, grille, side="right") - 1
    ok = i >= 0
    ii = np.clip(i, 0, None)
    ok &= (grille - connu[ii]) <= tolerance_ns
    return np.where(ok, valeurs[ii], np.nan)


def _place(x: pd.Series, w: int) -> np.ndarray:
    lo = x.rolling(w, min_periods=w // 3).min()
    hi = x.rolling(w, min_periods=w // 3).max()
    e = (hi - lo).to_numpy()
    p = np.where(e > 0, 2 * (x.to_numpy() - lo.to_numpy()) / np.where(e > 0, e, 1.0) - 1, 0.0)
    return np.where(np.isfinite(lo.to_numpy()) & np.isfinite(x.to_numpy()), p, np.nan)


def _rang(x: pd.Series, w: int) -> np.ndarray:
    return 2 * x.rolling(w, min_periods=w // 3).rank(pct=True).to_numpy() - 1


def calculer(brut: dict) -> tuple[np.ndarray, np.ndarray]:
    """(grille UTC ns tous les 15 min, valeurs [N, 19] float32) : ce qui est connu à chaque instant de la grille."""
    debuts = [d["connu"].min() for d in brut.values() if len(d["connu"])]
    fins = [d["connu"].max() for d in brut.values() if len(d["connu"])]
    if not debuts:
        return np.zeros(0, np.int64), np.zeros((0, NF), np.float32)
    g0 = (min(debuts) + QUINZE_NS - 1) // QUINZE_NS * QUINZE_NS
    g1 = max(fins) // QUINZE_NS * QUINZE_NS
    grille = np.arange(g0, g1 + 1, QUINZE_NS, dtype=np.int64)
    N = len(grille)
    X = np.full((N, NF), np.nan)
    idx = {n: i for i, n in enumerate(NOMS)}
    pres = {k: np.zeros(N, bool) for k in ("metrics", "funding", "klines", "prime")}
    if "metrics" in brut:
        m = brut["metrics"]
        okr = np.isfinite(m["ratio"]) & (m["ratio"] > 0)
        r = _asof(m["connu"][okr], m["ratio"][okr], grille, HEURE_NS)
        part = pd.Series(r / (1 + r))
        X[:, idx["part_acheteurs"]] = (part.to_numpy() - 0.5) * 4
        X[:, idx["place_90j"]] = _place(part, 90 * JOUR)
        X[:, idx["place_30j"]] = _place(part, 30 * JOUR)
        X[:, idx["rang_90j"]] = _rang(part, 90 * JOUR)
        oko = np.isfinite(m["oi"]) & (m["oi"] > 0)
        lo = pd.Series(np.log(_asof(m["connu"][oko], m["oi"][oko], grille, HEURE_NS)))
        for nom, pas, k in (("positions_4h", 16, 20.0), ("positions_24h", JOUR, 10.0), ("positions_7j", 7 * JOUR, 5.0)):
            X[:, idx[nom]] = (lo - lo.shift(pas)).to_numpy() * k
        pres["metrics"] = np.isfinite(r) | np.isfinite(lo.to_numpy())
    if "funding" in brut:
        f = brut["funding"]
        okf = np.isfinite(f["taux"])
        t = pd.Series(_asof(f["connu"][okf], f["taux"][okf], grille, 24 * HEURE_NS))
        X[:, idx["financement"]] = np.arcsinh(t.to_numpy() / 1e-4) / 2
        X[:, idx["financement_rang_180j"]] = _rang(t, 180 * JOUR)
        pres["funding"] = np.isfinite(t.to_numpy())
    if "klines" in brut:
        k = brut["klines"]
        i = np.searchsorted(grille, k["connu"])                         # bougie close exactement à cet instant
        ok = (i < N) & (grille[np.clip(i, 0, N - 1)] == k["connu"])
        v, tb = np.zeros(N), np.zeros(N)
        np.add.at(v, i[ok], k["v"][ok])
        np.add.at(tb, i[ok], k["tb"][ok])
        connue = np.zeros(N, bool)
        connue[i[ok]] = True
        V, TB, C = pd.Series(v), pd.Series(tb), pd.Series(connue.astype(float))
        for nom, w, kk in (("flux_1h", 4, 10.0), ("flux_4h", 16, 15.0), ("flux_24h", JOUR, 25.0)):
            sv, st = V.rolling(w, min_periods=1).sum().to_numpy(), TB.rolling(w, min_periods=1).sum().to_numpy()
            plein = C.rolling(w, min_periods=1).sum().to_numpy() >= 0.75 * w
            X[:, idx[nom]] = np.where((sv > 0) & plein, (st / np.where(sv > 0, sv, 1.0) - 0.5) * kk, np.nan)
        pres["klines"] = np.isfinite(X[:, idx["flux_1h"]])
    if "prime" in brut:
        p = brut["prime"]
        okp = np.isfinite(p["p"])
        # série horaire des primes connues (sur la grille : à chaque heure pleine, la bougie close à cet instant)
        x1 = _asof(p["connu"][okp], p["p"][okp], grille, HEURE_NS)
        X[:, idx["prime_1h"]] = np.arcsinh(x1 / 5e-4) / 2
        heure = (grille % HEURE_NS) == 0
        hx = pd.Series(np.where(heure, x1, np.nan))
        h8 = hx[heure].rolling(8, min_periods=6).mean()
        m8 = pd.Series(np.nan, index=hx.index)
        m8[heure] = h8.to_numpy()
        m8 = m8.ffill(limit=3).to_numpy()
        X[:, idx["prime_8h"]] = np.where(np.isfinite(x1), np.arcsinh(m8 / 5e-4) / 2, np.nan)
        pres["prime"] = np.isfinite(x1)
    for nom, k in (("comptes_presents", "metrics"), ("financement_present", "funding"), ("flux_present", "klines"),
                   ("prime_presente", "prime")):
        X[:, idx[nom]] = pres[k]
    X[:, idx["foule_absente"]] = ~(pres["metrics"] | pres["funding"] | pres["klines"] | pres["prime"])
    X = np.clip(np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0), -10, 10).astype(np.float32)
    return grille, X


# ============================================================================================== cache
def fichier_cache(sym: str) -> Path:
    return CACHE / "foule" / f"{sym}_v{VERSION}_{R().periodes.fin_donnees:%Y%m%d}.npz"


def table(sym: str, forcer: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """(grille UTC ns, valeurs [N, 19]) d'un symbole, calculées une fois et rangées sur le disque."""
    f = fichier_cache(sym)
    if f.exists() and not forcer:
        z = np.load(f)
        return z["grille"], z["x"]
    g, x = calculer(lire_brut(sym))
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.stem + f"_{os.getpid()}.tmp.npz")
    np.savez(tmp, grille=g, x=x)
    os.replace(tmp, f)
    return g, x


def preparer_tout(dire=print):
    for s in cryptos():
        deja = fichier_cache(s).exists()
        g, x = table(s)
        if not deja:
            debut = pd.Timestamp(int(g[0])) if len(g) else None
            dire(f"foule de {s} prête ({len(g)} instants depuis {debut})")


def serveur_vers_utc_ns(t_serveur) -> np.ndarray:
    """Heure du serveur (New York + 7 h) -> UTC (ns). Heure répétée de novembre ou inexistante : l'instant UTC le PLUS
    TÔT (on suppose en savoir moins : jamais de futur)."""
    ny = pd.DatetimeIndex(np.asarray(pd.DatetimeIndex(t_serveur), "datetime64[ns]")) - pd.Timedelta(hours=7)
    loc = ny.tz_localize("America/New_York", ambiguous=np.ones(len(ny), bool), nonexistent="shift_backward")
    return loc.tz_convert("UTC").tz_localize(None).as_unit("ns").asi8.astype(np.int64)   # toujours en ns


def valeurs_a(sym: str, miroir: bool, decisions_utc_ns: np.ndarray) -> np.ndarray:
    """[n, 19] : ce que voit l'IA à chaque instant de décision (UTC, ns)."""
    g, x = table(sym)
    out = np.broadcast_to(NEUTRE, (len(decisions_utc_ns), NF)).copy()
    if not len(g):
        return out
    i = np.searchsorted(g, decisions_utc_ns, side="right") - 1
    ok = (i >= 0) & (decisions_utc_ns - g[np.clip(i, 0, None)] <= HEURE_NS)
    out[ok] = x[i[ok]]
    if miroir:
        out[:, SENS] *= -1
    return out


def tenseurs(variantes: list[tuple[str, bool]], temps: pd.DatetimeIndex, dev) -> tuple[torch.Tensor, torch.Tensor]:
    """Pour un monde (univers.py) : FOULE [T, Mc + 1, 19] (une place par crypto du monde + une place neutre) et
    IDX [M] (place de chaque colonne). `temps` = ouverture des bougies de 15 min (heure du serveur) ; la décision a
    lieu à leur clôture."""
    dec = serveur_vers_utc_ns(pd.DatetimeIndex(temps) + pd.Timedelta(minutes=15))
    cr = set(cryptos())
    places, idx = [], []
    for nom, mir in variantes:
        if nom in cr:
            idx.append(len(places))
            places.append(valeurs_a(nom, mir, dec))
        else:
            idx.append(-1)
    neutre = np.broadcast_to(NEUTRE, (len(dec), NF))
    idx = [len(places) if i < 0 else i for i in idx]
    F = np.stack(places + [neutre], 1).astype(np.float32)
    return (torch.as_tensor(np.ascontiguousarray(F), device=dev),
            torch.as_tensor(np.asarray(idx, np.int64), device=dev))


# ============================================================================================== greffe
def _entree_avant_apres() -> tuple[int, int, int]:
    """(colonnes des yeux sans la foule = endroit de la greffe, taille d'entrée avant, après)."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import vue as V
    avant = activer_temporairement(False, V.taille_caracteristiques)
    return avant, avant + C.N_POS, avant + NF + C.N_POS


def activer_temporairement(oui: bool, f):
    ancien = active()
    activer(oui)
    try:
        return f()
    finally:
        activer(ancien)


def _grandir(w: torch.Tensor, ou: int) -> torch.Tensor:
    z = torch.zeros(*w.shape[:-1], NF, dtype=w.dtype, device=w.device)
    return torch.cat([w[..., :ou], z, w[..., ou:]], -1)


def greffer_etat(etat: dict) -> tuple[dict, bool]:
    """Agrandit un fichier de branche ({"cerveau", "opt"?, ...}) : 19 colonnes à ZÉRO insérées dans la 1re couche des
    yeux du marché, juste avant la description de la position (ordre des entrées : yeux, foule, position).
    Rend (état, changé)."""
    from collapsar.ecole.precision import cerveau as C
    ou, f_avant, f_apres = _entree_avant_apres()
    cle = "marche.0.weight"
    w = etat["cerveau"][cle]
    if w.shape[1] == f_apres:
        return etat, False
    if w.shape[1] != f_avant:
        raise ValueError(f"entrée du cerveau inattendue : {w.shape[1]} (attendu {f_avant} ou {f_apres})")
    etat = dict(etat)
    etat["cerveau"] = dict(etat["cerveau"])
    etat["cerveau"][cle] = _grandir(w, ou)
    opt = etat.get("opt")
    if opt:
        noms = [n for n, _ in C.Cerveau().named_parameters()]
        k = noms.index(cle)
        pid = opt["param_groups"][0]["params"][k]
        st = opt["state"].get(pid)
        if st:
            st = dict(st)
            for c in ("exp_avg", "exp_avg_sq"):
                if c in st and st[c].shape == w.shape:
                    st[c] = _grandir(st[c], ou)
            etat["opt"] = {**opt, "state": {**opt["state"], pid: st}}
    return etat, True


def greffer(dossier: Path | None = None, dire=print) -> dict:
    """LA GREFFE sur l'état d'un arbre arrêté : sauvegarde complète, puis chaque branche (vivante, sa meilleure
    version, la cime) reçoit les yeux de la foule avec des poids à zéro ; écrit foule.json (le cœur s'allume seul en
    mode foule au prochain démarrage)."""
    import psutil
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if greffee(dossier):
        raise SystemExit(f"{dossier} : déjà greffé (foule.json existe)")
    v = dossier / "coeur.verrou"
    if v.exists():
        try:
            pid = int(v.read_text())
            if psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower():
                raise SystemExit(f"le cœur bat encore (processus {pid}) : créer {dossier / 'ARRET'} et attendre sa fin")
        except ValueError:
            pass
    preparer_tout(dire)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_foule_{stamp}"
    sauve.mkdir(parents=True)
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (dossier / nom).exists():
            shutil.copy2(dossier / nom, sauve / nom)
    shutil.copytree(dossier / "branches", sauve / "branches")
    dire(f"sauvegarde de l'arbre : {sauve}")
    fichiers = sorted((dossier / "branches").glob("*.pt")) + ([dossier / "cime.pt"] if (dossier / "cime.pt").exists() else [])
    faits = []
    for f in fichiers:
        e = torch.load(f, map_location="cpu", weights_only=False)
        e2, change = greffer_etat(e)
        if change:
            tmp = f.with_suffix(".pt.tmp")
            torch.save(e2, tmp)
            os.replace(tmp, f)
            faits.append(f.name)
    ou, f_avant, f_apres = _entree_avant_apres()
    info = {"date": datetime.now().isoformat(timespec="seconds"), "version": VERSION, "valeurs": list(NOMS),
            "entree_avant": f_avant, "entree_apres": f_apres, "insertion": ou, "fichiers": faits,
            "sauvegarde": str(sauve)}
    (dossier / "foule.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        from collapsar.arbre.journal import Journal
        Journal(dossier / "journal_croissance.jsonl").ecrire("greffe_foule", fichiers=faits, sauvegarde=str(sauve))
    except Exception:
        pass
    dire(f"greffe faite : {len(faits)} fichiers (entrée {f_avant} -> {f_apres}) ; foule.json écrit")
    return info


def defaire(dossier: Path | None = None, dire=print):
    """Retour arrière : remet la sauvegarde d'avant la greffe (arbre arrêté)."""
    dossier = Path(dossier) if dossier else VIE
    info = json.loads((dossier / "foule.json").read_text(encoding="utf-8"))
    sauve = Path(info["sauvegarde"])
    shutil.rmtree(dossier / "branches")
    shutil.copytree(sauve / "branches", dossier / "branches")
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (sauve / nom).exists():
            shutil.copy2(sauve / nom, dossier / nom)
    (dossier / "foule.json").unlink()
    dire(f"greffe défaite : état remis depuis {sauve}")


# ============================================================================================== commandes
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("quoi", choices=["preparer", "greffer", "defaire", "voir"])
    ap.add_argument("sym", nargs="?", default="BTCUSDT")
    ap.add_argument("--dossier", default=None)
    a = ap.parse_args(argv)
    if a.quoi == "preparer":
        preparer_tout()
    elif a.quoi == "greffer":
        greffer(Path(a.dossier) if a.dossier else None)
    elif a.quoi == "defaire":
        defaire(Path(a.dossier) if a.dossier else None)
    else:
        g, x = table(a.sym)
        d = pd.DataFrame(x[-8:], columns=NOMS, index=pd.to_datetime(g[-8:]))
        print(d.T.round(3).to_string())


if __name__ == "__main__":
    main()
