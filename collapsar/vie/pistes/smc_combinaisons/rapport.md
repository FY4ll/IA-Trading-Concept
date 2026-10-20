# Piste « combinaisons SMC » — COLLAPSAR apprend à MÉLANGER les concepts (16/10/2026)

Demande du chef de projet : « les concepts il faut les mélanger, pas les prendre séparément ». COLLAPSAR (un petit modèle
d'arbres, fait maison) a appris, sur des centaines de milliers de contacts de zones, quelles combinaisons de concepts,
quel EMPLACEMENT de stop et quelle SORTIE donnent le meilleur résultat. Tout est écrit d'avance dans l'en-tête de
`collapsar/regarder/pistes/smc_combinaisons.py` (règles + 5 avenants, chacun daté avant le résultat qu'il concerne).

## Ce que COLLAPSAR voyait et choisissait

- **Événement** : le 1er contact d'une zone (bloc d'ordres, zone zones supply and demand, zone d'offre / demande ; définitions figées du
  laboratoire, inchangées), en 15 min et en 1 h, dans le sens de la zone. Entrée au marché à la clôture de la bougie de
  contact (tout est connu à cet instant). Plusieurs zones touchées ensemble = un seul événement « mélangé ».
- **31 faits** connus au contact : type(s) de zone, FVG du départ, FVG ouvert dans la zone (taille), BOS / CHoCH qui a
  créé la zone, balayage de liquidité récent, zone imbriquée dans une zone H1 / H4 / journalière (profondeur gigogne),
  zone opposée au-dessus, âge, zone déjà testée, volume fort, position dans la jambe (discount / premium), tendance de
  l'unité, H4, journalière, séance, week-end, largeur de zone, impulsion, rejet de la bougie, accord avec la cassure 24 h.
- **6 emplacements de stop** (comme un trader : derrière la zone, derrière le dernier creux M15 / H1 / H4, derrière la
  liquidité, derrière le FVG ou l'impulsion) x **8 sorties** (2 R, prochaine liquidité, zone opposée, sommet H1, et la
  gestion du chef : 80 % au TP1 = 1 / 1,5 / 2 R ou liquidité, 20 % qui courent vers la cible suivante avec le stop au
  prix d'entrée). 48 couples par événement, chacun mesuré sur le vrai chemin du prix, stop d'abord si doute, frais,
  glissements et nuits FTMO compris, tenue 2 jours au plus.
- Le modèle prédit le résultat de chaque couple et ne prend que le meilleur s'il est prévu > 0 (« choix appris ») ;
  risque 0,5 % par trade, une position à la fois par marché.
- **Témoin hasard** (demande du chef) : les mêmes zones (même hauteur, même distance au prix) posées à un moment tiré au
  hasard, même chaîne, même modèle. Si les vraies zones ne font pas mieux que ces fausses zones, l'avantage ne vient pas
  des zones.

## Résultats — CRYPTOS (frais FTMO corrigés : BTC 0,083 %, ETH 0,112 %, autres 0,12 % par aller-retour)

Apprentissage : BTC, ETH + groupe A Binance (ADA, ATOM, BCH, DOGE, EOS, FIL, LTC, NEAR, SOL, UNI, XLM, XRP), années
<= 2021. Contrôle : mêmes marchés, 2022 -> 10/2026 (jamais vus).

| 2022-2026 (contrôle) | Trades | Gain moyen (R) | Compte %/mois | Baisse max | Pire jour | Challenges réussis / morts | Force contre jumeau (par jour) |
|---|---|---|---|---|---|---|---|
| **Choix appris** (principal) | 7 341 | **-0,018** | **-1,14** | -90 % | -6,6 % | 20 % / 75 % | +1,5 (seuil 3) |
| (b) jumeau (sens au hasard) | 7 341 | -0,038 | -2,45 | | | 2 % / 93 % | |
| Témoin hasard (fausses zones, même modèle) | 6 781 | -0,026 | -1,56 | | | | |
| (a) toutes les zones, stop derrière la zone + 2 R | 78 146 | -0,349 | ruine | | | | |
| (c) cassure 24 h seule | 14 896 | | -0,84 | -91 % | -8,2 % | 18 % / 79 % | |

Pour information : sur l'apprentissage (<= 2021) le même modèle faisait +0,050 R, +1,9 %/mois, force 5,4 : ce qu'il a
appris ne s'est pas transporté sur 2022-2026. Avec les anciens frais (0,03 / 0,05 %, avant correction), le contrôle
était déjà négatif : -0,024 R, -2,6 %/mois (`resultats_anciens_frais.json`).
**Verdict crypto : INUTILE.** Contrôle négatif -> la confirmation sur le groupe B (ALGO, AVAX, BNB, DOT, ETC, LINK,
MATIC, POL, TRX, VET, XMR) reste FERMÉE, jamais regardée.

## Résultats — OR / INDICES / DEVISES (frais FTMO mesurés x 1,25 + nuits)

Apprentissage 2015-2021 + contrôle 2022-2026 : or, S&P 500, Dow Jones, DAX, EURUSD, USDJPY, AUDUSD, USDCHF, NZDUSD.
Confirmation (choisie avant) : Nasdaq, GBPUSD, USDCAD, argent.

| | Trades | Gain moyen (R) | Compte %/mois | Baisse max | Pire jour | Challenges réussis / morts | Force (par jour) |
|---|---|---|---|---|---|---|---|
| **Choix appris, contrôle 2022-2026** | 3 014 | **+0,012** | **+0,31** | -38 % | -2,5 % | 51 % / 34 % | +2,4 (seuil 3) |
| (b) jumeau | 3 014 | -0,026 | -0,69 | | | 3 % / 79 % | |
| Témoin hasard (fausses zones) | 3 129 | **+0,030** | **+0,81** | | | | |
| (a) toutes les zones, stop zone + 2 R | 40 916 | -0,210 | ruine | | | | |
| (c) cassure 24 h seule | 6 960 | | -0,48 | -45 % | -4,5 % | 0 % / 47 % | |
| **Confirmation 2022-2026** (4 marchés jamais appris) | 1 314 | **-0,022** | **-0,25** | | | | +2,0 |
| Confirmation, témoin hasard | 1 385 | -0,023 | -0,28 | | | | |
| Confirmation toutes années | 3 024 | -0,046 | -0,50 | | | | |

**Verdict or / indices / devises : FAIBLE, sans valeur pratique.** Le contrôle est à peine positif (+0,3 %/mois, sous le
seuil de preuve), les fausses zones font MIEUX que les vraies (+0,8 %/mois), et la confirmation sur 4 marchés neufs est
négative. Ce que le modèle a trouvé n'est pas une combinaison SMC : c'est surtout « acheter (61 % d'achats) avec un
stop large derrière le creux H4 », qui profite de la hausse de fond des indices et de l'or 2022-2026 (le jumeau, qui
achète et vend au hasard, perd).

## Les emplacements préférés (couples choisis au contrôle)

| Cryptos : couple choisi | Trades | R moyen | Or / indices / devises : couple choisi | Trades | R moyen |
|---|---|---|---|---|---|
| stop derrière le creux H4 + 2 R | 3 000 | -0,024 | stop derrière le creux H4 + 2 R | 2 188 | +0,001 |
| stop derrière le creux H4 + 80/20, TP1 1,5 R | 1 928 | -0,032 | stop derrière le creux H1 + 2 R | 495 | +0,038 |
| stop derrière le creux H1 + 80/20, TP1 1,5 R | 494 | +0,105 | stop derrière le FVG / l'impulsion + 2 R | 101 | +0,084 |
| stop derrière le creux H1 + 2 R | 460 | -0,038 | stop derrière le creux H4 + prochaine liquidité | 75 | +0,028 |
| stop derrière le creux H4 + sommet H1 | 381 | -0,033 | stop derrière le creux M15 + 2 R | 49 | +0,015 |

Ce que COLLAPSAR a réellement appris : **le stop serré derrière la zone est le pire choix** (les frais et le bruit le
mangent : -0,35 R en crypto, -0,21 R ailleurs) ; plus le stop est loin (derrière un creux H1 / H4), moins on perd.
Il n'a trouvé AUCUNE combinaison de concepts qui gagne après frais.

## Les 10 combinaisons que le modèle préfère (en mots, avec leur R réel au contrôle)

L'arbre simple qui résume le modèle (il imite ses prévisions à 94-96 %) ne coupe presque que sur la distance du stop :
les concepts (FVG, BOS, balayage, zone H4, zones supply and demand…) ne changent presque rien à ses prévisions.

| # | Cryptos | R prévu | R réel contrôle | Or / indices / devises | R prévu | R réel contrôle |
|---|---|---|---|---|---|---|
| 1 | stop > 1,05 ATR jour + achat | +0,003 | -0,008 | stop > 1,12 ATR jour | -0,023 | -0,022 |
| 2 | stop > 0,81 ATR jour + vente + tendance J1 avec ou neutre | -0,025 | -0,006 | stop 0,73-1,12 ATR jour | -0,042 | -0,030 |
| 3 | stop 0,81-1,05 ATR jour + achat | -0,032 | -0,042 | stop 0,41-0,73 + séance d'Asie | -0,050 | -0,037 |
| 4 | stop 0,35-0,81 + zone de plus d'une bougie | -0,055 | -0,088 | stop 0,41-0,73 + Londres / New York | -0,071 | -0,052 |
| 5 | stop > 0,81 + vente + tendance J1 contre | -0,058 | -0,048 | stop 0,29-0,41 + séance d'Asie | -0,084 | -0,054 |
| 6 | stop 0,35-0,81 + zone toute fraîche | -0,076 | -0,083 | stop 0,29-0,41 + Londres / New York | -0,107 | -0,077 |
| 7 | stop 0,25-0,35 + zone de plus d'une bougie | -0,088 | -0,141 | stop 0,24-0,29 + impulsion <= 2 ATR | -0,128 | -0,097 |
| 8 | stop 0,25-0,35 + zone toute fraîche | -0,110 | -0,141 | stop 0,20-0,24 + séance d'Asie | -0,133 | -0,094 |
| 9 | stop 0,18-0,25 + zone de plus d'une bougie | -0,135 | -0,187 | stop 0,24-0,29 + impulsion > 2 ATR | -0,158 | -0,105 |
| 10 | stop 0,18-0,25 + zone toute fraîche | -0,161 | -0,199 | stop 0,20-0,24 + Londres / New York | -0,159 | -0,120 |

(R moyen de toutes les lignes (événement, couple) de chaque groupe au contrôle, sans sélection.)

## Contre le témoin hasard (la question du chef : « mes zones font-elles mieux que des zones au hasard ? »)

- Toutes zones confondues, couple par couple : les vraies zones font en moyenne +0,025 R (cryptos) et +0,010 R
  (or / indices / devises) de mieux que les fausses ; mieux sur 32 et 34 couples sur 48. C'est le même ordre que la
  mesure du coordinateur (~+0,1 R sur une autre gestion) : **un petit vrai effet des zones, mais 10 à 30 fois plus
  petit que les frais d'un stop serré.**
- Avec le stop derrière la zone + 2 R (la règle d'origine), les vraies zones font PIRE que les fausses (-0,045 R
  cryptos, -0,023 R ailleurs).
- Avec le choix appris : cryptos +0,009 R mieux que le témoin (les deux perdent), or / indices / devises -0,018 R
  (le témoin gagne plus).

## Verdict honnête

1. Aucune combinaison de concepts SMC ne gagne après frais sur des années jamais vues, ni en cryptos (frais FTMO réels
   0,08-0,12 %) ni sur l'or, les indices et les devises.
2. COLLAPSAR a bien appris quelque chose de vrai : **ne pas mettre le stop collé à la zone** ; plus le stop est derrière
   une structure large (creux H1 / H4), moins on perd. Mais même là, le résultat est autour de zéro.
3. Le petit avantage des zones contre le hasard existe (quelques centièmes de R) mais il est noyé par les frais.

## Limites et ce qui manquerait pour aller plus loin

- Pas de minutes en crypto : entrée à la clôture de la bougie de contact, pas d'ordre limite au bord de la zone (un
  ordre limite paierait moins d'écart ; mais le laboratoire SMC, avec minutes, ne gagnait pas non plus).
- Frais de nuit crypto FTMO (30 %/an) payés : une position de 2 jours coûte ~0,17 % du prix.
- Les cryptos bougent ensemble : jusqu'à 14 positions à 0,5 % en même temps -> pire jour -6,6 %, au-delà de la limite
  FTMO de -5 %. Il faudrait un plafond de risque total.
- Le modèle d'arbres est simple (profondeur 3) ; le réseau de COLLAPSAR n'a pas été essayé (inutile tant que rien ne
  passe le contrôle : il apprendrait mieux le bruit de 2017-2021).
- Les années de contrôle 2022-2026 ont maintenant été vues (crypto deux fois, avec deux frais) : une nouvelle idée sur
  ces zones devra être jugée sur le direct.

## Fichiers

- Code : `collapsar/regarder/pistes/smc_combinaisons.py` (en-tête = règles écrites avant, avenants 1 à 5).
- Résultats : `resultats.json` (cryptos, frais corrigés), `resultats_anciens_frais.json`, `resultats_classique.json`,
  `confirmation_classique.json` (verrou : la confirmation or / indices / devises a été faite une fois),
  `modele*.pkl`, journaux `juger_*.log`, `confirmer_classique.log`, cache des événements `cache_evenements/`
  (le dossier `evenements/` contient un ancien cache d'essai, sans usage).
