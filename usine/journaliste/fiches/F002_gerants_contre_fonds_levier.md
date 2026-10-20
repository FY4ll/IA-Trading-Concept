# F002 — Gérants d'actifs contre fonds à effet de levier (rapport CFTC des contrats financiers)

Fournée 1 (20/10/2026) — journaliste. Statut : proposée. Risque de déjà-vu : **moyen** (famille COT déjà testée, mais
pas cette catégorie ni ces marchés).
Marchés FTMO : **EURUSD, USDJPY, GBPUSD, AUDUSD** (priorité) ; **US500, US100** (secondaire, voir piège).

## 1. Hypothèse
Sur les contrats à terme de devises, la variation sur 4 semaines de la position nette des **gérants d'actifs** (caisses
de retraite, assureurs, fonds de placement) annonce le sens de la devise sur les 2 à 4 semaines suivantes, et les
**fonds à effet de levier** (fonds spéculatifs, suiveurs de tendance) ne l'annoncent pas (ou à l'envers).
Signal principal (un seul) : variation 4 semaines de la position nette des gérants d'actifs, en part de l'intérêt ouvert,
classée sur 3 ans ; achat de la devise si dans le tiers haut, vente si dans le tiers bas.

## 2. Mécanisme
- Les gérants d'actifs changent leur couverture de change (part de leurs actifs étrangers couverte) par décisions lentes
  de comité, exécutées sur des semaines : un changement qui commence continue. C'est un flux réel, pas un pari.
- Les fonds à effet de levier, eux, suivent surtout le prix (comme les fonds gérés de l'or dans I101) : ils n'apportent
  pas d'information nouvelle.
- Pourquoi pas arbitré : donnée hebdomadaire avec 3 jours de retard, catégories peu regardées (la plupart des lecteurs
  du COT utilisent l'ancien rapport « spéculateurs / commerciaux »), et le flux de couverture est contraint, pas
  informé.
- **Piège pour les indices** : sur le contrat S&P 500, la grosse position vendeuse des fonds à levier est en bonne partie
  de l'arbitrage (vendeur du contrat, acheteur des actions) et la position acheteuse des gérants d'actifs de la
  réplication d'indice : la position nette n'y est PAS un avis sur le sens. C'est pourquoi les indices ne sont qu'en
  secondaire, et devront être jugés à part.

## 3. Donnée
| point | détail |
|---|---|
| source | CFTC, rapport « Traders in Financial Futures », fichiers historiques : https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm (section « Traders in Financial Futures ; Futures Only ») — **page vérifiée le 20/10/2026** |
| historique | fichier groupé **2006-2016** + un fichier par année jusqu'à 2026 (texte ou Excel) ; catégories : intermédiaires, gérants d'actifs, fonds à effet de levier, autres déclarés |
| **date de publication** | positions du **mardi**, publiées le **vendredi 15h30 New York** (lundi si semaine fériée ; retards lors des fermetures de l'État fin 2013 et 2018-2019) -> utilisable à l'ouverture suivante (dimanche 17h New York pour les devises) |
| gratuit et légal | oui, domaine public (agence fédérale américaine) |
| présent dans `data/` | **NON**. `data/cot/fut_disagg_*.zip` = rapport « désagrégé » des matières premières (or, pétrole…), sans devises ni indices. `data/foule_devises/cftc_brut/deacot*.zip` = ancien rapport (spéculateurs / commerciaux / petits), sans la catégorie « gérants d'actifs ». **À télécharger** (~15 fichiers zip, quelques Mo). |

## 4. Pourquoi ce n'est pas déjà au registre
- **I074** (contre la foule sur devises via CFTC) : utilisait les **petits spéculateurs** (comptes non déclarés) de
  l'ancien rapport, en sens contraire : -0,49 à -2,62 %/mois. **I101** et **I020** : positions COT sur **l'or**, fonds
  gérés et producteurs. **I025** : portage + tendance sur devises.
- Différence précise : autre catégorie (gérants d'actifs, jamais regardée), autre rapport, autre logique (suivre un flux
  de couverture lent, pas jouer contre une foule ni suivre des spéculateurs).

## 5. Ce qui la réfuterait — ordre de grandeur — frais
- **Réfutation 1** : force < 2 sur 2006-2015 pour le panier des 4 devises, ou signe inverse sur 2016-2023 -> morte.
- **Réfutation 2** : l'information disparaît une fois retiré le rendement passé de la devise sur 4 semaines (les gérants
  suivraient eux aussi le prix) -> morte.
- **Réfutation 3** : les fonds à effet de levier font aussi bien que les gérants d'actifs -> le mécanisme « couverture
  lente » est faux, ce n'est que de la tendance déguisée -> morte.
- Ordre de grandeur publié : **aucune étude sérieuse trouvée** sur ces catégories ; les notes de banques centrales citées
  dans la presse disent que les positions suivent surtout le prix. A priori faible : à traiter comme un pari honnête.
- Frais FTMO : grandes paires ~0,006-0,01 % aller-retour (écart + 5 $ par lot) + nuits ~2 %/an x 14-28/365 ≈ 0,08-0,15 %
  -> ~0,1-0,16 % par trade. L'euro bouge d'environ 1,5-2 % en 2-4 semaines : il faut un lien de rang de ~0,06-0,08.
  Signal hebdomadaire sur 4 devises : jamais d'inactivité FTMO.
