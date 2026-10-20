# F006 — La « liquidité nette » de la Fed annonce-t-elle les indices et l'or ?

Fournée 1 (20/10/2026) — journaliste. Statut : proposée. Risque de déjà-vu : **faible** (série jamais utilisée) ;
risque de **mode** élevé (idée très diffusée depuis 2022, sans étude sérieuse).
Marchés FTMO : **US500, US100** (principal), **XAUUSD** (secondaire).

## 1. Hypothèse
Quand la liquidité nette de la Fed (bilan total − compte du Trésor à la Fed − prises en pension inversées) augmente sur
4 semaines, les indices américains montent plus que d'habitude pendant les 1 à 4 semaines suivantes ; quand elle baisse,
ils montent moins (ou baissent).
Signal principal (un seul) : variation sur 4 semaines de la liquidité nette, en part de son niveau ; achat si dans le
tiers haut de ses 3 dernières années, rien (ou vente, à fixer d'avance) si dans le tiers bas ; révision chaque jeudi soir.

## 2. Mécanisme
- Plus de réserves bancaires = plus de financement disponible pour les intermédiaires et plus d'argent qui cherche un
  rendement ; le compte du Trésor (impôts, émissions de dette) retire ou rend des réserves de façon en partie prévisible.
- Pourquoi pas arbitré : la donnée est publique, mais l'effet passerait par des flux lents (bilans des banques, gestion
  de trésorerie) plutôt que par une nouvelle que les marchés reprennent tout de suite.
- **Soupçon fort** : l'indicateur a été popularisé en 2022 par des analystes de marché qui l'ont ajusté sur 2020-2022
  (période de création monétaire massive). C'est le cas typique d'une relation trouvée après coup. Le test doit se faire
  d'abord sur 2010-2019, AVANT sa popularisation.

## 3. Donnée
| point | détail |
|---|---|
| source | FRED : **WALCL** (bilan total de la Fed, niveau du mercredi), **WTREGEN** (compte général du Trésor à la Fed, mercredi), **RRPONTSYD** (prises en pension inversées, quotidien) — https://fred.stlouisfed.org/series/WALCL (page vérifiée le 20/10/2026) |
| historique | WALCL : décembre 2002 -> (date exacte de début non affichée sur la page, à relever) ; WTREGEN : même publication ; RRPONTSYD : quotidien, quasi nul avant 2021 (avant 2021 la mesure = bilan − compte du Trésor) |
| **date de publication** | WALCL et WTREGEN : publication H.4.1 **chaque jeudi vers 16h30 New York** pour le niveau du mercredi -> utilisable à l'ouverture **du vendredi**. RRPONTSYD : publié le jour même après l'opération (début d'après-midi New York) -> utilisable le lendemain. Révisions : rares ; premières valeurs disponibles sur ALFRED si besoin. |
| gratuit et légal | oui (FRED, données de la Réserve fédérale) |
| présent dans `data/` | **NON** (aucune trace de ces séries). **À télécharger** : 3 fichiers CSV FRED. |

## 4. Pourquoi ce n'est pas déjà au registre
- Lignes proches : **I008** (FRED : taux, dollar, inflation -> or à 10 jours), **I004** (17 variables hors or dans une
  IA : devises, argent, taux réels, dollar, VIX), **I088** (risque géopolitique, peurs CBOE), **I077** (VIX).
- Différence précise : aucune ne regarde la **quantité de monnaie centrale** (bilan, compte du Trésor, pensions). Autre
  série, autre mécanisme (quantité de liquidité, pas prix de l'argent).

## 5. Ce qui la réfuterait — ordre de grandeur — frais
- **Réfutation 1** : force < 2 sur 2010-2019 (avant la mode) -> morte, quel que soit le résultat sur 2020-2023.
- **Réfutation 2** : l'effet disparaît une fois retirée la tendance passée de l'indice sur 4 semaines -> ce n'est que de
  la tendance -> morte.
- **Réfutation 3** : ne bat pas « acheteur permanent à exposition égale » sur 2020-2023.
- Ordre de grandeur publié : **aucune étude sérieuse trouvée** ; seulement des graphiques d'analystes (TradingView,
  sites de conseil) qui montrent une ressemblance de niveaux, pas un gain hors échantillon.
- Frais FTMO : US500 ~0,016 % aller-retour + nuits ~5 %/an x 7-28/365 ≈ 0,1-0,4 % -> **~0,1-0,4 % par trade**.
  L'indice bouge de ~2,3 % par semaine : il faut un lien de rang de ~0,05-0,1. Révision hebdomadaire : pas
  d'inactivité FTMO si la règle autorise les deux sens.
