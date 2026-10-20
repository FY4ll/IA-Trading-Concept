"""Le jardinier et les images de l'arbre."""
import random
from datetime import datetime, timedelta

from collapsar.arbre.jardinier import TEMPERAMENT_GRAINE, Arbre, Reglages
from collapsar.surveillance import dessin


def _h(minutes):
    return (datetime(2026, 10, 13, 20, 0) + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def test_seve_partagee_et_jeunesse():
    a = Arbre()
    for _ in range(3):
        a.naitre([], TEMPERAMENT_GRAINE)
    for nom, s in zip("ABC", (52, 51, 50)):
        for _ in range(4):
            a.noter(nom, s)
    p = a.parts_de_seve()
    assert abs(sum(p.values()) - 1) < 1e-9 and p["A"] > p["B"] > p["C"]
    d = a.naitre(["A"], TEMPERAMENT_GRAINE)
    assert a.parts_de_seve()[d.nom] >= 0.15, "une jeune branche a de quoi faire ses preuves"
    assert a.cime == "A"


def test_la_cime_ne_change_pas_sur_une_note_chanceuse():
    a = Arbre()
    a.naitre([], TEMPERAMENT_GRAINE)
    a.naitre(["A"], TEMPERAMENT_GRAINE)
    for s in (52.07, 52.08, 52.24, 52.18, 52.23, 52.03):     # A : une baisse passagère à la fin
        a.noter("A", s)
    a.noter("B", 52.07)                                      # B : une seule note, un peu au-dessus de 52,03
    assert a.cime == "A", "la cime se juge sur la moyenne des 3 dernières notes"
    a.noter("B", 52.58)                                      # B brille, mais n'a que 2 notes
    assert a.cime == "A", "une jeune branche doit confirmer (3 notes) avant de devenir la cime"
    a.noter("B", 52.40)
    assert a.cime == "B"


def test_bourgeon_seulement_sil_reste_une_place():
    a = Arbre(Reglages(places=2, bourgeon_tous=1))
    a.naitre([], TEMPERAMENT_GRAINE)
    a.noter("A", 50.5); a.fin_de_battement(); a.noter("A", 50.7); a.fin_de_battement()
    assert ("bourgeon", "A") in a.decisions()
    a.naitre(["A"], TEMPERAMENT_GRAINE)
    assert not [x for x in a.decisions() if x[0] == "bourgeon"]


def test_coupe_et_fusion():
    a = Arbre(Reglages(places=3, jeunesse=1, coupe_apres=2, coupe_ecart=0.3, fusion_tous=1, fusion_maturite=2))
    for _ in range(3):
        a.naitre([], TEMPERAMENT_GRAINE)
    for s in (51, 51.5, 52):
        a.noter("A", s)
    for s in (51, 51.2, 51.4):
        a.noter("B", s)
    for s in (50.5, 50.4, 50.3):                      # C ne progresse plus et reste loin derrière
        a.noter("C", s)
        a.fin_de_battement()
    d = a.decisions()
    assert ("couper", "C") in d and ("fusion", "A", "B") in d
    a.mourir("A", "fusion")
    assert a.cime == "B", "la cime est réélue quand elle disparaît"


def test_memoire_de_l_arbre(tmp_path):
    a = Arbre()
    a.naitre([], TEMPERAMENT_GRAINE)
    a.noter("A", 50.8, bonnes=50.2)
    a.fin_de_battement()
    a.noter_seve()
    a.sauver(tmp_path / "arbre.json")
    b = Arbre.charger(tmp_path / "arbre.json")
    assert b.cime == "A" and b.battements == 1 and b.branches["A"].score == 50.8


def test_ajouter_un_horizon_sans_rien_perdre():
    import torch
    from collapsar.arbre.migration_horizons import etendre
    from collapsar.cerveau.reseau import Cerveau
    ancien = Cerveau(n_horizons=4)
    etat = ancien.state_dict()
    assert etendre(etat, 5) and not etendre(etat, 5)
    nouveau = Cerveau(n_horizons=5)
    nouveau.load_state_dict(etat)
    ancien.eval(), nouveau.eval()
    f, x = torch.randn(3, 6, 64, 6), torch.randn(3, 10)
    s4, a4, g4 = ancien(f, x)
    s5, a5, g5 = nouveau(f, x)
    assert torch.allclose(s4, s5[:, :4]) and torch.allclose(a4, a5[:, :4]) and torch.allclose(g4, g5[:, :4])
    assert torch.allclose(s5[:, 4], s4[:, 3]), "le 1 mois démarre de ce qu'elle pense à 1 semaine"


def test_porte_de_l_ecole():
    from collapsar.arbre import portes
    a = Arbre()
    a.naitre([], TEMPERAMENT_GRAINE)
    etat = {"ecole": {"ouverte": False, "verifications": []}}
    for s in (51.5, 51.8):
        a.noter("A", s)
    assert not portes.faut_il_verifier(a, etat), "moins de 3 notes / sous 52 % : pas de vérification"
    a.noter("A", 52.9)                                     # niveau (51,5 + 51,8 + 52,9) / 3 = 52,07
    assert portes.faut_il_verifier(a, etat)
    etat["ecole"]["verifications"].append({"cime": "A", "niveau": 52.07})
    assert not portes.faut_il_verifier(a, etat), "rien de nouveau depuis la dernière vérification"
    for s in (52.3, 52.4):
        a.noter("A", s)                                    # niveau 52,53 : +0,46 point -> on revérifie
    assert portes.faut_il_verifier(a, etat)
    etat["ecole"]["en_cours"] = {"depuis": datetime.now().isoformat(), "cime": "A", "niveau": 52.5}
    assert not portes.faut_il_verifier(a, etat), "une vérification est déjà en cours"
    etat["ecole"]["en_cours"]["depuis"] = (datetime.now() - timedelta(hours=3)).isoformat()
    assert portes.faut_il_verifier(a, etat), "une vérification bloquée depuis 3 h est relancée"
    etat["ecole"]["ouverte"] = True
    assert not portes.faut_il_verifier(a, etat) and "OUVERTE" in portes.resume(a, etat)


def test_mutation_reste_raisonnable():
    rng = random.Random(0)
    t = dict(TEMPERAMENT_GRAINE)
    for _ in range(200):
        t = Arbre.muter(t, rng)
        assert 3e-5 <= t["vitesse"] <= 3e-3 and 128 <= t["lot"] <= 2048 and 0 <= t["oubli"] <= 0.4


def test_les_images(tmp_path):
    a = Arbre(Reglages(jeunesse=1))
    a.naitre([], TEMPERAMENT_GRAINE, heure=_h(0))
    a.noter("A", 50.3, heure=_h(15), bonnes=50.1); a.noter_seve(_h(15))
    a.naitre(["A"], TEMPERAMENT_GRAINE, heure=_h(16))
    a.noter("B", 51.2, heure=_h(30), bonnes=50.6); a.noter_seve(_h(30))
    a.naitre(["A"], TEMPERAMENT_GRAINE, heure=_h(31))
    a.noter("C", 49.0, heure=_h(45)); a.noter_seve(_h(45))
    a.mourir("C", "coupée", heure=_h(46))
    f = a.naitre(["B", "A"], TEMPERAMENT_GRAINE, heure=_h(60))
    a.mourir("A", "fusion", heure=_h(60)); a.mourir("B", "fusion", heure=_h(60))
    a.noter(f.nom, 52.0, heure=_h(61), battement=False); a.noter_seve(_h(61))
    img = dessin.dessiner_arbre(a, tmp_path / "arbre.png", portes=[(_h(62), "compte à blanc")],
                                maintenant=datetime.fromisoformat(_h(75)))
    lignes = [{"quoi": "battement", "heure": _h(15 * k), "cime": "A", "cime_score": 50 + k / 3,
               "cime_bonnes": 50 + k / 5, "meme_reponse": 51.0} for k in range(1, 5)]
    courbe = dessin.dessiner_courbe(lignes, tmp_path / "courbe.png")
    assert img.stat().st_size > 10_000 and courbe.stat().st_size > 10_000
