"""
Ajoute AUREXIS « formé par le professeur » (scripts/professeur_aurexis.py) comme VEINE de l'évolution (09/10/2026).

Sur les 12 mois cachés (10/2025 -> 10/2026, 37 marchés, frais réalistes) : compte -20 % contre -64 % pour le champion,
challenges ratés 46 % contre 98 %. Il n'est PAS imposé : comme toute veine, il est nourri et jugé à l'examen tournant,
et ne devient le chemin principal que s'il bat le champion du cycle (mêmes garde-fous).

    python scripts/veine_professeur.py        (cwd = code/, Run A ARRÊTÉ ; lancé par boundary_apply_staged.ps1)
"""
import json, os, shutil, time

CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(CODE, "models", "professeur_AUREXIS", "agent.zip")
VDIR = os.path.join(CODE, "models", "champion_AUREXIS", "veines")
VID = "PROF_0910"


def main():
    vj = os.path.join(VDIR, "veines.json")
    veins = json.load(open(vj, encoding="utf-8")) if os.path.exists(vj) else []
    if any(v["id"] == VID for v in veins):
        print("Rien à faire : veine professeur déjà présente."); return
    if not os.path.exists(SRC):
        raise SystemExit("ABANDON : modèle du professeur introuvable")
    pf = os.path.join(CODE, "models", "_progress.json")
    progress = json.load(open(pf, encoding="utf-8")) if os.path.exists(pf) else {}
    gen = int(progress.get("generation", 0))
    path = os.path.join(VDIR, VID)
    shutil.copy(SRC, path + ".zip")
    veins.append({"id": VID, "score": 0.0, "gap": 0.0, "best_gap": 0.0, "flux": 1.5, "stall": 0, "tries": 0,
                  "born": gen, "last_gen": gen, "reason": "professeur (tendance de fond imitée) : 12 mois cachés -20 % "
                  "contre -64 % pour le champion", "hyperparams": None, "history": [], "path": path})
    shutil.copy(vj, vj + f".bak_{time.strftime('%Y%m%d_%H%M')}") if os.path.exists(vj) else None
    tmp = vj + ".tmp"
    json.dump(veins, open(tmp, "w", encoding="utf-8"), indent=1, default=str)
    os.replace(tmp, vj)
    print(f"OK : veine {VID} ajoutée ({len(veins)} veines vivantes)")


if __name__ == "__main__":
    main()
