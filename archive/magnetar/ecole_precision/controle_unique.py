"""CONTRÔLE 2024-2025 UNE SEULE FOIS sur une version FIGÉE de MAGNETAR (20/10/2026, corrections graves de l'audit).

Pourquoi : l'examen tournant de la lignée de MAGNETAR ne prouve rien (26 blocs d'examen sur 28 ont été appris par la
lignée avant le 19/10, voir vie/arbre_or/corrections_graves/rapport.md) ; la seule mesure honnête qui reste avant la démo
est 01/2024 -> 09/2025, jamais apprise. Elle a été lue trop souvent (rapport toutes les 50 générations) : désormais le
rapport de l'arbre ne la calcule plus (réglage rapports.controle_auto: false) et elle ne se lit QU'ICI, une fois par
version figée, JAMAIS pour choisir une branche.

  figer   : copie la cime actuelle (cime.pt + son tempérament) dans vie/arbre_or/controle_unique/versions/ (empreinte
            des poids) ; peut se faire arbre en marche (lecture seule).
  lancer  : --version <fichier figé> : rejoue CETTE version sur 01/2024 -> 09/2025 (examen fixe des réglages, elle et
            son jumeau), écrit le résultat et l'inscrit au registre ; REFUSE une version déjà contrôlée, et refuse si
            le registre contient déjà un contrôle de moins de 7 jours (pas de « lecture en boucle »), sauf --forcer.
            Arrêter l'arbre avant si la carte graphique est prise (ou --appareil cpu).

Depuis Test_IA (NE PAS LANCER sans l'accord du chef de projet) :
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.controle_unique figer
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.controle_unique lancer --version <chemin>
Rien après 09/2025 (réglages : fin_donnees).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

REGLAGES = Path(__file__).with_name("reglages_or.yaml")
if "collapsar.ecole.precision.reglages" not in sys.modules:
    os.environ.setdefault("COLLAPSAR_PRECISION_REGLAGES", str(REGLAGES))

import torch  # noqa: E402

from collapsar.ecole.precision.reglages import NOM, VIE, R  # noqa: E402

DOSSIER = "controle_unique"
REGISTRE = "registre.json"


def _empreinte(f: Path) -> str:
    return hashlib.sha256(Path(f).read_bytes()).hexdigest()[:16]


def _registre(dossier: Path) -> list:
    f = dossier / DOSSIER / REGISTRE
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def figer(dossier: Path = VIE) -> Path:
    dossier = Path(dossier)
    ch = torch.load(dossier / "cime.pt", map_location="cpu", weights_only=False)
    try:
        t = json.loads((dossier / "arbre.json").read_text(encoding="utf-8"))["branches"][ch["branche"]]["temperament"]
    except Exception:
        t = None
    out = dossier / DOSSIER / "versions"
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_tmp.pt"
    torch.save({"cerveau": ch["cerveau"], "branche": ch["branche"], "generation": ch["generation"], "temperament": t,
                "figee_le": datetime.now().isoformat(timespec="seconds"), "arbre": NOM}, tmp)
    h = _empreinte(tmp)
    f = out / f"{NOM}_g{ch['generation']}_{ch['branche']}_{h}.pt"
    shutil.move(str(tmp), str(f))
    print(f"version figée : {f} (branche {ch['branche']}, génération {ch['generation']}, empreinte {h})")
    return f


def lancer(version: Path, dossier: Path = VIE, appareil: str = "cuda", forcer: bool = False) -> dict:
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision.coeur import GRAINE_EXAMEN, monde_examen, resume_examen
    dossier, version = Path(dossier), Path(version)
    h = _empreinte(version)
    reg = _registre(dossier)
    if any(x["empreinte"] == h for x in reg):
        raise SystemExit(f"version {version.name} déjà contrôlée sur 2024-2025 : refus (une seule fois par version)")
    recents = [x for x in reg if datetime.fromisoformat(x["date"]) > datetime.now() - timedelta(days=7)]
    if recents and not forcer:
        raise SystemExit(f"un contrôle 2024-2025 a déjà été fait le {recents[-1]['date']} : refus (moins de 7 jours ; "
                         f"--forcer seulement avec l'accord du chef de projet)")
    allumer_yeux(dossier)
    v = torch.load(version, map_location=appareil, weights_only=False)
    net = C.cerveau_pour(v["cerveau"]).to(appareil)
    C.regler_precision(net, v.get("temperament"))
    C.regler_symetrie(net, v.get("temperament"))
    r = R()
    U, ex = monde_examen(r.periodes.rapport_de, r.periodes.rapport_jusqua, appareil)
    x = resume_examen(ex.jouer_un(net, GRAINE_EXAMEN))
    res = {"date": datetime.now().isoformat(timespec="seconds"), "version": version.name, "empreinte": h,
           "branche": v.get("branche"), "generation": v.get("generation"),
           "periode": f"{r.periodes.rapport_de:%m/%Y} -> {r.periodes.rapport_jusqua:%m/%Y} (exclu)",
           "gain_pct_mois": x["gain_pct_mois"], "jumeau_pct_mois": x["jumeau"]["gain_pct_mois"],
           "r_moyen": x["r_moyen"], "trades_mois": x["trades_mois"], "reussis_pct": x["reussis_pct"],
           "jumeau_reussis_pct": x["jumeau"]["reussis_pct"], "murs_pct": x["murs_pct"],
           "avantage_pct_mois": x["avantage_pct_mois"], "avantage_incertitude": x["avantage_incertitude"]}
    out = dossier / DOSSIER
    (out / f"resultat_{version.stem}.json").write_text(json.dumps(x, ensure_ascii=False, indent=1, default=float),
                                                      encoding="utf-8")
    reg.append(res)
    (out / REGISTRE).write_text(json.dumps(reg, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    return res


def allumer_yeux(dossier: Path):
    """Les mêmes yeux et mains que l'arbre (comme coeur.main) : foule greffée, tendance, suiveur, suiveur après +1R."""
    from collapsar.ecole.precision import foule as FO
    from collapsar.ecole.precision import monde as MO
    from collapsar.ecole.precision import suiveur as SV
    from collapsar.ecole.precision import tendance as TD
    from collapsar.ecole.precision import juge_trade as JT
    if FO.greffee(dossier):
        FO.activer()
    if MO.greffee(dossier):
        MO.activer()
    JT.allumer_si_greffe(dossier)
    if SV.greffee(dossier):
        SV.activer()
    if (dossier / "tendance.json").exists():
        TD.activer()
    if (dossier / "suiveur_1r.json").exists():
        R().mains.suiveur_1r = True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("quoi", choices=["figer", "lancer", "registre"])
    ap.add_argument("--version", default=None)
    ap.add_argument("--dossier", default=None)
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--forcer", action="store_true")
    a = ap.parse_args(argv)
    d = Path(a.dossier) if a.dossier else VIE
    if a.quoi == "figer":
        return figer(d)
    if a.quoi == "registre":
        print(json.dumps(_registre(d), ensure_ascii=False, indent=1))
        return 0
    if not a.version:
        raise SystemExit("--version <fichier figé> obligatoire")
    return lancer(Path(a.version), d, a.appareil, a.forcer)


if __name__ == "__main__":
    main()
