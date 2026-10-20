"""PISTE « SMC_COMBINAISONS » — COLLAPSAR apprend quelles COMBINAISONS de concepts SMC marchent, sur les CRYPTOS
(16/10/2026). Demande du chef de projet : « les concepts il faut les MÉLANGER pour obtenir quelque chose, pas les prendre
séparément : un bloc d'ordres sans FVG, avec FVG, etc. ».

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (rien ne sera réglé après avoir vu le contrôle ou la confirmation).

1. Données
- BTCUSD et ETHUSD : bougies de 15 min Dukascopy (dm.charger). Autres cryptos : data/binance/<SYM>_M15.csv (heure du
  serveur = New York + 7 h, comme Dukascopy) ; les 7 premiers jours de chaque symbole sont ignorés (prix d'ouverture
  de cotation aberrants), bougies incohérentes retirées.
- Bougies M15, H1, H4, J1 fabriquées par collapsar.regarder.smc.bougies (horloge de New York, ATR 14).
- Groupes : liste des fichiers data/binance/*_M15.csv par ordre alphabétique, hors BTCUSDT et ETHUSDT ; groupe A =
  le 1er, le 3e, le 5e… ; groupe B = les autres.

2. Événements (définitions des concepts INCHANGÉES : collapsar/regarder/smc/noyaux.py et nono.py)
- Zones, en M15 et en H1 : bloc d'ordres (K.order_blocks), zone zones supply and demand (nono.zones_nono, version prudente), zone
  d'offre / demande (K.zones_offre_demande). Une zone vit de sa confirmation jusqu'à la 1re clôture au-delà de son bord
  opposé, ou 500 bougies.
- Événement = PREMIER contact du bord proche par le prix (dans le sens de la zone : achat sur une demande / un bloc
  haussier). Pas de minutes pour les cryptos : on entre AU MARCHÉ à la CLÔTURE de la bougie de contact (aucune
  ambiguïté sur l'ordre des prix dans cette bougie ; tout ce qui sert à décider est connu à cette clôture). Si cette
  bougie clôture au-delà du bord opposé, la zone est morte : pas d'événement.
- Plusieurs zones touchées par la même bougie, dans le même sens et la même unité = UN seul événement (les concepts se
  mélangent : il est à la fois bloc d'ordres, zone zones supply and demand, …) ; le stop est derrière la zone la plus éloignée.
- Stop = bord opposé -/+ 0,2 ATR de l'unité ; distance minimum = 0,2 x ATR journalier du dernier jour complet.
  Objectif = 2 R. Tenue maximum = 2 jours (48 h). Triple barrière vérifiée bougie par bougie à partir de la bougie
  suivante ; stop et objectif dans la même bougie = perte (prudence) ; trou de prix au-delà du stop = sortie au prix
  d'ouverture.
- Frais par aller-retour (part du prix) : BTC 0,03 %, ETH 0,05 %, autres cryptos 0,05 % ; plus un demi-frais de
  glissement à l'entrée (au marché) et un demi-frais sur chaque stop touché (règle du laboratoire SMC). Pas de frais
  de nuit comptés (tenue <= 2 jours ; limite connue : FTMO facture la nuit sur les cryptos, voir rapport).
- Étiquette = résultat en R après frais. Le « jumeau » = même entrée, même stop / objectif en distance, sens opposé.

3. Faits (tous connus à la clôture de la bougie de contact)
  type de zone (bloc d'ordres / zones supply and demand / offre-demande, cumulables), unité (M15 / H1), achat ou vente, FVG du départ
  (oui / non), FVG encore ouvert DANS la zone (taille en ATR, 0 si aucun), cassure qui a créé la zone (aucune / BOS /
  CHoCH), balayage de liquidité (plus haut / bas de la veille ou sommets égaux pris puis clôture revenue) : nombre de
  bougies depuis le dernier balayage dans le sens du trade (max 13) et balayage sur la bougie de contact, zone
  imbriquée dans une zone du même sens de l'unité supérieure (H1 pour M15, H4, J1) et profondeur (nombre d'unités
  supérieures), prix dans une zone OPPOSÉE d'une unité supérieure, âge de la zone (bougies), zone déjà testée (une zone
  plus ancienne du même sens qui la chevauche a déjà été touchée), position dans la jambe (0 = au plus bas du dernier
  couple sommet-creux confirmé pour un achat, 1 = au plus haut ; miroir pour une vente), tendance (sens de la dernière
  cassure de structure) de l'unité, de H4 et de J1, dans le sens du trade (+1) ou contre (-1), séance (Asie 19h-2h,
  Londres 2h-7h, New York 7h-12h, après-midi américain 12h-19h, heure de New York), week-end, largeur de la zone et
  distance du stop en ATR journalier, force de l'impulsion qui a quitté la zone (en ATR), rejet de la bougie de contact
  (où elle clôture dans son étendue), clôture au-delà du milieu de la zone, accord avec la cassure 24 h du moment (règle
  C2 figée de bitcoin_journee : +1 même sens, -1 sens contraire, 0 pas de position).

4. Apprentissage (UNE seule variante, réglages fixés ici)
- Arbres boostés peu profonds : sklearn HistGradientBoostingRegressor(max_depth=3, max_iter=300, learning_rate=0.03,
  min_samples_leaf=500, l2_regularization=1.0, early_stopping=False, random_state=0). Cible = R après frais, bornée à
  [-3 ; +3] pour l'apprentissage seulement.
- Données d'apprentissage : BTC + ETH + groupe A, événements entrés ET sortis avant le 01/01/2022.
- Règle : on ne prend que les événements à R prévu > 0 (seuil fixé d'avance), risque fixe 0,5 % du compte par trade,
  UNE position à la fois par marché (un événement arrivant pendant une position ouverte sur ce marché est ignoré).
- Le petit réseau de COLLAPSAR n'est PAS une variante de cette étude (il ne serait utile que si les arbres trouvent
  quelque chose ; ce serait une nouvelle étude).

5. Juge
- Contrôle : 2022-01-01 -> fin des données, BTC + ETH + groupe A (mêmes marchés, années jamais vues).
- Comparaisons obligatoires (mêmes marchés, même période, même règle « une position à la fois », même risque) :
  (a) TOUS les événements, (b) jumeau = les événements choisis avec un sens tiré à pile ou face (20 tirages),
  (c) la cassure 24 h seule (règle C2 de bitcoin_journee, taille = min(1, cible / agitation 14 j), cible 1 % / racine
  du nombre de marchés, mêmes frais).
- Force contre le jumeau, OFFICIELLE = par JOUR (les cryptos bougent ensemble : les trades d'un même jour ne sont pas
  indépendants) : somme par jour de (R - R inverse) / 2, moyenne / écart type x racine(nombre de jours). Seuil de
  preuve = max(3, racine(2 ln 1)) = 3. La force trade par trade est donnée pour information.
- Compte : gains journaliers (au jour de sortie) -> %/mois, baisse max, pire jour, challenges FTMO simulés
  (bande_bruit.challenge, départ tous les 10 jours) contre 20 jumeaux.
- Contrôle POSITIF = R moyen > 0 après frais ET gain du compte > 0 sur 2022-2026. Seulement alors : CONFIRMATION UNE
  fois sur le groupe B (toutes années, même modèle sans réapprentissage), verrou
  collapsar/vie/pistes/smc_combinaisons/confirmation.json (s'il existe, on ne recalcule jamais). Les années <= 2021 du
  groupe B sont contemporaines de l'apprentissage (les cryptos bougent ensemble) : la partie 2022-2026 de B est la seule
  vraiment neuve ; les deux sont données.
- Verdict : PROUVÉ = contrôle positif avec force (par jour) >= 3 ET confirmation B 2022-2026 avec R > 0 et force > 0 ;
  FAIBLE = contrôle positif sans cela ; INUTILE = contrôle négatif.
- Les 10 combinaisons préférées : un arbre simple (profondeur 5, feuilles >= 1 % des événements d'apprentissage) imite
  les prévisions du modèle sur l'apprentissage ; ses feuilles = des combinaisons de faits en mots ; les 10 feuilles au
  R prévu le plus haut, avec leur R moyen réel au contrôle (tous les événements de la feuille).

AVENANT 1 (16/10/2026 02h20, écrit AVANT tout résultat réel : seul un essai mécanique sur les années d'apprentissage
de BTC/ETH, faux découpage 2019/2020, a tourné ; aucun réglage n'en a été tiré)
- Filtre Binance (consigne commune) : 7 premiers jours ignorés ; bougie dont le bas < 0,5 x clôture ou le haut > 2 x
  clôture -> bas / haut ramenés à min / max(ouverture, clôture) ; le krach éclair réel du 10/10/2025 est gardé.
  MATIC et POL restent séparés. Groupes A / B calculés sur la liste FINALE des fichiers (LISEZMOI présent).
- FRAIS DE NUIT ajoutés (fidélité FTMO, plus prudent que le point 2) : chaque minuit serveur traversé entre l'entrée et
  la sortie coûte taux annuel / 360 x prix d'entrée (collapsar.mains.nuit.taux_nuit ; cryptos : 30 %/an des deux
  côtés, taux de la fiche). Le week-end compte en nuits calendaires (vendredi -> lundi = 3 nuits). Même règle pour le
  jumeau (son propre sens et sa propre sortie). Le R « sans nuit » est gardé pour information.
- SECOND GROUPE « or / indices / devises » (demande du chef de projet), MÊME méthode, mêmes faits, même modèle, même
  seuil, mais appris SÉPARÉMENT : données dm.charger ; frais = collapsar.mains.frais_ftmo.frais(sym, prix) (écart FTMO
  mesuré x MARGE_PRUDENCE (1,25 jusqu'au 16/10, 1 depuis l'audit)) + demi-frais d'entrée au marché + demi-frais sur stop + nuits. Les bougies du laboratoire SMC
  commencent en 2015 : apprentissage 2015-2021, contrôle 2022-2026.
  Apprentissage + contrôle : XAUUSD, USA500IDXUSD, USA30IDXUSD, DEUIDXEUR, EURUSD, USDJPY, AUDUSD, USDCHF, NZDUSD.
  Confirmation UNE fois (choisie avant) : USATECHIDXUSD, GBPUSD, USDCAD, XAGUSD, toutes années (et 2022-2026 à part),
  verrou collapsar/vie/pistes/smc_combinaisons/confirmation_classique.json, seulement si le contrôle est positif.
  Comparaisons (a), (b), (c) identiques (cassure 24 h : frais_ftmo au prix d'entrée, fermée le soir, pas de nuit).
  Fichiers : resultats_classique.json, modele_classique.pkl. Seuil de preuve : 3 pour chaque groupe (une variante
  chacun ; deux groupes rapportés séparément).

AVENANT 2 — ANNULÉ par le chef de projet avant tout calcul (remplacé par l'avenant 3) ; gardé pour la trace.
(16/10/2026 02h30) — LA TAILLE DU STOP
- Pour chaque événement, 4 stops minimum : 0,2 / 0,5 / 1,0 / 1,5 x ATR journalier (dernier jour complet) ; stop =
  max(derrière la zone, plancher) ; objectif toujours 2 R ; tenue max 2 jours (0,2 et 0,5) ou 5 jours (1,0 et 1,5) ;
  frais et nuits comme ci-dessus. Le fait « distance du stop » devient « distance du stop DERRIÈRE LA ZONE / ATR jour »
  (avant plancher) et un fait « plancher » (0,2 / 0,5 / 1,0 / 1,5) est ajouté.
- UN modèle par groupe (mêmes réglages) apprend sur les 4 versions de chaque événement (plancher = un fait) : il
  prédit le R de chacune. VARIANTES (liste fermée, 5 par groupe) : plancher IMPOSÉ 0,2 / 0,5 / 1,0 / 1,5 (événements à
  R prévu > 0 pour ce plancher) et CHOIX APPRIS (pour chaque événement, le plancher au R prévu le plus haut, pris s'il
  est > 0). Seuil = max(3, racine(2 ln 5)) = 3. La variante PRINCIPALE du verdict et de la porte de confirmation est
  le CHOIX APPRIS (choisie ici, avant) ; les 4 plancher imposés sont rapportés à côté, sans sélection a posteriori.
  (a) tous les événements et (b) le jumeau sont donnés pour chaque variante.
- Les combinaisons en mots incluent la taille du stop (l'arbre simple imite les 4 prévisions).

AVENANT 3 (16/10/2026 02h45, correction du chef de projet, écrit AVANT tout résultat réel) — LE STOP SE PLACE, IL NE
SE RÈGLE PAS. COLLAPSAR apprend OÙ placer le stop et OÙ viser, comme un trader. Remplace le point 2 « Stop / Objectif »
(entrée, tenue max 2 jours, triple barrière, frais, nuits, jumeau : inchangés).
- 6 EMPLACEMENTS de stop (tous connus à la clôture de la bougie de contact ; pour un achat, sous l'entrée ; miroir pour
  une vente), chacun + marge 0,1 x ATR de l'unité de la structure de référence :
  (1) derrière la zone (bord opposé ; unité de l'événement) ;
  (2) derrière le dernier creux (sommet pour une vente) confirmé M15 situé sous l'entrée (fractal 2, 300 derniers au
      plus) ; (3) idem H1 ; (4) idem H4 ;
  (5) derrière la liquidité la plus proche sous l'entrée : plus bas de la veille (jour de New York), plus bas du jour en
      cours jusqu'à la bougie de contact comprise, creux égaux actifs (définition B6 du laboratoire) ;
  (6) derrière le FVG : bord bas du plus grand FVG haussier ouvert qui chevauche la zone, s'il est sous l'entrée ;
      sinon derrière la bougie d'impulsion (plus bas des bougies entre la bougie de la zone et la confirmation).
  Emplacement valable seulement si la distance est entre 0,05 et 3 ATR journaliers ; sinon pas de R pour ce stop.
- 4 OBJECTIFS : (a) 2 R ; (b) prochaine liquidité au-dessus de l'entrée (plus haut de la veille, plus haut du jour en
  cours, sommets égaux actifs, 20 derniers sommets confirmés de l'unité de l'événement : le plus proche) ; (c) bord
  proche de la plus proche zone OPPOSÉE vivante de l'unité de l'événement (les 3 types) ; (d) le plus proche sommet H1
  confirmé au-dessus de l'entrée (200 derniers), comme sa stratégie. Pas d'objectif trouvé = pas de R pour ce couple.
- R de chacun des 24 couples (stop, objectif) sur le vrai chemin du prix (stop d'abord si les deux dans la même bougie),
  frais + glissements + nuits ; jumeau = sens opposé, mêmes distances.
- MODÈLE (mêmes réglages, un par groupe) : une ligne = (événement, couple) avec les faits + 4 faits du couple (type de
  stop, type d'objectif, distance du stop en ATR jour, objectif en R). Pour tenir en mémoire, l'apprentissage prend au
  plus 6 couples valables tirés au hasard par événement (graine 0). Il prédit le R de chaque couple.
- VARIANTES (liste fermée, 25 par groupe) : CHOIX APPRIS (PRINCIPALE : pour chaque événement le couple au R prévu le
  plus haut, pris s'il est > 0) + les 24 couples IMPOSÉS (événements à R prévu > 0 pour ce couple), rapportés pour
  information. Seuil = max(3, racine(2 ln 25)) = 3. (a) « tous les événements » est donné pour chaque couple imposé
  (repère de base : couple (1)+(a) = la règle d'origine). Le jumeau du choix appris garde le couple choisi.
- Rapport : emplacements préférés (couples choisis au contrôle, nombre et R moyen) et 10 combinaisons en mots
  (l'arbre simple imite les prévisions, type de stop et d'objectif compris).

AVENANT 4 (16/10/2026 03h00, gestion de sortie du chef de projet + témoin hasard, écrit AVANT tout résultat réel)
- 4 objectifs AJOUTÉS (8 au total, 6 x 8 = 48 couples) : GESTION 80/20. TP1 ferme 80 % ; TP1 candidats : (e) 1 R,
  (f) 1,5 R, (g) 2 R, (h) prochaine liquidité. Les 20 % restants visent la plus proche cible AU-DELÀ du TP1 parmi
  {zone opposée (c), prochaine liquidité (b), sommet H1 (d)} (s'il n'y en a pas : tout sort au TP1) ; après le TP1 leur
  stop passe au prix d'entrée, vérifié à partir de la bougie SUIVANTE ; fin de tenue (2 jours) : sortie au marché.
  Frais : entrée 1 frais (écart + glissement), chaque part sortie paie 0,5 frais (+ 0,5 si stop) ; nuits : part
  pleine jusqu'au TP1, 20 % ensuite.
- VARIANTES : choix appris (principale) + 48 couples imposés = 49 ; seuil max(3, racine(2 ln 49)) = 3.
- TÉMOIN HASARD (comme le laboratoire SMC, point D1) : pour chaque vraie zone, une fausse zone : même hauteur, même
  distance au prix (clôture de la bougie de confirmation -> bord proche), même sens, posée à une bougie tirée au hasard
  (graine fixée par marché et unité), puis EXACTEMENT la même chaîne (1er contact, 48 couples, faits de contexte
  recalculés ; faits de « naissance » de la zone — type, FVG du départ, cassure de création, impulsion, volume fort —
  copiés de la vraie zone : même description, mauvais endroit). Le MÊME modèle (appris sur les vraies zones) est
  appliqué aux témoins. Mesure CONTRE le témoin, au contrôle : R moyen et compte du choix appris sur vraies zones
  moins le même sur témoins, et (a) « tous les événements » vraies zones moins témoins, couple par couple. Le gain
  propre aux zones = cet écart ; s'il est nul, l'avantage éventuel vient du contexte et pas de la zone.

AVENANT 5 (16/10/2026, correction des frais crypto vérifiée sur ftmo.com par le coordinateur) — ÉCRIT APRÈS avoir vu
le contrôle crypto calculé avec les anciens frais (choix appris : -0,024 R, -2,6 %/mois, donc négatif). Commission FTMO
0,0325 % par côté depuis le 28/07/2025 en plus de l'écart : frais aller-retour BTC 0,083 %, ETH 0,112 %, autres
cryptos 0,12 % (glissement compris) ; on garde PAR PRUDENCE le demi-frais d'entrée au marché et le demi-frais sur stop
(même règle que pour l'or / indices / devises). Le modèle crypto est RÉAPPRIS avec ces frais (étiquettes changées), une
seule fois, mêmes réglages. C'est un 2e regard sur le même contrôle : si ce 2e calcul devenait positif alors que le
1er ne l'était pas, ce serait signalé comme suspect. L'ancien calcul est gardé pour information
(resultats_anciens_frais.json). Or / indices / devises : inchangé.

AVENANT 6 (16/10/2026, audit indépendant, défaut 5, ordre du chef de projet) : le « x 1,25 » est retiré des écarts
(frais_ftmo.MARGE_PRUDENCE = 1) et la commission crypto n'est plus multipliée (BTC 0,066 %, ETH 0,090 %, autres
0,096 %) ; le demi-frais d'entrée au marché est retiré (glissement réel mesuré nul, noyaux.GLISSEMENT_MARCHE = 0) ;
le demi-frais sur stop est GARDÉ (mesuré). Les résultats d'avant ce jour sont à rejuger.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.smc_combinaisons
    evenements|juger|confirmer [crypto|classique]
"""
from __future__ import annotations

import json
import math
import pickle
import sys
import zlib
from datetime import datetime

import numpy as np
import pandas as pd
from numba import njit

from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche
from collapsar.mains.frais_ftmo import MARGE_PRUDENCE, frais as frais_ftmo
from collapsar.mains.nuit import taux_nuit
from collapsar.regarder import bande_bruit as bb
from collapsar.regarder.pistes import bitcoin_journee as bj
from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.bougies import bougies
from collapsar.regarder.smc.multi import sommets_confirmes
from collapsar.regarder.smc.nono import zones_nono

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "smc_combinaisons"
BINANCE = dm.RACINE / "data" / "binance"
DUKASCOPY = ("BTCUSD", "ETHUSD")
# avenant 5 (anciens : 0,03 % / 0,05 %) ; 16/10 (audit, défaut 5) : commission FTMO 0,065 % aller-retour + écart
# (BTC 0,0012 %, ETH 0,0248 % relevés, autres 0,031 %), la marge de prudence ne touche que l'écart (avant :
# (commission + écart) x 1,25 = 0,083 / 0,112 / 0,12 %)
FRAIS_CRYPTO = {"BTCUSD": 0.00065 + 0.0000122 * MARGE_PRUDENCE, "ETHUSD": 0.00065 + 0.000248 * MARGE_PRUDENCE}
FRAIS_AUTRES = 0.00065 + 0.00031 * MARGE_PRUDENCE
NUIT_CRYPTO = 0.30
CLASSIQUE_APP = ["XAUUSD", "USA500IDXUSD", "USA30IDXUSD", "DEUIDXEUR", "EURUSD", "USDJPY", "AUDUSD", "USDCHF", "NZDUSD"]
CLASSIQUE_CONF = ["USATECHIDXUSD", "GBPUSD", "USDCAD", "XAGUSD"]
FIN_APPRENTISSAGE = pd.Timestamp("2022-01-01")
UNITES_EVT = ("M15", "H1")
SUP = {"M15": ("H1", "H4", "D1"), "H1": ("H4", "D1")}
VIE_ZONE = 500
MARGE = 0.1
STOP_MIN, STOP_MAX = 0.05, 3.0
TENUE_NS = 48 * 3600 * 10 ** 9
RISQUE = 0.005
SEUIL_PREVU = 0.0
SEUIL_FORCE = max(3.0, math.sqrt(2 * math.log(49)))
COUPLES_APP = 6
JOURS_LISTING = 7
JAMAIS = np.iinfo(np.int64).max // 4
UNITES = ("M15", "H1", "H4", "D1")
PARAMS = dict(max_depth=3, max_iter=300, learning_rate=0.03, min_samples_leaf=500, l2_regularization=1.0,
              early_stopping=False, random_state=0)
SEANCES = ["Asie", "Londres", "New York", "après-midi américain"]
STOPS = ["derrière la zone", "derrière le creux/sommet M15", "derrière le creux/sommet H1",
         "derrière le creux/sommet H4", "derrière la liquidité", "derrière le FVG/l'impulsion"]
OBJECTIFS = ["2 R", "prochaine liquidité", "zone opposée", "sommet/creux H1", "80/20 TP1 1 R", "80/20 TP1 1,5 R",
             "80/20 TP1 2 R", "80/20 TP1 liquidité"]
NO = len(OBJECTIFS)
NC = len(STOPS) * NO
JOUR_NS = 86400 * 10 ** 9
SEPT_H = 7 * 3600 * 10 ** 9
MIN_NS = 60 * 10 ** 9

FAITS = ["est_OB", "est_Nono", "est_OD", "unite_H1", "achat", "fvg_depart", "fvg_zone", "cassure_creation",
         "balayage_age", "balayage_contact", "dans_H1", "dans_H4", "dans_D1", "profondeur", "contre_sup", "age_zone",
         "deja_testee", "volume_fort", "position_jambe", "tendance_unite", "tendance_H4", "tendance_D1", "seance",
         "week_end", "largeur_atrj", "zone_risque_atrj", "impulsion", "rejet", "au_dela_milieu", "cassure24"]
FAITS_COUPLE = ["type_stop", "type_objectif", "stop_atrj", "objectif_R"]
FAITS_MODELE = FAITS + FAITS_COUPLE
PRINCIPALE = "choix appris"


def nom_couple(c: int) -> str:
    return f"stop {STOPS[c // NO]} + objectif {OBJECTIFS[c % NO]}"


def famille(nom: str) -> dict:
    if nom == "crypto":
        a, b = groupes()
        return {"nom": "crypto", "app": list(DUKASCOPY) + a, "conf": b, "suffixe": "",
                "verrou": "confirmation.json"}
    return {"nom": "classique", "app": CLASSIQUE_APP, "conf": CLASSIQUE_CONF, "suffixe": "_classique",
            "verrou": "confirmation_classique.json"}


# ---------------------------------------------------------------------- données
def groupes() -> tuple[list[str], list[str]]:
    syms = sorted(p.name[:-len("_M15.csv")] for p in BINANCE.glob("*_M15.csv"))
    autres = [s for s in syms if s not in ("BTCUSDT", "ETHUSDT")]
    return autres[0::2], autres[1::2]


def est_crypto(sym: str) -> bool:
    return sym in DUKASCOPY or sym.endswith("USDT")


def frais_de(sym: str, prix: np.ndarray) -> np.ndarray:
    if est_crypto(sym):
        return np.full(len(prix), FRAIS_CRYPTO.get(sym, FRAIS_AUTRES))
    return np.asarray(frais_ftmo(sym, prix), float) * np.ones(len(prix))


def nuits_de(sym: str, t_ny: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Taux annuels (achat, vente) payés par nuit / 360, à l'instant d'entrée."""
    if sym.endswith("USDT"):
        return np.full(len(t_ny), NUIT_CRYPTO), np.full(len(t_ny), NUIT_CRYPTO)
    a, v = taux_nuit(fiche(sym), pd.DatetimeIndex(t_ny))
    return np.asarray(a, float), np.asarray(v, float)


def m15(sym: str) -> pd.DataFrame:
    """Bougies de 15 min, heure du serveur (New York + 7 h)."""
    if sym.endswith("USDT"):
        df = pd.read_csv(BINANCE / f"{sym}_M15.csv", parse_dates=["time"])
        df = df[df["time"] >= df["time"].iloc[0] + pd.Timedelta(days=JOURS_LISTING)].copy()
        bas_c, haut_c = df[["open", "close"]].min(axis=1), df[["open", "close"]].max(axis=1)
        faux_bas, faux_haut = df["low"] < 0.5 * df["close"], df["high"] > 2 * df["close"]
        df.loc[faux_bas, "low"] = bas_c[faux_bas]
        df.loc[faux_haut, "high"] = haut_c[faux_haut]
    else:
        d = dm.charger(sym, pd.Timestamp("2100-01-01"))
        df = pd.DataFrame({"time": pd.to_datetime(d["time"]), "open": d["open"], "high": d["high"], "low": d["low"],
                           "close": d["close"], "volume": d["volume"].astype(float)})
    df["time"] = pd.to_datetime(df["time"]).astype("datetime64[ns]")     # pandas 3 lit les CSV en microsecondes
    df = df.dropna().sort_values("time", kind="stable").drop_duplicates("time")
    ok = ((df["low"] > 0) & (df["high"] >= df[["open", "close"]].max(axis=1)) &
          (df["low"] <= df[["open", "close"]].min(axis=1)))
    return df[ok].reset_index(drop=True)


def matrice_df(df: pd.DataFrame) -> dict:
    """Comme bitcoin_journee.matrice, mais à partir de n'importe quelles bougies de 15 min (heure serveur)."""
    t = df["time"]
    jour = t.dt.normalize()
    jours = pd.date_range(jour.min(), jour.max(), freq="D")
    i = ((jour - jours[0]).dt.days).to_numpy()
    k = (t.dt.hour * 4 + t.dt.minute // 15).to_numpy()
    O, H, L, C = (np.full((len(jours), 96), np.nan) for _ in range(4))
    for X, col in ((O, "open"), (H, "high"), (L, "low"), (C, "close")):
        X[i, k] = df[col].to_numpy()
    nb = np.isfinite(C).sum(1)
    valide = (jours.dayofweek < 5) & (nb >= bj.BARRES_MIN)
    Cf = pd.DataFrame(C).ffill(axis=1).to_numpy()
    prev = np.c_[np.full(len(jours), np.nan), Cf[:, :-1]]
    manque = ~np.isfinite(C)
    for X in (O, H, L):
        X[manque] = prev[manque]
    C[manque] = prev[manque]
    premier = pd.DataFrame(O).bfill(axis=1).to_numpy()[:, :1]
    for X in (O, H, L, C):
        X[:] = np.where(np.isfinite(X), X, premier)
    for X in (O, H, L, C):
        X[~valide] = np.nan
    return {"O": O, "H": H, "L": L, "C": C, "valide": valide, "jours": jours}


# ---------------------------------------------------------------------- calculs rapides
@njit(cache=True)
def fin_et_contact(zh, zb, zs, zc, h, l, c, vie):
    """Fin de vie (clôture au-delà du bord opposé, ou abandon) et 1er contact du bord proche (-1 si aucun)."""
    m, n = len(zc), len(c)
    fin = np.empty(m, np.int64)
    contact = np.full(m, -1, np.int64)
    for z in range(m):
        s = zs[z]
        proche = zh[z] if s > 0 else zb[z]
        loin = zb[z] if s > 0 else zh[z]
        f = zc[z] + 1 + vie
        for i in range(zc[z] + 1, min(n, zc[z] + 1 + vie)):
            if contact[z] < 0 and ((s > 0 and l[i] <= proche) or (s < 0 and h[i] >= proche)):
                contact[z] = i
            if (s > 0 and c[i] < loin) or (s < 0 and c[i] > loin):
                f = i
                break
        fin[z] = f
    return fin, contact


@njit(cache=True)
def faits_zones(zh, zb, zs, zc, zd, h, l, atr, fc, fs, cassure):
    """FVG dans le départ, cassure qui a créé la zone (1 BOS, 2 CHoCH), force de l'impulsion (ATR), bout de
    l'impulsion (plus bas des bougies après la bougie de zone jusqu'à la confirmation, plus haut pour une offre)."""
    m = len(zc)
    fvg, cas, imp, bout = np.zeros(m), np.zeros(m), np.zeros(m), np.full(m, np.nan)
    for z in range(m):
        s = zs[z]
        a = np.searchsorted(fc, zd[z], side="right")
        b = np.searchsorted(fc, zc[z], side="right")
        for k in range(a, b):
            if fs[k] == s:
                fvg[z] = 1.0
                break
        ext = -1e300 if s > 0 else 1e300
        bo = 1e300 if s > 0 else -1e300
        for k in range(zd[z] + 1, zc[z] + 1):
            if cassure[k] * s > 0:
                cas[z] = max(cas[z], abs(cassure[k]))
            ext = max(ext, h[k]) if s > 0 else min(ext, l[k])
            bo = min(bo, l[k]) if s > 0 else max(bo, h[k])
        if zc[z] > zd[z] and atr[zc[z]] > 0:
            imp[z] = ((ext - zh[z]) if s > 0 else (zb[z] - ext)) / atr[zc[z]]
            bout[z] = bo
    return fvg, cas, imp, bout


@njit(cache=True)
def fvg_dans_zone(ii, hh, bb_, ss, fh, fb, fs, fc, fcomble, atr, fenetre):
    """Plus grand FVG du même sens, confirmé, non comblé à la bougie de contact, qui chevauche la zone : (taille en
    ATR, bord arrière = bas pour un achat, haut pour une vente)."""
    e_ = len(ii)
    taille = np.zeros(e_)
    bord = np.full(e_, np.nan)
    for e in range(e_):
        i = ii[e]
        a = np.searchsorted(fc, i - fenetre)
        b = np.searchsorted(fc, i, side="right")
        for k in range(a, b):
            if fs[k] == ss[e] and fcomble[k] > i and fb[k] <= hh[e] and fh[k] >= bb_[e]:
                x = (fh[k] - fb[k]) / atr[i]
                if x > taille[e]:
                    taille[e] = x
                    bord[e] = fb[k] if ss[e] > 0 else fh[k]
    return taille, bord


@njit(cache=True)
def deja_testee(ii, hh, bb_, ss, kc, kh, kb, ks, fenetre):
    """Une zone plus ancienne du même sens, qui chevauche, a déjà été touchée avant la bougie de contact."""
    e_ = len(ii)
    out = np.zeros(e_)
    for e in range(e_):
        a = np.searchsorted(kc, ii[e] - fenetre)
        b = np.searchsorted(kc, ii[e])
        for k in range(a, b):
            if ks[k] == ss[e] and kb[k] <= hh[e] and kh[k] >= bb_[e]:
                out[e] = 1.0
                break
    return out


@njit(cache=True)
def contexte_sup(t_ev, hh, bb_, ss, px, uh, ub, us, ut_conf, ut_fin, fenetre):
    """Zone vivante du même sens d'une unité supérieure qui chevauche la zone ; zone opposée qui contient le prix."""
    e_ = len(t_ev)
    meme, contre = np.zeros(e_), np.zeros(e_)
    for e in range(e_):
        b = np.searchsorted(ut_conf, t_ev[e], side="right")
        a = np.searchsorted(ut_conf, t_ev[e] - fenetre)
        for z in range(a, b):
            if ut_fin[z] <= t_ev[e]:
                continue
            if us[z] == ss[e]:
                if ub[z] <= hh[e] and uh[z] >= bb_[e]:
                    meme[e] = 1.0
            elif ub[z] <= px[e] <= uh[z]:
                contre[e] = 1.0
    return meme, contre


@njit(cache=True)
def swing_derriere(t, entree, sens, s_px, s_t, s_ty, profondeur):
    """Dernier creux (achat) / sommet (vente) confirmé à l'instant t et situé derrière l'entrée."""
    out = np.full(len(t), np.nan)
    for e in range(len(t)):
        k = np.searchsorted(s_t, t[e], side="right") - 1
        vus = 0
        while k >= 0 and vus < profondeur:
            if s_ty[k] == -sens[e]:
                vus += 1
                if (entree[e] - s_px[k]) * sens[e] > 0:
                    out[e] = s_px[k]
                    break
            k -= 1
    return out


@njit(cache=True)
def swing_devant(t, entree, sens, s_px, s_t, s_ty, profondeur):
    """Le plus proche sommet (achat) / creux (vente) confirmé, devant l'entrée, parmi les `profondeur` derniers."""
    out = np.full(len(t), np.nan)
    for e in range(len(t)):
        k = np.searchsorted(s_t, t[e], side="right") - 1
        vus = 0
        best = 1e300
        while k >= 0 and vus < profondeur:
            if s_ty[k] == sens[e]:
                vus += 1
                d = (s_px[k] - entree[e]) * sens[e]
                if 0 < d < best:
                    best = d
                    out[e] = s_px[k]
            k -= 1
    return out


@njit(cache=True)
def zone_opposee(ii, entree, sens, zh, zb, zs, zc, zfin, fenetre):
    """Bord proche de la plus proche zone opposée vivante devant l'entrée (zones triées par confirmation)."""
    out = np.full(len(ii), np.nan)
    for e in range(len(ii)):
        a = np.searchsorted(zc, ii[e] - fenetre)
        b = np.searchsorted(zc, ii[e])
        best = 1e300
        for z in range(a, b):
            if zs[z] == -sens[e] and zfin[z] > ii[e]:
                bord = zb[z] if sens[e] > 0 else zh[z]
                d = (bord - entree[e]) * sens[e]
                if 0 < d < best:
                    best = d
                    out[e] = bord
    return out


@njit(cache=True)
def egaux_actifs(h, l, atr):
    """Niveaux de sommets / creux égaux encore actifs après chaque bougie (définition B6, comme K.structure)."""
    n = len(h)
    eqh, eql = np.full(n, np.nan), np.full(n, np.nan)
    sh, sl, eh, el = np.nan, np.nan, np.nan, np.nan
    for i in range(n):
        j = i - 2
        if j >= 2:
            if h[j] > h[j - 1] and h[j] > h[j - 2] and h[j] > h[j + 1] and h[j] > h[j + 2]:
                if not np.isnan(sh) and abs(h[j] - sh) <= 0.1 * atr[i]:
                    eh = max(h[j], sh)
                sh = h[j]
            if l[j] < l[j - 1] and l[j] < l[j - 2] and l[j] < l[j + 1] and l[j] < l[j + 2]:
                if not np.isnan(sl) and abs(l[j] - sl) <= 0.1 * atr[i]:
                    el = min(l[j], sl)
                sl = l[j]
        if not np.isnan(eh) and h[i] > eh:
            eh = np.nan
        if not np.isnan(el) and l[i] < el:
            el = np.nan
        eqh[i], eql[i] = eh, el
    return eqh, eql


@njit(cache=True)
def suivre(o, h, l, c, i, kmax, sens, entree, risque, gain, frais):
    """Triple barrière à partir de la bougie i+1 : (R après frais de trade, hors nuits ; bougie de sortie).
    Frais (16/10, audit défaut 5) : entrée au marché = demi-fiche + K.GLISSEMENT_MARCHE (0 : mesuré nul ; 0,5 avant),
    sortie = demi-fiche, + K.GLISSEMENT_STOP (0,5, mesuré) si le stop est touché."""
    stop = entree - sens * risque
    obj = entree + sens * gain
    ent = 0.5 + K.GLISSEMENT_MARCHE
    for k in range(i + 1, kmax + 1):
        if (sens > 0 and l[k] <= stop) or (sens < 0 and h[k] >= stop):
            px = min(stop, o[k]) if sens > 0 else max(stop, o[k])
            return ((px - entree) * sens - (ent + 0.5 + K.GLISSEMENT_STOP) * frais * entree) / risque, k
        if (sens > 0 and h[k] >= obj) or (sens < 0 and l[k] <= obj):
            px = max(obj, o[k]) if sens > 0 else min(obj, o[k])
            return ((px - entree) * sens - (ent + 0.5) * frais * entree) / risque, k
    return ((c[kmax] - entree) * sens - (ent + 0.5) * frais * entree) / risque, kmax


@njit(cache=True)
def suivre_8020(o, h, l, c, i, kmax, sens, entree, risque, tp1, run, frais):
    """Gestion 80/20 : (R après frais de trade, bougie du TP1 ou de la sortie totale, bougie de sortie finale).
    Entrée au marché : demi-fiche + K.GLISSEMENT_MARCHE (16/10 ; une fiche entière avant)."""
    stop = entree - sens * risque
    t1 = entree + sens * tp1
    a_run = np.isfinite(run) and run > tp1
    tr = entree + sens * run
    w1 = 0.8 if a_run else 1.0
    gain = 0.0
    cout = (0.5 + K.GLISSEMENT_MARCHE) * frais * entree
    for k in range(i + 1, kmax + 1):
        if (sens > 0 and l[k] <= stop) or (sens < 0 and h[k] >= stop):
            px = min(stop, o[k]) if sens > 0 else max(stop, o[k])
            return ((px - entree) * sens - cout - frais * entree) / risque, k, k
        if (sens > 0 and h[k] >= t1) or (sens < 0 and l[k] <= t1):
            px = max(t1, o[k]) if sens > 0 else min(t1, o[k])
            gain += w1 * (px - entree) * sens
            cout += w1 * 0.5 * frais * entree
            if not a_run:
                return (gain - cout) / risque, k, k
            for k2 in range(k + 1, kmax + 1):
                if (sens > 0 and l[k2] <= entree) or (sens < 0 and h[k2] >= entree):
                    px = min(entree, o[k2]) if sens > 0 else max(entree, o[k2])
                    return (gain + 0.2 * (px - entree) * sens - cout - 0.2 * frais * entree) / risque, k, k2
                if (sens > 0 and h[k2] >= tr) or (sens < 0 and l[k2] <= tr):
                    px = max(tr, o[k2]) if sens > 0 else min(tr, o[k2])
                    return (gain + 0.2 * (px - entree) * sens - cout - 0.1 * frais * entree) / risque, k, k2
            return (gain + 0.2 * (c[kmax] - entree) * sens - cout - 0.1 * frais * entree) / risque, k, kmax
    return ((c[kmax] - entree) * sens - cout - 0.5 * frais * entree) / risque, kmax, kmax


@njit(cache=True)
def suivre_couples(o, h, l, c, bt, duree, ii, kmax, ss, entree, risques, gains, run3, no, frais, taux_t, taux_i,
                   jour_e):
    """R (nuits comprises) du trade et du jumeau pour chaque événement x couple ; minutes jusqu'à la sortie finale.
    Objectifs 0-3 : sortie unique ; 4-7 : gestion 80/20 (gains = TP1, run3 = cibles possibles des 20 %)."""
    n, nc = gains.shape
    R = np.full((n, nc), np.nan, np.float32)
    Ri = np.full((n, nc), np.nan, np.float32)
    mn = np.zeros((n, nc), np.int16)
    J, S7 = 86400 * 10 ** 9, 7 * 3600 * 10 ** 9
    for e in range(n):
        for c_ in range(nc):
            s, g_ = c_ // no, c_ % no
            r, g = risques[e, s], gains[e, c_]
            if not (np.isfinite(r) and np.isfinite(g)) or r <= 0 or g <= 0:
                continue
            q = taux_t[e] / 360 * entree[e] / r
            qi = taux_i[e] / 360 * entree[e] / r
            if g_ < 4:
                x, k = suivre(o, h, l, c, ii[e], kmax[e], ss[e], entree[e], r, g, frais[e])
                xi, ki = suivre(o, h, l, c, ii[e], kmax[e], -ss[e], entree[e], r, g, frais[e])
                R[e, c_] = x - q * ((bt[k] + duree + S7) // J - jour_e[e])
                Ri[e, c_] = xi - qi * ((bt[ki] + duree + S7) // J - jour_e[e])
                k2 = k
            else:
                run = np.inf
                for v in run3[e]:
                    if np.isfinite(v) and g < v < run:
                        run = v
                if not np.isfinite(run):
                    run = np.nan
                x, k1, k2 = suivre_8020(o, h, l, c, ii[e], kmax[e], ss[e], entree[e], r, g, run, frais[e])
                xi, k1i, k2i = suivre_8020(o, h, l, c, ii[e], kmax[e], -ss[e], entree[e], r, g, run, frais[e])
                n1, n2 = (bt[k1] + duree + S7) // J - jour_e[e], (bt[k2] + duree + S7) // J - jour_e[e]
                n1i, n2i = (bt[k1i] + duree + S7) // J - jour_e[e], (bt[k2i] + duree + S7) // J - jour_e[e]
                R[e, c_] = x - q * (n1 if k1 == k2 else 0.8 * n1 + 0.2 * n2)
                Ri[e, c_] = xi - qi * (n1i if k1i == k2i else 0.8 * n1i + 0.2 * n2i)
            mn[e, c_] = (bt[k2] - bt[ii[e]]) // (60 * 10 ** 9)
    return R, Ri, mn


@njit(cache=True)
def une_position(marche, t, t_sortie):
    """Une position à la fois par marché (événements triés par heure)."""
    n = len(t)
    garde = np.zeros(n, np.bool_)
    libre = np.full(marche.max() + 1 if n else 1, np.iinfo(np.int64).min)
    for k in range(n):
        m = marche[k]
        if t[k] >= libre[m]:
            garde[k] = True
            libre[m] = t_sortie[k]
    return garde


# ---------------------------------------------------------------------- événements d'un marché
def _derniere(bt_fin, t):
    """Index de la dernière bougie close à l'instant t (ou -1)."""
    return np.searchsorted(bt_fin, t, "right") - 1


def _signe_ffill(cassure):
    s = np.sign(cassure).astype(float)
    s[s == 0] = np.nan
    return pd.Series(s).ffill().fillna(0.0).to_numpy()


def _zones(b):
    """Les trois types de zones d'une unité : (haut, bas, sens, confirmation, début, type 0 OB / 1 zones supply and demand / 2 OD)."""
    oh, ob, os_, oc, oj = K.order_blocks(b.o, b.h, b.l, b.c, b.atr)
    nh, nb, _, ns, nc = zones_nono(b.o, b.h, b.l, b.c)
    dh, db, ds, dc, dd, _ = K.zones_offre_demande(b.h, b.l, b.c, b.atr)
    zh = np.r_[oh, nh, dh]
    zb = np.r_[ob, nb, db]
    zs = np.r_[os_, ns, ds].astype(np.int64)
    zc = np.r_[oc, nc, dc].astype(np.int64)
    zd = np.r_[oj, nc - 1, dd].astype(np.int64)
    ty = np.r_[np.zeros(len(oc)), np.ones(len(nc)), np.full(len(dc), 2)].astype(np.int64)
    return zh, zb, zs, zc, zd, ty


def _cassure24(df: pd.DataFrame):
    """Positions de la cassure 24 h (règle C2 figée) : intervalles (début, fin) en heure serveur (ns), sens ; + trades."""
    m = matrice_df(df)
    agit = bj.agitation(m)
    liste = bj.var_C(m, 24)
    j0 = m["jours"].values.astype("datetime64[ns]").astype(np.int64)
    deb = np.array([j0[d] + a * MIN_NS for d, s, a, b_ in liste], np.int64)
    fin = np.array([j0[d] + b_ * MIN_NS for d, s, a, b_ in liste], np.int64)
    sens = np.array([s for d, s, a, b_ in liste], np.int64)
    o = np.argsort(deb)
    tr = bj.trades(m, liste, agit)
    tr["prix_e"] = [bj.prix(m, d, a) for d, a in zip(tr["d"], tr["m_entree"])]
    return deb[o], fin[o], sens[o], tr[["jour", "sens", "r_prix", "agitation", "prix_e"]]


def _swings(b):
    px, cf, ty = sommets_confirmes(b.h, b.l)
    return px, b.bt[cf] + b.duree, ty


def _atr_a(b, t):
    k = _derniere(b.bt + b.duree, t)
    return np.where(k >= 0, b.atr[np.maximum(k, 0)], np.nan)


def evenements_marche(sym: str, temoin: bool = False) -> pd.DataFrame:
    """`temoin` : les zones de l'unité de l'événement sont remplacées par des fausses zones (avenant 4)."""
    f = VIE / "cache_evenements" / f"{sym}{'_temoin' if temoin else ''}.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    t0 = datetime.now()
    df = m15(sym)
    m = pd.DataFrame({"ny": df["time"] - pd.Timedelta(hours=7), "open": df["open"], "high": df["high"],
                      "low": df["low"], "close": df["close"], "volume": df["volume"]})
    f_moy = float(np.mean(frais_de(sym, df["close"].to_numpy()[-10:])))
    B = {u: bougies(sym, u, pd.Timestamp("2100-01-01"), m, frais=f_moy, facteur_ouverture=1.0, volume_inclus=True)
         for u in UNITES}
    c24_deb, c24_fin, c24_sens, c24_tr = _cassure24(df)
    del df, m
    Zs, tend = {}, {}
    for u in ("H1", "H4", "D1"):
        b = B[u]
        zh, zb, zs, zc, zd, ty = _zones(b)
        fin, _ = fin_et_contact(zh, zb, zs, zc, b.h, b.l, b.c, VIE_ZONE)
        t_conf = b.bt[zc] + b.duree
        t_fin = np.where(fin < b.n, b.bt[np.minimum(fin, b.n - 1)] + b.duree, JAMAIS)
        o = np.argsort(t_conf, kind="stable")
        Zs[u] = (zh[o], zb[o], zs[o], t_conf[o], t_fin[o], (VIE_ZONE + 2) * b.duree)
        cas, _, _, _ = K.structure(b.h, b.l, b.c, b.atr)
        tend[u] = (b.bt + b.duree, _signe_ffill(cas))
    SW = {u: _swings(B[u]) for u in ("M15", "H1", "H4")}
    D = B["D1"]
    lignes = []
    for u in UNITES_EVT:
        b = B[u]
        cassure, _, eh, el = K.structure(b.h, b.l, b.c, b.atr)
        eqh, eql = egaux_actifs(b.h, b.l, b.atr)
        jours_u = pd.Series(b.jour)
        haut_jour = pd.Series(b.h).groupby(jours_u).cummax().to_numpy()
        bas_jour = pd.Series(b.l).groupby(jours_u).cummin().to_numpy()
        fh, fb, fs, fc, fcomble = K.fvgs(b.h, b.l, b.atr)
        fs = fs.astype(np.int64)
        zh, zb, zs, zc, zd, ty = _zones(b)
        fin, contact = fin_et_contact(zh, zb, zs, zc, b.h, b.l, b.c, VIE_ZONE)
        vf = K.volume_fort(zh, zb, zc, b.h, b.l, b.v, b.atr)
        fvgd, cas, imp, bout = faits_zones(zh, zb, zs, zc, zd, b.h, b.l, b.atr, fc, fs, cassure)
        oz = np.argsort(zc, kind="stable")                     # VRAIES zones triées (objectif « zone opposée »)
        zt = (zh[oz], zb[oz], zs[oz], zc[oz], fin[oz])
        if temoin:                                             # même boîte, même distance au prix, moment au hasard
            rng = np.random.default_rng(zlib.crc32(f"{sym}|{u}".encode()))
            r = rng.integers(300, b.n - 600, len(zc)).astype(np.int64)
            proche = np.where(zs > 0, zh, zb)
            dist = (b.c[zc] - proche) * zs
            larg = zh - zb
            p2 = b.c[r] - zs * dist
            zh, zb = np.where(zs > 0, p2, p2 + larg), np.where(zs > 0, p2 - larg, p2)
            zc, zd = r, r - 1
            fin, contact = fin_et_contact(zh, zb, zs, zc, b.h, b.l, b.c, VIE_ZONE)
            _, _, _, bout = faits_zones(zh, zb, zs, zc, zd, b.h, b.l, b.atr, fc, fs, cassure)
        tk = contact >= 0
        ok_k = np.argsort(contact[tk], kind="stable")
        kc, kh, kb, ks = contact[tk][ok_k], zh[tk][ok_k], zb[tk][ok_k], zs[tk][ok_k]
        ok = (contact >= 0) & (contact < fin)
        z = pd.DataFrame({"i": contact[ok], "sens": zs[ok], "haut": zh[ok], "bas": zb[ok], "ty": ty[ok],
                          "volume_fort": vf[ok].astype(float), "fvg_depart": fvgd[ok], "cassure_creation": cas[ok],
                          "impulsion": imp[ok], "age_zone": (contact - zc)[ok].astype(float),
                          "bout_or": -zs[ok] * bout[ok]})             # orienté : le max = le plus loin de l'entrée
        z["est_OB"], z["est_Nono"], z["est_OD"] = (z["ty"] == 0) * 1.0, (z["ty"] == 1) * 1.0, (z["ty"] == 2) * 1.0
        e = z.groupby(["i", "sens"], as_index=False).agg(
            haut=("haut", "max"), bas=("bas", "min"), est_OB=("est_OB", "max"), est_Nono=("est_Nono", "max"),
            est_OD=("est_OD", "max"), volume_fort=("volume_fort", "max"), fvg_depart=("fvg_depart", "max"),
            cassure_creation=("cassure_creation", "max"), impulsion=("impulsion", "max"), age_zone=("age_zone", "min"),
            bout_or=("bout_or", "max"))
        ii = e["i"].to_numpy(np.int64)
        ss = e["sens"].to_numpy(np.int64)
        t_close = b.bt[ii] + b.duree
        jd = _derniere(D.bt + D.duree, t_close)
        atr_j = np.where(jd >= 0, D.atr[np.maximum(jd, 0)], np.nan)
        garde = np.isfinite(atr_j) & (atr_j > 0) & (ii < b.n - 1)
        e = e[garde].reset_index(drop=True)
        ii, ss, t_close, atr_j = ii[garde], ss[garde], t_close[garde], atr_j[garde]
        hh, bb_ = e["haut"].to_numpy(), e["bas"].to_numpy()
        entree = b.c[ii]
        atr_u = b.atr[ii]
        # ---- les 6 emplacements de stop (prix), marge 0,1 ATR de l'unité de référence
        taille_fvg, bord_fvg = fvg_dans_zone(ii, hh, bb_, ss, fh, fb, fs, fc, fcomble, b.atr, 1000)
        loin = np.where(ss > 0, bb_, hh)
        st = np.full((len(ii), len(STOPS)), np.nan)
        st[:, 0] = loin - ss * MARGE * atr_u
        for k_, U in ((1, "M15"), (2, "H1"), (3, "H4")):
            px = swing_derriere(t_close, entree, ss, *SW[U], 300)
            st[:, k_] = px - ss * MARGE * _atr_a(B[U], t_close)
        cands_l = np.column_stack([np.where(b.bas_veille[ii] > 0, b.bas_veille[ii], np.nan), bas_jour[ii], eql[ii]])
        cands_h = np.column_stack([np.where(b.haut_veille[ii] > 0, b.haut_veille[ii], np.nan), haut_jour[ii], eqh[ii]])
        cands = np.where((ss > 0)[:, None], cands_l, cands_h)
        dist = (entree[:, None] - cands) * ss[:, None]
        dist = np.where(dist > 0, dist, np.nan)
        dmin = np.nanmin(np.where(np.isfinite(dist), dist, np.inf), axis=1)
        liq = np.where(np.isfinite(dmin), entree - ss * dmin, np.nan)
        st[:, 4] = liq - ss * MARGE * atr_u
        bout_px = -ss * e["bout_or"].to_numpy()
        fvg_ok = np.isfinite(bord_fvg) & ((entree - bord_fvg) * ss > 0)
        derr = np.where(fvg_ok, bord_fvg, np.where((entree - bout_px) * ss > 0, bout_px, np.nan))
        st[:, 5] = derr - ss * MARGE * atr_u
        risques = (entree[:, None] - st) * ss[:, None]
        valide = (risques >= STOP_MIN * atr_j[:, None]) & (risques <= STOP_MAX * atr_j[:, None])
        risques = np.where(valide, risques, np.nan)
        # ---- les 4 objectifs (distances devant l'entrée ; (a) dépend du stop)
        sw_u = swing_devant(t_close, entree, ss, *SW[u], 20)
        cands_obj = np.where((ss > 0)[:, None], cands_h, cands_l)
        cands_obj = np.column_stack([cands_obj, sw_u])
        d_ob = (cands_obj - entree[:, None]) * ss[:, None]
        d_ob = np.where(d_ob > 0, d_ob, np.inf).min(1)
        g_liq = np.where(np.isfinite(d_ob), d_ob, np.nan)
        g_zone = (zone_opposee(ii, entree, ss, *zt, VIE_ZONE) - entree) * ss
        g_h1 = (swing_devant(t_close, entree, ss, *SW["H1"], 200) - entree) * ss
        gains = np.full((len(ii), NC), np.nan)
        for s_ in range(len(STOPS)):
            r_ = risques[:, s_]
            for g_, val in enumerate((2.0 * r_, g_liq, g_zone, g_h1, 1.0 * r_, 1.5 * r_, 2.0 * r_, g_liq)):
                gains[:, s_ * NO + g_] = val
        run3 = np.ascontiguousarray(np.column_stack([g_zone, g_liq, g_h1]))
        fr = frais_de(sym, entree)
        t_ny = b.t[ii]
        na, nv = nuits_de(sym, t_ny)
        taux_t, taux_i = np.where(ss > 0, na, nv), np.where(ss > 0, nv, na)
        jour_e = (t_close + SEPT_H) // JOUR_NS
        kmax = np.maximum(np.searchsorted(b.bt, t_close + TENUE_NS - b.duree, "right") - 1, ii + 1)
        kmax = np.minimum(kmax, b.n - 1)
        R, Ri, mn = suivre_couples(b.o, b.h, b.l, b.c, b.bt, b.duree, ii, kmax, ss, entree,
                                   np.ascontiguousarray(risques), np.ascontiguousarray(gains), run3, NO, fr, taux_t,
                                   taux_i, jour_e)
        cols = {}
        for c_ in range(NC):
            cols[f"R_{c_:02d}"] = R[:, c_]
            cols[f"Ri_{c_:02d}"] = Ri[:, c_]
            cols[f"mn_{c_:02d}"] = mn[:, c_]
            cols[f"ob_{c_:02d}"] = (gains[:, c_] / risques[:, c_ // NO]).astype(np.float32)
        e = pd.concat([e, pd.DataFrame(cols)], axis=1)
        for s_ in range(len(STOPS)):
            e[f"sa_{s_}"] = (risques[:, s_] / atr_j).astype(np.float32)
            e[f"cout_{s_}"] = (1.5 * fr * entree / risques[:, s_]).astype(np.float32)
            e[f"stop_{s_}"] = (risques[:, s_] / entree * 100).astype(np.float32)
        # ---- faits de contexte
        e["fvg_zone"] = taille_fvg
        bull = ((b.bas_veille > 0) & (b.l < b.bas_veille) & (b.c > b.bas_veille)) | \
            (b.c > np.nan_to_num(el, nan=np.inf))
        bear = ((b.haut_veille > 0) & (b.h > b.haut_veille) & (b.c < b.haut_veille)) | \
            (b.c < np.nan_to_num(eh, nan=-np.inf))
        idx = np.arange(b.n)
        der_bull = np.maximum.accumulate(np.where(bull, idx, -10 ** 9))
        der_bear = np.maximum.accumulate(np.where(bear, idx, -10 ** 9))
        age_b = np.where(ss > 0, ii - der_bull[ii], ii - der_bear[ii])
        e["balayage_age"] = np.minimum(age_b, 13).astype(float)
        e["balayage_contact"] = (age_b == 0) * 1.0
        e["deja_testee"] = deja_testee(ii, hh, bb_, ss, kc, kh, kb, ks, VIE_ZONE)
        prof = np.zeros(len(ii))
        contre = np.zeros(len(ii))
        for U in ("H1", "H4", "D1"):
            if U not in SUP[u]:
                e[f"dans_{U}"] = np.nan
                continue
            uh, ub, us, ut_conf, ut_fin, fen = Zs[U]
            meme, ctr = contexte_sup(t_close, hh, bb_, ss, entree, uh, ub, us, ut_conf, ut_fin, fen)
            e[f"dans_{U}"] = meme
            prof += meme
            contre = np.maximum(contre, ctr)
        e["profondeur"] = prof
        e["contre_sup"] = contre
        s_px, s_cf, s_ty = sommets_confirmes(b.h, b.l)
        hi, lo = np.full(b.n, np.nan), np.full(b.n, np.nan)
        hi[s_cf[s_ty == 1]] = s_px[s_ty == 1]
        lo[s_cf[s_ty == -1]] = s_px[s_ty == -1]
        hi, lo = pd.Series(hi).ffill().to_numpy()[ii], pd.Series(lo).ffill().to_numpy()[ii]
        pos = np.where(hi > lo, (entree - lo) / np.where(hi > lo, hi - lo, 1.0), np.nan)
        e["position_jambe"] = np.clip(np.where(ss > 0, pos, 1 - pos), -1, 2)
        e["tendance_unite"] = _signe_ffill(cassure)[ii] * ss
        for U in ("H4", "D1"):
            fin_u, sg = tend[U]
            k = _derniere(fin_u, t_close)
            e[f"tendance_{U}"] = np.where(k >= 0, sg[np.maximum(k, 0)], 0.0) * ss
        hny = b.minute[ii] // 60
        e["seance"] = np.select([(hny >= 19) | (hny < 2), hny < 7, hny < 12], [0, 1, 2], 3).astype(float)
        e["week_end"] = (pd.DatetimeIndex(t_ny).dayofweek >= 5) * 1.0
        e["largeur_atrj"] = (hh - bb_) / atr_j
        e["zone_risque_atrj"] = (entree - loin) * ss / atr_j
        rg = b.h[ii] - b.l[ii]
        rej = np.where(rg > 0, (b.c[ii] - b.l[ii]) / np.where(rg > 0, rg, 1.0), 0.5)
        e["rejet"] = np.where(ss > 0, rej, 1 - rej)
        e["au_dela_milieu"] = ((entree - (hh + bb_) / 2) * ss < 0) * 1.0
        t_srv = t_close + SEPT_H
        k = np.searchsorted(c24_deb, t_srv, "right") - 1
        etat = np.where((k >= 0) & (t_srv < c24_fin[np.maximum(k, 0)]), c24_sens[np.maximum(k, 0)], 0)
        e["cassure24"] = (etat * ss).astype(float)
        e["unite_H1"] = 1.0 if u == "H1" else 0.0
        e["achat"] = (ss > 0) * 1.0
        e["marche"] = sym
        e["unite"] = u
        e["t"] = pd.to_datetime(t_close)
        lignes.append(e.drop(columns=["i", "haut", "bas", "sens", "bout_or"]))
    ev = pd.concat(lignes, ignore_index=True).sort_values("t", kind="stable").reset_index(drop=True)
    for col in FAITS:
        ev[col] = ev[col].astype(np.float32)
    c24_tr["frais"] = frais_de(sym, c24_tr["prix_e"].to_numpy())
    c24_tr["marche"] = sym
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(pickle.dumps(ev))
    if not temoin:
        (VIE / "cache_evenements" / f"{sym}_cassure24.pkl").write_bytes(pickle.dumps(c24_tr))
    R = ev[[f"R_{c:02d}" for c in range(NC)]].to_numpy(float)
    print(f"{sym} : {len(ev)} événements ; couples valables {np.isfinite(R).mean() * 100:.0f} % ; "
          f"({(datetime.now() - t0).seconds} s)", flush=True)
    return ev


# ---------------------------------------------------------------------- juge
def vue(ev: pd.DataFrame, choix: np.ndarray) -> pd.DataFrame:
    """Les événements avec le couple choisi (index 0-23) : colonnes R, R_inverse, t_sortie, coûts."""
    out = ev[["marche", "unite", "t", "achat"]].copy()
    r = np.arange(len(ev))
    for nom, pre in (("R", "R_"), ("R_inverse", "Ri_"), ("mn", "mn_"), ("objectif_R", "ob_")):
        M = ev[[f"{pre}{c:02d}" for c in range(NC)]].to_numpy()
        out[nom] = M[r, choix]
    for nom, pre in (("cout_R", "cout_"), ("stop_pct", "stop_"), ("stop_atrj", "sa_")):
        M = ev[[f"{pre}{s}" for s in range(len(STOPS))]].to_numpy(float)
        out[nom] = M[r, choix // NO]
    out["t_sortie"] = out["t"] + pd.to_timedelta(out["mn"].astype(np.int64), unit="min")
    out["couple"] = choix
    return out[np.isfinite(out["R"].to_numpy(float))]


def _journalier(t: pd.DataFrame, r: np.ndarray, de, a) -> pd.Series:
    jours = pd.date_range(pd.Timestamp(de).normalize(), pd.Timestamp(a).normalize() - pd.Timedelta(days=1), freq="D")
    g = pd.Series(RISQUE * r, index=pd.to_datetime(t["t_sortie"]).dt.normalize()).groupby(level=0).sum()
    return g.reindex(jours, fill_value=0.0)


def _compte(j: pd.Series) -> dict:
    courbe = j.cumsum()
    ch = bb.challenge(j)
    return {"pct_mois": float(j.mean() * 30.44 * 100), "baisse_max_pct": float((courbe - courbe.cummax()).min() * 100),
            "pire_jour_pct": float(j.min() * 100), "reussis_pct": ch["reussis_pct"], "morts_pct": ch["morts_pct"],
            "regularite": float(j.mean() / j.std() * math.sqrt(365)) if j.std() > 0 else 0.0}


def bilan(t: pd.DataFrame, de, a, jumeaux: bool = True, court: bool = False) -> dict:
    """t : événements gardés (une position à la fois déjà appliquée)."""
    n = len(t)
    if n < 20:
        return {"trades": n}
    r, ri = t["R"].to_numpy(float), t["R_inverse"].to_numpy(float)
    d = (r - ri) / 2
    dj = pd.Series(d, index=pd.to_datetime(t["t"]).dt.normalize()).groupby(level=0).sum()
    x = {"trades": n, "R_moyen": float(r.mean()), "gagnants_pct": float((r > 0).mean() * 100),
         "force_jour": float(dj.mean() / dj.std(ddof=1) * math.sqrt(len(dj))) if dj.std() > 0 else 0.0}
    x["compte"] = _compte(_journalier(t, r, de, a))
    if court:
        return x
    x.update({"achats_pct": float(t["achat"].mean() * 100), "cout_R": float(t["cout_R"].mean()),
              "stop_pct_prix": float(t["stop_pct"].mean()), "stop_atrj": float(t["stop_atrj"].mean()),
              "objectif_R_moyen": float(np.nanmean(t["objectif_R"].astype(float))),
              "duree_h_moy": float(t["mn"].mean() / 60),
              "force_trade": float(d.mean() / d.std(ddof=1) * math.sqrt(n)) if d.std() > 0 else 0.0})
    if jumeaux:
        rng = np.random.default_rng(7)
        js = []
        for _ in range(20):
            rr = np.where(rng.random(n) < 0.5, r, ri)
            js.append((rr.mean(), _compte(_journalier(t, rr, de, a))))
        x["jumeau"] = {"R_moyen": float(np.mean([a_ for a_, _ in js])),
                       "pct_mois": float(np.mean([c["pct_mois"] for _, c in js])),
                       "reussis_pct": float(np.mean([c["reussis_pct"] for _, c in js])),
                       "morts_pct": float(np.mean([c["morts_pct"] for _, c in js]))}
    return x


def cassure_seule(marches: list[str], de, a) -> dict:
    parts = [pickle.loads((VIE / "cache_evenements" / f"{s}_cassure24.pkl").read_bytes()) for s in marches
             if (VIE / "cache_evenements" / f"{s}_cassure24.pkl").exists()]
    t = pd.concat(parts, ignore_index=True)
    t = t[(t["jour"] >= pd.Timestamp(de)) & (t["jour"] < pd.Timestamp(a))]
    if len(t) < 20:
        return {"trades": int(len(t))}
    cible = 0.01 / math.sqrt(len(marches))
    expo = np.minimum(1.0, cible / t["agitation"])
    g = expo * (t["sens"] * t["r_prix"] - t["frais"])
    jours = pd.date_range(pd.Timestamp(de).normalize(), pd.Timestamp(a).normalize() - pd.Timedelta(days=1), freq="D")
    j = g.groupby(t["jour"]).sum().reindex(jours, fill_value=0.0)
    x = {"trades": int(len(t)), "brut_moyen_pct": float((t["sens"] * t["r_prix"]).mean() * 100),
         "frais_moyen_pct": float(t["frais"].mean() * 100)}
    x["compte"] = _compte(j)
    return x


def _charger(marches, temoin: bool = False, depuis=None):
    ev = []
    for sym in marches:
        try:
            e = evenements_marche(sym, temoin)
        except Exception as x:                      # noqa: BLE001
            print(f"{sym} ignoré : {type(x).__name__}: {x}", flush=True)
            continue
        ev.append(e if depuis is None else e[e["t"] >= depuis])
    return pd.concat(ev, ignore_index=True).sort_values("t", kind="stable").reset_index(drop=True)


def _une_position(t: pd.DataFrame) -> pd.DataFrame:
    t = t.sort_values("t", kind="stable")
    codes = pd.factorize(t["marche"])[0].astype(np.int64)
    ns = lambda x: x.values.astype("datetime64[ns]").astype(np.int64)      # 16/10 : toujours en ns (audit, défaut 1)
    g = une_position(codes, ns(t["t"]), ns(t["t_sortie"]))
    return t[g]


def _tableaux(ev: pd.DataFrame) -> tuple:
    return (ev[FAITS].to_numpy(np.float32), ev[[f"ob_{c:02d}" for c in range(NC)]].to_numpy(np.float32),
            ev[[f"sa_{s}" for s in range(len(STOPS))]].to_numpy(np.float32))


def _lignes(T: tuple, couples: np.ndarray, evts: np.ndarray) -> np.ndarray:
    """Matrice du modèle pour des paires (événement, couple) ; T = _tableaux(ev)."""
    X, OB, SA = T
    return np.c_[X[evts], (couples // NO).astype(np.float32), (couples % NO).astype(np.float32),
                 SA[evts, couples // NO], OB[evts, couples]]


def _prevoir(mod, ev: pd.DataFrame, paquet: int = 20000) -> np.ndarray:
    """Matrice (événements x couples) des R prévus ; -inf pour un couple sans R."""
    R = ev[[f"R_{c:02d}" for c in range(NC)]].to_numpy(np.float32)
    T = _tableaux(ev)
    P = np.full((len(ev), NC), -np.inf, np.float32)
    for a in range(0, len(ev), paquet):
        b_ = min(len(ev), a + paquet)
        e_, c_ = np.nonzero(np.isfinite(R[a:b_]))
        if len(e_):
            P[a + e_, c_] = mod.predict(_lignes(T, c_, a + e_))
    return P


def evaluer(ev: pd.DataFrame, P: np.ndarray, de, a, marches) -> dict:
    """Variante principale (choix appris) + 24 couples imposés + (a) tous + (b) jumeau + (c) cassure 24 h."""
    res = {}
    best = P.argmax(1)
    v = vue(ev, best)
    res["choix appris"] = {"choisis (R prévu > 0)": bilan(_une_position(v[P.max(1)[v.index] > SEUIL_PREVU]), de, a)}
    ch = _une_position(v[P.max(1)[v.index] > SEUIL_PREVU])
    res["choix appris"]["couples choisis"] = {nom_couple(int(c)): {"trades": len(g), "R_moyen": float(g["R"].mean())}
                                             for c, g in ch.groupby("couple")}
    for c in range(NC):
        v = vue(ev, np.full(len(ev), c))
        res[nom_couple(c)] = {"choisis (R prévu > 0)": bilan(_une_position(v[P[v.index, c] > SEUIL_PREVU]), de, a,
                                                             jumeaux=False, court=True),
                              "(a) tous les événements": bilan(_une_position(v), de, a, jumeaux=False, court=True)}
    res["(c) cassure 24 h seule"] = cassure_seule(marches, de, a)
    return res


def _contre_temoin(vrai: dict, tem: dict) -> dict:
    """Écarts vraies zones - témoins (R moyen, %/mois), pour le choix appris et chaque couple imposé / tous."""
    def ecart(a, b):
        return {"vraies_trades": a.get("trades"), "temoin_trades": b.get("trades"),
                "vraies_R": a.get("R_moyen"), "temoin_R": b.get("R_moyen"),
                "ecart_R": (a["R_moyen"] - b["R_moyen"]) if "R_moyen" in a and "R_moyen" in b else None,
                "vraies_pct_mois": a.get("compte", {}).get("pct_mois"),
                "temoin_pct_mois": b.get("compte", {}).get("pct_mois")}
    out = {PRINCIPALE: ecart(vrai[PRINCIPALE]["choisis (R prévu > 0)"], tem[PRINCIPALE]["choisis (R prévu > 0)"])}
    for c in range(NC):
        k = nom_couple(c)
        out[k] = {s: ecart(vrai[k][s], tem[k][s]) for s in ("choisis (R prévu > 0)", "(a) tous les événements")}
    return out


def _imprimer(per: str, r: dict):
    print(per, flush=True)
    c = r["choix appris"]["choisis (R prévu > 0)"]
    print(f"  CHOIX APPRIS : {c.get('trades')} trades, R {c.get('R_moyen', float('nan')):+.3f}, force jour "
          f"{c.get('force_jour', float('nan')):+.2f}, compte {c.get('compte', {}).get('pct_mois', float('nan')):+.2f} "
          f"%/mois, jumeau {c.get('jumeau', {}).get('pct_mois', float('nan')):+.2f}", flush=True)
    for k in (nom_couple(0),):
        for s in ("choisis (R prévu > 0)", "(a) tous les événements"):
            x = r[k][s]
            print(f"  {k} | {s}: {x.get('trades')} trades, R {x.get('R_moyen', float('nan')):+.3f}", flush=True)
    x = r["(c) cassure 24 h seule"]
    print(f"  cassure 24 h : {x.get('compte', {}).get('pct_mois', float('nan')):+.2f} %/mois", flush=True)


# ---------------------------------------------------------------------- l'arbre « en mots »
def _mots(f: str, lo: float, hi: float) -> str | None:
    binaires = {"est_OB": "bloc d'ordres", "est_Nono": "zone zones supply and demand", "est_OD": "zone d'offre/demande",
                "unite_H1": "unité H1", "achat": "achat", "fvg_depart": "FVG dans le départ",
                "balayage_contact": "balayage sur la bougie de contact", "dans_H1": "dans une zone H1",
                "dans_H4": "dans une zone H4", "dans_D1": "dans une zone journalière",
                "contre_sup": "prix dans une zone opposée supérieure", "deja_testee": "zone déjà testée",
                "volume_fort": "volume fort", "week_end": "week-end", "au_dela_milieu": "clôture au-delà du milieu"}
    contraires = {"unite_H1": "unité M15", "achat": "vente", "dans_H1": "hors zone H1", "dans_H4": "hors zone H4",
                  "dans_D1": "hors zone journalière", "contre_sup": "pas de zone opposée supérieure",
                  "deja_testee": "zone jamais testée", "au_dela_milieu": "clôture en deçà du milieu",
                  "balayage_contact": "pas de balayage sur la bougie de contact"}
    if f in binaires:
        if lo >= 0.5:
            return binaires[f]
        if hi <= 0.5:
            return contraires.get(f, "sans " + binaires[f])
        return None
    if f == "type_stop":
        s = [STOPS[k] for k in range(len(STOPS)) if lo < k <= hi]
        return None if len(s) == len(STOPS) else "stop " + " ou ".join(s)
    if f == "type_objectif":
        s = [OBJECTIFS[k] for k in range(len(OBJECTIFS)) if lo < k <= hi]
        return None if len(s) == len(OBJECTIFS) else "objectif " + " ou ".join(s)
    if f == "seance":
        s = [SEANCES[k] for k in range(4) if lo < k <= hi]
        return None if len(s) == 4 else "séance " + " ou ".join(s)
    if f in ("tendance_unite", "tendance_H4", "tendance_D1", "cassure24"):
        noms = {-1: "contre", 0: "neutre", 1: "avec"}
        s = [noms[k] for k in (-1, 0, 1) if lo < k <= hi]
        lib = {"tendance_unite": "tendance de l'unité", "tendance_H4": "tendance H4", "tendance_D1": "tendance J1",
               "cassure24": "cassure 24 h"}[f]
        return None if len(s) == 3 else f"{lib} : " + " ou ".join(s)
    if f == "cassure_creation":
        noms = {0: "sans cassure", 1: "BOS", 2: "CHoCH"}
        s = [noms[k] for k in (0, 1, 2) if lo < k <= hi]
        return None if len(s) == 3 else "création : " + " ou ".join(s)
    lib = {"fvg_zone": "FVG ouvert dans la zone (ATR)", "balayage_age": "bougies depuis le balayage",
           "profondeur": "profondeur gigogne", "age_zone": "âge de la zone (bougies)",
           "position_jambe": "position dans la jambe (0 = discount)", "largeur_atrj": "largeur de zone / ATR jour",
           "zone_risque_atrj": "distance entrée-zone / ATR jour", "impulsion": "impulsion (ATR)",
           "rejet": "rejet de la bougie (1 = fort)", "stop_atrj": "stop / ATR jour",
           "objectif_R": "objectif (en R)"}[f]
    if lo == -np.inf:
        return f"{lib} <= {hi:.2f}"
    if hi == np.inf:
        return f"{lib} > {lo:.2f}"
    return f"{lib} entre {lo:.2f} et {hi:.2f}"


def feuilles_en_mots(arbre, noms) -> dict:
    tr = arbre.tree_
    out = {}

    def visite(nd, bornes):
        if tr.children_left[nd] < 0:
            mots = [m for f, (lo, hi) in bornes.items() if (m := _mots(f, lo, hi))]
            out[nd] = " + ".join(mots) if mots else "(tout)"
            return
        f, s = noms[tr.feature[nd]], tr.threshold[nd]
        lo, hi = bornes.get(f, (-np.inf, np.inf))
        visite(tr.children_left[nd], {**bornes, f: (lo, min(hi, s))})
        visite(tr.children_right[nd], {**bornes, f: (max(lo, s), hi)})
    visite(0, {})
    return out


# ---------------------------------------------------------------------- phases
def evenements(nom: str = "crypto"):
    F = famille(nom)
    for sym in F["app"]:
        for tem in (False, True):
            try:
                evenements_marche(sym, tem)
            except Exception as e:                      # noqa: BLE001
                print(f"{sym} {'témoin ' if tem else ''}ignoré : {type(e).__name__}: {e}", flush=True)


def juger(nom: str = "crypto"):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.tree import DecisionTreeRegressor
    F = famille(nom)
    marches = F["app"]
    ev = _charger(marches)
    mn_max = ev[[f"mn_{c:02d}" for c in range(NC)]].max(axis=1).to_numpy()
    t_fin_max = ev["t"] + pd.to_timedelta(mn_max, unit="min")
    fin = t_fin_max.max().normalize() + pd.Timedelta(days=1)
    app = ev[((ev["t"] < FIN_APPRENTISSAGE) & (t_fin_max < FIN_APPRENTISSAGE)).to_numpy()].reset_index(drop=True)
    ctl = ev[(ev["t"] >= FIN_APPRENTISSAGE).to_numpy()].reset_index(drop=True)
    del ev
    # lignes d'apprentissage : au plus 6 couples valables par événement, tirés au hasard (graine 0)
    Ra = app[[f"R_{c:02d}" for c in range(NC)]].to_numpy(np.float32)
    rng = np.random.default_rng(0)
    cle = np.where(np.isfinite(Ra), rng.random(Ra.shape), np.inf)
    rang = np.argsort(cle, axis=1)[:, :COUPLES_APP]
    evts = np.repeat(np.arange(len(app)), COUPLES_APP)
    couples = rang.ravel()
    garde = np.isfinite(Ra[evts, couples])
    evts, couples = evts[garde], couples[garde]
    X = _lignes(_tableaux(app), couples, evts)
    y = np.clip(Ra[evts, couples].astype(float), -3, 3)
    print(f"apprentissage : {len(app)} événements, {len(X)} lignes ; contrôle : {len(ctl)} événements", flush=True)
    mod = HistGradientBoostingRegressor(**PARAMS).fit(X, y)
    (VIE / f"modele{F['suffixe']}.pkl").write_bytes(pickle.dumps(mod))
    Pa, Pc = _prevoir(mod, app), _prevoir(mod, ctl)
    de0 = app["t"].min().normalize()
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "famille": nom, "marches": marches,
              "evenements": {"apprentissage": len(app), "controle": len(ctl), "lignes_apprentissage": len(X)},
              "periodes": {}}
    for per, t, P, de, a_ in (("apprentissage <= 2021", app, Pa, de0, FIN_APPRENTISSAGE),
                              ("contrôle 2022-2026", ctl, Pc, FIN_APPRENTISSAGE, fin)):
        sortie["periodes"][per] = evaluer(t, P, de, a_, marches)
        _imprimer(per, sortie["periodes"][per])
    best = Pc.argmax(1)
    v = vue(ctl, best)
    ch = _une_position(v[Pc.max(1)[v.index] > SEUIL_PREVU])
    sortie["controle_par_annee"] = {int(k): {"trades": len(g), "R_moyen": float(g["R"].mean())}
                                    for k, g in ch.groupby(ch["t"].dt.year)}
    sortie["controle_par_marche"] = {k: {"trades": len(g), "R_moyen": float(g["R"].mean())}
                                     for k, g in ch.groupby("marche")}
    sortie["controle_par_unite"] = {k: {"trades": len(g), "R_moyen": float(g["R"].mean())}
                                    for k, g in ch.groupby("unite")}
    # concepts seuls (aucune sélection), avec le couple d'origine (zone + 2 R) : repère
    seuls = {}
    for lib, masque in (("tous", ctl["achat"] >= 0), ("bloc d'ordres", ctl["est_OB"] > 0),
                        ("zone zones supply and demand", ctl["est_Nono"] > 0), ("offre/demande", ctl["est_OD"] > 0),
                        ("avec FVG ouvert dans la zone", ctl["fvg_zone"] > 0),
                        ("avec balayage (<= 3 bougies)", ctl["balayage_age"] <= 3),
                        ("dans une zone H4", ctl["dans_H4"] > 0),
                        ("dans le sens de la cassure 24 h", ctl["cassure24"] > 0)):
        g = ctl[masque.to_numpy()]
        r_, ri_ = g["R_00"].astype(float), g["Ri_00"].astype(float)
        ok = np.isfinite(r_)
        d = ((r_ - ri_) / 2)[ok]
        seuls[lib] = {"evenements": int(ok.sum()), "R_moyen": float(r_[ok].mean()),
                      "force_trade": float(d.mean() / d.std() * math.sqrt(len(d))) if len(d) > 2 else None}
    sortie["controle_concepts_seuls_zone_2R"] = seuls
    # les combinaisons préférées : l'arbre simple imite les prévisions sur les lignes d'apprentissage
    pa_l = Pa[evts, couples]
    arbre = DecisionTreeRegressor(max_depth=5, min_samples_leaf=max(200, len(X) // 100), random_state=0)
    arbre.fit(X, pa_l)
    mots = feuilles_en_mots(arbre, FAITS_MODELE)
    Rc = ctl[[f"R_{c:02d}" for c in range(NC)]].to_numpy(np.float32)
    Ric = ctl[[f"Ri_{c:02d}" for c in range(NC)]].to_numpy(np.float32)
    ec, cc = np.nonzero(np.isfinite(Rc))
    fa = arbre.apply(X)
    Tc = _tableaux(ctl)
    fc_ = np.concatenate([arbre.apply(_lignes(Tc, cc[a:a + 200000], ec[a:a + 200000]))
                          for a in range(0, len(ec), 200000)])
    del Tc
    yc, yci = Rc[ec, cc].astype(float), Ric[ec, cc].astype(float)
    combos = []
    for nd, txt in mots.items():
        sa, sc = fa == nd, fc_ == nd
        dd = (yc[sc] - yci[sc]) / 2
        combos.append({"combinaison": txt, "R_prevu": float(pa_l[sa].mean()), "R_apprentissage": float(y[sa].mean()),
                       "lignes_app": int(sa.sum()), "lignes_controle": int(sc.sum()),
                       "R_controle": float(yc[sc].mean()) if sc.any() else None,
                       "force_controle": float(dd.mean() / dd.std() * math.sqrt(len(dd))) if sc.sum() > 2 else None})
    combos.sort(key=lambda c: -c["R_prevu"])
    sortie["combinaisons"] = combos
    sortie["imitation_arbre_simple"] = float(np.corrcoef(arbre.predict(X), pa_l)[0, 1])
    del app, X, y, Pa, Rc, Ric, ec, cc, fc_, fa, yc, yci
    # le témoin hasard au contrôle : mêmes règles, même modèle, fausses zones
    tem = _charger(marches, temoin=True, depuis=FIN_APPRENTISSAGE)
    rt = evaluer(tem, _prevoir(mod, tem), FIN_APPRENTISSAGE, fin, marches)
    sortie["temoin_evenements_controle"] = len(tem)
    del tem
    sortie["temoin_controle"] = rt
    sortie["contre_temoin"] = _contre_temoin(sortie["periodes"]["contrôle 2022-2026"], rt)
    print("contre le témoin :", json.dumps(sortie["contre_temoin"][PRINCIPALE], ensure_ascii=False), flush=True)
    c = sortie["periodes"]["contrôle 2022-2026"][PRINCIPALE]["choisis (R prévu > 0)"]
    positif = c.get("R_moyen", -1) > 0 and c.get("compte", {}).get("pct_mois", -1) > 0
    sortie["controle_positif"] = bool(positif)
    sortie["ouvrir_confirmation"] = bool(positif)
    (VIE / f"resultats{F['suffixe']}.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=float),
                                                      encoding="utf-8")
    print("contrôle positif (choix appris) :", positif)
    for cmb in combos[:10]:
        print(f"{cmb['R_prevu']:+.3f} prévu | contrôle {cmb['R_controle']} ({cmb['lignes_controle']}) | "
              f"{cmb['combinaison']}")


def confirmer(nom: str = "crypto"):
    F = famille(nom)
    verrou = VIE / F["verrou"]
    if verrou.exists():
        print("Confirmation DÉJÀ faite :", verrou.read_text(encoding="utf-8")[:2000])
        return
    res = json.loads((VIE / f"resultats{F['suffixe']}.json").read_text(encoding="utf-8"))
    if not res.get("ouvrir_confirmation"):
        print("Contrôle non positif : la confirmation reste fermée.")
        return
    mod = pickle.loads((VIE / f"modele{F['suffixe']}.pkl").read_bytes())
    ev = _charger(F["conf"])
    P = _prevoir(mod, ev)
    fin = ev["t"].max().normalize() + pd.Timedelta(days=3)
    de0 = ev["t"].min().normalize()
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "famille": nom, "marches": F["conf"],
              "periodes": {}}
    for per, de, a_ in (("toutes années", de0, fin), ("<= 2021", de0, FIN_APPRENTISSAGE),
                        ("2022-2026 (neuf)", FIN_APPRENTISSAGE, fin)):
        sel = ((ev["t"] >= de) & (ev["t"] < a_)).to_numpy()
        sortie["periodes"][per] = evaluer(ev[sel].reset_index(drop=True), P[sel], de, a_, F["conf"])
        _imprimer(per, sortie["periodes"][per])
    del ev
    tem = _charger(F["conf"], temoin=True, depuis=FIN_APPRENTISSAGE)
    rt = evaluer(tem, _prevoir(mod, tem), FIN_APPRENTISSAGE, fin, F["conf"])
    del tem
    sortie["temoin_2022_2026"] = rt
    sortie["contre_temoin_2022_2026"] = _contre_temoin(sortie["periodes"]["2022-2026 (neuf)"], rt)
    print("contre le témoin :", json.dumps(sortie["contre_temoin_2022_2026"][PRINCIPALE], ensure_ascii=False))
    neuf = sortie["periodes"]["2022-2026 (neuf)"][PRINCIPALE]["choisis (R prévu > 0)"]
    c = res["periodes"]["contrôle 2022-2026"][PRINCIPALE]["choisis (R prévu > 0)"]
    sortie["prouve"] = bool(c.get("force_jour", 0) >= SEUIL_FORCE and neuf.get("R_moyen", -1) > 0
                            and neuf.get("force_jour", -1) > 0)
    verrou.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("PROUVÉ :", sortie["prouve"])


if __name__ == "__main__":
    VIE.mkdir(parents=True, exist_ok=True)
    action = sys.argv[1] if len(sys.argv) > 1 else "evenements"
    if action == "un":
        evenements_marche(sys.argv[2], len(sys.argv) > 3 and sys.argv[3] == "temoin")
    else:
        {"evenements": evenements, "juger": juger, "confirmer": confirmer}[action](
            sys.argv[2] if len(sys.argv) > 2 else "crypto")
