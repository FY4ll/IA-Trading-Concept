"""La DÉMO À BLANC en direct (15/10/2026, option B du chef de projet : le verdict, c'est le direct).

Toutes les 15 minutes : les nouvelles bougies de 15 minutes du compte FTMO (MetaTrader, lecture seule) sont ajoutées
à nos données (même heure : vérifié le 15/10, décalage 0, accord 99,4 % euro-dollar, 99,9 % S&P 500) ; COLLAPSAR
regarde quand c'est son heure (ou quand il est réveillé) ; un compte FICTIF de 100 000 $ applique ses décisions sur le
simulateur fidèle (murs FTMO, frais FTMO, frais de nuit de l'époque, fermeture avant les pauses) ; son carnet de bord
part sur le téléphone (format validé le 14/10).
Par défaut AUCUN ORDRE n'est envoyé (lecture des prix seulement). Depuis le 15/10 14h, avec vie/direct/mode.json
{"tradeco": true}, les positions du compte fictif sont RECOPIÉES sur le compte démo Tradeco (direct/tradeco.py) ;
le compte fictif reste le juge aux frais FTMO.
L'état du compte fictif est sauvé à chaque bougie (vie/direct/blanc.json) : un redémarrage reprend où il en était.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.direct.blanc [--eleve <fichier.pt>] [--une-fois]
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
import torch

from collapsar.cerveau.humain import REGARD_MAX, TraderHumain
from collapsar.donnees import marches as dm
from collapsar.ecole.regard import ClasseRegard, Etat, _note_evenements, _note_regard, donnees_regard
from collapsar.direct import tradeco
from collapsar.mains.simulateur import CAPITAL, Ordres
from collapsar.surveillance import carnet, telephone

TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"
MARCHES = ["EURUSD", "USDJPY", "XAUUSD", "USA500IDXUSD"]
DOSSIER = dm.RACINE / "collapsar" / "vie" / "direct"
ETAT = DOSSIER / "blanc.json"
HISTOIRE = pd.Timestamp("2019-06-01")                 # assez d'historique pour l'échelle « mois » (64 bougies)
ELEVE = dm.RACINE / "collapsar" / "vie" / "ecole_mondes" / "meilleur.pt"
MODE = DOSSIER / "mode.json"          # {"tradeco": true} : les positions sont recopiées sur le compte démo Tradeco


def sur_tradeco() -> bool:
    try:
        return bool(json.loads(MODE.read_text(encoding="utf-8")).get("tradeco"))
    except Exception:
        return False


def suffixe() -> str:
    return " (démo Tradeco)" if sur_tradeco() else " (à blanc)"


def dire(t):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {t}", flush=True)


def symboles_ftmo() -> dict:
    d = json.loads((dm.RACINE / "collapsar" / "mains" / "conditions_ftmo.json").read_text(encoding="utf-8"))
    from collapsar.mains.fiches import fiche
    return {m: d["symboles"].get(fiche(m).nom) for m in MARCHES}


def donnees_du_moment() -> dict[str, pd.DataFrame]:
    """Nos données + les bougies plus récentes du courtier (bougies CLOSES seulement). Avec Tradeco, MetaTrader reste
    connecté pour recopier les positions ensuite (prix Tradeco = nos données à 0,01 % près, heures identiques)."""
    if sur_tradeco():
        tradeco.connecter()
        syms = dict(tradeco.SYMBOLES)
    else:
        if not mt5.initialize(path=TERMINAL, timeout=60000):
            raise RuntimeError(f"MetaTrader injoignable : {mt5.last_error()}")
        syms = symboles_ftmo()
    donnees = donnees_regard(MARCHES, jusqua=pd.Timestamp("2100-01-01"))
    for m in list(donnees):
        df = donnees[m]
        df = df[df["time"] >= HISTOIRE]
        sym = syms.get(m) or m
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 1, 5000)      # 1 : la bougie en cours est exclue
        if r is not None and len(r):
            ft = pd.DataFrame({"time": pd.to_datetime(r["time"], unit="s"), "open": r["open"], "high": r["high"],
                               "low": r["low"], "close": r["close"], "volume": r["tick_volume"].astype(float)})
            df = pd.concat([df[df["time"] < ft["time"].iloc[0]], ft], ignore_index=True)
        donnees[m] = df.reset_index(drop=True)
    if not sur_tradeco():
        mt5.shutdown()
    return donnees


def _t(c, quand) -> int:
    return int(np.searchsorted(c.h.temps.values, pd.Timestamp(quand).to_datetime64()))


def restaurer(c: ClasseRegard, s: dict) -> Etat:
    e = Etat(c.h, 1)
    t0 = _t(c, s["derniere_bougie"])
    e.recommencer(torch.tensor([True]), torch.tensor([t0]))
    cpt = e.comptes
    for nom in ("u", "entree", "stop", "objectif"):
        getattr(cpt, nom)[0] = torch.tensor(s[nom], dtype=torch.float64)
    cpt.solde[0], cpt.solde_minuit[0] = s["solde"], s["solde_minuit"]
    if "att_type" in s:                       # 15/10 : ses ordres à l'avance survivent d'un passage à l'autre
        cpt.att_type[0] = torch.tensor(s["att_type"], dtype=cpt.att_type.dtype)
        cpt.att_prix[0] = torch.tensor(s["att_prix"], dtype=cpt.att_prix.dtype)
        cpt.att_montant[0] = torch.tensor(s["att_montant"], dtype=cpt.att_montant.dtype)
        cpt.att_reste[0] = torch.tensor(s["att_reste"], dtype=cpt.att_reste.dtype)
    cpt.jours_trades[0], cpt.jour_dernier_trade[0], cpt.jour_debut[0] = s["jours_trades"], s["jour_dernier_trade"], s["jour_debut"]
    # 15/10 : le prochain regard est gardé en NOMBRE DE BOUGIES (son heure est dans le futur : la bougie n'existe pas
    # encore ; gardé comme heure, il retombait sur la dernière bougie connue et elle regardait toutes les 15 min)
    if "prochain_dans" in s:
        e.prochain[0] = t0 + min(int(s["prochain_dans"]), REGARD_MAX)     # rendez-vous pris avant la limite de 4 h
    else:
        e.prochain[0] = _t(c, s["prochain"]) if s.get("prochain") else t0
    e.dernier[0] = _t(c, s["dernier"]) if s.get("dernier") else t0
    e.ouverture[0] = torch.tensor([_t(c, o) if o else -1 for o in s["ouverture"]])
    e.danger_vu[0], e.reveil[0] = s["danger_vu"], s["reveil"]
    e.memoire[0] = torch.tensor(s["memoire"])
    for nom in ("prix_vu", "taille_vue", "alerte_haut", "alerte_bas"):     # 15/10 : ses alertes survivent aussi
        if nom in s:
            getattr(e, nom)[0] = torch.tensor(s[nom], dtype=torch.float64)
    e.raison[0] = int(s.get("raison", 0))
    e.valeur_prec[0] = s["valeur_prec"]
    return e


def sauver(c: ClasseRegard, e: Etat, s: dict):
    cpt, h = e.comptes, c.h
    quand = lambda i: str(h.temps[min(int(i), h.T - 1)]) if int(i) >= 0 else None
    s.update({"derniere_bougie": str(h.temps[int(cpt.t[0])]), "u": cpt.u[0].tolist(), "entree": cpt.entree[0].tolist(),
              "stop": cpt.stop[0].tolist(), "objectif": cpt.objectif[0].tolist(), "solde": float(cpt.solde[0]),
              "att_type": cpt.att_type[0].tolist(), "att_prix": cpt.att_prix[0].tolist(),
              "att_montant": cpt.att_montant[0].tolist(), "att_reste": cpt.att_reste[0].tolist(),
              "prix_vu": e.prix_vu[0].tolist(), "taille_vue": e.taille_vue[0].tolist(),
              "alerte_haut": e.alerte_haut[0].tolist(), "alerte_bas": e.alerte_bas[0].tolist(), "raison": int(e.raison[0]),
              "solde_minuit": float(cpt.solde_minuit[0]), "jours_trades": int(cpt.jours_trades[0]),
              "jour_dernier_trade": int(cpt.jour_dernier_trade[0]), "jour_debut": int(cpt.jour_debut[0]),
              "prochain": quand(e.prochain[0]), "prochain_dans": int(e.prochain[0] - cpt.t[0]),
              "dernier": quand(e.dernier[0]),
              "ouverture": [quand(o) for o in e.ouverture[0].tolist()], "danger_vu": float(e.danger_vu[0]),
              "reveil": bool(e.reveil[0]), "memoire": e.memoire[0].tolist(), "valeur_prec": float(e.valeur_prec[0])})
    DOSSIER.mkdir(parents=True, exist_ok=True)
    ETAT.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def calme() -> bool:
    """Heures calmes (23h-8h, heure de la machine) : pas de message ; les décisions sont résumées à 8h."""
    h = datetime.now().hour
    return h >= 23 or h < 8


def resume(s: dict, c: ClasseRegard, e: Etat) -> str:
    cpt = e.comptes
    pos = [f"{m} {'acheteur' if u > 0 else 'vendeur'}" for m, u in zip(MARCHES, cpt.u[0].tolist()) if u != 0]
    prochain = (carnet.heure_paris(pd.Timestamp(s["derniere_bougie"]) + pd.Timedelta(minutes=15 * (1 + s.get("prochain_dans", 0))))
                if s.get("derniere_bougie") else None)
    return (f"Compte fictif : {s['valeur']:,.0f} $ ({(s['valeur'] / CAPITAL - 1) * 100:+.2f} % depuis le {s['debut'][:10]})".replace(",", " ")
            + f"\nPositions : {', '.join(pos) if pos else 'aucune'}"
            + (f"\nProchain regard : {prochain:%d/%m %Hh%M}" if prochain is not None else "")
            + f"\nDécisions en attente de la nuit : {s.get('nuit', 0)}" * bool(s.get("nuit"))
            + (f"\nCompte démo Tradeco : {s['tradeco']['capitaux']:,.0f}".replace(",", " ")
               + f" $ ({(s['tradeco']['capitaux'] / s['tradeco']['depart'] - 1) * 100:+.2f} % depuis le départ) ; "
               f"positions : {', '.join(s['tradeco']['positions']) or 'aucune'} ; ordres à l'avance : "
               f"{', '.join(s['tradeco'].get('ordres', [])) or 'aucun'}" if s.get("tradeco") else ""))


def envoyer(notes: list[dict]):
    for n in notes:
        if n["type"] == "regard":
            if not n["gestes"]:
                continue                                  # « je regarde, je garde » : pas de message (trop bavard)
            for titre, texte in carnet.messages_regard(n):
                telephone.envoyer_texte(titre + suffixe(), texte)
        else:
            titre, texte = carnet.message_evenement(n)
            telephone.envoyer_texte(titre + suffixe(), texte)


@torch.no_grad()
def un_passage(agent: TraderHumain, appareil: str, envoyer_tel: bool = True, depuis_bougies: int = 0) -> dict:
    donnees = donnees_du_moment()
    c = ClasseRegard(MARCHES, appareil, donnees)
    if ETAT.exists():
        s = json.loads(ETAT.read_text(encoding="utf-8"))
        e = restaurer(c, s)
    else:
        s = {"debut": str(c.h.temps[-1]), "regards": 0, "journal": []}
        e = Etat(c.h, 1)
        depart = max(c.h.T - 1 - depuis_bougies, 0)              # rodage : départ quelques bougies en arrière
        e.recommencer(torch.tensor([True]), torch.tensor([depart]))
        dire(f"compte fictif ouvert : 100 000 $, première bougie {c.h.temps[depart]}")
    notes = []
    cpt = e.comptes
    # 15/10 : le chef de projet peut la réveiller : fichier vie/direct/REGARDE (ou REGARDE.txt, créé avec l'Explorateur)
    demandes = [f for f in (DOSSIER / "REGARDE", DOSSIER / "REGARDE.txt") if f.exists()]
    if demandes:
        e.reveil[0] = True
        e.raison[0] = 6
        for f in demandes:
            f.unlink(missing_ok=True)
        dire("réveillée à la demande du chef de projet")
    while int(cpt.t[0]) < c.h.T - 1:
        qui = (cpt.t >= e.prochain) | e.reveil
        rg = None
        if bool(qui[0]):
            rg = c.decider(agent, e, qui, sur=True)
            notes.append(_note_regard(c, e, rg))
            c.noter_regard(e, rg)
            s["regards"] = s.get("regards", 0) + 1
        ordres = c.ordres(e, rg)
        if tradeco.fin_de_semaine(c.h.temps[int(cpt.t[0]) + 1]):
            # vendredi soir : tout est fermé avant la pause du week-end, comme sur Tradeco (rien ne s'ouvre)
            M = len(MARCHES)
            ordres = Ordres(cible=torch.zeros(1, M, dtype=torch.float64), attente_type=torch.full((1, M), -1),
                            attente_prix=torch.zeros(1, M, dtype=torch.float64),
                            attente_montant=torch.zeros(1, M, dtype=torch.float64),
                            attente_duree=torch.zeros(1, M, dtype=torch.long))
        r, ferme_seul, _ = c.avancer(e, ordres, rg)
        notes.extend(_note_evenements(c, e, r, ferme_seul))
        if bool(r["mort"][0]):
            dire("MUR FTMO touché sur le compte fictif : nouveau compte de 100 000 $")
            s.setdefault("comptes_perdus", 0)
            s["comptes_perdus"] += 1
            e.recommencer(torch.tensor([True]), cpt.t.clone())
    valeur = float(cpt.valeur(c.h.c[cpt.t], c.h.fx[cpt.t])[0])
    s["valeur"] = valeur
    sauver(c, e, s)
    if sur_tradeco():
        try:
            t_fin = c.h.temps[int(cpt.t[0])]
            fx = c.h.fx[int(cpt.t[0])]
            voulu = {}
            for j, m in enumerate(MARCHES):
                attente = None
                if int(cpt.att_type[0, j]) > 0:                 # son ordre à l'avance (en unités, comme le simulateur)
                    prix = float(cpt.att_prix[0, j])
                    attente = {"genre": int(cpt.att_type[0, j]), "prix": prix, "bougies": int(cpt.att_reste[0, j]),
                               "unites": float(cpt.att_montant[0, j]) / (prix * float(fx[j]))}
                voulu[m] = {"unites": float(cpt.u[0, j]), "stop": float(cpt.stop[0, j]),
                            "objectif": float(cpt.objectif[0, j]), "ouverture": s["ouverture"][j], "attente": attente}
            fait = tradeco.synchroniser(voulu, t_fin + pd.Timedelta(minutes=15))
            for f in fait:
                dire(f"Tradeco : {f}")
                # le carnet annonce déjà chaque décision : le téléphone ne reçoit que les échecs et les fermetures
                # de sécurité (coupe-circuit, fin de semaine) ; 10009 = ordre exécuté
                important = "COUPE-CIRCUIT" in f or "fin de semaine" in f or ("code" in f and "code 10009" not in f)
                if f == tradeco.ALGO_ETEINT:                 # rappel au plus une fois toutes les 3 heures
                    important = s.get("rappel_algo", "") < f"{pd.Timestamp.now() - pd.Timedelta(hours=3):%Y-%m-%d %H:%M}"
                    if important:
                        s["rappel_algo"] = f"{pd.Timestamp.now():%Y-%m-%d %H:%M}"
                        f = "Le bouton « Trading algo » est éteint dans MetaTrader : allume-le pour que les positions soient recopiées sur Tradeco."
                if important and envoyer_tel:
                    telephone.envoyer_texte("COLLAPSAR — Tradeco", f)
            s["tradeco"] = tradeco.compte()
        finally:
            mt5.shutdown()
    if envoyer_tel:
        actives = [n for n in notes if n["type"] != "regard" or n["gestes"]]
        if calme():
            s["nuit"] = s.get("nuit", 0) + len(actives)      # résumées à 8h
        else:
            envoyer(notes)
            moment = "matin" if datetime.now().hour < 20 else "soir"
            cle = f"{datetime.now():%Y-%m-%d}-{moment}"
            if s.get("dernier_resume") != cle and (moment == "matin" or datetime.now().hour >= 20):
                telephone.envoyer_texte(f"COLLAPSAR — point du {moment}{suffixe()}", resume(s, c, e))
                s["dernier_resume"], s["nuit"] = cle, 0
        sauver(c, e, s)
    return {"bougie": str(c.h.temps[int(cpt.t[0])]), "valeur": valeur, "notes": len(notes)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eleve", default=str(ELEVE))
    ap.add_argument("--une-fois", action="store_true")
    ap.add_argument("--sans-telephone", action="store_true")
    ap.add_argument("--appareil", default="cpu")
    ap.add_argument("--rodage", type=int, default=0, help="premier départ N bougies en arrière (essai)")
    ap.add_argument("--etat", default=None, help="autre fichier d'état (essai)")
    args = ap.parse_args()
    global ETAT
    if args.etat:
        ETAT = DOSSIER / args.etat
    agent = TraderHumain().to(args.appareil)
    cerveau = torch.load(args.eleve, map_location=args.appareil, weights_only=False)["cerveau"]
    agent.charger(cerveau)
    appris = cerveau["decisions.geste.bias"].shape[0]
    if appris < agent.decisions.geste.bias.shape[0]:
        # 15/10 : un élève d'avant les ordres à l'avance n'a jamais appris ce geste ; sans ça il en posait au hasard
        # (réglages jamais appris) et le téléphone recevait des « ordres à l'avance » qui ne voulaient rien dire
        with torch.no_grad():
            agent.decisions.geste.bias[appris:] = -1e4
        dire(f"gestes jamais appris par cet élève désactivés (il en connaît {appris})")
    agent.eval()
    dire(f"démo : élève {args.eleve}, marchés {', '.join(MARCHES)} "
         + ("(positions RECOPIÉES sur le compte démo Tradeco)" if sur_tradeco() else "(AUCUN ordre réel)"))
    while True:
        try:
            r = un_passage(agent, args.appareil, not args.sans_telephone, args.rodage)
            dire(f"bougie {r['bougie']} : compte fictif {r['valeur']:,.0f} $ ({(r['valeur'] / CAPITAL - 1) * 100:+.2f} %), "
                 f"{r['notes']} note(s) de carnet".replace(",", " "))
        except Exception as ex:
            dire(f"passage raté ({type(ex).__name__}: {ex}) : nouvel essai à la prochaine bougie")
        if args.une_fois:
            break
        maintenant = pd.Timestamp.now()
        prochaine = maintenant.ceil("15min") + pd.Timedelta(seconds=40)
        time.sleep(max(30.0, (prochaine - maintenant).total_seconds()))


if __name__ == "__main__":
    main()
