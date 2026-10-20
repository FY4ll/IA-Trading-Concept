"""Lance L'ÉCOLE DE COLLAPSAR SUR LES CRYPTOS (16/10/2026) — règles fixées dans l'en-tête de ecole/crypto_monde.py.

École : 4 mondes à tour de rôle, données <= 2021 seulement : un compte qui trade BTC + ETH + les 12 cryptos du groupe A,
le même compte sur les prix retournés (miroir), un compte BTC + ETH, et son miroir. Départ : le meilleur élève de l'école
des mille mondes (vie/ecole_mondes/meilleur.pt ; colonnes des repères ajoutées à zéro).
Contrôle toutes les ~35 min (mêmes marchés, 2022-01 -> 2026-10, jamais appris) : un compte de 2 mois tous les 10 jours,
elle ET son jumeau (sens tiré à pile ou face, mêmes gestes) dans le même paquet, + témoin du par cœur (2018-2021).
Référence à battre : la cassure v3 (version retenue) aux MÊMES départs, mêmes frais, mêmes règles de challenge.
Meilleur élève = note PRUDENTE (avantage sur le jumeau - incertitude - 0,05 x (murs + inactifs) %), moyenne des deux
comptes (14 cryptos et BTC + ETH). Garde-fous (REPRISE) : paralysie (plus de position) ou joueur (murs) -> retour au
meilleur élève, mémoire d'apprentissage vidée ; à la 2e fois, apprentissage 2 x plus lent.
Groupe B : `--confirmation`, UNE fois (verrou vie/ecole_crypto/confirmation.json posé avant de regarder).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.crypto_lancer --minutes 240
Arrêt propre : créer collapsar/vie/ecole_crypto/STOP.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
import psutil
import torch

from collapsar.ecole import crypto_monde as cm
from collapsar.ecole.regard import ProfesseurRegard
from collapsar.juge.note import avantage_sur_hasard
from collapsar.mains.fiches import MIROIR

VIE = cm.VIE
DEPART = cm.dm.RACINE / "collapsar" / "vie" / "ecole_mondes" / "meilleur.pt"
APPRENDRE_DE = pd.Timestamp("2017-09-01")
FENETRE, PARALYSIE_POSITION, MURS_MAX = 8, 1.0, 5.0      # 8 leçons ; < 1 % du temps en position ; > 5 murs / 512 comptes


def dire(texte):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {texte}", flush=True)


def verrou(dossier):
    f = dossier / "ecole.verrou"
    if f.exists():
        try:
            pid = int(f.read_text())
            if pid != os.getpid() and psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower():
                raise SystemExit(f"l'école crypto tourne déjà (processus {pid})")
        except ValueError:
            pass
    dossier.mkdir(parents=True, exist_ok=True)
    f.write_text(str(os.getpid()))
    return f


def note_prudente(n: dict, x: dict) -> float:
    return n["avantage_pct_mois"] - n["incertitude_pct_mois"] - 0.05 * (x["murs_touches_pct"] + x["inactifs_pct"])


class Controle:
    """Un monde de contrôle (données jusqu'à 10/2026) + ses départs + la cassure aux mêmes départs."""

    def __init__(self, nom, marches, dev, de, jusqua, temoin=True, pas_jours=10):
        self.nom, self.marches = nom, marches
        self.c = cm.ClasseCrypto(marches, dev)
        self.d = cm.departs(self.c, de, jusqua, pas_jours)
        self.dt = cm.departs(self.c, cm.TEMOIN_DE, cm.TEMOIN_JUSQUA, 20) if temoin else self.d[:0]
        self.dates = [self.c.h.temps[int(i)] for i in self.d.cpu()]
        self.cassure = cm.CompteCassure(marches).construire()
        self.ref = self.cassure.fenetres(self.dates)

    def noter(self, agent, essais, duree=cm.DUREE):
        n, nt = len(self.d), len(self.dt)
        tous = torch.cat([self.d, self.d, self.dt])
        masque = torch.zeros(len(tous), dtype=torch.bool, device=self.c.dev)
        masque[n:2 * n] = True
        brut = cm.jouer(self.c, agent, tous, duree, jumeau=masque, graine=12345)
        elle = cm.agreger(brut, np.arange(n))
        jum = cm.agreger(brut, np.arange(n, 2 * n))
        tem = cm.agreger(brut, np.arange(2 * n, 2 * n + nt)) if nt else None
        elle["note"] = avantage_sur_hasard(elle, [jum], essais, duree, 96 * 10)
        elle["prudente"] = note_prudente(elle["note"], elle)
        pe, pj = np.array(elle["pnl_comptes_marche"]), np.array(jum["pnl_comptes_marche"])
        elle["avantage_marche_pct_mois"] = (pe - pj).mean(0).tolist()
        for x in (elle, jum, tem):
            if x:
                x.pop("pnl_comptes_marche", None)
        return {"elle": elle, "jumeau": {k: v for k, v in jum.items() if not isinstance(v, list)}, "temoin": tem}


def ligne(nom, r, ref):
    e, j, n = r["elle"], r["jumeau"], r["elle"]["note"]
    t = r["temoin"]
    return (f"{nom}: elle {e['gain_moyen_pct']:+.2f} %/mois, réussis {e['challenges_reussis_pct']:.0f} %, murs "
            f"{e['murs_touches_pct']:.0f} %, inactifs {e['inactifs_pct']:.0f} % | jumeau {j['gain_moyen_pct']:+.2f} %/mois "
            f"({j['challenges_reussis_pct']:.0f} % / {j['murs_touches_pct']:.0f} %) | avantage {n['avantage_pct_mois']:+.2f} "
            f"± {n['incertitude_pct_mois']:.2f} (force {n['force_preuve']:+.1f}, seuil {n['seuil']:.1f}), prudente "
            f"{e['prudente']:+.2f} | cassure {ref['gain_moyen_pct']:+.2f} %/mois ({ref['challenges_reussis_pct']:.0f} % / "
            f"{ref['murs_touches_pct']:.0f} %, avantage sur ses jumeaux {ref['avantage_pct_mois']:+.2f}) | comportement : "
            f"{e['trades_par_mois']:.1f} trades/mois, regarde {e['regards_par_jour']:.1f}/jour, tient {e['tenue_moyenne_h']:.0f} h, "
            f"stop {e['avec_stop_pct']:.0f} %, en position {e['temps_en_position_pct']:.0f} %"
            + (f" | témoin 2018-2021 {t['gain_moyen_pct']:+.2f} %/mois" if t else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=240)
    ap.add_argument("--parties", type=int, default=512)
    ap.add_argument("--pas", type=int, default=512)
    ap.add_argument("--controle-minutes", type=float, default=35)
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--essai", action="store_true")
    ap.add_argument("--confirmation", action="store_true")
    ap.add_argument("--rapport", action="store_true")
    args = ap.parse_args()
    if args.confirmation:
        return confirmation(args.appareil)
    if args.rapport:
        return rapport()
    dossier = VIE / "essai" if args.essai else VIE
    f_verrou = verrou(dossier)
    stop = dossier / "STOP"
    dev = args.appareil
    groupe_a, _ = cm.groupes()
    tous = ["BTCUSDT", "ETHUSDT"] + groupe_a
    be = ["BTCUSDT", "ETHUSDT"]
    dire(f"école crypto : {len(tous)} marchés ({', '.join(tous)}) ; apprentissage <= 2021, contrôle 2022-2026")
    mondes = [cm.ClasseCrypto(m, dev, cm.FIN_APPRENTISSAGE) for m in
              (tous, [x + MIROIR for x in tous], be, [x + MIROIR for x in be])]
    dire("mondes d'école construits ; contrôles et référence cassure v3 (frais FTMO commission comprise)")
    jusqua = pd.Timestamp("2022-06-01") if args.essai else cm.CONTROLE_JUSQUA
    controles = [Controle("14 cryptos", tous, dev, cm.CONTROLE_DE, jusqua), Controle("BTC + ETH", be, dev, cm.CONTROLE_DE, jusqua)]
    for k in controles:
        dire(f"référence cassure v3, compte {k.nom}, {len(k.d)} challenges de 2 mois 2022-2026 : {k.ref['gain_moyen_pct']:+.2f} "
             f"%/mois, réussis {k.ref['challenges_reussis_pct']:.0f} %, murs {k.ref['murs_touches_pct']:.0f} % ; jumeaux "
             f"{k.ref['jumeaux_gain_pct']:+.2f} %/mois ; avantage sur ses jumeaux {k.ref['avantage_pct_mois']:+.2f} %/mois")
    agent = cm.TraderCrypto().to(dev)
    fichier = dossier / "eleve.pt"
    lecons, meilleur, essais, alertes = 0, None, 0, 0
    if fichier.exists():
        etat = torch.load(fichier, map_location=dev, weights_only=False)
        agent.charger(etat["cerveau"])
        lecons, meilleur, essais, alertes = etat["lecons"], etat.get("meilleur"), etat.get("essais", 0), etat.get("alertes", 0)
        dire(f"reprise : {lecons} leçons")
    else:
        etat = torch.load(DEPART, map_location=dev, weights_only=False)
        agent.charger(etat["cerveau"])
        dire(f"départ : meilleur élève de l'école des mille mondes (leçon {etat.get('lecons')})")
    depart_cerveau = {k: v.clone() for k, v in agent.state_dict().items()}
    vitesse = 3e-4 / (2 if alertes >= 2 else 1)
    prof = ProfesseurRegard(mondes, agent, parties=args.parties, pas=args.pas, graine=lecons, de=APPRENDRE_DE,
                            jusqua=cm.FIN_APPRENTISSAGE, duree=cm.DUREE, paquet=512, vitesse=vitesse,
                            vitesse_yeux=vitesse / 3)
    journal = dossier / "journal.jsonl"
    fin = time.time() + args.minutes * 60
    prochain = time.time() + args.controle_minutes * 60
    recents = []

    def sauver(f, **plus):
        torch.save({"cerveau": agent.state_dict(), "lecons": lecons, "meilleur": meilleur, "essais": essais,
                    "alertes": alertes, **plus}, f)

    def retour(raison):
        nonlocal alertes, recents
        alertes += 1
        src = dossier / "meilleur.pt"
        if src.exists():
            agent.charger(torch.load(src, map_location=dev, weights_only=False)["cerveau"])
        else:
            agent.load_state_dict(depart_cerveau)
        prof.opt.state.clear()
        if alertes >= 2:
            for g in prof.opt.param_groups:
                g["lr"] = g["lr"] / 2
        recents = []
        dire(f"GARDE-FOU ({raison}) : retour au {'meilleur élève' if src.exists() else 'cerveau de départ'}, mémoire "
             f"d'apprentissage vidée{' et apprentissage 2 x plus lent' if alertes >= 2 else ''} (alerte n° {alertes})")
        with journal.open("a", encoding="utf-8") as j:
            j.write(json.dumps({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons,
                                "garde_fou": raison, "alerte": alertes}, ensure_ascii=False) + "\n")

    def controler():
        nonlocal meilleur, essais
        essais += 1
        t0 = time.time()
        res = {k.nom: k.noter(agent, essais, 600 if args.essai else cm.DUREE) for k in controles}
        for k in controles:
            dire("CONTRÔLE " + ligne(k.nom, res[k.nom], k.ref))
        note = float(np.mean([res[k.nom]["elle"]["prudente"] for k in controles]))
        with journal.open("a", encoding="utf-8") as j:
            j.write(json.dumps({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons, "essais": essais,
                                "note": note, "controle": res, "cassure": {k.nom: {kk: v for kk, v in k.ref.items()
                                                                                   if not isinstance(v, list)}
                                                                           for k in controles},
                                "cassure_marches": controles[0].cassure.par_marche, "marches": controles[0].marches},
                               ensure_ascii=False, default=float) + "\n")
        if meilleur is None or note > meilleur:
            meilleur = note
            sauver(dossier / "meilleur.pt", controle=res)
            dire(f"nouveau meilleur élève (note prudente {note:+.3f}, leçon {lecons})")
        sauver(fichier)
        dire(f"contrôle fait en {time.time() - t0:.0f} s ; note prudente {note:+.3f} (meilleure {meilleur:+.3f})")
        e = res["14 cryptos"]["elle"]
        if e["trades_par_mois"] < 0.5 or e["inactifs_pct"] > 30:
            retour(f"paralysie au contrôle : {e['trades_par_mois']:.1f} trades/mois, {e['inactifs_pct']:.0f} % inactifs")
        elif e["murs_touches_pct"] > 25:
            retour(f"joueur au contrôle : {e['murs_touches_pct']:.0f} % de murs")
        try:
            rapport(dossier)
        except Exception as ex:                 # le rapport ne doit jamais arrêter l'école
            dire(f"rapport non écrit : {type(ex).__name__} {ex}")

    controler()                                 # le point de départ (élève des mille mondes, jamais vu de crypto)
    fini = False
    try:
        while time.time() < fin and not stop.exists():
            t0 = time.time()
            jeu = prof.jouer()
            appris = prof.apprendre()
            lecons += 1
            recents = (recents + [(jeu["en_position_pct"], jeu["morts"])])[-FENETRE:]
            dire(f"leçon {lecons} ({len(prof.mondes[prof.k].marches)} marchés{' miroir' if jeu['monde'].endswith(MIROIR) else ''}) : "
                 f"regarde {jeu['regards_par_jour']:.1f}/jour, garde {jeu['garder_pct']:.0f} % / protège {jeu['proteger_pct']:.0f} % "
                 f"/ change {jeu['changer_pct']:.0f} % / ordre à l'avance {jeu['attendre_pct']:.0f} % (risque "
                 f"{jeu['risque_moyen_pct']:.2f} %), en position {jeu['en_position_pct']:.0f} %, murs {jeu['morts']} "
                 f"(inactifs {jeu['inactifs']}), réussis {jeu['reussis']}, récompense/jour {jeu['recompense_par_jour']:+.3f} "
                 f"({time.time() - t0:.0f} s)")
            with journal.open("a", encoding="utf-8") as j:
                j.write(json.dumps({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons, **jeu, **appris},
                                   ensure_ascii=False) + "\n")
            if len(recents) == FENETRE:
                pos = np.mean([r[0] for r in recents])
                murs = np.mean([r[1] for r in recents])
                if pos < PARALYSIE_POSITION:
                    retour(f"paralysie à l'école : en position {pos:.1f} % du temps sur {FENETRE} leçons")
                elif murs > MURS_MAX * args.parties / 512:
                    retour(f"joueur à l'école : {murs:.1f} murs par leçon sur {FENETRE} leçons")
            if time.time() >= prochain or time.time() >= fin or stop.exists():
                prochain = time.time() + args.controle_minutes * 60
                controler()
        fini = True
    finally:
        sauver(fichier)
        f_verrou.unlink(missing_ok=True)
        dire(f"école crypto arrêtée après {lecons} leçons ({'fin normale' if fini else 'interrompue'})")


# ---------------------------------------------------------------------------------------------- groupe B
def confirmation(dev="cuda"):
    verrou_b = VIE / "confirmation.json"
    if verrou_b.exists():
        print("Confirmation DÉJÀ faite :", verrou_b.read_text(encoding="utf-8")[:3000])
        return
    meilleur = torch.load(VIE / "meilleur.pt", map_location=dev, weights_only=False)
    verrou_b.write_text(json.dumps({"quand": datetime.now().isoformat(timespec="seconds"), "etat": "en cours",
                                    "lecon_eleve": meilleur["lecons"]}), encoding="utf-8")   # posé AVANT de regarder
    _, groupe_b = cm.groupes()
    agent = cm.TraderCrypto().to(dev)
    agent.charger(meilleur["cerveau"])
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "groupe_B": groupe_b, "lecon_eleve": meilleur["lecons"]}
    for nom, (de, a) in {"2022-2026": (cm.CONTROLE_DE, cm.CONTROLE_JUSQUA),
                         "avant 2022": (pd.Timestamp("2019-07-01"), cm.FIN_APPRENTISSAGE)}.items():
        k = Controle("groupe B " + nom, groupe_b, dev, de, a, temoin=False)
        r = k.noter(agent, 1)
        dire("CONFIRMATION " + ligne(k.nom, r, k.ref))
        sortie[nom] = {"controle": r, "cassure": {kk: v for kk, v in k.ref.items() if not isinstance(v, list)},
                       "cassure_marches": k.cassure.par_marche}
        del k
        torch.cuda.empty_cache()
    verrou_b.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    rapport()


# ---------------------------------------------------------------------------------------------- rapport
def rapport(dossier=VIE):
    lignes = [json.loads(x) for x in (dossier / "journal.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    ctrl = [x for x in lignes if "controle" in x]
    lecons = [x for x in lignes if "regards_par_jour" in x]
    gardes = [x for x in lignes if "garde_fou" in x]
    if not ctrl:
        return
    meilleur = max(ctrl, key=lambda x: x["note"])
    ref = ctrl[0]["cassure"]
    L = ["# COLLAPSAR à l'école des cryptos (16/10/2026)", "",
         "Question : le trader humain numérique (son petit cerveau, ses gestes libres : sens, stop, objectif, taille, ordres "
         "à l'avance, moment du prochain regard) trouve-t-il SEUL un avantage sur les cryptos ?", "",
         "## Comment", "",
         "- Code : `collapsar/ecole/crypto_monde.py` (règles fixées dans l'en-tête avant tout résultat) et "
         "`collapsar/ecole/crypto_lancer.py`. L'école, le cerveau et le simulateur FTMO sont ceux de COLLAPSAR, sans "
         "modification.",
         "- Marchés : BTC, ETH + groupe A (ADA, ATOM, BCH, DOGE, EOS, FIL, LTC, NEAR, SOL, UNI, XLM, XRP), bougies Binance "
         "filtrées (filtre commun). Groupe B gardé pour la confirmation.",
         "- Frais FTMO commission comprise (correction du 16/10) : BTC 0,083 %, ETH 0,112 %, autres 0,12 % par aller-retour ; "
         "nuit 30 %/an chaque nuit ; levier 1:1.",
         "- Elle apprend sur 2017-2021 seulement (et sur les mêmes prix retournés, contre le par cœur de la hausse) ; elle "
         "voit en plus, comme des informations, sa position dans les canaux 12-48 h et la distance aux zones zones supply and demand actives "
         "(4 h et 1 h).",
         "- Contrôle (années jamais apprises 2022 -> 10/2026) : un challenge de 2 mois qui démarre tous les 10 jours, sur un "
         "compte 14 cryptos et un compte BTC + ETH ; même chose pour son JUMEAU (mêmes gestes, sens tiré à pile ou face) "
         "et pour la cassure v3 (version retenue, mêmes frais, mêmes départs).",
         "- Départ : le meilleur élève de l'école des mille mondes (n'a jamais vu de crypto).", "",
         "## Progression au contrôle (2022-2026)", "",
         "| contrôle | leçon | 14 cryptos : elle %/mois | jumeau | avantage ± incertitude | réussis / murs | trades/mois | "
         "BTC+ETH : elle %/mois | avantage | réussis / murs | note prudente |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in ctrl:
        a, b = x["controle"]["14 cryptos"], x["controle"]["BTC + ETH"]
        ea, eb = a["elle"], b["elle"]
        L.append(f"| {x['essais']} | {x['lecon']} | {ea['gain_moyen_pct']:+.2f} | {a['jumeau']['gain_moyen_pct']:+.2f} | "
                 f"{ea['note']['avantage_pct_mois']:+.2f} ± {ea['note']['incertitude_pct_mois']:.2f} | "
                 f"{ea['challenges_reussis_pct']:.0f} % / {ea['murs_touches_pct']:.0f} % | {ea['trades_par_mois']:.1f} | "
                 f"{eb['gain_moyen_pct']:+.2f} | {eb['note']['avantage_pct_mois']:+.2f} ± {eb['note']['incertitude_pct_mois']:.2f} | "
                 f"{eb['challenges_reussis_pct']:.0f} % / {eb['murs_touches_pct']:.0f} % | {x['note']:+.2f} |")
    L += ["", "## Meilleur élève (note prudente) contre la cassure v3 et le hasard", "",
          f"Contrôle n° {meilleur['essais']}, leçon {meilleur['lecon']}.", "",
          "| compte (2022-2026) | qui | %/mois | challenges réussis | murs | avantage sur ses jumeaux (%/mois) |",
          "|---|---|---|---|---|---|"]
    for nom in ("14 cryptos", "BTC + ETH"):
        e, j, r = meilleur["controle"][nom]["elle"], meilleur["controle"][nom]["jumeau"], ref[nom]
        L.append(f"| {nom} | COLLAPSAR | {e['gain_moyen_pct']:+.2f} | {e['challenges_reussis_pct']:.0f} % | "
                 f"{e['murs_touches_pct']:.0f} % | {e['note']['avantage_pct_mois']:+.2f} (force {e['note']['force_preuve']:+.1f}, "
                 f"seuil {e['note']['seuil']:.1f}) |")
        L.append(f"| {nom} | son jumeau | {j['gain_moyen_pct']:+.2f} | {j['challenges_reussis_pct']:.0f} % | "
                 f"{j['murs_touches_pct']:.0f} % | — |")
        L.append(f"| {nom} | cassure v3 | {r['gain_moyen_pct']:+.2f} | {r['challenges_reussis_pct']:.0f} % | "
                 f"{r['murs_touches_pct']:.0f} % | {r['avantage_pct_mois']:+.2f} |")
        L.append(f"| {nom} | jumeaux de la cassure | {r['jumeaux_gain_pct']:+.2f} | {r['jumeaux_reussis_pct']:.0f} % | "
                 f"{r['jumeaux_murs_pct']:.0f} % | — |")
    e = meilleur["controle"]["14 cryptos"]["elle"]
    t = meilleur["controle"]["14 cryptos"].get("temoin")
    L += ["", f"Comportement (14 cryptos) : {e['trades_par_mois']:.1f} trades/mois, regarde {e['regards_par_jour']:.1f} fois "
          f"par jour, tient {e['tenue_moyenne_h']:.0f} h en moyenne, stop posé {e['avec_stop_pct']:.0f} %, en position "
          f"{e['temps_en_position_pct']:.0f} % du temps, baisse max moyenne {e['baisse_max_moyenne_pct']:.1f} %."]
    if t:
        L.append(f"Témoin du par cœur (2018-2021, années apprises) : {t['gain_moyen_pct']:+.2f} %/mois.")
    L += ["", "Par marché (compte 14 cryptos, 2022-2026) : son argent et son avantage sur le jumeau (%/mois du compte), "
          "et la cassure v3 seule sur le marché (%/mois à sa taille, force contre ses jumeaux) :", "",
          "| marché | trades/mois | son argent | avantage sur le jumeau | cassure %/mois | cassure force |", "|---|---|---|---|---|---|"]
    for i, m in enumerate(meilleur["marches"]):
        cp = meilleur["cassure_marches"].get(m, {})
        L.append(f"| {m} | {e['trades_marche_par_mois'][i]:.1f} | {e['pnl_marche_pct_mois'][i]:+.3f} | "
                 f"{e['avantage_marche_pct_mois'][i]:+.3f} | {cp.get('pct_mois', float('nan')):+.2f} | {cp.get('force', float('nan')):+.1f} |")
    if gardes:
        L += ["", "## Garde-fous déclenchés", ""] + [f"- leçon {g['lecon']} : {g['garde_fou']}" for g in gardes]
    if lecons:
        L += ["", f"École : {len(lecons)} leçons ; dernière : en position {lecons[-1]['en_position_pct']:.0f} %, risque "
              f"{lecons[-1]['risque_moyen_pct']:.2f} %, murs {lecons[-1]['morts']} / 512 comptes."]
    vb = VIE / "confirmation.json"
    if vb.exists() and dossier == VIE:
        c = json.loads(vb.read_text(encoding="utf-8"))
        L += ["", "## Confirmation : groupe B (jamais vu, ouvert UNE fois)", ""]
        if "groupe_B" in c and "2022-2026" in c:
            L += [f"Marchés : {', '.join(c['groupe_B'])} ; élève de la leçon {c['lecon_eleve']}.", "",
                  "| période | COLLAPSAR %/mois | son jumeau | avantage ± incertitude (force) | réussis / murs | cassure v3 %/mois | "
                  "cassure avantage sur ses jumeaux | cassure réussis / murs |", "|---|---|---|---|---|---|---|---|"]
            for p in ("avant 2022", "2022-2026"):
                x = c[p]
                e, j, r = x["controle"]["elle"], x["controle"]["jumeau"], x["cassure"]
                L.append(f"| {p} | {e['gain_moyen_pct']:+.2f} | {j['gain_moyen_pct']:+.2f} | {e['note']['avantage_pct_mois']:+.2f} ± "
                         f"{e['note']['incertitude_pct_mois']:.2f} ({e['note']['force_preuve']:+.1f}) | "
                         f"{e['challenges_reussis_pct']:.0f} % / {e['murs_touches_pct']:.0f} % | {r['gain_moyen_pct']:+.2f} | "
                         f"{r['avantage_pct_mois']:+.2f} | {r['challenges_reussis_pct']:.0f} % / {r['murs_touches_pct']:.0f} % |")
        else:
            L.append("Commencée, pas finie (voir confirmation.json).")
    L += ["", "## Verdict", "", "(écrit à la fin de la séance)"]
    (dossier / "rapport.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
