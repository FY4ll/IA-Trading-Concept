# F005 — La semaine d'échéance mensuelle des options sur indices

Fournée 1 (20/10/2026) — journaliste. Statut : proposée. Risque de déjà-vu : **moyen** (famille « calendrier » I056
morte, mais cet événement n'y figurait pas ; il est noté comme « jamais chiffré » dans
`research_notes/Vivre de son IA de trading/comportement_flux_primes.md`).
Marchés FTMO : **US500, US100, US30**.

## 1. Hypothèse
Les indices américains montent plus pendant la semaine qui finit le 3e vendredi du mois (échéance mensuelle des options
sur indices et sur actions) que pendant les autres semaines.
Signal principal (un seul) : achat US500 / US100 / US30 à l'ouverture au comptant du lundi (9h30 New York) de la semaine
d'échéance, sortie à la clôture du jeudi (pour ne pas ouvrir ni garder près de la fermeture du vendredi). Variante
déclarée d'avance (au choix du scientifique, pas les deux) : échéances trimestrielles seulement (mars, juin, septembre,
décembre).

## 2. Mécanisme
- Stivers et Sun : les teneurs de marché d'options réduisent leurs couvertures vendeuses en actions à mesure que les
  options arrivent à échéance (rachats), et la peur lue dans les options baisse pendant la semaine.
- Pourquoi pas arbitré : ce sont des flux de couverture obligés ; l'effet est petit par rapport au risque d'une semaine
  d'indice, donc peu rentable pour un arbitragiste qui doit porter le risque du marché.
- Changement de fond à surveiller : depuis 2022, les options à échéance du jour même dominent les volumes ; le flux de
  l'échéance mensuelle pèse peut-être moins. La période 2022-2023 le dira.

## 3. Donnée
| point | détail |
|---|---|
| source | **aucune à télécharger** : la date est une règle des marchés d'options (3e vendredi du mois ; jeudi si le vendredi est férié). Calendrier des fériés de la Bourse de New York : déjà dans le code de la piste « peur_options » (`jours_nyse`). |
| historique | illimité (règle) ; nos prix d'indices 15 min : 2013 -> (I056 dit « données d'avant trop trouées ») |
| **date de publication** | connue des années à l'avance -> aucune fuite possible |
| gratuit et légal | oui |
| présent dans `data/` | **OUI** (rien à télécharger). Variante plus riche de Stivers-Sun (effet plus fort quand le volume d'options est élevé) : les volumes CBOE gratuits s'arrêtent au 04/10/2019 (`data/cboe/LISEZMOI.md`) -> **écartée**. |

## 4. Pourquoi ce n'est pas déjà au registre
- **I056** a testé 12 effets de calendrier : tournant du mois (US et monde), « besoin de liquidités » de fin de mois,
  veille de férié, semaines paires de la Fed, veille de Fed, or en Asie, fixing de Londres (2 variantes), rééquilibrage
  du dollar, nuit du S&P 500. **Aucun** ne porte sur l'échéance des options (vérifié dans
  `collapsar/archives/2026-10-16_pistes/vie/pistes/calendrier_horaires/rapport.md`). **I077** utilise le VIX (prix des
  options), pas leur échéance.
- Différence précise : événement distinct (échéance des options), mécanisme distinct (couvertures des teneurs de marché).

## 5. Ce qui la réfuterait — ordre de grandeur — frais
- **Juge** : contre « acheteur permanent à la même exposition » (comme I077), pas seulement contre le jumeau : toute
  semaine acheteuse gagne en moyenne sur des indices en hausse.
- **Réfutation 1** : l'écart « semaine d'échéance moins autres semaines » a une force < 2 sur 2013-2019, ou change de
  signe sur 2020-2023 -> morte.
- **Réfutation 2** : l'effet n'est qu'un morceau du tournant du mois ou de la veille de férié déjà testés (même
  rendement une fois ces jours retirés) -> morte.
- Ordre de grandeur publié : Stivers et Sun (Journal of Banking & Finance, 2013, 37(11) p. 4226-4240 ; version de
  travail 2010) : 28 grandes actions, 1996-2008 : **+0,45 % par semaine d'échéance contre +0,12 % les autres
  semaines** ; S&P 500 1983-2008 : rendements « relativement élevés » en semaine d'échéance, rien d'anormal avant 1983.
  Publié en 2010 : affaiblissement après publication probable.
- Frais FTMO : US500 ~0,016 % aller-retour (relevé x 2, `core/ftmo/frais.py`) + 3 nuits à ~5 %/an ≈ 0,04 % -> **~0,06 %
  par trade**. Si l'écart publié (~0,3 point par semaine) survivait même au tiers, il passerait les frais. 12 trades par
  an : pas d'inactivité FTMO. Règle FTMO « trou de prix » : on n'ouvre pas dans les 2 h avant la fermeture du vendredi
  (sortie le jeudi).
