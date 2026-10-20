"""Le cœur de COLLAPSAR : un programme qui ne s'arrête jamais. Pas de cycles : des battements.

À chaque battement :
1. chaque branche vivante s'entraîne un temps proportionnel à sa sève (15 minutes partagées), son cerveau est
   enregistré ;
2. elle est notée sur une période jamais apprise ;
3. (une branche née au battement précédent pousse donc tout de suite) ;
4. le jardinier redistribue la sève, fait des bourgeons, tente des fusions, coupe ce qui ne pousse plus ;
5. tout est écrit dans le journal de croissance ; matin et soir, les deux images partent sur le téléphone.
Si la machine s'arrête, l'arbre reprend exactement où il en était.

Lancement (depuis Test_IA) : venv_gpu\\Scripts\\python.exe -u -m collapsar.arbre.coeur
Pause : créer le fichier collapsar/vie/PAUSE (l'arbre attend, rien n'est perdu).
"""
from __future__ import annotations

import ctypes
import importlib
import os
import random
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import torch
import yaml

from collapsar.arbre import portes
from collapsar.arbre.jardinier import TEMPERAMENT_GRAINE, Arbre, Reglages, maintenant
from collapsar.arbre.journal import Journal
from collapsar.cerveau.reseau import Cerveau
from collapsar.cerveau.trader import CerveauTrader
from collapsar.donnees import marches as dm
from collapsar.regarder import vision_trader
from collapsar.regarder.exercices import HORIZONS, Exercices
from collapsar.surveillance import dessin, telephone
from collapsar.yeux.graphique import Graphique

VIE = dm.RACINE / "collapsar" / "vie"
BRANCHES = VIE / "branches"
ARCHIVES = VIE / "archives"
IMAGES = VIE / "images"
ETAT = VIE / "arbre.json"
VERROU = VIE / "coeur.verrou"
PAUSE = VIE / "PAUSE"
REGLAGES = dm.RACINE / "collapsar" / "reglages.yaml"
HEURES_ENVOI = (8, 20)
# ce que les yeux apprennent (reglages.yaml, « vision ») : « racines » = deviner sens / ampleur / agitation (arbre 2) ;
# « trader » = évaluer n'importe quel coup, sens + stop + objectif libres (arbre 3, 14/10/2026)
VISION = "racines"
# taille du cerveau à vision de trader (reglages.yaml, « largeur_trader ») : 14/10, un cerveau plus petit récite moins
LARGEUR_TRADER = 1.0


def dire(texte: str):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {texte}", flush=True)


def memoire_libre_go() -> float:
    class Etat(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    e = Etat()
    e.dwLength = ctypes.sizeof(Etat)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(e))
    return e.ullAvailPageFile / 2**30


def prendre_verrou():
    import psutil
    if VERROU.exists():
        try:
            pid = int(VERROU.read_text())
            if pid != os.getpid() and psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower():
                dire(f"le cœur bat déjà (processus {pid}) : on ne lance pas un deuxième cœur.")
                sys.exit(0)
        except (ValueError, psutil.Error):
            pass
    VERROU.write_text(str(os.getpid()))


# ---- cerveaux des branches ----
def nouveau_cerveau(temperament: dict, appareil) -> Cerveau | CerveauTrader:
    if VISION == "trader":
        return CerveauTrader(oubli=temperament["oubli"], largeur=LARGEUR_TRADER).to(appareil)
    return Cerveau(n_horizons=len(HORIZONS), oubli=temperament["oubli"]).to(appareil)


def optimiseur(cerveau: Cerveau, temperament: dict):
    return torch.optim.AdamW(cerveau.parameters(), lr=temperament["vitesse"], weight_decay=temperament["usure"])


def sauver_branche(nom: str, cerveau: Cerveau, opt):
    BRANCHES.mkdir(parents=True, exist_ok=True)
    tmp = BRANCHES / f"{nom}.tmp"
    torch.save({"cerveau": cerveau.state_dict(), "optimiseur": opt.state_dict() if opt else None}, tmp)
    tmp.replace(BRANCHES / f"{nom}.pt")


def charger_branche(nom: str, temperament: dict, appareil):
    cerveau = nouveau_cerveau(temperament, appareil)
    opt = optimiseur(cerveau, temperament)
    contenu = torch.load(BRANCHES / f"{nom}.pt", map_location=appareil, weights_only=True)
    cerveau.load_state_dict(contenu["cerveau"])
    if contenu.get("optimiseur"):
        opt.load_state_dict(contenu["optimiseur"])
        for g in opt.param_groups:                       # le tempérament fait foi
            g["lr"], g["weight_decay"] = temperament["vitesse"], temperament["usure"]
    return cerveau, opt


def archiver(nom: str):
    ARCHIVES.mkdir(parents=True, exist_ok=True)
    for f in (f"{nom}.pt", f"{nom}_meilleur.pt"):
        if (BRANCHES / f).exists():
            shutil.move(str(BRANCHES / f), str(ARCHIVES / f))


# 14/10 après-midi, CONTRE LE PAR CŒUR (vision du trader) : chaque branche garde sa meilleure version (meilleur lien
# prévu/réel sur 2020-2022) ; si son lien retombe de plus de RECUL point (elle s'est mise à réciter ses années
# apprises), elle revient à cette version et apprend ensuite deux fois plus doucement.
RECUL = 0.3
CLE = "lien"


def garder_ou_revenir(b, note: float, cerveau, appareil) -> tuple[float, str | None]:
    """Rend (note à inscrire, événement). Le cerveau est remplacé en place en cas de retour."""
    meilleur = BRANCHES / f"{b.nom}_meilleur.pt"
    if b.record is None or note > b.record or not meilleur.exists():
        b.record = note
        shutil.copyfile(BRANCHES / f"{b.nom}.pt", meilleur)
        return note, None
    if note < b.record - RECUL:
        contenu = torch.load(meilleur, map_location=appareil, weights_only=True)
        cerveau.load_state_dict(contenu["cerveau"])
        b.retours += 1
        b.temperament["vitesse"] = max(3e-5, b.temperament["vitesse"] * 0.5)
        sauver_branche(b.nom, cerveau, optimiseur(cerveau, b.temperament))
        return b.record, f"retour à sa meilleure version ({b.record:+.2f}) : elle récitait ({note:+.2f})"
    return note, None


def fusionner(a: Cerveau, b: Cerveau, temperament: dict, appareil) -> Cerveau:
    f = nouveau_cerveau(temperament, appareil)
    ea, eb = a.state_dict(), b.state_dict()
    f.load_state_dict({k: (ea[k] + eb[k]) / 2 if ea[k].is_floating_point() else ea[k] for k in ea})
    return f


# ---- images ----
def dernier_rendez_vous(now: datetime) -> datetime:
    rdv = [now.replace(hour=h, minute=0, second=0, microsecond=0) for h in HEURES_ENVOI]
    passes = [r for r in rdv if r <= now] or [rdv[-1] - timedelta(days=1)]
    return max(passes)


def envoyer_images(arbre: Arbre, journal: Journal, essai: bool = False):
    importlib.reload(dessin)                         # un dessin amélioré est pris sans arrêter l'arbre
    lignes = journal.lire()
    franchies = [(l["heure"], l["porte"]) for l in lignes if l.get("quoi") == "porte"]
    trader = VISION == "trader"
    f1 = dessin.dessiner_arbre(arbre, IMAGES / "arbre.png", franchies, trader=trader)
    f2 = dessin.dessiner_courbe(lignes, IMAGES / "courbe.png", trader=trader)
    cime = arbre.branches.get(arbre.cime) if arbre.cime else None
    if trader:
        note = (f"Cime {cime.nom} : lien entre gain prévu et gain réel {dessin._virgule(cime.score, 2)} % "
                f"(2020-2022, jamais appris ; 0 = au hasard). " if cime and cime.score is not None else "")
    else:
        note = (f"Cime {cime.nom} : {dessin._virgule(cime.score)} % des mouvements bien devinés (2020-2022). "
                if cime and cime.score is not None else "") + portes.resume(arbre, portes.lire())
    resume = f"{arbre.battements} battement(s), {len(arbre.vivantes())} branche(s) vivante(s). " + note
    titre = "COLLAPSAR : premier battement (essai)" if essai else "COLLAPSAR : l'arbre"
    ok1 = telephone.envoyer_image(f1, titre, resume)
    ok2 = telephone.envoyer_image(f2, "COLLAPSAR : progrès de la cime", resume)
    # même si l'envoi échoue, on ne réessaie qu'au prochain rendez-vous (sinon un envoi raté se répète à chaque
    # battement) ; une erreur de dessin ou d'envoi ne doit JAMAIS arrêter le cœur (voir l'appel, protégé)
    arbre.envois["dernier"] = maintenant()
    journal.ecrire("images", envoyees=bool(ok1 and ok2))
    dire(f"images {'envoyées' if ok1 and ok2 else 'NON envoyées'} au téléphone")


def main():
    global VISION, LARGEUR_TRADER
    VIE.mkdir(parents=True, exist_ok=True)
    prendre_verrou()
    reglages = yaml.safe_load(REGLAGES.read_text(encoding="utf-8")) if REGLAGES.exists() else {}
    minutes = float(reglages.get("battement_minutes", 15))
    VISION = reglages.get("vision", "racines")
    LARGEUR_TRADER = float(reglages.get("largeur_trader", 1.0))
    trader = VISION == "trader"
    appareil = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    journal = Journal(VIE / "journal_croissance.jsonl")
    dire(f"réveil du cœur ({appareil}), battement de {minutes:g} min")

    donnees = {}
    for nom in dm.liste_marches():
        df = dm.charger(nom)
        if len(df) >= dm.MIN_BOUGIES:
            donnees[nom] = df
    dire(f"{len(donnees)} marchés chargés, {sum(len(d) for d in donnees.values()):,} bougies de 15 min "
         f"(toutes avant 2023)".replace(",", " "))
    # tout l'historique : les années en bougies d'1 heure d'avant les 15 minutes (data/fx_h1, si téléchargées)
    horaires = {m: dm.charger_horaire(m, avant=df["time"].iloc[0]) for m, df in donnees.items()}
    dire(f"{sum(len(h) for h in horaires.values()):,} bougies d'1 heure en plus (années d'avant les 15 minutes, "
         f"{sum(1 for h in horaires.values() if len(h))} marchés)".replace(",", " "))
    g = Graphique(donnees, appareil, horaires)
    del donnees, horaires
    ex = vision_trader.VisionTrader(g) if trader else Exercices(g)
    unite = "% de lien prévu/réel (2020-2022)" if trader else "% des mouvements bien devinés"
    dire(f"vision « {VISION} » : {len(ex.idx_apprend):,} situations d'apprentissage, "
         f"{len(ex.idx_controle):,} de contrôle".replace(",", " "))

    if ETAT.exists():
        arbre = Arbre.charger(ETAT)
        dire(f"l'arbre reprend : {arbre.battements} battements, cime {arbre.cime}")
    else:
        arbre = Arbre(Reglages(**reglages.get("arbre", {})))
        graine = arbre.naitre([], TEMPERAMENT_GRAINE)
        torch.manual_seed(0)
        c = nouveau_cerveau(graine.temperament, appareil)
        sauver_branche(graine.nom, c, optimiseur(c, graine.temperament))
        arbre.noter_seve()
        arbre.sauver(ETAT)
        journal.ecrire("naissance", branche=graine.nom, parents=[], temperament=graine.temperament)
        dire(f"la graine {graine.nom} est plantée")
    rng = random.Random()

    while True:
        if PAUSE.exists():
            time.sleep(60)
            continue
        if memoire_libre_go() < 1.5:
            dire(f"mémoire basse ({memoire_libre_go():.1f} Go) : j'attends 5 minutes")
            time.sleep(300)
            continue
        # toutes les branches vivantes poussent à chaque battement ; la sève décide combien de temps chacune
        ancienne_cime = arbre.cime
        parts = arbre.parts_de_seve()
        resultats, meme = {}, []
        for nom, part in parts.items():
            b = arbre.branches[nom]
            cerveau, opt = charger_branche(nom, b.temperament, appareil)
            gen = torch.Generator().manual_seed(rng.randrange(2**31))
            t0 = time.time()
            traits = ({"bruit": b.temperament.get("bruit"), "masque": b.temperament.get("masque")} if trader else {})
            travail = ex.entrainer(cerveau, opt, max(1.0, minutes * part), b.temperament["lot"], gen,
                                   miroir=b.temperament.get("miroir", 0.0), **traits)
            sauver_branche(nom, cerveau, opt)
            note = ex.controler(cerveau)
            # vision du trader : les branches sont jugées sur le LIEN prévu/réel (14/10 après-midi : la note des 10 %
            # de coups les plus sûrs bougeait de ±3 points d'une mesure à l'autre), avec retour en arrière anti-par-cœur
            valeur, evenement = (garder_ou_revenir(b, note[CLE], cerveau, appareil) if trader
                                 else (note["score"], None))
            arbre.noter(nom, round(valeur, 3), bonnes=round(note["bonnes"], 3))
            if evenement:
                journal.ecrire("retour", branche=nom, texte=evenement)
                dire(f"  branche {nom} : {evenement}")
            resultats[nom] = {"seve": round(part, 3), "minutes": round((time.time() - t0) / 60, 1),
                              "exercices": travail["exercices"], "perte": round(travail["perte"], 4),
                              "score": note["score"], "bonnes": note["bonnes"]}
            if trader:
                resultats[nom]["details"] = vision_trader.details(note)
                meme.append(0.0)                                  # lien : 0 = elle ne voit rien
                dire(f"  branche {nom} (sève {part:.0%}) : {travail['exercices']:,} coups étudiés, "
                     f"coups les plus sûrs {note['score']:+.2f} % du risque (gagnants {note['bonnes']:.0f} %, "
                     f"lien prévu/réel {note.get('lien', float('nan')):+.2f} %, "
                     f"sur ses années apprises {note.get('par_coeur', float('nan')):+.2f}, "
                     f"meilleur coup fixe sans regarder {note['repere']:+.2f}, hasard {note['hasard']:+.2f})"
                     .replace(",", " "))
            else:
                resultats[nom]["horizons"] = {h: note[h] for h in HORIZONS}
                meme.append(sum(note[h]["meme_reponse"] for h in HORIZONS) / len(HORIZONS))
                dire(f"  branche {nom} (sève {part:.0%}) : {travail['exercices']:,} exercices, "
                     f"{note['score']:.2f} {unite}".replace(",", " "))
            del cerveau, opt
        arbre.fin_de_battement()
        cime = arbre.branches[arbre.cime]
        journal.ecrire("battement", branches=resultats, meme_reponse=sum(meme) / len(meme),
                       cime=cime.nom, cime_score=cime.score, cime_bonnes=cime.scores[-1][2], vision=VISION)
        dire(f"battement {arbre.battements} : cime {cime.nom} à {cime.score:.2f} {unite}")

        for action in arbre.decisions():
            if action[0] == "couper":
                arbre.mourir(action[1], "coupée")
                archiver(action[1])
                journal.ecrire("coupe", branche=action[1])
                dire(f"branche {action[1]} coupée (archivée)")
            elif action[0] == "fusion":
                a, bb = arbre.branches[action[1]], arbre.branches[action[2]]
                arbre.dernier_essai_fusion = arbre.battements
                meilleure = a if a.score >= bb.score else bb
                ca, _ = charger_branche(a.nom, a.temperament, appareil)
                cb, _ = charger_branche(bb.nom, bb.temperament, appareil)
                f = fusionner(ca, cb, meilleure.temperament, appareil)
                nf = ex.controler(f)
                nf["score_choix"] = nf[CLE] if trader else nf["score"]
                if nf["score_choix"] > max(a.score, bb.score):
                    nb = arbre.naitre([meilleure.nom, (bb if meilleure is a else a).nom], meilleure.temperament)
                    sauver_branche(nb.nom, f, optimiseur(f, nb.temperament))
                    arbre.noter(nb.nom, round(nf["score_choix"], 3), bonnes=round(nf["bonnes"], 3), battement=False)
                    if trader:
                        garder_ou_revenir(nb, nf["score_choix"], f, appareil)
                    for p in (a.nom, bb.nom):
                        arbre.mourir(p, "fusion")
                        archiver(p)
                    journal.ecrire("fusion", reussie=True, parents=[a.nom, bb.nom], branche=nb.nom,
                                   score=nf["score_choix"])
                    dire(f"FUSION réussie : {a.nom} + {bb.nom} = {nb.nom} ({nf['score_choix']:.2f} %)")
                else:
                    journal.ecrire("fusion", reussie=False, parents=[a.nom, bb.nom], score=nf["score_choix"])
                    dire(f"fusion {a.nom} + {bb.nom} essayée : pas meilleure ({nf['score_choix']:.2f} %), abandonnée")
                del ca, cb, f
            elif action[0] == "bourgeon":
                mere = arbre.branches[action[1]]
                if mere.morte:
                    continue
                t = Arbre.muter(mere.temperament, rng)
                nb = arbre.naitre([mere.nom], t)
                cm, _ = charger_branche(mere.nom, mere.temperament, appareil)
                for m in cm.modules():
                    if isinstance(m, torch.nn.Dropout):
                        m.p = t["oubli"]
                sauver_branche(nb.nom, cm, optimiseur(cm, t))
                arbre.dernier_bourgeon = arbre.battements
                journal.ecrire("naissance", branche=nb.nom, parents=[mere.nom], temperament=t)
                dire(f"bourgeon : {nb.nom} naît de {mere.nom} ({t})")
                del cm
        if arbre.cime != ancienne_cime:
            journal.ecrire("cime", branche=arbre.cime)
            dire(f"nouvelle cime : {arbre.cime}")
        arbre.noter_seve()
        arbre.sauver(ETAT)
        torch.cuda.empty_cache()

        # porte « observer -> école » : vérifiée à part (sans arrêter le cœur) quand la cime atteint le niveau requis
        try:
            etat_portes = portes.lire()
            if not trader and portes.faut_il_verifier(arbre, etat_portes):
                portes.lancer_verification(arbre, etat_portes)
                journal.ecrire("verification_porte", porte="école", cime=arbre.cime)
                dire(f"porte de l'école : la cime {arbre.cime} atteint le niveau, vérification lancée")
        except Exception as e:
            dire(f"porte de l'école : erreur ({type(e).__name__}: {e})")

        now = datetime.now()
        dernier = datetime.fromisoformat(arbre.envois["dernier"]) if arbre.envois.get("dernier") else None
        if dernier is None or dernier < dernier_rendez_vous(now):
            try:
                envoyer_images(arbre, journal, essai=dernier is None)
            except Exception as e:                       # 14/10 : un défaut d'envoi avait arrêté le cœur
                arbre.envois["dernier"] = maintenant()
                dire(f"images : erreur ({type(e).__name__}: {e}), le cœur continue")
            arbre.sauver(ETAT)


if __name__ == "__main__":
    main()
