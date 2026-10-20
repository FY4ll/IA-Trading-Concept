# Protocole de validation (non négociable) — 20/10/2026

## 1. Avant chaque test
- Un dossier `etudes/<date>_<nom>/` avec `PLAN_FIGE.md` : question, hypothèse, marchés, périodes, règles, juges,
  critères d'acceptation, ce qui la réfuterait. **Commité dans git AVANT le premier calcul** ; le script écrit un
  verrou (`resultats/VERROU*.json` : heure, commit, modifications non commitées) et refuse un 2e lancement.
- Une hypothèse déjà testée ne revient que si le plan dit : ce qui change, pourquoi l'ancien test ne suffisait pas, quel
  résultat la réfuterait, quelles données indépendantes la jugeront (mission §3.6).
- Inscription au registre unique `etudes/REGISTRE_IDEES.csv` (échecs compris, nombre de variantes).

## 2. Périodes
- Recherche / Validation / COFFRE séparées dans le temps. COFFRE actuel des hypothèses neuves : **2024-01-01 ->
  2026-10-13**, jamais chargé par les scripts de recherche (données coupées au 01/01/2024) ; ouvert seulement avec
  l'accord du chef de projet, une fois, pour un candidat qui a tout passé. Un COFFRE regardé est consommé.
- Pas de normalisation, de seuil ni de choix calculés sur une période postérieure à la décision (tests « sans futur »).

## 3. Juges (tous les tests)
- **Pile ou face** : même moment, même taille, mêmes distances, sens au hasard (espérance exacte = moyenne du trade et
  de son inverse).
- **Acheteur permanent** : le même marché tenu à l'achat tout le temps (taille selon la volatilité, frais de nuit),
  comparé à risque égal.
- **Hasard d'horaire** (hypothèses d'horaire) : mêmes fenêtres déplacées au hasard dans le même mois, 200 tirages.
- Avantage ± incertitude (par mois ou par trimestre selon la durée des positions). « Bat le juge » = avantage > 2 ×
  incertitude ; seuil relevé selon le nombre de comparaisons (racine(2 ln M)).

## 4. Frais et compte
- Frais FTMO réels (`core.ftmo`) : écart mesuré ramené au prix de l'époque, commission, frais de nuit de chaque époque,
  nuit triple ; sensibilité frais × 1,5 obligatoire.
- Règles FTMO vérifiées (`docs/FTMO_REGLES_VERIFIEES.md`) : -5 % par jour (solde de minuit à Prague, latent compris),
  -10 % au total, 30 jours sans ouvrir de trade (Challenge / Vérification), pas d'ouverture dans les 2 h avant une
  fermeture de 2 h ou plus, compte Swing (levier 1:30 devises, 1:15 indices / métaux).
- Taille par défaut : ajustée chaque jour à la volatilité (10 %/an).

## 5. Ce qui compte comme preuve
- Gain après frais > 0 sur chaque période ; bat ses juges ; robuste sur d'autres marchés quand c'est pertinent ;
  assez d'observations (un résultat sur trop peu de trades = « inconclusif », jamais « réussi ») ; puis COFFRE ; puis
  démo réelle avec réconciliation ; puis accord explicite avant tout argent réel.
- Un critère n'est jamais changé après avoir vu un résultat (sinon : accord du chef de projet et nouveau test).
- Les erreurs de MESURE trouvées après un lancement sont corrigées, déclarées dans le plan (avenant) et le test est
  relancé une fois ; le lancement fautif est gardé.
