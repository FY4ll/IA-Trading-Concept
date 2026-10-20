"""LOT 2 (suite), 22/09 : bug réel trouvé en démo réelle -- l'agent décidait
TOUJOURS avec une bougie de retard sur la donnée la plus fraîche récupérée
en direct (voir _StyleRuntime.decide, src/demo_trader.py). Root cause : la
boucle qui avance l'environnement jusqu'au point de décision s'arrêtait à
`len(df) - 2`, une marge que TradingEnv.step() réserve pour le prix de
remplissage de la bougie SUIVANTE (nécessaire en entraînement/backtest,
inutile en live où decide() ne rappelle jamais step() après coup).

Repéré en conditions réelles : une chute de prix de -0.93% sur la toute
dernière bougie H4 récupérée par MT5 était invisible pour l'agent -- une
sonde de probabilités d'action restait identique bit-à-bit avant/après le
mouvement, sur plusieurs heures.

Portée EXACTE du correctif (important, pour ne pas se mentir) : `_get_obs()`
(src/trading_env.py) exclut TOUJOURS la bougie `current_step` elle-même de
la fenêtre technique (`feats = feature_values[current_step-window:
current_step]`, borne haute exclusive) -- ça, le correctif ne le change PAS,
et ce serait incohérent de le faire (l'entraînement suit la même règle : la
bougie en cours de formation n'est jamais vue comme "historique clos"). Ce
que le correctif corrige, c'est que `current_step` pointait inutilement 2
bougies avant la fin des données récupérées au lieu d'1 seule -- il avançait
donc la fenêtre visible d'exactement UNE bougie. La bougie la PLUS récente
(potentiellement encore en formation) reste hors de la fenêtre technique
(feats) par design ; elle n'entre dans l'observation que faiblement, via
`current_context`/la requête mémoire (2 scalaires mem_pnl/mem_drawdown, pas
les features brutes)."""
from __future__ import annotations
import numpy as np

from src.data_loader import generate_synthetic_ohlcv
from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
from src.demo_trader import _StyleRuntime
import src.demo_trader as demo_trader_module


class _RecordingAgent:
    """Faux agent qui n'apprend rien -- capture juste l'observation reçue
    par predict() pour qu'on puisse l'inspecter, et répond toujours 'flat'
    (action=1) pour ne pas déclencher de logique d'ordre annexe."""

    def __init__(self):
        self.last_obs = None

    def predict(self, obs, deterministic=True):
        self.last_obs = np.array(obs, copy=True)
        return 1


def _decide_with_last_row_override(monkeypatch, override_value):
    """Construit un DataFrame réaliste (features techniques + normalisation),
    modifie UNIQUEMENT la valeur de la première feature sur l'AVANT-DERNIÈRE
    bougie récupérée -- celle que le correctif rend désormais visible dans
    la fenêtre de l'agent (`_get_obs()` exclut TOUJOURS la toute dernière
    bougie elle-même de la fenêtre technique, feats=[current_step-window:
    current_step), qu'elle soit encore en formation ou non -- seule sa
    position dans `current_step` change, cohérent avec la sémantique
    d'entraînement de TradingEnv.step() : voir docstring du module) --, et
    retourne l'observation réellement vue par l'agent via
    `_StyleRuntime.decide()` -- le VRAI chemin live, pas une reproduction
    isolée de TradingEnv."""
    window_size = 20
    df_full = generate_synthetic_ohlcv(n_bars=200, seed=1)
    df_full = add_technical_features(df_full)
    _, stats = normalize_features(df_full.copy(), columns=FEATURE_COLUMNS)

    raw_df = df_full.iloc[-(window_size + 40):].reset_index(drop=True).copy()
    target_col = FEATURE_COLUMNS[0]
    raw_df.loc[raw_df.index[-2], target_col] = override_value

    monkeypatch.setattr(demo_trader_module, "_build_live_dataframe", lambda *a, **k: raw_df)

    rt = _StyleRuntime()
    rt.agent = _RecordingAgent()
    rt.stats = stats
    rt.feature_columns = FEATURE_COLUMNS
    rt.mtf_config = {"primary_timeframe": "H1", "context_timeframes": [], "n_bars_context": 500}

    env_kwargs = dict(window_size=window_size, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1,
                       learn_stop_loss=False, atr_stop_loss=False)

    rt.decide(connector=None, fundamental_feed=None, n_bars_needed=window_size + 40,
              memory=None, memory_top_k=0, env_kwargs=env_kwargs)
    return rt.agent.last_obs


def test_decide_observation_reflects_freshest_available_bar(monkeypatch):
    """Coeur du correctif : une valeur radicalement différente sur
    l'AVANT-DERNIÈRE bougie récupérée (la dernière bougie CLÔTURÉE
    disponible) doit changer l'observation réellement passée à l'agent.
    AVANT le correctif, cette bougie était systématiquement exclue de la
    fenêtre (la boucle s'arrêtait 2 bougies trop tôt) -- deux marchés
    différant UNIQUEMENT sur cette bougie produisaient une observation
    strictement identique, quelle que soit l'ampleur du mouvement."""
    obs_calm = _decide_with_last_row_override(monkeypatch, override_value=0.0)
    obs_spike = _decide_with_last_row_override(monkeypatch, override_value=50.0)

    assert not np.allclose(obs_calm, obs_spike), (
        "l'observation ne change pas quand la derniere bougie recuperee change "
        "radicalement -- la decision live ignore la donnee la plus fraiche")
