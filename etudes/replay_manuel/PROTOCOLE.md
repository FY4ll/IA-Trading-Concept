# Replay manuel : mesurer ton œil sur l'or (protocole figé le 20/10/2026)

But : savoir si TES décisions à l'œil (pas notre traduction en règles) ont un avantage, contre les mêmes juges que
toutes nos idées. Objectif : 100 trades, à ton rythme. Rien ne t'attend : l'usine continue à côté.

## Comment faire une séance
1. Ouvre `sessions.csv` et prends la **prochaine séance non faite, dans l'ordre** (ne saute pas une date parce qu'elle
   ne te plaît pas ; si tu dois la sauter, écris pourquoi dans la colonne « remarque »).
2. TradingView, or (le symbole que tu utilises d'habitude ; note-le une fois dans la remarque de la séance 1).
   **Mets le fuseau horaire du graphique sur UTC** (Paramètres du graphique -> Fuseau horaire -> UTC).
3. Lance le Replay à la date de départ, 00:00 UTC. **Ne regarde rien après cette date** (ni autre graphique, ni
   souvenir de l'époque : si tu reconnais la période, écris-le dans la remarque).
4. Avance comme tu veux (n'importe quelle unité). Prends tes trades comme en vrai, **au plus 3 trades par séance**, et
   arrête la séance au plus tard **10 jours de bourse** après le départ (même sans trade : c'est une information aussi).
5. Pour chaque trade, une ligne dans `replay_trades.csv` (modèle ci-dessous), au moment où tu le prends et où tu sors.
   Remplis « faite_le » et « trades_pris » dans `sessions.csv` à la fin de la séance.

## Le fichier `replay_trades.csv` (séparateur « ; », une ligne par trade)
| colonne | exemple | règle |
|---|---|---|
| seance | 1 | numéro dans sessions.csv |
| entree_utc | 2015-05-18 13:45 | heure UTC de l'entrée (minute) |
| sens | A | A = achat, V = vente |
| prix_entree | 1225.40 | |
| stop | 1218.90 | obligatoire (là où tu sors si tu as tort) |
| objectif | 1240.00 | ton objectif (vide si aucun) |
| sortie_utc | 2015-05-19 09:30 | heure UTC de ta sortie réelle (stop, objectif ou à la main) |
| prix_sortie | 1236.10 | |
| partiel | 80 % à 2R | ta gestion si tu fermes en plusieurs fois (texte libre ; le prix de sortie = moyenne) |
| unite | H1 | unité principale de ta décision |
| raison | zone H4 retestée + VRVP | en quelques mots |

## Ce qui sera mesuré (figé AVANT ton premier trade : `mesurer.py`)
- Sur nos données d'1 minute (autre source que TradingView : petits écarts de prix normaux), chaque trade est vérifié
  (prix plausibles à ces minutes) puis compté en R (1 R = entrée -> stop), **frais FTMO réels** compris (écart, nuits).
- Trois juges sur les MÊMES trades : **pile ou face** (même entrée, même stop / objectif de l'autre côté, même sortie) ;
  **acheteur permanent** (le même trade en achat) ; **hasard d'horaire** (même trade, même durée, à un moment tiré au
  hasard dans les 10 jours de la séance, 200 tirages).
- Incertitude par séance (les trades d'une même séance ne sont pas indépendants).
- **Ton œil a un avantage mesurable si**, sur au moins 100 trades : gain moyen après frais > 0 ; avantage sur pile ou
  face > 2 × incertitude ; avantage sur l'acheteur > 0 ; avantage sur le hasard d'horaire > 0. Sinon : on le saura
  aussi, et c'est une information précieuse.
- Si c'est le cas : l'IA apprendra de tes trades, et on te proposera des séances sur le COFFRE (2024-2026) pour une
  vérification finale (avec ton accord).

`venv_gpu\Scripts\python.exe etudes\replay_manuel\mesurer.py` : point d'étape à tout moment (rien n'est choisi dessus).
