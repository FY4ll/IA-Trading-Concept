"""LE JOURNAL DE TRADING de MAGNETAR (18/10/2026, ordre du chef de projet) : comme le carnet de MetaTrader 5, propre à
CHAQUE compte, rempli au fil de SA vie, qu'elle consulte à chaque regard. AUCUNE règle : ce sont des informations
ajoutées à ce qu'elle voit (en dernier, poids à zéro au départ) ; elle apprend seule quoi en faire.

COMMENT UN COMPTE VIT DANS LE TEMPS (vérifié dans jeu.py, testé tests/test_journal_trading.py) : chaque compte a son
propre instant t (une ligne du monde = une bougie de 15 min). À chaque bougie, les comptes qui regardent décident à la
CLÔTURE de leur bougie t (ils ne voient que des bougies terminées), leurs ordres partent à l'ouverture de t + 1, puis le
simulateur avance TOUS les comptes d'une bougie (Table.avancer -> simulateur.pas_comptes : t -> t + 1). Jamais de retour
en arrière, jamais de saut : un compte vit son challenge bougie après bougie, dans l'ordre du temps, à l'école comme à
l'examen.

LES DEUX ONGLETS (comme MT5) :
- « Trade » (temps réel, son propre état, aucun futur) : ses positions ouvertes (sens, risque %, entrée, stop, objectif 1,
  destination, stop suiveur actif / remonté, prix actuel, flottant en $ et en R, meilleur R déjà atteint) et ses ordres en
  attente (prix, stop, objectif, destination, risque %, expiration). Ce que la vue lui donnait déjà (jeu.entrees_np :
  sens, ordre en attente, flottant en R, distances au stop / TP1 / destination / ordre en agitations, objectif 1 fait,
  temps tenu, validité restante) est COMPLÉTÉ ici par 12 valeurs (NOMS_TRADE).
- « Historique » : chaque trade FERMÉ (ouverture / fermeture : date, heure, prix ; stop et objectif d'origine, stop final,
  raison de sortie, résultat en $ et en R, meilleur et pire R atteints). Visible selon le réglage
  `journal.delai_historique` : `fermeture` (par défaut, comme MT5 : visible dès la décision qui suit la fermeture, à la
  clôture de la bougie où il s'est fermé) ou `lendemain` (visible à partir de J+1 00h00, heure du serveur, pour un trade
  fermé le jour J). Un trade non fermé n'est JAMAIS dans l'historique.

CE QU'ELLE VOIT DE SON HISTORIQUE (147 valeurs, NOMS_HISTORIQUE, calculées sur la carte graphique à chaque regard, sur
les seuls trades visibles) :
- les 10 trades passés les plus RESSEMBLANTS à la situation actuelle, pour un achat et pour une vente (ressemblance sur
  le résumé de la situation à la décision : unité et distance de la zone la plus proche de son côté, rebond / cassure,
  tendance, agitation, heure, tendance de chaque unité) : leur nombre, R moyen, part de gagnants, meilleur R, ressemblance
  moyenne ; et pour les 2 plus ressemblants, ce qu'ELLE RETROUVE SUR SON GRAPHIQUE (comme les flèches d'un trade d'il y a
  10 ans sur MT5, sans limite d'ancienneté) : la situation à l'entrée sur chaque unité (journalier, 4 h, 1 h, 15 min,
  5 min, 3 min : tendance, distance à ses zones des deux côtés), l'agitation, et le CHEMIN jusqu'à la sortie (meilleur R,
  pire R, heures jusqu'au meilleur, durée, R final, raison de sortie, ancienneté) ;
- ses 10 et 20 derniers trades : R moyen, série en cours (gagnante +, perdante -), baisse depuis le plus haut de son
  journal (% du capital), taille du journal, drapeaux « vide » et « court » (moins de 10 trades) ;
- ce qui marche pour elle EN CE MOMENT : R moyen de ses 20 derniers trades de chaque catégorie (achat / vente x rebond /
  cassure) et leur nombre ; R du dernier trade et heures depuis sa fermeture.
Valeurs neutres (0) quand il n'y a rien, avec les drapeaux.

UN JOURNAL PAR COMPTE : à l'école, un compte qui recommence un challenge garde son journal si le nouveau départ est
APRÈS la dernière fermeture de son journal (vie qui continue, chronologie respectée) ; sinon (départ plus tôt dans le
monde) il repart VIDE. À l'examen, chaque challenge commence avec un journal vide (un nouveau compte FTMO).

FICHIERS DE LOG (export façon MT5, à chaque génération, si l'arbre est greffé) : `<vie>/journal_trades/gNNNNN/` :
`<branche>_<examen|ecole>_historique.csv` (une ligne par trade fermé) et `<branche>_<examen|ecole>_trade.csv` (onglet
Trade à chaque regard : une ligne par position ou ordre en attente) pour la cime et les branches au journal ; rotation
(les 50 dernières générations + une toutes les 50). Images des 5 meilleurs et 5 pires trades de la cime à l'examen
toutes les 50 générations (`journal_trades/images/`, journal_dessin.py). Résumé : `python -m
collapsar.ecole.precision.journal_analyse`.

GREFFE SUR UNE SEULE BRANCHE (arbre ARRÊTÉ ; jamais automatique) :
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.journal_trading greffer --nouvelle [--dossier D] [--delai fermeture|lendemain]
  (ou --branche X pour une branche existante). Sauvegarde complète, NJ colonnes à ZÉRO ajoutées en DERNIER à l'entrée de
  sa première couche (décisions identiques, prouvé), journal.json écrit (le cœur allume aussi les fichiers de log).
  Retour arrière : `... journal_trading defaire [--dossier D]`.
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

from collapsar.ecole.precision import simulateur as SIM
from collapsar.ecole.precision.reglages import CAPITAL, R, UNITES, VIE
from collapsar.ecole.precision.vue import I_BRUTES, NU

VERSION = 1
CAPACITE = 256                      # trades gardés par compte (les plus anciens sortent au-delà)
KV = 10                             # trades ressemblants
ND = 2                              # trades ressemblants revus en détail (situation multi-unités + chemin)
UNITES_VUE = ("D1", "H4", "H1", "M15", "M5", "M3")
I_VUE = [UNITES.index(u) for u in UNITES_VUE]
I_TEND = [UNITES.index(u) for u in ("D1", "H4", "H1")]
QUINZE_NS = int(pd.Timedelta(minutes=15).value)
JOUR_NS = int(pd.Timedelta(days=1).value)
DELAIS = ("fermeture", "lendemain")

# ---- le résumé de la situation à la décision (pour un côté : achat ou vente)
NOMS_SITUATION = ("unite_zone", "distance_zone", "sans_zone", "part_cassure", "tendance", "agitation", "heure_sin",
                  "heure_cos") + tuple(f"{u}_{k}" for u in UNITES_VUE for k in ("tendance", "zone_meme_cote",
                                                                             "zone_en_face"))
NSIT = len(NOMS_SITUATION)
I_UNITES_SIT = slice(8, NSIT)
POIDS_RESSEMBLANCE = np.array([1, 1, 0.5, 1, 1, 1, 0.5, 0.5] + [0.25, 0, 0] * len(UNITES_VUE), np.float32)

# ---- raisons de sortie
RAISONS = ("stop", "stop à l'entrée (après objectif 1)", "stop suiveur", "objectif (destination)", "objectif 1 (tout)",
           "à la main", "fin de journée (pause)", "mur FTMO", "inactivité FTMO", "fin du challenge (encore ouverte)")
STOP_, STOP_ENTREE, SUIVEUR_, OBJECTIF, OBJECTIF1, MAIN, FIN_JOUR, MUR, INACTIF, FIN_CHALLENGE = range(len(RAISONS))
GROUPE_RAISON = (0, 0, 1, 2, 2, 3, 3, 0, 0, 3)      # stop pris / suiveur / objectif / à la main ou fin de journée
CATEGORIES = ("achat rebond", "achat cassure", "vente rebond", "vente cassure")

NOMS_TRADE = ("risque_position_pct", "suiveur_actif", "suiveur_remonte", "flottant_pct_capital", "prix_moins_entree",
              "meilleur_r_position", "ordre_stop_agit", "ordre_tp1_agit", "ordre_dest_agit", "ordre_laisser_courir",
              "ordre_risque_pct", "ordre_suiveur")
NT = len(NOMS_TRADE)
_COMPTE = ("r_moyen_10", "r_moyen_20", "serie", "baisse_journal", "taille_journal", "journal_vide", "journal_court") + \
    tuple(f"{c.replace(' ', '_')}_{k}" for c in CATEGORIES for k in ("r_moyen_20", "nombre")) + \
    ("dernier_r", "heures_depuis_dernier")
_DETAIL = ("ressemblance", "anciennete", "r_final", "meilleur_r", "pire_r", "heures_jusqu_au_meilleur", "duree",
           "sortie_stop", "sortie_suiveur", "sortie_objectif", "sortie_main") + NOMS_SITUATION[8:] + ("agitation",)
NOMS_HISTORIQUE = _COMPTE + tuple(f"{c}_{x}" for c in ("achat", "vente") for x in
                                  ("ressemblants_nombre", "ressemblants_r_moyen", "ressemblants_gagnants",
                                   "ressemblants_meilleur_r", "ressemblants_distance")
                                  + tuple(f"revu{i + 1}_{d}" for i in range(ND) for d in _DETAIL))
NH = len(NOMS_HISTORIQUE)
NJ = NT + NH                        # entrées ajoutées au cerveau d'une branche au journal
NOMS = NOMS_TRADE + NOMS_HISTORIQUE
assert len(_DETAIL) == 30 and NH == 17 + 2 * (5 + ND * 30)


# ============================================================================================== réglages
def delai_defaut() -> str:
    j = getattr(R(), "journal", None)
    d = getattr(j, "delai_historique", None) if j is not None else None
    return d or "fermeture"


def delai_branche(temperament: dict | None) -> str:
    """Délai de l'historique d'une branche : le réglage `journal.delai_historique` s'il existe (copie de réglages),
    sinon celui écrit à la greffe dans son tempérament, sinon « fermeture » (comme MT5)."""
    j = getattr(R(), "journal", None)
    d = getattr(j, "delai_historique", None) if j is not None else None
    if not d and temperament and isinstance(temperament.get("journal"), dict):
        d = temperament["journal"].get("delai_historique")
    d = d or "fermeture"
    assert d in DELAIS, d
    return d


def choix_branche(temperament: dict | None, etat: dict | None) -> tuple[bool, str]:
    """(journal ?, délai) du cerveau d'une branche : d'après ses poids s'ils existent, sinon son tempérament."""
    from collapsar.ecole.precision import cerveau as C
    if etat is not None:
        jr = C.a_journal(etat["cerveau"])
    else:
        jr = bool(temperament and temperament.get("journal"))
    return jr, delai_branche(temperament)


# ============================================================================================== fichiers de log
_LOGS = {"dossier": None}
_RECOLTE: dict = {}
ECHANTILLON = 32


def allumer_si_greffe(dossier: Path) -> bool:
    """Le cœur allume les fichiers de log si l'arbre a une branche au journal (journal.json)."""
    if (Path(dossier) / "journal.json").exists():
        _LOGS["dossier"] = Path(dossier)
        return True
    return False


def allumer_logs(dossier: Path | None):
    _LOGS["dossier"] = Path(dossier) if dossier else None


def logs_actifs() -> bool:
    return _LOGS["dossier"] is not None


def equiper(tb, net, phase: str, n_elle: int | None = None):
    """Donne un carnet à une table si le cerveau a le journal (il le voit) ou si les fichiers de log sont allumés.
    Sinon rien (tb.carnet reste None : exactement le comportement d'avant)."""
    voir = getattr(net, "n_journal", 0) > 0
    logs = logs_actifs() and (phase == "examen" or voir or getattr(net, "journal_logs", False))
    if not (voir or logs):
        return None
    cn = getattr(tb, "carnet", None)
    if cn is not None and cn.net is net and cn.voir == voir and cn.logs == logs:
        return cn
    B = tb.B
    if phase == "examen" and n_elle:
        hist = np.arange(B) < n_elle
        trade = np.zeros(B, bool)
        trade[np.unique(np.linspace(0, n_elle - 1, min(ECHANTILLON, n_elle)).round().astype(int))] = True
    else:
        hist = trade = np.arange(B) < ECHANTILLON
    tb.carnet = Carnet(tb, net, voir, getattr(net, "journal_delai", "fermeture"), logs, hist, trade)
    return tb.carnet


def recolter(tb, branche: str, phase: str):
    """Garde les lignes de log d'une table (avant qu'elle soit effacée) pour l'écriture de fin de génération."""
    cn = getattr(tb, "carnet", None)
    if cn is None or not cn.logs:
        return
    if phase == "examen":
        cn.terminer()
    _RECOLTE[(branche, phase)] = (list(cn.histo), list(cn.onglet))
    cn.histo.clear()
    cn.onglet.clear()


def generations_a_garder(gens: list[int], garder: int = 50, tous: int = 50) -> set[int]:
    gens = sorted(gens)
    return set(gens[-garder:]) | {g for g in gens if g % tous == 0}


def tourner(racine: Path, garder: int = 50, tous: int = 50) -> list[str]:
    """Rotation : garde les `garder` dernières générations + une toutes les `tous` ; rend les dossiers effacés."""
    d = {int(p.name[1:]): p for p in Path(racine).glob("g[0-9]*") if p.is_dir() and p.name[1:].isdigit()}
    ok = generations_a_garder(list(d), garder, tous)
    out = []
    for g, p in d.items():
        if g not in ok:
            shutil.rmtree(p, ignore_errors=True)
            out.append(p.name)
    return out


def ecrire_generation(dossier: Path, g: int, cime: str, examen, branches: dict, dire=print) -> Path | None:
    """Fin de génération : récolte les tables d'examen, écrit les CSV de la cime et des branches au journal, rotation,
    images des 5 meilleurs / 5 pires trades de la cime toutes les 50 générations."""
    for nom, br in branches.items():
        x = getattr(examen, "_tables", {}).get(id(br.net))
        if x is not None:
            recolter(x[0], nom, "examen")
    garder = {cime} | {n for n, br in branches.items() if getattr(br.net, "n_journal", 0) > 0}
    racine = Path(dossier) / "journal_trades"
    out = racine / f"g{g:05d}"
    out.mkdir(parents=True, exist_ok=True)
    ecrits = []
    for (nom, phase), (histo, onglet) in sorted(_RECOLTE.items()):
        if nom not in garder:
            continue
        br = branches.get(nom)
        role = ("cime" if nom == cime else "") + ("+journal" if br is not None and getattr(br.net, "n_journal", 0) else "")
        f1 = out / f"{nom}_{phase}_historique.csv"
        f2 = out / f"{nom}_{phase}_trade.csv"
        table_historique(histo).assign(branche=nom, role=role or "-").to_csv(f1, index=False, encoding="utf-8")
        table_onglet(onglet).assign(branche=nom).to_csv(f2, index=False, encoding="utf-8")
        ecrits += [f1.name, f2.name]
    _RECOLTE.clear()
    (out / "fait.json").write_text(json.dumps({"generation": g, "cime": cime, "fichiers": ecrits,
                                               "date": datetime.now().isoformat(timespec="seconds")},
                                              ensure_ascii=False), encoding="utf-8")
    tourner(racine)
    if g % 50 == 0:
        try:
            from collapsar.ecole.precision import journal_dessin as JD
            JD.images_meilleurs_pires(out / f"{cime}_examen_historique.csv", racine / "images" / f"g{g:05d}")
            JD.tourner_images(racine / "images")
        except Exception as ex:                   # une image ratée ne doit jamais arrêter le cœur
            dire(f"journal : images non faites ({type(ex).__name__}: {ex})")
    return out


def _dates(x) -> pd.Series:
    t = pd.to_datetime(pd.Series(np.asarray(x, np.int64)))
    return t.dt.strftime("%Y.%m.%d %H:%M").where(np.asarray(x, np.int64) > 0, "")


def nom_place(genre: str, i: int) -> str:
    """Texte d'un niveau choisi (cerveau.py : places d'entrée, de stop, de destination)."""
    K = R().yeux.zones_par_cote
    nz = NU * K
    if i is None or i < 0:
        return "-"
    i = int(i)
    if genre == "entree":
        return f"zone {UNITES[(i % nz) // K]} ({'bord proche' if i < nz else 'milieu'})"
    if i < nz:
        return f"zone {UNITES[i // K]} ({'bord lointain' if genre == 'stop' else 'zone en face'})"
    if i < nz + 2 * NU:
        return f"{'creux / sommet' if genre == 'stop' else 'sommet / creux'} {UNITES[(i - nz) // 2]}"
    return "laisser courir"


def nom_suiveur(u: int, apres_tp1: bool, apres_1r: bool = False, ag: float = 0.0) -> str:
    if u is None or u < 0:
        return "aucun"
    from collapsar.ecole.precision import suiveur as SV
    if apres_1r:                                     # suiveur après +1R (une branche)
        return SV.nom_option_1r(float(ag) if ag is not None and np.isfinite(ag) else 0.0, int(u))
    us = SV.unites() if SV.active() else ("D1", "H4", "H1", "M15")
    return f"{us[int(u)] if int(u) < len(us) else u} {'après objectif 1' if apres_tp1 else 'dès l entrée'}"


def table_historique(histo: list[dict]) -> pd.DataFrame:
    """L'onglet « Historique » (une ligne par trade fermé), prix bruts, comme un export MT5."""
    if not histo:
        return pd.DataFrame(columns=["ticket"])
    d = pd.DataFrame(histo)
    sit = np.stack(d.pop("sit").to_numpy())
    out = pd.DataFrame({
        "ticket": d["ticket"], "compte": d["compte"], "challenge": d["challenge"], "marche": d["marche"],
        "sens": np.where(d["sens"] > 0, "achat", "vente"), "entree": np.where(d["type"] == 1, "limite", "marché"),
        "pose_le": _dates(d["t_dec_ns"]), "ouverture": _dates(d["t_ouv_ns"]), "prix_ouverture": d["prix_ouv"].round(5),
        "volume": d["vol"], "risque_pct": d["risque"].round(3), "stop_origine": d["stop0"].round(5),
        "objectif1": d["tp1"].round(5), "part_objectif1": d["part"].round(2), "objectif1_atteint": d["tp1_fait"],
        "destination": d["dest"].map(lambda x: "laisser courir" if not np.isfinite(x) else round(x, 5)),
        "stop_suiveur": [nom_suiveur(a, b, r1, ag) for a, b, r1, ag in
                         zip(d["sv"], d["svtp1"], d.get("sv1r", pd.Series(False, index=d.index)),
                             d.get("svag", pd.Series(0.0, index=d.index)))],
        "fermeture": _dates(d["t_fin_ns"]), "prix_fermeture": d["prix_fin"].round(5), "stop_final": d["stop_fin"].round(5),
        "raison": [RAISONS[int(k)] for k in d["raison"]], "resultat_usd": d["pnl"].round(2), "r": d["r"].round(3),
        "meilleur_r": d["mfe"].round(3), "pire_r": d["mae"].round(3),
        "heures_jusqu_au_meilleur": d["h_best"].round(2), "duree_h": d["duree_h"].round(2),
        "zone_entree": [nom_place("entree", i) if t == 1 else "-" for i, t in zip(d["ent_code"], d["type"])],
        "stop_place": [nom_place("stop", i) for i in d["stop_code"]],
        "destination_place": [nom_place("dest", i) for i in d["dest_code"]],
        "categorie": [CATEGORIES[int(k)] for k in d["cat"]],
        "situation_unite_zone": [("aucune" if x > 1.1 else UNITES[int(round(x * (NU - 1)))]) for x in sit[:, 0]],
        "situation_distance_zone_agit": (sit[:, 1] * 3).round(2),
        "situation_genre": np.where(sit[:, 3] >= 0.5, "cassure", "rebond"),
        "situation_part_cassure": sit[:, 3].round(2), "situation_tendance": sit[:, 4].round(2),
        "situation_agitation_pct": (np.exp(sit[:, 5] * 1.5 - 4.5) * 100).round(3),
        "situation_heure": d["t_dec_ns"].map(lambda x: f"{pd.Timestamp(int(x)):%H:%M}" if x > 0 else ""),
    })
    for i, n in enumerate(NOMS_SITUATION[8:]):
        out[f"situation_{n}"] = sit[:, 8 + i].round(3)
    return out


def table_onglet(lignes: list[dict]) -> pd.DataFrame:
    """L'onglet « Trade » à chaque regard (une ligne par position ou ordre en attente)."""
    if not lignes:
        return pd.DataFrame(columns=["ticket"])
    d = pd.DataFrame(lignes)
    return pd.DataFrame({
        "regard": _dates(d["t_ns"]), "compte": d["compte"], "challenge": d["challenge"], "marche": d["marche"],
        "ligne": d["ligne"], "ticket": d["ticket"], "type": d["type"], "ouverture_ou_pose": _dates(d["t0_ns"]),
        "volume": d["vol"].round(2), "prix": d["prix"].round(5), "stop": d["stop"].round(5), "objectif1": d["tp1"].round(5), "part": d["part"].round(2),
        "destination": d["dest"].map(lambda x: "laisser courir" if not np.isfinite(x) else x),
        "stop_suiveur": d["suiveur"], "risque_pct": d["risque"].round(3), "prix_actuel": d["px"].round(5),
        "flottant_usd": d["flot"].round(2), "flottant_r": d["flot_r"].round(3), "meilleur_r": d["mfe"].round(3),
        "expiration": _dates(d["exp_ns"]), "solde": d["solde"].round(2), "valeur": d["valeur"].round(2)})


# ============================================================================================== ce qu'elle voit
_INDICES: dict = {}


def _indices(liste, dev) -> torch.Tensor:
    """Indices rangés UNE fois sur l'appareil (19/10/2026 : indexer avec une liste Python copie cette liste vers la carte
    graphique à chaque appel, ce qui est interdit pendant l'enregistrement d'un graphe de la carte, jeu.Decideur ; les
    deux tours d'échauffement du Decideur les créent avant l'enregistrement). Mêmes valeurs : mêmes résultats."""
    cle = (tuple(liste), str(dev))
    t = _INDICES.get(cle)
    if t is None:
        t = _INDICES[cle] = torch.tensor(list(liste), dtype=torch.long, device=dev)
    return t


def situation(s: dict, temps: torch.Tensor) -> torch.Tensor:
    """[n, J, 2, NSIT] : le résumé de la situation à la décision, pour un achat (côté 0) et une vente (côté 1)."""
    top, bot, okz = s["top"], s["bot"], s["ok"]                  # [n,J,U,2,K]
    p, A = s["p"], s["A"]
    i_brutes, i_tend, i_vue = (_indices(x, p.device) for x in (I_BRUTES, I_TEND, I_VUE))
    n, J = p.shape
    P, AA = p[:, :, None, None], A[:, :, None, None]
    inf = float("inf")

    def dist(tp, bt, ok):                    # distance hors de la zone (0 dedans), en agitations ; inf sans zone
        d = torch.where(P > tp, (P - tp) / AA, torch.where(P < bt, (P - bt) / AA, torch.zeros_like(tp)))
        return torch.where(ok, d, torch.full_like(d, inf))

    def proche(d):                           # [n,J,U,K] -> [n,J,U] : la zone la plus proche de chaque unité
        i = d.abs().argmin(-1, keepdim=True)
        return d.gather(-1, i).squeeze(-1)
    dem = proche(dist(top[:, :, :, 0], bot[:, :, :, 0], okz[:, :, :, 0]))      # zones de demande
    off = proche(dist(top[:, :, :, 1], bot[:, :, :, 1], okz[:, :, :, 1]))      # zones d'offre
    sw = s["sw"]
    tend_u = (torch.nan_to_num(torch.sign(sw[..., 0] - sw[..., 1])) + torch.nan_to_num(torch.sign(sw[..., 2] - sw[..., 3]))) / 2
    br = sw[:, :, i_brutes]
    fin_s, fin_c = torch.isfinite(br[..., 0]), torch.isfinite(br[..., 2])
    ag = ((torch.log(A / p) + 4.5) / 1.5)
    hs, hc = temps[:, None, 0].expand(n, J), temps[:, None, 1].expand(n, J)
    cotes = []
    for sg, meme, face in ((1.0, dem, off), (-1.0, off, dem)):
        a = meme.abs()
        iu = a.argmin(-1, keepdim=True)
        dz = meme.gather(-1, iu).squeeze(-1)
        trouve = torch.isfinite(dz)
        unite = torch.where(trouve, iu.squeeze(-1).float() / (NU - 1), torch.full_like(dz, 1.25))
        dzv = torch.where(trouve, (sg * dz / 3).clamp(-3, 3), torch.zeros_like(dz))
        if sg > 0:
            casse = ((p[..., None] > br[..., 0]) & fin_s).float().sum(-1) / fin_s.float().sum(-1).clamp(min=1)
        else:
            casse = ((p[..., None] < br[..., 2]) & fin_c).float().sum(-1) / fin_c.float().sum(-1).clamp(min=1)
        tend = sg * tend_u[:, :, i_tend].mean(-1)
        loin = lambda d: torch.where(torch.isfinite(d), (sg * d / 5).clamp(-2, 2), torch.full_like(d, 2.0))
        par_u = torch.stack([sg * tend_u[:, :, i_vue], loin(meme[:, :, i_vue]), loin(face[:, :, i_vue])], -1)
        cotes.append(torch.cat([torch.stack([unite, dzv, (~trouve).float(), casse, tend, ag, hs, hc], -1),
                                par_u.reshape(n, J, -1)], -1))
    out = torch.stack(cotes, 2)
    return torch.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


# ============================================================================================== le carnet d'une table
CHAMPS_DEC = ("type", "ent_code", "stop_code", "dest_code", "sv", "svtp1", "stop0", "tp1", "part", "dest", "t_dec",
              "ticket", "cat", "sv1r", "svag")


class Carnet:
    """Le journal de trading des B comptes d'une table : onglet Trade (état), Historique (trades fermés, sur la carte
    graphique pour qu'elle le consulte), lignes de log pour un échantillon de comptes."""

    def __init__(self, tb, net, voir: bool, delai: str, logs: bool, ech_hist: np.ndarray, ech_trade: np.ndarray):
        assert delai in DELAIS, delai
        U, B, J = tb.U, tb.B, tb.J
        self.tb, self.net, self.voir, self.delai, self.logs = tb, net, voir, delai, logs
        self.ech_hist, self.ech_trade = ech_hist & logs, ech_trade & logs
        self.B, self.J = B, J
        tns = np.asarray(U.t_ns, np.int64)
        self.t_ns = tns
        jo, jd = tns // JOUR_NS, (tns + QUINZE_NS) // JOUR_NS
        self.prochain_jour = np.searchsorted(jd, jo, side="right").astype(np.int64)   # 1re décision du lendemain
        self.heures = ((tns - tns[0]) / 3.6e12).astype(np.float64)
        self.glissement = float(R().monde.frais_stop_glissement)
        self.n_ch = np.zeros(B, np.int64)
        self.ticket = 0
        self.histo, self.onglet = [], []
        self.dernier = None
        z = lambda dt=np.float64, v=0: np.full((B, J), v, dt)
        self.a = {k: z(np.int64, -1) if k in ("type", "ent_code", "stop_code", "dest_code", "sv", "t_dec", "ticket", "cat")
                  else z(np.bool_, False) if k in ("svtp1", "sv1r") else z(np.float64, 0.0) if k == "svag"
                  else z(np.float64, np.nan) for k in CHAMPS_DEC}
        self.p = {k: v.copy() for k, v in self.a.items()}
        self.a_sit, self.p_sit = np.zeros((B, J, NSIT), np.float32), np.zeros((B, J, NSIT), np.float32)
        self.p_open = z(np.bool_, False)
        self.p_t = z(np.int64, -1)
        self.p_prix, self.p_vol, self.p_risque = z(), z(), z()
        self.p_mfe, self.p_mae, self.p_tmfe = z(), z(), z(np.int64, -1)
        self.dern_ns = np.full(B, -1, np.int64)
        self.hN_np = np.zeros(B, np.int64)
        if voir:
            dev = U.dev
            N = CAPACITE
            f = lambda *s_, dt=torch.float32: torch.zeros(*s_, dtype=dt, device=dev)
            self.hS, self.hSens, self.hR, self.hPnl, self.hHfin = f(B, N, NSIT), f(B, N), f(B, N), f(B, N), f(B, N)
            self.hCh = f(B, N, 6)
            self.hCat, self.hVis, self.hTk = f(B, N, dt=torch.long), f(B, N, dt=torch.long), f(B, N, dt=torch.long)
            self.hN = f(B, dt=torch.long)
            self.ar = torch.arange(N, device=dev)
            self.t_heures = torch.as_tensor(self.heures, dtype=torch.float32, device=dev)
            self.poids = torch.as_tensor(POIDS_RESSEMBLANCE, device=dev)
            self.groupe = torch.as_tensor(GROUPE_RAISON, dtype=torch.long, device=dev)

    # ------------------------------------------------------------------------------------------ vies et départs
    def vider(self):
        """Tous les comptes repartent d'un journal vide (examen : chaque challenge est un nouveau compte)."""
        self.hN_np[:] = 0
        self.dern_ns[:] = -1
        self.p_open[:] = False
        self.n_ch[:] = 0
        self.ticket = 0
        self.histo.clear()
        self.onglet.clear()
        if self.voir:
            self.hN.zero_()

    def avant_depart(self, i: np.ndarray, departs: np.ndarray):
        """Nouveaux challenges des comptes i : positions encore ouvertes notées « fin du challenge » ; le journal
        continue si le nouveau départ est APRÈS sa dernière fermeture, sinon il repart vide."""
        self._fin_challenge(i)
        cont = self.t_ns[np.asarray(departs, np.int64)] > self.dern_ns[i]
        vide = i[~cont]
        if len(vide):
            self.hN_np[vide] = 0
            self.dern_ns[vide] = -1
            if self.voir:
                self.hN[torch.as_tensor(vide, device=self.hN.device)] = 0
        self.p_open[i] = False
        self.n_ch[i] += 1

    def terminer(self):
        """Fin de l'examen : les positions encore ouvertes sont notées « fin du challenge » (jamais dans l'historique)."""
        self._fin_challenge(np.arange(self.B))

    def _fin_challenge(self, i):
        c = self.tb.cpt
        ouv = self.p_open[i] & (c.u[i] != 0)
        if not (self.logs and ouv.any()):
            return
        b, j = np.nonzero(ouv)
        b = np.asarray(i)[b]
        U = self.tb.U
        m = c.col[b, j]
        t = c.t[b]
        px = U.c[t, m]
        pnl = c.pnl_trade[b, j] + c.u[b, j] * (px - c.entree[b, j]) * U.fx[t, m]
        r = pnl / np.where(c.risque[b, j] > 0, c.risque[b, j], np.nan)
        self._noter(b, j, t, np.full(len(b), FIN_CHALLENGE), px, c.stop[b, j], pnl, r, inserer=False)
        self.p_open[b, j] = False

    # ------------------------------------------------------------------------------------------ à chaque regard
    def retenir(self, qui, choix, resume, k: int):
        """Ce que le décideur vient de calculer pour les comptes qui regardent (niveaux choisis, situation)."""
        ch = {kk: choix[kk][:k].cpu().numpy() for kk in ("entree", "stop", "dest") if kk in choix}
        self.dernier = (np.asarray(qui).copy(), ch, resume[:k].cpu().numpy() if resume is not None else None)

    def decision(self, qui: np.ndarray, g: dict):
        """Avant d'appliquer ses choix : onglet Trade (log) puis ordres notés en attente (ouverture à venir)."""
        tb, c = self.tb, self.tb.cpt
        if self.logs and self.ech_trade[qui].any():
            self._log_onglet(qui[self.ech_trade[qui]])
        ouv = g["ouvre"] & (c.col[qui] >= 0)
        if not ouv.any():
            return
        ii, jj = np.nonzero(ouv)
        b = qui[ii]
        d = self.dernier
        ok = d is not None and len(d[0]) == len(qui) and np.array_equal(d[0], qui)
        ch, res = (d[1], d[2]) if ok else ({}, None)
        cote = (g["sig"][ii, jj] < 0).astype(np.int64)
        self.a["type"][b, jj] = g["limite"][ii, jj].astype(np.int64)
        self.a["ent_code"][b, jj] = np.where(g["limite"][ii, jj], ch["entree"][ii, jj], -1) if "entree" in ch else -1
        self.a["stop_code"][b, jj] = ch["stop"][ii, jj] if "stop" in ch else -1
        self.a["dest_code"][b, jj] = ch["dest"][ii, jj] if "dest" in ch else -1
        if "suiveur_u" in g:
            self.a["sv"][b, jj] = g["suiveur_u"][ii, jj]
            self.a["svtp1"][b, jj] = g["suiveur_tp1"][ii, jj]
        else:
            self.a["sv"][b, jj] = -1
            self.a["svtp1"][b, jj] = False
        if "suiveur_1r" in g:                       # suiveur après +1R (une branche)
            self.a["sv1r"][b, jj] = g["suiveur_1r"][ii, jj]
            self.a["svag"][b, jj] = g["suiveur_ag"][ii, jj]
        else:
            self.a["sv1r"][b, jj] = False
            self.a["svag"][b, jj] = 0.0
        for k in ("stop", "tp1", "dest"):
            self.a["stop0" if k == "stop" else k][b, jj] = g[k][ii, jj]
        self.a["part"][b, jj] = np.where(np.isfinite(g["tp1"][ii, jj]), g["part"][ii, jj], 0.0)
        self.a["t_dec"][b, jj] = c.t[b]
        self.a["ticket"][b, jj] = self.ticket + np.arange(len(b)) + 1
        self.ticket += len(b)
        sit = res[ii, jj, cote] if res is not None else np.zeros((len(b), NSIT), np.float32)
        self.a_sit[b, jj] = sit
        self.a["cat"][b, jj] = cote * 2 + (sit[:, 3] >= 0.5)

    def onglet_trade(self, qui, px, A, fx, u, sg, att) -> np.ndarray:
        """[n, J, NT] : ce que l'onglet Trade ajoute à ce que la vue lui donnait déjà de sa position et de son ordre."""
        c = self.tb.cpt
        A = np.maximum(A, 1e-12)
        nr = lambda x: np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        pos_ = u != 0
        with np.errstate(invalid="ignore", divide="ignore"):
            ap, ast, atp, ade, au = (c.att_prix[qui], c.att_stop[qui], c.att_tp1[qui], c.att_dest[qui], c.att_u[qui])
            x = [np.where(pos_, c.risque[qui] / CAPITAL * 100, 0.0), (pos_ & (c.sv_u[qui] >= 0)).astype(float),
                 np.where(pos_ & (c.sv_u[qui] >= 0), np.minimum(c.sv_n[qui], 5) / 5, 0.0),
                 np.where(pos_, nr(u * (px - c.entree[qui]) * fx) / CAPITAL * 100, 0.0),
                 np.where(pos_, nr(sg * (px - c.entree[qui]) / A), 0.0),
                 np.where(pos_ & self.p_open[qui], self.p_mfe[qui], 0.0) / 2,
                 np.where(att, nr(np.abs(ap - ast) / A), 0.0),
                 np.where(att & np.isfinite(atp), nr(np.abs(atp - ap) / A), 0.0),
                 np.where(att & np.isfinite(ade), nr(np.abs(ade - ap) / A), 0.0),
                 (att & ~np.isfinite(ade)).astype(float),
                 np.where(att, nr(np.abs(au) * np.abs(ap - ast) * fx) / CAPITAL * 100, 0.0),
                 (att & (c.att_sv_u[qui] >= 0)).astype(float)]
        return np.stack(x, -1)

    @torch.no_grad()
    def historique(self, rang: torch.Tensor, t: torch.Tensor, q: torch.Tensor) -> torch.Tensor:
        """[n, J, NH] : ce qu'elle voit de son Historique (trades VISIBLES seulement), sur la carte graphique."""
        n, J = q.shape[:2]
        N = CAPACITE
        vis = self.visibles(rang, t)                                             # [n,N]
        R_, P_, C_, S_, Se, Hf, Ch = (x[rang] for x in (self.hR, self.hPnl, self.hCat, self.hS, self.hSens,
                                                         self.hHfin, self.hCh))
        now = self.t_heures[t]
        visf = vis.float()
        nv = visf.sum(-1)
        rev = vis.long().flip(-1).cumsum(-1).flip(-1)
        moy = lambda m, x: (x * m.float()).sum(-1) / m.float().sum(-1).clamp(min=1)
        gain = R_ > 0
        der = vis & (rev == 1)
        g_der = (gain & der).any(-1)
        diff = vis & (gain != g_der[:, None])
        minrev = torch.where(diff, rev, torch.full_like(rev, N + 1)).min(-1).values
        serie = torch.minimum(minrev - 1, nv.long()).float()
        serie = torch.where(g_der, serie, -serie) * (nv > 0).float()
        cum = (P_ * visf).cumsum(-1)
        baisse = (torch.cummax(cum, -1).values.clamp(min=0) - cum)[:, -1]
        h_der = torch.where(nv > 0, now - (Hf * der.float()).sum(-1), torch.zeros_like(nv)).clamp(min=0)
        cols = [moy(vis & (rev <= 10), R_) / 2, moy(vis & (rev <= 20), R_) / 2, serie / 5, baisse / 2,
                torch.log1p(nv) / 5, (nv == 0).float(), (nv < 10).float()]
        for k in range(4):
            m = vis & (C_ == k)
            sel = m & (m.long().flip(-1).cumsum(-1).flip(-1) <= 20)
            cols += [moy(sel, R_) / 2, sel.float().sum(-1) / 20]
        cols += [(R_ * der.float()).sum(-1) / 2, torch.log1p(h_der) / 5]
        compte = torch.stack(cols, -1)[:, None].expand(n, J, -1)
        cotes = []
        inf = float("inf")
        for sd, sg in ((0, 1.0), (1, -1.0)):
            m = vis & (Se == sg)
            d2 = (((q[:, :, sd, None, :] - S_[:, None]) ** 2) * self.poids).sum(-1)       # [n,J,N]
            d2 = torch.where(m[:, None, :], d2, torch.full_like(d2, inf))
            val, idx = torch.topk(d2, KV, dim=-1, largest=False)
            ok = torch.isfinite(val)
            okf = ok.float()
            cnt = okf.sum(-1)
            Rk = R_[:, None, :].expand(n, J, N).gather(-1, idx)
            dist = torch.where(ok, val, torch.zeros_like(val)).clamp(min=0).sqrt()
            best = torch.where(ok, Rk, torch.full_like(Rk, -inf)).max(-1).values
            part = [cnt / KV, (Rk * okf).sum(-1) / cnt.clamp(min=1) / 2,
                    ((Rk > 0).float() * okf).sum(-1) / cnt.clamp(min=1),
                    torch.where(cnt > 0, best, torch.zeros_like(best)) / 3, (dist * okf).sum(-1) / cnt.clamp(min=1)]
            det = []
            for i in range(ND):
                oi = okf[..., i:i + 1]
                ii = idx[..., i]                                                 # [n,J]
                Si = S_.gather(1, ii[..., None].expand(n, J, NSIT))
                Ci = Ch.gather(1, ii[..., None].expand(n, J, 6))
                Hi = Hf.gather(1, ii)
                # (comparaison plutôt que one_hot : one_hot vérifie ses valeurs, ce qu'un graphe de la carte refuse)
                gr = (self.groupe[Ci[..., 5].long().clamp(0, len(GROUPE_RAISON) - 1)][..., None] == self.ar[:4]).float()
                x = torch.cat([dist[..., i:i + 1], (torch.log1p(((now[:, None] - Hi) / 24).clamp(min=0)) / 5)[..., None],
                               Ci[..., 4:5] / 2, Ci[..., 0:1] / 3, Ci[..., 1:2],
                               torch.log1p(Ci[..., 2:3].clamp(min=0)) / 5, torch.log1p(Ci[..., 3:4].clamp(min=0)) / 5,
                               gr, Si[..., I_UNITES_SIT], Si[..., 5:6]], -1)
                det.append(x * oi)
            cotes.append(torch.cat([torch.stack(part, -1)] + det, -1))
        out = torch.cat([compte] + cotes, -1)
        return torch.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).clamp(-10, 10)

    def visibles(self, rang: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        """[n, CAPACITE] : trades de l'historique visibles à l'instant t (fermés, et selon le délai)."""
        return (self.ar[None, :] < self.hN[rang][:, None]) & (self.hVis[rang] <= t[:, None])

    # ------------------------------------------------------------------------------------------ à chaque bougie
    def apres_pas(self, u0, st0, tp0, de0, v_avant, actifs):
        """Après le pas du simulateur : ouvertures (l'ordre en attente devient position), fermetures (-> historique),
        meilleur / pire R des positions encore ouvertes."""
        tb, c, U = self.tb, self.tb.cpt, self.tb.U
        ev = c.evt
        n_t = c.t
        act = actifs[:, None]
        ouv = ((ev & (SIM.OUVERTE | SIM.EXECUTE)) != 0) & act
        if ouv.any():
            b, j = np.nonzero(ouv)
            for k in CHAMPS_DEC:
                self.p[k][b, j] = self.a[k][b, j]
            self.p_sit[b, j] = self.a_sit[b, j]
            self.p_t[b, j] = n_t[b]
            self.p_prix[b, j] = c.entree[b, j]
            self.p_vol[b, j] = c.u_init[b, j]
            self.p_risque[b, j] = c.risque[b, j] / np.maximum(v_avant[b], 1.0) * 100
            self.p_mfe[b, j] = 0.0
            self.p_mae[b, j] = 0.0
            self.p_tmfe[b, j] = n_t[b]
            self.p_open[b, j] = True
        r = c.r_ferme
        fermee = (np.isfinite(r) | ((u0 != 0) & (c.u == 0))) & act & self.p_open
        if fermee.any():
            self._fermer(*np.nonzero(fermee), u0, st0, tp0, de0)
        ouverte = (c.u != 0) & act & self.p_open
        if ouverte.any():
            b, j = np.nonzero(ouverte)
            m = c.col[b, j]
            n = n_t[b]
            sg = np.sign(c.u[b, j])
            dist = np.abs(self.p_prix[b, j] - self.p["stop0"][b, j])
            dist = np.where(dist > 0, dist, np.nan)
            fav = np.where(sg > 0, U.h[n, m], U.l[n, m])
            adv = np.where(sg > 0, U.l[n, m], U.h[n, m])
            rf = np.nan_to_num(sg * (fav - self.p_prix[b, j]) / dist)
            ra = np.nan_to_num(sg * (adv - self.p_prix[b, j]) / dist)
            mieux = rf > self.p_mfe[b, j]
            self.p_mfe[b, j] = np.maximum(self.p_mfe[b, j], rf)
            self.p_tmfe[b, j] = np.where(mieux, n, self.p_tmfe[b, j])
            self.p_mae[b, j] = np.minimum(self.p_mae[b, j], ra)

    def _fermer(self, b, j, u0, st0, tp0, de0):
        c, U = self.tb.cpt, self.tb.U
        e = c.evt[b, j]
        r = c.r_ferme[b, j].copy()
        n = c.t[b]
        m = c.col[b, j]
        lg = np.where(u0[b, j] != 0, u0[b, j] > 0, self.p["cat"][b, j] < 2)          # sens de la position
        s, oo = U.demi[n, m], U.o[n, m]
        fin = np.isfinite(r)
        mur = ~fin & c.mort[b] & ~c.inactif[b]
        ina = ~fin & c.inactif[b]
        has = lambda bit: (e & bit) != 0
        code = np.select([mur, ina, has(SIM.ELLE), has(SIM.FORCEE), has(SIM.DEST), has(SIM.STOP) & (c.sv_n[b, j] > 0),
                          has(SIM.STOP) & c.tp1_fait[b, j], has(SIM.STOP), has(SIM.TP1)],
                         [MUR, INACTIF, MAIN, FIN_JOUR, OBJECTIF, SUIVEUR_, STOP_ENTREE, STOP_, OBJECTIF1], STOP_)
        # niveaux d'avant la bougie ; une position ouverte DANS cette bougie (au marché, sortie dans la même bougie) :
        # les niveaux de sa décision
        neuve = u0[b, j] == 0
        st = np.where(neuve | ~np.isfinite(st0[b, j]), self.p["stop0"][b, j], st0[b, j])
        tp0 = np.where(neuve, self.p["tp1"][b, j], tp0[b, j])
        de0 = np.where(neuve, self.p["dest"][b, j], de0[b, j])
        st_avant = st.copy()
        suivi = has(SIM.SUIVI)
        if suivi.any() and getattr(c, "a_suiveur", False):
            k = np.where(lg, 0, 1)
            nv = c.sw_v[np.maximum(n - 1, 0), m, np.clip(c.sv_u[b, j], 0, None), k]
            nv = np.where(lg, nv - c.sv_m[b, j], nv + c.sv_m[b, j])
            ag = c.sv_1r[b, j] & (c.sv_ag[b, j] > 0)             # suiveur par agitation (après +1R) : le stop posé
            nv = np.where(ag, c.sv_dern[b, j], nv)
            st = np.where(suivi & np.isfinite(nv), nv, st)
        g = self.glissement
        px_stop = np.where(lg, np.minimum(st, oo * (1 - s)) * (1 - g * s), np.maximum(st, oo * (1 + s)) * (1 + g * s))
        px_marche = np.where(lg, oo * (1 - s), oo * (1 + s))
        px_dest = np.where(lg, np.maximum(de0, oo * (1 - s)), np.minimum(de0, oo * (1 + s)))
        px_tp1 = np.where(lg, np.maximum(tp0, oo * (1 - s)), np.minimum(tp0, oo * (1 + s)))
        pp = np.where(ina, U.c[n, m], np.where(lg, U.l[n, m], U.h[n, m]))
        px = np.select([(code == MUR) | (code == INACTIF), (code == MAIN) | (code == FIN_JOUR), code == OBJECTIF,
                        code == OBJECTIF1], [pp, px_marche, px_dest, px_tp1], px_stop)
        pnl = c.pnl_trade[b, j].copy()
        dur = mur | ina
        pnl = np.where(dur, pnl + u0[b, j] * (pp - c.entree[b, j]) * U.fx[n, m], pnl)
        r = np.where(fin, r, pnl / np.where(c.risque[b, j] > 0, c.risque[b, j], np.nan))
        stop_fin = np.where((code == STOP_) | (code == STOP_ENTREE) | (code == SUIVEUR_), st, st_avant)
        self._noter(b, j, n, code, px, stop_fin, pnl, r, inserer=True)
        self.p_open[b, j] = False

    def _noter(self, b, j, n, code, px, stop_fin, pnl, r, inserer: bool):
        """Un trade fermé : dans son historique (s'il le voit) et dans les lignes de log (échantillon)."""
        c, U = self.tb.cpt, self.tb.U
        r = np.nan_to_num(r, nan=0.0)
        mfe = np.maximum(self.p_mfe[b, j], r)
        mae = np.minimum(self.p_mae[b, j], r)
        t0 = self.p_t[b, j]
        h_best = (self.heures[np.where(self.p_tmfe[b, j] >= 0, self.p_tmfe[b, j], t0)] - self.heures[t0])
        h_best = np.where(mfe > r, h_best, self.heures[n] - self.heures[t0])
        duree = self.heures[n] - self.heures[t0]
        sens = np.where(self.p["cat"][b, j] >= 2, -1.0, 1.0)
        if inserer:
            self.dern_ns[b] = np.maximum(self.dern_ns[b], self.t_ns[n])
            if self.voir:
                vis = n if self.delai == "fermeture" else self.prochain_jour[n]
                ch = np.stack([mfe, mae, h_best, duree, r, code.astype(float)], -1)
                self._inserer(b, {"hS": self.p_sit[b, j], "hSens": sens, "hR": r, "hPnl": pnl / CAPITAL * 100,
                                  "hHfin": self.heures[n], "hCh": ch, "hCat": self.p["cat"][b, j], "hVis": vis,
                                  "hTk": self.p["ticket"][b, j]})
        if not self.logs:
            return
        w = self.ech_hist[b]
        for k in np.flatnonzero(w):
            bb, jj = b[k], j[k]
            m = c.col[bb, jj]
            self.histo.append({
                "ticket": int(self.p["ticket"][bb, jj]), "compte": int(bb), "challenge": int(self.n_ch[bb]),
                "marche": U.cols[m], "sens": float(sens[k]), "type": int(self.p["type"][bb, jj]),
                "ent_code": int(self.p["ent_code"][bb, jj]), "stop_code": int(self.p["stop_code"][bb, jj]),
                "dest_code": int(self.p["dest_code"][bb, jj]), "sv": int(self.p["sv"][bb, jj]),
                "svtp1": bool(self.p["svtp1"][bb, jj]), "sv1r": bool(self.p["sv1r"][bb, jj]),
                "svag": float(self.p["svag"][bb, jj]),
                "t_dec_ns": int(self.t_ns[self.p["t_dec"][bb, jj]] + QUINZE_NS) if self.p["t_dec"][bb, jj] >= 0 else 0,
                "t_ouv_ns": int(self.t_ns[t0[k]]), "prix_ouv": float(self.p_prix[bb, jj]),
                "vol": float(self.p_vol[bb, jj]), "risque": float(self.p_risque[bb, jj]),
                "stop0": float(self.p["stop0"][bb, jj]), "tp1": float(self.p["tp1"][bb, jj]),
                "part": float(self.p["part"][bb, jj]), "dest": float(self.p["dest"][bb, jj]),
                "tp1_fait": bool(c.tp1_fait[bb, jj]),
                "t_fin_ns": int(self.t_ns[n[k]]), "prix_fin": float(px[k]), "stop_fin": float(stop_fin[k]),
                "raison": int(code[k]), "pnl": float(pnl[k]), "r": float(r[k]), "mfe": float(mfe[k]),
                "mae": float(mae[k]), "h_best": float(h_best[k]), "duree_h": float(duree[k]),
                "cat": int(self.p["cat"][bb, jj]), "sit": self.p_sit[bb, jj].copy(), "fin_ligne": int(n[k])})

    def _inserer(self, b: np.ndarray, champs: dict):
        """Ajoute des trades fermés à l'historique de la carte graphique (au-delà de CAPACITE : les plus anciens sortent)."""
        N = CAPACITE
        o = np.argsort(b, kind="stable")
        b = b[o]
        champs = {k: np.asarray(v)[o] if np.ndim(v) else np.full(len(b), v) for k, v in champs.items()}
        debut = np.r_[0, np.flatnonzero(b[1:] != b[:-1]) + 1]
        off = np.arange(len(b)) - np.repeat(debut, np.diff(np.r_[debut, len(b)]))
        k = self.hN_np[b] + off
        for bb in np.unique(b[k >= N]):
            sh = int(k[b == bb].max() - N + 1)
            for nom in ("hS", "hSens", "hR", "hPnl", "hHfin", "hCh", "hCat", "hVis", "hTk"):
                x = getattr(self, nom)
                x[bb] = torch.roll(x[bb], -sh, 0)
            self.hN_np[bb] -= sh
            k[b == bb] -= sh
        dev = self.hN.device
        bi, ki = torch.as_tensor(b, device=dev), torch.as_tensor(k, device=dev)
        for nom, v in champs.items():
            x = getattr(self, nom)
            x[bi, ki] = torch.as_tensor(np.asarray(v), dtype=x.dtype, device=dev)
        np.add.at(self.hN_np, b, 1)
        u = np.unique(b)
        self.hN[torch.as_tensor(u, device=dev)] = torch.as_tensor(self.hN_np[u], device=dev)

    def _log_onglet(self, qui):
        """Onglet Trade (comme MT5) des comptes de l'échantillon qui regardent : positions et ordres en attente."""
        c, U = self.tb.cpt, self.tb.U
        v = c.valeurs()
        for b in qui:
            t = c.t[b]
            for j in range(self.J):
                m = c.col[b, j]
                if m < 0:
                    continue
                base = {"t_ns": int(self.t_ns[t] + QUINZE_NS), "compte": int(b), "challenge": int(self.n_ch[b]),
                        "marche": U.cols[m], "px": float(U.c[t, m]), "solde": float(c.solde[b]), "valeur": float(v[b])}
                if c.u[b, j] != 0:
                    flot = c.u[b, j] * (U.c[t, m] - c.entree[b, j]) * U.fx[t, m]
                    self.onglet.append({**base, "ligne": "position", "ticket": int(self.p["ticket"][b, j]),
                                        "type": "achat" if c.u[b, j] > 0 else "vente",
                                        "t0_ns": int(self.t_ns[self.p_t[b, j]]) if self.p_t[b, j] >= 0 else 0,
                                        "vol": float(abs(c.u[b, j])), "prix": float(c.entree[b, j]),
                                        "stop": float(c.stop[b, j]),
                                        "tp1": float(c.tp1[b, j]) if not c.tp1_fait[b, j] else float("nan"),
                                        "part": float(c.part[b, j]), "dest": float(c.dest[b, j]),
                                        "suiveur": nom_suiveur(int(c.sv_u[b, j]), bool(c.sv_tp1[b, j]),
                                                               bool(c.sv_1r[b, j]), float(c.sv_ag[b, j]))
                                        + (f", remonté {int(c.sv_n[b, j])} fois" if c.sv_u[b, j] >= 0 else ""),
                                        "risque": float(self.p_risque[b, j]), "flot": float(flot),
                                        "flot_r": float((c.pnl_trade[b, j] + flot) / c.risque[b, j]) if c.risque[b, j] > 0 else 0.0,
                                        "mfe": float(self.p_mfe[b, j]), "exp_ns": 0})
                if c.att[b, j]:
                    rq = abs(c.att_u[b, j]) * abs(c.att_prix[b, j] - c.att_stop[b, j]) * U.fx[t, m] / max(v[b], 1) * 100
                    self.onglet.append({**base, "ligne": "ordre", "ticket": int(self.a["ticket"][b, j]),
                                        "type": "achat limite" if c.att_u[b, j] > 0 else "vente limite",
                                        "t0_ns": int(self.t_ns[self.a["t_dec"][b, j]] + QUINZE_NS) if self.a["t_dec"][b, j] >= 0 else 0,
                                        "vol": float(abs(c.att_u[b, j])), "prix": float(c.att_prix[b, j]),
                                        "stop": float(c.att_stop[b, j]), "tp1": float(c.att_tp1[b, j]),
                                        "part": float(c.att_part[b, j]), "dest": float(c.att_dest[b, j]),
                                        "suiveur": nom_suiveur(int(c.att_sv_u[b, j]), bool(c.att_sv_tp1[b, j]),
                                                               bool(c.att_sv_1r[b, j]), float(c.att_sv_ag[b, j])),
                                        "risque": float(rq), "flot": 0.0, "flot_r": 0.0, "mfe": 0.0,
                                        "exp_ns": int(self.t_ns[t] + QUINZE_NS * (1 + int(c.att_reste[b, j])))})


# ============================================================================================== la greffe
def _grandir(w: torch.Tensor) -> torch.Tensor:
    return torch.cat([w, torch.zeros(*w.shape[:-1], NJ, dtype=w.dtype, device=w.device)], -1)


def greffer_etat(etat: dict, delai: str = "fermeture") -> tuple[dict, bool]:
    """Un fichier de branche ({"cerveau", "opt"?, "temperament"?}) : NJ colonnes à ZÉRO ajoutées EN DERNIER à la
    1re couche des yeux du marché (ordre des entrées : yeux, position, journal) ; mémoire de l'optimiseur de même ;
    tempérament noté « journal ». Rend (état, changé)."""
    from collapsar.ecole.precision import cerveau as C
    cle = "marche.0.weight"
    w = etat["cerveau"][cle]
    base = C.Cerveau().F
    if w.shape[1] == base + NJ:
        return etat, False
    if w.shape[1] != base:
        raise ValueError(f"entrée du cerveau inattendue : {w.shape[1]} (attendu {base} ou {base + NJ})")
    etat = dict(etat)
    etat["cerveau"] = {**etat["cerveau"], cle: _grandir(w)}
    opt = etat.get("opt")
    if opt:
        noms = [n for n, _ in C.Cerveau().named_parameters()]
        pid = opt["param_groups"][0]["params"][noms.index(cle)]
        st = opt["state"].get(pid)
        if st:
            st = {k: (_grandir(v) if k in ("exp_avg", "exp_avg_sq") and v.shape == w.shape else v) for k, v in st.items()}
            etat["opt"] = {**opt, "state": {**opt["state"], pid: st}}
    if "temperament" in etat:
        etat["temperament"] = {**(etat["temperament"] or {}), "journal": {"version": VERSION, "delai_historique": delai}}
    return etat, True


def _allumer_comme_l_arbre(dossier: Path):
    from collapsar.ecole.precision import foule as FO
    from collapsar.ecole.precision import juge_trade as JT
    from collapsar.ecole.precision import monde as MO
    from collapsar.ecole.precision import suiveur as SV
    if FO.greffee(dossier):
        FO.activer()
    JT.allumer_si_greffe(dossier)
    if MO.greffee(dossier):
        MO.activer()
    if SV.greffee(dossier):
        SV.activer()


def greffer(dossier: Path | None = None, branche: str | None = None, nouvelle: bool = False, delai: str = "fermeture",
            dire=print) -> dict:
    """LA GREFFE du journal sur UNE branche d'un arbre ARRÊTÉ (sauvegarde complète d'abord) :
    - `branche=X` : la branche X (et sa meilleure version ; cime.pt si c'est la cime) reçoit le journal ;
    - `nouvelle=True` : la branche la plus faible (hors cime) est archivée et remplacée par une branche « journal »
      née de la cime (copie exacte de ses poids + journal à zéro) ; la cime reste intacte.
    journal.json est écrit (le cœur allume les fichiers de log au prochain démarrage)."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import suiveur as SV
    assert delai in DELAIS, delai
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if (dossier / "journal.json").exists():
        raise SystemExit(f"{dossier} : déjà greffé du journal (journal.json existe)")
    pid = SV._pid_vivant(dossier / "coeur.verrou")
    if pid:
        raise SystemExit(f"le cœur bat encore (processus {pid}) : créer {dossier / 'ARRET'} et attendre sa fin")
    if not (dossier / "arbre.json").exists():
        raise SystemExit(f"{dossier} : aucun arbre")
    if (branche is None) == (not nouvelle):
        raise SystemExit("choisir --branche X OU --nouvelle")
    _allumer_comme_l_arbre(dossier)
    arbre = Arbre.charger(dossier / "arbre.json")
    cime = arbre.cime
    if branche is not None and (branche not in arbre.branches or arbre.branches[branche].morte is not None):
        raise SystemExit(f"branche {branche} absente ou morte")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_journal_{stamp}"
    k = 2
    while sauve.exists():
        sauve = dossier / "sauvegardes" / f"avant_journal_{stamp}_{k}"
        k += 1
    sauve.mkdir(parents=True)
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (dossier / nom).exists():
            shutil.copy2(dossier / nom, sauve / nom)
    shutil.copytree(dossier / "branches", sauve / "branches")
    dire(f"sauvegarde de l'arbre : {sauve}")
    journal = Journal(dossier / "journal_croissance.jsonl")
    info = {"date": datetime.now().isoformat(timespec="seconds"), "version": VERSION, "entrees": NJ,
            "delai_historique": delai, "sauvegarde": str(sauve), "cime": cime}
    tj = {"version": VERSION, "delai_historique": delai}
    if nouvelle:
        faible = SV.la_plus_faible(arbre, {cime})
        if faible is None:
            raise SystemExit("aucune branche à remplacer (hors cime)")
        e = torch.load(dossier / "branches" / f"{cime}.pt", map_location="cpu", weights_only=False)
        tc = dict(e.get("temperament") or arbre.branches[cime].temperament)
        tc.pop("alertes", None)
        t = {**tc, "nom": "journal", "journal": tj, "heritage": f"cime {cime} greffée du journal de trading ({stamp})"}
        e2, _ = greffer_etat({"cerveau": e["cerveau"]}, delai)
        arbre.mourir(faible, "coupée")
        (dossier / "archives").mkdir(exist_ok=True)
        for f in (f"{faible}.pt", f"{faible}_meilleur.pt"):
            if (dossier / "branches" / f).exists():
                shutil.move(str(dossier / "branches" / f), str(dossier / "archives" / f))
        b = arbre.naitre([cime], t)
        from collapsar.ecole.precision import cerveau as C
        net = C.Cerveau(journal=True, delai=delai)
        net.load_state_dict(e2["cerveau"])
        opt = torch.optim.AdamW(net.parameters(), lr=float(t.get("vitesse", R().ecole.vitesse)), weight_decay=1e-4)
        tmp = dossier / "branches" / f"{b.nom}.pt.tmp"
        torch.save({"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": t}, tmp)
        os.replace(tmp, dossier / "branches" / f"{b.nom}.pt")
        arbre._elire_cime()
        arbre.sauver(dossier / "arbre.json")
        fx = dossier / "derniers_examens.json"
        if fx.exists():
            x = json.loads(fx.read_text(encoding="utf-8"))
            x.pop(faible, None)
            fx.write_text(json.dumps(x, ensure_ascii=False, default=float), encoding="utf-8")
        journal.ecrire("coupe", branche=faible, raison="remplacée par une branche « journal » (greffe du journal de trading)")
        journal.ecrire("naissance", branche=b.nom, parents=[cime], temperament=t, heritage=t["heritage"])
        info.update({"mode": "nouvelle", "branches": [b.nom], "remplacee": faible, "fichiers": [f"{b.nom}.pt"]})
        dire(f"branche {faible} archivée ; branche {b.nom} « journal » née de la cime {cime} (journal à zéro)")
    else:
        faits = []
        fichiers = [dossier / "branches" / f"{branche}.pt", dossier / "branches" / f"{branche}_meilleur.pt"]
        if branche == cime:
            fichiers.append(dossier / "cime.pt")
        for f in fichiers:
            if not f.exists():
                continue
            e = torch.load(f, map_location="cpu", weights_only=False)
            e2, change = greffer_etat(e, delai)
            if change:
                tmp = f.with_suffix(".pt.tmp")
                torch.save(e2, tmp)
                os.replace(tmp, f)
                faits.append(f.name)
        arbre.branches[branche].temperament["journal"] = tj
        arbre.sauver(dossier / "arbre.json")
        info.update({"mode": "branche", "branches": [branche], "fichiers": faits})
        dire(f"branche {branche} greffée du journal ({len(faits)} fichiers, {NJ} entrées à zéro)")
    journal.ecrire("greffe_journal", **{k: v for k, v in info.items() if k != "date"})
    (dossier / "journal.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def defaire(dossier: Path | None = None, dire=print):
    """Retour arrière : remet la sauvegarde d'avant la greffe (arbre arrêté). Les fichiers de log restent."""
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : l'arrêter d'abord (fichier ARRET)")
    info = json.loads((dossier / "journal.json").read_text(encoding="utf-8"))
    sauve = Path(info["sauvegarde"])
    shutil.rmtree(dossier / "branches")
    shutil.copytree(sauve / "branches", dossier / "branches")
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (sauve / nom).exists():
            shutil.copy2(sauve / nom, dossier / nom)
    if info.get("remplacee"):
        for f in (f"{info['remplacee']}.pt", f"{info['remplacee']}_meilleur.pt"):
            (dossier / "archives" / f).unlink(missing_ok=True)
    (dossier / "journal.json").unlink()
    dire(f"greffe du journal défaite : état remis depuis {sauve}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="journal de trading de l'école de la précision")
    ap.add_argument("quoi", choices=["greffer", "defaire", "noms"])
    ap.add_argument("--dossier", default=None)
    ap.add_argument("--branche", default=None)
    ap.add_argument("--nouvelle", action="store_true")
    ap.add_argument("--delai", default="fermeture", choices=list(DELAIS))
    a = ap.parse_args(argv)
    if a.quoi == "greffer":
        greffer(Path(a.dossier) if a.dossier else None, a.branche, a.nouvelle, a.delai)
    elif a.quoi == "defaire":
        defaire(Path(a.dossier) if a.dossier else None)
    else:
        print(f"{NJ} entrées : onglet Trade {NT}, historique {NH}")
        for i, n in enumerate(NOMS):
            print(i, n)


if __name__ == "__main__":
    main()
