# Plan figé — contrôle des anciens agents « un par unité de temps » (Run A)

Écrit le **20/10/2026 à 01h50**, AVANT toute mesure. Ce texte ne sera plus modifié ; les écarts éventuels seront
ajoutés en bas, datés, avec la raison.

## Question
Les agents M15, M30, H1, H4, D1 (et en second H1T, H1X, H1XT) avaient-ils un talent réel, ou ont-ils seulement
« acheté l'or pendant qu'il montait » ? Le compte démo est monté vers ~102 500 $ début octobre 2026 : d'où vient ce gain ?

## Règles
- Lecture seule sur `runs\`, `archives\`, `collapsar\vie\arbre_or\`, `collapsar\direct\`. Aucun ordre MT5.
- Tout le travail dans ce dossier (`collapsar\vie\controle_echelles\`) et dans le dossier temporaire de la session.
- Calcul sur processeur, un seul calcul lourd à la fois, mémoire libre > 3 Go vérifiée avant.
- **Interdit : tout mois après 09/2025** dans les rejeux.

## Étape 1 — Les faits du compte démo (le plus important)
Sources : `code\data\decision_journal.sqlite`, `code\data\episodic_memory.sqlite`, journaux `code\logs\`,
`decisions_log.csv`, et l'historique MT5 en lecture seule (`history_deals_get`), si le terminal répond.
Pour chaque style : nombre de trades, gain net en $, % gagnants, gain moyen en R (si le stop est connu), achats/ventes,
dates. Courbe du compte reconstituée (pic ~102 583 ?). Part du gain par style.
Significativité : test simple « le gain moyen par trade est-il différent de zéro » (gain moyen / (écart / racine(n))) ;
et comparaison avec ce qu'aurait donné « acheter l'or » sur les mêmes durées (même nombre de trades, mêmes heures,
toujours à l'achat).

## Étape 2 — Rejeu avec le juge honnête (sur l'or, données `Test_IA\data`, variables de Run A)
Pour chaque champion trouvé (dossiers `champion_<STYLE>` actuels ; et, s'il existe, le champion qui tradait vraiment
en démo à la date des trades, retrouvé dans les archives) :
1. Vérifier ce qu'il a VU : dates d'entraînement / validation / jeu sous clé (config + meta.json + code de découpage).
2. Le faire décider bougie par bougie avec le code de Run A importé depuis une COPIE (rien n'est modifié dans `runs\`).
3. Comptabilité honnête de chaque trade : frais réels FTMO sur l'or (écart + commission si applicable, et frais de
   nuit), d'après `collapsar\mains` / `collapsar\juge` et l'audit de l'écart (0,47 $). Taille = risque fixe par trade
   égal au risque utilisé en démo (retrouvé à l'étape 1 ; à défaut 0,25 % et 1 %, les deux affichés).
4. **Jumeau** : ≥ 200 tirages, même nombre de trades, mêmes heures d'entrée et mêmes durées, même stop, sens tiré au
   hasard. Force = (gain réel − moyenne des jumeaux) / écart des jumeaux.
5. **Or retourné** : prix miroir k/prix (les bougies retournées : haut ↔ bas), même champion, mêmes réglages.
6. Périodes : principale = **01/2024 → 09/2025** (signaler si ces mois ont servi à le choisir, ex. jeu sous clé
   depuis 05/2023) ; ancienne jamais apprise = avant le début de ses données d'entraînement, si elle existe.
7. Sortie : % par mois sur 100 000 $, trades par mois, baisse maximale, chance de réussir le challenge FTMO
   (+10 % avant −5 % sur un jour ou −10 % au total ; tirages de départs glissants sur la période).

## Étape 3 — La hiérarchie
Retrouver comment les styles étaient combinés en démo (`demo_trader.py`, config de l'époque : priorité de la grande
unité ? budget de risque partagé ?) et rejouer la combinaison avec le même juge, si faisable.

## Critères (fixés maintenant)
- 🟢 **prouvé** : force ≥ 3 ET gain positif sur l'or retourné ET sur une période qu'il n'a pas vue (ni apprise,
  ni utilisée pour le choisir), frais FTMO compris.
- 🟡 **prometteur** : gain net positif après frais sur la période principale ET force ≥ 2, mais il manque une des
  conditions du vert (or retourné négatif, ou période déjà vue).
- ⚪ **bruit** : tout le reste (force < 2, ou perdant après frais, ou trop peu de trades : < 30 trades sur la période).
- Faits démo : un style est « significatif » seulement si |gain moyen| / (écart / racine(n)) ≥ 2 ET n ≥ 30.

## Ce qui sera dit clairement
Ce qui n'a pas pu être fait et pourquoi (champion introuvable, données manquantes, terminal MT5 fermé, etc.).

---
## Notes datées (écarts au plan)
