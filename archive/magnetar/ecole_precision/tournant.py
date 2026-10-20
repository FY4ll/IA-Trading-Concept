"""L'EXAMEN TOURNANT de l'arbre de l'or MAGNETAR (19/10/2026, accord du chef de projet) : sur une période d'examen
FIXE, l'arbre se fait sur-apprendre (MAGNETAR, génération 200 : +0,44 %/mois sur le jumeau en 2023, +0,01 ± 0,48 sur le
contrôle 2024-2025). Désormais (réglage `examen_tournant` de reglages_or.yaml SEULEMENT ; HYPERNOVA n'en a pas) :

- un RÉSERVOIR de blocs d'examen, fonction PURE des réglages (graine fixée) et ÉCRIT une fois (`blocs_examen.json` dans
  le dossier de vie, VÉRIFIÉ à chaque réveil : un réservoir changé est refusé) : de `de` à `jusqua` (2010 -> 2023), une
  TRANCHE de `tranche_mois` mois après l'autre ; dans chaque tranche, un BLOC de `bloc_jours` jours (= un challenge de
  2 mois) qui commence le 1er d'un mois tiré au hasard (mois 0 à tranche - 3 de la tranche) ;
- chaque bloc + une MARGE avant et après (`marge_avant_jours`, `marge_apres_jours`) est EXCLU des mondes
  d'apprentissage : aucun challenge d'apprentissage ne touche ces jours (`permis_depart`, utilisé par jeu.Lecon ; un
  monde sans assez de départs permis est re-tiré, coeur.monde_apprentissage) ;
- à chaque génération, `blocs_par_generation` blocs tirés au hasard dans le réservoir (graine des réglages + numéro de
  génération : le tirage est refait à l'identique à la reprise) ; dans chacun, l'or réel ET l'or retourné, chacun avec son
  JUMEAU au hasard (comme avant) ; TOUTES les branches passent les MÊMES fenêtres ; les blocs ne se chevauchent pas ;
  l'incertitude est calculée PAR BLOC (l'or réel et l'or retourné d'un même bloc ne sont pas indépendants) ;
- l'or à la minute (yeux journalier -> 3 min) pour les blocs qui commencent après son échauffement (02/2015), l'or en
  15 min avant ;
- le NIVEAU d'une branche reste la moyenne de ses 3 dernières notes (3 tirages différents) ; au passage, les notes de
  l'ancien examen fixe sont mises de côté (`tournant.json`) : les niveaux ne mélangent pas deux examens ; sa « meilleure
  version » (garde-fou) est celle du meilleur NIVEAU (une note seule n'est plus comparable d'un tirage à l'autre) ;
- le contrôle 01/2024 -> 09/2025 ne change pas et ne sert JAMAIS à choisir ; rien après 09/2025.
BIAIS DE DÉPART (documenté, suivi à chaque génération) : les branches vivantes au 19/10 ont appris jusqu'à fin 2022
(examen 2023), y compris sur les mois devenus blocs d'examen (et la graine HYPERNOVA aussi) : seuls les blocs qui
commencent après `appris_jusqua` (2023) sont NEUFS pour elles. Chaque examen rapporte la note sur les blocs « déjà
appris » et sur les blocs « neufs » ; toutes les branches ont le même biais (même origine), qui s'efface à mesure
qu'elles apprennent ailleurs ; le contrôle 2024-2025 reste la seule mesure sans biais.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from collapsar.ecole.precision import jeu as JEU
from collapsar.ecole.precision.reglages import R

FICHIER_BLOCS = "blocs_examen.json"
FICHIER_PASSAGE = "tournant.json"


def active() -> bool:
    return getattr(R(), "examen_tournant", None) is not None


def _r():
    return R().examen_tournant


def marge_avant() -> pd.Timedelta:
    return pd.Timedelta(days=float(getattr(_r(), "marge_avant_jours", 7)))


def marge_apres() -> pd.Timedelta:
    return pd.Timedelta(days=float(getattr(_r(), "marge_apres_jours", 7)))


def periode() -> tuple[pd.Timestamp, pd.Timestamp]:
    p = R().periodes
    return (pd.Timestamp(getattr(_r(), "de", p.selection_de)), pd.Timestamp(getattr(_r(), "jusqua", p.selection_jusqua)))


# ============================================================================================== le réservoir
def fabriquer_blocs() -> list[dict]:
    """Les blocs du réservoir, fonction PURE des réglages (même graine = mêmes blocs)."""
    r = _r()
    de, jusqua = periode()
    rng = np.random.default_rng(int(r.graine))
    mois = int(r.tranche_mois)
    duree = pd.Timedelta(days=int(getattr(r, "bloc_jours", R().monde.challenge_jours)))
    out, d = [], de
    while d + pd.DateOffset(months=mois) <= jusqua:
        k = int(rng.integers(0, max(mois - 2, 1)))
        a = d + pd.DateOffset(months=k)
        if a + duree > jusqua:
            raise ValueError(f"bloc {a:%Y-%m-%d} : dépasse la fin du réservoir")
        out.append({"id": len(out), "debut": str(a.date()), "fin": str((a + duree).date())})
        d = d + pd.DateOffset(months=mois)
    return out


def blocs() -> list[dict]:
    return fabriquer_blocs()


def zones_interdites() -> np.ndarray:
    """[k, 2] (début, fin) en nanosecondes : chaque bloc avec ses marges, jamais appris."""
    z = [(pd.Timestamp(b["debut"]) - marge_avant(), pd.Timestamp(b["fin"]) + marge_apres()) for b in blocs()]
    return np.asarray([(a.value, b.value) for a, b in z], np.int64).reshape(-1, 2)


def interdit(t_ns: np.ndarray) -> np.ndarray:
    """Vrai pour chaque instant (ns) qui tombe dans un bloc d'examen ou sa marge."""
    t_ns = np.asarray(t_ns, np.int64)
    out = np.zeros(len(t_ns), bool)
    for a, b in zones_interdites():
        out |= (t_ns >= a) & (t_ns < b)
    return out


def permis_depart(U) -> np.ndarray:
    """[T] : un challenge d'apprentissage peut partir de cet instant si TOUT le challenge (jusqu'à sa dernière bougie)
    reste hors des blocs d'examen et de leurs marges."""
    T = U.T
    bad = interdit(U.t_ns)
    t = np.arange(T)
    fin = U.fin_challenge(t)
    idx_bad = np.flatnonzero(bad)
    prochain = np.full(T, T + 10 ** 9, np.int64)
    if len(idx_bad):
        k = np.searchsorted(idx_bad, t, side="left")
        ok = k < len(idx_bad)
        prochain[ok] = idx_bad[k[ok]]
    return (~bad) & (prochain > fin)


# ============================================================================================== l'examen
def variantes_examen() -> list[tuple[str, bool]]:
    from collapsar.ecole.precision import donnees as D
    out = []
    for m in _r().marches:
        if m in D.univers():
            out += [(m, False), (m, True)]
    return out


def monde_examen_tournant(appareil: str):
    """Le monde de l'examen (tout le réservoir, chargé une fois) et l'examen tournant."""
    from collapsar.ecole.precision.univers import Univers
    de, jusqua = periode()
    U = Univers(variantes_examen(), de, jusqua, appareil)
    return U, ExamenTournant(U, blocs(), int(_r().blocs_par_generation))


class ExamenTournant(JEU.Examen):
    """Les challenges d'UNE génération : `tirer(g)` choisit les blocs (mêmes pour toutes les branches), puis
    `jouer_un(net, graine)` comme l'examen fixe (elle et son jumeau), + notes sur blocs déjà appris / neufs."""

    tournant = True

    def __init__(self, U, blocs_: list[dict], par_generation: int, parties: int | None = None):
        from collapsar.mains.fiches import MIROIR
        # PARTIES PAR BLOC (19/10 soir, réglage `parties_par_bloc`, absent = 1 = exactement comme avant) : chaque bloc
        # (or réel et retourné) est joué plusieurs fois en même temps, sur des comptes différents (ses tirages au sort
        # et ceux de son jumeau diffèrent d'une partie à l'autre) : la part de hasard de SON jeu se moyenne ; la
        # différence entre blocs (le marché) ne bouge pas. L'incertitude reste calculée par bloc.
        self.parties = max(1, int(parties if parties is not None else getattr(_r(), "parties_par_bloc", 1)))
        self.U = U
        self.blocs = [dict(b) for b in blocs_]
        idx = {c: i for i, c in enumerate(U.cols)}
        self.col_bloc, self.t_bloc = [], []
        T_last = U.T - 1
        for b in self.blocs:
            t0 = U.instant(pd.Timestamp(b["debut"]))
            for m in _r().marches:                                   # préférence : l'or à la minute s'il existe
                cr, cm = idx.get(m), idx.get(m + MIROIR)
                if cr is None or cm is None or t0 < max(U.premier[cr], U.premier[cm]):
                    continue
                if int(U.fin_challenge(np.array([t0]))[0]) >= T_last:
                    raise ValueError(f"bloc {b['debut']} : le challenge dépasse le monde de l'examen")
                self.col_bloc.append((cr, cm))
                self.t_bloc.append(t0)
                b["variante"] = m
                break
            else:
                raise ValueError(f"bloc {b['debut']} : aucun marché d'examen disponible")
        self.paniers = [["or réel"], ["or retourné"]]
        self.J = 1
        self.pas_jours = int(R().monde.challenge_jours)          # fenêtres sans chevauchement
        self.appris_jusqua = pd.Timestamp(getattr(_r(), "appris_jusqua", "1900-01-01"))
        # BLOCS NEUFS = TÉMOIN (20/10, corrections graves, réglage `temoins_neufs` ; absent = comme avant) : les blocs qui
        # commencent après `appris_jusqua` (jamais appris par la lignée) sont joués à CHAQUE génération mais ne comptent
        # PAS dans la note de sélection (ni dans les écarts de coupe) : sélectionner sur 2 blocs les userait en quelques
        # générations, et leur bruit (± 1 de note) rendrait le choix aléatoire. Les autres blocs sont tirés au hasard.
        self.neufs = [i for i, b in enumerate(self.blocs) if pd.Timestamp(b["debut"]) >= self.appris_jusqua] \
            if getattr(_r(), "temoins_neufs", False) else []
        self.tirables = [i for i in range(len(self.blocs)) if i not in self.neufs]
        self.par_generation = min(int(par_generation), len(self.tirables))
        self.tirer(0)

    def tirage(self, g: int) -> list[int]:
        rng = np.random.default_rng([int(_r().graine), int(g)])
        if not self.neufs:                                           # comme avant
            return [int(i) for i in np.sort(rng.choice(len(self.blocs), self.par_generation, replace=False))]
        ch = rng.choice(np.asarray(self.tirables), self.par_generation, replace=False)
        return sorted({int(i) for i in ch} | set(self.neufs))

    def tirer(self, g: int):
        ch = self.tirage(g)
        cols, dep, pan, ids = [], [], [], []
        for i in ch:
            for _ in range(self.parties):                            # (parties par bloc ; 1 = comme avant)
                for k in (0, 1):                                     # or réel, or retourné
                    cols.append([self.col_bloc[i][k]])
                    dep.append(self.t_bloc[i])
                    pan.append(k)
                    ids.append(int(i))
        self.cols = np.asarray(cols, np.int64)
        self.dep = np.asarray(dep, np.int64)
        self.panier = np.asarray(pan)
        self.ids = np.asarray(ids)
        self.temoin = np.isin(self.ids, self.neufs)                  # (blocs neufs joués à part ; vide = comme avant)
        self.groupes = self.ids                                      # incertitude par bloc
        self.n = len(dep)
        self.dates = [pd.Timestamp(self.blocs[i]["debut"]) for i in ch]
        self.generation = int(g)
        return ch

    def jouer_un(self, net, graine: int) -> dict:
        if getattr(_r(), "graine_par_generation", False):
            # (19/10 soir, réglage `graine_par_generation`, absent = comme avant) : les tirages au sort de l'examen
            # changent à chaque génération (les MÊMES pour toutes les branches d'une génération) : avec tous les blocs
            # à chaque génération, le niveau (3 générations) moyenne 3 jeux différents au lieu de 3 fois le même hasard
            graine = int(graine) + 7919 * int(self.generation)
        x = super().jouer_un(net, graine)
        x["graine_examen"] = int(graine)
        notes, gains = np.asarray(x["notes"]), np.asarray(x["gains_pct_mois"])
        appris = np.array([pd.Timestamp(self.blocs[i]["debut"]) < self.appris_jusqua for i in self.ids])
        moy = lambda a: float(a.mean()) if len(a) else float("nan")
        x["blocs"] = sorted({int(i) for i in self.ids})
        x["note_blocs_appris"], x["note_blocs_neufs"] = moy(notes[appris]), moy(notes[~appris])
        x["gain_blocs_appris"], x["gain_blocs_neufs"] = moy(gains[appris]), moy(gains[~appris])
        x["challenges_neufs"] = int((~appris).sum()) // self.parties
        x["parties_par_bloc"] = self.parties
        x["note_incertitude"] = JEU.incertitude_groupes(notes, self.ids)
        x["par_cote"] = par_cote(x)
        tem = np.asarray(getattr(self, "temoin", np.zeros(len(self.ids), bool)), bool)
        sel = ~tem
        if tem.any():
            # (20/10) blocs neufs = TÉMOIN : hors de la note de sélection et des écarts de coupe, rapportés à part
            x["note_toutes"] = x["note"]
            x["note"] = moy(notes[sel])
            x["note_incertitude"] = JEU.incertitude_groupes(notes[sel], self.ids[sel])
            ordre_s = sorted({int(i) for i in self.ids[sel]})
            x["notes_selection_blocs"] = [float(notes[self.ids == k].mean()) for k in ordre_s]
            x["temoin"] = resume_partie(x, tem, sorted({int(i) for i in self.ids[tem]}), self.parties)
            x["selection"] = resume_partie(x, sel, ordre_s, self.parties)
        if getattr(_r(), "note_cotes", None) == "moins_bon":
            # garde-fou anti-casino (coeur) sur le côté qui a le plus de murs
            murs = [v["murs_pct"] for v in x["par_cote"].values() if np.isfinite(v.get("murs_pct", np.nan))]
            x["murs_pct_pire_cote"] = float(max(murs)) if murs else x["murs_pct"]
            # NOTE DE SÉLECTION APPARIÉE (19/10 soir, réglage `note_cotes: moins_bon` ; absent = moyenne comme avant) :
            # la note = la MOINS BONNE des deux moyennes (or réel, or retourné) = moyenne - la moitié de l'écart. Prise
            # sur tout l'examen (pas bloc par bloc : le minimum de deux petits nombres bruités punirait surtout la
            # chance). Une branche qui n'a appris qu'« acheter » gagne d'un côté et perd de l'autre : elle est notée
            # sur le côté qu'elle perd. Les écarts entre branches (coupe) sont mesurés sur ce même côté, bloc par bloc.
            pan = np.asarray(self.panier)
            ordre = sorted({int(i) for i in self.ids[sel]})           # (témoin : hors note ; sans témoin, comme avant)
            cote = {s: np.asarray([notes[(self.ids == k) & (pan == s)].mean() for k in ordre]) for s in (0, 1)}
            moyennes = {s: float(notes[(pan == s) & sel].mean()) for s in (0, 1)}
            faible = 0 if moyennes[0] <= moyennes[1] else 1
            x["note_moyenne"] = x["note"]
            x["note_reel"], x["note_retourne"] = moyennes[0], moyennes[1]
            x["note_cote_faible"] = "or réel" if faible == 0 else "or retourné"
            x["note"] = moyennes[faible]
            x["notes_selection_blocs"] = cote[faible].tolist()
            x["note_incertitude"] = float(cote[faible].std(ddof=1) / np.sqrt(len(ordre))) if len(ordre) > 1 else float("nan")
        return x


def resume_partie(x: dict, m: np.ndarray, blocs_: list[int], parties: int) -> dict:
    """Résultats d'une partie des challenges (témoin = blocs neufs, ou sélection) : gain %/mois (et jumeau), note, R par
    trade frais compris (si l'examen mesure les exécutions)."""
    m = np.asarray(m, bool)
    g = np.asarray(x["gains_pct_mois"], float)[m]
    out = {"blocs": list(blocs_), "challenges": int(m.sum()) // max(parties, 1),
           "gain_pct_mois": float(g.mean()) if len(g) else float("nan"),
           "note": float(np.asarray(x["notes"], float)[m].mean()) if m.any() else float("nan")}
    if "gains_jumeau_pct_mois" in x:
        out["jumeau_pct_mois"] = float(np.asarray(x["gains_jumeau_pct_mois"], float)[m].mean())
    if "r_par_challenge" in x:
        nt = int(np.asarray(x["trades_r_par_challenge"])[m].sum())
        out["trades"] = nt
        out["r_moyen"] = float(np.asarray(x["r_par_challenge"], float)[m].sum() / nt) if nt else float("nan")
    return out


FICHIER_GAIN_REEL = "note_gain_reel.json"


def passer_gain_reel(dossier: Path, dire=print) -> bool:
    """La première fois qu'un arbre vivant se réveille avec la NOTE AU GAIN RÉEL (réglage note.gain_reel, 20/10) : ses
    notes d'avant (non comparables) sont mises de côté dans note_gain_reel.json, ses records remis à zéro, et ses
    « meilleures versions » (choisies avec l'ancienne note, celle de P2 était même paralysée) rangées dans
    sauvegardes/ ; événement au journal. Rend True si passage."""
    dossier = Path(dossier)
    fp = dossier / FICHIER_GAIN_REEL
    if not getattr(R().note, "gain_reel", False) or fp.exists():
        return False
    info = {"date": datetime.now().isoformat(timespec="seconds"), "note": "gain_reel",
            "reussite_contre_jumeau": bool(getattr(R().note, "reussite_contre_jumeau", False))}
    if (dossier / "arbre.json").exists():
        from collapsar.arbre.jardinier import Arbre
        from collapsar.arbre.journal import Journal
        a = Arbre.charger(dossier / "arbre.json")
        info["notes_avant"] = {br.nom: [list(s) for s in br.scores] for br in a.vivantes()}
        info["records_avant"] = {br.nom: br.record for br in a.vivantes()}
        for br in a.vivantes():
            br.record, br.scores, br.meilleur, br.sans_progres = None, [], None, 0
        a._elire_cime()
        a.sauver(dossier / "arbre.json")
        anciennes = sorted((dossier / "branches").glob("*_meilleur.pt")) if (dossier / "branches").exists() else []
        if anciennes:
            rang = dossier / "sauvegardes" / f"meilleures_avant_gain_reel_{datetime.now():%Y%m%d_%H%M%S}"
            rang.mkdir(parents=True, exist_ok=True)
            for f in anciennes:
                shutil.move(str(f), str(rang / f.name))
            info["meilleures_rangees"] = str(rang)
        info["generation"] = a.battements
        Journal(dossier / "journal_croissance.jsonl").ecrire("note_gain_reel", generation=a.battements)
        dire(f"NOTE AU GAIN RÉEL à partir de la génération {a.battements + 1} : terme de gain = min(gain - jumeau, gain), "
             f"réussite comparée au jumeau ; notes d'avant mises de côté ({fp.name})")
    fp.write_text(json.dumps(info, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return True


FICHIER_NOTE_COTES = "note_cotes.json"


def passer_note_cotes(dossier: Path, dire=print) -> bool:
    """La première fois qu'un arbre vivant se réveille avec `note_cotes: moins_bon` : ses notes d'avant (moyenne des
    deux côtés) sont mises de côté dans note_cotes.json et ses records remis à zéro (les niveaux ne mélangent pas deux
    notes), événement au journal. Rend True si passage."""
    dossier = Path(dossier)
    fp = dossier / FICHIER_NOTE_COTES
    if getattr(_r(), "note_cotes", None) != "moins_bon" or fp.exists():
        return False
    info = {"date": datetime.now().isoformat(timespec="seconds"), "note": "moins_bon"}
    if (dossier / "arbre.json").exists():
        from collapsar.arbre.jardinier import Arbre
        from collapsar.arbre.journal import Journal
        a = Arbre.charger(dossier / "arbre.json")
        info["notes_moyenne_avant"] = {br.nom: [list(s) for s in br.scores] for br in a.vivantes()}
        for br in a.vivantes():
            br.record, br.scores, br.meilleur, br.sans_progres = None, [], None, 0
        a._elire_cime()
        a.sauver(dossier / "arbre.json")
        info["generation"] = a.battements
        Journal(dossier / "journal_croissance.jsonl").ecrire("note_cotes", generation=a.battements, note="moins_bon")
        dire(f"NOTE APPARIÉE à partir de la génération {a.battements + 1} : note = côté le moins bon (or réel / or "
             f"retourné) ; notes d'avant mises de côté ({fp.name})")
    fp.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


# ============================================================================================== les deux côtés
def _cote_de(cle: str) -> str:
    return "retourné" if ("MIROIR" in cle or "retourn" in cle) else "réel"


def par_cote(x: dict) -> dict:
    """Résultats séparés or RÉEL / or RETOURNÉ d'un examen (tournant ou fixe à deux paniers) : gain %/mois (et jumeau),
    note, murs, trades, part d'achats, R moyen des achats et des ventes. Vide si l'examen n'a pas ces deux paniers."""
    pp = x.get("par_panier", {})
    if len(pp) != 2:
        return {}
    cotes = x.get("cotes", {})
    out = {}
    for cle, v in pp.items():
        s = _cote_de(cle)
        a = cotes.get("achats", {}).get("par_panier", {}).get(cle, {})
        ve = cotes.get("ventes", {}).get("par_panier", {}).get(cle, {})
        na, nv = int(a.get("trades", 0)), int(ve.get("trades", 0))
        out[s] = {"gain_pct_mois": v.get("gain_pct_mois"), "jumeau_pct_mois": v.get("jumeau_pct_mois"),
                  "note": v.get("note"), "murs_pct": v.get("murs_pct", float("nan")), "reussis_pct": v.get("reussis_pct"),
                  "trades_mois": v.get("trades_mois"),
                  "part_achats_pct": float(100 * na / (na + nv)) if na + nv else float("nan"),
                  "r_achats": a.get("r_moyen", float("nan")), "r_ventes": ve.get("r_moyen", float("nan")),
                  "achats": na, "ventes": nv}
    return out if set(out) == {"réel", "retourné"} else {}


def texte_cotes(x: dict) -> str:
    """« réel +0.30 %/mois (jumeau -0.10), achats 94 %, R achats -0.05 / ventes -0.12 ; retourné ... »."""
    pc = x.get("par_cote") or par_cote(x)
    if not pc:
        return ""
    f = lambda v, n=2: "—" if v is None or not np.isfinite(v) else f"{v:+.{n}f}"
    g = lambda v: "—" if v is None or not np.isfinite(v) else f"{v:.0f}"
    return " ; ".join(f"{s} {f(c['gain_pct_mois'])} %/mois (jumeau {f(c['jumeau_pct_mois'])}), achats "
                      f"{g(c['part_achats_pct'])} %, R achats {f(c['r_achats'])} / ventes {f(c['r_ventes'])}"
                      for s, c in pc.items())


# ============================================================================================== passage d'un arbre
def passer(dossier: Path, dire=print) -> bool:
    """Au réveil d'un arbre en examen tournant : écrit (ou VÉRIFIE) le réservoir `blocs_examen.json` ; la première fois
    pour un arbre déjà vivant (passage depuis l'examen fixe) : sauvegarde de l'arbre, notes de l'ancien examen mises de
    côté (dans tournant.json) et records remis à zéro (niveaux et « meilleures versions » mesurés sur l'examen tournant
    seulement), événement au journal. Rend True si passage."""
    dossier = Path(dossier)
    b = blocs()
    f = dossier / FICHIER_BLOCS
    if f.exists():
        ancien = json.loads(f.read_text(encoding="utf-8"))["blocs"]
        if [(x["debut"], x["fin"]) for x in ancien] != [(x["debut"], x["fin"]) for x in b]:
            raise SystemExit(f"{f} : le réservoir des blocs d'examen a changé (réglages examen_tournant modifiés ?) : refus")
    else:
        f.write_text(json.dumps({"date": datetime.now().isoformat(timespec="seconds"),
                                 "reglages": {k: (list(v) if isinstance(v, (list, tuple)) else v)
                                              for k, v in vars(_r()).items()},
                                 "marge_avant_jours": marge_avant().days, "marge_apres_jours": marge_apres().days,
                                 "blocs": b}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    fp = dossier / FICHIER_PASSAGE
    if fp.exists():
        return False
    info = {"date": datetime.now().isoformat(timespec="seconds"), "blocs": len(b),
            "par_generation": int(_r().blocs_par_generation)}
    if (dossier / "arbre.json").exists():
        from collapsar.arbre.jardinier import Arbre
        from collapsar.arbre.journal import Journal
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sauve = dossier / "sauvegardes" / f"avant_tournant_{stamp}"
        sauve.mkdir(parents=True)
        for nom in ("arbre.json", "derniers_examens.json"):
            if (dossier / nom).exists():
                shutil.copy2(dossier / nom, sauve / nom)
        a = Arbre.charger(dossier / "arbre.json")
        info["notes_examen_fixe"] = {br.nom: [list(s) for s in br.scores] for br in a.vivantes()}
        for br in a.vivantes():
            br.record, br.scores, br.meilleur, br.sans_progres = None, [], None, 0
        a._elire_cime()
        a.sauver(dossier / "arbre.json")
        info["sauvegarde"] = str(sauve)
        info["generation"] = a.battements
        Journal(dossier / "journal_croissance.jsonl").ecrire("examen_tournant", **{k: v for k, v in info.items()
                                                                                  if k != "notes_examen_fixe"})
        dire(f"PASSAGE à l'examen tournant après la génération {a.battements} : {len(b)} blocs, "
             f"{info['par_generation']} par génération ; notes de l'ancien examen mises de côté ; sauvegarde {sauve}")
    fp.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return True
