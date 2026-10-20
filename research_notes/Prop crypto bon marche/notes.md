# Où trader la stratégie crypto 24 h à bas coût (recherche du 16/10/2026)

Contexte : positions de ~24 h sur BTC, ETH et grandes cryptos ; +2,5 à +3,7 %/mois AVANT frais.
Chez FTMO, commission 0,0325 %/côté + écart + frais de nuit ~30 %/an mangent presque tout.

## 1. Mesure faite ici : vrai coût de financement des perpétuels Binance (API publique, 16/10/2026)
Taux de financement (payé par l'acheteur quand positif, reçu par le vendeur) :

| Marché | 12 derniers mois (16/10/2025 -> 16/10/2026) | Moyenne 3 ans (10/2023 -> 10/2026) |
|---|---|---|
| BTCUSDT | +3,26 %/an (moy. +0,0030 % par 8 h) ≈ 0,009 %/jour | +7,45 %/an ≈ 0,020 %/jour |
| ETHUSDT | +2,48 %/an | +7,6 %/an |
| SOLUSDT | — | +5,55 %/an |

Écart affiché sur le perpétuel BTC Binance au moment du relevé : 0,10 $ pour 82 130 $ (≈ 0,0001 %, négligeable).
=> Le financement réel d'une Bourse coûte ~3 à 8 %/an à l'acheteur, contre ~30 %/an de frais de nuit chez FTMO,
et un vendeur en reçoit la plupart du temps.

## 2. Les sociétés de financement crypto

### HyroTrader (Slovaquie, fondée 2022-2023) — liée à Bybit (et BloFin, plateforme maison CLEO)
- Frais : ceux de Bybit, niveau de base : faiseur 0,0200 %, preneur 0,0550 % (page officielle).
  https://www.hyrotrader.com/faq/bybit-platform/-what-are-bybits-fees/
- Financement : celui du marché Bybit (pas de frais de nuit maison selon les revues ; HyroTrader ne détaille pas).
- ATTENTION : la FAQ officielle (lue le 16/10/2026) dit : « All trading on HyroTrader takes place on simulated (demo)
  accounts that run on real exchange market data. There is no real-capital stage at any point. »
  Les anciens articles de blog parlaient d'ordres réels dans le carnet Bybit : ce n'est plus le cas.
  https://www.hyrotrader.com/
- Programmes automatiques : AUTORISÉS par API (robots maison ou tiers) ; interdits : copie de signaux, haute fréquence,
  exploitation de failles. https://www.hyrotrader.com/faq/hyrotrader-account/can-i-use-trading-bots-or-signal-bots-during-the-challenge-or-on-a-funded-account/
- Règles (site officiel 16/10/2026) : 1 étape = +10 %, perte du jour 4 %, perte max 6 %, 5 jours min ;
  2 étapes = +10 % puis +5 %, perte du jour 5 %, perte max 10 %, 5+5 jours. Durée illimitée.
  Perte du jour « suiveuse » : mesurée depuis le plus haut du jour, gains latents compris, remise à zéro 00h UTC.
  Perte réalisée max par trade : 3 % du capital de départ (stop non obligatoire, contrôle manuel).
  Règle de répartition : pendant l'examen, aucun jour ne doit faire plus de 40 % de l'objectif.
  Altcoins de faible capitalisation : 5 % du capital max.
  https://www.hyrotrader.com/faq/rules/what-are-the-risk-management-conditions-at-hyrotrader/
  https://www.hyrotrader.com/faq/rules/d/
- Levier jusqu'à 150x BTC/ETH ; 700+ paires Bybit.
- Partage 80 % -> 90 % ; paiement sous 24 h en USDT/USDC ; prix remboursé au 1er paiement ;
  retrait plafonné à 5 % du compte par retrait (selon cryptoslate/Kraken learn).
- Prix 100 000 $ (comparatif publié par HyroTrader, 03/07/2026) : 2 étapes 579 $, 1 étape 749 $, 0 étape 949 $.
  https://www.hyrotrader.com/blog/hyrotrader-vs-kraken-prop/
- Réputation : Trustpilot ~4,1-4,4/5 (~190-250 avis, 04/2026). Mars 2026 : plaintes (perte max abaissée de 10 % à 6 %
  sans prévenir, refus de paiement pour « modèle de risque », bannissements Discord). Pas de régulation (entités EAU/BVI,
  paiements via Slovaquie). https://www.propscorer.com/de/blog/hyrotrader-controversy-full-story
  https://cryptoslate.com/prop-firms/hyrotrader-review/

### Kraken Prop (ex-Breakout, racheté par Kraken 09/2025, lancé dans Kraken Pro le 27/05/2026)
- Frais : 0,04 % par côté sur la crypto + « financement de marge » 0,033 %/jour (prélevé par tranches de 4 h)
  ≈ 12 %/an. https://proprubric.com/firms/kraken-prop/ ; https://support.kraken.com/articles/kraken-prop-lite
- Levier 5x BTC/ETH, 2x autres ; 60+ paires.
- Règles : perte du jour 3 % (calculée à 00h30 UTC sur le solde hors positions ouvertes), perte max FIXE
  3 % (Advanced, objectif 9 %), 5 % (Intermediate, 12 %), 6 % (Starter, 10 %). Pas de règle de cohérence,
  pas de minimum de jours, pas de limite de temps. https://www.kraken.com/prop
- Programmes automatiques : selon proprubric, « no API access; all orders placed manually » -> À CONFIRMER
  PAR ÉCRIT auprès de Kraken (pas trouvé de page officielle). Sans API, inutilisable pour l'IA.
- Capital : 5 000 à 200 000 $ max (cumul). Partage 80 % (90 % avec option +20 % du prix). Paiement à la demande,
  < 24 h, minimum 50 $.
- Prix 100 000 $ : 330 $ (Advanced), 545 $ (Intermediate), 800 $ (Starter), NON remboursables.
- Compte simulé ; le contrat autorise un routage « A-Book et B-Book » au choix de la société.
- Sérieux : adossé à Kraken (grande Bourse régulée), 35 000+ comptes financés depuis 2023 (site Kraken).

### Crypto Fund Trader (fondée 2022, affiche Suisse/Espagne ; partenaire Bybit depuis 04/2025)
- Frais : ceux du compte Bybit, sans majoration ; financement : taux du marché Bybit, pas de frais de nuit maison.
  Seuls les contrats USDT sont permis ; 715+ paires. (thegodfunded / fxempire, communiqué 04/2025)
  https://www.fxempire.com/press-release/article/crypto-fund-trader-x-bybit-redefining-the-future-of-crypto-prop-trading-1510782
- Règles 100 000 $ : 1 phase +10 %, perte du jour 4 %, max 6 % (619 $) ; 2 phases +8 %/+5 %, 5 %/10 % (660 $).
- Robots/API autorisés (mais connexion API à ne pas modifier, stop dans les 5 min selon une revue ; pas de haute
  fréquence ni arbitrage). Partage 50-90 % progressif ; paiement tous les 15 jours tradés ou 30 jours.
- Sérieux : MAUVAIS signaux. Trustpilot a suspendu sa note (08/2026, infraction aux règles de Trustpilot) ;
  propfirmmap la classe « risque élevé » (note D) ; inscrite à la liste d'avertissement de la FINMA depuis 08/2024
  (selon fundedtrading, non revérifié sur le site FINMA) ; plaintes de refus de paiement (« même adresse IP »).
  https://propfirmmap.com/trust-check/cryptofundtrader

### Bitfunded (Tronovix LTD, Émirats, fondée 12/2023) — plateforme maison
- Commission 0,04 % par trade, écart nul affiché ; financement/frais de nuit non publiés.
- Levier 5x ; 100+ paires ; 2 étapes : +8 %/+5 %, perte du jour 5 %, max 8 % ; 1 étape 4 %/6 % ; 5 jours min.
- Robots autorisés (avec restrictions). Partage 80 -> 90 %. Paiement quotidien après 14 jours.
- Prix 100 000 $ 2 étapes : 799 $. Trustpilot 4,5-4,6 (~180 avis) ; plaintes : lenteurs en forte volatilité,
  règle « anti-jeu » appliquée après coup pour réduire des paiements.
  https://thetrustedprop.com/prop-firms/bitfunded

### FundedNext / Funded Trading Plus (crypto en CFD sur MT5, comme FTMO)
- FundedNext : crypto levier 1:1, frais de nuit (triple le vendredi), stop obligatoire, robots seulement sur MT4/MT5,
  100 000 $ = 549,99 $. Même modèle de coûts que FTMO -> pas de gain sur les frais.
  https://www.hyrotrader.com/blog/fundednext-review/
- Funded Trading Plus : CFD MT5/cTrader/DXTrade, aucun détail de coûts crypto publié trouvé.

## 3. Bourses en direct et CME
- Binance contrats USDT : faiseur 0,0200 %, preneur 0,0500 % (‑10 % si paiement en BNB : 0,018 / 0,045 %).
  https://www.binance.com/fr/support/articles/360033544231
- Bybit : faiseur 0,0200 %, preneur 0,0550 % (niveau de base).
- ATTENTION pays : en France, l'accès des particuliers aux perpétuels crypto est en pratique bloqué par Binance/Bybit
  (AMF : interdiction des CFD aux particuliers ; Bybit EU agréée MiCA mais sans perpétuels pour la France).
  À vérifier selon le pays de résidence réel (Suisse ≠ France).
  https://www.amf-france.org/en/news-publications/news-releases/amf-news-releases/amf-reminds-public-cryptoasset-trading-platform-bybit-blacklisted
- CME micro bitcoin (MBT) : 0,1 BTC (~8 200 $ à 82 000 $), pas de 5 points = 0,50 $ ; frais de Bourse non-membre
  2,50 $/côté + courtier (~0,25 à 2,50 $/côté) ; le coût de portage est dans le prix (prime sur le comptant, ~5-10 %/an).
  CME a annoncé la cotation 24 h/24, 7 j/7 des contrats crypto à partir du 29/05/2026.
  https://www.cmegroup.com/education/lessons/micro-bitcoin-futures-product-overview.html
  https://www.theblock.co/post/373240/cme-make-crypto-futures-always-on-24-7-trading-2026
  Petit capital : un MBT = ~8 200 $ d'exposition, marge ~ quelques milliers de $ : faisable avec 10-20 k$.

## 4. Coût d'un aller-retour de 24 h sur BTC (en % de la position)
Financement = moyenne BTC Binance 12 mois (0,009 %/jour) ; « 3 ans » = 0,020 %/jour.

| Où | Entrée+sortie | Écart | Nuit / financement 24 h | Total 24 h | Si toujours investi 1x (30 allers-retours/mois) |
|---|---|---|---|---|---|
| FTMO (CFD) | 0,065 % | ~0,01-0,03 % (estimé, non publié) | ~0,08 % (30 %/an) | ~0,16-0,18 % | ~5 %/mois |
| Kraken Prop | 0,08 % | faible | 0,033 % | ~0,11 % | ~3,4 %/mois |
| HyroTrader / CFT (Bybit) preneur | 0,11 % | ~0 | 0,009-0,020 % | ~0,12-0,13 % | ~3,7 %/mois |
| HyroTrader / CFT (Bybit) faiseur | 0,04 % | 0 (gagné) | 0,009-0,020 % | ~0,05-0,06 % | ~1,6 %/mois |
| Bitfunded | 0,08 % | 0 affiché | non publié | ≥ 0,08 % | ≥ 2,4 %/mois |
| Binance direct preneur (BNB) | 0,09 % | ~0 | 0,009-0,020 % | ~0,10-0,11 % | ~3,1 %/mois |
| Binance direct faiseur (BNB) | 0,036 % | 0 | 0,009-0,020 % | ~0,045-0,056 % | ~1,5 %/mois |
| CME micro bitcoin | ~0,07-0,12 % | ~0,006 % | portage ~0,015-0,03 % | ~0,09-0,15 % | ~3-4,5 %/mois |

Un vendeur REÇOIT le financement sur Bourse (en moyenne) au lieu de le payer : avantage supplémentaire pour les ventes.
Lecture : seule l'exécution en FAISEUR (ordre limite posé dans le carnet) divise les frais par ~3 par rapport à FTMO.
En preneur, toutes les solutions coûtent 0,10-0,13 %/jour : la stratégie resterait très rognée.

## 5. Classement
1. HyroTrader (2 étapes 100 k$ = 579 $, remboursé au 1er paiement) : frais Bybit réels, ordres limites faiseur
   possibles, API/robots autorisés, financement réel. Pièges : perte du jour SUIVEUSE depuis le plus haut du jour
   (gains latents compris), règle des 40 % par jour pendant l'examen, 3 % max de perte par trade, retrait plafonné
   à 5 % du compte, comptes 100 % simulés, réputation moyenne (changement de règles 03/2026).
2. Bourse en direct (Binance/Bybit faiseur) si le pays le permet : coût ~0,05 %/jour, aucune règle piège, mais
   l'argent risqué est le sien. Sinon CME micro bitcoin via un courtier : légal partout, mais ~0,1 %/jour -> à peine
   mieux que Kraken Prop.
3. Kraken Prop : société la plus sûre (Kraken), mais 0,04 %/côté + 12 %/an de marge, perte max 3-6 %, et
   apparemment PAS d'API (à confirmer) -> inutilisable pour une IA tant que non confirmé.
4. À éviter : Crypto Fund Trader (note Trustpilot suspendue, avertissement FINMA signalé, refus de paiement),
   Bitfunded (plateforme maison, coûts de financement non publiés), FundedNext/FTP (CFD comme FTMO).
Règle FTMO-like commune : vérifier par écrit, avant de payer, que l'IA maison est acceptée (HyroTrader : oui par écrit
dans la FAQ ; Kraken : à demander).
