"""LES TROIS CHANGEMENTS DE MAGNETAR (19/10/2026 après-midi, accord explicite du chef de projet), sur l'arbre ARRÊTÉ :

1. YEUX DE LA TENDANCE DE FOND (tendance.py) sur UNE branche « tendance » née de la cime : copie exacte de ses poids
   (journal et stops proches compris), 12 entrées ajoutées EN DERNIER, poids à ZÉRO (décisions identiques, prouvé).
2. STOP SUIVEUR QUI BOUGE APRÈS +1R (suiveur.py, simulateur.py) sur UNE autre branche « suiveur_1r » née de la cime :
   copie exacte + une tête de plus (options 1 h / 4 h / 1 agitation après +1R), poids à ZÉRO, penchant de départ vers ces
   options (biais calibré sur de vrais regards : ~70 % des ouvertures) ; les anciens gestes ne changent pas (prouvé).
3. EXAMEN TOURNANT pour tout l'arbre (tournant.py, réglage examen_tournant de reglages_or.yaml) : passage fait ici
   (réservoir écrit, notes de l'ancien examen mises de côté).
Organisation : cime intacte + « tendance » + « suiveur_1r » + la meilleure des autres (toutes gardent les stops proches
et le journal) ; les autres branches sont ARCHIVÉES (archives/). Preuves : vie/arbre_or/trois_changements/preuves.json.

Depuis Test_IA (arbre arrêté, ARRET en place) :
  $env:COLLAPSAR_PRECISION_REGLAGES="...\\collapsar\\ecole\\precision\\reglages_or.yaml"
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.trois_changements appliquer --sauvegarde <dossier>
Retour arrière : `... trois_changements defaire` (remet la vie de l'arbre ET reglages_or.yaml d'avant ; le code peut
rester : sans les réglages, il est inerte, empreintes identiques).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from collapsar.ecole.precision.reglages import R, VIE

FICHIER = "trois_changements.json"
FLAGS = ("tendance.json", "suiveur_1r.json", "tournant.json", "blocs_examen.json", FICHIER)


def _univers_preuve(appareil: str = "cpu"):
    """Un petit monde réel pour les preuves et le calibrage (l'or à la minute, réel et retourné, 2021)."""
    from collapsar.ecole.precision.univers import Univers
    return Univers([("XAUUSD@M1", False), ("XAUUSD@M1", True)], pd.Timestamp("2021-02-01"), pd.Timestamp("2021-10-01"),
                   appareil)


def _partie(U, net, B=64, bougies=400, graine=1):
    """Une partie entière (table, journal, ordres, simulateur, réveils) : gestes, log-probabilités, valeurs, comptes."""
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import journal_trading as JN
    tb = JEU.Table(U, B, 1)
    JN.equiper(tb, net, "ecole")
    rng = np.random.default_rng(0)
    ok = np.flatnonzero(U.premier < U.T - bougies - 200)
    cols = rng.choice(ok, B)[:, None]
    tb.demarrer(np.ones(B, bool), cols, np.asarray([rng.integers(U.premier[c], U.T - bougies - 100) for c in cols[:, 0]]))
    dec = JEU.Decideur(tb, net, evaluer=True, graphe=False)
    torch.manual_seed(graine)
    c = tb.cpt
    gestes, lps, vals, suiv = [], [], [], []
    for _ in range(bougies):
        qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
        if len(qui):
            (choix, lp, _, _, valeur, _), _, paquet = dec(qui)
            k = len(qui)
            gestes.append(choix["geste"][:k].clone())
            lps.append(lp[:k].clone())
            vals.append(valeur[:k].clone())
            g = JEU.niveaux_np(paquet[:, :k])
            suiv.append(torch.as_tensor(g["suiveur_u"]))
            tb.appliquer(qui, g)
        tb.avancer()
        c.actif &= ~(c.mort | c.reussi)
    return {"gestes": torch.cat(gestes), "lp": torch.cat(lps), "valeurs": torch.cat(vals), "suiveur": torch.cat(suiv),
            "comptes": c.valeurs().copy(), "trades": int(np.isfinite(c.r_ferme).sum())}


def _egales(a: dict, b: dict) -> dict:
    """Décisions (gestes, options du suiveur, comptes à la fin) : EXACTEMENT égales ; probabilités et valeurs : écart
    maximal (l'entrée agrandie d'une 1re couche change l'ordre des additions de la machine : arrondis de 1e-7)."""
    out = {k: bool(torch.equal(a[k], b[k]) if isinstance(a[k], torch.Tensor) else np.array_equal(a[k], b[k]))
           for k in ("gestes", "suiveur", "comptes")}
    for k in ("lp", "valeurs"):
        out[f"ecart_max_{k}"] = float((a[k].double() - b[k].double()).abs().max()) if len(a[k]) == len(b[k]) else 1e9
    return out


def _decisions_egales(x: dict, lp: bool = True) -> bool:
    return (x["gestes"] and x["suiveur"] and x["comptes"] and x["ecart_max_valeurs"] < 1e-4
            and (not lp or x["ecart_max_lp"] < 1e-4))


def prouver_tendance(cime, tend, U) -> dict:
    """Mêmes décisions, même partie : la cime et la branche « tendance » (12 entrées à zéro, qu'elle VOIT)."""
    a, b = _partie(U, cime), _partie(U, tend)
    vu = float((U.tTEND != 0).float().mean())
    return {"identique": _egales(a, b), "regards": int(len(a["gestes"])),
            "ouvertures": int(((a["gestes"] >= 1) & (a["gestes"] <= 4)).sum()), "part_valeurs_tendance_non_nulles": vu}


def prouver_suiveur_1r(cime, s1r, U) -> dict:
    """(1) le tirage du suiveur rendu sans hasard (le meilleur des ANCIENNES options) : la partie de la branche
    « suiveur_1r » est EXACTEMENT celle de la cime ; (2) un regard à graine égale avec son vrai penchant : tous les autres
    gestes, niveaux et probabilités identiques, seule l'option du suiveur change ; part des options après +1R."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import journal_trading as JN
    from collapsar.ecole.precision import suiveur as SV
    n_s = cime.n_suiv
    tirer = C.Loi.tirer

    def sans_hasard(self):
        if self.logits.shape[-1] in (n_s, n_s + s1r.n_suiv1r):
            return self.logits[..., :n_s].argmax(-1)
        return tirer(self)
    C.Loi.tirer = sans_hasard
    try:
        a, b = _partie(U, cime), _partie(U, s1r)
    finally:
        C.Loi.tirer = tirer
    out = {"partie_sans_hasard_du_suiveur_identique": _egales(a, b), "regards": int(len(a["gestes"])),
           "ouvertures": int(((a["gestes"] >= 1) & (a["gestes"] <= 4)).sum())}
    # un regard de 512 comptes, graine égale
    res = []
    for net in (cime, s1r):
        tb = JEU.Table(U, 512, 1)
        JN.equiper(tb, net, "ecole")
        rng = np.random.default_rng(3)
        ok = np.flatnonzero(U.premier < U.T - 96 * 70)
        cols = rng.choice(ok, 512)[:, None]
        tb.demarrer(np.ones(512, bool), cols, np.asarray([rng.integers(U.premier[c], U.T - 96 * 65) for c in cols[:, 0]]))
        torch.manual_seed(11)
        with torch.no_grad():
            (choix, lp, lpe, hasard, valeur, lv), (t, cols_, fc, pos) = tb.regarder(net, np.arange(512))
            s = tb.vue.structure(t, cols_)                   # (pos : déjà complète, journal compris)
            h, _ = net.corps(torch.cat([tb.vue.caracteristiques(s), pos], -1), fc, s["slot"])
            tetes = (net.tetes(h), net.suiv(h)[..., :net.n_suiv], net.suiv(h)[..., net.n_suiv:])
        res.append((choix, lv, valeur, tetes))
    (c0, l0, v0, t0), (c1, l1, v1, t1) = res
    autres = {k: bool(torch.equal(c0[k], c1[k])) for k in c0 if k != "suiveur"}
    niv = {k: bool(torch.equal(torch.nan_to_num(l0[k].float(), nan=-7.0), torch.nan_to_num(l1[k].float(), nan=-7.0)))
           for k in l0 if not k.startswith("suiveur")}
    ouvre = (c1["geste"] >= 1) & (c1["geste"] <= 4)
    out.update({"un_regard_autres_choix_identiques": autres, "un_regard_niveaux_identiques": niv,
                "un_regard_valeur_identique": bool(torch.equal(v0, v1)),
                "anciennes_tetes_identiques": bool(all(torch.equal(x, y) for x, y in zip(t0, t1))),
                "part_ouvertures_apres_1r_pct": float((c1["suiveur"][ouvre] >= s1r.n_suiv).float().mean() * 100),
                "part_ouvertures_suiveur_cime_pct": float((c0["suiveur"][(c0["geste"] >= 1) & (c0["geste"] <= 4)] > 0)
                                                          .float().mean() * 100),
                "options_1r": [x[2] for x in SV.options_1r()]})
    return out


def _tout_vrai(x) -> bool:
    if isinstance(x, dict):
        return all(_tout_vrai(v) for v in x.values())
    return bool(x) if isinstance(x, bool) else True


def appliquer(dossier: Path | None = None, sauvegarde: Path | None = None, dire=print) -> dict:
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import journal_trading as JN
    from collapsar.ecole.precision import suiveur as SV
    from collapsar.ecole.precision import tendance as TD
    from collapsar.ecole.precision import tournant as TN
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if (dossier / FICHIER).exists():
        raise SystemExit(f"{dossier} : les trois changements sont déjà faits ({FICHIER})")
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : créer ARRET et attendre sa fin")
    if not (dossier / "ARRET").exists():
        raise SystemExit(f"{dossier / 'ARRET'} doit être en place pendant la manipulation")
    if not (TD.active() and SV.active_1r() and TN.active()):
        raise SystemExit("réglages de l'or attendus : yeux.tendance, mains.suiveur_1r, examen_tournant")
    JN._allumer_comme_l_arbre(dossier)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if sauvegarde is None:                               # sauvegarde de la vie de l'arbre (le code : à faire avant)
        sauvegarde = dossier / "sauvegardes" / f"avant_tendance_suiveur_tournant_{stamp}"
        shutil.copytree(dossier, sauvegarde / "vie", ignore=shutil.ignore_patterns(
            "journal_trades", "sauvegardes", "precision", "contrefactuel"))
    sauvegarde = Path(sauvegarde).resolve()
    assert (sauvegarde / "vie" / "arbre.json").exists(), sauvegarde
    out = dossier / "trois_changements"
    out.mkdir(exist_ok=True)
    arbre = Arbre.charger(dossier / "arbre.json")
    cime = arbre.cime
    autres = sorted([b for b in arbre.vivantes() if b.nom != cime and b.score is not None], key=lambda b: -b.score)
    garder = autres[0].nom
    archivees = [b.nom for b in arbre.vivantes() if b.nom not in (cime, garder)]
    dire(f"cime {cime} intacte ; meilleure des autres : {garder} (niveau {autres[0].score:+.2f}) ; archivées : "
         + ", ".join(f"{n} ({arbre.branches[n].score:+.2f})" if arbre.branches[n].score is not None else f"{n} (née)"
                     for n in archivees))
    journal = Journal(dossier / "journal_croissance.jsonl")
    e = torch.load(dossier / "branches" / f"{cime}.pt", map_location="cpu", weights_only=False)
    tc = dict(e.get("temperament") or arbre.branches[cime].temperament)
    tc.pop("alertes", None)
    vitesse = float(tc.get("vitesse", R().ecole.vitesse))
    cime_net = C.regler_precision(C.cerveau_pour(e["cerveau"]), tc)
    U = _univers_preuve()
    # ---- 1. branche « tendance »
    t1 = {**tc, "nom": "tendance", "tendance": {"version": TD.VERSION, "entrees": TD.NTD, "noms": list(TD.NOMS)},
          "heritage": f"cime {cime}, yeux de la tendance de fond 20/60/120 j (poids à zéro, {stamp})"}
    tend = C.regler_precision(C.cerveau_pour(TD.etat_avec_tendance(e["cerveau"])), t1)
    assert tend.n_tendance == TD.NTD and tend.n_journal == cime_net.n_journal
    p1 = prouver_tendance(cime_net, tend, U)
    dire(f"preuve tendance : {p1}")
    # ---- 2. branche « suiveur_1r »
    s1r = C.Cerveau(journal=bool(cime_net.n_journal), delai=cime_net.journal_delai, suiveur_1r=True)
    s1r.load_state_dict(C.adapter(e["cerveau"], s1r))
    C.regler_precision(s1r, tc)
    cible = float(getattr(R().mains, "suiveur_1r_depart_pct", 70.0))
    biais, part = SV.calibrer_1r(s1r, U, cible)
    dire(f"suiveur après +1R : biais de départ {biais:+.3f} -> {part:.0f} % des ouvertures (cible {cible:.0f} %)")
    t2 = {**tc, "nom": "suiveur_1r", "suiveur_1r": {"version": 1, "options": [x[2] for x in SV.options_1r()],
                                                    "depart_pct": cible, "biais": biais, "part_mesuree_pct": part},
          "heritage": f"cime {cime}, stop suiveur après +1R (1 h / 4 h / 1 agitation, {stamp})"}
    p2 = prouver_suiveur_1r(cime_net, s1r, U)
    dire(f"preuve suiveur après +1R : {p2}")
    preuves = {"tendance": p1, "suiveur_1r": p2, "monde": "XAUUSD@M1 réel + retourné, 02/2021 -> 10/2021 (processeur)"}
    (out / "preuves.json").write_text(json.dumps(preuves, ensure_ascii=False, indent=1), encoding="utf-8")
    # (suiveur après +1R : la probabilité du choix du suiveur change par construction, le penchant ; pas les décisions)
    ok = (_decisions_egales(p1["identique"]) and _decisions_egales(p2["partie_sans_hasard_du_suiveur_identique"], False)
          and _tout_vrai(p2["un_regard_autres_choix_identiques"]) and _tout_vrai(p2["un_regard_niveaux_identiques"])
          and p2["un_regard_valeur_identique"] and p2["anciennes_tetes_identiques"])
    if not ok:
        raise SystemExit(f"PREUVE RATÉE (rien n'est changé dans l'arbre) : {preuves}")
    for n in archivees:
        arbre.mourir(n, "coupée")
        for f in (f"{n}.pt", f"{n}_meilleur.pt"):
            if (dossier / "branches" / f).exists():
                shutil.move(str(dossier / "branches" / f), str(dossier / "archives" / f))
        journal.ecrire("coupe", branche=n, raison="archivée (trois changements du 19/10 : place pour « tendance » et "
                                                  "« suiveur_1r »)")
    nes = {}
    for t, net in ((t1, tend), (t2, s1r)):
        b = arbre.naitre([cime], t)
        opt = torch.optim.AdamW(net.parameters(), lr=vitesse, weight_decay=1e-4)
        tmp = dossier / "branches" / f"{b.nom}.pt.tmp"
        torch.save({"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": t}, tmp)
        os.replace(tmp, dossier / "branches" / f"{b.nom}.pt")
        journal.ecrire("naissance", branche=b.nom, parents=[cime], temperament=t, heritage=t["heritage"])
        nes[t["nom"]] = b.nom
        dire(f"branche {b.nom} « {t['nom']} » née de la cime {cime}")
    arbre._elire_cime()
    arbre.sauver(dossier / "arbre.json")
    fx = dossier / "derniers_examens.json"
    if fx.exists():
        x = json.loads(fx.read_text(encoding="utf-8"))
        for n in archivees:
            x.pop(n, None)
        fx.write_text(json.dumps(x, ensure_ascii=False, default=float), encoding="utf-8")
    info = {"date": datetime.now().isoformat(timespec="seconds"), "cime": cime, "gardee": garder,
            "archivees": archivees, "nees": nes, "sauvegarde": str(sauvegarde), "preuves": str(out / "preuves.json")}
    (dossier / "tendance.json").write_text(json.dumps({**info, "branche": nes["tendance"], "version": TD.VERSION,
                                                       "noms": list(TD.NOMS)}, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    (dossier / "suiveur_1r.json").write_text(json.dumps({**info, "branche": nes["suiveur_1r"], **t2["suiveur_1r"]},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")
    journal.ecrire("trois_changements", **{k: v for k, v in info.items() if k != "date"})
    # ---- 3. examen tournant : passage (réservoir écrit, notes de l'ancien examen mises de côté)
    TN.passer(dossier, dire)
    (dossier / FICHIER).write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def defaire(dossier: Path | None = None, dire=print):
    """Retour arrière (arbre arrêté) : la vie de l'arbre d'avant (sauvegarde) et reglages_or.yaml d'avant (code_avant)."""
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : l'arrêter d'abord (fichier ARRET)")
    info = json.loads((dossier / FICHIER).read_text(encoding="utf-8"))
    sauve = Path(info["sauvegarde"])
    shutil.rmtree(dossier / "branches")
    shutil.copytree(sauve / "vie" / "branches", dossier / "branches")
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (sauve / "vie" / nom).exists():
            shutil.copy2(sauve / "vie" / nom, dossier / nom)
    for n in info["archivees"]:
        for f in (f"{n}.pt", f"{n}_meilleur.pt"):
            (dossier / "archives" / f).unlink(missing_ok=True)
    for f in FLAGS:
        (dossier / f).unlink(missing_ok=True)
    ya = sauve / "code_avant" / "ecole_precision" / "reglages_or.yaml"
    if ya.exists():
        from collapsar.ecole.precision import reglages as RG
        shutil.copy2(ya, RG.DEFAUT.with_name("reglages_or.yaml"))
        dire("reglages_or.yaml d'avant remis")
    dire(f"trois changements défaits : état remis depuis {sauve}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="trois changements de MAGNETAR (19/10)")
    ap.add_argument("quoi", choices=["appliquer", "defaire"])
    ap.add_argument("--dossier", default=None)
    ap.add_argument("--sauvegarde", default=None)
    a = ap.parse_args(argv)
    d = Path(a.dossier) if a.dossier else None
    if a.quoi == "appliquer":
        appliquer(d, Path(a.sauvegarde) if a.sauvegarde else None)
    else:
        defaire(d)


if __name__ == "__main__":
    main()
