# Couche 1 — Perception « TENDANCE DE FOND » : plan FIGÉ (20/10/2026, écrit AVANT toute mesure)

Ordre du chef de projet (20/10) : sens = signe du rendement sur N mois, N = 1, 3, 6, 12, TOUS publiés ; juges pile ou
face et acheteur permanent ; drawdown et limites FTMO ; robustesse sur d'autres marchés ; taille selon la volatilité,
stop large, frais FTMO réels. Le commit git qui contient ce fichier et le code fait foi ; le test est lancé UNE fois
(verrou `resultats/VERROU_TEST.json`).

## Données et périodes
- Bougies de 15 min (heure du serveur) -> bougies d'1 h (suivi des positions) et journalières (décisions).
- **Test verrouillé : 2018-01-01 -> 2026-10-13** (tous les marchés). Historique d'avant 2018 utilisé seulement pour
  calculer les rendements passés et la volatilité au départ.
- Or : XAUUSD. **Robustesse (choisis avant le test, mêmes règles, jamais tradés)** : argent XAGUSD, S&P 500
  USA500IDXUSD, Nasdaq 100 USATECHIDXUSD, euro-dollar EURUSD, dollar-yen USDJPY (gains convertis en dollars).
- Aucune mise au point sur les gains : seuls les comptes (nombre de trades) sont vérifiés avant le test.

## Le module (rien n'est appris) — paramètres, tous figés
- **Sens** à la clôture de chaque jour du serveur : signe de (clôture du jour / clôture du dernier jour ≤ même date
  il y a N mois − 1), N ∈ {1, 3, 6, 12} mois (calendaires). Zéro = pas de position.
- **Exécution** : à l'ouverture de la 1re bougie d'1 h après la clôture du jour de décision.
- **Taille selon la volatilité** : viser 10 %/an de volatilité pour un compte de 100 000 $ : montant = 100 000 × 0,10 /
  (écart type des 60 derniers rendements journaliers × racine(252)) ; fixée à l'ouverture, gardée jusqu'à la sortie.
  Plafonnée par le levier FTMO du marché.
- **Stop large** : 3 × ATR(20 jours) depuis le prix d'entrée. Stop touché -> à plat ; le lendemain, nouvelle
  décision (on reprend la position si le sens est toujours le même).
- **Sortie** : quand le sens change (on se retourne à l'ouverture suivante) ou au stop.
- **Frais FTMO réels** : écart + commission (`core.ftmo.frais`, ramenés au prix de l'époque) payés à chaque passage
  d'ordre (moitié à l'entrée, moitié à la sortie) ; **frais de nuit** de chaque époque, achat et vente séparés
  (`core.ftmo.nuit.taux_nuit`), nuit triple comme FTMO (`core.ftmo.horloge.nuits_payees`). Compte FTMO **Swing**
  (positions gardées le week-end ; le compte Normal l'interdit).
- Gains non réinvestis (taille calculée sur 100 000 $) : les gains s'additionnent, les juges sont comparables.

## Les juges (même période, mêmes règles de taille, stop, frais)
- **Acheteur permanent** (le juge clé) : le même système avec le sens toujours +1.
- **Pile ou face** : moyenne du système et du même système au sens inversé (espérance d'un sens tiré au hasard).

## Ce qui est mesuré (par marché et par N)
- Gain %/mois, volatilité annuelle, rapport gain / volatilité (annualisé), **pire baisse** (du plus haut, au pire
  moment de chaque heure), **pire jour** (pire moment du jour contre la clôture de la veille), jours ≤ -5 %.
- **Challenge FTMO simulé** : un départ au début de chaque mois du test ; réussi si +10 % (clôture d'un jour) avant
  -10 % au total, une journée à -5 % ou **30 jours sans ouvrir de trade** (règle d'inactivité FTMO) ; % réussis /
  échoués (dont inactivité) / non conclus à la fin des données.
- Trades par an, part du temps en position, part du temps à l'achat.

## Verdicts (figés)
- Avantage = gain mensuel du système - gain du juge ; incertitude par TRIMESTRES (une tendance dure plusieurs mois :
  écart type des sommes trimestrielles / racine du nombre de trimestres, ramené au mois).
- **À risque égal** : l'acheteur permanent est ramené à la même volatilité mensuelle que le système (gains × σ système
  / σ acheteur) ; avantage à risque égal = système - acheteur ramené.
- **Bat l'acheteur permanent une fois le risque pris en compte** si l'avantage à risque égal > 2 × incertitude.
- **Robuste** (pour un N donné) si sur les 5 autres marchés l'avantage à risque égal est positif sur au moins 3, ET la
  moyenne des 5 (trimestre par trimestre) > 2 × son incertitude.
- Tous les N et tous les marchés sont publiés.
