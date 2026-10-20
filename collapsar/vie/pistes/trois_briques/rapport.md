# Piste « trois_briques » : UN compte FTMO 100 000 $ qui fait tourner ensemble la cassure, les zones du chef et C1 (16/10/2026)

Code : `collapsar/regarder/pistes/trois_briques.py` (cahier des charges dans l'en-tête, écrit AVANT les résultats).
Chiffres : `resultats.json`, `controle.json` ; journaux `journal.txt`, `sortie.txt` ; challenges départ par départ
`cache/challenges.npy` (vrai + 20 jumeaux).

**À lire d'abord : toutes ces années (2017-2026) ont DÉJÀ été vues pour les trois briques.** Ce qui suit est une
**estimation** de ce que donnerait un compte qui les fait tourner ensemble, **pas une preuve**. Une seule configuration
a été calculée (rien n'a été choisi sur les résultats). Seul le direct jugera.

## Ce qui a été simulé (vraie simulation conjointe, pas une addition)
- **Une seule grille de 15 min** (heure du serveur) depuis 08/2017 : à chaque quart d'heure, les stops, objectifs et
  sorties des trois briques sont vérifiés, toutes les positions sont marquées au plus mauvais prix de la bougie (au
  même instant, prudent), puis l'arrêt du jour et les murs FTMO sont contrôlés.
- **Cassure 24 h C2** (BTC, ETH, prix Dukascopy, fermée à 23h45, arrêt propre -3 %) : ~37 trades/mois.
- **Zones du chef V1** (19 cryptos, gestion par tiers, au plus 4 positions) : 4 à 9 trades/mois.
- **C1 « contre la foule »** (17 cryptos, stop 1,5 x agitation du jour, sortie 24 h, au plus 5 positions dont 3 dans le
  même sens) : 87 à 99 trades/mois depuis 2022 ; **avant 2022, seul le bitcoin existe (depuis 10/2020)**.
- **Frais FTMO réels** : commission 0,0325 % par côté + écart (BTC 0,0015 %, ETH 0,025 %, autres 0,03 %), x 1,25 ;
  frais entiers sur un stop ; nuits 30 %/an. Levier 1:1.
- **Budget figé** : agitation visée 9 %/an, **un tiers à chaque brique** (5,2 %/an chacune). Calage sur l'agitation
  seulement : zones 0,25 % -> **0,248 % par trade**, cassure -> **c = 0,217 %**, C1 -> **0,187 % par trade** (C1 calé
  sur 03/2022-02/2023, sa première année complète).
- **Sécurité** : arrêt global du jour à -2,5 % (réalisé + latent), risque divisé par 2 sous 94 000 $, au plus
  **8 positions ensemble**.
- **Jumeaux** : 20 comptes identiques où le sens de chaque trade des trois briques est tiré à pile ou face.
- **Contrôles réussis** : la cassure et les zones calées comme dans compte_combine (agitation 11,95 et 5,24 %/an) ;
  cassure + zones seules dans ce simulateur = compte_combine à l'identique (2022-2023 : +0,95 %/mois, -15,6 %, 77 %
  réussis) ; C1 seule = crypto_flux_compte (+0,36 puis -0,09 %/mois contre +0,35 / -0,07) ; prix d'entrée de C1 identique
  à 99,99 %.

## Résultat : le compte à trois briques

| Période | Gain %/mois | Baisse max | Pire jour | Part du gain zones / cassure / C1 | Challenges réussis / morts (jumeaux) | Réussis < 6 / < 12 mois (jumeaux < 12) | Financé 12 mois : survie, gain/mois | Espérance par challenge (jumeaux) | Revenu 4 comptes : durable / tant que financés |
|---|---|---|---|---|---|---|---|---|---|
| 2018-2021 | +0,65 % | -9,8 % | -1,4 % | 18 / 69 / 13 % | 82 / 0 % (6 / 52) | 12 / 49 % (3 %) | 100 %, +0,96 % | +3 785 € (-511) | +945 / +2 744 €/mois |
| 2022-2023 | **+1,35 %** | -12,3 % | -2,5 % | 31 / 31 / 39 % | 74 / 0 % (0 / 98) | 22 / 34 % (0 %) | 100 %, +0,43 % | +904 € (-538) | +260 / +1 225 €/mois |
| 2024 -> 09/2026 | **+0,19 %** | -15,9 % | -2,1 % | 72 / 107 / **-79 %** | 20 / **11 %** (0 / 75) | 7 / 20 % (0 %) | 100 %, 0,00 % | **-371 €** (-536) | -106 / 0 €/mois |
| 2022 -> 09/2026 | +0,66 % | -15,9 % | -2,5 % | 40 / 45 / 15 % | 43 / 6 % (0 / 85) | 13 / 26 % (0 %) | 100 %, +0,24 % | +308 € (-537) | +88 / +681 €/mois |
| tout 2018 -> 09/2026 | +0,65 % | -16,5 % | -2,5 % | 33 / 54 / 13 % | 61 / 3 % (3 / 70) | 13 / 37 % (1 %) | 100 %, +0,68 % | +2 102 € (-524) | +560 / +1 950 €/mois |

Agitation réellement obtenue : 7,9 %/an (2018-2021, C1 presque absente), 12,6 % (2022-2023), 10,6 % (2024-2026).
Force contre le jumeau (trades réellement pris) : zones +0,8 / +1,7 / +1,5 ; cassure +3,7 / +2,9 / +2,7 ; C1 +2,2 /
+4,3 / +2,1 (sur tout : zones +2,3, cassure +5,4, C1 +4,6). Gain par brique en 2024-2026 : zones +0,14, cassure +0,21,
**C1 -0,15 %/mois**. Le plafond de 8 positions a refusé 321 trades (toutes briques) ; l'arrêt global du jour s'est
déclenché 8 fois.

## Comparaison avec l'addition approchée et avec les deux briques seules (2022 -> 09/2026)

| Compte | Gain %/mois | Baisse max | Challenges réussis / morts | < 12 mois | Espérance |
|---|---|---|---|---|---|
| Addition approchée de crypto_flux (jour par jour) | +1,15 % | -15,7 % | 52 / 24 % | 30 % | +2 420 € |
| Même tailles, **simulation conjointe** (contrôle, ajouté après lecture) | +0,72 % | -16,8 % | 35 / 28 % | 28 % | +280 € |
| **Trois briques, un tiers chacune (ce test)** | +0,66 % | -15,9 % | 43 / 6 % | 26 % | +308 € |
| Cassure + zones seules, moitié chacune (compte_combine) | +0,66 % | -15,6 % | 48 / 0 % | 31 % | +579 € |

## Verdict honnête
1. **L'addition approchée était beaucoup trop flatteuse** : simulés pour de vrai, quart d'heure par quart d'heure,
   avec les mêmes tailles, les trois briques font +0,72 %/mois et non +1,15 %, et l'espérance tombe de +2 420 € à +280 €
   par challenge (les pires points des briques tombent les mêmes jours, et C1 perd depuis 2024 aux frais FTMO).
2. **C1 n'améliore pas le compte sur 2022-2026** : à risque égal (un tiers chacune), le compte gagne autant que la
   cassure + les zones seules (+0,66 %/mois) mais **des challenges meurent** (6 % contre 0 %) et l'espérance est moitié
   moindre (+308 € contre +579 €). C1 aide beaucoup en 2022-2023 (+1,35 %/mois, 39 % du gain) et **coûte depuis 2024**
   (-0,15 %/mois : la nuit à 30 %/an et 0,12 % de frais mangent son avantage).
3. **Les trois briques battent nettement leurs jumeaux** (52 à 98 % de challenges morts chez les jumeaux selon la période, 0 à 11 % ici) :
   il y a bien de l'information. Mais **sur 2024-2026 le compte n'est plus rentable pour un challenge** : +0,19 %/mois,
   20 % réussis, 11 % morts, espérance -371 €, compte financé à 0 %/mois.
4. Les gros chiffres viennent d'avant 2022 (bitcoin 2018-2021, cassure surtout) et de 2022-2023. Les départs de
   challenge ne sont pas indépendants (ils réussissent ou meurent souvent le même jour) : le nombre réel de cas est petit.

## Limites
- Années déjà vues ; prix Binance (zones, C1) et Dukascopy (cassure), pas ceux de FTMO ; vrais écarts et nuits FTMO des
  cryptos non relevés ; 11 des cryptos ne sont chez FTMO que depuis le 28/07/2025.
- Le calage de C1 regarde l'agitation (pas le gain) de 03/2022-02/2023, une année de la période 2022-2023.
- Limite du jour comptée contre le solde du début du jour ; retraits possibles avec des positions ouvertes ; 1 € =
  1,116 $ ; les 4 comptes du trader font les mêmes trades (ils vivent et meurent ensemble).

## Ce qui manquerait pour aller plus loin
1. **Ne pas ajouter C1 telle quelle chez FTMO** : son coût (nuit 30 %/an + 0,12 %) l'efface depuis 2024. Elle ne
   redevient utile qu'avec un coût plus bas (bourse au marché, contrats micro CME), à tester à blanc en direct.
2. **Le direct à blanc** du compte cassure + zones (le meilleur des comptes mesurés ici, +579 € d'espérance sur
   2022-2026), au niveau décidé avant, pendant quelques mois : seul juge neuf.
3. Relever sur l'essai gratuit FTMO les vrais écarts et taux de nuit des cryptos (C1 et les zones y sont très sensibles).
