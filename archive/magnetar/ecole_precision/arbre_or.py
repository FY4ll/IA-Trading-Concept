"""LANCEUR DE L'ARBRE DE L'OR (18/10/2026) : le même cœur qu'HYPERNOVA (coeur.py), avec SES réglages
(reglages_or.yaml : nom, dossier de vie, l'or seul réel et retourné, examen 2023 sur l'or, graine héritée d'HYPERNOVA).

Depuis Test_IA :  venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.precision.arbre_or --generations 1000
Mêmes options que le cœur (--dossier, --muet, --rapport, --appareil). Pause : créer collapsar\\vie\\arbre_or\\PAUSE ;
arrêt propre : créer collapsar\\vie\\arbre_or\\ARRET. Son verrou est dans son dossier (indépendant d'HYPERNOVA).
Le gardien le reconnaît au nom de ce module (« precision.arbre_or »), jamais confondu avec « precision.coeur ».
STOP SUIVEUR (18/10, suiveur.py) : greffe sans perte sur l'arbre arrêté : `arbre_or --greffer-suiveur` (retour arrière :
`--defaire-suiveur`).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REGLAGES = Path(__file__).with_name("reglages_or.yaml")
_deja = sys.modules.get("collapsar.ecole.precision.reglages")
if _deja is not None and Path(_deja.FICHIER).resolve() != REGLAGES.resolve():
    raise SystemExit("arbre_or : les réglages d'un autre arbre sont déjà chargés dans ce programme")
os.environ["COLLAPSAR_PRECISION_REGLAGES"] = str(REGLAGES)
# Carte graphique partagée avec HYPERNOVA (plafond `carte_max_go` des réglages) : la réserve inutilisée est rendue tôt
# (dès 70 % du plafond) et les gros blocs ne sont pas découpés (moins de mémoire perdue en morceaux). Avant CUDA.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "garbage_collection_threshold:0.7,max_split_size_mb:64")

from collapsar.ecole.precision import coeur  # noqa: E402  (après le choix des réglages)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] in (["--greffer-suiveur"], ["--defaire-suiveur"]):
        # GREFFE du stop suiveur (suiveur.py) sur l'arbre ARRÊTÉ (sauvegarde automatique), ou retour arrière
        from collapsar.ecole.precision import suiveur as SV
        from collapsar.ecole.precision.reglages import VIE
        d = Path(argv[argv.index("--dossier") + 1]) if "--dossier" in argv else VIE
        return SV.greffer(d) if argv[0] == "--greffer-suiveur" else SV.defaire(d)
    if argv[:1] == ["--penchant"]:
        # un penchant de départ de plus pour UNE branche (arbre ARRÊTÉ) : --penchant G fermer=-8 [courir=...]
        from collapsar.ecole.precision import suiveur as SV
        from collapsar.ecole.precision.reglages import VIE
        d = Path(argv[argv.index("--dossier") + 1]) if "--dossier" in argv else VIE
        pen = {k: float(v) for k, v in (x.split("=") for x in argv[2:] if "=" in x)}
        return SV.pencher_branche(d, argv[1], pen)
    return coeur.main(argv)


if __name__ == "__main__":
    main()
