# Fiche — « Contre la foule » (C1) sur les cryptos (20/10/2026)

Sources : `collapsar/vie/pistes/crypto_flux/rapport.md` (+ `suite.json`), `collapsar/vie/pistes/hyrotrader/rapport.md`.
Registre : I073 (positif non prouvé), I076. Aucune année ci-dessous n'est vierge pour C1 : toutes ont été vues.

**Le signal.** Chaque heure, la part des COMPTES acheteurs chez les clients Binance (contrats perpétuels, donnée publique
avec 15 min de retard de sécurité). Au plus haut de 90 jours : VENDRE 24 h ; au plus bas : ACHETER 24 h. Prix du trade
= comptant. 14 cryptos (BTC, ETH + 12), puis un 2e groupe de 11 jamais vu, ouvert une fois.

**Sa force (contre un jumeau même moment, même taille, sens au hasard).**

| jeu de données | période | trades | gain brut %/mois | gain aux frais FTMO %/mois | force (par trade / par jour) |
|---|---|---|---|---|---|
| développement | 10/2020 -> 2023 | 2 764 | +3,75 | +1,76 | 4,5 / 3,2 |
| contrôle (mêmes marchés) | 2024 -> 09/2026 | 3 556 | +3,72 | +0,88 | 3,3 / 2,4 |
| 2e groupe (jamais vu) ≤ 2023 | 2020 -> 2023 | 1 946 | +3,62 | +1,04 | 3,4 / 2,8 |
| 2e groupe 2024 -> 2026 | 2024 -> 09/2026 | 2 390 | +1,57 | **-0,63** | 1,7 / 1,4 |

Vérifié : un retard d'1 h en plus ne change rien (aucun regard dans le futur) ; ce n'est pas l'élan déguisé ; 12 marchés
sur 14 positifs ; achats et ventes positifs. Faiblesses : baisse de 37 à 55 % à la taille testée, pas de stop, la force
« par jour » (les cryptos bougent ensemble) n'atteint 3 que sur le développement.

**Ses frais aux conditions FTMO.** Écart + commission 0,083 % (BTC) à 0,12 % (autres) par aller-retour + une nuit à
30 %/an (~0,083 %) : **≈ 0,17 à 0,20 % par trade, tout compris.**

**Le niveau de frais où il meurt** (le gain brut ne dépend pas des frais : seuil = frais FTMO × brut / (brut − net)) :

| jeu de données | frais où le gain tombe à 0 (par trade, tout compris) |
|---|---|
| développement 2020-2023 | ≈ 0,33 - 0,38 % |
| contrôle 2024-2026 | ≈ 0,22 - 0,26 % |
| 2e groupe ≤ 2023 | ≈ 0,24 - 0,28 % |
| 2e groupe 2024-2026 (le plus récent jamais vu) | **≈ 0,12 - 0,14 %** |

**Conclusion.** Information réelle, mais l'avantage brut a baissé en 2024-2026 sur les marchés jamais vus ; il meurt
dès ~0,13 % par trade sur l'échantillon le plus récent. FTMO (~0,17-0,20 %, dont la moitié en frais de nuit) est
AU-DESSUS : mort chez FTMO. Il vivrait sous ~0,10 % par trade (bourse avec ordres limites, ou contrats sans frais de
nuit) : estimations de mêmes années, donc pas des preuves. Version prudente « compte financé » (0,15 % de risque, stop,
5 positions) : -0,07 %/mois aux frais FTMO en 2024-2026. Décision du chef de projet (20/10) : pas de changement de
courtier pour l'instant.
