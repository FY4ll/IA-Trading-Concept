"""Contre le par cœur : une branche garde sa meilleure version et y revient si son lien retombe."""
import torch

from collapsar.arbre import coeur
from collapsar.arbre.jardinier import TEMPERAMENT_GRAINE, Arbre


def test_garder_puis_revenir(tmp_path, monkeypatch):
    monkeypatch.setattr(coeur, "BRANCHES", tmp_path)
    monkeypatch.setattr(coeur, "VISION", "trader")
    monkeypatch.setattr(coeur, "LARGEUR_TRADER", 0.35)
    a = Arbre()
    b = a.naitre([], dict(TEMPERAMENT_GRAINE))
    c = coeur.nouveau_cerveau(b.temperament, "cpu")
    coeur.sauver_branche(b.nom, c, coeur.optimiseur(c, b.temperament))
    assert coeur.garder_ou_revenir(b, 3.5, c, "cpu") == (3.5, None) and b.record == 3.5
    bon = {k: v.clone() for k, v in c.state_dict().items()}
    with torch.no_grad():
        for p in c.parameters():
            p.add_(1.0)                                   # elle « apprend par cœur »
    coeur.sauver_branche(b.nom, c, coeur.optimiseur(c, b.temperament))
    assert coeur.garder_ou_revenir(b, 3.3, c, "cpu") == (3.3, None), "petite baisse (bruit) : on continue"
    note, evenement = coeur.garder_ou_revenir(b, 2.9, c, "cpu")
    assert note == 3.5 and evenement and b.retours == 1
    assert all(torch.equal(v, bon[k]) for k, v in c.state_dict().items()), "le cerveau est revenu à sa meilleure version"
    assert b.temperament["vitesse"] == TEMPERAMENT_GRAINE["vitesse"] / 2
    sur_disque = torch.load(tmp_path / f"{b.nom}.pt", weights_only=True)["cerveau"]
    assert all(torch.equal(v, bon[k]) for k, v in sur_disque.items())
