"""LE CERVEAU ET LES MAINS de l'école de la précision : des choix LIBRES, mais exprimés en STRUCTURE.

À chaque regard, pour chaque marché de son panier, un geste :
  0 garder · 1 acheter au marché · 2 vendre au marché · 3 poser un ordre d'achat limite · 4 poser un ordre de vente
  limite · 5 fermer la position / annuler l'ordre.
Pour une ouverture, elle désigne (aucune règle, aucun menu de stratégie : des niveaux du graphique, comme un trader
qui pose ses lignes) :
- l'ENTRÉE (ordre limite) : le bord proche ou le milieu d'une de ses zones vivantes (journalier -> 3 min) ;
- le STOP : le bord lointain d'une zone ou un creux / sommet confirmé de n'importe quelle unité, DERRIÈRE l'entrée,
  + une petite marge au choix (0 à 0,5 agitation) ;
- la DESTINATION : une zone opposée ou un sommet / creux d'une unité, ou « laisser courir » ;
- la PART encaissée à l'objectif 1 (0, 50 ou 80 %), et l'OBJECTIF 1 : un niveau de structure avant la destination
  ou 1, 2, 3 fois le risque ; après l'objectif 1, le stop du reste passe à l'entrée (simulateur.py) ;
- le RISQUE (0,1 / 0,25 / 0,5 / 1 % du compte) et, pour un ordre limite, sa durée de validité ;
- (arbre de l'or, réglage mains.suiveur, éteint pour HYPERNOVA) le STOP SUIVEUR : aucun, ou derrière les nouveaux
  creux / sommets confirmés d'une unité, dès l'entrée ou après l'objectif 1 (suiveur.py) ; tiré EN DERNIER par une
  tête de plus (avec un penchant appris pour « laisser courir ») : les autres gestes ne changent pas.
- (19/10, UNE branche « suiveur_1r ») des options de STOP SUIVEUR APRÈS +1R (1 h / 4 h / 1 agitation sous le plus haut,
  suiveur.py) : une tête de plus (`suiv1r`), tirée avec celle du suiveur, en dernier ; (UNE branche « tendance ») les
  12 valeurs de la TENDANCE DE FOND en dernier à l'entrée (tendance.py).
- (19/10 soir, UNE branche « symetrique », symetrie.py) le CERVEAU SYMÉTRIQUE : acheter et vendre jugés par les mêmes
  neurones (la tête « acheter » lue sur sa vue et sur la vue du graphique retourné) ; mêmes poids, aucune entrée de plus.
Et pour le compte : QUAND revenir regarder (15 min -> 4 h ; elle est aussi réveillée par ses positions et le prix).
Chaque niveau proposé est décrit à ses yeux (unité, type, distance au prix et à l'entrée en agitations, multiple du
risque, zone touchée / réaction / zone dans la zone) : c'est elle qui apprend lequel choisir.
Seules contraintes mécaniques (MetaTrader) : un niveau doit être à plus d'un aller-retour de frais de l'entrée, un
ordre limite du bon côté du prix ; une seule idée à la fois par marché (position OU ordre en attente).
"""
from __future__ import annotations

import torch
from torch import nn

from collapsar.ecole.precision import suiveur as SV
from collapsar.ecole.precision.reglages import R
from collapsar.ecole.precision.vue import NU, nan0, taille_caracteristiques

GARDER, ACHAT_M, VENTE_M, ACHAT_L, VENTE_L, FERMER = range(6)
N_POS = 11
N_COMPTE = 18
N_STAT = 16                            # type (7) + unité (7) + rang (1) + « vient d'une zone » (1)
N_DYN = 8
TYPES = ("proche", "milieu", "lointain", "opposee", "sommet", "R", "courir")
# REGARDS PLUS ESPACÉS (19/10 nuit, mentor.py, UNE branche « apprentie ») : délais avant de revenir regarder, en bougies de
# 15 min, rangés par taille de la tête « délai » (les 5 premiers = ceux des réglages, dans le même ordre) ; une branche
# sans eux (toutes les autres, HYPERNOVA) : la tête et la liste des réglages, rien ne change.
REGARDS_LONGS = {7: (1, 2, 4, 8, 16, 32, 96)}          # 15 min, 30 min, 1 h, 2 h, 4 h, 8 h, 1 jour
_STAT = {}
_CONST = {}


def constantes(dev) -> dict:
    """Petites tables de valeurs, créées une fois par appareil (rien n'est copié du processeur pendant un graphe)."""
    cle = str(dev)
    if cle not in _CONST:
        r = R().mains
        t = lambda x, dt=torch.float32: torch.tensor(x, dtype=dt, device=dev)
        _CONST[cle] = {"sgn": t([1.0, -1.0]), "marges": t(r.marges_stop), "rr": t(r.tp1_en_r),
                       "parts": t(r.parts_tp1), "risques": t(r.risques_pct),
                       "validites": t(r.validites_ordre, torch.long), "delais": t(r.delais_regard, torch.long)}
    return _CONST[cle]


def _constantes_1r(o1r, dev):
    """(unités, agitations) des options après +1R, rangées UNE fois sur l'appareil (rien n'est copié du processeur
    pendant l'enregistrement d'un graphe de la carte graphique)."""
    cle = (tuple(o1r), str(dev))
    if cle not in _CONST:
        _CONST[cle] = (torch.tensor([iu for iu, _, _ in o1r], dtype=torch.long, device=dev),
                       torch.tensor([ag for _, ag, _ in o1r], dtype=torch.float32, device=dev))
    return _CONST[cle]


def statiques(K: int, dev) -> dict:
    """Description fixe de chaque place de niveau (type, unité, rang), calculée une fois."""
    cle = (K, str(dev))
    if cle in _STAT:
        return _STAT[cle]

    def zone(type_):
        x = torch.zeros(NU, K, N_STAT)
        for u in range(NU):
            for k in range(K):
                x[u, k, TYPES.index(type_)] = 1
                x[u, k, 7 + u] = 1
                x[u, k, 14] = k
                x[u, k, 15] = 1
        return x.reshape(NU * K, N_STAT)

    def sommet():
        x = torch.zeros(NU, 2, N_STAT)
        for u in range(NU):
            for k in range(2):
                x[u, k, TYPES.index("sommet")] = 1
                x[u, k, 7 + u] = 1
                x[u, k, 14] = k
        return x.reshape(NU * 2, N_STAT)

    r = torch.zeros(len(R().mains.tp1_en_r), N_STAT)
    r[:, TYPES.index("R")] = 1
    courir = torch.zeros(1, N_STAT)
    courir[0, TYPES.index("courir")] = 1
    _STAT[cle] = {k: v.to(dev) for k, v in {
        "entree": torch.cat([zone("proche"), zone("milieu")]),
        "stop": torch.cat([zone("lointain"), sommet()]),
        "dest": torch.cat([zone("opposee"), sommet(), courir]),
        "tp1": torch.cat([zone("opposee"), sommet(), r])}.items()}
    return _STAT[cle]


class Pointeur(nn.Module):
    """Note chaque niveau proposé d'après ce qu'elle pense du marché (h) et la description du niveau."""

    def __init__(self, d: int, f: int = N_STAT + N_DYN, cache: int = 64):
        super().__init__()
        self.a = nn.Linear(d, cache)
        self.b = nn.Linear(f, cache)
        self.c = nn.Linear(cache, 1)

    def forward(self, h, x):
        return self.c(torch.nn.functional.gelu(self.a(h)[:, :, None] + self.b(x))).squeeze(-1)


class Cerveau(nn.Module):
    def __init__(self, d: int = 128, journal: bool = False, delai: str | None = None, tendance: bool = False,
                 suiveur_1r: bool = False, delais: tuple | None = None):
        super().__init__()
        r = R().mains
        # REGARDS PLUS ESPACÉS (une branche, mentor.py) : None (défaut) = la liste des réglages, exactement comme avant
        dl = tuple(int(x) for x in delais) if delais is not None else None
        if dl is not None and dl == tuple(int(x) for x in r.delais_regard):
            dl = None
        if dl is not None and (len(dl) not in REGARDS_LONGS or REGARDS_LONGS[len(dl)] != dl
                               or dl[:len(r.delais_regard)] != tuple(int(x) for x in r.delais_regard)):
            raise ValueError(f"délais de regard inattendus : {dl} (prévus : {REGARDS_LONGS})")
        self.delais_regard = dl
        # JOURNAL DE TRADING (journal_trading.py, une branche greffée seulement) : NJ entrées EN DERNIER (après la
        # position) ; sans journal (défaut : HYPERNOVA, MAGNETAR) rien ne change
        from collapsar.ecole.precision import journal_trading as JN
        from collapsar.ecole.precision import tendance as TD
        self.n_journal = JN.NJ if journal else 0
        self.journal_delai = delai or JN.delai_defaut()
        # TENDANCE DE FOND (tendance.py, une branche seulement) : NTD entrées EN DERNIER (après le journal) ; sans
        # tendance (défaut) rien ne change
        self.n_tendance = TD.NTD if tendance else 0
        # STOPS PROCHES (stop_proche.py, une branche greffée seulement) : distance maximale entrée -> stop, en
        # agitations ; None (défaut : HYPERNOVA, toutes les autres branches) = rien ne change. Pas un poids.
        self.stop_max_agitation = None
        self.F = taille_caracteristiques() + N_POS + self.n_journal + self.n_tendance
        self.marche = nn.Sequential(nn.Linear(self.F, 256), nn.LayerNorm(256), nn.GELU(), nn.Linear(256, d), nn.GELU())
        self.compte = nn.Sequential(nn.Linear(N_COMPTE, 64), nn.GELU())
        self.ensemble = nn.Sequential(nn.Linear(2 * d + 64, d), nn.LayerNorm(d), nn.GELU(), nn.Linear(d, d), nn.GELU())
        self.entree, self.stop, self.dest, self.tp1 = Pointeur(d), Pointeur(d), Pointeur(d), Pointeur(d)
        self.n_marge, self.n_part = len(r.marges_stop), len(r.parts_tp1)
        self.n_risque, self.n_valid = len(r.risques_pct), len(r.validites_ordre)
        self.n_suiv = SV.n_options()                          # 0 = pas de stop suiveur (HYPERNOVA)
        # têtes simples d'un marché : geste (6), marge, part, risque, validité
        self.tetes = nn.Linear(d, 6 + self.n_marge + self.n_part + self.n_risque + self.n_valid)
        self.delai = nn.Linear(d + 64, len(dl) if dl is not None else len(r.delais_regard))
        self.valeur = nn.Linear(d + 64, 1)
        for couche in (self.tetes, self.delai):
            nn.init.zeros_(couche.weight)
            nn.init.zeros_(couche.bias)
        with torch.no_grad():
            self.tetes.bias[GARDER] = 1.5                     # au départ : garder ~ la moitié des regards
            o = 6 + self.n_marge + self.n_part
            self.tetes.bias[o:o + self.n_risque] = torch.tensor([0.5, 0.5, 0.0, -0.5, -1.0])[:self.n_risque]
            self.delai.bias[:len(r.delais_regard)] = torch.tensor([-0.5, 0.0, 0.5, 0.5, 0.0])[:len(r.delais_regard)]
            if dl is not None:                                # regards plus espacés : peu choisis au départ
                self.delai.bias[len(r.delais_regard):] = -2.0
        if dl is not None:                                    # (pas dans les poids : suit l'appareil du cerveau)
            self.register_buffer("delais_t", torch.tensor(dl, dtype=torch.long), persistent=False)
        if self.n_suiv:
            # tête du STOP SUIVEUR (suiveur.py), créée EN DERNIER (les autres couches naissent comme avant) : options
            # (aucun, unité x moment) + penchant « laisser courir » ; poids à zéro, chaque option essayée de temps en temps
            self.suiv = nn.Linear(d, self.n_suiv + 1)
            with torch.no_grad():
                nn.init.zeros_(self.suiv.weight)
                nn.init.zeros_(self.suiv.bias)
                self.suiv.bias[1:self.n_suiv] = SV.biais_depart()
        self.n_suiv1r = 0
        if suiveur_1r:
            # tête du SUIVEUR APRÈS +1R (suiveur.py, une branche), créée EN DERNIER : ses options s'ajoutent à celles du
            # suiveur ; poids et biais à zéro (le penchant de départ est posé à la greffe)
            if not self.n_suiv:
                raise ValueError("suiveur après +1R sans stop suiveur (réglage mains.suiveur éteint)")
            self.n_suiv1r = SV.n_options_1r()
            self.suiv1r = nn.Linear(d, self.n_suiv1r)
            with torch.no_grad():
                nn.init.zeros_(self.suiv1r.weight)
                nn.init.zeros_(self.suiv1r.bias)

    def corps(self, fm, fc, slot):
        hm = self.marche(fm)
        c = self.compte(fc)
        w = slot.float()[..., None]
        moy = (hm * w).sum(1) / w.sum(1).clamp(min=1)
        n, J, _ = hm.shape
        h = self.ensemble(torch.cat([hm, moy[:, None].expand(n, J, -1), c[:, None].expand(n, J, -1)], -1))
        g = torch.cat([(h * w).sum(1) / w.sum(1).clamp(min=1), c], -1)
        return h, g


def forme(etat_cerveau: dict) -> dict:
    """La forme d'un cerveau d'après ses poids : {"journal", "tendance", "suiveur_1r"} (entrée de la 1re couche =
    yeux + position [+ NJ journal] [+ NTD tendance], tête « suiv1r » présente ou non)."""
    from collapsar.ecole.precision import journal_trading as JN
    from collapsar.ecole.precision import tendance as TD
    w = etat_cerveau["marche.0.weight"].shape[1]
    base = taille_caracteristiques() + N_POS
    formes = {base: (False, False), base + JN.NJ: (True, False), base + TD.NTD: (False, True),
              base + JN.NJ + TD.NTD: (True, True)}
    if w not in formes:
        raise ValueError(f"entrée du cerveau inattendue : {w} (attendu {sorted(formes)})")
    jr, td = formes[w]
    out = {"journal": jr, "tendance": td, "suiveur_1r": "suiv1r.weight" in etat_cerveau}
    nd = etat_cerveau["delai.weight"].shape[0] if "delai.weight" in etat_cerveau else None
    if nd is not None and nd != len(R().mains.delais_regard):     # regards plus espacés (mentor.py, une branche)
        if nd not in REGARDS_LONGS:
            raise ValueError(f"tête « délai » inattendue : {nd} sorties")
        out["delais"] = REGARDS_LONGS[nd]
    return out


def a_journal(etat_cerveau: dict) -> bool:
    """Ces poids sont-ils ceux d'une branche au journal de trading (entrée agrandie de NJ colonnes) ?"""
    return forme(etat_cerveau)["journal"]


def cerveau_pour(etat_cerveau: dict, delai: str | None = None) -> "Cerveau":
    """Un cerveau de la bonne forme pour ces poids (journal, tendance, suiveur après +1R), poids chargés."""
    net = Cerveau(delai=delai, **forme(etat_cerveau))
    net.load_state_dict(etat_cerveau)
    return net


def regler_precision(net: "Cerveau", temperament: dict | None) -> "Cerveau":
    """STOPS PROCHES (stop_proche.py) : le réglage `precision.stop_max_agitation` du TEMPÉRAMENT d'une branche (absent =
    None = comme avant). Ce n'est pas une règle sur QUAND trader : seulement sur OÙ un stop peut être posé (les niveaux
    de structure plus loin que ce plafond, marge comprise, sont retirés des choix ; aucun niveau assez proche = pas
    d'ouverture possible à ce moment-là)."""
    p = (temperament or {}).get("precision") if isinstance(temperament, dict) else None
    v = p.get("stop_max_agitation") if isinstance(p, dict) else None
    net.stop_max_agitation = float(v) if v is not None else None
    return net


def regler_symetrie(net: "Cerveau", temperament: dict | None) -> "Cerveau":
    """CERVEAU SYMÉTRIQUE (symetrie.py) : le réglage `symetrique` du TEMPÉRAMENT d'une branche (absent = False = comme
    avant). Aucun poids de plus : seule la façon de lire ses têtes change (politique)."""
    net.symetrique = isinstance(temperament, dict) and bool(temperament.get("symetrique"))
    return net


def adapter(etat_cerveau: dict, net: "Cerveau") -> dict:
    """Les poids d'une autre branche ramenés à la forme de `net` (journal / tendance ajoutés à zéro ou retirés, bloc par
    bloc ; tête du suiveur après +1R gardée telle quelle si `net` l'a et pas la source, retirée dans l'autre sens) :
    garde-fou qui ramène une branche à la cime quand leurs formes diffèrent. Sans différence : les poids tels quels."""
    cle = "marche.0.weight"
    w = etat_cerveau[cle]
    F = net.marche[0].in_features
    out = dict(etat_cerveau)
    if w.shape[1] != F:
        src = forme(etat_cerveau)
        base = taille_caracteristiques() + N_POS
        from collapsar.ecole.precision import journal_trading as JN
        from collapsar.ecole.precision import tendance as TD
        z = lambda k: torch.zeros(w.shape[0], k, dtype=w.dtype, device=w.device)
        j0 = base + (JN.NJ if src["journal"] else 0)
        blocs = [w[:, :base],
                 (w[:, base:j0] if src["journal"] else z(JN.NJ)) if net.n_journal else None,
                 (w[:, j0:j0 + TD.NTD] if src["tendance"] else z(TD.NTD)) if net.n_tendance else None]
        out[cle] = torch.cat([b for b in blocs if b is not None], 1)
    if getattr(net, "n_suiv1r", 0) and "suiv1r.weight" not in out:
        out["suiv1r.weight"] = net.suiv1r.weight.detach().clone()
        out["suiv1r.bias"] = net.suiv1r.bias.detach().clone()
    if not getattr(net, "n_suiv1r", 0):
        out.pop("suiv1r.weight", None)
        out.pop("suiv1r.bias", None)
    # regards plus espacés (mentor.py) : les délais en plus gardés tels quels si `net` les a et pas la source, retirés
    # dans l'autre sens (les premiers délais sont les mêmes dans les deux listes)
    nd = net.delai.out_features
    for k in ("delai.weight", "delai.bias"):
        if k in out and out[k].shape[0] != nd:
            v = out[k]
            mien = getattr(net.delai, k.split(".")[1]).detach().clone().to(v.device, v.dtype)
            out[k] = torch.cat([v, mien[v.shape[0]:]], 0) if v.shape[0] < nd else v[:nd].clone()
    return out


class Loi:
    """Un choix parmi des places (certaines interdites) : tirage, probabilité, hasard (entropie)."""

    def __init__(self, logits, masque=None):
        if masque is not None:
            masque = masque.clone()
            masque[..., 0] |= ~masque.any(-1)                 # aucune place valable : place 0 (jamais comptée)
            logits = logits.masked_fill(~masque, -1e9)
        self.logits = logits.float()
        self._lp = None

    @property
    def lp(self):
        if self._lp is None:
            self._lp = torch.log_softmax(self.logits, -1)
        return self._lp

    def tirer(self):
        u = torch.rand_like(self.logits).clamp(1e-9, 1 - 1e-9)
        return (self.logits - torch.log(-torch.log(u))).argmax(-1)

    def log_prob(self, i):
        return self.lp.gather(-1, i[..., None]).squeeze(-1)

    def hasard(self):
        return -(self.lp.exp() * self.lp).sum(-1)


# ============================================================================================== niveaux proposés
def niveaux(s: dict):
    """Pour chaque côté (0 achat, 1 vente) : niveaux d'entrée, de stop, de destination (prix) [n, J, 2, C], leur
    validité, et ce que l'on sait de chacun [n, J, 2, C, 5] (touchée, réaction, zone dans la zone, hauteur, âge)."""
    top, bot, ok = s["top"], s["bot"], s["ok"]
    n, J = top.shape[:2]
    A = s["A"][:, :, None, None]
    sw = s["sw"]                                                    # [n,J,U,4] : s1, s2, c1, c2
    mid = (top + bot) / 2
    att = torch.stack([s["tou"].float(), s["rea"].float(), s["dans"].float(), (top - bot) / A[..., None],
                       torch.log1p(s["age"]) / 5], -1)            # [n,J,U,2,K,5]
    att = att.permute(0, 1, 3, 2, 4, 5).reshape(n, J, 2, -1, 5)     # [n,J,2(côté de zone),U*K,5]
    f = lambda x: x.reshape(n, J, -1)
    z5 = torch.zeros(n, J, NU * 2, 5, device=top.device)
    # côté 0 = achat (zones de demande d'entrée, zones d'offre en face), côté 1 = vente
    proche = torch.stack([f(top[:, :, :, 0]), f(bot[:, :, :, 1])], 2)
    milieu = torch.stack([f(mid[:, :, :, 0]), f(mid[:, :, :, 1])], 2)
    loin = torch.stack([f(bot[:, :, :, 0]), f(top[:, :, :, 1])], 2)
    opp = torch.stack([f(bot[:, :, :, 1]), f(top[:, :, :, 0])], 2)
    zok = torch.stack([f(ok[:, :, :, 0]), f(ok[:, :, :, 1])], 2)
    sw_stop = torch.stack([f(sw[..., 2:4]), f(sw[..., 0:2])], 2)
    sw_dest = torch.stack([f(sw[..., 0:2]), f(sw[..., 2:4])], 2)
    return {"entree": torch.cat([proche, milieu], -1), "entree_ok": torch.cat([zok, zok], -1),
            "entree_att": torch.cat([att, att], 3),
            "stop": torch.cat([loin, sw_stop], -1), "stop_ok": torch.cat([zok, torch.isfinite(sw_stop)], -1),
            "stop_att": torch.cat([att, z5[:, :, None].expand(-1, -1, 2, -1, -1)], 3),
            "dest": torch.cat([opp, sw_dest], -1), "dest_ok": torch.cat([zok.flip(2), torch.isfinite(sw_dest)], -1),
            "dest_att": torch.cat([att.flip(2), z5[:, :, None].expand(-1, -1, 2, -1, -1)], 3)}


def _dyn(niv, attr, sig, p, e, A, rd):
    """Description changeante d'un niveau : distance au prix et à l'entrée (agitations, sens du trade), multiple du
    risque, et ce que l'on sait de la zone."""
    s = sig[..., None]
    x_p = s * (niv - p[..., None]) / A[..., None]
    x_e = s * (niv - e[..., None]) / A[..., None]
    x_r = s * (niv - e[..., None]) / rd[..., None] if rd is not None else torch.zeros_like(x_p)
    return nan0(torch.cat([torch.stack([x_p, x_e, x_r], -1), attr], -1)).clamp(-20, 20)


def politique(net: Cerveau, s: dict, fm, fc, pos, choix: dict | None = None, evaluer: bool = True,
              jumeau: torch.Tensor | None = None):
    """Tire ses choix (choix=None) ou relit la probabilité de choix déjà faits. Rend (choix, log-probabilité par
    compte [n], part de la log-probabilité qui ne compte que si l'ordre s'exécute [n, J], hasard [n], valeur [n],
    niveaux en prix). `evaluer=False` (examen) : seulement les choix et les niveaux (plus rapide).
    `jumeau` [n] (examen) : ces comptes sont son JUMEAU AU HASARD : mêmes gestes (ouvrir au marché / poser un ordre,
    même moment, même risque, même part à l'objectif 1, même délai), mais le SENS de chaque ouverture est tiré à pile ou
    face ; les niveaux (entrée, stop, destination) sont alors ceux qu'elle choisirait de ce côté-là. Si le côté tiré
    n'offre aucun niveau possible, le jumeau ne trade pas."""
    r = R().mains
    dev = fm.device
    n, J = fm.shape[:2]
    sym = bool(getattr(net, "symetrique", False))
    if sym:
        # CERVEAU SYMÉTRIQUE (symetrie.py, une branche) : le même corps lit sa vue x et la vue miroir(x) (un seul passage) ;
        # acheter = tête « acheter » sur x, vendre = la même tête sur miroir(x), rien / fermer / délai / valeur = moyenne
        from collapsar.ecole.precision import symetrie as SY
        sl = s["slot"]
        hh, gg = net.corps(torch.cat([fm, SY.miroir_vue(fm, net)]), torch.cat([fc, fc]), torch.cat([sl, sl]))
        h, h_m, g, g_m = hh[:n], hh[n:], gg[:n], gg[n:]
        valeur = 0.5 * (net.valeur(g) + net.valeur(g_m))[:, 0] if evaluer else None
        t_x, t_m = net.tetes(h), net.tetes(h_m)
        tetes = t_x
        l_geste = SY.logits_geste(t_x, t_m)
    else:
        h, g = net.corps(fm, fc, s["slot"])
        valeur = net.valeur(g)[:, 0] if evaluer else None
        tetes = net.tetes(h)
        l_geste = tetes[..., :6]
    o1, o2, o3, o4 = 6, 6 + net.n_marge, 6 + net.n_marge + net.n_part, 6 + net.n_marge + net.n_part + net.n_risque
    st = statiques(s["top"].shape[-1], dev)
    nv = niveaux(s)
    p, A, demi = s["p"], s["A"], s["demi"]
    frais = 2 * demi * p                                       # un aller-retour, en prix
    K_ = constantes(dev)
    sgn = K_["sgn"][None, None, :, None]
    # ---- entrées valables (bon côté du prix, pas trop loin, un stop possible derrière) pour les deux côtés
    e_niv, s_niv = nv["entree"], nv["stop"]                     # [n,J,2,C]
    p4, f4 = p[..., None, None], frais[..., None, None]
    e_ok = nv["entree_ok"] & (sgn * (p4 - e_niv) > f4) & ((p4 - e_niv).abs() <= r.entree_max_agitation * A[..., None, None])
    # STOPS PROCHES (stop_proche.py, une branche greffée) : un stop ne peut être posé que derrière une structure à moins
    # de `cap` agitations de l'entrée ; None (défaut) = exactement comme avant
    cap = getattr(net, "stop_max_agitation", None)
    d_es = sgn[..., None] * (e_niv[..., None] - s_niv[:, :, :, None, :])
    derriere = nv["stop_ok"][:, :, :, None, :] & (d_es > f4[..., None])
    if cap is not None:
        derriere = derriere & (d_es <= cap * A[..., None, None, None])
    e_ok = e_ok & derriere.any(-1)
    d_ms = sgn * (p4 - s_niv)
    m_ok = nv["stop_ok"] & (d_ms > f4)
    if cap is not None:
        m_ok = m_ok & (d_ms <= cap * A[..., None, None])
    m_ok = m_ok.any(-1)                                                                # [n,J,2]
    # ---- geste
    a_pos, a_att = pos[..., 0] != 0, pos[..., 1] != 0
    libre = s["slot"] & ~a_pos & ~a_att
    if bool(getattr(r, "marche_annule_ordre", False)):
        # (20/10, MAGNETAR, réglage mains.marche_annule_ordre ; absent = comme avant) : un ordre limite EN ATTENTE ne bloque
        # plus rien : elle peut ouvrir au marché ou poser un autre ordre limite, qui le remplace (jeu.Table.appliquer)
        libre = s["slot"] & ~a_pos
    mg = torch.stack([torch.ones_like(libre), libre & m_ok[..., 0], libre & m_ok[..., 1], libre & e_ok[..., 0, :].any(-1),
                      libre & e_ok[..., 1, :].any(-1), s["slot"] & (a_pos | a_att)], -1)
    L_geste = Loi(l_geste, mg)
    tire = choix is None
    if tire:
        choix = {"geste": L_geste.tirer()}
        if jumeau is not None:
            G0 = choix["geste"]
            ouv0 = (G0 >= ACHAT_M) & (G0 <= VENTE_L)
            autre = torch.where(G0 % 2 == 1, G0 + 1, G0 - 1).clamp(0, 5)           # achat <-> vente, même type
            permis = mg.gather(-1, autre[..., None]).squeeze(-1)
            pile = jumeau[:, None] & ouv0 & (torch.rand(n, J, device=dev) < 0.5)
            choix["geste"] = torch.where(pile, torch.where(permis, autre, torch.zeros_like(G0)), G0)
    G = choix["geste"]
    vente = (G == VENTE_M) | (G == VENTE_L)
    ic = vente.long()
    sig = 1.0 - 2.0 * vente.float()
    limite = (G == ACHAT_L) | (G == VENTE_L)
    ouvre = (G >= ACHAT_M) & (G <= VENTE_L)
    if sym:                                           # les mains d'une vente : les mêmes têtes, lues sur miroir(x)
        v3 = vente[..., None]
        h = torch.where(v3, h_m, h)
        tetes = torch.where(v3, t_m, t_x)

    def pick(x):
        i = ic.reshape(n, J, 1, *([1] * (x.dim() - 3))).expand(n, J, 1, *x.shape[3:])
        return x.gather(2, i).squeeze(2)
    # ---- entrée
    eN, eAT = pick(e_niv), pick(nv["entree_att"])
    xe = torch.cat([st["entree"].expand(n, J, -1, -1), _dyn(eN, eAT, sig, p, p, A, None)], -1)
    L_ent = Loi(net.entree(h, xe), pick(e_ok))
    if tire:
        choix["entree"] = L_ent.tirer()
    e = torch.where(limite, eN.gather(2, choix["entree"][..., None]).squeeze(-1), p)
    # ---- stop (derrière l'entrée) + marge
    sN, sAT = pick(s_niv), pick(nv["stop_att"])
    sOK = pick(nv["stop_ok"]) & (sig[..., None] * (e[..., None] - sN) > frais[..., None])
    if cap is not None:                               # stops proches : les niveaux plus lointains sont retirés
        sOK = sOK & (sig[..., None] * (e[..., None] - sN) <= cap * A[..., None])
    xs = torch.cat([st["stop"].expand(n, J, -1, -1), _dyn(sN, sAT, sig, p, e, A, None)], -1)
    L_stop = Loi(net.stop(h, xs), sOK)
    if tire:
        choix["stop"] = L_stop.tirer()
    marges = K_["marges"]
    if cap is None:
        L_marge = Loi(tetes[..., o1:o2])
    else:                                             # stops proches : la marge ne fait pas dépasser le plafond
        d0 = sig * (e - sN.gather(2, choix["stop"][..., None]).squeeze(-1))
        L_marge = Loi(tetes[..., o1:o2], d0[..., None] + marges * A[..., None] <= cap * A[..., None])
    if tire:
        choix["marge"] = L_marge.tirer()
    stop = sN.gather(2, choix["stop"][..., None]).squeeze(-1) - sig * marges[choix["marge"]] * A
    rd = (sig * (e - stop)).clamp(min=1e-12)
    # ---- destination (ou laisser courir)
    zc = torch.zeros(n, J, 1, device=dev)
    dN = torch.cat([pick(nv["dest"]), zc], -1)
    dAT = torch.cat([pick(nv["dest_att"]), torch.zeros(n, J, 1, 5, device=dev)], 2)
    dOK = torch.cat([pick(nv["dest_ok"]) & (sig[..., None] * (dN[..., :-1] - e[..., None]) > frais[..., None]),
                     torch.ones(n, J, 1, dtype=torch.bool, device=dev)], -1)
    xd = _dyn(dN, dAT, sig, p, e, A, rd)
    xd[..., -1, :] = 0.0
    l_dest = net.dest(h, torch.cat([st["dest"].expand(n, J, -1, -1), xd], -1))
    if net.n_suiv:                                    # penchant appris pour « laisser courir » (0 au départ)
        t_suiv = net.suiv(h)
        l_dest = torch.cat([l_dest[..., :-1], l_dest[..., -1:] + t_suiv[..., net.n_suiv:]], -1)
    L_dest = Loi(l_dest, dOK)
    if tire:
        choix["dest"] = L_dest.tirer()
    courir = choix["dest"] == dN.shape[-1] - 1
    dest = torch.where(courir, float("nan"), dN.gather(2, choix["dest"][..., None]).squeeze(-1))
    # ---- objectif 1 (structure avant la destination, ou 1 / 2 / 3 R) et part encaissée
    rr = K_["rr"]
    nr = len(r.tp1_en_r)
    tN = torch.cat([dN[..., :-1], e[..., None] + sig[..., None] * rr * rd[..., None]], -1)
    tAT = torch.cat([dAT[:, :, :-1], torch.zeros(n, J, nr, 5, device=dev)], 2)
    avant = courir[..., None] | (sig[..., None] * (dest[..., None] - tN) > 0)
    tOK = torch.cat([dOK[..., :-1], torch.ones(n, J, nr, dtype=torch.bool, device=dev)], -1) & \
        (sig[..., None] * (tN - e[..., None]) > frais[..., None]) & avant
    L_tp1 = Loi(net.tp1(h, torch.cat([st["tp1"].expand(n, J, -1, -1), _dyn(tN, tAT, sig, p, e, A, rd)], -1)), tOK)
    mp = torch.cat([torch.ones(n, J, 1, dtype=torch.bool, device=dev),
                    tOK.any(-1, keepdim=True).expand(-1, -1, net.n_part - 1)], -1)
    L_part = Loi(tetes[..., o2:o3], mp)
    L_risque = Loi(tetes[..., o3:o4])
    L_valid = Loi(tetes[..., o4:])
    L_delai = Loi(0.5 * (net.delai(g) + net.delai(g_m)) if sym else net.delai(g))
    if tire:
        choix["tp1"] = L_tp1.tirer()
        choix["part"] = L_part.tirer()
        choix["risque"] = L_risque.tirer()
        choix["validite"] = L_valid.tirer()
        choix["delai"] = L_delai.tirer()
    part = K_["parts"][choix["part"]]
    a_tp1 = part > 0
    tp1 = torch.where(a_tp1, tN.gather(2, choix["tp1"][..., None]).squeeze(-1), float("nan"))
    lv = {"entree": e, "stop": stop, "tp1": tp1, "part": part, "dest": dest, "rd": rd, "sig": sig, "ouvre": ouvre,
          "limite": limite, "ferme": G == FERMER,
          "risque_pct": K_["risques"][choix["risque"]], "validite": K_["validites"][choix["validite"]],
          "delai": (net.delais_t if getattr(net, "delais_regard", None) else K_["delais"])[choix["delai"]]}
    if getattr(net, "voir_lois", False):              # mesures (symetrie.py) : probabilités des 6 gestes
        lv["lp_geste"] = L_geste.lp
    L_suiv = None
    if net.n_suiv:
        # ---- stop suiveur (tiré EN DERNIER : à graine égale, tous les autres tirages sont les mêmes qu'avant)
        NS = (net.n_suiv - 1) // 2
        dsp = s["sv_dispo"]                                                   # [n,J,NS] unité connue de ce marché
        ms = torch.cat([torch.ones(n, J, 1, dtype=torch.bool, device=dev), dsp, dsp & a_tp1[..., None]], -1)
        n1r = getattr(net, "n_suiv1r", 0)
        if n1r:
            # SUIVEUR APRÈS +1R (suiveur.py, une branche) : ses options s'ajoutent après celles du suiveur
            o1r = SV.options_1r()
            m1 = torch.stack([dsp[..., iu] if ag == 0 else torch.ones_like(dsp[..., 0]) for iu, ag, _ in o1r], -1)
            L_suiv = Loi(torch.cat([t_suiv[..., :net.n_suiv], net.suiv1r(h)], -1), torch.cat([ms, m1], -1))
        else:
            L_suiv = Loi(t_suiv[..., :net.n_suiv], ms)
        if tire:
            choix["suiveur"] = L_suiv.tirer()
        k = choix["suiveur"]
        if n1r:
            nouv = k >= net.n_suiv
            i1 = (k - net.n_suiv).clamp(0, n1r - 1)
            u1, a1 = _constantes_1r(o1r, dev)
            k0 = torch.where(nouv, torch.zeros_like(k), k)
            lv["suiveur_u"] = torch.where(nouv, u1[i1], torch.where(k0 > 0, (k0 - 1) % NS, -1)).float()
            lv["suiveur_tp1"] = (k0 > NS).float()
        else:
            lv["suiveur_u"] = torch.where(k > 0, (k - 1) % NS, -1).float()
            lv["suiveur_tp1"] = (k > NS).float()
        lv["suiveur_marge"] = marges[choix["marge"]] * A
        if SV.active_1r():                            # (réglage allumé : toutes les branches donnent ces deux clés)
            if n1r:
                lv["suiveur_1r"] = nouv.float()
                lv["suiveur_ag"] = torch.where(nouv, a1[i1] * A, torch.zeros_like(A))
            else:
                lv["suiveur_1r"] = torch.zeros_like(A)
                lv["suiveur_ag"] = torch.zeros_like(A)
    if not evaluer:
        return choix, None, None, None, None, lv
    # ---- probabilités : seuls les choix qui ont servi comptent
    w = s["slot"].float()
    o, lim, at = ouvre.float() * w, limite.float() * w, a_tp1.float()
    lp_base = (L_geste.log_prob(G) * w + lim * (L_ent.log_prob(choix["entree"]) + L_valid.log_prob(choix["validite"])))
    lp_exec = o * (L_stop.log_prob(choix["stop"]) + L_marge.log_prob(choix["marge"]) + L_dest.log_prob(choix["dest"])
                   + L_part.log_prob(choix["part"]) + at * L_tp1.log_prob(choix["tp1"])
                   + L_risque.log_prob(choix["risque"]))
    if L_suiv is not None:
        lp_exec = lp_exec + o * L_suiv.log_prob(choix["suiveur"])
    lp = lp_base.sum(-1) + lp_exec.sum(-1) + L_delai.log_prob(choix["delai"])
    hasard = (L_geste.hasard() * w + o * (L_stop.hasard() + L_dest.hasard() + L_marge.hasard() + L_part.hasard()
                                          + L_risque.hasard()) + lim * L_ent.hasard()).sum(-1)
    if L_suiv is not None:
        hasard = hasard + (o * L_suiv.hasard()).sum(-1)
    return choix, lp, lp_exec, hasard, valeur, lv
