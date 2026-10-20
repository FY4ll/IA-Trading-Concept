"""Le simulateur fidèle : UN SEUL compte FTMO de 100 000 $ pour tous les marchés qu'elle trade.

Des centaines de comptes jouent en même temps (un par partie), chacun à son propre moment de l'histoire.
Elle décide à la clôture d'une bougie ; tout s'exécute pendant la bougie SUIVANTE, dans cet ordre :
1. ses consignes : stop, objectif, ordre à l'avance (posé, déplacé ou annulé) ;
2. fermeture forcée des marchés qui vont faire une pause de plus de 2 h (week-end compris) ;
3. ordre au marché vers la position voulue, à l'ouverture, en payant l'écart (refusé si l'argent engagé dépasserait
   la valeur du compte, comme MT5 ; un stop ou un objectif du mauvais côté du prix est refusé, comme MT5) ;
4. stop et objectif : si les deux sont touchés dans la même bougie, LE STOP d'abord (le pire cas) ; un trou de prix
   à l'ouverture fait sortir au prix d'ouverture ;
5. ordre à l'avance : un ordre limite ne passe que si le prix va VRAIMENT au-delà de son niveau ;
6. frais de nuit au passage de minuit du serveur (triples le mercredi, ou le vendredi pour les indices, les énergies
   et les cryptos, comme FTMO : mains/horloge.py) ;
7. murs FTMO, contrôlés au pire moment de la bougie : valeur < solde de minuit (Prague) - 5 % du capital, ou
   valeur < 90 % du capital = partie perdue ; valeur >= 110 % = challenge réussi, SEULEMENT après au moins 4 jours
   de trading différents (règle FTMO) ;
8. inactivité (règle FTMO, signalée par le chef de projet le 14/10/2026) : 30 jours sans ouvrir de trade = compte
   terminé (partie perdue, comme un mur).
Toutes les positions sont comptées dans le même compte, en dollars (conversion des devises de cotation).
"""
from __future__ import annotations

from dataclasses import dataclass

import torch

from collapsar.mains.horloge import Horloge

CAPITAL = 100_000.0
MUR_JOUR = 0.05
MUR_TOTAL = 0.10
OBJECTIF_FTMO = 0.10
JOURS_TRADING_MIN = 4               # jours (différents) où un trade a été ouvert, pour valider le challenge
INACTIVITE_JOURS = 30               # jours sans ouvrir de trade avant que FTMO termine le compte
N_VUE_MARCHE = 13
N_VUE_COMPTE = 7


@dataclass
class Ordres:
    """Ce qu'elle décide, pour chaque partie [B] et chaque marché [M]. None = rien sur ce point.
    - cible : position voulue, en dollars (signe + achat, - vente ; 0 = tout fermer ; NaN = ne pas toucher) ;
    - stop / objectif : niveau de prix (NaN = ne pas toucher, 0 = retirer) ;
    - attente_type : -1 annuler, 0 ne pas toucher, 1 ordre limite, 2 ordre stop ; avec attente_prix,
      attente_montant (dollars, signé) et attente_duree (en bougies de 15 minutes)."""
    cible: torch.Tensor | None = None
    stop: torch.Tensor | None = None
    objectif: torch.Tensor | None = None
    attente_type: torch.Tensor | None = None
    attente_prix: torch.Tensor | None = None
    attente_montant: torch.Tensor | None = None
    attente_duree: torch.Tensor | None = None


class Comptes:
    def __init__(self, horloge: Horloge, parties: int, capital: float = CAPITAL):
        self.h = horloge
        self.B, self.M = parties, horloge.M
        self.capital = capital
        dev = horloge.appareil
        z = lambda *s: torch.zeros(*s, dtype=torch.float64, device=dev)
        self.u, self.entree = z(self.B, self.M), z(self.B, self.M)          # unités détenues, prix moyen d'entrée
        self.stop = torch.full((self.B, self.M), float("nan"), dtype=torch.float64, device=dev)
        self.objectif = self.stop.clone()
        self.att_type = torch.zeros(self.B, self.M, dtype=torch.int64, device=dev)
        self.att_prix, self.att_montant = z(self.B, self.M), z(self.B, self.M)
        self.att_reste = torch.zeros(self.B, self.M, dtype=torch.int64, device=dev)
        self.solde = torch.full((self.B,), capital, dtype=torch.float64, device=dev)
        self.solde_minuit = self.solde.clone()
        self.jour = torch.zeros(self.B, dtype=torch.int64, device=dev)
        self.t = torch.zeros(self.B, dtype=torch.int64, device=dev)
        self.jours_trades = torch.zeros(self.B, dtype=torch.int64, device=dev)       # jours de trading (FTMO)
        self.jour_dernier_trade = torch.full((self.B,), -1, dtype=torch.int64, device=dev)
        self.jour_debut = torch.zeros(self.B, dtype=torch.int64, device=dev)

    # ---------------------------------------------------------------- départ d'une partie
    def recommencer(self, masque: torch.Tensor, departs: torch.Tensor):
        m = masque.to(self.h.appareil)
        m2 = m[:, None]
        nan = torch.full_like(self.stop, float("nan"))
        self.u = torch.where(m2, 0.0, self.u)
        self.entree = torch.where(m2, 0.0, self.entree)
        self.stop = torch.where(m2, nan, self.stop)
        self.objectif = torch.where(m2, nan, self.objectif)
        self.att_type = torch.where(m2, 0, self.att_type)
        self.att_reste = torch.where(m2, 0, self.att_reste)
        self.solde = torch.where(m, self.capital, self.solde)
        self.solde_minuit = torch.where(m, self.capital, self.solde_minuit)
        self.t = torch.where(m, departs.to(self.t), self.t)
        self.jour = torch.where(m, self.h.jour[self.t], self.jour)
        self.jour_debut = torch.where(m, self.jour, self.jour_debut)
        self.jours_trades = torch.where(m, 0, self.jours_trades)
        self.jour_dernier_trade = torch.where(m, -1, self.jour_dernier_trade)

    def jours_sans_trade(self) -> torch.Tensor:
        """Jours depuis le dernier trade ouvert (ou depuis le début du compte) : à 30, FTMO termine le compte."""
        return self.jour - torch.maximum(self.jour_debut, self.jour_dernier_trade)

    # ---------------------------------------------------------------- outils
    def _prix(self, t):
        h = self.h
        return h.o[t], h.h[t], h.l[t], h.c[t], h.fx[t], h.ouvert[t]

    def valeur(self, prix: torch.Tensor, fx: torch.Tensor) -> torch.Tensor:
        return self.solde + (self.u * (prix - self.entree) * fx).sum(1)

    def _executer(self, masque, du, prix, fx):
        """Achète (du > 0) ou vend (du < 0) des unités au prix donné (écart déjà compris dans `prix`)."""
        du = torch.where(masque, du, torch.zeros_like(du))
        u, e = self.u, self.entree
        nouveau = u + du
        meme_sens = (u * du) >= 0
        ferme = torch.where(meme_sens, torch.zeros_like(u), torch.minimum(du.abs(), u.abs()) * torch.sign(u))
        self.realise = self.realise + ferme * (prix - e) * fx            # [B, M] : gain réalisé (avant frais)
        self.solde = self.solde + (ferme * (prix - e) * fx).sum(1)
        retourne = (~meme_sens) & (nouveau * u < 0)
        moyen = torch.where(nouveau != 0, (u * e + du * prix) / torch.where(nouveau != 0, nouveau, 1.0), 0.0)
        e2 = torch.where(meme_sens, moyen, torch.where(retourne, prix, torch.where(nouveau == 0, 0.0, e)))
        a_change = masque & (du != 0)
        self.u = torch.where(a_change, nouveau, u)
        self.entree = torch.where(a_change, e2, e)
        vide = a_change & ((nouveau == 0) | retourne)          # plus de position (ou sens inversé) : stops retirés
        nan = torch.full_like(self.stop, float("nan"))
        self.stop = torch.where(vide, nan, self.stop)
        self.objectif = torch.where(vide, nan, self.objectif)
        return (du.abs() * prix * fx * self.h.demi_ecart / (1 + self.h.demi_ecart)).where(a_change, 0).sum(1)

    def _au_lot(self, du, o, fx, cible_zero=None):
        """Arrondit au pas de lot de MT5 (0,01 lot). Fermer tout reste exact ; un reste plus petit qu'un pas est fermé."""
        h = self.h
        pas = torch.where(h.pas_unites > 0, h.pas_unites, h.pas_dollars / (o * fx))
        arrondi = torch.round(du / pas) * pas
        arrondi = torch.where(arrondi.abs() < h.min_unites, torch.zeros_like(arrondi), arrondi)   # sous le minimum
        reste_minuscule = (self.u + arrondi).abs() < torch.maximum(pas * 0.5, h.min_unites)
        arrondi = torch.where(reste_minuscule & (self.u != 0), -self.u, arrondi)
        if cible_zero is not None:
            arrondi = torch.where(cible_zero, -self.u, arrondi)
        return arrondi

    def _marge_ok(self, u_apres, o, fx, valeur):
        engage = (u_apres.abs() * o * fx / self.h.levier).sum(1)
        return engage <= valeur

    # ---------------------------------------------------------------- une bougie
    def pas(self, ordres: Ordres) -> dict:
        h = self.h
        n = torch.clamp(self.t + 1, max=h.T - 1)
        o, hi, lo, c, fx, ouvert = self._prix(n)
        s = h.demi_ecart[None, :]
        nan = torch.full_like(self.stop, float("nan"))
        refus = torch.zeros(self.B, dtype=torch.int64, device=h.appareil)
        self.realise = torch.zeros_like(self.u)

        # nouveau jour FTMO (minuit à Prague) : le solde de minuit sert de base au mur du jour
        nouveau_jour = h.jour[n] != self.jour
        self.solde_minuit = torch.where(nouveau_jour, self.solde, self.solde_minuit)
        self.jour = h.jour[n]

        # 1. consignes (un stop / objectif NOUVEAU sera vérifié après l'ordre au marché ; un ancien, déjà accepté,
        #    reste valable même si un trou de prix le fait passer de l'autre côté : il se déclenche)
        faux = torch.zeros_like(self.u, dtype=torch.bool)
        stop_neuf = (~torch.isnan(ordres.stop) & (ordres.stop != 0)) if ordres.stop is not None else faux
        obj_neuf = (~torch.isnan(ordres.objectif) & (ordres.objectif != 0)) if ordres.objectif is not None else faux
        if ordres.stop is not None:
            self.stop = torch.where(torch.isnan(ordres.stop), self.stop, torch.where(ordres.stop == 0, nan, ordres.stop))
        if ordres.objectif is not None:
            self.objectif = torch.where(torch.isnan(ordres.objectif), self.objectif,
                                        torch.where(ordres.objectif == 0, nan, ordres.objectif))
        if ordres.attente_type is not None:
            type_ = ordres.attente_type.to(torch.int64)
            pose = type_ > 0
            annule = type_ < 0
            self.att_type = torch.where(pose, type_, torch.where(annule, 0, self.att_type))
            self.att_prix = torch.where(pose, ordres.attente_prix, self.att_prix)
            self.att_montant = torch.where(pose, ordres.attente_montant, self.att_montant)
            self.att_reste = torch.where(pose, ordres.attente_duree.to(torch.int64), self.att_reste)

        # 2. fermeture forcée avant une pause de plus de 2 h : position à zéro, ordre à l'avance annulé
        derniere = h.derniere[n]
        cible = ordres.cible if ordres.cible is not None else nan
        cible = torch.where(derniere & (self.u != 0), torch.zeros_like(cible), torch.where(derniere, nan, cible))
        self.att_type = torch.where(derniere, 0, self.att_type)
        forcees_marche = derniere & (self.u != 0)
        forcees = forcees_marche.sum(1)

        # 3. ordre au marché à l'ouverture
        voulu = ouvert & ~torch.isnan(cible)
        du = torch.where(voulu, torch.nan_to_num(cible) / (o * fx) - self.u, torch.zeros_like(self.u))
        du = self._au_lot(du, o, fx, cible_zero=voulu & (cible == 0))
        voulu = voulu & (du != 0)
        valeur_ouverture = self.valeur(o, fx)
        grandit = voulu & ((self.u + du).abs() > self.u.abs())
        if grandit.any():
            ok = self._marge_ok(self.u + du, o, fx, valeur_ouverture)
            refus += (grandit & ~ok[:, None]).sum(1)
            du = torch.where(grandit & ~ok[:, None], torch.zeros_like(du), du)
        prix = o * (1 + s * torch.sign(du))
        apres = self.u + du
        ouvre = voulu & (du != 0) & ((apres.abs() > self.u.abs()) | (apres * self.u < 0))   # un trade OUVERT
        frais = self._executer(voulu, du, prix, fx)
        # un stop / objectif posé avec un retournement (achat -> vente) vaut pour la NOUVELLE position (14/10 : il
        # était effacé avec ceux de l'ancienne)
        if ordres.stop is not None:
            self.stop = torch.where(stop_neuf, ordres.stop, self.stop)
        if ordres.objectif is not None:
            self.objectif = torch.where(obj_neuf, ordres.objectif, self.objectif)

        # stop / objectif du mauvais côté du prix : refusés (comme MT5)
        vente_o, achat_o = o * (1 - s), o * (1 + s)
        long, court = self.u > 0, self.u < 0
        mauvais_stop = stop_neuf & ((long & (self.stop >= vente_o)) | (court & (self.stop <= achat_o)) | ~ouvert)
        mauvais_obj = obj_neuf & ((long & (self.objectif <= vente_o)) | (court & (self.objectif >= achat_o)) | ~ouvert)
        refus += ((mauvais_stop & (self.u != 0)).sum(1) + (mauvais_obj & (self.u != 0)).sum(1))
        sans_position = self.u == 0
        self.stop = torch.where(mauvais_stop | sans_position, nan, self.stop)
        self.objectif = torch.where(mauvais_obj | sans_position, nan, self.objectif)

        # 4. stop et objectif (le stop d'abord si les deux sont touchés)
        long, court = self.u > 0, self.u < 0
        sl, tp = self.stop, self.objectif
        a_sl, a_tp = ~torch.isnan(sl), ~torch.isnan(tp)
        sl_long = long & a_sl & (lo * (1 - s) <= sl)
        tp_long = long & a_tp & (hi * (1 - s) >= tp)
        sl_court = court & a_sl & (hi * (1 + s) >= sl)
        tp_court = court & a_tp & (lo * (1 + s) <= tp)
        touche_sl = ouvert & (sl_long | sl_court)
        touche_tp = ouvert & (tp_long | tp_court) & ~touche_sl
        px_sl = torch.where(long, torch.minimum(torch.nan_to_num(sl), vente_o), torch.maximum(torch.nan_to_num(sl), achat_o))
        px_tp = torch.where(long, torch.maximum(torch.nan_to_num(tp), vente_o), torch.minimum(torch.nan_to_num(tp), achat_o))
        sortie = touche_sl | touche_tp
        frais += self._executer(sortie, -self.u, torch.where(touche_sl, px_sl, px_tp), fx)

        # 5. ordre à l'avance
        actif = (self.att_type > 0) & ouvert
        P, montant = self.att_prix, self.att_montant
        achat = montant > 0
        limite, arret = self.att_type == 1, self.att_type == 2
        passe = actif & (
            (limite & achat & (lo * (1 + s) < P)) | (limite & ~achat & (hi * (1 - s) > P))
            | (arret & achat & (hi * (1 + s) >= P)) | (arret & ~achat & (lo * (1 - s) <= P)))
        px_att = torch.where(limite & achat, torch.minimum(P, achat_o),
                 torch.where(limite & ~achat, torch.maximum(P, vente_o),
                 torch.where(arret & achat, torch.maximum(P, achat_o), torch.minimum(P, vente_o))))
        du_att = torch.where(passe, montant / (torch.where(P > 0, P, 1.0) * fx), torch.zeros_like(P))
        du_att = torch.where(passe, self._au_lot(du_att, o, fx), du_att)
        if passe.any():
            ok = self._marge_ok(self.u + du_att, o, fx, self.valeur(o, fx))
            refus += (passe & ~ok[:, None]).sum(1)
            passe = passe & ok[:, None]
        frais += self._executer(passe, du_att, px_att, fx)
        # jours de trading (FTMO) : un jour où au moins un trade a été ouvert
        actif = (ouvre | (passe & (du_att != 0))).any(1)
        self.jours_trades = self.jours_trades + (actif & (self.jour_dernier_trade != self.jour)).long()
        self.jour_dernier_trade = torch.where(actif, self.jour, self.jour_dernier_trade)
        self.att_reste = torch.where(self.att_type > 0, self.att_reste - 1, self.att_reste)
        self.att_type = torch.where(passe | (self.att_reste <= 0), 0, self.att_type)

        # 6. frais de nuit
        na, nv = (h.nuit_achat[n], h.nuit_vente[n]) if h.nuit_achat.dim() == 2 else (h.nuit_achat, h.nuit_vente)
        taux = torch.where(self.u > 0, na, nv)                     # frais de nuit de l'époque (mains/nuit.py)
        if hasattr(h, "nuits"):          # 16/10 : nuit triple du mercredi ou du vendredi selon le marché (FTMO)
            nuit = (self.u.abs() * o * fx * taux / 360 * h.nuits(n)).sum(1)
        else:
            nuit = (self.u.abs() * o * fx * taux / 360).sum(1) * h.nuit[n]
        self.solde = self.solde - nuit

        # 7. murs FTMO au pire moment de la bougie
        pire_prix = torch.where(self.u > 0, lo, hi)
        pire = self.valeur(pire_prix, fx)
        valeur = self.valeur(c, fx)
        mur = (pire < self.solde_minuit - MUR_JOUR * self.capital) | (pire < (1 - MUR_TOTAL) * self.capital)
        inactif = ~mur & (self.jours_sans_trade() >= INACTIVITE_JOURS)
        mort = mur | inactif
        reussi = ~mort & (valeur >= (1 + OBJECTIF_FTMO) * self.capital) & (self.jours_trades >= JOURS_TRADING_MIN)
        if mort.any():
            pire = torch.where(inactif, valeur, pire)          # compte terminé pour inactivité : au prix du moment
            self.solde = torch.where(mort, pire, self.solde)
            self.u = torch.where(mort[:, None], torch.zeros_like(self.u), self.u)
            self.entree = torch.where(mort[:, None], torch.zeros_like(self.u), self.entree)
            valeur = torch.where(mort, pire, valeur)
        fin_histoire = n >= h.T - 1
        self.t = n
        return {"valeur": valeur, "mort": mort, "inactif": inactif, "reussi": reussi, "fin_histoire": fin_histoire, "frais": frais,
                "nuit": nuit, "forcees": forcees, "refus": refus,
                "fermees_sans_ordre": sortie | forcees_marche,     # [B, M] : stop, objectif ou pause du marché
                "attente_executee": passe,
                "realise": self.realise}                            # [B, M] : gain réalisé à cette bougie, avant frais                          # [B, M] : un ordre à l'avance s'est exécuté

    # ---------------------------------------------------------------- ce qu'elle voit de son compte
    def vue(self) -> tuple[torch.Tensor, torch.Tensor]:
        """[B, M, 13] par marché et [B, 7] pour le compte : elle voit TOUTES ses positions en même temps."""
        h, t = self.h, self.t
        c, fx = h.c[t], h.fx[t]
        valeur = self.valeur(c, fx).clamp(min=1.0)
        v = valeur[:, None]
        expo = self.u * c * fx / v
        latent = self.u * (c - self.entree) * fx / v * 100
        dist = lambda niveau: torch.nan_to_num((niveau - c) / c * 100)
        a_stop, a_obj = (~torch.isnan(self.stop)).double(), (~torch.isnan(self.objectif)).double()
        att = self.att_type > 0
        marche = torch.stack([
            expo / 10, latent, dist(self.stop), a_stop, dist(self.objectif), a_obj,
            (self.att_type == 1).double(), (self.att_type == 2).double(),
            torch.where(att, (self.att_prix - c) / c * 100, torch.zeros_like(c)),
            torch.where(att, self.att_montant / v / 10, torch.zeros_like(c)),
            torch.where(att, self.att_reste.double() / 96, torch.zeros_like(c)),
            h.ouvert[t].double(), h.heures_pause[t].double() / 48], -1)
        engage = (self.u.abs() * c * fx / h.levier).sum(1)
        cap = self.capital
        compte = torch.stack([
            (valeur / cap - 1) * 10, (valeur - self.solde_minuit) / cap * 10,
            (valeur - (self.solde_minuit - MUR_JOUR * cap)) / cap * 10, (valeur - (1 - MUR_TOTAL) * cap) / cap * 10,
            engage / valeur, expo.abs().sum(1) / 10, (self.u != 0).double().mean(1)], -1)
        return marche.float(), compte.float()
