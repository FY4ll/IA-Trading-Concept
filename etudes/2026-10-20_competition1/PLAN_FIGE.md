# Compétition 1 — 3 hypothèses NEUVES (plan FIGÉ le 20/10/2026, AVANT toute mesure)

Mission (§15) : hypothèses jamais testées (`etudes/REGISTRE_IDEES.csv`, 105 idées), choisies pour leur chance réelle
d'avantage après frais FTMO, critères figés et commités avant le test. Rien n'est appris : règles fixes.

**Écartées avant tout calcul** (1er brouillon de ce plan, jamais commité ni lancé) : l'or en séance d'Asie, la nuit du
S&P 500 et le tournant du mois — déjà testés le 16/10 (registre I056, `collapsar/archives/2026-10-16_pistes/vie/pistes/
calendrier_horaires/rapport.md` : morts après frais). Aucune raison nouvelle et réfutable de les refaire.

## Périodes (tous marchés)
- **Recherche : 2012-01-01 -> 2019-12-31** ; **Validation : 2020-01-01 -> 2023-12-31** ; la règle doit tenir sur CHACUNE.
- **COFFRE : 2024-01-01 -> 2026-10-13** : FERMÉ ; jamais chargé (données coupées au 01/01/2024 dans le script).
  Ouverture seulement avec l'accord du chef de projet, une fois, pour une candidate qui a passé tous les critères.

## Heures, prix, règles FTMO
Heure du serveur MetaTrader = New York + 7 h. Prix à un instant X = ouverture de la bougie de 15 min qui commence dans
les 30 min après X, sinon clôture de la bougie qui finit à X ; sinon la fenêtre est sautée. Pas d'ouverture dans les
2 h avant une fermeture du marché de 2 h ou plus (week-ends, fériés = trous de 20 h ou plus dans nos données ; règle
FTMO vérifiée, `docs/FTMO_REGLES_VERIFIEES.md`). Taille selon la volatilité (10 %/an, écart type des 60 derniers
rendements journaliers connus la veille). Frais FTMO réels (`core.ftmo`) : écart + commission à l'entrée et à la sortie,
nuits de chaque époque (nuit triple). Gains en % de 100 000 $, non réinvestis. Sensibilité : écart × 1,5.

## Les 3 hypothèses
- **N1 — l'élan de la journée sur les indices américains** (Gao, Han, Li, Zhou 2018, « Market intraday momentum ») :
  à 22:30 serveur (15:30 NY), sens = signe du rendement de la veille 23:00 serveur (clôture) à 17:00 serveur (10:00 NY) ;
  position de 22:30 à 23:00 serveur. Marché : S&P 500 (USA500IDXUSD) ; robustesse : Nasdaq 100, Dow Jones.
  Famille voisine déjà testée : la bande de bruit de Zarattini (registre I052, négative) — règle DIFFÉRENTE (cassure
  d'une bande en journée) ; la règle de Gao (la dernière demi-heure suit le reste de la journée) n'a jamais été testée.
  Réfutée si : pas d'avantage sur pile ou face, ou perte après frais.
- **N2 — le trou d'ouverture se referme** sur les indices américains (« l'ouverture efface la nuit ») : chaque jour de
  bourse, trou = prix à 16:30 serveur (09:30 NY) / prix de la veille à 23:00 serveur - 1 ; si |trou| ≥ 0,25 × écart type
  journalier (60 jours, connu la veille), position de sens OPPOSÉ au trou de 16:30 à 23:00 serveur. Marché : S&P 500 ;
  robustesse : Nasdaq 100, Dow Jones. Réfutée si : pas d'avantage sur pile ou face, ou perte après frais.
- **N3 — retournement de la semaine entre devises** (le gagnant d'une semaine rend une partie la semaine suivante) :
  7 grandes paires (EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD), chaque devise mesurée contre le dollar.
  Rendement de la semaine = vendredi 21:00 serveur -> vendredi 21:00 serveur. On ACHÈTE les 2 devises qui ont le plus
  baissé et on VEND les 2 qui ont le plus monté, du lundi 02:00 au vendredi 21:00 serveur (chaque jambe : moitié de la
  taille selon la volatilité). Réfutée si : pas d'avantage sur le tirage au hasard des devises, ou perte après frais.

## Juges
- **Pile ou face** (juge clé de N1, N2) : même fenêtre, sens au hasard (espérance exacte).
- **Tirage au hasard des devises** (juge clé de N3) : chaque semaine, 2 devises achetées et 2 vendues au hasard parmi
  les 7, mêmes heures, même taille ; 200 tirages. 2e juge de N3 : pile ou face sur les mêmes 4 jambes.
- **Acheteur permanent à risque égal** (N1, N2) : l'indice tenu à l'achat tout le temps, ramené à la même volatilité.
- Incertitude : écart type des avantages mensuels / racine du nombre de mois.

## Critères d'acceptation (tous obligatoires, 2012-2023, sur le marché principal)
1. Gain moyen après frais > 0 sur la Recherche ET sur la Validation.
2. Avantage sur le juge clé > 2 × incertitude sur 2012-2023 (3 hypothèses : racine(2 ln 3) = 1,48 < 2), ET positif
   sur chacune des deux périodes.
3. N1, N2 : avantage sur l'acheteur permanent à risque égal > 0 ; N3 : avantage sur pile ou face > 0.
4. Robustesse : N1, N2 : avantage sur pile ou face positif sur au moins 1 des 2 autres indices ; N3 : la part de
   chaque devise (ses jambes contre le tirage au hasard) positive pour au moins 5 devises sur 7.
5. Écart × 1,5 : gain moyen toujours > 0 sur 2012-2023.
6. Au moins 100 trades sur 2012-2023.
Une hypothèse qui passe tout = candidate -> demande d'ouverture du COFFRE au chef de projet. Sinon : inscrite au
registre avec sa raison. Aucun critère ne change après avoir vu un résultat.
