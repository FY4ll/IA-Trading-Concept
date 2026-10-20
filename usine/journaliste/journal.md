# Journal du rôle « journaliste »

- 20/10/2026 : rôle créé (définition : .claude/agents/journaliste.md).

## 20/10/2026 — fournée 1 (données hors prix : or, indices US, grandes devises)

**Lu** : `.claude/agents/journaliste.md`, `usine/README.md`, `etudes/REGISTRE_IDEES.csv` (111 idées),
`docs/RESEARCH_HISTORY.md`, `docs/FTMO_REGLES_VERIFIEES.md`, rapports `RA/reports/info_test.md` (I020),
`RA/reports/brain_research.md` (I008), `collapsar/vie/cot_or/rapport.md` (I101), `archive/magnetar/vie/hypernova/monde/rapport.md`
(I088), `collapsar/vie/pistes/peur_options/rapport.md` (I077), `collapsar/archives/2026-10-16_pistes/vie/pistes/calendrier_horaires/rapport.md`
(I056), notes `research_notes/*` (recherche de mots).
Remarque COFFRE : certains rapports lus citent des résultats déjà calculés sur 2024-2025 (I101, I077, I088) ; aucune
DONNÉE postérieure au 31/12/2023 n'a été ouverte. Données locales : seulement les LISEZMOI et les premières lignes
(en-têtes) des fichiers.

**Données locales vérifiées (lecture seule)** : `data/maitres/spdr_gld` (GLD 2004 ->), `data/maitres/fred` (DFII10, T10YIE,
DTWEXBGS, GVZCLS), `data/maitres/cftc_cot` (or/argent désagrégé), `data/cot` (désagrégé matières premières 2006-2023),
`data/foule_devises/cftc_brut` (ancien rapport), `data/taux` (taux directeurs mensuels), `data/monde` (GPR, EPU, OVX, GVZ),
`data/cboe` (VIX & co ; ratios puts/calls arrêtés en 2019), `data/calendrier` (Forex Factory 2007-2025, MT5), `data/macro_events_real.csv`.
Absents : rapport CFTC des contrats financiers (gérants d'actifs / fonds à levier), adjudications du Trésor, bilan de la Fed.

**Sources externes vérifiées (existence seulement, rien téléchargé)** : page CFTC des fichiers historiques (rapport des
contrats financiers 2006-2016 + annuels), fiscaldata.treasury.gov (adjudications depuis 1979, gratuit), FRED WALCL
(H.4.1, jeudi), FRED RRPONTSYD, pages de la Fed (calendrier des réunions), articles : Lou-Yan-Zhang 2013,
Mueller-Tahbaz-Salehi-Vedolin 2017 (chiffre exact non relu), Stivers-Sun 2013, études sur les flux des fonds d'or.

**Fiches écrites** (`fiches/`) :
| fiche | hypothèse | donnée | locale ? | déjà-vu |
|---|---|---|---|---|
| F001 | flux GLD suivis 10 j -> or suit 10 j | avoirs GLD | oui | faible |
| F002 | variation des gérants d'actifs (rapport CFTC contrats financiers) -> devises 2-4 sem. | CFTC | non | moyen |
| F003 | écart de l'or à sa relation taux réel + dollar se referme en 20-60 j | FRED | oui | élevé |
| F004 | adjudications 10/30 ans : dollar-yen monte avant, rebaisse après | fiscaldata | non | faible (transmission douteuse) |
| F005 | indices US plus forts la semaine d'échéance des options | règle de calendrier | oui | moyen |
| F006 | liquidité nette de la Fed (bilan − Trésor − pensions) -> indices | FRED | non | faible (mode 2022) |
| F007 | dollar vendu le jour de décision de la Fed | dates Fed | oui | moyen à élevé |

**Idées écartées et pourquoi** :
- Indice NAAIM (exposition des gérants actifs) : **payant depuis le 01/08/2026**.
- Sondage AAII : historique réservé aux membres (non vérifié) ; famille « foule » déjà large (I044, I073, I074).
- Achats d'or des banques centrales : trimestriels (Conseil mondial de l'or) avec 1-2 mois de retard ; annonce
  mensuelle de la banque de Chine : ~40 annonces avant 2024, presque toutes attendues -> échantillon trop petit.
- Positions COT des banques « swap » sur l'or : même famille que I020/I101, aucune raison nouvelle.
- Veille de Fed / dérive avant la Fed : déjà I056 (et effet disparu d'après les notes).
- Prime / décote de GLD : surtout un décalage d'heure entre la valeur du fonds (Londres) et la clôture de New York,
  donc une information de PRIX, pas hors prix.
- Ratios puts / calls CBOE : fichiers arrêtés en 2019. GDELT : accès bloqué (I088). Stocks des entrepôts COMEX : pas
  d'historique gratuit trouvé. Coffres de Londres (LBMA) : mensuel depuis 2016, trop peu de points.
- Obligation US chez FTMO : absente du relevé `core/ftmo/conditions_ftmo.json` -> F004 vise le dollar-yen, pas l'obligation.
