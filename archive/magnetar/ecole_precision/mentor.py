"""LE MENTOR DE MAGNETAR (19/10/2026, ordre du chef de projet) : un programme FIXE qui trade selon la logique du chef,
écrit et figé AVANT d'être mesuré (`vie/arbre_or/mentor/plan_fige.md`, version 1), puis une branche « apprentie » qui
l'IMITE d'abord, et le DÉPASSE ensuite par la récompense « en laisse ».

1. LE MENTOR (`decider`) s'exprime avec les MÊMES GESTES que les mains de MAGNETAR (cerveau.py) : à chaque regard, un
   geste (rien / ordre limite d'achat ou de vente / fermer), et pour une ouverture : l'entrée (bord proche d'une de ses
   zones), le stop (bord lointain de la même zone) + une marge, la destination « laisser courir », la part à l'objectif 1
   (0 %), le risque (0,5 %), la validité de l'ordre (4 h), le stop suiveur (« 4 h après +1R »), et le délai avant de
   revenir regarder (prochaine clôture de 4 h). Ses choix sont des NUMÉROS dans les listes des mains : la branche peut
   les reproduire exactement (testé : mêmes niveaux que cerveau.politique avec ces numéros).
   Règles (plan figé) : décision seulement quand une bougie de 4 h s'est terminée depuis le regard précédent ; sens = les
   signes 20 / 60 / 120 jours de la tendance de fond (tendance.py) identiques, sinon rien ; entrée = la zone vivante la
   plus proche dans le sens, 4 h puis 1 h, TOUCHÉE puis avec RÉACTION, hauteur + 0,05 agitation <= 0,4 agitation ; stop
   juste derrière ; laisser courir ; position jamais fermée à la main ; ordre annulé si la tendance n'est plus d'accord.
   Son JUMEAU au hasard : mêmes moments et mêmes gestes, sens tiré à pile ou face (aucune zone de ce côté : rien).
2. LA MESURE (`mesurer`) : le juge habituel de l'arbre (examen tournant 28 blocs x 8 parties, or réel et retourné ;
   contrôle 01/2024 -> 09/2025, jumeau tiré 8 fois). Rien après 09/2025.
3. L'APPRENTIE (`appliquer`, `imiter`, `apprendre_en_laisse`) : voir plus bas.

Depuis Test_IA (réglages de l'or) :
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.mentor mesurer [--variante v1] [--appareil cuda]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if __name__ == "__main__" and not os.environ.get("COLLAPSAR_PRECISION_REGLAGES"):
    # lancé seul : les réglages de l'arbre de l'or (comme arbre_or.py), AVANT tout import des réglages
    if "collapsar.ecole.precision.reglages" in sys.modules:
        raise SystemExit("mentor : les réglages d'un autre arbre sont déjà chargés")
    os.environ["COLLAPSAR_PRECISION_REGLAGES"] = str(Path(__file__).with_name("reglages_or.yaml"))

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from datetime import datetime  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

from collapsar.ecole.precision.reglages import CAPITAL, R, UNITES, VIE  # noqa: E402

VERSION = 1
FICHIER = "mentor.json"                     # écrit à la greffe de l'apprentie (dossier de vie)
SOUS_DOSSIER = "mentor"                     # vie/arbre_or/mentor : plan figé, mesures, rapport
# les variantes figées le 19/10 22h37 AVANT toute mesure (plan_fige.md) : v1 = le mentor du chef ; v2, v3 = secours
VARIANTES = {"v1": {"vierge": False, "plafond": 0.4},
             "v2": {"vierge": True, "plafond": 0.4},
             "v3": {"vierge": False, "plafond": 1.0}}
MARGE_STOP = 0.05                           # « juste derrière la zone », en agitations
RISQUE_PCT = 0.5
VALIDITE = 16                               # bougies de 15 min = 4 h
ORDRE_ZONES = (("H4", 0), ("H4", 1), ("H1", 0), ("H1", 1))
UNITE_DECISION = "H4"
UNITE_SUIVEUR = "H4"
QUART_NS = int(pd.Timedelta(minutes=15).value)
QUATRE_H_NS = int(pd.Timedelta(hours=4).value)


# ============================================================================================== ses choix (numéros)
def numeros() -> dict:
    """Les numéros de ses choix dans les listes des mains (cerveau.politique)."""
    from collapsar.ecole.precision import suiveur as SV
    r = R().mains
    K, NU = R().yeux.zones_par_cote, len(UNITES)
    if not SV.active_1r():
        raise ValueError("mentor : il faut le stop suiveur après +1R (réglages mains.suiveur et mains.suiveur_1r)")
    us = SV.unites()
    iu = us.index(UNITE_SUIVEUR)
    o1r = SV.options_1r()
    k1r = [k for k, (u, ag, _) in enumerate(o1r) if u == iu and ag == 0]
    if not k1r:
        raise ValueError(f"mentor : pas d'option « {UNITE_SUIVEUR} après +1R » dans les mains")
    proche = lambda liste, x: int(np.argmin([abs(float(v) - x) for v in liste]))
    i_courir = NU * K + NU * 2                   # destinations : zones opposées (U*K), sommets / creux (U*2), courir
    return {"courir": i_courir, "tp1": i_courir + proche(r.tp1_en_r, 1.0), "part": proche(r.parts_tp1, 0.0),
            "risque": proche(r.risques_pct, RISQUE_PCT), "marge": proche(r.marges_stop, MARGE_STOP),
            "validite": proche(r.validites_ordre, VALIDITE), "suiveur": SV.n_options() + k1r[0], "sv_unite": iu,
            "marge_val": float(r.marges_stop[proche(r.marges_stop, MARGE_STOP)]),
            "risque_val": float(r.risques_pct[proche(r.risques_pct, RISQUE_PCT)]),
            "validite_val": int(r.validites_ordre[proche(r.validites_ordre, VALIDITE)])}


def _t_ns(U) -> torch.Tensor:
    t = getattr(U, "_mentor_t_ns", None)
    if t is None or t.device != U.dev:
        t = torch.as_tensor(np.asarray(U.t_ns, np.int64), device=U.dev)
        U._mentor_t_ns = t
    return t


def zones_valables(s: dict, variante: str = "v1"):
    """Pour chaque côté (0 achat, 1 vente) : la 1re zone valable dans l'ordre 4 h (1re, 2e) puis 1 h (1re, 2e) ->
    (existe [n,J,2], numéro de la place d'entrée / de stop [n,J,2], entrée [n,J,2], bord lointain [n,J,2])."""
    v = VARIANTES[variante]
    r = R().mains
    K = R().yeux.zones_par_cote
    p, A = s["p"], s["A"]
    frais = 2 * s["demi"] * p
    n, J = p.shape
    dev = p.device
    existe = torch.zeros(n, J, 2, dtype=torch.bool, device=dev)
    place = torch.zeros(n, J, 2, dtype=torch.long, device=dev)
    ent = torch.zeros(n, J, 2, device=dev)
    loin = torch.zeros(n, J, 2, device=dev)
    for c in (0, 1):
        sg = 1.0 if c == 0 else -1.0
        for u, k in reversed(ORDRE_ZONES):              # du dernier au premier : le premier valable gagne
            iu = UNITES.index(u)
            top, bot = s["top"][:, :, iu, c, k], s["bot"][:, :, iu, c, k]
            e, f = (top, bot) if c == 0 else (bot, top)
            ok = s["ok"][:, :, iu, c, k]
            if not v["vierge"]:
                ok = ok & s["tou"][:, :, iu, c, k] & s["rea"][:, :, iu, c, k]
            h = sg * (e - f)
            ok = ok & (sg * (p - e) > frais) & ((p - e).abs() <= r.entree_max_agitation * A) & (h > frais) \
                & (h + MARGE_STOP * A <= v["plafond"] * A)
            existe[:, :, c] |= ok
            place[:, :, c] = torch.where(ok, iu * K + k, place[:, :, c])
            ent[:, :, c] = torch.where(ok, e, ent[:, :, c])
            loin[:, :, c] = torch.where(ok, f, loin[:, :, c])
    return existe, place, ent, loin


@torch.no_grad()
def decider(U, s: dict, t: torch.Tensor, pos: torch.Tensor, d_regard: torch.Tensor, jumeau: torch.Tensor | None = None,
            variante: str = "v1", delais=None):
    """Les choix du mentor pour n comptes qui regardent : (choix {numéros [n, J], delai [n]}, niveaux comme
    cerveau.politique). `pos` [n, J, >= 11] (position de jeu.entrees_np), `d_regard` [n] bougies depuis son regard
    précédent (0 = 1er regard du challenge), `jumeau` [n] : son jumeau au hasard (sens à pile ou face)."""
    from collapsar.ecole.precision import cerveau as C
    r = R().mains
    ix = numeros()
    dev = s["p"].device
    n, J = s["p"].shape
    cc, slot, p, A = s["cc"], s["slot"], s["p"], s["A"]
    tt = t[:, None].expand(n, J)
    # 1. QUAND : une bougie de 4 h s'est terminée depuis le regard précédent (ou 1er regard du challenge)
    iu4 = UNITES.index(UNITE_DECISION)
    d = d_regard.to(dev).long()
    t_av = (t - d.clamp(min=0)).clamp(min=0)
    l_now = U.tLIGNES[tt, cc, iu4]
    l_av = U.tLIGNES[t_av[:, None].expand(n, J), cc, iu4]
    moment = (d <= 0)[:, None] | (l_now != l_av)
    # délai : la prochaine clôture de 4 h (le plus grand délai des mains qui n'y passe pas)
    fin_bougie = _t_ns(U)[t] + QUART_NS
    reste = QUATRE_H_NS // QUART_NS - torch.remainder(fin_bougie, QUATRE_H_NS) // QUART_NS          # 1 .. 16
    dl = torch.as_tensor(list(delais if delais is not None else r.delais_regard), device=dev).long()
    i_delai = ((dl[None, :] <= reste[:, None]).sum(1) - 1).clamp(min=0)
    # 4. SENS : les trois tendances d'accord
    sg = U.tTEND[tt, cc][..., 0:3]
    accord = (sg[..., 0] == sg[..., 1]) & (sg[..., 1] == sg[..., 2]) & (sg[..., 0] != 0)
    sens = torch.where(accord, sg[..., 0], torch.zeros_like(sg[..., 0]))
    # 5-6. les zones valables de chaque côté
    existe, place, ent, loin = zones_valables(s, variante)
    a_pos, a_att, sens_att = pos[..., 0] != 0, pos[..., 1] != 0, pos[..., 2]
    libre = slot & moment & ~a_pos & ~a_att
    c_m = (sens < 0).long()                                              # côté du mentor (0 achat, 1 vente)
    pk = lambda x, c: x.gather(2, c[..., None]).squeeze(2)
    ouvrirait = libre & accord & pk(existe, c_m)
    if jumeau is not None and bool(jumeau.any()):
        pile = jumeau.to(dev)[:, None] & (torch.rand(n, J, device=dev) < 0.5)
        cote = torch.where(pile, 1 - c_m, c_m)
    else:
        cote = c_m
    ouvre = ouvrirait & pk(existe, cote)
    geste = torch.where(ouvre, torch.where(cote == 0, C.ACHAT_L, C.VENTE_L), torch.full_like(cote, C.GARDER))
    # 3. ordre en attente : annulé si la tendance n'est plus d'accord avec son sens (jumeau : si l'accord est perdu)
    garde_ok = accord & (sens == torch.sign(sens_att))
    if jumeau is not None:
        garde_ok = torch.where(jumeau.to(dev)[:, None], accord, garde_ok)
    annule = slot & moment & a_att & ~a_pos & ~garde_ok
    geste = torch.where(annule, torch.full_like(geste, C.FERMER), geste)
    z = lambda v: torch.full((n, J), int(v), dtype=torch.long, device=dev)
    choix = {"geste": geste, "entree": torch.where(ouvre, pk(place, cote), z(0)), "stop": torch.where(ouvre, pk(place, cote), z(0)),
             "marge": z(ix["marge"]), "dest": z(ix["courir"]), "tp1": z(ix["tp1"]), "part": z(ix["part"]),
             "risque": z(ix["risque"]), "validite": z(ix["validite"]), "suiveur": z(ix["suiveur"]), "delai": i_delai}
    # niveaux (comme cerveau.politique avec ces numéros)
    sig = torch.where((geste == C.VENTE_M) | (geste == C.VENTE_L), -1.0, 1.0)
    e = torch.where(ouvre, pk(ent, cote), p)
    stop = torch.where(ouvre, pk(loin, cote) - sig * ix["marge_val"] * A, p - sig * A)
    rd = (sig * (e - stop)).clamp(min=1e-12)
    nan = torch.full((n, J), float("nan"), device=dev)
    un = torch.ones(n, J, device=dev)
    lv = {"entree": e, "stop": stop, "tp1": nan, "part": torch.zeros(n, J, device=dev), "dest": nan.clone(), "rd": rd,
          "sig": sig, "ouvre": ouvre, "limite": ouvre.clone(), "ferme": geste == C.FERMER,
          "risque_pct": un * ix["risque_val"], "validite": z(ix["validite_val"]), "delai": dl[i_delai]}
    from collapsar.ecole.precision import suiveur as SV
    if SV.active():
        lv["suiveur_u"] = un * ix["sv_unite"]
        lv["suiveur_tp1"] = torch.zeros(n, J, device=dev)
        lv["suiveur_marge"] = ix["marge_val"] * A
        if SV.active_1r():
            lv["suiveur_1r"] = un.clone()
            lv["suiveur_ag"] = torch.zeros(n, J, device=dev)
    return choix, lv


def d_depuis_compte(fc: torch.Tensor) -> torch.Tensor:
    """Bougies depuis le regard précédent, relues dans la vue du compte (jeu.entrees_np : min((t - dernier) / 16, 4))."""
    x = fc[:, 8]
    return torch.where(x >= 4.0 - 1e-6, torch.full_like(x, 64.0), (x * 16).round()).long()


# ============================================================================================== le mentor à la table
class Mentor:
    """Le mentor, présenté comme un « élève » à l'examen habituel (jeu.Examen) : pas de poids, pas de journal."""

    n_journal = 0
    n_tendance = 0
    symetrique = False

    def __init__(self, variante: str = "v1"):
        assert variante in VARIANTES, variante
        self.variante = variante

    def eval(self):
        return self


class DecideurMentor:
    """Comme jeu.Decideur (même interface), mais les choix sont ceux du mentor (et de son jumeau au hasard)."""

    def __init__(self, table, mentor: Mentor, jumeau_depuis: int | None = None):
        self.tb, self.net, self.jumeau_depuis = table, mentor, jumeau_depuis

    @torch.no_grad()
    def __call__(self, qui: np.ndarray):
        from collapsar.ecole.precision import jeu as JEU
        tb = self.tb
        t, cols, fc, pos = tb.entrees(qui)
        s = tb.vue.structure(t, cols)
        d = torch.as_tensor(tb.cpt.t[qui] - tb.dernier[qui], device=t.device)
        jum = torch.as_tensor((np.asarray(qui) >= self.jumeau_depuis) if self.jumeau_depuis is not None
                              else np.zeros(len(qui), bool), device=t.device)
        choix, lv = decider(tb.U, s, t, pos, d, jum, self.net.variante)
        comp = JEU._vecteur_comportement(choix, lv, ~jum)
        return (choix, None, None, None, None, lv), comp, JEU.paquet_niveaux(lv)


@contextmanager
def mentor_a_l_examen():
    """Pendant ce bloc, jeu.Examen fait jouer le mentor (et son jumeau) quand l'élève est un Mentor ; les cerveaux
    ordinaires jouent comme avant. (Rien n'est changé dans jeu.py : remplacement le temps de la mesure seulement.)"""
    from collapsar.ecole.precision import jeu as JEU
    ancien = JEU.Decideur

    def fabrique(table, net, evaluer, comportement=False, graphe=None, jumeau_depuis=None):
        if isinstance(net, Mentor):
            return DecideurMentor(table, net, jumeau_depuis)
        return ancien(table, net, evaluer, comportement, graphe, jumeau_depuis)
    JEU.Decideur = fabrique
    try:
        yield
    finally:
        JEU.Decideur = ancien


# ============================================================================================== la mesure
def _gains_fin(ex, eleve) -> tuple[np.ndarray, np.ndarray]:
    """Gains %/mois de chaque challenge (élève, jumeau) relus dans la table de l'examen qui vient d'être joué."""
    tb = ex._tables[id(eleve)][0]
    mois = R().monde.challenge_jours / 30.4375
    g = (tb.cpt.valeur / CAPITAL - 1) * 100 / mois
    return g[:ex.n].copy(), g[ex.n:].copy()


def _incertitude(d: np.ndarray, ex) -> float:
    from collapsar.ecole.precision import jeu as JEU
    if getattr(ex, "groupes", None) is not None:
        return JEU.incertitude_groupes(d, ex.groupes)
    indep = max(1.0, len(d) * min(1.0, ex.pas_jours / R().monde.challenge_jours))
    return float(np.std(d, ddof=1) / math.sqrt(indep)) if len(d) > 1 else float("nan")


def jouer(ex, eleve, graines: list[int]) -> dict:
    """L'élève (mentor ou cerveau) sur un examen, son jumeau tiré avec chaque graine ; résumé + gains challenge par
    challenge, avantage sur la MOYENNE de ses jumeaux et son incertitude."""
    from collapsar.ecole.precision.coeur import resume_examen
    xs, gj = [], []
    with mentor_a_l_examen():
        for g in graines:
            x = ex.jouer_un(eleve, int(g))
            el, ju = _gains_fin(ex, eleve)
            if not np.allclose(el, x["gains_pct_mois"], atol=1e-6):
                raise AssertionError("gains relus différents de ceux de l'examen")
            xs.append(x)
            gj.append(ju)
    el = np.asarray(xs[0]["gains_pct_mois"])
    ju = np.mean(gj, 0)
    d = el - ju
    out = {"premier": resume_examen(xs[0]), "graines": [int(g) for g in graines],
           "gains_pct_mois": el.tolist(), "jumeau_moyen_pct_mois": ju.tolist(),
           "gain_pct_mois": float(el.mean()), "gain_incertitude": _incertitude(el, ex),
           "jumeau_pct_mois": float(ju.mean()), "avantage_pct_mois": float(d.mean()), "avantage_incertitude": _incertitude(d, ex),
           "avantage_par_graine": [float(x["avantage_pct_mois"]) for x in xs],
           "jumeau_reussis_pct": float(np.mean([x["jumeau"]["reussis_pct"] for x in xs])),
           "jumeau_murs_pct": float(np.mean([x["jumeau"]["murs_pct"] for x in xs])),
           "jumeau_r_moyen": float(np.nanmean([x["jumeau"]["r_moyen"] for x in xs]))}
    if getattr(ex, "groupes", None) is not None:
        out["blocs"] = sorted({int(i) for i in ex.ids})
    pan = np.asarray(ex.panier)
    out["par_cote"] = {nom: {"gain_pct_mois": float(el[pan == k].mean()), "jumeau_pct_mois": float(ju[pan == k].mean()),
                             "avantage_pct_mois": float(d[pan == k].mean())} for k, nom in enumerate(("réel", "retourné"))
                       if (pan == k).any()}
    out["force"] = out["avantage_pct_mois"] / out["avantage_incertitude"] if out["avantage_incertitude"] > 0 else 0.0
    return out


def mesurer(variante: str = "v1", appareil: str = "cuda", dossier: Path | None = None, graines_controle: int = 8,
            dire=print) -> dict:
    """Le mentor au juge habituel : examen tournant (tous les blocs x parties) puis contrôle 2024-2025."""
    from collapsar.ecole.precision import coeur as CO
    from collapsar.ecole.precision import tournant as TN
    dossier = Path(dossier) if dossier else VIE / SOUS_DOSSIER
    dossier.mkdir(parents=True, exist_ok=True)
    m = Mentor(variante)
    res = {"variante": variante, "regles": VARIANTES[variante], "version": VERSION,
           "date": datetime.now().isoformat(timespec="seconds")}
    r = R()
    t0 = time.time()
    if TN.active():
        U, ex = TN.monde_examen_tournant(appareil)
        ch = ex.tirer(0)
        dire(f"examen tournant : {len(ch)} blocs x {ex.parties} parties = {ex.n} challenges (réel + retourné)")
        res["examen"] = jouer(ex, m, [CO.GRAINE_EXAMEN])
        dire(f"  examen fait ({time.time() - t0:.0f} s) : {_ligne(res['examen'])}")
        del U, ex
        _vider(appareil)
    t1 = time.time()
    U, ex = CO.monde_examen(r.periodes.rapport_de, r.periodes.rapport_jusqua, appareil)
    dire(f"contrôle {r.periodes.rapport_de:%m/%Y} -> {r.periodes.rapport_jusqua:%m/%Y} : {ex.n} challenges, "
         f"jumeau tiré {graines_controle} fois")
    res["controle"] = jouer(ex, m, [CO.GRAINE_EXAMEN + k for k in range(graines_controle)])
    dire(f"  contrôle fait ({time.time() - t1:.0f} s) : {_ligne(res['controle'])}")
    del U, ex
    _vider(appareil)
    res["verdict"] = verdict(res["controle"])
    f = dossier / f"mesure_{variante}.json"
    f.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    dire(f"mesure écrite : {f} ; verdict : {res['verdict']}")
    return res


def verdict(c: dict) -> str:
    """Le verdict écrit AVANT la mesure (plan_fige.md)."""
    a, ia = c["avantage_pct_mois"], c["avantage_incertitude"]
    g, ig = c["gain_pct_mois"], c["gain_incertitude"]
    if a > 2 * ia:
        return "prouvé"
    if g < -2 * ig or a < -2 * ia:
        return "perd clairement"
    return "au moins neutre"


def _vider(appareil):
    import gc
    gc.collect()
    if appareil == "cuda":
        torch.cuda.empty_cache()


def _ligne(x: dict) -> str:
    p = x["premier"]
    return (f"{x['gain_pct_mois']:+.2f} ± {x['gain_incertitude']:.2f} %/mois (jumeau {x['jumeau_pct_mois']:+.2f}), "
            f"avantage {x['avantage_pct_mois']:+.2f} ± {x['avantage_incertitude']:.2f}, R moyen {p['r_moyen']:+.3f}, "
            f"gagnants {p['gagnants_pct']:.0f} %, >= 3R {p.get('trades_3r_pct', float('nan')):.1f} % / >= 5R "
            f"{p.get('trades_5r_pct', float('nan')):.1f} % / >= 10R {p.get('trades_10r_pct', float('nan')):.1f} %, "
            f"réussis {p['reussis_pct']:.1f} %, murs {p['murs_pct']:.1f} %, baisse max moy. {p['baisse_max_moyenne_pct']:.1f} %, "
            f"{p['trades_mois']:.1f} trades/mois")


# ============================================================================================== l'apprentie
# UNE branche « apprentie » née de la cime SYMÉTRIQUE (N2) : elle garde la symétrie, les stops proches (<= 0,4
# agitation), son journal ; elle reçoit ce qu'il faut pour POUVOIR faire comme le mentor :
# - les YEUX DE LA TENDANCE DE FOND (tendance.py, 12 entrées à zéro en dernier) : le mentor décide d'après elle ;
# - la tête du SUIVEUR APRÈS +1R (suiveur.py) : le mentor gère par « 4 h après +1R » ;
# - des REGARDS PLUS ESPACÉS (cerveau.REGARDS_LONGS : + 8 h et 1 jour) : décider surtout sur 4 h / journalier.
# (a) IMITATION (`imiter`) : sur des mondes d'apprentissage (<= 2023, hors blocs d'examen et marges), le mentor tient les
#     comptes ; à chacun de ses regards elle apprend à donner la plus forte probabilité au geste du mentor (même entrée,
#     même stop, même suiveur, même délai...). L'accord est mesuré sur chaque monde AVANT d'y apprendre (monde neuf).
# (b) RÉCOMPENSE EN LAISSE (`apprendre_en_laisse`, cœur de l'arbre) : son apprentissage habituel (essais et erreurs) + un
#     rappel du mentor : sur ses PROPRES regards, ce que le mentor aurait fait, pesé par la laisse, qui se relâche à
#     chaque génération : laisse = depart x relache ^ (générations depuis sa naissance).
NOM_BRANCHE = "apprentie"
LAISSE_DEPART = 1.0
LAISSE_RELACHE = 0.8
JEUNESSE = 12                               # générations avant de pouvoir être coupée (le temps que la laisse se relâche)


def regards_longs() -> tuple:
    from collapsar.ecole.precision import cerveau as C
    return C.REGARDS_LONGS[7]


def laisse(temperament: dict, generation: int) -> float:
    """Le poids du rappel du mentor à cette génération (0 sans mentor)."""
    m = (temperament or {}).get("mentor") if isinstance(temperament, dict) else None
    if not isinstance(m, dict):
        return 0.0
    k = max(0, int(generation) - int(m.get("nee_a", generation)))
    return float(m.get("laisse_depart", LAISSE_DEPART)) * float(m.get("relache", LAISSE_RELACHE)) ** k


def est_apprentie(temperament) -> bool:
    return isinstance(temperament, dict) and isinstance(temperament.get("mentor"), dict)


def temperament_apprentie(t_mere: dict, mere: str, variante: str = "v1", nee_a: int = 0) -> dict:
    from collapsar.ecole.precision import tendance as TD
    from collapsar.ecole.precision import suiveur as SV
    t = {k: v for k, v in dict(t_mere).items() if k != "alertes"}
    if not t.get("symetrique"):
        raise ValueError("l'apprentie naît d'une branche au cerveau symétrique")
    t.update({"nom": NOM_BRANCHE,
              "tendance": {"version": TD.VERSION, "entrees": TD.NTD, "noms": list(TD.NOMS)},
              "suiveur_1r": {"version": SV.VERSION, "options": [x[2] for x in SV.options_1r()]},
              "regards": list(regards_longs()),
              "mentor": {"version": VERSION, "variante": variante, "laisse_depart": LAISSE_DEPART,
                         "relache": LAISSE_RELACHE, "nee_a": int(nee_a), "plan": "vie/arbre_or/mentor/plan_fige.md"},
              "jeunesse": JEUNESSE,
              "heritage": f"cime symétrique {mere}, apprentie du mentor ({variante}) : imitation puis récompense en laisse"})
    return t


def cerveau_apprentie(etat_mere: dict, t: dict, appareil: str = "cpu"):
    """Le cerveau de l'apprentie : les poids de la mère ramenés à sa forme (tendance, suiveur après +1R et délais en plus
    ajoutés à zéro / au départ), réglages de la branche (stops proches, symétrie)."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import journal_trading as JN
    fo = C.forme(etat_mere)
    net = C.Cerveau(journal=fo["journal"], delai=JN.delai_branche(t), tendance=True, suiveur_1r=True,
                    delais=tuple(t["regards"]))
    net.load_state_dict(C.adapter(etat_mere, net))
    C.regler_precision(net, t)
    C.regler_symetrie(net, t)
    return net.to(appareil)


def regarder_le_mentor(lecon, net, bougies: int, variante: str = "v1") -> dict:
    """Le MENTOR tient les comptes d'une leçon pendant `bougies` bougies ; à chacun de ses regards, ce que l'apprentie
    VOIT (ses yeux, sa position, son journal, la tendance) et les choix du mentor sont gardés."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import journal_trading as JN
    tb = lecon.table
    c = tb.cpt
    JN.equiper(tb, net, "ecole")
    mem = []
    st = {"regards": 0, "ouvertures": 0, "fermer": 0, "trades": 0, "r": []}
    with torch.no_grad():
        for _ in range(bougies):
            qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
            if len(qui):
                t, cols, fc, pos = tb.entrees(qui)
                s = tb.vue.structure(t, cols)
                car, pos_plein, q = JEU.yeux_complets(tb, s, t, pos, torch.as_tensor(np.asarray(qui, np.int64), device=t.device), net)
                d = torch.as_tensor(c.t[qui] - tb.dernier[qui], device=t.device)
                choix, lv = decider(tb.U, s, t, pos[..., :C.N_POS], d, None, variante)
                if tb.carnet is not None:
                    tb.carnet.retenir(qui, choix, q, len(qui))
                g = JEU.niveaux_np(JEU.paquet_niveaux(lv))
                tb.appliquer(qui, g)
                mem.append({"t": t, "cols": cols, "fc": fc, "pos": pos_plein, "choix": choix})
                st["regards"] += len(qui)
                st["ouvertures"] += int(g["ouvre"].sum())
                st["fermer"] += int(g["ferme"].sum())
            r, fini, actifs = tb.avancer()
            rr = c.r_ferme[np.isfinite(c.r_ferme)]
            st["r"] += rr.tolist()
            if fini.any():
                tb.demarrer(fini, *lecon._tirer_comptes(np.flatnonzero(fini)))
    out = {k: torch.cat([m[k] for m in mem]) for k in ("t", "cols", "fc", "pos")}
    out["choix"] = {k: torch.cat([m["choix"][k] for m in mem]) for k in mem[0]["choix"]}
    st["trades"] = len(st["r"])
    st["r_moyen"] = float(np.mean(st["r"])) if st["r"] else float("nan")
    del st["r"]
    return out, st


def _lot(table, m: dict, i):
    s = table.vue.structure(m["t"][i], m["cols"][i])
    fm = torch.cat([table.vue.caracteristiques(s), m["pos"][i]], -1)
    return s, fm, {k: v[i] for k, v in m["choix"].items()}


PLANCHER_LP = -50.0                         # un choix du mentor impossible pour ses mains (arrondi) ne fait pas exploser


def perte_imitation(net, s, fm, fc, pos, choix) -> tuple[torch.Tensor, int]:
    """- log P(les choix du mentor), moyenne par regard (plancher : choix impossible pour ses mains)."""
    from collapsar.ecole.precision import cerveau as C
    _, lp, *_ = C.politique(net, s, fm, fc, pos, choix)
    hors = int((lp < PLANCHER_LP).sum())
    return -lp.clamp(min=PLANCHER_LP).mean(), hors


@torch.no_grad()
def accord(net, table, m: dict, paquet: int = 2048, graine: int = 0) -> dict:
    """Ce qu'elle ferait (ses propres tirages) aux regards du mentor : même geste (au plus probable et au tirage), et
    quand le mentor ouvre : même côté, même entrée, même stop, même suiveur, même risque ; même délai partout."""
    from collapsar.ecole.precision import cerveau as C
    N = len(m["t"])
    net.eval()
    tot = {k: 0.0 for k in ("regards", "geste_probable", "geste_tire", "ouvre_m", "ouvre_les_deux", "meme_geste_ouv",
                            "entree", "stop", "suiveur", "risque", "marge", "dest", "part", "delai", "moments_rien",
                            "rien_tire", "nll")}
    gen = torch.random.fork_rng(devices=[table.dev] if table.dev.type == "cuda" else [])
    with gen:
        torch.manual_seed(graine)
        net.voir_lois = True
        try:
            for d in range(0, N, paquet):
                i = torch.arange(d, min(N, d + paquet), device=m["t"].device)
                s, fm, cm = _lot(table, m, i)
                ch, lp, _, _, _, lv = C.politique(net, s, fm, m["fc"][i], m["pos"][i], None)
                _, lpm, *_ = C.politique(net, s, fm, m["fc"][i], m["pos"][i], cm)
                w = s["slot"]
                gm, gt = cm["geste"], ch["geste"]
                gp = lv["lp_geste"].argmax(-1)
                om = (gm >= C.ACHAT_M) & (gm <= C.VENTE_L) & w
                ot = (gt >= C.ACHAT_M) & (gt <= C.VENTE_L) & w
                deux = om & ot & (gm == gt)
                tot["regards"] += float(w.sum())
                tot["geste_probable"] += float(((gp == gm) & w).sum())
                tot["geste_tire"] += float(((gt == gm) & w).sum())
                tot["ouvre_m"] += float(om.sum())
                tot["meme_geste_ouv"] += float(deux.sum())
                tot["ouvre_les_deux"] += float(deux.sum())
                for k in ("entree", "stop", "suiveur", "risque", "marge", "dest", "part"):
                    tot[k] += float(((ch[k] == cm[k]) & deux).sum())
                tot["delai"] += float((ch["delai"] == cm["delai"]).sum())
                rien = (gm == C.GARDER) & w
                tot["moments_rien"] += float(rien.sum())
                tot["rien_tire"] += float(((gt == C.GARDER) & rien).sum())
                tot["nll"] += float(-lpm.clamp(min=PLANCHER_LP).sum())
        finally:
            net.voir_lois = False
    R_ = lambda a, b: 100.0 * tot[a] / max(tot[b], 1.0)
    return {"regards": int(tot["regards"]), "ouvertures_mentor": int(tot["ouvre_m"]),
            "geste_le_plus_probable_pct": R_("geste_probable", "regards"), "geste_tire_pct": R_("geste_tire", "regards"),
            "quand_il_ne_fait_rien_pct": R_("rien_tire", "moments_rien"),
            "quand_il_ouvre_meme_geste_pct": R_("meme_geste_ouv", "ouvre_m"),
            **{f"{k}_pct": R_(k, "ouvre_les_deux") for k in ("entree", "stop", "suiveur", "risque", "marge", "dest", "part")},
            "delai_pct": 100.0 * tot["delai"] / max(N, 1), "perte_par_regard": tot["nll"] / max(N, 1)}


def imiter(net, appareil: str, mondes: int = 10, essai_final: int = 2, comptes: int = 512, bougies: int = 2048,
           epoques: int = 3, paquet: int = 1024, vitesse: float = 1e-4, graine: int = 20261020, variante: str = "v1",
           dire=print) -> dict:
    """Phase (a) : elle apprend à reproduire les gestes du mentor sur des mondes d'apprentissage NEUFS (<= 2023, hors
    blocs d'examen et marges : coeur.monde_apprentissage) ; accord mesuré sur chaque monde avant d'y apprendre, et sur
    `essai_final` mondes de plus où elle n'apprend pas."""
    from collapsar.ecole.precision import coeur as CO
    from collapsar.ecole.precision import jeu as JEU
    opt = torch.optim.AdamW(net.parameters(), lr=vitesse, weight_decay=1e-4)
    rng = np.random.default_rng(graine)
    debuts = CO.debuts_marches()
    hist = []
    for w in range(mondes + essai_final):
        t0 = time.time()
        U = CO.monde_apprentissage(rng, appareil, debuts)
        lecon = JEU.Lecon(U, comptes, np.random.default_rng(graine + w))
        m, st = regarder_le_mentor(lecon, net, bougies, variante)
        a = accord(net, lecon.table, m, graine=w)
        ligne = {"monde": w + 1, "de": str(U.de.date()), "jusqua": str(U.jusqua.date()), "appris": w < mondes,
                 "mentor": st, "accord_avant": a}
        if w < mondes:
            N = len(m["t"])
            net.train()
            pertes, hors = [], 0
            for _ in range(epoques):
                ordre = torch.randperm(N, device=m["t"].device)
                for d in range(0, N, paquet):
                    i = ordre[d:d + paquet]
                    s, fm, cm = _lot(lecon.table, m, i)
                    perte, h = perte_imitation(net, s, fm, m["fc"][i], m["pos"][i], cm)
                    opt.zero_grad(set_to_none=True)
                    perte.backward()
                    torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                    opt.step()
                    pertes.append(float(perte))
                    hors += h
            ligne["perte_debut"], ligne["perte_fin"], ligne["choix_impossibles"] = pertes[0], float(np.mean(pertes[-10:])), hors
        ligne["duree_s"] = time.time() - t0
        hist.append(ligne)
        dire(f"monde {w + 1}/{mondes + essai_final} ({ligne['de']} -> {ligne['jusqua']}, {'appris' if w < mondes else 'essai seul'}, "
             f"{ligne['duree_s']:.0f} s) : mentor {st['regards']} regards, {st['ouvertures']} ordres posés, {st['trades']} "
             f"trades (R {st['r_moyen']:+.2f}) | accord avant : geste {a['geste_le_plus_probable_pct']:.1f} % (tiré "
             f"{a['geste_tire_pct']:.1f} %), quand il ouvre {a['quand_il_ouvre_meme_geste_pct']:.1f} %, entrée {a['entree_pct']:.0f} %, "
             f"stop {a['stop_pct']:.0f} %, suiveur {a['suiveur_pct']:.0f} %, délai {a['delai_pct']:.0f} %, perte "
             f"{a['perte_par_regard']:.2f}" + (f" | appris : perte {ligne['perte_debut']:.2f} -> {ligne['perte_fin']:.2f}"
                                              if w < mondes else ""))
        del m, lecon, U
        _vider(appareil)
    return {"mondes": hist, "final": hist[-1]["accord_avant"] if hist else {},
            "essai_final": [h["accord_avant"] for h in hist if not h["appris"]],
            "reglages": {"mondes": mondes, "essai_final": essai_final, "comptes": comptes, "bougies": bougies,
                         "epoques": epoques, "paquet": paquet, "vitesse": vitesse, "graine": graine}}


def apprendre_en_laisse(br, table, m: dict, generation: int, e) -> dict:
    """Phase (b), dans le cœur : son apprentissage habituel (jeu.apprendre, PPO) + le rappel du mentor sur ses propres
    regards (ce qu'il aurait fait), pesé par la laisse de cette génération."""
    from collapsar.ecole.precision import cerveau as C
    net, opt = br.net, br.opt
    lam = laisse(br.t, generation)
    variante = br.t["mentor"].get("variante", "v1")
    curiosite = br.t.get("curiosite", e.curiosite)
    N = len(m["lp"])
    adv = (m["adv"] - m["adv"].mean()) / (m["adv"].std() + 1e-8)
    sans = m["sans"].float()
    lp_vieux = m["lp"] - (m["lp_exec"] * sans).sum(-1)
    net.train()
    b = {"perte_decision": 0.0, "perte_valeur": 0.0, "hasard": 0.0, "perte_mentor": 0.0, "accord_geste_pct": 0.0}
    nb = 0
    dev = m["lp"].device
    for _ in range(e.epoques):
        ordre = torch.randperm(N, device=dev)
        for d in range(0, N, e.paquet):
            i = ordre[d:d + e.paquet]
            s = table.vue.structure(m["t"][i], m["cols"][i])
            fm = torch.cat([table.vue.caracteristiques(s), m["pos"][i]], -1)
            choix = {k: v[i] for k, v in m["choix"].items()}
            _, lp, lp_exec, hasard, valeur, _ = C.politique(net, s, fm, m["fc"][i], m["pos"][i], choix)
            lp = lp - (lp_exec * sans[i]).sum(-1)
            ratio = (lp - lp_vieux[i]).clamp(-20, 20).exp()
            p1, p2 = ratio * adv[i], ratio.clamp(1 - e.coupe, 1 + e.coupe) * adv[i]
            perte_dec = -torch.min(p1, p2).mean()
            perte_v = torch.nn.functional.huber_loss(valeur, m["ret"][i])
            perte = perte_dec + 0.5 * perte_v - curiosite * hasard.mean()
            if lam > 1e-4:
                with torch.no_grad():
                    cm, _ = decider(table.U, s, m["t"][i], m["pos"][i][..., :C.N_POS], d_depuis_compte(m["fc"][i]),
                                    None, variante)
                pm, _ = perte_imitation(net, s, fm, m["fc"][i], m["pos"][i], cm)
                perte = perte + lam * pm
                b["perte_mentor"] += float(pm)
                b["accord_geste_pct"] += float(100 * ((cm["geste"] == choix["geste"]) & s["slot"]).float().sum()
                                               / s["slot"].float().sum().clamp(min=1))
            opt.zero_grad(set_to_none=True)
            perte.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
            opt.step()
            b["perte_decision"] += float(perte_dec)
            b["perte_valeur"] += float(perte_v)
            b["hasard"] += float(hasard.mean())
            nb += 1
    out = {k: v / max(nb, 1) for k, v in b.items()} | {"regards_appris": N, "laisse": lam}
    return out


# ============================================================================================== la greffe
def appliquer(dossier: Path | None, apprentie: Path, code_avant: Path | None = None, mere: str | None = None,
              dire=print) -> dict:
    """La branche « apprentie » (cerveau déjà imité, fichier `apprentie`) remplace la branche la plus faible hors cime et
    hors mère (archivée). Sauvegarde complète d'abord (vie + code d'avant si donné). Arbre ARRÊTÉ, ARRET en place."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if (dossier / FICHIER).exists():
        raise SystemExit(f"{dossier} : l'apprentie du mentor est déjà greffée ({FICHIER})")
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : créer ARRET et attendre sa fin")
    if not (dossier / "ARRET").exists():
        raise SystemExit(f"{dossier / 'ARRET'} doit être en place pendant la manipulation")
    x = torch.load(apprentie, map_location="cpu", weights_only=False)
    t = dict(x["temperament"])
    fo = C.forme(x["cerveau"])
    if not (fo["tendance"] and fo["suiveur_1r"] and fo.get("delais") and est_apprentie(t) and t.get("symetrique")):
        raise SystemExit(f"{apprentie} : ce n'est pas un cerveau d'apprentie ({fo})")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_mentor_{stamp}"
    shutil.copytree(dossier, sauve / "vie", ignore=shutil.ignore_patterns("journal_trades", "sauvegardes", "precision",
                                                                         "contrefactuel", "symetrique", "mentor",
                                                                         "trois_changements", "images"))
    if code_avant is not None and Path(code_avant).exists():
        shutil.copytree(code_avant, sauve / "code_avant")
    dire(f"sauvegarde complète : {sauve}")
    arbre = Arbre.charger(dossier / "arbre.json")
    cime = arbre.cime
    mere = mere or x.get("mere") or cime
    if mere not in arbre.branches or arbre.branches[mere].morte is not None:
        raise SystemExit(f"mère {mere} : pas une branche vivante")
    faible = SV.la_plus_faible(arbre, {cime, mere})
    if faible is None:
        raise SystemExit("aucune branche à remplacer (hors cime et mère)")
    dire(f"cime {cime} ; mère {mere} ; remplacée : {faible} (niveau {arbre.branches[faible].score:+.2f})")
    journal = Journal(dossier / "journal_croissance.jsonl")
    arbre.mourir(faible, "coupée")
    (dossier / "archives").mkdir(exist_ok=True)
    for f in (f"{faible}.pt", f"{faible}_meilleur.pt"):
        if (dossier / "branches" / f).exists():
            shutil.move(str(dossier / "branches" / f), str(dossier / "archives" / f))
    journal.ecrire("coupe", branche=faible, raison="archivée (place pour l'apprentie du mentor, 19/10)")
    t["mentor"] = {**t["mentor"], "nee_a": int(arbre.battements)}
    net = C.cerveau_pour(x["cerveau"], JN_delai(t))
    opt = torch.optim.AdamW(net.parameters(), lr=float(t.get("vitesse", R().ecole.vitesse)), weight_decay=1e-4)
    b = arbre.naitre([mere], t)
    tmp = dossier / "branches" / f"{b.nom}.pt.tmp"
    torch.save({"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": t}, tmp)
    os.replace(tmp, dossier / "branches" / f"{b.nom}.pt")
    journal.ecrire("naissance", branche=b.nom, parents=[mere], temperament=t, heritage=t["heritage"])
    arbre._elire_cime()
    arbre.sauver(dossier / "arbre.json")
    fx = dossier / "derniers_examens.json"
    if fx.exists():
        ex = json.loads(fx.read_text(encoding="utf-8"))
        ex.pop(faible, None)
        fx.write_text(json.dumps(ex, ensure_ascii=False, default=float), encoding="utf-8")
    info = {"date": datetime.now().isoformat(timespec="seconds"), "version": VERSION, "branche": b.nom, "mere": mere,
            "cime": cime, "remplacee": faible, "sauvegarde": str(sauve), "apprentie": str(apprentie),
            "nee_a": int(arbre.battements), "variante": t["mentor"]["variante"]}
    journal.ecrire("mentor", **{k: v for k, v in info.items() if k != "date"})
    (dossier / FICHIER).write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    dire(f"branche {b.nom} « {NOM_BRANCHE} » née de {mere} (génération {arbre.battements}) ; {faible} archivée")
    return info


def JN_delai(t: dict) -> str:
    from collapsar.ecole.precision import journal_trading as JN
    return JN.delai_branche(t)


def retirer(dossier: Path | None = None, dire=print):
    """Retour arrière léger (arbre arrêté) : l'apprentie (et ses filles) archivée(s), l'arbre continue."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : l'arrêter d'abord (fichier ARRET)")
    arbre = Arbre.charger(dossier / "arbre.json")
    journal = Journal(dossier / "journal_croissance.jsonl")
    app = [b.nom for b in arbre.vivantes() if est_apprentie(b.temperament)]
    if app and len(app) == len(arbre.vivantes()):
        raise SystemExit("toutes les branches sont apprenties : utiliser « defaire »")
    for n in app:
        arbre.mourir(n, "coupée")
        for f in (f"{n}.pt", f"{n}_meilleur.pt"):
            if (dossier / "branches" / f).exists():
                shutil.move(str(dossier / "branches" / f), str(dossier / "archives" / f))
        journal.ecrire("coupe", branche=n, raison="apprentie du mentor retirée (retour arrière)")
    arbre._elire_cime()
    arbre.sauver(dossier / "arbre.json")
    (dossier / FICHIER).unlink(missing_ok=True)
    dire(f"apprenties archivées : {app} ; cime {arbre.cime}")


def defaire(dossier: Path | None = None, dire=print):
    """Retour arrière complet (arbre arrêté) : la vie de l'arbre d'avant la greffe (sauvegarde)."""
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : l'arrêter d'abord (fichier ARRET)")
    info = json.loads((dossier / FICHIER).read_text(encoding="utf-8"))
    sauve = Path(info["sauvegarde"]) / "vie"
    shutil.rmtree(dossier / "branches")
    shutil.copytree(sauve / "branches", dossier / "branches")
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl", "note_cotes.json"):
        if (sauve / nom).exists():
            shutil.copy2(sauve / nom, dossier / nom)
    for f in (f"{info['remplacee']}.pt", f"{info['remplacee']}_meilleur.pt"):
        (dossier / "archives" / f).unlink(missing_ok=True)
    (dossier / FICHIER).unlink(missing_ok=True)
    dire(f"apprentie défaite : vie remise depuis {sauve}")


def preparer(dossier: Path, mere: str, sortie: Path, appareil: str, mondes: int, essai_final: int, variante: str = "v1",
             dire=print, **k) -> dict:
    """Une copie de la branche mère (fichier de l'arbre, jamais modifié) -> cerveau d'apprentie -> imitation -> fichier
    `sortie` (cerveau + tempérament + mesures), prêt pour `appliquer`."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.arbre.jardinier import Arbre
    e = torch.load(Path(dossier) / "branches" / f"{mere}.pt", map_location="cpu", weights_only=False)
    gen = Arbre.charger(Path(dossier) / "arbre.json").battements
    t = temperament_apprentie(e.get("temperament") or {}, mere, variante, gen)
    torch.manual_seed(20261020)
    net = cerveau_apprentie(e["cerveau"], t, appareil)
    dire(f"apprentie née de {mere} (génération {gen}) : forme {C.forme(net.state_dict())}, symétrique {net.symetrique}, "
         f"stops <= {net.stop_max_agitation} agitation")
    im = imiter(net, appareil, mondes, essai_final, variante=variante, dire=dire, **k)
    sortie = Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"cerveau": net.state_dict(), "temperament": t, "mere": mere, "generation_mere": gen, "imitation": im},
               sortie)
    (sortie.with_suffix(".json")).write_text(json.dumps({k_: v for k_, v in im.items()}, ensure_ascii=False, indent=1,
                                                         default=float), encoding="utf-8")
    dire(f"apprentie imitée : {sortie}")
    return im


# ============================================================================================== commandes
def main(argv=None):
    ap = argparse.ArgumentParser(description="le mentor de MAGNETAR (19/10)")
    ap.add_argument("quoi", choices=["mesurer", "preparer", "appliquer", "retirer", "defaire"])
    ap.add_argument("--variante", default="v1", choices=sorted(VARIANTES))
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--dossier", default=None, help="dossier de vie de l'arbre (défaut : celui des réglages)")
    ap.add_argument("--sortie", default=None)
    ap.add_argument("--mere", default=None)
    ap.add_argument("--apprentie", default=None)
    ap.add_argument("--code-avant", default=None)
    ap.add_argument("--mondes", type=int, default=10)
    ap.add_argument("--essai-final", type=int, default=2)
    ap.add_argument("--comptes", type=int, default=512)
    ap.add_argument("--bougies", type=int, default=2048)
    ap.add_argument("--vitesse", type=float, default=1e-4)
    ap.add_argument("--carte-max-go", type=float, default=None)
    a = ap.parse_args(argv)
    if a.carte_max_go and a.appareil == "cuda":
        tot = torch.cuda.get_device_properties(0).total_memory / 1e9
        torch.cuda.set_per_process_memory_fraction(min(1.0, a.carte_max_go / tot), 0)
    d = Path(a.dossier) if a.dossier else VIE
    _allumer(d)
    if a.quoi == "mesurer":
        mesurer(a.variante, a.appareil, Path(a.sortie) if a.sortie else None)
    elif a.quoi == "preparer":
        sortie = Path(a.sortie) if a.sortie else VIE / SOUS_DOSSIER / "apprentie.pt"
        preparer(d, a.mere or "N2", sortie, a.appareil, a.mondes, a.essai_final, a.variante, comptes=a.comptes,
                 bougies=a.bougies, vitesse=a.vitesse)
    elif a.quoi == "appliquer":
        appliquer(d, Path(a.apprentie or VIE / SOUS_DOSSIER / "apprentie.pt"),
                  Path(a.code_avant) if a.code_avant else None, a.mere)
    elif a.quoi == "retirer":
        retirer(d)
    else:
        defaire(d)


def _allumer(dossier: Path):
    """Les yeux et les mains comme l'arbre (foule, juge, monde, suiveur, tendance, suiveur après +1R)."""
    from collapsar.ecole.precision import journal_trading as JN
    from collapsar.ecole.precision import suiveur as SV
    from collapsar.ecole.precision import tendance as TD
    JN._allumer_comme_l_arbre(dossier)
    if (dossier / "tendance.json").exists():
        TD.activer()
    if (dossier / "suiveur.json").exists():
        SV.activer()
    if (dossier / "suiveur_1r.json").exists() and SV.active():
        R().mains.suiveur_1r = True


if __name__ == "__main__":
    main()
