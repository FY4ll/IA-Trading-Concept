# Taille de position : résultat de la passe unique (20/10/2026)

Plan : `PLAN.md` (commit `eff86a1`). Or, 2018-01-01 -> 2026-10-13 (2e regard déclaré). Signaux inchangés. Chiffres en
% de la valeur du compte ; frais FTMO compris. Détail : `resultats/taille.json` (dont le rendement par année).

| signal | taille | rendement / an | volatilité | gain / vol | pire baisse | pire jour | jours ≤ -5 % | nuits / an | challenge réussi / mur / inactivité |
|---|---|---|---|---|---|---|---|---|---|
| acheteur | A fixe | +9,99 % | 16,5 % | 0,66 | 34,2 % | -14,4 % | 11 | 7,7 % | 5 / 7 / 88 % |
| acheteur | B capital | +9,99 % | 16,5 % | 0,66 | 34,2 % | -14,4 % | 11 | 7,7 % | 5 / 7 / 88 % |
| acheteur | C vol | +5,93 % | 8,6 % | **0,71** | 18,3 % | -4,2 % | 0 | 3,5 % | 0 / 0 / 99 % |
| acheteur | D capital+vol | +7,77 % | 11,2 % | **0,72** | 18,9 % | -5,4 % | 2 | 4,5 % | 2 / 3 / 94 % |
| 1 mois | A / B / C / D | -2,3 / -2,3 / -0,4 / -0,8 % | 11-19 % | -0,14 à 0,06 | 32-47 % | -5,2 à -9 % | 1-10 | 1,9-2,8 % | ≤ 12 % réussis |
| 3 mois | A / B / C / D | +4,7 / +4,1 / +5,7 / +5,3 % | 10-12 % | 0,40 à **0,59** | 19-22 % | -5,2 à -9,8 % | 1-7 | 2,9-3,4 % | ≤ 3 % réussis |
| 6 mois | A / B / C / D | +5,4 / +4,7 / +5,0 / +5,3 % | 10-14 % | 0,40 à 0,53 | 19-33 % | -4,6 à -13,5 % | 0-12 | 3,1-4,4 % | ≤ 6 % réussis |
| 12 mois | A / B / C / D | +7,5 / +4,9 / +2,7 / +2,1 % | 12-23 % | 0,23 à 0,43 | 39-50 % | -5,4 à -16,6 % | 1-33 | 2,7-6,4 % | ≤ 12 % réussis |

(B = A pour l'acheteur : un seul trade, ouvert au départ quand le compte vaut 100 000 $.)

## Ce que ça dit
1. **Le défaut est corrigé** : avec la taille suivie chaque jour (C, D), plus de position démesurée ; pires baisses
   ~18-23 % (hors 12 mois), pire jour ~-4 à -6 %, presque plus de jours sous -5 %.
2. **Le verdict de la tendance ne change pas** : à risque égal (gain / vol), l'acheteur permanent (0,71-0,72) reste
   au-dessus de la meilleure tendance (3 mois : 0,53-0,59). Comme prévu (§8 de la mission), la taille déplace le
   risque, elle ne crée pas d'avantage.
3. **Les frais de nuit pèsent lourd** : garder de l'or à l'achat chez FTMO coûte 3,5 à 7,7 % par an (selon la
   taille), soit la moitié environ du gain de l'acheteur.
4. **FTMO** : avec la règle de 30 jours sans ouvrir de trade (à vérifier pour chaque type de compte, en cours),
   87 à 99 % des challenges échouent par inactivité pour tous ces systèmes lents. La taille n'y change rien.

Conséquence : pour la suite, la taille « C vol » (ajustée chaque jour à la volatilité) devient la règle par défaut des
mesures ; pas d'autre réglage de taille sur la tendance de fond (décision du chef de projet).
