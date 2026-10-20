"""Le carnet de bord du trader humain numérique (validé par le chef de projet le 14/10/2026 : « sinon j'ai un
fantôme »). Chaque regard et chaque événement devient un message court, au format :

    COLLAPSAR — Achat EURUSD
    Risque : 0,5 % du compte · Stop : 1,0720 · Objectif : 1,0910
    Je garde et je reviens dans 5 jours : lundi 19/10 vers 14h
    Compte : +1,2 % · Distance au mur du jour : 4,3 %

Heures données à l'heure de PARIS (les données sont à l'heure du serveur, New York + 7 h). Le même format servira au
compte fictif en direct (messages sur le téléphone) ; à l'école, il fabrique un carnet d'exemple à lire.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from collapsar.mains.simulateur import CAPITAL

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def heure_paris(temps_serveur: pd.Timestamp) -> pd.Timestamp:
    ny = (pd.Timestamp(temps_serveur) - pd.Timedelta(hours=7)).tz_localize("America/New_York", ambiguous=True,
                                                                           nonexistent="shift_forward")
    return ny.tz_convert("Europe/Paris")


def _nombre(x: float, decimales: int) -> str:
    return f"{x:,.{decimales}f}".replace(",", " ").replace(".", ",")


def _pct(x: float, signe: bool = False) -> str:
    return (f"{x:+.1f}" if signe else f"{x:.1f}").replace(".", ",") + " %"


def _decimales(prix: float) -> int:
    return 4 if prix < 10 else 3 if prix < 200 else 2 if prix < 10_000 else 1


def _quand(depuis: pd.Timestamp, jusqua: pd.Timestamp) -> str:
    p = heure_paris(jusqua)
    ecart = jusqua - depuis
    if ecart < pd.Timedelta(hours=1):
        dans = f"dans {int(ecart.total_seconds() // 60)} min"
    elif ecart < pd.Timedelta(hours=24):
        dans = f"dans {int(round(ecart.total_seconds() / 3600))} h"
    else:
        jours = int(round(ecart.total_seconds() / 86400))
        dans = f"dans {jours} jour" + ("s" if jours > 1 else "")
    return f"{dans} : {JOURS[p.dayofweek]} {p:%d/%m} vers {p.hour}h{p.minute:02d}".replace("h00", "h")


def messages_regard(note: dict) -> list[tuple[str, str]]:
    """Un message par geste (ou un seul « je regarde, je garde » si elle ne touche à rien)."""
    valeur = CAPITAL * (1 + note["compte_pct"] / 100)
    retour = f"Je reviens {_quand(note['temps'], note['retour'])}"
    compte = f"Compte : {_pct(note['compte_pct'], True)} · Distance au mur du jour : {_pct(note['mur_jour_pct'])}"
    if not note["gestes"]:
        return [("COLLAPSAR — Je regarde, je ne touche à rien", f"{retour}\n{compte}")]
    sortie = []
    if note.get("reveil"):                              # 15/10 : réveillée avant l'heure prévue
        compte = f"{compte}\n(Réveillée par {note['reveil']})"
    for g in note["gestes"]:
        d = _decimales(g["prix"])
        pos = g["position_dollars"]
        if g["geste"] == 3:                                # ordre à l'avance (15/10)
            if g.get("annule"):
                sortie.append((f"COLLAPSAR — Ordre annulé {g['marche']}", f"J'annule mon ordre en attente.\n{retour}\n{compte}"))
                continue
            sens = "Achat" if pos > 0 else "Vente"
            genre = "limite" if g["limite"] else "stop"
            explication = (("si le prix redescend à" if pos > 0 else "si le prix remonte à") if g["limite"]
                           else ("si le prix casse au-dessus de" if pos > 0 else "si le prix casse en dessous de"))
            sortie.append((f"COLLAPSAR — Ordre à l'avance : {sens} {genre} {g['marche']}",
                           f"{sens} {explication} {_nombre(g['prix_ordre'], d)} (prix actuel {_nombre(g['prix'], d)}), "
                           f"taille {_pct(abs(pos) / valeur * 100)} du compte, valable {g['duree_h']:.0f} h\n{retour}\n{compte}"))
            continue
        if g["geste"] == 2:
            quoi = "Achat" if pos > 0 else "Vente" if pos < 0 else "Fermeture"
        else:
            quoi = "Protections"
        titre = f"COLLAPSAR — {quoi} {g['marche']}"
        if quoi == "Fermeture":
            sortie.append((titre, f"Je ferme tout sur {g['marche']}.\n{retour}\n{compte}"))
            continue
        if g["stop"] is not None:
            risque = abs(pos) * abs(g["prix"] - g["stop"]) / g["prix"] / valeur * 100
            ligne = f"Risque : {_pct(risque)} du compte · Stop : {_nombre(g['stop'], d)}"
        else:
            ligne = f"Sans stop (taille : {_pct(abs(pos) / valeur * 100)} du compte)"
        ligne += f" · Objectif : {_nombre(g['objectif'], d)}" if g["objectif"] is not None else " · Aucun objectif"
        if g["stop"] is not None and g["objectif"] is not None and g["stop"] != g["prix"]:      # 15/10 : le ratio
            ligne += f" ({_nombre(abs(g['objectif'] - g['prix']) / abs(g['prix'] - g['stop']), 1)} R)"
        garde = "Je garde et je reviens" if pos else "Je reviens"
        sortie.append((titre, f"{ligne}\n{garde} {_quand(note['temps'], note['retour'])}\n{compte}"))
    return sortie


def message_evenement(ev: dict) -> tuple[str, str]:
    compte = f"Compte : {_pct(ev['compte_pct'], True)}"
    quand = heure_paris(ev["temps"])
    a = f"{JOURS[quand.dayofweek]} {quand:%d/%m} {quand:%H}h{quand:%M}"
    if ev["type"] == "mur":
        return "COLLAPSAR — MUR FTMO TOUCHÉ", f"Le compte a touché un mur FTMO ({a}). Partie perdue.\n{compte}"
    if ev["type"] == "inactif":
        return ("COLLAPSAR — COMPTE TERMINÉ (INACTIVITÉ)",
                f"30 jours sans ouvrir de trade ({a}) : FTMO termine le compte.\n{compte}")
    if ev["type"] == "reussi":
        return "COLLAPSAR — CHALLENGE RÉUSSI", f"+10 % atteint ({a}).\n{compte}"
    raison = "fermeture obligatoire avant la pause du marché" if ev["forcee"] else "stop ou objectif touché"
    return (f"COLLAPSAR — Position fermée sur {ev['marche']}",
            f"Fermée pendant mon absence ({a}) : {raison}. Je reviens regarder.\n{compte}")


def ecrire(notes: list[dict], fichier: Path) -> str:
    """Le carnet complet en texte (à l'école : carnet d'exemple d'un compte de contrôle)."""
    blocs = []
    for n in notes:
        messages = messages_regard(n) if n["type"] == "regard" else [message_evenement(n)]
        blocs += [f"{titre}\n{texte}" for titre, texte in messages]
    texte = "\n\n".join(blocs)
    Path(fichier).parent.mkdir(parents=True, exist_ok=True)
    Path(fichier).write_text(texte, encoding="utf-8")
    return texte
