# Taille de position — passe UNIQUE (mission, section 8 ; décision du chef de projet du 20/10/2026)

But : corriger le défaut déclaré du test de la tendance (taille figée à l'entrée pendant des années) et mesurer ce que
la façon de dimensionner change au RISQUE. Ce n'est PAS une recherche d'avantage : la tendance de fond a échoué à ses
tests de sens (etudes/2026-10-20_couche1_tendance/RAPPORT.md) et ne sera pas réglée davantage.

- Signaux identiques (aucun changement) : tendance de fond N = 1, 3, 6, 12 mois + acheteur permanent ; or seul.
- Période : 2018-01-01 -> 2026-10-13 = 2e regard DÉCLARÉ sur cette période (déjà consommée par le test de la tendance).
- 4 tailles (cerveau/mesure/compte.py, `taille=`) : A fixe (à l'entrée, sur 100 000 $, le défaut), B capital (à
  l'entrée, sur la valeur actuelle du compte), C vol (chaque jour, ajustée si l'écart > 10 %), D capital_vol.
- Mêmes frais FTMO (écart, commission, nuits), même stop 3 ATR, même cible de 10 %/an de volatilité.
- Mesures en % de la valeur du compte : rendement, baisse depuis le plus haut, pire jour, jours ≤ -5 %, frais et nuits
  (% par an), rotation, trades, challenge FTMO (compte neuf), rendement par année.
- Pas de critère d'acceptation : mesure descriptive. Règle d'interprétation (mission §8) : la taille change la
  distribution du risque, elle ne crée pas d'avantage de prédiction.
- Lancée une fois ; le commit qui contient ce fichier et le code fait foi.
