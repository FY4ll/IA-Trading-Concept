"""Lance L'ÉCOLE CRYPTO n° 2 (16/10/2026) — règles fixées dans l'en-tête de ecole/crypto2_monde.py.

École : 4 mondes à tour de rôle, données <= 2021 seulement : compte BTC + ETH (départs 2018-2021), son miroir, compte BTC
seul aux années où la foule est visible (départs 10/2020-2021), son miroir. Cerveau NEUF.
Contrôle toutes les 40 min (BTC + ETH, 2022-2023, données chargées jusqu'au 31/12/2023) : un challenge de 2 mois qui
démarre tous les 5 jours, elle ET son jumeau (mêmes gestes, sens à pile ou face) dans le même paquet ; référence : la
cassure C2 seule aux MÊMES départs (et la cassure v3 pour information) ; témoin du par cœur 2018-2021.
Meilleur élève = note PRUDENTE du projet (controleur_mondes.note_prudente). Garde-fous (REPRISE) : paralysie ou joueur
-> retour au meilleur élève, mémoire d'apprentissage vidée ; à la 2e fois, apprentissage 2 x plus lent.
Évaluation finale 2024-01 -> 2026-09 : `--final`, UNE fois (verrou vie/ecole_crypto2/final.json posé AVANT de regarder).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.crypto2_lancer --minutes 450
Arrêt propre : créer collapsar/vie/ecole_crypto2/STOP.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

import numpy as np
import pandas as pd
import torch

from collapsar.ecole import crypto2_monde as c2
from collapsar.ecole import crypto_monde as cm
from collapsar.ecole.controleur_mondes import note_prudente
from collapsar.ecole.crypto_lancer import dire, verrou
from collapsar.ecole.regard import ProfesseurRegard
from collapsar.juge.note import avantage_sur_hasard
from collapsar.mains.fiches import MIROIR

VIE = c2.VIE
FENETRE, PARALYSIE_POSITION, MURS_MAX = 8, 1.0, 5.0      # 8 leçons ; < 1 % du temps en position ; > 5 murs / 512 comptes
PAS_JOURS = 5


class Controle:
    """Un compte BTC + ETH sur une période (données chargées jusqu'à `jusqua_donnees`), ses départs, et les références
    aux mêmes départs : cassure C2 seule, cassure v3."""

    def __init__(self, nom, dev, jusqua_donnees, de, a, temoin=True, pas_jours=PAS_JOURS):
        self.nom, self.pas_jours = nom, pas_jours
        self.c = c2.ClasseCrypto2(c2.MARCHES, dev, jusqua_donnees)
        self.d = cm.departs(self.c, de, a, pas_jours)
        self.dt = cm.departs(self.c, c2.TEMOIN_DE, c2.TEMOIN_JUSQUA, 20) if temoin else self.d[:0]
        self.dates = [self.c.h.temps[int(i)] for i in self.d.cpu()]
        self.ref = c2.CompteC2(c2.MARCHES, c2.C2).fenetres(self.dates)
        self.ref_v3 = c2.CompteC2(c2.MARCHES, cm.CASSURE).fenetres(self.dates)

    def noter(self, agent, essais, masque=False):
        n, nt = len(self.d), len(self.dt)
        tous = torch.cat([self.d, self.d, self.dt])
        jum = torch.zeros(len(tous), dtype=torch.bool, device=self.c.dev)
        jum[n:2 * n] = True
        sm = torch.zeros_like(jum)
        sm[:n] = True
        self.c.masque = masque
        try:
            brut = c2.jouer(self.c, agent, tous, c2.DUREE, jumeau=jum, graine=12345, suivi_masque=sm)
        finally:
            self.c.masque = False
        elle = cm.agreger(brut, np.arange(n))
        j = cm.agreger(brut, np.arange(n, 2 * n))
        tem = cm.agreger(brut, np.arange(2 * n, 2 * n + nt)) if nt else None
        elle["note"] = avantage_sur_hasard(elle, [j], essais, c2.DUREE, 96 * self.pas_jours)
        elle["prudente"] = note_prudente(elle)
        elle["propositions"] = c2.lire_suivi(brut["suivi"])
        pe, pj = np.array(elle["pnl_comptes_marche"]), np.array(j["pnl_comptes_marche"])
        elle["avantage_marche_pct_mois"] = (pe - pj).mean(0).tolist()
        for x in (elle, j, tem):
            if x:
                x.pop("pnl_comptes_marche", None)
        jl = {k: v for k, v in j.items() if not isinstance(v, list)}
        if tem:
            tem = {k: v for k, v in tem.items() if not isinstance(v, list)}
        return {"elle": elle, "jumeau": jl, "temoin": tem}


def resume_ref(r):
    return {k: v for k, v in r.items() if not isinstance(v, list)}


def ligne(nom, r, ref):
    e, j, n = r["elle"], r["jumeau"], r["elle"]["note"]
    t = r["temoin"]
    p = e["propositions"]
    return (f"{nom}: elle {e['gain_moyen_pct']:+.2f} %/mois, réussis {e['challenges_reussis_pct']:.0f} %, murs "
            f"{e['murs_touches_pct']:.0f} %, inactifs {e['inactifs_pct']:.0f} % | jumeau {j['gain_moyen_pct']:+.2f} %/mois "
            f"({j['challenges_reussis_pct']:.0f} % / {j['murs_touches_pct']:.0f} %) | avantage {n['avantage_pct_mois']:+.2f} "
            f"± {n['incertitude_pct_mois']:.2f} (force {n['force_preuve']:+.1f}, seuil {n['seuil']:.1f}), prudente "
            f"{e['prudente']:+.2f} | cassure C2 {ref['gain_moyen_pct']:+.2f} %/mois ({ref['challenges_reussis_pct']:.0f} % / "
            f"{ref['murs_touches_pct']:.0f} %, avantage sur ses jumeaux {ref['avantage_pct_mois']:+.2f}) | "
            f"{e['trades_par_mois']:.1f} trades/mois, regarde {e['regards_par_jour']:.1f}/jour, tient "
            f"{e['tenue_moyenne_h']:.0f} h, stop {e['avec_stop_pct']:.0f} %, en position {e['temps_en_position_pct']:.0f} % | "
            f"propositions : dans le sens de C2 {p['dans_le_sens_de_c2_pct']:.0f} % / contre {p['contre_c2_pct']:.0f} % "
            f"du temps où C2 est active ; sens de C1 {p['dans_le_sens_de_c1_pct']:.0f} % / contre {p['contre_c1_pct']:.0f} %"
            + (f" | témoin 2018-2021 {t['gain_moyen_pct']:+.2f} %/mois" if t else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=450)
    ap.add_argument("--parties", type=int, default=512)
    ap.add_argument("--pas", type=int, default=512)
    ap.add_argument("--controle-minutes", type=float, default=40)
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--essai", action="store_true")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--rapport", action="store_true")
    args = ap.parse_args()
    if args.final:
        return final(args.appareil)
    if args.rapport:
        return rapport()
    dossier = VIE / "essai" if args.essai else VIE
    f_verrou = verrou(dossier)
    stop = dossier / "STOP"
    dev = args.appareil
    be = c2.MARCHES
    dire(f"école crypto n° 2 : {', '.join(be)} (+ miroirs), cerveau NEUF, propositions : {', '.join(c2.NOMS_PROP)} ; "
         f"regard minimum 1 h ; apprentissage 2018-2021, contrôle 2022-2023")
    mondes = [c2.ClasseCrypto2(m, dev, c2.FIN_APPRENTISSAGE) for m in
              (be, [x + MIROIR for x in be], ["BTCUSDT"], ["BTCUSDT" + MIROIR])]
    dire("mondes d'école construits ; contrôle 2022-2023 et références (cassure C2 seule, cassure v3)")
    jusqua = pd.Timestamp("2022-06-01") if args.essai else c2.CONTROLE_JUSQUA
    k = Controle("BTC + ETH 2022-2023", dev, jusqua, c2.CONTROLE_DE, jusqua)
    dire(f"référence cassure C2 seule, {len(k.d)} challenges de 2 mois : {k.ref['gain_moyen_pct']:+.2f} %/mois, réussis "
         f"{k.ref['challenges_reussis_pct']:.0f} %, murs {k.ref['murs_touches_pct']:.0f} % ; jumeaux "
         f"{k.ref['jumeaux_gain_pct']:+.2f} %/mois ; avantage sur ses jumeaux {k.ref['avantage_pct_mois']:+.2f} %/mois | "
         f"cassure v3 {k.ref_v3['gain_moyen_pct']:+.2f} %/mois")
    torch.manual_seed(20261016)
    agent = c2.TraderCrypto2().to(dev)
    fichier = dossier / "eleve.pt"
    lecons, meilleur, essais, alertes = 0, None, 0, 0
    if fichier.exists():
        etat = torch.load(fichier, map_location=dev, weights_only=False)
        agent.load_state_dict(etat["cerveau"])
        lecons, meilleur, essais, alertes = etat["lecons"], etat.get("meilleur"), etat.get("essais", 0), etat.get("alertes", 0)
        dire(f"reprise : {lecons} leçons")
    else:
        dire(f"départ : cerveau NEUF ({sum(p.numel() for p in agent.parameters()):,} connexions)".replace(",", " "))
    depart_cerveau = {kk: v.clone() for kk, v in agent.state_dict().items()}
    vitesse = 3e-4 / (2 if alertes >= 2 else 1)
    prof = ProfesseurRegard(mondes, agent, parties=args.parties, pas=args.pas, graine=lecons, de=c2.APPRENDRE_DE,
                            jusqua=c2.FIN_APPRENTISSAGE, duree=c2.DUREE, paquet=512, vitesse=vitesse,
                            vitesse_yeux=vitesse / 3)
    prof.installer(2, mondes[2], c2.FOULE_DE, c2.FIN_APPRENTISSAGE)
    prof.installer(3, mondes[3], c2.FOULE_DE, c2.FIN_APPRENTISSAGE)
    journal = dossier / "journal.jsonl"
    fin = time.time() + args.minutes * 60
    prochain = time.time() + args.controle_minutes * 60
    recents = []

    def sauver(f, **plus):
        torch.save({"cerveau": agent.state_dict(), "lecons": lecons, "meilleur": meilleur, "essais": essais,
                    "alertes": alertes, **plus}, f)

    def ecrire(obj):
        with journal.open("a", encoding="utf-8") as j:
            j.write(json.dumps(obj, ensure_ascii=False, default=float) + "\n")

    def retour(raison):
        nonlocal alertes, recents
        alertes += 1
        src = dossier / "meilleur.pt"
        if src.exists():
            agent.load_state_dict(torch.load(src, map_location=dev, weights_only=False)["cerveau"])
        else:
            agent.load_state_dict(depart_cerveau)
        prof.opt.state.clear()
        if alertes >= 2:
            for g in prof.opt.param_groups:
                g["lr"] = g["lr"] / 2
        recents = []
        dire(f"GARDE-FOU ({raison}) : retour au meilleur élève, mémoire d'apprentissage vidée"
             f"{' et apprentissage 2 x plus lent' if alertes >= 2 else ''} (alerte n° {alertes})")
        ecrire({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons, "garde_fou": raison,
                "alerte": alertes})

    def controler():
        nonlocal meilleur, essais
        essais += 1
        t0 = time.time()
        res = k.noter(agent, essais)
        dire("CONTRÔLE " + ligne(k.nom, res, k.ref))
        note = float(res["elle"]["prudente"])
        ecrire({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons, "essais": essais, "note": note,
                "controle": res, "cassure_c2": resume_ref(k.ref), "cassure_v3": resume_ref(k.ref_v3)})
        if meilleur is None or note > meilleur:
            meilleur = note
            sauver(dossier / "meilleur.pt", controle=res)
            dire(f"nouveau meilleur élève (note prudente {note:+.3f}, leçon {lecons})")
        sauver(fichier)
        dire(f"contrôle fait en {time.time() - t0:.0f} s ; note prudente {note:+.3f} (meilleure {meilleur:+.3f})")
        e = res["elle"]
        if e["trades_par_mois"] < 0.5 or e["inactifs_pct"] > 30:
            retour(f"paralysie au contrôle : {e['trades_par_mois']:.1f} trades/mois, {e['inactifs_pct']:.0f} % inactifs")
        elif e["murs_touches_pct"] > 25:
            retour(f"joueur au contrôle : {e['murs_touches_pct']:.0f} % de murs")
        try:
            rapport(dossier)
        except Exception as ex:                 # le rapport ne doit jamais arrêter l'école
            dire(f"rapport non écrit : {type(ex).__name__} {ex}")

    controler()
    fini = False
    try:
        while time.time() < fin and not stop.exists():
            t0 = time.time()
            jeu = prof.jouer()
            appris = prof.apprendre()
            lecons += 1
            recents = (recents + [(jeu["en_position_pct"], jeu["morts"])])[-FENETRE:]
            dire(f"leçon {lecons} ({'+'.join(x.replace('USDT', '') for x in prof.mondes[prof.k].marches)}) : "
                 f"regarde {jeu['regards_par_jour']:.1f}/jour, garde {jeu['garder_pct']:.0f} % / protège "
                 f"{jeu['proteger_pct']:.0f} % / change {jeu['changer_pct']:.0f} % / ordre à l'avance "
                 f"{jeu['attendre_pct']:.0f} % (risque {jeu['risque_moyen_pct']:.2f} %), en position "
                 f"{jeu['en_position_pct']:.0f} %, murs {jeu['morts']} (inactifs {jeu['inactifs']}), réussis "
                 f"{jeu['reussis']}, récompense/jour {jeu['recompense_par_jour']:+.3f} ({time.time() - t0:.0f} s)")
            ecrire({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons, **jeu, **appris})
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
        dire(f"école crypto n° 2 arrêtée après {lecons} leçons ({'fin normale' if fini else 'interrompue'})")


# ---------------------------------------------------------------------------------------------- évaluation finale
def final(dev="cuda"):
    verrou_f = VIE / "final.json"
    if verrou_f.exists():
        print("Évaluation finale DÉJÀ faite :", verrou_f.read_text(encoding="utf-8")[:3000])
        return
    meilleur = torch.load(VIE / "meilleur.pt", map_location=dev, weights_only=False)
    verrou_f.write_text(json.dumps({"quand": datetime.now().isoformat(timespec="seconds"), "etat": "en cours",
                                    "lecon_eleve": meilleur["lecons"]}), encoding="utf-8")   # posé AVANT de regarder
    agent = c2.TraderCrypto2().to(dev)
    agent.load_state_dict(meilleur["cerveau"])
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "lecon_eleve": meilleur["lecons"]}
    # 1) contrôle 2022-2023 (déjà vu par le choix) : avec et SANS ses propositions
    k = Controle("BTC + ETH 2022-2023", dev, c2.CONTROLE_JUSQUA, c2.CONTROLE_DE, c2.CONTROLE_JUSQUA, temoin=False)
    sortie["controle_avec"] = k.noter(agent, 1)
    sortie["controle_sans_propositions"] = k.noter(agent, 1, masque=True)
    dire("CONTRÔLE (avec) " + ligne(k.nom, sortie["controle_avec"], k.ref))
    dire("CONTRÔLE (sans propositions) " + ligne(k.nom, sortie["controle_sans_propositions"], k.ref))
    del k
    torch.cuda.empty_cache()
    # 2) la période jamais vue 2024-01 -> 2026-09, UNE fois
    kf = Controle("BTC + ETH 2024 -> 09/2026", dev, c2.FINAL_JUSQUA, c2.FINAL_DE, c2.FINAL_JUSQUA, temoin=False)
    sortie["final_avec"] = kf.noter(agent, 1)
    sortie["final_sans_propositions"] = kf.noter(agent, 1, masque=True)
    sortie["final_cassure_c2"] = resume_ref(kf.ref)
    sortie["final_cassure_v3"] = resume_ref(kf.ref_v3)
    sortie["final_departs"] = len(kf.d)
    dire("FINAL (avec) " + ligne(kf.nom, sortie["final_avec"], kf.ref))
    dire("FINAL (sans propositions) " + ligne(kf.nom, sortie["final_sans_propositions"], kf.ref))
    verrou_f.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    rapport()


# ---------------------------------------------------------------------------------------------- rapport
def _prop_lignes(p):
    f = lambda x: "—" if x != x else f"{x:.0f} %"
    return [f"| C2 active (part du temps) | {f(p['c2_actif_pct_du_temps'])} |",
            f"| quand C2 est active : elle est dans son sens / contre / à plat | {f(p['dans_le_sens_de_c2_pct'])} / "
            f"{f(p['contre_c2_pct'])} / {f(100 - p['dans_le_sens_de_c2_pct'] - p['contre_c2_pct'])} |",
            f"| ses ouvertures pendant C2 active : avec / contre C2 | {f(p['ouvertures_avec_c2_pct'])} / "
            f"{f(p['ouvertures_contre_c2_pct'])} |",
            f"| foule C1 active (part du temps) | {f(p['c1_actif_pct_du_temps'])} |",
            f"| quand C1 est active : dans son sens / contre / à plat | {f(p['dans_le_sens_de_c1_pct'])} / "
            f"{f(p['contre_c1_pct'])} / {f(100 - p['dans_le_sens_de_c1_pct'] - p['contre_c1_pct'])} |",
            f"| ses ouvertures pendant C1 active : avec / contre C1 | {f(p['ouvertures_avec_c1_pct'])} / "
            f"{f(p['ouvertures_contre_c1_pct'])} |",
            f"| achats parmi ses ouvertures : prix en haut du canal 24 h / en bas | "
            f"{f(p['achat_quand_prix_haut_du_canal_pct'])} / {f(p['achat_quand_prix_bas_du_canal_pct'])} |",
            f"| lien entre sa position et la place du prix dans le canal (-1 à +1) | {p['lien_position_canal']:+.2f} |",
            f"| achats parmi toutes ses ouvertures | {f(p['ouvertures_achat_pct'])} |"]


def rapport(dossier=VIE):
    lignes = [json.loads(x) for x in (dossier / "journal.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    ctrl = [x for x in lignes if "controle" in x]
    lecons = [x for x in lignes if "regards_par_jour" in x]
    gardes = [x for x in lignes if "garde_fou" in x]
    if not ctrl:
        return
    meilleur = max(ctrl, key=lambda x: x["note"])
    ref = ctrl[0]["cassure_c2"]
    v3 = ctrl[0]["cassure_v3"]
    L = ["# COLLAPSAR à l'école des cryptos n° 2 (16/10/2026)", "",
         "Question du chef de projet : « COLLAPSAR doit en être capable ». Un cerveau NEUF, sur BTC et ETH seulement, avec "
         "des PROPOSITIONS sous les yeux (des informations, pas des règles) : trouve-t-il un avantage, et bat-il la "
         "cassure seule ?", "",
         "## Comment", "",
         "- Code : `collapsar/ecole/crypto2_monde.py` (règles fixées dans l'en-tête avant tout résultat) et "
         "`collapsar/ecole/crypto2_lancer.py`. École, simulateur FTMO et cerveau (TraderHumain) de COLLAPSAR sans "
         "modification ; seules les propositions et le regard minimum sont ajoutés.",
         "- Marchés : BTCUSDT et ETHUSDT (Binance 15 min, filtre commun), + leurs miroirs pour apprendre. Frais FTMO réels : "
         "BTC 0,083 %, ETH 0,112 % par aller-retour, nuit 30 %/an, levier 1:1.",
         "- Propositions à ses yeux : place du prix dans le canal des 24 h ; signal de la cassure C2 du moment ; part des "
         "comptes Binance acheteurs et son rang sur 90 jours ; signal « contre la foule » C1 du moment ; heure et jour. "
         "La foule n'existe dans les données que depuis 10/2020 (BTC) et 12/2021 (ETH) : un monde d'école BTC 10/2020-2021 "
         "a été ajouté pour qu'elle la voie en apprenant.",
         "- Contre l'excès de trades : frais dans la récompense + regard minimum 1 h (rien d'autre d'imposé).",
         "- Apprentissage 2018-2021 ; contrôle 2022-2023 (challenge de 2 mois tous les 5 jours) contre son JUMEAU (mêmes "
         "gestes, sens à pile ou face) et contre la cassure C2 seule aux mêmes départs ; meilleur élève = note prudente "
         "(avantage sur le jumeau - incertitude - pénalité murs).", "",
         "## Progression au contrôle (BTC + ETH, 2022-2023, jamais appris)", "",
         "| contrôle | leçon | elle %/mois | jumeau | avantage ± incertitude (force) | réussis / murs | trades/mois | "
         "regards/jour | en position | sens de C2 / contre | note prudente | témoin 2018-21 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in ctrl:
        e, j = x["controle"]["elle"], x["controle"]["jumeau"]
        n, p, t = e["note"], e["propositions"], x["controle"].get("temoin")
        tem = f"{t['gain_moyen_pct']:+.2f}" if t else "—"
        L.append(f"| {x['essais']} | {x['lecon']} | {e['gain_moyen_pct']:+.2f} | {j['gain_moyen_pct']:+.2f} | "
                 f"{n['avantage_pct_mois']:+.2f} ± {n['incertitude_pct_mois']:.2f} ({n['force_preuve']:+.1f}) | "
                 f"{e['challenges_reussis_pct']:.0f} % / {e['murs_touches_pct']:.0f} % | {e['trades_par_mois']:.1f} | "
                 f"{e['regards_par_jour']:.1f} | {e['temps_en_position_pct']:.0f} % | "
                 f"{p['dans_le_sens_de_c2_pct']:.0f} / {p['contre_c2_pct']:.0f} % | {x['note']:+.2f} | {tem} |")
    e, j = meilleur["controle"]["elle"], meilleur["controle"]["jumeau"]
    L += ["", "## Meilleur élève (note prudente) contre la cassure C2 et le hasard (2022-2023)", "",
          f"Contrôle n° {meilleur['essais']}, leçon {meilleur['lecon']}.", "",
          "| qui | %/mois | challenges réussis | murs | avantage sur ses jumeaux (%/mois) |", "|---|---|---|---|---|",
          f"| COLLAPSAR | {e['gain_moyen_pct']:+.2f} | {e['challenges_reussis_pct']:.0f} % | {e['murs_touches_pct']:.0f} % | "
          f"{e['note']['avantage_pct_mois']:+.2f} (force {e['note']['force_preuve']:+.1f}, seuil {e['note']['seuil']:.1f}) |",
          f"| son jumeau | {j['gain_moyen_pct']:+.2f} | {j['challenges_reussis_pct']:.0f} % | {j['murs_touches_pct']:.0f} % | — |",
          f"| cassure C2 seule | {ref['gain_moyen_pct']:+.2f} | {ref['challenges_reussis_pct']:.0f} % | "
          f"{ref['murs_touches_pct']:.0f} % | {ref['avantage_pct_mois']:+.2f} |",
          f"| jumeaux de C2 | {ref['jumeaux_gain_pct']:+.2f} | {ref['jumeaux_reussis_pct']:.0f} % | "
          f"{ref['jumeaux_murs_pct']:.0f} % | — |",
          f"| (info) cassure v3 | {v3['gain_moyen_pct']:+.2f} | {v3['challenges_reussis_pct']:.0f} % | "
          f"{v3['murs_touches_pct']:.0f} % | {v3['avantage_pct_mois']:+.2f} |", "",
          f"Comportement : {e['trades_par_mois']:.1f} trades/mois (2 marchés), regarde {e['regards_par_jour']:.1f} fois par "
          f"jour, tient {e['tenue_moyenne_h']:.0f} h en moyenne, stop posé {e['avec_stop_pct']:.0f} %, en position "
          f"{e['temps_en_position_pct']:.0f} % du temps, baisse max moyenne {e['baisse_max_moyenne_pct']:.1f} %. "
          f"Argent par marché (BTC, ETH) : {', '.join(f'{v:+.3f}' for v in e['pnl_marche_pct_mois'])} %/mois ; "
          f"avantage sur le jumeau : {', '.join(f'{v:+.3f}' for v in e['avantage_marche_pct_mois'])}.", "",
          "### Ce qu'elle fait de ses propositions (meilleur élève, 2022-2023)", "", "| mesure | valeur |", "|---|---|"]
    L += _prop_lignes(e["propositions"])
    if gardes:
        L += ["", "## Garde-fous déclenchés", ""] + [f"- leçon {g['lecon']} : {g['garde_fou']}" for g in gardes]
    if lecons:
        x = lecons[-1]
        L += ["", f"École : {len(lecons)} leçons ; dernière : regarde {x['regards_par_jour']:.1f}/jour, en position "
              f"{x['en_position_pct']:.0f} %, risque {x['risque_moyen_pct']:.2f} %, murs {x['morts']} / 512 comptes."]
    vf = VIE / "final.json"
    if vf.exists() and dossier == VIE:
        c = json.loads(vf.read_text(encoding="utf-8"))
        L += ["", "## Évaluation finale (2024-01 -> 2026-09, jamais vue, ouverte UNE fois)", ""]
        if "final_avec" in c:
            L += [f"Élève de la leçon {c['lecon_eleve']} ; {c['final_departs']} challenges de 2 mois (un tous les 5 jours).",
                  "", "| période | qui | %/mois | réussis | murs | avantage sur ses jumeaux (%/mois) |",
                  "|---|---|---|---|---|---|"]
            for per, avec, sans, r2, r3 in (("2022-2023 (contrôle)", "controle_avec", "controle_sans_propositions",
                                             None, None),
                                            ("2024 -> 09/2026", "final_avec", "final_sans_propositions",
                                             "final_cassure_c2", "final_cassure_v3")):
                for nom, cle in (("COLLAPSAR", avec), ("COLLAPSAR sans propositions", sans)):
                    ee, jj = c[cle]["elle"], c[cle]["jumeau"]
                    nn = ee["note"]
                    L.append(f"| {per} | {nom} | {ee['gain_moyen_pct']:+.2f} | {ee['challenges_reussis_pct']:.0f} % | "
                             f"{ee['murs_touches_pct']:.0f} % | {nn['avantage_pct_mois']:+.2f} ± "
                             f"{nn['incertitude_pct_mois']:.2f} (force {nn['force_preuve']:+.1f}) |")
                    L.append(f"| {per} | son jumeau ({nom}) | {jj['gain_moyen_pct']:+.2f} | "
                             f"{jj['challenges_reussis_pct']:.0f} % | {jj['murs_touches_pct']:.0f} % | — |")
                if r2:
                    for nom, cle in (("cassure C2 seule", r2), ("(info) cassure v3", r3)):
                        rr = c[cle]
                        L.append(f"| {per} | {nom} | {rr['gain_moyen_pct']:+.2f} | {rr['challenges_reussis_pct']:.0f} % "
                                 f"| {rr['murs_touches_pct']:.0f} % | {rr['avantage_pct_mois']:+.2f} |")
            ee = c["final_avec"]["elle"]
            L += ["", f"Comportement 2024-2026 : {ee['trades_par_mois']:.1f} trades/mois, regarde "
                  f"{ee['regards_par_jour']:.1f}/jour, tient {ee['tenue_moyenne_h']:.0f} h, en position "
                  f"{ee['temps_en_position_pct']:.0f} %.", "", "Ses propositions en 2024-2026 :", "",
                  "| mesure | valeur |", "|---|---|"] + _prop_lignes(ee["propositions"])
        else:
            L.append("Commencée, pas finie (voir final.json).")
    verdict = dossier / "verdict.md"
    L += ["", "## Verdict", ""] + ([verdict.read_text(encoding="utf-8")] if verdict.exists() else
                                   ["(écrit à la fin de la séance)"])
    (dossier / "rapport.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
