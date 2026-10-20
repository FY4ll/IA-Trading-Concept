"""Le cerveau du TRADER HUMAIN NUMÉRIQUE (nouvelle école, 14/10/2026 : « un humain dans une machine »).

Ce qu'il voit (comme un trader devant MetaTrader) :
- pour chaque marché : les graphiques bruts de 15 minutes au mois (ses yeux, petits et NEUFS : aucune greffe, les gros
  cerveaux et les greffes récitaient leurs années apprises), ce qu'il a sur ce marché (position, gain latent, stop,
  objectif, heures avant la fermeture du week-end), le calendrier des annonces importantes, depuis quand il tient ;
- pour le compte : valeur, baisse du jour, distance aux murs FTMO, argent engagé, séances ouvertes, et depuis
  combien de temps il n'a pas regardé.

Ce qu'il fait, à chaque REGARD (et seulement là), pour chaque marché, un geste :
- 0 : garder (ne rien toucher) ;
- 1 : revoir ses protections (poser, déplacer ou retirer stop et objectif, position inchangée) ;
- 2 : changer de position : acheter, vendre ou fermer, avec ses protections. La TAILLE se pense comme un trader :
  « combien je risque » = la part du compte que lui coûterait une bougie du jour entière contre lui (de 0,01 % à
  20 % : bien au-delà des murs, le casino reste possible, à lui d'apprendre à l'éviter). 14/10 18h40 : la taille
  « en fois la valeur du compte » faisait partir ses premiers essais à 3-5 fois le compte -> murs partout ->
  paralysie en 35 leçons (vie/ecole_regard/classe1_paralysie_taille_compte).
- 3 : poser un ORDRE À L'AVANCE (15/10/2026, comme dans MetaTrader) : sens et taille comme une position, prix
  d'entrée à une distance choisie (en bougies du jour), LIMITE (acheter moins cher / vendre plus cher si le prix y
  revient) ou STOP (acheter / vendre si le prix casse ce niveau), durée de validité ; « fermer » = annuler l'ordre.
Stop et objectif : LIBRES, n'importe quelle distance (de 1/20 à 20 fois la taille d'une bougie du jour) ou aucun.
Et pour le compte entier : QUAND il reviendra regarder (de 15 minutes à 4 heures de marché depuis le 15/10, décision
du chef de projet : « elle passerait à côté d'opportunités »). Pour chaque marché, ses ALERTES DE PRIX (15/10) : un
niveau au-dessus et un au-dessous (en bougies du jour) qui la réveillent si le prix y passe, comme les alertes de
MetaTrader. Entre deux regards, le compte vit seul : stops, objectifs, fermeture du week-end et murs FTMO restent
actifs (comme MetaTrader) ; elle est aussi réveillée par un gros mouvement et avant une annonce importante
(ecole/regard.py).
"""
from __future__ import annotations

import math

import torch
from torch import nn
from torch.distributions import Bernoulli, Categorical, Normal

from collapsar.cerveau.reseau import Cerveau
from collapsar.mains.simulateur import N_VUE_COMPTE, N_VUE_MARCHE
from collapsar.yeux.faits import N_CALENDRIER, N_SEANCES

N_VUE_MARCHE_H = N_VUE_MARCHE + N_CALENDRIER + 1        # + depuis combien de jours il tient la position
# + depuis combien de temps il n'a pas regardé, jours sans ouvrir de trade (/30, règle FTMO d'inactivité) et jours
#   de trading déjà faits (/4, minimum FTMO pour valider le challenge)
# + sa mémoire d'expérience : résultat moyen par jour de son compte sur ~5 et ~20 jours (école des mille mondes)
N_VUE_COMPTE_H = N_VUE_COMPTE + N_SEANCES + 5
GARDER, PROTEGER, CHANGER, ATTENDRE = 0, 1, 2, 3
VENDRE, FERMER, ACHETER = 0, 1, 2
RISQUE_MIN, RISQUE_MAX = math.log(0.0001), math.log(0.20)   # part du compte par bougie du jour contre lui
RISQUE_DEPART = math.log(0.005)                              # ses premiers essais : ~0,5 % par bougie du jour
REGARD_MIN, REGARD_MAX = 1, 16                          # en bougies de 15 minutes : 15 min -> 4 heures (15/10)
ATTENTE_MAX = 480                                       # un ordre à l'avance peut vivre jusqu'à 5 jours de marché
ALERTE_MIN, ALERTE_MAX = -3.0, 1.1                      # log de la distance d'une alerte (1/20 -> 3 bougies du jour)
DIST_MIN, DIST_MAX = -3.0, 3.0                          # log de la distance du stop / objectif en bougies du jour
ATT_MIN, ATT_MAX = -3.0, 1.6                            # log de la distance d'un ordre à l'avance (1/20 -> 5 bougies du jour)


class Decisions(nn.Module):
    """Les mains et le jugement, branchés sur ce que voient les yeux (séparés pour pouvoir les tester seuls)."""

    def __init__(self, d: int = 128, entree: int = 256):
        super().__init__()
        self.marche = nn.Sequential(nn.Linear(entree + N_VUE_MARCHE_H, d), nn.LayerNorm(d), nn.GELU())
        self.compte = nn.Sequential(nn.Linear(N_VUE_COMPTE_H, 64), nn.GELU())
        self.ensemble = nn.Sequential(nn.Linear(d + 64, d), nn.LayerNorm(d), nn.GELU(), nn.Linear(d, d), nn.GELU())
        self.geste = nn.Linear(d, 4)
        self.attente = nn.Linear(d, 3)                   # ordre à l'avance : distance, limite ?, durée de validité
        self.position = nn.Linear(d, 4)                  # vendre / fermer / acheter, puis combien il risque
        self.protections = nn.Linear(d, 4)              # stop ? distance du stop, objectif ? distance de l'objectif
        self.alerte = nn.Linear(d, 2)                    # alertes de prix : log des distances au-dessus / au-dessous
        self.regard = nn.Linear(d + 64, 1)               # log du délai avant le prochain regard (en bougies)
        self.valeur = nn.Linear(d + 64, 1)               # ce qu'il attend de l'argent du compte, d'ici la fin
        # largeur des essais : taille, stop, objectif, regard. 15/10 : stop et objectif à 1 (au lieu de 0,5) : ses essais
        # vont de ~1/3 à ~3 bougies du jour (1 fois sur 3 au-delà), pour qu'elle découvre aussi les trades à stop serré et
        # objectif lointain (10R), qu'elle n'essayait presque jamais
        # + distance et durée d'un ordre à l'avance (15/10)
        # + distances des alertes au-dessus et au-dessous (15/10)
        self.log_ecart = nn.Parameter(torch.tensor([-1.0, 0.0, 0.0, -0.7, -0.5, -0.5, -0.5, -0.5]))
        for couche in (self.geste, self.position, self.protections, self.regard, self.attente, self.alerte):
            nn.init.zeros_(couche.weight)
            nn.init.zeros_(couche.bias)
        with torch.no_grad():
            self.geste.bias[GARDER] = 1.0                # au départ : garder ~58 %, protections ~21 %, changer ~21 %
            self.regard.bias.fill_(math.log(16.0))       # au départ : revient regarder dans ~4 heures
            self.position.bias[3] = RISQUE_DEPART
            self.geste.bias[ATTENDRE] = -1.0             # ordres à l'avance rares au départ (~7 % des gestes)
            self.attente.bias[0] = math.log(0.5)         # à une demi-bougie du jour du prix
            self.attente.bias[2] = math.log(32.0)        # valable ~8 heures
            self.alerte.bias.fill_(math.log(0.5))        # alertes à une demi-bougie du jour de part et d'autre

    def forward(self, lu, vue_marche, vue_compte) -> dict:
        b, m, _ = vue_marche.shape
        par_marche = self.marche(torch.cat([lu, vue_marche], -1))
        c = self.compte(vue_compte)
        x = self.ensemble(torch.cat([par_marche, c[:, None, :].expand(b, m, -1)], -1))
        g = torch.cat([x.mean(1), c], -1)
        p = self.protections(x)
        pos = self.position(x)
        att = self.attente(x)
        return {"geste": self.geste(x), "sens": pos[..., :3], "taille": pos[..., 3],
                "att_dist": att[..., 0], "att_logit": att[..., 1], "att_duree": att[..., 2], "alerte": self.alerte(x),
                "stop_logit": p[..., 0], "stop_dist": p[..., 1], "obj_logit": p[..., 2], "obj_dist": p[..., 3],
                "regard": self.regard(g)[:, 0], "valeur": self.valeur(g)[:, 0]}


class TraderHumain(nn.Module):
    def __init__(self, largeur: float = 0.35, oubli: float = 0.0, d: int = 128):
        """`oubli` à 0 : ses choix rejoués à l'école doivent être exactement ceux qu'il a faits en jouant ; contre le
        par cœur : petit cerveau, monde miroir, contrôle sur années jamais vues."""
        super().__init__()
        self.yeux = Cerveau(oubli=oubli, largeur=largeur)
        self.yeux.regarder.requires_grad_(False)          # la tête des anciens exercices ne sert pas ici
        self.decisions = Decisions(d)

    def forward(self, fenetres, extra, vue_marche, vue_compte) -> dict:
        """fenetres [B*M, échelles, 64, traits], extra [B*M, ...], vue_marche [B, M, N], vue_compte [B, N]."""
        b, m, _ = vue_marche.shape
        lu = self.yeux.comprendre(fenetres, extra).reshape(b, m, -1)
        return self.decisions(lu, vue_marche, vue_compte)

    # ------------------------------------------------------------------ ses choix comme des lois de probabilité
    def lois(self, sortie: dict) -> dict:
        e = self.decisions.log_ecart.clamp(-3.0, 0.5).exp()
        return {"geste": Categorical(logits=sortie["geste"]),
                "sens": Categorical(logits=sortie["sens"]),
                "taille": Normal(sortie["taille"], e[0].expand_as(sortie["taille"])),
                "stop_on": Bernoulli(logits=sortie["stop_logit"]),
                "stop_dist": Normal(sortie["stop_dist"], e[1].expand_as(sortie["stop_dist"])),
                "obj_on": Bernoulli(logits=sortie["obj_logit"]),
                "obj_dist": Normal(sortie["obj_dist"], e[2].expand_as(sortie["obj_dist"])),
                "regard": Normal(sortie["regard"], e[3].expand_as(sortie["regard"])),
                "att_dist": Normal(sortie["att_dist"], e[4].expand_as(sortie["att_dist"])),
                "att_limite": Bernoulli(logits=sortie["att_logit"]),
                "att_duree": Normal(sortie["att_duree"], e[5].expand_as(sortie["att_duree"])),
                "alerte": Normal(sortie["alerte"], e[6:8].expand_as(sortie["alerte"]))}

    @staticmethod
    def choisir(lois: dict, sur: bool = False) -> dict:
        """Tire ses choix. `sur` (contrôle, examen) : les grandeurs (taille, distances, délai) sont ses meilleures
        idées ; les gestes restent tirés (il n'agit pas à chaque regard, et c'est voulu)."""
        tire = lambda k: lois[k].mean if sur else lois[k].sample()
        return {"geste": lois["geste"].sample(), "sens": lois["sens"].sample(), "taille": tire("taille"),
                "stop_on": lois["stop_on"].sample(), "stop_dist": tire("stop_dist"),
                "obj_on": lois["obj_on"].sample(), "obj_dist": tire("obj_dist"), "regard": tire("regard"),
                "att_dist": tire("att_dist"), "att_limite": lois["att_limite"].sample(), "att_duree": tire("att_duree"),
                "alerte": tire("alerte")}

    @staticmethod
    def log_prob(lois: dict, a: dict, sans_taille: torch.Tensor | None = None) -> torch.Tensor:
        """Probabilité (log) de l'ensemble de ses choix à un regard [B] : seuls les choix qui ont servi comptent.
        `sans_taille` [B, M] : taille non comptée (15/10 : ordre à l'avance jamais exécuté, sa taille n'a rien changé)."""
        change = (a["geste"] == CHANGER).float()
        attend = (a["geste"] == ATTENDRE).float()
        protege = ((a["geste"] == PROTEGER) | (a["geste"] == CHANGER)).float()
        ouvre = (change + attend) * (a["sens"] != FERMER).float()
        pose = attend * (a["sens"] != FERMER).float()
        lp = (lois["geste"].log_prob(a["geste"]) + (change + attend) * lois["sens"].log_prob(a["sens"])
              + ouvre * lois["taille"].log_prob(a["taille"]) * (1.0 if sans_taille is None else (~sans_taille).float())
              + pose * (lois["att_dist"].log_prob(a["att_dist"]) + lois["att_limite"].log_prob(a["att_limite"])
                        + lois["att_duree"].log_prob(a["att_duree"]))
              + protege * (lois["stop_on"].log_prob(a["stop_on"]) + a["stop_on"] * lois["stop_dist"].log_prob(a["stop_dist"])
                           + lois["obj_on"].log_prob(a["obj_on"]) + a["obj_on"] * lois["obj_dist"].log_prob(a["obj_dist"])))
        lp = lp + lois["alerte"].log_prob(a["alerte"]).sum(-1)        # ses alertes, posées à chaque regard
        return lp.sum(-1) + lois["regard"].log_prob(a["regard"])

    @staticmethod
    def log_prob_taille_attente(lois: dict, a: dict) -> torch.Tensor:
        """[B, M] : la part « taille » de la probabilité, pour les ordres à l'avance posés à ce regard."""
        pose = ((a["geste"] == ATTENDRE) & (a["sens"] != FERMER)).float()
        return pose * lois["taille"].log_prob(a["taille"])

    @staticmethod
    def hasard(lois: dict) -> torch.Tensor:
        """Sa part d'essais (entropie) sur ses choix « oui / non » (geste, stop ou pas, objectif ou pas), pour qu'il
        continue d'essayer pendant l'école. Pas sur les grandeurs : leur largeur d'essai, c'est l'école qui la règle
        (sinon elle grandirait sans fin)."""
        par_marche = (lois["geste"].entropy() + lois["sens"].entropy() + lois["stop_on"].entropy()
                      + lois["obj_on"].entropy() + lois["att_limite"].entropy())
        return par_marche.sum(-1)

    # ------------------------------------------------------------------ des choix aux ordres
    @staticmethod
    def position_voulue(sens: torch.Tensor, taille: torch.Tensor, valeur_compte: torch.Tensor,
                        taille_jour: torch.Tensor) -> torch.Tensor:
        """Position voulue en dollars [B, M] : signe (vendre -1, fermer 0, acheter +1) x risque x valeur du compte /
        taille d'une bougie du jour (en part du prix). Ex. : risque 0,5 %, bougie du jour 0,6 % -> 0,83 x le compte."""
        signe = (sens.to(taille.dtype) - FERMER)
        risque = torch.exp(taille.clamp(RISQUE_MIN, RISQUE_MAX))
        return signe * risque * valeur_compte[:, None] / taille_jour.clamp(min=1e-4)

    @staticmethod
    def risque_pct(taille: torch.Tensor) -> torch.Tensor:
        return torch.exp(taille.clamp(RISQUE_MIN, RISQUE_MAX)) * 100

    def charger(self, etat: dict):
        """Charge un cerveau, y compris d'AVANT les ordres à l'avance et les alertes (15/10) : ses gestes et ses
        largeurs d'essai sont repris, les nouvelles têtes gardent leur départ."""
        actuel = self.state_dict()
        for k, v in etat.items():
            if k not in actuel:
                continue
            if actuel[k].shape == v.shape:
                actuel[k] = v
            elif k.endswith("geste.weight") or k.endswith("geste.bias") or k.endswith("log_ecart"):
                n = v.shape[0]
                actuel[k] = actuel[k].clone()
                actuel[k][:n] = v
        self.load_state_dict(actuel)

    @staticmethod
    def duree_attente(x: torch.Tensor) -> torch.Tensor:
        return torch.exp(x).round().clamp(1, ATTENTE_MAX).long()

    @staticmethod
    def delai(x: torch.Tensor) -> torch.Tensor:
        """Délai avant le prochain regard, en bougies de 15 minutes (1 -> 16 : 4 heures au plus)."""
        return torch.exp(x).round().clamp(REGARD_MIN, REGARD_MAX).long()

    @staticmethod
    def distance_alerte(x: torch.Tensor, taille_jour: torch.Tensor) -> torch.Tensor:
        """Distance d'une alerte en part du prix : exp(x) bougies du jour (1/20 -> 3)."""
        return torch.exp(x.clamp(ALERTE_MIN, ALERTE_MAX)) * taille_jour

    @staticmethod
    def distance(s: torch.Tensor, taille_jour: torch.Tensor) -> torch.Tensor:
        """Distance du stop / objectif en part du prix : exp(s) bougies du jour (1/20 -> 20)."""
        return torch.exp(s.clamp(DIST_MIN, DIST_MAX)) * taille_jour
