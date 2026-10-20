"""Bilan en une lecture : l'arbre (derniers battements, branches, porte), les données, la machine.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.surveillance.bilan"""
from __future__ import annotations

import json
import subprocess

from collapsar.arbre import portes
from collapsar.arbre.jardinier import Arbre
from collapsar.donnees import marches as dm

VIE = dm.RACINE / "collapsar" / "vie"


def main():
    lignes = [json.loads(x) for x in open(VIE / "journal_croissance.jsonl", encoding="utf-8")]
    bat = [x for x in lignes if x["quoi"] == "battement" and "branches" in x]
    print(f"battements : {len(bat)} | dernier : {bat[-1]['heure'][11:16] if bat else '-'}")
    for x in bat[-4:]:
        br = " ".join(f"{n}:{r['score']:.2f}" for n, r in x["branches"].items())
        print(f"  {x['heure'][11:16]} cime {x['cime']} {x['cime_score']:.2f} | {br}")
    for x in [x for x in lignes if x["quoi"] in ("naissance", "coupe", "fusion", "porte", "porte_fermee",
                                                  "verification_porte")][-5:]:
        print("  ", x["heure"][11:16], x["quoi"], {k: v for k, v in x.items() if k not in ("heure", "quoi", "temperament")})
    arbre = Arbre.charger(VIE / "arbre.json")
    for b in arbre.vivantes():
        print(f"  vivante {b.nom} niveau {b.score if b.score is not None else 0:.2f} ({len(b.scores)} notes) "
              f"{'miroir ' if b.temperament.get('miroir') else ''}vitesse {b.temperament['vitesse']:g} lot {b.temperament['lot']}")
    print(" ", portes.resume(arbre, portes.lire()))
    debut = {}
    for f in (dm.DOSSIER_M15).glob("*_M15.csv"):
        with open(f, encoding="utf-8") as h:
            h.readline()
            debut[f.name[:-8]] = h.readline()[:4]
    print(f"données depuis 2010 : {sum(1 for v in debut.values() if v <= '2011')} marchés ; depuis 2018 : "
          f"{', '.join(sorted(m for m, v in debut.items() if v >= '2016'))}")
    smi = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used",
                          "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    print(f"carte graphique : {smi}")


if __name__ == "__main__":
    main()
