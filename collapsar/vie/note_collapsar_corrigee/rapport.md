# Nouvelle note de COLLAPSAR avec le juge réparé (16/10/2026)

Programme : `note_corrigee.py` (copie dans ce dossier). Résultats : `mondes_*.json`, `crypto1_*.json`,
`crypto2_*.json`, `crypto2_final_*.json`, `frais.json`, `synthese.json`. Tout a tourné sur le processeur.
« Avant » = le code `mains/` archivé le 15/10 à 20h28 (`archives/collapsar_avant_SMC_20261015_2028.zip`), c'est l'état
des notes publiées. « Après » = le code `mains/` réparé le 16/10. Mêmes élèves, mêmes départs, mêmes graines.
Aucun processus arrêté, aucun verrou touché (`ecole_crypto2/final.json` intact). Les 12 mois cachés (après 09/2025)
n'ont pas été rouverts.

## 1. Les versions de COLLAPSAR et leurs notes publiées

| version | élève | juge publié | période | note publiée (où) |
|---|---|---|---|---|
| École des mille mondes | `ecole_mondes/meilleur.pt`, leçon 748 (celui de la démo à blanc depuis le 15/10 16h02) | contrôleur (`ecole/controleur_mondes.py`) : vrai euro-dollar + mondes réalistes | euro-dollar 2020-2022 | +0,02 %/mois, avantage +0,08 (force 0,6) (`ecole_mondes/controles.jsonl`, 15/10 14h17) |
| Mille mondes, élèves plus anciens | leçon 147 (`meilleur_examen_15oct.pt`) et un élève du 15/10 matin (fichier écrasé) | `juge/examen_humain.py` (4 marchés, challenges de 6 mois) | 09/2023 -> 09/2025 | -0,03 puis +0,10 %/mois, avantage +0,05 / +0,19 (`vie/examen_humain_20261015_*.json`) |
| École crypto n° 1 | `ecole_crypto/meilleur.pt`, leçon 67 | `ecole/crypto_lancer.py` (contrôle à jumeau) | 2022 -> 10/2026 | 14 cryptos -1,06 %/mois (avantage +0,32) ; BTC+ETH -0,21 (-0,03) (`ecole_crypto/rapport.md`) |
| École crypto n° 2 | `ecole_crypto2/meilleur.pt`, leçon 58 | `ecole/crypto2_lancer.py` | 2022-2023 ; final 2024 -> 09/2026 | +0,32 (puis +0,13 remesuré) ; final +0,06 %/mois, avantage +0,56 (`ecole_crypto2/rapport.md`, `final.json`) |
| Démo à blanc (`direct/blanc.py`) | leçon 748 | compte fictif en direct | depuis le 15/10 | **aucun trade** (compte fictif 100 000 $, 44 regards) : rien à noter |

`juge/examen.py`, `test_verite.py`, `test_tenir.py` notaient les anciennes écoles (13/10, arbre 1-2) : sans objet ici.
Le juge publié de la leçon 748 (14h17) est ANTÉRIEUR aux « 3 réveils » ajoutés à 14h57 : il n'est pas comparable
(7,9 trades/mois alors contre 23 avec le code actuel). D'où des « avant » recalculés ici avec le code de la démo.

## 2. Frais aller-retour appliqués aujourd'hui

| marché | simulateur de COLLAPSAR (`mains/fiches.py`) | changé par la réparation ? | frais FTMO réparés des pistes (`frais_ftmo.py`), prix d'aujourd'hui / janv. 2020 | levier avant -> après | nuit achat / vente %/an (oct. 2026) avant -> après |
|---|---|---|---|---|---|
| or | 0,012 % | non | 0,0125 % / 0,032 % | 30 -> 15 | 7,8 / 0,1 -> 5,3 / 0,4 |
| US500 | 0,012 % | non | 0,0078 % / 0,019 % | 30 -> 15 | 7,6 / -0,1 -> 5,7 / 2,1 |
| EURUSD | 0,006 % | non | 0,006 % / 0,006 % | 100 -> 30 | 3,3 / -0,3 -> 2,7 / -0,1 |
| BTC (FTMO) | 0,08 % | non | 0,066 % / 0,080 % | 2 -> 1 | 30 / 30 (inchangé) |
| BTC / ETH écoles crypto (`crypto_monde.frais_crypto`) | 0,083 % / 0,112 % | **non (oubli)** | 0,066 % / 0,090 % | 1 (inchangé) | 30 / 30 chaque nuit |

- Le simulateur de COLLAPSAR n'a jamais eu le « x 1,25 » ni la demi-fiche en plus : chaque ordre paie une demi-fiche
  (entrée + sortie = 1 fiche). La réparation C ne change donc PAS ses frais de trade. Elle change : les **nuits**
  (table FTMO achat / vente séparés, triple le vendredi pour indices / énergie / crypto), et le **levier** (Swing mesuré).
  Reste prudent sur l'US500 (0,012 % contre 0,0078 % mesuré).
- Écoles crypto 1 et 2 : frais = (commission 0,065 % + écart) x 1,25, commission comprise ; nuit 30 %/an payée chaque
  nuit 7/7 sans triple (même total par semaine que FTMO) ; levier 1:1. Elles ne voient PAS la réparation : les frais
  sont écrits en dur dans `ecole/crypto_monde.py` (0,083 / 0,112 / 0,12 %). « Après » = frais réparés des pistes
  (`regarder/pistes/crypto_flux.frais`) injectés à la place.

## 3. Ancienne note / nouvelle note (même élève, même période, processeur)

« % compte / trade » = %/mois divisé par trades/mois (frais compris). Avantage = sur le jumeau au hasard, seuil 3.

| version, période | code | %/mois | jumeau | avantage ± (force) | trades/mois | % compte / trade | baisse max moy. | réussis / murs | réussis parmi terminés |
|---|---|---|---|---|---|---|---|---|---|
| Mille mondes 748, examen 4 marchés 09/2023-09/2025 (41 challenges 6 mois) | avant | -0,08 | -0,21 | +0,13 ± 0,29 (0,5) | 115 | -0,0007 | 2,8 % | 0 % / 0 % | aucun terminé |
| | après | **+0,03** | -0,19 | **+0,22 ± 0,34 (0,6)** | 115 | +0,0003 | 2,8 % | 2 % / 0 % | 1 sur 1 |
| Mille mondes 748, vrai euro-dollar 2020-2022 (36 comptes 2 mois) | avant | -0,08 | — | -0,11 ± 0,13 (-0,9) | 23 | -0,0035 | 1,1 % | 0 / 0 | aucun |
| | après | -0,07 | — | -0,14 ± 0,13 (-1,1) | 24 | -0,0029 | 1,0 % | 0 / 0 | aucun |
| Crypto 1 (67), BTC+ETH 2022-09/2025 | avant | -0,18 | -0,22 | +0,04 ± 0,11 (0,4) | 44 | -0,004 | 1,0 % | 0 / 0 | aucun |
| | après | -0,15 | -0,18 | +0,04 ± 0,10 (0,4) | 44 | -0,003 | 0,9 % | 0 / 0 | aucun |
| Crypto 1 (67), 14 cryptos 2022-09/2025 | avant | -1,23 | -1,41 | +0,18 ± 0,26 (0,7) | 448 | -0,003 | 4,2 % | 1,5 % / 1,5 % | 2 sur 4 |
| | après | -1,12 | -1,07 | -0,05 ± 0,29 (-0,2) | 450 | -0,002 | 4,1 % | 1,5 % / 0,8 % | 2 sur 3 |
| Crypto 2 (58), BTC+ETH 2022-2023 (134 challenges) | avant | +0,25 | -0,55 | +0,80 ± 0,48 (1,7) | 36 | +0,007 | 2,7 % | 1,5 % / 0 % | 2 sur 2 |
| | après | **+0,46** | -0,38 | +0,85 ± 0,52 (1,6) | 36 | +0,013 | 2,7 % | 1,5 % / 0 % | 2 sur 2 |
| Crypto 2 (58), BTC+ETH 01/2024-09/2025 (116 challenges) | avant | +0,14 | -0,50 | +0,64 ± 0,42 (1,5) | 35 | +0,004 | 2,7 % | 0 / 0 | aucun |
| | après | +0,13 | -0,34 | +0,47 ± 0,43 (1,1) | 34 | +0,004 | 2,8 % | 0 / 0 | aucun |

Repère « connaisseur du risque » (examen 4 marchés) : +0,02 (avant) / +0,05 %/mois (après). Mille mondes : résultat
moyen d'un trade avant frais -0,008 R -> +0,002 R (14 000 trades).

Différences avec les notes publiées : les écoles crypto étaient notées sur la carte graphique (tirages au hasard
différents) ; la crypto 2 sur 2022-2023 donne +0,32 (publié), +0,13 (`final.json`) et +0,25 ici avec le même code :
**le bruit d'une mesure est d'environ ± 0,2 %/mois**. Crypto 1 et crypto 2 « final » sont coupées au 01/10/2025
(publié : jusqu'à 10/2026 et 09/2026) pour ne pas rouvrir les 12 mois cachés.

## 4. Ce qui change et pourquoi

- **Mille mondes (4 vrais marchés)** : +0,11 %/mois. Cause : les nuits. Elle est en position 71 % du temps, surtout
  acheteuse d'or et d'indice : la table FTMO fait payer 5,3-5,7 %/an à l'achat au lieu de 7,6-7,8 %. Le levier plus bas
  (15 au lieu de 30) n'a rien bloqué (tailles bien en dessous). Le jumeau bouge peu -> l'avantage passe de +0,13 à +0,22,
  toujours loin d'être prouvé (force 0,6 pour 3).
- **Euro-dollar seul** : presque rien (nuits de l'euro proches de l'ancien modèle).
- **Cryptos** : frais 20 % plus bas -> le jumeau gagne +0,03 à +0,34 %/mois (c'est l'effet mécanique des frais). Son
  avantage sur le hasard, lui, saute de ± 0,2 dans un sens ou dans l'autre : c'est le bruit (ses décisions dépendent de
  l'état de son compte, donc tout le chemin change).
- Les challenges : presque aucun ne se termine en 2 ou 6 mois (0 à 4 sur 41-134) ; « réussis parmi terminés » n'a pas
  de sens sur si peu. Ce n'est pas un défaut du juge : elle trade trop petit pour atteindre +10 % ou un mur.

## 5. Les écoles en cours voient-elles la réparation ?

- Aucune ne réimporte `mains/` : un programme Python lit le code une fois, au démarrage ; pas de sous-processus.
- **Contrôleur des mille mondes** (démarré le 15/10 17h46) : garde l'ancien code en mémoire. À son prochain redémarrage :
  mondes inventés INCHANGÉS (famille « monde » -> ancienne règle des nuits, leur propre levier) ; le contrôle sur le vrai
  euro-dollar changera un peu (nuits, levier 30).
- **École crypto n° 2** (`--final`, démarrée le 16/10 14h46, après la réparation) et toute future école crypto :
  inchangées par construction (fiches faites à la main, nuit imposée 7/7, levier 1) ; elles gardent les ANCIENS frais
  x 1,25 (0,083 / 0,112 / 0,12 %), car `crypto_monde.frais_crypto` n'a pas été recalé. À recaler si on veut qu'elles
  apprennent avec les frais réparés (0,066 / 0,090 / 0,096 %).
- **Démo à blanc** (démarrée le 15/10 16h02) : ancien code en mémoire ; nouvelles nuits et levier au prochain
  redémarrage (aucun trade depuis le départ).
- École des mille mondes elle-même : arrêtée depuis le 15/10 23h50 ; si relancée, ses mondes inventés ne changent pas.

## 6. Conclusion

Le juge réparé améliore un peu la note de COLLAPSAR (+0,1 à +0,2 %/mois, surtout par des nuits moins chères ou des frais
crypto plus justes), mais aucune version n'a un avantage prouvé sur le hasard (force 1,7 au mieux pour un seuil de 3).
La meilleure reste l'école crypto n° 2 (BTC + ETH avec ses propositions) : +0,13 à +0,46 %/mois selon la période,
toujours sous la cassure seule, et 0 à 2 % de challenges réussis. Les écarts mesurés ici sont du même ordre que le bruit
d'une mesure (± 0,2 %/mois) : la réparation ne change pas le verdict.
