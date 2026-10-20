# Piste « crypto_flux » : ce que voient les traders crypto et que les autres marchés n'ont pas (16/10/2026)

Code : `collapsar/regarder/pistes/crypto_flux.py` (règles et liste fermée de 11 variantes écrites dans l'en-tête AVANT
tout résultat). Données neuves : `data/binance_futures/` (voir son LISEZMOI : 25 cryptos, contrats perpétuels Binance,
sommes de contrôle toutes conformes, heure alignée avec le comptant). Chiffres : `developpement.json`,
`controle.json` (verrou), `confirmation.json` (verrou, groupe B ouvert une seule fois), diagnostics
`diagnostic_developpement.json`, `diagnostic_C1_contre_elan.json`, journaux `journal_*.txt`.

## Règles communes
- Décision à chaque fin d'heure UTC, avec seulement l'information connue à ce moment (financement : après son heure de
  règlement ; positions ouvertes et ratios : 15 min de retard de sécurité ; flux : bougies closes ; prime : bougie 1 h
  close). « Extrême » = centile calculé sur les 90 ou 180 jours PASSÉS. Prix du trade = comptant Binance (filtre commun).
- Tenue fixe (4 h, 24 h ou 72 h), une position à la fois par marché. Frais FTMO crypto par aller-retour : BTC 0,083 %,
  ETH 0,112 %, autres 0,12 % ; nuit 30 %/an par minuit serveur franchi. Taille : 0,5 % d'agitation par trade, levier 1.
- Développement : BTC, ETH + groupe A (ADA, ATOM, BCH, DOGE, EOS, FIL, LTC, NEAR, SOL, UNI, XLM, XRP), jusqu'à 2023.
  Contrôle : mêmes marchés 2024 -> 09/2026. Confirmation : groupe B (ALGO, AVAX, BNB, DOT, ETC, LINK, MATIC, POL, TRX,
  VET, XMR), une fois. Seuil de preuve 3. « Force jour » = même calcul sur les gains par jour (les cryptos bougent
  ensemble : c'est la mesure honnête, exigée >= 3 pour être retenue).

## 1. Développement (jusqu'à 2023), les 11 variantes
| Variante | Trades | Gain %/mois après frais (sans frais) | Force (jour) | Baisse max | Challenges réussis / morts (jumeaux) | Lien avec la cassure 24 h |
|---|---|---|---|---|---|---|
| F1 financement extrême, contraire (72 h) | 3 693 | -1,75 (+0,36) | +0,4 (+0,3) | -88 % | 22 / 77 (6 / 90) | -0,01 |
| F2 financement + élan (72 h) | 3 521 | +1,37 (+3,35) | **+4,2** (+2,7) | -95 % | 41 / 53 (7 / 85) | +0,02 |
| O1 positions en hausse + prix extrême (24 h) | 1 337 | -1,54 (-0,66) | -1,1 (-0,8) | -83 % | 0 / 98 | -0,10 |
| O2 positions qui fondent = liquidations, contraire (24 h) | 1 771 | -0,23 (+0,93) | +1,4 (+0,8) | -60 % | 20 / 75 | -0,01 |
| L1 flux acheteur 1 h, suite (4 h) | 31 386 | -31 (-3,5) | -1,9 | ruine | 0 / 99 | +0,13 |
| L2 flux 4 h, retour (24 h) | 10 110 | -5,1 (+0,34) | +0,3 | ruine | 9 / 86 | +0,09 |
| L3 flux 24 h contre prix, absorption (24 h) | 297 | -0,40 (-0,30) | -1,1 | -27 % | 0 / 46 | +0,02 |
| P1 prime du perpétuel, contraire (72 h) | 2 745 | -3,2 (-1,7) | -2,4 | ruine | 20 / 79 | -0,03 |
| **C1 comptes acheteurs extrêmes, contraire (24 h)** | **2 764** | **+1,76 (+3,75)** | **+4,5 (+3,2)** | -37 % | **60 / 39 (6 / 89)** | +0,12 |
| T1 gros traders contre la foule (24 h) | 1 431 | +0,63 (+1,80) | +3,1 (+2,3) | -36 % | 24 / 71 (2 / 92) | +0,00 |
| S1 surchauffe financement + positions + prix (72 h) | 611 | -0,94 (-0,49) | -1,2 | -40 % | 0 / 98 | -0,05 |
| (repère) C2 cassure 24 h, mêmes marchés et frais | 11 632 | -1,79 (+1,49) | +1,5 (+0,7) | ruine | 15 / 84 | 1 |

Règle mécanique : seule **C1** passe (gain > 0, force >= 3 ET force jour >= 3) -> retenue. F2 (force jour 2,7) et T1
(2,3) échouent ; F2 vient d'ailleurs presque entièrement de 2021 (sans 2021 : -0,06 %/mois) et ne gagne que sur les
achats. Le flux d'ordres (L1-L3), le financement contraire (F1) et la prime (P1) n'apportent rien après frais.

C1 = quand la part des COMPTES acheteurs (tous les clients Binance) est au plus haut de 90 jours -> vendre 24 h ; au plus
bas -> acheter 24 h.

## 2. Contrôle et confirmation de C1
| Période | Trades | Gain %/mois après frais | Sans frais | Baisse max | Pire jour | Force (jour) | Challenges réussis / morts | Jumeaux |
|---|---|---|---|---|---|---|---|---|
| Développement (≈ 2022-2023, BTC dès 10/2020) | 2 764 | +1,76 | +3,75 | -37 % | -9,1 % | +4,5 (+3,2) | 60 / 39 % | 6 / 89 % |
| **Contrôle 2024 -> 09/2026** | 3 556 | **+0,88** | +3,72 | -38 % | -5,9 % | **+3,3** (+2,4) | 18 / 70 % | 3 / 88 % |
| Groupe B jamais vu, tout | 4 336 | +0,06 | +2,42 | -55 % | -17,5 % | **+3,5** (+2,8) | 41 / 56 % | 4 / 89 % |
| Groupe B jusqu'à 2023 | 1 946 | +1,04 | +3,62 | -35 % | -5,4 % | +3,4 (+2,8) | 29 / 42 % | 4 / 87 % |
| Groupe B 2024-2026 | 2 390 | **-0,63** | +1,57 | -55 % | -17,5 % | +1,7 (+1,4) | 33 / 63 % | 4 / 85 % |

Verdict de la règle écrite : contrôle positif, confirmation « prouvée » (gain > 0, force 3,5 >= 3). Mais le gain après
frais du groupe B est presque nul (+0,06 %/mois) et négatif depuis 2024.

## 3. Recherche du défaut (C1)
- Heures : 1 h de retard en plus sur toute l'information -> force 4,3, +1,53 %/mois (rien ne vient d'un regard dans le
  futur). Prix du perpétuel au lieu du comptant : identique (+1,75). Sans BTC/ETH : +1,01 %/mois, force 3,0. Sans sa
  meilleure année (2022) : +0,55 %/mois, force 2,9. 12 marchés sur 14 positifs ; achats ET ventes positifs.
- Ce n'est PAS l'élan déguisé : C1 va dans le sens de l'élan 24 h dans 75-85 % des cas, mais l'élan 24 h pris aux mêmes
  moments ne fait rien (force 0,5 en développement, 0,8 en contrôle), et quand C1 va CONTRE l'élan il a encore raison
  (force 3,4 puis 2,5). L'information « la foule des comptes est d'un seul côté » est réelle.
- Le pire jour du groupe B (-17,5 %) = 03/12/2024 : TRX +75 % en 24 h contre une vente de C1 (TRX n'est pas coté chez
  FTMO). Sans ce jour, groupe B 2024-2026 ≈ -0,1 %/mois. Aucune protection (stop) n'était prévue.
- Défaut corrigé en cours de route : le 1er calcul jetait toute la ligne des métriques quand le ratio des gros traders
  manquait (presque toute l'année 2022) ; corrigé AVANT le contrôle (colonnes traitées séparément), développement
  refait ; le 1er essai est gardé (`journal_*_essai1_bogue_metrics.txt`, où rien n'était retenu).
- Lien avec la cassure 24 h : +0,12 (développement), +0,09 (contrôle) -> presque indépendant, utile pour un compte
  combiné. Mais la cassure 24 h elle-même perd -1,8 %/mois sur ces cryptos aux frais FTMO réels.

## Verdict honnête
- **Une vraie information trouvée** : la position de la foule des comptes Binance, prise à contre-pied 24 h, bat son
  jumeau sur 3 jeux indépendants (forces 4,5 / 3,3 / 3,5). C'est la première information propre aux cryptos qui tient
  hors échantillon dans ce projet.
- **Mais elle ne paie presque pas après les frais FTMO** : ~3,7 %/mois brut se réduit à +0,9 (contrôle) et -0,6
  (groupe B 2024-2026) après 0,12 % de frais + 1 nuit par trade. Le flux d'ordres, le financement et la prime : rien.
- À la taille testée (0,5 % par trade sur 14 marchés liés), la baisse atteint 37 à 55 % : impossible chez FTMO (mur à
  -10 %). Ramenée à un quart de la taille, la baisse passe sous 10-14 % mais le gain tombe à ~0,2 %/mois.

## Ce qui manquerait pour aller plus loin
1. Coûts : un compte à frais plus bas (futures CME micro sans frais de nuit, ou Kraken Prop en perpétuels) changerait
   tout : sans frais, C1 fait +2,4 à +3,7 %/mois. Chez FTMO, relever le vrai écart et le vrai taux de nuit sur l'essai.
2. Fixer AVANT un nouveau test : plafond de positions ensemble, taille 0,1-0,15 % et un stop, sur les seules cryptos
   cotées chez FTMO ; puis suivi à blanc en direct (les métriques Binance sont publiques en temps réel).
3. Tenue plus courte pour éviter la nuit (fermer avant minuit serveur) : à écrire comme nouvelle variante, jugée sur
   données neuves (le direct), pas re-choisie sur ces années.

---

# SUITE (16/10/2026, demande du coordinateur) — ESTIMATIONS, PAS DES PREUVES

**Toutes les années ci-dessous ont déjà été vues pour C1** (développement, contrôle, groupe B). Les règles ont été
figées par écrit avant le calcul (en-tête de `collapsar/regarder/pistes/crypto_flux_compte.py`), mais il s'agit
d'estimations ; **le seul juge restant est le direct.** Chiffres : `suite.json`, journaux `journal_suite_*.txt`.

## 1. Coûts par lieu (mêmes trades C1, taille 0,5 % d'agitation, sans plafond de positions)
| Lieu (coût par aller-retour) | Dév. ≤ 2023 | Dév. 2024 -> 09/2026 | Groupe B ≤ 2023 | Groupe B 2024 -> 09/2026 |
|---|---|---|---|---|
| a FTMO (0,083-0,12 % + nuit 30 %/an) | +1,76 %/mois, baisse -37 % | +0,88, -38 % | +1,04, -35 % | **-0,63**, -55 % |
| b bourse preneur (0,10 % + financement réel) | +2,81, -30 % | +2,35, -30 % | +2,34, -30 % | +0,63, -39 % |
| c bourse faiseur 70 % (0,058 % + financement) | +3,23, -28 % | +2,96, -27 % | +2,87, -28 % | +1,09, -37 % |

- Le financement réel est EN FAVEUR de C1 (il va contre la foule, donc reçoit souvent le financement payé par elle) :
  la différence entre (a) et (b) vient surtout de la nuit FTMO à 30 %/an, bien plus chère que le financement réel.
- (c) suppose 70 % d'ordres limites exécutés sans défaveur : optimiste.

Même périmètre BTC + ETH seulement (le seul possible sur les contrats micro CME) :
| BTC + ETH | ≤ 2023 | 2024 -> 09/2026 |
|---|---|---|
| a FTMO, tous les trades | +1,15 %/mois, baisse -9 % | +0,65, -8 % |
| b bourse preneur, tous les trades | +1,36, -8 % | +0,92, -7 % |
| d CME micro (0,03 % + 1 pas ≈ 0,047 %), tous les trades | +1,44, -8 % | +1,09, -7 % |
| d CME micro, **séance CME seulement** (42 % des trades perdus : week-ends, pause) | +0,69, -6 % | +0,74, -8 % |

Les contrats micro CME sont les moins chers, mais la fermeture du week-end retire près de la moitié des trades (les
moments de foule extrême du week-end). La base des contrats à terme n'est pas comptée.

## 2. Version « compte financé » (figée avant : 17 cryptos, risque 0,15 % par trade, stop 1,5 x agitation du jour,
## 5 positions au plus dont 3 dans le même sens, arrêt du jour -2 %, sortie 24 h)
| Coût | Période | Trades/mois | %/mois | Baisse max | Pire jour | Force | FTMO 2 étapes réussis / morts (jumeaux) | < 6 / < 12 mois | Société crypto réussis (< 12 mois) | Espérance € / challenge |
|---|---|---|---|---|---|---|---|---|---|---|
| a FTMO | ≤ 2023 (dès 10/2020) | 58 | +0,35 | -4,8 % | -0,7 % | +3,9 | 0 / 0 % (0 / 59 %) | 0 / 0 % | 20 % (0 %) | -540 |
| a FTMO | 2024 -> 09/2026 | 98 | **-0,07** | -6,7 % | -1,2 % | +2,3 | 0 / 0 % (0 / 54 %) | 0 / 0 % | 0 % | -540 |
| b bourse | ≤ 2023 | 58 | +0,52 | -3,9 % | -0,7 % | +3,9 | 17 / 0 % (0 / 12 %) | 0 / 0 % | 82 % (8 %) | -540 (crypto -336) |
| b bourse | 2024 -> 09/2026 | 98 | +0,20 | -4,5 % | -1,2 % | +2,3 | 0 / 0 % (0 / 12 %) | 0 / 0 % | 0 % | -540 |

Lecture : à ce risque, le compte est sûr (baisse < 7 %, pire jour -1,2 %, jamais mort) mais **beaucoup trop lent** :
aucun challenge réussi en moins de 12 mois au coût FTMO, l'espérance d'un challenge est la perte des 540 €. Avec le
stop (11-14 % des trades) et le plafond de 5 positions, l'avantage est plus mince que dans le test sans plafond.

## 3. Combinaison avec la cassure C2 (BTC/ETH) et les zones du chef (niveau 9 % de compte_combine), 2022 -> 09/2026
Addition jour par jour (approchée : les briques gardent leurs coûts FTMO ; pire jour et challenges approchés sur les
clôtures journalières ; aucun jumeau). Les deux briques seules donnent ici +1,14 %/mois en 2022-2023 contre +0,95 %
dans compte_combine (compte unique avec arrêts communs) : l'approximation est un peu flatteuse.
| Compte | 2022-2023 | 2024 -> 09/2026 | Baisse max | FTMO réussis / morts, < 12 mois (tout) | Espérance € (tout) |
|---|---|---|---|---|---|
| C1 seul (coût b) | +0,70 %/mois | +0,20 | -4,5 % | 6 / 0 %, 0 % | -540 |
| cassure + zones | +1,14 | +0,53 | -15,5 % | 48 / 17 %, 25 % | +650 |
| C1 + cassure | +1,21 | +0,46 | -7,9 % | 37 / 0 %, 14 % | +611 |
| C1 + cassure + zones | +1,84 | +0,73 | -15,5 % | 53 / 24 %, 33 % | **+2 840** |

Lien jour par jour : C1 / cassure +0,24, C1 / zones +0,07. C1 ajoute environ +0,4 %/mois sans presque rien ajouter à la
baisse : utile comme 3e brique, inutile seul à ce risque.

## 4. La donnée en direct
- Gratuite, sans clé : API publique `https://fapi.binance.com/futures/data/globalLongShortAccountRatio` (5 min à 1 jour,
  500 lignes, 30 derniers jours seulement). Lecteur : `collapsar/donnees/binance_foule.py` (lecture seule ; aussi
  gros traders et positions ouvertes).
- Mesuré : la valeur d'horodatage T paraît 20 s à ~5 min après T ; elle est identique (à 0,0001 près) à la ligne T - 5
  min des fichiers journaliers. Le test historique l'utilisait l'équivalent de T + 10 min : le direct est plus rapide,
  donc rien dans le test ne dépendait d'une information impossible à avoir en direct.

## Verdict de la suite
L'information C1 est réelle, mais **chez FTMO elle ne paie pas seule** (nuit à 30 %/an ; version prudente : -0,07
%/mois depuis 2024). Ailleurs elle tient mieux : en bourse au marché, +0,2 à +2,4 %/mois selon la taille ; sur CME,
coût minimal mais week-ends perdus. Son meilleur usage estimé : **3e brique** d'un compte cassure + zones (+2 840 €
d'espérance par challenge contre +650 sans elle, sur des années déjà vues). Prochaine étape : un suivi à blanc en
direct de la version figée au point 2, via `binance_foule.py`.

## 5. Variante C1-JOUR (écrite avant le calcul ; ESTIMATION, années déjà vues)
Même signal ; fermée à 23h45 serveur (aucune nuit FTMO), rouverte à 00h15 si le signal est toujours actif au même
sens (59 % des trades rouverts), sortie à 24 h ; 2 allers-retours FTMO si elle traverse minuit. Règles dans l'en-tête
de `crypto_flux_compte.py` (point 4) ; chiffres `suite.json` (clés `c1_jour_*`), journal `journal_suite_c1_jour.txt`.

| Mesure (coût FTMO) | Période | C1 d'origine (nuit payée) | C1-JOUR |
|---|---|---|---|
| Pleine taille, développement | jusqu'à 2023 | +1,76 %/mois, force 4,5, chall. 60/39 % (jum. 6/89) | +1,49, force 4,3, 66/33 % (5/89) |
| Pleine taille, développement | 2024 -> 09/2026 | +0,88, force 3,3, 18/70 % (3/88) | **+0,18**, force 2,9, 8/86 % (2/88) |
| Pleine taille, groupe B | jusqu'à 2023 | +1,04, force 3,4, 29/42 % | +0,92, force 3,5, 29/28 % |
| Pleine taille, groupe B | 2024 -> 09/2026 | -0,63, force 1,7, 33/63 % | -0,42, force 2,1, 22/74 % |
| Compte financé (0,15 %, 17 cryptos, grille 15 min) | jusqu'à 2023 | +0,35, baisse -4,8 %, FTMO 0 % réussis (jum. 0/69 % morts) | +0,40, -4,0 %, 0 % (0/56) |
| Compte financé | 2024 -> 09/2026 | -0,07, -6,7 %, 0 % | +0,05, -6,7 %, 0 % |
| 3e brique + cassure + zones (tout coût FTMO), 2022 -> 09/2026 | tout | +1,15 %/mois, baisse -15,7 %, FTMO 52/24 %, < 12 mois 30 %, **+2 420 €** | +1,03, -17,7 %, 50/30 %, 30 %, +2 185 € |
| (repère) cassure + zones seules | tout | +0,79 %/mois, -15,5 %, 48/17 %, 25 %, +650 € | |

Lecture : supprimer la nuit ne paie pas. Le 2e aller-retour (0,083-0,12 %) coûte autant que la nuit évitée (0,083 %),
et le trou de 23h45 à 00h15 plus les 41 % de trades non rouverts enlèvent une partie de l'avantage (brut par trade
+0,38 % -> +0,33 %, puis +0,29 % -> +0,22 % en 2024-2026). C1-JOUR ne fait mieux que dans le compte financé
(+0,05 contre -0,07 %/mois depuis 2024), où c'est encore trop lent pour un challenge. En 3e brique, C1 d'origine
reste meilleur (+2 420 € contre +2 185 € d'espérance par challenge, sur des années déjà vues).