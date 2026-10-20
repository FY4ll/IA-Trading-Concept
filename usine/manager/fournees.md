# Fournées de l'usine

Compteur : 2 fournées « prix seuls » d'avant l'usine (compétitions 1 et 2 du 20/10) : 0 idée retenue. Registre : 111 idées.
Nombre total d'essais (registre) : ≈ 117 500 (≈ 11 800 sans la découverte automatique de Run A). Inchangé tant que
la fournée 1 n'est pas jugée (les idées n'entrent au registre qu'une fois testées).

## Fournée 1 (20/10/2026) — tri des fiches F001 à F007 du journaliste

Période de choix : 2012-2019. Vérification : 2020-2023. COFFRE 2024-01-01 -> 2026-10-13 fermé.
Repère de puissance (pour toutes) : les signaux lents sur un seul marché ont peu de cas indépendants ; « prouvé »
(force ≈ 4,8) est hors de portée pour chacune ; le but réaliste de cette fournée est « prometteur » (force > 2 corrigée
pour la fournée) sur 2012-2019 ET même signe sur 2020-2023.

### Retenues (classées par chance réelle d'avantage après frais FTMO)

| rang | fiche | pourquoi retenue |
|---|---|---|
| 1 | **F007** dollar vendu le jour de décision de la Fed | seul effet publié EN DEVISES (Mueller, Tahbaz-Salehi, Vedolin 2017), frais quasi nuls (~0,015 %/jour), aucune fuite possible (dates connues un an avant), données locales. Différent de I056 (indices, veille) et I038 (surprise, lendemain). Limite : ~8 cas/an -> composant seulement (inactivité FTMO seule). |
| 2 | **F002** gérants d'actifs (rapport CFTC des contrats financiers) sur devises | catégorie jamais regardée (I074 = petits spéculateurs de l'ancien rapport ; I101/I020 = or), raison nouvelle et réfutable (contrôle « fonds à levier » + retrait du rendement passé). Meilleure puissance de la fournée (plusieurs devises, hebdomadaire). A priori faible : aucune étude. |
| 3 | **F001** flux du fonds d'or GLD (persistance 10 jours) | source jamais utilisée, données locales datées (connues à j+1), signal quotidien. Contre : l'étude du personnel de la SEC ne trouve rien et les flux suivent souvent le prix -> le piège doit être tué par le retrait de la tendance (I030/I041/I105). |
| 4 | **F006** liquidité nette de la Fed (bilan − compte du Trésor − pensions) | série jamais utilisée, publication datée (jeudi 16h30 NY), test honnête possible AVANT la mode (2012-2019). Contre : idée de mode ajustée sur 2020-2022, indices peu puissants (peu de cas indépendants). Dernière de la liste. |

### Refusées

| fiche | raison |
|---|---|
| **F003** écart de l'or à sa relation taux réel + dollar | déjà testée sans raison nouvelle suffisante : I020 a testé le taux réel (niveau classé sur 1 an et variations) jusqu'à **20 jours** (t ≈ -0,3 à -1,1, rien) ; I008 (FRED -> or 10 j, tri 0,48-0,52) ; I004. Cassure connue de la relation depuis 2022. Trop peu de cas (tenue 20-60 j : ~40-80 trades sur 2012-2019), frais 0,2-0,5 %/trade, inactivité FTMO. |
| **F004** adjudications du Trésor -> dollar-yen | obligation US non tradable chez FTMO (absente de `core/ftmo/conditions_ftmo.json`) ; transmission au dollar-yen jamais publiée ; ~12 grappes/an (10 et 30 ans la même semaine) -> ~96 cas sur 2012-2019, incertitude ~0,12-0,15 % par cas contre un effet plausible de 0,05-0,1 % (quelques points de base de taux) : nombre de cas trop faible pour conclure. À rouvrir seulement si FTMO propose une obligation US. |
| **F005** semaine d'échéance des options sur indices | famille calendrier déjà morte (I056 : 12 effets, dont semaines de la Fed et tournant du mois) ; effet publié en 2010 sur 1996-2008, « relativement élevé » seulement sur le S&P 500 ; ~96 semaines sur 2012-2019 : incertitude ~0,24 % pour un écart plausible ≤ 0,15 % (force < 1,5 même si l'effet publié survivait en entier) : nombre de cas trop faible. Écart de 5 semaines entre deux échéances certains mois -> inactivité FTMO > 30 jours. |

### Fiche technique des idées retenues (pour le scientifique)

**1. F007 — dollar vendu le jour de Fed**
- Données : dates des réunions PRÉVUES (local `data/macro_events_real.csv` 2015 -> ; compléter 2012-2014, ~24 dates,
  depuis federalreserve.gov, gratuit) ; réunions d'urgence exclues. Prix 15 min locaux `data/fx_intraday/` (7 paires,
  2010 ->). EPU local `data/monde/All_Daily_Policy_Data.csv` (variante unique, valeur de la veille).
  Relever AVANT le plan figé le chiffre exact de l'article (le journaliste n'a pas pu le lire).
- Marché principal : panier « dollar vendu » contre EUR, JPY, GBP, AUD, NZD, CAD, CHF (poids égaux, taille selon
  l'agitation). Robustesse : chaque paire seule (même signe attendu sur la majorité), devises à taux élevés contre
  taux bas (prédiction de l'article), XAUUSD (même fenêtre).
- Cas attendus : 2012-2019 ≈ 64 décisions ; 2020-2023 ≈ 31 (hors urgences de mars 2020).
- Juge clé : jumeau « jours ordinaires tirés au hasard, même fenêtre 17h -> 17h New York, même panier » (écart Fed −
  autres jours) ; + contrôle « dollar vendu en permanence » (tendance du dollar 2014-2022). Force ≥ 2 sur 2012-2019
  et même signe sur 2020-2023, sinon morte. Seuil de taille : effet < 0,08 % par jour de Fed = « non mesurable ».
  Note FTMO : jamais seule (6-7 semaines entre deux réunions).

**2. F002 — gérants d'actifs (CFTC) sur devises**
- Données : à télécharger (gratuit, domaine public) : CFTC « Traders in Financial Futures ; Futures Only », fichier
  groupé 2006-2016 + annuels 2017-2023 -> `data/cftc_tff/`. Date d'usage : vendredi 15h30 NY (lundi si férié),
  retards connus (fermetures de l'État oct. 2013, déc. 2018-janv. 2019) à relever dans les archives de calendrier CFTC,
  utilisables à l'ouverture suivante. Prix locaux `data/fx_intraday/` (2010 ->). Attention : contrat yen = JPY/USD
  (signe inversé pour USDJPY), idem CHF, CAD.
- Marché principal : EURUSD, USDJPY, GBPUSD, AUDUSD (panier). Robustesse : USDCHF, USDCAD, NZDUSD. Indices US500/US100
  EXCLUS de cette fournée (positions d'arbitrage et de réplication : pas un avis sur le sens).
- Cas attendus (un seul horizon à fixer d'avance, 4 semaines conseillé) : 2012-2019 ≈ 280 trades de 4 semaines sur le
  panier (≈ 1 100 semaines-devise en position) ; 2020-2023 ≈ 140. Robustesse : +≈ 210 / +≈ 105.
- Juge clé : lien du signal APRÈS retrait du rendement passé de la devise sur 4 semaines (piège « ils suivent le prix »)
  + contrôle « fonds à effet de levier » (même règle : s'ils font aussi bien, morte) + jumeau sens au hasard mêmes
  semaines ; frais FTMO réels avec nuits (~0,1-0,16 %/trade).

**3. F001 — flux du fonds GLD**
- Données : locales `data/maitres/spdr_gld/gld_reserves_quotidiennes.csv` (18/11/2004 ->, colonne `tonnes_or`) ; jour d
  utilisable à d+1 10h00 New York ; usage privé seulement. Or : `data/kaggle_gold/XAU_15m_data.csv` et `XAU_1d_data.csv`
  (2004 ->). Le scientifique choisit UNE variante d'avance (persistance 10 j conseillée ; la variante « reprise après
  sortie extrême » abandonnée).
- Marché principal : XAUUSD. Robustesse : XAGUSD (local 2010 ->) et période d'avant 2005-2011 sur l'or (données
  indépendantes déjà locales).
- Cas attendus (|signal| > 1, sortie à 10 jours) : 2012-2019 ≈ 120-200 trades ; 2020-2023 ≈ 60-100 ; 2005-2011 ≈ 100-175.
- Juge clé : acheteur permanent à exposition égale (l'or a monté) + même lien après retrait du rendement passé de l'or
  10 j et de la tendance 60 j (si l'information disparaît : copie de la tendance, morte) ; frais ~0,10 %/trade.

**4. F006 — liquidité nette de la Fed**
- Données : à télécharger (FRED, gratuit) : WALCL, WTREGEN, RRPONTSYD ; premières publications via ALFRED si possible,
  sinon décalage prudent déclaré ; niveau du mercredi utilisable le vendredi à l'ouverture. Attention : les pensions
  inversées existent dès 2013 avec des pics de fin de trimestre (2014-2015) : règle de traitement fixée d'avance.
  Prix locaux : USA500IDXUSD et USATECHIDXUSD (09/2011 ->), USA30IDXUSD (09/2013 ->), XAUUSD (kaggle 2004 ->).
- Marché principal : US500. Robustesse : US100, US30, XAUUSD. Sens « tiers bas » (rien ou vente) fixé d'avance.
- Cas attendus (révision hebdomadaire, tiers haut) : 2012-2019 ≈ 140 semaines en position (≈ 35 blocs indépendants de
  4 semaines) ; 2020-2023 ≈ 70 (≈ 17 blocs). Puissance faible : conclure « non mesurable » si l'incertitude domine.
- Juge clé : acheteur permanent à exposition égale ; décision sur 2012-2019 SEULEMENT (avant la mode), 2020-2023 en
  simple confirmation ; lien après retrait de la tendance 4 semaines de l'indice.

### Résumé téléphone
Fournée 1 : 4 idées retenues sur 7 (Fed et dollar, gérants d'actifs CFTC sur devises, flux du fonds d'or, liquidité de la Fed).
3 refusées : taux réels de l'or (déjà testé), adjudications du Trésor et échéance des options (trop peu de cas).

### Résultats
(à remplir après le juge)
