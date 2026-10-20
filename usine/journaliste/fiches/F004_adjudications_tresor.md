# F004 — Les adjudications du Trésor américain poussent les taux avant, puis les relâchent

Fournée 1 (20/10/2026) — journaliste. Statut : proposée. Risque de déjà-vu : **faible** (événement jamais utilisé) ;
risque de **transmission** élevé (l'effet publié porte sur les obligations, pas sur nos marchés).
Marchés FTMO : **USDJPY** (principal), **XAUUSD** (secondaire). Obligation US : `core/ftmo/fiches.py` connaît
« USBOND » mais il est **absent** de `core/ftmo/conditions_ftmo.json` (relevé du compte d'essai FTMO) -> non tradable
confirmé, donc pas visé.

## 1. Hypothèse
Les jours avant une adjudication d'obligations du Trésor à 10 et 30 ans, les taux américains montent (le prix des
obligations baisse) jusqu'au jour de l'adjudication puis redescendent dans les 2-3 jours après. Le dollar-yen, très
sensible aux taux américains, suit : il monte de J-5 à J et rebaisse de J à J+3 ; l'or fait l'inverse.
Signal principal (un seul) : achat USDJPY à la clôture de J-5, sortie à la clôture de J ; puis vente de J à J+3.
J = jour d'adjudication des titres à 10 et 30 ans (~24-36 par an).

## 2. Mécanisme
- Lou, Yan et Zhang (Review of Financial Studies, 2013) : avant une adjudication, les intermédiaires (banques
  « primaires » obligées d'acheter) font de la place dans leur bilan en vendant les titres semblables ; les acheteurs
  finaux arrivent lentement. Le prix baisse jusqu'au jour J puis remonte.
- Pourquoi pas arbitré : capacité de risque limitée des intermédiaires, capital lent des acheteurs finaux — effet
  connu et répété malgré la date publique.
- Transmission au dollar-yen : l'écart de taux États-Unis / Japon est le premier moteur du dollar-yen à court terme ;
  une hausse passagère des taux US doit le pousser. **Rien n'a été publié sur cette transmission** : c'est le maillon
  le plus faible.

## 3. Donnée
| point | détail |
|---|---|
| source | Trésor américain, jeu de données « Treasury Securities Auctions Data » : https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/ (CSV, JSON ou interface publique `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/`) — **page vérifiée le 20/10/2026** |
| historique | depuis le **15/11/1979** ; 114 champs (dont date d'adjudication, type et durée du titre ; présence des champs « date d'annonce », « taux obtenu », « couverture de la demande » à confirmer dans le dictionnaire des données) |
| **date de publication** | la DATE d'adjudication est connue d'avance (calendrier trimestriel provisoire, annonce de l'offre ~1 semaine avant) -> **aucune fuite** pour le signal principal, qui n'utilise que la date. Résultats publiés le jour J à 13h00 New York (variante « demande faible » seulement, non retenue ici). |
| gratuit et légal | oui (données publiques du gouvernement américain) |
| présent dans `data/` | **NON** (aucune trace). **À télécharger** (un seul fichier, quelques Mo). Pour la vérification du mécanisme : taux à 10 ans FRED **DGS10** (non présent non plus, gratuit). |

## 4. Pourquoi ce n'est pas déjà au registre
- Aucune ligne sur les adjudications. Proches : **I038** (surprise des annonces économiques -> dérive du lendemain),
  **I056** (12 effets de calendrier : tournant du mois, veille de férié, Fed…), **I025** (portage sur devises).
- Différence précise : l'événement est une **offre de dette** dont la date est connue des mois à l'avance (pas une
  surprise, pas un jour du mois), et le mécanisme est la capacité des intermédiaires (pas l'humeur ni le calendrier).

## 5. Ce qui la réfuterait — ordre de grandeur — frais
- **Réfutation 0 (bon marché, à faire d'abord)** : le motif n'existe plus dans le taux à 10 ans lui-même sur 2010-2023
  (FRED DGS10 : pas de hausse moyenne de J-5 à J ni de baisse de J à J+3, force < 2) -> morte sans aller plus loin.
- **Réfutation 1** : le motif existe dans les taux mais pas dans le dollar-yen (force < 2 sur 2010-2019) -> morte.
- **Réfutation 2** : le jumeau (mêmes jours, sens tiré au hasard) fait aussi bien sur 2020-2023 -> morte.
- Ordre de grandeur publié : Lou-Yan-Zhang : coût caché pour le Trésor de **9 à 18 points de base de la taille de
  l'adjudication** (sur le prix des titres, période 1980-2008 environ). Effet sur le dollar-yen : inconnu, sans doute
  bien plus petit.
- Frais FTMO : dollar-yen ~0,006-0,01 % aller-retour + nuits ~2 %/an x 3-5/365 ≈ 0,02-0,03 % -> **~0,03-0,04 % par
  trade**. Le dollar-yen bouge de ~1,2 % en 5 jours : il faut un avantage moyen > 0,04 %. Très bon marché, mais
  ~24-36 événements par an seulement : beaucoup d'années nécessaires pour une force de 2.
