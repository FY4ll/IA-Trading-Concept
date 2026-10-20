# Repris de Run A (src/backtester.py, version du 08/10/2026) pour l'architecture v3 -- calculs IDENTIQUES
# (prouvé par tests/test_juge_equivalence.py). Toute modification doit garder ce test vert.
"""
backtester.py
=============
Évalue un agent entraîné sur des données qu'il n'a jamais vues (val/test),
en respectant l'ordre chronologique (aucune fuite d'information du futur).

Calcule les métriques qui définissent le "reward / performance" au niveau
projet : pas seulement le taux de trades gagnants, mais le couple
rendement/risque (Sharpe, drawdown, profit factor...).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from aurexis.cerveau.simulateur import TradingEnv
from aurexis.juge.scenarios import (
    block_bootstrap_rows, high_volatility_subset,
    inject_macro_shocks, stationary_block_bootstrap,
    garch_stress_dataset, resolve_friction_params,
)


def run_episode(agent, env: TradingEnv):
    # 06/10/2026 : évaluation accélérée (src/fast_eval.py -- LSTM pré-calculé pour toutes les bougies,
    # décisions identiques, ~x5) quand le réseau s'y prête ; sinon, ou en cas d'erreur, version d'origine.
    from aurexis.cerveau.rejeu_rapide import supported, run_episode_fast
    if supported(agent, env):
        try:
            return run_episode_fast(agent, env)
        except Exception as e:
            import logging
            logging.getLogger("backtester").warning(f"Évaluation accélérée impossible ({type(e).__name__}: {e}) "
                                                    f"-> évaluation pas à pas d'origine.")
    obs, _ = env.reset()
    done = False
    while not done:
        action = agent.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
    return env


# Nombre de barres par an pour chaque timeframe (252 jours de bourse/an),
# utilisé pour annualiser le Sharpe correctement selon le style évalué --
# un facteur unique câblé pour H1 sous-évaluait/sur-évaluait le Sharpe des
# autres timeframes, rendant leurs scores non comparables entre eux alors
# qu'ils sont comparés directement pour élire le champion tous styles
# confondus (voir continuous_trainer.py).
BARS_PER_YEAR = {
    "M15": 252 * 24 * 4,
    "M30": 252 * 24 * 2,
    "H1": 252 * 24,
    "H4": 252 * 6,
    "D1": 252,
}


def compute_metrics(env: TradingEnv, timeframe: str = "H1") -> dict:
    equity = np.array(env.equity_curve)
    returns = np.diff(equity) / equity[:-1]

    total_return = equity[-1] / equity[0] - 1
    bars_per_year = BARS_PER_YEAR.get(timeframe, BARS_PER_YEAR["H1"])
    sharpe = 0.0
    if returns.std() > 1e-9:
        sharpe = (returns.mean() / returns.std()) * np.sqrt(bars_per_year)

    # SORTINO (audit institutionnel, item 5) : comme Sharpe, mais ne
    # pénalise QUE la variance des rendements NÉGATIFS (downside deviation)
    # -- un Sharpe pénalise à égalité une hausse "trop" volatile et une
    # baisse volatile, alors qu'un trader (et un investisseur) n'a jamais
    # rien contre une hausse erratique. Deux stratégies au même Sharpe
    # peuvent avoir un profil de risque réel très différent si l'une
    # concentre sa variance côté gains et l'autre côté pertes -- Sortino
    # distingue les deux, Sharpe seul ne le peut pas.
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() if len(downside_returns) > 1 else 0.0
    sortino = 0.0
    if downside_std > 1e-9:
        sortino = float((returns.mean() / downside_std) * np.sqrt(bars_per_year))

    # PLAFOND ANTI-ARTEFACT STATISTIQUE (26/09, bug réel observé DEUX FOIS le
    # même jour -- M30 gen:29 sortino=2057 sur 3 trades, PUIS H4 gen:340
    # sortino=97.8 sur 1 SEUL trade malgré le plancher de fiabilité déjà
    # ajouté dans evaluate_agent_walkforward ci-dessous) : sur un tout petit
    # nombre de trades, l'écart-type des pertes peut être quasi nul par pur
    # hasard (aucune perte "malchanceuse" dans l'échantillon), ce qui fait
    # diverger le ratio sharpe/sortino vers l'infini -- un plancher sur le
    # NOMBRE de trades pondérant la moyenne (voir plus bas) ne suffit pas si
    # la valeur individuelle explose plus vite que son poids ne la réduit.
    # Plafonné ICI, à la SOURCE (avant toute agrégation/pondération), pour
    # que TOUT consommateur (score de sélection, dashboard, comparaisons de
    # plateau...) en bénéficie automatiquement. ±10 est large : aucun
    # sharpe/sortino réaliste observé sur ce run (candidats sains comme
    # dégradés) n'a jamais dépassé ~9 en valeur absolue.
    sharpe = float(np.clip(sharpe, -10.0, 10.0))
    sortino = float(np.clip(sortino, -10.0, 10.0))

    max_drawdown = env.max_drawdown

    trades = env.trade_log
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    win_rate = len(wins) / len(trades) if trades else 0.0

    gross_profit = sum(t["pnl_pct"] for t in wins)
    gross_loss = abs(sum(t["pnl_pct"] for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 1e-9 else float("inf")

    stopped_out = [t for t in trades if t.get("stopped_out")]
    stop_exit_rate = len(stopped_out) / len(trades) if trades else 0.0

    # RÉPARTITION DES TRADES PAR ANNÉE (23/09, demande explicite -- un
    # candidat peut agréger un score/nombre de trades correct tout en étant
    # quasi muet sur une année entière de la fenêtre évaluée, noyée dans le
    # total par les autres années). `years_in_span` liste les années
    # SUFFISAMMENT couvertes par `env.df` (>= 60% d'une année de bougies pour
    # ce timeframe -- une année tronquée en bord de fenêtre n'a pas assez de
    # bougies pour qu'un faible nombre de trades soit un signe fiable de
    # dégénérescence) ; `trades_by_year` compte les trades RÉELLEMENT
    # observés par année (une année de `years_in_span` absente de ce dict a
    # 0 trade). Voir `passes_validation` -- `min_trades_per_year` ci-dessous.
    # Silencieusement vide si `env.df` n'a pas de colonne "time" (mêmes
    # gardes-fous que `_hour_of_day` dans trading_env.py).
    trades_by_year: dict[int, int] = {}
    years_in_span: list[int] = []
    if "time" in env.df.columns and len(env.df) > 0:
        years_series = pd.to_datetime(env.df["time"]).dt.year
        bars_per_year_expected = BARS_PER_YEAR.get(timeframe, BARS_PER_YEAR["H1"])
        counts_per_year = years_series.value_counts()
        years_in_span = sorted(
            int(year) for year, n_bars in counts_per_year.items()
            if n_bars >= 0.6 * bars_per_year_expected
        )
        for t in trades:
            step = t["step"]
            if 0 <= step < len(years_series):
                year = int(years_series.iloc[step])
                trades_by_year[year] = trades_by_year.get(year, 0) + 1

    # BENCHMARK BUY-AND-HOLD (25/09, demande explicite -- "un bon trader fait
    # à peu près le marché : le marché fait +16%, lui +13%") : rendement de
    # l'instrument lui-même sur la période où l'agent pouvait agir (les
    # `window_size` premières bougies ne sont que du contexte de lecture).
    # `excess_return` = agent - marché, en points : direction-agnostique par
    # construction (un short gagnant une année baissière donne un excès
    # positif, rester plat une année haussière donne un excès négatif). Sans
    # ça, un agent qui fait +2% avec un drawdown minuscule affiche un Sharpe
    # superbe alors qu'il n'a capté que 5% d'un marché à +25%. Voir
    # `passes_validation` (max_lag_vs_market_pts) et continuous_trainer.py
    # (excess_return_weight). 0.0 si pas de colonne close (jamais une erreur).
    benchmark_return = 0.0
    if "close" in env.df.columns and len(env.df) > 1:
        closes = env.df["close"].to_numpy(dtype=np.float64)
        start_idx = min(max(getattr(env, "window_size", 0) - 1, 0), len(closes) - 2)
        if closes[start_idx] > 1e-12:
            benchmark_return = float(closes[-1] / closes[start_idx] - 1)
    excess_return = float(total_return) - benchmark_return

    return {
        "total_return": float(total_return),
        "benchmark_return": float(benchmark_return),
        "excess_return": float(excess_return),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(max_drawdown),
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor) if profit_factor != float("inf") else 999.0,
        "n_trades": len(trades),
        "stop_exit_rate": float(stop_exit_rate),
        "trades_by_year": trades_by_year,
        "years_in_span": years_in_span,
    }


def evaluate_agent(agent, df, env_kwargs, timeframe: str = "H1") -> dict:
    env = TradingEnv(df, **env_kwargs)
    env = run_episode(agent, env)
    return compute_metrics(env, timeframe=timeframe)


def evaluate_agent_walkforward(agent, df, env_kwargs, n_windows: int = 3,
                                 stress_test: bool = False, stress_seed: int | None = None,
                                 timeframe: str = "H1", garch_stress: bool = False,
                                 garch_context_tfs: list | None = None, garch_stats: dict | None = None,
                                 garch_params: dict | None = None,
                                 macro_event_timestamps: list | None = None,
                                 friction_profile: str = "pessimistic") -> dict:
    """Évalue l'agent sur PLUSIEURS fenêtres temporelles indépendantes plutôt
    qu'un seul long épisode continu, puis agrège les résultats.

    Pourquoi : `evaluate_agent` fait composer l'équité de façon multiplicative
    sur tout l'épisode de validation (potentiellement plus d'un an de
    bougies). Sur un historique avec un mouvement de fond marqué (ex: une
    forte hausse de l'or), un agent qui "attrape" ce mouvement par chance
    voit ses gains s'enchaîner en cascade sur tout le reste de l'épisode,
    ce qui peut faire passer de la chance pour de la compétence -- et
    produire un écart énorme entre deux candidats pourtant très proches en
    hyperparamètres. Découper la validation en plusieurs fenêtres
    indépendantes (chacune repartant du solde initial) et moyenner réduit
    fortement ce bruit : un candidat doit être bon sur PLUSIEURS morceaux
    de marché différents pour obtenir un bon score, pas sur un seul.

    Le drawdown agrégé est le PIRE des fenêtres (pas la moyenne) : on ne
    veut jamais masquer une fenêtre catastrophique en la diluant dans des
    fenêtres favorables.

    `stress_test` (voir src/stress_test.py) ajoute QUATRE scénarios
    adversariaux (réordonnancement de blocs, sous-ensemble haute
    volatilité, bootstrap stationnaire, chocs macro simulés) construits à
    partir de VRAIS morceaux de marché, jamais vus dans cet ordre/cette
    combinaison à l'entraînement. Leur drawdown entre dans le pire-cas
    agrégé (un candidat qui s'effondre sous stress ne peut pas s'en cacher
    derrière de bonnes fenêtres "normales"), mais leur rendement/sharpe
    reste EXCLU de la moyenne principale -- on ne veut pas qu'un scénario
    délibérément adversarial fausse la mesure de performance "typique",
    seulement sa mesure de ROBUSTESSE.

    `garch_stress` (défaut False, voir src/stress_test.py::
    garch_stress_dataset -- audit institutionnel, section 1 "Modélisation
    non linéaire de la Volatilité") ajoute un CINQUIÈME scénario, distinct
    des quatre ci-dessus par nature : une série ENTIÈREMENT SYNTHÉTIQUE
    (récursion GARCH(1,1), queues épaisses, clustering de volatilité) plutôt
    qu'un réarrangement de l'historique réel -- teste une dynamique de
    volatilité qu'aucun réarrangement de données réelles ne peut produire.
    Nécessite `garch_context_tfs`/`garch_stats` (contexte multi-timeframe et
    stats de normalisation DU CANDIDAT, jamais réajustées sur la série
    synthétique) ; silencieusement absent du résultat si `timeframe` est
    plus fin que H1 (M15/M30 -- voir GARCH_STRESS_SUPPORTED_PRIMARY_TFS,
    limite de la série de base à fréquence horaire fixe) ou si ces
    paramètres ne sont pas fournis. `garch_params` (dict optionnel :
    dof/alpha/beta) surcharge les défauts de generate_synthetic_ohlcv_garch.

    `macro_event_timestamps` (défaut None, voir src/stress_test.py::
    load_macro_events_csv -- audit institutionnel, section 3) : liste de
    VRAIS horodatages CPI/NFP/FOMC transmise au scénario `macro_shock`
    existant (remplace son proxy statistique par défaut). None (défaut,
    comportement d'origine inchangé) = proxy statistique.
    """
    n = len(df)
    window_size = env_kwargs.get("window_size", 50)
    min_len = window_size + 20  # fenêtre trop courte pour être significative
    chunk = n // n_windows

    if chunk < min_len:
        # dataset de validation trop court pour être découpé -> repli sur une seule fenêtre
        return evaluate_agent(agent, df, env_kwargs, timeframe=timeframe)

    per_window = []
    for i in range(n_windows):
        start = i * chunk
        end = n if i == n_windows - 1 else (i + 1) * chunk
        sub_df = df.iloc[start:end].reset_index(drop=True)
        if len(sub_df) < min_len:
            continue
        per_window.append(evaluate_agent(agent, sub_df, env_kwargs, timeframe=timeframe))

    if not per_window:
        return evaluate_agent(agent, df, env_kwargs, timeframe=timeframe)

    stress_windows = []
    if stress_test:
        try:
            block_size = max(min_len, n // 20 or min_len)
            bootstrap_df = block_bootstrap_rows(df, block_size=block_size, seed=stress_seed)
            if len(bootstrap_df) >= min_len:
                m = evaluate_agent(agent, bootstrap_df, env_kwargs, timeframe=timeframe)
                m["stress"] = "block_bootstrap"
                stress_windows.append(m)
        except Exception:
            pass  # un scénario adversarial qui échoue à se construire ne doit jamais bloquer l'évaluation
        try:
            highvol_df = high_volatility_subset(df, window_size=max(min_len * 5, 500))
            if len(highvol_df) >= min_len:
                m = evaluate_agent(agent, highvol_df, env_kwargs, timeframe=timeframe)
                m["stress"] = "high_volatility"
                stress_windows.append(m)
        except Exception:
            pass
        try:
            stationary_df = stationary_block_bootstrap(df, seed=stress_seed)
            if len(stationary_df) >= min_len:
                m = evaluate_agent(agent, stationary_df, env_kwargs, timeframe=timeframe)
                m["stress"] = "stationary_bootstrap"
                stress_windows.append(m)
        except Exception:
            pass
        try:
            # CALENDRIER MACRO RÉEL (audit institutionnel, section 3) :
            # `macro_event_timestamps`, si fourni (voir
            # src/stress_test.py::load_macro_events_csv et
            # `stress_test.macro_events_csv` en config), remplace le proxy
            # statistique par défaut de `inject_macro_shocks` (pics de
            # rendement/volume) par les VRAIS horaires CPI/NFP/FOMC -- None
            # (par défaut, comportement d'origine inchangé) retombe sur ce
            # proxy, exactement comme avant.
            # FRICTIONS CALIBRABLES (LOT 2, phase 5) : "pessimistic" (défaut)
            # renvoie exactement les valeurs déjà en place -- comportement
            # inchangé tant que `friction_profile` n'est pas explicitement
            # réglé à "calibrated".
            friction_params = resolve_friction_params(friction_profile)
            macro_shock_df = inject_macro_shocks(df, event_timestamps=macro_event_timestamps, seed=stress_seed,
                                                   **friction_params)
            if len(macro_shock_df) >= min_len:
                m = evaluate_agent(agent, macro_shock_df, env_kwargs, timeframe=timeframe)
                m["stress"] = "macro_shock"
                stress_windows.append(m)
        except Exception:
            pass

    # GARCH (voir docstring ci-dessus) : garde INDÉPENDANTE de `stress_test`
    # -- son propre interrupteur (`garch_stress`), sa propre config
    # (`stress_test.garch.*`, voir continuous_trainer.py) -- pour pouvoir
    # l'activer/désactiver sans toucher aux 4 scénarios existants.
    if garch_stress and garch_context_tfs is not None and garch_stats is not None:
        try:
            params = garch_params or {}
            garch_df = garch_stress_dataset(
                primary_tf=timeframe, context_tfs=garch_context_tfs,
                feature_columns=env_kwargs.get("feature_columns") or [],
                stats=garch_stats, n_primary_bars=max(min_len * 5, 500),
                seed=stress_seed, **params,
            )
            if garch_df is not None and len(garch_df) >= min_len:
                m = evaluate_agent(agent, garch_df, env_kwargs, timeframe=timeframe)
                m["stress"] = "garch"
                stress_windows.append(m)
        except Exception:
            pass  # même garde-fou que les 4 autres scénarios : jamais bloquant

    # PONDÉRATION PAR NOMBRE DE TRADES (pas une moyenne simple) : sans ça,
    # une fenêtre à 5 trades pèse EXACTEMENT autant qu'une fenêtre à 70
    # trades dans la moyenne -- un pur coup de chance statistique sur une
    # poignée de trades (variance énorme sur un si petit échantillon) peut
    # alors gonfler le score agrégé autant qu'une fenêtre bien plus fiable.
    # Bug réel trouvé le 14/09 : le style H4 n'avait plus progressé depuis
    # sa génération 1 en ~89 cycles -- sa fenêtre n°3 (5 trades, Sharpe 4.46)
    # gonflait le score agrégé de ~31% par rapport aux 3 autres fenêtres
    # (15-70 trades chacune), rendant la barre à battre artificiellement
    # haute pour tout candidat futur, pourtant réellement meilleur. Une
    # fenêtre à 0 trade (poids nul) est explicitement exclue plutôt que de
    # risquer une division par zéro. `max_drawdown` reste le PIRE (pas une
    # moyenne, pondérée ou non) : voir docstring plus haut, cette logique-là
    # était déjà correcte et n'a pas besoin d'être changée.
    weights = np.array([m["n_trades"] for m in per_window], dtype=np.float64)
    # PLANCHER DE FIABILITÉ POUR LA MOYENNE PONDÉRÉE (26/09, bug réel observé
    # sur M30 gen:29 ET H4 gen:69 -- tous deux devenus "champions" bloquants
    # avec un score gonflé à l'infini) : le poids par n_trades ci-dessus
    # atténue déjà l'influence d'une fenêtre à faible échantillon. Exclut les
    # fenêtres sous ce plancher du calcul pondéré (poids mis à 0) -- combiné
    # au plafond ±10 sur sharpe/sortino dans `compute_metrics` ci-dessus
    # (2e ligne de défense : même une fenêtre incluse ne peut plus exploser).
    # CORRECTIF DU 26/09 APRÈS-MIDI : le repli précédent ("si AUCUNE fenêtre
    # n'atteint le plancher, revenir à la pondération PAR TRADES d'origine")
    # réintroduisait exactement le bug qu'il devait éviter -- observé en
    # conditions réelles sur H4 gen:340 (1 SEUL trade sur toutes les
    # fenêtres, sortino de cette fenêtre à 97.8 avant plafonnement). Le repli
    # est maintenant une moyenne SIMPLE (équipoids), jamais pondérée par un
    # tout petit échantillon. N'affecte PAS `trades_by_year`/`n_trades`
    # (comptes réels, inchangés) ni `max_drawdown` (déjà le pire cas, jamais
    # moyenné).
    MIN_TRADES_FOR_RELIABLE_STATS = 5
    reliable = weights >= MIN_TRADES_FOR_RELIABLE_STATS
    def _weighted_mean(key):
        values = np.array([m[key] for m in per_window], dtype=np.float64)
        if reliable.any():
            return float(np.average(values, weights=np.where(reliable, weights, 0.0)))
        return float(np.mean(values))

    # BENCHMARK (voir compute_metrics) : moyenne SIMPLE, pas pondérée par les
    # trades -- une fenêtre à 0 trade a un poids nul dans _weighted_mean, ce
    # qui ferait justement disparaître le retard sur le marché d'un agent
    # resté plat toute une année haussière, l'exact cas que cette mesure
    # doit attraper. Les scénarios de stress sont exclus (séquences
    # réarrangées dont la dérive n'a pas de sens comme benchmark).
    benchmark_return = float(np.mean([m.get("benchmark_return", 0.0) for m in per_window]))
    excess_return = float(np.mean([m.get("excess_return", 0.0) for m in per_window]))

    return {
        "total_return": _weighted_mean("total_return"),
        "benchmark_return": benchmark_return,
        "excess_return": excess_return,
        "sharpe": _weighted_mean("sharpe"),
        "sortino": _weighted_mean("sortino"),
        "max_drawdown": float(np.max([m["max_drawdown"] for m in per_window + stress_windows])),
        "win_rate": _weighted_mean("win_rate"),
        "profit_factor": _weighted_mean("profit_factor"),
        "stop_exit_rate": _weighted_mean("stop_exit_rate"),
        "n_trades": int(np.sum([m["n_trades"] for m in per_window])),
        "per_window": per_window,  # détail par fenêtre, utile pour diagnostiquer
        "stress_windows": stress_windows,  # scénarios adversariaux (vide si stress_test=False)
        # AGRÉGATION PAR ANNÉE (23/09, voir `compute_metrics` -- même
        # rationale) : chaque fenêtre de `per_window` a déjà son propre
        # `trades_by_year`/`years_in_span` (calculés sur son SEUL sous-
        # ensemble de `df`) -- fusionnés ici (somme des comptes, union des
        # années) pour obtenir la vue sur TOUTE la période walk-forward
        # évaluée, indépendamment du découpage en fenêtres.
        "trades_by_year": {
            year: sum(w.get("trades_by_year", {}).get(year, 0) for w in per_window)
            for year in sorted(set().union(*(w.get("years_in_span", []) for w in per_window)))
        } if per_window else {},
        "years_in_span": sorted(set().union(*(w.get("years_in_span", []) for w in per_window))) if per_window else [],
    }


def compute_walk_forward_efficiency(agent, train_df, val_metrics: dict, env_kwargs: dict,
                                      timeframe: str = "H1", is_eval_bars: int | None = 5000,
                                      oos_n_bars: int | None = None, min_trades_suspect: int = 30) -> dict:
    """Walk-Forward Efficiency (WFE, audit institutionnel item 6) : compare
    le rendement ANNUALISÉ obtenu IN-SAMPLE (sur l'historique
    d'entraînement, `train_df`) à celui obtenu OUT-OF-SAMPLE (déjà mesuré
    par `evaluate_agent_walkforward`, passé ici via `val_metrics`) --
    `wfe = oos_annualized_return / is_annualized_return`. Un WFE proche de
    1.0 (ou au-dessus) signale un candidat qui généralise bien : il
    performe hors-échantillon à peu près comme sur les données qu'il a
    vues à l'entraînement. Un WFE très inférieur à 1.0 signale un
    surapprentissage classique : de bons résultats en entraînement qui ne
    se répètent pas sur des données neuves.

    COÛT/COMPROMIS DOCUMENTÉ (`is_eval_bars`, défaut 5000) : évaluer
    l'agent sur l'INTÉGRALITÉ de `train_df` (potentiellement des dizaines
    de milliers de bougies, parfois bien plus) avec une politique
    récurrente (LSTM) est très lent -- un épisode complet doit être rejoué
    séquentiellement, pas de vectorisation possible. Par défaut, on ne
    rejoue donc que les `is_eval_bars` DERNIÈRES bougies de `train_df`
    (`train_df.tail(is_eval_bars)`) -- un compromis délibéré entre rigueur
    (idéalement, tout l'historique d'entraînement) et coût (des cycles
    d'évolution continue qui tournent en permanence, voir
    continuous_trainer.py). Passez `is_eval_bars=None` pour désactiver ce
    plafond et évaluer sur `train_df` en entier (rigueur maximale, coût
    maximal) -- au jugement de l'appelant, qui peut se le permettre pour
    une validation ponctuelle mais pas forcément à chaque cycle.

    NOMBRE DE BOUGIES OOS (`oos_n_bars`) : `val_metrics` (le dict retourné
    par `evaluate_agent_walkforward`) est un AGRÉGAT pondéré sur plusieurs
    fenêtres -- il n'expose pas directement "le nombre de bougies OOS
    total" nécessaire pour annualiser son `total_return`. Si `val_metrics`
    contient `"per_window"` (cas normal, walk-forward multi-fenêtres), on
    estime `oos_n_bars` en sommant `n_trades`... NON -- n_trades n'est pas
    un nombre de bougies. On ne peut PAS reconstruire le nombre exact de
    bougies par fenêtre à partir de `per_window` (ce détail n'y est pas
    stocké) : on accepte donc `oos_n_bars` en paramètre EXPLICITE, à la
    charge de l'appelant (qui, lui, connaît la taille du dataset de
    validation découpé) -- choix documenté ici plutôt qu'une estimation
    silencieusement approximative qui fausserait l'annualisation sans que
    personne ne s'en aperçoive. Si `oos_n_bars` n'est pas fourni, on retombe
    sur `len(train_df)` comme approximation grossière (mieux qu'un crash,
    mais l'appelant est encouragé à toujours passer la vraie valeur).

    GESTION DES CAS DÉGÉNÉRÉS (`is_annualized_return <= 0`) : un ratio
    OOS/IS n'a de sens usuel que si la BASE (IS) est un rendement positif
    -- sinon la division produit un nombre qui n'a plus l'interprétation
    habituelle "quelle fraction de la performance IS se retrouve OOS"
    (ex: IS = -5%, OOS = -1% donnerait un ratio positif alors que les DEUX
    sont mauvais). Règle retenue, documentée pour l'appelant :
      - IS <= 0 ET OOS <= 0 : `wfe = 0.0` (les deux sont mauvais, aucune
        "efficacité" à mesurer, mais on ne veut pas non plus renvoyer un
        signal trompeur -- 0.0 reste clairement dans la zone "mauvais").
      - IS <= 0 ET OOS > 0 : `wfe = None` (cas rare et déroutant --
        performerait mieux hors-échantillon qu'en entraînement -- le ratio
        n'est pas interprétable de façon fiable ; `None` signale
        explicitement "ne pas évaluer sur cette valeur", voir
        `passes_validation` qui traite `None` comme un no-op, jamais comme
        un échec ou une réussite implicite).
    Retourne toujours `{"wfe", "is_annualized_return", "oos_annualized_return",
    "is_total_return", "oos_total_return", "is_n_trades", "oos_n_trades",
    "reason", "suspect"}` (LOT 2, phase 6 -- champs enrichis, mêmes clés
    d'origine INCHANGÉES) :
      - "reason" : None si `wfe` est un nombre normal, sinon une explication
        courte (ex: "IS<=0 et OOS<=0" / "IS<=0 et OOS>0, ratio non
        interprétable").
      - "suspect" (bool) : True si `wfe > 1.5` (généralise MIEUX
        hors-échantillon qu'en entraînement -- statistiquement suspect,
        signe fréquent d'un OOS trop court/chanceux plutôt qu'une vraie
        généralisation) OU si `oos_n_trades < min_trades_suspect` (trop peu
        de trades OOS pour faire confiance au ratio) -- jamais gaté
        automatiquement ici, seulement signalé pour revue humaine/future
        logique de gating (voir passes_validation).
    """
    bars_per_year = BARS_PER_YEAR.get(timeframe, BARS_PER_YEAR["H1"])

    train_df_tail = train_df.tail(is_eval_bars).reset_index(drop=True) if is_eval_bars else train_df
    is_metrics = evaluate_agent(agent, train_df_tail, env_kwargs, timeframe=timeframe)
    is_total_return = is_metrics["total_return"]
    is_n_bars = max(1, len(train_df_tail))
    is_annualized_return = (1 + is_total_return) ** (bars_per_year / is_n_bars) - 1

    oos_total_return = val_metrics["total_return"]
    oos_n_bars_resolved = oos_n_bars if oos_n_bars else max(1, len(train_df))
    oos_annualized_return = (1 + oos_total_return) ** (bars_per_year / oos_n_bars_resolved) - 1

    reason = None
    if is_annualized_return > 0:
        wfe = oos_annualized_return / is_annualized_return
    elif oos_annualized_return <= 0:
        wfe = 0.0  # les deux mauvais -- pas d'efficacité à mesurer, mais pas un signal positif trompeur
        reason = "IS<=0 et OOS<=0 -- aucune efficacité mesurable, wfe forcé à 0.0"
    else:
        wfe = None  # base IS <= 0 mais OOS > 0 -- ratio non interprétable de façon fiable, "ne pas gater dessus"
        reason = "IS<=0 et OOS>0 -- ratio non interprétable de façon fiable"

    is_n_trades = int(is_metrics.get("n_trades", 0))
    oos_n_trades = int(val_metrics.get("n_trades", 0))
    suspect = (wfe is not None and wfe > 1.5) or (oos_n_trades < min_trades_suspect)

    return {
        "wfe": wfe,
        "is_annualized_return": float(is_annualized_return),
        "oos_annualized_return": float(oos_annualized_return),
        "is_total_return": float(is_total_return),
        "oos_total_return": float(oos_total_return),
        "is_n_trades": is_n_trades,
        "oos_n_trades": oos_n_trades,
        "reason": reason,
        "suspect": suspect,
    }


def passes_validation(metrics: dict, cfg: dict, style=None) -> bool:
    """Un candidat "passe" s'il dépasse le Sharpe minimal, reste sous le
    drawdown maximal toléré, a été évalué sur assez de trades pour que ces
    deux chiffres soient dignes de confiance, ne s'appuie pas sur une
    fenêtre walk-forward non significative, ET ne s'est pas dégénéré en un
    agent qui ne trade quasiment plus.

    Sans le plancher de trades globaux, un candidat évalué sur une poignée
    de trades seulement (ex: un style swing D1 qui ne trade que rarement)
    peut afficher un Sharpe spectaculaire par pur coup de chance
    statistique (petit échantillon, forte variance) et passer la
    validation -- alors que rien ne prouve que ce résultat se
    reproduirait sur un échantillon plus large. `min_trades_to_go_live`
    (défaut 30) fixe ce plancher ; mettez à 0 pour désactiver (comportement
    d'origine, sharpe/drawdown seuls).

    REJET ANTI-DÉGÉNÉRESCENCE (`max_stop_exit_rate`, défaut 0.40) : cas réel
    observé sur le pilote M15 v3 (reward_type="risk_adjusted_v2", avant la
    friction asymétrique de v3) -- 72.5% des sorties se faisaient par
    stop-loss (4.4% en production), l'agent ayant appris à quasiment ne
    plus jamais agir pour éviter la pénalité de friction. Un tel agent peut
    quand même afficher un score flatteur (peu de trades = peu d'occasions
    de perdre), donc ce critère REFUSE le candidat quel que soit son score
    dès que son taux de sorties par stop dépasse ce seuil. Mettez à 1.0 (ou
    davantage) pour désactiver.

    PLANCHER PAR FENÊTRE (`min_trades_per_window`, défaut 5) : le même
    incident montrait aussi une fenêtre walk-forward tombée à 1 seul trade
    sur 5563 pas -- une mesure sur un échantillon aussi petit n'est pas
    significative, même si le total agrégé sur toutes les fenêtres dépasse
    `min_trades_to_go_live`. Ne s'applique que si `metrics` contient le
    détail par fenêtre (`per_window`, voir `evaluate_agent_walkforward`) ;
    silencieusement ignoré pour une évaluation à fenêtre unique
    (`evaluate_agent`). Mettez à 0 pour désactiver.

    PLANCHER PAR ANNÉE (`min_trades_per_year`, défaut 5, 23/09, demande
    explicite -- cas réel : un style peut agréger un nombre de trades total
    correct tout en étant quasi muet sur une année entière de la période
    walk-forward évaluée, noyée dans la moyenne par les autres années plus
    actives) : rejette un candidat dont AU MOINS UNE année suffisamment
    couverte par la période évaluée (voir `years_in_span`/`compute_metrics`
    -- une année tronquée en bord de fenêtre, avec trop peu de bougies, n'est
    jamais comptée) tombe sous ce plancher de trades. Distinct de
    `min_trades_per_window` : une fenêtre walk-forward peut très bien
    contenir plusieurs années, ce plancher-ci attrape une année dégénérée
    NOYÉE dans une fenêtre par ailleurs correcte. Silencieusement ignoré si
    `metrics` ne contient pas `years_in_span` (ex: `evaluate_agent` seul,
    sans walk-forward, ou données sans colonne "time"). Mettez à 0 pour
    désactiver.

    WALK-FORWARD EFFICIENCY (`min_wfe`, audit institutionnel item 6,
    optionnel, DÉSACTIVÉ PAR DÉFAUT) : rejette un candidat dont l'efficacité
    walk-forward (voir `compute_walk_forward_efficiency`) tombe sous ce
    seuil -- un signal de surapprentissage (bon en entraînement, mauvais
    hors-échantillon) distinct du Sharpe/drawdown OOS seuls. Suit
    EXACTEMENT le même principe "no-op sauf configuration explicite" que
    les autres critères ci-dessus : ignoré si `cfg["validation"]` ne
    contient pas `min_wfe`, ET ignoré si `metrics` ne contient pas de clé
    `"wfe"` (ex: l'appelant n'a pas encore câblé `compute_walk_forward_
    efficiency` dans son pipeline) OU si cette clé vaut `None` (WFE non
    interprétable pour ce candidat, voir `compute_walk_forward_efficiency`
    -- ne doit jamais faire échouer ni réussir silencieusement un candidat
    sur une valeur qui n'a pas de sens).
    """
    v = cfg["validation"]

    per_window = metrics.get("per_window")
    if per_window:
        min_per_window = v.get("min_trades_per_window", 5)
        if any(w.get("n_trades", 0) < min_per_window for w in per_window):
            return False

    years_in_span = metrics.get("years_in_span")
    if years_in_span:
        min_per_year = v.get("min_trades_per_year", 5)
        trades_by_year = metrics.get("trades_by_year", {})
        if any(trades_by_year.get(year, 0) < min_per_year for year in years_in_span):
            return False

    # PLANCHER SUR LES SCÉNARIOS DE STRESS (22/09, bug réel observé sur H4
    # gen:134 et D1 gen:327 -- tous deux VALIDÉS et déployés en démo malgré
    # 0 trade sur toute la fenêtre de stress "garch" (queues épaisses/
    # clustering de volatilité, voir src/stress_test.py::garch_stress_dataset).
    # `stress_windows` n'était jusqu'ici jamais contrôlé par cette fonction
    # (seulement affiché/archivé dans meta.json) -- un candidat pouvait donc
    # se figer complètement (0 trade) sous un régime de volatilité difficile
    # et passer quand même, exactement le même type de dégénérescence que le
    # plancher `min_trades_per_window` ci-dessus corrige déjà pour les
    # fenêtres walk-forward normales. `min_trades_per_stress_window` (défaut
    # 1, càd "pas complètement figé") : mettez à 0 pour désactiver.
    stress_windows = metrics.get("stress_windows")
    if stress_windows:
        min_per_stress_window = v.get("min_trades_per_stress_window", 1)
        if any(w.get("n_trades", 0) < min_per_stress_window for w in stress_windows):
            return False

    max_stop_rate = (v.get("max_stop_exit_rate_by_style") or {}).get(style, v.get("max_stop_exit_rate", 0.40))
    if metrics.get("stop_exit_rate", 0.0) > max_stop_rate:
        return False

    # RETARD MAXIMAL SUR LE MARCHÉ (`max_lag_vs_market_pts`, 25/09, demande
    # explicite -- voir `compute_metrics`) : rejette un candidat qui, sur AU
    # MOINS UNE fenêtre walk-forward, fait plus de X points de moins que le
    # buy-and-hold de l'instrument (ex: 0.10 = rester plat pendant une année
    # à +18% est refusé, rester plat une année à -3% est accepté). Même
    # principe "no-op sauf configuration explicite" que `min_wfe` : ignoré si
    # la clé est absente de la config ou si les fenêtres n'ont pas
    # d'`excess_return` (anciens meta.json).
    max_lag = v.get("max_lag_vs_market_pts")
    if max_lag is not None and per_window:
        if any(w.get("excess_return") is not None and w["excess_return"] < -max_lag
               for w in per_window):
            return False

    if v.get("min_wfe") is not None and metrics.get("wfe") is not None:
        if metrics["wfe"] < v["min_wfe"]:
            return False

    min_sharpe = (v.get("min_sharpe_to_go_live_by_style") or {}).get(style, v["min_sharpe_to_go_live"])
    return (
        metrics["sharpe"] >= min_sharpe
        and metrics["max_drawdown"] <= v["max_drawdown_allowed"]
        and metrics.get("n_trades", 0) >= v.get("min_trades_to_go_live", 30)
    )
