# COLLAPSAR aux commandes de la cassure (amélioration n° 7) — 16/10/2026

Code et juge (écrit avant tout résultat) : `collapsar/regarder/pistes/cassure_collapsar.py`. Pour chaque signal de la version retenue, COLLAPSAR choisit la taille : 0 (il ne prend pas) à 1,5 fois. Appris sur 2017-2021 (BTC, ETH et groupe A), contrôlé sur 2022-2023 puis 2024-2026, jamais sur le groupe B.

Notes : **compte** = rapport gain / risque du compte BTC + ETH + (challenges réussis - morts) / 100 ; **groupe A** = rapport gain / risque moyen des 12 marchés du groupe A. Gardé seulement si les deux notes battent la version retenue sur les deux moitiés.

Fidélité : sans COLLAPSAR, ce programme redonne le laboratoire sur 2022-2026 (écart max sur le groupe A 0.0e+00 ; challenges 77 % / 0 % contre 77 % / 0 %).

## Résultat au contrôle

| version | moitié | note compte | note groupe A | compte %/mois | baisse max | challenges réussis / morts |
|---|---|---|---|---|---|---|
| version retenue | 2022-2023 | +1.116 | -0.441 | +0.52 % | -8.4 % | 40 % / 0 % |
| (a) arbres boostés | 2022-2023 | +1.885 | -0.266 | +1.27 % | -9.0 % | 62 % / 0 % |
| (b) petit réseau | 2022-2023 | +1.318 | +0.065 | +0.86 % | -10.4 % | 35 % / 0 % |
| version retenue | 2024-2026 | +1.323 | +0.236 | +0.50 % | -7.4 % | 62 % / 0 % |
| (a) arbres boostés | 2024-2026 | +0.793 | +0.161 | +0.42 % | -8.5 % | 24 % / 0 % |
| (b) petit réseau | 2024-2026 | +0.694 | +0.056 | +0.44 % | -8.7 % | 11 % / 0 % |
| version retenue | 2022-2026 | +1.494 | -0.059 | +0.59 % | -9.3 % | 77 % / 0 % |
| (a) arbres boostés | 2022-2026 | +1.435 | -0.033 | +0.78 % | -9.0 % | 54 % / 0 % |
| (b) petit réseau | 2022-2026 | +1.384 | +0.074 | +0.73 % | -10.4 % | 48 % / 0 % |
| version retenue | 2017-2021 (appris) | +1.844 | +0.587 | +1.54 % | -11.9 % | 63 % / 0 % |
| (a) arbres boostés | 2017-2021 (appris) | +2.368 | +1.196 | +2.20 % | -8.9 % | 73 % / 0 % |
| (b) petit réseau | 2017-2021 (appris) | +2.787 | +1.258 | +2.40 % | -7.6 % | 84 % / 0 % |

| cerveau | verdict | lien prévision / réalité 2022-2023 | 2024-2026 | appris (2017-2021) | refusés au contrôle | taille moyenne au contrôle |
|---|---|---|---|---|---|---|
| (a) arbres boostés | **REJETÉ** | -0.023 | -0.028 | +0.091 | 6 % | 0.92 |
| (b) petit réseau | **REJETÉ** | +0.049 | -0.011 | +0.109 | 16 % | 0.84 |

(lien prévision / réalité = accord de rang entre ce que COLLAPSAR prévoit et le gain réel du signal ; 0 = aucun, 1 = parfait.)

## Marché par marché (rapport gain / risque, groupe A)

| marché | moitié | version retenue | (a) arbres boostés | (b) petit réseau |
|---|---|---|---|---|
| ADAUSDT | 2022-2023 | +0.06 | -0.11 | +0.40 |
| ADAUSDT | 2024-2026 | +0.24 | -0.38 | -0.09 |
| ATOMUSDT | 2022-2023 | -1.12 | -0.60 | +0.04 |
| ATOMUSDT | 2024-2026 | +0.08 | +0.11 | -0.12 |
| BCHUSDT | 2022-2023 | +0.18 | +0.15 | +0.67 |
| BCHUSDT | 2024-2026 | +0.18 | -0.03 | -0.16 |
| DOGEUSDT | 2022-2023 | -1.08 | -0.98 | -0.63 |
| DOGEUSDT | 2024-2026 | +0.34 | +0.30 | +0.43 |
| EOSUSDT | 2022-2023 | -1.51 | -1.57 | -0.97 |
| EOSUSDT | 2024-2026 | -0.02 | +0.35 | -0.42 |
| FILUSDT | 2022-2023 | -0.15 | +0.30 | +0.27 |
| FILUSDT | 2024-2026 | +0.35 | +0.30 | +0.46 |
| LTCUSDT | 2022-2023 | -0.32 | -0.34 | -0.36 |
| LTCUSDT | 2024-2026 | -0.19 | -0.42 | -0.60 |
| NEARUSDT | 2022-2023 | -0.97 | -0.60 | -0.35 |
| NEARUSDT | 2024-2026 | +0.60 | +0.53 | +0.36 |
| SOLUSDT | 2022-2023 | +0.27 | +0.47 | +1.36 |
| SOLUSDT | 2024-2026 | -0.17 | +0.01 | -0.03 |
| UNIUSDT | 2022-2023 | -0.99 | -0.53 | -0.48 |
| UNIUSDT | 2024-2026 | +0.38 | +0.42 | +0.16 |
| XLMUSDT | 2022-2023 | +0.04 | +0.15 | +0.42 |
| XLMUSDT | 2024-2026 | +0.32 | +0.13 | +0.22 |
| XRPUSDT | 2022-2023 | +0.30 | +0.47 | +0.42 |
| XRPUSDT | 2024-2026 | +0.73 | +0.62 | +0.47 |

## Ce que (a) arbres boostés a appris (sur 2017-2021)

Réglage choisi sur 2021 : 20 arbres. Signaux appris : refusés 6 %, grossis (> 1) 47 %, taille moyenne 0.95.

| fait | importance | tranche | refusés | taille moyenne |
|---|---|---|---|---|
| résultat récent de la stratégie | 23 % | 20 % les plus bas | 2 % | 1.03 |
| résultat récent de la stratégie | 23 % | milieu | 3 % | 1.03 |
| résultat récent de la stratégie | 23 % | 20 % les plus hauts | 18 % | 0.65 |
| heure | 21 % | 1 | 5 % | 1.03 |
| heure | 21 % | 2 | 9 % | 0.95 |
| heure | 21 % | 3 | 12 % | 0.93 |
| heure | 21 % | 4 | 8 % | 0.99 |
| heure | 21 % | 5 | 8 % | 0.98 |
| heure | 21 % | 6 | 5 % | 1.03 |
| heure | 21 % | 7 | 1 % | 1.08 |
| heure | 21 % | 8 | 3 % | 1.07 |
| heure | 21 % | 9 | 2 % | 1.10 |
| heure | 21 % | 10 | 1 % | 1.09 |
| heure | 21 % | 11 | 2 % | 1.10 |
| heure | 21 % | 12 | 4 % | 1.05 |
| heure | 21 % | 13 | 5 % | 1.03 |
| heure | 21 % | 14 | 2 % | 1.10 |
| heure | 21 % | 15 | 2 % | 0.92 |
| heure | 21 % | 16 | 2 % | 0.95 |
| heure | 21 % | 17 | 3 % | 0.94 |
| heure | 21 % | 18 | 7 % | 0.74 |
| heure | 21 % | 19 | 8 % | 0.68 |
| heure | 21 % | 20 | 9 % | 0.68 |
| heure | 21 % | 21 | 9 % | 0.68 |
| heure | 21 % | 22 | 11 % | 0.66 |
| tendance 1 j (dans le sens) | 17 % | 20 % les plus bas | 6 % | 0.94 |
| tendance 1 j (dans le sens) | 17 % | milieu | 3 % | 1.00 |
| tendance 1 j (dans le sens) | 17 % | 20 % les plus hauts | 13 % | 0.84 |
| jour de la semaine | 12 % | 0 | 1 % | 1.04 |
| jour de la semaine | 12 % | 1 | 0 % | 1.02 |
| jour de la semaine | 12 % | 2 | 1 % | 1.00 |
| jour de la semaine | 12 % | 3 | 9 % | 0.87 |
| jour de la semaine | 12 % | 4 | 17 % | 0.83 |
| tendance 5 j (dans le sens) | 9 % | 20 % les plus bas | 5 % | 0.81 |
| tendance 5 j (dans le sens) | 9 % | milieu | 5 % | 1.00 |
| tendance 5 j (dans le sens) | 9 % | 20 % les plus hauts | 10 % | 0.96 |
| tendance 20 j (dans le sens) | 8 % | 20 % les plus bas | 5 % | 0.92 |
| tendance 20 j (dans le sens) | 8 % | milieu | 6 % | 0.95 |
| tendance 20 j (dans le sens) | 8 % | 20 % les plus hauts | 8 % | 1.01 |
| volume relatif | 6 % | 20 % les plus bas | 2 % | 1.06 |
| volume relatif | 6 % | milieu | 6 % | 0.93 |
| volume relatif | 6 % | 20 % les plus hauts | 10 % | 0.91 |
| résultat du jour (mur du jour) | 3 % | 20 % les plus bas | 7 % | 0.82 |
| résultat du jour (mur du jour) | 3 % | milieu | 2 % | 0.90 |
| résultat du jour (mur du jour) | 3 % | 20 % les plus hauts | 6 % | 0.99 |
| accord BTC-ETH (BTC pour le groupe A) | 1 % | -1 | 3 % | 1.01 |
| accord BTC-ETH (BTC pour le groupe A) | 1 % | -0 | 29 % | 0.54 |
| accord BTC-ETH (BTC pour le groupe A) | 1 % | 1 | 6 % | 0.94 |
| distance au mur des -10 % | 0 % | 20 % les plus bas | 4 % | 0.98 |
| distance au mur des -10 % | 0 % | milieu | 6 % | 0.96 |
| distance au mur des -10 % | 0 % | 20 % les plus hauts | 8 % | 0.91 |
| largeur du canal / agitation | 0 % | 20 % les plus bas | 2 % | 1.02 |
| largeur du canal / agitation | 0 % | milieu | 5 % | 0.97 |
| largeur du canal / agitation | 0 % | 20 % les plus hauts | 11 % | 0.86 |

| marché | refusés (appris) | taille (appris) | refusés (contrôle) | taille (contrôle) |
|---|---|---|---|---|
| ADAUSDT | 7 % | 0.94 | 7 % | 0.91 |
| ATOMUSDT | 6 % | 0.94 | 6 % | 0.92 |
| BCHUSDT | 6 % | 0.96 | 6 % | 0.94 |
| BTCUSD | 5 % | 0.95 | 6 % | 0.89 |
| DOGEUSDT | 5 % | 1.00 | 5 % | 0.93 |
| EOSUSDT | 5 % | 0.95 | 6 % | 0.95 |
| ETHUSD | 7 % | 0.93 | 7 % | 0.89 |
| FILUSDT | 6 % | 0.99 | 6 % | 0.93 |
| LTCUSDT | 6 % | 0.95 | 6 % | 0.93 |
| NEARUSDT | 6 % | 0.97 | 7 % | 0.92 |
| SOLUSDT | 5 % | 0.98 | 7 % | 0.91 |
| UNIUSDT | 5 % | 0.95 | 6 % | 0.93 |
| XLMUSDT | 6 % | 0.95 | 7 % | 0.93 |
| XRPUSDT | 5 % | 0.97 | 6 % | 0.92 |

## Ce que (b) petit réseau a appris (sur 2017-2021)

Réglage choisi sur 2021 : 1 passages. Signaux appris : refusés 17 %, grossis (> 1) 41 %, taille moyenne 0.83.

| fait | importance | tranche | refusés | taille moyenne |
|---|---|---|---|---|
| heure | 22 % | 1 | 20 % | 0.84 |
| heure | 22 % | 2 | 20 % | 0.84 |
| heure | 22 % | 3 | 28 % | 0.65 |
| heure | 22 % | 4 | 22 % | 0.72 |
| heure | 22 % | 5 | 24 % | 0.75 |
| heure | 22 % | 6 | 30 % | 0.58 |
| heure | 22 % | 7 | 27 % | 0.65 |
| heure | 22 % | 8 | 28 % | 0.65 |
| heure | 22 % | 9 | 6 % | 1.02 |
| heure | 22 % | 10 | 5 % | 1.08 |
| heure | 22 % | 11 | 7 % | 0.88 |
| heure | 22 % | 12 | 24 % | 0.70 |
| heure | 22 % | 13 | 8 % | 1.02 |
| heure | 22 % | 14 | 8 % | 1.04 |
| heure | 22 % | 15 | 11 % | 0.88 |
| heure | 22 % | 16 | 9 % | 0.96 |
| heure | 22 % | 17 | 4 % | 1.01 |
| heure | 22 % | 18 | 6 % | 1.09 |
| heure | 22 % | 19 | 24 % | 0.75 |
| heure | 22 % | 20 | 11 % | 0.82 |
| heure | 22 % | 21 | 24 % | 0.76 |
| heure | 22 % | 22 | 18 % | 0.79 |
| tendance 5 j (dans le sens) | 12 % | 20 % les plus bas | 32 % | 0.55 |
| tendance 5 j (dans le sens) | 12 % | milieu | 13 % | 0.89 |
| tendance 5 j (dans le sens) | 12 % | 20 % les plus hauts | 18 % | 0.92 |
| jour de la semaine | 12 % | 0 | 11 % | 0.97 |
| jour de la semaine | 12 % | 1 | 18 % | 0.82 |
| jour de la semaine | 12 % | 2 | 14 % | 0.88 |
| jour de la semaine | 12 % | 3 | 26 % | 0.69 |
| jour de la semaine | 12 % | 4 | 19 % | 0.79 |
| tendance 20 j (dans le sens) | 11 % | 20 % les plus bas | 30 % | 0.58 |
| tendance 20 j (dans le sens) | 11 % | milieu | 16 % | 0.86 |
| tendance 20 j (dans le sens) | 11 % | 20 % les plus hauts | 12 % | 1.00 |
| résultat récent de la stratégie | 10 % | 20 % les plus bas | 9 % | 0.97 |
| résultat récent de la stratégie | 10 % | milieu | 13 % | 0.88 |
| résultat récent de la stratégie | 10 % | 20 % les plus hauts | 41 % | 0.52 |
| accord BTC-ETH (BTC pour le groupe A) | 9 % | -1 | 5 % | 1.04 |
| accord BTC-ETH (BTC pour le groupe A) | 9 % | -0 | 0 % | 0.99 |
| accord BTC-ETH (BTC pour le groupe A) | 9 % | 1 | 21 % | 0.78 |
| tendance 1 j (dans le sens) | 7 % | 20 % les plus bas | 6 % | 0.99 |
| tendance 1 j (dans le sens) | 7 % | milieu | 15 % | 0.86 |
| tendance 1 j (dans le sens) | 7 % | 20 % les plus hauts | 39 % | 0.58 |
| largeur du canal / agitation | 6 % | 20 % les plus bas | 4 % | 1.03 |
| largeur du canal / agitation | 6 % | milieu | 14 % | 0.86 |
| largeur du canal / agitation | 6 % | 20 % les plus hauts | 43 % | 0.53 |
| volume relatif | 5 % | 20 % les plus bas | 15 % | 0.86 |
| volume relatif | 5 % | milieu | 20 % | 0.80 |
| volume relatif | 5 % | 20 % les plus hauts | 14 % | 0.91 |
| distance au mur des -10 % | 5 % | 20 % les plus bas | 8 % | 0.96 |
| distance au mur des -10 % | 5 % | milieu | 18 % | 0.83 |
| distance au mur des -10 % | 5 % | 20 % les plus hauts | 27 % | 0.71 |
| résultat du jour (mur du jour) | 1 % | 20 % les plus bas | 12 % | 0.90 |
| résultat du jour (mur du jour) | 1 % | milieu | 10 % | 0.95 |
| résultat du jour (mur du jour) | 1 % | 20 % les plus hauts | 19 % | 0.81 |

| marché | refusés (appris) | taille (appris) | refusés (contrôle) | taille (contrôle) |
|---|---|---|---|---|
| ADAUSDT | 20 % | 0.81 | 20 % | 0.78 |
| ATOMUSDT | 15 % | 0.85 | 16 % | 0.84 |
| BCHUSDT | 18 % | 0.82 | 17 % | 0.81 |
| BTCUSD | 21 % | 0.78 | 17 % | 0.83 |
| DOGEUSDT | 18 % | 0.83 | 15 % | 0.85 |
| EOSUSDT | 14 % | 0.86 | 16 % | 0.86 |
| ETHUSD | 22 % | 0.78 | 16 % | 0.84 |
| FILUSDT | 19 % | 0.82 | 12 % | 0.89 |
| LTCUSDT | 15 % | 0.87 | 11 % | 0.89 |
| NEARUSDT | 14 % | 0.89 | 19 % | 0.80 |
| SOLUSDT | 20 % | 0.84 | 20 % | 0.79 |
| UNIUSDT | 17 % | 0.81 | 13 % | 0.89 |
| XLMUSDT | 15 % | 0.86 | 14 % | 0.86 |
| XRPUSDT | 15 % | 0.87 | 13 % | 0.86 |

## En mots simples

**Verdict : les deux cerveaux sont REJETÉS. La version retenue reste telle quelle, sans COLLAPSAR aux commandes.**
Le groupe B n'a pas été ouvert.

Ce que COLLAPSAR a appris sur 2017-2021 (les deux cerveaux disent à peu près la même chose) :
- il **réduit ou refuse** les signaux qui arrivent juste après une série gagnante de la stratégie (résultat récent
  élevé : 18 % refusés pour les arbres, 41 % pour le réseau), ceux qui partent après une forte montée (ou baisse) déjà
  faite dans la journée dans le même sens (« trop tard »), ceux d'un canal très large, ceux de la fin de soirée
  (18h-22h serveur pour les arbres) et du jeudi-vendredi ;
- il **grossit** les signaux du matin et de la mi-journée (7h-14h serveur pour les arbres, 9h-10h et 13h-18h pour le
  réseau), après une série perdante de la stratégie, et le réseau ceux qui vont dans le sens de la tendance 5-20 jours ;
- la distance au mur des -10 % ne lui sert presque à rien (0 % et 5 % d'importance) : normal, l'état du challenge ne
  dit rien sur le prochain mouvement du prix ; le mur reste géré par la réduction de la version retenue.

Pourquoi c'est rejeté : sur 2017-2021 ses prévisions suivaient un peu la réalité (accord de rang +0,09 / +0,11) et le
compte gagnait nettement plus. Au contrôle, cet accord tombe à zéro (-0,03 à +0,05) : ce qu'il a appris ne s'est pas
répété après 2021. Sur 2022-2023 il fait mieux par chance (compte +1,27 %/mois contre +0,52 % pour les arbres), sur
2024-2026 il fait moins bien (challenges réussis 24 % et 11 % contre 62 %), donc le juge fixé à l'avance le refuse.

Piste honnête : la cassure n'a pas de « bons » et « mauvais » signaux reconnaissables avec ces faits ; son avantage
vient de les prendre tous. COLLAPSAR peut servir ailleurs (choisir les marchés, le risque), pas pour trier ces signaux.
