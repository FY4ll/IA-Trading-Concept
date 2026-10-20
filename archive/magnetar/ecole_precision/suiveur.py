"""LE STOP SUIVEUR DERRIÈRE LA STRUCTURE (18/10/2026, ordre du chef de projet pour l'arbre de l'or MAGNETAR :
« les gros mouvements, pas des miettes »). Un NOUVEAU GESTE de ses mains, un CHOIX libre de l'IA (jamais imposé) :
à l'ouverture d'un trade elle choisit aussi
  - aucun stop suiveur (comme avant), ou
  - un stop suiveur d'une unité (réglage `mains.suiveur_unites`, ex. journalier / 4 h / 1 h / 15 min), qui commence DÈS
    L'ENTRÉE ou seulement APRÈS L'OBJECTIF 1 : le stop est remonté derrière chaque nouveau creux confirmé (achat) /
    descendu derrière chaque nouveau sommet confirmé (vente) de cette unité, + la même petite marge que son stop de
    départ (0 à 0,5 agitation, déjà choisie par elle), jamais reculé, jamais au-delà du prix (simulateur.py) ;
  - et la destination peut alors être « laisser courir » (choix qui existait déjà) ; un PENCHANT appris pour « laisser
    courir » s'ajoute à la note de cette destination (à zéro au départ : rien ne change).
Sommets / creux : ceux que ses yeux voient déjà (structure.py, fractal 2 confirmé 2 bougies plus tard), connus à la
clôture de la bougie précédente : rien du futur.

Allumé SEULEMENT par le réglage `mains.suiveur: true` (reglages_or.yaml) ou un arbre greffé (fichier `suiveur.json` dans
son dossier de vie). HYPERNOVA (reglages.yaml) : éteint, rien ne change (empreinte prouvée par tests/test_suiveur.py).

GREFFE SANS PERTE (arbre arrêté) :  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.arbre_or --greffer-suiveur
- sauvegarde complète de son dossier de vie (vie/arbre_or/sauvegardes/avant_suiveur_<date>/) ;
- les têtes de décision de chaque branche (vivante, sa meilleure version, la cime) reçoivent une TÊTE DE PLUS (le
  suiveur et le penchant « laisser courir »), poids à ZÉRO, AUCUNE ancienne valeur modifiée ; « aucun suiveur » garde
  la plus grande part ; les options de suiveur ont ensemble une probabilité de départ faible mais non nulle (réglage
  `mains.suiveur_depart_pct`, 10 %) pour être essayées (choix : non nulle plutôt que neutre, sinon l'apprentissage par
  essais et erreurs ne la découvrirait jamais) ; TOUS les autres gestes gardent exactement les mêmes probabilités et, à
  graine égale, les mêmes tirages (le suiveur est tiré en dernier) ; l'optimiseur reçoit la nouvelle tête à la fin ;
- la branche la plus faible (hors cime et hors témoin neuf) est archivée et remplacée par une branche « laisse_courir »
  partant de la cime greffée, avec ses PENCHANTS de départ : ne rien encaisser à l'objectif 1, stop suiveur, laisser
  courir (ajoutés aux biais appris : elle reste libre d'apprendre autre chose).
Retour arrière : `--defaire-suiveur`.
"""
from __future__ import annotations

import json
import math
import os
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

from collapsar.ecole.precision.reglages import R, UNITES, VIE

VERSION = 1
NOMS_U = {"D1": "journalier", "H4": "4 h", "H1": "1 h", "M30": "30 min", "M15": "15 min", "M5": "5 min", "M3": "3 min"}
MOMENTS = ("entree", "tp1")                    # dès l'entrée / après l'objectif 1
# tempérament « laisse_courir » : penchants AJOUTÉS aux biais appris de la cime (logits). Calibrés le 18/10 sur une copie
# de la cime de MAGNETAR (examen 2023 allégé) : +3/+3 -> rien encaissé à l'objectif 1 dans 69 % des trades, laisser courir
# 47 % ; +4/+5 -> 82 % et 87 % (retenu) ; suiveur choisi dans 89 % des trades.
LAISSE_COURIR = {"nom": "laisse_courir", "penchants": {"part0": 4.0, "suiveur_pct": 90.0, "courir": 5.0}}


# ============================================================================================== activation
def active() -> bool:
    return bool(getattr(R().mains, "suiveur", False))


def activer(oui: bool = True):
    R().mains.suiveur = bool(oui)


def activer_temporairement(oui: bool, f):
    ancien = active()
    activer(oui)
    try:
        return f()
    finally:
        activer(ancien)


def greffee(dossier: Path) -> bool:
    return (Path(dossier) / "suiveur.json").exists()


def unites() -> tuple[str, ...]:
    u = tuple(getattr(R().mains, "suiveur_unites", ("H4", "H1", "M15")))
    assert all(x in UNITES for x in u), u
    return u


def n_options() -> int:
    """Nombre de sorties de la tête du suiveur : aucun + (unité x moment) ; 0 si éteint."""
    return 1 + len(MOMENTS) * len(unites()) if active() else 0


def n_sorties() -> int:
    """Sorties ajoutées aux têtes du cerveau : options du suiveur + penchant « laisser courir » ; 0 si éteint."""
    return n_options() + 1 if active() else 0


def option(k: int) -> tuple[int, bool]:
    """Option k de la tête -> (place de l'unité dans les tableaux du monde, -1 = aucun ; après l'objectif 1 ?)."""
    if k <= 0:
        return -1, False
    NS = len(unites())
    return (k - 1) % NS, (k - 1) // NS == 1


def biais_options(total_pct: float) -> float:
    """Biais de chaque option de suiveur (poids à zéro, « aucun » à 0) pour que toutes ensemble pèsent total_pct %."""
    k = n_options() - 1
    p = min(max(total_pct / 100, 1e-6), 1 - 1e-6)
    return math.log(p / ((1 - p) * k))


def biais_depart() -> float:
    return biais_options(float(getattr(R().mains, "suiveur_depart_pct", 10.0)))


# ============================================================================================== suiveur après +1R
# STOP SUIVEUR QUI BOUGE APRÈS +1R (19/10/2026, accord du chef de projet, sur UNE branche) : constat (rapport de la
# génération 200) : le suiveur est choisi dans 80-90 % des trades mais réglé à 60 % sur le JOURNALIER et remonté dans 2 %
# des trades seulement. Nouvelles OPTIONS de ses mains (choix libre, jamais imposé) : un suiveur qui ne s'active qu'APRÈS
# +1R atteint (avant : le stop d'origine, rien ne bouge), puis
#   - derrière les nouveaux creux (achat) / sommets (vente) confirmés d'une unité (réglage `mains.suiveur_1r_unites`,
#     1 h et 4 h), + la marge de son stop, comme le suiveur d'avant ;
#   - ou (variante par agitation, réglage `mains.suiveur_1r_agitations`, 1,0) à X agitations sous le plus haut atteint
#     (achat) / au-dessus du plus bas (vente) ;
# jamais reculé (simulateur.py). Une tête de plus du cerveau (`suiv1r`, après la tête du suiveur), poids à ZÉRO : les
# autres gestes ne changent pas ; un PENCHANT de départ (biais) vers ces options, pour qu'elle les essaie.
# Allumé par le réglage `mains.suiveur_1r: true` (reglages_or.yaml) ; seule une branche au tempérament « suiveur_1r »
# (cerveau construit avec suiveur_1r=True) peut les choisir.
def active_1r() -> bool:
    return active() and bool(getattr(R().mains, "suiveur_1r", False))


def options_1r() -> list[tuple[int, float, str]]:
    """Les options après +1R : (place de l'unité dans les tableaux du monde, agitations (0 = creux / sommets), nom)."""
    us = unites()
    out = []
    for u in getattr(R().mains, "suiveur_1r_unites", ("H1", "H4")):
        assert u in us, (u, us)
        out.append((us.index(u), 0.0, f"{NOMS_U[u]} après +1R"))
    for k in getattr(R().mains, "suiveur_1r_agitations", (1.0,)):
        assert float(k) > 0, k
        out.append((0, float(k), f"{float(k):g} agitation sous le plus haut, après +1R"))
    return out


def n_options_1r() -> int:
    return len(options_1r()) if active() else 0


def part_1r(net, U, n: int = 1024, graine: int = 0) -> float:
    """Part des ouvertures où la branche choisit une option après +1R (un regard de n comptes au hasard dans le monde U,
    même graine à chaque appel : hasard commun, la part monte avec le biais)."""
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import journal_trading as JN
    from collapsar.ecole.precision.cerveau import ACHAT_M, VENTE_L
    rng = np.random.default_rng(graine)
    tb = JEU.Table(U, n, 1)
    JN.equiper(tb, net, "ecole")
    ok = np.flatnonzero(U.premier < U.T - 96 * 70)
    cols = rng.choice(ok, n)[:, None]
    dep = np.asarray([rng.integers(U.premier[c0], U.T - 96 * 65) for c0 in cols[:, 0]], np.int64)
    tb.demarrer(np.ones(n, bool), cols, dep)
    torch.manual_seed(graine)
    with torch.no_grad():
        (choix, *_), _ = tb.regarder(net, np.arange(n))
    g = choix["geste"]
    ouvre = (g >= ACHAT_M) & (g <= VENTE_L)
    if not bool(ouvre.any()):
        return float("nan")
    return float((choix["suiveur"][ouvre] >= net.n_suiv).float().mean() * 100)


def calibrer_1r(net, U, cible_pct: float, n: int = 1024, graine: int = 0) -> tuple[float, float]:
    """Le biais de départ des options après +1R (le même pour toutes, poids à zéro) pour qu'ensemble elles soient
    choisies dans `cible_pct` % des ouvertures (mesuré sur de vrais regards de la branche, monde U). Rend (biais, part)."""
    assert net.n_suiv1r > 0
    lo, hi = -15.0, 15.0
    for _ in range(30):
        b = (lo + hi) / 2
        with torch.no_grad():
            net.suiv1r.bias[:] = b
        p = part_1r(net, U, n, graine)
        if p < cible_pct:
            lo = b
        else:
            hi = b
    b = (lo + hi) / 2
    with torch.no_grad():
        net.suiv1r.bias[:] = b
    return b, part_1r(net, U, n, graine)


def nom_option_1r(ag: float, u: int) -> str:
    """Texte d'une option après +1R (journal) : `ag` = distance par agitation EN PRIX (0 = creux / sommets)."""
    if ag and ag > 0:
        return f"agitation ({ag:.2f} sous le plus haut), après +1R"
    us = unites() if active() else ("D1", "H4", "H1", "M15")
    return f"{NOMS_U.get(us[int(u)], us[int(u)]) if 0 <= int(u) < len(us) else u} après +1R"


# ============================================================================================== le monde
def numeros(sw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Numéro du dernier creux / sommet connu à chaque ligne de l'unité (+1 à chaque nouveau), comme
    regarder/pistes/mouvements.suiveur_lignes."""
    sw = np.asarray(sw, np.float64)
    ch = lambda a, b: (a != b) & ~(np.isnan(a) & np.isnan(b))
    if len(sw) < 2:
        return np.zeros(len(sw), np.int64), np.zeros(len(sw), np.int64)
    nc = np.r_[0, np.cumsum(ch(sw[1:, 2], sw[:-1, 2]) | ch(sw[1:, 3], sw[:-1, 3]))].astype(np.int64)
    ns = np.r_[0, np.cumsum(ch(sw[1:, 0], sw[:-1, 0]) | ch(sw[1:, 1], sw[:-1, 1]))].astype(np.int64)
    return nc, ns


def tableaux(bruts: dict, cols: list[str], tranches: list[tuple[int, int]], loc: np.ndarray, T: int):
    """Pour un monde (univers.py) : SW_V [T, M, NS, 2] (dernier creux, dernier sommet confirmés de chaque unité du
    suiveur, connus à la clôture de chaque bougie), SW_ID [T, M, NS, 2] (leurs numéros) et DISPO [M, NS]."""
    us = unites()
    M, NS = len(cols), len(us)
    sw_v = np.full((T, M, NS, 2), np.nan)
    sw_id = np.zeros((T, M, NS, 2), np.int64)
    dispo = np.zeros((M, NS), bool)
    for j, col in enumerate(cols):
        a, _ = tranches[j]
        lj = loc[:, j]
        for i, u in enumerate(us):
            if u not in bruts[col]:
                continue
            x = bruts[col][u]
            sw = np.asarray(x["sw"], np.float64)
            nc, ns = numeros(sw)
            lg = np.asarray(x["ligne"]).astype(np.int64)
            ok = lj >= 0
            li = np.where(ok, lg[np.clip(a + lj, 0, len(lg) - 1)], -1)
            ok &= li >= 0
            lc = np.clip(li, 0, None)
            sw_v[:, j, i, 0] = np.where(ok, sw[lc, 2], np.nan)
            sw_v[:, j, i, 1] = np.where(ok, sw[lc, 0], np.nan)
            sw_id[:, j, i, 0] = np.where(ok, nc[lc], 0)
            sw_id[:, j, i, 1] = np.where(ok, ns[lc], 0)
            dispo[j, i] = bool(ok.any())
    return sw_v, sw_id, dispo


# ============================================================================================== greffe des têtes
CLES = ("suiv.weight", "suiv.bias")             # la tête du suiveur (cerveau.py), enregistrée EN DERNIER


def greffer_etat(etat: dict) -> tuple[dict, bool]:
    """Les têtes de décision reçoivent la TÊTE DU SUIVEUR : n_options() sorties (aucun, unité x moment) + le penchant
    « laisser courir », poids à ZÉRO ; biais : « aucun » 0, chaque option biais_depart() (toutes ensemble = la part de
    départ), penchant 0. Aucune autre valeur ne change (mêmes clés, mêmes tenseurs). Optimiseur : la nouvelle tête est
    ajoutée à la fin de ses paramètres (sa mémoire naîtra au premier pas). Rend (état, changé)."""
    from collapsar.ecole.precision import cerveau as C
    cer = etat["cerveau"]
    if all(k in cer for k in CLES):
        return etat, False
    ref = cer["tetes.weight"]
    n = activer_temporairement(True, n_options)
    b = torch.zeros(n + 1, dtype=ref.dtype, device=ref.device)       # comme cerveau.Cerveau : même départ
    b[1:n] = activer_temporairement(True, biais_depart)
    etat = dict(etat)
    etat["cerveau"] = {**cer, "suiv.weight": torch.zeros(n + 1, ref.shape[1], dtype=ref.dtype, device=ref.device),
                       "suiv.bias": b}
    opt = etat.get("opt")
    if opt:
        n_avant = len(list(activer_temporairement(False, C.Cerveau).parameters()))
        groupes = [dict(g) for g in opt["param_groups"]]
        ids = [p for g in groupes for p in g["params"]]
        if len(ids) != n_avant:
            raise ValueError(f"optimiseur inattendu : {len(ids)} paramètres (attendu {n_avant})")
        nouveau = max(ids) + 1
        groupes[-1]["params"] = list(groupes[-1]["params"]) + [nouveau, nouveau + 1]
        etat["opt"] = {**opt, "param_groups": groupes}
    return etat, True


def pencher(net, penchants: dict):
    """PENCHANTS de départ d'une branche, AJOUTÉS à ses biais appris (elle reste libre d'apprendre autre chose) :
    part0 (logit en plus pour « rien encaisser à l'objectif 1 »), suiveur_pct (part de départ des options de suiveur,
    poids à zéro), courir (logit en plus pour la destination « laisser courir »)."""
    assert net.n_suiv > 0, "cerveau sans tête de suiveur"
    from collapsar.ecole.precision.cerveau import FERMER
    o2 = 6 + net.n_marge
    with torch.no_grad():
        if penchants.get("part0"):
            net.tetes.bias[o2] += float(penchants["part0"])
        if penchants.get("fermer"):                    # (facultatif) logit en plus / en moins pour fermer à la main
            net.tetes.bias[FERMER] += float(penchants["fermer"])
        b = net.suiv.bias
        if penchants.get("suiveur_pct") is not None:
            b[1:net.n_suiv] = b[0] + biais_options(float(penchants["suiveur_pct"]))
        if penchants.get("courir"):
            b[net.n_suiv] += float(penchants["courir"])


# ============================================================================================== la greffe d'un arbre
def _pid_vivant(f: Path) -> int | None:
    import psutil
    if not f.exists():
        return None
    try:
        pid = int(f.read_text())
    except ValueError:
        return None
    return pid if psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower() else None


def la_plus_faible(arbre, exclure: set[str]) -> str | None:
    """La branche vivante au plus faible niveau, hors `exclure` (cime, témoin neuf)."""
    c = [b for b in arbre.vivantes() if b.nom not in exclure and b.score is not None]
    return min(c, key=lambda b: b.score).nom if c else None


def greffer(dossier: Path | None = None, dire=print, remplacer: bool = True) -> dict:
    """LA GREFFE sur un arbre ARRÊTÉ : sauvegarde complète, têtes agrandies (toutes les branches, meilleures versions,
    cime), suiveur.json écrit ; puis (remplacer=True) la branche la plus faible (hors cime et témoin neuf vivant) est
    archivée et remplacée par une branche « laisse_courir » partant de la cime greffée."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import cerveau as C
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if greffee(dossier):
        raise SystemExit(f"{dossier} : déjà greffé (suiveur.json existe)")
    pid = _pid_vivant(dossier / "coeur.verrou")
    if pid:
        raise SystemExit(f"le cœur bat encore (processus {pid}) : créer {dossier / 'ARRET'} et attendre sa fin")
    if not (dossier / "arbre.json").exists():
        raise SystemExit(f"{dossier} : aucun arbre")
    from collapsar.ecole.precision import foule as FO
    from collapsar.ecole.precision import juge_trade as JT
    from collapsar.ecole.precision import monde as MO
    if FO.greffee(dossier):                          # les mêmes yeux que l'arbre (entrées du cerveau)
        FO.activer()
    JT.allumer_si_greffe(dossier)
    if MO.greffee(dossier):
        MO.activer()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_suiveur_{stamp}"
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
    activer(True)
    info = {"date": datetime.now().isoformat(timespec="seconds"), "version": VERSION, "unites": list(unites()),
            "moments": list(MOMENTS), "options": n_options(), "depart_pct": float(getattr(R().mains, "suiveur_depart_pct", 10.0)),
            "fichiers": faits, "sauvegarde": str(sauve)}
    journal = Journal(dossier / "journal_croissance.jsonl")
    journal.ecrire("greffe_suiveur", fichiers=faits, sauvegarde=str(sauve))
    dire(f"greffe faite : {len(faits)} fichiers (tête du suiveur : {n_options()} options + penchant « laisser courir »)")
    if remplacer:
        arbre = Arbre.charger(dossier / "arbre.json")
        cime = arbre.cime
        temoins = {b.nom for b in arbre.vivantes() if str(b.temperament.get("heritage", "")).startswith("aucun")
                   or b.temperament.get("nom") == "temoin"}
        faible = la_plus_faible(arbre, {cime} | temoins)
        if faible is None:
            raise SystemExit("aucune branche à remplacer (hors cime et témoin)")
        e = torch.load(dossier / "branches" / f"{cime}.pt", map_location="cpu", weights_only=False)
        tc = dict(e.get("temperament") or arbre.branches[cime].temperament)
        net = C.Cerveau()
        net.load_state_dict(e["cerveau"])
        pencher(net, LAISSE_COURIR["penchants"])
        t = {"nom": LAISSE_COURIR["nom"], "vitesse": float(tc.get("vitesse", R().ecole.vitesse)),
             "curiosite": float(tc.get("curiosite", R().ecole.curiosite)), "penchants": dict(LAISSE_COURIR["penchants"]),
             "heritage": f"cime {cime} greffée du stop suiveur ({stamp})"}
        arbre.mourir(faible, "coupée")
        for f in (f"{faible}.pt", f"{faible}_meilleur.pt"):
            if (dossier / "branches" / f).exists():
                (dossier / "archives").mkdir(exist_ok=True)
                shutil.move(str(dossier / "branches" / f), str(dossier / "archives" / f))
        b = arbre.naitre([cime], t)
        opt = torch.optim.AdamW(net.parameters(), lr=t["vitesse"], weight_decay=1e-4)
        tmp = dossier / "branches" / f"{b.nom}.pt.tmp"
        torch.save({"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": t}, tmp)
        os.replace(tmp, dossier / "branches" / f"{b.nom}.pt")
        arbre._elire_cime()
        arbre.sauver(dossier / "arbre.json")
        fx = dossier / "derniers_examens.json"
        if fx.exists():
            x = json.loads(fx.read_text(encoding="utf-8"))
            x.pop(faible, None)
            fx.write_text(json.dumps(x, ensure_ascii=False, default=float), encoding="utf-8")
        journal.ecrire("coupe", branche=faible, raison=f"remplacée par une branche « laisse_courir » (greffe du stop suiveur)")
        journal.ecrire("naissance", branche=b.nom, parents=[cime], temperament=t, heritage=t["heritage"])
        info["remplacee"], info["nouvelle"], info["cime"] = faible, b.nom, cime
        dire(f"branche {faible} archivée ; branche {b.nom} « laisse_courir » née de la cime {cime} greffée")
    (dossier / "suiveur.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def pencher_branche(dossier: Path | None, nom: str, penchants: dict, dire=print) -> dict:
    """Un PENCHANT DE DÉPART de plus pour UNE branche d'un arbre ARRÊTÉ (ex. « fermer moins à la main » pour la branche
    laisse_courir, accord du chef de projet du 18/10) : sauvegarde automatique (sauvegardes/avant_penchant_<nom>_<date>/),
    ajouté aux biais de la branche ET de sa meilleure version (un retour du garde-fou le garde), noté dans son tempérament.
    Aucune autre branche ne bouge. Penchants : part0, courir, fermer (logits ajoutés), suiveur_pct (part de départ)."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import foule as FO
    from collapsar.ecole.precision import juge_trade as JT
    from collapsar.ecole.precision import monde as MO
    dossier = (Path(dossier) if dossier else VIE).resolve()
    pid = _pid_vivant(dossier / "coeur.verrou")
    if pid:
        raise SystemExit(f"le cœur bat encore (processus {pid}) : créer {dossier / 'ARRET'} et attendre sa fin")
    if not greffee(dossier):
        raise SystemExit(f"{dossier} : pas greffé du stop suiveur")
    arbre = Arbre.charger(dossier / "arbre.json")
    if nom not in arbre.branches or arbre.branches[nom].morte is not None:
        raise SystemExit(f"branche {nom} absente ou morte")
    if FO.greffee(dossier):
        FO.activer()
    JT.allumer_si_greffe(dossier)
    if MO.greffee(dossier):
        MO.activer()
    activer(True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_penchant_{nom}_{stamp}"
    sauve.mkdir(parents=True)
    fichiers = [f for f in (dossier / "branches" / f"{nom}.pt", dossier / "branches" / f"{nom}_meilleur.pt") if f.exists()]
    for f in fichiers + [dossier / "arbre.json"]:
        shutil.copy2(f, sauve / f.name)
    for f in fichiers:
        e = torch.load(f, map_location="cpu", weights_only=False)
        net = C.cerveau_pour(e["cerveau"])                  # avec ou sans journal de trading
        pencher(net, penchants)
        e["cerveau"] = net.state_dict()
        if "temperament" in e:
            e["temperament"] = {**e["temperament"], "penchants": {**e["temperament"].get("penchants", {}), **penchants}}
        tmp = f.with_suffix(".pt.tmp")
        torch.save(e, tmp)
        os.replace(tmp, f)
    t = arbre.branches[nom].temperament
    t["penchants"] = {**t.get("penchants", {}), **penchants}
    arbre.sauver(dossier / "arbre.json")
    Journal(dossier / "journal_croissance.jsonl").ecrire("penchant", branche=nom, penchants=penchants, sauvegarde=str(sauve))
    dire(f"branche {nom} : penchants {penchants} ajoutés ({len(fichiers)} fichiers) ; sauvegarde {sauve}")
    return {"branche": nom, "penchants": penchants, "fichiers": [f.name for f in fichiers], "sauvegarde": str(sauve)}


def defaire(dossier: Path | None = None, dire=print):
    """Retour arrière : remet la sauvegarde d'avant la greffe (arbre arrêté)."""
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if _pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : l'arrêter d'abord")
    info = json.loads((dossier / "suiveur.json").read_text(encoding="utf-8"))
    sauve = Path(info["sauvegarde"])
    shutil.rmtree(dossier / "branches")
    shutil.copytree(sauve / "branches", dossier / "branches")
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (sauve / nom).exists():
            shutil.copy2(sauve / nom, dossier / nom)
    if info.get("remplacee"):
        for f in (f"{info['remplacee']}.pt", f"{info['remplacee']}_meilleur.pt"):
            (dossier / "archives" / f).unlink(missing_ok=True)
    (dossier / "suiveur.json").unlink()
    dire(f"greffe du stop suiveur défaite : état remis depuis {sauve}")
