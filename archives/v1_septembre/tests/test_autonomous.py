"""
test_autonomous.py
===================
Vérifie, sans MT5 réel ni internet, que :
  - la boucle d'évolution continue crée un champion (par style) au premier
    cycle puis l'améliore par warm start au cycle suivant (jamais de retour
    à zéro) ;
  - plusieurs styles de trading (timeframes primaires différentes) évoluent
    bien EN PARALLÈLE, avec des jeux de features distincts dérivés
    automatiquement, et que le meilleur des styles est celui éligible à la
    démo ;
  - la boucle de trading en démo recharge le champion (et son style
    dynamique) et prend des décisions ;
  - le volume de données bascule bien selon les heures de marché XAUUSD ;
  - le suivi anti-surapprentissage (plateau) fonctionne et persiste ;
  - le garde-fou de sécurité MT5Connector bloque tout ordre réel sur un
    compte qui n'est pas détecté comme démo, même si dry_run=False.
"""
import sys, os, types, threading
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np

from src.continuous_trainer import ContinuousEvolutionTrainer
from src.demo_trader import run_demo_trading_loop
from src.mt5_connector import MT5Connector
from src.episodic_memory import EpisodicMemory
from src.features import FEATURE_COLUMNS, add_technical_features, normalize_features
from src.data_loader import generate_synthetic_ohlcv, chronological_split

BASE_CFG = {
    "agent": {"policy": "MlpPolicy", "learning_rate": 3e-4, "n_steps": 128,
              "batch_size": 32, "gamma": 0.99, "gae_lambda": 0.95, "ent_coef": 0.01},
    "continuous": {"candidates_per_cycle": 2, "timesteps_per_cycle": 256, "mutation_scale": 0.2},
    "memory": {"db_path": None, "max_episodes": 500},
}


def _make_data_fn(n_bars=2000, seed=3):
    """Fournisseur de données à un seul style pour les tests qui ne portent
    pas spécifiquement sur le pool multi-style (signature compatible :
    accepte primary_tf mais l'ignore, retourne toujours le même jeu)."""
    def get_data(primary_tf=None):
        df = generate_synthetic_ohlcv(n_bars=n_bars, seed=seed)
        df = add_technical_features(df)
        train_df, val_df, _ = chronological_split(df, 0.7, 0.3)
        train_df, stats = normalize_features(train_df, columns=FEATURE_COLUMNS)
        val_df, _ = normalize_features(val_df, stats, columns=FEATURE_COLUMNS)
        return train_df, val_df, stats, FEATURE_COLUMNS, []
    return get_data


def test_episodic_memory_created_in_one_thread_used_in_another(tmp_path):
    """Reproduit exactement le bug remonté en usage réel : EpisodicMemory
    instanciée dans le thread principal (comme le fait autonomous_agent.py),
    puis utilisée depuis un thread séparé (comme le fait la boucle
    d'évolution continue). Sans check_same_thread=False, sqlite3 lève
    'SQLite objects created in a thread can only be used in that same thread'.
    """
    db_path = str(tmp_path / "mem_threaded.sqlite")
    memory = EpisodicMemory(db_path, max_episodes=100)  # créée dans le thread principal

    errors = []

    def worker():
        try:
            for i in range(5):
                memory.store(context=np.array([1.0, 2.0, 3.0]), action=1,
                             pnl_pct=0.01, drawdown=0.02, generation=i)
            snap = memory.snapshot(dim=3)
            assert len(snap[0]) == 5
        except Exception as e:
            errors.append(e)

    t = threading.Thread(target=worker, name="EVOLUTION")
    t.start()
    t.join(timeout=10)

    assert not errors, f"Erreur cross-thread : {errors}"
    memory.close()


def test_episodic_memory_training_snapshot_excludes_live_episodes(tmp_path):
    """Reproduit et corrige une vraie fuite d'information trouvée le 15/09 :
    la mémoire épisodique est partagée entre l'entraînement (backtest sur
    données historiques) et le trading live (MT5 réel), sans aucune
    distinction de source. Un trade réel de la nuit (contexte de marché très
    récent) pouvait donc être retrouvé par similarité pendant l'évaluation
    d'un candidat sur une fenêtre historique bien ANTÉRIEURE -- une fuite du
    futur vers le passé qui gonflait artificiellement la vraisemblance des
    scores.

    Corrigé en étiquetant chaque épisode par sa source ("backtest" ou
    "live") : continuous_trainer.py ne demande désormais QUE les épisodes
    "backtest" pour construire le signal mémoire donné aux candidats, tandis
    que demo_trader.py (décision live réelle) continue de voir tout
    l'historique -- ça, ce n'est pas une fuite, une décision prise
    aujourd'hui a le droit de s'appuyer sur toute l'expérience déjà connue."""
    db_path = str(tmp_path / "mem_sources.sqlite")
    memory = EpisodicMemory(db_path, max_episodes=100)

    memory.store(context=np.array([1.0, 2.0, 3.0]), action=1,
                 pnl_pct=0.05, drawdown=0.01, generation=10, source="backtest")
    memory.store(context=np.array([9.0, 9.0, 9.0]), action=-1,
                 pnl_pct=-0.30, drawdown=0.30, generation=999, source="live")

    training_snapshot = memory.snapshot(dim=3, sources=["backtest"])
    contexts, pnls, drawdowns = training_snapshot
    assert len(contexts) == 1, "l'épisode live ne doit JAMAIS apparaître dans le signal d'entraînement"
    assert abs(pnls[0] - 0.05) < 1e-6  # float32 : comparaison approchée

    live_snapshot = memory.snapshot(dim=3)
    assert len(live_snapshot[0]) == 2, "sans filtre (décision live réelle), les deux sources doivent apparaître"

    memory.close()


def test_style_runtime_defers_reload_while_position_open(tmp_path, monkeypatch):
    """Garde-fou demandé explicitement par l'utilisateur le 15/09 : une
    position réelle ouverte par la génération N d'un style ne doit JAMAIS se
    retrouver gérée/fermée par la génération N+1 fraîchement promue -- deux
    "avis" différents sur le même trade, un risque concret par exemple juste
    avant une fermeture de marché. `_StyleRuntime.maybe_reload` doit reporter
    le chargement d'une nouvelle version tant qu'une position est ouverte,
    mais ne JAMAIS bloquer le tout premier chargement d'un style qui vient
    de devenir éligible (rien à préserver dans ce cas)."""
    monkeypatch.chdir(tmp_path)
    import types
    from src.demo_trader import _StyleRuntime
    import src.demo_trader as demo_trader_module

    def _boom(*a, **k):
        raise AssertionError("ne doit pas être appelé : le rechargement aurait dû être reporté ou bloqué avant")

    monkeypatch.setattr(demo_trader_module, "_build_live_dataframe", _boom)

    rt = _StyleRuntime()
    rt.agent = object()  # simule un style DÉJÀ chargé (pas un premier chargement)
    rt.last_loaded_at = 1000.0

    from src.trading_env import ENV_VERSION
    entry = {"style": "H1", "meta": {"updated_at": 2000.0, "generation": 42, "score": 3.0,
                                       "feature_columns": ["x"], "primary_timeframe": "H1",
                                       "context_timeframes": [], "env_version": ENV_VERSION}}

    open_connector = types.SimpleNamespace(get_open_positions_by_style=lambda styles: {
        "H1": {"ticket": 123, "direction": 1, "volume": 0.01, "price_open": 4300.0,
               "sl": 4250.0, "profit": -5.0},
    })
    rt.maybe_reload(entry, open_connector, None, 100, 100, None, 5, {})
    assert rt.last_loaded_at == 1000.0, "le rechargement doit être REPORTÉ tant qu'une position est ouverte"

    # Position fermée entre-temps (compte à plat) -- le rechargement doit
    # maintenant être TENTÉ (on vérifie juste qu'il n'est plus bloqué par le
    # garde-fou : _build_live_dataframe doit être appelé, d'où le sentinel
    # _boom qui lève une erreur reconnaissable plutôt que de charger un vrai
    # modèle).
    flat_connector = types.SimpleNamespace(get_open_positions_by_style=lambda styles: {})
    try:
        rt.maybe_reload(entry, flat_connector, None, 100, 100, None, 5, {})
        assert False, "aurait dû lever via le sentinel _build_live_dataframe"
    except AssertionError as e:
        assert "ne doit pas être appelé" in str(e)

    # Premier chargement d'un style tout juste éligible (self.agent est None)
    # : ne doit JAMAIS être bloqué, même avec une position ouverte -- rien à
    # préserver, ce style n'a encore rien décidé.
    rt2 = _StyleRuntime()
    try:
        rt2.maybe_reload(entry, open_connector, None, 100, 100, None, 5, {})
        assert False, "aurait dû lever via le sentinel _build_live_dataframe (1er chargement jamais bloqué)"
    except AssertionError as e:
        assert "ne doit pas être appelé" in str(e)


def test_style_runtime_reload_not_deferred_by_another_style_position(tmp_path, monkeypatch):
    """Bug réel trouvé le 21/09 en observant M30 rester bloqué sur sa toute
    première version pendant des heures en démo : `maybe_reload` interrogeait
    LA position du SYMBOLE entier (`get_open_position_info`), donc une
    position ouverte par H4 reportait aussi le rechargement de M30, qui
    n'avait pourtant lui-même aucune position à préserver. Avec le
    multi-position indépendant par style (LOT 2), une position d'un AUTRE
    style ne doit JAMAIS reporter le rechargement de celui-ci."""
    monkeypatch.chdir(tmp_path)
    import types
    from src.demo_trader import _StyleRuntime
    import src.demo_trader as demo_trader_module

    def _boom(*a, **k):
        raise AssertionError("ne doit pas être appelé : le rechargement aurait dû être reporté ou bloqué avant")

    monkeypatch.setattr(demo_trader_module, "_build_live_dataframe", _boom)

    rt = _StyleRuntime()
    rt.agent = object()  # simule un style DÉJÀ chargé (pas un premier chargement)
    rt.last_loaded_at = 1000.0

    from src.trading_env import ENV_VERSION
    entry = {"style": "M30", "meta": {"updated_at": 2000.0, "generation": 173, "score": 3.19,
                                        "feature_columns": ["x"], "primary_timeframe": "M30",
                                        "context_timeframes": [], "env_version": ENV_VERSION}}

    # Position ouverte pour H4 UNIQUEMENT -- rien pour M30, le style qu'on
    # recharge ici.
    other_style_connector = types.SimpleNamespace(get_open_positions_by_style=lambda styles: {
        "H4": {"ticket": 999, "direction": -1, "volume": 0.5, "price_open": 4380.0,
               "sl": 4418.0, "profit": 12.0},
    })
    try:
        rt.maybe_reload(entry, other_style_connector, None, 100, 100, None, 5, {})
        assert False, "aurait dû lever via le sentinel _build_live_dataframe (rechargement JAMAIS reporté par une position d'un AUTRE style)"
    except AssertionError as e:
        assert "ne doit pas être appelé" in str(e)


def test_reentry_cooldown_blocks_immediate_reopen_after_close():
    """Cœur du garde-fou de fréquence : une fermeture immédiatement suivie
    d'une tentative de RÉOUVERTURE (départ de plat) doit être bloquée tant
    que min_reentry_cooldown_minutes ne s'est pas écoulé."""
    from src.demo_trader import _StyleRuntime
    rt = _StyleRuntime()

    now = 1_000_000.0
    # Position ouverte (target=1.0), puis fermeture (target=0.0) à t=now.
    assert rt.apply_reentry_cooldown("D1", 1.0, cooldown_minutes=15, now=now) == 1.0
    assert rt.apply_reentry_cooldown("D1", 0.0, cooldown_minutes=15, now=now) == 0.0

    # Tentative de réouverture 1 minute plus tard (cooldown de 15 min actif)
    # -> bloquée, doit rester à plat (0.0), jamais le -1.0 demandé.
    blocked = rt.apply_reentry_cooldown("D1", -1.0, cooldown_minutes=15, now=now + 60)
    assert blocked == 0.0, f"réouverture pendant le cooldown doit être bloquée (0.0), obtenu {blocked}"


def test_reentry_cooldown_allows_reopen_after_cooldown_elapsed():
    """Une fois min_reentry_cooldown_minutes écoulé, une nouvelle ouverture
    doit passer normalement -- le garde-fou est temporaire, pas définitif."""
    from src.demo_trader import _StyleRuntime
    rt = _StyleRuntime()

    now = 2_000_000.0
    rt.apply_reentry_cooldown("H1", 1.0, cooldown_minutes=15, now=now)
    rt.apply_reentry_cooldown("H1", 0.0, cooldown_minutes=15, now=now)

    # 15 minutes et 1 seconde plus tard -> cooldown écoulé, réouverture autorisée.
    allowed = rt.apply_reentry_cooldown("H1", 1.0, cooldown_minutes=15, now=now + 15 * 60 + 1)
    assert allowed == 1.0, f"réouverture après le cooldown doit passer (1.0), obtenu {allowed}"


def test_reentry_cooldown_never_blocks_a_closing_decision():
    """RÈGLE ABSOLUE de la demande : une décision de FERMETURE (retour à
    plat, ou retournement vers le sens opposé) ne doit JAMAIS être bloquée,
    quel que soit le timing -- même si un cooldown est actif au moment
    précis de cette fermeture (ex: un cooldown resté actif depuis avant
    l'ouverture de la position qu'on ferme maintenant)."""
    from src.demo_trader import _StyleRuntime
    rt = _StyleRuntime()

    now = 3_000_000.0
    # Un cooldown est "en cours" depuis peu (ex: une fermeture précédente,
    # avant même l'ouverture de la position actuelle) ; on force cet état
    # directement pour isoler le comportement de la fermeture.
    rt.cooldown_last_close_at = now - 30  # cooldown démarré il y a 30s
    rt.cooldown_prev_target = 1.0  # une position EST actuellement ouverte

    # Décision de fermeture (retour à plat) 1 seconde après -- doit passer
    # IMMÉDIATEMENT, le cooldown ne concerne jamais une sortie.
    result = rt.apply_reentry_cooldown("M15", 0.0, cooldown_minutes=15, now=now)
    assert result == 0.0, "une fermeture ne doit jamais être bloquée, quel que soit le cooldown en cours"

    # Idem pour un retournement direct (1.0 -> -1.0) : la partie "sortie" de
    # la position actuelle doit passer (ramenée à plat ce cycle-ci), seule
    # la réouverture dans le nouveau sens est reportée -- jamais un blocage
    # pur et simple qui laisserait la position d'origine ouverte malgré elle.
    rt2 = _StyleRuntime()
    rt2.cooldown_last_close_at = now - 5
    rt2.cooldown_prev_target = 1.0
    result2 = rt2.apply_reentry_cooldown("M15", -1.0, cooldown_minutes=15, now=now)
    assert result2 == 0.0, (
        "un retournement doit toujours laisser sortir la position actuelle (0.0 ce cycle), "
        f"jamais forcer le maintien de l'ancienne position ou ouvrir directement l'inverse -- obtenu {result2}"
    )


def test_reentry_cooldown_is_independent_per_style():
    """Le cooldown est PAR STYLE (une instance _StyleRuntime par style, voir
    runtimes dans run_demo_trading_loop) -- un retournement rapide sur D1 ne
    doit jamais affecter le cooldown de M15."""
    from src.demo_trader import _StyleRuntime
    rt_d1 = _StyleRuntime()
    rt_m15 = _StyleRuntime()

    now = 4_000_000.0
    rt_d1.apply_reentry_cooldown("D1", 1.0, cooldown_minutes=15, now=now)
    rt_d1.apply_reentry_cooldown("D1", 0.0, cooldown_minutes=15, now=now)  # D1 en cooldown

    # M15, jamais touché, doit pouvoir ouvrir immédiatement -- son propre
    # cooldown n'a jamais démarré.
    m15_result = rt_m15.apply_reentry_cooldown("M15", 1.0, cooldown_minutes=15, now=now + 1)
    assert m15_result == 1.0, "le cooldown de D1 ne doit jamais bloquer une ouverture légitime sur M15"

    # Et D1, lui, reste bien bloqué en parallèle.
    d1_result = rt_d1.apply_reentry_cooldown("D1", 1.0, cooldown_minutes=15, now=now + 1)
    assert d1_result == 0.0, "D1 doit rester en cooldown indépendamment de M15"


def test_no_gpu_messages_logged(tmp_path, monkeypatch, capsys=None):
    """Répond directement à la demande de supprimer les messages GPU du
    terminal : instancie un agent et vérifie qu'aucun log ne mentionne le
    GPU/CUDA (peu importe qu'un GPU soit présent ou non sur la machine)."""
    monkeypatch.chdir(tmp_path)
    import logging, io
    from src.agent import TradingAgent
    from src.trading_env import TradingEnv

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    agent_logger = logging.getLogger("agent")
    agent_logger.addHandler(handler)
    agent_logger.setLevel(logging.INFO)
    try:
        df = generate_synthetic_ohlcv(n_bars=200, seed=1)
        df = add_technical_features(df)
        df, _ = normalize_features(df, columns=FEATURE_COLUMNS)
        env = TradingEnv(df, window_size=20, feature_columns=FEATURE_COLUMNS)
        TradingAgent(env, {"n_steps": 32, "batch_size": 16, "device": "cpu"})
    finally:
        agent_logger.removeHandler(handler)

    output = stream.getvalue()
    assert "GPU" not in output and "CUDA" not in output, \
        f"un message GPU/CUDA a été journalisé alors qu'il ne devrait plus l'être : {output!r}"


def test_progress_callback_logs_during_training(tmp_path, monkeypatch):
    """Répond à la demande de plus d'informations d'avancement pendant les
    cycles : vérifie qu'un label de progression apparaît bien dans les logs
    pendant l'entraînement d'un candidat."""
    monkeypatch.chdir(tmp_path)
    import logging, io
    from src.agent import TradingAgent
    from src.trading_env import TradingEnv

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    agent_logger = logging.getLogger("agent")
    agent_logger.addHandler(handler)
    agent_logger.setLevel(logging.INFO)
    try:
        df = generate_synthetic_ohlcv(n_bars=300, seed=1)
        df = add_technical_features(df)
        df, _ = normalize_features(df, columns=FEATURE_COLUMNS)
        env = TradingEnv(df, window_size=20, feature_columns=FEATURE_COLUMNS)
        agent = TradingAgent(env, {"n_steps": 32, "batch_size": 16, "device": "cpu"})
        agent.learn(128, label="[TEST candidat]")
    finally:
        agent_logger.removeHandler(handler)

    output = stream.getvalue()
    assert "[TEST candidat]" in output, "le label de progression doit apparaître dans les logs"
    assert "%" in output, "un pourcentage d'avancement doit être journalisé"


def test_agent_chosen_stop_loss_triggers_on_bar_low_discrete(tmp_path, monkeypatch):
    """Répond directement à la demande explicite de l'utilisateur : 'il faut
    laisser decider le stop loss au agent... ca doit etre des trader, pas
    des robot'. Vérifie que (1) la distance de stop vient de l'ACTION du
    modèle (un bucket parmi agent.stop_loss_buckets), pas d'un pourcentage
    fixe imposé par la config, et (2) le stop se déclenche dès que le PLUS
    BAS réel d'une bougie le franchit -- pas seulement sa clôture --
    exactement comme un stop côté broker, AVANT que la nouvelle décision de
    l'agent ne soit traitée."""
    monkeypatch.chdir(tmp_path)
    import pandas as pd
    from src.trading_env import TradingEnv

    n = 10
    df = pd.DataFrame({
        "open": [100.0] * n, "high": [100.0] * n, "low": [100.0] * n, "close": [100.0] * n,
        "volume": [1.0] * n,
    })
    # bougie n°4 : plus bas à 95, largement sous le stop attendu (~97.02, voir
    # ci-dessous). LATENCE D'EXÉCUTION (audit institutionnel, item 4) : une
    # décision prise au pas n°3 (window_size=3, donc premier step() traité)
    # remplit désormais à l'OUVERTURE de la bougie n°4 (98.0), pas à la
    # clôture de la n°3 (100.0) -- voir TradingEnv.step(). D'où stop_price =
    # 98.0 * (1 - 1%) = 97.02, PAS 100 * (1-1%) = 99 (ancien comportement,
    # avant la latence T+1).
    df.loc[4, ["open", "high", "low", "close"]] = [98.0, 100.0, 95.0, 96.0]

    env = TradingEnv(df, window_size=3, feature_columns=["close"],
                      learn_stop_loss=True, stop_loss_buckets=[0.01], transaction_cost=0.0)
    env.reset()
    assert list(env.action_space.nvec) == [3, 1], "MultiDiscrete(direction, distance de stop) attendu"

    env.step([2, 0])  # long, stop = bucket 0 = 1%
    assert env.position == 1
    # Rempli à l'ouverture de la bougie n°4 (98.0, latence T+1) -- pas la
    # clôture de la n°3 (100.0, comportement d'avant la latence d'exécution).
    assert abs(env.entry_price - 98.0) < 1e-9, "l'entrée doit être remplie à l'OUVERTURE de T+1, pas à la clôture de T"
    assert abs(env.stop_price - 97.02) < 1e-9, "le stop doit venir du bucket choisi par l'agent (1% de l'entrée réelle), pas d'un défaut"

    env.step([1, 0])  # l'agent demande flat -- mais le stop a dû agir avant ça
    assert env.position == 0, "le stop doit clôturer la position AVANT que la nouvelle action ne soit traitée"
    assert len(env.trade_log) == 1
    assert env.trade_log[0]["stopped_out"] is True
    assert abs(env.trade_log[0]["pnl_pct"] - (-0.01)) < 1e-9, "perte réalisée au prix du STOP (99), pas à la clôture (96)"


def test_agent_chosen_stop_loss_continuous_decoding(tmp_path, monkeypatch):
    """Même vérification que le test discret, mais pour SAC/TD3 (action
    continue) : la 2e dimension de l'action doit être mise à l'échelle sur
    agent.stop_loss_range, pas ignorée."""
    monkeypatch.chdir(tmp_path)
    import pandas as pd
    from src.trading_env import TradingEnv

    n = 10
    df = pd.DataFrame({
        "open": [100.0] * n, "high": [100.0] * n, "low": [100.0] * n, "close": [100.0] * n,
        "volume": [1.0] * n,
    })

    env = TradingEnv(df, window_size=3, feature_columns=["close"], continuous_action=True,
                      learn_stop_loss=True, stop_loss_range=(0.0, 0.10), transaction_cost=0.0)
    env.reset()
    assert env.action_space.shape == (2,)

    env.step(np.array([1.0, 0.0], dtype=np.float32))  # position pleine, milieu de la plage -> 5%
    assert env.position == 1
    assert abs(env.stop_price - 95.0) < 1e-6, "0.0 (milieu de [-1,1]) doit correspondre au milieu de stop_loss_range"


def test_stop_loss_inactive_when_learn_stop_loss_disabled(tmp_path, monkeypatch):
    """Garde-fou de non-régression : sans agent.learn_stop_loss (comportement
    d'origine, PPO discret classique), aucun stop n'est simulé -- une
    position survit à une bougie qui aurait pourtant franchi n'importe quel
    seuil raisonnable."""
    monkeypatch.chdir(tmp_path)
    import pandas as pd
    from src.trading_env import TradingEnv

    n = 10
    df = pd.DataFrame({
        "open": [100.0] * n, "high": [100.0] * n, "low": [100.0] * n, "close": [100.0] * n,
        "volume": [1.0] * n,
    })
    df.loc[4, ["open", "high", "low", "close"]] = [98.0, 100.0, 50.0, 96.0]  # chute violente

    env = TradingEnv(df, window_size=3, feature_columns=["close"], transaction_cost=0.0)
    env.reset()
    env.step(2)  # long
    assert env.position == 1
    env.step(2)  # reste long malgré la bougie violente -- aucun stop actif
    assert env.position == 1
    assert env.trade_log == [], "aucune clôture forcée sans agent.learn_stop_loss"


def test_min_generations_before_demo_gate(tmp_path, monkeypatch):
    """Répond directement à la demande : même un candidat avec d'EXCELLENTES
    métriques ne doit PAS être envoyé en démo avant que le nombre minimal de
    générations configuré ne soit atteint.
    """
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct

    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1}
    cfg["memory"] = {"db_path": "mem3.sqlite", "max_episodes": 500}
    cfg["validation"] = {"min_sharpe_to_go_live": 1.0, "max_drawdown_allowed": 0.20,
                         "min_generations_before_demo": 3}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)

    def excellent_metrics(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": 0.3, "sharpe": 3.0, "max_drawdown": 0.05,
                "win_rate": 0.6, "profit_factor": 2.5, "n_trades": 50}

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=excellent_metrics):
        trainer.run_one_cycle()
        assert trainer.has_demo_champion() is False, \
            "générations insuffisantes : ne doit pas encore être envoyé en démo"
        trainer.run_one_cycle()
        assert trainer.has_demo_champion() is False, \
            "générations toujours insuffisantes (2/3)"
        trainer.run_one_cycle()
        assert trainer.has_demo_champion() is True, \
            "le seuil de 3 générations est atteint : doit maintenant être promu"
    trainer.close()


def test_notify_every_cycle_sends_start_and_summary_alerts(tmp_path, monkeypatch):
    """Répond directement à la demande d'une notification au LANCEMENT de
    chaque cycle (en plus de celle de fin de cycle déjà en place, et de
    celle du coupe-circuit) : vérifie que les deux sont envoyées pour un
    cycle notifié, aucune pour un cycle sauté, et que `notify_cycle_every_n`
    continue de gouverner les deux de la même façon sans rien changer à la
    logique d'entraînement elle-même."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct

    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1}
    cfg["memory"] = {"db_path": "mem_notify.sqlite", "max_episodes": 500}
    cfg["notifications"] = {"enabled": True, "channel": "ntfy", "ntfy_topic": "x",
                             "notify_every_cycle": True, "notify_cycle_every_n": 2}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)

    with patch("src.notifier.send_alert") as mock_alert:
        trainer.run_one_cycle()  # génération 1 -> 1 % 2 != 0, pas d'alerte
        assert mock_alert.call_count == 0, "notify_cycle_every_n=2 : pas d'alerte au cycle 1"
        trainer.run_one_cycle()  # génération 2 -> 2 % 2 == 0, alerte de lancement ET de fin
        assert mock_alert.call_count == 2, "notify_cycle_every_n=2 : lancement + fin au cycle 2"
        start_subject = mock_alert.call_args_list[0].kwargs["subject"].lower()
        assert "cycle 2" in start_subject and "démarré" in start_subject
        _, end_kwargs = mock_alert.call_args_list[1]
        assert "cycle 2" in end_kwargs["subject"].lower()
        message = end_kwargs["message"]
        assert "cycle(s) sans nouveau record" in message
        assert "record absolu" in message.lower()
        # le message doit MENER avec le progrès par style, le compteur
        # global de stagnation étant relégué en repère secondaire en fin de
        # message (pour éviter qu'un compteur global figé masque un progrès
        # réel sur d'autres styles -- voir _format_score_delta ci-dessous)
        assert message.index("Styles :") < message.index("cycle(s) sans nouveau record")
    trainer.close()


def test_format_score_delta_shows_percentage_or_absolute():
    """Test unitaire de _format_score_delta : le mot "score" doit TOUJOURS
    être présent (jamais confondu avec un rendement financier -- cas réel :
    un style passant de -1.01 à +2.15 affichait "+311%", qui avait pu être
    lu à tort comme un gain de trading). Pourcentage par rapport au score
    précédent -- y compris à travers un changement de signe (sur demande
    explicite de l'utilisateur : le pourcentage donne un ordre de grandeur
    utile même dans ce cas, le préfixe "score" suffit à éviter la
    confusion) -- sauf variation absolue si le score précédent est trop
    proche de zéro (pourcentage mathématiquement absurde, ex: +50000%).
    Chaîne vide sans score précédent connu."""
    from src.continuous_trainer import _format_score_delta

    assert _format_score_delta(0.90, None) == ""

    up = _format_score_delta(0.905, 0.90)
    assert "score" in up and "%" in up and "+" in up

    down = _format_score_delta(0.80, 0.90)
    assert "score" in down and "-" in down

    near_zero = _format_score_delta(0.5, 0.0)
    assert "score" in near_zero and "%" not in near_zero, \
        "un score précédent quasi nul doit rester en variation absolue (pourcentage infini sinon)"

    sign_flip = _format_score_delta(2.15, -1.01)
    assert "score" in sign_flip and "%" in sign_flip, \
        "un changement de signe doit maintenant afficher un pourcentage (demande explicite), " \
        "le préfixe \"score\" suffit à éviter la confusion avec un rendement financier"


def test_confidence_marker_flags_scores_backed_by_too_few_trades():
    """Test unitaire de _confidence_marker : répond au cas réel rencontré
    cette nuit (D1 passé de 4.69 à 4.10 en franchissant 100 trades -- un
    VRAI progrès illisible comme tel dans une notification, ressemblant à
    une régression). ✓ à partir du seuil de confiance, △ en dessous,
    toujours ✓ si le mécanisme est désactivé (seuil <= 0)."""
    from src.continuous_trainer import _confidence_marker

    assert _confidence_marker(70, 100) == "△"
    assert _confidence_marker(100, 100) == "✓"
    assert _confidence_marker(112, 100) == "✓"
    assert _confidence_marker(0, 0) == "✓"


def test_resolve_max_bars_gives_more_history_to_overridden_styles():
    """Répond directement à la demande d'améliorer les timeframes courtes :
    vérifie que `data.max_bars_by_style` donne bien PLUS d'historique au
    style surchargé (M15), laisse les autres (H4) sur le plafond global, et
    ne réduit JAMAIS un plafond déjà "illimité" (None -- typiquement
    max_bars_market_closed) avec une surcharge pensée pour le marché
    ouvert."""
    from autonomous_agent import _resolve_max_bars

    overrides = {"M15": 150000, "H1": 100000}
    assert _resolve_max_bars("M15", 60000, overrides) == 150000
    assert _resolve_max_bars("H1", 60000, overrides) == 100000
    assert _resolve_max_bars("H4", 60000, overrides) == 60000, "un style non listé garde le plafond global"
    assert _resolve_max_bars("D1", 60000, {}) == 60000, "aucune surcharge configurée -> comportement d'origine"
    assert _resolve_max_bars("M15", None, overrides) is None, \
        "un plafond de base illimité (marché fermé) ne doit jamais être RÉDUIT par une surcharge"


def test_resolve_stress_test_per_style_override():
    """Répond directement à la demande d'activer le stress-test (anti-
    mémorisation) sur les styles voulus : la liste stress_test_styles, si
    configurée, l'emporte sur le réglage global ; sans liste, le réglage
    global s'applique à tous les styles uniformément (comportement
    d'origine)."""
    from src.continuous_trainer import _resolve_stress_test

    assert _resolve_stress_test("D1", True, None) is True, "sans liste, le réglage global s'applique partout"
    assert _resolve_stress_test("M15", True, None) is True
    assert _resolve_stress_test("D1", False, ["H4", "D1"]) is True, "présent dans la liste -> activé"
    assert _resolve_stress_test("M15", False, ["H4", "D1"]) is False, "absent de la liste -> pas activé"
    assert _resolve_stress_test("M15", True, ["H4", "D1"]) is False, \
        "la liste l'emporte sur le réglage global même quand celui-ci est activé"


def test_stress_seed_stable_per_style_not_per_cycle():
    """Répond directement à l'observation que le stress-test comparait
    chaque candidat à un scénario DIFFÉRENT à chaque cycle (l'ancienne
    graine dépendait de la génération) : vérifie que la graine ne dépend
    plus que du style, jamais du cycle en cours."""
    from src.continuous_trainer import _stress_seed_for_style

    assert _stress_seed_for_style("D1") == _stress_seed_for_style("D1")
    assert _stress_seed_for_style("D1") != _stress_seed_for_style("M15")


def test_block_bootstrap_rebases_price_no_teleport():
    """Répond directement à la demande : le stress-test ne doit jamais
    produire une bougie à 100$ suivie d'une bougie à 4000$. Simule un
    historique qui part de 100$ et grimpe à 4000$ (comme XAUUSD 2004 vs
    aujourd'hui -- le pire cas pour cet artefact) et vérifie qu'après
    réordonnancement des blocs, aucun écart de prix entre bougies
    consécutives ne dépasse largement ce qui existe déjà DANS les
    données d'origine, et que la cohérence OHLC (high >= open/close >= low)
    reste respectée après la mise à l'échelle."""
    import numpy as np
    import pandas as pd
    from src.stress_test import block_bootstrap_rows

    n = 1000
    prices = np.linspace(100, 4000, n)
    df = pd.DataFrame({
        "open": prices, "high": prices * 1.001, "low": prices * 0.999,
        "close": prices, "volume": np.ones(n),
    })
    max_real_step = df["close"].pct_change().abs().max()

    result = block_bootstrap_rows(df, block_size=50, seed=1)
    steps = result["close"].pct_change().abs().dropna()
    assert steps.max() < max_real_step * 5, \
        f"écart de prix anormal détecté à une jonction de blocs : {steps.max():.2%} (max réel : {max_real_step:.2%})"
    assert (result["high"] >= result[["open", "close"]].max(axis=1) - 1e-6).all()
    assert (result["low"] <= result[["open", "close"]].min(axis=1) + 1e-6).all()


def test_high_volatility_subset_rebases_price_no_teleport():
    """Même vérification que ci-dessus, pour high_volatility_subset : les
    fenêtres les plus volatiles sélectionnées ne sont pas forcément
    adjacentes dans le temps, donc exposées au même risque de
    téléportation de prix."""
    import numpy as np
    import pandas as pd
    from src.stress_test import high_volatility_subset

    n = 3000
    prices = np.linspace(100, 4000, n)
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 0.001, n)
    noise[500:1000] *= 20    # fenêtre très volatile, tôt (prix bas)
    noise[2000:2500] *= 20   # fenêtre très volatile, tard (prix haut) -- non adjacente à la première
    close = np.abs(prices * (1 + np.cumsum(noise)))
    df = pd.DataFrame({
        "open": close, "high": close * 1.001, "low": close * 0.999,
        "close": close, "volume": np.ones(n),
    })
    max_real_step = pd.Series(close).pct_change().abs().max()

    result = high_volatility_subset(df, window_size=500, top_k=2)
    steps = result["close"].pct_change().abs().dropna()
    assert steps.max() < max_real_step * 5, \
        f"écart de prix anormal détecté entre fenêtres non adjacentes : {steps.max():.2%}"


def test_stress_test_applied_per_style_in_real_cycle(tmp_path, monkeypatch):
    """Vérifie, à travers un VRAI cycle (pas juste le helper unitaire), que
    stress_test_styles route bien la bonne valeur au bon style lors de la
    construction des candidats."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct

    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1, "parallel_workers": 1,
                         "stress_test": False, "stress_test_styles": ["D1"]}
    cfg["memory"] = {"db_path": "mem_stress.sqlite", "max_episodes": 500}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1", "D1"], env_kwargs)

    calls = []

    def spy(agent, df, env_kwargs, n_windows=3, stress_test=False, **kwargs):
        calls.append(stress_test)
        return {"total_return": 0.1, "sharpe": 0.5, "max_drawdown": 0.05, "win_rate": 0.5,
                "profit_factor": 1.2, "n_trades": 10}

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=spy):
        trainer.run_one_cycle()
    trainer.close()

    assert calls == [False, True], f"H1 ne doit PAS avoir stress_test, D1 doit l'avoir : {calls}"


def test_cycle_notification_shows_progress_margin_between_alerts(tmp_path, monkeypatch):
    """Répond directement à la demande d'afficher la marge de progression
    (ex: '0.90 (+0.5%)') à côté du score de chaque style dans l'alerte de
    cycle : rien au tout premier cycle notifié (pas de référence), puis une
    marge visible dès le second, calculée par rapport à la DERNIÈRE alerte
    envoyée (pas forcément le cycle juste avant)."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct

    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1}
    cfg["memory"] = {"db_path": "mem_delta.sqlite", "max_episodes": 500}
    cfg["notifications"] = {"enabled": True, "channel": "ntfy", "ntfy_topic": "x",
                             "notify_every_cycle": True, "notify_cycle_every_n": 1}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)

    def metrics_v1(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": 0.1, "sharpe": 0.9, "max_drawdown": 0.0, "win_rate": 0.5,
                "profit_factor": 1.2, "n_trades": 50}

    def metrics_v2(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": 0.15, "sharpe": 1.2, "max_drawdown": 0.0, "win_rate": 0.5,
                "profit_factor": 1.3, "n_trades": 50}

    with patch("src.notifier.send_alert") as mock_alert:
        with patch.object(ct, "evaluate_agent_walkforward", side_effect=metrics_v1):
            trainer.run_one_cycle()
        first_message = mock_alert.call_args.kwargs["message"]
        assert "%" not in first_message, "aucune marge affichable au tout premier cycle notifié (pas de référence)"

        with patch.object(ct, "evaluate_agent_walkforward", side_effect=metrics_v2):
            trainer.run_one_cycle()
        second_message = mock_alert.call_args.kwargs["message"]
        assert "%" in second_message, "une marge de progression doit apparaître au 2e cycle notifié"
    trainer.close()


def test_champion_promotion_archives_versioned_snapshot(tmp_path, monkeypatch):
    """Répond directement à la demande de versionner les champions (pouvoir
    revenir EXACTEMENT à une promotion antérieure si une future s'avère
    mauvaise après coup) : chaque promotion doit archiver le modèle, les
    stats de normalisation et le meta.json dans
    models/champion_<TF>/history/gen_<N>/, SANS jamais toucher aux fichiers
    "courants" qui restent la seule source utilisée par la démo/l'ensemble."""
    monkeypatch.chdir(tmp_path)
    import os
    from unittest.mock import patch
    import src.continuous_trainer as ct

    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1}
    cfg["memory"] = {"db_path": "mem_history.sqlite", "max_episodes": 500}
    cfg["validation"] = {"min_sharpe_to_go_live": -999, "max_drawdown_allowed": 1.0,
                         "min_generations_before_demo": 0}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)

    def metrics_v1(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": 0.05, "sharpe": 0.5, "max_drawdown": 0.10,
                 "win_rate": 0.5, "profit_factor": 1.1, "n_trades": 10}

    def metrics_v2(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": 0.10, "sharpe": 1.0, "max_drawdown": 0.08,
                 "win_rate": 0.55, "profit_factor": 1.3, "n_trades": 20}

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=metrics_v1):
        trainer.run_one_cycle()
    gen1_dir = os.path.join("models", "champion_H1", "history", "gen_1")
    assert os.path.isfile(os.path.join(gen1_dir, "agent.zip"))
    assert os.path.isfile(os.path.join(gen1_dir, "norm_stats.json"))
    assert os.path.isfile(os.path.join(gen1_dir, "meta.json"))

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=metrics_v2):
        trainer.run_one_cycle()
    gen2_dir = os.path.join("models", "champion_H1", "history", "gen_2")
    assert os.path.isfile(os.path.join(gen2_dir, "agent.zip")), "la 2e promotion doit créer un 2e instantané"
    assert os.path.isfile(os.path.join(gen1_dir, "agent.zip")), \
        "l'ancien instantané ne doit pas être supprimé (bien en dessous de HISTORY_MAX_SNAPSHOTS)"
    # le fichier COURANT reste bien à jour indépendamment de l'archive
    import json
    with open(os.path.join("models", "champion_H1", "meta.json"), encoding="utf-8") as f:
        current_meta = json.load(f)
    assert current_meta["score"] != 0  # juste s'assurer qu'il a été écrit normalement
    trainer.close()


def test_prune_history_keeps_only_most_recent_snapshots(tmp_path, monkeypatch):
    """Test unitaire de _prune_history : ne garde que les
    HISTORY_MAX_SNAPSHOTS dernières générations (par numéro, pas date de
    fichier) -- évite une croissance illimitée du disque sur un système qui
    tourne H24 pendant des mois."""
    monkeypatch.chdir(tmp_path)
    import os
    from src.continuous_trainer import _prune_history, HISTORY_MAX_SNAPSHOTS

    history_root = "history_test"
    for gen in range(1, HISTORY_MAX_SNAPSHOTS + 6):
        os.makedirs(os.path.join(history_root, f"gen_{gen}"), exist_ok=True)

    _prune_history(history_root)

    remaining = sorted(os.listdir(history_root), key=lambda d: int(d.split("_")[1]))
    assert len(remaining) == HISTORY_MAX_SNAPSHOTS
    assert remaining[0] == "gen_6", "les 5 plus anciennes générations doivent être supprimées"
    assert remaining[-1] == f"gen_{HISTORY_MAX_SNAPSHOTS + 5}"


def test_recheck_gate_eligibility_flips_flag_without_new_promotion(tmp_path, monkeypatch):
    """Répond directement au constat en usage réel : un style (H1) passait
    déjà largement les 3 seuils de qualité bien avant que
    validation.min_generations_before_demo soit atteint, mais restait
    bloqué à passes_validation:false MÊME une fois la porte de générations
    franchie, parce que ce flag n'était recalculé qu'au moment d'une
    NOUVELLE promotion -- jamais rétroactivement pour un champion déjà en
    place dont les métriques n'ont pourtant pas changé. Ce test vérifie que
    _recheck_gate_eligibility() corrige ce flag dès l'ouverture de la porte,
    sans attendre qu'une nouvelle promotion survienne par hasard."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct
    import json, os

    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1}
    cfg["memory"] = {"db_path": "mem_gate_recheck.sqlite", "max_episodes": 500}
    cfg["validation"] = {"min_sharpe_to_go_live": 1.0, "max_drawdown_allowed": 0.20,
                         "min_generations_before_demo": 5}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)

    good_metrics = {"total_return": 0.10, "sharpe": 2.0, "max_drawdown": 0.10,
                    "win_rate": 0.55, "profit_factor": 1.3, "n_trades": 50}
    meta_path = os.path.join("models", "champion_H1", "meta.json")

    with patch.object(ct, "evaluate_agent_walkforward", return_value=good_metrics):
        trainer.run_one_cycle()  # génération 1/5 : promotion a lieu, mais porte pas encore ouverte
        with open(meta_path, encoding="utf-8") as f:
            assert json.load(f)["passes_validation"] is False, \
                "porte pas encore ouverte (1/5) malgré de bonnes métriques -- doit rester false"

        # cycles suivants : mêmes métriques -> le candidat n'améliore jamais
        # le champion existant -> AUCUNE nouvelle promotion ne doit survenir,
        # seul _recheck_gate_eligibility() peut donc faire bouger le flag.
        for _ in range(3):
            trainer.run_one_cycle()  # génération 2, 3, 4/5
        with open(meta_path, encoding="utf-8") as f:
            assert json.load(f)["passes_validation"] is False, "porte toujours pas ouverte avant génération 5"

        trainer.run_one_cycle()  # génération 5/5 : la porte s'ouvre CE cycle
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["passes_validation"] is True, (
            "la porte vient de s'ouvrir et les métriques déjà stockées passent les seuils -- "
            "doit basculer à true sans attendre une nouvelle promotion"
        )
        assert meta["generation"] == 0 and meta["score"] == 1.8, \
            "le correctif ne doit RIEN changer d'autre que le flag (pas de fausse promotion)"
    trainer.close()


def test_demo_champion_requires_validation_pass(tmp_path, monkeypatch):
    """LE test qui vérifie directement le problème remonté en usage réel :
    un agent avec un score négatif ne doit JAMAIS être envoyé en démo, même
    s'il est techniquement "le meilleur candidat disponible" au moment du
    bootstrap initial.
    """
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct

    cfg = dict(BASE_CFG)
    # candidates_per_cycle: 1 -- avec 2 (défaut BASE_CFG), le cycle bascule
    # sur un VRAI sous-processus (ProcessPoolExecutor) qui n'a pas le mock
    # d'evaluate_agent_walkforward ci-dessous (chaque processus réimporte le
    # module), ce qui rendrait ce test non-déterministe (vrai entraînement
    # PPO sur données synthétiques aléatoires au lieu des métriques forcées).
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1}
    cfg["memory"] = {"db_path": "mem2.sqlite", "max_episodes": 500}
    cfg["validation"] = {"min_sharpe_to_go_live": 1.0, "max_drawdown_allowed": 0.20,
                         "min_generations_before_demo": 0}  # ce test cible le garde-fou qualité, pas le nombre de générations
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)

    def bad_metrics(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": -0.1, "sharpe": -2.0, "max_drawdown": 0.25,
                "win_rate": 0.3, "profit_factor": 0.5, "n_trades": 10}

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=bad_metrics):
        trainer.run_one_cycle()

    assert trainer.has_champion() is True, "le champion technique doit exister (base du warm start)"
    assert trainer.has_demo_champion() is False, \
        "un agent avec sharpe négatif NE DOIT PAS être envoyé en démo"

    def good_metrics(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": 0.2, "sharpe": 1.5, "max_drawdown": 0.05,
                "win_rate": 0.6, "profit_factor": 2.0, "n_trades": 40}

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=good_metrics):
        trainer.run_one_cycle()

    assert trainer.has_demo_champion() is True, \
        "un agent qui passe les seuils doit être promu champion démo"
    trainer.close()


def test_multi_style_pool_trains_in_parallel_with_distinct_features(tmp_path, monkeypatch):
    """LE test du "vrai trader multi-couche" : plusieurs styles (timeframes
    primaires différentes) doivent évoluer EN PARALLÈLE, chacun avec un
    contexte multi-timeframe et un nombre de features DIFFÉRENT dérivé
    automatiquement (une timeframe primaire plus large a moins de contexte
    disponible), et chacun avec sa PROPRE lignée de champion (répertoires
    distincts, pas de collision)."""
    monkeypatch.chdir(tmp_path)
    import numpy as np
    import pandas as pd
    import yaml
    import autonomous_agent

    folder = tmp_path / "kaggle_gold"
    folder.mkdir()

    def make_csv(fname, freq_minutes, n, seed):
        rng = np.random.default_rng(seed)
        prices = [2000.0]
        for _ in range(1, n):
            prices.append(max(prices[-1] * (1 + rng.normal(0, 0.001)), 1.0))
        prices = np.array(prices)
        times = pd.date_range("2020-01-01", periods=n, freq=f"{freq_minutes}min")
        pd.DataFrame({
            "Date": times.strftime("%Y.%m.%d"), "Time": times.strftime("%H:%M:%S"),
            "Open": prices, "High": prices * 1.001, "Low": prices * 0.999,
            "Close": prices, "Volume": rng.integers(10, 500, n),
        }).to_csv(folder / fname, index=False, sep=";")

    make_csv("XAU_1h_data.csv", 60, 3000, 1)
    make_csv("XAU_4h_data.csv", 240, 800, 2)
    make_csv("XAU_1d_data.csv", 1440, 400, 3)

    cfg_yaml = f"""
data:
  folder: '{folder}'
  timeframe_pool: ["H1", "D1"]
  max_bars: 2000
  max_bars_market_closed: 0
  n_bars_context: 500
  train_ratio: 0.7
  val_ratio: 0.3
  lockbox_start: "2099-01-01"
market_hours:
  enabled: false
environment:
  window_size: 20
  initial_balance: 10000
  transaction_cost: 0.0002
  max_position: 1
  reward_type: "risk_adjusted"
  drawdown_penalty: 2.0
agent:
  policy: "MlpPolicy"
  learning_rate: 0.0003
  n_steps: 128
  batch_size: 32
  gamma: 0.99
  gae_lambda: 0.95
  ent_coef: 0.01
continuous:
  candidates_per_cycle: 1
  timesteps_per_cycle: 128
  mutation_scale: 0.2
memory:
  db_path: "mem_mtf.sqlite"
  max_episodes: 500
fundamental:
  enabled: false
validation:
  min_sharpe_to_go_live: -999
  max_drawdown_allowed: 1.0
  min_generations_before_demo: 0
  min_trades_to_go_live: 0
"""
    cfg = yaml.safe_load(cfg_yaml)

    get_data_fn, timeframe_pool = autonomous_agent.make_data_provider(cfg)
    assert timeframe_pool == ["H1", "D1"]

    # style "H1" : contexte = H4 + D1 (plus larges disponibles) -> 12 + 2*5 = 22 features
    _, _, _, cols_h1, ctx_h1 = get_data_fn("H1")
    assert ctx_h1 == ["H4", "D1"]
    assert len(cols_h1) == 22

    # style "D1" : rien de plus large disponible dans ces 3 fichiers -> pas de contexte, 12 features
    _, _, _, cols_d1, ctx_d1 = get_data_fn("D1")
    assert ctx_d1 == []
    assert len(cols_d1) == 12

    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ContinuousEvolutionTrainer(cfg, get_data_fn, timeframe_pool, env_kwargs)
    trainer.run_one_cycle()

    assert trainer.has_champion("H1") is True
    assert trainer.has_champion("D1") is True
    from src.continuous_trainer import _champion_model
    assert _champion_model("H1") != _champion_model("D1"), \
        "les deux styles doivent avoir des répertoires de champion DISTINCTS"
    # un candidat, tous styles confondus, doit avoir été jugé éligible à la démo
    # (seuils volontairement permissifs dans ce test)
    assert trainer.has_demo_champion() is True
    trainer.close()


def test_market_hours_switches_max_bars(tmp_path, monkeypatch):
    """Répond à la demande de "manger le maximum de données" pendant la
    fermeture du marché : vérifie que le dataset reconstruit utilise
    data.max_bars_market_closed (ici illimité) quand le marché est fermé,
    et data.max_bars quand il est ouvert."""
    monkeypatch.chdir(tmp_path)
    from datetime import datetime, timezone
    from src.market_hours import is_market_open

    cfg = {"market_hours": {"enabled": True, "close_weekday": 4, "close_hour": 21,
                             "open_weekday": 6, "open_hour": 21}}
    # Samedi -> marché fermé
    saturday = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)  # un samedi
    assert saturday.weekday() == 5
    assert is_market_open(cfg, now=saturday) is False

    # Mercredi midi -> marché ouvert
    wednesday = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    assert wednesday.weekday() == 2
    assert is_market_open(cfg, now=wednesday) is True

    # désactivé -> toujours "ouvert"
    cfg_disabled = {"market_hours": {"enabled": False}}
    assert is_market_open(cfg_disabled, now=saturday) is True


def test_overfitting_plateau_tracking_persists(tmp_path, monkeypatch):
    """Vérifie que le compteur de cycles sans amélioration est bien suivi et
    PERSISTE d'une instance de trainer à l'autre (fichier _progress.json)."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct

    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1,
                         "overfitting_patience_cycles": 2}
    cfg["memory"] = {"db_path": "mem_plateau.sqlite", "max_episodes": 500}
    cfg["validation"] = {"min_sharpe_to_go_live": -999, "max_drawdown_allowed": 1.0,
                         "min_generations_before_demo": 0}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)

    # métriques CONSTANTES -> après le premier cycle (nouveau champion), plus
    # aucune amélioration n'est possible -> le compteur doit monter
    def flat_metrics(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": 0.05, "sharpe": 0.5, "max_drawdown": 0.05,
                "win_rate": 0.5, "profit_factor": 1.1, "n_trades": 5}

    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)
    with patch.object(ct, "evaluate_agent_walkforward", side_effect=flat_metrics):
        trainer.run_one_cycle()
        assert trainer.cycles_since_improvement == 0  # premier champion = amélioration
        trainer.run_one_cycle()
        assert trainer.cycles_since_improvement == 1
    trainer.close()

    # une NOUVELLE instance doit reprendre le compteur là où il en était
    trainer2 = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)
    assert trainer2.cycles_since_improvement == 1, \
        "le suivi de plateau doit persister entre deux instances (fichier _progress.json)"
    trainer2.close()


def test_confident_score_discounts_small_samples_never_helps_bad_scores():
    """Test unitaire de src.continuous_trainer._confident_score : réduit un
    score POSITIF obtenu sur peu de trades, ne touche jamais un score
    négatif ou nul, et se désactive avec min_trades<=0."""
    from src.continuous_trainer import _confident_score

    assert _confident_score(5.0, 10, 100) == 0.5          # 10/100 -> facteur 0.1
    assert _confident_score(5.0, 200, 100) == 5.0          # assez de trades -> inchangé (plafonné à 1.0)
    assert _confident_score(5.0, 100, 100) == 5.0          # exactement au seuil -> inchangé
    assert _confident_score(-3.0, 5, 100) == -3.0          # jamais aidé un score négatif
    assert _confident_score(0.0, 5, 100) == 0.0
    assert _confident_score(5.0, 10, 0) == 5.0             # min_trades<=0 -> désactivé


def test_lucky_small_sample_score_does_not_block_plateau_detection(tmp_path, monkeypatch):
    """Reproduit exactement le cas réel observé (style D1) qui a motivé
    _confident_score : un style qui décroche un Sharpe énorme sur une
    poignée de trades (coup de chance statistique, pas une vraie
    compétence) ne doit PAS bloquer indéfiniment la détection de progrès
    des AUTRES styles -- un style qui progresse ensuite sincèrement, avec
    largement assez de trades pour qu'on lui fasse confiance, doit pouvoir
    remettre `cycles_since_improvement` à zéro même s'il ne bat pas le
    record BRUT du premier (qui reste affiché tel quel, sans y toucher)."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct

    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1, "parallel_workers": 1,
                         "min_trades_for_confident_score": 100}
    cfg["memory"] = {"db_path": "mem_lucky.sqlite", "max_episodes": 500}
    cfg["validation"] = {"min_sharpe_to_go_live": -999, "max_drawdown_allowed": 1.0,
                         "min_generations_before_demo": 0, "min_trades_to_go_live": 0}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)

    # Cycle 1 : H1 décroche un score ÉNORME (5.0) mais sur seulement 5
    # trades -- exactement le cas D1 (Sharpe élevé, échantillon minuscule).
    # D1 obtient un score franchement mauvais (premier essai).
    # Cycle 2 : H1 ne rejoue rien de nouveau -- D1, lui, progresse vraiment
    # (0.5, bien échantillonné sur 150 trades) sans pour autant approcher
    # le record BRUT de H1.
    responses = [
        {"total_return": 0.3, "sharpe": 5.0, "max_drawdown": 0.0, "win_rate": 0.3,
         "profit_factor": 3.0, "n_trades": 5},     # H1, cycle 1 (chance, petit échantillon)
        {"total_return": -0.1, "sharpe": -0.5, "max_drawdown": 0.1, "win_rate": 0.3,
         "profit_factor": 0.8, "n_trades": 150},   # D1, cycle 1 (mauvais, mais bien échantillonné)
        {"total_return": 0.3, "sharpe": 5.0, "max_drawdown": 0.0, "win_rate": 0.3,
         "profit_factor": 3.0, "n_trades": 5},     # H1, cycle 2 (identique -- aucun nouveau progrès)
        {"total_return": 0.1, "sharpe": 0.5, "max_drawdown": 0.0, "win_rate": 0.5,
         "profit_factor": 1.5, "n_trades": 150},   # D1, cycle 2 (vraie amélioration, bien échantillonnée)
    ]

    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1", "D1"], env_kwargs)
    with patch.object(ct, "evaluate_agent_walkforward", side_effect=responses):
        trainer.run_one_cycle()
        assert trainer.champion_score["H1"] == 5.0
        assert trainer.best_ever_score == 5.0, "le record BRUT affiché doit rester le score réel mesuré"
        assert trainer.cycles_since_improvement == 0, "premier cycle : premier champion de chaque style"

        trainer.run_one_cycle()
        # D1 progresse réellement (-0.5 -> 0.5, bien échantillonné) mais son
        # score BRUT (0.5) reste loin derrière le record brut de H1 (5.0,
        # gonflé par la chance sur 5 trades) -- le record affiché ne doit
        # donc PAS bouger. Mais en confiance, D1 (0.5, aucune réduction,
        # 150>=100 trades) dépasse maintenant H1 (5.0 x 5/100 = 0.25) :
        # ça DOIT compter comme une vraie amélioration globale.
        assert trainer.champion_score["D1"] == 0.5
        assert trainer.best_ever_score == 5.0, "le record brut ne doit pas bouger (rien ne l'a battu en brut)"
        assert trainer.cycles_since_improvement == 0, \
            "un style bien échantillonné (150 trades) qui dépasse en confiance un score gonflé par la " \
            "chance (5 trades) doit débloquer la détection de progrès, même sans battre le score brut"
    trainer.close()


def test_parallel_candidate_training_matches_sequential_behavior(tmp_path, monkeypatch):
    """Répond directement à la demande d'augmenter le débit d'entraînement :
    vérifie que l'entraînement PARALLÈLE des candidats (plusieurs processus,
    voir continuous.parallel_workers) produit un résultat cohérent -- même
    promotion du champion, mêmes fichiers nettoyés -- que le mode séquentiel,
    en forçant le chemin parallèle même sur une machine à un seul coeur.
    """
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct

    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 3, "parallel_workers": 3}
    cfg["memory"] = {"db_path": "mem_parallel.sqlite", "max_episodes": 500}
    cfg["validation"] = {"min_sharpe_to_go_live": -999, "max_drawdown_allowed": 1.0,
                         "min_generations_before_demo": 0, "min_trades_to_go_live": 0,
                         "max_stop_exit_rate": 1.0, "min_trades_per_window": 0}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)

    with patch("os.cpu_count", return_value=4):
        trainer.run_one_cycle()
        assert trainer.has_champion() is True
        assert trainer.has_demo_champion() is True
        # les modèles temporaires de candidats doivent être nettoyés après le cycle
        remaining = os.listdir(ct.CANDIDATES_TMP_DIR)
        assert remaining == [], f"fichiers temporaires non nettoyés : {remaining}"

        trainer.run_one_cycle()  # deuxième cycle : warm start à travers les processus
        assert trainer.generation == 2
    trainer.close()


def test_demo_trader_fuses_live_multi_timeframe(tmp_path, monkeypatch):
    """Vérifie que la boucle de démo fusionne bien PLUSIEURS timeframes
    récupérées en direct via le connecteur (primaire + contexte), lit le
    style dynamiquement depuis meta.json (et non un paramètre fixe), et
    qu'un champion démo pré-entraîné produit effectivement une décision."""
    monkeypatch.chdir(tmp_path)
    import json
    from src.multi_timeframe import fuse_mtf_frames
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
    from src.continuous_trainer import DEMO_DIR, DEMO_MODEL, DEMO_META, DEMO_STATS

    class FakeMTFConnector:
        def __init__(self):
            self.orders = []
        def connect(self):
            pass
        def is_demo_account(self):
            return True
        def close_orphan_positions(self, recognized_styles):
            return []
        def get_open_positions_by_style(self, recognized_styles):
            return {}
        def get_latest_bars(self, timeframe, n_bars):
            seed = {"H1": 1, "H4": 2, "D1": 3}.get(timeframe, 0)
            return generate_synthetic_ohlcv(n_bars=n_bars, seed=seed)
        def send_order(self, target_position, stop_pct=None, **kwargs):
            self.orders.append(target_position)

    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)

    dfs = {"H1": generate_synthetic_ohlcv(n_bars=1000, seed=1),
           "H4": generate_synthetic_ohlcv(n_bars=500, seed=2),
           "D1": generate_synthetic_ohlcv(n_bars=500, seed=3)}
    df, mtf_cols = fuse_mtf_frames(dfs, "H1", ["H4", "D1"])
    df = add_technical_features(df)
    all_cols = FEATURE_COLUMNS + mtf_cols
    df, stats = normalize_features(df, columns=all_cols)

    env = TradingEnv(df, feature_columns=all_cols, **env_kwargs)
    agent = TradingAgent(env, {"n_steps": 64, "batch_size": 16})
    agent.learn(64)

    os.makedirs(DEMO_DIR, exist_ok=True)
    agent.save(DEMO_MODEL)
    from src.trading_env import ENV_VERSION
    with open(DEMO_META, "w") as f:
        json.dump({
            "generation": 0, "score": 5.0, "updated_at": 123.0,
            "primary_timeframe": "H1", "context_timeframes": ["H4", "D1"],
            "feature_columns": all_cols, "env_version": ENV_VERSION,
        }, f)
    with open(DEMO_STATS, "w") as f:
        json.dump({k: list(v) for k, v in stats.items()}, f)

    cfg = {"live": {"dry_run": True, "poll_seconds": 0, "allow_real_account": False},
           "fundamental": {"enabled": False}, "data": {"n_bars_context": 500},
           "market_hours": {"enabled": False}}
    fake = FakeMTFConnector()
    run_demo_trading_loop(cfg, env_kwargs, connector=fake, max_iterations=2)

    assert len(fake.orders) == 2, "la boucle doit avoir pris 2 décisions et envoyé 2 ordres (dry-run)"
    assert all(o in (-1, 0, 1) for o in fake.orders)


def test_demo_trader_forwards_agent_chosen_stop_loss(tmp_path, monkeypatch):
    """Vérifie le câblage de bout en bout, à travers la VRAIE boucle de démo
    (pas seulement TradingEnv) : quand agent.learn_stop_loss est actif, la
    distance de stop décodée depuis l'action du modèle est bien transmise
    jusqu'à MT5Connector.send_order -- et cohérente avec la position
    décidée (aucun stop pour une position flat, un des buckets configurés
    sinon). Répond directement à la demande de l'utilisateur : le stop ne
    doit JAMAIS venir d'une règle fixe externe quand ce mode est actif."""
    monkeypatch.chdir(tmp_path)
    import json
    from src.multi_timeframe import fuse_mtf_frames
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
    from src.continuous_trainer import DEMO_DIR, DEMO_MODEL, DEMO_META, DEMO_STATS

    class FakeMTFConnector:
        def __init__(self):
            self.orders = []  # liste de (target_position, stop_pct)
        def connect(self):
            pass
        def is_demo_account(self):
            return True
        def close_orphan_positions(self, recognized_styles):
            return []
        def get_open_positions_by_style(self, recognized_styles):
            return {}
        def get_latest_bars(self, timeframe, n_bars):
            seed = {"H1": 1, "H4": 2, "D1": 3}.get(timeframe, 0)
            return generate_synthetic_ohlcv(n_bars=n_bars, seed=seed)
        def send_order(self, target_position, stop_pct=None, **kwargs):
            self.orders.append((target_position, stop_pct))

    buckets = [0.02]  # un seul bucket -> décodage entièrement déterministe
    # atr_stop_loss=False EXPLICITE (LOT 2, phase 3) : ce test vérifie le
    # chemin des buckets STATIQUES spécifiquement -- _build_live_dataframe
    # peuple TOUJOURS atr_14_raw quand "atr_14" est présent, donc sans ce
    # False explicite, le stop ATR (actif par défaut) prendrait la main et
    # transmettrait un multiple, pas un stop_pct (voir
    # tests/test_atr_live_wiring.py pour ce chemin-là).
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1,
                       learn_stop_loss=True, stop_loss_buckets=buckets, atr_stop_loss=False)

    dfs = {"H1": generate_synthetic_ohlcv(n_bars=1000, seed=1),
           "H4": generate_synthetic_ohlcv(n_bars=500, seed=2),
           "D1": generate_synthetic_ohlcv(n_bars=500, seed=3)}
    df, mtf_cols = fuse_mtf_frames(dfs, "H1", ["H4", "D1"])
    df = add_technical_features(df)
    all_cols = FEATURE_COLUMNS + mtf_cols
    df, stats = normalize_features(df, columns=all_cols)

    env = TradingEnv(df, feature_columns=all_cols, **env_kwargs)
    agent = TradingAgent(env, {"n_steps": 64, "batch_size": 16})
    agent.learn(64)

    os.makedirs(DEMO_DIR, exist_ok=True)
    agent.save(DEMO_MODEL)
    from src.trading_env import ENV_VERSION
    with open(DEMO_META, "w") as f:
        json.dump({
            "generation": 0, "score": 5.0, "updated_at": 123.0,
            "primary_timeframe": "H1", "context_timeframes": ["H4", "D1"],
            "feature_columns": all_cols, "env_version": ENV_VERSION,
        }, f)
    with open(DEMO_STATS, "w") as f:
        json.dump({k: list(v) for k, v in stats.items()}, f)

    cfg = {"live": {"dry_run": True, "poll_seconds": 0, "allow_real_account": False},
           "fundamental": {"enabled": False}, "data": {"n_bars_context": 500},
           "market_hours": {"enabled": False}}
    fake = FakeMTFConnector()
    run_demo_trading_loop(cfg, env_kwargs, connector=fake, max_iterations=2)

    assert len(fake.orders) == 2
    for target, stop_pct in fake.orders:
        if target == 0:
            assert stop_pct is None, "aucun stop envoyé pour une position flat"
        else:
            assert stop_pct == buckets[0], \
                f"le stop doit venir du bucket choisi par l'agent ({buckets[0]}), pas d'une valeur fixe externe : {stop_pct}"


def test_demo_trader_multi_position_independent_styles(tmp_path, monkeypatch):
    """Étape 3 (18/09) : retrait du blending d'ensemble -- 2 styles
    éligibles SIMULTANÉMENT (H1, H4), décisions DIFFÉRENTES dont une paire
    en directions OPPOSÉES (H1 long, H4 short). Vérifie que chacun appelle
    send_order INDÉPENDAMMENT (un appel par style, taggé style+génération,
    jamais mélangé/moyenné). MISE À JOUR (19/09, coordination inter-styles) :
    `conflict_resolution` n'est PAS réglé dans ce cfg -> défaut "disabled",
    donc les deux directions opposées coexistent SANS blocage ni fermeture
    forcée -- exactement le comportement testé ici avant l'ajout de la
    coordination (voir test_demo_trader_conflict_resolution_disabled_* pour
    une confirmation explicite dédiée). Le budget de risque, en revanche,
    suit maintenant l'option B (dynamique, remplace l'option A fixe) : H1
    est traité EN PREMIER (ordre du pool, scores à égalité -- tri stable),
    donc seul actif au moment de son ouverture -> budget plein (0.02) ; H4
    est traité ensuite, H1 déjà "actif" -> budget partagé à 2 (0.01)."""
    monkeypatch.chdir(tmp_path)
    import json
    import src.demo_trader as demo_trader_module
    from src.continuous_trainer import _champion_meta, _champion_stats, _champion_dir

    class FakeConnector:
        def __init__(self):
            self.calls = []
        def connect(self):
            pass
        def is_demo_account(self):
            return True
        def close_orphan_positions(self, recognized_styles):
            return []
        def get_open_positions_by_style(self, recognized_styles):
            return {}
        def get_latest_bars(self, timeframe, n_bars):
            return generate_synthetic_ohlcv(n_bars=n_bars, seed=1)
        def send_order(self, target_exposure, stop_pct=None, atr_multiplier=None, atr_price_units=None,
                        style=None, generation=None, risk_pct_override=None):
            self.calls.append({"style": style, "target": target_exposure, "stop_pct": stop_pct,
                                "generation": generation, "risk_pct_override": risk_pct_override})

    from src.trading_env import ENV_VERSION
    for tf, gen in [("H1", 10), ("H4", 20)]:
        os.makedirs(_champion_dir(tf), exist_ok=True)
        with open(_champion_meta(tf), "w", encoding="utf-8") as f:
            json.dump({"generation": gen, "score": 5.0, "updated_at": 123.0 + gen,
                       "primary_timeframe": tf, "context_timeframes": [],
                       "feature_columns": FEATURE_COLUMNS, "passes_validation": True,
                       "env_version": ENV_VERSION, "metrics": {}}, f)
        with open(_champion_stats(tf), "w", encoding="utf-8") as f:
            json.dump({}, f)

    # decide()/maybe_reload() monkeypatchés : on teste ici le DISPATCH par
    # style de la boucle, pas la qualité d'une prédiction RL réelle --
    # décisions FIXES et volontairement opposées (H1 long, H4 short).
    fixed_decisions = {"H1": (1.0, 0.02), "H4": (-1.0, 0.03)}

    def fake_maybe_reload(self, entry, *a, **k):
        self.mtf_config = {"primary_timeframe": entry["style"], "context_timeframes": [], "n_bars_context": 100}
        self.feature_columns = FEATURE_COLUMNS
        self.agent = object()
        self.last_loaded_at = entry["meta"].get("updated_at")

    def fake_decide(self, *a, **k):
        target, stop_pct = fixed_decisions[self.mtf_config["primary_timeframe"]]
        return target, stop_pct, None, None, None

    monkeypatch.setattr(demo_trader_module._StyleRuntime, "maybe_reload", fake_maybe_reload)
    monkeypatch.setattr(demo_trader_module._StyleRuntime, "decide", fake_decide)

    cfg = {"live": {"dry_run": True, "poll_seconds": 0, "allow_real_account": False,
                     "risk_guard": False, "max_risk_pct_per_trade": 0.02},
           "fundamental": {"enabled": False}, "data": {"n_bars_context": 100, "timeframe_pool": ["H1", "H4"]},
           "market_hours": {"enabled": False}, "memory": {}}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    fake = FakeConnector()
    demo_trader_module.run_demo_trading_loop(cfg, env_kwargs, connector=fake, max_iterations=1)

    assert len(fake.calls) == 2, f"un appel send_order PAR STYLE éligible attendu, obtenu {len(fake.calls)}"
    by_style = {c["style"]: c for c in fake.calls}
    assert set(by_style.keys()) == {"H1", "H4"}, "aucune agrégation -- deux appels bien distincts par style"

    assert by_style["H1"]["target"] == 1.0
    assert by_style["H1"]["generation"] == 10
    assert by_style["H4"]["target"] == -1.0
    assert by_style["H4"]["generation"] == 20
    assert by_style["H1"]["target"] * by_style["H4"]["target"] < 0, "directions opposées confirmées, jamais moyennées"

    # Budget de risque -- option B (dynamique, remplace l'option A fixe) :
    # H1 traité en premier (ordre du pool, égalité de score -> tri stable),
    # seul actif à son ouverture -> budget plein (0.02/1). H4 ensuite, H1
    # déjà comptabilisé comme actif -> budget partagé (0.02/2 = 0.01).
    assert by_style["H1"]["risk_pct_override"] == 0.02
    assert by_style["H4"]["risk_pct_override"] == 0.01


def _write_champion_meta(tf, gen, score, passes_validation):
    """Écrit un meta.json de champion minimal mais COMPLET pour `tf` --
    factorisé par les tests de coordination inter-styles ci-dessous, qui ont
    besoin de styles au score connu, certains ÉLIGIBLES (ils décident ce
    cycle) et d'autres NON (ils ne décident plus mais détiennent encore une
    position, dont le score reste comparable pour l'arbitrage)."""
    import json
    from src.continuous_trainer import _champion_meta, _champion_stats, _champion_dir
    from src.trading_env import ENV_VERSION
    os.makedirs(_champion_dir(tf), exist_ok=True)
    with open(_champion_meta(tf), "w", encoding="utf-8") as f:
        json.dump({"generation": gen, "score": score, "updated_at": 123.0 + gen,
                    "primary_timeframe": tf, "context_timeframes": [],
                    "feature_columns": FEATURE_COLUMNS, "passes_validation": passes_validation,
                    "env_version": ENV_VERSION, "metrics": {}}, f)
    with open(_champion_stats(tf), "w", encoding="utf-8") as f:
        json.dump({}, f)


def _patch_style_runtime(monkeypatch, demo_trader_module, fixed_decisions):
    """Neutralise le chargement/la prédiction RL réels : ces tests portent
    sur l'ARBITRAGE entre styles de la boucle, pas sur la qualité d'une
    prédiction -- décisions FIXES et déterministes par style."""
    def fake_maybe_reload(self, entry, *a, **k):
        self.mtf_config = {"primary_timeframe": entry["style"], "context_timeframes": [],
                            "n_bars_context": 100}
        self.feature_columns = FEATURE_COLUMNS
        self.agent = object()
        self.last_loaded_at = entry["meta"].get("updated_at")

    def fake_decide(self, *a, **k):
        target, stop_pct = fixed_decisions[self.mtf_config["primary_timeframe"]]
        return target, stop_pct, None, None, None

    monkeypatch.setattr(demo_trader_module._StyleRuntime, "maybe_reload", fake_maybe_reload)
    monkeypatch.setattr(demo_trader_module._StyleRuntime, "decide", fake_decide)


class _CoordFakeConnector:
    """Faux connecteur pour les tests de coordination : l'état des positions
    déjà ouvertes PAR STYLE est PRÉ-RÉGLÉ (simule des positions ouvertes lors
    de cycles précédents), et chaque send_order est enregistré tel quel."""

    def __init__(self, preexisting: dict | None = None):
        self.calls = []
        self._preexisting = preexisting or {}

    def connect(self):
        pass

    def is_demo_account(self):
        return True

    def close_orphan_positions(self, recognized_styles):
        return []

    def get_open_positions_by_style(self, recognized_styles):
        return {style: {"ticket": 1000 + i, "direction": direction, "volume": 0.1,
                         "price_open": 4300.0}
                for i, (style, direction) in enumerate(self._preexisting.items())}

    def get_latest_bars(self, timeframe, n_bars):
        return generate_synthetic_ohlcv(n_bars=n_bars, seed=1)

    def send_order(self, target_exposure, stop_pct=None, atr_multiplier=None, atr_price_units=None,
                    style=None, generation=None, risk_pct_override=None):
        self.calls.append({"style": style, "target": target_exposure, "stop_pct": stop_pct,
                            "generation": generation, "risk_pct_override": risk_pct_override})


def _coord_cfg(pool, conflict_resolution):
    return {"live": {"dry_run": True, "poll_seconds": 0, "allow_real_account": False,
                      "risk_guard": False, "max_risk_pct_per_trade": 0.02,
                      "conflict_resolution": conflict_resolution},
            "fundamental": {"enabled": False},
            "data": {"n_bars_context": 100, "timeframe_pool": pool},
            "market_hours": {"enabled": False}, "memory": {}}


_COORD_ENV_KWARGS = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                          reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)


def test_demo_trader_conflict_resolution_new_style_with_better_score_closes_existing(tmp_path, monkeypatch):
    """COORDINATION INTER-STYLES (19/09) -- scénario EXACT observé en démo
    (deux styles, directions OPPOSÉES, scores DIFFÉRENTS), cas 1 : c'est le
    NOUVEAU style qui a le meilleur score. H1 (score 3.0) détient déjà une
    position LONGUE ; H4 (score 8.0, bien meilleur) veut ouvrir SHORT. La
    règle de priorité doit FERMER la position de H1 (send_order cible 0,
    taggé 'H1') PUIS laisser H4 s'ouvrir normalement -- jamais les deux
    positions opposées en même temps."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module

    # H1 : score plus faible, PLUS éligible ce cycle (ne décide plus) mais
    # détient encore une position -- son score reste lu depuis son meta.json
    # pour l'arbitrage (voir demo_trader._style_score).
    _write_champion_meta("H1", gen=10, score=3.0, passes_validation=False)
    _write_champion_meta("H4", gen=20, score=8.0, passes_validation=True)

    _patch_style_runtime(monkeypatch, demo_trader_module, {"H4": (-1.0, 0.02)})

    fake = _CoordFakeConnector(preexisting={"H1": 1})  # H1 déjà LONG
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(["H1", "H4"], "priority_by_score"), _COORD_ENV_KWARGS,
        connector=fake, max_iterations=1)

    by_style = {}
    for call in fake.calls:
        by_style.setdefault(call["style"], []).append(call)

    assert "H1" in by_style, "la position opposée de H1 doit être explicitement fermée"
    assert by_style["H1"][0]["target"] == 0.0, \
        "fermeture = cible 0 sur le style H1, jamais une ouverture dans l'autre sens"
    assert by_style["H1"][0]["generation"] == 10, "la fermeture doit rester taggée sur la génération de H1"

    assert "H4" in by_style, "H4 doit ensuite s'ouvrir normalement"
    assert by_style["H4"][0]["target"] == -1.0, "H4 garde sa décision SHORT intacte (il a gagné l'arbitrage)"

    # L'ordre compte : on ferme AVANT d'ouvrir l'opposé, jamais l'inverse.
    assert fake.calls[0]["style"] == "H1" and fake.calls[-1]["style"] == "H4", \
        f"séquence attendue : fermeture H1 puis ouverture H4, obtenu {[c['style'] for c in fake.calls]}"


def test_demo_trader_conflict_resolution_existing_style_with_better_score_blocks_challenger(tmp_path, monkeypatch):
    """COORDINATION INTER-STYLES (19/09) -- même scénario, cas 2 (miroir) :
    c'est le style DÉJÀ en position qui a le meilleur score. H4 (score 8.0)
    détient déjà une position SHORT ; H1 (score 3.0) veut ouvrir LONG. La
    nouvelle ouverture de H1 doit être BLOQUÉE (ramenée à 0 pour ce cycle,
    retentée aux cycles suivants), et la position de H4 ne doit JAMAIS être
    touchée -- aucun ordre taggé 'H4' ne doit partir."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module

    _write_champion_meta("H1", gen=10, score=3.0, passes_validation=True)
    _write_champion_meta("H4", gen=20, score=8.0, passes_validation=False)

    _patch_style_runtime(monkeypatch, demo_trader_module, {"H1": (1.0, 0.02)})

    fake = _CoordFakeConnector(preexisting={"H4": -1})  # H4 déjà SHORT
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(["H1", "H4"], "priority_by_score"), _COORD_ENV_KWARGS,
        connector=fake, max_iterations=1)

    assert all(c["style"] != "H4" for c in fake.calls), \
        "la position du style prioritaire (H4) ne doit JAMAIS être fermée par un style de moindre score"

    h1_calls = [c for c in fake.calls if c["style"] == "H1"]
    assert len(h1_calls) == 1, f"un seul appel attendu pour H1, obtenu {len(h1_calls)}"
    assert h1_calls[0]["target"] == 0.0, \
        "l'ouverture opposée de H1 doit être ramenée à 0 (bloquée), pas envoyée à +1.00"


def test_demo_trader_conflict_resolution_disabled_allows_opposite_directions(tmp_path, monkeypatch):
    """conflict_resolution: "disabled" doit restaurer EXACTEMENT le
    comportement d'avant cette étape : le MÊME scénario que le cas 2
    ci-dessus (H4 déjà SHORT avec un bien meilleur score, H1 veut ouvrir
    LONG) doit alors laisser H1 s'ouvrir quand même -- chacun fait ce qu'il
    veut, hedging possible, aucune fermeture forcée ni blocage. C'est le
    réglage à utiliser quand la firme visée autorise explicitement le
    hedging (voir config/risk_profiles/*.yaml)."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module

    _write_champion_meta("H1", gen=10, score=3.0, passes_validation=True)
    _write_champion_meta("H4", gen=20, score=8.0, passes_validation=False)

    _patch_style_runtime(monkeypatch, demo_trader_module, {"H1": (1.0, 0.02)})

    fake = _CoordFakeConnector(preexisting={"H4": -1})
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(["H1", "H4"], "disabled"), _COORD_ENV_KWARGS,
        connector=fake, max_iterations=1)

    assert all(c["style"] != "H4" for c in fake.calls), "aucune fermeture forcée quand la coordination est désactivée"
    h1_calls = [c for c in fake.calls if c["style"] == "H1"]
    assert len(h1_calls) == 1
    assert h1_calls[0]["target"] == 1.0, \
        "coordination désactivée : H1 doit ouvrir LONG malgré la position SHORT opposée de H4"


def test_demo_trader_temporal_hierarchy_blocks_low_style_opposing_high_style_far_gap(tmp_path, monkeypatch):
    """HIÉRARCHIE TEMPORELLE (17/09) -- écart >= 2 niveaux : D1 (niveau 5)
    détient déjà une position LONGUE ; M15 (niveau 1, écart de 4) veut
    ouvrir SHORT. Contrairement à "priority_by_score", le score walk-forward
    n'intervient JAMAIS ici -- même si M15 avait un bien meilleur score, son
    ouverture opposée doit être BLOQUÉE (ramenée à 0) uniquement à cause de
    l'écart de rang."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module

    _write_champion_meta("M15", gen=50, score=99.0, passes_validation=True)

    _patch_style_runtime(monkeypatch, demo_trader_module, {"M15": (-1.0, 0.02)})

    fake = _CoordFakeConnector(preexisting={"D1": 1})  # D1 déjà LONG
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(["D1", "M15"], "temporal_hierarchy"), _COORD_ENV_KWARGS,
        connector=fake, max_iterations=1)

    m15_calls = [c for c in fake.calls if c["style"] == "M15"]
    assert len(m15_calls) == 1
    assert m15_calls[0]["target"] == 0.0, (
        "M15 (niveau 1) ne peut pas s'opposer à D1 (niveau 5, écart 4 >= 2) "
        "même avec un meilleur score -- l'arbitrage ne doit PLUS dépendre du score."
    )


def test_demo_trader_temporal_hierarchy_blocks_on_one_level_gap_too(tmp_path, monkeypatch):
    """HIÉRARCHIE TEMPORELLE -- ZÉRO HEDGING TOLÉRÉ (18/09, durci sur demande
    explicite -- un BUY/SELL simultané sur le même symbole entre deux styles,
    même à un seul niveau d'écart, est le genre de pattern qu'un broker ou
    une prop firm anti-hedging détecte, avec un vrai risque au moment d'un
    retrait) : M30 (niveau 2) détient déjà une position LONGUE ; M15
    (niveau 1, écart de 1 avec M30) veut ouvrir SHORT. Doit maintenant être
    BLOQUÉ, pas seulement réduit -- l'ancien palier intermédiaire "écart=1
    -> autorisé à budget réduit" a été retiré. NOTE : la hiérarchie
    TIMEFRAME_HIERARCHY = {D1:5, H4:4, H1:3, M30:2, M15:1} donne un écart de
    2 (pas 1) entre H1 et M15 -- la paire adjacente à écart 1 la plus proche
    de M15 est M30, utilisée ici."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module

    _write_champion_meta("M15", gen=1, score=0.0, passes_validation=True)
    _patch_style_runtime(monkeypatch, demo_trader_module, {"M15": (-1.0, 0.02)})

    fake = _CoordFakeConnector(preexisting={"M30": 1})  # M30 déjà LONG
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(["M30", "M15"], "temporal_hierarchy"), _COORD_ENV_KWARGS,
        connector=fake, max_iterations=1)

    m15_calls = [c for c in fake.calls if c["style"] == "M15"]
    assert len(m15_calls) == 1
    assert m15_calls[0]["target"] == 0.0, (
        "écart de 1 niveau : maintenant BLOQUÉ aussi -- zéro hedging toléré, "
        "même à un seul niveau d'écart"
    )


def test_demo_trader_temporal_hierarchy_m30_and_h1_coexist_opposite_directions(tmp_path, monkeypatch):
    """HIÉRARCHIE TEMPORELLE -- écart = 1 niveau entre styles ADJACENTS
    (M30=niveau 2, H1=niveau 3) : le style SUPÉRIEUR (H1) ne doit jamais
    être restreint par un style inférieur déjà en position opposée --
    seul l'inférieur peut être bloqué/réduit, jamais l'inverse."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module

    _write_champion_meta("H1", gen=1, score=0.0, passes_validation=True)
    _patch_style_runtime(monkeypatch, demo_trader_module, {"H1": (-1.0, 0.02)})

    fake = _CoordFakeConnector(preexisting={"M30": 1})  # M30 déjà LONG
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(["M30", "H1"], "temporal_hierarchy"), _COORD_ENV_KWARGS,
        connector=fake, max_iterations=1)

    h1_calls = [c for c in fake.calls if c["style"] == "H1"]
    assert len(h1_calls) == 1
    assert h1_calls[0]["target"] == -1.0, (
        "H1 (niveau 3, supérieur) doit pouvoir s'ouvrir SHORT malgré M30 (niveau 2) déjà LONG -- "
        "M30 et H1 coexistent en directions opposées."
    )


def test_demo_trader_temporal_hierarchy_d1_and_h4_coexist_opposite_directions(tmp_path, monkeypatch):
    """HIÉRARCHIE TEMPORELLE -- même vérification que ci-dessus sur la paire
    adjacente D1 (niveau 5) / H4 (niveau 4, écart 1) : les deux plus hauts
    rangs de la hiérarchie doivent aussi pouvoir coexister en directions
    opposées."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module

    _write_champion_meta("D1", gen=1, score=0.0, passes_validation=True)
    _patch_style_runtime(monkeypatch, demo_trader_module, {"D1": (1.0, 0.02)})

    fake = _CoordFakeConnector(preexisting={"H4": -1})  # H4 déjà SHORT
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(["H4", "D1"], "temporal_hierarchy"), _COORD_ENV_KWARGS,
        connector=fake, max_iterations=1)

    d1_calls = [c for c in fake.calls if c["style"] == "D1"]
    assert len(d1_calls) == 1
    assert d1_calls[0]["target"] == 1.0, (
        "D1 (niveau 5, supérieur) doit pouvoir s'ouvrir LONG malgré H4 (niveau 4) déjà SHORT -- "
        "D1 et H4 coexistent en directions opposées."
    )


def test_demo_trader_conflict_resolution_disabled_bypasses_temporal_hierarchy_too(tmp_path, monkeypatch):
    """`conflict_resolution: "disabled"` doit court-circuiter la hiérarchie
    temporelle EXACTEMENT comme il court-circuitait "priority_by_score" --
    même écart énorme (D1 vs M15, 4 niveaux) qui serait bloqué sous
    "temporal_hierarchy" (voir test ci-dessus) doit laisser passer M15 sans
    aucune restriction quand la coordination est désactivée."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module

    _write_champion_meta("M15", gen=1, score=0.0, passes_validation=True)
    _patch_style_runtime(monkeypatch, demo_trader_module, {"M15": (-1.0, 0.02)})

    fake = _CoordFakeConnector(preexisting={"D1": 1})  # D1 déjà LONG
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(["D1", "M15"], "disabled"), _COORD_ENV_KWARGS,
        connector=fake, max_iterations=1)

    m15_calls = [c for c in fake.calls if c["style"] == "M15"]
    assert len(m15_calls) == 1
    assert m15_calls[0]["target"] == -1.0, (
        "coordination désactivée : M15 doit ouvrir SHORT malgré l'écart hiérarchique avec D1"
    )


def test_demo_trader_dynamic_risk_budget_scales_with_active_style_count(tmp_path, monkeypatch):
    """BUDGET DYNAMIQUE -- option B (19/09, remplace la division fixe par la
    taille du pool) : le budget par trade est
    max_risk_pct_per_trade / nombre de styles RÉELLEMENT en position au
    moment de l'ouverture. Vérifié avec 1, 3 et 5 styles actifs
    simultanément, à pool CONSTANT (5 styles configurés) : sous l'ancienne
    option A les trois cas auraient donné le même 0.004 (0.02/5) même avec
    4 styles flat -- c'est précisément ce que cette option corrige."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module

    _write_champion_meta("H1", gen=10, score=3.0, passes_validation=True)
    _patch_style_runtime(monkeypatch, demo_trader_module, {"H1": (1.0, 0.02)})

    pool = ["H1", "H4", "D1", "M30", "M15"]

    # (styles DÉJÀ en position en plus de H1) -> (styles actifs attendus)
    for others, expected_active in [([], 1), (["H4", "D1"], 3), (["H4", "D1", "M30", "M15"], 5)]:
        # Même direction que H1 (LONG) : aucun conflit possible, on isole
        # ici le seul calcul de budget.
        fake = _CoordFakeConnector(preexisting={s: 1 for s in others})
        demo_trader_module.run_demo_trading_loop(
            _coord_cfg(pool, "priority_by_score"), _COORD_ENV_KWARGS,
            connector=fake, max_iterations=1)

        h1_calls = [c for c in fake.calls if c["style"] == "H1"]
        assert len(h1_calls) == 1, f"un seul appel H1 attendu ({expected_active} actifs)"
        assert h1_calls[0]["target"] == 1.0
        assert h1_calls[0]["risk_pct_override"] == 0.02 / expected_active, (
            f"{expected_active} style(s) actif(s) -> budget attendu {0.02 / expected_active}, "
            f"obtenu {h1_calls[0]['risk_pct_override']}"
        )

    # Un style SEUL actif doit bien utiliser 100% du budget max (et non
    # 1/5 comme avant), c'est l'objectif explicite de l'option B.
    fake_solo = _CoordFakeConnector(preexisting={})
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(pool, "priority_by_score"), _COORD_ENV_KWARGS,
        connector=fake_solo, max_iterations=1)
    assert fake_solo.calls[0]["risk_pct_override"] == 0.02


def test_walkforward_evaluation_reduces_single_path_luck(tmp_path, monkeypatch):
    """Répond directement à l'observation d'un écart énorme (30% à 130% de
    rendement) entre candidats d'une même génération : vérifie que
    l'évaluation walk-forward (1) découpe bien en plusieurs fenêtres
    indépendantes, (2) agrège le drawdown en prenant le PIRE cas (pas une
    moyenne qui le diluerait), et (3) reste cohérente avec un repli sur une
    seule fenêtre si le jeu de validation est trop court pour être découpé.
    """
    monkeypatch.chdir(tmp_path)
    from src.backtester import evaluate_agent, evaluate_agent_walkforward
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent

    df = generate_synthetic_ohlcv(n_bars=4000, seed=11)
    df = add_technical_features(df)
    train_df, val_df, _ = chronological_split(df, 0.7, 0.3)
    train_df, stats = normalize_features(train_df, columns=FEATURE_COLUMNS)
    val_df, _ = normalize_features(val_df, stats, columns=FEATURE_COLUMNS)

    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1,
                       feature_columns=FEATURE_COLUMNS)
    env = TradingEnv(train_df, **env_kwargs)
    agent = TradingAgent(env, {"n_steps": 64, "batch_size": 16, "device": "cpu"})
    agent.learn(64)

    wf = evaluate_agent_walkforward(agent, val_df, env_kwargs, n_windows=3)
    assert "per_window" in wf and len(wf["per_window"]) == 3
    # le drawdown agrégé doit être le pire, jamais inférieur à celui de chaque fenêtre
    worst = max(w["max_drawdown"] for w in wf["per_window"])
    assert wf["max_drawdown"] == worst

    # repli sur une seule fenêtre si le dataset est trop court pour être découpé
    tiny_df = val_df.iloc[:30].reset_index(drop=True)
    single = evaluate_agent(agent, tiny_df, env_kwargs)
    fallback = evaluate_agent_walkforward(agent, tiny_df, env_kwargs, n_windows=10)
    assert "per_window" not in fallback
    assert fallback["n_trades"] == single["n_trades"]


def test_walkforward_score_weighted_by_trade_count_not_simple_mean(tmp_path, monkeypatch):
    """Reproduit exactement le bug trouvé en usage réel le 14/09 : le style
    H4 n'avait plus progressé depuis sa génération 1 en ~89 cycles. Cause :
    l'agrégation par fenêtre (sharpe, total_return, win_rate, profit_factor)
    était une MOYENNE SIMPLE, où une fenêtre à 5 trades pesait autant
    qu'une fenêtre à 70 trades -- un pur coup de chance sur un échantillon
    minuscule (variance énorme) pouvait gonfler le score agrégé et rendre
    la barre à battre artificiellement haute pour de vrais meilleurs
    candidats. Ce test isole l'agrégation (mock de evaluate_agent, pas de
    vrai entraînement) avec exactement le motif observé : une fenêtre à 5
    trades et un Sharpe très élevé, entourée de fenêtres à bien plus de
    trades et un Sharpe plus modeste -- vérifie que le résultat pondéré est
    proche de la moyenne pondérée par trades, PAS de la moyenne simple."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.backtester as bt

    # "sortino" (audit institutionnel, item 5) : ajouté à chaque fenêtre
    # simulée -- evaluate_agent_walkforward l'agrège maintenant comme
    # "sharpe" (voir _weighted_mean), sinon KeyError. Valeur sans importance
    # pour CE test (qui ne vérifie que la pondération de sharpe/total_return
    # par nombre de trades) -- reprend simplement la valeur de "sharpe".
    fake_windows = [
        {"total_return": 0.227, "sharpe": 1.641, "sortino": 1.641, "max_drawdown": 0.188, "win_rate": 0.048,
         "profit_factor": 1.051, "n_trades": 21, "stop_exit_rate": 0.0},
        {"total_return": 0.118, "sharpe": 1.087, "sortino": 1.087, "max_drawdown": 0.201, "win_rate": 0.0,
         "profit_factor": 0.0, "n_trades": 15, "stop_exit_rate": 0.0},
        {"total_return": 0.589, "sharpe": 4.464, "sortino": 4.464, "max_drawdown": 0.088, "win_rate": 0.2,
         "profit_factor": 5.230, "n_trades": 5, "stop_exit_rate": 0.0},
        {"total_return": 0.876, "sharpe": 3.255, "sortino": 3.255, "max_drawdown": 0.231, "win_rate": 0.129,
         "profit_factor": 3.377, "n_trades": 70, "stop_exit_rate": 0.0},
    ]
    calls = iter(fake_windows)
    with patch.object(bt, "evaluate_agent", side_effect=lambda *a, **k: next(calls)):
        df = generate_synthetic_ohlcv(n_bars=4000, seed=1)
        env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                           reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
        result = bt.evaluate_agent_walkforward(None, df, env_kwargs, n_windows=4)

    simple_mean_sharpe = sum(w["sharpe"] for w in fake_windows) / 4  # 2.612 (ancien comportement)
    weighted_sharpe = sum(w["sharpe"] * w["n_trades"] for w in fake_windows) / sum(w["n_trades"] for w in fake_windows)

    # Sur CES données précises (celles d'H4 en conditions réelles), la
    # pondération par trades donne un résultat plus ÉLEVÉ que la moyenne
    # simple (2.71 contre 2.61) -- la fenêtre à 70 trades a elle-même un
    # Sharpe élevé (3.26) et pèse maintenant bien plus lourd que la fenêtre
    # à 5 trades qu'on soupçonnait de fausser le score. La direction n'est
    # PAS garantie a priori : ce test vérifie que le calcul correspond
    # EXACTEMENT à la moyenne pondérée par trades (la correction
    # statistiquement correcte), pas une direction supposée à l'avance.
    assert abs(result["sharpe"] - weighted_sharpe) < 1e-6, \
        f"doit correspondre à la moyenne PONDÉRÉE ({weighted_sharpe:.3f}), obtenu {result['sharpe']:.3f}"
    assert abs(result["sharpe"] - simple_mean_sharpe) > 0.01, \
        "la pondération doit changer concrètement le résultat par rapport à l'ancienne moyenne simple"
    # le drawdown agrégé (le pire cas) ne doit PAS être affecté par ce changement
    assert result["max_drawdown"] == max(w["max_drawdown"] for w in fake_windows)


def test_continuous_evolution_improves_via_warm_start(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = dict(BASE_CFG)
    cfg["memory"] = {"db_path": "mem.sqlite", "max_episodes": 500}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)

    trainer = ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)
    assert not trainer.has_champion()
    trainer.run_one_cycle()
    assert trainer.has_champion(), "un champion doit exister après le premier cycle"
    gen0_score = trainer.champion_score["H1"]
    trainer.run_one_cycle()
    # le score du champion ne doit jamais RÉGRESSER (on ne promeut que si mieux)
    assert trainer.champion_score["H1"] >= gen0_score
    trainer.close()


def test_mt5_connector_blocks_real_account(tmp_path, monkeypatch):
    # isolation cwd (19/09) : send_order() écrit maintenant un journal
    # d'exécution best-effort (data/execution_log.jsonl, voir
    # MT5Connector._log_execution) quand un ordre RÉEL passe -- sans chdir
    # vers un répertoire temporaire, ce test écrirait dans le vrai dossier
    # data/ du projet au lieu d'un emplacement jetable.
    monkeypatch.chdir(tmp_path)
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class RealAccount:
        trade_mode = 2  # réel

    called = {"order_sent": False}
    fake_mt5.account_info = lambda: RealAccount()
    fake_mt5.positions_get = lambda symbol=None: []
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=1.1, ask=1.1001)

    def fake_order_send(request):
        called["order_sent"] = True
        return types.SimpleNamespace(retcode=10009)

    fake_mt5.order_send = fake_order_send

    cfg = {"live": {"symbol": "EURUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    assert conn.is_demo_account() is False
    conn.send_order(1)
    assert called["order_sent"] is False, "AUCUN ordre réel ne doit être envoyé sur un compte non-démo"


def test_mt5_connector_allows_demo_account(tmp_path, monkeypatch):
    # isolation cwd (19/09) : voir le commentaire équivalent dans
    # test_mt5_connector_blocks_real_account -- ce test envoie un ordre
    # RÉEL (compte démo confirmé), donc écrit bien dans
    # data/execution_log.jsonl si le cwd n'est pas isolé.
    monkeypatch.chdir(tmp_path)
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class DemoAccount:
        trade_mode = 0

    called = {"order_sent": False}
    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.positions_get = lambda symbol=None: []
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=1.1, ask=1.1001)

    def fake_order_send(request):
        called["order_sent"] = True
        return types.SimpleNamespace(retcode=10009)

    fake_mt5.order_send = fake_order_send

    cfg = {"live": {"symbol": "EURUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    assert conn.is_demo_account() is True
    conn.send_order(1)
    assert called["order_sent"] is True, "un ordre doit être envoyé sur un compte démo confirmé"


def _make_fake_mt5_with_account(equity: float, bid: float, ask: float, contract_size: float,
                                  requests: list):
    """Faux module MT5 complet (équité, symbole, tick) pour vérifier le
    dimensionnement basé sur le risque réel (voir MT5Connector.send_order),
    par opposition aux deux tests ci-dessus qui vérifient seulement le
    garde-fou démo/réel avec un faux minimal (sans équité ni symbole -> ils
    exercent volontairement le repli sur live.lot_size)."""
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class DemoAccount:
        trade_mode = 0
    DemoAccount.equity = equity

    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.positions_get = lambda symbol=None: []
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
        trade_contract_size=contract_size, volume_step=0.01, volume_min=0.01,
        volume_max=100.0, digits=2, filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=bid, ask=ask)

    def fake_order_send(request):
        requests.append(request)
        return types.SimpleNamespace(retcode=10009)
    fake_mt5.order_send = fake_order_send
    return fake_mt5


def test_mt5_connector_sizes_position_from_risk_not_fixed_lot(tmp_path, monkeypatch):
    """Répond directement à la demande de l'utilisateur : laisser l'agent
    doser lui-même son exposition selon son équité RÉELLE et le risque réel
    en jeu, plutôt qu'un lot toujours identique. Vérifie que (1) la taille
    dépend de l'équité et de la distance du stop CHOISI PAR L'AGENT (pas de
    live.lot_size), et (2) qu'un stop plus large réduit la taille pour
    garder le même risque en dollars -- le compromis taille/risque qu'un
    vrai trader fait, impossible avec un lot fixe."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector

    # équité 10 000$, or à 2000$/oz (bid=ask pour simplifier), contrat de
    # 100 oz -- risque max 2% (200$) par défaut.
    requests_a = []
    fake_mt5 = _make_fake_mt5_with_account(equity=10000.0, bid=2000.0, ask=2000.0,
                                            contract_size=100.0, requests=requests_a)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    conn.send_order(1.0, stop_pct=0.01)  # stop à 1% -> distance de 20$/oz
    assert len(requests_a) == 1
    # 200$ de risque max / (20$ x 100oz par lot) = 0.10 lot
    assert abs(requests_a[0]["volume"] - 0.10) < 1e-6, \
        f"taille attendue ≈0.10 lot (risque/stop), obtenu {requests_a[0]['volume']}"

    # même équité, stop DEUX FOIS PLUS LARGE -> position DEUX FOIS PLUS PETITE
    # pour garder le même risque en dollars.
    requests_b = []
    fake_mt5_b = _make_fake_mt5_with_account(equity=10000.0, bid=2000.0, ask=2000.0,
                                              contract_size=100.0, requests=requests_b)
    conn_b = MT5Connector(cfg)
    conn_b._mt5 = fake_mt5_b
    conn_b.send_order(1.0, stop_pct=0.02)
    assert len(requests_b) == 1
    assert abs(requests_b[0]["volume"] - 0.05) < 1e-6, \
        f"un stop deux fois plus large doit donner une taille deux fois plus petite, obtenu {requests_b[0]['volume']}"


def test_mt5_connector_floors_to_min_lot_when_risk_sizing_rounds_to_zero(tmp_path, monkeypatch):
    """Reproduit exactement le cas trouvé en conditions réelles le 14/09 :
    compte démo à 1000$, or à ~2650$/oz, stop de l'agent à 1% -> le calcul
    par risque (2% par défaut) donne 0.0075 lot, sous le minimum broker
    (0.01) -- H1 avait un signal fort (+1.00, pleine conviction) mais AUCUN
    ordre n'était envoyé, silencieusement, malgré la conviction de l'agent.
    Avec le floor (demande explicite de l'utilisateur), un signal
    directionnel réel doit remonter au lot minimum plutôt que disparaître."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = _make_fake_mt5_with_account(equity=1000.0, bid=2650.0, ask=2650.0,
                                            contract_size=100.0, requests=requests)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    conn.send_order(1.0, stop_pct=0.01)
    assert len(requests) == 1, "un signal directionnel réel ne doit jamais disparaître silencieusement"
    assert abs(requests[0]["volume"] - 0.01) < 1e-6, \
        f"doit être remonté au lot minimum (0.01), obtenu {requests[0]['volume']}"

    # à l'inverse, un style FLAT (pas de conviction directionnelle) ne doit
    # toujours PAS forcer un ordre -- le floor ne s'applique qu'à un vrai signal.
    requests_flat = []
    fake_mt5_flat = _make_fake_mt5_with_account(equity=1000.0, bid=2650.0, ask=2650.0,
                                                 contract_size=100.0, requests=requests_flat)
    conn_flat = MT5Connector(cfg)
    conn_flat._mt5 = fake_mt5_flat
    conn_flat.send_order(0.0, stop_pct=0.01)
    assert len(requests_flat) == 0, "flat doit rester flat, jamais forcé au lot minimum"


def test_mt5_connector_does_not_reopen_unchanged_position_every_cycle(tmp_path, monkeypatch):
    """Reproduit exactement le bug observé en conditions réelles le 14/09 :
    l'utilisateur a remarqué dans l'historique MT5 une position XAUUSD
    fermée puis rouverte IDENTIQUE toutes les 5 minutes (poll_seconds),
    alors que le modèle décidait H1=+1.00 (pleine conviction) à CHAQUE
    cycle sans jamais changer d'avis -- payant le spread deux fois à
    chaque cycle pour rien. Cause : get_open_position() comparait le lot
    RISQUE réellement ouvert (souvent le lot minimum du broker après floor,
    voir le correctif précédent) à une taille de référence NOTIONNELLE
    différente, donnant une exposition "actuelle" jamais proche de 1.0.
    Ce test simule une VRAIE position ouverte (positions_get renvoie l'ordre
    déjà passé) et vérifie qu'un second appel avec la MÊME cible et le
    MÊME stop ne déclenche NI fermeture NI réouverture."""
    monkeypatch.chdir(tmp_path)
    import types
    from src.mt5_connector import MT5Connector

    requests = []
    open_position = {"volume": None, "type": None}

    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class DemoAccount:
        trade_mode = 0
        equity = 1000.0
    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
        trade_contract_size=100.0, volume_step=0.01, volume_min=0.01, volume_max=100.0,
        digits=2, filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=2650.0, ask=2650.0)

    def fake_positions_get(symbol=None):
        if open_position["volume"] is None:
            return []
        return [types.SimpleNamespace(volume=open_position["volume"], type=open_position["type"],
                                       ticket=1, symbol="XAUUSD")]
    fake_mt5.positions_get = fake_positions_get

    def fake_order_send(request):
        requests.append(request)
        if request.get("action") == fake_mt5.TRADE_ACTION_DEAL and "position" not in request:
            open_position["volume"] = request["volume"]
            open_position["type"] = request["type"]
        elif "position" in request:
            open_position["volume"] = None
        return types.SimpleNamespace(retcode=10009)
    fake_mt5.order_send = fake_order_send

    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(1.0, stop_pct=0.01)
    assert len(requests) == 1, "première décision : une seule ouverture"
    assert open_position["volume"] == 0.01

    requests.clear()
    conn.send_order(1.0, stop_pct=0.01)
    assert len(requests) == 0, (
        "MÊME décision (H1=+1.00, même stop) au cycle suivant : ne doit RIEN renvoyer -- "
        "reproduit le bug du 'scalping' involontaire (fermeture/réouverture à chaque cycle)"
    )


def test_mt5_connector_does_not_reopen_when_ensemble_gives_fractional_exposure(tmp_path, monkeypatch):
    """Reproduit le bug observé en conditions réelles le 15/09, dès que M15
    a rejoint H1 comme 2e style éligible à la démo (voir demo_trader.py,
    ensemble pondéré) : les logs montrent 'Décision ensemble ... H1=+0.00
    (poids=0.87, stop=5.00%), M15=+1.00 (poids=0.13, stop=2.00%) ->
    exposition finale = +0.13, stop=2.00%' IDENTIQUE à deux cycles
    consécutifs (5 min d'écart) -- pourtant la position a été fermée puis
    rouverte à chaque cycle, payant le spread deux fois pour rien, malgré
    une décision qui n'a pas changé d'un iota.

    Cause : sur ce compte modeste (968$) tradant XAUUSD (grosse valeur de
    contrat), le calcul par risque donne un lot BRUT sous le minimum broker
    même à pleine conviction (target_exposure=1.0) -- `_risk_based_lots`
    (qui ne dépend PAS de target_exposure, seulement du stop et de
    l'équité) est déjà sous 0.01 avant même d'être mis à l'échelle par la
    conviction. Le floor (voir
    test_mt5_connector_floors_to_min_lot_when_risk_sizing_rounds_to_zero)
    s'applique donc IDENTIQUEMENT que la conviction soit 0.13 ou 1.0 --
    0.01 lot dans les deux cas. `get_open_position` divisait alors le lot
    RÉELLEMENT ouvert (0.01) par une taille de référence qui, elle AUSSI,
    finissait flooree à 0.01 -- reconstruisant TOUJOURS une exposition
    'actuelle' de 1.0 (pleine conviction), quelle que soit la conviction
    d'origine réellement floorée à l'ouverture. Dès que la cible n'est PAS
    proche de {-1, 0, 1} (le cas normal d'un ensemble à plusieurs styles en
    désaccord), l'écart avec ce 1.0 reconstruit dépasse toujours la
    tolérance de 0.05 -- fermeture/réouverture à chaque cycle pour rien.
    Corrigé en comparant directement la DIRECTION et le VOLUME réels de la
    position ouverte au volume qui serait envoyé pour la cible actuelle,
    au lieu de reconstruire (avec perte d'information) une fraction
    d'exposition à partir d'un lot déjà floored."""
    monkeypatch.chdir(tmp_path)
    import types
    from src.mt5_connector import MT5Connector

    requests = []
    open_position = {"volume": None, "type": None}

    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class DemoAccount:
        trade_mode = 0
        equity = 968.0
    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
        trade_contract_size=100.0, volume_step=0.01, volume_min=0.01, volume_max=100.0,
        digits=2, filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=4296.0, ask=4296.0)

    def fake_positions_get(symbol=None):
        if open_position["volume"] is None:
            return []
        return [types.SimpleNamespace(volume=open_position["volume"], type=open_position["type"],
                                       ticket=1, symbol="XAUUSD")]
    fake_mt5.positions_get = fake_positions_get

    def fake_order_send(request):
        requests.append(request)
        if request.get("action") == fake_mt5.TRADE_ACTION_DEAL and "position" not in request:
            open_position["volume"] = request["volume"]
            open_position["type"] = request["type"]
        elif "position" in request:
            open_position["volume"] = None
        return types.SimpleNamespace(retcode=10009)
    fake_mt5.order_send = fake_order_send

    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(0.13, stop_pct=0.02)
    assert len(requests) == 1, "première décision : une seule ouverture"
    assert open_position["volume"] == 0.01

    requests.clear()
    conn.send_order(0.13, stop_pct=0.02)
    assert len(requests) == 0, (
        "MÊME exposition fractionnaire (+0.13) au cycle suivant : ne doit RIEN renvoyer -- "
        "reproduit le retour du bug de scalping avec un 2e style dans l'ensemble"
    )


def test_mt5_connector_caps_executed_stop_distance(tmp_path, monkeypatch):
    """Demande explicite de l'utilisateur (15/09) après avoir constaté un
    stop réel envoyé à MT5 à ~4.4% du prix d'entrée -- une distance si large
    qu'elle ne protège plus rien en pratique (la perte flottante peut
    s'accumuler librement avant que l'agent ne décide de fermer). Ajout de
    `live.max_stop_pct_executed` : plafonne la distance RÉELLEMENT utilisée
    à l'exécution (dimensionnement ET champ `sl` envoyé au broker), SANS
    toucher aux buckets de stop appris par l'agent (`agent.stop_loss_buckets`
    reste inchangé -- le modèle choisit toujours librement parmi eux, seule
    la distance exécutée en aval est bornée, comme risk_guard/le
    coupe-circuit de compte bornent déjà d'autres aspects sans jamais
    modifier l'espace d'action)."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = _make_fake_mt5_with_account(equity=1000.0, bid=2650.0, ask=2650.0,
                                            contract_size=100.0, requests=requests)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                     "allow_real_account": False, "max_stop_pct_executed": 0.02}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    # L'agent demande un stop à 5% (le plus large de ses buckets) -- doit
    # être plafonné à 2% (max_stop_pct_executed) pour le dimensionnement ET
    # le champ sl envoyé au broker.
    conn.send_order(1.0, stop_pct=0.05)
    assert len(requests) == 1
    # RESSERRÉ de 2597.0 à 2630.0 (voir MT5Connector.send_order, correctif
    # lot/stop) : à stop_pct=2% (déjà plafonné ici par max_stop_pct_executed),
    # le lot IDÉAL par risque (~0.0038 lot, budget 20$ / distance 53$ / contrat
    # 100) tombe ENCORE sous le minimum broker (0.01) et est remonté à ce
    # minimum -- le correctif du resserrement lot/stop s'applique donc EN
    # CASCADE par-dessus le plafond de 2% déjà en place, resserrant encore le
    # stop RÉELLEMENT envoyé (~0.75%) pour que le risque réel au lot flooré
    # (0.01 x 20$ x 100 = 20$) corresponde exactement au budget ciblé (2% de
    # 1000$), au lieu de rester silencieusement à 2% de distance sur un lot
    # devenu plus gros que prévu (risque réel alors > budget ciblé).
    expected_sl_after_risk_tightening = 2630.0
    uncapped_sl_would_be = round(2650.0 * (1 - 0.05), 2)   # 2517.5
    assert requests[0]["sl"] == expected_sl_after_risk_tightening, (
        f"le stop envoyé au broker doit être resserré à ~0.75% ({expected_sl_after_risk_tightening}) "
        f"pour tenir le budget de risque au lot flooré, pas le 5% brut demandé par l'agent "
        f"({uncapped_sl_would_be}) -- obtenu {requests[0]['sl']}"
    )


def test_mt5_connector_falls_back_to_notional_equity_without_stop(tmp_path, monkeypatch):
    """Sans stop disponible (agent.learn_stop_loss désactivé), la taille
    doit retomber sur une fraction notionnelle de l'équité réelle (pas sur
    live.lot_size, tant que l'équité/le symbole sont connus)."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = _make_fake_mt5_with_account(equity=10000.0, bid=2000.0, ask=2000.0,
                                            contract_size=100.0, requests=requests)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    conn.send_order(1.0, stop_pct=None)
    assert len(requests) == 1
    # 10 000$ d'équité / (2000$ x 100oz par lot) = 0.05 lot -- PAS 0.01 (live.lot_size)
    assert abs(requests[0]["volume"] - 0.05) < 1e-6, \
        f"repli notionnel/équité attendu ≈0.05 lot, obtenu {requests[0]['volume']}"


def _make_fake_mt5_small_account(equity, bid, ask, contract_size, requests,
                                  trade_stops_level=0, point=0.01):
    """Faux module MT5 pour les scénarios de petit compte où le lot calculé
    par risque tombe sous le minimum broker (voir les tests de resserrement
    du stop ci-dessous) -- variante de `_make_fake_mt5_with_account` qui
    expose aussi `trade_stops_level`/`point` (distance de stop minimale
    imposée par le broker, nécessaires au garde-fou dur)."""
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class DemoAccount:
        trade_mode = 0
    DemoAccount.equity = equity

    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.positions_get = lambda symbol=None: []
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
        trade_contract_size=contract_size, volume_step=0.01, volume_min=0.01,
        volume_max=100.0, digits=2, filling_mode=0,
        trade_stops_level=trade_stops_level, point=point)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=bid, ask=ask)

    def fake_order_send(request):
        requests.append(request)
        return types.SimpleNamespace(retcode=10009)
    fake_mt5.order_send = fake_order_send
    return fake_mt5


def test_mt5_connector_tightens_stop_after_lot_floored_to_broker_minimum(tmp_path, monkeypatch):
    """Reproduit et corrige le bug confirmé par calcul : compte 1000$,
    XAUUSD à 4300, stop 1% -- le lot IDÉAL par risque (0.0047 lot) tombe
    sous le minimum broker (0.01) et est remonté au minimum. SANS
    recalcul, le risque réel au lot final serait de 0.01 x 43 x 100 = 43$,
    plus du double du budget ciblé (20$ = 2% de 1000$). Le stop
    RÉELLEMENT envoyé à MT5 doit être resserré pour que le risque réel
    (volume final x distance x contrat) ne dépasse jamais ce budget."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = _make_fake_mt5_small_account(equity=1000.0, bid=4300.0, ask=4300.0,
                                             contract_size=100.0, requests=requests)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                     "allow_real_account": False, "max_risk_pct_per_trade": 0.02}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    conn.send_order(1.0, stop_pct=0.01)

    assert len(requests) == 1, "lot flooré au minimum -> un signal réel doit quand même partir"
    req = requests[0]
    assert abs(req["volume"] - 0.01) < 1e-6

    max_loss_dollars = 1000.0 * 0.02
    real_risk_dollars = req["volume"] * abs(req["price"] - req["sl"]) * 100.0
    assert real_risk_dollars <= max_loss_dollars + 1e-6, (
        f"risque réel ({real_risk_dollars:.2f}$) dépasse le budget ciblé "
        f"({max_loss_dollars:.2f}$) -- le stop n'a pas été resserré après floor du lot"
    )


def test_mt5_connector_tightens_stop_after_lot_floored_to_broker_minimum_wider_stop(tmp_path, monkeypatch):
    """Même compte/symbole que le test précédent, mais stop de l'agent à 2%
    -- lot idéal encore plus petit (0.0023 lot), floor identique (0.01).
    SANS recalcul, le risque réel serait de 0.01 x 86 x 100 = 86$, soit
    ~4.3x le budget ciblé (20$) -- le facteur x4 confirmé par calcul dans
    la demande. Doit rester borné après correctif, comme le cas à 1%."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = _make_fake_mt5_small_account(equity=1000.0, bid=4300.0, ask=4300.0,
                                             contract_size=100.0, requests=requests)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                     "allow_real_account": False, "max_risk_pct_per_trade": 0.02}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    conn.send_order(1.0, stop_pct=0.02)

    assert len(requests) == 1
    req = requests[0]
    assert abs(req["volume"] - 0.01) < 1e-6

    max_loss_dollars = 1000.0 * 0.02
    real_risk_dollars = req["volume"] * abs(req["price"] - req["sl"]) * 100.0
    assert real_risk_dollars <= max_loss_dollars + 1e-6, (
        f"risque réel ({real_risk_dollars:.2f}$) dépasse le budget ciblé "
        f"({max_loss_dollars:.2f}$) -- non borné pour un stop plus large"
    )


def test_mt5_connector_cancels_order_when_tightened_stop_below_broker_minimum(tmp_path, monkeypatch):
    """Garde-fou dur : si le broker impose une distance de stop minimale
    (trade_stops_level) PLUS LARGE que le stop resserré nécessaire pour
    respecter le budget de risque, il est structurellement impossible de
    satisfaire les deux en même temps à ce prix/cette taille de compte --
    l'ordre doit être annulé plutôt que d'envoyer un risque excessif (ou un
    ordre que MT5 rejetterait de toute façon)."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector

    requests = []
    # stops_level=3000 points x point=0.01 = distance mini 30 -> 30/4300
    # ≈ 0.698%, largement au-dessus du stop resserré nécessaire (≈0.465%,
    # voir les deux tests précédents) -- impossible à satisfaire.
    fake_mt5 = _make_fake_mt5_small_account(equity=1000.0, bid=4300.0, ask=4300.0,
                                             contract_size=100.0, requests=requests,
                                             trade_stops_level=3000, point=0.01)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                     "allow_real_account": False, "max_risk_pct_per_trade": 0.02}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    conn.send_order(1.0, stop_pct=0.01)

    assert len(requests) == 0, (
        "ordre structurellement impossible à sécuriser (stop_level broker > stop resserré requis) "
        "-- doit être annulé, jamais envoyé avec un risque excessif"
    )


def test_position_comment_tag_format_and_parsing():
    """Format de tag "{style} gen:{génération}" (18/09, fondation du
    multi-position) : lisible directement dans l'historique MT5, et le
    parsing (utilisé pour retrouver la position d'UN style précis) doit
    retomber sur exactement le même style, sans confusion avec un comment
    générique/manuel."""
    from src.mt5_connector import _position_comment, _parse_style_from_comment

    comment = _position_comment("D1", 296)
    assert comment == "D1 gen:296"
    assert _parse_style_from_comment(comment) == "D1"

    comment_m15 = _position_comment("M15", 314)
    assert comment_m15 == "M15 gen:314"
    assert _parse_style_from_comment(comment_m15) == "M15"

    # Génération manquante -- ne doit jamais planter, juste un repli lisible.
    assert _position_comment("H4", None) == "H4 gen:?"

    # Pas de style fourni du tout -- signal explicite pour l'appelant
    # (retombe sur les anciens comments génériques), pas une chaîne vide.
    assert _position_comment(None, 296) is None

    # Comments génériques/manuels legacy -- jamais interprétés comme un style.
    assert _parse_style_from_comment("opened_by_agent") is None
    assert _parse_style_from_comment("close_by_agent") is None
    assert _parse_style_from_comment(None) is None
    assert _parse_style_from_comment("") is None


def test_parse_generation_from_comment():
    """`_parse_generation_from_comment` (21/09, voir
    demo_trader.py::_resolve_entry_for_open_position) -- pendant de
    `_parse_style_from_comment` mais pour la génération, utilisé pour
    retrouver le snapshot archivé EXACT qui a ouvert une position."""
    from src.mt5_connector import _position_comment, _parse_generation_from_comment

    assert _parse_generation_from_comment(_position_comment("H4", 134)) == 134
    assert _parse_generation_from_comment(_position_comment("D1", 0)) == 0
    # Génération inconnue au moment de l'ouverture ("?", voir _position_comment) -- jamais une exception.
    assert _parse_generation_from_comment(_position_comment("H4", None)) is None
    assert _parse_generation_from_comment("opened_by_agent") is None
    assert _parse_generation_from_comment(None) is None
    assert _parse_generation_from_comment("") is None


def test_mt5_connector_closes_only_the_tagged_position_for_its_own_style(tmp_path, monkeypatch):
    """CORRECTIF DU BUG (18/09) : deux positions simultanées, sur des
    styles DIFFÉRENTS, en directions OPPOSÉES (D1 long, M15 short) --
    fermer la position de D1 ne doit JAMAIS toucher celle de M15, et
    inversement. Avant le correctif, la boucle de clôture utilisait UNE
    direction partagée (déduite de la première position trouvée) pour
    fermer TOUTES les positions -- silencieusement faux dès que deux
    positions coexistent en désaccord de direction."""
    monkeypatch.chdir(tmp_path)
    import types
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class DemoAccount:
        trade_mode = 0
        equity = 100000.0
    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
        trade_contract_size=100.0, volume_step=0.01, volume_min=0.01, volume_max=100.0,
        digits=2, filling_mode=0, trade_stops_level=0, point=0.01)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=4300.0, ask=4300.5)

    pos_d1 = types.SimpleNamespace(ticket=111, type=fake_mt5.ORDER_TYPE_BUY, volume=0.5,
                                    symbol="XAUUSD", comment="D1 gen:296")
    pos_m15 = types.SimpleNamespace(ticket=222, type=fake_mt5.ORDER_TYPE_SELL, volume=0.3,
                                     symbol="XAUUSD", comment="M15 gen:314")
    fake_mt5.positions_get = lambda symbol=None: [pos_d1, pos_m15]

    def fake_order_send(request):
        requests.append(request)
        return types.SimpleNamespace(retcode=10009)
    fake_mt5.order_send = fake_order_send

    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    # Fermeture demandée pour D1 (target=0.0, style="D1") -- ne doit
    # toucher QUE le ticket 111 (D1, long), jamais le ticket 222 (M15).
    conn.send_order(0.0, style="D1", generation=296)

    assert len(requests) == 1, f"une seule fermeture attendue (D1 seul), obtenu {len(requests)}"
    closed = requests[0]
    assert closed["position"] == 111, "doit fermer le ticket de D1, pas celui de M15"
    assert closed["type"] == fake_mt5.ORDER_TYPE_SELL, (
        "D1 est LONG (BUY) -- le fermer nécessite un ordre SELL, pas la direction de M15"
    )
    assert closed["comment"] == "D1 gen:296"

    # Symétrique : fermer M15 ne doit jamais toucher D1.
    requests.clear()
    conn.send_order(0.0, style="M15", generation=314)
    assert len(requests) == 1
    closed_m15 = requests[0]
    assert closed_m15["position"] == 222, "doit fermer le ticket de M15, pas celui de D1"
    assert closed_m15["type"] == fake_mt5.ORDER_TYPE_BUY, (
        "M15 est SHORT (SELL) -- le fermer nécessite un ordre BUY"
    )
    assert closed_m15["comment"] == "M15 gen:314"


def test_mt5_connector_send_order_without_style_keeps_legacy_behavior(tmp_path, monkeypatch):
    """`style=None` (appel non taggé, ce que demo_trader.py utilise encore
    aujourd'hui) doit garder EXACTEMENT le comportement d'origine : toutes
    les positions du symbole sont considérées, comments génériques."""
    monkeypatch.chdir(tmp_path)
    import types
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = _make_fake_mt5_with_account(equity=10000.0, bid=2000.0, ask=2000.0,
                                            contract_size=100.0, requests=requests)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5
    conn.send_order(1.0, stop_pct=0.01)  # pas de style -- comportement legacy

    assert len(requests) == 1
    assert requests[0]["comment"] == "opened_by_agent", "sans style, le comment générique d'origine doit rester"


def test_mt5_connector_opens_new_style_position_without_touching_an_existing_other_style(tmp_path, monkeypatch):
    """Étape 2 (18/09) : le style A détient déjà une position ouverte
    (long) ; le style B décide d'OUVRIR une position (short) au même
    moment. L'ouverture de B ne doit être NI bloquée (le contrôle
    anti-doublon ne doit comparer B qu'à SA PROPRE position, absente ici)
    NI faussée (le dimensionnement/comment de B ne doit référencer que B)
    par la présence de la position de A -- et la position de A ne doit
    apparaître dans AUCUNE requête envoyée pour B."""
    monkeypatch.chdir(tmp_path)
    import types
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class DemoAccount:
        trade_mode = 0
        equity = 100000.0
    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
        trade_contract_size=100.0, volume_step=0.01, volume_min=0.01, volume_max=100.0,
        digits=2, filling_mode=0, trade_stops_level=0, point=0.01)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=4300.0, ask=4300.5)

    # Style A (D1) a DEJA une position ouverte, longue -- jamais touchee par cet appel.
    pos_a = types.SimpleNamespace(ticket=111, type=fake_mt5.ORDER_TYPE_BUY, volume=0.5,
                                   symbol="XAUUSD", comment="D1 gen:296")
    fake_mt5.positions_get = lambda symbol=None: [pos_a]

    def fake_order_send(request):
        requests.append(request)
        return types.SimpleNamespace(retcode=10009)
    fake_mt5.order_send = fake_order_send

    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    # Style B (M15) ouvre une position SHORT -- A n'a aucune position pour
    # B (style_positions vide), donc rien a fermer, et le controle
    # anti-doublon (current_direction=0 pour B) ne doit pas bloquer.
    conn.send_order(-1.0, stop_pct=0.02, style="M15", generation=314)

    assert len(requests) == 1, f"une seule requete attendue (ouverture de B), obtenu {len(requests)}"
    opened = requests[0]
    assert opened["comment"] == "M15 gen:314"
    assert opened["type"] == fake_mt5.ORDER_TYPE_SELL
    assert "position" not in opened, "une OUVERTURE n'a jamais de champ 'position' (reserve aux clotures)"
    assert all(r.get("position") != 111 for r in requests), (
        "la position de A (ticket 111) ne doit apparaitre dans AUCUNE requete envoyee pour B"
    )


def test_mt5_connector_closes_only_orphan_positions_at_migration(tmp_path, monkeypatch):
    """Étape 3 (18/09), garde-fou de migration : une position déjà taguée
    pour un style RECONNU ne doit JAMAIS être fermée par
    close_orphan_positions (même si le format legacy existait aussi pour ce
    ticket) -- seules les positions au tag ABSENT ou NON reconnu (ex:
    l'ancien comment générique "opened_by_agent" de l'ère blending
    d'ensemble) sont fermées, une fois, proprement."""
    monkeypatch.chdir(tmp_path)
    import types
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class DemoAccount:
        trade_mode = 0
    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=4300.0, ask=4300.5)

    pos_tagged = types.SimpleNamespace(ticket=111, type=fake_mt5.ORDER_TYPE_BUY, volume=0.5,
                                        symbol="XAUUSD", comment="D1 gen:296", profit=42.0)
    pos_orphan = types.SimpleNamespace(ticket=999, type=fake_mt5.ORDER_TYPE_BUY, volume=0.73,
                                        symbol="XAUUSD", comment="opened_by_agent", profit=-183.23)
    fake_mt5.positions_get = lambda symbol=None: [pos_tagged, pos_orphan]

    def fake_order_send(request):
        requests.append(request)
        return types.SimpleNamespace(retcode=10009)
    fake_mt5.order_send = fake_order_send

    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    closed = conn.close_orphan_positions(recognized_styles=["D1", "M15", "H1", "H4", "M30"])

    assert len(requests) == 1, "seule la position orpheline doit être fermée"
    assert requests[0]["position"] == 999
    assert requests[0]["comment"] == "migration_close_untagged"
    assert all(r.get("position") != 111 for r in requests), \
        "la position déjà taguée pour un style reconnu ne doit JAMAIS être touchée"

    assert len(closed) == 1
    assert closed[0]["ticket"] == 999
    assert closed[0]["original_comment"] == "opened_by_agent"
    assert closed[0]["profit"] == -183.23

    # Idempotence : un second appel (ex: redémarrage suivant) ne doit plus
    # rien trouver à fermer une fois l'orpheline traitée -- ici le fake est
    # statique (ne retire pas pos_orphan de positions_get), donc on vérifie
    # seulement que l'appel reste sûr (ne plante pas) sur un jeu déjà propre
    # en simulant la disparition de l'orpheline après sa fermeture.
    fake_mt5.positions_get = lambda symbol=None: [pos_tagged]
    requests.clear()
    closed_again = conn.close_orphan_positions(recognized_styles=["D1", "M15", "H1", "H4", "M30"])
    assert closed_again == []
    assert requests == []


def _make_fake_mt5_accumulating(equity: float, price: float, contract_size: float,
                                  requests: list, positions: list):
    """Faux MT5 qui SIMULE LES EXÉCUTIONS : chaque ordre d'ouverture accepté
    ajoute réellement une position à `positions` (avec son prix d'entrée et
    son stop tels qu'envoyés). Indispensable pour tester l'exposition
    CUMULÉE, qui se relit sur `positions_get()` à chaque ouverture -- un faux
    qui renverrait toujours [] ne pourrait jamais rien cumuler."""
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class DemoAccount:
        trade_mode = 0
    DemoAccount.equity = equity

    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.positions_get = lambda symbol=None: list(positions)
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
        trade_contract_size=contract_size, volume_step=0.01, volume_min=0.01,
        volume_max=100.0, digits=2, filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=price, ask=price)

    def fake_order_send(request):
        requests.append(request)
        closing_ticket = request.get("position")
        if closing_ticket:
            # Une clôture RETIRE réellement la position : sans ça le faux
            # mentirait sur l'état du compte, et un futur test pourrait
            # passer au vert sur une exposition cumulée déjà libérée.
            positions[:] = [p for p in positions if p.ticket != closing_ticket]
        else:
            positions.append(types.SimpleNamespace(
                ticket=9000 + len(positions), type=request["type"], volume=request["volume"],
                symbol="XAUUSD", comment=request.get("comment", ""),
                price_open=request["price"], sl=request.get("sl", 0.0), profit=0.0))
        return types.SimpleNamespace(retcode=10009)
    fake_mt5.order_send = fake_order_send
    return fake_mt5


def _total_worst_case(positions, contract_size):
    from src.mt5_connector import _worst_case_loss
    return sum(_worst_case_loss(p.price_open, p.sl, p.volume, contract_size) for p in positions)


def test_mt5_connector_cumulative_exposure_caps_five_styles_stacking_same_direction(tmp_path, monkeypatch):
    """PLAFOND D'EXPOSITION CUMULÉE (19/09) -- reproduit EXACTEMENT le
    scénario chiffré qui a motivé ce garde-fou : 5 styles D'ACCORD sur la
    même direction ouvrent l'un après l'autre sous budget DYNAMIQUE (option
    B : 2%, puis 1%, 0.67%, 0.5%, 0.4% -- chacun divisé par le nombre de
    styles actifs à SON ouverture). Comme une position déjà ouverte n'est
    jamais redimensionnée quand un nouveau style la rejoint, le risque
    simultané s'empile.

    Chiffres (équité 100 000$, prix 1000, contrat 100, stop 1% -> 1000$ de
    risque par lot) :
      BRAS DE CONTRÔLE (plafond désactivé = état du code avant ce commit) :
        les 5 ouvertures passent, cumul = 4 566.65$ = 4.57% de l'équité,
        soit 2.28x le plafond NOMINAL par trade (2%) -- l'invariant cassé.
      BRAS PROTÉGÉ (plafond à 4%) : les 4ᵉ et 5ᵉ ouvertures sont refusées
        AVANT envoi, cumul réel plafonné à 3 666.65$ (3.67%), et les
        positions déjà ouvertes ne sont jamais touchées.
    """
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector

    EQUITY, PRICE, CONTRACT = 100000.0, 1000.0, 100.0
    # Budgets dynamiques de l'option B pour 5 styles ouvrant séquentiellement.
    budgets = [0.02, 0.01, 0.02 / 3, 0.005, 0.004]

    def _run(cumulative_cfg):
        requests, positions = [], []
        fake_mt5 = _make_fake_mt5_accumulating(EQUITY, PRICE, CONTRACT, requests, positions)
        cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                         "allow_real_account": False, **cumulative_cfg}}
        conn = MT5Connector(cfg)
        conn._mt5 = fake_mt5
        for i, budget in enumerate(budgets):
            conn.send_order(1.0, stop_pct=0.01, style=f"S{i + 1}", generation=i,
                             risk_pct_override=budget)
        return positions

    # --- BRAS DE CONTRÔLE : sans plafond, le problème est bien réel ---
    positions_unguarded = _run({})
    assert len(positions_unguarded) == 5, "sans plafond, les 5 styles ouvrent bien tous"
    total_unguarded = _total_worst_case(positions_unguarded, CONTRACT)
    assert abs(total_unguarded - 4566.65) < 1.0, \
        f"cumul non protégé attendu ~4566.65$, obtenu {total_unguarded:.2f}$"
    assert total_unguarded / EQUITY > 0.045, "le cumul non protégé dépasse bien 4.5% de l'équité"
    assert total_unguarded / (EQUITY * 0.02) > 2.2, \
        "le cumul non protégé dépasse bien 2.2x le plafond nominal par trade"

    # --- BRAS PROTÉGÉ : le plafond à 4% doit mordre AVANT le dépassement ---
    positions_guarded = _run({"cumulative_exposure_enabled": True,
                               "cumulative_exposure_max_pct": 0.04})
    assert len(positions_guarded) == 3, (
        f"les 4e et 5e ouvertures doivent être refusées, obtenu {len(positions_guarded)} positions "
        f"({[p.comment for p in positions_guarded]})"
    )
    assert [p.comment.split(" gen:")[0] for p in positions_guarded] == ["S1", "S2", "S3"], \
        "ce sont bien les 3 PREMIÈRES ouvertures qui passent, les suivantes qui sont refusées"

    total_guarded = _total_worst_case(positions_guarded, CONTRACT)
    assert total_guarded <= EQUITY * 0.04, (
        f"le cumul réel ({total_guarded:.2f}$) ne doit JAMAIS dépasser le plafond "
        f"({EQUITY * 0.04:.2f}$) -- le refus intervient AVANT le dépassement, pas après"
    )
    assert abs(total_guarded - 3666.65) < 1.0, \
        f"cumul protégé attendu ~3666.65$, obtenu {total_guarded:.2f}$"

    # Les positions déjà ouvertes sont intactes : un refus ne ferme rien.
    assert all(p.sl > 0 for p in positions_guarded), "les positions conservées gardent leur stop"


def test_mt5_connector_cumulative_exposure_never_blocks_a_close(tmp_path, monkeypatch):
    """Le plafond ne doit JAMAIS pouvoir bloquer une FERMETURE : une
    clôture ne fait que RÉDUIRE le risque, et un garde-fou qui empêcherait
    de sortir d'une position enfermerait le compte dans l'exposition qu'il
    est justement censé limiter. Vérifié dans l'état le plus défavorable :
    exposition déjà TRÈS au-dessus du plafond."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector

    requests, positions = [], []
    fake_mt5 = _make_fake_mt5_accumulating(100000.0, 1000.0, 100.0, requests, positions)
    # Position déjà ouverte, à elle seule très au-delà du plafond (10 lots
    # x 10 points x 100 = 10 000$ = 10% de l'équité, plafond à 1%).
    positions.append(types.SimpleNamespace(
        ticket=1, type=0, volume=10.0, symbol="XAUUSD", comment="D1 gen:204",
        price_open=1000.0, sl=990.0, profit=-50.0))

    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                     "allow_real_account": False, "cumulative_exposure_enabled": True,
                     "cumulative_exposure_max_pct": 0.01}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(0.0, stop_pct=0.01, style="D1", generation=204)

    closes = [r for r in requests if r.get("position") == 1]
    assert len(closes) == 1, \
        "la fermeture doit partir malgré une exposition cumulée très au-dessus du plafond"

    # ... alors qu'une OUVERTURE dans le même état serait bien refusée.
    requests.clear()
    conn.send_order(1.0, stop_pct=0.01, style="H1", generation=176, risk_pct_override=0.02)
    assert requests == [], "aucune ouverture ne doit partir tant que le plafond est dépassé"


def test_mt5_connector_cumulative_exposure_refuses_when_risk_is_not_measurable(tmp_path, monkeypatch):
    """Un plafond qu'on ne peut pas MESURER ne garantit rien. Si une
    position ouverte n'a aucun stop, sa perte maximale n'est pas bornée :
    la compter comme un risque nul laisserait passer des ouvertures sous un
    plafond faux. Le garde-fou doit refuser explicitement, jamais supposer
    zéro."""
    monkeypatch.chdir(tmp_path)
    from src.mt5_connector import MT5Connector, _worst_case_loss

    assert _worst_case_loss(1000.0, 0.0, 1.0, 100.0) is None, "sans stop -> risque NON borné, pas 0"
    assert _worst_case_loss(1000.0, 990.0, 1.0, 100.0) == 1000.0

    requests, positions = [], []
    fake_mt5 = _make_fake_mt5_accumulating(100000.0, 1000.0, 100.0, requests, positions)
    positions.append(types.SimpleNamespace(
        ticket=1, type=0, volume=0.1, symbol="XAUUSD", comment="D1 gen:204",
        price_open=1000.0, sl=0.0, profit=0.0))   # AUCUN stop

    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False,
                     "allow_real_account": False, "cumulative_exposure_enabled": True,
                     "cumulative_exposure_max_pct": 0.04}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    conn.send_order(1.0, stop_pct=0.01, style="H1", generation=176, risk_pct_override=0.02)
    assert requests == [], \
        "position sans stop -> exposition non mesurable -> l'ouverture doit être refusée"

    # Désactivé, le même cas repasse : ce refus vient bien du plafond, et
    # n'ajoute aucune restriction à qui ne l'a pas activé.
    cfg["live"]["cumulative_exposure_enabled"] = False
    conn2 = MT5Connector(cfg)
    conn2._mt5 = fake_mt5
    conn2.send_order(1.0, stop_pct=0.01, style="H1", generation=176, risk_pct_override=0.02)
    assert len(requests) == 1, "plafond désactivé -> comportement d'origine strictement inchangé"


def test_mt5_connector_get_open_positions_by_style_maps_only_recognized_tags(tmp_path, monkeypatch):
    """COORDINATION INTER-STYLES (19/09) : la primitive de lecture qui
    alimente l'arbitrage doit (1) associer CHAQUE position à SON style via
    son tag de comment, (2) rendre la direction exploitable (+1 achat / -1
    vente), et (3) IGNORER toute position dont le tag n'est pas un style
    reconnu (ancien format "opened_by_agent", style retiré du pool...) --
    sans jamais envoyer le moindre ordre, c'est une lecture seule."""
    monkeypatch.chdir(tmp_path)
    import types
    from src.mt5_connector import MT5Connector

    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0

    def _fail_order_send(request):
        raise AssertionError("get_open_positions_by_style doit être en LECTURE SEULE")
    fake_mt5.order_send = _fail_order_send

    positions = [
        types.SimpleNamespace(ticket=1, type=0, volume=0.5, symbol="XAUUSD",
                              comment="D1 gen:204", price_open=4300.0, sl=4250.0, profit=12.5),
        types.SimpleNamespace(ticket=2, type=1, volume=0.2, symbol="XAUUSD",
                              comment="H1 gen:176", price_open=4310.0, sl=4330.0, profit=-3.2),
        types.SimpleNamespace(ticket=3, type=0, volume=0.7, symbol="XAUUSD",
                              comment="opened_by_agent", price_open=4264.6, sl=0.0, profit=0.0),
        types.SimpleNamespace(ticket=4, type=0, volume=0.1, symbol="XAUUSD",
                              comment="W1 gen:12", price_open=4290.0, sl=0.0, profit=0.0),
    ]
    fake_mt5.positions_get = lambda symbol=None: positions

    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": True, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    out = conn.get_open_positions_by_style(recognized_styles=["M15", "H1", "H4", "D1", "M30"])

    assert set(out.keys()) == {"D1", "H1"}, \
        "seules les positions taguées d'un style RECONNU doivent apparaître (ni orpheline, ni W1 hors pool)"
    assert out["D1"]["direction"] == 1 and out["D1"]["ticket"] == 1
    assert out["H1"]["direction"] == -1 and out["H1"]["ticket"] == 2
    assert out["D1"]["volume"] == 0.5
    assert out["D1"]["profit"] == 12.5 and out["H1"]["profit"] == -3.2
    assert out["D1"]["sl"] == 4250.0 and out["H1"]["sl"] == 4330.0
    assert out["D1"]["opened_by_generation"] == 204 and out["H1"]["opened_by_generation"] == 176

    assert conn.get_open_positions_by_style(recognized_styles=[]) == {}, \
        "aucun style reconnu -> aucune position remontée, jamais d'erreur"

    fake_mt5.positions_get = lambda symbol=None: None  # compte à plat (MT5 renvoie None)
    assert conn.get_open_positions_by_style(recognized_styles=["D1"]) == {}


def test_mt5_connector_close_orphan_positions_respects_dry_run(tmp_path, monkeypatch):
    """close_orphan_positions reste un ordre RÉEL envoyé à MT5 -- doit
    respecter le MÊME garde-fou que send_order (jamais d'ordre réel en
    dry_run, ou sur un compte non confirmé démo sans allow_real_account),
    jamais le contourner sous prétexte que c'est une migration."""
    monkeypatch.chdir(tmp_path)
    import types
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009

    class DemoAccount:
        trade_mode = 0
    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=4300.0, ask=4300.5)

    pos_orphan = types.SimpleNamespace(ticket=999, type=fake_mt5.ORDER_TYPE_BUY, volume=0.73,
                                        symbol="XAUUSD", comment="opened_by_agent", profit=-183.23)
    fake_mt5.positions_get = lambda symbol=None: [pos_orphan]

    def fake_order_send(request):
        requests.append(request)
        return types.SimpleNamespace(retcode=10009)
    fake_mt5.order_send = fake_order_send

    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": True, "allow_real_account": False}}
    conn = MT5Connector(cfg)
    conn._mt5 = fake_mt5

    closed = conn.close_orphan_positions(recognized_styles=["D1", "M15"])

    assert requests == [], "dry_run actif -- aucun ordre réel ne doit jamais partir"
    assert closed == [], "rien de réellement fermé en dry_run, la liste retournée doit rester vide"


def test_mt5_connector_close_orphan_positions_does_not_declare_success_on_rejected_order(tmp_path, monkeypatch):
    """Bug constaté en conditions réelles le 18/09 (marché fermé, ticket
    21846536) : `order_send` ne lève JAMAIS d'exception sur un ordre
    refusé (ici retcode=10018 'Market closed') -- close_orphan_positions
    envoyait bien la tentative, mais loggait "fermée" et l'ajoutait à la
    liste retournée (qui déclenche l'alerte ntfy de succès) SANS jamais
    vérifier que MT5 avait réellement exécuté l'ordre. Résultat : le log
    et l'alerte annonçaient un succès alors que la position restait
    ouverte sur le compte réel. Aligné ici sur le même standard que
    send_order (qui vérifie déjà retcode == TRADE_RETCODE_DONE) : un rejet
    ne doit produire NI un log de succès NI une entrée dans la liste
    retournée -- la position doit rester "non reconnue" pour qu'une
    tentative future (prochain redémarrage) puisse la retraiter."""
    monkeypatch.chdir(tmp_path)
    import types
    from unittest.mock import patch
    from src.mt5_connector import MT5Connector

    requests = []
    fake_mt5 = types.SimpleNamespace()
    fake_mt5.ACCOUNT_TRADE_MODE_DEMO = 0
    fake_mt5.TRADE_ACTION_DEAL = 1
    fake_mt5.ORDER_TYPE_BUY = 0
    fake_mt5.ORDER_TYPE_SELL = 1
    fake_mt5.ORDER_FILLING_FOK = 0
    fake_mt5.ORDER_FILLING_IOC = 1
    fake_mt5.ORDER_FILLING_RETURN = 2
    fake_mt5.TRADE_RETCODE_DONE = 10009  # succès -- volontairement PAS ce que renvoie order_send ici

    class DemoAccount:
        trade_mode = 0
    fake_mt5.account_info = lambda: DemoAccount()
    fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(filling_mode=0)
    fake_mt5.symbol_info_tick = lambda symbol: types.SimpleNamespace(bid=4300.0, ask=4300.5)

    pos_orphan = types.SimpleNamespace(ticket=21846536, type=fake_mt5.ORDER_TYPE_BUY, volume=0.73,
                                        symbol="XAUUSD", comment="opened_by_agent", profit=-94.17)
    fake_mt5.positions_get = lambda symbol=None: [pos_orphan]

    def fake_order_send(request):
        requests.append(request)
        # Rejet réel constaté : marché fermé -- pas d'exception, juste un
        # retcode d'échec dans le résultat.
        return types.SimpleNamespace(retcode=10018, comment="Market closed")
    fake_mt5.order_send = fake_order_send

    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": False, "allow_real_account": False},
           "notifications": {"enabled": True, "channel": "discord", "webhook_url": "https://example.invalid/hook"}}

    alert_calls = []

    def fake_send_alert(cfg, subject, message):
        alert_calls.append((subject, message))

    with patch("src.notifier.send_alert", side_effect=fake_send_alert):
        conn = MT5Connector(cfg)
        conn._mt5 = fake_mt5
        closed = conn.close_orphan_positions(recognized_styles=["D1", "M15", "H1", "H4", "M30"])

    assert len(requests) == 1, "la tentative de fermeture doit bien être envoyée à MT5"
    assert requests[0]["position"] == 21846536

    assert closed == [], ("un ordre REFUSÉ ne doit JAMAIS être déclaré comme fermé -- la position doit "
                           "rester traitable à la prochaine tentative")

    assert len(alert_calls) == 1, "une alerte doit être envoyée, mais UNE SEULE, et ce doit être un échec"
    assert "échec" in alert_calls[0][0].lower(), "l'alerte doit annoncer un échec, jamais un succès de fermeture"
    assert "fermée(s)" not in alert_calls[0][0], "aucune alerte de succès ne doit partir sur un ordre rejeté"


def test_account_guard_halts_on_drawdown_and_stays_halted(tmp_path, monkeypatch):
    """Répond directement à la demande d'un coupe-circuit au niveau du
    compte : dès que l'équité réelle chute de plus que le seuil configuré
    depuis son pic, tout ordre doit être bloqué -- et reste bloqué même si
    l'équité remonte ensuite, tant que reset() n'est pas appelé
    explicitement (revue humaine), exactement le comportement voulu d'un
    coupe-circuit (ni l'agent ni le marché ne peuvent le lever eux-mêmes)."""
    monkeypatch.chdir(tmp_path)
    import src.account_guard as ag

    class FakeConnector:
        def __init__(self):
            self.equity_sequence = []
        def get_account_equity(self):
            return self.equity_sequence.pop(0)

    cfg = {"live": {"symbol": "XAUUSD", "max_account_drawdown_pct": 0.15},
           "notifications": {"enabled": False}}
    conn = FakeConnector()

    conn.equity_sequence = [10000.0]
    assert ag.check(conn, cfg) is True  # premier appel : établit le pic
    assert ag.is_halted() is False

    conn.equity_sequence = [9500.0]  # -5%, sous le seuil de 15%
    assert ag.check(conn, cfg) is True

    conn.equity_sequence = [8400.0]  # -16%, au-delà du seuil
    assert ag.check(conn, cfg) is False
    assert ag.is_halted() is True

    conn.equity_sequence = [10000.0]  # l'équité remonte...
    assert ag.check(conn, cfg) is False, \
        "doit rester bloqué malgré une remontée, sans reset() explicite (revue humaine requise)"

    ag.reset()
    conn.equity_sequence = [10000.0]
    assert ag.check(conn, cfg) is True
    assert ag.is_halted() is False


def test_account_guard_disabled_without_threshold(tmp_path, monkeypatch):
    """Sans seuil configuré (max_account_drawdown_pct absent ou 0), le
    coupe-circuit ne doit jamais bloquer -- comportement d'origine
    inchangé pour qui ne l'active pas explicitement."""
    monkeypatch.chdir(tmp_path)
    import src.account_guard as ag

    class FakeConnector:
        def get_account_equity(self):
            return 1.0  # équité catastrophique -- ne doit quand même jamais bloquer, seuil désactivé

    cfg = {"live": {"symbol": "XAUUSD"}}
    assert ag.check(FakeConnector(), cfg) is True


def test_account_guard_total_drawdown_static_vs_trailing(tmp_path, monkeypatch):
    """live.total_drawdown_mode distingue deux references pour le drawdown
    total : "trailing" (par defaut, comportement d'origine -- pic
    historique, monte avec chaque nouveau sommet) vs "static" (reference
    FIGEE a la toute premiere equite observee, ex: capital initial d'un
    challenge prop firm 2-Step). Meme trajectoire d'equite (10000 -> 12000
    -> 10500), les deux modes doivent donner un verdict DIFFERENT : en
    trailing, -12.5% depuis le pic de 12000 declenche un seuil a 10% ; en
    static, 10500 > 10000 (capital initial) -- aucun drawdown du tout."""
    monkeypatch.chdir(tmp_path)
    import src.account_guard as ag

    class FakeConnector:
        def __init__(self):
            self.equity_sequence = []
        def get_account_equity(self):
            return self.equity_sequence.pop(0)

    base_cfg = {"live": {"symbol": "XAUUSD", "max_account_drawdown_pct": 0.10},
                "notifications": {"enabled": False}}

    # --- mode trailing (defaut) ---
    conn = FakeConnector()
    cfg_trailing = {**base_cfg, "live": {**base_cfg["live"], "total_drawdown_mode": "trailing"}}
    conn.equity_sequence = [10000.0]
    assert ag.check(conn, cfg_trailing) is True
    conn.equity_sequence = [12000.0]
    assert ag.check(conn, cfg_trailing) is True  # nouveau pic
    conn.equity_sequence = [10500.0]
    assert ag.check(conn, cfg_trailing) is False, \
        "trailing : -12.5% depuis le pic de 12000 doit depasser le seuil de 10%"
    assert ag.is_halted() is True
    ag.reset()

    # --- mode static ---
    conn2 = FakeConnector()
    cfg_static = {**base_cfg, "live": {**base_cfg["live"], "total_drawdown_mode": "static"}}
    conn2.equity_sequence = [10000.0]
    assert ag.check(conn2, cfg_static) is True  # fige la reference a 10000
    conn2.equity_sequence = [12000.0]
    assert ag.check(conn2, cfg_static) is True
    conn2.equity_sequence = [10500.0]
    assert ag.check(conn2, cfg_static) is True, \
        "static : 10500 > 10000 (capital initial) -- aucun drawdown, ne doit JAMAIS bloquer ici"
    assert ag.is_halted() is False


def test_account_guard_daily_loss_triggers_and_resets_at_boundary(tmp_path, monkeypatch):
    """Perte quotidienne (live.daily_loss_enabled/daily_loss_max_pct) :
    reference reinitialisee a chaque passage de l'heure de reset LOCALE de
    la firme (voir src/risk_profile.py::current_reset_boundary_utc).
    Verifie (1) qu'une perte >= seuil DANS la meme journee declenche, et
    (2) qu'apres reset() ET passage a une NOUVELLE journee, une equite plus
    basse ne redeclenche pas immediatement puisque la reference du jour
    repart de l'equite courante -- exactement le comportement d'un vrai
    reset quotidien chez un broker/prop firm."""
    monkeypatch.chdir(tmp_path)
    import src.account_guard as ag
    from datetime import datetime, timezone

    class _FrozenDatetime:
        _now = None
        @classmethod
        def now(cls, tz=None):
            return cls._now

    monkeypatch.setattr(ag, "datetime", _FrozenDatetime)

    class FakeConnector:
        def __init__(self):
            self.equity_sequence = []
        def get_account_equity(self):
            return self.equity_sequence.pop(0)

    cfg = {"live": {"symbol": "XAUUSD", "daily_loss_enabled": True, "daily_loss_max_pct": 0.05,
                     "daily_loss_reset_time_local": "00:00", "daily_loss_reset_timezone": "UTC"},
           "notifications": {"enabled": False}}
    conn = FakeConnector()

    # Jour 1, 10h UTC : premiere lecture -- fixe la reference du jour a 10000.
    _FrozenDatetime._now = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    conn.equity_sequence = [10000.0]
    assert ag.check(conn, cfg) is True

    # Jour 1, 14h UTC : -6% depuis la reference du jour -- au-dela du seuil de 5%.
    _FrozenDatetime._now = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
    conn.equity_sequence = [9400.0]
    assert ag.check(conn, cfg) is False, "perte de 6% dans la journee doit depasser le seuil de 5%"
    assert ag.is_halted() is True

    ag.reset()

    # Jour 2 (apres le reset de minuit UTC), memes 9400 -- la reference du
    # jour repart de l'equite COURANTE (9400), donc plus de drawdown du
    # tout au meme instant -- ne doit PAS redeclencher immediatement.
    _FrozenDatetime._now = datetime(2026, 1, 16, 1, 0, tzinfo=timezone.utc)
    conn.equity_sequence = [9400.0]
    assert ag.check(conn, cfg) is True, (
        "nouvelle journee : la reference repart de l'equite courante, "
        "ne doit pas redeclencher sur une equite deja basse mais stable"
    )
    assert ag.is_halted() is False


def test_account_guard_equity_unreadable_blocks_cycle_without_persistent_halt(tmp_path, monkeypatch):
    """CORRECTIF FAIL-SAFE (19/09, audit institutionnel) : une equite
    illisible (connexion MT5 perturbee) doit bloquer LE CYCLE par precaution
    (return False), MAIS sans halt PERSISTANT -- contrairement a un vrai
    depassement de seuil, aucun reset() humain ne doit etre necessaire pour
    qu'un prochain appel reussisse normalement des que l'equite redevient
    lisible (comportement attendu pour un simple blip transitoire, pas un
    probleme structurel)."""
    monkeypatch.chdir(tmp_path)
    import src.account_guard as ag

    class FakeConnector:
        def __init__(self):
            self.equity_sequence = []
        def get_account_equity(self):
            return self.equity_sequence.pop(0)

    cfg = {"live": {"symbol": "XAUUSD", "max_account_drawdown_pct": 0.15},
           "notifications": {"enabled": False}}
    conn = FakeConnector()

    conn.equity_sequence = [10000.0]
    assert ag.check(conn, cfg) is True

    conn.equity_sequence = [None]  # connexion MT5 perturbee -- equite illisible
    assert ag.check(conn, cfg) is False, "equite illisible doit bloquer le cycle par precaution"
    assert ag.is_halted() is False, "un blip transitoire ne doit JAMAIS declencher un halt persistant"

    conn.equity_sequence = [9700.0]  # -3%, sous le seuil -- l'equite redevient lisible
    assert ag.check(conn, cfg) is True, "un prochain appel reussi ne doit pas exiger de reset() humain"


def test_account_guard_daily_loss_auto_resumes_next_day_without_manual_reset(tmp_path, monkeypatch):
    """AUTO-REPRISE (19/09, audit institutionnel item 1 -- "bloque... jusqu'au
    lendemain") : contrairement au drawdown total (reset() humain exige),
    la cause "perte quotidienne" doit se lever TOUTE SEULE des qu'une
    nouvelle journee de trading commence, SANS appel explicite a reset()."""
    monkeypatch.chdir(tmp_path)
    import src.account_guard as ag
    from datetime import datetime, timezone

    class _FrozenDatetime:
        _now = None
        @classmethod
        def now(cls, tz=None):
            return cls._now

    monkeypatch.setattr(ag, "datetime", _FrozenDatetime)

    class FakeConnector:
        def __init__(self):
            self.equity_sequence = []
        def get_account_equity(self):
            return self.equity_sequence.pop(0)

    cfg = {"live": {"symbol": "XAUUSD", "daily_loss_enabled": True, "daily_loss_max_pct": 0.05,
                     "daily_loss_reset_time_local": "00:00", "daily_loss_reset_timezone": "UTC"},
           "notifications": {"enabled": False}}
    conn = FakeConnector()

    _FrozenDatetime._now = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    conn.equity_sequence = [10000.0]
    assert ag.check(conn, cfg) is True

    _FrozenDatetime._now = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
    conn.equity_sequence = [9400.0]  # -6%, au-dela du seuil de 5%
    assert ag.check(conn, cfg) is False
    assert ag.is_halted() is True

    # SANS ag.reset() : un appel LE MEME JOUR doit rester bloque.
    _FrozenDatetime._now = datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc)
    conn.equity_sequence = [9800.0]
    assert ag.check(conn, cfg) is False, "meme journee : doit rester bloque sans reset() explicite"

    # NOUVELLE JOURNEE (apres minuit UTC) : leve automatiquement, sans reset().
    _FrozenDatetime._now = datetime(2026, 1, 16, 1, 0, tzinfo=timezone.utc)
    conn.equity_sequence = [9200.0]
    assert ag.check(conn, cfg) is True, "nouvelle journee : doit reprendre automatiquement sans reset() humain"
    assert ag.is_halted() is False


def test_account_guard_total_drawdown_never_auto_resumes(tmp_path, monkeypatch):
    """La cause "drawdown total" ne doit JAMAIS beneficier de la reprise
    automatique -- meme apres le passage a une nouvelle journee, elle reste
    bloquee tant que reset() n'est pas appele explicitement (probleme
    structurel, pas une notion de "journee")."""
    monkeypatch.chdir(tmp_path)
    import src.account_guard as ag
    from datetime import datetime, timezone

    class _FrozenDatetime:
        _now = None
        @classmethod
        def now(cls, tz=None):
            return cls._now

    monkeypatch.setattr(ag, "datetime", _FrozenDatetime)

    class FakeConnector:
        def __init__(self):
            self.equity_sequence = []
        def get_account_equity(self):
            return self.equity_sequence.pop(0)

    cfg = {"live": {"symbol": "XAUUSD", "max_account_drawdown_pct": 0.15,
                     "daily_loss_enabled": True, "daily_loss_max_pct": 0.05,
                     "daily_loss_reset_time_local": "00:00", "daily_loss_reset_timezone": "UTC"},
           "notifications": {"enabled": False}}
    conn = FakeConnector()

    _FrozenDatetime._now = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    conn.equity_sequence = [10000.0]
    assert ag.check(conn, cfg) is True

    _FrozenDatetime._now = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
    conn.equity_sequence = [8000.0]  # -20%, depasse le seuil de drawdown TOTAL (15%)
    assert ag.check(conn, cfg) is False
    assert ag.is_halted() is True

    _FrozenDatetime._now = datetime(2026, 1, 16, 1, 0, tzinfo=timezone.utc)
    conn.equity_sequence = [8500.0]
    assert ag.check(conn, cfg) is False, "drawdown total : ne doit JAMAIS reprendre automatiquement"
    assert ag.is_halted() is True


def test_reset_boundary_utc_handles_dst_winter_and_summer():
    """current_reset_boundary_utc (src/risk_profile.py) : l'heure de reset
    est stockee en heure LOCALE de la firme (ex: 00:00 Europe/Prague pour
    FTMO), la conversion UTC doit etre CORRECTE des deux cotes du
    changement d'heure, sans ajustement manuel -- zoneinfo applique le bon
    decalage pour CHAQUE date. Verifie une date d'hiver (CET, UTC+1) et une
    date d'ete (CEST, UTC+2)."""
    from datetime import datetime, timezone
    from src.risk_profile import current_reset_boundary_utc

    # Hiver : 15 janvier 2026, 10h UTC -> 11h locale Prague (CET, UTC+1).
    # Le dernier 00:00 Prague est le 15/01 00:00 Prague = 14/01 23:00 UTC.
    winter_now = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    winter_boundary = current_reset_boundary_utc(winter_now, "00:00", "Europe/Prague")
    assert winter_boundary == datetime(2026, 1, 14, 23, 0, tzinfo=timezone.utc), \
        f"hiver (UTC+1) : attendu 14/01 23:00 UTC, obtenu {winter_boundary}"

    # Ete : 15 juillet 2026, 10h UTC -> 12h locale Prague (CEST, UTC+2).
    # Le dernier 00:00 Prague est le 15/07 00:00 Prague = 14/07 22:00 UTC.
    summer_now = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
    summer_boundary = current_reset_boundary_utc(summer_now, "00:00", "Europe/Prague")
    assert summer_boundary == datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc), \
        f"ete (UTC+2) : attendu 14/07 22:00 UTC, obtenu {summer_boundary}"

    # Le decalage horaire doit bien DIFFERER entre les deux (preuve que
    # zoneinfo applique reellement hiver/ete, pas un offset fige).
    winter_offset = winter_now - winter_boundary
    summer_offset = summer_now - summer_boundary
    assert winter_offset != summer_offset


def test_apply_risk_profile_merges_into_live_config():
    """apply_risk_profile (src/risk_profile.py) doit ALIMENTER cfg["live"]
    avec les seuils du profil FTMO 2-Step reel (pas une structure separee)
    -- et ne RIEN changer si live.risk_profile est absent (comportement
    d'origine du projet, aucune regression pour qui n'utilise pas cette
    fonctionnalite)."""
    from src.risk_profile import apply_risk_profile

    cfg_no_profile = {"live": {"max_risk_pct_per_trade": 0.02, "max_account_drawdown_pct": 0.15}}
    result = apply_risk_profile(cfg_no_profile)
    assert result["live"]["max_risk_pct_per_trade"] == 0.02, "sans profil : rien ne doit changer"
    assert "daily_loss_enabled" not in result["live"]
    assert "conflict_resolution" not in result["live"]

    cfg_ftmo = {"live": {"risk_profile": "ftmo_2step", "max_risk_pct_per_trade": 0.02}}
    result = apply_risk_profile(cfg_ftmo)
    assert result["live"]["max_risk_pct_per_trade"] == 0.01
    assert result["live"]["max_account_drawdown_pct"] == 0.10
    assert result["live"]["total_drawdown_mode"] == "static"
    assert result["live"]["daily_loss_enabled"] is True
    assert result["live"]["daily_loss_max_pct"] == 0.05
    assert result["live"]["daily_loss_reset_timezone"] == "Europe/Prague"
    # Hedging non universellement interdit chez les prop firms (FTMO
    # l'autoriserait selon une source) -- posture prudente par défaut tant
    # que ce n'est pas vérifié pour ce profil précis, éditable au besoin.
    assert result["live"]["conflict_resolution"] == "disabled"
    assert result["live"]["cumulative_exposure_enabled"] is True
    assert result["live"]["cumulative_exposure_max_pct"] == 0.025

    cfg_default = {"live": {"risk_profile": "default"}}
    result = apply_risk_profile(cfg_default)
    assert result["live"]["conflict_resolution"] == "temporal_hierarchy", \
        "le profil démo/default active la coordination par hiérarchie temporelle par défaut (17/09, " \
        "remplace l'ancien priority_by_score) pour un comportement plus cohérent"
    # Le profil qui active le budget DYNAMIQUE (option B) doit aussi
    # plafonner l'exposition cumulée : l'option B peut structurellement
    # dépasser max_risk_pct_per_trade, laisser le plafond désactivé ICI
    # serait incohérent.
    assert result["live"]["cumulative_exposure_enabled"] is True
    assert result["live"]["cumulative_exposure_max_pct"] == 0.04


def test_risk_guard_anomaly_scale_normal_market_no_reduction(tmp_path, monkeypatch):
    """Cas nominal : un marché "normal" (bruit gaussien homogène, la
    dernière bougie n'est pas différente statistiquement des précédentes)
    ne doit déclencher AUCUNE réduction d'exposition -- `risk_guard.py`
    est un filet de sécurité INDÉPENDANT qui ne doit intervenir que sur une
    vraie anomalie, jamais par défaut."""
    monkeypatch.chdir(tmp_path)
    import pandas as pd
    from src.risk_guard import anomaly_scale

    rng = np.random.default_rng(42)
    returns = rng.normal(loc=0.0002, scale=0.001, size=250)
    closes = np.concatenate([[100.0], 100.0 * np.cumprod(1 + returns)])
    df = pd.DataFrame({"close": closes})

    scale, info = anomaly_scale(df, lookback=200, z_threshold=4.0)
    assert scale == 1.0, f"marché normal : aucune réduction attendue, obtenu scale={scale} ({info})"
    assert info["last_return_z"] <= 4.0
    assert info["last_vol_z"] <= 4.0


def test_risk_guard_anomaly_scale_triggers_on_extreme_move(tmp_path, monkeypatch):
    """Un mouvement de prix extrême sur la DERNIÈRE bougie (très loin de
    tout ce qui a été vu récemment) doit couper l'exposition à zéro --
    c'est la raison d'être de ce filet de sécurité : réagir à une situation
    inédite que le réseau appris pourrait, lui, ne pas reconnaître comme
    anormale."""
    monkeypatch.chdir(tmp_path)
    import pandas as pd
    from src.risk_guard import anomaly_scale

    rng = np.random.default_rng(7)
    returns = list(rng.normal(loc=0.0, scale=0.0008, size=200))
    returns.append(0.15)  # +15% sur une seule bougie -- le bruit habituel est ~0.08%
    closes = [100.0]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    df = pd.DataFrame({"close": closes})

    scale, info = anomaly_scale(df, lookback=200, z_threshold=4.0)
    assert scale == 0.0, f"un saut de +15% sur un bruit de ~0.08% doit couper l'exposition à zéro, obtenu {scale}"
    assert info["last_return_z"] > 4.0


def test_risk_guard_anomaly_scale_linear_decay_at_threshold_boundaries(tmp_path, monkeypatch):
    """Vérifie la formule de décroissance documentée dans le docstring de
    `anomaly_scale` : scale=1.0 PILE au seuil, décroît LINÉAIREMENT jusqu'à
    0.0 à exactement 2x le seuil, puis reste plafonné à 0.0 au-delà --
    jamais de coupure brutale, jamais de valeur hors [0, 1].

    Construction : un historique où TOUS les rendements (fond + dernier)
    sont POSITIFS. Dans ce cas précis, le z-score de rendement et le
    z-score de volatilité deviennent mathématiquement identiques (la
    valeur absolue d'un nombre positif est lui-même), ce qui permet de
    piloter `worst_z` à une valeur EXACTE plutôt que de deviner un scénario
    au hasard -- indispensable pour tester une valeur pile à la frontière
    du seuil, pas juste "loin au-dessus" ou "loin en-dessous"."""
    monkeypatch.chdir(tmp_path)
    import pandas as pd
    from src.risk_guard import anomaly_scale

    z_threshold = 4.0
    lookback = 20
    # Fond VARIÉ (pas une valeur unique répétée) mais entièrement positif,
    # de longueur lookback-1=19 -- exactement la fenêtre utilisée en
    # interne par la fonction (`returns[-lookback:-1]`).
    background = np.tile([0.0010, 0.0015, 0.0008, 0.0020, 0.0012], 4)[:lookback - 1]
    bg_mean, bg_std = background.mean(), background.std()

    for target_z, expected_scale in [
        (0.5, 1.0),   # bien en dessous du seuil -- aucune réduction
        (4.0, 1.0),   # PILE au seuil -- toujours aucune réduction (comparaison <=)
        (6.0, 0.5),   # à mi-chemin entre le seuil et 2x le seuil -- décroissance linéaire
        (8.0, 0.0),   # PILE à 2x le seuil -- exposition coupée à zéro
        (20.0, 0.0),  # bien au-delà -- reste plafonné à zéro, jamais négatif
    ]:
        last_return = bg_mean + target_z * bg_std
        returns = np.concatenate([[bg_mean], background, [last_return]])
        closes = np.concatenate([[100.0], 100.0 * np.cumprod(1 + returns)])
        df = pd.DataFrame({"close": closes})

        scale, info = anomaly_scale(df, lookback=lookback, z_threshold=z_threshold)
        # Tolérance 1e-4 (pas 1e-6) : l'aller-retour prix -> rendement
        # (np.diff/np.cumprod) introduit une dérive flottante de l'ordre de
        # 1e-5 sur le z-score reconstruit, largement négligeable devant la
        # précision qu'on cherche réellement à vérifier ici (la FORME de la
        # décroissance linéaire, pas la 6e décimale).
        assert abs(scale - expected_scale) < 1e-4, (
            f"target_z={target_z} : attendu scale={expected_scale}, obtenu {scale} (info={info})"
        )


def test_risk_guard_anomaly_scale_handles_empty_or_insufficient_history(tmp_path, monkeypatch):
    """Ne doit JAMAIS planter sur un historique vide ou trop court pour être
    évalué statistiquement -- retombe sur scale=1.0 (pas assez de recul
    pour juger, donc aucune réduction) plutôt que de lever une exception
    qui interromprait toute la boucle de décision live."""
    monkeypatch.chdir(tmp_path)
    import pandas as pd
    from src.risk_guard import anomaly_scale

    # DataFrame complètement vide (colonne présente, 0 ligne)
    scale, info = anomaly_scale(pd.DataFrame({"close": []}), lookback=200)
    assert scale == 1.0
    assert "reason" in info

    # historique bien trop court pour lookback=200 (quelques bougies seulement)
    scale, info = anomaly_scale(pd.DataFrame({"close": [100.0, 100.5, 99.8, 101.2]}), lookback=200)
    assert scale == 1.0
    assert "reason" in info

    # un seul point -- ne doit pas non plus planter
    scale, info = anomaly_scale(pd.DataFrame({"close": [100.0]}), lookback=200)
    assert scale == 1.0
    assert "reason" in info


def test_risk_guard_anomaly_scale_handles_missing_close_column(tmp_path, monkeypatch, caplog):
    """Correctif du 15/09 : un DataFrame SANS colonne 'close' (appelant
    malformé) levait une KeyError immédiate, un vrai trou de robustesse
    trouvé en écrivant les tests ci-dessus -- ce filet de sécurité ne doit
    jamais lui-même devenir une source de panne pour la boucle de décision
    live. Retombe désormais sur le même scale=1.0 neutre qu'un historique
    insuffisant, avec un avertissement journalisé plutôt qu'un plantage
    silencieux ou bruyant."""
    monkeypatch.chdir(tmp_path)
    import logging
    import pandas as pd
    from src.risk_guard import anomaly_scale

    with caplog.at_level(logging.WARNING, logger="risk_guard"):
        scale, info = anomaly_scale(pd.DataFrame({"open": [100.0, 101.0, 99.5]}), lookback=200)

    assert scale == 1.0
    assert "close" in info["reason"]
    assert any("close" in rec.message for rec in caplog.records), \
        "un avertissement journalisé est attendu, pas un échec silencieux"


def test_notifier_dispatches_to_configured_channel(tmp_path, monkeypatch):
    """Vérifie que send_alert() appelle bien le bon transport (discord ici)
    avec le message attendu -- une faute de frappe dans un nom de clé de
    config serait sinon indétectable avant le premier vrai déclenchement."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    from src.notifier import send_alert

    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return types.SimpleNamespace(status_code=200, raise_for_status=lambda: None)

    with patch("requests.post", side_effect=fake_post):
        cfg = {"notifications": {"enabled": True, "channel": "discord",
                                  "webhook_url": "https://example.invalid/hook"}}
        send_alert(cfg, "Sujet de test", "Message de test")

    assert len(calls) == 1
    assert calls[0][0] == "https://example.invalid/hook"
    assert "Sujet de test" in calls[0][1]["json"]["content"]
    assert "Message de test" in calls[0][1]["json"]["content"]


def test_send_ntfy_posts_to_configured_topic_and_server(tmp_path, monkeypatch):
    """Vérifie l'URL/le topic/le titre RÉELLEMENT construits pour ntfy --
    seul canal utilisé en production sur ce projet."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    from src.notifier import send_alert

    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return types.SimpleNamespace(status_code=200, raise_for_status=lambda: None)

    with patch("requests.post", side_effect=fake_post):
        cfg = {"notifications": {"enabled": True, "channel": "ntfy", "ntfy_topic": "mon-topic-secret"}}
        send_alert(cfg, "Sujet", "Corps du message")

    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://ntfy.sh/mon-topic-secret"
    assert kwargs["headers"]["Title"] == "Sujet"
    assert kwargs["data"] == "Corps du message".encode("utf-8")


def test_send_alert_logs_real_failure_instead_of_claiming_success(tmp_path, monkeypatch, caplog):
    """Bug réel trouvé le 22/09 en observant l'absence totale de
    notifications reçues sur plusieurs heures alors que les logs affichaient
    "Alerte envoyée via ntfy" à chaque cycle : ntfy.sh renvoyait en réalité
    un 429 (quota quotidien gratuit dépassé), mais `requests.post` ne lève
    PAS d'exception sur un code d'erreur HTTP -- sans vérification explicite
    du code de statut, l'échec restait invisible. Ce test reproduit
    EXACTEMENT ce scénario (réponse 429) et vérifie qu'un vrai échec est
    maintenant journalisé, pas un faux succès."""
    monkeypatch.chdir(tmp_path)
    import logging
    from unittest.mock import patch
    import requests
    from src.notifier import send_alert

    def fake_post_quota_exceeded(url, **kwargs):
        resp = requests.Response()
        resp.status_code = 429
        return resp

    with patch("requests.post", side_effect=fake_post_quota_exceeded):
        cfg = {"notifications": {"enabled": True, "channel": "ntfy", "ntfy_topic": "x"}}
        with caplog.at_level(logging.ERROR, logger="notifier"):
            send_alert(cfg, "Sujet", "Message")

    assert any("Échec d'envoi" in rec.message for rec in caplog.records), \
        "un code HTTP d'erreur (429) doit produire un VRAI log d'échec, jamais un faux succès silencieux"
    assert not any("Alerte envoyée" in rec.message for rec in caplog.records), \
        "ne doit JAMAIS journaliser un succès quand le serveur a réellement refusé le message"


def test_notifier_disabled_does_not_call_network(tmp_path, monkeypatch):
    """`notifications.enabled: false` (le défaut) ne doit tenter AUCUN appel
    réseau -- juste journaliser."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    from src.notifier import send_alert

    with patch("requests.post") as mock_post:
        send_alert({"notifications": {"enabled": False}}, "Sujet", "Message")
        mock_post.assert_not_called()


def test_send_order_notifies_on_trade_open_dry_run_and_real(tmp_path, monkeypatch):
    """Répond directement à la demande d'être notifié quand le trader ouvre
    un trade -- vérifie que send_order() alerte à l'ouverture, aussi bien en
    dry-run (étiqueté SIMULATION -- indispensable pendant toute la phase de
    validation où aucun ordre réel n'est jamais envoyé) qu'en mode réel
    (étiqueté ORDRE RÉEL), jamais l'un pour l'autre."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    from src.mt5_connector import MT5Connector

    calls = []
    requests_log = []
    fake_mt5 = _make_fake_mt5_with_account(equity=10000.0, bid=2000.0, ask=2000.0,
                                            contract_size=100.0, requests=requests_log)
    cfg = {"live": {"symbol": "XAUUSD", "lot_size": 0.01, "dry_run": True, "allow_real_account": False},
           "notifications": {"enabled": True, "channel": "discord", "webhook_url": "https://example.invalid/hook"}}

    def fake_send_alert(cfg, subject, message):
        calls.append((subject, message))

    with patch("src.notifier.send_alert", side_effect=fake_send_alert):
        conn = MT5Connector(cfg)
        conn._mt5 = fake_mt5
        conn.send_order(1.0, stop_pct=0.01)
        assert len(calls) == 1
        assert "SIMULATION" in calls[0][0]

        calls.clear()
        cfg["live"]["dry_run"] = False
        conn2 = MT5Connector(cfg)
        conn2._mt5 = fake_mt5
        conn2.send_order(1.0, stop_pct=0.01)
        assert len(calls) == 1
        assert "RÉEL" in calls[0][0]


def test_promotion_events_send_notifications(tmp_path, monkeypatch):
    """Répond directement à la demande d'être notifié quand un agent est
    promu en démo : vérifie qu'aucune alerte n'est envoyée tant qu'aucun
    style ne passe la validation, puis qu'une transition vers "éligible"
    déclenche bien les deux alertes (style individuellement éligible à
    l'ensemble, ET champion démo gagnant-unique)."""
    monkeypatch.chdir(tmp_path)
    from unittest.mock import patch
    import src.continuous_trainer as ct

    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1}
    cfg["memory"] = {"db_path": "mem_promo_notif.sqlite", "max_episodes": 500}
    cfg["validation"] = {"min_sharpe_to_go_live": 1.0, "max_drawdown_allowed": 0.20,
                         "min_generations_before_demo": 0}
    cfg["notifications"] = {"enabled": True, "channel": "discord", "webhook_url": "https://example.invalid/hook"}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, _make_data_fn(), ["H1"], env_kwargs)

    def bad_metrics(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": -0.1, "sharpe": -2.0, "max_drawdown": 0.25,
                "win_rate": 0.3, "profit_factor": 0.5, "n_trades": 50}

    def good_metrics(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": 0.2, "sharpe": 1.5, "max_drawdown": 0.05,
                "win_rate": 0.6, "profit_factor": 2.0, "n_trades": 50}

    calls = []

    def fake_send_alert(cfg, subject, message):
        calls.append(subject)

    with patch("src.notifier.send_alert", side_effect=fake_send_alert):
        with patch.object(ct, "evaluate_agent_walkforward", side_effect=bad_metrics):
            trainer.run_one_cycle()
        assert calls == [], "aucun style ne passe encore la validation -> pas d'alerte de promotion"

        with patch.object(ct, "evaluate_agent_walkforward", side_effect=good_metrics):
            trainer.run_one_cycle()
    trainer.close()

    assert any("promu en demo" in c for c in calls), f"alerte de style éligible attendue, obtenu {calls}"
    assert any("nouveau champion demo" in c for c in calls), f"alerte de champion démo attendue, obtenu {calls}"


def test_settings_server_validates_whitelist_and_applies_live(tmp_path, monkeypatch):
    """Répond directement à la demande de pouvoir régler des paramètres
    depuis le tableau de bord : vérifie qu'un réglage AUTORISÉ (voir
    WHITELIST) est appliqué IMMÉDIATEMENT au dictionnaire de config partagé
    (sans redémarrage), qu'un chemin NON autorisé est refusé sans jamais
    être appliqué, et qu'une valeur hors bornes est refusée aussi. Utilise
    un port dynamique (0) pour ne jamais entrer en conflit avec une
    véritable instance déjà en cours sur le port par défaut."""
    monkeypatch.chdir(tmp_path)
    import json
    import urllib.request
    import urllib.error
    from src.settings_server import start_server

    cfg = {"live": {"symbol": "XAUUSD", "dry_run": True, "max_account_drawdown_pct": 0.15,
                     "max_risk_pct_per_trade": 0.02, "risk_guard_z_threshold": 4.0, "poll_seconds": 300},
           "continuous": {"cycle_interval_seconds": 60},
           "notifications": {"enabled": False, "notify_cycle_every_n": 1}}

    server = start_server(cfg, port=0)
    assert server is not None
    try:
        base = f"http://127.0.0.1:{server.server_port}"

        with urllib.request.urlopen(f"{base}/api/settings", timeout=5) as resp:
            data = json.loads(resp.read())
        assert data["settings"]["live.dry_run"] is True
        assert data["settings"]["live.poll_seconds"] == 300

        payload = json.dumps({"live.poll_seconds": 30, "live.dry_run": False}).encode()
        req = urllib.request.Request(f"{base}/api/settings", data=payload, method="POST",
                                       headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        assert result["errors"] == {}
        assert result["applied"] == {"live.poll_seconds": 30, "live.dry_run": False}
        assert cfg["live"]["poll_seconds"] == 30, "doit modifier le dict cfg PARTAGÉ immédiatement"
        assert cfg["live"]["dry_run"] is False

        payload2 = json.dumps({"agent.use_lstm": False}).encode()
        req2 = urllib.request.Request(f"{base}/api/settings", data=payload2, method="POST",
                                        headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req2, timeout=5)
            assert False, "un chemin non whitelisté doit renvoyer un statut d'erreur"
        except urllib.error.HTTPError as e:
            result2 = json.loads(e.read())
        assert "agent.use_lstm" in result2["errors"]
        assert "agent" not in cfg, "un réglage non autorisé ne doit JAMAIS être appliqué, même refusé"

        payload3 = json.dumps({"live.max_account_drawdown_pct": 5.0}).encode()
        req3 = urllib.request.Request(f"{base}/api/settings", data=payload3, method="POST",
                                        headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req3, timeout=5)
            assert False, "une valeur hors bornes doit renvoyer un statut d'erreur"
        except urllib.error.HTTPError as e:
            result3 = json.loads(e.read())
        assert "live.max_account_drawdown_pct" in result3["errors"]
        assert cfg["live"]["max_account_drawdown_pct"] == 0.15, "valeur hors bornes jamais appliquée"
    finally:
        server.shutdown()


def test_settings_server_persists_overrides_across_restart(tmp_path, monkeypatch):
    """Un réglage changé depuis le tableau de bord doit survivre à un
    redémarrage du script (fichier data/settings_overrides.json), pas
    seulement rester en mémoire pour la session en cours."""
    monkeypatch.chdir(tmp_path)
    import json
    import urllib.request
    from src.settings_server import start_server, load_overrides_into

    cfg = {"live": {"poll_seconds": 300}, "continuous": {}, "notifications": {}}
    server = start_server(cfg, port=0)
    assert server is not None
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        payload = json.dumps({"live.poll_seconds": 45}).encode()
        req = urllib.request.Request(f"{base}/api/settings", data=payload, method="POST",
                                       headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    finally:
        server.shutdown()

    # nouveau dict "frais" -> simule un redémarrage complet du script
    fresh_cfg = {"live": {"poll_seconds": 300}, "continuous": {}, "notifications": {}}
    load_overrides_into(fresh_cfg)
    assert fresh_cfg["live"]["poll_seconds"] == 45, \
        "le réglage doit être restauré au démarrage depuis data/settings_overrides.json"


def test_dashboard_history_accumulates_and_renders_chart(tmp_path, monkeypatch):
    """Répond directement à la demande de graphique de progression EN
    LIVE dans le tableau de bord (pas juste dans le rapport ponctuel) :
    vérifie que chaque appel à write_training_status ajoute une ligne à
    reports/score_history.jsonl (au lieu d'écraser, contrairement à
    champion_<TF>/meta.json) et que le graphique SVG généré à partir de
    cet historique mentionne bien chaque style suivi."""
    monkeypatch.chdir(tmp_path)
    from src.dashboard import write_training_status, _read_history, _history_chart_svg

    for gen, m15, h1 in [(1, 0.10, -1.20), (2, 0.10, -0.80), (3, 0.25, -0.30)]:
        write_training_status({
            "generation": gen, "best_ever_score": max(m15, h1), "cycles_since_improvement": 0,
            "plateau": False,
            "styles": {"M15": {"score": m15, "generation": gen, "passes_validation": False},
                       "H1": {"score": h1, "generation": gen, "passes_validation": False}},
        })

    history = _read_history()
    assert len(history) == 3, "une ligne par cycle, jamais écrasée"
    assert history[-1]["styles"]["M15"] == 0.25

    svg = _history_chart_svg(history)
    assert "<svg" in svg and "M15" in svg and "H1" in svg


def test_startup_wait_does_not_block_forever_when_only_one_style_eligible(tmp_path, monkeypatch):
    """Reproduit exactement le bug trouvé en usage réel le 14/09 : H1 était
    marqué passes_validation:true (voir _recheck_gate_eligibility) mais
    AUCUN trade n'a jamais été envoyé pendant plus d'1h30, y compris avec
    zéro contention CPU (test --no-train négatif). Cause réelle :
    autonomous_agent.py n'attendait que trainer.has_demo_champion() --
    l'ANCIEN mécanisme à champion unique (models/demo_champion/), qui reste
    bloqué tant que le style au meilleur score BRUT (ici D1) ne passe pas
    LUI-MÊME tous les seuils, même si un AUTRE style (H1) est individuellement
    éligible via l'ensemble multi-styles. La condition de démarrage doit
    aussi vérifier _scan_eligible_styles(cfg), sans quoi la boucle
    d'attente ne se termine jamais alors même que la démo aurait de quoi
    tourner."""
    monkeypatch.chdir(tmp_path)
    import os, json
    import src.continuous_trainer as ct
    from src.demo_trader import _scan_eligible_styles

    cfg = dict(BASE_CFG)
    cfg["data"] = {"timeframe_pool": ["M15", "H1", "H4", "D1", "M30"]}
    cfg["live"] = {"ensemble": True}

    # D1 : meilleur score BRUT du pool, mais échoue la validation (comme en
    # conditions réelles -- drawdown trop élevé) -> le champion démo unique
    # (has_demo_champion) ne sera donc JAMAIS créé.
    os.makedirs(os.path.join("models", "champion_D1"), exist_ok=True)
    with open(os.path.join("models", "champion_D1", "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"score": 4.87, "passes_validation": False, "feature_columns": ["x"]}, f)

    # H1 : score plus faible, mais INDIVIDUELLEMENT éligible (exactement le
    # scénario réel du 14/09).
    from src.trading_env import ENV_VERSION
    h1_dir = os.path.join("models", "champion_H1")
    os.makedirs(h1_dir, exist_ok=True)
    with open(os.path.join(h1_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"score": 1.96, "passes_validation": True, "feature_columns": ["x"],
                    "env_version": ENV_VERSION}, f)
    with open(os.path.join(h1_dir, "norm_stats.json"), "w", encoding="utf-8") as f:
        json.dump({}, f)

    assert not os.path.exists(ct.DEMO_MODEL + ".zip"), "précondition du bug : pas de champion démo unique"
    eligible = _scan_eligible_styles(cfg)
    assert any(e["style"] == "H1" for e in eligible), "H1 doit être détecté éligible par l'ensemble"

    # La condition RÉELLE utilisée dans autonomous_agent.py (voir le fix) :
    # avant le correctif, seule `not has_demo_champion()` était testée (donc
    # toujours True ici -> boucle infinie) ; après, elle doit être False dès
    # qu'un style est éligible même sans champion démo unique.
    has_demo_champion = os.path.exists(ct.DEMO_MODEL + ".zip")
    should_keep_waiting = (not has_demo_champion) and not _scan_eligible_styles(cfg)
    assert should_keep_waiting is False, \
        "ne doit PAS continuer à attendre : H1 est éligible, la démo doit pouvoir démarrer"


def test_write_hourly_report_renders_on_dashboard(tmp_path, monkeypatch):
    """Répond directement à la demande de l'utilisateur ("mets les rapports
    sur le dashboard, plus simple pour moi") : write_hourly_report doit
    persister le dernier rapport compilé et _render_locked() doit l'inclure
    dans le HTML généré (résumé, points clés, prévisions, avis, lien vers
    l'Artifact complet) -- sans dépendre du process d'entraînement pour
    déclencher le rendu, puisqu'il est appelé depuis un script à part."""
    monkeypatch.chdir(tmp_path)
    import time
    from src.dashboard import write_hourly_report, DASHBOARD_PATH

    write_hourly_report({
        "timestamp": time.time(), "generation": 83,
        "headline": "H1 est éligible et pilote la démo depuis 1h, toujours 0 trade.",
        "highlights": ["D1 bat son record (4.875)", "M15 et H4 ont re-élargi leur mutation"],
        "forecast": "Rythme stable, ~20 min/cycle.",
        "verdict": "Rien d'anormal, juste le début de l'historique live pour H1.",
        "artifact_url": "https://claude.ai/code/artifact/exemple",
    })

    assert os.path.isfile(DASHBOARD_PATH)
    with open(DASHBOARD_PATH, encoding="utf-8") as f:
        html = f.read()
    assert "Dernier rapport horaire" in html
    assert "H1 est éligible et pilote la démo" in html
    assert "D1 bat son record" in html
    assert "https://claude.ai/code/artifact/exemple" in html


def test_is_authorized_requires_token_for_non_local_clients():
    """Test unitaire de _is_authorized (voir src/settings_server.py) :
    répond directement à la demande d'accès réseau local (Safari iPhone)
    -- la machine elle-même (127.0.0.1) n'a jamais besoin de jeton, mais un
    appareil distant sans jeton configuré (dashboard.lan_access: false,
    donc aucun jeton à vérifier) doit être refusé plutôt qu'autorisé par
    défaut."""
    from src.settings_server import _is_authorized

    assert _is_authorized("127.0.0.1", "/", "secret123") is True, \
        "la machine elle-même n'a jamais besoin de jeton"
    assert _is_authorized("192.168.1.42", "/", None) is False, \
        "sans jeton configuré (lan_access désactivé), un appareil distant doit être refusé"
    assert _is_authorized("192.168.1.42", "/", "secret123") is False, \
        "un appareil distant sans jeton doit être refusé"
    assert _is_authorized("192.168.1.42", "/?token=wrong", "secret123") is False, \
        "un mauvais jeton doit être refusé"
    assert _is_authorized("192.168.1.42", "/?token=secret123", "secret123") is True, \
        "le bon jeton en query string doit être accepté depuis un appareil distant"


def test_start_server_binds_lan_and_requires_token(tmp_path, monkeypatch):
    """Vérifie que `dashboard.lan_access: true` fait bien écouter le
    serveur au-delà de 127.0.0.1 (0.0.0.0) et qu'un jeton est généré et
    persisté (data/dashboard_token.txt) -- sans dupliquer le test réseau
    distant (voir test_is_authorized_requires_token_for_non_local_clients
    ci-dessus pour la logique d'autorisation elle-même)."""
    monkeypatch.chdir(tmp_path)
    import os
    from src.settings_server import start_server, TOKEN_PATH

    cfg = {"live": {}, "continuous": {}, "notifications": {}, "dashboard": {"lan_access": True}}
    server = start_server(cfg, port=0)
    assert server is not None
    try:
        assert server.server_address[0] == "0.0.0.0", \
            "lan_access: true doit écouter sur toutes les interfaces, pas juste 127.0.0.1"
        assert os.path.exists(TOKEN_PATH), "le jeton doit être persisté sur disque"
        token = open(TOKEN_PATH, encoding="utf-8").read().strip()
        assert len(token) > 10
    finally:
        server.shutdown()


if __name__ == "__main__":
    import tempfile, pathlib
    from conftest import DummyMonkeypatch  # voir tests/conftest.py -- fusion des 3 définitions dupliquées
    test_episodic_memory_created_in_one_thread_used_in_another(pathlib.Path(tempfile.mkdtemp()))
    test_episodic_memory_training_snapshot_excludes_live_episodes(pathlib.Path(tempfile.mkdtemp()))
    test_style_runtime_defers_reload_while_position_open(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_no_gpu_messages_logged(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_progress_callback_logs_during_training(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_agent_chosen_stop_loss_triggers_on_bar_low_discrete(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_agent_chosen_stop_loss_continuous_decoding(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_stop_loss_inactive_when_learn_stop_loss_disabled(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_champion_promotion_archives_versioned_snapshot(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_prune_history_keeps_only_most_recent_snapshots(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_recheck_gate_eligibility_flips_flag_without_new_promotion(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_demo_champion_requires_validation_pass(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_min_generations_before_demo_gate(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_notify_every_cycle_sends_start_and_summary_alerts(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_format_score_delta_shows_percentage_or_absolute()
    test_confidence_marker_flags_scores_backed_by_too_few_trades()
    test_resolve_max_bars_gives_more_history_to_overridden_styles()
    test_resolve_stress_test_per_style_override()
    test_stress_seed_stable_per_style_not_per_cycle()
    test_block_bootstrap_rebases_price_no_teleport()
    test_high_volatility_subset_rebases_price_no_teleport()
    test_stress_test_applied_per_style_in_real_cycle(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_cycle_notification_shows_progress_margin_between_alerts(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_multi_style_pool_trains_in_parallel_with_distinct_features(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_market_hours_switches_max_bars(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_overfitting_plateau_tracking_persists(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_confident_score_discounts_small_samples_never_helps_bad_scores()
    test_lucky_small_sample_score_does_not_block_plateau_detection(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_parallel_candidate_training_matches_sequential_behavior(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_demo_trader_fuses_live_multi_timeframe(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_demo_trader_forwards_agent_chosen_stop_loss(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_walkforward_evaluation_reduces_single_path_luck(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_walkforward_score_weighted_by_trade_count_not_simple_mean(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_continuous_evolution_improves_via_warm_start(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_mt5_connector_blocks_real_account()
    test_mt5_connector_allows_demo_account()
    test_mt5_connector_sizes_position_from_risk_not_fixed_lot(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_mt5_connector_floors_to_min_lot_when_risk_sizing_rounds_to_zero(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_mt5_connector_does_not_reopen_unchanged_position_every_cycle(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_mt5_connector_falls_back_to_notional_equity_without_stop(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_account_guard_halts_on_drawdown_and_stays_halted(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_account_guard_disabled_without_threshold(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_notifier_dispatches_to_configured_channel(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_notifier_disabled_does_not_call_network(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_send_order_notifies_on_trade_open_dry_run_and_real(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_promotion_events_send_notifications(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_settings_server_validates_whitelist_and_applies_live(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_settings_server_persists_overrides_across_restart(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_dashboard_history_accumulates_and_renders_chart(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_startup_wait_does_not_block_forever_when_only_one_style_eligible(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_write_hourly_report_renders_on_dashboard(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_is_authorized_requires_token_for_non_local_clients()
    test_start_server_binds_lan_and_requires_token(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    print("SMOKE TEST autonomous: SUCCESS")
