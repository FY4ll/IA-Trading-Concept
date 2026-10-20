"""Couche 4 -- LA SÉLECTION : décider, après l'examen, qui devient champion et quelles lignées (« veines ») on garde.
Logique pure (aucun entraînement ici) ; mêmes règles que Run A (continuous_trainer : note fiable, tri du petit
examen, activité minimale, promotion avec marge, veines mesurées contre le champion du même cycle), prouvées
identiques par tests/test_selection.py."""
from __future__ import annotations
import os
import shutil

import numpy as np


# ------------------------------------------------------------------------------------------------ comparaison juste
def note_fiable(score: float, n_trades: int, min_trades: int) -> float:
    """Une note obtenue sur trop peu de trades est incertaine : positive -> réduite, négative -> accentuée."""
    if min_trades <= 0 or n_trades <= 0:
        return score
    r = min(1.0, n_trades / min_trades)
    if r >= 1.0 or score == 0:
        return score
    return score * r if score > 0 else score / r


def tri_petit_examen(notes: dict, note_champion: float | None, marge: float = 0.25, garder: int = 1) -> set:
    """Candidats retenus pour l'examen complet : au moins presque aussi bons que le champion au petit examen,
    plus les `garder` meilleurs quoi qu'il arrive. `notes` = {candidat: note du petit examen}."""
    ordre = sorted(notes, key=notes.get, reverse=True)
    return {c for i, c in enumerate(ordre) if i < garder or note_champion is None or notes[c] >= note_champion - marge}


def promotion(champion: dict, candidats: list[dict], min_trades_fiables: int, marge: float,
              actif=lambda m: True) -> dict | None:
    """Le meilleur candidat ACTIF dont la note fiable bat celle du champion de `marge` (champion trop peu actif :
    battable par tout candidat actif). Dicts : {"score", "metrics"}."""
    actifs = [c for c in candidats if actif(c["metrics"])]
    if not actifs:
        return None
    meilleur = max(actifs, key=lambda c: note_fiable(c["score"], c["metrics"].get("n_trades", 0), min_trades_fiables))
    barre = -99.0 if not actif(champion["metrics"]) else note_fiable(
        champion["score"], champion["metrics"].get("n_trades", 0), min_trades_fiables)
    gagne = note_fiable(meilleur["score"], meilleur["metrics"].get("n_trades", 0), min_trades_fiables) > barre + marge
    return meilleur if gagne else None


# ------------------------------------------------------------------------------------------------ les veines
def nouveau_talent(m: dict, m_champion: dict | None, regles: dict) -> tuple[bool, str]:
    """Talent à garder : actif, pas d'effondrement sur l'or, et mieux que le champion du même cycle sur les marchés
    inversés (il sait vendre) ou sur au moins 2/3 des marchés."""
    if not m.get("markets") or not m_champion or not m_champion.get("markets"):
        return False, ""
    if m.get("max_drawdown", 1.0) > float(regles.get("max_drawdown", 0.30)):
        return False, ""
    if int(m.get("n_trades", 0) or 0) < int(regles.get("min_trades", 100)):
        return False, ""
    ch = {p["market"]: p["score"] for p in m_champion["markets"]}
    ca = {p["market"]: p["score"] for p in m["markets"]}
    communs = [k for k in ca if k in ch]
    if not communs:
        return False, ""
    inverses = [k for k in communs if k.endswith("miroir")]
    if inverses:
        gain = float(np.mean([ca[k] for k in inverses]) - np.mean([ch[k] for k in inverses]))
        if gain >= float(regles.get("min_mirror_gain", 0.25)):
            return True, f"vend mieux que le champion (marchés inversés {gain:+.2f})"
    gagnes = sum(1 for k in communs if ca[k] > ch[k] + 0.05)
    if gagnes * 3 >= 2 * len(communs):
        return True, f"bat le champion sur {gagnes}/{len(communs)} marchés"
    return False, ""


def veine_a_nourrir(veines: list, generation: int):
    if not veines:
        return None
    w = np.array([max(1e-6, float(v.get("flux", 1.0))) for v in veines])
    return veines[int(np.random.default_rng(generation).choice(len(veines), p=w / w.sum()))]


def ecart(v: dict) -> float:
    return float(v.get("gap", -9.0))


def faire_vivre_veines(dossier: str, veines: list, resultats: list, m_champion: dict | None, note_champion: float,
                       generation: int, regles: dict) -> tuple[list, list]:
    """Après un cycle : une veine qui progresse (écart au champion du même cycle) grossit et garde son nouveau
    cerveau ; une veine qui stagne s'amincit puis disparaît (archivée) ; un nouveau talent ouvre une veine.
    `resultats` : {"id", "score", "metrics", "fichier", "hyperparams", "veine", "promu"}."""
    maxi, grow, shrink = int(regles.get("max_veins", 3)), float(regles.get("grow", 1.5)), float(regles.get("shrink", 0.7))
    flux_max, flux_min = float(regles.get("flux_max", 4.0)), float(regles.get("flux_min", 0.2))
    max_stall, min_gain = int(regles.get("max_stall", 4)), float(regles.get("min_gain", 0.02))
    protege, archives = float(regles.get("protect_gap", 0.10)), int(regles.get("archives", 3))
    os.makedirs(dossier, exist_ok=True)
    veines = [dict(v) for v in veines]
    journal = []
    for r in resultats:
        g = float(r["score"]) - note_champion
        v = next((x for x in veines if x["id"] == r.get("veine")), None)
        if r.get("promu"):
            if v is not None:
                veines.remove(v)
                _retirer(v)
                journal.append(f"veine {v['id']} a battu le champion -> devient le chemin principal")
            continue
        if v is not None:
            v["tries"] = int(v.get("tries", 0)) + 1
            if g > ecart(v) + min_gain:
                shutil.copy(r["fichier"] + ".zip", v["path"] + ".zip")
                journal.append(f"veine {v['id']} PROGRESSE : écart {ecart(v):+.3f} -> {g:+.3f}")
                v.update(score=float(r["score"]), gap=g, best_gap=max(float(v.get("best_gap", g)), g),
                         hyperparams=r.get("hyperparams"), stall=0, flux=min(flux_max, float(v["flux"]) * grow))
            else:
                v["stall"] = int(v.get("stall", 0)) + 1
                v["flux"] = float(v["flux"]) * shrink
                if ecart(v) >= -protege:
                    v["flux"] = max(v["flux"], 0.3)
                journal.append(f"veine {v['id']} stagne ({v['stall']} essai(s))")
            continue
        ok, pourquoi = nouveau_talent(r.get("metrics") or {}, m_champion, regles)
        if not ok:
            continue
        nv = {"id": f"V{generation}_{r['id']}", "score": float(r["score"]), "gap": g, "best_gap": g, "flux": 1.0,
              "stall": 0, "tries": 0, "born": generation, "reason": pourquoi, "hyperparams": r.get("hyperparams")}
        nv["path"] = os.path.join(dossier, nv["id"])
        if len(veines) >= maxi:
            faible = min(veines, key=ecart)
            if g <= ecart(faible):
                continue
            veines.remove(faible)
            _archiver(dossier, faible, archives)
            journal.append(f"veine {faible['id']} remplacée (archivée)")
        shutil.copy(r["fichier"] + ".zip", nv["path"] + ".zip")
        veines.append(nv)
        journal.append(f"NOUVELLE veine {nv['id']} : {pourquoi}")
    for v in list(veines):
        prot = ecart(v) >= -protege
        if int(v.get("stall", 0)) >= max_stall * (2 if prot else 1) or (not prot and float(v.get("flux", 1)) < flux_min):
            veines.remove(v)
            _archiver(dossier, v, archives)
            journal.append(f"veine {v['id']} disparaît (archivée)")
    return veines, journal


def _retirer(v):
    try:
        os.remove(v["path"] + ".zip")
    except OSError:
        pass


def _archiver(dossier, v, garder):
    a = os.path.join(dossier, "archives")
    os.makedirs(a, exist_ok=True)
    try:
        shutil.move(v["path"] + ".zip", os.path.join(a, v["id"] + ".zip"))
    except OSError:
        return
    gardees = sorted((f for f in os.listdir(a) if f.endswith(".zip")),
                     key=lambda f: os.path.getmtime(os.path.join(a, f)), reverse=True)
    for f in gardees[garder:]:
        try:
            os.remove(os.path.join(a, f))
        except OSError:
            pass
