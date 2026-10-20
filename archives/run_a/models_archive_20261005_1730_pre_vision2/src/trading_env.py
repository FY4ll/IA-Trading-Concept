"""
trading_env.py
==============
L'environnement simulé dans lequel l'agent "vit" :
  Observer -> Décider -> Agir -> Mesurer le résultat -> (recommencer)

L'agent voit une fenêtre glissante de features de marché, choisit une position
(-1 short, 0 flat, +1 long), et reçoit une récompense qui dépend du PnL réalisé
ET du risque pris (drawdown), pas seulement du fait de "gagner" le trade.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces

from src.features import FEATURE_COLUMNS
from src.style_utils import base_timeframe
from src.memory_features import MemoryQuery
from src.risk_engine import (
    lots_from_risk, notional_lots, round_volume, tighten_stop_or_cancel, atr_stop_distance_pct,
    ATR_STOP_PCT_FLOOR as _RISK_ATR_STOP_PCT_FLOOR, ATR_STOP_PCT_CEILING as _RISK_ATR_STOP_PCT_CEILING,
)

# VERSION D'ENVIRONNEMENT (LOT 2, phase 1) : à incrémenter à CHAQUE changement
# de l'espace d'OBSERVATION ou d'ACTION (jamais pour un changement de
# comportement qui laisse ces espaces inchangés). Un modèle entraîné sous une
# version différente ne doit JAMAIS être chargé pour l'inférence live ni
# réutilisé comme warm start : le réseau peut se charger SANS ERREUR (même
# forme de tenseur par coïncidence), mais la SIGNIFICATION de chaque
# entrée/sortie a changé -- ça produirait des décisions silencieusement
# incorrectes plutôt qu'un crash visible. Voir env_version_matches ci-dessous
# et ses appelants (src/agent.py::TradingAgent.load/_warm_start,
# src/demo_trader.py::_scan_eligible_styles/_StyleRuntime.maybe_reload).
ENV_VERSION = 2


def env_version_matches(meta: dict) -> bool:
    """True si le meta.json d'un modèle correspond à la version d'environnement
    ACTUELLE (ENV_VERSION). Absence de la clé "env_version" (meta.json écrit
    avant l'introduction de ce mécanisme) = version 1 implicite -- rejetée
    automatiquement dès qu'ENV_VERSION > 1, sans cas particulier à gérer côté
    appelant."""
    return meta.get("env_version", 1) == ENV_VERSION


class EnvVersionMismatch(Exception):
    """Levée quand un modèle dont le meta.json indique un env_version
    différent d'ENV_VERSION est sur le point d'être chargé pour l'inférence
    (voir TradingAgent.load) -- jamais silencieux."""


class TradingEnv(gym.Env):
    metadata = {"render_modes": []}
    # Buckets de stop-loss par défaut, différenciés par style de trading
    # (`style` passé via env_kwargs) : un scalp M15/M30 évolue sur un bruit
    # de marché bien plus faible qu'un swing D1, donc les MÊMES distances de
    # stop n'ont pas de sens dans les deux cas -- un stop de 5% est énorme
    # pour du M15 (coupe rarement, encaisse un gros drawdown avant) et un
    # stop de 0.5% est du bruit pur en D1 (se déclenche presque toujours
    # avant que le mouvement attendu ait le temps de se dessiner).
    STOP_LOSS_BUCKETS_BY_STYLE = {
        "M15": [0.003, 0.005, 0.008, 0.012, 0.02],
        "M30": [0.003, 0.005, 0.008, 0.012, 0.02],
        "H1": [0.005, 0.01, 0.02, 0.03, 0.05],
        "H4": [0.005, 0.01, 0.02, 0.03, 0.05],
        "D1": [0.01, 0.02, 0.04, 0.07, 0.10],
    }
    # STOP-LOSS ATR (audit institutionnel, item 1 ; valeurs revues LOT 2
    # phase 3) : au lieu d'une fraction FIXE du prix (ci-dessus), le stop
    # devient un MULTIPLE de l'ATR courant -- un marché deux fois plus
    # volatil qu'hier doit avoir un stop deux fois plus large, sinon le stop
    # se déclenche sur du bruit pur.
    #
    # PAR STYLE (pas une échelle unique) : la justification initiale ("l'ATR
    # est déjà en unités de CHAQUE timeframe, donc la même échelle suffit")
    # s'est révélée FAUSSE une fois mesurée sur l'historique or réel --
    # calcul (médiane de ATR_14/prix par bougie sur tout l'historique
    # data/kaggle_gold/, voir le multiple qu'il fallait pour retomber sur
    # chaque ancien bucket % statique) :
    #   style | médiane ATR/prix | multiples IMPLICITES par les anciens % (médiane)
    #   M15   | 0.121%           | [2.5, 4.2, 6.6, 10.0, 16.6]
    #   M30   | 0.177%           | [1.7, 2.8, 4.5, 6.8, 11.3]
    #   H1    | 0.255%           | [2.0, 3.9, 7.8, 11.8, 19.6]
    #   H4    | 0.519%           | [1.0, 1.9, 3.9, 5.8, 9.6]
    #   D1    | 1.408%           | [0.7, 1.4, 2.8, 5.0, 7.1]
    # L'ancienne échelle unique [0.5, 1.0, 1.5, 2.5, 4.0] était donc BEAUCOUP
    # plus serrée que ce que les anciens buckets % représentaient réellement,
    # surtout sur les timeframes courtes (jusqu'à 4-5x trop serré en M15/H1).
    # Valeurs ci-dessous arrondies depuis ces multiples implicites (même
    # progression relative, cardinalité inchangée à 5 par style, pour ne
    # jamais changer la taille de `action_space` -- voir __init__).
    ATR_STOP_MULTIPLIERS_BY_STYLE = {
        "M15": [2.5, 4.0, 6.5, 10.0, 16.5],
        "M30": [1.5, 3.0, 4.5, 7.0, 11.0],
        "H1": [2.0, 4.0, 8.0, 12.0, 20.0],
        "H4": [1.0, 2.0, 4.0, 6.0, 10.0],
        "D1": [0.75, 1.5, 3.0, 5.0, 7.0],
    }
    # Bornes de sécurité : un ATR quasi nul (marché mort) ou aberrant (pic
    # de données) ne doit jamais produire un stop dégénéré (~0%, ou >15% du
    # prix -- une distance qui n'a plus de sens comme "stop", plus proche
    # d'un pari directionnel sans protection). Source UNIQUE (LOT 2, phase 2) :
    # src/risk_engine.py, partagée avec MT5Connector.
    ATR_STOP_PCT_FLOOR = _RISK_ATR_STOP_PCT_FLOOR
    ATR_STOP_PCT_CEILING = _RISK_ATR_STOP_PCT_CEILING

    # SPREAD SESSION/HEURE (audit institutionnel, item 2) : élargissement du
    # coût de transaction selon l'heure UTC de la bougie -- combiné de façon
    # MULTIPLICATIVE avec le facteur de volatilité déjà existant (voir
    # _effective_transaction_cost). Forme retenue : {nom: (heure_debut_incl,
    # heure_fin_excl, multiplicateur)} pour chaque bande horaire nommée, plus
    # une clé "default" (float, pas de tuple) pour tout le reste de la
    # journée. Bandes (UTC) :
    #   - "rollover" 21h-22h : élargissement de rollover (changement de jour
    #     de valeur), spread large chez la plupart des brokers.
    #   - "asian" 0h-7h : session asiatique, liquidité plus faible sur
    #     XAUUSD (paire dominée par Londres/New York).
    #   - "overlap" 13h-16h : chevauchement Londres/New York, la fenêtre la
    #     plus liquide de la journée -- POINT DE RÉFÉRENCE (1.0x, pas
    #     d'élargissement).
    #   - "default" 1.1x : reste de la journée (Londres seule ou NY seule
    #     hors chevauchement), légèrement au-dessus du 1.0x de référence.
    # Ces bandes/valeurs sont des estimations raisonnables, pas calibrées
    # sur un flux broker réel -- `session_spread_multipliers` (kwarg
    # __init__) permet de les remplacer entièrement (câblage config prévu
    # côté appelant).
    DEFAULT_SESSION_SPREAD_MULTIPLIERS = {
        "rollover": (21, 22, 2.5),
        "asian": (0, 7, 1.3),
        "overlap": (13, 16, 1.0),
        "default": 1.1,
    }
    # position, unrealized_pnl, pnl moyen mémoire, drawdown moyen mémoire --
    # nombre de valeurs hors-séquence ajoutées après la fenêtre glissante
    # aplatie (voir _get_obs). Valeur de BASE (voir __init__ : devient une
    # valeur d'INSTANCE, +1 quand `learn_stop_loss` est actif). Exposé ici
    # pour que src/agent.py puisse construire un extracteur de features
    # (LSTM) sans dupliquer ce nombre.
    EXTRA_DIM = 4

    def __init__(self, df, window_size=50, initial_balance=10000,
                 transaction_cost=0.0002, reward_type="risk_adjusted",
                 drawdown_penalty=2.0, max_position=1, feature_columns=None,
                 memory_snapshot=None, memory_top_k=5, continuous_action=False,
                 spread_volatility_multiplier=1.0, learn_stop_loss=False,
                 stop_loss_buckets=None, stop_loss_range=(0.003, 0.06),
                 giveback_ratio_threshold=0.4, giveback_penalty_coef=0.03,
                 friction_window=12, friction_penalty_coef=0.01, style=None,
                 atr_stop_loss=True, raw_atr=None,
                 session_spread_enabled=True, session_spread_multipliers=None,
                 symbol_spec=None, risk_pct=0.02, drawdown_tolerance=0.002,
                 inactivity_penalty_coef=0.0, randomize_start=False,
                 learn_take_profit=False, take_profit_rr_buckets=None,
                 max_stops_per_day=0, learn_order_type=False, limit_offsets_atr=None):
        super().__init__()
        # TYPE D'ORDRE APPRIS (05/10/2026, style "TRADER") : 4e dimension d'action = ordre au
        # MARCHÉ (décalage 0) ou LIMITE placée à `décalage x ATR` plus bas (achat) / plus haut (vente)
        # que la clôture, valable UNE bougie : remplie seulement si la bougie suivante l'atteint (au
        # prix limite, ou à l'ouverture si elle s'ouvre déjà au-delà), sans slippage ; sinon pas
        # d'entrée. Exige learn_take_profit (donc learn_stop_loss). Désactivé par défaut.
        self._learn_order_type_requested = bool(learn_order_type)
        self.learn_order_type = False   # activé plus bas seulement avec learn_take_profit (discret)
        self.limit_offsets_atr = [float(x) for x in (limit_offsets_atr or [0.0, 0.25, 0.5])]
        self.n_limit_orders = 0
        self.n_limit_filled = 0
        # PLAFOND DE STOP-OUTS PAR JOUR (prop firm, 04/10) : au-delà de N
        # clôtures par stop-loss dans la même journée UTC, plus aucune
        # OUVERTURE jusqu'au lendemain (les clôtures restent permises).
        # 0 = désactivé. Sans colonne "time", désactivé aussi.
        self.max_stops_per_day = int(max_stops_per_day or 0)
        self._stops_today = 0
        self._stops_day = None
        # POINT DE DÉPART ALÉATOIRE (29/09, bug réel trouvé en investiguant
        # pourquoi H1 restait bloqué à 0 trade sur 50+ cycles après son
        # reset, alors que D1 avait redémarré à trader en quelques cycles
        # seulement avec le même mécanisme de reset -- voir reset() plus
        # bas) : SANS `_segment_id_col` (cas normal, un seul symbole), reset()
        # plaçait TOUJOURS `current_step` au même endroit fixe
        # (`self.window_size`), jamais ailleurs. Avec `timesteps_per_cycle`
        # (6000, voir run_config_A.yaml) très inférieur au nombre de bougies
        # disponibles pour H1/M15/M30 (100k-150k, voir data.max_bars_by_style),
        # CHAQUE candidat entraîné voyait donc littéralement LA MÊME tranche
        # fixe des ~6000 premières bougies du dataset, cycle après cycle --
        # un problème déterministe, pas stochastique : si cette tranche
        # précise s'avère structurellement peu rentable à trader (period
        # calme/coûts de transaction > opportunité), AUCUNE mutation
        # d'hyperparamètre ne peut y échapper, puisque les données
        # d'entraînement ne varient jamais. D1 (peu de bougies au total)
        # n'était jamais concerné : ses 6000 pas couvrent déjà tout son
        # historique. `randomize_start=True` (opt-in, comportement d'origine
        # INCHANGÉ par défaut -- notamment pour backtester.py::evaluate_agent*
        # qui doit rester déterministe/reproductible fenêtre par fenêtre) fait
        # démarrer chaque épisode à un point aléatoire du dataset, exactement
        # comme le fait déjà la branche multi-actifs juste en dessous --
        # utilisé UNIQUEMENT par continuous_trainer.py pour l'environnement
        # d'ENTRAÎNEMENT (jamais pour l'évaluation walk-forward/mémoire
        # épisodique, qui doivent rester reproductibles).
        self._randomize_start = randomize_start
        # RISK_ENGINE PARTAGÉ (LOT 2, phase 2) : `symbol_spec` (voir
        # src/risk_engine.py::SymbolSpec) donne à l'environnement les mêmes
        # contraintes broker (pas de lot, minimum, stops_level...) que
        # MT5Connector -- None (défaut) = pas de simulation de
        # plancher/resserrement/annulation de lot (comportement d'origine,
        # l'environnement ne raisonne qu'en direction/intensité de position,
        # jamais en lots). Voir simulate_broker_sizing().
        self.symbol_spec = symbol_spec
        self.risk_pct = risk_pct
        self.df = df.reset_index(drop=True)
        self.window_size = window_size
        self.initial_balance = initial_balance
        self.transaction_cost = transaction_cost
        self.reward_type = reward_type
        self.drawdown_penalty = drawdown_penalty
        # ZONE MORTE DE DRAWDOWN (22/09, bug réel repéré en observant le
        # figement quasi total de H4/D1 sous stress -- voir _compute_reward) :
        # jusqu'ici `drawdown_penalty * drawdown` s'appliquait DÈS le premier
        # centime de creux, sans aucun seuil -- contrairement à la pénalité
        # "giveback" ci-dessous qui, elle, tolère jusqu'à
        # `giveback_ratio_threshold` avant de pénaliser. Or le pic d'équité
        # est mesuré au moment exact où l'agent est encore flat (juste avant
        # l'ouverture) : le tout premier tick défavorable après une entrée
        # (bruit normal, spread, exécution -- quasi inévitable même sur un
        # trade in fine gagnant) comptait donc déjà comme "drawdown" et
        # déclenchait la pénalité ×2 dès la première bougie. Résultat :
        # OUVRIR une position était structurellement pénalisé même quand la
        # décision était bonne, ce qui pousse vers "ne jamais s'exposer" --
        # amplifié quand la volatilité rend ce premier creux plus profond
        # (voir le scénario de stress "garch", 0 trade sur toute la fenêtre).
        # `drawdown_tolerance` (défaut 0.002, soit 0.2% d'équité) absorbe ce
        # bruit d'ouverture normal SANS réduire la protection contre un vrai
        # dérapage : la pénalité ne démarre qu'AU-DELÀ de ce seuil, voir
        # `max(0.0, drawdown - self.drawdown_tolerance)` dans _compute_reward
        # et _base_risk_adjusted_reward. Mettez à 0.0 pour l'ancien
        # comportement (pénalité dès le premier centime).
        self.drawdown_tolerance = drawdown_tolerance
        self.max_position = max_position
        # PILOTE "risk_adjusted_v2" (18/09, suite à l'analyse de churn --
        # 12/18 trades qui redonnent >=30% de leur pic flottant, plusieurs
        # retournements en 5 min, ~38% seulement d'une tendance nette captée)
        # -- ignorés par les autres reward_type, voir _compute_reward.
        # Calibrés par une petite recherche sur le champion M15 existant :
        # à ces seuils, le tiers de trades qui gardent le mieux leur pic
        # (giveback ratio moyen ~0.002) reçoit une pénalité nulle, le tiers
        # le plus problématique (giveback ratio moyen ~8.6 -- devient
        # carrément perdant après avoir été gagnant) reçoit une pénalité
        # nette et clairement non nulle.
        self.giveback_ratio_threshold = giveback_ratio_threshold
        self.giveback_penalty_coef = giveback_penalty_coef
        self.friction_window = friction_window
        self.friction_penalty_coef = friction_penalty_coef
        # PÉNALITÉ D'INACTIVITÉ (23/09, demande explicite -- constat : les
        # 4 styles actifs affichent tous une probabilité "flat" dominante
        # (51-74%) de façon persistante, alors même que le marché bouge
        # réellement -- voir le constat chiffré du 22/09 : +1.94% d'amplitude
        # sur XAUUSD la veille, largement raté). Cause structurelle trouvée
        # dans `_base_risk_adjusted_reward` : drawdown/giveback/friction
        # pénalisent tous une MAUVAISE décision de trading, mais AUCUN terme
        # ne pénalise l'ABSENCE de décision -- rester plat en permanence est
        # donc un point fixe "gratuit" (reward=0, jamais puni) que
        # l'optimisation peut préférer à un trade légitime mais incertain.
        # `inactivity_penalty_coef` (défaut 0.0, comportement d'origine
        # INCHANGÉ -- opt-in comme les autres réglages du projet) : petit
        # coût par pas de temps passé à plat, représentant le coût
        # d'opportunité de ne pas être exposé au marché. Volontairement
        # PETIT par rapport à friction_penalty_coef/giveback_penalty_coef
        # (qui ne s'activent que sur un comportement identifié comme
        # mauvais) puisque celui-ci s'applique à CHAQUE pas flat d'un
        # épisode entier (~6000 pas) -- un coefficient du même ordre de
        # grandeur forcerait un surtrading compulsif plutôt que de
        # simplement lever le biais vers l'inaction. Seuil à calibrer par
        # l'expérience ; 0 pour revenir au comportement d'origine.
        self.inactivity_penalty_coef = inactivity_penalty_coef
        self._peak_unrealized_pnl_pct = 0.0
        self._recent_position_changes = []  # historique borné à friction_window (booléens)
        # COÛT D'EXÉCUTION RÉALISTE : sur un instrument réel, le spread
        # bid/ask s'élargit fortement pendant les pics de volatilité
        # (annonces macro, flash moves) -- un coût de transaction FIXE
        # sous-estime systématiquement ce qu'il coûterait réellement de
        # trader dans ces moments, gonflant artificiellement les
        # performances de backtest par rapport à la démo/au réel.
        # `spread_volatility_multiplier` (>1) fait grimper le coût
        # jusqu'à ce facteur quand `volatility_regime` (déjà calculé dans
        # features.py, z-score de la volatilité récente) est élevé -- 1.0
        # = comportement d'origine (coût toujours fixe).
        self.spread_volatility_multiplier = spread_volatility_multiplier
        # `continuous_action=True` (voir agent.algo: SAC/TD3) : l'agent
        # apprend directement l'INTENSITÉ de la position dans [-1, 1], pas
        # juste sa direction -- pas de mapping vers {-1,0,1}. Nécessite un
        # algorithme à action continue (PPO reste discret).
        self.continuous_action = continuous_action

        # STOP-LOSS DÉCIDÉ PAR L'AGENT, PAS IMPOSÉ : `learn_stop_loss=True`
        # ajoute une DEUXIÈME dimension à l'action -- la distance de son
        # propre stop, pas une règle fixe extérieure. L'agent apprend, par
        # l'expérience (un stop trop serré coupe des mouvements qui
        # auraient été gagnants ; un stop trop large laisse filer une
        # perte), à choisir une distance adaptée au contexte -- exactement
        # ce qu'un trader fait, pas un robot qui applique toujours le même
        # pourcentage. Le stop est simulé de façon RÉALISTE : vérifié à
        # chaque bougie contre le PLUS HAUT/PLUS BAS réel (pas juste la
        # clôture), donc peut se déclencher AVANT la prochaine décision de
        # l'agent, comme chez un vrai broker.
        self.learn_stop_loss = learn_stop_loss
        # TAKE-PROFIT APPRIS, EN MULTIPLE DU RISQUE PRIS (30/09, demande
        # explicite -- "éviter l'all-in pour gagner 1 euro") : sur le même
        # principe que `learn_stop_loss` -- au lieu d'une distance de sortie
        # gagnante FIXE ou arbitraire, l'agent choisit un MULTIPLE de la
        # distance de stop qu'il vient LUI-MÊME de choisir (ex: 2.0 = viser
        # deux fois le risque prix en gain avant de sortir). Structure
        # DIRECTEMENT le ratio risque/récompense dans l'espace de décision :
        # un stop large (gros risque) ne peut produire qu'un take-profit
        # proportionnellement large, jamais un profit dérisoire pour un
        # risque énorme. Nécessite `learn_stop_loss=True` (le take-profit
        # n'a de sens QUE relatif à un stop choisi par l'agent -- jamais
        # combiné à un stop fixe externe). Ajoute une DIMENSION à l'action
        # (comme `learn_stop_loss` lui-même) -- CASSE la compatibilité
        # warm-start pour les champions déjà entraînés sans cette option
        # (voir le commentaire de `learn_stop_loss` ci-dessus, même
        # catégorie d'impact).
        self.learn_take_profit = learn_take_profit and learn_stop_loss
        self.take_profit_rr_buckets = (list(take_profit_rr_buckets) if take_profit_rr_buckets is not None
                                         else [1.0, 1.5, 2.0, 3.0])
        self.take_profit_price = None
        self.style = style
        # Discret (PPO) : une distance parmi ces choix, en fraction du prix.
        # Priorité : buckets explicites > défaut par style > défaut générique
        # (rétrocompatible avec les appels qui ne connaissent pas `style`).
        if stop_loss_buckets is not None:
            default_buckets = stop_loss_buckets
        elif base_timeframe(style) in self.STOP_LOSS_BUCKETS_BY_STYLE:
            default_buckets = self.STOP_LOSS_BUCKETS_BY_STYLE[base_timeframe(style)]
        else:
            default_buckets = [0.005, 0.01, 0.02, 0.03, 0.05]
        self.stop_loss_buckets = list(default_buckets)
        # Continu (SAC/TD3) : la 2e dimension de l'action ([-1,1]) est
        # mise à l'échelle linéairement sur cet intervalle.
        self.stop_loss_range = stop_loss_range
        self.stop_price = None

        # `feature_columns` permet d'utiliser un jeu de colonnes différent du
        # défaut (ex: fusion multi-timeframe avec des colonnes de contexte
        # supplémentaires comme "rsi_14_4H", "trend_signal_1D", etc.)
        if feature_columns is None:
            feature_columns = FEATURE_COLUMNS
        self.feature_columns = list(feature_columns)

        self.n_features = len(self.feature_columns)
        # index de la colonne de régime de volatilité, si présente dans ce
        # jeu de features (toujours le cas avec features.py -- absent
        # seulement pour un jeu de colonnes personnalisé) : None -> coût
        # de transaction toujours fixe, sans erreur.
        self._vol_regime_idx = (self.feature_columns.index("volatility_regime")
                                 if "volatility_regime" in self.feature_columns else None)
        # index de la colonne ATR (LOT 2, phase 4 : "atr_pct", la version
        # sans unité de "atr_14" -- voir src/features.py), si présente -- sert
        # UNIQUEMENT de garde-fou booléen ("ce déploiement inclut-il l'ATR
        # dans son observation ?"), jamais pour indexer une valeur de stop
        # (voir _atr_price_units/ATR_RAW_COLUMN, mécanisme séparé et
        # toujours en unités de prix brutes).
        self._atr_idx = (self.feature_columns.index("atr_pct")
                          if "atr_pct" in self.feature_columns else None)

        # STOP-LOSS ATR (item 1, suite) : `atr_14` tel qu'il arrive dans
        # self.feature_columns/self._feature_values est NORMALISÉ (z-score)
        # par le pipeline réel AVANT la construction de TradingEnv --
        # vérifié dans src/features.py::normalize_features et tracé dans
        # autonomous_agent.py::get_data (`train_df, stats =
        # normalize_features(train_df, columns=cache["cols"])`, où "atr_14"
        # fait partie de `cache["cols"]`) puis src/continuous_trainer.py qui
        # construit TradingEnv directement à partir de ce `train_df`/`val_df`
        # déjà normalisé. Une valeur z-scorée (centrée sur 0, souvent
        # négative) est ILLISIBLE comme distance en unités de prix -- on a
        # donc choisi l'option (a) documentée dans le brief d'audit : un
        # kwarg `raw_atr` SÉPARÉ, fourni par l'appelant à partir du
        # dataframe AVANT normalisation, aligné indice-pour-indice avec
        # `self.df`. Tant que l'appelant (continuous_trainer.py, hors
        # périmètre de ce fichier) ne le fournit pas, `atr_stop_loss` reste
        # actif mais retombe silencieusement sur les buckets STATIQUES
        # existants (voir _atr_stop_loss_active / step()) -- comportement
        # live inchangé jusqu'au câblage de `raw_atr` côté appelant, jamais
        # un calcul silencieusement faux à partir d'un ATR normalisé.
        self.atr_stop_loss = atr_stop_loss
        self._raw_atr = np.asarray(raw_atr, dtype=np.float64) if raw_atr is not None else None
        if self._raw_atr is not None and len(self._raw_atr) != len(self.df):
            raise ValueError(
                f"raw_atr a une longueur ({len(self._raw_atr)}) différente de "
                f"len(df) ({len(self.df)}) -- doit être aligné indice-pour-indice "
                "avec le dataframe (PRÉ-normalisation) passé à TradingEnv."
            )
        # Échelle de multiplicateurs ATR, dimensionnée pour correspondre
        # EXACTEMENT à `len(self.stop_loss_buckets)` (et donc à la forme de
        # `action_space`, déjà figée par ce nombre plus bas) -- y compris
        # dans le cas peu courant d'un `stop_loss_buckets` explicite d'une
        # longueur différente de 5 (voir test_explicit_stop_loss_buckets_
        # override_style_default) : tronqué si trop long, dernière valeur
        # répétée si trop court, jamais un décalage d'index silencieux entre
        # l'action choisie et le bucket qu'elle sélectionne réellement.
        _generic_atr_multipliers = [0.5, 1.0, 1.5, 2.5, 4.0]
        _atr_multipliers = list(self.ATR_STOP_MULTIPLIERS_BY_STYLE.get(base_timeframe(style), _generic_atr_multipliers))
        _n_buckets = len(self.stop_loss_buckets)
        if len(_atr_multipliers) >= _n_buckets:
            self.atr_stop_multipliers = _atr_multipliers[:_n_buckets]
        else:
            self.atr_stop_multipliers = _atr_multipliers + [_atr_multipliers[-1]] * (_n_buckets - len(_atr_multipliers))
        # Buckets EFFECTIVEMENT utilisés par step() pour interpréter l'action
        # discrète -- recalculés chaque pas si l'ATR dynamique est actif
        # (voir _atr_stop_loss_active), sinon reste égal à self.stop_loss_buckets
        # (comportement d'origine). Initialisé ici pour que la forme soit
        # toujours valide même avant le premier step().
        self._current_stop_loss_buckets = list(self.stop_loss_buckets)

        # SPREAD SESSION/HEURE (item 2) : voir DEFAULT_SESSION_SPREAD_MULTIPLIERS.
        # `self._hour_of_day` est None (donc facteur toujours neutre, 1.0)
        # si `self.df` n'a pas de colonne "time" -- cas des tests/contextes
        # qui construisent un TradingEnv à partir de features seules, sans
        # horodatage ; ne doit JAMAIS lever d'erreur dans ce cas.
        self.session_spread_enabled = session_spread_enabled
        self.session_spread_multipliers = (session_spread_multipliers
                                            if session_spread_multipliers is not None
                                            else self.DEFAULT_SESSION_SPREAD_MULTIPLIERS)
        self._hour_of_day = (pd.to_datetime(self.df["time"]).dt.hour.to_numpy()
                              if "time" in self.df.columns else None)
        self._day_id = (pd.to_datetime(self.df["time"]).dt.normalize().astype("int64").to_numpy()
                        if self.max_stops_per_day > 0 and "time" in self.df.columns else None)

        # Snapshot numpy des colonnes de features, calculé UNE SEULE FOIS ici
        # plutôt que reconstruit par un `.iloc[...].values` à chaque appel de
        # _get_obs/_effective_transaction_cost (potentiellement des millions
        # de fois sur un entraînement long) -- accès en lecture seule pour
        # éviter toute mutation accidentelle d'un array partagé.
        self._feature_values = self.df[self.feature_columns].to_numpy(dtype=np.float32)
        self._feature_values.setflags(write=False)

        # PRIX BRUTS PRÉ-EXTRAITS (tâche d'optimisation, audit institutionnel
        # section 7.C) : MÊME RAISONNEMENT que _feature_values ci-dessus --
        # profilage réel (cProfile sur un cycle d'entraînement complet)
        # a confirmé que `pandas.core.internals.managers.fast_xs` (l'accès
        # ligne-par-ligne `self.df.iloc[i]`, utilisé auparavant pour lire
        # open/high/low/close/cost_multiplier/slippage_price_offset/l'ATR
        # brut À CHAQUE PAS) représentait ~9.6% du temps total d'un cycle,
        # au-dessus du seuil de 5% retenu -- largement plus que le coût d'un
        # simple index numpy. Valeurs IDENTIQUES (même dtype float64 que
        # pandas stocke déjà en interne pour ces colonnes) : voir
        # tests/test_trading_env_perf.py pour la vérification numérique
        # stricte (np.allclose, rtol=1e-9) avant/après ce changement. None
        # pour les colonnes optionnelles absentes -- jamais une erreur.
        self._open = self.df["open"].to_numpy(dtype=np.float64)
        self._high = self.df["high"].to_numpy(dtype=np.float64)
        self._low = self.df["low"].to_numpy(dtype=np.float64)
        self._close = self.df["close"].to_numpy(dtype=np.float64)
        self._cost_multiplier_col = (self.df["cost_multiplier"].to_numpy(dtype=np.float64)
                                      if "cost_multiplier" in self.df.columns else None)
        self._slippage_price_offset_col = (self.df["slippage_price_offset"].to_numpy(dtype=np.float64)
                                            if "slippage_price_offset" in self.df.columns else None)
        self._atr_raw_col = (self.df[self.ATR_RAW_COLUMN].to_numpy(dtype=np.float64)
                              if self.ATR_RAW_COLUMN in self.df.columns else None)
        # FRONTIÈRES DE SEGMENT (LOT 2, phase 4, point 3 -- pipeline
        # multi-actifs, voir src/multi_asset.py::build_multi_asset_dataset) :
        # colonne optionnelle "segment_id" -- None si absente (comportement
        # D'ORIGINE inchangé, un seul dataframe continu, cas normal pour
        # l'entraînement mono-actif). Jamais dans feature_columns (jamais vue
        # par l'agent) -- sert uniquement à reset()/step() pour ne jamais
        # laisser un stop/PnL/récompense traverser une jointure entre deux
        # segments (potentiellement deux SYMBOLES différents).
        self._segment_id_col = (self.df["segment_id"].to_numpy()
                                  if "segment_id" in self.df.columns else None)
        self._spread_pct_col = (self.df["spread_pct"].to_numpy(dtype=np.float64)
                                  if "spread_pct" in self.df.columns else None)

        # MÉMOIRE ÉPISODIQUE COMME SIGNAL D'OBSERVATION : donne à l'agent
        # accès à "dans des situations de marché proches de celle-ci,
        # qu'ont obtenu mes versions précédentes ?" (voir
        # src/memory_features.py). Sans instantané fourni (mémoire encore
        # vide, ou début du tout premier cycle), le signal est neutre
        # (0.0, 0.0) : la taille de l'observation reste donc TOUJOURS la
        # même, avec ou sans mémoire disponible.
        self._memory = MemoryQuery(memory_snapshot, memory_top_k)

        if self.continuous_action:
            # action continue : intensité + direction en une seule valeur,
            # -1 = pleine position vendeuse, +1 = pleine position acheteuse.
            # +1 dimension (distance du stop) si learn_stop_loss. Le
            # take-profit appris (`learn_take_profit`) n'est PAS supporté en
            # continu pour l'instant (scope volontairement limité au cas
            # discret/PPO, voir demande explicite du 30/09) -- ignoré
            # silencieusement ici (pas d'erreur), jamais un décalage
            # d'action non documenté.
            n_dims = 2 if self.learn_stop_loss else 1
            self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(n_dims,), dtype=np.float32)
        elif self.learn_take_profit:
            # direction (3) x distance du stop x multiple de take-profit (x type d'ordre si appris).
            self.learn_order_type = self._learn_order_type_requested
            dims = [3, len(self.stop_loss_buckets), len(self.take_profit_rr_buckets)]
            if self.learn_order_type:
                dims.append(len(self.limit_offsets_atr))
            self.action_space = spaces.MultiDiscrete(dims)
        elif self.learn_stop_loss:
            # direction (3) x distance du stop parmi stop_loss_buckets.
            self.action_space = spaces.MultiDiscrete([3, len(self.stop_loss_buckets)])
        else:
            # 3 actions discrètes : 0 = short, 1 = flat, 2 = long
            self.action_space = spaces.Discrete(3)

        # +1 dimension d'observation (distance du stop actuel, 0.0 si flat)
        # quand l'agent choisit lui-même son stop -- il doit pouvoir voir
        # son propre risque en cours, pas seulement sa position.
        self.EXTRA_DIM = 4 + (1 if self.learn_stop_loss else 0)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(self.window_size * self.n_features + self.EXTRA_DIM,),
            dtype=np.float32,
        )
        self.reset()

    def _effective_transaction_cost(self) -> float:
        """Coût de transaction pour LE PAS COURANT : combine (multiplicativement)
        TROIS facteurs indépendants, chacun neutre (1.0) par défaut/absence :
          1. VOLATILITÉ (comportement d'origine) : élargi quand la volatilité
             récente (`volatility_regime`, z-score déjà normalisé) est
             au-dessus de sa moyenne, plafonné à `spread_volatility_multiplier`
             x le coût de base. Neutre si `volatility_regime` n'est pas dans
             les colonnes de features de cet environnement, ou si le
             multiplicateur est <= 1.0.
          2. SESSION/HEURE (item 2, audit institutionnel) : élargi selon
             l'heure UTC de la bougie courante (rollover, session asiatique
             peu liquide, etc. -- voir DEFAULT_SESSION_SPREAD_MULTIPLIERS).
             Neutre si `session_spread_enabled=False` ou si `self.df` n'a
             pas de colonne "time".
          3. CHOC MACRO (item 3, colonne optionnelle `cost_multiplier` de
             `self.df`, produite par src/stress_test.py::inject_macro_shocks
             -- JAMAIS une feature visible par l'agent, seulement son EFFET
             sur le coût). Neutre si la colonne est absente.
        `1.0 = coût toujours fixe` reste vrai quand LES TROIS facteurs sont
        neutres (comportement d'origine intégralement préservé).
        """
        vol_factor = 1.0
        if self._vol_regime_idx is not None and self.spread_volatility_multiplier > 1.0:
            vol_z = float(self._feature_values[self.current_step, self._vol_regime_idx])
            # 3 écarts-types au-dessus de la moyenne -> multiplicateur
            # maximal ; jamais réduit sous le coût de base même si la
            # volatilité est basse.
            vol_factor = 1.0 + max(0.0, vol_z) / 3.0 * (self.spread_volatility_multiplier - 1.0)
            vol_factor = min(self.spread_volatility_multiplier, vol_factor)

        session_factor = self._session_spread_factor()

        # COÛT PAR LIGNE (LOT 2, phase 4, point 4 -- pipeline multi-actifs) :
        # colonne optionnelle "spread_pct" (valeurs par symbole, voir
        # config `multi_asset.spread_pct_by_symbol`) remplace
        # `self.transaction_cost` comme coût DE BASE pour CE pas -- un
        # spread fixe unique n'a pas de sens en mélangeant des instruments
        # aux frictions très différentes (ex: EURUSD très liquide vs un
        # indice moins liquide). Neutre (comportement d'origine inchangé,
        # jamais utilisé en live mono-actif) si la colonne est absente.
        base_cost = (float(self._spread_pct_col[self.current_step])
                     if self._spread_pct_col is not None else self.transaction_cost)

        cost = base_cost * vol_factor * session_factor
        if self._cost_multiplier_col is not None:
            cost *= float(self._cost_multiplier_col[self.current_step])
        return cost

    def _session_spread_factor(self) -> float:
        """Multiplicateur de coût lié à l'heure UTC de la bougie COURANTE
        (voir DEFAULT_SESSION_SPREAD_MULTIPLIERS pour les bandes/valeurs) --
        1.0 (neutre, jamais d'erreur) si `session_spread_enabled=False` ou
        si `self._hour_of_day` est None (pas de colonne "time" dans
        `self.df`, cas des tests/contextes à features seules).
        """
        if not self.session_spread_enabled or self._hour_of_day is None:
            return 1.0
        hour = int(self._hour_of_day[self.current_step])
        for name, band in self.session_spread_multipliers.items():
            if name == "default":
                continue
            start, end, mult = band
            if start <= hour < end:
                return mult
        return self.session_spread_multipliers.get("default", 1.1)

    # Nom de colonne optionnelle sur `self.df` (PAS dans feature_columns,
    # donc jamais normalisée ni vue par l'agent) portant l'ATR en unités de
    # PRIX -- deuxième source possible pour `_atr_price_units`, ajoutée
    # après le constat que le kwarg `raw_atr` seul (aligné une fois à la
    # construction) se DÉSYNCHRONISE dès que le dataframe passé à un AUTRE
    # TradingEnv est un sous-découpage/réordonnancement du premier (fenêtres
    # walk-forward dans evaluate_agent_walkforward, scénarios de
    # src/stress_test.py) : le kwarg ne suit pas ces transformations, alors
    # qu'une colonne supplémentaire sur `self.df` SUIT AUTOMATIQUEMENT tout
    # `.iloc[...]`/concat/réordonnancement fait sur ce dataframe, exactement
    # comme `cost_multiplier`/`slippage_price_offset` le font déjà pour les
    # chocs macro. C'est donc la source RECOMMANDÉE pour tout appelant qui
    # construit potentiellement plusieurs TradingEnv à partir de dérivés
    # d'un même dataset (la quasi-totalité du pipeline réel) ; `raw_atr`
    # reste disponible pour un usage direct/ponctuel plus simple.
    ATR_RAW_COLUMN = "atr_14_raw"

    def _atr_price_units(self) -> float | None:
        """ATR en unités de PRIX pour le pas courant, ou None si aucune
        source fiable n'est disponible (voir commentaire dans __init__ sur
        pourquoi `self._feature_values[..., self._atr_idx]` -- normalisé en
        production -- n'est PAS utilisable ici). Priorité : kwarg `raw_atr`
        explicite (si fourni à la construction) > colonne `atr_14_raw` sur
        `self.df` (voir ATR_RAW_COLUMN, suit correctement tout sous-découpage
        du dataframe) > aucune source -> None (retombe sur les buckets
        statiques, voir _atr_stop_loss_active)."""
        if self._raw_atr is not None:
            return float(self._raw_atr[self.current_step])
        if self._atr_raw_col is not None:
            return float(self._atr_raw_col[self.current_step])
        return None

    @property
    def _atr_stop_loss_active(self) -> bool:
        """True si les buckets de stop doivent être recalculés dynamiquement
        comme des multiples de l'ATR courant plutôt que d'utiliser les
        buckets statiques (fraction fixe du prix, comportement d'origine).
        Nécessite `atr_stop_loss=True`, "atr_14" présent dans
        `feature_columns` (signal que ce déploiement est bien construit avec
        l'ATR disponible), ET un `raw_atr` fourni au constructeur -- sans
        cette dernière condition, retombe silencieusement sur les buckets
        statiques plutôt que d'utiliser un ATR normalisé (faux) ou de lever
        une erreur (système EN LIVE, ne doit jamais crasher pour ça).
        """
        return bool(self.atr_stop_loss and self._atr_idx is not None
                     and self._atr_price_units() is not None)

    def _compute_atr_stop_loss_buckets(self, price: float) -> list:
        """Buckets de stop-loss recalculés POUR CE PAS comme des MULTIPLES
        de l'ATR courant (`self.atr_stop_multipliers`, voir
        ATR_STOP_MULTIPLIERS_BY_STYLE), au lieu de fractions fixes du prix
        (`self.stop_loss_buckets`) : un stop de taille constante n'a pas de
        sens sur un actif dont la volatilité varie dans le temps -- le même
        stop est confortable en marché calme et se déclenche sur du bruit
        pur en marché agité.
        `atr_price_units * multiplier / price` convertit l'ATR (unités de
        prix, ex: dollars pour l'or) en fraction du prix courant, puis
        chaque valeur est bornée à [ATR_STOP_PCT_FLOOR, ATR_STOP_PCT_CEILING]
        pour ne jamais produire un stop dégénéré (ATR quasi nul ou aberrant).
        """
        # LOT 2, phase 2 : délègue à risk_engine.atr_stop_distance_pct (même
        # formule, partagée avec MT5Connector.send_order -- voir phase 3).
        atr_price_units = self._atr_price_units()
        return [atr_stop_distance_pct(atr_price_units, m, price, self.ATR_STOP_PCT_FLOOR, self.ATR_STOP_PCT_CEILING)
                for m in self.atr_stop_multipliers]

    def simulate_broker_sizing(self, equity: float, target_exposure: float, stop_pct: float | None,
                                 price: float, risk_pct_override: float | None = None):
        """Reproduit EXACTEMENT la hiérarchie de dimensionnement de
        MT5Connector.send_order (LOT 2, phase 2 : même risk_engine des deux
        côtés) : (1) risque réel/distance de stop, (2) repli notionnel/équité
        sans stop. Sans `self.symbol_spec` configuré (défaut), retourne
        (0.0, stop_pct, False) -- rien à plancher/resserrer sans contraintes
        broker connues, l'environnement continue de raisonner en
        direction/intensité pure (comportement d'origine).

        NE reproduit PAS le tout dernier repli `live.lot_size` de
        MT5Connector (un lot fixe de config) : c'est un concept propre au
        live, sans équivalent dans un environnement de simulation qui ne
        connaît pas cette config -- seuls les deux premiers échelons
        (risque/stop puis notionnel) sont partagés.

        Retourne (volume, stop_pct_effectif, cancel) -- `cancel=True` signifie
        que MT5 aurait refusé cet ordre (stop resserré sous le minimum
        broker) : voir tests/test_risk_parity.py pour la preuve d'égalité
        avec MT5Connector sur une grille d'entrées.
        """
        if self.symbol_spec is None:
            return 0.0, stop_pct, False
        risk_pct = risk_pct_override if risk_pct_override is not None else self.risk_pct
        max_lots = lots_from_risk(equity, risk_pct, price, stop_pct, self.symbol_spec.contract_size)
        sizing_by_risk = max_lots > 0
        if not sizing_by_risk:
            max_lots = notional_lots(equity, price, self.symbol_spec.contract_size)
        if max_lots <= 0:
            return 0.0, stop_pct, False
        raw_volume = abs(target_exposure) * max_lots
        target_direction = 0 if abs(target_exposure) < 1e-9 else (1 if target_exposure > 0 else -1)
        volume = round_volume(raw_volume, self.symbol_spec, floor_if_positive=(target_direction != 0))
        effective_stop_pct = stop_pct
        cancel = False
        if sizing_by_risk and effective_stop_pct is not None and volume > raw_volume > 0:
            effective_stop_pct, cancel = tighten_stop_or_cancel(
                raw_volume, volume, effective_stop_pct, equity, price, risk_pct, self.symbol_spec)
        return volume, effective_stop_pct, cancel

    @staticmethod
    def _apply_slippage(price: float, offset: float, is_buy: bool) -> float:
        """Applique `slippage_price_offset` (item 3, toujours en unités de
        PRIX, toujours DÉFAVORABLE au trader -- jamais une amélioration de
        prix) : un ordre ACHETEUR (ouverture long / clôture short) exécute
        PLUS CHER (+offset), un ordre VENDEUR (ouverture short / clôture
        long) exécute MOINS CHER (-offset). `offset` est déjà supposé >= 0 ;
        neutre si 0.0 ou colonne absente (voir appelant)."""
        if offset == 0.0:
            return price
        return price + offset if is_buy else price - offset

    # ------------------------------------------------------------------ #
    def _get_obs(self):
        feats = self._feature_values[self.current_step - self.window_size: self.current_step].flatten()
        current_context = self._feature_values[self.current_step]
        mem_pnl, mem_drawdown = self._memory.query(current_context)
        extra_values = [self.position, self.unrealized_pnl_pct, mem_pnl, mem_drawdown]
        if self.learn_stop_loss:
            # distance du stop ACTUEL en fraction du prix d'entrée, signée
            # dans le sens du risque (0.0 si flat) -- l'agent doit voir son
            # propre risque en cours, pas juste sa position.
            if self.position != 0 and self.entry_price and self.stop_price is not None:
                stop_distance = abs(self.entry_price - self.stop_price) / self.entry_price
            else:
                stop_distance = 0.0
            extra_values.append(stop_distance)
        extra = np.array(extra_values, dtype=np.float32)
        return np.concatenate([feats, extra]).astype(np.float32)

    def _segment_bounds(self, segment_id) -> tuple[int, int]:
        """(premier index, dernier index inclus) de `segment_id` dans
        `self._segment_id_col`."""
        idx = np.flatnonzero(self._segment_id_col == segment_id)
        return int(idx[0]), int(idx[-1])

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if self._segment_id_col is not None:
            # MULTI-ACTIFS (LOT 2, phase 4) : choisit un segment au hasard à
            # CHAQUE reset (pas toujours le premier) -- sur de nombreux
            # resets pendant l'entraînement (SB3 rappelle reset() à chaque
            # fin d'épisode), garantit une couverture équilibrée de tous les
            # segments plutôt que de ne jamais dépasser le premier. Un
            # segment trop court pour `window_size` est exclu (jamais un
            # épisode qui ne peut même pas produire une première observation).
            segment_ids = np.unique(self._segment_id_col)
            valid = [sid for sid in segment_ids
                     if self._segment_bounds(sid)[1] - self._segment_bounds(sid)[0] + 1 > self.window_size]
            chosen = valid[int(self.np_random.integers(0, len(valid)))] if valid else segment_ids[0]
            start, _ = self._segment_bounds(chosen)
            self.current_step = start + self.window_size
        elif self._randomize_start:
            # Voir le commentaire dans __init__ -- laisse au moins de quoi
            # produire quelques pas avant la fin des données (`- 2`, comme la
            # condition de fin d'épisode ci-dessous dans step()).
            max_offset = max(0, len(self.df) - self.window_size - 2)
            offset = int(self.np_random.integers(0, max_offset + 1)) if max_offset > 0 else 0
            self.current_step = self.window_size + offset
        else:
            self.current_step = self.window_size
        self.balance = self.initial_balance
        self.equity_curve = [self.initial_balance]
        self.position = 0  # -1, 0, +1
        self.entry_price = None
        self.stop_price = None
        self.take_profit_price = None
        self.unrealized_pnl_pct = 0.0
        self.peak_equity = self.initial_balance
        self.max_drawdown = 0.0
        self.trade_log = []
        self.n_limit_orders = 0
        self.n_limit_filled = 0
        self._peak_unrealized_pnl_pct = 0.0
        self._recent_position_changes = []
        self._stops_today = 0
        self._stops_day = None
        return self._get_obs(), {}

    def _log_trade(self, position, entry_price, exit_price, pnl_pct, stopped_out):
        self.trade_log.append({
            "step": self.current_step, "position": position,
            "entry": entry_price, "exit": exit_price, "pnl_pct": pnl_pct,
            "stopped_out": stopped_out,
            # contexte de marché au moment de la clôture -- c'est ce
            # vecteur qui alimente la mémoire épisodique (voir
            # continuous_trainer.py) et qui sera comparé à celui de
            # futures situations via MemoryQuery.
            # Identique à self.df.iloc[current_step][feature_columns].values.astype(np.float32)
            # (mêmes valeurs, même dtype -- _feature_values EST déjà cette
            # même projection, calculée une fois en __init__, voir ce
            # commentaire là-bas) : évite un accès .iloc redondant pour une
            # donnée déjà disponible en numpy.
            "context": self._feature_values[self.current_step].tolist(),
        })

    def step(self, action):
        # FRONTIÈRE DE SEGMENT (LOT 2, phase 4, point 3) : si la PROCHAINE
        # bougie (celle qui servirait de prix de remplissage T+1, voir plus
        # bas) appartient à un autre segment que la bougie courante, cette
        # bougie appartient déjà à un autre symbole/époque -- aucun stop, PnL
        # ni récompense ne doit utiliser ses valeurs. Position forcée à plat
        # SANS réaliser de PnL (jamais un prix de clôture emprunté au
        # segment suivant), épisode terminé ici. Vérifié EN TOUT PREMIER,
        # avant toute autre logique de ce pas.
        if (self._segment_id_col is not None and self.current_step + 1 < len(self._segment_id_col)
                and self._segment_id_col[self.current_step + 1] != self._segment_id_col[self.current_step]):
            self.position = 0.0
            self.entry_price = None
            self.stop_price = None
            self.unrealized_pnl_pct = 0.0
            equity = self.balance
            self.equity_curve.append(equity)
            self.peak_equity = max(self.peak_equity, equity)
            drawdown = (self.peak_equity - equity) / self.peak_equity if self.peak_equity > 0 else 0.0
            return self._get_obs(), 0.0, True, False, {
                "equity": equity, "drawdown": drawdown, "balance": self.balance,
                "segment_boundary": True,
            }

        # self._open/_high/_low/_close (pré-extraits en __init__) remplacent
        # l'ancien `bar = self.df.iloc[self.current_step]` -- voir le
        # commentaire d'__init__ pour le raisonnement/la mesure de
        # profilage. Valeurs STRICTEMENT identiques (même dtype float64).
        price = float(self._close[self.current_step])
        # Capturé AVANT tout changement (stop-loss intra-bougie ou décision
        # de l'agent ci-dessous) -- sert uniquement au suivi giveback/friction
        # de risk_adjusted_v2 (voir fin de step()), jamais à la logique de
        # coût de transaction existante (qui a sa propre notion de `changed`).
        position_before_this_step = self.position

        # STOP-LOSS RÉALISTE : vérifié AVANT la nouvelle décision, contre le
        # PLUS HAUT/PLUS BAS réel de la bougie (pas juste sa clôture) -- une
        # position peut donc être coupée AVANT que l'agent n'ait l'occasion
        # de décider, exactement comme chez un vrai broker. Le stop n'est
        # actif que si l'agent en a choisi un (learn_stop_loss) ; sans lui,
        # aucune protection intra-bougie (comportement d'origine).
        if self.learn_stop_loss and self.position != 0 and self.stop_price is not None:
            stopped_out = ((self.position > 0 and float(self._low[self.current_step]) <= self.stop_price) or
                            (self.position < 0 and float(self._high[self.current_step]) >= self.stop_price))
            if stopped_out:
                exit_price = self.stop_price
                realized = (exit_price - self.entry_price) / self.entry_price * self.position
                cost = abs(self.position) * self._effective_transaction_cost()
                self.balance *= (1 + realized - cost)
                self._log_trade(self.position, self.entry_price, exit_price, realized, stopped_out=True)
                self.position = 0.0
                self.entry_price = None
                self.stop_price = None
                if self._day_id is not None:
                    day = self._day_id[self.current_step]
                    if self._stops_day != day:
                        self._stops_day, self._stops_today = day, 0
                    self._stops_today += 1

        # TAKE-PROFIT RÉALISTE : même principe que le stop-loss ci-dessus
        # (vérifié contre le PLUS HAUT/PLUS BAS réel de la bougie, avant la
        # nouvelle décision) -- vérifié APRÈS le stop (si les deux sont
        # atteints dans la même bougie, le stop gagne : hypothèse
        # conservatrice, jamais une sortie gagnante supposée sur une bougie
        # qui aurait pu tout aussi bien toucher le stop en premier). N'existe
        # que si `learn_take_profit` ET une position avec un take-profit
        # fixé (jamais le cas si le stop vient déjà de clôturer la position
        # ci-dessus -- `self.position` est alors 0).
        if self.learn_take_profit and self.position != 0 and self.take_profit_price is not None:
            hit_tp = ((self.position > 0 and float(self._high[self.current_step]) >= self.take_profit_price) or
                       (self.position < 0 and float(self._low[self.current_step]) <= self.take_profit_price))
            if hit_tp:
                exit_price = self.take_profit_price
                realized = (exit_price - self.entry_price) / self.entry_price * self.position
                cost = abs(self.position) * self._effective_transaction_cost()
                self.balance *= (1 + realized - cost)
                self._log_trade(self.position, self.entry_price, exit_price, realized, stopped_out=False)
                self.position = 0.0
                self.entry_price = None
                self.stop_price = None
                self.take_profit_price = None

        # STOP-LOSS ATR (item 1, suite) : buckets recalculés CHAQUE PAS, car
        # l'ATR évolue -- doivent être à jour AVANT l'interprétation de
        # l'action ci-dessous, pour que le `stop_idx` choisi par l'agent
        # sélectionne bien le bucket courant, pas celui du pas précédent.
        # Ne concerne que le cas discret (learn_stop_loss) ; retombe sur
        # `self.stop_loss_buckets` (comportement statique d'origine) si
        # `_atr_stop_loss_active` est False (voir cette propriété pour les
        # conditions exactes, notamment `raw_atr` non fourni).
        if self.learn_stop_loss:
            self._current_stop_loss_buckets = (
                self._compute_atr_stop_loss_buckets(price) if self._atr_stop_loss_active
                else self.stop_loss_buckets
            )

        # ---- interprétation de l'action (direction, + distance du stop si learn_stop_loss) ----
        stop_pct = None
        tp_rr_multiple = None  # résolu ci-dessous seulement si learn_take_profit (toujours combiné à learn_stop_loss, jamais au cas continu -- voir action_space)
        if self.continuous_action:
            arr = np.asarray(action, dtype=np.float32).reshape(-1)
            target_position = float(np.clip(arr[0], -1.0, 1.0)) * self.max_position
            if self.learn_stop_loss and arr.shape[0] > 1:
                lo, hi = self.stop_loss_range
                stop_pct = lo + (float(np.clip(arr[1], -1.0, 1.0)) + 1) / 2 * (hi - lo)
            # seuil mort : évite de "trader" en permanence pour un bruit
            # numérique négligeable (jamais un problème en discret, où les
            # valeurs sont exactement -1/0/1, comparées par égalité stricte).
            changed = abs(target_position - self.position) > 0.01
        elif self.learn_stop_loss:
            direction_idx, stop_idx = int(action[0]), int(action[1])
            target_position = {0: -1, 1: 0, 2: 1}[direction_idx] * self.max_position
            stop_pct = self._current_stop_loss_buckets[stop_idx]
            changed = target_position != self.position
            # Multiple de take-profit choisi -- résolu en pourcentage
            # seulement à l'ouverture (voir plus bas, `take_profit_pct`),
            # car il dépend de `stop_pct` ci-dessus qui, lui, dépend
            # potentiellement de l'ATR COURANT (voir _current_stop_loss_
            # buckets) -- jamais figé avant que ce pas ne soit résolu.
            tp_rr_multiple = self.take_profit_rr_buckets[int(action[2])] if self.learn_take_profit else None
            order_idx = int(action[3]) if self.learn_order_type else 0
        else:
            target_position = {0: -1, 1: 0, 2: 1}[int(action)] * self.max_position
            changed = target_position != self.position

        # ATR REQUIS MAIS INDISPONIBLE (LOT 2, phase 3, point 2) : si ce
        # déploiement est configuré pour le stop ATR (atr_stop_loss=True et
        # "atr_14" dans feature_columns) mais qu'aucune valeur d'ATR n'est
        # disponible POUR CE PAS précis (donnée manquante/NaN -- pas
        # "raw_atr jamais fourni", voir _atr_price_units), AUCUNE OUVERTURE
        # n'est permise à ce pas -- jamais un stop-loss silencieusement
        # incohérent avec ce que l'agent a appris. Une clôture pure
        # (target_position == 0) n'est JAMAIS affectée ; une position déjà
        # ouverte reste inchangée (le changement, y compris un
        # retournement, est simplement annulé).
        if self.learn_stop_loss and target_position != 0 and changed:
            atr_required = self.atr_stop_loss and self._atr_idx is not None
            if atr_required and self._atr_price_units() is None:
                target_position = self.position
                changed = False

        if (self._day_id is not None and target_position != 0 and changed and self.position == 0
                and self._stops_day == self._day_id[self.current_step]
                and self._stops_today >= self.max_stops_per_day):
            target_position = self.position
            changed = False

        # ORDRE LIMITE (learn_order_type, voir __init__) : décidé ici, AVANT le bloc d'exécution --
        # une limite non atteinte par la bougie suivante annule l'ouverture (on reste/repasse à plat).
        limit_fill_price = None
        if (self.learn_order_type and changed and abs(target_position) > 1e-9
                and self.limit_offsets_atr[order_idx] > 0):
            atr_units = self._atr_price_units()
            if atr_units:
                off = self.limit_offsets_atr[order_idx] * atr_units
                fidx = min(self.current_step + 1, len(self.df) - 1)
                self.n_limit_orders += 1
                if target_position > 0:
                    lp = price - off
                    filled = float(self._low[fidx]) <= lp
                    fill_px = min(float(self._open[fidx]), lp)
                else:
                    lp = price + off
                    filled = float(self._high[fidx]) >= lp
                    fill_px = max(float(self._open[fidx]), lp)
                if filled:
                    self.n_limit_filled += 1
                    limit_fill_price = fill_px
                else:
                    target_position = 0.0
                    changed = target_position != self.position

        # coût de transaction si on change de position. NOTE (action
        # continue) : un changement de TAILLE (ex: 0.3 -> 0.5, même sens)
        # est traité comme une clôture complète suivie d'une réouverture au
        # prix courant -- simplification qui ne fait pas de vrai suivi de
        # prix moyen pondéré pour un ajout partiel, cohérente avec le modèle
        # déjà utilisé en discret (toujours clôture totale/réouverture).
        cost = 0.0
        if changed:
            cost = abs(target_position - self.position) * self._effective_transaction_cost()
            # LATENCE D'EXÉCUTION (item 4, audit institutionnel) : un ordre
            # DÉCIDÉ PAR L'AGENT (ouverture/clôture/retournement) n'exécute
            # PAS à la clôture de la bougie T sur laquelle la décision a été
            # prise (comportement d'origine) mais à l'OUVERTURE de la
            # bougie T+1 -- le temps que la décision devienne un ordre
            # envoyé/exécuté chez le broker, T est déjà close. Ne s'applique
            # JAMAIS au déclenchement d'un stop-loss (bloc plus haut, non
            # modifié -- surveillance continue côté broker, pas soumise à
            # cette latence) ni au marque-au-marché ci-dessous (qui reste
            # basé sur la clôture de T, aucun ordre n'étant passé pour une
            # position simplement maintenue).
            # `min(...)` est une garde défensive (jamais atteinte en usage
            # normal vu `terminated` ci-dessous, qui réserve toujours au
            # moins une bougie de plus) : ne lève jamais d'IndexError même
            # si step() était appelé après la fin réelle de l'épisode.
            fill_idx = min(self.current_step + 1, len(self.df) - 1)
            fill_price_raw = float(self._open[fill_idx])
            # SLIPPAGE (item 3, colonne optionnelle `slippage_price_offset`
            # de `self.df`, produite par inject_macro_shocks -- JAMAIS une
            # feature visible par l'agent) : lu sur la MÊME bougie T+1 que le
            # prix d'exécution, puisque c'est la bougie contre laquelle
            # l'ordre s'exécute réellement.
            slippage_offset = (float(self._slippage_price_offset_col[fill_idx])
                                if self._slippage_price_offset_col is not None else 0.0)
            if self.entry_price is not None:
                # clôture de l'ancienne position : ordre ACHETEUR si elle
                # était SHORT (self.position < 0), VENDEUR si elle était LONG.
                close_fill = self._apply_slippage(fill_price_raw, slippage_offset, is_buy=self.position < 0)
                realized = (close_fill - self.entry_price) / self.entry_price * self.position
                self.balance *= (1 + realized - cost)
                self._log_trade(self.position, self.entry_price, close_fill, realized, stopped_out=False)
            if abs(target_position) > 1e-9:
                # ouverture de la nouvelle position : ordre ACHETEUR si LONG,
                # VENDEUR si SHORT -- jambe INDÉPENDANTE de la clôture
                # ci-dessus : un retournement paie le slippage DEUX FOIS (une
                # fois par jambe), ce qui est réaliste (on traverse le
                # spread/la liquidité deux fois).
                self.entry_price = (limit_fill_price if limit_fill_price is not None else
                                    self._apply_slippage(fill_price_raw, slippage_offset, is_buy=target_position > 0))
            else:
                self.entry_price = None
            self.position = target_position
            # NOUVEAU stop pour la position nouvellement ouverte -- choisi
            # par l'agent lui-même (stop_pct), basé sur le NOUVEAU prix
            # d'entrée (donc déjà sur la bougie T+1, ajusté du slippage).
            if abs(target_position) > 1e-9 and stop_pct is not None:
                self.stop_price = (self.entry_price * (1 - stop_pct) if target_position > 0
                                    else self.entry_price * (1 + stop_pct))
            else:
                self.stop_price = None
            # TAKE-PROFIT = stop_pct x multiple choisi par l'agent (voir le
            # commentaire de `learn_take_profit` dans __init__) -- calculé
            # UNIQUEMENT à l'ouverture, sur le stop_pct EFFECTIVEMENT retenu
            # ci-dessus (déjà résolu ATR ou statique, peu importe -- voir
            # _current_stop_loss_buckets), jamais recalculé tant que la
            # position reste ouverte (comme le stop lui-même).
            if abs(target_position) > 1e-9 and tp_rr_multiple is not None and stop_pct is not None:
                take_profit_pct = stop_pct * tp_rr_multiple
                self.take_profit_price = (self.entry_price * (1 + take_profit_pct) if target_position > 0
                                            else self.entry_price * (1 - take_profit_pct))
            else:
                self.take_profit_price = None
        else:
            self.balance *= (1 - cost)  # cost=0 ici de toute façon

        # PnL flottant (marque-au-marché) pour la récompense intra-épisode
        if self.position != 0 and self.entry_price:
            self.unrealized_pnl_pct = (price - self.entry_price) / self.entry_price * self.position
        else:
            self.unrealized_pnl_pct = 0.0

        equity = self.balance * (1 + self.unrealized_pnl_pct)
        self.equity_curve.append(equity)
        self.peak_equity = max(self.peak_equity, equity)
        drawdown = (self.peak_equity - equity) / self.peak_equity
        self.max_drawdown = max(self.max_drawdown, drawdown)

        # Suivi PILOTE (risk_adjusted_v2/v3 uniquement -- ignoré et donc
        # gratuit pour les autres reward_type, voir _compute_reward) : pic de
        # PnL flottant depuis l'ouverture de la position COURANTE
        # (réinitialisé à une ouverture ou un retournement), et historique
        # borné des changements de position pour la friction de fréquence.
        position_changed_this_step = self.position != position_before_this_step
        if self.position == 0.0:
            self._peak_unrealized_pnl_pct = 0.0
        elif position_before_this_step == 0.0 or (position_before_this_step * self.position < 0):
            self._peak_unrealized_pnl_pct = self.unrealized_pnl_pct
        else:
            self._peak_unrealized_pnl_pct = max(self._peak_unrealized_pnl_pct, self.unrealized_pnl_pct)

        # FRICTION ASYMÉTRIQUE (17/09, "risk_adjusted_v3" UNIQUEMENT --
        # risk_adjusted_v2 continue de compter TOUT changement, comportement
        # inchangé) : sous v2, sortir en prenant un profit coûtait EXACTEMENT
        # la même friction qu'un retournement compulsif -- rien ne
        # distinguait "je prends mon gain et je repasse plat" de "je change
        # d'avis toutes les 2 bougies". Constaté en conditions réelles sur le
        # pilote atr_fix : 72.5% de sorties au stop-loss (4.4% en
        # production), une fenêtre walk-forward à 1 seul trade sur 5563 pas
        # -- l'agent avait appris à ne quasiment plus jamais agir plutôt que
        # de payer cette friction pour sortir proprement. Sous v3, revenir à
        # FLAT (target_position == 0) ne compte plus comme un événement de
        # friction ; seules restent "friction" : l'ouverture d'une nouvelle
        # position depuis plat, et le retournement direct (long<->short),
        # qui reste le cas le plus coûteux (deux jambes en un seul pas).
        if self.reward_type == "risk_adjusted_v3":
            friction_relevant_change = position_changed_this_step and self.position != 0.0
        else:
            friction_relevant_change = position_changed_this_step
        self._recent_position_changes.append(friction_relevant_change)
        if len(self._recent_position_changes) > self.friction_window:
            self._recent_position_changes.pop(0)

        reward = self._compute_reward(equity, drawdown)

        self.current_step += 1
        # -2 (pas -1, comportement d'origine) : un fill agent (item 4)
        # consomme la bougie current_step+1 (son OUVERTURE) -- il faut donc
        # toujours qu'il reste AU MOINS une bougie de plus après
        # current_step pour qu'un futur appel à step() puisse encore
        # trouver un prix de remplissage T+1 valide sans dépasser la fin du
        # dataframe.
        terminated = self.current_step >= len(self.df) - 2
        truncated = False
        return self._get_obs(), reward, terminated, truncated, {
            "equity": equity, "drawdown": drawdown, "balance": self.balance,
        }

    def _base_risk_adjusted_reward(self, step_return, drawdown):
        base = step_return - self.drawdown_penalty * max(0.0, drawdown - self.drawdown_tolerance)

        giveback = 0.0
        if self.position != 0.0 and self._peak_unrealized_pnl_pct > 1e-9:
            giveback = max(0.0, self._peak_unrealized_pnl_pct - self.unrealized_pnl_pct)
            giveback_ratio = giveback / self._peak_unrealized_pnl_pct
        else:
            giveback_ratio = 0.0
        giveback_penalty = self.giveback_penalty_coef * max(
            0.0, giveback_ratio - self.giveback_ratio_threshold)

        change_rate = (sum(self._recent_position_changes) / len(self._recent_position_changes)
                       if self._recent_position_changes else 0.0)
        friction_penalty = self.friction_penalty_coef * change_rate

        # Voir __init__ pour le rationale complet -- s'applique À CHAQUE pas
        # où l'agent est plat (self.position == 0.0), jamais quand une
        # position est ouverte (une position ouverte a déjà son propre
        # signal via step_return/giveback/drawdown, pas besoin de ce terme).
        inactivity_penalty = self.inactivity_penalty_coef if self.position == 0.0 else 0.0

        return base - giveback_penalty - friction_penalty - inactivity_penalty

    def _compute_reward(self, equity, drawdown):
        step_return = (self.equity_curve[-1] / self.equity_curve[-2]) - 1

        if self.reward_type == "pnl":
            return step_return

        if self.reward_type == "sharpe_delta":
            returns = np.diff(self.equity_curve[-min(50, len(self.equity_curve)):]) \
                      / np.array(self.equity_curve[-min(50, len(self.equity_curve)) - 1:-1])
            if len(returns) > 1 and returns.std() > 1e-9:
                return float(returns.mean() / (returns.std() + 1e-9))
            return step_return

        if self.reward_type in ("risk_adjusted_v2", "risk_adjusted_v3"):
            # PILOTES risk_adjusted_v2 (18/09, voir scripts/pilot_m15_v2.py)
            # et risk_adjusted_v3 (17/09, voir scripts/pilot_m15_v4.py) :
            # même formule (base + giveback + friction) -- part de
            # "risk_adjusted" telle quelle (même base, même pénalité de
            # drawdown de compte), PLUS deux termes calibrés sur le
            # comportement DÉJÀ OBSERVÉ :
            #  (1) GIVEBACK : pénalise le fait de redonner une part
            #      significative (> giveback_ratio_threshold) du pic de
            #      PnL flottant déjà atteint sur la position EN COURS,
            #      PENDANT qu'elle reste ouverte -- pas seulement à la
            #      clôture, pour un signal d'apprentissage immédiat plutôt
            #      qu'un crédit différé difficile à attribuer par PPO.
            #  (2) FRICTION : pénalise un taux ÉLEVÉ de changements de
            #      position sur une fenêtre glissante récente -- répond au
            #      constat que le coût de transaction seul (déjà présent,
            #      voir `cost` dans step()) est correct pour un trade isolé
            #      mais ne pénalise pas la fréquence CUMULATIVE des
            #      retournements.
            # Les deux restent des points de comparaison INDÉPENDANTS malgré
            # le code partagé : giveback_ratio_threshold/giveback_penalty_coef
            # sont des paramètres d'instance (0.4/0.03 par défaut sous v2,
            # 0.25/0.15 sous v3 -- voir scripts/pilot_m15_v4.py), et la
            # friction asymétrique de v3 (un retour à FLAT ne compte plus
            # comme événement de friction) est décidée dans step(), pas ici
            # -- rien dans cette formule partagée ne couple leur comportement.
            return self._base_risk_adjusted_reward(step_return, drawdown)

        # "risk_adjusted" (par défaut) : pénalise le drawdown, pas seulement les pertes
        penalty = self.drawdown_penalty * max(0.0, drawdown - self.drawdown_tolerance)
        return step_return - penalty
