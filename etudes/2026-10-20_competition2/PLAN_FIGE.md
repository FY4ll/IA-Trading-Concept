# Compétition 2 — 3 hypothèses neuves à rotation lente (plan FIGÉ le 20/10/2026, AVANT toute mesure)

Leçon des 108 idées du registre : à 10 %/an de volatilité, les frais FTMO tuent ce qui trade chaque jour, les frais de
nuit tuent ce qui tient longtemps à l'achat, la règle d'inactivité (30 jours) tue ce qui trade rarement. Les 3
hypothèses ci-dessous tradent toutes les 2 semaines (ou chaque jour seulement si la prévision dépasse les frais), sur
plusieurs marchés à la fois. Vérifiées absentes du registre (`etudes/REGISTRE_IDEES.csv`).

## Univers (fixé avant tout calcul)
11 marchés FTMO dont l'aller-retour coûte au plus 0,05 % et qui ont des données depuis 2011-2013 : EURUSD, GBPUSD,
AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD, XAUUSD, USA500IDXUSD, USATECHIDXUSD, USA30IDXUSD (ce dernier entre quand il a
13 mois d'historique). Exclus : argent (0,25 %), énergies, cryptos (frais), obligation US (données depuis 2018).

## Périodes, prix, frais
- Recherche 2012-01-01 -> 2019-12-31 ; Validation 2020-01-01 -> 2023-12-31 ; **COFFRE 2024-01-01 -> 2026-10-13
  fermé, jamais chargé**.
- Prix de clôture d'un jour = prix à 23:00 serveur (16:00 New York ; clôture de la bougie de 22:45), commun à tous.
  Gains en dollars (paires dont le dollar est la base : convertis au cours).
- Frais FTMO réels (`core.ftmo`) : demi-écart à chaque changement de position (en montant), frais de nuit de chaque
  époque par nuit tenue (nuit triple). Pas d'ouverture ni d'agrandissement à la clôture du vendredi (règle FTMO des 2 h
  avant le week-end) : seulement réduire. Sensibilité écart × 1,5. Limite : compte suivi à la clôture du jour (pas de
  pire moment dans la journée).

## Les 3 hypothèses
- **M1 — momentum RELATIF entre marchés** (Asness, Moskowitz, Pedersen 2013 « Value and momentum everywhere » ;
  Menkhoff et al. 2012 pour les devises) : un mercredi sur deux, score = rendement des 12 derniers mois SANS le dernier
  mois (252 -> 21 jours de bourse), divisé par la volatilité (60 jours) ; ACHAT du quart le mieux classé, VENTE du quart
  le moins bien classé (arrondi au supérieur), tenus 2 semaines. Chaque jambe : 10 %/an / racine(nombre de jambes).
  Différent de la tendance de fond testée (registre I030, I105 : chaque marché seul contre son propre passé) et des
  paires de valeur (I055). Juge clé : **tirage au hasard** des marchés achetés / vendus (mêmes nombres, espérance exacte).
- **M2 — un modèle linéaire commun à tous les marchés** (référence « simple » de la mission §5.4) : à la clôture de
  chaque jour, entrées = rendements sur 1, 5, 21, 63, 126, 252 jours divisés par (volatilité 60 jours × racine de la
  durée) ; sortie = rendement du lendemain / volatilité ; régression ridge (alpha = 1) commune aux 11 marchés,
  ré-apprise chaque 1er janvier sur toutes les années d'avant (rien de l'année jugée). Position du lendemain = signe de
  la prévision si |prévision| > frais aller-retour / volatilité du marché, sinon rien. Taille : 10 %/an / racine(11).
  Différent du moteur de prédiction de Run A (I023 : or M15, réseau de neurones). Juge clé : **pile ou face** ; aussi
  l'acheteur permanent des 11 marchés à risque égal.
- **M3 — exposition gérée par la volatilité** (Moreira, Muir 2017 « Volatility-managed portfolios ») : acheteur
  permanent du S&P 500 dont le montant, recalculé un mercredi sur deux, vaut 100 000 $ × (10 %/an)² / variance des 21
  derniers rendements journaliers annualisée (plafond 300 000 $). Juge clé : **acheteur à montant constant**, ramené au
  même risque ; 2e juge : acheteur à taille selon la volatilité (pas la variance). Robustesse : Nasdaq 100, or.

## Critères d'acceptation (tous obligatoires, 2012-2023 ; M2 jugé à partir de 2013)
1. Gain moyen après frais > 0 sur la Recherche ET sur la Validation.
2. Avantage sur le juge clé > 2 × incertitude sur toute la période (3 hypothèses : racine(2 ln 3) = 1,48 < 2), ET
   positif sur chacune des deux périodes. Incertitude : écart type des avantages par TRIMESTRE / racine(nombre de
   trimestres), ramené au mois (positions de 2 semaines).
3. M1 : avantage sur pile ou face > 0 ; M2 : avantage sur l'acheteur permanent (11 marchés) à risque égal > 0 ; M3 :
   avantage sur le 2e juge à risque égal > 0.
4. Robustesse : M1 et M2 : avantage positif sur chacun des 2 sous-ensembles (devises / autres) ; M3 : avantage sur le
   juge clé positif sur au moins 1 des 2 autres marchés.
5. Écart × 1,5 : gain moyen > 0 sur toute la période.
6. Au moins 100 positions ouvertes ; et pas plus de 30 jours sans ouvrir (règle FTMO), vérifié.
Une hypothèse qui passe tout = candidate -> demande d'ouverture du COFFRE. Aucun critère ne change après un résultat.
