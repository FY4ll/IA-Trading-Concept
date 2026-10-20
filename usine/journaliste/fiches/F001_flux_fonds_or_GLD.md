# F001 — Les entrées / sorties d'or du fonds GLD continuent-elles dans le même sens ?

Fournée 1 (20/10/2026) — journaliste. Statut : proposée. Risque de déjà-vu : **faible** (source jamais utilisée).
Marché FTMO : **XAUUSD** (or).

## 1. Hypothèse
Quand le fonds coté SPDR Gold Shares (GLD) gagne (ou perd) de l'or de façon suivie pendant 10 jours de Bourse, l'or
continue dans le même sens pendant les 10 jours de Bourse suivants.
- Signal principal (un seul) : somme des variations de tonnes sur les 10 derniers jours connus, divisée par l'écart
  type de cette somme sur les 250 jours précédents. Achat si > +1, vente si < -1, sinon rien. Sortie après 10 jours.
- Variante opposée, à déclarer d'avance ou à abandonner (le scientifique choisit, pas les deux après coup) : après une
  sortie d'or extrême sur UN jour, l'or se reprend 3 à 5 jours (pression de prix passagère).

## 2. Mécanisme
- Les parts de GLD sont créées ou détruites par de grandes banques (« participants autorisés ») qui achètent ou
  revendent de l'or physique à Londres. Une hausse des tonnes = de l'argent frais d'investisseurs lents (conseillers en
  patrimoine, caisses de retraite, gestion de fortune) qui achètent du vrai métal.
- Ces investisseurs décident par comité et étalent leurs achats sur des semaines : le flux d'aujourd'hui annonce une
  partie du flux des jours suivants, donc une demande de métal qui n'est pas encore passée.
- Pourquoi ce ne serait pas déjà arbitré : la donnée est publique mais seulement le lendemain ; les acteurs rapides de
  l'or (marché à terme de New York) regardent le prix, pas les tonnes ; la demande physique étalée est un flux, pas une
  nouvelle. **Contre-argument fort** : le personnel de la SEC n'a trouvé aucun lien entre les flux des fonds de métaux
  et les prix suivants, et plusieurs analyses disent que les flux SUIVENT le prix (les investisseurs achètent après la
  hausse). C'est le piège principal à contrôler (section 5).

## 3. Donnée
| point | détail |
|---|---|
| source | SPDR Gold Shares, page officielle https://www.spdrgoldshares.com/usa/historical-data/ (fichier .xlsx) |
| historique | 18/11/2004 -> aujourd'hui, un jour de Bourse par ligne |
| **date de publication** | chiffres du jour d mis en ligne vers 6h00-6h30 heure de New York le jour d+1 -> utilisable à **d+1 10h00 New York** (marge prudente) |
| gratuit et légal | gratuit ; **usage privé et interne seulement** (clause du fichier : reproduction interdite) |
| présent dans `data/` | **OUI** : `data/maitres/spdr_gld/gld_reserves_quotidiennes.csv` (colonnes `tonnes_or`, `variation_tonnes`, `prime_decote_pct`), téléchargé le 19/10/2026 ; LISEZMOI à côté. Rien à télécharger. |
| complément possible (non nécessaire) | fonds iShares IAU (ishares.com) : historique des avoirs moins accessible, non vérifié |

## 4. Pourquoi ce n'est pas déjà au registre
- Aucune ligne du registre n'utilise les avoirs ou les flux d'un fonds d'or.
- Lignes proches : **I020** (macro + positions COT + marchés liés -> or, rien de stable), **I101** (positions COT des
  fonds sur l'or : force max 1,0 ; les fonds à terme suivent le prix, lien +0,68 la même semaine), **I073/I074**
  (contre la foule).
- Différence précise : autre population (acheteurs de métal physique via un fonds coté, pas spéculateurs à terme), donnée
  QUOTIDIENNE connue le lendemain (le COT est hebdomadaire avec 3 jours de retard), et le sens testé est la
  **persistance** du flux, pas l'extrême d'une position.

## 5. Ce qui la réfuterait — ordre de grandeur — frais
- **Réfutation 1** : force du lien (signal connu à d+1 10h00 -> rendement de l'or de d+1 à d+11) < 2 sur la période de
  choix 2005-2015, ou signe inverse sur 2016-2023 -> morte.
- **Réfutation 2 (piège « les flux suivent le prix »)** : refaire le lien en retirant le rendement passé de l'or sur
  10 jours (et la tendance 60 jours). Si l'information disparaît, le flux n'est qu'une copie de la tendance (déjà
  testée : I030, I041, I105) -> morte.
- **Réfutation 3** : ne bat pas « acheteur permanent à exposition égale » (l'or a monté sur la période).
- Ordre de grandeur publié : personnel de la SEC (analyse de causalité sur les fonds de métaux) : **aucun lien** ;
  une étude par modèle à retards (thèse, non relue) : effet **positif à 1-2 jours puis négatif à 3-5 jours** (pression
  de prix qui se retourne) — c'est ce qui justifie la variante opposée. Aucun chiffre de gain publié sérieux trouvé.
- Frais FTMO : ~0,02 % aller-retour + nuits ~3 %/an x 10/365 ≈ 0,08 % -> **~0,10 % par trade**. L'or bouge d'environ
  3 % en 10 jours (agitation ~15 %/an) : il faut un avantage moyen > 0,10 %, soit un lien de rang d'environ 0,04-0,05.
  Possible seulement si l'effet est réel. ~15-25 trades par an : pas de mort par inactivité FTMO.
