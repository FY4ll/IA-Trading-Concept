"""La nouvelle école : « elle choisit quand revenir regarder » (validée par le chef de projet le 14/10/2026).

Le trader humain numérique (cerveau/humain.py) joue des centaines de comptes FTMO de 100 000 $ en même temps, chacun à
son propre moment de l'histoire, sur le simulateur fidèle (mains/simulateur.py). Bougie de 15 minutes par bougie :
- un compte dont c'est l'heure du REGARD (choisie par elle au regard précédent) ou qui est RÉVEILLÉ la voit décider :
  un geste par marché (garder / revoir ses protections / changer de position) et l'heure de son prochain regard ;
- les autres comptes vivent seuls : stops, objectifs, fermeture avant le week-end et murs FTMO restent actifs ;
- RÉVEILS (comme les alertes du téléphone d'un trader) : une position fermée sans elle (stop, objectif, fermeture du
  week-end) ou un compte qui passe à mi-chemin d'un mur FTMO.
Récompense : l'argent du compte (en % du capital, frais réels compris) entre deux regards ; une perte près d'un mur fait
plus mal (« sentir le danger », décision du 13/10) ; toucher un mur = -20 ; réussir le +10 % = +5. Ne rien faire ne
rapporte rien : on ne réussit jamais un challenge sans trader.
Méthode : essais et erreurs (« PPO »), chaque regard jugé sur ce qu'il a rapporté jusqu'au regard suivant, l'avenir
plus lointain compté un peu moins (horizon ~1 mois).

Les années (pour ne jamais se mentir) : elle apprend sur 2010 -> 2019, elle est contrôlée sur 2020 -> 2022 (jamais
apprises) et sur 2016 -> 2019 (témoin du par cœur : briller ici et pas sur 2020-2022 = elle récite). Le juge
(2023-09/2025) et les 12 mois cachés ne sont jamais chargés ici (donnees/marches.py rend seulement l'avant-2023).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch

from collapsar.cerveau.humain import (ACHETER, ATT_MAX, ATT_MIN, ATTENDRE, CHANGER, FERMER, PROTEGER, VENDRE,
                                     TraderHumain)
from collapsar.donnees import marches as dm
from collapsar.ecole.classe import BONUS_REUSSITE, PUNITION_MUR, danger, ressenti
from collapsar.mains.fiches import MIROIR, fiche, taux_vers_dollar
from collapsar.mains.horloge import Horloge
from collapsar.mains.simulateur import CAPITAL, INACTIVITE_JOURS, JOURS_TRADING_MIN, Comptes, Ordres
from collapsar.yeux.faits import calendrier, seances
from collapsar.yeux.graphique import Graphique

APPRENDRE_DE = pd.Timestamp("2010-02-01")          # un mois d'historique avant la première partie
APPRENDRE_JUSQUA = pd.Timestamp("2020-01-01")
CONTROLE_DE, CONTROLE_JUSQUA = pd.Timestamp("2020-01-01"), pd.Timestamp("2023-01-01")
TEMOIN_DE, TEMOIN_JUSQUA = pd.Timestamp("2016-01-01"), pd.Timestamp("2020-01-01")
UN_MOIS = 2100                                     # bougies de 15 minutes dans un mois de marché (environ)
# une partie = 2 mois (14/10) : sur 1 mois, la règle FTMO d'inactivité (30 jours sans trade) ne jouait presque jamais
DUREE_PARTIE = 2 * UN_MOIS
GAMMA = 0.9995                                     # par bougie : l'argent d'ici ~1 mois compte presque autant qu'aujourd'hui
SEUIL_REVEIL = 0.5                                 # mi-chemin d'un mur FTMO
SEMAINE = 480.0                                    # bougies dans 5 jours de marché
# 15/10 (chef de projet : « sinon elle passerait à côté d'opportunités ») : réveillée aussi par ses ALERTES de prix,
# par un GROS MOUVEMENT (une bougie du jour entière depuis son dernier regard) et 15 min avant une ANNONCE importante
GROS_MOUVEMENT = 1.0
AVANT_ANNONCE_H = 0.25
RAISONS = {1: "une position fermée sans moi", 2: "le compte s'approche d'un mur", 3: "une alerte de prix",
           4: "un gros mouvement", 5: "une annonce importante dans 15 min", 6: "le chef de projet"}


def donnees_regard(marches: list[str], jusqua: pd.Timestamp = dm.FIN_APPRENTISSAGE) -> dict[str, pd.DataFrame]:
    """Les marchés (un nom en « _MIROIR » = le marché retourné) + ceux qui convertissent leurs devises en dollars.
    `jusqua` : avant 2023 par défaut (apprentissage) ; le juge seul va jusqu'à la fin de l'examen (09/2025)."""
    def charger(m):
        return (dm.miroir(dm.charger(m[:-len(MIROIR)], jusqua)) if m.endswith(MIROIR) else dm.charger(m, jusqua))
    donnees = {m: charger(m) for m in marches}
    for m in marches:
        source, _ = taux_vers_dollar(fiche(m).cotation)
        if source and source not in donnees:
            donnees[source] = dm.charger(source, jusqua)
    return donnees


class Etat:
    """Des comptes et, pour chacun, l'état de ses regards."""

    def __init__(self, h: Horloge, parties: int):
        dev = h.appareil
        self.comptes = Comptes(h, parties)
        self.prochain = torch.zeros(parties, dtype=torch.int64, device=dev)       # instant de son prochain regard
        self.dernier = torch.zeros(parties, dtype=torch.int64, device=dev)        # instant de son dernier regard
        self.debut = torch.zeros(parties, dtype=torch.int64, device=dev)
        self.ouverture = torch.full((parties, h.M), -1, dtype=torch.int64, device=dev)   # depuis quand elle tient
        self.danger_vu = torch.zeros(parties, device=dev)                         # le danger à son dernier regard
        self.reveil = torch.ones(parties, dtype=torch.bool, device=dev)
        # sa mémoire d'expérience (« mes lectures marchent-elles en ce moment ? ») : résultat moyen par jour du
        # compte sur ~5 et ~20 jours de marché
        self.valeur_prec = torch.full((parties,), CAPITAL, dtype=torch.float64, device=dev)
        self.memoire = torch.zeros(parties, 2, device=dev)
        # 15/10 : le prix et l'agitation vus au dernier regard, ses alertes de prix, et pourquoi on l'a réveillée
        nan = torch.full((parties, h.M), float("nan"), dtype=torch.float64, device=dev)
        self.prix_vu, self.alerte_haut, self.alerte_bas = nan.clone(), nan.clone(), nan.clone()
        self.taille_vue = torch.zeros(parties, h.M, dtype=torch.float64, device=dev)
        self.raison = torch.zeros(parties, dtype=torch.int64, device=dev)

    def recommencer(self, masque: torch.Tensor, departs: torch.Tensor):
        self.comptes.recommencer(masque, departs)
        for nom in ("prochain", "dernier", "debut"):
            setattr(self, nom, torch.where(masque, departs, getattr(self, nom)))
        self.ouverture = torch.where(masque[:, None], -1, self.ouverture)
        self.danger_vu = torch.where(masque, 0.0, self.danger_vu)
        self.reveil = self.reveil | masque
        self.valeur_prec = torch.where(masque, CAPITAL, self.valeur_prec)
        self.memoire = torch.where(masque[:, None], 0.0, self.memoire)
        for nom in ("prix_vu", "alerte_haut", "alerte_bas"):
            setattr(self, nom, torch.where(masque[:, None], float("nan"), getattr(self, nom)))
        self.raison = torch.where(masque, 0, self.raison)


@dataclass
class Regard:
    """Ce qu'elle a vu et décidé à un regard (seulement pour les comptes qui regardaient)."""
    qui: torch.Tensor          # [B] : qui regardait
    idx: torch.Tensor          # [n, M] : lignes des graphiques
    vm: torch.Tensor           # [n, M, N]
    vc: torch.Tensor           # [n, N]
    choix: dict                # ses choix [n, M] ou [n]
    lp: torch.Tensor           # [n]
    valeur: torch.Tensor       # [n]
    taille_jour: torch.Tensor  # [n, M] : taille d'une bougie du jour, en part du prix
    lp_taille_attente: torch.Tensor | None = None   # [n, M] : part « taille » des ordres à l'avance posés


class ClasseRegard:
    def __init__(self, marches: list[str], appareil="cpu", donnees=None, annonces=None, fiches=None):
        """`fiches` : fiches des marchés inventés (école des mille mondes)."""
        donnees = donnees or donnees_regard(marches)
        self.dev = torch.device(appareil)
        self.marches = list(marches)
        # vrais marchés : frais de nuit de chaque époque (mains/nuit.py) ; mondes inventés : ceux de leur fiche
        self.h = Horloge(donnees, self.marches, appareil, fiches, nuit_historique=fiches is None)
        self.g = Graphique({m: donnees[m] for m in self.marches}, appareil)
        self.offset = torch.tensor(self.g.debut_marche[:len(self.marches)], device=self.dev)
        self.seances = torch.from_numpy(seances(self.h.temps)).to(self.dev)
        self.cal = torch.from_numpy(calendrier(self.h.temps, self.marches, annonces)).to(self.dev)
        self.i_jour = dm.ECHELLES.index("jour")

    def instant(self, date: pd.Timestamp) -> int:
        return int(np.searchsorted(self.h.temps.values, pd.Timestamp(date).to_datetime64()))

    # ------------------------------------------------------------------ ce qu'elle voit
    def voir(self, e: Etat, qui: torch.Tensor):
        vm, vc = e.comptes.vue()
        t = e.comptes.t
        idx = self.offset[None, :] + self.h.local[t].clamp(min=0)
        tenue = torch.where(e.ouverture >= 0, (t[:, None] - e.ouverture).float() / SEMAINE, torch.zeros_like(vm[..., 0]))
        depuis = ((t - e.dernier).float() / SEMAINE)[:, None]
        sans_trade = (e.comptes.jours_sans_trade().float() / INACTIVITE_JOURS)[:, None]
        jours_trading = (e.comptes.jours_trades.clamp(max=JOURS_TRADING_MIN).float() / JOURS_TRADING_MIN)[:, None]
        vm = torch.cat([vm, self.cal[t], tenue[..., None]], -1)
        vc = torch.cat([vc, self.seances[t], depuis, sans_trade, jours_trading, e.memoire * 10], -1)
        return idx[qui], vm[qui], vc[qui]

    def sortie(self, agent: TraderHumain, idx, vm, vc):
        f, x = self.g.voir(idx.reshape(-1))
        n, m = idx.shape
        taille = torch.exp(x[:, self.i_jour] * 3 - 6).reshape(n, m)
        return agent(f, x, vm, vc), taille

    def decider(self, agent: TraderHumain, e: Etat, qui: torch.Tensor, sur: bool = False) -> Regard:
        idx, vm, vc = self.voir(e, qui)
        sortie, taille = self.sortie(agent, idx, vm, vc)
        lois = agent.lois(sortie)
        choix = agent.choisir(lois, sur)
        return Regard(qui, idx, vm, vc, choix, agent.log_prob(lois, choix), sortie["valeur"], taille,
                      agent.log_prob_taille_attente(lois, choix))

    # ------------------------------------------------------------------ de ses choix aux ordres
    def ordres(self, e: Etat, rg: Regard | None) -> Ordres:
        c = e.comptes
        nan = torch.full_like(c.u, float("nan"))
        if rg is None or not rg.qui.any():
            return Ordres()
        q = rg.qui
        a = rg.choix
        prix, fx = self.h.c[c.t], self.h.fx[c.t]
        valeur = c.valeur(prix, fx)[q]
        geste = a["geste"]
        voulue = TraderHumain.position_voulue(a["sens"], a["taille"].double(), valeur, rg.taille_jour.double())
        cible_q = torch.where(geste == CHANGER, voulue, float("nan"))          # ordre au marché
        sens = torch.where(geste == CHANGER, torch.sign(voulue), torch.sign(c.u[q]))
        p = prix[q]
        d_stop = TraderHumain.distance(a["stop_dist"], rg.taille_jour).double()
        d_obj = TraderHumain.distance(a["obj_dist"], rg.taille_jour).double()
        stop_q = torch.where(a["stop_on"] > 0.5, p * (1 - sens * d_stop), 0.0)        # 0 = pas de stop
        obj_q = torch.where(a["obj_on"] > 0.5, p * (1 + sens * d_obj), 0.0)
        touche = ((geste == PROTEGER) | (geste == CHANGER)) & (sens != 0)
        cible, stop, objectif = nan.clone(), nan.clone(), nan.clone()
        cible[q] = cible_q
        stop[q] = torch.where(touche, stop_q, float("nan"))
        objectif[q] = torch.where(touche, obj_q, float("nan"))
        # ordres à l'avance (15/10) : limite = meilleur prix (acheter plus bas / vendre plus haut), stop = cassure
        attend = geste == ATTENDRE
        annule = attend & (a["sens"] == FERMER)
        pose = attend & ~annule & (voulue != 0)
        d_att = torch.exp(a["att_dist"].double().clamp(ATT_MIN, ATT_MAX)) * rg.taille_jour.double()
        limite = a["att_limite"] > 0.5
        signe = torch.sign(voulue)
        prix_att = torch.where(limite, p * (1 - signe * d_att), p * (1 + signe * d_att))
        z = torch.zeros_like(c.u)
        att_type, att_prix, att_montant, att_duree = z.clone().long(), z.clone(), z.clone(), z.clone().long()
        att_type[q] = torch.where(pose, torch.where(limite, 1, 2), torch.where(annule, -1, 0))
        att_prix[q] = torch.where(pose, prix_att, 0.0)
        att_montant[q] = torch.where(pose, voulue, 0.0)
        att_duree[q] = torch.where(pose, TraderHumain.duree_attente(a["att_duree"]), 0)
        return Ordres(cible=cible, stop=stop, objectif=objectif, attente_type=att_type, attente_prix=att_prix,
                      attente_montant=att_montant, attente_duree=att_duree)

    def noter_regard(self, e: Etat, rg: Regard):
        """Après un regard : l'heure du prochain, et le danger qu'elle a vu (pour le réveil à mi-chemin d'un mur)."""
        q = rg.qui
        t = e.comptes.t
        delai = TraderHumain.delai(rg.choix["regard"])
        e.prochain = e.prochain.clone()
        e.prochain[q] = t[q] + delai
        e.dernier = torch.where(q, t, e.dernier)
        c = e.comptes
        d = danger(c.valeur(self.h.c[t], self.h.fx[t]), c.solde_minuit).float()
        e.danger_vu = torch.where(q, d, e.danger_vu)
        e.reveil = e.reveil & ~q
        e.raison = torch.where(q, 0, e.raison)
        p = self.h.c[t][q]
        e.prix_vu, e.taille_vue = e.prix_vu.clone(), e.taille_vue.clone()
        e.prix_vu[q], e.taille_vue[q] = p, rg.taille_jour.double()
        if "alerte" in rg.choix:                       # ses alertes de prix (au-dessus, au-dessous)
            dist = TraderHumain.distance_alerte(rg.choix["alerte"].double(), rg.taille_jour.double()[..., None])
            e.alerte_haut, e.alerte_bas = e.alerte_haut.clone(), e.alerte_bas.clone()
            e.alerte_haut[q], e.alerte_bas[q] = p * (1 + dist[..., 0]), p * (1 - dist[..., 1])

    def avancer(self, e: Etat, ordres: Ordres, rg: Regard | None) -> tuple[dict, torch.Tensor, torch.Tensor]:
        """Une bougie. Rend (résultat du simulateur, positions fermées SANS elle [B, M], réveils [B])."""
        c = e.comptes
        avant = c.u.clone()
        r = c.pas(ordres)
        apres = c.u
        ferme_seul = r["fermees_sans_ordre"]
        ouvre = (apres != 0) & ((avant == 0) | (torch.sign(apres) != torch.sign(avant)))
        e.ouverture = torch.where(apres == 0, -1, torch.where(ouvre, c.t[:, None], e.ouverture))
        gain_jour = ((r["valeur"] - e.valeur_prec) / CAPITAL * 100 * 96).float()          # en % par jour
        e.valeur_prec = r["valeur"].clone()
        rythme = torch.tensor([1 / (5 * 96), 1 / (20 * 96)], device=e.memoire.device)
        e.memoire = e.memoire + rythme[None, :] * (gain_jour[:, None] - e.memoire)
        d = danger(r["valeur"], c.solde_minuit).float()
        t = c.t
        haut, bas, prix = self.h.h[t], self.h.l[t], self.h.c[t]
        tp = (t - 1).clamp(min=0)
        causes = [(ferme_seul.any(1), 1),
                  ((d >= SEUIL_REVEIL) & (e.danger_vu < SEUIL_REVEIL), 2),
                  ((haut >= e.alerte_haut).any(1) | (bas <= e.alerte_bas).any(1), 3),
                  (((prix / e.prix_vu - 1).abs() >= GROS_MOUVEMENT * e.taille_vue).any(1), 4),
                  (((self.cal[t][..., 0] * 48 < AVANT_ANNONCE_H) & (self.cal[tp][..., 0] * 48 >= AVANT_ANNONCE_H)).any(1), 5)]
        for cause, code in causes:
            e.raison = torch.where(cause & ~e.reveil, code, e.raison)
            e.reveil = e.reveil | cause
        return r, ferme_seul, d


def avantages_regards(r, v, qui, fin, v_fin, gamma: float, lam: float):
    """Avantage de chaque regard quand les regards sont espacés librement [T, B] (rendus sur toute la grille, à lire
    seulement là où `qui`) : argent gagné jusqu'au regard suivant (compté gamma^k après k bougies) + ce qu'elle
    attendait au regard suivant x gamma^(écart) - ce qu'elle attendait à ce regard. Une fin de partie coupe tout."""
    T, B = r.shape
    adv = torch.zeros_like(r)
    acc = torch.zeros(B, device=r.device)
    disc = torch.ones(B, device=r.device)
    v_suiv = v_fin.clone()
    suite = torch.zeros(B, device=r.device)
    for t in reversed(range(T)):
        vivant = 1.0 - fin[t]
        acc, disc, suite = acc * vivant, disc * vivant, suite * vivant
        acc = r[t] + gamma * acc
        disc = gamma * disc
        delta = acc + disc * v_suiv - v[t]
        a_t = delta + disc * lam * suite
        q = qui[t]
        adv[t] = torch.where(q, a_t, 0.0)
        suite = torch.where(q, a_t, suite)
        v_suiv = torch.where(q, v[t], v_suiv)
        acc = torch.where(q, torch.zeros_like(acc), acc)
        disc = torch.where(q, torch.ones_like(disc), disc)
    return adv


class ProfesseurRegard:
    """Fait jouer la classe (ou plusieurs « mondes » à tour de rôle : le marché et son miroir), puis renforce les
    regards qui ont mieux rapporté que prévu."""

    def __init__(self, mondes: list[ClasseRegard], agent: TraderHumain, parties: int = 512, pas: int = 512,
                 vitesse: float = 3e-4, vitesse_yeux: float = 1e-4, gamma: float = GAMMA, lam: float = 0.95,
                 coupe: float = 0.2, epoques: int = 4, paquet: int = 1024, curiosite: float = 0.003,
                 graine: int = 0, de: pd.Timestamp = APPRENDRE_DE, jusqua: pd.Timestamp = APPRENDRE_JUSQUA,
                 duree: int = DUREE_PARTIE):
        self.mondes, self.agent = mondes, agent
        self.B, self.pas, self.gamma, self.lam = parties, pas, gamma, lam
        self.coupe, self.epoques, self.paquet, self.curiosite, self.duree = coupe, epoques, paquet, curiosite, duree
        yeux = [p for p in agent.yeux.parameters() if p.requires_grad]
        reste = list(agent.decisions.parameters())
        self.opt = torch.optim.AdamW([{"params": reste, "lr": vitesse}, {"params": yeux, "lr": vitesse_yeux}],
                                     weight_decay=1e-4)
        dev = mondes[0].dev
        self.gen = torch.Generator(device=dev).manual_seed(graine)
        self.de, self.jusqua = de, jusqua
        self.mondes, self.bornes, self.etats = [], [], []
        for i, c in enumerate(mondes):
            self.installer(i, c)
        self.k = 0

    def installer(self, i: int, c: ClasseRegard, de: pd.Timestamp | None = None, jusqua: pd.Timestamp | None = None):
        """Met le monde `c` à la place `i` (école des mille mondes : un monde neuf remplace un ancien) ; ses comptes
        partent au hasard entre `de` et `jusqua` (par défaut : les années d'apprentissage)."""
        lo = max(c.instant(de if de is not None else self.de), 96 * 30)
        hi = c.instant(jusqua if jusqua is not None else self.jusqua) - self.duree - 1
        if hi <= lo:
            raise ValueError("monde trop court pour une partie")
        e = Etat(c.h, self.B)
        for liste, valeur in ((self.mondes, c), (self.bornes, (lo, hi)), (self.etats, e)):
            if i < len(liste):
                liste[i] = valeur
            else:
                liste.append(valeur)
        e.recommencer(torch.ones(self.B, dtype=torch.bool, device=c.dev), self._departs(i, self.B))

    def _departs(self, i: int, n: int) -> torch.Tensor:
        lo, hi = self.bornes[i]
        return torch.randint(lo, hi, (n,), device=self.mondes[i].dev, generator=self.gen)

    @torch.no_grad()
    def jouer(self) -> dict:
        self.k = (self.k + 1) % len(self.mondes)
        c, e, a = self.mondes[self.k], self.etats[self.k], self.agent
        a.eval()
        B, T, dev = self.B, self.pas, c.dev
        grille = {k: torch.zeros(T, B, device=dev) for k in ("r", "v", "fin")}
        grille["qui"] = torch.zeros(T, B, dtype=torch.bool, device=dev)
        regards = []
        # 15/10 : quel regard a posé l'ordre à l'avance en cours (ligne de la mémoire), et lesquels se sont exécutés :
        # la taille d'un ordre jamais exécuté n'est pas apprise (elle n'a rien changé ; avant, l'élève grossissait)
        poseur = torch.full((B, c.h.M), -1, dtype=torch.long, device=dev)
        executees, lignes = [], 0
        st = {"regards": 0, "garder": 0, "proteger": 0, "changer": 0, "morts": 0, "inactifs": 0, "reussis": 0,
              "fermes_seul": 0, "en_position": 0.0, "delai": 0.0, "frais": 0.0, "ouvre": 0, "risque": 0.0,
              "attendre": 0}
        for t in range(T):
            qui = (e.comptes.t >= e.prochain) | e.reveil
            rg = None
            if qui.any():
                rg = c.decider(a, e, qui)
                regards.append(rg)
                n_q = int(qui.sum())
                pose = (rg.choix["geste"] == ATTENDRE) & (rg.choix["sens"] != FERMER)
                ids = (lignes + torch.arange(n_q, device=dev))[:, None].expand(-1, c.h.M)
                poseur[qui] = torch.where(pose, ids, poseur[qui])
                lignes += n_q
                grille["qui"][t] = qui
                grille["v"][t, qui] = rg.valeur
                c.noter_regard(e, rg)
                g = rg.choix["geste"]
                st["regards"] += int(qui.sum())
                st["garder"] += int((g == 0).sum())
                st["proteger"] += int((g == 1).sum())
                st["changer"] += int((g == 2).sum())
                st["attendre"] += int((g == ATTENDRE).sum())
                ouvre = (g == CHANGER) & (rg.choix["sens"] != FERMER)
                st["ouvre"] += int(ouvre.sum())
                st["risque"] += float(TraderHumain.risque_pct(rg.choix["taille"])[ouvre].sum())
                st["delai"] += float(TraderHumain.delai(rg.choix["regard"]).float().sum())
            avant = e.comptes.valeur(c.h.c[e.comptes.t], c.h.fx[e.comptes.t])
            d_avant = danger(avant, e.comptes.solde_minuit).float()
            r, ferme_seul, _ = c.avancer(e, c.ordres(e, rg), rg)
            ex = r["attente_executee"] & (poseur >= 0)
            if ex.any():
                b_, m_ = ex.nonzero(as_tuple=True)
                executees.append(torch.stack([poseur[b_, m_], m_], 1))
                poseur[b_, m_] = -1
            gain = ((r["valeur"] - avant) / CAPITAL * 100).float()
            grille["r"][t] = ressenti(gain, d_avant) - PUNITION_MUR * r["mort"].float() \
                + BONUS_REUSSITE * r["reussi"].float()
            fin = (r["mort"] | r["reussi"] | r["fin_histoire"] | (e.comptes.t >= self.bornes[self.k][1] + self.duree)
                   | (e.comptes.t - e.debut >= self.duree))
            grille["fin"][t] = fin.float()
            st["morts"] += int(r["mort"].sum())
            st["inactifs"] += int(r["inactif"].sum())
            st["reussis"] += int(r["reussi"].sum())
            st["fermes_seul"] += int(ferme_seul.sum())
            st["frais"] += float(r["frais"].sum())
            st["en_position"] += float((e.comptes.u != 0).any(1).float().mean())
            if fin.any():
                e.recommencer(fin, self._departs(self.k, B))
        # ce qu'elle attend de chaque compte à la fin de la séance (un regard « pour voir », sans agir)
        tous = torch.ones(B, dtype=torch.bool, device=dev)
        v_fin = c.sortie(a, *c.voir(e, tous))[0]["valeur"]
        adv = avantages_regards(grille["r"], grille["v"], grille["qui"], grille["fin"], v_fin, self.gamma, self.lam)
        q = grille["qui"]
        self.memoire = {"idx": torch.cat([x.idx for x in regards]), "vm": torch.cat([x.vm for x in regards]),
                        "vc": torch.cat([x.vc for x in regards]), "lp": torch.cat([x.lp for x in regards]),
                        "adv": adv[q], "ret": adv[q] + grille["v"][q],
                        "choix": {k: torch.cat([x.choix[k] for x in regards]) for k in regards[0].choix},
                        "lp_taille_attente": torch.cat([x.lp_taille_attente for x in regards])}
        executee = torch.zeros(lignes, c.h.M, dtype=torch.bool, device=dev)
        if executees:
            ij = torch.cat(executees)
            executee[ij[:, 0], ij[:, 1]] = True
        ch = self.memoire["choix"]
        self.memoire["sans_taille"] = (ch["geste"] == ATTENDRE) & (ch["sens"] != FERMER) & ~executee
        n = max(st["regards"], 1)
        jours = T * B / 96
        return {"regards_par_jour": st["regards"] / jours, "delai_moyen_h": st["delai"] / n / 4,
                "garder_pct": st["garder"] / n / c.h.M * 100, "proteger_pct": st["proteger"] / n / c.h.M * 100,
                "changer_pct": st["changer"] / n / c.h.M * 100, "attendre_pct": st["attendre"] / n / c.h.M * 100, "fermes_sans_elle": st["fermes_seul"],
                "morts": st["morts"], "inactifs": st["inactifs"], "reussis": st["reussis"], "en_position_pct": st["en_position"] / T * 100,
                "recompense_par_jour": float(grille["r"].sum()) / jours, "monde": c.marches[0],
                "risque_moyen_pct": st["risque"] / max(st["ouvre"], 1)}

    def apprendre(self) -> dict:
        c, a, m = self.mondes[self.k], self.agent, self.memoire
        N = len(m["lp"])
        adv = m["adv"]
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)
        a.train()
        bilan = {"perte_decision": 0.0, "perte_valeur": 0.0, "hasard": 0.0}
        n = 0
        for _ in range(self.epoques):
            ordre = torch.randperm(N, device=c.dev)
            for d in range(0, N, self.paquet):
                i = ordre[d:d + self.paquet]
                sortie, _ = c.sortie(a, m["idx"][i], m["vm"][i], m["vc"][i])
                lois = a.lois(sortie)
                choix = {k: v[i] for k, v in m["choix"].items()}
                sans = m["sans_taille"][i]
                lp_avant = m["lp"][i] - (m["lp_taille_attente"][i] * sans.float()).sum(-1)
                ratio = (a.log_prob(lois, choix, sans_taille=sans) - lp_avant).exp()
                p1, p2 = ratio * adv[i], ratio.clamp(1 - self.coupe, 1 + self.coupe) * adv[i]
                perte_dec = -torch.min(p1, p2).mean()
                perte_v = torch.nn.functional.huber_loss(sortie["valeur"], m["ret"][i])
                hasard = a.hasard(lois).mean()
                perte = perte_dec + 0.5 * perte_v - self.curiosite * hasard
                self.opt.zero_grad(set_to_none=True)
                perte.backward()
                torch.nn.utils.clip_grad_norm_(a.parameters(), 0.5)
                self.opt.step()
                bilan["perte_decision"] += float(perte_dec)
                bilan["perte_valeur"] += float(perte_v)
                bilan["hasard"] += float(hasard)
                n += 1
        return {k: v / max(n, 1) for k, v in bilan.items()} | {"regards_appris": N}


# ---------------------------------------------------------------------- contrôle et examen de son comportement
@torch.no_grad()
def jouer_comptes(c: ClasseRegard, agent: TraderHumain, departs: torch.Tensor, duree: int = DUREE_PARTIE,
                  graine: int = 0, carnet: list | None = None, jumeau: bool = False) -> dict:
    """Des comptes FTMO de 100 000 $ partent aux instants `departs` et jouent `duree` bougies, comme un challenge
    (arrêt à +10 % ou à un mur). Rend l'argent ET le comportement (regards, durée de détention, stops...).
    `carnet` (liste) : y ajoute les événements du PREMIER compte, pour fabriquer le carnet de bord.
    `jumeau` (15/10/2026, nouvelle note du juge) : son JUMEAU au hasard fait exactement ses gestes (mêmes regards,
    même taille, mêmes stops et objectifs en distance, mêmes frais) mais le SENS de chaque ouverture est tiré à pile
    ou face : ce qu'elle gagne de plus que lui, c'est son vrai avantage (la taille et le timing seuls n'en créent
    pas)."""
    appareils = [c.dev] if c.dev.type == "cuda" else []
    with torch.random.fork_rng(devices=appareils):
        torch.manual_seed(graine)
        return _jouer(c, agent, departs.to(c.dev), duree, carnet, jumeau)


def _jouer(c: ClasseRegard, agent: TraderHumain, departs, duree, carnet, jumeau: bool = False) -> dict:
    agent.eval()
    n = len(departs)
    e = Etat(c.h, n)
    e.recommencer(torch.ones(n, dtype=torch.bool, device=c.dev), departs)
    cpt = e.comptes
    vivant = torch.ones(n, dtype=torch.bool, device=c.dev)
    reussi, mort, inactif = torch.zeros_like(vivant), torch.zeros_like(vivant), torch.zeros_like(vivant)
    finale = torch.full((n,), CAPITAL, dtype=torch.float64, device=c.dev)
    sommet, baisse_max = finale.clone(), torch.zeros_like(finale)
    st = {"regards": 0, "delai": 0.0, "ouvertures": 0, "avec_stop": 0, "avec_objectif": 0, "dist_stop": 0.0,
          "tenues": [], "en_position": 0.0, "fermes_seul": 0, "tailles": [], "resultats_r": [], "objectifs_r": []}
    # 15/10 (chef de projet : « qu'elle apprenne les ratios, 2R... ») : 1 R = ce que coûterait son stop à l'ouverture ;
    # résultat de chaque trade en R (gains réalisés, avant frais), et l'objectif prévu en R (objectif / stop)
    un_r = torch.full_like(cpt.u, float("nan"))
    cumul = torch.zeros_like(cpt.u)
    for _ in range(duree):
        qui = ((cpt.t >= e.prochain) | e.reveil) & vivant
        rg = None
        if qui.any():
            rg = c.decider(agent, e, qui, sur=True)
            if jumeau:                                   # même geste, sens d'ouverture tiré à pile ou face
                s = rg.choix["sens"]
                hasard = torch.where(torch.rand(s.shape, device=s.device) < 0.5, VENDRE, ACHETER)
                rg.choix["sens"] = torch.where(s == FERMER, s, hasard)
            if carnet is not None and bool(qui[0]):
                carnet.append(_note_regard(c, e, rg))
            c.noter_regard(e, rg)
            st["regards"] += int(qui.sum())
            st["delai"] += float(TraderHumain.delai(rg.choix["regard"]).float().sum())
        ordres = c.ordres(e, rg)
        ouverture_avant = e.ouverture.clone()
        t_avant = cpt.t.clone()
        r, ferme_seul, _ = c.avancer(e, ordres, rg)
        # comportement : ouvertures (avec ou sans stop), durées de détention des positions fermées
        ouvre = (e.ouverture >= 0) & (e.ouverture != ouverture_avant)
        ferme = (ouverture_avant >= 0) & (e.ouverture != ouverture_avant)
        cumul = cumul + r["realise"]
        if ferme.any():
            compte = ferme & (un_r > 0)
            st["resultats_r"] += (cumul / un_r)[compte].tolist()
            cumul = torch.where(ferme, 0.0, cumul)
            un_r = torch.where(ferme, float("nan"), un_r)
        if ouvre.any():
            fx_ = c.h.fx[cpt.t]
            a_stop_ = ouvre & ~torch.isnan(cpt.stop)
            un_r = torch.where(a_stop_, cpt.u.abs() * (cpt.entree - cpt.stop).abs() * fx_, un_r)
            prevu = a_stop_ & ~torch.isnan(cpt.objectif) & (cpt.entree != cpt.stop)
            st["objectifs_r"] += ((cpt.objectif - cpt.entree).abs() / (cpt.entree - cpt.stop).abs())[prevu].tolist()
        if ouvre.any():
            st["ouvertures"] += int(ouvre.sum())
            a_stop = ouvre & ~torch.isnan(cpt.stop)
            st["avec_stop"] += int(a_stop.sum())
            st["avec_objectif"] += int((ouvre & ~torch.isnan(cpt.objectif)).sum())
            prix = c.h.c[cpt.t]
            st["dist_stop"] += float(torch.where(a_stop, (cpt.stop - prix).abs() / prix, 0.0).sum())
            valeur = cpt.valeur(prix, c.h.fx[cpt.t])[:, None]
            st["tailles"] += ((cpt.u * prix * c.h.fx[cpt.t]).abs() / valeur)[ouvre].float().tolist()
        if ferme.any():
            st["tenues"] += ((t_avant[:, None] + 1 - ouverture_avant)[ferme].float() / 4).tolist()   # en heures
        if carnet is not None and bool(vivant[0]):
            carnet.extend(_note_evenements(c, e, r, ferme_seul))
        st["fermes_seul"] += int(ferme_seul[vivant].sum())
        st["en_position"] += float(((cpt.u != 0).any(1) & vivant).float().sum() / n)
        v = torch.where(vivant, r["valeur"], finale)
        sommet = torch.maximum(sommet, v)
        baisse_max = torch.maximum(baisse_max, (sommet - v) / sommet)
        finale = v
        reussi |= vivant & r["reussi"]
        mort |= vivant & r["mort"]
        inactif |= vivant & r["inactif"]
        vivant &= ~(r["mort"] | r["reussi"] | r["fin_histoire"])
        if not vivant.any():
            break
    gains = (finale / CAPITAL - 1) * 100
    jours = n * duree / 96
    tenues = st["tenues"]
    mois = duree / UN_MOIS
    tailles = np.array(st["tailles"]) if st["tailles"] else np.zeros(1)
    rr = np.array(st["resultats_r"]) if st["resultats_r"] else np.zeros(0)
    gagnes, perdus = rr[rr > 0], rr[rr <= 0]
    return {"gain_moyen_pct": float(gains.mean()) / mois, "gain_total_pct": float(gains.mean()),
            "gains_comptes_pct_mois": (gains / mois).tolist(), "reussis_comptes": reussi.tolist(),
            "morts_comptes": (mort & ~inactif).tolist(),
            # règle FTMO « pas de positions beaucoup plus grosses que d'habitude » : plus grosse / taille médiane
            "taille_max_sur_mediane": float(tailles.max() / max(np.median(tailles), 1e-9)),
            # ses trades en R (avec un stop à l'ouverture) : résultat moyen, gagnants, gain et perte moyens, objectif prévu
            "trades_en_r": int(len(rr)), "r_moyen": float(rr.mean()) if len(rr) else float("nan"),
            "gagnants_pct": float((rr > 0).mean() * 100) if len(rr) else float("nan"),
            "gain_moyen_r": float(gagnes.mean()) if len(gagnes) else float("nan"),
            "perte_moyenne_r": float(perdus.mean()) if len(perdus) else float("nan"),
            "objectif_prevu_r": float(np.median(st["objectifs_r"])) if st["objectifs_r"] else float("nan"),
            "comptes_positifs_pct": float((gains > 0).float().mean() * 100),
            "challenges_reussis_pct": float(reussi.float().mean() * 100),
            "murs_touches_pct": float((mort & ~inactif).float().mean() * 100),
            "inactifs_pct": float(inactif.float().mean() * 100),
            "jours_trading_moyen": float(cpt.jours_trades.float().mean()),
            "baisse_max_moyenne_pct": float(baisse_max.mean() * 100),
            "regards_par_jour": st["regards"] / jours, "delai_moyen_h": st["delai"] / max(st["regards"], 1) / 4,
            "trades_par_mois": st["ouvertures"] / n * UN_MOIS / duree,
            "tenue_moyenne_h": float(np.mean(tenues)) if tenues else 0.0,
            "tenue_mediane_h": float(np.median(tenues)) if tenues else 0.0,
            "avec_stop_pct": st["avec_stop"] / max(st["ouvertures"], 1) * 100,
            "avec_objectif_pct": st["avec_objectif"] / max(st["ouvertures"], 1) * 100,
            "stop_moyen_pct_prix": st["dist_stop"] / max(st["avec_stop"], 1) * 100,
            "temps_en_position_pct": st["en_position"] / duree * 100}


def controler(c: ClasseRegard, agent: TraderHumain, de=CONTROLE_DE, jusqua=CONTROLE_JUSQUA, comptes: int = 36,
              duree: int = DUREE_PARTIE, graine: int = 12345) -> dict:
    """Comptes étalés régulièrement sur la période (un par mois sur 3 ans par défaut), tirages figés : le même
    contrôle à chaque fois, pour comparer."""
    lo, hi = c.instant(de), c.instant(jusqua) - duree - 1
    departs = torch.linspace(lo, max(hi, lo + 1), comptes, device=c.dev).long()
    return jouer_comptes(c, agent, departs, duree, graine)


# ---------------------------------------------------------------------- le carnet de bord (premier compte)
def _note_regard(c: ClasseRegard, e: Etat, rg: Regard) -> dict:
    """Ce qu'elle décide au regard du premier compte (indice 0 dans les comptes qui regardent)."""
    cpt, h = e.comptes, c.h
    t = int(cpt.t[0])
    prix, fx = h.c[t], h.fx[t]
    valeur = float(cpt.valeur(prix[None], fx[None])[0])
    a = {k: v[0] for k, v in rg.choix.items()}
    gestes = []
    for j, m in enumerate(c.marches):
        g = int(a["geste"][j])
        if g == 0:
            continue
        voulue = float(TraderHumain.position_voulue(a["sens"][j:j + 1, None], a["taille"][j:j + 1, None].double(),
                                                    torch.tensor([valeur], dtype=torch.float64, device=c.dev),
                                                    rg.taille_jour[0:1, j:j + 1].double())[0, 0])
        p = float(prix[j])
        if g == ATTENDRE:                                  # ordre à l'avance (15/10)
            if int(a["sens"][j]) == FERMER or voulue == 0:
                if int(cpt.att_type[0, j]) > 0:
                    gestes.append({"marche": m, "geste": g, "annule": True, "prix": p, "position_dollars": 0.0,
                                   "stop": None, "objectif": None})
                continue
            d_att = float(torch.exp(a["att_dist"][j].clamp(ATT_MIN, ATT_MAX)) * rg.taille_jour[0, j])
            limite = bool(a["att_limite"][j] > 0.5)
            s = float(np.sign(voulue))
            gestes.append({"marche": m, "geste": g, "annule": False, "prix": p, "position_dollars": voulue,
                           "prix_ordre": p * (1 - s * d_att) if limite else p * (1 + s * d_att), "limite": limite,
                           "duree_h": int(TraderHumain.duree_attente(a["att_duree"][j])) / 4, "stop": None,
                           "objectif": None})
            continue
        sens = np.sign(voulue) if g == CHANGER else float(np.sign(float(cpt.u[0, j])))
        if sens == 0 and float(cpt.u[0, j]) == 0:          # geste sans effet (rien à protéger, rien à fermer)
            continue
        d_stop = float(TraderHumain.distance(a["stop_dist"][j], rg.taille_jour[0, j]))
        d_obj = float(TraderHumain.distance(a["obj_dist"][j], rg.taille_jour[0, j]))
        stop = p * (1 - sens * d_stop) if a["stop_on"][j] > 0.5 and sens else None
        objectif = p * (1 + sens * d_obj) if a["obj_on"][j] > 0.5 and sens else None
        gestes.append({"marche": m, "geste": g, "position_dollars": voulue if g == CHANGER else
                       float(cpt.u[0, j] * prix[j] * fx[j]), "prix": p, "stop": stop, "objectif": objectif})
    delai = int(TraderHumain.delai(a["regard"]))
    # en direct, son retour est dans le futur : au-delà de la dernière bougie connue, on compte 15 min par bougie
    retour = (h.temps[t + delai] if t + delai < h.T else h.temps[h.T - 1] + pd.Timedelta(minutes=15 * (t + delai - h.T + 1))) \
        + pd.Timedelta(minutes=15)
    raison = int(e.raison[0])
    return {"type": "regard", "temps": h.temps[t] + pd.Timedelta(minutes=15), "gestes": gestes, "retour": retour,
            "reveil": RAISONS.get(raison) if raison else None,
            "compte_pct": (valeur / CAPITAL - 1) * 100,
            "mur_jour_pct": (valeur - (float(cpt.solde_minuit[0]) - 0.05 * CAPITAL)) / CAPITAL * 100}


def _note_evenements(c: ClasseRegard, e: Etat, r: dict, ferme_seul: torch.Tensor) -> list[dict]:
    cpt, h = e.comptes, c.h
    t = int(cpt.t[0])
    sortie = []
    valeur = float(r["valeur"][0])
    if bool(r["mort"][0]):
        sortie.append({"type": "inactif" if bool(r["inactif"][0]) else "mur", "temps": h.temps[t], "compte_pct": (valeur / CAPITAL - 1) * 100})
    if bool(r["reussi"][0]):
        sortie.append({"type": "reussi", "temps": h.temps[t], "compte_pct": (valeur / CAPITAL - 1) * 100})
    for j in torch.nonzero(ferme_seul[0]).flatten().tolist():
        sortie.append({"type": "fermee", "temps": h.temps[t], "marche": c.marches[j],
                       "forcee": bool(h.derniere[t, j]), "compte_pct": (valeur / CAPITAL - 1) * 100})
    return sortie
