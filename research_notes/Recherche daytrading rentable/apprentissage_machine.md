# Apprentissage machine et apprentissage par renforcement pour le trading intrajournalier : ce qui marche vraiment (hors échantillon, après frais) et les erreurs classiques

Notes de recherche (15/10/2026). ~27 recherches/lectures. Les chiffres viennent des sources citées ; ce qui n'a pas pu être vérifié est rangé dans « Lacunes ».

---

## 1. Apprentissage profond sur le carnet d'ordres (DeepLOB, Sirignano-Cont, Kolm-Turiel-Westray) : précision, horizon, rentabilité après frais

### Takeaway
Le carnet d'ordres contient un vrai signal, stable dans le temps et commun à toutes les actions, mais seulement à des horizons de quelques secondes (1 à 2 changements de prix). Aucun de ces articles fondateurs ne montre un gain après frais ; quand on ajoute même 1 point de base (0,01 %) de frais, DeepLOB perd presque tout son capital dans une simulation.

### Cited Findings
- **Sirignano & Cont (Quantitative Finance 2019)** : ~1 000 actions NASDAQ, 01/2014 → 03/2017, « des milliards » de cotations ; cible = sens du prochain changement de prix moyen (en moyenne toutes les ~1,7 s) ; ~500 actions pour l'entraînement, ~500 pour le test — [ar5iv 1803.06917](https://ar5iv.arxiv.org/html/1803.06917)
- Le modèle « universel » (toutes actions mélangées) gagne ~10 points de précision par rapport aux modèles linéaires par action, et marche sur des actions jamais vues ; un modèle entraîné 01/2014–05/2015 garde sa précision jusqu'en 01–03/2017 (18+ mois hors échantillon). **Aucun calcul de rentabilité ni de frais** — [ar5iv 1803.06917](https://ar5iv.arxiv.org/html/1803.06917) ; [IDEAS/Quant. Finance](https://ideas.repec.org/a/taf/quantf/v19y2019i9p1449-1459.html)
- Les auteurs notent qu'avec un tel volume, même 1 % d'écart au-dessus de 50 % est statistiquement significatif (significatif ≠ rentable) — [ar5iv 1803.06917](https://ar5iv.arxiv.org/html/1803.06917)
- **DeepLOB (Zhang, Zohren, Roberts, IEEE Trans. Signal Processing 2019)** : réseau convolutif + LSTM sur le carnet ; testé sur le jeu FI-2010 et un an de cotations de la Bourse de Londres ; précision « remarquablement stable » et transfert à des titres non vus à l'entraînement — [arXiv 1808.03668](https://arxiv.org/abs/1808.03668)
- La simulation de trading d'origine de DeepLOB utilise le prix moyen **sans frais** ; des travaux ultérieurs notent que dans les carnets à petit pas de cotation et bruités, les prédictions ne se traduisent pas en signaux rentables — [résumé emergentmind DeepLOB](https://api.emergentmind.com/topics/deeplob)
- **T-KAN (arXiv 2601.02310, 2026)** sur FI-2010, horizon k=100 événements : avec 1,0 point de base de frais, DeepLOB finit à **-82,76 %** ; T-KAN à +132,48 % (F1 +19,1 % relatif). L'article décrit une « décroissance de l'avantage » : DeepLOB perd son pouvoir prédictif quand l'horizon s'allonge — [arXiv 2601.02310](https://arxiv.org/abs/2601.02310). (Résultat récent, un seul jeu de données ancien, non répliqué.)
- **Kolm, Turiel, Westray, « Deep order flow imbalance » (Mathematical Finance 2023)** : 115 actions NASDAQ ; les modèles nourris de **flux d'ordres** (variations du carnet, stationnaires) battent nettement ceux nourris de l'état brut du carnet ; horizon utile ≈ **deux changements de prix moyens** par action ; les actions « riches en information » sont mieux prédites ; des réseaux simples sur variables bien construites battent des architectures complexes sur données brutes — [CiteDrive / DOI 10.1111/mafi.12413](https://www.citedrive.com/en/discovery/deep-order-flow-imbalance-extracting-alpha-at-multiple-horizons-from-the-limit-order-book/)
- Le déséquilibre du flux d'ordres explique une part importante des variations de prix surtout quand la profondeur est faible ; utiliser les 3 premiers niveaux du carnet augmente le pouvoir explicatif — [Cont et al., Price impact of generalized OFI](https://arxiv.org/pdf/2112.02947)
- Étude du groupe d'Oxford (Transformers vs LSTM, trading électronique) : la note de Sharpe d'un LSTM tombe de 0,50 à 0,33 avec 2 points de base de frais (transformer : 0,55 → 0,54) — [arXiv 2309.11400](https://arxiv.org/pdf/2309.11400)

### Inferences
- Le signal du carnet vit à l'échelle de la seconde ; à cet horizon, le mouvement attendu est plus petit que l'écart achat/vente. Il sert surtout à **mieux exécuter** (choisir le moment d'entrer) ou à faire de la tenue de marché, pas à « deviner la direction » pour un trader de détail.
- Leçon transférable : des entrées stationnaires (variations, flux) généralisent mieux que des niveaux bruts, et un modèle commun à beaucoup de marchés peut battre des modèles spécialisés.
- Pour un compte FTMO sur MT5 (pas de carnet complet, latence de détail, écart payé), ces résultats ne sont pas directement exploitables.

### Gaps
- Chiffres exacts de précision de DeepLOB sur la Bourse de Londres (horizons k=20/50/100) non récupérés (PDF non lisible).
- Pas trouvé de test publié de DeepLOB / Sirignano-Cont avec frais réels sur données récentes et exécution réaliste (file d'attente, latence).
- Précision chiffrée exacte de Sirignano-Cont (le résumé ne donne que des écarts relatifs).

---

## 2. Apprentissage machine sur barres intrajournalières / journalières (actions, devises, contrats à terme, cryptos) : précision ~51-55 % et ce que ça donne après frais

### Takeaway
Les succès publiés les plus cités (LSTM / forêts aléatoires sur les actions du S&P 500) étaient forts avant 2010 et **ont disparu après frais depuis 2010**. Les gains rapportés sont souvent « avant frais ». Sur les cryptos, quelques études montrent des gains nets modestes (quelques points de base par jour). Le contraste mensuel (Gu-Kelly-Xiu) montre que l'apprentissage machine apporte surtout là où les frais pèsent peu.

### Cited Findings
- **Fischer & Krauss (European Journal of Operational Research 2018)**, LSTM sur les constituants du S&P 500, 1992–2015 : **0,46 %/jour et Sharpe 5,8 avant frais** ; nette surperformance 1992–2009, mais **depuis 2010 les gains semblent arbitrés : rentabilité autour de zéro après frais** ; les titres choisis sont très volatils avec un profil de retournement de court terme ; une simple règle de retournement fait 0,23 %/jour avant frais — [FAU discussion paper](https://iwf.rw.fau.de/files/2015/12/11-2017.pdf) ; [résumé](https://slogix.in/machine-learning/deep-learning-with-long-short-term-memory-networks-for-financial-market-predictions/)
- **Ghosh, Neufeld, Sahoo (Finance Research Letters, 2021)**, intrajournalier ouverture→clôture, S&P 500, 1993–2018 : 0,64 %/jour (LSTM) et 0,54 % (forêts aléatoires) **avant frais**, contre 0,41 % / 0,39 % pour la version Krauss — [arXiv 2004.10178](https://arxiv.org/abs/2004.10178)
- Un LSTM sur l'indice S&P 500 seul : +339,6 % cumulé, 19,5 %/an (2010–2018) **en ignorant les frais** (justifié par peu de trades) — [arXiv 1902.03125](https://arxiv.org/pdf/1902.03125)
- **Cryptos, arbitrage statistique (Fischer, Krauss, Deinert 2019)** : forêt aléatoire sur rendements passés de 40 cryptos, horizon 120 minutes (surperformer la médiane) : **7,1 points de base par jour hors échantillon après 15 points de base de frais par demi-aller** — [résumé via recherche, FAU](https://cris.fau.de/publications/216708387)
- Bitcoin, 3 312 règles techniques sur barres de 5 minutes : nombreuses règles significativement rentables même après correction pour le sur-test et frais ; combiner les règles par réseau de neurones fait mieux que chaque règle — [Journal of Finance and Data Science 2022, DOAJ](https://doaj.org/article/cfc09801314441198e3e1c92a3914e54)
- Bitcoin, données ordre par ordre regroupées en 5 minutes : frais très faibles (0,0003 %) ; quand le marché est calme, les mouvements ne couvrent pas les frais : **même avec de bonnes prédictions, on peut perdre de l'argent** — [arXiv 2010.07404](https://arxiv.org/pdf/2010.07404)
- Cryptos en journalier : ensemble LSTM/GRU, Sharpe hors échantillon après frais 3,23 et 3,12 (résultat à prendre avec prudence, une seule étude) — [résumé de recherche, Hull repository](https://hull-repository.worktribe.com/output/2328042)
- **Gu, Kelly, Xiu (Review of Financial Studies 2020)**, contraste **mensuel** sur actions US : arbres et réseaux de neurones les meilleurs grâce aux interactions non linéaires ; portefeuilles avec Sharpe annualisé > 2,0 ; signaux dominants = momentum, liquidité, volatilité — [AQR](https://www.aqr.com/Insights/Research/Journal-Article/Empirical-Asset-Pricing-via-Machine-Learning) ; [NBER w25398](https://www.nber.org/papers/w25398.pdf)

### Inferences
- Les « 51-55 % de bonnes prédictions » ne suffisent pas : ce qui compte est **gain moyen par trade / frais par trade**. À 52 % de réussite avec gains et pertes égaux, l'avantage brut est ~4 % de la taille moyenne du mouvement ; si l'écart + commission représente plus de ~4 % du mouvement visé, l'avantage est nul. Plus l'horizon est court, plus les frais pèsent (c'est exactement ce qu'a mesuré COLLAPSAR : ~51-52 % sans avantage net après frais).
- Le cas Fischer-Krauss est la leçon type : un vrai signal (retournement de court terme) découvert par la machine, puis effacé par la concurrence après publication/diffusion.
- Les succès nets publiés ont en commun : beaucoup d'actifs en même temps (classement relatif, pas direction absolue), frais explicitement modélisés, horizon de plusieurs heures à plusieurs jours.

### Gaps
- **Krauss, Do, Huck (EJOR 2017)** (réseaux profonds, arbres boostés, forêts sur S&P 500, 1992–2015) : chiffres exacts non récupérés (de mémoire ~0,45 %/jour avant frais pour l'ensemble, décroissant après 2001 — **non vérifié**).
- Peu d'études crédibles sur **devises en intrajournalier** avec frais et validation glissante trouvées dans ce temps imparti.
- Chiffres exacts de Gu-Kelly-Xiu (R² hors échantillon ~0,4 %/mois, Sharpe long-court) non vérifiés dans la source.

---

## 3. Apprentissage par renforcement pour le trading : contrats à terme, FinRL, TDQN, tenue de marché, exécution optimale, critiques

### Takeaway
L'apprentissage par renforcement a des succès solides là où **le problème est bien défini et le simulateur fidèle** : exécution optimale (+50 % d'amélioration, Nevmyvaka-Feng-Kearns 2006) et tenue de marché (écart connu, gestion du stock). Pour « deviner la direction », le meilleur résultat sérieux (Zhang-Zohren-Roberts 2020) est en **journalier sur 50 contrats à terme**, avec frais, et ressemble à un suivi de tendance amélioré. Beaucoup d'autres résultats (FinRL, TDQN) sont fragiles et souffrent de sur-ajustement.

### Cited Findings
- **Zhang, Zohren, Roberts, « Deep RL for Trading » (J. Financial Data Science 2020)** : 50 contrats à terme liquides (matières premières, indices, taux, devises), **données journalières** 2005–2019, réentraînement tous les 5 ans, hors échantillon 2011–2019, frais 2 points de base, récompense ajustée à la volatilité. Sharpe : DQN 1,29, A2C 1,05, PG 0,75 contre achat seul 0,06, signe du rendement passé (momentum) 0,44, MACD 0,09. DQN et A2C restent positifs jusqu'à **25 points de base de frais**. Points faibles : périodes à forte tendance où l'achat simple suffit (indices actions) ; A2C trade trop (frais) — [ar5iv 1911.10107](https://ar5iv.labs.arxiv.org/html/1911.10107)
- **Nevmyvaka, Feng, Kearns (ICML 2006)** : premier usage à grande échelle de l'apprentissage par renforcement pour l'exécution optimale, 1,5 an de données carnet NASDAQ à la milliseconde ; **amélioration de 50 % ou plus** du coût d'exécution par rapport à la politique « placer et laisser » ; astuce : décomposition de l'état à « faible impact » (temps restant, quantité restante, variables de marché) — [UPenn Kearns](https://www.cis.upenn.edu/~mkearns/papers/rlexec) ; [ICML 2006](https://mlanthology.org/icml/2006/nevmyvaka2006icml-reinforcement)
- **Spooner et al. (AAMAS 2018)**, tenue de marché : simulateur haute fidélité du carnet, apprentissage par différence temporelle, récompense qui pénalise le stock détenu ; bat des stratégies simples et une méthode d'apprentissage en ligne — [arXiv 1804.04216](https://arxiv.org/abs/1804.04216v1). Des réseaux Q récurrents font mieux que Spooner en simulation — [CBS research](https://research.cbs.dk/en/publications/deep-recurrent-q-networks-for-market-making/) ; tenue de marché par renforcement sur cryptos réelles avec données tick + signal périodique : meilleure rentabilité et gestion du risque que les méthodes existantes — [arXiv 2306.17179](https://arxiv.org/abs/2306.17179v1)
- **Théate & Ernst, TDQN (Expert Systems with Applications 173, 2021)** : adaptation de DQN maximisant le Sharpe, entraînement sur **trajectoires artificielles** générées à partir d'un historique limité ; propose une méthode d'évaluation plus rigoureuse ; résultats décrits comme « prometteurs » — [arXiv 2004.06627](https://arxiv.org/abs/2004.06627)
- Critique : les travaux de renforcement profond « rapportent avec optimisme » des profits en test historique qui peuvent être des faux positifs dus au sur-ajustement. Méthode proposée (FinRL / cryptos, 10 cryptos, 05–06/2022 avec deux krachs) : tester l'hypothèse de sur-ajustement et **rejeter les agents sur-ajustés** ; les agents moins sur-ajustés ont un meilleur Sharpe que les plus sur-ajustés, qu'un portefeuille équipondéré et que l'indice S&P DBM — [arXiv 2209.05559](https://arxiv.org/abs/2209.05559v1)
- Forex par renforcement (2026) : article consacré à la décomposition de la récompense et à un **environnement réaliste** (frais, exécution) comme condition préalable — [arXiv 2604.00031](https://arxiv.org/pdf/2604.00031)

### Inferences
- Ce qui a fait marcher le renforcement : (1) une **source d'avantage connue d'avance** (l'écart encaissé en tenue de marché, le coût d'impact à réduire en exécution, la tendance de fond pour Zhang et al.) ; (2) un simulateur où l'action de l'agent n'altère pas le futur de façon irréaliste ; (3) récompense ajustée au risque/à la volatilité et frais dans la récompense. Le renforcement **optimise une façon de trader un avantage existant** ; il ne crée pas l'avantage.
- Zhang et al. est quotidien, pas intrajournalier : c'est un argument pour que COLLAPSAR exploite d'abord la tendance de fond multi-marchés (cohérent avec les mesures d'AUREX : seule source d'avantage mesurée = tendance de fond).
- Le constat interne du projet (longs entraînements PPO → l'IA ne trade plus ou trade n'importe comment) est cohérent avec la littérature : sans avantage dans les données, le renforcement converge vers « ne rien faire » ou sur-ajuste.

### Gaps
- Chiffres de Sharpe de TDQN par action et période exacte (de mémoire : 30 actions, données journalières 2012–2019, résultats mitigés selon les titres — **non vérifié**).
- Aucune preuve trouvée d'un agent de renforcement directionnel intrajournalier publié avec résultats réels audités après frais.

---

## 4. Bonnes méthodes : López de Prado, Bailey et al., étiquetage triple barrière, méta-étiquetage, validation purgée, Sharpe dégonflé, volatilité vs direction

### Takeaway
Le consensus des praticiens : l'apprentissage machine marche mieux comme **filtre/dimensionneur** d'une stratégie qui a déjà une raison d'être (méta-étiquetage), avec des étiquettes qui suivent le chemin du prix (stop / objectif / temps maximum), une validation qui empêche les fuites, et une correction pour le nombre d'essais. La prévision de **volatilité** est beaucoup plus facile et fiable que la prévision de direction.

### Cited Findings
- López de Prado (« The 10 reasons most ML funds fail », J. Portfolio Management 2018) — pièges listés : chercheurs isolés au lieu d'une « usine de recherche » ; différenciation entière (perte de mémoire, proposer la différenciation fractionnaire) ; échantillonnage par le temps au lieu de barres d'information (volume, montant échangé) ; **mauvais étiquetage à horizon fixe** au lieu d'étiquettes qui tiennent compte du chemin du prix ; échantillons non indépendants à pondérer ; **fuites dans la validation croisée** (purger les observations dont les étiquettes chevauchent le test) ; **sur-ajustement du test historique** (Sharpe dégonflé) — [Quantpedia](https://quantpedia.com/why-machine-learning-funds-fail/)
- La « famille » de méthodes : barres d'information, triple barrière, méta-étiquetage, unicité des échantillons, validation K-fold purgée, validation combinatoire purgée, Sharpe dégonflé, probabilité de sur-ajustement du test historique — [Quantpedia](https://quantpedia.com/why-machine-learning-funds-fail/) ; [tradingstrategy.ai](https://tradingstrategy.ai/docs/learn/backtesting.html)
- **Sharpe dégonflé (Bailey & López de Prado 2014)** : corrige le Sharpe pour le biais de sélection quand on a essayé beaucoup de stratégies, et pour les rendements non normaux (asymétrie, queues épaisses) ; donne la probabilité que le vrai Sharpe dépasse un seuil, sachant le nombre d'essais et la dispersion de leurs Sharpe — [tradingstrategy.ai](https://tradingstrategy.ai/docs/learn/backtesting.html)
- **Probabilité de sur-ajustement du test historique** : Bailey, Borwein, López de Prado, Zhu, J. Computational Finance 2017 — [tradingstrategy.ai](https://tradingstrategy.ai/docs/learn/backtesting.html)
- **Méta-étiquetage** : un second modèle estime la probabilité qu'un trade proposé par une stratégie principale soit gagnant ; sert à décider de le prendre et à fixer la taille ; vise à **augmenter la précision sans sacrifier le rappel** ; série d'articles de Joubert et coll. (Hudson & Thames) dans le Journal of Financial Data Science — [Wikipédia (via recherche)](https://en.wikipedia.org/wiki/Meta-Labeling) ; [Hudson & Thames](https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/embed/) ; [Jesse docs](https://docs.jesse.trade/docs/research/ml/meta-labeling)
- **Volatilité** : Christensen, Siggaard, Veliyev (J. Financial Econometrics 2022) — l'apprentissage machine est compétitif et bat la famille HAR pour prévoir la variance réalisée des actions du Dow Jones, gains plus nets aux horizons longs, et sait exploiter des variables supplémentaires — [arXiv 2601.13014](https://www.arxiv.org/abs/2601.13014) ; nuance : « HARd to Beat » montre que des fenêtres glissantes bien choisies rendent le modèle HAR simple très difficile à battre — [arXiv 2406.08041](https://arxiv.org/html/2406.08041v1)

### Inferences
- Pour COLLAPSAR : (a) étiqueter les situations par **triple barrière** (stop, objectif, temps max) colle exactement à « décrire un coup » de la vision trader ; (b) un méta-modèle qui dit « prendre/ne pas prendre/quelle taille » au-dessus d'une idée simple (tendance de fond, cassure) est la voie la plus documentée ; (c) la prévision de volatilité pour **régler stop et taille** est un usage fiable de l'apprentissage machine, contrairement à la direction ; (d) toute sélection parmi de nombreux candidats (mille mondes, cimes) doit être corrigée par le Sharpe dégonflé / la probabilité de sur-ajustement.
- L'approche « réglage humain + filtre machine » est celle que les praticiens recommandent le plus ; elle est compatible avec l'idée d'une IA qui apprend si le filtre/le dimensionnement est appris et non codé en règle.

### Gaps
- Chiffres précis d'amélioration du Sharpe par méta-étiquetage dans la série Joubert et al. (JFDS 2022-2023) non récupérés (page Wikipédia en erreur 404 au moment de la lecture).
- Pas d'étude indépendante (hors Hudson & Thames) mesurant le méta-étiquetage en trading réel.

---

## 5. Données synthétiques / simulateurs de marché pour l'entraînement (GAN, multi-agents, randomisation) : preuve de transfert vers le marché réel

### Takeaway
Les simulateurs (ABIDES, générateurs GAN de carnets, « agent monde ») reproduisent de mieux en mieux les **faits stylisés** (queues épaisses, regroupement de volatilité, réaction du marché), mais je n'ai trouvé **aucune preuve publiée** qu'un agent de trading entraîné seulement sur données synthétiques gagne ensuite de l'argent net sur le marché réel. Le seul usage documenté avec succès est l'augmentation de données (TDQN) et les tests de robustesse.

### Cited Findings
- Stock-GAN : entraîné sur des ordres venant d'un simulateur multi-agents et d'un vrai marché ; but = générer des flux d'ordres réalistes — [U. Michigan](https://micl.engin.umich.edu/stories/generating-realistic-stock-market-data-for-deeper-financial-research)
- GAN conditionnel « agent monde » entraîné sur données agrégées réelles, intégré au simulateur ABIDES ; meilleure réactivité et réalisme (faits stylisés) que les travaux précédents ; motivation : les données par agent sont privées, donc difficile de calibrer des agents multiples — [arXiv 2110.13287](https://ar5iv.labs.arxiv.org/html/2110.13287) ; [arXiv 2210.09897](https://ar5iv.labs.arxiv.org/html/2210.09897)
- Usages annoncés des données générées : entraîner des modèles de prévision, calibrer des stratégies, tests de crise, tests historiques, détection d'anomalies (annoncés, pas démontrés sur gains réels) — [ar5iv 2110.13287](https://ar5iv.labs.arxiv.org/html/2110.13287)
- TDQN entraîne l'agent sur des **trajectoires artificielles** générées à partir d'un historique limité (augmentation de données) — [arXiv 2004.06627](https://arxiv.org/abs/2004.06627)
- Un réseau profond peut **reproduire** le comportement de traders adaptatifs dans un marché simulé de carnet d'ordres (preuve en simulation seulement) — [arXiv 1811.02880](https://arxiv.org/pdf/1811.02880)

### Inferences
- Un monde synthétique a des lois que le concepteur a choisies : l'agent apprend à trouver des avantages **de ce type**. Le transfert ne vaut que si les vrais marchés contiennent des lois similaires (tendance de fond, retour à la moyenne, regroupement de volatilité). L'école des mille mondes est donc utile pour apprendre la **méthode** (chercher l'avantage, gérer le risque, ne pas trader sans avantage) — pas pour apporter un avantage en soi. Le juge doit rester 100 % réel.
- La randomisation de domaine (beaucoup de mondes différents) est le bon principe pour éviter que l'agent mémorise un monde ; il manque la preuve en finance.

### Gaps
- Aucune étude trouvée mesurant le transfert « entraîné sur synthétique → rentable net sur réel » pour un agent directionnel.
- Pas d'information trouvée sur l'usage interne de simulateurs par les fonds (Man AHL, etc.) au-delà de l'exécution.

---

## 6. Apprentissage par imitation des décisions de traders experts

### Takeaway
Les travaux existent (clonage de comportement, renforcement inverse, combinaison imitation + renforcement) mais sont presque tous académiques, avec des « experts » souvent synthétiques (stratégies pré-construites). Défaut connu : le clonage pur ne sait pas se rattraper quand il sort des situations vues. Aucune preuve forte de rentabilité réelle après frais.

### Cited Findings
- Le clonage de comportement imite l'expert par apprentissage supervisé sans raisonner sur les conséquences ; quand l'agent dérive vers des situations jamais vues, il ne sait pas revenir vers les états démontrés — [arXiv 2105.03844](https://arxiv.org/pdf/2105.03844)
- Combinaison DQN « duel » + clonage de comportement pour imiter des « experts » d'investissement pré-construits tout en explorant ; renforcement inverse adversarial multi-experts avec contrôle du risque (2026) — [arXiv 2105.03844](https://arxiv.org/pdf/2105.03844) ; [arXiv 2608.15770](https://arxiv.org/pdf/2608.15770)
- FlowHFT : imitation de plusieurs stratégies expertes pour le trading haute fréquence selon les conditions de marché (en simulation) — [arXiv 2505.05784](https://arxiv.org/pdf/2505.05784)
- Clonage de stratégies à partir de relevés de trades par renforcement multi-agents — [NYCU](https://scholar.nycu.edu.tw/zh/publications/cloning-strategies-from-trading-records-using-agent-based-reinfor/)

### Inferences
- Imiter un trader n'apporte un avantage que si ce trader en a un (et la plupart des traders de détail n'en ont pas). L'imitation est utile comme **point de départ** (comportement sain, gestion du stop), puis à corriger par la récompense — c'est ce que le projet a déjà fait (« école par avis » : imitation puis récompense en laisse).
- Choisir des experts à l'historique long et vérifié (cf. mémoire `sources-maitres`) et filtrer ceux dont les gains sont réels après frais.

### Gaps
- Pas d'étude trouvée d'imitation de vrais traders humains rentables avec test hors échantillon et frais.

---

## 7. Erreurs classiques (biais d'anticipation, survivants, sur-test, frais, non-stationnarité, fuite d'étiquette, trop peu d'échantillons indépendants, mémorisation)

### Takeaway
Les échecs documentés tombent presque tous dans quelques pièges : frais absents ou trop faibles, fuites d'information entre entraînement et test, choix du meilleur parmi des centaines d'essais sans correction, et marchés qui changent (l'avantage disparaît après découverte).

### Cited Findings
- **Frais ignorés** : simulations DeepLOB d'origine sans frais ; -82,76 % avec 1 point de base — [emergentmind](https://api.emergentmind.com/topics/deeplob) ; [arXiv 2601.02310](https://arxiv.org/abs/2601.02310). Nombreux résultats LSTM rapportés « avant frais » — [arXiv 2004.10178](https://arxiv.org/abs/2004.10178) ; [arXiv 1902.03125](https://arxiv.org/pdf/1902.03125)
- **Non-stationnarité / disparition de l'avantage** : Fischer-Krauss, rentabilité ≈ 0 après frais depuis 2010 — [FAU](https://iwf.rw.fau.de/files/2015/12/11-2017.pdf) ; perte de pouvoir prédictif quand l'horizon s'allonge — [arXiv 2601.02310](https://arxiv.org/abs/2601.02310)
- **Sur-ajustement / sur-test** : profits de renforcement « optimistes », faux positifs — [arXiv 2209.05559](https://arxiv.org/abs/2209.05559v1) ; Sharpe dégonflé et probabilité de sur-ajustement comme remède — [tradingstrategy.ai](https://tradingstrategy.ai/docs/learn/backtesting.html)
- **Fuite d'étiquette dans la validation** (étiquettes qui se chevauchent dans le temps) et **échantillons non indépendants** — [Quantpedia](https://quantpedia.com/why-machine-learning-funds-fail/)
- **Significativité ≠ rentabilité** : avec des milliards de points, 51 % est significatif — [ar5iv 1803.06917](https://ar5iv.arxiv.org/html/1803.06917) ; bonnes prédictions mais mouvements trop petits pour couvrir les frais — [arXiv 2010.07404](https://arxiv.org/pdf/2010.07404)
- **Mauvaise référence** : en période de forte tendance, l'achat simple bat le renforcement (indices actions) — [ar5iv 1911.10107](https://ar5iv.labs.arxiv.org/html/1911.10107)
- **Trop de trades** : A2C trade trop et perd en rendement par trade — [ar5iv 1911.10107](https://ar5iv.labs.arxiv.org/html/1911.10107)

### Inferences
- Liste de vérification pour COLLAPSAR : frais réels par marché dans l'apprentissage ET dans la note ; validation purgée avec embargo entre périodes ; compter tous les essais (cimes, mondes, candidats) et dégonfler le Sharpe ; comparer à des références simples (achat seul, tendance de fond, hasard) ; mesurer le gain par trade en part des frais ; garder les 12 mois cachés intacts.
- Le biais des survivants touche surtout les actions (titres disparus) ; pour les marchés FTMO (devises, indices, métaux), le risque principal est plutôt les **contrats continus** (raccords des contrats à terme) et les écarts/frais historiques irréalistes.

### Gaps
- Pas de chiffre global trouvé sur la part des stratégies d'apprentissage machine publiées qui échouent en réel (les études de réplication en intrajournalier sont rares).
- Biais d'anticipation et biais des survivants : pas d'exemple chiffré récupéré dans ce lot de sources (bien connus, mais non sourcés ici).
