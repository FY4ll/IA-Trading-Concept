"""EMPREINTE DE MAGNETAR (18/10/2026, avant le journal de trading) : ce que fait le code de l'école de la précision avec
les réglages de l'ARBRE DE L'OR (reglages_or.yaml : stop suiveur allumé, yeux de la foule allumés comme l'arbre greffé)
et la VRAIE CIME de MAGNETAR (copie figée tests/donnees/cime_magnetar_18oct.pt, cime de la génération 68), sur un
marché inventé. Calculée UNE fois avec le code d'AVANT le journal de trading (tests/donnees/empreinte_magnetar.npz),
puis comparée à chaque passage des tests (test_journal_trading.py) : décisions de la cime à travers la table
(ordres, simulateur, réveils), une leçon et un pas d'apprentissage, un examen avec son jumeau. Tout doit rester
EXACTEMENT identique tant que le journal n'est pas greffé.

Toujours lancé dans un programme à part (les réglages de l'or se choisissent avant tout import) :
  $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m collapsar.tests.empreinte_magnetar ecrire
  (comparer : même commande avec « comparer »)

19/10/2026 : MAGNETAR passe au COMPTE SWING (reglages_or.yaml, mains.compte) et mesure ses sorties
(selection.mesurer_sorties). « comparer » calcule l'empreinte RÈGLES SWING MISES À PART (compte « normal », mesure des
sorties éteinte) : elle doit rester IDENTIQUE à celle du 18/10 (preuve que rien d'autre ne change pour les branches non
greffées). « swing » calcule avec les vrais réglages (compte Swing) et la compare à empreinte_magnetar_swing.npz
(écrite une fois le 19/10 par « ecrire_swing ») ; « diff_swing » montre ce que le Swing change par rapport au 18/10.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REGLAGES_OR = Path(__file__).resolve().parents[1] / "ecole" / "precision" / "reglages_or.yaml"
if __name__ == "__main__":
    os.environ["COLLAPSAR_PRECISION_REGLAGES"] = str(REGLAGES_OR)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

DONNEES = Path(__file__).with_name("donnees")
FICHIER = DONNEES / "empreinte_magnetar.npz"
FICHIER_SWING = DONNEES / "empreinte_magnetar_swing.npz"
CIME = DONNEES / "cime_magnetar_18oct.pt"


def calculer(swing: bool = False, nouveautes: bool = False, corrections: bool = False) -> dict:
    """swing=False : règles Swing mises à part (compte « normal », sans mesure des sorties) ; True : vrais réglages.
    19/10 (trois changements) : la tendance de fond (yeux.tendance), le suiveur après +1R (mains.suiveur_1r) et la mesure
    de la tenue (selection.mesurer_tenue) sont MIS À PART sauf si nouveautes=True (la cime figée n'a ni la tendance ni
    la tête du suiveur après +1R : ses décisions doivent rester les mêmes avec ces réglages allumés)."""
    from collapsar.ecole.precision.reglages import R
    r = R()
    # 19/10 soir : l'apprentissage apparié (ecole.apprentissage_apparie : réel ET retourné aux mêmes départs) est MIS À
    # PART : le monde inventé de l'empreinte n'a qu'un sens ; il ne change aucune décision (testé à part,
    # tests/test_trois_changements.py::test_apprentissage_apparie_reel_et_retourne)
    r.ecole.apprentissage_apparie = False
    # 20/10 (CORRECTIONS GRAVES de l'audit) : ordre limite plafonné à 1,5 agitation, ordre en attente remplaçable, frais
    # honnêtes, note au gain réel, mesure des exécutions : MIS À PART ici (ils CHANGENT ses décisions et ses résultats,
    # c'est voulu ; testés à part, tests/test_corrections_graves.py ; « diff_corrections » montre ce qu'ils changent)
    if not corrections:
        r.mains.entree_max_agitation = 6.0
        r.mains.marche_annule_ordre = False
        r.frais_honnetes = None
        r.note.gain_reel = False
        r.note.reussite_contre_jumeau = False
        r.selection.mesurer_executions = False
    if not nouveautes:
        r.yeux.tendance = False
        r.mains.suiveur_1r = False
        r.selection.mesurer_tenue = False
    if not swing:
        r.mains.compte = "normal"
        r.selection.mesurer_sorties = False
    else:
        assert r.mains.compte == "swing", "reglages_or.yaml : mains.compte doit être « swing »"
    return _calculer()


def _calculer() -> dict:
    sys.path.insert(0, str(Path(__file__).parent))
    from empreinte_hypernova import _donnees_inventees
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import foule as FO
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import reglages as RG
    from collapsar.ecole.precision import structure as S
    from collapsar.ecole.precision import suiveur as SV
    from collapsar.ecole.precision.reglages import R
    from collapsar.ecole.precision.univers import Univers
    assert RG.NOM == "MAGNETAR", "l'empreinte se calcule avec les réglages de l'arbre de l'or"
    FO.activer()                                     # comme l'arbre greffé (foule.json)
    assert SV.active()
    torch.set_num_threads(1)
    etat = torch.load(CIME, map_location="cpu", weights_only=False)["cerveau"]
    out = {}
    x = _donnees_inventees()
    lire = S.lire
    S.lire = lambda nom, mir: x
    try:
        U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
        # 1. décisions de la cime à travers la table (choix tirés, ordres, simulateur, stop suiveur)
        net = C.Cerveau()
        net.load_state_dict(etat)
        B = 48
        tb = JEU.Table(U, B, 1)
        rng = np.random.default_rng(0)
        dep = rng.integers(U.premier[0], U.T - 900, B)
        tb.demarrer(np.ones(B, bool), np.zeros((B, 1), np.int64), dep)
        dec = JEU.Decideur(tb, net, evaluer=True, graphe=False)
        torch.manual_seed(1)
        gestes, lps, stops, suiv = [], [], [], []
        for _ in range(700):
            c = tb.cpt
            qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
            if len(qui):
                (choix, lp, _, hasard, valeur, lv), _, paquet = dec(qui)
                g = JEU.niveaux_np(paquet[:, :len(qui)])
                tb.appliquer(qui, g)
                gestes.append(choix["geste"][:len(qui)].numpy().ravel())
                lps.append(lp[:len(qui)].numpy())
                stops.append(np.nan_to_num(g["stop"].ravel(), nan=-1.0))
                suiv.append(g["suiveur_u"].ravel())
            tb.avancer()
            c.actif &= ~(c.mort | c.reussi)
        out["table_valeurs"] = tb.cpt.valeurs()
        out["table_gestes"] = np.concatenate(gestes)
        out["table_lp"] = np.concatenate(lps)
        out["table_stops"] = np.concatenate(stops)
        out["table_suiveur"] = np.concatenate(suiv)
        # 2. une leçon et un pas d'apprentissage (copie de la cime)
        net2 = C.Cerveau()
        net2.load_state_dict(etat)
        opt = torch.optim.AdamW(net2.parameters(), lr=3e-4, weight_decay=1e-4)
        lecon = JEU.Lecon(U, 32, np.random.default_rng(3))
        torch.manual_seed(3)
        m, b = lecon.jouer(net2, 96)
        a = JEU.apprendre(net2, opt, lecon.table, m, 1, 256, 0.2, 0.003)
        out["lecon_bilan"] = np.array([b[k] for k in sorted(b)], float)
        out["lecon_adv"] = m["adv"].numpy()
        out["apprendre"] = np.array([a[k] for k in sorted(a)], float)
        out["poids_apres"] = torch.cat([p.detach().flatten() for p in net2.parameters()]).numpy()
        # 3. un examen de la cime (elle et son jumeau)
        r = R()
        ancien = r.monde.challenge_jours
        r.monde.challenge_jours = 10
        try:
            ex = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 10)
            xe = ex.jouer_un(net, 5)
        finally:
            r.monde.challenge_jours = ancien
        out["examen_notes"] = np.asarray(xe["notes"], float)
        out["examen_gains"] = np.asarray(xe["gains_pct_mois"], float)
        out["examen_jumeau"] = np.array([xe["jumeau"]["gain_pct_mois"], xe["jumeau"]["trades_mois"],
                                         xe["trades_mois"], xe["r_moyen"] if np.isfinite(xe["r_moyen"]) else -999.0,
                                         xe.get("suiveur_pct", -1.0)])
        out["examen_cles"] = np.array(sorted(xe.keys()))
    finally:
        S.lire = lire
    return out


def _ecart(a, b) -> str:
    """Ce qui change entre deux mesures (pour « diff_swing »)."""
    if np.shape(a) != np.shape(b):
        return f"taille {np.shape(a)} -> {np.shape(b)}"
    if a.dtype.kind in "fi":
        a_, b_ = np.asarray(a, float), np.asarray(b, float)
        dif = ~np.isclose(a_, b_, equal_nan=True)
        return f"{int(dif.sum())} valeurs sur {a_.size} changent (écart max {np.nanmax(np.abs(a_ - b_)) if dif.any() else 0:.4g})"
    return f"{sorted(set(map(str, b.ravel())) - set(map(str, a.ravel())))} en plus"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] in (["ecrire"], ["ecrire_swing"]):
        swing = argv[0] == "ecrire_swing"
        f = FICHIER_SWING if swing else FICHIER
        if f.exists():
            raise SystemExit(f"{f} existe déjà : ne pas la refaire")
        out = calculer(swing)
        np.savez_compressed(f, **out)
        print(f"empreinte écrite : {f} ({', '.join(f'{k} {np.shape(v)}' for k, v in out.items())})")
        return 0
    if argv[:1] in (["diff_swing"], ["diff_corrections"]):   # ce que le Swing (réf. 18/10) / les corrections changent
        corr = argv[0] == "diff_corrections"
        ref = np.load(FICHIER_SWING if corr else FICHIER)
        out = calculer(True, corr, corr)
        for k in ref.files:
            same = np.shape(ref[k]) == np.shape(out[k]) and np.array_equal(ref[k], out[k], equal_nan=ref[k].dtype.kind == "f")
            print(k, "identique" if same else "change : " + _ecart(ref[k], out[k]))
        return 0
    swing = argv[:1] in (["swing"], ["nouveautes"])
    nouv = argv[:1] == ["nouveautes"]
    ref = np.load(FICHIER_SWING if swing else FICHIER)
    out = calculer(swing, nouv)
    if nouv:
        # « nouveautes » (19/10) : vrais réglages de l'or AVEC tendance, suiveur après +1R et mesure de la tenue : toutes
        # les décisions et tous les résultats identiques à l'empreinte Swing ; l'examen rapporte seulement des clés EN PLUS
        cles = set(map(str, out["examen_cles"]))
        assert set(map(str, ref["examen_cles"])) <= cles, "clés de l'examen perdues"
        print("clés de l'examen en plus :", sorted(cles - set(map(str, ref["examen_cles"]))))
        out["examen_cles"] = ref["examen_cles"]
    diff = [k for k in ref.files if not (np.shape(ref[k]) == np.shape(out[k]) and
                                         np.array_equal(ref[k], out[k], equal_nan=ref[k].dtype.kind == "f"))]
    for k in ref.files:
        print(k, "DIFFERENT" if k in diff else "identique")
    print("RESULTAT", "IDENTIQUE" if not diff else "DIFFERENT")
    return 1 if diff else 0


if __name__ == "__main__":
    raise SystemExit(main())
