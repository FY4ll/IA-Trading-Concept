# Méthodes d'intelligence artificielle en trading : ce qui apporte vraiment quelque chose à un développeur seul (PC GTX 1060 6 Go, 16 Go, données gratuites), état 2024-2026

Note de méthode : les chiffres « en échantillon » (sur les données qui ont servi à construire le modèle) et « hors échantillon / réel » sont distingués partout. Rappel du contexte du projet : il a déjà constaté que l'apprentissage par renforcement (PPO) et les réseaux profonds sur les prix seuls apprennent par cœur sans avantage hors échantillon, et qu'un juge supervisé « valeur d'un coup », bien calibré, n'était pas rentable.

## 1. Gestion du risque et répartition : prévision de volatilité, détection de régimes, répartition hiérarchique

### Takeaway
C'est le domaine où les preuves sont les plus solides et les plus durables : prévoir la volatilité marche (la volatilité est persistante, contrairement au rendement), et le ciblage de volatilité réduit surtout les pertes extrêmes et les baisses maximales ; il n'améliore le rapport rendement/risque que sur les actifs « à risque » (actions, crédit), presque pas sur devises, matières premières, obligations. Les modèles simples (HAR, GARCH) restent très difficiles à battre ; l'apprentissage automatique ajoute quelques % de précision au mieux.

### Cited Findings
- Ciblage de volatilité (Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, Van Hemert, Man AHL, JPM 2018, plus de 60 actifs, données depuis 1926 jusqu'à 2017) : pour les actions, rapport rendement/risque de 0,40 (sans ciblage) à 0,48-0,51 (avec) ; pour obligations, devises et matières premières, effet sur ce rapport « négligeable » ; mais le ciblage réduit la probabilité des rendements extrêmes dans TOUTES les classes d'actifs et réduit la baisse maximale des portefeuilles équilibrés et « parité de risque ». — [Quantpedia, résumé du papier](https://quantpedia.com/the-impact-of-volatility-targeting-on-equities-bonds-commodities-and-currencies) ; [papier original, Duke](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf)
- L'amélioration côté actions est reliée à « l'effet de levier » (la volatilité monte quand les actions baissent), d'où l'absence d'effet sur devises/matières premières. — [Quantpedia](https://quantpedia.com/the-impact-of-volatility-targeting-on-equities-bonds-commodities-and-currencies)
- Contre-preuve importante : Cederburg, O'Doherty, Wang et Yan (JFE 2020), 103 stratégies actions : les portefeuilles « gérés par la volatilité » ne battent PAS systématiquement les portefeuilles non gérés ; les versions réalisables en temps réel gagnent en général un rapport rendement/risque plus bas que l'investissement simple ; cause : instabilité des paramètres estimés. Exceptions : facteurs momentum, rentabilité (ROE) et « faible bêta ». — [Alpha Architect](https://alphaarchitect.com/does-portfolio-timing-based-on-volatility-signals-outperform-buy-and-hold/) ; [papier Lehigh](https://www.lehigh.edu/~xuy219/research/COWY.pdf)
- Prévision de volatilité réalisée par apprentissage automatique (Christensen, Siggaard, Veliyev, J. Financial Econometrics 2023, actions du Dow Jones) : les réseaux de neurones battent la famille HAR, jusqu'à -11,8 % d'erreur quadratique sur certains titres, gains plus nets à horizon long, même avec seulement les retards jour/semaine/mois de la volatilité comme entrées. — [CREATES working paper](https://repec.econ.au.dk/repec/creates/rp/21/rp21_03.pdf) (résumé via moteur de recherche)
- Un papier de 2024 (« HARd to Beat ») soutient que l'avantage apparent de l'apprentissage automatique sur HAR vient en partie de l'usage de fenêtres glissantes négligé pour HAR : avec des fenêtres glissantes, HAR redevient très compétitif. — [arXiv 2406.08041](https://arxiv.org/html/2406.08041v1) (titre et résumé seulement, non lu en entier)
- Volatilité réalisée, 50 actifs (40 actions US 2015-2026, 5 paires de devises et 5 contrats à terme 2009-2026), 9 modèles de fondation en usage direct (sans réentraînement) contre 8 modèles économétriques : seul un petit modèle (TTM, « Tiny Time Mixers ») bat le Log-HAR à tous les horizons, et de peu (rapports de perte 0,982 / 0,986 / 0,987 à 1, 5, 22 jours, soit 1,3 à 1,8 % de mieux) ; les autres modèles de fondation font 1,038 à 1,532 (pires) ; une moyenne à parts égales TTM + Log-HAR égale le meilleur modèle. Conclusion des auteurs : « les modèles de fondation n'apportent pas un gain uniforme ». — [arXiv 2607.05291](https://arxiv.org/html/2607.05291v1)
- Régimes (chaînes de Markov cachées) : Nystrup et al. (DTU) : stratégies fondées sur un modèle à 2 états estimé de façon adaptative battent un rééquilibrage fixe hors échantillon après frais, avec un délai réaliste entre détection du régime et ajustement. — [DTU, « Regime-Based Asset Allocation - Do Profitable Strategies Exist? »](https://www2.imm.dtu.dk/pubdb/pubs/6808-full.html)
- Autre étude HMM d'allocation (source exacte non vérifiée parmi les résultats de recherche) : hors échantillon, rentable après frais, volatilité réduite de 41 % en moyenne, excès de rendement annuel de 0,185 % à 2,016 %. — [résultats de recherche, MPRA 121552](https://mpra.ub.uni-muenchen.de/121552/1/MPRA_paper_121552.pdf) (attribution à vérifier)
- Répartition hiérarchique (« parité de risque hiérarchique », López de Prado) : variance hors échantillon plus faible que minimum-variance, inverse-variance et parts égales en simulations Monte-Carlo ; mais une comparaison hors échantillon étendue sur le marché brésilien conclut qu'elle « ne donne pas la meilleure performance en général ». Un essai cryptos (non académique) : parts égales 0,794, inverse-volatilité 0,853, hiérarchique 0,922 (rapport rendement/risque). — [Revista Brasileira de Finanças](https://periodicos.fgv.br/rbfin/article/download/89848/84802/201368) ; [QuantConnect](https://www.quantconnect.com/research/18784/digital-asset-stockpile-portfolio-construction-techniques/)

### Inferences
- Pour un compte FTMO (règle -5 %/jour, -10 % total), l'intérêt principal du ciblage de volatilité est la réduction des queues de distribution et de la baisse maximale, pas le gain : c'est exactement ce que demande FTMO. Sur devises/métaux/énergies, ne pas attendre de hausse du rapport rendement/risque.
- Un modèle HAR (régression linéaire sur volatilité réalisée du jour, de la semaine, du mois) suffit : il tourne en millisecondes sur le PC, et rien de publié ne justifie un réseau profond pour cela. Le gain de l'apprentissage automatique (quelques % de précision) est petit et fragile.
- Le ciblage « naïf » (exposition = cible / volatilité prévue) est plus robuste que des versions optimisées par régression (cf. Cederburg et al. : c'est l'estimation de paramètres qui casse en temps réel).
- Les régimes HMM : preuve modeste, surtout en allocation d'actifs à basse fréquence ; à utiliser comme moduleur de taille, pas comme générateur de signaux.

### Gaps
- Pas trouvé d'étude hors échantillon spécifique au ciblage de volatilité sur un compte de type « prop firm » ou sur de l'intrajournalier multi-marchés.
- Moreira & Muir (2017, « Volatility-managed portfolios ») non vérifié directement (seulement via sa critique).
- Répartition par apprentissage automatique entre plusieurs stratégies : aucune preuve solide trouvée dans le temps imparti.

## 2. Méta-étiquetage (López de Prado) : un second modèle qui filtre les coups d'une stratégie

### Takeaway
L'idée est saine (la direction vient d'une stratégie primaire qui a un avantage ; un second modèle décide de prendre ou non le coup et de sa taille), mais les preuves publiques hors échantillon sont minces et viennent surtout des promoteurs de la méthode (Hudson & Thames) ; le méta-étiquetage ne crée pas d'avantage si la stratégie primaire n'en a pas.

### Cited Findings
- Définition : couche de décision secondaire qui évalue les signaux d'un modèle primaire, estime leur probabilité de réussite, et sert à dimensionner les positions et supprimer les faux positifs. — [Wikipédia « Meta-Labeling »](https://en.wikipedia.org/wiki/Meta-Labeling) (via résumé de recherche)
- Hudson & Thames (Joubert et al.) ont publié un rapport et une présentation « Does Meta-Labeling Add to Signal Efficacy? » affirmant une amélioration des mesures de performance hors échantillon. — [Hudson & Thames, mise à jour de recherche](https://hudsonthames.org/?p=3448) ; [exemple jouet](https://hudsonthames.org/meta-labeling-a-toy-example/)
- Chiffre vu dans un résultat de recherche (source exacte non confirmée) : rapport rendement/risque d'une stratégie de 0,36 sans méta-étiquetage, 0,74 avec, 0,83 avec sélection de variables. Man & Chan (arXiv 2005.12483) montrent que la sélection de variables (MDA, LIME, SHAP) sur forêts aléatoires « améliore significativement diverses mesures prédictives hors échantillon » sur données synthétiques, publiques et d'une stratégie réelle. — [arXiv 2005.12483](https://arxiv.org/abs/2005.12483) (le chiffre 0,36 -> 0,83 n'y a pas été confirmé dans le résumé)
- Mécanisme : modèle primaire à fort rappel (prend beaucoup de signaux), méta-modèle binaire qui prédit lesquels sont de vrais positifs -> précision accrue, rappel préservé. — [Jesse, documentation méta-étiquetage](https://docs.jesse.trade/docs/research/ml/meta-labeling)

### Inferences
- Pièges connus (inférence à partir de la littérature López de Prado et du constat du projet) : (1) chevauchement des étiquettes (les coups se recouvrent dans le temps) -> il faut une validation « purgée » avec embargo, sinon fuite d'information ; (2) si le primaire n'a pas d'avantage, filtrer ne fait que réduire le nombre de coups ; (3) le méta-modèle doit être jugé en argent après frais, pas en précision. C'est exactement ce que le projet a vécu avec son « juge » calibré mais non rentable : la calibration ne garantit pas la rentabilité.
- Utilisation la plus raisonnable pour le projet : appliquer le méta-étiquetage à la seule stratégie qui a tenu hors échantillon (cassure 24 h du bitcoin) pour décider de la TAILLE (pas de la direction), avec validation purgée et correction du nombre d'essais.

### Gaps
- Aucune étude indépendante (hors Hudson & Thames) avec un rapport rendement/risque hors échantillon après frais n'a été trouvée.
- Série d'articles Joubert / Meyer / Thumbran (Journal of Financial Data Science 2022-2023) : non lue directement (page Wikipédia inaccessible au moment de la recherche, erreur 404).

## 3. Prédiction supervisée des rendements (arbres boostés, réseaux) sur de grandes coupes transversales, et pourquoi la prédiction d'un seul actif échoue

### Takeaway
L'apprentissage automatique ajoute une vraie valeur pour CLASSER des milliers d'actions entre elles à horizon mensuel avec des centaines de caractéristiques (Gu-Kelly-Xiu) ; mais une grande partie de ce gain vient de petites actions difficiles à traiter et disparaît après frais si on ne les intègre pas dans l'optimisation. Sur un seul actif, en série temporelle, le rapport signal/bruit est si faible que les gains sont statistiquement nuls.

### Cited Findings
- Gu, Kelly, Xiu (RFS 2020) : arbres et réseaux de neurones sont les meilleurs ; gains économiques « importants », « dans certains cas doublant la performance des stratégies de régression de la littérature » ; gains attribués aux interactions non linéaires ; signaux dominants : variantes de momentum, liquidité, volatilité. — [NBER w25398](https://www.nber.org/papers/w25398)
- Avramov, Cheng, Metzker (Management Science 2023) : les signaux d'apprentissage profond tirent leur rentabilité des actions difficiles à arbitrer et des périodes de fortes limites à l'arbitrage ; exclure micro-capitalisations, entreprises en détresse ou épisodes de forte volatilité « atténue considérablement » la rentabilité. — [SSRN 3450322](https://papers.ssrn.com/abstract=3450322)
- Jensen, Kelly, Malamud, Pedersen (RFS, « Machine Learning and the Implementable Efficient Frontier ») : les prévisions d'apprentissage automatique ignorantes des frais s'appuient sur des caractéristiques fugaces de petites actions -> mauvais rendements nets ; la solution est d'apprendre directement les poids de portefeuille avec un objectif économique net de frais. — [SSRN 4187217](https://papers.ssrn.com/abstract=4187217)
- Rahimikia, Ni, Wang (2025, arXiv 2511.18578), ~18 millions d'observations hors échantillon 2001-2023, ~10 000 actions US : meilleur modèle CatBoost : R² hors échantillon -0,03 %, précision de direction 51,16 %, (portefeuille long-court quotidien, avant frais) rapport rendement/risque 6,79 et 46,5 %/an ; régression simple : précision 51,23 %. — [arXiv 2511.18578](https://arxiv.org/html/2511.18578v1)
- Série temporelle d'un seul actif : prévision des rendements à 20 jours de 5 grandes actions (AAPL, AMZN, GOOG, JPM, META, test 08/2024-02/2026) : gains contre la marche aléatoire « petits et épars », scores d'habileté de l'ordre de 0,001 ; significatifs dans seulement 2 cas sur 10. Les auteurs rappellent que la croissance logarithmique maximale atteignable par n'importe quel couple prévision-stratégie avant frais est « correspondamment petite ». — [arXiv 2606.27100](https://arxiv.org/html/2606.27100)

### Inferences
- Les « Sharpe 6,79 » de type Rahimikia sont des portefeuilles quotidiens long-court équipondérés sur ~10 000 actions avant frais : avec précision 51 %, cela ne marche que grâce à la diversification sur des milliers de paris indépendants par jour ; sur 1 à 45 marchés FTMO corrélés, la même précision de 51 % ne donne rien après frais. C'est cohérent avec le constat du projet (~51 % sur 2020-2022, aucun avantage net).
- Ordre de grandeur utile : la loi « fondamentale » de la gestion active (rapport ≈ habileté × racine du nombre de paris indépendants) explique pourquoi la largeur compte plus que la précision (inférence, non sourcée ici).
- Pour un particulier, l'horizon où l'apprentissage automatique est le plus documenté (mensuel, coupe transversale d'actions, données comptables) n'est pas accessible via FTMO (pas de milliers d'actions à faible coût ; FTMO offre surtout des CFD sur indices, devises, matières premières, quelques actions).

### Gaps
- Chiffres exacts de Gu-Kelly-Xiu (R² mensuel hors échantillon ~0,4 %, rapport rendement/risque long-court) non confirmés par une source lue dans cette session.
- Jensen-Kelly-Malamud-Pedersen : chiffres de rendement net non extraits.
- Pas trouvé d'étude rigoureuse ML sur coupe transversale de contrats à terme / devises (style « momentum transversal » appris) dans le temps imparti.

## 4. Texte et sentiment des nouvelles avec des modèles LOCAUX (FinBERT, petits modèles de langage quantifiés sur 6 Go)

### Takeaway
L'effet est réel et bien documenté sur les ACTIONS US individuelles (nouvelles d'entreprise, horizon 1 jour), mais il décroît rapidement avec l'adoption des modèles de langage, il est concentré dans les petites actions (peu tradables) et il est sensible aux frais ; les modèles locaux de taille BERT/FinBERT captent une partie du signal. Pour des CFD sur indices/devises/or, aucune preuve comparable n'a été trouvée.

### Cited Findings
- Lopez-Lira & Tang (version arXiv v6) : période 10/2021 à 12/2023 ; stratégie long-court sur scores ChatGPT-4 : plus de 650 % cumulés avant frais (0,38 %/jour), >300 % avec 5 points de base de frais, ~150 % avec 10 points de base ; rapport rendement/risque annuel par modèle : GPT-4 3,28, GPT-3.5 1,79, DistilBart-MNLI 1,61, BART-Large 1,24, BERT-Large 1,12, GPT-1/GPT-2/BERT négatifs. — [ar5iv 2304.07619](https://ar5iv.labs.arxiv.org/html/2304.07619)
- Décroissance : le rapport rendement/risque de la stratégie ChatGPT tombe de 6,54 (fin 2021) à 3,68 (2022) puis 2,33 (2023) ; la théorie des auteurs prédit que la prévisibilité s'affaiblit à mesure que plus d'investisseurs utilisent ces modèles. — [ar5iv 2304.07619](https://ar5iv.labs.arxiv.org/html/2304.07619) ; [arXiv 2304.07619](https://arxiv.org/pdf/2304.07619)
- Petites actions : coefficient plus de 6 fois plus grand sous le 10e percentile de taille NYSE (0,688 contre 0,102) ; prévisibilité plus forte pour les mauvaises nouvelles (limites à l'arbitrage). — [ar5iv 2304.07619](https://ar5iv.labs.arxiv.org/html/2304.07619) ; [arXiv v4](https://arxiv.org/abs/2304.07619v4)
- Kirtac & Germano (Finance Research Letters 2024), 965 375 articles 2010-06/2023 : précision OPT (GPT-3) 74,4 %, BERT 72,5 %, FinBERT 72,2 %, dictionnaire Loughran-McDonald 50,1 % ; rapport rendement/risque long-court : OPT 3,05, BERT 2,11, FinBERT 2,07, dictionnaire 1,23. Pas d'analyse des frais ni du biais d'anticipation dans le résumé. — [arXiv 2412.19245](https://arxiv.org/abs/2412.19245)
- LLaMA-2 adapté à la finance : rendements de stratégie supérieurs à FinBERT ; la prévisibilité de FinBERT s'efface en marché agité, celle de LLaMA-2 tient. — [ScienceDirect, Pacific-Basin Finance Journal](https://www.sciencedirect.com/science/article/abs/pii/S0927538X24003846)
- Biais d'anticipation : Glasserman & Lin (2023) : quand la période de test chevauche l'entraînement du modèle de langage, deux biais : connaissance des rendements futurs et « distraction » (connaissance générale de l'entreprise) ; en échantillon, les titres anonymisés font MIEUX, donc la distraction pèse plus que l'anticipation, surtout pour les grandes entreprises ; hors échantillon, seule la distraction subsiste. — [arXiv 2309.17322](https://arxiv.org/html/2309.17322v1)
- Un banc d'essai dédié au biais d'anticipation des modèles de langage en finance existe désormais (Look-Ahead-Bench, 2026). — [arXiv 2601.13770](https://arxiv.org/pdf/2601.13770)

### Inferences
- Faisabilité matérielle : FinBERT (~110 M paramètres) tourne sans problème sur une GTX 1060 6 Go (inférence de milliers de titres par minute) ; un modèle de 7-8 milliards de paramètres quantifié en 4 bits (~4-5 Go) tient en mémoire mais lentement (ordre de quelques secondes par titre) : suffisant pour un flux de nouvelles quotidien, pas pour la haute fréquence. (Inférence technique, non sourcée ici.)
- Le signal publié est un signal ACTIONS individuelles à 1 jour, surtout petites capitalisations et mauvaises nouvelles : précisément ce qui n'est pas tradable sur un compte FTMO de CFD. Pour l'or, les devises et les indices, les nouvelles macro sont absorbées en secondes par les professionnels.
- Le chiffre « BERT-Large 1,12 » et « FinBERT 2,07 » montre qu'un petit modèle local récupère une partie du signal, mais la décroissance 6,54 -> 2,33 en deux ans suggère qu'en 2026 ce qui reste est faible, et ces chiffres sont avant frais réalistes d'un particulier.
- Toute évaluation maison doit se faire sur des nouvelles postérieures à la date de coupure du modèle de langage utilisé, et avec anonymisation.

### Gaps
- Aucune étude trouvée sur le sentiment de nouvelles avec modèle local appliqué à l'or, aux devises ou aux indices avec frais réalistes.
- Pas de mesure publiée de la décroissance après 2023 (2024-2026) trouvée.
- Données de nouvelles gratuites et horodatées à la seconde : disponibilité non vérifiée.

## 5. Modèles de fondation pour séries temporelles (Chronos, TimesFM, Moirai, Lag-Llama, TimeGPT) sur rendements financiers

### Takeaway
Utilisés tels quels, ils ne prédisent pas les rendements mieux que la marche aléatoire (gains de l'ordre de 0,1 %, rarement significatifs) et sont souvent PIRES que des arbres boostés simples ; seuls des modèles préentraînés de zéro sur des milliards d'observations financières se rapprochent des références classiques. Pour la volatilité, un seul petit modèle bat de peu le HAR ; la plupart font pire.

### Cited Findings
- Rendements de 5 grandes actions, horizon 20 jours, test 08/2024-02/2026 : TimeGPT, TimesFM-2.5, Moirai-2.0, Chronos, Chronos-2 contre NBEATS, NHITS, PatchTST, iTransformer, KAN ; les modèles de fondation gagnent 8 tâches sur 10 entre modèles, mais contre la marche aléatoire le gain n'est significatif que 2 fois (Chronos sur AMZN, Moirai-2.0 sur GOOG), scores d'habileté ~0,001 ; aucun résultat de trading ni de frais ; conclusion : ce ne sont pas « des moteurs universels de rendement statistiquement fiable ». — [arXiv 2606.27100](https://arxiv.org/html/2606.27100)
- Rahimikia et al. 2025 (~10 000 actions US, 2001-2023) : en usage direct, Chronos (grand) R² -1,37 %, précision 51,05 %, 20,17 %/an (contre CatBoost 46,5 %/an) ; TimesFM (500 M) R² -2,80 %, précision 49,88 % (moins bien que le hasard), -1,47 %/an ; le réentraînement fin améliore peu ou dégrade ; préentraînés de zéro sur données financières : Chronos (petit) rapport rendement/risque 5,42, 36,84 %/an ; sur données mondiales (89 marchés, >2 milliards d'observations), précision 51,74 % contre 51,16 % pour CatBoost. Conclusion : « le préentraînement générique ne se transfère pas directement à la finance ». — [arXiv 2511.18578](https://arxiv.org/html/2511.18578v1) ; [modèles FinText sur Hugging Face](https://huggingface.co/FinText)
- Volatilité réalisée (50 actifs dont 5 devises et 5 contrats à terme) : TTM seul bat Log-HAR à tous les horizons (gain 1,3-1,8 %) ; Chronos-Bolt, Moirai, Lag-Llama, TimesFM 2.5, Toto, Sundial ont des pertes 1,038 à 1,532 fois celles du Log-HAR à au moins un horizon ; inclusion dans l'ensemble des meilleurs modèles : TTM 94-98 %, Log-HAR 86-90 %, la plupart des modèles de fondation 0-34 % ; « le choix de l'architecture compte plus que le choix fondation contre économétrie ». — [arXiv 2607.05291](https://arxiv.org/html/2607.05291v1)
- Banc d'essai FinVerse (2026) proposé pour une évaluation plus réaliste de la prévision financière. — [arXiv 2608.03259](https://arxiv.org/html/2608.03259v1) (non lu en détail)
- Kronos (Tsinghua, AAAI 2026), modèle de fondation spécialisé chandeliers financiers : existe, résultats non vérifiés indépendamment. — [Pebblous, résumé](https://blog.pebblous.ai/report/kronos-financial-foundation-model/en/)

### Inferences
- Les modèles TTM (~1-5 M paramètres), Chronos-Bolt petit, TimesFM tournent sur la GTX 1060 ; mais le seul usage justifié par les preuves est la prévision de VOLATILITÉ en complément d'un HAR (moyenne des deux), pas la direction.
- Préentraîner un modèle de fondation financier de zéro sur des milliards d'observations n'est pas à la portée d'une GTX 1060 dans un délai raisonnable ; les modèles FinText déjà préentraînés sont téléchargeables, mais leurs résultats sont sur actions quotidiennes en coupe transversale, pas sur 45 CFD.

### Gaps
- Aucune évaluation publiée trouvée de ces modèles sur rendements intrajournaliers de devises/or/indices avec frais.
- Kronos : pas de vérification indépendante hors échantillon trouvée.

## 6. Apprentissage par renforcement profond pour le trading

### Takeaway
Pour décider « acheter/vendre », les résultats publiés sont surtout des tests rétrospectifs optimistes souffrant de surapprentissage ; même les promoteurs (FinRL) en sont réduits à rejeter les agents à forte probabilité de surapprentissage. Là où l'apprentissage par renforcement a des preuves plus solides, c'est l'EXÉCUTION (découper un gros ordre) en simulateur de carnet d'ordres, ce qui ne concerne pas un petit compte.

### Cited Findings
- FinRL / Columbia : les travaux existants rapportent avec optimisme des profits en test rétrospectif « qui peuvent souffrir de faux positifs dus au surapprentissage » ; un chercheur peut être « chanceux » et obtenir un agent surappris. Méthode proposée : entraîner, estimer la probabilité de surapprentissage, rejeter les agents surappris. Test sur 10 cryptos du 01/05/2022 au 27/06/2022 (deux krachs) : les agents moins surappris font mieux que les plus surappris, que la pondération égale et que l'indice S&P. — [arXiv 2209.05559](https://arxiv.org/abs/2209.05559)
- Concours FinRL 2024 : données d'entraînement/validation et jeu hors échantillon retenu pour l'évaluation ; agents à forte probabilité de surapprentissage rejetés. — [arXiv 2504.02281](https://arxiv.org/pdf/2504.02281) ; [Wiley, AIE 2025](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/aie2.12004)
- Exécution optimale : dans un simulateur multi-agents (ABIDES), l'apprentissage par renforcement bat significativement TWAP sur le coût d'exécution (t = 4,52 et 4,75) ; une politique par imitation réduit le coût moyen de 86 % par rapport à TWAP (21,24 contre 148,65 points de base) en simulateur. — [arXiv 2411.06389](https://arxiv.org/pdf/2411.06389) ; [arXiv 2511.15262](https://arxiv.org/pdf/2511.15262)

### Inferences
- Le test FinRL « hors échantillon » de 8 semaines sur cryptos est trop court pour conclure ; le fait que la méthode de référence du domaine soit « rejeter les agents surappris » confirme le constat du projet (PPO apprend par cœur).
- L'apprentissage par renforcement a un sens quand l'environnement est connu et simulable fidèlement (exécution, gestion de taille sous contraintes FTMO connues), pas quand il doit découvrir un avantage de prédiction absent des données. L'avantage doit venir d'ailleurs ; l'apprentissage par renforcement ne fait au mieux que l'exploiter.
- Les résultats d'exécution sont en simulateur ; pour un compte FTMO de 100 000 $ l'impact de marché est négligeable, donc cet usage n'apporte presque rien.

### Gaps
- Aucune preuve publiée trouvée d'un agent d'apprentissage par renforcement de trading directionnel rentable en réel sur plusieurs années, après frais.

## 7. Bonnes pratiques contre le surapprentissage des tests rétrospectifs

### Takeaway
Les outils existent et sont gratuits : rapport rendement/risque « dégonflé » (corrige le nombre d'essais et la non-normalité), probabilité de surapprentissage du test rétrospectif (validation croisée combinatoire symétrique), longueur minimale de test, validation croisée purgée avec embargo. Le facteur clé est de COMPTER tous les essais faits, y compris ceux abandonnés.

### Cited Findings
- Rapport rendement/risque dégonflé (Bailey & López de Prado, JPM 2014) : corrige deux sources d'inflation, le biais de sélection par essais multiples et la non-normalité des rendements ; c'est un rapport « probabiliste » dont le seuil intègre l'ensemble des stratégies essayées. — [SSRN 2460551](https://papers.ssrn.com/abstract=2460551) ; [eScholarship](https://escholarship.org/content/qt2329p290/qt2329p290.pdf)
- Longueur minimale de test rétrospectif (Bailey, Borwein, López de Prado, Zhu) : évite de choisir une stratégie à fort rapport en échantillon mais nul ou négatif hors échantillon ; ne pas contrôler le nombre d'essais conduit à des attentes trop optimistes. — [SSRN 2507040](https://papers.ssrn.com/abstract=2507040) ; [outils, D. Bailey](https://www.davidhbailey.com/dhbpapers/overfit-tools-at.pdf)
- Application concrète de la probabilité de surapprentissage pour filtrer des agents d'apprentissage par renforcement (cryptos). — [arXiv 2209.05559](https://arxiv.org/abs/2209.05559)

### Inferences
- Avec des centaines de candidats évalués (cycles d'évolution AUREXIS, pistes testées pour COLLAPSAR), le seuil de rapport rendement/risque à franchir pour être crédible monte nettement ; la cassure bitcoin (~+0,5 %/mois après commissions) doit être jugée avec le nombre total de pistes essayées depuis septembre, pas seule.
- Les 12 mois cachés du projet et la démo réelle sont la meilleure protection ; le rapport dégonflé est un complément peu coûteux (quelques lignes de Python).

### Gaps
- Formule numérique du seuil (ex. rapport attendu maximal sous N essais ≈ racine de 2 ln N en unités d'écart-type) non citée depuis une source lue ici.
- Leçons des concours (Numerai, Jane Street sur Kaggle) non recherchées faute de temps : à couvrir si besoin.
