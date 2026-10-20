# Critères de passage en réel

Ce document liste les critères objectifs à valider avant d'envisager un compte
financé réel (prop firm) ou un compte personnel réel. Il sert de référence
pour l'avenir — tant qu'on n'est pas explicitement en train de les évaluer,
rien ici n'a d'effet sur le système, qui reste en démo.

Valeurs proposées par défaut, à ajuster.

## 1. Durée de fonctionnement continu

- **≥ 60 jours consécutifs** de fonctionnement (entraînement + trading démo),
  avec un journal des incidents (redémarrages, plantages, garde-fous
  déclenchés) — pas nécessairement zéro incident, mais chaque incident
  **compris et documenté**, pas juste "c'est reparti tout seul".
- Aucun incident classé "grave" (perte de données, comportement erratique
  non expliqué, garde-fou contourné) dans les 14 derniers jours de la
  période évaluée.

## 2. Stabilité du score walk-forward

- Sharpe walk-forward **≥ 1.0 maintenu**, pas juste atteint une fois — mesuré
  sur au moins **4 semaines consécutives**, sans dégradation soutenue
  (un recul ponctuel d'un cycle n'invalide pas le critère, une tendance à la
  baisse sur plusieurs semaines si).
- Drawdown backtest walk-forward **≤ 20%** (seuil déjà en place,
  `validation.max_drawdown_allowed`) sur la même période.
- Au moins **2 styles distincts** (pas un seul) doivent individuellement
  passer ces seuils — un seul style qui passe reste un signal fragile.

## 3. Absence de perte isolée excessive

- **Aucune position clôturée avec une perte réelle dépassant le risque
  ciblé** (`max_risk_pct_per_trade`, actuellement 2%) sur la période
  évaluée — le garde-fou lot/stop est censé le garantir structurellement ;
  ce critère vérifie qu'il n'y a eu AUCUNE violation constatée en
  conditions réelles, pas seulement en test.
- Référence concrète : l'incident du 16/09 (-1748$ sur un compte à 100k$,
  soit ~1.75%, causé par un stop mal calibré à l'échelle du style D1) ne
  doit plus pouvoir se reproduire — ce critère est directement né de cet
  incident.

## 4. Volume de trades suffisant pour `reliability_tracker.py`

- **≥ 100 trades réels enregistrés** en mémoire épisodique (`source="live"`)
  — le seuil déjà codé (`reliability.min_trades_for_confidence`). Au moment
  de la rédaction de ce document : **~20 trades**, très loin du seuil.
- Le verdict de `reliability_tracker.py` doit être **"Cohérent"** (pas
  "ÉCART SIGNIFICATIF") au moment de l'évaluation — le backtest doit
  refléter fidèlement ce qui se passe réellement, pas juste sur le papier.

## 5. Discipline des garde-fous

- Le coupe-circuit de compte (`account_guard.py`, total et quotidien une
  fois activé) ne doit s'être déclenché, sur la période évaluée, que dans
  des circonstances **comprises et attendues** (jamais un mystère non
  élucidé qui reste sans explication).
- Zéro contournement ou désactivation temporaire d'un garde-fou pour
  "débloquer" une situation sans en comprendre la cause racine.

## 6. Fréquence de trading raisonnable

- Le taux de retournement de position (churn) doit être mesurablement
  **sous contrôle** — pas de retour au pattern documenté le 17/09 (0% de
  stops touchés, retournements en 5 minutes). Mesure concrète : durée de
  détention médiane des positions cohérente avec l'échelle de temps du
  style concerné (une position D1 qui dure typiquement moins d'une heure
  est un signal d'alerte, pas un détail).

## 7. Aucun problème connu non résolu ou non explicitement accepté

- Se référer à la cartographie du 18/09 (état du dépôt) : tout ce qui y est
  classé **PROBLÈME CONNU** doit être soit corrigé, soit explicitement
  documenté comme "accepté en connaissance de cause" avant le passage en
  réel — pas simplement oublié.

## Ce que ce document N'EST PAS

Une checklist automatisée. Chaque critère ici demande un jugement humain au
moment de l'évaluation, pas un script qui répond "GO/NO-GO". L'objectif est
d'avoir une référence écrite pour ne pas décider "sur le vif" un jour où le
compte a l'air de bien se comporter.
