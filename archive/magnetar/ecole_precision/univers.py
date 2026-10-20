"""Un MONDE de l'école de la précision : des marchés (réels ou retournés) sur une fenêtre d'années, avec
- l'horloge FTMO du projet (mains/horloge.Horloge : heures du serveur, fermeture avant toute pause > 2 h, jour de
  Prague pour le mur du jour, conversion en dollars, levier mesuré, nuits de chaque époque et nuit triple FTMO) ;
- les frais FTMO réparés du 16/10 à chaque bougie (donnees.demi_frais) ;
- ses yeux rangés à plat (structure.py) pour être lus d'un coup par la carte graphique.
Les comptes ont chacun leur PANIER de marchés (colonnes) et leur propre instant : un seul monde sert à tous.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision.reglages import R, UNITES, UNITES_BRUTES
from collapsar.mains.horloge import Horloge
from collapsar.yeux.faits import seances

RETOUR_BRUT = 16                      # lignes d'unité gardées avant le début (bougies brutes)
COMPTES = ("normal", "swing")


def compte_ftmo() -> str:
    """Type de compte FTMO simulé (réglage `mains.compte`) : « normal » par défaut (HYPERNOVA), « swing » (MAGNETAR)."""
    c = str(getattr(R().mains, "compte", "normal")).lower()
    if c not in COMPTES:
        raise ValueError(f"mains.compte : {c} (attendu {COMPTES})")
    return c


def regles_compte(compte: str, pause_longue: np.ndarray, heures_pause: np.ndarray, ouvert: np.ndarray, hmin: float):
    """(derniere, sans_ouverture) [T, M] pour le simulateur. Normal : fermeture forcée à la dernière bougie avant une
    pause > 2 h et pas d'ouverture à cette bougie (le MÊME tableau, comme avant). Swing : jamais de fermeture forcée ;
    pas de nouvelle position quand il reste au plus `hmin` heures avant une pause > 2 h (0 : aucune limite)."""
    if compte != "swing":
        return pause_longue, pause_longue
    rien = np.zeros_like(pause_longue)
    return rien, ((heures_pause <= hmin) & ouvert if hmin > 0 else rien)


class Univers:
    def __init__(self, variantes: list[tuple[str, bool]], de: pd.Timestamp, jusqua: pd.Timestamp,
                 appareil: str = "cpu", echauffement_jours: float | None = None):
        r = R()
        jusqua = min(pd.Timestamp(jusqua), r.periodes.fin_donnees)
        ech = r.monde.echauffement_jours if echauffement_jours is None else echauffement_jours
        self.variantes = list(variantes)
        self.cols = [D.nom_variante(n, m) for n, m in self.variantes]
        self.dev = torch.device(appareil)
        self.de, self.jusqua = pd.Timestamp(de), jusqua
        debut = pd.Timestamp(de) - pd.Timedelta(days=ech)
        bruts, dfs, tranches = {}, {}, []
        for (nom, mir), col in zip(self.variantes, self.cols):
            x = S.lire(nom, mir)
            t15 = np.asarray(x["t15"])
            a = int(np.searchsorted(t15, debut.value))
            b = int(np.searchsorted(t15, jusqua.value))
            if b - a < 96 * 10:
                raise ValueError(f"{col} : trop peu de données entre {debut:%Y-%m-%d} et {jusqua:%Y-%m-%d}")
            bruts[col] = x
            tranches.append((a, b))
            dfs[col] = pd.DataFrame({"time": t15[a:b].astype("datetime64[ns]"),
                                     **{k: np.asarray(x[c][a:b]) for k, c in
                                        (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"))}})
        donnees = dict(dfs)
        for src in D.sources_conversion([n for n, _ in self.variantes]):
            if src not in donnees:
                q = D.quinze(src)
                donnees[src] = q[(q["time"] >= debut - pd.Timedelta(days=7)) & (q["time"] < jusqua)].reset_index(drop=True)
        fiches = {col: D.fiche_variante(n, m) for (n, m), col in zip(self.variantes, self.cols)}
        h = Horloge(donnees, self.cols, "cpu", fiches, nuit_historique=True)
        del donnees
        self.temps = h.temps
        self.T, self.M = h.T, h.M
        np_ = lambda x: x.cpu().numpy()
        # ---------------------------------------------------------------- le simulateur (numpy, processeur)
        self.o, self.h, self.l, self.c = np_(h.o), np_(h.h), np_(h.l), np_(h.c)
        self.fx = np_(h.fx)
        self.ouvert, self.derniere = np_(h.ouvert), np_(h.derniere)
        self.jour = np_(h.jour).astype(np.int64)
        self.levier = np_(h.levier)
        self.pas_u, self.pas_d, self.min_u = np_(h.pas_unites), np_(h.pas_dollars), np_(h.min_unites)
        na, nv = np_(h.nuit_achat), np_(h.nuit_vente)
        self.nuit_a = na if na.ndim == 2 else np.broadcast_to(na, (self.T, self.M)).copy()
        self.nuit_v = nv if nv.ndim == 2 else np.broadcast_to(nv, (self.T, self.M)).copy()
        self.nuits = np_(h.nuits_regle)[np_(h.regle_nuit)].T.copy()                         # [T, M]
        self.heures_pause = np_(h.heures_pause).astype(np.float32)
        # TYPE DE COMPTE FTMO (réglage `mains.compte`, absent = « normal », comme HYPERNOVA) :
        # - normal : fermeture forcée à la dernière bougie avant une pause > 2 h (week-end compris), ordres annulés ;
        # - swing (19/10/2026, compte du chef de projet) : positions et ordres gardés par-dessus les pauses et le
        #   week-end ; aucune nouvelle position dans les `ouverture_interdite_avant_pause_h` dernières heures avant une
        #   pause > 2 h (règle FTMO « jeu des écarts »). `pause_longue` garde la dernière bougie avant chaque pause.
        self.pause_longue = self.derniere
        self.compte = compte_ftmo()
        self.derniere, self.sans_ouverture = regles_compte(self.compte, self.pause_longue, self.heures_pause, self.ouvert,
                                                           float(getattr(r.mains, "ouverture_interdite_avant_pause_h", 0.0)))
        loc = np_(h.local).astype(np.int64)                                                  # ligne du marché
        self.local = loc
        self.demi = np.zeros((self.T, self.M))
        for j, col in enumerate(self.cols):
            a, b = tranches[j]
            dm_ = np.asarray(bruts[col]["demi"][a:b])
            self.demi[:, j] = dm_[np.clip(loc[:, j], 0, None)]
        del h
        # premier instant où un compte peut partir sur chaque marché (historique et agitation suffisants)
        t_ns = self.temps.values.astype("datetime64[ns]").astype(np.int64)
        self.t_ns = t_ns
        self.premier = np.full(self.M, self.T, np.int64)
        A = np.zeros((self.T, self.M), np.float32)
        for j, col in enumerate(self.cols):
            a, b = tranches[j]
            Av = np.asarray(bruts[col]["A"][a:b])
            A[:, j] = np.where(loc[:, j] >= 0, Av[np.clip(loc[:, j], 0, None)], np.nan)
            t0 = np.asarray(bruts[col]["t15"][0]) + int(pd.Timedelta(days=ech).value)
            ok = (loc[:, j] >= 0) & np.isfinite(A[:, j]) & (A[:, j] > 0) & (t_ns >= t0) & (t_ns >= pd.Timestamp(de).value)
            w = np.flatnonzero(ok)
            if len(w):
                self.premier[j] = w[0]
        self.A = np.nan_to_num(A, nan=0.0)
        if getattr(r, "frais_honnetes", None) is not None:
            # FRAIS HONNÊTES (20/10, MAGNETAR, frais_honnetes.py ; absent = HYPERNOVA, comme avant) : demi-écart de chaque
            # bougie x facteur de l'heure (réouverture, avant une pause) et des grandes annonces
            from collapsar.ecole.precision import frais_honnetes as FH
            self.bilan_frais = FH.appliquer(self, r.frais_honnetes)
        # ---------------------------------------------------------------- les yeux (tenseurs, carte graphique)
        dev = self.dev
        T_ = lambda x, dt=None: torch.as_tensor(np.ascontiguousarray(x), device=dev, dtype=dt)
        self.tC = T_(self.c, torch.float32)
        self.tA = T_(self.A, torch.float32)
        self.tDEMI = T_(self.demi, torch.float32)
        self.tLOC = T_(loc.astype(np.int32))
        self.tPAUSE = T_(self.heures_pause)
        self.tOUVERT = T_(self.ouvert)
        tt = self.temps + pd.Timedelta(minutes=15)
        hh = (tt.hour + tt.minute / 60).to_numpy()
        wd = (tt.dayofweek + hh / 24).to_numpy()
        temps_f = np.stack([np.sin(2 * np.pi * hh / 24), np.cos(2 * np.pi * hh / 24), np.sin(2 * np.pi * wd / 7),
                            np.cos(2 * np.pi * wd / 7)], 1).astype(np.float32)
        self.tTEMPS = T_(np.concatenate([temps_f, seances(self.temps)], 1))               # [T, 7]
        if bool(getattr(r.yeux, "foule", False)):            # yeux de la foule (foule.py) : seulement si allumés
            from collapsar.ecole.precision import foule as FO
            self.tFOULE, self.tFOULE_IDX = FO.tenseurs(self.variantes, self.temps, dev)
        # Tout est rangé À PLAT pour être lu en quelques lectures groupées (toutes unités, tous marchés) :
        # - LIGNES [T, M, U] : ligne de l'unité (dans DONNEES) vue à chaque instant, -1 si aucune ;
        # - DONNEES [ΣR, 2K + 5] : ids des 2K zones les plus proches (-1), 4 derniers sommets / creux, clôture ;
        # - ZONES [ΣZ, 5] : haut, bas, instant où elle devient visible, 1er contact, réaction (en lignes du marché).
        K = R().yeux.zones_par_cote
        NUn = len(UNITES)
        self.dispo = np.zeros((self.M, NUn), np.float32)
        lignes = np.full((self.T, self.M, NUn), -1, np.int64)
        r_debut = np.zeros((self.M, NUn), np.int64)
        donnees_l, zones_l = [], []
        off_r, off_z = 0, 0
        for iu, u in enumerate(UNITES):
            for j, col in enumerate(self.cols):
                if u not in bruts[col]:
                    continue
                x = bruts[col][u]
                a, b = tranches[j]
                lg = np.asarray(x["ligne"][a:b]).astype(np.int64)
                ok = lg >= 0
                if not ok.any():
                    continue
                self.dispo[j, iu] = 1.0
                r0 = max(0, int(lg[ok].min()) - RETOUR_BRUT)
                r1 = int(lg[ok].max()) + 1
                k = np.asarray(x["knn"][r0:r1]).astype(np.int64).reshape(r1 - r0, 2 * K)
                kk = k[k >= 0]
                z0, z1 = (int(kk.min()), int(kk.max()) + 1) if len(kk) else (0, 0)
                k = np.where(k >= 0, k - z0 + off_z, -1)
                lj = np.where(ok, lg - r0 + off_r, -1)
                lignes[:, j, iu] = np.where(loc[:, j] >= 0, lj[np.clip(loc[:, j], 0, None)], -1)
                r_debut[j, iu] = off_r
                donnees_l.append(np.concatenate([k.astype(np.float32), np.asarray(x["sw"][r0:r1], np.float32),
                                                 np.asarray(x["cl"][r0:r1], np.float32)[:, None]], 1))
                # instants rangés en lignes du marché (tranche [a, b)) : comparés à `local` au moment de décider
                temps_z = [np.asarray(x[cle][z0:z1]).astype(np.int64) for cle in ("vis", "tou", "rea")]
                temps_z = [np.where(v >= S.JAMAIS, 2 ** 30, np.clip(v - a, -2 ** 30, 2 ** 30)).astype(np.float32)
                           for v in temps_z]
                zones_l.append(np.stack([np.asarray(x["top"][z0:z1], np.float32), np.asarray(x["bot"][z0:z1], np.float32),
                                         *temps_z], 1))
                off_r += r1 - r0
                off_z += z1 - z0
        if off_z >= 2 ** 24:
            raise ValueError("trop de zones pour des identifiants exacts en float32")
        self.tLIGNES = T_(lignes.astype(np.int32))
        self.tDONNEES = T_(np.concatenate(donnees_l) if donnees_l else np.zeros((1, 2 * K + 5), np.float32))
        self.tZONES = T_(np.concatenate(zones_l) if zones_l else np.zeros((1, 5), np.float32))
        self.tRDEBUT = T_(r_debut)
        self.tDISPO = T_(self.dispo)
        from collapsar.ecole.precision import suiveur as SV
        if SV.active():                                      # stop suiveur (suiveur.py) : seulement si allumé
            self.sw_v, self.sw_id, sv_dispo = SV.tableaux(bruts, self.cols, tranches, loc, self.T)
            self.tSV_DISPO = T_(sv_dispo)
        del bruts, lignes
        if bool(getattr(r.yeux, "tendance", False)):         # tendance de fond (tendance.py) : seulement si allumée
            from collapsar.ecole.precision import tendance as TD
            self.tTEND = T_(TD.tableau(self.variantes, self.t_ns), torch.float32)          # [T, M, 12]
        if bool(getattr(r.yeux, "monde", False)):            # yeux du monde (monde.py) : seulement si allumés
            from collapsar.ecole.precision import monde as MO
            self.tMONDE, self.tMONDE_IDX = MO.tenseurs(self.variantes, self.temps, dev)
        if bool(getattr(r.yeux, "juge", False)):             # notes du juge (juge_trade.py) : seulement si allumées
            from collapsar.ecole.precision import juge_trade as JT
            self.tJUGE = JT.tenseur_notes(self)

    def vers(self, appareil) -> "Univers":
        """Le monde rangé sur un autre appareil (tous ses tenseurs). Examen tournant de l'arbre de l'or (carte plafonnée) :
        le grand monde de l'examen (2010 -> 2023) attend dans la mémoire vive pendant les leçons."""
        dev = torch.device(appareil)
        if dev != self.dev:
            for k, v in list(vars(self).items()):
                if isinstance(v, torch.Tensor):
                    setattr(self, k, v.to(dev))
            self.dev = dev
        return self

    # ---------------------------------------------------------------------------------------------- départs
    def instant(self, date) -> int:
        return int(np.searchsorted(self.t_ns, pd.Timestamp(date).value))

    def fin_challenge(self, t0: np.ndarray) -> np.ndarray:
        """Dernière ligne du challenge de chaque départ (2 mois de calendrier)."""
        jours = R().monde.challenge_jours
        fin = self.t_ns[t0] + int(pd.Timedelta(days=jours).value)
        return np.searchsorted(self.t_ns, fin, side="left") - 1
