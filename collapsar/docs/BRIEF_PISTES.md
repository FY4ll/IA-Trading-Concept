# Brief commun des chercheurs-testeurs (16/10/2026)

Ordre du chef de projet : « trouve-moi quelque chose qui peut marcher, quitte à être complètement hors sujet de la DA
COLLAPSAR ». Donc : n'importe quelle stratégie (règles, portefeuille, statistiques, apprentissage), à condition
qu'elle soit tradable sur un compte FTMO (CFD MetaTrader 5) et qu'elle gagne APRÈS frais réels sur des années jamais
utilisées pour la régler. But : réussir le challenge FTMO 100 000 $ (+10 % puis +5 %, mort à -5 % sur un jour ou
-10 % au total ; compte Swing = positions gardées la nuit et le week-end permises), puis durer en compte financé.

## Environnement (Windows, PowerShell, depuis C:\Users\utilisateur\Documents\Test_IA)
- Python : `venv_gpu\Scripts\python.exe` ; mettre `$env:CUDA_VISIBLE_DEVICES='-1'` (pas de carte graphique).
- **Mémoire : 16 Go pour toute la machine, ~4-5 Go libres, 5 chercheurs en parallèle.** Rester sous ~1,5 Go : bougies
  de 15 minutes ou journalières (les fabriquer à partir des 15 min et les garder en cache .parquet / .npz dans ton
  dossier), jamais toutes les minutes de tous les marchés à la fois. Libérer la mémoire entre marchés.
- **Ne touche à AUCUN processus en cours** (école, contrôleur, démo, collecteurs) ni à aucun fichier existant du
  projet : crée seulement tes fichiers dans `collapsar/regarder/pistes/<ta_piste>.py` (ajoute un `__init__.py` vide s'il
  manque) et tes résultats dans `collapsar/vie/pistes/<ta_piste>/`. Pas de pip install dans le venv.

## Données
- `from collapsar.donnees import marches as dm` ; `dm.liste_marches()` = 47 marchés FTMO (devises, indices
  DEUIDXEUR, USA500IDXUSD, USATECHIDXUSD, USA30IDXUSD, JPNIDXJPY, GBRIDXGBP, FRAIDXEUR, EUSIDXEUR, AUSIDXAUD, or
  XAUUSD, argent XAGUSD, pétroles LIGHTCMDUSD / BRENTCMDUSD, gaz, obligation US USTBONDTRUSD, cryptos) ;
  `dm.charger(sym, pd.Timestamp("2100-01-01"))` -> bougies de 15 min (time, open, high, low, close, volume), heure du
  serveur MetaTrader (= New York + 7 h), de 2010 (certains marchés commencent plus tard) à 10/2026.
- Minutes : `collapsar.regarder.orb.minutes("US500"|"NAS100"|"XAUUSD")` (colonne `ny` = heure de New York),
  `collapsar.regarder.orb.seances(df)` -> séances 9h30-16h. EURUSD minute : `collapsar.donnees.histdata.charger("EURUSD")`.
- Taux d'intérêt mensuels de 8 devises : `collapsar/donnees/taux.py`. Calendrier économique (heures justes)
  `collapsar.donnees.calendrier.charger_mt5()` (depuis 2017 pour les prévisions).

## Frais (obligatoires)
- Aller-retour (écart + commission) : `from collapsar.mains.fiches import fiche` ; `fiche(sym).frais` = part du
  montant par trade complet (0,006 % grandes devises, 0,012 % or / indices…). Ajouter un glissement prudent (x 1,25).
- Nuit : `from collapsar.mains.nuit import taux_nuit` ; `taux_nuit(fiche(sym), temps)` -> (taux annuel achat, taux
  annuel vente) payés par nuit / 360 (mercredi x 3 pour les devises : prends-le en compte simplement, ou x 7/5).

## Juge honnête (obligatoire, sinon le résultat ne compte pas)
1. Écrire les règles et la LISTE FERMÉE de variantes (peu : <= 12) dans l'en-tête du fichier AVANT de regarder un
   résultat.
2. Choisir la variante sur **2010-2021** (ou 2015-2021 si données plus courtes), vérifier sur **2022-2023**.
3. **2024-01 -> 2026-10 = période cachée** : l'ouvrir UNE seule fois, seulement pour la variante retenue et si elle est
   positive après frais en 2022-2023 ; verrou `collapsar/vie/pistes/<ta_piste>/cachee.json` (si le fichier existe,
   ne jamais recalculer). Les réglages publiés dans la littérature peuvent être pris tels quels (aucun choix).
4. Comparer à un **jumeau** : mêmes moments, même taille, sens tiré à pile ou face (force = moyenne de (R - R_inverse)/2
   / écart type x racine(n) ; seuil de preuve max(3, racine(2 ln variantes))).
5. Gains journaliers du compte (taille réglée sur l'agitation, risque par trade raisonnable) -> challenge FTMO
   simulé : `from collapsar.regarder.bande_bruit import challenge` ; `challenge(serie_gains_journaliers_en_part_du_compte)`
   (départ tous les 10 jours) -> % réussis / morts / inachevés ; idem pour 20 jumeaux.
6. Pièges connus du projet : un regard manquant en fin de séance a déjà fait disparaître les gagnants ; heures des
   données (serveur = New York + 7 h) ; tout ce qui sert à décider doit être connu AVANT l'entrée ; un résultat
   « trop beau » = chercher le défaut avant d'y croire.

## Ce qui est déjà mesuré (ne pas refaire tel quel)
Tendance de fond multi-marchés ~+0,5 %/mois 2018-2025 (baisse max ~19 %) ; cassure d'ouverture de New York : morte
après frais ; zones offre/demande (SMC, indicateur du chef) : rien après frais ; bande de bruit intraday
(Zarattini 2024) : avantage avant frais 2015-2023 mais -0,26 %/mois en 2024-2026 ; annonces économiques (dérive
1 jour) : morte ; IA qui devine le sens à 15 min - 1 semaine : ~51 %, rien après frais.

## À rendre
`collapsar/vie/pistes/<ta_piste>/rapport.md` en français simple (pas de jargon anglais) : règles, variantes, tableau
par période (trades, gain %/mois après frais, baisse max, pire jour, force contre le jumeau, challenges réussis /
morts contre jumeaux), verdict honnête, et ce qui manquerait pour aller plus loin. Résumé de 10 lignes en réponse.
