# Journal du rôle « travailleur »

- 20/10/2026 : rôle créé (définition : .claude/agents/travailleur.md).

## 20/10/2026 — fournée 1 : données hors prix (F001, F002, F006, F007)

Chargeurs `cerveau/donnees_hors_prix/` (cftc_tff, fed_liquidite, fomc, gld + __init__) : colonne `publie` = instant de
publication à l'heure du serveur (New York + 7 h) ; rien de publié à partir de la limite (défaut 2024-01-01, plus tard
refusé). Fichiers dans `data/hors_prix/<source>/` (hors git). Aucun gain calculé.

| source | couverture (limite 2024-01-01) | publication retenue |
|---|---|---|
| CFTC TFF, 7 devises | 06/2006 -> 26/12/2023, 916 semaines, 6 409 lignes | vendredi 15h30 NY ; +1 jour ouvré par fermeture de l'État mer.-ven. ; 29 semaines par annonce officielle |
| WALCL / WDTGAL (mercredi) | 12/2002 -> 12/2023, 1 098 ; 1re publication ALFRED dès 07/2011 | jeudi 16h30 NY (vendredi si férié), ou date ALFRED si plus tard |
| WTREGEN (moyenne semaine) | 12/2002 -> 12/2023, 1 098 ; 1re publication dès 12/2008 | idem |
| RRPONTSYD (quotidien) | 02/2003 -> 12/2023, 2 651 (vrai début 09/2013) ; 1re publication dès 03/2016 | le jour même 13h15 NY |
| FOMC | 2010 -> 2023 : 111 prévues + 9 exceptionnelles | heure du communiqué (2016+) ; 2010-2015 heure de l'époque vérifiée |
| GLD | 11/2004 -> 12/2023, 4 809 jours | jour de Bourse suivant 10h00 NY |

Vérifications (indépendantes) :
- CFTC : calendriers officiels archivés (web.archive.org, 2010-2023) = notre jour sur 708/735 semaines, les 27 autres
  = retards annoncés après coup (arrêts de l'État 2013, 2018-19, incident ION 2023, fériés exceptionnels) ;
  calendrier MetaTrader 2015-2023 : jamais avant lui, égal à 98 %+ (avant 2015 et en octobre 2013, MetaTrader recopie
  les vendredis prévus : faux).
- Arrêt de l'État 22/12/2018 -> 25/01/2019 : communiqué CFTC 7864-19 (un rapport le mardi et un le vendredi, du
  01/02 au 08/03/2019, positions du 24/12/2018 au 05/03/2019) ; les 11 dates confirmées par MetaTrader. Règle
  prudente proposée au scientifique : garder ces 11 semaines avec leur vraie date (l'info arrive 4-5 semaines en
  retard), ou les EXCLURE comme `collapsar/donnees/cot.py` (choix à figer dans le plan).
- Arrêt d'octobre 2013 : communiqué 6745-13 (archive) : jour exact inconnu pour 4 rapports -> vendredi de la semaine
  annoncée (prudent), `source_publie = annonce_cftc_fin_de_semaine`.
- FOMC 2010-2015 sans heure écrite : 14h15 / 12h30 (conférences 2011-2012) / 14h00 dès le 20/03/2013, confirmé par
  Forex Factory (41 réunions), MetaTrader (14) et le saut de prix euro/yen (48/48) ; 2015-2023 identique à
  `data/macro_events_real.csv`.
- FRED : WTREGEN publié en milliards jusqu'au 12/11/2025 (converti en millions) ; RRPONTSYD du 19/02/2020 publié
  5 149 puis révisé 95 (on garde 5 149, la valeur connue alors) ; WALCL : 92 valeurs sur 651 révisées ensuite, toutes de 0,14 % au plus.

Problèmes : cftc.gov bloque après ~20 pages d'affilée (code 429) -> archives web.archive.org ; avant 2010 aucun
calendrier officiel archivé (règle seule, non vérifiée : 2006-2009) ; WTREGEN est une MOYENNE de semaine (WDTGAL
ajouté, niveau du mercredi comme WALCL).
Tests : `cerveau/tests/test_donnees_hors_prix.py` (14) ; `pytest cerveau/tests core/tests` : 52 réussis, 0 échec.
