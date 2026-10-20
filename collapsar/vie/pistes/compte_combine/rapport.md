# Piste « compte_combine » : un compte FTMO 100 000 $ qui fait tourner la cassure ET les zones du chef (16/10/2026)

Code : `collapsar/regarder/pistes/compte_combine.py` (cahier des charges dans l'en-tête, écrit avant les résultats).
Chiffres complets : `resultats.json` ; journal `journal.txt` / `sortie.txt` ; challenges départ par départ `cache/challenges_*.npy`.

**À lire d'abord : toutes ces années (2017-2026) ont DÉJÀ été vues pour les deux briques.** Ce qui suit est une
**estimation** de ce que donnerait un compte qui fait tourner les deux ensemble, **pas une preuve**. Seul le direct
(démo, puis essai FTMO) jugera.

## Ce qui a été simulé
- **Brique 1, cassure 24 h C2** (celle de la démo) sur BTC et ETH, prix Dukascopy : canal des 24 dernières heures,
  lundi -> vendredi, sortie au milieu du canal, tout fermé à 23h45 (aucune nuit), arrêt propre à -3 % dans la journée.
  3 971 trades (BTC 2 044, ETH 1 927), environ 36 par mois.
- **Brique 2, zones du chef V1** (gestion par tiers 2 R / sommet H1 / zone opposée) sur 19 cryptos, prix Binance,
  trades repris tels quels de la piste chef_compte_ftmo : 802 trades, au plus 4 positions et 1 par crypto.
- **Frais réels FTMO** : commission 0,0325 % par côté + écart (BTC 0,0015 %, ETH 0,025 %, autres 0,03 %), le tout
  x 1,25 ; nuits 30 %/an. Compte Swing, levier crypto 1:1 (la somme des positions ne dépasse jamais les fonds).
- **Budget de risque fixé avant** : 3 niveaux d'agitation visée du compte (6, 9, 12 %/an), chaque brique en porte la
  moitié (niveau / racine(2)). Calage une seule fois sur 2017-2021, sur l'agitation (jamais sur le gain) :

  | niveau | chef : risque par trade | cassure : taille (part du compte / agitation du jour) |
  |---|---|---|
  | 6 % | 0,20 % | 0,18 % (soit ~6 % du compte par position sur le bitcoin) |
  | 9 % | 0,30 % | 0,27 % (~9 %) |
  | 12 % | 0,41 % | 0,35 % (~12 %) |

- **2 règles de sécurité** : arrêt de toute la journée à -2,5 % (réalisé + latent, au plus mauvais prix de chaque
  bougie de 15 min) ; risque divisé par 2 quand les fonds sont à moins de 4 % du mur des -10 %.
- **Challenges** : départ tous les 10 jours (337 départs), +10 % puis +5 %, mort à -5 % dans la journée ou -10 %,
  4 jours de trading minimum, contre 20 jumeaux (mêmes moments, même taille, sens tiré à pile ou face). Puis compte
  financé 12 mois (retrait tous les 30 jours, 80 % pour le trader). Espérance d'un challenge à 540 € (remboursé si
  réussi) : non réussi en 12 mois = abandonné (-540 €). Revenu « durable » de 4 comptes = on rachète un challenge dès
  qu'un compte meurt, est abandonné ou finit ses 12 mois.

## Résultat principal : le compte combiné

| niveau | période | gain %/mois | baisse max | pire jour | challenges réussis / morts (jumeaux) | réussis en < 6 mois / < 12 mois (jumeaux < 12 mois) | financé 12 mois : survie, gain/mois | espérance par challenge (jumeaux) | revenu 4 comptes : durable / tant que financés |
|---|---|---|---|---|---|---|---|---|---|
| 6 % | avant 2022 | +0,46 % | -9,5 % | -1,2 % | 54 / 0 % (4 / 14) | 9 / 22 % (1 %) | 100 %, +0,56 % | +615 € (-530) | +182 / +1 602 €/mois |
| 6 % | 2022-2023 | +0,73 % | -10,7 % | -1,4 % | 26 / 0 % (1 / 35) | 0 / 0 % (0 %) | aucun cas | -540 € (-540) | -180 / - |
| 6 % | 2024-2026 | +0,35 % | -9,4 % | -1,3 % | 3 / 0 % (0 / 21) | 1 / 1 % (0 %) | 1 cas | -476 € (-540) | -158 / - |
| **9 %** | avant 2022 | +0,66 % | -14,8 % | -1,7 % | 75 / 2 % (8 / 56) | 12 / 46 % (4 %) | 100 %, +1,27 % | +4 768 € (-409) | +1 224 / +3 642 €/mois |
| **9 %** | 2022-2023 | +0,95 % | -15,6 % | -2,2 % | 77 / 0 % (3 / 82) | 3 / 37 % (1 %) | 100 %, +0,21 % | +336 € (-522) | +87 / +609 €/mois |
| **9 %** | 2024-2026 | +0,43 % | -13,5 % | -1,9 % | 27 / 0 % (1 / 55) | 14 / 27 % (1 %) | 100 %, +0,29 % | +782 € (-531) | +210 / +843 €/mois |
| **9 %** | **tout** | **+0,66 %** | **-15,6 %** | **-2,2 %** | **61 / 1 %** (5 / 61) | **10 / 39 %** (3 %) | 100 %, +0,84 % | **+2 826 €** (-463) | **+735 / +2 409 €/mois** |
| 12 % | avant 2022 | +0,81 % | -20,7 % | -2,3 % | 74 / 25 % (11 / 80) | 22 / 54 % (7 %) | 75 %, +1,59 % | +7 200 € (-314) | +2 015 / +4 569 €/mois |
| 12 % | 2022-2023 | +1,05 % | -20,2 % | -2,9 % | 44 / 27 % (2 / 95) | 29 / 34 % (1 %) | 36 %, +0,05 % | -217 € (-518) | -80 / +134 €/mois |
| 12 % | 2024-2026 | +0,37 % | -16,8 % | -2,6 % | 26 / 29 % (1 / 74) | 9 / 24 % (1 %) | 100 %, +0,00 % | -349 € (-525) | -99 / 0 €/mois |

Lecture : « baisse max » = depuis le plus haut atteint, compte continu sans arrêt au mur ; « pire jour » = dans la
journée, latent compris. Un départ est rangé dans la période où il commence (son financé peut tomber dans la période
suivante). Agitation réellement obtenue : 6 % -> 6-8 %/an, 9 % -> 9-12 %/an, 12 % -> 12-15 %/an (2022-2023 plus agité).

## Chaque brique seule, au même risque (niveau 9 %)

| brique | période | gain %/mois | baisse max | pire jour | challenges réussis / morts (jumeaux) | < 12 mois | espérance | revenu 4 comptes durable |
|---|---|---|---|---|---|---|---|---|
| cassure seule | avant 2022 | +0,58 % | -6,9 % | -1,7 % | 41 / 0 % (1 / 19) | 23 % | +897 € | +252 €/mois |
| cassure seule | 2022-2023 | +0,49 % | -7,4 % | -1,3 % | 16 / 0 % (0 / 20) | 1 % | -501 € | -165 €/mois |
| cassure seule | 2024-2026 | +0,26 % | -6,6 % | -1,9 % | 0 / 0 % (0 / 11) | 0 % | -540 € | -180 €/mois |
| chef seul | avant 2022 | -0,04 % | -12,9 % | -1,6 % | 54 / 0 % (11 / 13) | 14 % | -361 € | -110 €/mois |
| chef seul | 2022-2023 | +0,59 % | -11,9 % | -2,1 % | 16 / 32 % (3 / 66) | 14 % | -466 € | -139 €/mois |
| chef seul | 2024-2026 | +0,21 % | -13,9 % | -2,0 % | 19 / 0 % (2 / 31) | 16 % | +294 € | +86 €/mois |
| **combiné** | **tout** | **+0,66 %** | **-15,6 %** | -2,2 % | **61 / 1 %** | **39 %** | **+2 826 €** | **+735 €/mois** |
| cassure seule | tout | +0,46 % | -7,7 % | -1,7 % | 23 / 0 % | 12 % | +245 € | +74 €/mois |
| chef seul | tout | +0,17 % | -14,5 % | -2,1 % | 35 / 7 % | 14 % | -244 € | -73 €/mois |

(Niveaux 6 % et 12 % des briques seules : dans `resultats.json` et `sortie.txt`. À 6 %, aucune brique seule ne réussit
de challenge en moins de 12 mois sur 2022-2026.)

**Lien entre les deux briques, jour par jour : +0,05 (avant 2022), +0,13 (2022-2023), +0,08 (2024-2026)** : presque
indépendantes. **Force contre le jumeau** (par trade) : cassure +4,0 / +2,9 / +2,8 (tout +5,7) ; chef +0,8 / +2,0 / +1,6
(tout +2,5).

## Verdict honnête
1. **Les deux briques ensemble valent nettement mieux que chacune seule** : elles sont presque indépendantes (lien
   ~0,08), donc à risque égal le compte gagne la somme des deux (+0,66 %/mois au niveau 9 %) avec une baisse à peine
   plus grande. C'est ce qui fait passer les challenges : 39 % réussis en moins d'un an au niveau 9 % (cassure seule
   12 %, chef seul 14 %, jumeaux 3 %).
2. **Le niveau 9 % est le seul qui reste positif sur les trois périodes** (espérance +4 768 / +336 / +782 € par
   challenge, aucun challenge mort sur 2022-2026). À 12 %, un challenge sur quatre meurt et l'espérance est négative
   depuis 2022. À 6 %, le compte est trop lent pour FTMO. Attention : cette lecture est faite sur des années déjà vues
   (aucun niveau n'a été choisi, les trois sont publiés).
3. **Les gros chiffres viennent d'avant 2022** (bitcoin 2017-2021 très favorable à la cassure). Sur 2022-2026, au niveau
   9 % : environ +0,4 à +0,9 %/mois, financé +0,2 à +0,3 %/mois, **revenu durable de 4 comptes de l'ordre de 90 à
   210 €/mois** (600 à 850 €/mois tant que les 4 comptes sont financés), pas des milliers.
4. Les départs de challenge ne sont pas indépendants : ceux d'une même période réussissent ou échouent souvent le
   même jour (même marché). Le nombre réel de « cas » est bien plus petit que le nombre de départs.

## Limites
- Années déjà vues ; prix Binance (chef) et Dukascopy (cassure), pas ceux de FTMO ; écarts et frais de nuit réels des
  cryptos FTMO non publiés ; 11 des 19 cryptos du chef ne sont chez FTMO que depuis le 28/07/2025.
- Bougies de 15 min : le pire prix de chaque bougie est pris au même instant pour toutes les positions (prudent).
- Retraits du financé supposés possibles même avec des positions ouvertes ; 1 € = 1,116 $ ; 4 comptes avec la même
  stratégie = mêmes trades (comptés ensemble dans le plafond FTMO de 400 000 $) : ils vivent et meurent ensemble.

## Ce qui manquerait pour aller plus loin
1. **Le direct à blanc du compte combiné** (cassure déjà en démo + zones du chef sur les 19 cryptos), au niveau décidé
   AVANT (par exemple 9 %), pendant quelques mois : seul juge neuf.
2. **Relever les vrais écarts et frais de nuit** des cryptos sur l'essai gratuit FTMO (la cassure fait ~36 trades par
   mois : 0,01 % d'écart en plus ou en moins compte).
3. Confirmer par écrit auprès de FTMO qu'une IA automatique sur cryptos (< 2 000 requêtes/jour) est acceptée.
