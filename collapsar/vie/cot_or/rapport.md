# Les fonds sur l'or annoncent-ils le SENS de l'or ? (COT CFTC, 20/10/2026)

**Verdict : non. Les 9 signaux x 3 horizons = 27 cases sont ⚪ bruit.** Aucune n'atteint même la moitié du seuil
de preuve sur 2006-2019. Rien à donner à MAGNETAR comme information de sens.

Plan figé avant tout calcul : `plan_fige.md` (00h57). Code : `analyse_cot.py`, lecture sans futur
`collapsar/donnees/cot.py` (5 tests verts, `collapsar/tests/test_cot.py`). Résultats : `resultats_choix.json`,
`controle.json` (contrôle calculé une seule fois, verrou), journaux `log_choix.txt`, `log_controle.txt`.

## Règle anti-triche (vérifiée)
| Contrôle | Résultat |
|---|---|
| Entrée strictement après la publication (vendredi 15h30 New York ; lundi si semaine fériée) | ✅ 100 % des semaines |
| Entrée le lundi / le mardi (semaine fériée) / mercredi | 797 / 198 / 9 semaines |
| 40 semaines recalculées avec le fichier coupé à leur date | écart 0 (identique) |
| Paralysies de l'État (2013, 2018-19) | semaines exclues |

Le piège montré en chiffres : la variation des fonds sur la semaine colle au mouvement de l'or de la MÊME semaine
(lien de rang +0,68 sur 2006-2019, force +20 ; +0,72 sur 2020-22). **Les fonds suivent le prix.** Une fois la donnée
publiée, il ne reste rien (tableau ci-dessous).

## Résultat, case par case (force du lien signal -> rendement futur ; seuil de preuve 3,80)
Force = lien de rang corrigé des chevauchements. « avec tendance » = force du signal quand la tendance 60 j est
dans la même régression.

| Signal | Horizon | Choix 2006-19 | Vérif. 2020-22 | Contrôle 2023-09/25 | Avec tendance (choix) | Étiquette |
|---|---|---|---|---|---|---|
| Variation 1 sem. | 1 / 2 / 4 sem. | -0,4 / 0,0 / -0,6 | -0,4 / -0,2 / -1,4 | -1,5 / -1,6 / -0,9 | -0,7 / +0,3 / -0,6 | ⚪ |
| Variation 4 sem. | 1 / 2 / 4 | -0,5 / -0,5 / -0,5 | -1,8 / -1,4 / -0,5 | -0,6 / -0,3 / 0,0 | -0,9 / -0,5 / -0,5 | ⚪ |
| Rang 52 sem. | 1 / 2 / 4 | -0,1 / +0,1 / -0,4 | -0,8 / -0,7 / -1,0 | -1,0 / -0,9 / -0,7 | -0,2 / +0,5 / +0,4 | ⚪ |
| Rang 156 sem. | 1 / 2 / 4 | -0,4 / -0,2 / -0,1 | -0,2 / -0,1 / -0,5 | -0,1 / -0,1 / +0,4 | -0,5 / +0,4 / +0,6 | ⚪ |
| Part longue | 1 / 2 / 4 | +0,1 / +0,3 / +0,3 | 0,0 / +0,1 / -0,1 | +0,8 / +1,0 / +1,4 | -0,4 / -0,1 / +0,2 | ⚪ |
| Pression spéculative (Fan) | 1 / 2 / 4 | +0,2 / +0,3 / +0,4 | +0,1 / +0,1 / -0,1 | +1,4 / +1,6 / +2,1 | -0,3 / -0,2 / -0,2 | ⚪ |
| Divergence fonds / prix | 1 / 2 / 4 | +0,7 / +0,4 / +1,0 | -0,5 / -0,9 / -0,8 | +0,3 / +0,1 / -0,3 | +0,8 / +0,5 / +1,0 | ⚪ |
| Extrême 52 sem. (10 % / 90 %) | 1 / 2 / 4 | +0,3 / +0,1 / +0,4 | +0,5 / +0,7 / +1,1 | +0,3 / +0,2 / -0,1 | +0,6 / -0,2 / -0,4 | ⚪ |
| Extrême 156 sem. | 1 / 2 / 4 | +0,4 / -0,1 / -0,3 | -0,7 / -1,0 / -0,7 | -0,1 / -0,1 / -0,5 | +0,5 / -0,5 / -0,8 | ⚪ |
| *Repère : tendance 60 j seule* | 1 / 2 / 4 | +0,4 / +0,1 / -0,3 | -0,8 / -0,8 / -0,4 | -1,7 / -1,9 / -1,4 | — | ⚪ |

- Plus forte valeur sur la période de choix : +1,0 (divergence, 4 semaines), loin de 3,80 et même de 2.
- Le seul chiffre > 2 est la pression spéculative à 4 semaines sur le **contrôle** (+2,1) : elle était à +0,4
  puis -0,1 avant. C'est le reflet de la grande hausse 2023-25 (fonds longs ET or qui monte), pas un signal stable.
- Kang et al. (« le mouvement dû aux fonds se retourne ») : variation 1 semaine lue à l'envers ; signe négatif
  sur les trois périodes mais force -0,4 à -1,6 : pas assez.
- Coyle et al. (extrêmes) : aux extrêmes de 156 semaines, l'or n'a PAS fait l'inverse des fonds (4 sem. après un
  sommet des fonds : or en hausse 57 % du temps ; après un creux : 52 %). Hypothèse contraire non retrouvée.
- Dates au hasard (2 000 décalages) : sur 2006-2019, aucune case sous 39 % (valeur p) ; le vrai lien n'est pas plus
  fort que des dates tirées au hasard.

## Le trade simple (entrée le lundi après publication, frais FTMO de l'or + nuits, compte Swing, agitation 10 %/an)
| Période | Meilleur des 27 (gain %/mois après frais) | Moyenne des 27 | Force contre jumeau (meilleure) | Repère tendance 60 j |
|---|---|---|---|---|
| Choix 2006-19 | +0,06 (extrême 156, 2 sem.) | -0,16 | +1,3 | -0,05 à +0,05 |
| Vérif. 2020-22 | +0,58 (rang 52, 4 sem., contre les fonds) | -0,11 | +1,8 | -0,22 à +0,03 |
| Contrôle 2023-09/25 | +0,45 (variation 1 sem., 1 sem., contre les fonds) | -0,27 | +1,8 | -0,02 à +0,65 |

Les cases qui gagnent ne sont pas les mêmes d'une période à l'autre ; aucune force contre le jumeau n'atteint 3,80
(maximum 1,8). Les challenges FTMO simulés suivent le hasard (ex. variation 1 sem. sur 2006-19 : 8 % réussis /
90 % morts, jumeaux 12 % / 82 %).

## Indépendant de la tendance de fond ?
Sans objet : il n'y a pas d'information à séparer. Avec la tendance 60 j dans la même régression, aucune force ne
dépasse 1,0 sur 2006-2019. (La tendance 60 j seule n'a pas non plus d'avantage sur l'or en sens hebdomadaire.)

## À donner à MAGNETAR ?
**Non.** ⚪ partout. Si on veut quand même lui montrer le positionnement, ce serait comme simple « contexte »
(qui est déjà dans le prix) — à ne pas compter comme une source de sens.

## Limites honnêtes
- Prix journaliers (Kaggle, heure du serveur) : entrée et sortie à l'ouverture du jour, pas de glissement en plus.
- Dates de publication reconstruites (règle prudente des jours fériés) ; le fichier n'a pas la vraie date.
- Le calcul des frais d'écart utilise le prix de l'or au relevé FTMO (10/2026) comme le reste du projet (constante de
  frais, ne sert à aucun choix).
- Le test des dates au hasard est peu fiable sur les périodes courtes (vérification, contrôle : ~140-156 semaines).
- Futures COMEX seulement (pas les options), or seul, positions de « fonds gérés » seulement.
