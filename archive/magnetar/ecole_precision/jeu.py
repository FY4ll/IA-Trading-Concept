"""LA TABLE DE JEU de l'école de la précision : des comptes FTMO qui vivent dans un monde (univers.py), le simulateur
(simulateur.py), ses yeux (vue.py), ses mains (cerveau.py), ses regards et ses réveils ; les leçons (essais et
erreurs, PPO comme les écoles précédentes : chaque regard jugé sur l'argent gagné jusqu'au regard suivant) et
l'EXAMEN (mêmes fenêtres pour le candidat et le champion).

DANS L'ORDRE DU TEMPS (vérifié le 18/10, tests/test_journal_trading.py) : chaque compte a son instant t ; ceux qui
regardent décident à la clôture de leur bougie t (bougies terminées seulement), leurs ordres partent à l'ouverture de
t + 1, puis Table.avancer fait passer TOUS les comptes actifs de t à t + 1 (jamais de saut, jamais de retour).
JOURNAL DE TRADING (journal_trading.py) : tb.carnet = None par défaut (rien ne change) ; une branche greffée voit son
carnet (onglet Trade ajouté à sa position, Historique ajouté EN DERNIER sur la carte graphique).

Récompense (comme ecole/regard.py) : l'argent du compte en % du capital, frais et nuits compris, une perte près d'un mur
fait plus mal (ecole/classe.ressenti), un mur ou l'inactivité FTMO = -20, un challenge réussi = +5. Attendre ne coûte
rien et ne rapporte rien. PEUR PAR BRANCHE (19/10, peur.py) : Table.peur (tempérament « peur » de la branche) remplace
ce ressenti pour elle seule ; None = comme avant.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import torch

from collapsar.ecole.precision import cerveau as C
from collapsar.ecole.precision import journal_trading as JN
from collapsar.ecole.precision import simulateur as SIM
from collapsar.ecole.precision.reglages import CAPITAL, R, UNITES
from collapsar.ecole.precision.vue import Vue
from collapsar.ecole.regard import avantages_regards
from collapsar.mains.simulateur import INACTIVITE_JOURS, JOURS_TRADING_MIN

REVEIL_GERE, REVEIL_EXECUTE, REVEIL_DANGER, REVEIL_MOUVEMENT, REVEIL_DEBUT = 1, 2, 3, 4, 5
GERE = SIM.STOP | SIM.TP1 | SIM.DEST | SIM.FORCEE | SIM.REFUS | SIM.EXPIRE


def danger(v, solde_minuit):
    jour = (solde_minuit - v) / (0.05 * CAPITAL)
    total = (CAPITAL - v) / (0.10 * CAPITAL)
    return np.clip(np.maximum(jour, total), 0, 1)


def ressenti(gain, d):
    from collapsar.ecole.classe import PEUR_DU_MUR
    return np.where(gain < 0, gain * (1 + PEUR_DU_MUR * d * d), gain)


# PEUR DU MUR PAR BRANCHE (19/10/2026, accord du chef de projet ; peur.py) : réglage `peur` du tempérament d'UNE branche,
# absent = la peur d'avant (ressenti ci-dessus) pour toutes les autres branches et pour HYPERNOVA.
PEURS = ("pres_des_murs", "fermeture_r")


def multiplicateur_peur(d, seuil: float = 0.5, maxi: float = 5.0):
    """« pres_des_murs » : 1 tant que moins de `seuil` de la perte permise est consommée, puis monte en ligne droite
    jusqu'à `maxi` au mur."""
    return 1.0 + (maxi - 1.0) * np.clip((d - seuil) / max(1.0 - seuil, 1e-9), 0.0, 1.0)


def douleur_pres_des_murs(gain, v_avant, v_apres, ref, d_apres, seuil: float = 0.5, maxi: float = 5.0):
    """Récompense d'une bougie (en % du capital) : l'argent gagné ou perdu tel quel (gain), MOINS une douleur en plus
    seulement pour la part de la baisse qui passe SOUS `ref` (le plus haut solde réalisé de la journée : un trade
    gagnant qui oscille au-dessus ne fait jamais mal), multipliée par (multiplicateur - 1) : rien loin des murs."""
    sous = np.clip(np.minimum(v_avant, ref) - v_apres, 0.0, None) / CAPITAL * 100
    return gain - (multiplicateur_peur(d_apres, seuil, maxi) - 1.0) * sous


class Table:
    def __init__(self, U, B: int, J: int):
        self.U, self.B, self.J = U, B, J
        self.cpt = SIM.Comptes(U, B, J)
        self.vue = Vue(U)
        self.dev = U.dev
        self.prochain = np.zeros(B, np.int64)
        self.dernier = np.zeros(B, np.int64)
        self.reveil = np.zeros(B, np.bool_)
        self.raison = np.zeros(B, np.int64)
        self.prix_vu = np.full((B, J), np.nan)
        self.danger_vu = np.zeros(B)
        self.t_ouv = np.full((B, J), -1, np.int64)
        self.poseur = np.full((B, J), -1, np.int64)
        # JOURNAL DE TRADING (journal_trading.py) : None = aucun (comportement d'avant) ; donné par JN.equiper
        self.carnet = None
        # PEUR DU MUR de la branche qui joue (tempérament « peur », peur.py) : None = la peur d'avant (ressenti)
        self.peur = None
        self.haut_solde = np.full(B, CAPITAL)       # plus haut solde réalisé de la journée (peur « pres_des_murs »)

    # ------------------------------------------------------------------------------------------------ départs
    def demarrer(self, masque: np.ndarray, cols: np.ndarray, departs: np.ndarray):
        i = np.flatnonzero(masque)
        if not len(i):
            return
        if self.carnet is not None:                 # journal : fin des positions ouvertes, journal continué ou vidé
            self.carnet.avant_depart(i, np.asarray(departs, np.int64))
        self.cpt.recommencer(masque, cols, departs)
        self.prochain[i] = departs
        self.dernier[i] = departs
        self.reveil[i] = True
        self.raison[i] = REVEIL_DEBUT
        self.prix_vu[i] = np.nan
        self.danger_vu[i] = 0.0
        self.t_ouv[i] = -1
        self.poseur[i] = -1
        self.haut_solde[i] = CAPITAL

    # ------------------------------------------------------------------------------------------------ ce qu'elle voit
    def entrees(self, qui: np.ndarray):
        """Pour les comptes `qui` (indices) : t, colonnes, vue du compte [n, 18], positions [n, J, 11] (tenseurs)."""
        t, cols, compte, pos = self.entrees_np(qui)
        dev = self.dev
        tens = lambda x, dt=torch.float32: torch.as_tensor(np.ascontiguousarray(x), dtype=dt, device=dev)
        return tens(t, torch.long), tens(cols, torch.long), tens(compte), tens(pos)

    def entrees_np(self, qui: np.ndarray):
        U, c = self.U, self.cpt
        t = c.t[qui]
        cols = c.col[qui]
        cc = np.clip(cols, 0, None)
        slot = cols >= 0
        px = U.c[t[:, None], cc]
        A = np.maximum(U.A[t[:, None], cc], 1e-12)
        fx = U.fx[t[:, None], cc]
        u = c.u[qui]
        sg = np.sign(u)
        with np.errstate(invalid="ignore", divide="ignore"):
            nr = lambda x: np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
            latent = nr(u * (px - c.entree[qui]) * fx / np.where(c.risque[qui] > 0, c.risque[qui], np.nan))
            d_stop = nr(sg * (px - c.stop[qui]) / A)
            tp_actif = np.isfinite(c.tp1[qui]) & ~c.tp1_fait[qui] & (c.part[qui] > 0)
            d_tp1 = np.where(tp_actif, nr(sg * (c.tp1[qui] - px) / A), 0.0)
            d_dest = nr(sg * (c.dest[qui] - px) / A)
            att = c.att[qui] > 0
            sa = np.sign(c.att_u[qui]) * att
            d_att = np.where(att, nr(sa * (px - c.att_prix[qui]) / A), 0.0)
        tenu = np.where(u != 0, np.log1p(np.maximum(t[:, None] - self.t_ouv[qui], 0) / 4) / 5, 0.0)
        pos = np.stack([sg, att.astype(float), sa, np.clip(latent, -10, 10), np.clip(d_stop, -10, 10),
                        np.clip(d_tp1, -10, 10), np.clip(d_dest, -10, 10), c.tp1_fait[qui].astype(float), tenu,
                        np.clip(d_att, -10, 10), c.att_reste[qui] / 96 * att], -1) * slot[..., None]
        if self.carnet is not None and self.carnet.voir:   # journal : l'onglet Trade complète sa position / son ordre
            pos = np.concatenate([pos, self.carnet.onglet_trade(qui, px, A, fx, u, sg, att) * slot[..., None]], -1)
        v = c.valeurs()[qui]
        sm = c.solde_minuit[qui]
        der = np.maximum(c.jour_debut[qui], c.jour_dernier[qui])
        rais = np.zeros((len(qui), 6))
        rais[np.arange(len(qui)), self.raison[qui]] = 1
        compte = np.concatenate([np.stack([
            (v / CAPITAL - 1) * 10, (v - sm) / CAPITAL * 10, (v - (sm - 0.05 * CAPITAL)) / CAPITAL * 10,
            (v - 0.9 * CAPITAL) / CAPITAL * 10, (u != 0).sum(1) / self.J, att.sum(1) / self.J,
            (c.jour_cpt[qui] - der) / INACTIVITE_JOURS, np.minimum(c.jours_trades[qui], JOURS_TRADING_MIN) / JOURS_TRADING_MIN,
            np.minimum((t - self.dernier[qui]) / 16, 4), (c.fin[qui] - t) / 5856, danger(v, sm), slot.sum(1) / 4], -1),
            rais], -1)
        return t, cols, np.clip(compte, -10, 10).astype(np.float32), np.clip(pos, -10, 10).astype(np.float32)

    def regarder(self, net, qui: np.ndarray, choix=None, evaluer: bool = True):
        """Décision des comptes `qui` (ou relecture de choix donnés). Rend (choix, lp, lp_exec, hasard, valeur, niveaux,
        entrées)."""
        t, cols, fc, pos = self.entrees(qui)
        s = self.vue.structure(t, cols)
        car, pos, q = yeux_complets(self, s, t, pos, torch.as_tensor(np.asarray(qui, np.int64), device=t.device), net)
        fm = torch.cat([car, pos], -1)
        sortie = C.politique(net, s, fm, fc, pos, choix, evaluer)
        if self.carnet is not None:
            self.carnet.retenir(qui, sortie[0], q, len(qui))
        return sortie, (t, cols, fc, pos)

    # ------------------------------------------------------------------------------------------------ ses mains
    def appliquer(self, qui: np.ndarray, lv: dict):
        """Ses choix -> ordres du simulateur (exécutés à la bougie suivante)."""
        U, c = self.U, self.cpt
        g = niveaux_np(lv)
        if self.carnet is not None:                 # journal : onglet Trade noté (log), ordres notés en attente
            self.carnet.decision(np.asarray(qui), g)
        t = c.t[qui]
        cols = c.col[qui]
        cc = np.clip(cols, 0, None)
        fx = U.fx[t[:, None], cc]
        v = c.valeurs()[qui]
        risque_d = g["risque_pct"] / 100 * v[:, None]
        unites = g["sig"] * risque_d / (np.maximum(g["rd"], 1e-12) * fx)
        act = np.where(g["ferme"], SIM.FERMER, np.where(g["limite"], SIM.LIMITE, np.where(g["ouvre"], SIM.MARCHE, SIM.RIEN)))
        act = np.where(cols >= 0, act, SIM.RIEN)
        if getattr(R().mains, "marche_annule_ordre", False):
            # (20/10, réglage mains.marche_annule_ordre de MAGNETAR ; absent = comme avant) : une ouverture au marché ou un
            # nouvel ordre limite REMPLACE l'ordre limite en attente sur ce marché (annulé à la même ouverture de bougie,
            # comme « fermer / annuler » puis ouvrir) ; le cerveau le permet (cerveau.politique)
            ann = ((act == SIM.MARCHE) | (act == SIM.LIMITE)) & (c.att[qui] > 0) & (c.u[qui] == 0)
            if ann.any():
                c.att[qui] = np.where(ann, 0, c.att[qui])
        c.ord_act[qui] = act
        c.ord_u[qui] = np.where(g["ouvre"], unites, 0.0)
        c.ord_prix[qui] = g["entree"]
        c.ord_stop[qui] = g["stop"]
        c.ord_tp1[qui] = g["tp1"]
        c.ord_part[qui] = np.where(np.isfinite(g["tp1"]), g["part"], 0.0)
        c.ord_dest[qui] = g["dest"]
        c.ord_duree[qui] = g["validite"]
        if "suiveur_u" in g:                                  # stop suiveur (suiveur.py) : son choix pour ce trade
            c.ord_sv_u[qui] = np.where(g["ouvre"] & (cols >= 0), g["suiveur_u"], -1)
            c.ord_sv_tp1[qui] = g["suiveur_tp1"]
            c.ord_sv_m[qui] = g["suiveur_marge"]
        if "suiveur_1r" in g:                                 # suiveur après +1R (une branche) : son choix
            c.ord_sv_1r[qui] = g["suiveur_1r"] & g["ouvre"] & (cols >= 0)
            c.ord_sv_ag[qui] = g["suiveur_ag"]
        # regard : prochain rendez-vous, prix vu, danger vu
        self.prochain[qui] = t + g["delai"]
        self.dernier[qui] = t
        self.reveil[qui] = False
        self.raison[qui] = 0
        self.prix_vu[qui] = U.c[t[:, None], cc]
        self.danger_vu[qui] = danger(v, c.solde_minuit[qui])

    # ------------------------------------------------------------------------------------------------ une bougie
    def avancer(self):
        U, c = self.U, self.cpt
        actifs = c.actif.copy()
        v_avant = c.valeurs()
        d_avant = danger(v_avant, c.solde_minuit)
        cn = self.carnet
        if cn is not None:                          # journal : l'état d'avant la bougie (prix de sortie, raisons)
            avant = (c.u.copy(), c.stop.copy(), c.tp1.copy(), c.dest.copy())
        jour_avant = c.jour_cpt.copy() if self.peur else None
        c.pas(R().monde.frais_stop_glissement)
        if cn is not None:
            cn.apres_pas(*avant, v_avant, actifs)
        ev = c.evt
        ouverte = (ev & (SIM.OUVERTE | SIM.EXECUTE)) != 0
        self.t_ouv = np.where(ouverte, c.t[:, None], self.t_ouv)
        # réveils
        cc = np.clip(c.col, 0, None)
        px = U.c[c.t[:, None], cc]
        A = U.A[c.t[:, None], cc]
        d = danger(c.valeur, c.solde_minuit)
        bouge = ((np.abs(px - self.prix_vu) >= R().mains.gros_mouvement * A) & (c.col >= 0)).any(1)
        causes = [((ev & GERE) != 0).any(1), REVEIL_GERE], [((ev & SIM.EXECUTE) != 0).any(1), REVEIL_EXECUTE], \
                 [(d >= 0.5) & (self.danger_vu < 0.5), REVEIL_DANGER], [bouge, REVEIL_MOUVEMENT]
        for cause, code in causes:
            cause = cause & actifs
            self.raison = np.where(cause & ~self.reveil, code, self.raison)
            self.reveil |= cause
        gain = (c.valeur - v_avant) / CAPITAL * 100
        if self.peur:                               # peur de la branche (peur.py) ; sinon exactement comme avant
            base = self._ressenti_branche(gain, v_avant, jour_avant)
        else:
            base = ressenti(gain, d_avant)
        r = base - R().monde.punition_mur * c.mort + R().monde.bonus_reussite * c.reussi
        fini = c.mort | c.reussi | (c.t >= c.fin)
        return np.where(actifs, r, 0.0), fini & actifs, actifs

    def _ressenti_branche(self, gain, v_avant, jour_avant):
        """La peur choisie pour cette branche (self.peur = {"mode": ..., "seuil", "max"}), après le pas du simulateur :
        - « pres_des_murs » : argent tel quel ; douleur en plus seulement près des murs (multiplicateur_peur) et
          seulement sur la baisse sous le plus haut solde RÉALISÉ de la journée (douleur_pres_des_murs) ;
        - « fermeture_r » : rien pendant le trade ; à la fermeture, son résultat en R (somme des trades fermés)."""
        c = self.cpt
        p = self.peur
        mode = p.get("mode")
        if mode == "fermeture_r":
            return np.where(np.isfinite(c.r_ferme), c.r_ferme, 0.0).sum(1)
        if mode != "pres_des_murs":
            raise ValueError(f"peur inconnue : {mode} (attendu {PEURS})")
        ref = np.where(c.jour_cpt != jour_avant, c.solde_minuit, self.haut_solde)   # nouveau jour : solde de minuit
        r = douleur_pres_des_murs(gain, v_avant, c.valeur, ref, danger(c.valeur, c.solde_minuit),
                                  float(p.get("seuil", 0.5)), float(p.get("max", 5.0)))
        self.haut_solde = np.maximum(ref, c.solde)
        return r


CLES_NIV = ("entree", "stop", "tp1", "part", "dest", "rd", "sig", "ouvre", "limite", "ferme", "risque_pct", "validite",
            "delai")
CLES_SUIVEUR = ("suiveur_u", "suiveur_tp1", "suiveur_marge")      # stop suiveur (suiveur.py), en plus si allumé
CLES_1R = ("suiveur_1r", "suiveur_ag")                          # suiveur après +1R (suiveur.py), en plus si allumé


def cles_niv() -> tuple[str, ...]:
    from collapsar.ecole.precision import suiveur as SV
    if not SV.active():
        return CLES_NIV
    return CLES_NIV + CLES_SUIVEUR + (CLES_1R if SV.active_1r() else ())


def paquet_niveaux(lv: dict) -> torch.Tensor:
    """[13, n, J] (+3 avec le stop suiveur) : les niveaux choisis en un seul tableau (le délai, propre au compte, est
    recopié sur chaque marché)."""
    J = lv["entree"].shape[1]
    return torch.stack([(lv[k][:, None].expand(-1, J) if k == "delai" else lv[k]).float() for k in cles_niv()])


def niveaux_np(lv) -> dict:
    """Les niveaux choisis, ramenés sur le processeur en UN seul transfert (dict de tenseurs ou paquet [13, n, J])."""
    if isinstance(lv, dict) and isinstance(lv.get("entree"), np.ndarray):
        return lv
    x = (paquet_niveaux(lv) if isinstance(lv, dict) else lv).cpu().numpy()
    g = {k: x[i].astype(np.float64) for i, k in enumerate(cles_niv())}
    for k in ("ouvre", "limite", "ferme"):
        g[k] = g[k] > 0.5
    g["validite"] = g["validite"].round().astype(np.int64)
    g["delai"] = g["delai"][:, 0].round().astype(np.int64)
    if "suiveur_u" in g:
        g["suiveur_u"] = g["suiveur_u"].round().astype(np.int64)
        g["suiveur_tp1"] = g["suiveur_tp1"] > 0.5
    if "suiveur_1r" in g:
        g["suiveur_1r"] = g["suiveur_1r"] > 0.5
    return g


def yeux_complets(tb: Table, s: dict, t: torch.Tensor, pos: torch.Tensor, rang: torch.Tensor, net=None):
    """(yeux du marché, position complète, situation) : sans journal, exactement comme avant (yeux, position, None) ;
    avec un carnet, la situation de chaque côté est résumée (journal_trading.situation) et, si le cerveau voit son
    journal, son Historique est ajouté EN DERNIER à la position. Un cerveau à la TENDANCE DE FOND (tendance.py, une
    branche) la voit ensuite, tout à la fin."""
    car = tb.vue.caracteristiques(s)
    cn = tb.carnet
    q = None
    if cn is not None:
        q = JN.situation(s, tb.U.tTEMPS[t])
        if cn.voir:
            pos = torch.cat([pos, cn.historique(rang, t, q) * s["slot"][..., None]], -1)
    if getattr(net, "n_tendance", 0):
        if not hasattr(tb.U, "tTEND"):
            raise ValueError("cerveau à la tendance de fond dans un monde sans tendance (réglage yeux.tendance éteint)")
        n, J = s["cc"].shape
        pos = torch.cat([pos, tb.U.tTEND[t[:, None].expand(n, J), s["cc"]] * s["slot"][..., None]], -1)
    return car, pos, q


class _Entrees:
    """Tableaux d'entrée fixes d'un graphe (une taille de groupe)."""

    def __init__(self, n: int, J: int, dev, n_pos: int = C.N_POS):
        self.t = torch.zeros(n, dtype=torch.long, device=dev)
        self.cols = torch.full((n, J), -1, dtype=torch.long, device=dev)
        self.fc = torch.zeros(n, C.N_COMPTE, device=dev)
        self.pos = torch.zeros(n, J, n_pos, device=dev)
        self.qui = torch.zeros(n, dtype=torch.bool, device=dev)          # lignes réelles (pas du rembourrage)
        self.jumeau = torch.zeros(n, dtype=torch.bool, device=dev)       # lignes « jumeau au hasard » (examen)
        self.rang = torch.zeros(n, dtype=torch.long, device=dev)         # comptes (journal de trading)
        self.pos_plein = None                                            # position + journal (ce qui est appris)
        self.resume = None                                               # situation (journal de trading)
        self.g = None
        self.sortie = None


class Decideur:
    """Les décisions des comptes qui regardent à cette bougie. Sur la carte graphique, le calcul entier (yeux, niveaux,
    choix) est enregistré une fois par TAILLE DE GROUPE (32, 64, 128... comptes ; le groupe est complété par des
    copies) puis rejoué : des centaines de petites opérations ne coûtent plus qu'un lancement, et seuls ceux qui
    regardent sont calculés. Les poids du cerveau sont lus en place : un apprentissage ou un chargement de poids est vu
    au rejeu suivant. `jumeau_depuis` : les comptes d'indice >= sont des jumeaux au hasard (examen)."""

    def __init__(self, table: Table, net, evaluer: bool, comportement: bool = False, graphe: bool | None = None,
                 jumeau_depuis: int | None = None):
        self.tb, self.net, self.evaluer, self.comp = table, net, evaluer, comportement
        self.graphe = (table.dev.type == "cuda") if graphe is None else graphe
        self.jumeau_depuis = jumeau_depuis
        self.tailles: dict[int, _Entrees] = {}
        cn = table.carnet
        if getattr(net, "n_journal", 0) and (cn is None or not cn.voir):
            raise ValueError("cerveau au journal de trading sur une table sans carnet (journal_trading.equiper)")
        self.voit_journal = cn is not None and cn.voir
        self.n_pos = C.N_POS + (JN.NT if self.voit_journal else 0)

    def _calcul(self, e: _Entrees):
        s = self.tb.vue.structure(e.t, e.cols)
        car, pos, e.resume = yeux_complets(self.tb, s, e.t, e.pos, e.rang, self.net)
        e.pos_plein = pos
        fm = torch.cat([car, pos], -1)
        out = C.politique(self.net, s, fm, e.fc, pos, None, self.evaluer, e.jumeau)
        comp = _vecteur_comportement(out[0], out[5], e.qui & ~e.jumeau) if self.comp else None
        return out, comp, paquet_niveaux(out[5])

    @torch.no_grad()
    def __call__(self, qui: np.ndarray):
        """`qui` : indices des comptes qui regardent. Rend (sortie de politique, compteurs, paquet de niveaux) dont
        les k = len(qui) premières lignes sont les leurs, dans l'ordre de `qui`."""
        k = len(qui)
        taille = max(32, 1 << max(k - 1, 0).bit_length()) if self.graphe else k
        rang = np.r_[qui, np.full(taille - k, qui[0])].astype(np.int64)
        t, cols, fc, pos = self.tb.entrees_np(rang)
        e = self.tailles.get(taille)
        if e is None:
            e = self.tailles[taille] = _Entrees(taille, self.tb.J, self.tb.dev, self.n_pos)
        e.t.copy_(torch.from_numpy(t))
        e.cols.copy_(torch.from_numpy(cols))
        e.fc.copy_(torch.from_numpy(fc))
        e.pos.copy_(torch.from_numpy(pos))
        e.qui.copy_(torch.from_numpy(np.arange(taille) < k))
        jum = (rang >= self.jumeau_depuis) if self.jumeau_depuis is not None else np.zeros(taille, bool)
        e.jumeau.copy_(torch.from_numpy(jum))
        cn = self.tb.carnet
        if cn is not None:
            e.rang.copy_(torch.from_numpy(rang))
        self.dernieres_entrees = e
        if not self.graphe:
            self.net.eval()
            out = self._calcul(e)
            if cn is not None:                      # journal : niveaux choisis et situation, pour le carnet
                cn.retenir(qui, out[0][0], e.resume, k)
            return out
        if e.g is None:
            self.net.eval()
            flux = torch.cuda.Stream()
            flux.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(flux):
                for _ in range(2):
                    self._calcul(e)
            torch.cuda.current_stream().wait_stream(flux)
            e.g = torch.cuda.CUDAGraph()
            with torch.cuda.graph(e.g):
                e.sortie = self._calcul(e)
        e.g.replay()
        if cn is not None:
            cn.retenir(qui, e.sortie[0][0], e.resume, k)
        return e.sortie


# ================================================================================================== l'école
class Lecon:
    """Les comptes d'apprentissage d'un monde : chacun joue des challenges de 2 mois, panier et départ tirés au
    hasard (re-tirés à chaque fin de challenge)."""

    def __init__(self, U, B: int, rng: np.random.Generator):
        r = R()
        self.U, self.rng = U, rng
        self.J = r.ecole.marches_par_compte[1]
        self.table = Table(U, B, self.J)
        self.jmin = r.ecole.marches_par_compte[0]
        jours = r.monde.challenge_jours
        self.dernier_depart = U.instant(U.jusqua - pd.Timedelta(days=jours)) - 1
        self.ok = np.flatnonzero(U.premier < self.dernier_depart - 96 * 5)
        # EXAMEN TOURNANT (tournant.py, arbre de l'or) : départs PERMIS seulement (challenge entier hors des blocs
        # d'examen et de leurs marges) ; absent (HYPERNOVA, tests) : tous les départs, exactement comme avant
        permis = getattr(U, "permis_depart", None)
        self.permis = None if permis is None else np.flatnonzero(permis[:max(self.dernier_depart, 0)])
        if self.permis is not None:
            self.ok = np.asarray([m for m in self.ok if (self.permis >= U.premier[m]).any()], np.int64)
        if not len(self.ok):
            raise ValueError("monde sans marché utilisable")
        # APPRENTISSAGE APPARIÉ (19/10 soir, réglage ecole.apprentissage_apparie, arbre de l'or ; absent = comme avant) :
        # la 1re moitié des comptes joue toujours le marché RÉEL, la 2e moitié le MÊME marché RETOURNÉ ; chaque
        # (marché, départ) tiré d'un côté est rejoué de l'autre côté par le prochain compte de ce côté qui (re)démarre
        # (au départ : comptes i et i + B/2). « Toujours acheter » rapporte ainsi ~zéro au total : seul lire le sens paie.
        self.apparie = None
        if bool(getattr(r.ecole, "apprentissage_apparie", False)):
            self.apparie = self._preparer_paires(B)
        self.table.demarrer(np.ones(B, bool), *self._tirer_comptes(np.arange(B)))

    def _preparer_paires(self, B: int) -> dict:
        if self.J != 1 or self.jmin != 1 or B % 2:
            raise ValueError("apprentissage apparié : un marché par compte et un nombre pair de comptes")
        pos = {v: j for j, v in enumerate(self.U.variantes)}
        partenaire = np.full(self.U.M, -1, np.int64)
        for (nom, mir), j in pos.items():
            partenaire[j] = pos.get((nom, not mir), -1)
        miroir = np.array([bool(m) for _, m in self.U.variantes])
        reels = np.asarray([m for m in self.ok if not miroir[m] and partenaire[m] in set(self.ok.tolist())], np.int64)
        if not len(reels):
            raise ValueError("apprentissage apparié : aucun marché présent dans les deux sens")
        return {"partenaire": partenaire, "reels": reels, "cote": (np.arange(B) >= B // 2).astype(np.int64),
                "attente": ([], [])}

    def _tirer_comptes(self, qui: np.ndarray):
        """(Re)départ des comptes `qui` : comme avant (`_tirer`), ou apparié réel / retourné."""
        if self.apparie is None:
            return self._tirer(len(qui))
        p = self.apparie
        cols = np.full((len(qui), 1), -1, np.int64)
        dep = np.zeros(len(qui), np.int64)
        for k, i in enumerate(qui):
            s = int(p["cote"][i])
            if p["attente"][s]:
                reel, d = p["attente"][s].pop(0)
            else:
                reel = int(self.rng.choice(p["reels"]))
                d = self._un_depart(int(max(self.U.premier[reel], self.U.premier[p["partenaire"][reel]])))
                p["attente"][1 - s].append((reel, d))
            cols[k, 0] = reel if s == 0 else p["partenaire"][reel]
            dep[k] = d
        return cols, dep

    def _un_depart(self, lo: int) -> int:
        if self.permis is None:
            return int(self.rng.integers(lo, max(lo + 1, self.dernier_depart)))
        a = int(np.searchsorted(self.permis, lo))
        if a >= len(self.permis):
            raise ValueError("aucun départ permis hors des blocs d'examen pour ce panier")
        return int(self.permis[self.rng.integers(a, len(self.permis))])

    def _tirer(self, n: int):
        cols = np.full((n, self.J), -1, np.int64)
        dep = np.zeros(n, np.int64)
        for i in range(n):
            k = int(self.rng.integers(self.jmin, self.J + 1))
            ch = self.rng.choice(self.ok, size=min(k, len(self.ok)), replace=False)
            cols[i, :len(ch)] = ch
            lo = int(self.U.premier[ch].max())
            if self.permis is None:
                dep[i] = int(self.rng.integers(lo, max(lo + 1, self.dernier_depart)))
            else:
                a = int(np.searchsorted(self.permis, lo))
                if a >= len(self.permis):
                    raise ValueError("aucun départ permis hors des blocs d'examen pour ce panier")
                dep[i] = int(self.permis[self.rng.integers(a, len(self.permis))])
        return cols, dep

    @torch.no_grad()
    def jouer(self, net, bougies: int) -> tuple[dict, dict]:
        tb = self.table
        c = tb.cpt
        B = tb.B
        dev = tb.dev
        JN.equiper(tb, net, "ecole")                # journal de trading : seulement s'il le voit ou si les logs sont allumés
        if getattr(self, "dec", None) is None or self.dec.net is not net:
            self.dec = Decideur(tb, net, evaluer=True)
        grille = {k: np.zeros((bougies, B), np.float32) for k in ("r", "v", "fin")}
        grille["qui"] = np.zeros((bougies, B), np.bool_)
        mem = []
        lignes = 0
        tb.poseur[:] = -1          # un ordre posé à une leçon précédente n'est plus relié à un regard de celle-ci
        executees = []
        st = {"regards": 0, "ouvertures": 0, "limites": 0, "fermer": 0, "morts": 0, "inactifs": 0, "reussis": 0,
              "en_position": 0.0, "trades_r": [], "risque": 0.0, "fins": 0}
        for k in range(bougies):
            masque = c.actif & ((c.t >= tb.prochain) | tb.reveil)
            qui = np.flatnonzero(masque)
            if len(qui):
                (choix, lp, lp_exec, hasard, valeur, lv), _, paquet = self.dec(qui)
                kq = len(qui)
                sel = lambda x: x[:kq].clone()
                lvq = niveaux_np(paquet[:, :kq])
                pose = lvq["limite"]
                ids = lignes + np.arange(len(qui))
                tb.poseur[qui] = np.where(pose, ids[:, None], tb.poseur[qui])
                tb.appliquer(qui, lvq)
                d = self.dec.dernieres_entrees
                mem.append({"t": sel(d.t), "cols": sel(d.cols), "fc": sel(d.fc), "pos": sel(d.pos_plein), "lp": sel(lp),
                            "lp_exec": sel(lp_exec), "v": sel(valeur), "choix": {kk: sel(vv) for kk, vv in choix.items()}})
                grille["qui"][k, qui] = True
                lignes += len(qui)
                st["regards"] += len(qui)
                ouv = lvq["ouvre"]
                st["ouvertures"] += int(ouv.sum())
                st["limites"] += int(pose.sum())
                st["fermer"] += int(lvq["ferme"].sum())
                st["risque"] += float(lvq["risque_pct"][ouv].sum())
            r, fini, actifs = tb.avancer()
            ev = c.evt
            ex = ((ev & SIM.EXECUTE) != 0) & (tb.poseur >= 0)
            if ex.any():
                b_, j_ = np.nonzero(ex)
                executees.append(np.stack([tb.poseur[b_, j_], j_], 1))
            fin_ordre = ((ev & (SIM.EXECUTE | SIM.EXPIRE)) != 0) | (c.att == 0)
            tb.poseur = np.where(fin_ordre, -1, tb.poseur)
            grille["r"][k] = r
            grille["fin"][k] = fini
            st["morts"] += int((c.mort & ~c.inactif & actifs).sum())
            st["inactifs"] += int((c.inactif & actifs).sum())
            st["reussis"] += int((c.reussi & actifs).sum())
            st["fins"] += int(fini.sum())
            st["en_position"] += float(((c.u != 0).any(1) & actifs).mean())
            rr = c.r_ferme[np.isfinite(c.r_ferme)]
            st["trades_r"] += rr.tolist()
            if fini.any():
                tb.demarrer(fini, *self._tirer_comptes(np.flatnonzero(fini)))
        # ce qu'elle attend de chaque compte à la fin (un regard « pour voir », sans agir)
        v_fin = torch.zeros(B, device=dev)
        tous = np.flatnonzero(c.actif)
        if len(tous):
            (_, _, _, _, val, _), _, _ = self.dec(tous)
            v_fin[torch.as_tensor(tous, device=dev)] = val[:len(tous)].float()
        memoire = {kk: torch.cat([m[kk] for m in mem]) for kk in ("t", "cols", "fc", "pos", "lp", "lp_exec", "v")}
        memoire["choix"] = {kk: torch.cat([m["choix"][kk] for m in mem]) for kk in mem[0]["choix"]}
        g = {k: torch.as_tensor(v, device=dev) for k, v in grille.items()}
        q = g["qui"]
        # les regards ont été rangés bougie par bougie, compte par compte croissant : même ordre que [q]
        g["v"][q] = memoire["v"].float()
        r_ = R().ecole
        adv = avantages_regards(g["r"], g["v"], q, g["fin"], v_fin, r_.gamma, r_.lam)
        memoire["adv"] = adv[q]
        memoire["ret"] = adv[q] + g["v"][q]
        executee = np.zeros((lignes, self.J), bool)
        if executees:
            ij = np.concatenate(executees)
            executee[ij[:, 0], ij[:, 1]] = True
        G = memoire["choix"]["geste"]
        pose = (G == C.ACHAT_L) | (G == C.VENTE_L)
        memoire["sans"] = pose & ~torch.as_tensor(executee, device=dev)
        n = max(st["regards"], 1)
        jours = bougies * B / 96
        tr = np.asarray(st["trades_r"]) if st["trades_r"] else np.zeros(0)
        bilan = {"regards_par_jour": st["regards"] / jours, "ouvertures_par_jour": st["ouvertures"] / jours,
                 "part_limites_pct": 100 * st["limites"] / max(st["ouvertures"], 1),
                 "risque_moyen_pct": st["risque"] / max(st["ouvertures"], 1),
                 "en_position_pct": st["en_position"] / bougies * 100, "morts": st["morts"],
                 "inactifs": st["inactifs"], "reussis": st["reussis"], "fins": st["fins"],
                 "trades": int(len(tr)), "r_moyen": float(tr.mean()) if len(tr) else float("nan"),
                 "recompense_par_jour": float(grille["r"].sum()) / jours}
        return memoire, bilan


def apprendre(net, opt, table: Table, m: dict, epoques: int, paquet: int, coupe: float, curiosite: float,
              plancher: tuple | None = None) -> dict:
    """Renforce les regards qui ont rapporté plus que prévu (PPO). La taille, le stop, la destination... d'un ordre
    limite JAMAIS exécuté ne sont pas appris (ils n'ont rien changé) : seuls le geste, l'entrée et la validité le sont.
    PLANCHER DU HASARD (20/10, réglages ecole.hasard_min / hasard_force de MAGNETAR ; None = comme avant) : quand le
    hasard moyen de ses choix (entropie) passe sous `hasard_min`, une poussée `force x (hasard_min - hasard)` le remonte
    (audit : curiosité effondrée 3,3 -> 1,0, elle n'essayait plus rien)."""
    N = len(m["lp"])
    adv = (m["adv"] - m["adv"].mean()) / (m["adv"].std() + 1e-8)
    sans = m["sans"].float()
    lp_vieux = m["lp"] - (m["lp_exec"] * sans).sum(-1)
    net.train()
    b = {"perte_decision": 0.0, "perte_valeur": 0.0, "hasard": 0.0}
    nb = 0
    dev = m["lp"].device
    for _ in range(epoques):
        ordre = torch.randperm(N, device=dev)
        for d in range(0, N, paquet):
            i = ordre[d:d + paquet]
            s = table.vue.structure(m["t"][i], m["cols"][i])
            fm = torch.cat([table.vue.caracteristiques(s), m["pos"][i]], -1)
            choix = {k: v[i] for k, v in m["choix"].items()}
            _, lp, lp_exec, hasard, valeur, _ = C.politique(net, s, fm, m["fc"][i], m["pos"][i], choix)
            lp = lp - (lp_exec * sans[i]).sum(-1)
            ratio = (lp - lp_vieux[i]).clamp(-20, 20).exp()
            p1, p2 = ratio * adv[i], ratio.clamp(1 - coupe, 1 + coupe) * adv[i]
            perte_dec = -torch.min(p1, p2).mean()
            perte_v = torch.nn.functional.huber_loss(valeur, m["ret"][i])
            perte = perte_dec + 0.5 * perte_v - curiosite * hasard.mean()
            if plancher is not None:
                perte = perte + float(plancher[1]) * torch.relu(float(plancher[0]) - hasard.mean())
            opt.zero_grad(set_to_none=True)
            perte.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
            opt.step()
            b["perte_decision"] += float(perte_dec)
            b["perte_valeur"] += float(perte_v)
            b["hasard"] += float(hasard.mean())
            nb += 1
    return {k: v / max(nb, 1) for k, v in b.items()} | {"regards_appris": N}


# ================================================================================================== l'examen
def paniers_selection() -> list[list[str]]:
    """Paniers fixes de l'examen (tous les marchés de l'école, 4 par panier, par familles). Un arbre spécialisé peut
    les fixer dans ses réglages (selection.paniers : noms de variantes, « _MIROIR » = marché retourné)."""
    from collapsar.ecole.precision import donnees as D
    fixes = getattr(R().selection, "paniers", None)
    if fixes:
        return [list(p) for p in fixes]
    taille = R().selection.taille_panier
    tous = list(D.univers())
    fam = {}
    for m in tous:
        cle = "crypto" if D.source(m) == "binance" else ("minute" if D.source(m) == "minute" else D.famille(m))
        fam.setdefault(cle, []).append(m)
    ordre = ["crypto", "minute", "devise", "indice", "metal", "energie", "obligation"]
    paniers = []
    reste = []
    for f in ordre + [f for f in fam if f not in ordre]:
        L = fam.get(f, [])
        for i in range(0, len(L), taille):
            morceau = L[i:i + taille]
            if len(morceau) == taille or f in ("crypto",):
                paniers.append(morceau)
            else:
                reste += morceau
    for i in range(0, len(reste), taille):
        paniers.append(reste[i:i + taille])
    return paniers


class Examen:
    """Des challenges FIXES (paniers x départs tous les 15 jours) dans un monde ; on y fait jouer deux élèves en même
    temps (candidat et champion), sur les MÊMES fenêtres, avec les mêmes tirages au sort."""

    def __init__(self, U, paniers: list[list[str]], de, jusqua, pas_jours: int):
        self.U = U
        jours = R().monde.challenge_jours
        cols, dep, nom = [], [], []
        d = pd.Timestamp(de)
        dates = []
        while d + pd.Timedelta(days=jours) <= pd.Timestamp(jusqua):
            dates.append(d)
            d += pd.Timedelta(days=pas_jours)
        idx = {c: i for i, c in enumerate(U.cols)}
        J = max(len(p) for p in paniers)
        for ip, p in enumerate(paniers):
            cc = [idx[m] for m in p if m in idx]
            if not cc:
                continue
            for dt in dates:
                t0 = U.instant(dt)
                if t0 < U.premier[cc].max():
                    continue
                cols.append(cc + [-1] * (J - len(cc)))
                dep.append(t0)
                nom.append(ip)
        self.cols = np.asarray(cols, np.int64)
        self.dep = np.asarray(dep, np.int64)
        self.panier = np.asarray(nom)
        self.paniers = paniers
        self.n = len(dep)
        self.J = J
        self.dates = dates
        self.pas_jours = pas_jours

    @torch.no_grad()
    def jouer(self, eleves: list, graine: int) -> list[dict]:
        """Fait jouer chaque élève (l'un après l'autre) sur tous les challenges ; rend un résultat par élève."""
        return [self.jouer_un(net, graine) for net in eleves]

    @torch.no_grad()
    def jouer_un(self, net, graine: int) -> dict:
        """Elle ET son jumeau au hasard (mêmes gestes, sens à pile ou face) sur tous les challenges, dans la même
        partie (comptes 0..n-1 : elle ; n..2n-1 : son jumeau)."""
        U, n1 = self.U, self.n
        n = 2 * n1
        cle = id(net)
        if not hasattr(self, "_tables"):
            self._tables = {}
        if cle not in self._tables:
            tb = Table(U, n, self.J)
            JN.equiper(tb, net, "examen", n1)       # journal de trading : seulement s'il le voit ou si les logs sont allumés
            dec = Decideur(tb, net, evaluer=False, comportement=True, jumeau_depuis=n1)
            self._tables[cle] = (tb, dec, net)
        tb, dec, _ = self._tables[cle]
        tb.demarrer(np.ones(n, bool), np.tile(self.cols, (2, 1)), np.tile(self.dep, 2))
        if tb.carnet is not None:                   # examen : chaque challenge = un nouveau compte, journal vide
            tb.carnet.vider()
        c = tb.cpt
        dev = tb.dev
        sommet = np.full(n, CAPITAL)
        baisse, trades, en_pos, pas_ = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
        fin_v = np.full(n, CAPITAL)
        fin_reussi, fin_mort, fin_inactif = np.zeros(n, bool), np.zeros(n, bool), np.zeros(n, bool)
        fin_jours = np.full(n, np.nan)
        fin_jt = np.zeros(n, np.int64)
        rs = [[] for _ in range(n)]
        from collapsar.ecole.precision import suiveur as SV
        suiv = SV.active()                          # stop suiveur : quels trades l'avaient choisi, quelle unité
        rs_sv = [[] for _ in range(n)]
        comp = torch.zeros(_N_COMP, device=dev)
        # mesure du MOUVEMENT ATTRAPÉ (réglage selection.mesurer_mouvement, éteint par défaut) : voir mouvement_parcouru
        mesure = bool(getattr(R().selection, "mesurer_mouvement", False))
        capte = np.zeros(n)
        fin_t = np.zeros(n, np.int64)
        # mesure des SORTIES (réglage selection.mesurer_sorties, éteint par défaut) : comment chaque trade s'est fermé
        # (à la main, stop, stop suiveur, objectif, objectif 1, forcée) et s'il a été gardé par-dessus une pause > 2 h
        sorties = bool(getattr(R().selection, "mesurer_sorties", False))
        pause_l = getattr(U, "pause_longue", U.derniere)
        garde = np.zeros((n, self.J), bool)
        rs_so = [[] for _ in range(n)]
        # mesure de la TENUE (réglage selection.mesurer_tenue, 19/10, éteint par défaut) : sens de chaque trade (achats /
        # ventes), trades >= 3R, stop réellement remonté (sur TOUS les trades), suiveur après +1R choisi / déclenché
        tenue = bool(getattr(R().selection, "mesurer_tenue", False))
        sens = np.zeros((n, self.J))
        rs_te = [[] for _ in range(n)]
        # OUVERTURES RÉELLEMENT EXÉCUTÉES (réglage selection.mesurer_executions, 20/10, éteint par défaut) : au marché,
        # ordres limites exécutés, ordres limites expirés, séparés des ordres seulement POSÉS (audit : « 91 % par ordre
        # limite » comptait des ordres jamais exécutés)
        execs = bool(getattr(R().selection, "mesurer_executions", False))
        n_marche, n_lim, n_exp = np.zeros(n), np.zeros(n), np.zeros(n)
        appareils = [U.dev] if U.dev.type == "cuda" else []
        with torch.random.fork_rng(devices=appareils):
            torch.manual_seed(graine)
            while c.actif.any():
                masque = c.actif & ((c.t >= tb.prochain) | tb.reveil)
                qui = np.flatnonzero(masque)
                if len(qui):
                    _, vc, paquet = dec(qui)
                    tb.appliquer(qui, niveaux_np(paquet[:, :len(qui)]))
                    comp += vc
                if mesure:                          # sens des positions tenues pendant la bougie qui vient
                    t_av = c.t.copy()
                    col_av = np.clip(c.col, 0, None)
                    s_av = np.sign(c.u) * (c.col >= 0)
                if sorties:                         # positions ouvertes à la dernière bougie avant une longue pause
                    avant_pause = (c.u != 0) & (c.col >= 0) & pause_l[c.t[:, None], np.clip(c.col, 0, None)]
                if tenue:
                    ordu = c.ord_u.copy()           # sens des ordres au marché de ce regard (vidés par le pas)
                r, fini, actifs = tb.avancer()
                if execs:
                    ev_x = c.evt
                    n_marche += ((ev_x & SIM.OUVERTE) != 0).sum(1) * actifs
                    n_lim += ((ev_x & SIM.EXECUTE) != 0).sum(1) * actifs
                    n_exp += ((ev_x & SIM.EXPIRE) != 0).sum(1) * actifs
                if tenue:                           # sens de chaque position à son ouverture
                    ev_ = c.evt
                    sens = np.where((ev_ & SIM.OUVERTE) != 0, np.sign(ordu),
                                    np.where((ev_ & SIM.EXECUTE) != 0, np.sign(c.att_u), sens))
                    for b_, j_ in zip(*np.nonzero(np.isfinite(c.r_ferme) & actifs[:, None])):
                        rs_te[b_].append((float(sens[b_, j_]), int(c.sv_n[b_, j_]) > 0, bool(c.sv_1r[b_, j_]),
                                          bool(c.sv_1r[b_, j_] and c.sv_on[b_, j_]), int(self.panier[b_ % n1])))
                if sorties:
                    nouv = (c.evt & (SIM.OUVERTE | SIM.EXECUTE)) != 0
                    garde = (garde & ~nouv) | (avant_pause & (c.u != 0) & ~nouv)
                    for b_, j_ in zip(*np.nonzero(np.isfinite(c.r_ferme) & actifs[:, None])):
                        e_ = int(c.evt[b_, j_])
                        code = ("main" if e_ & SIM.ELLE else "forcee" if e_ & SIM.FORCEE else
                                ("stop_suiveur" if c.sv_n[b_, j_] > 0 else "stop") if e_ & SIM.STOP else
                                "objectif" if e_ & SIM.DEST else "objectif1" if e_ & SIM.TP1 else "autre")
                        rs_so[b_].append((code, bool(garde[b_, j_] or (avant_pause[b_, j_] and not nouv[b_, j_]))))
                if mesure:
                    dp = U.c[c.t[:, None], col_av] - U.c[t_av[:, None], col_av]
                    capte += np.nan_to_num(s_av * dp).sum(1) * actifs
                v = c.valeur
                sommet = np.where(actifs, np.maximum(sommet, v), sommet)
                baisse = np.where(actifs, np.maximum(baisse, (sommet - v) / sommet), baisse)
                trades += (((c.evt & (SIM.OUVERTE | SIM.EXECUTE)) != 0).sum(1)) * actifs
                en_pos += ((c.u != 0).any(1)) & actifs
                pas_ += actifs
                for b_, j_ in zip(*np.nonzero(np.isfinite(c.r_ferme) & actifs[:, None])):
                    rs[b_].append(float(c.r_ferme[b_, j_]))
                    if suiv:                        # (unité, après l'objectif 1, stop remonté au moins une fois)
                        u_sv = int(c.sv_u[b_, j_])  # (suiveur après +1R : unité + 100, compté à part)
                        rs_sv[b_].append((u_sv + 100 if u_sv >= 0 and c.sv_1r[b_, j_] else u_sv,
                                          bool(c.sv_tp1[b_, j_]), int(c.sv_n[b_, j_]) > 0))
                if fini.any():                      # état final de chaque challenge
                    i = np.flatnonzero(fini)
                    fin_v[i] = v[i]
                    fin_reussi[i] = c.reussi[i]
                    fin_mort[i] = (c.mort & ~c.inactif)[i]
                    fin_inactif[i] = c.inactif[i]
                    fin_jours[i] = (U.t_ns[c.t[i]] - U.t_ns[c.debut[i]]) / 86400e9
                    fin_jt[i] = c.jours_trades[i]
                    fin_t[i] = c.t[i]
                    c.actif[i] = False
        mois = R().monde.challenge_jours / 30.4375
        g = (fin_v / CAPITAL - 1) * 100 / mois
        dd = baisse * 100
        el, ju = slice(0, n1), slice(n1, n)
        note = note_challenges(fin_reussi[el], fin_jours[el], fin_mort[el], fin_inactif[el], g[el], g[ju], dd[el],
                               fin_reussi[ju], fin_jours[ju])
        note_j = note_challenges(fin_reussi[ju], fin_jours[ju], fin_mort[ju], fin_inactif[ju], g[ju], g[ju], dd[ju])
        d_j = g[el] - g[ju]
        if getattr(self, "groupes", None) is not None:     # examen tournant : un bloc (or réel + retourné) = un groupe
            inc_j = incertitude_groupes(d_j, self.groupes)
        else:
            indep = max(1.0, n1 * min(1.0, self.pas_jours / R().monde.challenge_jours))
            inc_j = float(d_j.std(ddof=1) / np.sqrt(indep)) if n1 > 1 else float("nan")
        parcours = mouvement_parcouru(U, np.tile(self.cols, (2, 1)), np.tile(self.dep, 2), fin_t) if mesure else None

        def gros(s, r_all):
            """Part du mouvement attrapée et part des gros trades (demande du chef de projet : les gros mouvements)."""
            if not mesure:
                return {}
            pos = r_all[r_all > 0]
            return {"part_mouvement_pct": float(100 * capte[s].sum() / max(parcours[s].sum(), 1e-12)),
                    "trades_5r_pct": float((r_all >= 5).mean() * 100) if len(r_all) else float("nan"),
                    "trades_10r_pct": float((r_all >= 10).mean() * 100) if len(r_all) else float("nan"),
                    "gains_des_5r_pct": float(100 * pos[pos >= 5].sum() / pos.sum()) if len(pos) else float("nan"),
                    "meilleur_r": float(r_all.max()) if len(r_all) else float("nan")}

        def suiveur_stats(s, r_all):
            """Usage du stop suiveur (% des trades) et R moyen des trades au stop suiveur contre les autres."""
            if not suiv:
                return {}
            sv = [x for b in range(s.start, s.stop) for x in rs_sv[b]]
            u_ = np.asarray([x[0] for x in sv], np.int64)
            avec = u_ >= 0
            moy = lambda a: float(a.mean()) if len(a) else float("nan")
            us = SV.unites()
            return {"suiveur_pct": float(avec.mean() * 100) if len(avec) else float("nan"),
                    "suiveur_trades": int(avec.sum()),
                    "r_moyen_suiveur": moy(r_all[avec]), "r_moyen_sans_suiveur": moy(r_all[~avec]),
                    "suiveur_apres_tp1_pct": float(100 * np.mean([x[1] for x, a in zip(sv, avec) if a])) if avec.any() else float("nan"),
                    "suiveur_remonte_pct": float(100 * np.mean([x[2] for x, a in zip(sv, avec) if a])) if avec.any() else float("nan"),
                    "trades_5r_suiveur_pct": float((r_all[avec] >= 5).mean() * 100) if avec.any() else float("nan"),
                    "suiveur_unite_pct": {u: float(100 * (u_[avec] == i).mean()) if avec.any() else 0.0
                                          for i, u in enumerate(us)}
                    | ({"après +1R": float(100 * (u_[avec] >= 100).mean())} if (u_ >= 100).any() else {})}

        def sorties_stats(s, r_all):
            """Comment ses trades se ferment (% des trades fermés) et part gardée par-dessus une pause > 2 h (week-end)."""
            if not sorties:
                return {}
            so = [x for b in range(s.start, s.stop) for x in rs_so[b]]
            if not so:
                return {"sorties_pct": {}, "gardes_pause_pct": float("nan"), "gardes_pause_r_moyen": float("nan")}
            codes = np.asarray([x[0] for x in so])
            gp = np.asarray([x[1] for x in so], bool)
            return {"sorties_pct": {k: float(100 * (codes == k).mean())
                                    for k in ("main", "stop", "stop_suiveur", "objectif", "objectif1", "forcee", "autre")},
                    "gardes_pause_pct": float(100 * gp.mean()), "gardes_pause_trades": int(gp.sum()),
                    "gardes_pause_r_moyen": float(r_all[gp].mean()) if gp.any() and len(r_all) == len(gp) else float("nan")}

        def tenue_stats(s, r_all):
            """Achats / ventes (R moyen, nombre ; par panier), trades >= 3R / 5R, stop réellement remonté (part de TOUS
            les trades), suiveur après +1R (part des trades, part où +1R a été atteint, R moyen)."""
            if not tenue:
                return {}
            te = [x for b in range(s.start, s.stop) for x in rs_te[b]]
            if not te or len(te) != len(r_all):
                return {"trades_3r_pct": float("nan")}
            sg = np.asarray([x[0] for x in te])
            rem, a1r, on1r = (np.asarray([x[k] for x in te], bool) for k in (1, 2, 3))
            pan = np.asarray([x[4] for x in te])
            moy = lambda a: float(a.mean()) if len(a) else float("nan")
            cotes = {}
            for nom_c, m_ in (("achats", sg > 0), ("ventes", sg < 0)):
                cotes[nom_c] = {"trades": int(m_.sum()), "r_moyen": moy(r_all[m_]),
                                "par_panier": {" + ".join(self.paniers[ip]): {"trades": int((m_ & (pan == ip)).sum()),
                                                                             "r_moyen": moy(r_all[m_ & (pan == ip)])}
                                               for ip in np.unique(self.panier)}}
            return {"trades_3r_pct": float((r_all >= 3).mean() * 100), "trades_5r_tous_pct": float((r_all >= 5).mean() * 100),
                    "stop_remonte_tous_pct": float(rem.mean() * 100), "suiveur_1r_pct": float(a1r.mean() * 100),
                    "suiveur_1r_atteint_pct": float(100 * on1r[a1r].mean()) if a1r.any() else float("nan"),
                    "r_moyen_suiveur_1r": moy(r_all[a1r]), "trades_3r_suiveur_1r_pct":
                        float((r_all[a1r] >= 3).mean() * 100) if a1r.any() else float("nan"), "cotes": cotes}

        def bloc(s, nt):
            r_all = np.asarray([x for b in range(s.start, s.stop) for x in rs[b]])
            jr = fin_jours[s][fin_reussi[s]]
            return {**gros(s, r_all), **suiveur_stats(s, r_all), **sorties_stats(s, r_all), **tenue_stats(s, r_all),
                    "note": float(nt.mean()),
                    "gain_pct_mois": float(g[s].mean()),
                    "reussis_pct": float(fin_reussi[s].mean() * 100),
                    "jours_median_reussite": float(np.median(jr)) if len(jr) else float("nan"),
                    "reussis_en_30_jours_pct": float((fin_reussi[s] & (fin_jours[s] <= 30)).mean() * 100),
                    # contrôle de cohérence (règle FTMO des 4 jours de trading) : doit rester à 0
                    "reussis_sans_4_jours": int((fin_reussi[s] & (fin_jt[s] < 4)).sum()),
                    "murs_pct": float(fin_mort[s].mean() * 100), "inactifs_pct": float(fin_inactif[s].mean() * 100),
                    "baisse_max_moyenne_pct": float(dd[s].mean()), "trades_mois": float((trades[s] / mois).mean()),
                    "en_position_pct": float((en_pos[s] / np.maximum(pas_[s], 1)).mean() * 100),
                    "trades_r": int(len(r_all)), "r_moyen": float(r_all.mean()) if len(r_all) else float("nan"),
                    "gagnants_pct": float((r_all > 0).mean() * 100) if len(r_all) else float("nan"),
                    "gain_moyen_r": float(r_all[r_all > 0].mean()) if (r_all > 0).any() else float("nan"),
                    "perte_moyenne_r": float(r_all[r_all <= 0].mean()) if (r_all <= 0).any() else float("nan")}
        par_panier = {}
        for ip in np.unique(self.panier):
            w = self.panier == ip
            par_panier[" + ".join(self.paniers[ip])] = {"gain_pct_mois": float(g[el][w].mean()),
                                                       "jumeau_pct_mois": float(g[ju][w].mean()),
                                                       "note": float(note[w].mean()),
                                                       "trades_mois": float((trades[el][w] / mois).mean()),
                                                       "reussis_pct": float(fin_reussi[el][w].mean() * 100),
                                                       "murs_pct": float(fin_mort[el][w].mean() * 100)}
            if mesure:
                k = " + ".join(self.paniers[ip])
                par_panier[k]["part_mouvement_pct"] = float(100 * capte[el][w].sum() / max(parcours[el][w].sum(), 1e-12))
                par_panier[k]["jumeau_mouvement_pct"] = float(100 * capte[ju][w].sum() / max(parcours[ju][w].sum(), 1e-12))
        out = {**bloc(el, note), "notes": note.tolist(), "gains_pct_mois": g[el].tolist(),
               "jumeau": bloc(ju, note_j), "avantage_pct_mois": float(d_j.mean()), "avantage_incertitude": inc_j,
               "comportement": _resume_comportement({"v": comp}), "par_panier": par_panier, "challenges": int(n1)}
        if execs:
            cv = comp.cpu().numpy().astype(float)
            nm, nl = float(n_marche[el].sum()), float(n_lim[el].sum())
            nr = int(sum(len(rs[b]) for b in range(n1)))
            out["executions"] = {
                "ouvertures_decidees": float(cv[0]), "ordres_limites_poses": float(cv[1]),
                "ouvertures_marche": int(nm), "ordres_limites_executes": int(nl),
                "ordres_limites_expires": int(n_exp[el].sum()), "sans_resultat": int(nm + nl) - nr,
                "ouvertures_executees_mois": float(((n_marche[el] + n_lim[el]) / mois).mean()),
                "part_limites_executees_pct": float(100 * nl / max(nm + nl, 1)),
                "part_ordres_executes_pct": float(100 * nl / max(cv[1], 1))}
            out["gains_jumeau_pct_mois"] = g[ju].tolist()
            out["r_par_challenge"] = [float(np.sum(rs[b])) for b in range(n1)]
            out["trades_r_par_challenge"] = [len(rs[b]) for b in range(n1)]
        return out


def mouvement_parcouru(U, cols: np.ndarray, debut: np.ndarray, fin: np.ndarray) -> np.ndarray:
    """Le MOUVEMENT DISPONIBLE de chaque challenge [n] : le chemin du prix jour par jour (somme des écarts entre
    clôtures de fin de journée, du départ à la fin du challenge), additionné sur les marchés du panier, en prix.
    Part du mouvement attrapée = (prix gagnés en suivant le sens de ses positions, clôture à clôture de 15 min, quelle
    que soit la taille) / ce chemin. 100 % = elle a suivi chaque journée dans le bon sens ; 0 % = rien ou autant
    contre que pour ; négatif = surtout à contre-sens."""
    jour = np.asarray(U.jour)
    fins = np.flatnonzero(jour[1:] != jour[:-1])            # dernière ligne de chaque journée
    out = np.zeros(len(debut))
    for j in range(cols.shape[1]):
        cj = cols[:, j]
        ok = cj >= 0
        for col in np.unique(cj[ok]):
            w = np.flatnonzero(cj == col)
            c = np.asarray(U.c[:, col], float)
            ce = c[fins]
            S = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(ce)))])          # S[k] = chemin de fins[0] à fins[k]
            a, b = debut[w], np.maximum(fin[w], debut[w])
            if not len(fins):
                out[w] += np.nan_to_num(np.abs(c[b] - c[a]))
                continue
            k0 = np.searchsorted(fins, a, side="right")                      # 1re fin de journée après le départ
            k1 = np.searchsorted(fins, b, side="left")                       # 1re fin de journée >= la fin
            dedans = k1 > k0
            k0c, k1c = np.clip(k0, 0, len(fins) - 1), np.clip(k1 - 1, 0, len(fins) - 1)
            chemin = np.where(dedans, np.abs(ce[k0c] - c[a]) + (S[k1c] - S[k0c]) + np.abs(c[b] - ce[k1c]),
                              np.abs(c[b] - c[a]))
            out[w] += np.nan_to_num(chemin)
    return out


def note_challenges(reussi, jours, mur, inactif, g, g_jumeau, baisse, reussi_j=None, jours_j=None):
    """Note de chaque challenge (reglages.yaml, section note) : la réussite compte d'autant plus qu'elle est RAPIDE,
    un mur coûte très cher, et le gain mensuel ne compte que pour ce qui dépasse le jumeau au hasard.
    GAIN RÉEL (20/10/2026, corrections graves de l'audit de MAGNETAR ; réglage note.gain_reel, absent = comme avant) :
    le terme de gain = min(gain - jumeau, gain) : « perdre moins que le hasard » ne rapporte plus rien (un gain négatif
    compte toujours négatif), un gain positif ne compte que pour ce qui dépasse aussi le jumeau. RÉUSSITE CONTRE LE
    JUMEAU (note.reussite_contre_jumeau, avec reussi_j / jours_j) : le bonus de réussite du jumeau sur le MÊME challenge
    est retiré (une réussite que le hasard aurait eue aussi ne compte pas)."""
    q = R().note
    duree = R().monde.challenge_jours
    vite = np.where(reussi, np.clip((duree - np.nan_to_num(jours, nan=duree)) / duree, 0, 1), 0.0)
    if not getattr(q, "gain_reel", False):
        return (reussi * (q.bonus_reussite + q.bonus_vitesse * vite) - q.punition_mur * mur - q.punition_inactif * inactif
                + np.clip(g - g_jumeau, -q.plafond_gain_mois, q.plafond_gain_mois)
                - 0.5 * np.maximum(baisse - q.baisse_toleree, 0))
    bonus = reussi * (q.bonus_reussite + q.bonus_vitesse * vite)
    if reussi_j is not None and getattr(q, "reussite_contre_jumeau", False):
        vite_j = np.where(reussi_j, np.clip((duree - np.nan_to_num(jours_j, nan=duree)) / duree, 0, 1), 0.0)
        bonus = bonus - reussi_j * (q.bonus_reussite + q.bonus_vitesse * vite_j)
    return (bonus - q.punition_mur * mur - q.punition_inactif * inactif
            + np.clip(np.minimum(g - g_jumeau, g), -q.plafond_gain_mois, q.plafond_gain_mois)
            - 0.5 * np.maximum(baisse - q.baisse_toleree, 0))


_N_COMP = 2 + 3 * 7 + 2 + 6


def _vecteur_comportement(choix: dict, lv: dict, qui: torch.Tensor) -> torch.Tensor:
    """Ce qu'elle choisit quand elle ouvre (pour le rapport : apprend-elle la précision ?), compté pour les comptes
    `qui` [n] : un vecteur de compteurs calculé sur la carte graphique (dans le graphe, sans aller-retour)."""
    NUn = len(UNITES)
    K = R().yeux.zones_par_cote
    nz = NUn * K                                            # places « zone » ; puis 2 sommets / creux par unité
    o = lv["ouvre"] & qui[:, None]
    lim = o & lv["limite"]
    unite = lambda i: torch.where(i < nz, i // K, (i - nz) // 2).clamp(0, NUn - 1)
    oh = lambda i, m: (torch.nn.functional.one_hot(i, NUn) * m[..., None]).sum((0, 1)).float()
    stp, ds = choix["stop"], choix["dest"]
    courir = ds == nz + 2 * NUn
    dr = lv["sig"] * (lv["dest"] - lv["entree"]) / lv["rd"]
    okr = torch.isfinite(dr) & o
    one = lambda x: x.sum().float()[None]
    v = torch.cat([one(o), one(lim), oh((choix["entree"] % nz) // K, lim), oh(unite(stp), o), one((stp < nz) & o),
                   one(courir & o), oh(unite(ds), o & ~courir), one(o & (lv["part"] == 0)),
                   one(o & (lv["part"] == 0.5)), one(o & (lv["part"] == 0.8)), one(lv["risque_pct"] * o),
                   one(torch.where(okr, dr.clamp(max=50), 0.0)), one(okr)])
    return v


def _resume_comportement(a: dict) -> dict:
    if "v" not in a:
        return {"ouvertures": 0.0}
    v = a["v"].cpu().numpy().astype(float)
    NUn = len(UNITES)
    n, nl = max(v[0], 1.0), max(v[1], 1.0)
    i = 2
    ent, i = v[i:i + NUn], i + NUn
    stp, i = v[i:i + NUn], i + NUn
    stop_zone, courir, i = v[i], v[i + 1], i + 2
    dst, i = v[i:i + NUn], i + NUn
    p0, p50, p80, risque, drs, drn = v[i:i + 6]
    return {"ouvertures": v[0], "limites_pct": 100 * v[1] / n, "stop_sur_zone_pct": 100 * stop_zone / n,
            "laisser_courir_pct": 100 * courir / n, "part_0_50_80_pct": [100 * p0 / n, 100 * p50 / n, 100 * p80 / n],
            "risque_moyen_pct": risque / n, "destination_en_r_moyenne": drs / max(drn, 1.0),
            "entree_unite_pct": {u: 100 * ent[k] / nl for k, u in enumerate(UNITES)},
            "stop_unite_pct": {u: 100 * stp[k] / n for k, u in enumerate(UNITES)},
            "dest_unite_pct": {u: 100 * dst[k] / n for k, u in enumerate(UNITES)}}


def incertitude_groupes(d: np.ndarray, groupes) -> float:
    """Incertitude d'une moyenne quand les challenges vont par groupes dépendants (examen tournant : l'or réel et l'or
    retourné d'un même bloc) : écart type des moyennes de groupe / racine du nombre de groupes."""
    d, gr = np.asarray(d, float), np.asarray(groupes)
    m = np.asarray([d[gr == k].mean() for k in np.unique(gr)])
    return float(m.std(ddof=1) / math.sqrt(len(m))) if len(m) > 1 else float("nan")


def comparer(cand: dict, champ: dict, pas_jours: int, groupes=None) -> dict:
    """Différence de note compte par compte (mêmes fenêtres) et son incertitude (fenêtres qui se chevauchent comptées
    comme moins indépendantes, comme juge/note.py ; examen tournant : par blocs, `groupes`)."""
    if (groupes is not None and "notes_selection_blocs" in cand and "notes_selection_blocs" in champ
            and cand.get("blocs") == champ.get("blocs")):
        # note appariée (tournant.py, note_cotes : moins_bon) : chacune sur SON côté le moins bon, bloc par bloc
        d = np.asarray(cand["notes_selection_blocs"]) - np.asarray(champ["notes_selection_blocs"])
        inc = float(d.std(ddof=1) / math.sqrt(len(d))) if len(d) > 1 else float("nan")
        return {"ecart": float(d.mean()), "incertitude": inc, "force": float(d.mean() / inc) if inc and inc > 0 else 0.0}
    d = np.asarray(cand["notes"]) - np.asarray(champ["notes"])
    n = len(d)
    if groupes is not None:
        inc = incertitude_groupes(d, groupes)
    else:
        indep = max(1.0, n * min(1.0, pas_jours / R().monde.challenge_jours))
        inc = float(d.std(ddof=1) / math.sqrt(indep)) if n > 1 else float("nan")
    return {"ecart": float(d.mean()), "incertitude": inc, "force": float(d.mean() / inc) if inc and inc > 0 else 0.0}
