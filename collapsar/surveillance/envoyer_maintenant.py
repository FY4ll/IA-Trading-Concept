"""Envoie tout de suite les deux images de l'arbre réel au téléphone (sans toucher au cœur qui bat).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.surveillance.envoyer_maintenant"""
from collapsar.arbre.coeur import ETAT, IMAGES, VIE
from collapsar.arbre.jardinier import Arbre
from collapsar.arbre.journal import Journal
from collapsar.surveillance import dessin, telephone


def main():
    arbre = Arbre.charger(ETAT)
    lignes = Journal(VIE / "journal_croissance.jsonl").lire()
    portes = [(l["heure"], l["porte"]) for l in lignes if l.get("quoi") == "porte"]
    f1 = dessin.dessiner_arbre(arbre, IMAGES / "arbre.png", portes)
    f2 = dessin.dessiner_courbe(lignes, IMAGES / "courbe.png")
    cime = arbre.branches.get(arbre.cime)
    resume = f"{arbre.battements} battement(s). Cime {cime.nom} : {dessin._virgule(cime.score, 2)} %." if cime else ""
    ok = telephone.envoyer_image(f1, "COLLAPSAR : l'arbre", resume) and \
        telephone.envoyer_image(f2, "COLLAPSAR : progrès de la cime", resume)
    print("envoyées" if ok else "NON envoyées")


if __name__ == "__main__":
    main()
