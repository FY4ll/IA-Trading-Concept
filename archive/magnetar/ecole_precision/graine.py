"""LA GRAINE HÉRITÉE d'un arbre spécialisé de l'école de la précision (18/10/2026, arbre de l'or).

Un arbre spécialisé ne part pas de zéro : il part de branches d'un AUTRE arbre de l'école (ex. la cime d'HYPERNOVA,
qui a déjà appris le geste : ordres limites sur ses zones, stop derrière la zone, sélectivité, respect des murs).
Réglage `arbre.graine` de son fichier de réglages :
  source: dossier de vie de l'arbre source (ex. collapsar/vie/hypernova)
  branches: liste de {nom, de: cime | deuxieme | neuve, curiosite_x (facultatif), temperament (pour « neuve »)}
- `copier_source` : COPIE (jamais de déplacement ni de modification) de l'état de l'arbre source dans
  <dossier>/graine_source/ ; si l'arbre source bat, la copie se fait juste APRÈS la fin d'une de ses générations (ses
  fichiers viennent d'être écrits et ne le seront plus avant ~2 min) : aucune lecture d'un fichier en cours d'écriture,
  et jamais de fichier source tenu ouvert au moment où il le remplace. Les greffes de l'arbre source (foule.json,
  juge.json, monde.json) sont recopiées : les yeux s'allument comme les siens (entrées du cerveau compatibles).
- `planter` : les branches de départ (copie de la cime, copie de la cime plus curieuse, copie de la 2e meilleure
  branche vivante, une branche NEUVE comme témoin pour voir si l'héritage aide).
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

from collapsar.donnees.marches import RACINE

SOUS_DOSSIER = "graine_source"
GREFFES = ("foule.json", "juge.json", "monde.json")
AGE_MIN_S, AGE_MAX_S = 4.0, 60.0          # fenêtre sûre après la dernière sauvegarde de l'arbre source


def _source(g) -> Path:
    p = Path(g.source)
    return p if p.is_absolute() else RACINE / p


def _bat(source: Path) -> bool:
    v = source / "coeur.verrou"
    if not v.exists():
        return False
    try:
        import psutil
        pid = int(v.read_text())
        return psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower()
    except Exception:
        return False


def niveau(b: dict) -> float | None:
    s = [x[1] for x in b.get("scores", [])[-3:]]
    return sum(s) / len(s) if s else None


def choisir(arbre: dict) -> tuple[str, str | None]:
    """(cime, 2e meilleure branche vivante) d'un arbre.json. Comme l'élection de la cime : parmi les branches qui ont
    fait leurs preuves (au moins 3 notes), une jeune branche brillante sur une seule note ne compte pas (sinon toutes)."""
    cime = arbre["cime"]
    autres = [(niveau(b), len(b.get("scores", [])) >= 3, n) for n, b in arbre["branches"].items()
              if b.get("morte") is None and n != cime and niveau(b) is not None]
    confirmees = [(v, n) for v, ok, n in autres if ok] or [(v, n) for v, _, n in autres]
    return cime, (max(confirmees)[1] if confirmees else None)


def copier_source(g, dossier: Path, dire=print, attente_max_s: float = 900.0) -> dict:
    """Copie (une seule fois) l'état utile de l'arbre source dans <dossier>/graine_source/ ; rend la fiche copie.json."""
    dossier = Path(dossier)
    snap = dossier / SOUS_DOSSIER
    fiche = snap / "copie.json"
    if fiche.exists():
        info = json.loads(fiche.read_text(encoding="utf-8"))
    else:
        source = _source(g)
        if not (source / "arbre.json").exists():
            raise SystemExit(f"graine : aucun arbre dans {source}")
        snap.mkdir(parents=True, exist_ok=True)
        info = None
        t0 = time.time()
        while info is None:
            if time.time() - t0 > attente_max_s:
                raise RuntimeError(f"graine : pas de fenêtre sûre pour copier {source} en {attente_max_s:.0f} s")
            bat = _bat(source)
            if bat:
                age = time.time() - (source / "arbre.json").stat().st_mtime
                if not (AGE_MIN_S <= age <= AGE_MAX_S):
                    time.sleep(1.0)
                    continue
            m0 = (source / "arbre.json").stat().st_mtime
            try:
                shutil.copyfile(source / "arbre.json", snap / "arbre.json")
                arbre = json.loads((snap / "arbre.json").read_text(encoding="utf-8"))
                cime, deux = choisir(arbre)
                noms = [cime] + ([deux] if deux else [])
                for n in noms:
                    shutil.copyfile(source / "branches" / f"{n}.pt", snap / f"{n}.pt")
                for f in GREFFES:
                    if (source / f).exists():
                        shutil.copyfile(source / f, snap / f)
            except (OSError, json.JSONDecodeError) as ex:
                dire(f"graine : copie à refaire ({type(ex).__name__}: {ex})")
                time.sleep(2.0)
                continue
            if (source / "arbre.json").stat().st_mtime != m0:          # une sauvegarde pendant la copie : on refait
                time.sleep(2.0)
                continue
            for n in noms:                                             # copies lisibles (fichiers entiers)
                torch.load(snap / f"{n}.pt", map_location="cpu", weights_only=False)
            b = arbre["branches"]
            info = {"date": datetime.now().isoformat(timespec="seconds"), "source": str(source),
                    "source_battait": bat, "generation": arbre["battements"],
                    "cime": cime, "cime_niveau": niveau(b[cime]), "deuxieme": deux,
                    "deuxieme_niveau": niveau(b[deux]) if deux else None,
                    "greffes": [f for f in GREFFES if (snap / f).exists()]}
            fiche.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
            dire(f"graine copiée depuis {source.name} (génération {info['generation']}) : cime {cime} "
                 f"(niveau {info['cime_niveau']:+.2f}), 2e {deux} "
                 + (f"(niveau {info['deuxieme_niveau']:+.2f})" if deux else ""))
    for f in info.get("greffes", []):                                  # les mêmes yeux que l'arbre source
        if not (dossier / f).exists():
            x = json.loads((snap / f).read_text(encoding="utf-8"))
            x["herite_de"] = info["source"]
            (dossier / f).write_text(json.dumps(x, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def planter(coeur, g, dire=print) -> list[str]:
    """Les branches de départ de l'arbre (dans coeur.arbre / coeur.branches), sauvegardées."""
    from collapsar.arbre.jardinier import Arbre, Reglages
    M = sys.modules[type(coeur).__module__]                # Branche, appliquer_temperament du cœur qui tourne
    info = copier_source(g, coeur.dossier, dire)
    snap = coeur.dossier / SOUS_DOSSIER
    a = coeur.r.arbre
    coeur.arbre = Arbre(Reglages(places=a.places))
    src_nom = Path(info["source"]).name.upper()
    noms = []
    for i, spec in enumerate(g.branches):
        spec = dict(spec)
        de = spec["de"]
        if de == "neuve":
            t = dict(spec.get("temperament") or a.temperaments[0])
            t["nom"] = spec.get("nom", t.get("nom", "temoin"))
            t["heritage"] = "aucun (branche neuve, témoin)"
            b = coeur.arbre.naitre([], t)
            torch.manual_seed(20261018 + i)
            br = M.Branche(b.nom, t, coeur.dev)
            M.appliquer_temperament(br.net, t)
        else:
            nom_src = info["cime"] if de == "cime" else info["deuxieme"]
            if nom_src is None:
                raise SystemExit(f"graine : l'arbre source n'a pas de branche « {de} »")
            e = torch.load(snap / f"{nom_src}.pt", map_location=coeur.dev, weights_only=False)
            from collapsar.ecole.precision import suiveur as SV
            if SV.active():                                # arbre né avec le stop suiveur : têtes greffées sans perte
                e = SV.greffer_etat(e)[0]
            t = dict(e.get("temperament") or {})
            t.pop("alertes", None)
            t["nom"] = spec.get("nom", t.get("nom", nom_src))
            if spec.get("curiosite_x"):
                t["curiosite"] = float(np.clip(float(t.get("curiosite", coeur.r.ecole.curiosite)) * float(spec["curiosite_x"]),
                                               1e-4, 0.03))
            t["heritage"] = f"{src_nom} {nom_src} (génération {info['generation']})"
            b = coeur.arbre.naitre([], t)
            br = M.Branche(b.nom, t, coeur.dev, e)        # mêmes yeux (greffes recopiées) : chargement strict
        br.sauver(coeur.dossier)
        coeur.branches[b.nom] = br
        coeur.journal.ecrire("naissance", branche=b.nom, parents=[], temperament=t, heritage=t["heritage"])
        noms.append(b.nom)
        dire(f"  branche {b.nom} « {t['nom']} » : {t['heritage']} (vitesse {t['vitesse']:.2g}, curiosité "
             f"{t.get('curiosite', coeur.r.ecole.curiosite):.2g})")
    coeur.arbre.sauver(coeur.f_arbre)
    return noms
