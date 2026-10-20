"""LES YEUX DU MONDE de l'arbre HYPERNOVA (18/10/2026) : le contexte géopolitique et la peur, comme un trader qui suit
l'actualité (chef de projet : son sens venait « de mes zones ET des tensions géopolitiques qui couraient »). Ce sont des
INFORMATIONS que l'IA voit, jamais des règles : elle apprend seule si et quand s'en servir.

Ce qu'elle voit (les mêmes pour tous les marchés, 36 valeurs, données de collapsar/donnees/monde.py) :
  pour chacune des 11 séries (GPR, GPR menaces, GPR actes, EPU, VIX, VIX 3 mois, VVIX, OVX, GVZ, GDELT noirceur, GDELT
  part des articles de guerre) :
    niveau : (log x - moyenne des 250 valeurs précédentes) / leur écart, / 2, borné à +-5
    saut   : même chose sur les 60 valeurs précédentes
    haut30 : 1 si la dernière valeur est un nouveau plus haut des 30 précédentes
  courbe de la peur : log(VIX / VIX 3 mois) x 5 (positif = peur immédiate plus forte que la peur à 3 mois)
  tension géopolitique : 1 si le GPR moyen des 7 derniers jours dépasse son centile 80 des 365 jours précédents
  monde absent : 1 si aucune série n'est connue à cet instant
Valeur inconnue (ou plus vieille que 10 jours) = 0.

Marché retourné (miroir) : TOUT est multiplié par -1 sauf « monde absent ». Raison : l'école apprend aussi sur des marchés
retournés ; sans ce retournement, « la peur monte -> l'or monte » sur l'or et « la peur monte -> l'or retourné baisse »
sur son miroir s'annuleraient et l'IA ne pourrait rien apprendre du sens que donne le monde.

SANS FUTUR : valeur datée du jour J utilisable à J+1 08h00 heure du serveur (donnees/monde.py) ; niveaux, sauts, plus
hauts et tension ne regardent que les valeurs précédentes. Testé : calcul coupé à t = calcul complet (tests/test_monde.py).
Rien n'est lu à partir de reglages.periodes.fin_donnees.

Activation : réglage `yeux.monde` (false par défaut : l'arbre actuel n'est pas touché) OU arbre greffé (fichier
`monde.json` dans son dossier de vie, écrit par la greffe : le cœur s'en aperçoit seul au démarrage). Les yeux du monde
viennent en DERNIER (après la foule et les notes du juge) : à greffer après elles.

GREFFE (non appliquée tant qu'on ne la lance pas) : arrêter le cœur (fichier ARRET), puis
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.monde greffer [--dossier <vie de l'arbre>]
Sauvegarde automatique, entrée du cerveau de chaque branche agrandie de 36 valeurs, poids des nouvelles entrées à ZÉRO
(décisions identiques au départ, prouvé par tests/test_monde.py), mémoire de l'optimiseur agrandie de même.
Retour arrière : `defaire`. Voir les dernières valeurs : `voir`.
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

from collapsar.donnees import monde as MW
from collapsar.ecole.precision.reglages import R, VIE

VERSION = 1
VIEUX_J = 10
NOMS = tuple(f"{s}_{k}" for s in MW.SERIES for k in ("niveau", "saut", "haut30")) + ("courbe_peur", "tension_gpr",
                                                                                       "monde_absent")
NM = len(NOMS)
SENS = np.array([n != "monde_absent" for n in NOMS], bool)
NEUTRE = np.zeros(NM, np.float32)
NEUTRE[NOMS.index("monde_absent")] = 1.0


# ============================================================================================== activation
def active() -> bool:
    return bool(getattr(R().yeux, "monde", False))


def activer(oui: bool = True):
    R().yeux.monde = bool(oui)


def activer_temporairement(oui: bool, f):
    ancien = active()
    activer(oui)
    try:
        return f()
    finally:
        activer(ancien)


def greffee(dossier: Path) -> bool:
    return (Path(dossier) / "monde.json").exists()


# ============================================================================================== calcul
def _asof(connu: np.ndarray, valeurs: np.ndarray, t_ns: np.ndarray) -> np.ndarray:
    if not len(connu):
        return np.full(len(t_ns), np.nan)
    i = np.searchsorted(connu, t_ns, side="right") - 1
    ok = i >= 0
    ii = np.clip(i, 0, None)
    ok &= (t_ns - connu[ii]) <= VIEUX_J * MW.JOUR_NS
    return np.where(ok, valeurs[ii], np.nan)


def valeurs_a(t_ns: np.ndarray, coupe_ns: int | None = None) -> np.ndarray:
    """[n, NM] : ce que voit l'IA à chaque instant (heure du serveur, ns), marché non retourné. `coupe_ns` (tests) :
    on fait comme si rien n'était publié à partir de cet instant."""
    t_ns = np.asarray(t_ns, np.int64)
    X = np.full((len(t_ns), NM), np.nan)
    idx = {n: i for i, n in enumerate(NOMS)}
    present = np.zeros(len(t_ns), bool)
    for s in MW.SERIES:
        tb = MW.tableau(s, coupe_ns)
        if not len(tb):
            continue
        c = tb["connu"].to_numpy(np.int64)
        niv = _asof(c, np.clip(tb["z250"].to_numpy(float), -10, 10) / 2, t_ns)
        X[:, idx[f"{s}_niveau"]] = niv
        X[:, idx[f"{s}_saut"]] = _asof(c, np.clip(tb["z60"].to_numpy(float), -10, 10) / 2, t_ns)
        X[:, idx[f"{s}_haut30"]] = _asof(c, tb["haut30"].to_numpy(float), t_ns)
        present |= np.isfinite(_asof(c, tb["v"].to_numpy(float), t_ns))
    v1, v3 = MW.tableau("vix", coupe_ns), MW.tableau("vix3m", coupe_ns)
    if len(v1) and len(v3):
        a = _asof(v1["connu"].to_numpy(np.int64), v1["v"].to_numpy(float), t_ns)
        b = _asof(v3["connu"].to_numpy(np.int64), v3["v"].to_numpy(float), t_ns)
        X[:, idx["courbe_peur"]] = np.log(a / b) * 5
    X[:, idx["tension_gpr"]] = MW.tension_a(t_ns, coupe_ns).astype(float)
    X[:, idx["monde_absent"]] = ~present
    X = np.clip(np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0), -10, 10).astype(np.float32)
    X[~present] = NEUTRE
    return X


def tenseurs(variantes: list[tuple[str, bool]], temps: pd.DatetimeIndex, dev) -> tuple[torch.Tensor, torch.Tensor]:
    """Pour un monde (univers.py) : MONDE [T, 2, NM] (0 = marché tel quel, 1 = retourné) et IDX [M] (0 / 1 selon que la
    colonne est retournée). `temps` = ouverture des bougies de 15 min (serveur) ; la décision a lieu à leur clôture."""
    dec = (pd.DatetimeIndex(temps) + pd.Timedelta(minutes=15)).as_unit("ns").asi8
    x = valeurs_a(dec)
    xm = x.copy()
    xm[:, SENS] *= -1
    F = np.stack([x, xm], 1).astype(np.float32)
    idx = [1 if mir else 0 for _, mir in variantes]
    return (torch.as_tensor(np.ascontiguousarray(F), device=dev), torch.as_tensor(np.asarray(idx, np.int64), device=dev))


# ============================================================================================== greffe
def _entree_avant_apres() -> tuple[int, int, int]:
    """(endroit de la greffe = taille des yeux sans le monde, taille d'entrée avant, après)."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import vue as V
    avant = activer_temporairement(False, V.taille_caracteristiques)
    return avant, avant + C.N_POS, avant + NM + C.N_POS


def _grandir(w: torch.Tensor, ou: int) -> torch.Tensor:
    z = torch.zeros(*w.shape[:-1], NM, dtype=w.dtype, device=w.device)
    return torch.cat([w[..., :ou], z, w[..., ou:]], -1)


def greffer_etat(etat: dict) -> tuple[dict, bool]:
    """NM colonnes à ZÉRO insérées dans la 1re couche des yeux du marché, juste avant la position (ordre des entrées :
    yeux, foule, notes du juge, MONDE, position) ; mémoire de l'optimiseur agrandie de même. Rend (état, changé)."""
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
    """LA GREFFE sur l'état d'un arbre ARRÊTÉ : sauvegarde complète, puis chaque branche (vivante, sa meilleure version,
    la cime) reçoit les yeux du monde avec des poids à zéro ; écrit monde.json (le cœur s'allume seul en mode monde au
    prochain démarrage). Les greffes déjà faites (foule, juge) sont allumées d'abord pour trouver le bon endroit."""
    import psutil
    from collapsar.ecole.precision import foule as FO
    from collapsar.ecole.precision import juge_trade as JT
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if greffee(dossier):
        raise SystemExit(f"{dossier} : déjà greffé (monde.json existe)")
    v = dossier / "coeur.verrou"
    if v.exists():
        try:
            pid = int(v.read_text())
            if psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower():
                raise SystemExit(f"le cœur bat encore (processus {pid}) : créer {dossier / 'ARRET'} et attendre sa fin")
        except ValueError:
            pass
    if FO.greffee(dossier):
        FO.activer()
    JT.allumer_si_greffe(dossier)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_monde_{stamp}"
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
    (dossier / "monde.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        from collapsar.arbre.journal import Journal
        Journal(dossier / "journal_croissance.jsonl").ecrire("greffe_monde", fichiers=faits, sauvegarde=str(sauve))
    except Exception:
        pass
    dire(f"greffe faite : {len(faits)} fichiers (entrée {f_avant} -> {f_apres}) ; monde.json écrit")
    return info


def defaire(dossier: Path | None = None, dire=print):
    """Retour arrière : remet la sauvegarde d'avant la greffe (arbre arrêté)."""
    dossier = Path(dossier) if dossier else VIE
    info = json.loads((dossier / "monde.json").read_text(encoding="utf-8"))
    sauve = Path(info["sauvegarde"])
    shutil.rmtree(dossier / "branches")
    shutil.copytree(sauve / "branches", dossier / "branches")
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (sauve / nom).exists():
            shutil.copy2(sauve / nom, dossier / nom)
    (dossier / "monde.json").unlink()
    dire(f"greffe du monde défaite : état remis depuis {sauve}")


# ============================================================================================== commandes
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("quoi", choices=["greffer", "defaire", "voir"])
    ap.add_argument("--dossier", default=None)
    a = ap.parse_args(argv)
    if a.quoi == "greffer":
        greffer(Path(a.dossier) if a.dossier else None)
    elif a.quoi == "defaire":
        defaire(Path(a.dossier) if a.dossier else None)
    else:
        t = pd.date_range(MW.FIN_DONNEES - pd.Timedelta(days=8), MW.FIN_DONNEES - pd.Timedelta(hours=1), freq="1D")
        x = valeurs_a(t.as_unit("ns").asi8)
        print(pd.DataFrame(x, columns=NOMS, index=t).T.round(2).to_string())


if __name__ == "__main__":
    main()
