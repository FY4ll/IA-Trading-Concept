"""Le RAPPORT LISIBLE de l'arbre HYPERNOVA (toutes les 50 générations, ou à la demande :
venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.precision.coeur --rapport).

Il montre : l'arbre (branches vivantes, coupées, divisions), la progression de la cime à l'examen de sélection
2022-2023, la cime sur 01/2024 -> 09/2025 (période de RAPPORT, jamais utilisée pour choisir), toujours contre son jumeau
au hasard, et ce qu'elle fait de ses mains (entrées, stops, destinations, part encaissée à l'objectif 1) pour voir si
elle apprend « l'asymétrie par la précision ». Vocabulaire du chef de projet : « ses zones d'offre et de demande ».
"""
from __future__ import annotations

import gc
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

from collapsar.ecole.precision import cerveau as C
from collapsar.ecole.precision.reglages import NOM, R, UNITES, etiquette_rapport, etiquette_selection

NOMS_U = {"D1": "journalier", "H4": "4 h", "H1": "1 h", "M30": "30 min", "M15": "15 min", "M5": "5 min", "M3": "3 min"}


def _f(x, n=2, signe=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:+.{n}f}" if signe else f"{x:.{n}f}"


def _comportement(c: dict) -> list[str]:
    if not c or c.get("ouvertures", 0) == 0:
        return ["(aucune ouverture)"]
    L = [f"- ouvertures décidées (ordres limites posés compris, même jamais exécutés) : {c['ouvertures']:.0f} ; "
         f"par ordre limite (entrée sur une de ses zones) : "
         f"{c['limites_pct']:.0f} % ; au marché : {100 - c['limites_pct']:.0f} %",
         f"- stop derrière une zone (bord lointain) : {c['stop_sur_zone_pct']:.0f} % ; derrière un sommet / creux : "
         f"{100 - c['stop_sur_zone_pct']:.0f} %",
         f"- destination « laisser courir » : {c['laisser_courir_pct']:.0f} % ; destination moyenne visée : "
         f"{_f(c.get('destination_en_r_moyenne'), 1, False)} fois le risque",
         f"- part encaissée à l'objectif 1 : 0 % -> {c['part_0_50_80_pct'][0]:.0f} %, 50 % -> {c['part_0_50_80_pct'][1]:.0f} %, "
         f"80 % -> {c['part_0_50_80_pct'][2]:.0f} % des trades ; risque moyen {c['risque_moyen_pct']:.2f} % du compte", "",
         "| unité | entrées (ordres limites) | stops | destinations |", "|---|---|---|---|"]
    for u in UNITES:
        L.append(f"| {NOMS_U[u]} | {c['entree_unite_pct'][u]:.0f} % | {c['stop_unite_pct'][u]:.0f} % | "
                 f"{c['dest_unite_pct'][u]:.0f} % |")
    return L


def _executions(x: dict) -> list[str]:
    """(20/10) Ouvertures RÉELLEMENT exécutées, séparées des ordres seulement posés (si l'examen les mesure)."""
    e = x.get("executions")
    if not e:
        return []
    return [f"- ouvertures RÉELLEMENT exécutées : {e['ouvertures_executees_mois']:.1f} par mois ; au marché "
            f"{e['ouvertures_marche']}, ordres limites exécutés {e['ordres_limites_executes']} "
            f"({e['part_limites_executees_pct']:.0f} % des trades) sur {e['ordres_limites_poses']:.0f} ordres limites posés "
            f"({e['part_ordres_executes_pct']:.0f} % exécutés, {e['ordres_limites_expires']} expirés)"]


def _ligne(nom: str, x: dict) -> str:
    return (f"| {nom} | {_f(x['note'])} | {_f(x['gain_pct_mois'])} | {x['reussis_pct']:.0f} % | "
            f"{_f(x.get('jours_median_reussite'), 0, False)} j | {x.get('reussis_en_30_jours_pct', float('nan')):.0f} % | "
            f"{x['murs_pct']:.0f} % | {x['inactifs_pct']:.0f} % | {x['baisse_max_moyenne_pct']:.1f} % | "
            f"{x['trades_mois']:.1f} | {x['en_position_pct']:.0f} % | {_f(x['r_moyen'], 3)} |")


def _deux(nom: str, x: dict) -> list[str]:
    out = [_ligne(nom, x)]
    if "jumeau" in x:
        out.append(_ligne(f"{nom} — son jumeau au hasard", x["jumeau"]))
    return out


def _gros(lignes: list[tuple[str, dict]]) -> list[str]:
    """Les gros mouvements (si l'examen les mesure : réglage selection.mesurer_mouvement)."""
    lignes = [(n, x) for n, x in lignes if x and "part_mouvement_pct" in x]
    if not lignes:
        return []
    L = ["", "## Les gros mouvements (« on veut les gros mouvements, pas des miettes »)", "",
         "Part du mouvement attrapée = prix gagnés en suivant le sens de ses positions (clôture à clôture de 15 min, "
         "quelle que soit la taille) / chemin du prix jour par jour pendant le challenge. 100 % = chaque journée suivie "
         "dans le bon sens ; 0 % = rien attrapé (ou autant contre que pour).", "",
         "| période | part du mouvement | trades >= 5R | trades >= 10R | part des gains venant des trades >= 5R | "
         "meilleur trade |", "|---|---|---|---|---|---|"]
    for nom, x in lignes:
        for n2, y in ((nom, x), (f"{nom} — jumeau", x.get("jumeau", {}))):
            if "part_mouvement_pct" in y:
                L.append(f"| {n2} | {_f(y['part_mouvement_pct'], 1)} % | {_f(y['trades_5r_pct'], 1, False)} % | "
                         f"{_f(y['trades_10r_pct'], 1, False)} % | {_f(y.get('gains_des_5r_pct'), 0, False)} % | "
                         f"{_f(y.get('meilleur_r'), 1)} R |")
    return L


def _suiveur(lignes: list[tuple[str, dict]]) -> list[str]:
    """Le stop suiveur (arbre de l'or, suiveur.py) : usage et R moyen des trades au suiveur contre les autres."""
    lignes = [(n, x) for n, x in lignes if x and "suiveur_pct" in x]
    if not lignes:
        return []
    L = ["", "## Le stop suiveur derrière la structure (son choix, trade par trade)", "",
         "Stop remonté derrière chaque nouveau creux (achat) / sommet (vente) confirmé de l'unité choisie, + la marge de "
         "son stop, jamais reculé ; dès l'entrée ou après l'objectif 1.", "",
         "| période | trades au stop suiveur | R moyen au suiveur | R moyen des autres | >= 5R au suiveur | "
         "stop remonté | après l'objectif 1 | unités (journalier / 4 h / 1 h / 15 min...) |",
         "|---|---|---|---|---|---|---|---|"]
    for nom, x in lignes:
        for n2, y in ((nom, x), (f"{nom} — jumeau", x.get("jumeau", {}))):
            if "suiveur_pct" in y:
                u = " / ".join(f"{NOMS_U.get(k, k)} {v:.0f} %" for k, v in y.get("suiveur_unite_pct", {}).items())
                L.append(f"| {n2} | {_f(y['suiveur_pct'], 0, False)} % ({y.get('suiveur_trades', 0)}) | "
                         f"{_f(y['r_moyen_suiveur'])} | {_f(y['r_moyen_sans_suiveur'])} | "
                         f"{_f(y.get('trades_5r_suiveur_pct'), 1, False)} % | {_f(y.get('suiveur_remonte_pct'), 0, False)} % | "
                         f"{_f(y.get('suiveur_apres_tp1_pct'), 0, False)} % | {u} |")
    return L


def _branches(dossier: Path) -> list[str]:
    """Les branches à la dernière génération (mesure de la tenue, selection.mesurer_tenue) : gain contre le jumeau, stop
    réellement remonté (part de TOUS les trades), trades >= 3R / 5R, achats / ventes, suiveur après +1R."""
    f = dossier / "derniers_examens.json"
    if not f.exists():
        return []
    ex = json.loads(f.read_text(encoding="utf-8"))
    if not any("stop_remonte_tous_pct" in x for x in ex.values()):
        return []
    try:
        br = json.loads((dossier / "arbre.json").read_text(encoding="utf-8"))["branches"]
    except Exception:
        br = {}
    L = ["", "## Les branches au dernier examen", "",
         "| branche | rôle | note | %/mois (jumeau) | stop réellement remonté | trades >= 3R | >= 5R | achats : R moyen (trades) | "
         "ventes : R moyen (trades) | suiveur après +1R (+1R atteint) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for nom, x in ex.items():
        if "stop_remonte_tous_pct" not in x:
            continue
        c = x.get("cotes", {})
        a, v = c.get("achats", {}), c.get("ventes", {})
        role = br.get(nom, {}).get("temperament", {}).get("nom", "")
        if isinstance(br.get(nom, {}).get("temperament", {}).get("maitre"), dict):   # lignée Gold Reaper
            role += " (contrôle 2024-2025 non valable)"
        L.append(f"| {nom} | {role} | {_f(x['note'])} | {_f(x['gain_pct_mois'])} ({_f(x.get('jumeau', {}).get('gain_pct_mois'))}) | "
                 f"{_f(x['stop_remonte_tous_pct'], 1, False)} % | {_f(x.get('trades_3r_pct'), 1, False)} % | "
                 f"{_f(x.get('trades_5r_tous_pct'), 1, False)} % | {_f(a.get('r_moyen'), 3)} ({a.get('trades', 0)}) | "
                 f"{_f(v.get('r_moyen'), 3)} ({v.get('trades', 0)}) | {_f(x.get('suiveur_1r_pct'), 0, False)} % "
                 f"({_f(x.get('suiveur_1r_atteint_pct'), 0, False)} %) |")
    return L


def _cotes(dossier: Path, autres: list[tuple[str, dict]]) -> list[str]:
    """(19/10 soir) OR RÉEL / OR RETOURNÉ séparés : chaque branche au dernier examen, et la cime (sélection, rapport) :
    gain %/mois (jumeau), part d'achats, R moyen des achats et des ventes. Sait-elle lire le sens, ou seulement acheter ?"""
    from collapsar.ecole.precision import tournant as TN
    lignes = []
    f = dossier / "derniers_examens.json"
    if f.exists():
        lignes += [(f"branche {n}", x) for n, x in json.loads(f.read_text(encoding="utf-8")).items()]
    lignes += autres
    L = []
    for nom, x in lignes:
        pc = x.get("par_cote") or TN.par_cote(x)
        for s, c in pc.items():
            L.append(f"| {nom} | {s} | {_f(c['gain_pct_mois'])} ({_f(c['jumeau_pct_mois'])}) | {_f(c['note'])} | "
                     f"{_f(c['part_achats_pct'], 0, False)} % | {_f(c['r_achats'], 3)} ({c['achats']}) | "
                     f"{_f(c['r_ventes'], 3)} ({c['ventes']}) | {_f(c.get('murs_pct'), 0, False)} % |")
        if pc and "note_moyenne" in x:
            L.append(f"| {nom} | **note de sélection** | côté le moins bon : {x['note_cote_faible']} | {_f(x['note'])} | "
                     f"(moyenne des deux {_f(x['note_moyenne'])}) | | | |")
    if not L:
        return []
    return ["", "## Or réel / or retourné (lire le sens, pas seulement acheter)", "",
            "Sur l'or retourné, le prix est l'inverse du vrai : une IA qui sait lire le sens y vend autant qu'elle achète "
            "sur le vrai. Note de sélection (si réglée) = le côté le moins bon.", "",
            "| qui | côté | %/mois (jumeau) | note | part d'achats | achats : R moyen (trades) | ventes : R moyen (trades) "
            "| murs |", "|---|---|---|---|---|---|---|---|"] + L


def ecrire_rapport(dossier: Path, appareil: str = "cuda") -> Path:
    from collapsar.ecole.precision.coeur import GRAINE_EXAMEN, monde_examen, resume_examen
    r = R()
    lignes = [json.loads(x) for x in (dossier / "journal_croissance.jsonl").read_text(encoding="utf-8").splitlines()
              if x.strip()]
    gens = [x for x in lignes if x.get("quoi") == "generation"]
    ch = torch.load(dossier / "cime.pt", map_location=appareil, weights_only=False)
    cle = f"{ch['branche']}_{ch['generation']}"
    cache = dossier / f"rapport_cime_{cle}.json"
    if not getattr(r.rapports, "controle_auto", True):
        # (20/10, corrections graves, MAGNETAR : rapports.controle_auto: false) : le contrôle 2024-2025 n'est plus lu
        # toutes les 50 générations ; une seule fois par version figée (controle_unique.py)
        rap = {"challenges": 0, "comportement": {}, "par_panier": {}, "non_calcule": True}
    elif cache.exists():
        rap = json.loads(cache.read_text(encoding="utf-8"))
    else:
        net = C.cerveau_pour(ch["cerveau"]).to(appareil)          # avec ou sans journal de trading
        try:                                                      # stops proches de la branche (stop_proche.py)
            t = json.loads((dossier / "arbre.json").read_text(encoding="utf-8"))["branches"][ch["branche"]]["temperament"]
        except Exception:
            t = None
        C.regler_precision(net, t)
        C.regler_symetrie(net, t)                                 # cerveau symétrique (symetrie.py) ; absent = rien
        U, ex = monde_examen(r.periodes.rapport_de, r.periodes.rapport_jusqua, appareil)
        rap = resume_examen(ex.jouer_un(net, GRAINE_EXAMEN))
        cache.write_text(json.dumps(rap, ensure_ascii=False, default=float), encoding="utf-8")
        del U, ex, net
        gc.collect()
        if appareil == "cuda":
            torch.cuda.empty_cache()
    sel = ch["examen"]
    es, er = etiquette_selection(), etiquette_rapport()
    try:                                                          # lignée Gold Reaper (gold_reaper.py) ?
        t_c = json.loads((dossier / "arbre.json").read_text(encoding="utf-8"))["branches"][ch["branche"]]["temperament"]
    except Exception:
        t_c = None
    if isinstance(t_c, dict) and isinstance(t_c.get("maitre"), dict):
        er = f"{er} — NON VALABLE pour cette cime (elle a appris les trades de {t_c['maitre'].get('nom', 'Gold Reaper')} 10/2024 -> 09/2025)"
    fin_app = (r.periodes.apprentissage_fin - np.timedelta64(1, "D")).year
    L = [f"# COLLAPSAR — arbre {NOM}, génération {ch['generation']} (rapport du {datetime.now():%d/%m/%Y %H:%M})", "",
         "Ce qu'il apprend : « l'asymétrie par la précision ». Il VOIT ses zones d'offre et de demande vivantes de "
         "toutes les unités (journalier, 4 h, 1 h, 30 min, 15 min ; 5 et 3 min sur l'or, le Nasdaq, le S&P 500 et l'euro), "
         "les zones dans les zones, les sommets et creux, l'agitation, l'heure. Il CHOISIT librement, en niveaux du "
         "graphique : rien / acheter / vendre, au marché ou par ordre limite sur une zone, le stop derrière une zone ou un "
         "creux / sommet (+ petite marge), la destination (zone opposée, sommet / creux, ou laisser courir), la part "
         "encaissée à l'objectif 1 (0 / 50 / 80 %, stop à l'entrée ensuite), le risque (0,1 à 2 %), et quand revenir "
         "regarder. Seules les limites FTMO sont imposées (simulateur fidèle, frais FTMO du 16/10, nuits, levier).", "",
         (f"- Apprentissage : années jusqu'à fin {fin_app}, SAUF les blocs d'examen et 7 jours autour. Sélection : EXAMEN "
          f"TOURNANT, {sel.get('challenges', '?')} challenges de 2 mois par génération (blocs tirés dans le réservoir "
          f"{es}, or réel et retourné, les mêmes pour toutes les branches)" if "blocs" in sel else
          f"- Apprentissage : années jusqu'à fin {fin_app}. Sélection : {es}, {sel.get('challenges', '?')} challenges de 2 "
          f"mois") +
         f". Rapport (jamais pour choisir) : {er}, {rap.get('challenges', '?')} challenges. Rien après 09/2025.",
         f"- Cime actuelle : branche {ch['branche']} (génération {ch['generation']}).", "",
         "## La cime contre son jumeau au hasard", "",
         "| période | note | %/mois | challenges réussis | en (médiane) | réussis en 30 j | morts (murs) | inactifs | "
         "baisse max moy. | trades/mois | en position | R moyen |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    g1 = "génération 1 (examen de l'époque)"
    if gens:
        L += _deux(g1, gens[0]["cime_examen"])
    sans_rap = bool(rap.get("non_calcule"))           # (20/10) contrôle 2024-2025 : une seule fois, controle_unique.py
    R_ = [] if sans_rap else [(f"{er} (rapport)", rap)]
    L += _deux(f"{es} (sélection)", sel) + ([] if sans_rap else _deux(f"{er} (rapport)", rap))
    if sans_rap:
        L += ["", f"Contrôle {er} : NON calculé ici (lu une seule fois par version figée : "
                  "`python -m collapsar.ecole.precision.controle_unique`)."]
    tm = sel.get("temoin")
    if tm:
        L += ["", f"TÉMOIN (blocs jamais appris, hors de la note) : {_f(tm['gain_pct_mois'])} %/mois (jumeau "
                  f"{_f(tm.get('jumeau_pct_mois'))}), R par trade {_f(tm.get('r_moyen'), 3)}, {tm.get('challenges')} challenges."]
    L += _gros(([(g1, gens[0]["cime_examen"])] if gens else []) + [(f"{es} (sélection)", sel)] + R_)
    L += _suiveur([(f"{es} (sélection)", sel)] + R_)
    L += _branches(dossier)
    L += _cotes(dossier, [(f"cime, {es} (sélection)", sel)] + [(f"cime, {n}", x) for n, x in R_])
    for nom, x in ((es, sel),) + ((() if sans_rap else ((er, rap),))):
        if "avantage_pct_mois" in x:
            L.append(f"\nAvantage sur le jumeau au hasard ({nom}) : {_f(x['avantage_pct_mois'])} ± "
                     f"{x['avantage_incertitude']:.2f} %/mois.")
    L += ["", "Objectif du chef de projet : 8 à 10 %/mois, réussir le +10 % vite sans toucher -5 %/jour ni -10 %.",
          ("Note d'un challenge (depuis le 20/10, GAIN RÉEL) = (réussi x (5 + 5 x part des 61 jours restants) - la même "
           "chose pour le jumeau) - 10 x mur - 5 x inactif + min(gain %/mois - gain du jumeau, gain %/mois) borné à +-10 "
           "- 0,5 x (baisse max - 6 %) : perdre moins que le hasard ne rapporte plus rien."
           if getattr(r.note, "gain_reel", False) else
           "Note d'un challenge = réussi x (5 + 5 x part des 61 jours encore restants) - 10 x mur - 5 x inactif "
           "+ (gain %/mois - gain du jumeau, borné à +-10) - 0,5 x (baisse max - 6 %). Le jumeau fait les mêmes gestes, "
           "sens tiré à pile ou face : un gain qui ne bat pas le jumeau ne compte pas."),
          "R moyen = résultat moyen d'un trade en multiples de son risque (frais et nuits compris).", "",
          f"### Ce que la cime fait de ses mains (sélection {es})", ""] + _comportement(sel.get("comportement", {})) \
        + _executions(sel)
    if not sans_rap:
        L += ["", f"### Ce que la cime fait de ses mains (rapport {er})", ""] + _comportement(rap.get("comportement", {})) \
            + _executions(rap)
    paniers = [(f"sélection {es}", sel)] if len(sel.get("par_panier", {})) <= 4 else []
    for titre, x in paniers + ([] if sans_rap else [(f"rapport {er}", rap)]):
        mv = any("part_mouvement_pct" in v for v in x.get("par_panier", {}).values())
        L += ["", f"### Par panier ({titre})", "",
              "| panier | %/mois | jumeau %/mois | note | trades/mois | réussis | murs |" + (" mouvement (jumeau) |" if mv else ""),
              "|---|---|---|---|---|---|---|" + ("---|" if mv else "")]
        for k, v in x.get("par_panier", {}).items():
            L.append(f"| {k.replace('USDT', '').replace('@M1', ' (minute)').replace('_MIROIR', ' retourné')} | "
                     f"{_f(v['gain_pct_mois'])} | {_f(v.get('jumeau_pct_mois'))} | {_f(v['note'])} | {v['trades_mois']:.1f} | "
                     f"{v.get('reussis_pct', 0):.0f} % | {v.get('murs_pct', 0):.0f} % |"
                     + (f" {_f(v.get('part_mouvement_pct'), 1)} % ({_f(v.get('jumeau_mouvement_pct'), 1)} %) |" if mv else ""))
    L += ["", f"## Progression de la cime (examen {es} ; une ligne toutes les 10 générations et à chaque changement)",
          "", "| génération | cime | niveau | %/mois (jumeau) | réussis (jumeau) | jours médians | morts (jumeau) | "
          "trades/mois | branches | durée |", "|---|---|---|---|---|---|---|---|---|---|"]
    avant = None
    for x in gens:
        if x["generation"] % 10 and x["cime"] == avant and x is not gens[-1]:
            continue
        avant = x["cime"]
        c, j = x["cime_examen"], x["cime_examen"].get("jumeau", {})
        L.append(f"| {x['generation']} | {x['cime']} | {_f(x['cime_niveau'])} | {_f(c['gain_pct_mois'])} "
                 f"({_f(j.get('gain_pct_mois'))}) | {c['reussis_pct']:.0f} % ({j.get('reussis_pct', float('nan')):.0f} %) | "
                 f"{_f(c.get('jours_median_reussite'), 0, False)} | {c['murs_pct']:.0f} % ({j.get('murs_pct', float('nan')):.0f} %) "
                 f"| {c['trades_mois']:.1f} | {len(x['vivantes'])} | {x['duree_s'] / 60:.1f} min |")
    evts = [x for x in lignes if x.get("quoi") in ("naissance", "coupe", "garde_fou", "plantage")]
    if evts:
        L += ["", "## Vie de l'arbre (derniers événements)", ""]
        for x in evts[-25:]:
            if x["quoi"] == "naissance":
                L.append(f"- {x['heure']} : naissance de {x['branche']}"
                         + (f" (division de {x['parents'][0]})" if x.get("parents") else " (graine)"))
            elif x["quoi"] == "coupe":
                L.append(f"- {x['heure']} : {x['branche']} coupée — {x.get('raison', '')}")
            elif x["quoi"] == "garde_fou":
                L.append(f"- {x['heure']} : garde-fou sur {x['branche']} — {x.get('raison', '')}")
            else:
                L.append(f"- {x['heure']} : PLANTAGE — {str(x.get('erreur', ''))[:200]}")
    if gens:
        d = np.array([x["duree_s"] for x in gens])
        L += ["", f"Durée moyenne d'une génération : {d.mean() / 60:.1f} min ; mémoire du programme "
              f"{gens[-1].get('memoire_go', 0):.1f} Go ; carte graphique {gens[-1].get('carte_max_go', 0):.1f} Go au plus."]
    f = dossier / "rapport.md"
    f.write_text("\n".join(L) + "\n", encoding="utf-8")
    return f
