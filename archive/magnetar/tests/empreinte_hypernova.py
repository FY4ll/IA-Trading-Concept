"""EMPREINTE D'HYPERNOVA (18/10/2026) : ce que fait le code de l'école de la précision avec les réglages d'HYPERNOVA
(reglages.yaml), sur un marché inventé, calculé UNE fois avec le code d'AVANT le stop suiveur de l'arbre de l'or
(fichier donnees/empreinte_hypernova.npz) puis comparé à chaque passage des tests (test_suiveur.py) : simulateur avec
ordres au hasard (marché, limites, objectif 1, parts), décisions d'un cerveau à travers la table, une leçon et un pas
d'apprentissage, un examen avec son jumeau. Tout doit rester EXACTEMENT identique.

Création (une seule fois, code d'avant) : depuis Test_IA,
  $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m collapsar.tests.empreinte_hypernova ecrire
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

FICHIER = Path(__file__).with_name("donnees") / "empreinte_hypernova.npz"


def _donnees_inventees():
    sys.path.insert(0, str(Path(__file__).parent))
    from test_ecole_precision import chemin_minutes
    from collapsar.ecole.precision import donnees as D
    from collapsar.ecole.precision import structure as S
    from collapsar.ecole.precision.reglages import R, UNITES_15
    m = chemin_minutes(220, 11, depart="2019-01-07")
    q = D.reechantillonner(m, "15min")
    t15 = q["time"].values.astype("datetime64[ns]").astype(np.int64)
    s = S.calculer(t15, *(q[k].to_numpy(float) for k in ("open", "high", "low", "close")), None, UNITES_15,
                   R().yeux.zones_par_cote, q)
    x = {"t15": t15, "o": s["o"], "h": s["h"], "l": s["l"], "c": s["c"], "A": s["A"], "demi": np.full(len(t15), 3e-5)}
    for u in UNITES_15:
        x[u] = {k: v for k, v in s[u].items() if k not in ("ne", "fin", "debut_u")}
    return x


def _simulateur_au_hasard() -> dict:
    from collapsar.ecole.precision import simulateur as SIM
    from test_ecole_precision import univers_minimal
    rng = np.random.default_rng(17)
    T, B = 1500, 64
    x = 100 + np.cumsum(rng.normal(0, 0.05, (T, 4)), 0).reshape(T, 4)
    o = np.r_[100.0, x[:-1, -1]]
    U = univers_minimal(o, np.maximum(x.max(1), o), np.minimum(x.min(1), o), x[:, -1], jour=np.arange(T) // 96,
                        nuits=(np.arange(T) % 96 == 0).astype(float), demi=2e-4, nuit_achat=0.03)
    cp = SIM.Comptes(U, B, 1)
    cp.recommencer(np.ones(B, bool), np.zeros((B, 1), np.int64), np.zeros(B, np.int64))
    soldes, evts, rs = [], [], []
    for t in range(T - 2):
        a = rng.random(B)
        plat = (cp.u[:, 0] == 0) & (cp.att[:, 0] == 0)
        p = U.c[cp.t, 0]
        sens = np.where(rng.random(B) < 0.5, -1.0, 1.0)
        act = np.where(plat & (a < 0.03), SIM.MARCHE, np.where(plat & (a < 0.06), SIM.LIMITE,
                                                                np.where(~plat & (a < 0.07), SIM.FERMER, SIM.RIEN)))
        cp.ord_act[:, 0] = act
        cp.ord_u[:, 0] = sens * 300
        e = np.where(act == SIM.LIMITE, p - sens * rng.uniform(0.02, 0.2, B), p)
        cp.ord_prix[:, 0] = e
        cp.ord_stop[:, 0] = e - sens * rng.uniform(0.1, 0.6, B)
        cp.ord_tp1[:, 0] = np.where(rng.random(B) < 0.6, e + sens * rng.uniform(0.1, 0.5, B), np.nan)
        cp.ord_part[:, 0] = rng.choice([0.0, 0.5, 0.8], B)
        cp.ord_dest[:, 0] = np.where(rng.random(B) < 0.5, e + sens * rng.uniform(0.5, 2.0, B), np.nan)
        cp.ord_duree[:, 0] = rng.choice([16, 96], B)
        cp.pas(1.0)
        soldes.append(cp.solde.copy())
        evts.append(cp.evt[:, 0].copy())
        rs.append(np.nan_to_num(cp.r_ferme[:, 0], nan=-999.0))
        cp.mort[:] = False
    return {"sim_solde": np.asarray(soldes), "sim_evt": np.asarray(evts), "sim_r": np.asarray(rs)}


def calculer() -> dict:
    """Toutes les mesures de l'empreinte (réglages d'HYPERNOVA, processeur)."""
    sys.path.insert(0, str(Path(__file__).parent))
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import reglages as RG
    from collapsar.ecole.precision import structure as S
    from collapsar.ecole.precision.reglages import R
    from collapsar.ecole.precision.univers import Univers
    assert RG.NOM == "HYPERNOVA", "l'empreinte se calcule avec les réglages d'HYPERNOVA"
    torch.set_num_threads(1)
    out = _simulateur_au_hasard()
    x = _donnees_inventees()
    lire = S.lire
    S.lire = lambda nom, mir: x
    try:
        U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
        # 1. décisions d'un cerveau à travers la table (choix tirés, ordres, simulateur)
        torch.manual_seed(0)
        net = C.Cerveau()
        B = 48
        tb = JEU.Table(U, B, 1)
        rng = np.random.default_rng(0)
        dep = rng.integers(U.premier[0], U.T - 900, B)
        tb.demarrer(np.ones(B, bool), np.zeros((B, 1), np.int64), dep)
        dec = JEU.Decideur(tb, net, evaluer=True, graphe=False)
        torch.manual_seed(1)
        gestes, lps, stops = [], [], []
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
            tb.avancer()
            c.actif &= ~(c.mort | c.reussi)
        out["table_valeurs"] = tb.cpt.valeurs()
        out["table_gestes"] = np.concatenate(gestes)
        out["table_lp"] = np.concatenate(lps)
        out["table_stops"] = np.concatenate(stops)
        # 2. une leçon et un pas d'apprentissage
        torch.manual_seed(2)
        net2 = C.Cerveau()
        opt = torch.optim.AdamW(net2.parameters(), lr=3e-4, weight_decay=1e-4)
        lecon = JEU.Lecon(U, 32, np.random.default_rng(3))
        torch.manual_seed(3)
        m, b = lecon.jouer(net2, 96)
        a = JEU.apprendre(net2, opt, lecon.table, m, 1, 256, 0.2, 0.003)
        out["lecon_bilan"] = np.array([b[k] for k in sorted(b)], float)
        out["lecon_adv"] = m["adv"].numpy()
        out["apprendre"] = np.array([a[k] for k in sorted(a)], float)
        out["poids_apres"] = torch.cat([p.detach().flatten() for p in net2.parameters()]).numpy()
        # 3. un examen (elle et son jumeau)
        r = R()
        ancien = r.monde.challenge_jours
        r.monde.challenge_jours = 10
        try:
            ex = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 10)
            xe = ex.jouer_un(net2, 5)
        finally:
            r.monde.challenge_jours = ancien
        out["examen_notes"] = np.asarray(xe["notes"], float)
        out["examen_gains"] = np.asarray(xe["gains_pct_mois"], float)
        out["examen_jumeau"] = np.array([xe["jumeau"]["gain_pct_mois"], xe["jumeau"]["trades_mois"],
                                         xe["trades_mois"], xe["r_moyen"] if np.isfinite(xe["r_moyen"]) else -999.0])
        out["examen_cles"] = np.array(sorted(xe.keys()))
    finally:
        S.lire = lire
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["ecrire"]:
        if FICHIER.exists():
            raise SystemExit(f"{FICHIER} existe déjà (empreinte du code d'avant) : ne pas la refaire")
        FICHIER.parent.mkdir(parents=True, exist_ok=True)
        out = calculer()
        np.savez_compressed(FICHIER, **out)
        print(f"empreinte écrite : {FICHIER} ({', '.join(f'{k} {np.shape(v)}' for k, v in out.items())})")
    else:
        ref = np.load(FICHIER)
        out = calculer()
        for k in ref.files:
            print(k, "identique" if np.array_equal(ref[k], out[k], equal_nan=ref[k].dtype.kind == "f") else "DIFFÉRENT")


if __name__ == "__main__":
    main()
