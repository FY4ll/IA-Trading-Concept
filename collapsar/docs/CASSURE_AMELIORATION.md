# Amélioration de la cassure crypto + COLLAPSAR aux commandes (16/10/2026) — FIGÉ AVANT TOUT RÉSULTAT

Ordre du chef de projet : « améliorer un maximum, et COLLAPSAR doit en être capable ».
Base : C2 (regarder/pistes/bitcoin_journee.py, en démo Tradeco : direct/bitcoin_cassure.py).

## Le juge (rien ne se choisit sur ce qui sert à juger)
- Les années 2017-2026 du BTC / ETH (Dukascopy) sont DÉJÀ VUES : elles servent au développement seulement.
- Terrain NEUF : bougies de 15 min Binance (data/binance/, ~22 autres cryptos, week-ends compris), coupé en deux
  groupes FIXES par ordre alphabétique des symboles disponibles : groupe A (1 sur 2, en commençant par le 1er) =
  développement ; groupe B (les autres) = CONFIRMATION, ouverte UNE seule fois pour la version finale (verrou
  collapsar/vie/cassure_v3/confirmation.json). Frais des cryptos hors FTMO : 0,05 % par aller-retour ; BTC 0,03 % ;
  ETH frais_ftmo.
- Une amélioration n'est gardée que si elle améliore la note SUR LE DÉVELOPPEMENT (BTC + ETH + groupe A) ET n'y
  dégrade aucune des deux moitiés de temps (2017-2021, 2022-2026). Note = gain moyen par jour / agitation des gains
  (rapport gain/risque), plus % de challenges FTMO réussis - morts (compte BTC + ETH, frais FTMO).
- Le compte FTMO réel ne contient que BTC et ETH (seules cryptos à frais raisonnables chez FTMO) ; les autres cryptos
  servent à JUGER l'idée, pas à trader.

## Liste fermée des améliorations (testées dans cet ordre, chacune gardée ou rejetée)
1. ENSEMBLE de canaux N = 12, 18, 24, 30, 36, 48 h : position = moyenne des 6 avis (chacun avec son propre état
   entrée / sortie) ; taille identique au total. (Justifié par le plateau mesuré le 16/10 : toutes les N gagnent.)
2. WEEK-END : trader aussi samedi et dimanche (FTMO cote la crypto 7 j / 7) — jugé sur Binance seulement (Dukascopy
   presque vide le week-end).
3. SORTIE : milieu du canal (actuel) contre canal opposé de N/2 heures (sortie de Donchian classique).
4. TAILLE : agitation journalière 14 j (actuel) contre agitation des 24 dernières heures (bougies de 15 min).
5. ARRÊT DE LA JOURNÉE : -3 % (actuel) contre -2 % contre aucun.
6. COMPTE BTC + ETH : budget d'agitation partagé (cible / racine(2) x 1,25) contre BTC seul.
7. COLLAPSAR AUX COMMANDES (« second avis » appris) : pour chaque signal, un petit modèle appris (arbres boostés peu
   profonds, puis le petit réseau de COLLAPSAR) décide la TAILLE (0 à 1,5 x) à partir de faits connus à l'entrée :
   largeur du canal / agitation, heure, jour, tendance 1 j / 5 j / 20 j, accord BTC-ETH, volume relatif (Binance),
   résultat récent de la stratégie, distance aux murs FTMO. Appris sur le développement (années 2017-2021), contrôlé
   sur 2022-2026 du développement, puis confirmation.
8. RÉGLAGE DU RISQUE POUR LE CHALLENGE : cible d'agitation 0,75 / 1 / 1,25 / 1,5 % et réduction près du mur des -10 %
   (distance au mur) — choisi sur le développement.

## Après la confirmation
Version finale figée -> mise à jour de la démo Tradeco (même numéro magique), carnet téléphone, revue chaque semaine.
