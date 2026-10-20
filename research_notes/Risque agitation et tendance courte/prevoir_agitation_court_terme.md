# Prévoir l'agitation des prix à court terme (15 min à quelques jours) — devises, or, indices, pétrole, bitcoin

Notes de recherche du 15/10/2026. Conventions :
- **[VÉRIFIÉ]** = chiffre lu dans le texte de la source (PDF téléchargé et lu, ou page lue).
- **[RÉSUMÉ]** = chiffre lu seulement dans un résumé/une page secondaire, pas dans la table d'origine.
- **[MÉMOIRE]** = souvenir non revérifié pendant cette session : à confirmer avant de s'en servir.
- **[MESURÉ LOCAL]** = mesuré pendant cette session sur les bougies M15 du projet (lecture seule) :
  `data/fx_intraday/*_M15.csv` (Dukascopy) et `data/kaggle_gold/XAU_15m_data.csv`. Scripts et résultats bruts
  copiés dans `research_notes/Risque agitation et tendance courte/mesures_locales_agitation/`
  (`mesure_agitation.py`, `mesure_intraday.py`, `mesures.json`). Périodes : devises 2010→10/2026, or 2004→10/2026,
  S&P 500 2011→, DAX 2013→, pétrole WTI 2018→, bitcoin 2017→. Hors échantillon = 2e moitié de chaque historique.
- « Agitation » = volatilité. RV = volatilité réalisée (somme des carrés des petits rendements d'une journée).
- **Heure des fichiers** : l'annonce de l'emploi américain (NFP, 8h30 heure de New York) tombe toute l'année sur la
  bougie de 15h30 des fichiers → les fichiers sont à l'heure « serveur MT5 » (UTC+2 l'hiver, UTC+3 l'été, minuit =
  clôture de New York). Toutes les heures ci-dessous sont dans cette convention sauf mention contraire.

---

## 1. Modèles HAR (Corsi 2009) et extensions vs GARCH vs estimateurs à partir des bougies (OHLC)

### Takeaway
L'agitation est la grandeur la plus prévisible de la finance : un simple modèle HAR (moyenne pondérée de l'agitation
d'hier, de la semaine et du mois) explique ~40-75 % des variations de l'agitation du lendemain/de la semaine selon le
marché et l'échelle (log). Les extensions (sauts, HARQ) gagnent 0-20 % d'erreur en plus, pas plus. Avec les seules
bougies quotidiennes (haut-bas-ouverture-clôture), on garde l'essentiel : sur nos marchés, le HAR hors échantillon
explique 48-67 % (agitation mesurée par M15) à 1 jour et 62-77 % à 5 jours ; avec une mesure purement « bougie du
jour » (Parkinson) comme cible, 29-47 % à 1 jour et 49-68 % à 5 jours.

### Cited Findings
**HAR et HAR-J (Andersen, Bollerslev & Diebold 2007, Review of Economics and Statistics 89(4):701-720)** [VÉRIFIÉ, tables 2A-2C du document de travail NBER w11775]
- Données 5 min : DM/$ 12/1986-06/1999 (3 045 jours) ; S&P 500 à terme et obligations US 30 ans 01/1990-12/2002 (3 213 jours) — [NBER w11775](https://www.nber.org/papers/w11775)
- R² (dans l'échantillon) du HAR-RV-J, cible log(RV), horizons 1 / 5 / 22 jours : **DM/$ 0,476 / 0,502 / 0,407** ; **S&P 500 0,693 / 0,761 / 0,727** ; obligations US 0,200 / 0,351 / 0,379 — [NBER w11775](https://www.nber.org/system/files/working_papers/w11775/w11775.pdf)
- Même modèle mais avec seulement les rendements quotidiens au carré comme explicatifs (= ce qu'on voit avec des clôtures seules) : R² log **DM/$ 0,160 / 0,159 / 0,138 ; S&P 500 0,197 / 0,219 / 0,218** → les données intrajournalières multiplient le R² par 2 à 3 (« triplent » au mois pour S&P et obligations, selon les auteurs) — [NBER w11775](https://www.nber.org/system/files/working_papers/w11775/w11775.pdf)
- Coefficients HAR typiques (DM/$, cible RV, h=1) : jour 0,430, semaine 0,196, mois 0,244 ; S&P 500 : 0,341 / 0,485 / 0,165 — [NBER w11775](https://www.nber.org/system/files/working_papers/w11775/w11775.pdf)
- Les sauts ne prédisent presque rien : pour le S&P 500, une journée dont toute l'agitation vient d'un saut a un effet total sur le lendemain de **-0,027** (DM/$ : coefficient de saut -0,486 qui annule l'effet). Jours avec saut significatif : 30,6 % (DM/$), 27,9 % (S&P), 18,3 % (obligations) des jours — [NBER w11775](https://www.nber.org/system/files/working_papers/w11775/w11775.pdf)
- Les auteurs rappellent que l'erreur de mesure de la cible fait sous-estimer le R² par rapport à la prévisibilité vraie de l'agitation latente — [NBER w11775](https://www.nber.org/system/files/working_papers/w11775/w11775.pdf)

**HARQ (Bollerslev, Patton & Quaedvlieg 2016, Journal of Econometrics 192(1):1-18)** [VÉRIFIÉ, texte intégral]
- S&P 500 (5 min, 1997-2013, 3 096 jours) + 27 actions du Dow Jones. R² dans l'échantillon (cible RV, 1 jour) : AR 0,4235 ; **HAR 0,5224 ; HARQ 0,5624** ; actions en moyenne HAR 0,4852 → HARQ 0,5090 — [Maastricht CRIS PDF](https://cris.maastrichtuniversity.nl/ws/files/12579554/1600566.pdf)
- Hors échantillon, rapport d'erreur au carré (MSE) vs HAR, fenêtre glissante 1 000 jours, S&P 500 : HAR-J 0,918, CHAR 0,958, SHAR 0,838, ARQ 0,812, **HARQ 0,827** ; QLIKE : HARQ 0,946, HAR-J 1,006. Actions (moyenne) MSE : HARQ 0,935, HAR-J 1,015 → gains de 5-17 % d'erreur, et HAR-J n'aide pas sur les actions — [Maastricht CRIS PDF](https://cris.maastrichtuniversity.nl/ws/files/12579554/1600566.pdf)
- Autocorrélation d'ordre 1 de la RV quotidienne du S&P 500 : 0,651 (persistance « vraie » corrigée de l'erreur de mesure : 0,953) — [Maastricht CRIS PDF](https://cris.maastrichtuniversity.nl/ws/files/12579554/1600566.pdf)
- Pour le S&P 500 le test d'égalité de prévision n'est rejeté qu'au seuil de 10 % (p = 0,063 en MSE, p = 0,871 en QLIKE) → avantage HARQ modeste et fragile sur l'indice — [Maastricht CRIS PDF](https://cris.maastrichtuniversity.nl/ws/files/12579554/1600566.pdf)

**Estimateurs à partir des bougies (Parkinson 1980, Garman-Klass 1980, Rogers-Satchell 1991, Yang-Zhang 2000)**
- Efficacité théorique vs carré de la clôture-à-clôture (mouvement brownien) : Parkinson 2,5 à 5 fois ; Garman-Klass 7,4 ; Rogers-Satchell 6,0 ; Kunitomo 10 — [Mouti 2023, arXiv 2312.01426](https://arxiv.org/pdf/2312.01426) [VÉRIFIÉ]
- S&P 500, 01/2000-04/2015 (3 786 jours), comparés à la RV 5 min (bibliothèque Oxford-Man) : erreur quadratique moyenne ×10⁻⁴ : clôture-clôture 0,533 ; **Parkinson 0,092 ; Garman-Klass 0,094** ; Rogers-Satchell 0,206. Biais proportionnel négatif (−8 à −18 %) : les estimateurs par bougies **sous-estiment** l'agitation (prix discrets, sommets/creux manqués). Garman-Klass = le plus proche de la RV et le moins dispersé — [Mouti 2023](https://arxiv.org/pdf/2312.01426) [VÉRIFIÉ]
- Prévision de log(agitation Garman-Klass) avec seulement des bougies quotidiennes, rapport erreur/variance P (≈ 1 − R²) du HAR : S&P 100 0,443 (1 j), 0,546 (5 j), 0,734 (21 j) ; **EUR/USD 0,507 / 0,532 / 0,618** ; FTSE 0,463 / 0,545 / 0,699 ; indice matières premières BCOM **0,805 / 0,821 / 0,874** (peu prévisible) ; ensemble des indices 0,527 / 0,640 / 0,809. Le modèle « agitation rugueuse » (RFSV) fait à peu près pareil (meilleur à 21 j, moins bon à 1 j) — [Mouti 2023, table 6](https://arxiv.org/pdf/2312.01426) [VÉRIFIÉ]
- Shu & Zhang (2006, Journal of Futures Markets 26(3):297-313) : les estimateurs par bougies sont bons sous mouvement continu, mais divergent en présence d'un saut à l'ouverture ou d'une forte dérive ; sur le S&P 500, leurs variances sont « assez proches » de la variance intégrée quotidienne — [IDEAS](https://ideas.repec.org/a/wly/jfutmk/v26y2006i3p297-313.html) [RÉSUMÉ]
- Parkinson ne voit pas les trous entre bougies (ouverture ≠ clôture précédente) : il sous-estime sur les marchés qui ont des trous (indices, week-end) — [MQL5, article secondaire](https://www.mql5.com/en/articles/23454) [RÉSUMÉ, source non académique]

**Mesures locales sur nos marchés** [MESURÉ LOCAL — `mesures.json`]
- Corrélation (jour par jour) entre log de l'agitation tirée de la seule bougie quotidienne et log de la RV calculée sur les 96 bougies M15 : Garman-Klass **0,85-0,93** (EURUSD 0,877 ; USDJPY 0,901 ; GBPUSD 0,846 ; or 0,890 ; argent 0,893 ; S&P 500 0,918 ; DAX 0,895 ; WTI 0,896 ; bitcoin 0,933) ; Parkinson 0,82-0,92 ; carré ouverture→clôture seulement 0,36-0,52. → la bougie (haut/bas) contient l'essentiel de l'information d'agitation, la clôture seule non.
- HAR hors échantillon (2e moitié, réestimé tous les 21 jours), R² sur log(RV M15), 1 jour / moyenne 5 jours : EURUSD 0,608 / 0,754 ; USDJPY 0,567 / 0,629 ; GBPUSD 0,524 / 0,635 ; or 0,596 / 0,718 ; argent 0,668 / 0,770 ; S&P 500 0,608 / 0,634 ; DAX 0,606 / 0,623 ; WTI 0,612 / 0,665 ; bitcoin 0,478 / 0,658.
- Même chose avec la cible Parkinson (bougie quotidienne seule, plus bruitée) : 1 jour 0,29-0,47 ; 5 jours 0,49-0,68. Le « recopier hier » (marche aléatoire) donne R² ≈ 0 voire négatif sur cette cible bruitée → il faut lisser (moyennes semaine/mois), jamais se fier à la bougie d'hier seule.

**GARCH**
- ABDV 2003 utilisent un GARCH(1,1) quotidien comme niveau d'agitation du jour dans leur modèle intrajournalier, car il « fournit couramment une bonne approximation » de la dynamique quotidienne — [NBER w8959](https://www.nber.org/system/files/working_papers/w8959/w8959.pdf) [VÉRIFIÉ]
- Hansen & Lunde (2005, Journal of Applied Econometrics) : sur le DM/$ aucun des 330 modèles testés ne bat nettement un GARCH(1,1) ; sur une action (IBM), les modèles avec effet de levier font mieux — [MÉMOIRE, pas de lien vérifié]
- Andersen, Bollerslev, Diebold & Labys (2003, Econometrica) : un modèle sur la RV intrajournalière bat les GARCH sur rendements quotidiens pour les devises — cité par Harvey et al. 2018 (« Andersen et al. (2003) showed that realized intraday volatility predicts daily return volatility well for a number of currencies ») — [Harvey et al. 2018 PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf) [VÉRIFIÉ pour la citation]

### Inferences
- Pour une IA qui ne voit que des bougies M15 : elle peut reconstituer une RV quotidienne (somme des carrés des 96 rendements M15) presque aussi informative qu'une RV 5 min ; c'est mieux que Parkinson/Garman-Klass quotidien. Ordre d'information : RV M15 > Garman-Klass jour > Parkinson jour >> clôture-clôture.
- Le « plafond » réaliste de prévision de l'agitation du lendemain est un R² log de ~0,5-0,7, et ~0,6-0,8 pour la moyenne de la semaine à venir. Un modèle qui annonce beaucoup mieux sur des données jamais vues doit être suspecté de fuite d'information.
- Les marchés matières premières diversifiés (BCOM) et les obligations sont les moins prévisibles ; indices actions et devises les plus prévisibles.

### Gaps
- Pas trouvé de R² hors échantillon HAR publié spécifiquement pour l'or au comptant, le WTI ou l'USD/JPY dans des revues ; seules nos mesures locales les couvrent.
- Corsi (2009, Journal of Financial Econometrics) non relu : chiffres d'origine (USD/CHF, S&P 500, T-bond) non vérifiés.
- Table GARCH vs HAR hors échantillon chiffrée pour devises/or non retrouvée (Mouti 2023 annonce une comparaison GARCH mais sa table 6 n'a que AR/HAR/RFSV).

---

## 2. Saisonnalité intrajournalière et hebdomadaire de l'agitation

### Takeaway
Le rythme de la journée est le plus gros effet « facile » : sur nos données, l'heure la plus agitée l'est 2,3 à 3,8 fois
plus que la plus calme (devises 2,3-3,1 ; or 3,3 ; indices et pétrole 3,8 ; bitcoin seulement 1,6). Le pic est
partout l'ouverture de New York + les chiffres de 10h ET (bougies 16h-18h serveur), le creux est la fin de séance
asiatique/avant l'Europe (6h-7h serveur) ou juste après la clôture de New York (23h). Le lundi est ~10 % plus calme
que la moyenne en devises ; le samedi/dimanche du bitcoin ~40 % plus calme.

### Cited Findings
- Andersen & Bollerslev (1997, Journal of Empirical Finance 4(2-3):115-158) : périodicité intrajournalière omniprésente sur devises et actions ; S&P 500 en forme de U ; il faut la retirer pour voir la vraie dynamique de l'agitation (sinon les autocorrélations des rendements absolus 5 min sont déformées) — [Kellogg](https://www.kellogg.northwestern.edu/academics-research/research/detail/1997/intraday-periodicity-and-volatility-persistence-in-financial-markets/) [RÉSUMÉ]
- Andersen & Bollerslev (1998, Journal of Finance 53(1):219-265) : DM/$ en 5 min sur un an ; rythme intrajournalier, annonces macro et persistance quotidienne quantifiés séparément, expliquent une part substantielle de la variabilité — [Duke Scholars](https://scholars.duke.edu/publication/761296) [RÉSUMÉ]
- ABDV 2003 : forme de Fourier souple avec seulement **4** paires sinus/cosinus suffisant (critères Schwarz/Akaike) + variables pour l'ouverture de Tokyo, la pause déjeuner de Tokyo et la fin d'après-midi US en heure d'été — [NBER w8959](https://www.nber.org/system/files/working_papers/w8959/w8959.pdf) [VÉRIFIÉ]
- Ito & Hashimoto (2006, Journal of the Japanese and International Economies 20(4)) sur EBS (USD/JPY, EUR/USD 1999-2001) : 3 pics d'activité par jour (été : GMT 0, 6-7, 12-14 ; hiver : 0, 8, 13-15), 3 creux (déjeuner Tokyo GMT 3, déjeuner Londres, GMT 21-22) ; l'agitation suit l'activité ; écart achat-vente le plus large GMT 18-22 ; le pic de Tokyo est beaucoup plus faible pour l'EUR/USD que pour l'USD/JPY — [NBER w12413](https://www.nber.org/papers/w12413.pdf) [VÉRIFIÉ]
- Bitcoin (Eross, McGroarty, Urquhart & Wolfe 2019, Research in International Business and Finance 49:71-81, données 5 min sur 4 ans) : agitation « assez constante » sur la journée, plus forte aux ouvertures des trois grandes places boursières ; liquidité faible tôt le matin (GMT) — [Reading CentAUR](https://centaur.reading.ac.uk/81745/) [VÉRIFIÉ]

**Profils mesurés (range moyen des bougies M15 par heure, rapport à la moyenne)** [MESURÉ LOCAL]

| Marché | Pic (heure serveur) | Creux | Pic/creux | Lundi / vendredi (range jour, rel.) |
|---|---|---|---|---|
| EURUSD | 17h (1,72) ; 15-16h 1,6 ; 10h 1,43 | 6-7h (0,58) | **2,99** | 0,89 / 1,03 |
| GBPUSD | 17h (1,70) | 6h (0,54) | **3,13** | 0,90 / 1,03 |
| USDJPY | 17h (1,53) ; 3h Tokyo 1,22 | 23h (0,67) | **2,26** | 0,90 / 1,05 |
| Or (XAU) | 16h (1,79) ; 15-17h ~1,7 | 23h (0,54) | **3,31** | 0,93 / 1,04 |
| Argent | 16h (1,74) | 23h (0,61) | 2,86 | 0,97 / 1,06 |
| S&P 500 | 17h (1,87) ; 22h clôture 1,66 | 6-7h (0,50) | **3,76** | 0,94 / 1,02 |
| DAX | 10h ouverture Xetra (1,91) ; 17h 1,58 | 6h (0,50) | **3,84** | 0,99 / 0,97 |
| WTI | 16-17h (1,8) | 7h (0,48) | **3,77** | 1,01 / 0,93 |
| Bitcoin | 17h (1,30) | 7-8h (0,82) | **1,59** | lundi 1,14 ; dimanche 0,60 |

- Jeudi est en général le jour le plus agité (EURUSD 1,09 ; USDJPY 1,07 ; S&P 1,06). [MESURÉ LOCAL]
- À lui seul, le profil heure×jour de la semaine prévoit le log du range de la prochaine bougie M15 avec un R² hors échantillon de 0,07 (bitcoin) à 0,38 (WTI) ; EURUSD 0,30 ; S&P 0,26 ; or 0,17 ; USDJPY 0,14 — [MESURÉ LOCAL, `mesure_intraday.py`]

### Inferences
- Un stop fixe en points placé à 10h du matin serveur (calme) est ~3 fois « plus serré » en unités d'agitation à 17h. Toute règle de stop/taille doit être exprimée en agitation attendue **pour l'heure à venir**, pas en agitation moyenne du jour.
- Le bitcoin sur Dukascopy a un trou le samedi dans nos fichiers (aucune bougie « samedi » dans le profil) : à vérifier avant d'en tirer une conclusion week-end.

### Gaps
- Les rapports pic/creux publiés (figures d'Andersen-Bollerslev 1997/1998) n'ont pas été lus en chiffres ; seules nos mesures donnent des rapports.
- Pas de source académique lue sur la saisonnalité intrajournalière de l'or au comptant (Cai, Cheung & Wong 2001, Journal of Futures Markets 21(3):257-278, porte sur l'or COMEX ; texte intégral non obtenu — [IDEAS](https://ideas.repec.org/a/wly/jfutmk/v21y2001i3p257-278.html)).

---

## 3. Annonces macro : taille du saut d'agitation et durée

### Takeaway
Les grandes annonces américaines programmées (emploi, banque centrale, inflation) produisent le saut d'agitation le
plus prévisible du calendrier : la bougie M15 de l'emploi US a un range ~2 à 3 fois celui des autres vendredis à la
même heure (devises 2,2-2,9 ; or 2,0 ; S&P 2,2 ; bitcoin 1,5), l'excès retombe à ~+30-50 % après 30 min et disparaît
en ~2 h. Le prix « saute » presque instantanément (moins de 5 min) ; c'est l'agitation qui met jusqu'à ~1-2 h à
revenir.

### Cited Findings
- ABDV (2003, American Economic Review 93(1) ; document NBER w8959, 2002) : 6 ans de cotations, DM, livre, yen, franc suisse, euro contre dollar. Les **surprises** (écart réalisé − attendu) font sauter la moyenne conditionnelle ; les annonces conformes aux attentes n'ont pas d'effet. Ajustement « très rapide » : saut immédiat puis peu de mouvement — [NBER w8959](https://www.nber.org/system/files/working_papers/w8959/w8959.pdf) [VÉRIFIÉ]
- Une surprise d'une unité d'écart-type sur l'emploi US (NFP) déplace le DM/$ de **0,16 %** ; pour comparaison, seulement **0,7 %** des rendements 5 min dépassent 0,10 %, et l'écart achat-vente moyen est ~0,06 % — [NBER w8959](https://www.nber.org/system/files/working_papers/w8959/w8959.pdf) [VÉRIFIÉ]
- Dans le modèle d'agitation d'ABDV, l'effet des nouvelles est limité à **1 heure** ; essai à 3 heures : « une heure suffisait pour l'ajustement complet, pour tous les indicateurs et toutes les devises ». Les auteurs notent que la variance s'ajuste plus lentement que la moyenne — [NBER w8959](https://www.nber.org/system/files/working_papers/w8959/w8959.pdf) [VÉRIFIÉ]
- 58 % des jours contiennent une annonce, mais les 5 min suivant les annonces ne représentent que ~0,2 % des observations ; asymétrie : les mauvaises nouvelles pèsent plus que les bonnes — [NBER w8959](https://www.nber.org/system/files/working_papers/w8959/w8959.pdf) [VÉRIFIÉ]
- Indicateurs américains significatifs sur toutes les devises : emploi, commandes de biens durables, balance commerciale, inscriptions au chômage, indice NAPM/ISM, ventes de détail, confiance, PIB avancé ; FOMC : coefficients et R² « frappants ». Les annonces allemandes (heure de publication imprécise) ont peu d'effet — [NBER w8959](https://www.nber.org/system/files/working_papers/w8959/w8959.pdf) [VÉRIFIÉ]
- ABD 2007 : l'indice NAPM donne le plus fort R² de rendement 5 min parmi les annonces régulières (S&P/obligations) — [NBER w11775](https://www.nber.org/system/files/working_papers/w11775/w11775.pdf) [VÉRIFIÉ]
- Lahaye, Laurent & Neely (2011, Journal of Applied Econometrics 26(6):893-921) : emploi (NFP) et objectif des fonds fédéraux = les annonces les plus importantes toutes classes confondues ; balance commerciale importante pour les devises ; mais les annonces n'expliquent que **~3-4 % des sauts du dollar** (et l'objectif des fonds fédéraux ~1 %) — la plupart des sauts de devises viennent de chocs de liquidité. Par contre les nouvelles accompagnent 73 % des sauts communs Nasdaq-obligations — [St. Louis Fed WP 2007-032](https://files.stlouisfed.org/files/htdocs/wp/2007/2007-032.pdf) [VÉRIFIÉ]
- Or : parmi 23 annonces US, emploi, PIB, prix à la consommation (CPI) et revenu personnel ont le plus d'effet sur l'or COMEX (Cai, Cheung & Wong 2001) — [IDEAS](https://ideas.repec.org/a/wly/jfutmk/v21y2001i3p257-278.html) [RÉSUMÉ]

**Mesure locale de l'effet « emploi US »** (1er vendredi du mois ≈ NFP ; range moyen de chaque bougie M15 divisé par celui des autres vendredis à la même heure ; la bougie 15h30 serveur = 8h30 New York) [MESURÉ LOCAL]

| Marché | Bougie 8h30 ET | +15 min | +30 min | +45 min | +1 h | +2 h |
|---|---|---|---|---|---|---|
| EURUSD | **2,49** | 1,57 | 1,43 | 1,31 | 1,19 | ~1,0 |
| USDJPY | **2,91** | 1,82 | 1,49 | 1,35 | 1,32 | ~1,03-1,1 |
| GBPUSD | 2,23 | 1,45 | 1,33 | 1,27 | 1,18 | ~1,0 |
| Or | 1,99 | 1,35 | 1,28 | 1,21 | 1,15 | ~1,04 |
| S&P 500 | 2,18 | 1,67 | 1,36 | 1,04 | 1,22 | ~1,08 |
| DAX | 1,88 | 1,40 | 1,29 | 1,16 | 1,17 | ~1,05 |
| WTI | 1,58 | 1,19 | 1,04 | 1,08 | 1,24 | ~1,1 |
| Bitcoin | 1,46 | 1,09 | 0,97 | 0,88 | 0,90 | ~0,9 |

- Ces rapports sont des **minorants** : certains « 1ers vendredis » ne sont pas des jours NFP (NFP parfois le 2e vendredi), et une bougie M15 dilue un saut de quelques secondes.

### Inferences
- L'IA ne voit pas le calendrier économique ; mais avec l'heure et le jour (1er vendredi, mercredi FOMC à 14h ET = 21h serveur, etc.) elle peut apprendre une partie de l'effet ; le plus simple et le plus robuste est de lui donner explicitement l'heure/jour et éventuellement un drapeau « annonce majeure programmée ».
- Conséquence pour les stops : un stop serré traversant 8h30 ET un jour d'emploi a ~2-3 fois plus de chances d'être touché par le bruit dans les 15 min ; et les sauts de prix (glissement au-delà du stop) se concentrent sur ces bougies.

### Gaps
- Pas de chiffre vérifié de durée pour FOMC / BCE / CPI séparément (seule la règle « ≤ 1 h » d'ABDV et notre mesure NFP).
- Andersen, Bollerslev, Diebold & Vega 2007 (Journal of International Economics, actions/obligations/devises) et Evans & Lyons (2008, Journal of Financial Economics : la nouvelle passe aussi par le flux d'ordres pendant des heures) non relus — [MÉMOIRE].

---

## 4. Apprentissage automatique / réseaux de neurones vs HAR

### Takeaway
Les méthodes d'apprentissage battent le HAR d'environ 0-12 % d'erreur quadratique quand elles reçoivent des
informations supplémentaires ; avec les mêmes trois entrées (jour/semaine/mois) le gain est de ~0-5 %. Un travail
récent montre qu'un HAR réestimé chaque jour sur fenêtre glissante redevient le meilleur sur 1 445 actions. Le gain
possible d'une IA sur la **prévision de l'agitation** est donc petit ; il est surtout dans les marchés calmes.

### Cited Findings
- Christensen, Siggaard & Veliyev (2023, Journal of Financial Econometrics ; document CREATES RP 2021-03) : 29 actions du Dow Jones, 2001-2017, prévision RV à 1 jour. Avec seulement les 3 retards HAR (M1) : forêt aléatoire 1,020, boosting 1,055, réseaux de neurones **0,950-0,972** (ensemble de 5-10 réseaux) — c.-à-d. ≤ 5 % de gain. Avec 12 variables (M3, dont caractéristiques d'entreprise et macro) : ridge 0,915, filet élastique 0,910 (−9,0 %), forêt 0,906 (−9,4 %), réseaux **0,882-0,885 (−11,5 à −11,8 %)** — [CREATES RP 21-03](https://repec.econ.au.dk/repec/creates/rp/21/rp21_03.pdf) [VÉRIFIÉ]
- Même étude : gain du réseau à 3 couches **−36 %** d'erreur dans les 10 % de jours les plus calmes, seulement **−7,4 %** dans les 10 % les plus agités ; ensemble de modèles de confiance : réseaux retenus 72-90 % du temps contre 41 % pour le HAR ; résultat sensible au krach éclair du 24/08/2015 — [CREATES RP 21-03](https://repec.econ.au.dk/repec/creates/rp/21/rp21_03.pdf) [VÉRIFIÉ]
- Version publiée : l'apprentissage « bat la lignée HAR même avec seulement les retards jour/semaine/mois », gains plus nets aux horizons longs (persistance plus longue) — [résumé, arXiv 2311.06256 citant l'article](https://arxiv.org/pdf/2311.06256) / [X-MOL](https://ma.x-mol.com/paper/1539803485281558528) [RÉSUMÉ]
- « HARd to Beat » (arXiv 2406.08041, 2024) : 1 445 actions US 2016-11/2023 ; HAR réestimé chaque jour sur 630 jours glissants. Erreur moyenne : HAR (moindres carrés pondérés) 0,425 ; lasso 0,435 ; forêt 0,460 ; boosting 0,473 ; réseau 0,568. Le HAR est retenu dans l'ensemble des meilleurs pour 88,5 % des actions (MSE) ; utilité économique HAR 3,218 % vs lasso 3,202 % — [arXiv 2406.08041](https://arxiv.org/html/2406.08041v1) [VÉRIFIÉ, page HTML]
- Bucci (2020, Journal of Financial Econometrics 18(3):502-531) : réseaux récurrents (LSTM, NARX) battent les modèles économétriques (dont ARFIMA) pour la RV **mensuelle** du S&P 500 (1997-2017) — horizon hors de notre cible — [IDEAS](https://ideas.repec.org/a/oup/jfinec/v18yi3p502-531..html) [RÉSUMÉ]
- Petneházi & Gáll (arXiv 1803.07152) : avec des LSTM sur le Dow Jones, les changements des estimateurs par bougies (Parkinson, etc.) sont plus prévisibles que ceux de la clôture-clôture — [arXiv 1803.07152](https://arxiv.org/pdf/1803.07152) [VÉRIFIÉ, résumé du PDF]

### Inferences
- Pour COLLAPSAR : un « œil » d'IA qui prévoit l'agitation n'a pas à être complexe ; un HAR multi-échelle (dernières heures, jour, semaine, mois) + profil horaire est déjà proche du plafond. Le vrai test d'honnêteté : l'IA doit au moins égaler ce HAR sur données jamais vues ; si elle fait beaucoup mieux, chercher une fuite.
- La réestimation fréquente (fenêtre glissante) compte plus que la complexité du modèle.

### Gaps
- Aucune étude d'apprentissage vs HAR trouvée spécifiquement sur l'or, le pétrole ou les devises à 15 min-1 jour avec des bougies seulement.

---

## 5. Spécificités crypto (24 h/24, 7 j/7, week-ends)

### Takeaway
Le bitcoin est 4 à 7 fois plus agité que les devises (≈ 60 %/an sur nos données), a des queues plus épaisses et
beaucoup plus de sauts, mais son agitation reste bien prévisible au jour/semaine (HAR hors échantillon R² 0,48 à 1 j,
0,66 à 5 j). Son rythme intrajournalier est faible (pic/creux 1,6) ; le week-end est nettement plus calme.

### Cited Findings
- Hu, Kuo & Härdle (arXiv 1912.05228, « Risk of Bitcoin market ») : 5 min, 01/2017-12/2020, 1 385 jours ; rendements 5 min de −18,64 % à +10,30 % ; RV annualisée moyenne 0,86 (écart-type 1,88, max 36,93) ; **64 %** des jours ont plus d'un saut détecté (seuil 99,99 %) ; à 1 jour, le HAR sans sauts bat les versions avec sauts ; les sauts aident à 30 jours — [arXiv 1912.05228](https://ar5iv.arxiv.org/html/1912.05228) [VÉRIFIÉ, page]
- Études HAR sur bitcoin : sauts et ruptures structurelles améliorent la prévision à 1 jour, 1 semaine, 1 mois (Mensi et al. / Reading) ; HARQ-F-J meilleur à 1 jour dans une autre étude — [Reading CentAUR 87932](https://reading-clone.eprints-hosting.org/87932) ; [Nottingham ePrints](https://eprints.nottingham.ac.uk/57681) [RÉSUMÉ ; résultats contradictoires avec Hu et al. sur l'utilité des sauts à 1 jour]
- Eross et al. 2019 : agitation assez constante dans la journée, plus forte aux ouvertures des places boursières — [Reading CentAUR](https://centaur.reading.ac.uk/81745/) [VÉRIFIÉ]
- [MESURÉ LOCAL] bitcoin 2017→10/2026 : agitation annuelle moyenne 60,5 % ; écart-type du log de l'agitation quotidienne 0,57 (le plus élevé) ; range quotidien dimanche 0,60× la moyenne, lundi 1,14× ; bougies M15 > 4 écarts-types locaux : **364 par an** (1,3 % des bougies, contre 0,6-0,9 % ailleurs) ; indice de queue 2,6 (plus épais que 2,9-3,4 ailleurs) ; l'emploi US ne multiplie le range que par 1,46.

### Inferences
- En CFD FTMO, le bitcoin demande une taille divisée par ~5-7 par rapport à l'EUR/USD pour un même risque, et une marge supplémentaire pour les sauts (le stop peut être dépassé).
- Le samedi est absent de nos fichiers bitcoin Dukascopy : vérifier si le flux de données coupe le week-end avant d'entraîner l'IA sur des week-ends crypto.

### Gaps
- Pas trouvé d'article évalué par des pairs donnant un rapport chiffré « agitation week-end / semaine » pour le bitcoin ; seule notre mesure (dimanche ≈ 0,6).

---

## 6. Utiliser la prévision d'agitation pour les stops et la taille

### Takeaway
La taille « au risque constant » (exposition = cible ÷ agitation prévue) est la pratique standard des fonds de
tendance ; elle réduit toujours l'agitation de l'agitation, les queues et les pertes maximales, mais n'améliore le
rendement ajusté du risque que sur les actifs « à effet de levier » (actions, crédit) ; neutre sur devises, matières
premières, obligations. Les stops n'ajoutent du rendement que s'il existe de l'inertie (tendance) ; sous marche
aléatoire ils en retirent toujours.

### Cited Findings
- Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert (2018, Journal of Portfolio Management 45(1):14-33) : 60+ actifs, données quotidiennes depuis 1926 (actions) jusqu'à 2017, cible 10 %/an, agitation estimée par moyenne exponentielle des carrés des rendements quotidiens (moyenne supposée nulle), demi-vies testées 10 à 90 jours — [Duke PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf) [VÉRIFIÉ]
- Actions US 1927-2017 : rendement/risque **0,40 sans pilotage → 0,48 à 0,51 avec**, peu sensible au choix de l'estimateur ; avec demi-vie 10 jours, coûts ≈ 0,066 %/an (0,4831 brut → 0,4766 net) ; rotation de ~5 fois par an (estimateur le plus réactif) à < 1 fois — [Duke PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf) [VÉRIFIÉ]
- Obligations, devises, matières premières : effet sur le rendement/risque « négligeable » ; mais baisse de l'agitation de l'agitation et des extrêmes sur **tous** les actifs ; gains les plus forts avec l'estimateur le plus réactif ; le pilotage coupe les deux queues (gauche et droite) — [Duke PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf) [VÉRIFIÉ]
- Ils ont aussi piloté le S&P 500 à terme avec une RV 5 min (9h15-14h00 Chicago) depuis 1988 — [Duke PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf) [VÉRIFIÉ]
- Moskowitz, Ooi & Pedersen (2012, Journal of Financial Economics, « Time series momentum ») : agitation ex ante = moyenne exponentielle des carrés des rendements quotidiens, poids choisis pour un **centre de masse de 60 jours** ; chaque position divisée par cette agitation (contribution égale au risque) — [notebook de réplication Quantopian](https://nbviewer.jupyter.org/github/quantopian/research_public/blob/master/advanced_sample_analyses/TSMOM/TS%20MOM.ipynb) ; [SSRN 2089463](https://papers.ssrn.com/abstract=2089463) [RÉSUMÉ ; la cible de 40 %/an par actif est un souvenir — MÉMOIRE]
- Kaminski & Lo (2014, Journal of Financial Markets 18:234-254) : sous l'hypothèse de marche aléatoire, une règle de stop simple (0/1) **diminue toujours** le rendement espéré ; en présence d'inertie (momentum) elle peut ajouter de la valeur ; sur données mensuelles 1950-2004, certaines règles ajoutent **50 à 100 points de base par mois** au portefeuille actions pendant les périodes « stoppées », tout en réduisant nettement l'agitation — [MIT DSpace](https://dspace.mit.edu/handle/1721.1/114876) [RÉSUMÉ, PDF bloqué (erreur 429)]
- Osler (2002/2005, rapport NY Fed n°150 « Stop-loss orders and price cascades in currency markets ») : les ordres stop se regroupent à des niveaux connus ; quand ils sont atteints, les tendances sont anormalement rapides (« cascades ») ; l'effet dure des heures mais pas des jours ; contribue aux queues épaisses des devises — [NY Fed Staff Report 150](https://www.newyorkfed.org/research/staff_reports/sr150.html) [VÉRIFIÉ sur le résumé du PDF ; URL de mémoire]

### Inferences
- Pour un challenge FTMO (perte du jour −5 %, totale −10 %), le pilotage par l'agitation est surtout un outil **anti-mur** : il réduit les extrêmes et les pertes maximales, ce qui est exactement ce qui fait échouer un challenge, même s'il ne crée pas d'avantage.
- Stop et taille doivent être liés : risque monétaire = taille × distance du stop ; si la distance est en multiples d'agitation prévue (pour l'heure qui vient), la taille s'ajuste automatiquement. La littérature citée ne donne pas de multiple « optimal » d'agitation pour le stop (pratique de fonds, pas de preuve publiée trouvée).
- Pour une IA libre de choisir son stop : la seule manière qu'un stop rapporte est qu'il y ait de l'inertie à court terme après les grosses sorties de range (Kaminski & Lo ; Osler) ; sinon le stop ne fait que transformer le profil de gains (moins de grosses pertes, plus de petites).

### Gaps
- Pas de preuve académique chiffrée sur les stops « k × agitation » à l'échelle 15 min-quelques jours (pratique des fonds de tendance non publiée sous forme vérifiable).
- Moreira & Muir (2017, Journal of Finance, « Volatility-managed portfolios ») non relu — [MÉMOIRE].

---

## 7. Chiffres pour bâtir des marchés synthétiques réalistes

### Takeaway
Ordres de grandeur à reproduire : agitation annuelle 8-9 % (grandes devises), 17-18 % (or, indices), 33 % (argent),
~47 % (WTI 2018-2026), ~60 % (bitcoin) ; écart-type du log de l'agitation quotidienne 0,36-0,57 ; mémoire longue
(autocorrélation du log-agitation encore 0,2-0,4 après 3 mois) ; queues de puissance d'indice ~3 (« loi cubique »)
sur les rendements M15 normalisés ; sauts : environ un jour sur quatre en devises, un sur 12-15 en indices.

### Cited Findings
**Sauts (Lahaye, Laurent & Neely 2011)** [VÉRIFIÉ, table 2 du WP St. Louis Fed]
- Devises en 5 min, 24 h/24, 1987-2004 (USD/EUR, USD/GBP, JPY/USD, CHF/USD) : jours avec saut **24,3-26,9 %** ; 1,33-1,38 saut par jour de saut ; taille moyenne absolue **0,27-0,36 %** ; ~50 % de sauts négatifs (pas d'asymétrie) ; agitation annualisée 10,2-12,2 % — [St. Louis Fed WP 2007-032](https://files.stlouisfed.org/files/htdocs/wp/2007/2007-032.pdf)
- S&P 500, Nasdaq 100, Dow Jones à terme : jours avec saut **6,6-8,4 %** ; taille moyenne 0,74 % (DJ), 0,89 % (S&P), 1,61 % (Nasdaq) ; obligations US 8,3 %, 0,51 % ; proportion de bougies 5 min avec saut 0,24-0,39 % partout ; un saut moyen ≈ 3 % (devises), 4 % (actions), 5 % (obligations) de l'agitation annuelle — [St. Louis Fed WP 2007-032](https://files.stlouisfed.org/files/htdocs/wp/2007/2007-032.pdf)

**Persistance** 
- S&P 500 : autocorrélation d'ordre 1 de la RV quotidienne 0,651 (corrigée de l'erreur de mesure 0,953) ; actions du Dow 0,37-0,73 — [BPQ 2016](https://cris.maastrichtuniversity.nl/ws/files/12579554/1600566.pdf) [VÉRIFIÉ]
- Le log de l'agitation se comporte comme un mouvement « rugueux » avec un exposant de Hurst < 0,1 sur les estimateurs par bougies (≈ 0,1 sur la RV, Gatheral et al.) — [Mouti 2023](https://arxiv.org/pdf/2312.01426) [VÉRIFIÉ, résumé]
- Harvey et al. testent des demi-vies 10-90 jours pour l'estimateur ; demi-vie 20 jours utilisée dans plusieurs figures — [Duke PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf) [VÉRIFIÉ]

**Mesures locales** [MESURÉ LOCAL — `mesures.json`]

| Marché | Agit. annuelle | Écart-type log-agit. jour | Autocorr. log RV j : 1 / 5 / 22 / 66 j | Retard où l'autocorr. tombe à la moitié de celle à 1 j | Bougies M15 > 4σ / an (> 6σ) | Jours > 4σ / an | Indice de queue (M15) |
|---|---|---|---|---|---|---|---|
| EURUSD | 8,4 % | 0,40 | 0,69 / 0,63 / 0,48 / 0,38 | 77 j | 169 (50) | 0,36 | 3,1 |
| USDJPY | 9,2 % | 0,45 | 0,67 / 0,51 / 0,36 / 0,22 | 27 j | 219 (67) | 1,31 | 2,9 |
| GBPUSD | 8,9 % | 0,36 | 0,66 / 0,59 / 0,39 / 0,31 | 47 j | 145 (41) | 0,36 | 3,2 |
| Or | 17,5 % | 0,43 | 0,68 / 0,60 / 0,47 / 0,33 | 57 j | 179 (50) | 0,76 | 3,1 |
| Argent | 32,6 % | 0,44 | 0,70 / 0,62 / 0,49 / 0,38 | 78 j | 193 (53) | 1,07 | 3,1 |
| S&P 500 | 15,9 % | 0,55 | 0,78 / 0,60 / 0,38 / 0,19 | 21 j | 121 (31) | 1,00 | 3,2 |
| DAX | 17,9 % | 0,46 | 0,75 / 0,60 / 0,36 / 0,24 | 21 j | 120 (28) | 1,15 | 3,4 |
| WTI | 47,2 % | 0,46 | 0,80 / 0,68 / 0,48 / 0,09 | 31 j | 149 (37) | 1,71 | 3,3 |
| Bitcoin | 60,5 % | 0,57 | 0,65 / 0,49 / 0,33 / 0,27 | 19 j | 364 (123) | 0,96 | 2,6 |

Notes de méthode : σ local d'une bougie M15 = agitation moyenne par bougie de la veille × profil horaire ; « jours
> 4σ » = rendement ouverture→clôture du jour divisé par l'agitation exponentielle passée (centre de masse 60 j) ;
indice de queue = estimateur de Hill sur les 2,5 % plus grands |rendements normalisés| ; kurtosis des rendements M15
normalisés 16-33 (jusqu'à 180-210 pour USDJPY/bitcoin à cause de quelques chocs extrêmes, ex. franc suisse 2015).
Une loi normale donnerait ~0,006 % de bougies > 4σ, soit ~1,5 par an sur 24 000 bougies : on en observe
**80 à 240 fois plus**.
- Une AR(1) sur le log de l'agitation quotidienne donne une demi-vie de seulement 1,6-3 jours (trompeur : bruit de
  mesure + mémoire longue) ; la décroissance réelle est lente : la moitié de l'autocorrélation à 1 jour est perdue
  après 19-78 jours.

### Inferences
- Un générateur synthétique réaliste doit avoir : (1) une agitation log-normale à mémoire longue (au moins trois
  composantes jour/semaine/mois ou un processus « rugueux »), écart-type du log 0,4-0,55 ; (2) un profil horaire
  multiplicatif pic/creux ~3 (bitcoin 1,6) ; (3) des chocs programmés (vendredi emploi ×2-3 sur 15 min, décroissance
  sur ~2 h) ; (4) des sauts : ~25 % des jours en devises de taille ~0,3 %, ~7 % des jours en indices de ~0,7-1,6 %,
  sans mémoire pour l'agitation suivante ; (5) des queues de puissance d'indice ~3.
- Tant qu'un tel générateur n'a pas de **direction** prévisible, l'IA ne doit y apprendre que la gestion du risque
  (stop, taille, éviter les heures/annonces dangereuses) — cohérent avec l'idée « l'enfant découvre que la perte n'est
  pas forcément mauvaise ».

### Gaps
- Pas de demi-vie publiée par marché (or, WTI, bitcoin) retrouvée dans la littérature : seules nos mesures.
- Agitation de l'agitation publiée par classe d'actif (Harvey et al. la mesurent mais les tables par actif n'ont pas été extraites).

---

## 8. Ce qu'une IA qui ne voit que des bougies M15 peut réalistement prévoir

### Takeaway
L'**agitation** à venir est très prévisible depuis les seules bougies : R² hors échantillon de ~0,58-0,69 pour le log
du range de la prochaine bougie M15, ~0,70-0,80 pour les 4 prochaines (1 h), ~0,74-0,84 pour les 16 prochaines (4 h),
~0,74-0,85 pour les 96 prochaines (1 jour). À l'inverse, la direction est quasiment imprévisible (voir travaux du
projet : ~51 % sur 2020-2022). L'IA doit donc tirer son avantage de la gestion de la taille et du stop autant que du
sens.

### Cited Findings
**Mesure locale** — R² hors échantillon (2e moitié) du log du range moyen des h prochaines bougies M15 ; régression
simple sur : profil heure×jour de la semaine (appris en 1re moitié) + log du range moyen des 4, 96 et 480 dernières
bougies [MESURÉ LOCAL, `mesure_intraday.py`]

| Marché | 15 min : saison / passé / les deux | 1 h (4 bougies) | 4 h (16) | 1 jour (96) |
|---|---|---|---|---|
| EURUSD | 0,30 / 0,62 / **0,67** | 0,36 / 0,69 / **0,80** | 0,35 / 0,61 / **0,84** | 0,01 / 0,84 / **0,85** |
| USDJPY | 0,14 / 0,58 / **0,61** | 0,16 / 0,66 / **0,73** | 0,13 / 0,63 / **0,75** | 0,01 / 0,76 / **0,77** |
| Or | 0,17 / 0,56 / **0,58** | 0,22 / 0,63 / **0,70** | 0,22 / 0,58 / **0,75** | 0,02 / 0,79 / **0,81** |
| S&P 500 | 0,26 / 0,65 / **0,69** | 0,32 / 0,69 / **0,80** | 0,30 / 0,60 / **0,81** | −0,04 / 0,72 / **0,74** |
| WTI | 0,38 / 0,60 / **0,67** | 0,46 / 0,65 / **0,80** | 0,44 / 0,55 / **0,84** | 0,00 / 0,80 / **0,81** |
| Bitcoin | 0,07 / 0,63 / **0,64** | 0,08 / 0,71 / **0,72** | 0,09 / 0,70 / **0,74** | 0,04 / 0,74 / **0,77** |

- À 4 h, l'heure de la journée apporte +10 à +29 points de R² par rapport au passé seul (EURUSD 0,61 → 0,84 ; WTI
  0,55 → 0,84) : c'est l'horizon où le rythme de la journée compte le plus. À 1 jour, l'heure n'apporte presque rien
  (le jour entier contient toutes les heures). [MESURÉ LOCAL]
- Littérature : HAR quotidien log ~0,48-0,76 R² (ABD 2007, BPQ 2016), apprentissage +0-12 % d'erreur en moins
  (Christensen et al.) — voir sections 1 et 4.

### Inferences
- Ces R² sont en échelle log : en échelle de variance (ce qui compte pour une perte en argent), ils sont plus bas,
  car les chocs (sauts, annonces surprises) dominent les queues et sont imprévisibles (les sauts ne prédisent rien,
  ABD 2007 ; seulement 3-4 % des sauts de devises viennent d'annonces, LLN 2011).
- Donc : une IA peut savoir **combien** le prix va probablement bouger dans l'heure (à ±30-40 % près), pas **dans
  quel sens**. Le choix de la distance du stop et de la taille peut être bien calibré ; la question « le stop sera-t-il
  touché avant l'objectif ? » reste dominée par le sens, quasi imprévisible.
- Un repère simple à fournir à l'IA (ou à battre) : « agitation prévue = profil de l'heure × moyenne pondérée de
  l'agitation des 1 h / 1 jour / 5 jours », réestimée régulièrement.

### Gaps
- R² en échelle de variance (non log) et sur la probabilité « stop touché avant objectif » non mesurés pendant cette
  session.
- Les mesures locales n'excluent pas les jours fériés/fins d'année à faible liquidité et n'ont pas d'intervalle de
  confiance ; à reproduire avant usage pour décision.
