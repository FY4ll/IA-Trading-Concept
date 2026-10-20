"""LE CŒUR DE L'ARBRE HYPERNOVA (16/10/2026) : un seul programme qui bat en continu (comme collapsar/arbre/coeur.py).

Au réveil (une fois) : les yeux de tous les marchés (ses zones de toutes les unités, sommets / creux, agitation) sont
calculés si besoin et rangés sur le disque, l'examen de sélection 2022-2023 est monté en mémoire, les branches sont
rechargées (reprise exacte après un arrêt).
Une GÉNÉRATION (un battement) :
1. un monde d'apprentissage tiré au hasard (24 marchés réels ou retournés, 18 mois avant 2022) ; chaque BRANCHE vivante
   y apprend un tour (leçons d'essais et erreurs, ses propres comptes) ;
2. toutes les branches passent l'EXAMEN sur les MÊMES challenges 2022-2023 (paniers fixes de tous les marchés, un départ
   tous les 30 jours), chacune avec son JUMEAU au hasard (mêmes gestes, sens à pile ou face) ; note d'un challenge
   (objectif du chef de projet : 8-10 %/mois, réussir vite sans mur) = réussi x (5 + 5 x part des jours restants)
   - 10 x mur - 5 x inactif + (gain %/mois - gain du jumeau, borné à +-10) - 0,5 x (baisse max - 6 %) ;
3. le NIVEAU d'une branche = moyenne de ses 3 dernières notes ; la CIME = le meilleur niveau ; la plus faible est COUPÉE
   (archivée) si la cime la bat de plus de 2 incertitudes sur le dernier examen (ou, toutes les 10 générations, si elle
   est simplement derrière) ; une place libre : la cime se DIVISE (copie + petite variation des poids et du tempérament) ;
4. sauvegardes, journal de croissance, images de l'arbre et de la cime (après la 1re génération, puis 8h et 20h),
   rapport lisible toutes les 50 générations, message toutes les 100, et en cas de plantage.
Garde-fous de l'école (pas des règles de trading) : une branche paralysée ou joueuse revient à sa meilleure version.

Depuis Test_IA :  venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.precision.coeur --generations 1000
Reprise : la même commande. Pause : créer collapsar\\vie\\hypernova\\PAUSE ; arrêt propre : créer ...\\ARRET.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import shutil
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from collapsar.arbre.jardinier import Arbre, Reglages, maintenant
from collapsar.arbre.journal import Journal
from collapsar.ecole.precision import cerveau as C
from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision import jeu as JEU
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision.reglages import NOM, R, VIE, etiquette_selection
from collapsar.ecole.precision.univers import Univers
from collapsar.mains.fiches import MIROIR

GRAINE_EXAMEN = 20261016
DEBUT_DONNEES = pd.Timestamp("2010-03-01")
HEURES_ENVOI = (8, 20)


def dire(texte):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {texte}", flush=True)


def verrou(dossier: Path) -> Path:
    import psutil
    f = dossier / "coeur.verrou"
    if f.exists():
        try:
            pid = int(f.read_text())
            if pid != os.getpid() and psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower():
                raise SystemExit(f"le cœur de l'arbre {NOM} bat déjà (processus {pid})")
        except ValueError:
            pass
    dossier.mkdir(parents=True, exist_ok=True)
    f.write_text(str(os.getpid()))
    return f


def sauver_atomique(obj, f: Path):
    tmp = f.with_suffix(f.suffix + ".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, f)


def heures_calmes() -> bool:
    h = datetime.now().hour
    return h >= 23 or h < 8


def telephone(titre: str, message: str, urgent: bool, dossier: Path):
    """Message (gardé pour 8h pendant les heures calmes 23h-8h, sauf urgence). Muet si COLLAPSAR_MUET est posée."""
    if os.environ.get("COLLAPSAR_MUET"):
        return
    attente = dossier / "message_en_attente.json"
    if not urgent and heures_calmes():
        attente.write_text(json.dumps({"titre": titre, "message": message}, ensure_ascii=False), encoding="utf-8")
        return
    try:
        from collapsar.surveillance.telephone import envoyer_texte
        envoyer_texte(titre, message)
    except Exception:
        pass


def envoyer_en_attente(dossier: Path):
    attente = dossier / "message_en_attente.json"
    if attente.exists() and not heures_calmes():
        m = json.loads(attente.read_text(encoding="utf-8"))
        attente.unlink(missing_ok=True)
        telephone(m["titre"], m["message"], True, dossier)


def dernier_rendez_vous(now: datetime) -> datetime:
    rdv = [now.replace(hour=h, minute=0, second=0, microsecond=0) for h in HEURES_ENVOI]
    passes = [r for r in rdv if r <= now] or [rdv[-1] - timedelta(days=1)]
    return max(passes)


# ============================================================================================== mondes
def debuts_marches() -> dict:
    out = {}
    for nom in D.univers():
        f = S.dossier(nom, False) / "fait.json"
        if f.exists():
            out[nom] = pd.Timestamp(json.loads(f.read_text())["debut"])
    return out


def monde_apprentissage(rng: np.random.Generator, appareil: str, debuts: dict) -> Univers:
    r = R()
    fin = r.periodes.apprentissage_fin
    duree = pd.DateOffset(months=r.ecole.monde_mois)
    ech = pd.Timedelta(days=r.monde.echauffement_jours)
    from collapsar.ecole.precision import foule as FO
    debut = getattr(r.periodes, "debut_donnees", DEBUT_DONNEES)     # arbre spécialisé : plus d'histoire si elle existe
    if FO.active() and rng.random() < getattr(r.ecole, "part_monde_foule", 0.0):
        debut = r.periodes.foule_debut                 # arbre greffé : monde à l'époque où la foule existe
    minimum = int(getattr(r.ecole, "marches_min_monde", 4))
    for _ in range(20):
        jours = ((fin - duree) - debut).days
        d0 = debut + pd.Timedelta(days=int(rng.integers(0, max(jours, 1))))
        dispo = [m for m, d in debuts.items() if d + ech <= d0]
        if len(dispo) < minimum:
            continue
        choix = rng.choice(dispo, size=min(r.ecole.marches_par_monde, len(dispo)), replace=False)
        if getattr(r.ecole, "reel_et_miroir", False):
            # arbre spécialisé (un seul marché) : chaque marché est là DANS LES DEUX SENS (réel et retourné) ; un
            # compte d'un seul marché tombe donc une fois sur deux sur le miroir, dans chaque monde
            variantes = [(str(m), mir) for m in choix for mir in (False, True)]
        else:
            variantes = [(str(m), bool(rng.random() < r.ecole.part_miroir)) for m in choix]
        U = Univers(variantes, d0, min(d0 + duree, fin), appareil)
        from collapsar.ecole.precision import tournant as TN
        if TN.active():
            # examen tournant (arbre de l'or) : les blocs d'examen et leurs marges ne sont JAMAIS appris ; il faut assez
            # de départs permis (un challenge entier hors des blocs), sinon un autre monde est tiré
            U.permis_depart = TN.permis_depart(U)
            dd = U.instant(U.jusqua - pd.Timedelta(days=r.monde.challenge_jours)) - 1
            if U.permis_depart[int(U.premier.min()):max(dd, 0)].sum() < 96 * 20:
                del U
                continue
        return U
    raise RuntimeError("aucun monde d'apprentissage possible")


def monde_examen(de, jusqua, appareil: str) -> tuple[Univers, JEU.Examen]:
    paniers = JEU.paniers_selection()
    variantes = []
    for p in paniers:
        for m in p:                                   # « _MIROIR » (paniers fixés par un arbre spécialisé) = retourné
            v = (m[:-len(MIROIR)], True) if m.endswith(MIROIR) else (m, False)
            if v not in variantes:
                variantes.append(v)
    U = Univers(variantes, pd.Timestamp(de), pd.Timestamp(jusqua), appareil)
    return U, JEU.Examen(U, paniers, de, jusqua, R().selection.pas_jours)


def resume_examen(x: dict) -> dict:
    return {k: v for k, v in x.items() if k not in ("notes", "gains_pct_mois", "gains_jumeau_pct_mois", "r_par_challenge",
                                                    "trades_r_par_challenge")}


# ============================================================================================== branches
def appliquer_temperament(net: C.Cerveau, t: dict):
    """Le tempérament de départ d'une branche : les penchants initiaux de ses mains (rester à l'écart, ordres limites,
    délai avant de revenir regarder, part encaissée à l'objectif 1). Elle reste libre d'apprendre autre chose."""
    with torch.no_grad():
        b = net.tetes.bias
        b[C.GARDER] = float(t.get("garder", 1.5))
        b[C.ACHAT_L] = b[C.VENTE_L] = float(t.get("limite", 0.0))
        o2 = 6 + net.n_marge
        part = t.get("part")
        if part:
            b[o2:o2 + net.n_part] = torch.tensor(part[:net.n_part], dtype=b.dtype)
        delai = t.get("delai")
        if delai:
            net.delai.bias[:] = torch.tensor(delai[:net.delai.bias.shape[0]], dtype=b.dtype)


def bornes_temperament() -> tuple[float, float]:
    """(vitesse la plus basse, curiosité la plus basse) d'une branche. PLANCHERS (20/10/2026, corrections graves de
    l'audit de MAGNETAR : vitesse descendue à 3e-5 et curiosité effondrée = « elle n'apprend presque plus ») : réglages
    arbre.vitesse_min / arbre.curiosite_min ; absents (HYPERNOVA) = les bornes d'avant (3e-5, 1e-4)."""
    a = R().arbre
    return float(getattr(a, "vitesse_min", None) or 3e-5), float(getattr(a, "curiosite_min", None) or 1e-4)


def planchers(t: dict) -> dict:
    """Le tempérament remonté à ses planchers s'ils sont réglés (sinon inchangé)."""
    a = R().arbre
    for cle, reglage in (("vitesse", "vitesse_min"), ("curiosite", "curiosite_min")):
        v = getattr(a, reglage, None)
        if v and cle in t:
            t[cle] = max(float(t[cle]), float(v))
    return t


class Branche:
    """Une branche vivante en mémoire : son cerveau, son optimiseur, son tempérament."""

    def __init__(self, nom: str, temperament: dict, appareil: str, etat: dict | None = None):
        self.nom, self.t = nom, planchers(dict(temperament))
        from collapsar.ecole.precision import journal_trading as JN
        jr, delai = JN.choix_branche(self.t, etat)          # journal de trading : seulement une branche greffée
        # tendance de fond (tendance.py) et suiveur après +1R (suiveur.py) : d'après ses poids s'ils existent, sinon
        # son tempérament (une fille hérite des deux)
        fo = C.forme(etat["cerveau"]) if etat is not None else {"tendance": bool(self.t.get("tendance")),
                                                                 "suiveur_1r": bool(self.t.get("suiveur_1r"))}
        # regards plus espacés (mentor.py, l'apprentie et ses filles) : d'après ses poids, sinon son tempérament
        delais = fo.get("delais") if etat is not None else (tuple(self.t["regards"]) if self.t.get("regards") else None)
        self.net = C.Cerveau(journal=jr, delai=delai, tendance=fo["tendance"], suiveur_1r=fo["suiveur_1r"],
                             delais=delais).to(appareil)
        C.regler_precision(self.net, self.t)                # stops proches (stop_proche.py) ; absent = comme avant
        C.regler_symetrie(self.net, self.t)                 # cerveau symétrique (symetrie.py) ; absent = comme avant
        self.opt = torch.optim.AdamW(self.net.parameters(), lr=self.t["vitesse"], weight_decay=1e-4)
        if etat is not None:
            self.net.load_state_dict(etat["cerveau"])
            if etat.get("opt"):
                self.opt.load_state_dict(etat["opt"])
            for g in self.opt.param_groups:
                g["lr"] = self.t["vitesse"]
        self.recents = []

    def sauver(self, dossier: Path):
        sauver_atomique({"cerveau": self.net.state_dict(), "opt": self.opt.state_dict(), "temperament": self.t},
                        dossier / "branches" / f"{self.nom}.pt")


# ============================================================================================== le cœur
class Coeur:
    def __init__(self, dossier: Path, appareil: str):
        self.dossier, self.dev = dossier, appareil
        self.r = R()
        (dossier / "branches").mkdir(parents=True, exist_ok=True)
        (dossier / "archives").mkdir(parents=True, exist_ok=True)
        (dossier / "images").mkdir(parents=True, exist_ok=True)
        self.f_arbre = dossier / "arbre.json"
        self.f_examens = dossier / "derniers_examens.json"
        self.journal = Journal(dossier / "journal_croissance.jsonl")
        self.branches: dict[str, Branche] = {}
        self.examens: dict[str, dict] = {}

    # ------------------------------------------------------------------------------------------ naissance / reprise
    def planter_ou_reprendre(self) -> bool:
        a = self.r.arbre
        if self.f_arbre.exists():
            self.arbre = Arbre.charger(self.f_arbre)
            for b in self.arbre.vivantes():
                e = torch.load(self.dossier / "branches" / f"{b.nom}.pt", map_location=self.dev, weights_only=False)
                self.branches[b.nom] = Branche(b.nom, e.get("temperament", b.temperament), self.dev, e)
            if self.f_examens.exists():
                self.examens = json.loads(self.f_examens.read_text(encoding="utf-8"))
            return True
        if getattr(a, "graine", None) is not None:     # arbre spécialisé : graine HÉRITÉE d'un autre arbre (graine.py)
            from collapsar.ecole.precision import graine as GR
            GR.planter(self, a.graine, dire)
            return False
        self.arbre = Arbre(Reglages(places=a.places))
        for i, t in enumerate(a.temperaments[:a.places]):
            b = self.arbre.naitre([], t)
            torch.manual_seed(20261016 + i)
            br = Branche(b.nom, t, self.dev)
            appliquer_temperament(br.net, t)
            br.sauver(self.dossier)
            self.branches[b.nom] = br
            self.journal.ecrire("naissance", branche=b.nom, parents=[], temperament=t)
        self.arbre.sauver(self.f_arbre)
        return False

    def couper(self, nom: str, raison: str, examen: JEU.Examen):
        self.arbre.mourir(nom, "coupée")
        br = self.branches.pop(nom)
        if hasattr(examen, "_tables"):                          # libère sa table d'examen (mémoire de la carte)
            examen._tables.pop(id(br.net), None)
        for f in (f"{nom}.pt", f"{nom}_meilleur.pt"):
            src = self.dossier / "branches" / f
            if src.exists():
                shutil.move(str(src), str(self.dossier / "archives" / f))
        self.examens.pop(nom, None)
        self.journal.ecrire("coupe", branche=nom, raison=raison)
        dire(f"branche {nom} coupée (archivée) : {raison}")

    def diviser(self, mere: str, rng: np.random.Generator):
        m = self.branches[mere]
        t = dict(m.t)
        trait = rng.choice(["vitesse", "curiosite"])
        v_min, c_min = bornes_temperament()                 # (planchers de MAGNETAR ; HYPERNOVA : 3e-5 et 1e-4)
        t[trait] = float(np.clip(t[trait] * rng.choice([0.5, 2.0]), *((v_min, 3e-3) if trait == "vitesse" else (c_min, 0.03))))
        b = self.arbre.naitre([mere], t)
        fille = Branche(b.nom, t, self.dev)
        fille.net.load_state_dict(m.net.state_dict())
        bruit = self.r.arbre.bruit_division
        with torch.no_grad():
            for p in fille.net.parameters():
                if p.numel() > 1 and p.std() > 0:
                    p.add_(torch.randn_like(p) * p.std() * bruit)
        fille.sauver(self.dossier)
        self.branches[b.nom] = fille
        self.journal.ecrire("naissance", branche=b.nom, parents=[mere], temperament=t)
        dire(f"DIVISION : {b.nom} naît de la cime {mere} ({trait} -> {t[trait]:.2g})")

    def revenir(self, br: Branche, raison: str):
        """Garde-fou : la branche revient à sa meilleure version (ou à la cime), mémoire d'apprentissage vidée ; à la
        2e fois, elle apprend 2 x plus lentement."""
        f = self.dossier / "branches" / f"{br.nom}_meilleur.pt"
        if f.exists():
            br.net.load_state_dict(C.adapter(torch.load(f, map_location=self.dev, weights_only=False)["cerveau"], br.net))
        elif self.arbre.cime and self.arbre.cime in self.branches and self.arbre.cime != br.nom:
            br.net.load_state_dict(C.adapter(self.branches[self.arbre.cime].net.state_dict(), br.net))
        br.opt.state.clear()
        br.t["alertes"] = br.t.get("alertes", 0) + 1
        if br.t["alertes"] >= 2:
            br.t["vitesse"] = max(bornes_temperament()[0], br.t["vitesse"] / 2)
            for g in br.opt.param_groups:
                g["lr"] = br.t["vitesse"]
        br.recents = []
        self.journal.ecrire("garde_fou", branche=br.nom, raison=raison)
        dire(f"  GARDE-FOU branche {br.nom} ({raison}) : retour à sa meilleure version")
        return raison

    # ------------------------------------------------------------------------------------------ une génération
    def generation(self, examen: JEU.Examen, debuts: dict) -> dict:
        r = self.r
        e, gf, s = r.ecole, r.gardefous, r.selection
        g = self.arbre.battements + 1
        t0 = time.time()
        torch.manual_seed(1000 + g)
        rng = np.random.default_rng(1000 + g)
        tournant = bool(getattr(examen, "tournant", False))
        plafonnee = self.dev == "cuda" and bool(getattr(r, "carte_max_go", None))
        garer = tournant and plafonnee and hasattr(examen.U, "vers")
        if garer:
            # examen tournant, carte plafonnée (19/10) : le grand monde de l'examen (2010 -> 2023, ~0,2 Go) attend dans la
            # mémoire vive pendant les leçons ; ses tables (et graphes de la carte) sont refaites à chaque génération
            if hasattr(examen, "_tables"):
                examen._tables.clear()
            examen.U.vers("cpu")
            gc.collect()
            torch.cuda.empty_cache()
        U = monde_apprentissage(rng, self.dev, debuts)
        t_monde = time.time() - t0
        res, temps = {}, {}
        from collapsar.ecole.precision import journal_trading as JN
        logs = JN.logs_actifs()                    # fichiers du journal de trading (arbre greffé : journal.json)
        for i, (nom, br) in enumerate(list(self.branches.items())):
            t1 = time.time()
            if logs:                               # à l'école : la cime d'avant et les branches au journal
                br.net.journal_logs = nom == self.arbre.cime or br.net.n_journal > 0
            lecon = JEU.Lecon(U, e.comptes, np.random.default_rng(1000 * g + i))
            lecon.table.peur = br.t.get("peur")    # peur du mur de CETTE branche (peur.py) ; absente = comme avant
            bilans, gardes = [], []
            mentor = isinstance(br.t.get("mentor"), dict)     # l'apprentie du mentor (mentor.py) ; sinon comme avant
            maitre = isinstance(br.t.get("maitre"), dict)     # la branche Gold Reaper (gold_reaper.py) ; sinon comme avant
            for _ in range(e.lecons_par_generation):
                m, b = lecon.jouer(br.net, e.bougies_par_lecon)
                if mentor:                                    # récompense EN LAISSE : + le rappel du mentor
                    from collapsar.ecole.precision import mentor as MT
                    a = MT.apprendre_en_laisse(br, lecon.table, m, g, e)
                elif maitre:                                  # récompense EN LAISSE : + le rappel de Gold Reaper
                    from collapsar.ecole.precision import gold_reaper as GRP
                    a = GRP.apprendre_en_laisse(br, lecon.table, m, g, e)
                else:
                    hm = getattr(e, "hasard_min", None)       # plancher du hasard (MAGNETAR, 20/10) ; absent = comme avant
                    a = JEU.apprendre(br.net, br.opt, lecon.table, m, e.epoques, e.paquet, e.coupe,
                                      br.t.get("curiosite", e.curiosite),
                                      plancher=(float(hm), float(getattr(e, "hasard_force", 0.03))) if hm else None)
                bilans.append({**b, **a})
                del m
                if garer:                          # (19/10) carte plafonnée : réserve rendue après chaque leçon
                    torch.cuda.empty_cache()
                br.recents = (br.recents + [(b["en_position_pct"], b["morts"])])[-gf.fenetre_lecons:]
                if len(br.recents) == gf.fenetre_lecons:
                    pos = float(np.mean([x[0] for x in br.recents]))
                    murs = float(np.mean([x[1] for x in br.recents]))
                    if pos < gf.position_min_pct:
                        gardes.append(self.revenir(br, f"paralysie à l'école ({pos:.1f} % du temps en position)"))
                    elif murs > gf.murs_max_par_lecon_pour_512 * e.comptes / 512:
                        gardes.append(self.revenir(br, f"joueuse à l'école ({murs:.1f} murs par leçon)"))
            if logs:
                JN.recolter(lecon.table, nom, "ecole")
            del lecon
            if self.dev == "cuda" and getattr(r, "carte_max_go", None):   # carte plafonnée : rendre la réserve
                gc.collect()
                torch.cuda.empty_cache()
            moy = lambda k: float(np.nanmean([x[k] for x in bilans]))
            res[nom] = {"lecons": {k: moy(k) for k in ("regards_par_jour", "ouvertures_par_jour", "part_limites_pct",
                                                       "risque_moyen_pct", "en_position_pct", "morts", "trades",
                                                       "r_moyen", "recompense_par_jour", "perte_decision", "hasard")},
                        "garde_fous": gardes}
            if mentor or maitre:                              # la laisse de l'apprentie à cette génération
                res[nom]["laisse"] = {k: moy(k) for k in ("laisse", "perte_mentor", "accord_geste_pct")}
                if maitre:                                    # Gold Reaper : son nom, contrôle 2024-2025 non valable
                    res[nom]["laisse"].update({"maitre": br.t["maitre"].get("nom", "Gold Reaper"),
                                               "accord_il_ouvre_pct": moy("accord_il_ouvre_pct"),
                                               "controle_2024_2025": "non valable"})
            temps[nom] = {"lecons_s": time.time() - t1}
        monde = {"de": str(U.de.date()), "jusqua": str(U.jusqua.date()),
                 "marches": [D.nom_variante(n, m) for n, m in U.variantes]}
        del U
        gc.collect()
        if self.dev == "cuda":
            torch.cuda.empty_cache()
        # ---- examen : toutes les branches sur les mêmes challenges, chacune avec son jumeau au hasard
        if tournant:                                    # examen tournant (tournant.py) : les blocs de cette génération
            blocs_g = examen.tirer(g)
            if hasattr(examen, "_tables"):              # nouvelles fenêtres : tables d'examen refaites
                examen._tables.clear()
            if garer:
                examen.U.vers(self.dev)
        for nom, br in self.branches.items():
            t2 = time.time()
            x = examen.jouer_un(br.net, GRAINE_EXAMEN)
            if plafonnee and hasattr(examen, "_tables"):
                # carte plafonnée (arbre de l'or, 19/10) : sa table d'examen (et ses calculs enregistrés sur la carte)
                # est libérée tout de suite, son carnet récolté avant ; l'examen suivant repart d'une table neuve, comme
                # le premier examen après un redémarrage (tous les comptes remis à zéro). HYPERNOVA (aucun plafond) :
                # comme avant.
                tx = examen._tables.pop(id(br.net), None)
                if tx is not None and logs:
                    JN.recolter(tx[0], nom, "examen")
                del tx
                gc.collect()
                torch.cuda.empty_cache()
            temps[nom]["examen_s"] = time.time() - t2
            self.examens[nom] = x
            res[nom]["examen"] = resume_examen(x)
            self.arbre.noter(nom, round(x["note"], 4), bonnes=round(x["gain_pct_mois"], 3))
            b = self.arbre.branches[nom]
            meilleur = self.dossier / "branches" / f"{nom}_meilleur.pt"
            # sa « meilleure version » : la meilleure note (examen fixe) ou le meilleur NIVEAU (examen tournant : une
            # note seule n'est pas comparable d'un tirage de blocs à l'autre)
            critere = b.score if tournant else x["note"]
            # (20/10, corrections graves, réglage gardefous.meilleure_apres_gardefous de MAGNETAR ; absent = comme avant) :
            # la « meilleure version » n'est enregistrée QU'APRÈS les garde-fous, et seulement s'ils passent : une version
            # paralysée ou joueuse ne devient jamais la référence vers laquelle on revient (boucle de P2, audit 3)
            apres = bool(getattr(r.gardefous, "meilleure_apres_gardefous", False))

            def garder_meilleure():
                if b.record is None or critere > b.record or not meilleur.exists():
                    b.record = critere
                    sauver_atomique({"cerveau": br.net.state_dict(), "generation": g, "examen": resume_examen(x)},
                                    meilleur)
            if not apres:
                garder_meilleure()
            if x["trades_mois"] < s.trades_mois_min or x["inactifs_pct"] > s.inactifs_max_pct:
                res[nom]["garde_fous"].append(self.revenir(br, f"paralysie à l'examen ({x['trades_mois']:.1f} trades/mois)"))
            elif x.get("murs_pct_pire_cote", x["murs_pct"]) > s.murs_max_pct:
                # (examen tournant de l'or : le côté — or réel ou retourné — qui a le plus de murs ; sinon comme avant)
                m_ = x.get("murs_pct_pire_cote", x["murs_pct"])
                res[nom]["garde_fous"].append(self.revenir(br, f"joueuse à l'examen ({m_:.0f} % de murs)"))
            elif apres:
                garder_meilleure()
        ancienne = self.arbre.cime
        self.arbre.fin_de_battement()
        self.arbre._elire_cime()
        cime = self.arbre.cime
        # ---- jardin : couper la plus faible si la cime la bat nettement ; une place libre -> la cime se divise
        a = r.arbre
        # (une branche peut porter sa propre jeunesse dans son tempérament : l'apprentie du mentor, mentor.py)
        vivantes = [b for b in self.arbre.vivantes() if b.nom != cime and len(b.scores) >= int(
            (b.temperament or {}).get("jeunesse", a.jeunesse) if isinstance(b.temperament, dict) else a.jeunesse)]
        if vivantes:
            faible = min(vivantes, key=lambda b: b.score)
            cp = JEU.comparer(self.examens[cime], self.examens[faible.nom], examen.pas_jours,
                              getattr(examen, "groupes", None) if tournant else None)
            if cp["ecart"] > a.coupe_force * cp["incertitude"]:
                self.couper(faible.nom, f"la cime {cime} la bat de {cp['ecart']:+.2f} ± {cp['incertitude']:.2f}", examen)
            elif g % a.renouveler_tous == 0 and faible.score < self.arbre.branches[cime].score:
                self.couper(faible.nom, f"renouvellement (niveau {faible.score:+.2f} contre {self.arbre.branches[cime].score:+.2f})",
                            examen)
        while len(self.arbre.vivantes()) < a.places and cime in self.branches:
            self.diviser(cime, rng)
        if cime != ancienne:
            self.journal.ecrire("cime", branche=cime)
            dire(f"nouvelle cime : {cime}")
        # ---- sauvegardes
        for br in self.branches.values():
            br.sauver(self.dossier)
        self.arbre.sauver(self.f_arbre)
        self.f_examens.write_text(json.dumps({k: {**resume_examen(v), "notes": list(v["notes"]), "gains_pct_mois":
                                                  list(v["gains_pct_mois"])} for k, v in self.examens.items()},
                                             ensure_ascii=False, default=float), encoding="utf-8")
        cx = self.examens[cime]
        sauver_atomique({"cerveau": self.branches[cime].net.state_dict(), "generation": g, "branche": cime,
                         "examen": resume_examen(cx)}, self.dossier / "cime.pt")
        if logs:                                   # fichiers du journal de trading (jamais bloquants)
            t3 = time.time()
            try:
                JN.ecrire_generation(self.dossier, g, cime, examen, self.branches, dire)
            except Exception as ex:
                dire(f"journal de trading : fichiers non écrits ({type(ex).__name__}: {ex})")
            temps["_journal_s"] = {"ecriture_s": time.time() - t3}
        ligne = {"generation": g, "duree_s": time.time() - t0, "monde_s": t_monde, "temps": temps, "monde": monde,
                 "branches": res, "cime": cime, "cime_niveau": self.arbre.branches[cime].score,
                 "cime_examen": resume_examen(cx), "vivantes": [b.nom for b in self.arbre.vivantes()],
                 "memoire_go": memoire_go(),
                 "carte_max_go": (torch.cuda.max_memory_allocated() / 1e9) if self.dev == "cuda" else 0.0,
                 "carte_reservee_max_go": (torch.cuda.max_memory_reserved() / 1e9) if self.dev == "cuda" else 0.0}
        if tournant:
            ligne["blocs_examen"] = blocs_g
        self.journal.ecrire("generation", **ligne)
        j = cx["jumeau"]
        dire(f"génération {g} ({ligne['duree_s']:.0f} s, {len(self.branches)} branches) | CIME {cime} (niveau "
             f"{ligne['cime_niveau']:+.2f}) : {cx['gain_pct_mois']:+.2f} %/mois (jumeau {j['gain_pct_mois']:+.2f}), réussis "
             f"{cx['reussis_pct']:.0f} % en {cx['jours_median_reussite']:.0f} j médians (jumeau {j['reussis_pct']:.0f} %), "
             f"morts {cx['murs_pct']:.0f} % (jumeau {j['murs_pct']:.0f} %), {cx['trades_mois']:.1f} trades/mois"
             f"{texte_gros(cx)} | "
             + " · ".join((f"{n}{' [SYMÉTRIQUE]' if getattr(self.branches[n].net, 'symetrique', False) else ''}"
                           f"{texte_laisse(res.get(n, {}))} "
                           f"{self.examens[n]['note']:+.2f}" + texte_branche(self.examens[n]))
                          if n in self.examens else f"{n} (née)" for n in self.branches))
        return ligne

    def envoyer_images(self, premiere: bool):
        from collapsar.ecole.precision import images
        from collapsar.surveillance import telephone as tel
        lignes = self.journal.lire()
        f1 = images.dessiner_arbre(self.arbre, self.examens, self.dossier / "images" / "arbre.png", NOM)
        f2 = images.dessiner_courbe(lignes, self.dossier / "images" / "courbe.png", NOM)
        self.arbre.envois["dernier"] = maintenant()
        if os.environ.get("COLLAPSAR_MUET"):
            return
        cx = self.examens.get(self.arbre.cime, {})
        resume = (f"génération {self.arbre.battements}, {len(self.branches)} branches ; cime {self.arbre.cime} : "
                  f"{cx.get('gain_pct_mois', float('nan')):+.2f} %/mois (jumeau "
                  f"{cx.get('jumeau', {}).get('gain_pct_mois', float('nan')):+.2f}), réussis {cx.get('reussis_pct', 0):.0f} %")
        titre = f"COLLAPSAR — arbre {NOM}" + (" : première génération" if premiere else f", génération {self.arbre.battements}")
        ok = tel.envoyer_image(f1, titre, resume) and tel.envoyer_image(f2, f"COLLAPSAR — arbre {NOM} : la cime", resume)
        self.journal.ecrire("images", envoyees=bool(ok))


def plafond_carte(appareil: str) -> float | None:
    """Réglage facultatif `carte_max_go` (absent = aucun plafond, comme HYPERNOVA) : la mémoire que ce cœur peut
    réserver sur la carte graphique (hors contexte CUDA, ~0,4 Go), pour laisser sa place à un autre arbre qui tourne
    en même temps. Au-delà, la réserve inutilisée est libérée avant toute nouvelle demande."""
    go = getattr(R(), "carte_max_go", None)
    if not go or appareil != "cuda" or not torch.cuda.is_available():
        return None
    total = torch.cuda.get_device_properties(0).total_memory / 1e9
    torch.cuda.set_per_process_memory_fraction(min(1.0, float(go) / total), 0)
    dire(f"carte graphique : ce cœur se limite à {float(go):.1f} Go réservés (sur {total:.1f})")
    return float(go)


def texte_gros(x: dict) -> str:
    """« , mouvement attrapé 12 % (jumeau 1 %), trades >= 5R 3 % / >= 10R 1 % » si l'examen le mesure, sinon rien."""
    if "part_mouvement_pct" not in x:
        return texte_corrections(x)
    j = x.get("jumeau", {})
    t = (f", mouvement attrapé {x['part_mouvement_pct']:+.1f} % (jumeau {j.get('part_mouvement_pct', float('nan')):+.1f} %),"
         f" trades >= 5R {x['trades_5r_pct']:.1f} % / >= 10R {x['trades_10r_pct']:.1f} %")
    if "suiveur_pct" in x:                          # stop suiveur (arbre de l'or)
        t += (f", stop suiveur {x['suiveur_pct']:.0f} % des trades (R moyen {x['r_moyen_suiveur']:+.2f} contre "
              f"{x['r_moyen_sans_suiveur']:+.2f} sans)")
    if "note_blocs_neufs" in x and x.get("challenges_neufs", 0):   # examen tournant : biais des blocs déjà appris
        t += (f", note blocs déjà appris {x['note_blocs_appris']:+.2f} / neufs {x['note_blocs_neufs']:+.2f} "
              f"({x['challenges_neufs']} challenges neufs)")
    return t + texte_corrections(x)


def texte_corrections(x: dict) -> str:
    """(20/10, corrections graves) « ; TÉMOIN blocs neufs +0.10 %/mois (jumeau -0.20, R -0.05) ; ouvertures exécutées
    8.1/mois (limites exécutées 9 % des trades, 3 % des ordres posés), R par trade -0.06 » si l'examen le mesure."""
    t = ""
    f = lambda v, n=2: "—" if v is None or not np.isfinite(v) else f"{v:+.{n}f}"
    tm = x.get("temoin")
    if tm:
        t += (f" ; TÉMOIN blocs neufs {tm.get('blocs')} (hors note) {f(tm['gain_pct_mois'])} %/mois (jumeau "
              f"{f(tm.get('jumeau_pct_mois', float('nan')))}, R par trade {f(tm.get('r_moyen', float('nan')), 3)})")
    e = x.get("executions")
    if e:
        t += (f" ; ouvertures RÉELLEMENT exécutées {e['ouvertures_executees_mois']:.1f}/mois (au marché "
              f"{e['ouvertures_marche']}, ordres limites exécutés {e['ordres_limites_executes']} = "
              f"{e['part_ordres_executes_pct']:.0f} % des {e['ordres_limites_poses']:.0f} posés), R par trade "
              f"{f(x.get('r_moyen', float('nan')), 3)}")
    return t


def texte_laisse(r: dict) -> str:
    """« [APPRENTIE laisse 0.80, accord 71 %] » pour l'apprentie du mentor (mentor.py), sinon rien."""
    x = r.get("laisse") if isinstance(r, dict) else None
    if not x:
        return ""
    if x.get("maitre"):                             # la branche Gold Reaper (gold_reaper.py)
        return (f" [{str(x['maitre']).upper()} laisse {x['laisse']:.2f}, accord du geste {x['accord_geste_pct']:.0f} %, "
                f"quand il ouvre {x.get('accord_il_ouvre_pct', float('nan')):.0f} % ; contrôle 2024-2025 non valable]")
    return f" [APPRENTIE laisse {x['laisse']:.2f}, accord du geste {x['accord_geste_pct']:.0f} %]"


def texte_branche(x: dict) -> str:
    """Pour chaque branche de la ligne de génération (mesure de la tenue, selection.mesurer_tenue) : « (%/mois +0.10
    jumeau -0.30, stop remonté 4 %, >= 3R 0.5 % / >= 5R 0.1 %, achats +0.02 R / ventes -0.05 R, après +1R 70 %) »."""
    if "stop_remonte_tous_pct" not in x:
        return ""
    f = lambda v, n=1: "—" if v is None or not np.isfinite(v) else f"{v:.{n}f}"
    c = x.get("cotes", {})
    t = (f" (%/mois {x['gain_pct_mois']:+.2f} jumeau {x.get('jumeau', {}).get('gain_pct_mois', float('nan')):+.2f}, "
         f"stop remonté {f(x['stop_remonte_tous_pct'], 0)} %, >= 3R {f(x['trades_3r_pct'])} % / >= 5R "
         f"{f(x.get('trades_5r_tous_pct'))} %, achats {c.get('achats', {}).get('r_moyen', float('nan')):+.2f} R / ventes "
         f"{c.get('ventes', {}).get('r_moyen', float('nan')):+.2f} R")
    if x.get("suiveur_1r_pct", 0) > 0:
        t += f", après +1R {f(x['suiveur_1r_pct'], 0)} % (+1R atteint {f(x.get('suiveur_1r_atteint_pct'), 0)} %)"
    if x.get("par_cote"):                           # (19/10 soir) or réel / or retourné séparés
        from collapsar.ecole.precision import tournant as TN
        t += " | " + TN.texte_cotes(x)
        if "note_moyenne" in x:
            t += f" | note = côté le moins bon ({x['note_cote_faible']}), moyenne {x['note_moyenne']:+.2f}"
    return t + ")"


def chemin_lisible(f: Path) -> str:
    from collapsar.donnees.marches import RACINE
    try:
        return Path(f).resolve().relative_to(RACINE).as_posix()
    except ValueError:
        return str(f)


def memoire_go() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e9
    except Exception:
        return float("nan")


# ============================================================================================== boucle
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", type=int, default=1000, help="nombre TOTAL de générations visé")
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--dossier", default=None, help="dossier de vie (par défaut collapsar/vie/hypernova)")
    ap.add_argument("--rapport", action="store_true", help="écrire le rapport maintenant et s'arrêter")
    ap.add_argument("--muet", action="store_true", help="aucun message ni image au téléphone (essais)")
    args = ap.parse_args(argv)
    if args.muet:
        os.environ["COLLAPSAR_MUET"] = "1"
    dossier = Path(args.dossier) if args.dossier else VIE
    dossier.mkdir(parents=True, exist_ok=True)
    if getattr(R().arbre, "graine", None) is not None and not (dossier / "arbre.json").exists() and not args.rapport:
        # arbre spécialisé, avant sa naissance : copie de la graine (entre deux générations de l'arbre source) et de
        # ses greffes (foule.json...), pour que les yeux s'allument comme ceux de l'arbre source (graine.py)
        from collapsar.ecole.precision import graine as GR
        GR.copier_source(R().arbre.graine, dossier, dire)
    # yeux de la foule (foule.py) : allumés seulement si l'arbre a été GREFFÉ (foule.json) ou par le réglage yeux.foule
    from collapsar.ecole.precision import foule as FO
    if FO.greffee(dossier):
        FO.activer()
    elif FO.active() and (dossier / "arbre.json").exists():
        raise SystemExit(f"réglage yeux.foule allumé mais l'arbre de {dossier} n'est pas greffé : lancer d'abord "
                         f"« python -m collapsar.ecole.precision.foule greffer »")
    # notes du juge (juge_trade.py) : allumées seulement si l'arbre a été GREFFÉ (juge.json) ou par le réglage yeux.juge
    from collapsar.ecole.precision import juge_trade as JT
    if not JT.allumer_si_greffe(dossier) and JT.active() and (dossier / "arbre.json").exists():
        raise SystemExit(f"réglage yeux.juge allumé mais l'arbre de {dossier} n'est pas greffé : lancer d'abord "
                         f"« python -m collapsar.ecole.precision.juge_trade greffer --dossier {dossier} »")
    # yeux du monde (monde.py) : allumés seulement si l'arbre a été GREFFÉ (monde.json) ou par le réglage yeux.monde
    from collapsar.ecole.precision import monde as MO
    if MO.greffee(dossier):
        MO.activer()
    elif MO.active() and (dossier / "arbre.json").exists():
        raise SystemExit(f"réglage yeux.monde allumé mais l'arbre de {dossier} n'est pas greffé : lancer d'abord "
                         f"« python -m collapsar.ecole.precision.monde greffer --dossier {dossier} »")
    # stop suiveur (suiveur.py) : allumé par le réglage mains.suiveur (arbre de l'or) ou par un arbre GREFFÉ (suiveur.json)
    from collapsar.ecole.precision import suiveur as SV
    if SV.greffee(dossier):
        SV.activer()
    elif SV.active() and (dossier / "arbre.json").exists():
        raise SystemExit(f"réglage mains.suiveur allumé mais l'arbre de {dossier} n'est pas greffé : l'arrêter puis lancer "
                         f"« python -m collapsar.ecole.precision.arbre_or --greffer-suiveur »")
    # tendance de fond (tendance.py) et suiveur après +1R (suiveur.py) : allumés par leurs réglages (reglages_or.yaml) ou
    # par un arbre greffé (tendance.json, suiveur_1r.json) ; HYPERNOVA : ni l'un ni l'autre, rien ne change
    from collapsar.ecole.precision import tendance as TD
    if (dossier / "tendance.json").exists():
        TD.activer()
    if (dossier / "suiveur_1r.json").exists():
        if not SV.active():
            raise SystemExit("arbre greffé du suiveur après +1R sans stop suiveur (réglage mains.suiveur)")
        R().mains.suiveur_1r = True
    # journal de trading (journal_trading.py) : une branche greffée (journal.json) -> fichiers de log allumés ; le
    # cerveau de cette branche (et lui seul) voit son journal
    from collapsar.ecole.precision import journal_trading as JN
    JN.allumer_logs(None)
    if JN.allumer_si_greffe(dossier):
        dire("JOURNAL DE TRADING : branche(s) greffée(s) " + ", ".join(json.loads((dossier / "journal.json").read_text(
            encoding="utf-8")).get("branches", [])) + f" ; fichiers de log dans {dossier / 'journal_trades'}")
    if args.rapport:
        from collapsar.ecole.precision.rapport import ecrire_rapport
        return ecrire_rapport(dossier, args.appareil)
    f_verrou = verrou(dossier)
    plafond_carte(args.appareil)
    en_cours = dossier / "EN_COURS"
    en_cours.write_text(json.dumps({"generations": args.generations, "appareil": args.appareil,
                                    "depuis": datetime.now().isoformat(timespec="seconds")}))
    arret, pause = dossier / "ARRET", dossier / "PAUSE"
    fini = False
    try:
        dire(f"réveil du cœur de l'arbre {NOM} ({args.appareil}) : yeux de tous les marchés (déjà faits = immédiat)")
        S.preparer_tout(dire=dire)
        if FO.active():
            dire("yeux de la FOULE allumés (arbre greffé) : comptes acheteurs, financement, positions, flux, prime")
            FO.preparer_tout(dire)
        debuts = debuts_marches()
        r = R()
        t0 = time.time()
        from collapsar.ecole.precision import tournant as TN
        if TN.active():
            # EXAMEN TOURNANT (tournant.py, arbre de l'or) : réservoir de blocs jamais appris, tirage à chaque génération
            TN.passer(dossier, dire)
            TN.passer_note_cotes(dossier, dire)         # (19/10 soir) note appariée : réglage note_cotes
            TN.passer_gain_reel(dossier, dire)          # (20/10) note au gain réel : réglage note.gain_reel
            U_sel, examen = TN.monde_examen_tournant(args.appareil)
            de_t, a_t = TN.periode()
            dire(f"examen TOURNANT en mémoire : réservoir de {len(examen.blocs)} blocs de {r.monde.challenge_jours} jours "
                 f"({de_t:%m/%Y} -> {a_t:%m/%Y}, jamais appris, marges {TN.marge_avant().days} j / "
                 f"{TN.marge_apres().days} j), {examen.par_generation} blocs tirés à chaque génération = {examen.n} "
                 f"challenges (réel + retourné), {U_sel.M} marchés ({time.time() - t0:.0f} s)")
        else:
            U_sel, examen = monde_examen(r.periodes.selection_de, r.periodes.selection_jusqua, args.appareil)
            dire(f"examen de sélection en mémoire : {examen.n} challenges de 2 mois ({r.periodes.selection_de:%m/%Y} -> "
                 f"{r.periodes.selection_jusqua:%m/%Y}), {len(examen.paniers)} paniers, "
                 f"{U_sel.M} marchés ({time.time() - t0:.0f} s)")
        coeur = Coeur(dossier, args.appareil)
        if coeur.planter_ou_reprendre():
            dire(f"l'arbre {NOM} reprend après la génération {coeur.arbre.battements} : {len(coeur.branches)} branches, "
                 f"cime {coeur.arbre.cime}")
        else:
            dire(f"graine {NOM} plantée : {len(coeur.branches)} branches ("
                 + ", ".join(f"{n} {b.t.get('nom', '')}" for n, b in coeur.branches.items()) + ")")
            if SV.active():                         # né avec le stop suiveur : noté comme un arbre greffé
                (dossier / "suiveur.json").write_text(json.dumps({"date": datetime.now().isoformat(timespec="seconds"),
                                                                  "version": SV.VERSION, "ne_avec": True,
                                                                  "unites": list(SV.unites())}), encoding="utf-8")
        rr = r.rapports
        while coeur.arbre.battements < args.generations:
            if arret.exists():
                dire("ARRET demandé : le cœur s'arrête proprement")
                en_cours.unlink(missing_ok=True)
                break
            while pause.exists() and not arret.exists():
                time.sleep(30)
            if arret.exists():
                continue
            envoyer_en_attente(dossier)
            coeur.generation(examen, debuts)
            g = coeur.arbre.battements
            now = datetime.now()
            dernier = datetime.fromisoformat(coeur.arbre.envois["dernier"]) if coeur.arbre.envois.get("dernier") else None
            if dernier is None or dernier < dernier_rendez_vous(now):
                try:
                    coeur.envoyer_images(premiere=dernier is None)
                except Exception as ex:                 # une image ratée ne doit jamais arrêter le cœur
                    coeur.arbre.envois["dernier"] = maintenant()
                    dire(f"images : erreur ({type(ex).__name__}: {ex}), le cœur continue")
                coeur.arbre.sauver(coeur.f_arbre)
            if g % rr.rapport_tous == 0:
                try:
                    from collapsar.ecole.precision.rapport import ecrire_rapport
                    ecrire_rapport(dossier, args.appareil)
                    dire("rapport écrit : " + str(dossier / "rapport.md"))
                except Exception as ex:
                    dire(f"rapport non écrit : {type(ex).__name__} {ex}")
                gc.collect()
                if args.appareil == "cuda":
                    torch.cuda.empty_cache()
            if g % rr.telephone_tous == 0:
                cx = coeur.examens[coeur.arbre.cime]
                j = cx["jumeau"]
                telephone(f"COLLAPSAR — arbre {NOM}, génération {g}",
                          f"Cime {coeur.arbre.cime}, sélection {etiquette_selection()} : {cx['gain_pct_mois']:+.2f} %/mois "
                          f"(jumeau au hasard {j['gain_pct_mois']:+.2f}), challenges réussis {cx['reussis_pct']:.0f} % en "
                          f"{cx['jours_median_reussite']:.0f} jours médians (jumeau {j['reussis_pct']:.0f} %), morts "
                          f"{cx['murs_pct']:.0f} % (jumeau {j['murs_pct']:.0f} %), {cx['trades_mois']:.1f} trades/mois"
                          f"{texte_gros(cx)}. Rapport : {chemin_lisible(dossier / 'rapport.md')}", False, dossier)
        else:
            fini = True
            dire(f"l'arbre {NOM} a fini ses {coeur.arbre.battements} générations")
    except SystemExit:
        raise
    except BaseException as ex:
        trace = traceback.format_exc()
        dire(f"PLANTAGE : {type(ex).__name__} {ex}\n{trace}")
        try:
            Journal(dossier / "journal_croissance.jsonl").ecrire("plantage", erreur=str(ex), trace=trace[-3000:])
        except Exception:
            pass
        if not isinstance(ex, KeyboardInterrupt):
            telephone(f"COLLAPSAR — arbre {NOM} : plantage",
                      f"{type(ex).__name__} : {str(ex)[:300]}. Le gardien relancera le cœur (reprise à la dernière "
                      f"génération sauvegardée).", True, dossier)
        raise
    finally:
        f_verrou.unlink(missing_ok=True)
        if fini:
            en_cours.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
