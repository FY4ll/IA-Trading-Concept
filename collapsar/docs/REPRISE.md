# COLLAPSAR — fiche de reprise (écrite le 14/10/2026 vers 17h30, avant effacement du contexte)

## ÉTAT AU 16/10 SOIR — à lire en premier (carte des dossiers : `docs/CARTE.md`)
- **Juge réparé** (audit `vie/audit/rapport.md`, programmes `audit/`) : A = heures (µs lues comme ns -> zones
  confirmées des mois trop tard ; corrigé dans `donnees/` et `regarder/smc/bougies.py`) ; B = notes (force pondérée par
  la taille, challenges comptés parmi les TERMINÉS, séances trouées écartées, -5 % jugé au pire point du jour) ; C = frais sans le « x 1,25 », nuits selon la table FTMO (achat /
  vente, triple le vendredi pour indices / énergie / crypto), levier du compte Swing mesuré. Calculs de base justes.
- **Zones du chef, juge corrigé** (`vie/pistes/verdict_zones_corrige/rapport.md`, 71 lignes) : une seule ligne tient
  sur les 3 périodes = cryptos, ANCIENNE traduction, départ H4 : **+0,22 R/trade, force 2,5** (< 3), compte FTMO
  +0,3 %/mois à 0,25 %. Son indicateur traduit fidèlement et sa pratique gigogne (D1/H4/H1, stop minimum) **ne gagnent
  nulle part après frais** (+0,09 à -0,30 R). Années toutes déjà vues.
- **Nouvelle note de COLLAPSAR** (`vie/note_collapsar_corrigee/rapport.md`) : +0,1 à +0,2 %/mois grâce aux nuits moins
  chères ; **aucun avantage prouvé** sur le hasard (force 1,7 au mieux). Meilleure : école crypto n° 2.
- **Nouvelle école « de la précision » EN CONSTRUCTION** (autre agent ; `vie/ecole_precision/`) : zones dans les
  zones, stop placé derrière une structure, 1 000 générations prévues.
- **Rangement fait** : 16 pistes réfutées + 11 expériences des 13-15/10 -> `archives/2026-10-16_pistes/` ; arbres 1 et 3,
  essais, anciens avis, vieux résultats -> `archives/2026-10-16_vie/` (manifestes dedans, rien d'effacé).
  Les chemins cités plus bas pour ces pistes sont donc dans l'archive.

## ⚠️ PASSATION 15/10/2026 23h30 — À LIRE EN PREMIER
**Le chef de projet a mis fin à la session, très énervé** (« tu commences sérieusement à me péter les c… »). Causes
probables : trop de questions et de longues explications, enchaînement de tests tous négatifs sans solution concrète,
lenteur. **À la prochaine session : réponses COURTES, agir au lieu de demander, apporter des solutions et pas seulement
des verdicts, ne jamais lui faire la morale sur le hasard plus d'une fois.**

**Ce qui tourne (rien d'arrêté) :**
- École des mille mondes (`ecole.lancer_mondes --sans-controle`, repartie du meilleur élève, garde-fou anti-dérive),
  contrôleur (`ecole.controleur_mondes`, choix prudent du meilleur élève), démo en direct (`direct.blanc`) qui
  RECOPIE ses positions et ses ordres limite sur le compte démo Tradeco (`direct/tradeco.py`, mode
  `vie/direct/mode.json`), collecteurs gTrade / Ostium, préapprentissage sur la masse (`maitres.lancer_masse`).
  MetaTrader est sur Tradeco (plus sur l'essai FTMO). Gardien : relance démo et collecteurs.

**Ce qui a été fait le 15/10 (détails plus bas) :** maîtres (Ostium, persistance du talent), corrections de l'école
(taille des ordres non exécutés, garde-fou), démo Tradeco réelle (ordres limite, réveils, alertes, 4 h max), piste
ORB (NO-GO), laboratoire SMC (rien de prouvé), méthode multi-unités, indicateur du chef de projet indicateur de zones d'offre et de demande (supply and demand)
traduit à l'identique (`regarder/smc/zones supply and demand.py`), zones gigognes (`regarder/smc/gigogne.py`), stop minimum,
évaluation 2024-2026 de SA stratégie : NÉGATIVE (-0,27 R sur 4 marchés, -0,34 R sur 45). Rapport
`reports/Laboratoire SMC.md`. Définitions figées et empreintes : `docs/SMC_*.md`, `docs/CASCADE_ZONES.md`,
`vie/smc/empreinte_definitions.txt`. Archives avant travaux : `archives/collapsar_avant_ORB_*.zip`,
`archives/collapsar_avant_SMC_*.zip`.

**Interrompu au moment de l'arrêt :** le chef de projet avait demandé « tu checkes les deux [filtre de tendance de
fond + étude de la réaction des zones] et tu explores les possibilités autour ; c'est une stratégie qui gagne, j'étais
à 55 % de ROI ». Seule la restructuration de `gigogne.py` était faite (fonctions `preparer` / `entrees`, vérifiée :
mêmes trades). Le filtre de tendance et l'étude de réaction ne sont PAS lancés. La période 2024-2026 a déjà servi pour
sa stratégie : le seul juge neuf restant est le direct (signaux sur son téléphone, 3 mois ou 100 trades).

**15/10 23h30 (nouvelle session) — filtre de tendance de fond sur SA stratégie FAIT** (`regarder/smc/filtre_tendance.py`,
`vie/smc/filtre_tendance_strategie_chef.csv`) : trades de « Gigogne H4 stop A plancher 0.2 » gardés seulement dans le
sens de la tendance 20 / 60 / 120 j ou des 3 d'accord : AUCUN filtre n'aide (dans le sens de la tendance c'est même
pire : 4 marchés minute -0,43 à -0,84 R ; 45 marchés -0,03 à +0,21 R puis -0,28 à -0,47 R sur 2024-2026). Ses zones
marchent plutôt CONTRE la tendance (retour en arrière), sans gain net après frais. Préapprentissage sur la masse des
maîtres (`maitres.lancer_masse`, lancé 17h24) BLOQUÉ depuis 17h46 (10 Go envoyés sur le disque, aucun progrès ;
sens équilibré 0,50-0,57 = rien) : arrêt refusé par la sécurité, à faire par le chef de projet.

**16/10 nuit — RECHERCHE « day traders qui en vivent » FAITE** (ordre du chef de projet : « manger des connaissances »,
les traders Ostium ne sont PAS une référence) : `collapsar/reports/Recherche daytrading rentable.md`, notes
`research_notes/Recherche daytrading rentable/`. 5 pistes classées : 1 bouclier de volatilité (stops/taille sur
l'agitation), 2 tendance de fond + entrée/sortie libres dans la journée, 3 chasseur de journées de tendance (bande de
bruit horaire, indices + or, stop suiveur, filtre de second avis), 4 horloge des flux (fin de séance, fixings, fin de
mois, or Asie/Occident), 5 mille mondes calqués sur les lois réelles.
**16/10 nuit — PISTE 3+1 TESTÉE** (`regarder/bande_bruit.py`, méthode publiée Zarattini-Aziz-Barbon 2024, réglages du
papier, prix moyen de séance au lieu du VWAP faute de volume ; `regarder/second_avis.py`) : US500, NAS100, or à la
minute 9h30-16h NY, frais fiche FTMO x 1,25. Défaut corrigé en cours (regard de 15h59 manquant -> gagnants oubliés).
AVANT FRAIS, avantage réel du sens (compte 3 marchés : force +2,7 sur 2015-2021, +3,9 sur 2022-2023) ; après frais :
+0,00 %/mois (2015-21), +0,91 %/mois baisse max 4 % et 44 % de challenges réussis à cible 2 % contre 5 % aux jumeaux
(2022-23) ; PÉRIODE CACHÉE 2024-2026 (UNE fois, verrou `vie/bande_bruit/cachee.json`) : -0,26 %/mois, brut ~0
(S&P et or), Nasdaq +0,15. Second avis (arbres boostés, appris 2015-21) : n'aide pas en 2022-23 ni en 2024-26. Leçon :
les journées de tendance existent (premier avantage intraday AVANT frais mesuré du projet) mais 1 trade/jour/marché
paie trop de frais -> s'en servir comme MOMENT d'entrée d'une position plus longue (piste 2), pas comme trade seul.

**16/10 — 5 CHERCHEURS-TESTEURS LANCÉS EN PARALLÈLE** (ordre : « trouve quelque chose qui peut marcher, quitte à être
hors DA COLLAPSAR ») : brief commun `docs/BRIEF_PISTES.md` (frais, nuit, juge à jumeau, 2010-21 / 2022-23 / cachée
2024-26 une fois). Pistes : `tendance_timing`, `indices_creux`, `paires_valeur`, `calendrier_horaires`,
`ingenierie_challenge` ; code `regarder/pistes/`, résultats et rapports `vie/pistes/<piste>/rapport.md`.

**16/10 — RÉSULTATS DES 5 PISTES** (rapports `vie/pistes/<piste>/rapport.md`) : tendance_timing MORTE (frais de nuit FTMO
3-13 %/an > gain) ; paires_valeur MORTE (petit retour à la moyenne des croisées +0,1 %/mois seulement) ; calendrier :
tout mort SAUF « l'or monte en Asie » (entrée 19h NY, sortie 8h Londres) : force 2,9 (2010-21), 1,4 (2022-23) et
3,45 sur années VIERGES 2004-2009 (+0,75 %/mois) ; indices_creux : achat des creux Connors réel mais crashs simultanés ;
ingenierie_challenge : seule brique solide = achat des creux indices US (force 4,5 / 1,5 / 3,4 sur 2024-26 cachée) ;
compte combiné espérance challenge -359 € (cachée). FRAIS : `mains/frais_ftmo.py` (écart FTMO mesuré en points, ramené
au prix de l'époque) : indices US ~2 x moins chers que la fiche aujourd'hui, plus chers avant 2020. Bande de bruit avec
ces frais : toujours morte (-0,25 %/mois 2024-26). **ALERTE DONNÉES : l'or (Kaggle, minute ET 15 min) est à NY + 6 h
avant 06/2011 (pas + 7) -> ajouter 1 h.** En cours : `creux_v2` (achat des creux 9 indices, taille plafonnée au niveau du
compte, frais FTMO) et ouverture unique de 2024-26 pour l'or en Asie.

**16/10 nuit (carte blanche) — suite :** creux_v2 (9 indices, taille au niveau du compte, frais FTMO) : +0,18 / -0,05 /
+0,22 %/mois (cachée ouverte), challenges = jumeaux -> MORT. Or en Asie, entrée 19h figée après correction d'heure :
mort après frais (cachée NON ouverte). Bande de bruit sur 7 indices jamais testés (`regarder/pistes/bande_monde.py`) :
rien même avant frais -> l'élan intraday n'est pas général. École des mondes : séance de 6 h finie à 23h50 (leçon 803),
toujours ~0 contre le hasard ; non relancée. Préapprentissage maîtres : disparu (mémoire libérée). Piste structurelle
en cours : la CRYPTO (écart FTMO / agitation ~20 x plus faible que les autres marchés) : `bitcoin_journee` (dans la
journée, fermé avant minuit) et `crypto_tendance` (tendance plusieurs jours, nuits 30 %/an comprises).

**16/10 ~01h — PREMIER CANDIDAT QUI TIENT : CASSURE 24 H DU BITCOIN DANS LA JOURNÉE** (`regarder/pistes/bitcoin_journee.py`
variante C2, `regarder/pistes/bitcoin_cassure.py`) : à chaque heure pleine lun-ven, clôture de l'heure > plus haut des
24 h précédentes -> achat (< plus bas -> vente), sortie au retour au milieu du canal ou 23h45 serveur (aucune nuit),
exposition = min(1, 1 % / agitation 14 j), arrêt de la journée à -3 %. 2017-21 +1,84 %/mois, 2022-23 +1,93 (frais
0,01 %) ; PÉRIODE CACHÉE 2024-26 (ouverte une fois, verrou `vie/pistes/bitcoin_cassure/cachee.json`) : +1,11 %/mois
(0,01 %), +0,95 (0,03 %), +0,42 (0,1 %) ; challenges réussis 71 % / morts 17 % contre jumeaux 10 / 51 % ; force pesée
2,10 (seuil 2,04 pour 8 variantes, < 3) ; 2025 négatif (-0,3 %/mois), gain concentré sur les meilleurs jours.
Choisie APRÈS avoir vu 2017-2023 parmi 8 variantes -> la cachée est le seul juge neuf, et maintenant le direct.
**DÉMO RÉELLE TRADECO LANCÉE 16/10 00h43** : `collapsar/direct/bitcoin_cassure.py` (numéro magique 16102027, messages
téléphone à chaque trade, journal `vie/logs/bitcoin_cassure.txt`, trades `vie/direct/bitcoin_cassure_trades.csv`,
arrêt volontaire `vie/direct/BITCOIN_ARRET`), surveillé par le gardien. Écart BTC Tradeco ~30 $ (0,036 %) = scénario
très prudent. À FAIRE : relever l'écart BTC réel chez FTMO aux heures pleines.

**16/10 matin — CONSIGNES DU CHEF DE PROJET (à respecter)** : logique de trader AVANT les chiffres ; les concepts se
MÉLANGENT (bloc d'ordres avec/sans FVG, BOS, balayage, zones gigognes…) ; le stop se PLACE derrière une structure
(« 100 pips » = ordre d'idée) et COLLAPSAR doit APPRENDRE où ; ce qui compte = le prix ENTRE dans la zone et il y a une
RÉACTION (pas forcément au milieu) ; sortie : TP1 = 80 % de la position, 20 % jusqu'à la zone suivante ou TP2 ; pour
lui les lignes de tendance / cassures sont dépassées, sa méthode offre/demande + OB + FVG est meilleure : ne jamais la
présenter comme remplacée. En cours : `smc_combinaisons` (COLLAPSAR apprend combinaisons + placement stop/TP1 80/20,
cryptos ET or/indices/devises, contre témoin hasard), `chef_crypto` (sa stratégie sur cryptos), `cassure_collapsar`
(n°7). Mesure zones (`regarder/pistes/zones_milieu.py`) : réaction 38 % dans ses zones contre 39 % pour une fausse zone
à même distance du prix à un moment au hasard ; ses zones tournent moins profond (0,77 contre 0,92) et ~+0,1 R. (Un
premier témoin mal placé avait donné « 5 x plus » : corrigé devant lui.) Cassure v3 (développement) : +1,48 %/mois
BTC+ETH, challenges 88 % / 0 % morts, groupe B NON ouvert.

**16/10 nuit (2h30) — verdicts** : n°7 COLLAPSAR décide la taille de la cassure : REJETÉ (accord prévision/réel -> 0
au contrôle). CONFIRMATION groupe B de la cassure v3 (ouverte une fois, `vie/cassure_v3/confirmation.json`) : ÉCHEC sur
les autres cryptos (note -0,16 ; 2017-21 +0,23 ; 2022-26 -0,57 ; BNB seul bon avant 2022) -> l'effet de cassure est
propre au BTC (et ETH), pas une loi des cryptos ; la démo BTC reste le juge. STRATÉGIE DU CHEF sur cryptos
(`regarder/pistes/chef_crypto.py`) : sa version figée V1 positive sur groupe A (+0,29 R, 463 trades) ET CONFIRMÉE sur
groupe B jamais vu (+0,26 R, 403 trades, force 1,9, challenges 58 % / 33 % contre jumeaux 16 / 70) ; profil suiveur de
tendance (gain sur quelques gros trades) ; BTC/ETH Binance 7j/7 négatifs (-0,19 R) ; baisse max 16 % à 0,5 %/trade ->
taille à réduire. Mise en démo Tradeco de sa stratégie (BTC/ETH, 0,25 %, magique 16102028) : `direct/chef_zones.py`
(agent en cours). École COLLAPSAR sur cryptos (carte graphique) et recherche conditions FTMO crypto : en cours.

**16/10 03h — CORRECTION MAJEURE DES FRAIS CRYPTO** : FTMO prend 0,0325 % PAR CÔTÉ de commission sur les cryptos depuis
le 28/07/2025 (vérifié sur ftmo.com) -> ~0,08 % (BTC) / ~0,11 % (ETH) par aller-retour avec glissement, et non 0,0015 % :
l'argument « crypto 20 x moins chère » était FAUX (rapportée à l'agitation, la crypto FTMO est même plus chère que les
indices US). `mains/frais_ftmo.py` corrigé (commission crypto). Cassure C2 avec vrais frais : BTC +1,42 / +1,46 / +0,53
%/mois (2017-21 / 22-23 / 24-26), ETH +0,94 / +0,38 / +0,51 : toujours positive, divisée par ~2 récemment. Démo
Tradeco (écart ~0,036 %, sans commission) = plus favorable que FTMO. FTMO : 32 cryptos (liste dans
`research_notes/FTMO conditions crypto/notes.md`), levier 1:3,3 (Normal) / 1:1 (Swing), plafond 400 000 $ par
stratégie, plan de croissance seulement si >= +10 % en 4 mois ; revenus : +1 %/mois sur 400 k$ à 80 % = 3 200 $/mois.

**16/10 03h30** : cassure C2 sur indices (bon nombre de jours, BARRES_MIN 76) : négative même avant frais -> effet
propre au BTC/ETH. Stratégie du chef sur cryptos AVEC commission FTMO (0,12 % alts) : groupe A +0,22 R, groupe B
(jamais vu) +0,18 R (avant 2022 +0,19, après +0,18) -> résiste aux vrais frais (stops larges, frais 0,13 R). En cours :
`chef_compte_ftmo` (compte FTMO toutes cryptos FTMO, 0,25 %/trade, 4 positions max, gestion 80/20 en information).

**16/10 04h — smc_combinaisons fini** (`regarder/pistes/smc_combinaisons.py`, rapport `vie/pistes/smc_combinaisons/`) :
COLLAPSAR a appris sur des centaines de milliers de contacts de zones (31 faits, 6 emplacements de stop, 8 sorties dont
80/20) : AUCUNE combinaison ne gagne au contrôle 2022-2026 (cryptos -0,018 R ; or/indices/devises +0,012 R, force 2,4,
surtout des achats en hausse de fond ; confirmation négative). Les concepts (FVG, BOS, balayage, H4, zones supply and demand) ne changent
presque rien ; seul l'éloignement du stop (creux H1/H4) réduit les pertes. Zones réelles vs fausses : +0,01 à +0,025 R.
CONTRASTE : le SYSTÈME COMPLET du chef (V1 gigogne H4, entrée au milieu de la plus petite zone, sorties par tiers
jusqu'à la zone opposée) reste positif sur cryptos (+0,18 R jamais vues) : son avantage vient des gros trades qui
COURENT (profil suiveur de tendance), pas du contact de zone lui-même.

**16/10 04h30 — chef_compte_ftmo** : V1 du chef sur 19 cryptos FTMO, 0,25 %/trade, 4 positions, frais FTMO réels :
+0,19 R/trade (802 trades, force 2,5) mais compte +0,15 %/mois (6,6 trades/mois), baisse max 12 %, challenges 36 %
réussis / 0 % morts (jumeaux 4 / 62) mais 17 mois médians -> espérance -469 €/challenge. Sûr mais trop lent. En cours :
`compte_combine` (cassure BTC/ETH + zones du chef dans un compte, frais FTMO réels, revenus pour 4 x 100 k$).

**16/10 05h — compte_combine** (cassure C2 BTC/ETH + zones du chef V1 19 cryptos, frais FTMO réels, années déjà vues) :
briques presque indépendantes (lien +0,05 à +0,13) ; niveau 9 % d'agitation = seul positif partout : +0,66 / +0,95 /
+0,43 %/mois, baisse max ~15 %, challenges 75/2, 77/0, 27/0 % (jumeaux 8/56, 3/82, 1/55), espérance +336 à +782 €
par challenge depuis 2022 ; revenu durable 4 comptes ~90-210 €/mois depuis 2022 : PAS ENCORE DE QUOI VIVRE.
En cours : `crypto_flux` (flux d'ordres taker, financement, positions ouvertes, prime : données publiques Binance
futures), école COLLAPSAR crypto, démo des zones du chef (chef_zones).

**16/10 05h — DÉMO DES ZONES DU CHEF SUR TRADECO** (`collapsar/direct/chef_zones.py`, magique 16102028, BTCUSD/ETHUSD,
0,25 %/trade, 2 positions max, arrêt du jour -2 %, gardien « chef_zones_proc », arrêt `vie/direct/CHEF_ARRET`) : rejeu
3 mois = 7/7 trades du test retrouvés à l'identique ; tourne depuis 03h07. 1er ordre posé : vente limite ETH (zone
H4 -> M15) à 2 701,81, stop 2 720,06. Fréquence attendue ~5 trades/an/marché. Écart ETH Tradeco ~0,1 %.

**16/10 ~06h — INFORMATION LA PLUS FORTE DU PROJET : « contre la foule » (crypto_flux C1)** (`regarder/pistes/crypto_flux.py`,
données `data/binance_futures/`, rapport `vie/pistes/crypto_flux/`) : part des comptes Binance acheteurs au plus haut
de 90 j -> vendre 24 h, au plus bas -> acheter 24 h. AVANT frais +3,75 (dév.) / +3,72 (contrôle 2024-26) / +2,42 %/mois
(groupe B jamais vu, ouvert une fois), force >= 3 sur les 3 ; ni l'élan déguisé ni un décalage d'heure. APRÈS frais
FTMO (0,065 % commission + nuits 30 %/an) : +1,76 / +0,88 / +0,06 -> les frais FTMO mangent l'avantage. Baisse max
37-55 % à 0,5 %/trade : taille à diviser. Peu liée à la cassure C2 (lien ~0,1). Flux d'ordres, financement extrême,
prime : rien après frais. EN COURS : coûts par lieu (Bourse perpétuels preneur/faiseur avec financement réel, CME
micro), version compte financé figée, lecteur direct `donnees/binance_foule.py` ; recherche des sociétés de financement
crypto à bas coûts (HyroTrader/Bybit, Kraken Prop…) -> `research_notes/Prop crypto bon marche/`.

**16/10 ~06h30 — OÙ TRADER LA CRYPTO MOINS CHER** (`research_notes/Prop crypto bon marche/notes.md`) : aller-retour 24 h
BTC : FTMO ~0,16-0,18 % ; HyroTrader (Bybit, comptes SIMULÉS, robots par API AUTORISÉS, 579 $ remboursé) en ordres
limites ~0,05-0,06 %, au marché ~0,12 % ; Kraken Prop ~0,11 % (API non confirmée, pertes max 3-6 %) ; Binance direct
faiseur ~0,05 % (perpétuels bloqués aux particuliers en France) ; CME micro ~0,1-0,15 %. Financement réel BTC
~+3 à +7 %/an (contre 30 %/an FTMO). Pièges HyroTrader : perte du jour depuis le plus haut du jour, jour <= 40 % de
l'objectif, perte d'un trade <= 3 %, retrait plafonné, plaintes 03/2026. Crypto Fund Trader : à éviter.

**16/10 ~07h — C1 « contre la foule » selon le lieu** (estimations, années vues ; `vie/pistes/crypto_flux/rapport.md`
« SUITE ») : pleine taille 2024->09/26 dév. / groupe B : FTMO +0,88 / -0,63 ; Bourse au marché + financement réel
+2,35 / +0,63 ; Bourse 70 % ordres limites +2,96 / +1,09 %/mois (baisse 27-39 %) ; CME micro BTC+ETH +0,74. Version
compte financé figée (0,15 %, 17 cryptos) : sûre mais trop lente (FTMO -0,07 %/mois 2024-26). 3 briques C1 + cassure +
zones (2024-26) : +0,73 %/mois, baisse 15,5 %, challenges 53 / 24 %, espérance +2 840 € (flatteur). Données directes
gratuites (`donnees/binance_foule.py`, 30 j d'API). Suivi À BLANC lancé : `direct/foule_blanc.py` (agent en cours).

**16/10 ~07h30 — foule_devises** : aucun historique gratuit et légal >= 3 ans du positionnement des clients des
courtiers (Dukascopy, IG, Myfxbook, FXSSI, Saxo : non). Cousin CFTC (petits traders, hebdo) : rien après frais
(contrôle et 2e moitié NON ouverts). Collecteur direct `donnees/foule_devises.py` (gTrade + CFTC, toutes les heures,
arrêt `data/foule_devises/direct/ARRET`, pas de tâche Windows). À DEMANDER AU CHEF : un jeton OANDA démo
(`oanda_rattrapage 2017-01-01` relirait l'historique du livre des positions = seul vrai test de C1 sur les devises).

**16/10 ~08h — C1-JOUR (fermer 23h45, rouvrir 00h15)** : pas mieux (2e aller-retour FTMO coûte autant que la nuit).
Garder C1 d'origine en 3e brique : cassure + zones + C1, coûts FTMO, 2022->09/2026 : +1,15 %/mois, baisse 15,7 %,
30 % des challenges réussis en < 12 mois, ~+2 420 € par challenge (addition approchée, sans jumeaux, années vues).
MEILLEUR SYSTÈME ESTIMÉ À CE JOUR = ces 3 briques ; juges restants : démos Tradeco (cassure, zones) + suivi à blanc C1.

**16/10 ~08h30 — SUIVI À BLANC C1 EN DIRECT** (`collapsar/direct/foule_blanc.py`, aucun ordre/MT5/téléphone ; deux
comptes fictifs : coûts FTMO et coûts Bourse + financement réel ; historique raccordé sans trou
`vie/direct/foule_historique/` ; rejeu 25 jours = 1 168 signaux et 77 trades identiques au test ; gardien
« foule_blanc », arrêt `vie/direct/FOULE_ARRET`). Lancé ~04h57 ; 1re position fictive : achat ALGO.
DÉMOS EN COURS : bitcoin_cassure (Tradeco, magique 16102027), chef_zones (Tradeco, 16102028), foule_blanc (fictif),
direct/blanc COLLAPSAR (fictif + recopie Tradeco 15102026), collecteur foule_devises.

**16/10 ~09h — trois_briques (simulation CONJOINTE, 15 min, coûts FTMO)** : 2018-21 +0,65 %/mois ; 2022-23 +1,35 ;
2024->09/26 +0,19 (baisse 15,9 %, challenges 20 % réussis / 11 % morts, jumeaux 0 / 75) ; 2022->09/26 +0,66, espérance
+308 €. L'addition approchée (+1,15) était TROP FLATTEUSE. C1 chez FTMO n'aide pas depuis 2024 (nuits + 0,12 %).
Meilleur compte FTMO mesuré = cassure + zones (2022->09/26 ~+0,66 %/mois, espérance ~+579 €) : PAS de quoi vivre.
Piste restante pour C1 : un lieu à coûts de Bourse (HyroTrader / Bybit, robots permis) -> simulation en cours.

**16/10 ~09h30 — HyroTrader (Bybit) simulé** (`regarder/pistes/hyrotrader.py`, estimation années vues) : C1 seul,
70 % ordres faiseurs, agitation 15 % : 2024->09/26 +1,06 %/mois, baisse 17 %, challenges 55 / 41 % (jumeaux 1 / 88),
espérance +4 449 $/challenge, revenu ~880 $/mois à 200 k$ ; au marché (preneur) : ~0 ou négatif. Comptes financés
morts en < 12 mois (krach 10/10/2025, mur fixe 90 k$ + retraits). Règles HyroTrader contradictoires (perte du jour),
comptes simulés, plaintes 03/2026.

**16/10 ~10h — peur_options** (`regarder/pistes/peur_options.py`, données CBOE gratuites `data/cboe/`) : V2 « fin de
l'inversion du VIX » (VIX repasse sous VIX3M -> achat US500 10 jours) positive sur 3 périodes après frais FTMO et nuits
(+0,31 / +0,23 / +0,33 %/mois, cachée 2024-26 ouverte une fois) mais 3-4 trades/an, force contre « garder » 0,8-1,4 ;
lien -0,03 avec cassure + zones -> petite brique indépendante. Le reste (courbe inversée, VIX Connors, SKEW) : rien.

**16/10 ~06h20 — École COLLAPSAR sur cryptos** (`ecole/crypto_monde.py`, `ecole/crypto_lancer.py`, rapport
`vie/ecole_crypto/rapport.md`, 109 leçons, 3 h 20 carte graphique, frais FTMO réels) : PAS d'avantage seule ; elle
apprend à perdre moins (risque 0,6 % -> 0,16 %) mais trade trop (30 trades/mois/marché, 93 % du temps en position) ;
groupe B ouvert une fois : égale au jumeau. Cassure v3 BTC+ETH mêmes frais : +0,41 %/mois (avantage +1,29 sur le
jumeau) ; sur 14 cryptos la cassure perd aussi. Idée suivante : cerveau NEUF sur BTC+ETH seuls, école longue, avec les
propositions (cassure, foule C1) comme informations.

**16/10 ~14h — DÉFAUT MAJEUR DANS LA TRADUCTION DE SON INDICATEUR** : code Pine original rangé dans
`collapsar/docs/zones supply and demand.pine` (il était resté dans la conversation effacée). L'ancienne traduction
(`regarder/smc/zones supply and demand.py`) effaçait les zones à la 1re clôture M3/M15 au-delà du milieu, alors que le Pine efface à la
clôture du GRAPHIQUE REGARDÉ (H4 si on regarde en H4) ; et le multi-unités du Pine (request.security, dernière bougie
terminée, une seule bougie de petite unité examinée par bougie du graphique) n'était pas reproduit. TOUS les tests de sa
stratégie (gigogne, chef_crypto, smc_combinaisons…) ont donc tourné sur trop peu de zones. Traduction fidèle :
`regarder/smc/zones supply and demand.py` (zones_graphique) ; image `vie/images/nono_v7_XAUUSD_H4.jpg` (or H4, proche de son
TradingView : sa H1 Demand 4 050-4 065 ~ notre M30 4 061-4 076). Réglages du chef : tout par défaut sauf journalier ->
M3 à H4 affichés. Il combine zones supply and demand + VRVP (profil de volume TradingView par défaut). Tout est relancé avec zones supply and demand
(`zones_retouchees`).

**16/10 ~14h30 — AUDIT DU JUGE (`collapsar/vie/audit/rapport.md`, scripts `collapsar/audit/`)** : calculs de base justes
(tricheuse gagne énormément, hasard perd exactement les frais). MAIS défaut GRAVE n°1 : pandas 3 lit les heures en µs,
le labo SMC comptait en ns -> zones H4 « confirmées » ~166 jours trop tard ; V1 du chef 4 marchés 2015-23 : -0,08 R
(faux) -> +0,22 R (or -0,51 -> +0,25) ; explique aussi le calcul « non reproductible » du 15/10. CORRIGÉ à la source
(bougies.py, marches.py, histdata.py ; 128 tests verts). TOUS les résultats de ses zones d'avant (gigogne, cachée,
chef_crypto, chef_compte_ftmo, smc_combinaisons, zones_milieu ?) sont à refaire. Autres défauts (pessimistes) : force
non pondérée par la taille (C2 BTC 1,6 -> 3,1), séances trouées bouchées à plat (~2 %/an bande de bruit), frais x 1,25 +
demi-fiche à l'entrée au marché alors que le glissement mesuré est nul (~1 %/an), challenges inachevés comptés dans le
% ; (optimistes) -5 % sur la clôture seule dans bande_bruit, commission crypto oubliée (déjà corrigée).

**16/10 ~15h — zones_retouchees (traduction fidèle + heures corrigées)** (`regarder/pistes/zones_retouchees*.py`,
rapport `vie/pistes/zones_retouchees/`) : aucune variante (1er contact, 2e, 3e, rebond au milieu, à l'entrée, par unité,
VRVP) positive sur les 3 périodes ; 2e contact ne fait pas mieux que le 1er sur les mêmes zones ; « 2e fois au milieu »
non vérifié ; fréquence de l'indicateur seul : 0,2-0,3 trade/semaine sur 4 indices (lui : 4-5) -> ses trades viennent
de son jugement + VRVP + LuxAlgo, pas de l'indicateur seul -> demander son HISTORIQUE DE TRADES. Réconciliation avec
l'audit : +0,22 R = 2015-2023, frais du labo, sans nuits ; frais FTMO + nuits : +0,09 R ; 2024-2026 : -0,31 R.

## BILAN DE LA NUIT 15->16/10 (à dire au chef de projet quand il écrit, COURT)
- Aucune solution « pour en vivre » prouvée. Meilleur compte FTMO mesuré honnêtement : cassure BTC/ETH + ses zones
  sur cryptos ≈ +0,66 %/mois 2022-26 (+0,19 depuis 2024 avec C1), espérance challenge légèrement positive.
- Information la plus forte du projet : « contre la foule » Binance (C1), +2,4 à +3,7 %/mois AVANT frais sur 3 jeux
  indépendants ; tuée par les frais FTMO crypto (commission 0,065 % + nuits 30 %/an) ; viable seulement à coûts de
  Bourse en ordres limites (HyroTrader ~+1 %/mois estimé, société fragile).
- Sa stratégie (zones gigognes) : positive sur cryptos jamais vues (+0,18 R après vrais frais) ; trop peu de trades
  pour un challenge ; ses concepts appris en combinaison par COLLAPSAR : rien de plus que des zones au hasard ; son
  avantage = les gros trades qui courent.
- Erreurs corrigées : commission crypto FTMO oubliée (« crypto 20 x moins chère » FAUX), témoin des zones mal placé.
- En direct : démos Tradeco cassure + zones, suivi à blanc C1 (coûts FTMO et Bourse), collecteur foule devises.
- Décisions à lui demander : jeton OANDA démo (historique foule devises) ; écrire à FTMO (IA) et à HyroTrader (règles).

**Encore en attente de lui :** la vraie « feuille de route » (le fichier `PROMPT_MAITRE_CODE.md` trouvé est un projet
Roblox sans rapport, il s'est trompé de fichier) ; ses historiques MQL5 ; une clé Collective2 / un compte Darwinex.
Anomalie non expliquée : un calcul d'évaluation non reproductible (`vie/smc/*_DEFECTUEUX_non_reproductible.*`).

À lire en entier au début de la session suivante, avec `CLAUDE.md` (section COLLAPSAR en haut) et la mémoire
`new-child-ai-project.md`. Cette fiche est volontairement factuelle : elle sépare ce qui est MESURÉ de ce qui est
supposé, pour repartir l'esprit clair.

## 1. Ce que veut le chef de projet (ne pas le perdre de vue)
- **LE BUT, dans ses mots (14/10) : « un humain dans une machine », un trader humain numérique.** Chaque choix de
  conception se juge à cette question : « un trader humain devant MetaTrader pourrait-il voir / faire ça ? ».
- Une IA qui trade **comme un trader humain devant MetaTrader, en mieux** : aucune émotion, discipline parfaite.
  Il se juge lui-même mauvais trader (« je me gère mal ») : c'est la raison du projet.
- **Aucun menu, aucune règle de trader imposée** (il refuse le « robot TikTok » : zones d'offre/demande, blocs
  d'ordres, lignes de tendance = « bullshit » à ses yeux, et nos mesures vont dans son sens). Seules limites
  imposées : FTMO (-5 %/jour, -10 % total, compte Normal, fermeture avant toute pause > 2 h dont le week-end).
- Il veut viser haut (2 %/mois) et refuse qu'on se résigne à « la tendance de fond » : il a raison sur un point,
  **nos IA ont été enfermées dans le court terme par nos choix** (voir §4), donc « on n'a rien trouvé » ≠ « il n'y a
  rien ».
- Forme : français simple, pas de jargon, chiffres en %, avis AVANT de coder, il valide la structure.
- Il a refusé FTMO Instant (3 000 € le compte) : visée = challenge classique (~540 €, remboursé), après démo.

## 2. Ce qui tourne en ce moment
- **Cœur de l'arbre 3** (`python -m collapsar.arbre.coeur`, relancé par la tâche « TestIA_CollapsarGardien ») :
  vision « trader » (`reglages.yaml` : `vision: trader`, `largeur_trader: 0.35`), yeux neufs (sans greffe), choisi
  sur le « lien » prévu/réel SANS frais, retour en arrière contre le par cœur. Utilité douteuse (voir §3) : peut
  être arrêté (créer `collapsar/vie/ARRET`, puis tuer le processus) si la carte graphique sert à autre chose.
- **MetaTrader 5** (compte démo Tradeco, aucune position) lancé avec `collapsar/surveillance/mt5_calendrier.ini` :
  le programme MQL5 `Experts\Collapsar\ExportCalendrier` (aucun ordre) écrit chaque minute
  `%APPDATA%\MetaQuotes\Terminal\Common\Files\collapsar_calendrier_direct.csv` (+ `_histoire.csv` au démarrage).
  Copie de l'historique : `data/calendrier/mt5_calendrier_histoire.csv`.
- Rien d'autre (AUREX/AUREXIS arrêtés depuis le 13/10).

## 3. Ce qui est MESURÉ (années jamais vues, frais réels) — fiable
| Piste | Résultat |
|---|---|
| Racines « deviner le sens » (arbre 2) | ~50,8 % ; à 1 jour / 1 semaine pire que « répondre toujours pareil » |
| École A3 (anciens yeux, compte unique 12 marchés) | grand examen 192 challenges 2023-09/2025 : +0,00 %/mois, 0 % de murs |
| Vision « trader » (arbre 3, n'importe quel coup) | lien prévu/réel sans frais ~1 %, sur le SENS ~0 ; verdict rapide 45 marchés : 0 |
| Vue d'ensemble 49 nombres + cerveau souple | apprend la DATE par cœur, ~0 sur années vierges |
| Pondération simple (ridge) réapprise chaque année | lien semaine +1,9 % sur 2020-22 mais de -10 % à +10 % selon l'année : instable |
| Annonces économiques, heures JUSTES (MetaTrader) | dérive 1 jour : +0,5 % (2017-19), -1,3 % (2020-22), +5 % (2023-25) ; méthode figée jugée UNE fois sur les 12 mois cachés (10/2025 → 10/2026) : **-1 %/3 mois, morte** |
| Tendance de fond multi-marchés (repère du 09/10) | ~+0,5 %/mois sur 2018-2025, baisse max ~19 % |

**Les 12 mois cachés ont été utilisés UNE fois** (pour la piste des annonces seulement). Ne plus s'en servir pour
choisir quoi que ce soit ; les garder pour le verdict final d'une IA figée.

## 4. Pourquoi nos IA n'ont rien trouvé — causes identifiées (pas seulement « le marché est efficace »)
1. **Enfermées dans le court terme** : décision obligatoire toutes les 15 min, récompense à chaque bougie, yeux
   entraînés sur 1 h / 4 h. Tenir une semaine = dire « je garde » 480 fois. Le chef de projet l'a pointé : c'est
   notre faute, pas la sienne.
2. **Par cœur** : les gros cerveaux (CNN 540 000-720 000 connexions, MLP sur 49 nombres) reconnaissent chaque moment
   (ou chaque date) de leurs années d'apprentissage et récitent la suite : +40 à +97 % du risque par coup sur années
   apprises, 0 sur années vierges. La greffe des yeux de l'arbre 2 transmettait cette mémoire. Petits cerveaux et
   cerveaux simples récitent moins.
3. Très peu de situations vraiment indépendantes (bougies voisines = même avenir) : ~100 000, pas 8 millions.

## 5. Pièges débusqués le 14/10 (ne pas retomber dedans)
- « Lien » prévu/réel calculé FRAIS COMPRIS : 2,7 points sur 2,8 venaient des frais connus des deux côtés. Toujours
  mesurer SANS les frais et sur le SENS (`lien`, `lien_sens` dans `regarder/vision_trader.py`).
- Note des « 10 % de coups les plus sûrs » : ±3 points de bruit (quelques centaines de moments indépendants).
- **Heures du calendrier Forex Factory fausses** pour des annonces clés (CPI américain daté la veille à 22h30) :
  fuite d'information → faux avantage énorme. Aussi : étés 2023+ décalés d'1 h (Iran). Ne PLUS utiliser Forex
  Factory pour mesurer de l'argent.
- Calendrier MetaTrader : heure fixe d'été → retirer 1 h en hiver (fait dans `donnees/calendrier.charger_mt5`).
- **Règle : vérifier les heures annonce par annonce (la plus grosse bougie) et recouper avec une 2e source AVANT
  tout test d'argent ; ne jamais annoncer un résultat au chef de projet avant ce recoupement.**
- Prix Dukascopy = heure du serveur MetaTrader (accord 99-100 % en 2025-2026), sauf ~3 semaines en mars (les
  États-Unis changent d'heure avant l'Europe) : décalage d'1 h, à corriger pour le direct.
- Ne jamais laisser `collapsar/vie/ARRET` après une expérience (le cœur est resté arrêté 5 h le 14/10).

## 6. Le plan validé dans son principe (à présenter en détail AVANT de coder)
**Nouvelle école, « elle choisit quand revenir regarder »** :
- Yeux : prix bruts toutes échelles et tous marchés + faits objectifs seulement (heure, jour, séances Asie /
  Londres / New York, calendrier MetaTrader aux heures justes, son compte et la distance aux murs). Aucun dessin de
  trader.
- Mains libres : sens, stop, objectif, taille, rien ; **et le moment de son prochain regard** (15 min → 1 semaine).
  Stops / objectifs / coupe-circuit actifs entre deux regards.
- Récompense : l'argent du compte jusqu'au prochain regard, frais compris ; mourir aux murs coûte très cher.
- Cerveau : petit (contre le par cœur), apprentissage sur années choisies, contrôle sur années jamais vues.
- Juge : simulateur FTMO fidèle (`mains/`, `juge/`), puis démo à blanc en direct ; verdict final sur les 12 mois
  cachés une seule fois, IA figée.
Le chef de projet doit dire « on lance » sur le plan détaillé avant le code.

## 6 bis. 14/10 soir : la nouvelle école est CONSTRUITE (ordre du chef de projet : « tu fais les deux points »)
- Fichiers : `cerveau/humain.py` (TraderHumain : petit cerveau NEUF ~250 000 connexions, gestes garder / revoir ses
  protections / changer de position, stop et objectif libres en bougies du jour ou aucun, prochain regard 15 min ->
  5 jours), `yeux/faits.py` (séances Tokyo/Londres/New York, calendrier MetaTrader : heures avant/depuis l'annonce
  importante, nombre dans 24 h), `ecole/regard.py` (comptes qui vivent seuls entre deux regards, réveils : position
  fermée sans elle ou mi-chemin d'un mur ; avantage de chaque regard jusqu'au suivant), `ecole/lancer_regard.py`,
  `surveillance/carnet.py` (format de message validé). Tests : `tests/test_regard.py` (62 tests au total, verts).
- Simulateur corrigé : un stop posé avec un retournement vaut pour la nouvelle position ; `pas()` rend
  `fermees_sans_ordre` [B, M].
- Années : apprend 2010-2019 (+ miroir), contrôle 2020-2022, témoin du par cœur 2016-2019.
- Lancement (carte graphique libre) : `venv_gpu\Scripts\python.exe -u -m collapsar.ecole.lancer_regard --classe 1
  --minutes 240` ; arrêt propre : créer `vie/ecole_regard/STOP` ; résultats `vie/ecole_regard/classe1/`
  (journal.jsonl, eleve.pt, meilleur.pt, carnet_exemple.txt). Essai court sur processeur fait (dossier `classe1_essai`).
- 14/10 18h20 : arbre 3 ARRÊTÉ (ordre explicite du chef de projet) et archivé dans `vie/arbre3_14oct/` ;
  `vie/ARRET` est en place EXPRÈS (le gardien ne relance plus le cœur ; il ne relance pas non plus l'école).
- 18h40 : 1er élève PARALYSÉ en 35 leçons (taille en « fois le compte » : premiers essais à 3-5 x le compte -> murs
  -> plus aucun trade) ; archivé `classe1_paralysie_taille_compte`. Correction : la taille = SENS (vendre / fermer /
  acheter) + « combien je risque » = % du compte par bougie du jour contre lui (0,01 % -> 20 %, départ 0,5 %).
- 18h57 : le chef de projet rappelle la règle FTMO d'inactivité. Ajouté au simulateur (vérifié sur le site) :
  30 jours sans ouvrir de trade = compte terminé (`inactif`, compté comme partie perdue) ; challenge validé
  seulement après 4 jours de trading. Elle VOIT les jours sans trade et ses jours de trading. Parties de 2 mois.
  2e élève (sans ces règles) archivé `classe1_sans_regle_inactivite` (glissait vers 8 % du temps en position).
- 19h04 : 3e lancement de la classe 1 (4 h), messages téléphone au début et à la fin de l'école.

## 6 ter. 14/10 ~20h : NOUVELLE DIRECTION VALIDÉE — « l'école des mille mondes » (mémoire `ecole-mille-mondes.md`)
- Idée : l'entraîner dans des millions de marchés INVENTÉS aux lois cachées (tendances, retour au calme, agitation en
  vagues, sauts, annonces, facteur commun, régimes qui changent ; beaucoup de mondes sans avantage). Image du chef
  de projet : « chercher l'avantage comme un joueur de poker ».
- Fait : `mondes/generateur.py` (tirer_lois(rng, marches, intensite), fabriquer -> bougies + vérité cachée),
  `mondes/empreintes.py` (12 propriétés statistiques des vrais marchés, Cont 2001), `mondes/verifier.py` (rapport
  `vie/mondes_verification.json`), `tests/test_mondes.py`. Les 15 empreintes des vrais marchés (2010-2019) sont
  couvertes par les mondes. Calibrage : le retour au calme était bien trop fort (biais anti-tendance) -> 0,05/jour max.
- Test de vérité (faux euro-dollar à tendance cachée, `ecole/verite.py`, `lancer_regard --verite`) : contrôle
  -0,10 -> -0,01 -> +0,17 %/mois en 50 min : l'école COMMENCE à trouver un avantage caché. Classe 1 réelle : ~-0,05.
- Test de vérité, fin : contrôle (années jamais vues) monte à +0,54 %/mois puis retombe à -0,95, pendant que les
  années APPRISES du faux marché montent à +3,31 %/mois (50 % de challenges) : PAR CŒUR d'une histoire unique, même
  inventée. Preuve que l'école sait trouver un avantage ET qu'il faut des mondes toujours neufs.
- 14/10 21h37 : ÉCOLE DES MILLE MONDES LANCÉE pour 10 h (`ecole/lancer_mondes.py`, journaux
  `vie/logs/ecole_mondes_*.txt`, élève `vie/ecole_mondes/eleve.pt` + `meilleur.pt`, `journal.jsonl`) : 6 mondes en jeu,
  chaque monde ne sert qu'UNE leçon puis est remplacé ; 1 à 4 marchés par monde ; intensité 1 -> 0,3 quand elle
  capture >= 25 % du gagnable ; contrôle toutes les 40 min (4 mondes fixes à l'intensité en cours + 4 réalistes +
  vrai euro-dollar 2020-2022). `mondes/ecole.py` : ClasseMonde (frais, frais de nuit, levier LIÉS à l'agitation),
  connaisseur (sait la tendance cachée et le rappel PRÉSENT ; gagnable ~+0,4 %/mois à intensité 1, ~+0,1-0,2 à 0,3),
  ControleMondes (construit une fois). Mémoire d'expérience dans sa vue (résultat moyen/jour sur ~5 et ~20 jours).
- Corrigés pendant le contrôle complet : sauts trop fréquents (calés sur les trous d'ouverture des indices),
  frais/frais de nuit tirés au hasard (un monde calme payait ceux d'une crypto), connaisseur qui lisait le rappel
  FUTUR (pariait à contresens). 74 tests verts.
- Gardien modifié : `vie/ARRET` n'arrête plus que l'ARBRE ; l'école déclare sa séance (`vie/ecole/seance.json`,
  avec ses arguments) et le gardien la relance si elle s'arrête avant l'heure (fin normale ou STOP : séance effacée).

## 6 quater. 15/10 nuit : la science et le plan d'action (rapports `reports/Études de marché pour COLLAPSAR.md`,
`reports/Risque agitation et tendance courte.md`)
- Conclusion des deux recherches : l'AGITATION se prévoit (58-80 % expliqués sur nos données), la DIRECTION presque
  pas ; la tendance de fond est réelle mais faible (~0,4 de rapport gain/agitation) et a disparu à court terme sur
  devises et indices depuis 2009 ; noter l'IA sur sa chance de réussir AU-DESSUS DU HASARD (au hasard : ~50 % phase 1,
  ~33 % les deux phases, moins avec frais).
- FTMO (lu sur ftmo.com/au/forbidden-trading-practices, mémoire `ftmo-rules-ai-clause.md`) : interdit « tout logiciel,
  IA ... qui pourrait ... donner un avantage déloyal », > 2 000 requêtes/jour, trading de trous, tailles soudain
  beaucoup plus grosses. EA permis. À FAIRE PAR LE CHEF DE PROJET : demander par écrit à FTMO avant tout challenge.
- Construit et testé (84 tests verts) :
  * `juge/note.py` : note = avantage sur le JUMEAU au hasard (mêmes gestes, sens tiré à pile ou face,
    `jouer_comptes(..., jumeau=True)`), incertitude avec comptes qui se chevauchent, seuil max(3, racine(2 ln essais)) ;
    branchée dans l'école des mondes (mondes réalistes + vrai euro-dollar ; le meilleur élève = avantage sur le hasard).
  * `juge/examen_humain.py` : examen sur vrais marchés 09/2023-09/2025 (EURUSD, USDJPY, XAUUSD, USA500), un compte,
    challenges de 6 mois tous les 10 jours : elle, 2 jumeaux, CONNAISSEUR DU RISQUE (tendance 20 j, risque = 10 % de
    la distance au mur le plus proche, stop = 1 bougie du jour, rien dans le 1/4 h d'une annonce).
  * `regarder/mesures_science.py` -> `vie/mesures_science_2010_2019.json`.
  * FRAIS DE NUIT DE CHAQUE ÉPOQUE (`donnees/taux.py` : taux 3 mois de 8 devises via l'API FRED, clé de Run A ;
    `mains/nuit.py` : devises = écart de taux + 1,63 % (marge vérifiée sur 28 paires Tradeco), autres = taux de la
    devise + 2,5 % À REMPLACER par la table FTMO ; `Horloge(nuit_historique=True)` pour les vrais marchés).
- MESURÉ (23 marchés, 2010-2019) : tendance 60 j fermée le vendredi = +0,39 / +0,41 SANS frais, -0,15 / -0,09 avec
  tous les frais réalistes (moitié écarts, moitié marge des frais de nuit) ; 6,2 paris indépendants sur 23 marchés.
  Avec les anciens frais de nuit (relevé 2026 appliqué à 2010-2019) : -0,6 -> le simulateur sur-punissait le fait de
  garder une position plusieurs jours.
- École des mille mondes relancée par le GARDIEN le 15/10 01h20 (relance automatique vérifiée).

## 6 quinquies. 15/10 2h-5h30 : compte FTMO, maîtres, démo à blanc
- COMPTE D'ESSAI FTMO (Swing, levier 1:30, FTMO-Demo, aucun trade : l'essai de 14 jours démarre au 1er trade) :
  connecté par le chef de projet sur le MetaTrader PRINCIPAL (Program Files). Accès rangés hors du projet
  (`%USERPROFILE%\.collapsar\acces_ftmo.json`, jamais affichés). Le MetaTrader « MT5_FTMO » séparé ne marche pas
  (mise à jour en boucle) : inutile. Le programme du CALENDRIER (ExportCalendrier) s'est ARRÊTÉ au changement de
  compte : à remettre à la main sur un graphique EURUSD M15 (le système de sécurité refuse un fichier de démarrage
  contenant le mot de passe).
- CONDITIONS FTMO RELEVÉES (`mains/conditions_ftmo.json`, installées dans `conditions_reelles.json` ; Tradeco gardé
  dans `conditions_reelles_tradeco_13oct.json`) : marges des frais de nuit devises 1,46 %/an, indices 3,75 %, métaux
  3,95 % (`mains/nuit.py`) ; pétrole vendeur ~90 %/an, acheteur reçoit ~20 % ; crypto 30 %/an, levier 1:1.
- MESURE AVEC FRAIS FTMO (23 marchés 2010-2019) : tendance 60 j +0,49/+0,31 sans frais, ~0 avec (-0,14 à +0,05).
- MAÎTRES (option B : leurs trades couvrent nos années d'examen -> verdict = démo en direct) :
  * Paul Wei (BitMEX, `data/maitres/coolish`, public pour être étudié) : gagnant sur toutes les périodes (exact,
    exécution par exécution) ; force contre le hasard +1,2 (2020-22) / +2,2 (2023-26) ; ~60 % gagnants ; gains
    concentrés sur quelques gros trades ; ×54 de 2020-21 = petites cryptos à fort levier (-80 %).
  * MQL5 : règlement art. 3.7 interdit l'accès automatique -> liste de 45 signaux à exporter À LA MAIN
    (`docs/MAITRES_A_TELECHARGER.md`, fichiers dans `data/maitres/mql5/<id>.csv`).
  * Hyperliquid (`maitres/hyperliquid.py`, API officielle publique) : 47 083 traders, 6 826 « durables » ; repérage
    lent (~5/min) et peu de hors-crypto (5/295) ; courbes de risque souvent incohérentes (sous-comptes) : source
    SECONDAIRE. Recherche de sources plus fiables lancée (notes : `research_notes/Sources de maitres/`).
  * `maitres/juge.py` (décisions de fermeture, force contre le jumeau, risque sur courbes officielles),
    `maitres/trades.py` (format commun MQL5 / Paul Wei), `maitres/imitation.py` + `lancer_imitation.py` (école avec
    maîtres : entrée / tenue / sortie / à plat, contrôle sur les 20 % de trades les plus récents). Essai Paul Wei
    seul : sens retrouvé 59 % puis 46 % (par cœur) -> il faut des milliers de trades de nombreux maîtres.
- DÉMO À BLANC EN DIRECT (`direct/blanc.py`, lancée 15/10 05h24, journal `vie/logs/direct_blanc.txt`, état
  `vie/direct/blanc.json`) : prix FTMO toutes les 15 min (même heure que nos données, vérifié), élève
  `ecole_mondes/meilleur.pt`, compte FICTIF, carnet sur le téléphone (heures calmes 23h-8h, points 8h et 20h).
  AUCUN ORDRE n'est envoyé (le programme ne contient pas la fonction).

## 6 sexies. 15/10 05h40 : l'école ne s'arrête plus pour se contrôler ; gTrade
- École des mille mondes relancée en mode `--sans-controle --parties 2048` (journal `vie/logs/ecole_mondes_*.txt`) :
  copie de l'élève toutes les 10 min (`vie/ecole_mondes/eleve_a_controler.pt`) ; CONTRÔLEUR à part
  (`ecole/controleur_mondes.py`, journal `vie/logs/controleur_*.txt`, résultats `vie/ecole_mondes/controles.jsonl`,
  meilleur élève `meilleur.pt`, consigne d'intensité `consigne.json` lue par l'école). Le gardien relance le
  contrôleur s'il manque. Heures calmes 23h-8h pour les messages de l'école.
- gTrade (`maitres/gtrade.py`, boucle toutes les 3 h, `vie/logs/maitres_gtrade.txt`) : adresses hors crypto ->
  historiques ; `trades.lire_gtrade` (stop / objectif connus quand le trade s'est fermé dessus) ; stops des maîtres
  mesurés en part de LEUR prix d'entrée (SPY ≠ niveau de l'indice). `juge.juger_standard` : maîtres retenus si
  >= 30 trades, <= 3 % liquidés, force > 1,5. À 05h30 : 2 retenus sur 33 (Paul Wei ; un trader gTrade
  hors crypto à 61 %, levier 2, 36 % gagnants, gains 3,6 x les pertes, force +2,4).
- L'école avec maîtres n'apprend que des maîtres retenus, pesés par leur force (`lancer_imitation.py`).
- 06h00 : ORDRES À L'AVANCE dans ses mains (`cerveau/humain.py`, geste 3 « ATTENDRE ») : sens + taille + distance
  (bougies du jour) + limite/stop + durée ; « fermer » = annuler. Branchés dans `ClasseRegard.ordres`, le carnet
  (« Achat si le prix redescend à … ») ; `TraderHumain.charger()` recharge les élèves d'avant (gestes 0-2 repris).
  88 tests verts. École et contrôleur redémarrés avec (leçon 659). La démo à blanc tourne encore avec l'ancien code
  (elle rechargera via `charger` à son prochain redémarrage).

## 6 septies. 15/10 06h-07h30 : OSTIUM, le talent qui dure, d'où vient l'avantage des maîtres
- Nouvelle source honnête, non crypto : **Ostium** (échange sur la chaîne publique Arbitrum ; devises, or, argent,
  pétrole, indices). `maitres/ostium.py` lit le sous-graphe public officiel (adresse prise dans le paquet officiel
  `ostium-python-sdk`, sans clé, lecture seule) -> `data/maitres/ostium/ordres.csv` : **748 288 ordres, 08/2024 ->
  10/2026**, ~14 900 traders (morts compris). Boucle toutes les 3 h (`vie/logs/ostium_*.txt`). Lecture au format
  commun : `trades.lire_ostium` (sorties partielles, stop / objectif / liquidation / fin de journée). Lecteur
  Hyperliquid aussi prêt (`trades.lire_hyperliquid`, attend les historiques). Tests `tests/test_maitres.py` (4).
- **Le talent dure-t-il ?** (`maitres/persistance.py`, `vie/ecole_maitres/persistance.json`) : coupe de chaque
  historique en deux moitiés. Choisis à force > 1,5 : ils PERDENT ensuite (force -0,3 ; 37 % encore gagnants) =
  des chanceux. Choisis à **>= 200 trades et force > 3** (gain rapporté à la taille) : ils RESTENT bons (force +1,3 ;
  65 % encore gagnants ; 20 traders). -> nouveau critère du juge (`juge.MIN_TRADES_MAITRE`, `FORCE_MAITRE`) :
  **11 maîtres retenus sur 14 902** ; sur leurs 20 % de trades les plus récents (jamais vus) : 73 % encore gagnants.
- École avec maîtres revue (`lancer_imitation.py`) : maîtres choisis sur leur passé seulement ; 70 % apprendre /
  10 % validation (choix de l'arrêt) / 20 % contrôle vierge ; exemples de tous les maîtres mélangés ; mesure
  ÉQUILIBRÉE du sens (achats et ventes à part). Piège débusqué : les « 70 % de sens juste » d'avant = « toujours
  acheter » (les maîtres achetaient 70 % du temps). Vrai résultat au contrôle : **53,8 %** équilibré (faible).
- **D'où vient leur avantage ?** (`maitres/origine_avantage.py`) : leurs entrées gagnent à 1-3 jours (force +9), leurs
  sorties ≈ hasard ; mais une fois leur PENCHANT retiré (même part d'achats, moments mélangés), sur leurs trades
  récents : surplus ≈ 0 (force -0,2 sur le vrai résultat). **Leur avantage = être du bon côté d'une grande tendance
  (acheteurs d'or, d'argent, de pétrole pendant leur hausse) et y rester**, pas le choix fin du moment. Même leçon
  que tout le reste du projet : la seule source mesurée est la tendance de fond. Piste : apprendre des maîtres le
  PENCHANT (quel côté, quand en changer), pas le moment d'entrée. Ce penchant n'est PAS la tendance du graphique
  (accord 69 % contre 65 % attendu par hasard) : une conviction de fond (un maître fait même pétrole US acheté /
  Brent vendu).
- Le meilleur « maître » gTrade (force 16) fermait dans la même seconde : programme qui joue sur le retard du prix
  de la bourse -> exclu (`juge.DUREE_MEDIANE_MIN_MINUTES` = 5). Reste **10 maîtres** (70 % encore gagnants ensuite).
  Durées médianes des vrais maîtres : de 30 min à 5 jours.
- **La foule** (`maitres/foule.py`, tous les traders Ostium, 16 marchés, ~6 900 jours-marché) : elle SUIT les 5
  derniers jours (force +7) mais sa position n'annonce RIEN pour les 1 et 5 jours suivants (force -1,1). Piste fermée.
- **Tendance de fond sans la nuit ?** (`regarder/tendance_sans_nuit.py`, 43 marchés non crypto, 2010-2022, frais FTMO
  et frais de nuit de l'époque) : qualité moyenne par marché (rendement / agitation par an), tendance 20/60/120 j
  moyennées : avant frais +0,08 ; en gardant -0,20 ; en JOURNÉE seulement (sortie avant minuit) -0,26 (un aller-retour
  par jour coûte plus que la nuit). Positifs après frais : US100 +0,35, obligation US +0,58, USDJPY +0,25, or +0,22,
  argent +0,23 — à ne PAS choisir après coup (ce serait se tromper soi-même). Piste « journée seule » fermée.
- **Habitudes qui annoncent un trader durablement bon** (`maitres/habitudes.py`, 705 traders >= 100 trades, habitudes
  sur la 1re moitié, force sur la 2de) : tenir plus longtemps (lien +0,30, force +7,9 ; +5,5 à résultats passés
  égaux), trader moins souvent (-0,23, force -6,0), part de gagnants (+0,28) ; levier élevé : plutôt mauvais (-0,11).
  Leçon pour COLLAPSAR : peu de trades, tenus longtemps (les frais punissent l'agitation).
- Contrôleur (07h51) : le meilleur élève est choisi sur la note PRUDENTE (avantage - incertitude - pénalités,
  `controleur_mondes.note_prudente`) : avec des notes à ± 0,15, garder la plus haute couronnait la chance. La démo à
  blanc charge l'élève au DÉMARRAGE seulement (verdict stable) : changer d'élève en démo = décision volontaire.
- Hyperliquid (10h25) : aperçu fini (6 826 traders durables, 2 025 touchent des marchés hors crypto, 241 à >= 30 %) ;
  téléchargement des historiques lancé (`maitres.hyperliquid historiques 600`, `vie/logs/hyperliquid_historiques_*`).
  Ces traders sont rarement « à plat » : peu de trades complets au format commun (le juge par ordres
  `juge.juger_tous` reste l'outil pour eux). Noms HIP-3 ajoutés (`trades.HYPERLIQUID` : CL, NATGAS, XYZ100…).
- Veranta (ex-Avantis) sondé : historique par trader lisible, mais découverte des traders pauvre -> secondaire
  (`research_notes/Sources de maitres/sources.md` §4).
- **POINT D'ATTENTION (09h)** : depuis le redémarrage de 06h02 (mains « ordres à l'avance »), l'élève de l'école
  devient plus joueur : risque moyen 0,32 % (leçons 600) -> 0,70 % (leçons 900), murs 0 -> ~5 comptes / 2 048 par
  leçon, récompense -0,005 -> -0,025 par jour, erreur de la valeur 0,04 -> 0,2 ; largeur des essais presque stable
  (c'est son intention qui grossit). Le meilleur élève gardé (leçon 731) reste sain. Correction à PROPOSER au chef de
  projet (pas imposée) : repartir du meilleur élève, apprendre plus lentement la taille, ou revoir l'élargissement
  forcé des essais de stop/objectif à la reprise (`lancer_mondes.py`, `log_ecart[1:3] >= -0,3`). Piste de cause :
  `TraderHumain.log_prob` compte la taille d'un ORDRE À L'AVANCE même s'il n'est jamais exécuté (aucune conséquence
  -> signal d'apprentissage sans fond sur la taille). La dérive touche tous les mondes (avec 4 marchés : ~10 murs par
  leçon aux leçons 900). En contrôle (gestes moyens) : 0 mur mais baisse max 1,0 % -> 1,9 %. Contrôle 09h28
  (leçon 906) : mondes réalistes -0,49 %/mois contre le hasard (force -2,4), vrai euro -0,22 ; mondes faciles : 44 %
  du gagnable capturé (intensité -> 0,51). Elle exploite les lois fortes en grossissant, ce qui coûte quand elles
  sont faibles.
- **15/10 13h45 — CORRECTION DE L'ÉCOLE (ordre du chef de projet)** : (1) la taille d'un ordre à l'avance n'est
  apprise QUE s'il s'est exécuté (`simulateur` rend `attente_executee`, `ProfesseurRegard.jouer` relie chaque
  exécution au regard qui l'a posé, `TraderHumain.log_prob(..., sans_taille=...)`, test
  `test_la_taille_d_un_ordre_a_l_avance_jamais_execute_n_est_pas_apprise`, cohérence vérifiée : écart 7e-7) ;
  (2) plus d'élargissement forcé des essais de stop/objectif à chaque reprise ; (3) école repartie du meilleur élève
  (`lancer_mondes --depart meilleur.pt`, leçon 731, intensité 0,8 ; l'élève dérivé gardé dans
  `eleve_avant_depart_*.pt`). 94 tests verts.
- **Notifications d'« ordres à l'avance » du matin** : la démo à blanc tournait avec un élève d'AVANT les ordres à
  l'avance ; `charger` lui donnait ce geste avec des réglages jamais appris -> ordres fictifs au hasard (jamais
  exécutés, compte inchangé, AUCUN ordre réel). Corrigé : `direct/blanc.py` désactive tout geste que l'élève n'a pas
  appris ; démo relancée à 13h41 avec `meilleur.pt` (leçon 731, qui a appris ce geste).
- **15/10 14h02 — COLLAPSAR SUR LE COMPTE DÉMO TRADECO** (ordre du chef de projet) : MetaTrader rebasculé sur
  Tradeco (<serveur démo du courtier>, <solde démo> ; numéro dans `%USERPROFILE%\.collapsar\acces_tradeco.json`, mot de passe gardé
  par MetaTrader ; le compte d'essai FTMO n'est plus connecté). `direct/tradeco.py` RECOPIE les positions du compte
  fictif (stop et objectif posés dans MetaTrader ; on n'agit que quand la position voulue change ; numéro magique
  15102026 ; coupe-circuit -4,5 %/jour et -9 % -> tout fermé + `vie/direct/TRADECO_ARRET` ; vendredi 22h45 serveur ->
  tout fermé, aussi dans le compte fictif ; compte réel refusé). Interrupteur : `vie/direct/mode.json`
  {"tradeco": true}. Prix Tradeco = nos données (écart médian 0,00 %, heures identiques) ; S&P 500 = « US500Cash ».
  Bouton « Trading algo » allumé par Ctrl+E (s'il s'éteint : rien n'est tenté, rappel téléphone toutes les 3 h).
  Essai réel 0,01 lot (ouvrir, déplacer le stop, fermer) : OK. Tests `tests/test_tradeco.py` (7, faux MetaTrader).
  Limite : un ordre à l'avance du compte fictif est recopié en ordre au marché quand il s'exécute (au plus 15 min
  de décalage).
- **15/10 14h10-14h25 — deux défauts de la démo corrigés** (`direct/blanc.py`, tests `tests/test_blanc.py`) :
  (1) le prochain regard était sauvé comme une HEURE future, inexistante -> retombait sur la dernière bougie : elle
  regardait toutes les 15 min (35 regards de 6h à 14h) ; maintenant sauvé en nombre de bougies (`prochain_dans`) ;
  premier regard corrigé : retour dans 78 bougies (~19 h 30). (2) les ordres à l'avance n'étaient pas sauvés entre
  deux passages -> perdus 15 min après (d'où des notifications d'ordres sans aucun trade) ; maintenant sauvés.
  Bilan au 15/10 14h25 : aucune position ouverte depuis 6h, compte fictif 100 000 $, Tradeco <solde démo>.
- **15/10 14h35 — vrais ordres à l'avance chez Tradeco** (ordre du chef de projet) : `tradeco.poser` pose les ordres
  limite / stop du compte fictif dans MetaTrader avec expiration (durée choisie par l'IA), `annuler` quand le fictif
  annule ; déjà exécutable -> au marché. Divergences de prix : exécuté chez Tradeco seulement -> gardé tant que
  l'ordre fictif vit, fermé s'il expire ; exécuté dans le fictif seulement -> PAS d'achat en retard. Fin de semaine
  et coupe-circuit annulent aussi les ordres. Essai réel (0,01 lot loin du prix, posé puis annulé) : OK. Tests
  `test_tradeco.py` 13 ; suite complète 109 verts.
- **15/10 14h57 — les 3 réveils** (accord du chef de projet : « les 3 sont bien ») : (1) ALERTES DE PRIX choisies
  par elle à chaque regard (tête `decisions.alerte`, au-dessus / au-dessous, 1/20 à 3 bougies du jour,
  `log_ecart` 8 valeurs, `charger` reprend les anciens élèves) ; (2) réveil sur GROS MOUVEMENT (une bougie du jour
  depuis son dernier regard) et 15 min AVANT une annonce importante (`ecole/regard.py`, `Etat.raison`, le carnet
  dit « Réveillée par … ») ; (3) délai MAXIMUM 4 h (`REGARD_MAX` = 16 ; un ordre à l'avance peut encore vivre
  5 jours : `ATTENTE_MAX`). École, contrôle et démo identiques (école reprise à la leçon 831 : ~7-9 regards par
  jour). Démo : alertes sauvées entre deux passages, rendez-vous anciens ramenés à 4 h. 114 tests verts.
- **15/10 soir — PISTE « OUVERTURE DE NEW YORK » (cassure du range d'ouverture) : NO-GO.** Archive avant travaux :
  `archives/collapsar_avant_ORB_20261015_1908.zip`. Données minute : S&P 500 / Nasdaq = HistData
  (`donnees/histdata.py`, 2015 -> 10/2026 ; ATTENTION leurs heures sont DÉJÀ l'heure de New York avec l'heure d'été,
  vérifié : accord 95-98 % avec Dukascopy et saut d'agitation à 9h30) ; or = Kaggle 1 min (heure serveur - 7 h,
  vérifié : sauts à 8h20/8h30). Dukascopy minute trop bridé (`donnees/minutes.py`, abandonné). Moteur
  `regarder/orb.py` (tests `tests/test_orb.py`), frais = fiches FTMO 0,012 % x écart d'ouverture Tradeco (1,07 / 1,16
  / 1,0) + glissement des ordres stop. 18 variantes -> seuil 3. Choix 2015-2021 (force contre le jumeau) : Nasdaq N=5
  (+1,7), S&P N=5 (+1,9), or N=30 (+3,6) ; vérification 2022-2023 : +0,4 / +1,2 / +1,7 ; PÉRIODE CACHÉE 2024-2026
  (évaluée une fois, verrou `vie/orb/cachee.json`) : Nasdaq 685 trades +0,009 R force +0,6 ; S&P 686 trades -0,115 R
  force +1,0 ; or 675 trades -0,082 R force -0,3. Le sens de la cassure ne bat pas le hasard ; les frais (0,09 à 0,17
  R par trade) mangent le reste ; l'effet de l'or (2015-2021) a disparu. Seule vérification propre restante : en
  direct, à partir d'aujourd'hui.
- **15/10 nuit — LABORATOIRE SMC : rien de prouvé.** Archive `archives/collapsar_avant_SMC_20261015_2028.zip`.
  Définitions figées AVANT les tests : `docs/SMC_DEFINITIONS.md` (empreinte `vie/smc/empreinte_definitions.txt`).
  Code `regarder/smc/` (bougies, noyaux numba, labo, rapport ; tests `tests/test_smc.py`), EURUSD HistData ajouté
  (heures vérifiées). numba installé (numpy inchangé). Biais trouvé et corrigé avant la période cachée : la bougie
  d'entrée d'un ordre limite est suivie à la minute (sinon le jumeau était stoppé par un extrême d'avant l'entrée).
  366 variantes -> seuil 3,44. Un seul candidat retenu (OB qui provoque un BOS, or H1) : période cachée 303 trades,
  -0,047 R, force -0,46. Stratégie perso : M5 ruinée par les frais (stop 0,03 % du prix, frais ~1 R) ; H1 légèrement
  positive (1er contact +0,085 R, force 1,9) mais non prouvée ; le filtre FVG fait toujours moins bien. OB et zones
  perso : réaction réelle au-dessus du hasard (59,8 % contre 57,0 % ; 54,7 % contre 47,9 %) mais pas d'argent après
  frais. Rapport : `reports/Laboratoire SMC.md` ; annexes `vie/smc/*.csv`.
- **15/10 21h-21h40 — stratégie MULTI-UNITÉS du chef de projet** (`docs/SMC_MULTI_UT.md` + avenant 1, figés ;
  `regarder/smc/multi.py`) : zones de fond H4 / journalier à volume fort, affinées sur la bougie avant l'explosion,
  sorties par tiers (2 R, sommet H1, zone opposée). 4 marchés à la minute : H4 -> M15 = +0,5 R sur 73 trades
  (force 1,2), trop peu de cas. 45 marchés (bougies de 15 min, bougie d'entrée ignorée des deux côtés) : H4 -> M15
  marge 0,5 = +0,27 R sur 439 trades 2015-2021 (force 1,0) mais -0,40 à -0,49 R sur 2022-2023 (force -1,2 à -2,0) ;
  marge 0,2 et journalier : négatifs. Aucun candidat retenu -> période cachée NON ouverte pour cette méthode.
  Prochaine piste demandée : traduire l'indicateur TradingView du chef de projet (ses vraies zones) et sa cascade
  D1 -> H4 -> H1 -> M30 -> M15 -> M5 -> M3 -> M1.
- **15/10 22h — CASCADE avec l'INDICATEUR du chef de projet (indicateur de zones d'offre et de demande (supply and demand), Pine traduit à l'identique :
  bougie opposée + FVG + BOS sur 4-5 bougies, effacée à la clôture au-delà du milieu)** : `docs/CASCADE_ZONES.md`
  (figé, réponses du questionnaire), `regarder/smc/zones supply and demand.py`, tests `tests/test_nono.py`. 8 paires sur 4 marchés à la
  minute + 3 paires sur 45 marchés. Résultat : aucune variante retenue (période cachée NON ouverte). Cascades D1 / H4 :
  presque pas de cas (2 à 20 en 7 ans sur 4 marchés). H1 -> M15 : 1 096 trades sur 45 marchés, gain médian -1,16 R,
  28 % de gagnants, force -0,8. Stops très serrés (zone d'entrée = UNE bougie M15/M5 : 0,044 % du prix en médiane)
  -> frais ~0,4 R par trade. Même sans les stops < 0,05 % : ~-1 R médian.
- **15/10 22h10 — ZONES GIGOGNES** (`docs/CASCADE_ZONES.md` avenant 1, `regarder/smc/gigogne.py`) : chaîne de zones zones supply and demand
  qui se chevauchent, du journalier / H4 jusqu'au M3 (M15 pour les 45 marchés), entrée au milieu de la plus petite.
  Aucune variante retenue, période cachée NON ouverte. 45 marchés départ H4 : moyenne +0,30 R mais due à UN trade à
  +817 R (stop microscopique) ; sans les 5 meilleurs -0,69 R ; médiane -1,2 R ; années tantôt + tantôt - ;
  2022-2023 : -0,58 R. 4 marchés à la minute : -0,14 R (stop A), -0,91 R (stop B). Départ journalier : trop peu de cas.
- **15/10 22h40 — « les stops sont trop petits » (avenant 2, stop minimum = 0,1 / 0,2 / 0,3 ATR journalier)** : théorie
  CONFIRMÉE pour les pertes, pas pour un gain. Zones gigognes départ H4 : frais 0,38-0,60 R -> 0,04-0,11 R ; moyenne
  sans les 5 meilleurs -1,17 / -0,69 R -> -0,20 à 0,00 R ; force max 1,9 ; aucune variante retenue (période cachée
  NON ouverte). Les grands stops arrêtent l'hémorragie mais ne créent pas d'avantage : on tombe à environ zéro.
- **15/10 23h — STRATÉGIE DU CHEF DE PROJET SUR LES DERNIÈRES ANNÉES** (avenant 3, version figée « Gigogne H4 stop A
  plancher 0.2 », évaluée sur 2024-2026 à sa demande) : 4 marchés à la minute 109 trades, -0,27 R (médiane -1,06,
  24 % de gagnants, force -2,0) ; 45 marchés 473 trades, -0,34 R (médiane -1,08, 31 %, force -1,6). Non prouvé,
  négatif ; par an 2022 à 2026 surtout négatif (seul 2023 sur 45 marchés : +0,21 R). ATTENTION : le 1er calcul de
  cette évaluation n'a PAS pu être reproduit (4 850 lignes au lieu de 1 533 sur les 45 marchés ; fichiers
  `vie/smc/*_DEFECTUEUX_non_reproductible.*`) ; le calcul de contrôle (`strategie_chef_trades_REPRISE_controle.csv`)
  redonne exactement les calculs précédents et sert de verdict (`cachee_strategie_chef.json`). Les deux sont négatifs.
  Cause de l'anomalie non trouvée : à surveiller si elle réapparaît.
- Gardien (`surveillance/gardien.ps1`) : surveille aussi la DÉMO À BLANC (arrêt volontaire : `vie/direct/ARRET`) et
  les collecteurs gTrade / Ostium (relancés s'ils manquent). Suite complète : 93 tests verts.
- Examen du meilleur élève des mondes (07h32, 09/2023 -> 09/2025, 41 challenges, 4 marchés) : +0,10 %/mois, avantage
  sur le hasard +0,19 %/mois (± 0,18, force 1,1 : pas prouvé), 0 mur, 0 challenge réussi (taille trop petite).

## 7. Outils utiles construits le 14/10
- `regarder/vision_trader.py` : moteur du vrai chemin du prix pour n'importe quel coup (stop d'abord dans une même
  bougie, trou payé à l'ouverture, fermeture avant pause > 2 h) — réutilisable pour juger des coups.
- `juge/verdict_rapide.py`, `juge/examen_annonces.py` (exemple de branchement d'une IA sur le simulateur FTMO fidèle,
  challenges de 90 jours tous les 2 jours), `juge/grand_examen.py`.
- `donnees/calendrier.py` (Forex Factory — à éviter — et MetaTrader `charger_mt5(direct=True)`).
- `surveillance/comparer_heures_prix.py` (accord prix téléchargés / serveur MetaTrader, mois par mois).
- Expériences `regarder/experience_*.py` (par cœur, vue d'ensemble, simple, semaine, annonces...) : résultats en §3.
