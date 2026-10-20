# F007 — Le dollar baisse les jours de décision de la Fed

Fournée 1 (20/10/2026) — journaliste. Statut : proposée. Risque de déjà-vu : **moyen à élevé** (famille « Fed » :
I056 veille de Fed et semaines paires, I038 surprises des annonces). À rejeter si le scientifique juge la différence
insuffisante.
Marchés FTMO : **EURUSD, USDJPY, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDCHF** (panier) ; **XAUUSD** en secondaire.

## 1. Hypothèse
Le jour d'une décision prévue de la Fed, le dollar baisse en moyenne contre les autres grandes devises, d'autant plus
contre les devises à taux élevés et quand l'incertitude sur la politique de la Fed est forte.
Signal principal (un seul) : vendre le dollar contre le panier des 7 devises (poids égaux, taille réglée sur l'agitation)
de 17h New York la veille à 17h New York le jour de la décision. Aucun choix de sens : on vend toujours le dollar.
Variante conditionnelle déclarée d'avance (une seule) : seulement quand l'incertitude est haute (indice EPU de la
politique américaine, déjà local, dans son tiers haut sur 1 an, valeur connue la veille).

## 2. Mécanisme
- Mueller, Tahbaz-Salehi et Vedolin (Journal of Finance, 2017) : les intermédiaires qui portent la demande mondiale de
  devises ont un capital limité ; le risque de la décision de la Fed leur fait demander une prime, payée le jour de
  l'annonce par ceux qui détiennent le dollar. Plus forte quand la Fed baisse ses taux et quand l'incertitude est haute.
- Pourquoi pas arbitré : c'est une **prime de risque** (on est payé pour porter le risque de la décision), pas une
  erreur de prix : elle peut durer, mais elle peut aussi coûter cher certains jours.

## 3. Donnée
| point | détail |
|---|---|
| source | dates des réunions de la Fed : https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm et pages historiques par année (accès par « historical materials by year », vérifié le 20/10/2026). Incertitude (variante) : EPU, policyuncertainty.com. |
| historique | dates : depuis 1936 ; décisions annoncées le jour même depuis 1994 |
| **date de publication** | dates fixées et publiées un an à l'avance -> aucune fuite. **Piège déjà rencontré (I038)** : l'heure de l'annonce a changé (14h15 New York jusqu'en 2012, 12h30 certains jours de 2011-2012, 14h00 depuis 2013) et les heures de Forex Factory sont fausses ; ici la fenêtre couvre la journée entière, donc l'heure exacte n'est pas nécessaire. Réunions d'urgence (non prévues, ex. mars 2020) : **exclues** (pas connues d'avance). EPU : valeur du jour J utilisable à J+1 08h00 serveur (`data/monde/LISEZMOI.md`). |
| gratuit et légal | oui |
| présent dans `data/` | **OUI** : `data/macro_events_real.csv` (vrais horodatages CPI / emploi / Fed, 2015 -> ; à compléter 2010-2014 depuis le site de la Fed, une liste de ~40 dates), `data/calendrier/*.csv` (2007 -> ; heures douteuses), EPU dans `data/monde/All_Daily_Policy_Data.csv`. Prix des 7 devises : déjà locaux. |

## 4. Pourquoi ce n'est pas déjà au registre
- **I056** : « avant_fed » = achat **US500** de 14h la veille jusqu'à l'annonce (Lucca-Moench) et « semaines paires de la
  Fed » sur indices US ; aucune ligne sur les **devises** le jour de la décision. **I038** : sens donné par la **surprise**
  d'une annonce, dérive du **lendemain**. **I025** : portage sur devises toute l'année.
- Différence précise : marchés (devises + or, pas indices), fenêtre (le jour de la décision, pas la veille ni le
  lendemain), et aucune lecture du contenu de l'annonce (position fixe : dollar vendeur).

## 5. Ce qui la réfuterait — ordre de grandeur — frais
- **Réfutation 1** : rendement moyen du panier « dollar vendu » les jours de Fed moins les autres jours : force < 2 sur
  2010-2019 -> morte.
- **Réfutation 2** : signe inverse ou nul sur 2020-2023 (années de hausse rapide des taux : la prime pouvait s'inverser)
  -> noter comme dépendance au régime, pas comme preuve.
- **Réfutation 3 (puissance)** : 8 décisions par an -> ~110 sur 2010-2023. Agitation d'un jour du panier ≈ 0,4 % -> 
  incertitude de la moyenne ≈ 0,04 % ; il faut un effet ≥ 0,08-0,1 % par jour de Fed pour une force de 2. En dessous,
  conclure « non mesurable ».
- Ordre de grandeur publié : rendement « nettement plus élevé » du dollar vendu les jours de Fed, plus fort contre les
  devises à taux élevés (résumé de l'article) ; **le chiffre exact n'a pas pu être relu** (PDF illisible le 20/10) : à
  relever avant le plan figé.
- Frais FTMO : ~0,006-0,01 % aller-retour par paire + 1 nuit à ~2 %/an ≈ 0,005 % -> **~0,015 % par jour de Fed** :
  les frais ne sont pas l'obstacle, la taille de l'échantillon l'est. Restriction FTMO « 2 minutes autour des
  nouvelles » : seulement en compte financé Standard ; la position est ouverte la veille, donc permise ; libre en Swing.
  8 trades par an : à combiner avec autre chose contre l'inactivité.
