"""Jeu sous clé (LOT 2, phase 1) : src/data_loader.py::default_lockbox_start,
split_lockbox, et leur câblage dans autonomous_agent.py::make_data_provider.
Fichier DÉDIÉ (pas tests/test_autonomous.py), comme demandé."""
from __future__ import annotations
import numpy as np
import pandas as pd

from src.data_loader import default_lockbox_start, split_lockbox


def _df_with_times(start, periods, freq="1h"):
    times = pd.date_range(start, periods=periods, freq=freq)
    return pd.DataFrame({"time": times, "close": np.arange(periods, dtype=float)})


def test_default_lockbox_start_is_15pct_from_end_rounded_to_month_start():
    df = _df_with_times("2020-01-01", periods=24 * 365 * 10, freq="1h")  # ~10 ans
    result = default_lockbox_start(df)
    assert result.day == 1 and result.hour == 0
    earliest = pd.to_datetime(df["time"]).min()
    latest = pd.to_datetime(df["time"]).max()
    expected_raw = latest - (latest - earliest) * 0.15
    # Le résultat doit tomber dans le MÊME mois que le calcul brut (arrondi
    # au début de CE mois, jamais un mois arbitrairement différent).
    assert (result.year, result.month) == (expected_raw.year, expected_raw.month)


def test_split_lockbox_visible_never_contains_rows_at_or_after_cutoff():
    df = _df_with_times("2023-01-01", periods=5000, freq="1h")
    lockbox_start = pd.Timestamp("2023-06-01")
    visible, lockbox = split_lockbox(df, lockbox_start)
    assert (pd.to_datetime(visible["time"]) < lockbox_start).all()
    assert (pd.to_datetime(lockbox["time"]) >= lockbox_start).all()
    assert len(visible) + len(lockbox) == len(df)


def test_split_lockbox_applies_purge_and_embargo_gap_before_cutoff():
    df = _df_with_times("2023-01-01", periods=5000, freq="1h")
    lockbox_start = pd.Timestamp("2023-06-01")
    visible_no_gap, _ = split_lockbox(df, lockbox_start)
    visible_with_gap, _ = split_lockbox(df, lockbox_start, purge_bars=50, embargo_bars=24)
    assert len(visible_with_gap) == len(visible_no_gap) - 74
    # La dernière bougie visible avec la marge doit être strictement plus
    # ancienne que la dernière bougie visible sans marge.
    assert visible_with_gap["time"].iloc[-1] < visible_no_gap["time"].iloc[-1]


def test_split_lockbox_none_disables_mechanism():
    df = _df_with_times("2023-01-01", periods=1000, freq="1h")
    visible, lockbox = split_lockbox(df, None)
    assert len(visible) == len(df)
    assert len(lockbox) == 0


def test_split_lockbox_gap_never_produces_negative_length():
    df = _df_with_times("2023-01-01", periods=10, freq="1h")
    lockbox_start = pd.Timestamp("2023-01-01 05:00")
    visible, _ = split_lockbox(df, lockbox_start, purge_bars=50, embargo_bars=50)
    assert len(visible) == 0  # jamais d'exception, juste vide


def test_make_data_provider_never_serves_lockbox_rows_for_any_style(tmp_path, monkeypatch):
    """Le test explicitement demandé : le provider ne renvoie aucune ligne
    >= lockbox_start, quel que soit le style."""
    monkeypatch.chdir(tmp_path)
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

    make_csv("XAU_1h_data.csv", 60, 6000, 1)
    make_csv("XAU_4h_data.csv", 240, 1500, 2)
    make_csv("XAU_1d_data.csv", 1440, 400, 3)

    # lockbox_start choisi à 80% de l'historique H1 (250 jours, pas 125) --
    # D1 n'a qu'UNE bougie par jour : il faut assez de jours AVANT la
    # coupure pour dépasser la purge de chauffe des indicateurs glissants
    # (~50 bougies, voir add_technical_features) ET le plancher de sécurité
    # min_usable_bars (voir autonomous_agent.py::get_data) -- sinon le
    # repli "lockbox désactivé pour ce style" s'applique à raison (voir le
    # test dédié à ce repli plus bas), mais ce n'est pas ce que CE test-ci
    # veut vérifier (lockbox normalement actif et respecté en profondeur).
    times_h1 = pd.date_range("2020-01-01", periods=6000, freq="60min")
    lockbox_start = times_h1[int(len(times_h1) * 0.8)]

    cfg_yaml = f"""
data:
  folder: '{folder}'
  timeframe_pool: ["H1", "D1"]
  max_bars: 2000
  max_bars_market_closed: 0
  n_bars_context: 500
  train_ratio: 0.7
  val_ratio: 0.3
  purge_bars: 10
  embargo_hours: 2
  lockbox_start: "{lockbox_start.date()}"
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
fundamental:
  enabled: false
"""
    cfg = yaml.safe_load(cfg_yaml)
    get_data_fn, timeframe_pool = autonomous_agent.make_data_provider(cfg)

    for style in ["H1", "D1"]:
        train_df, val_df, _, _, _ = get_data_fn(style)
        for split_name, split_df in [("train", train_df), ("val", val_df)]:
            assert (pd.to_datetime(split_df["time"]) < lockbox_start).all(), \
                f"style={style} split={split_name} contient des bougies >= lockbox_start"


def test_make_data_provider_default_lockbox_start_when_not_configured(tmp_path, monkeypatch, caplog):
    """Sans data.lockbox_start explicite : calculé automatiquement (15% les
    plus récents de l'historique or, arrondi au début du mois) ET affiché."""
    monkeypatch.chdir(tmp_path)
    import logging
    caplog.set_level(logging.INFO)
    import yaml
    import autonomous_agent

    folder = tmp_path / "kaggle_gold"
    folder.mkdir()

    def make_csv(fname, freq_minutes, n, seed):
        rng = np.random.default_rng(seed)
        prices = [2000.0] * n
        times = pd.date_range("2015-01-01", periods=n, freq=f"{freq_minutes}min")
        pd.DataFrame({
            "Date": times.strftime("%Y.%m.%d"), "Time": times.strftime("%H:%M:%S"),
            "Open": prices, "High": prices, "Low": prices, "Close": prices,
            "Volume": rng.integers(10, 500, n),
        }).to_csv(folder / fname, index=False, sep=";")

    make_csv("XAU_1d_data.csv", 1440, 2000, 3)  # ~5.5 ans -- sert de référence pour le défaut

    cfg_yaml = f"""
data:
  folder: '{folder}'
  timeframe_pool: ["D1"]
  max_bars: 2000
  max_bars_market_closed: 0
  train_ratio: 0.7
  val_ratio: 0.3
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
fundamental:
  enabled: false
"""
    cfg = yaml.safe_load(cfg_yaml)
    autonomous_agent.make_data_provider(cfg)
    assert any("Jeu sous clé" in r.message for r in caplog.records), \
        "la date retenue doit être affichée (loggée) au démarrage"


def test_make_data_provider_disables_lockbox_gracefully_when_style_window_entirely_after_cutoff(
        tmp_path, monkeypatch, caplog):
    """Bug réel trouvé pendant l'essai à blanc LOT 2, phase 7 : la date de
    lockbox est UNIQUE pour tous les styles, mais un style dont la fenêtre de
    données réellement utilisée est ENTIÈREMENT postérieure à cette date
    (ex: M15, souvent limité à un historique récent par max_bars/
    max_bars_by_style, contrairement à D1) se retrouvait avec un train_df
    VIDE -> IndexError au premier reset() de TradingEnv. Le lockbox doit
    être désactivé pour CE style/ce cycle uniquement, jamais planter."""
    import logging
    caplog.set_level(logging.WARNING)
    monkeypatch.chdir(tmp_path)
    import yaml
    import autonomous_agent

    folder = tmp_path / "kaggle_gold"
    folder.mkdir()

    def make_csv(fname, freq_minutes, n, seed, start):
        # Marche aléatoire (pas un prix CONSTANT) : RSI/MACD/Bollinger %B ont
        # des divisions dégénérées (0/0 -> NaN) sur une série totalement
        # plate, ce qui viderait le dataframe via dropna() -- un artefact de
        # construction du test, pas le bug réel visé ici.
        rng = np.random.default_rng(seed)
        prices = [2000.0]
        for _ in range(1, n):
            prices.append(max(prices[-1] * (1 + rng.normal(0, 0.001)), 1.0))
        prices = np.array(prices)
        times = pd.date_range(start, periods=n, freq=f"{freq_minutes}min")
        pd.DataFrame({
            "Date": times.strftime("%Y.%m.%d"), "Time": times.strftime("%H:%M:%S"),
            "Open": prices, "High": prices * 1.001, "Low": prices * 0.999, "Close": prices,
            "Volume": rng.integers(10, 500, n),
        }).to_csv(folder / fname, index=False, sep=";")

    # M15 : fenêtre RÉCENTE seulement (simule max_bars_by_style qui limite
    # les styles courts à un historique récent, contrairement à D1).
    make_csv("XAU_15m_data.csv", 15, 3000, 1, start="2026-06-01")
    # D1 : historique LONG, remonte bien avant lockbox_start -- ET couvre
    # largement au-delà de la période M15 ci-dessus (sinon la fusion
    # multi-timeframe produit des NaN de contexte D1 manquant sur la
    # période M15, qui seraient ensuite droppés par add_technical_features,
    # un artefact de CE test, pas le bug réel visé ici).
    make_csv("XAU_1d_data.csv", 1440, 4500, 2, start="2015-01-01")

    lockbox_start = "2023-01-01"  # antérieur à TOUTE bougie M15 disponible

    cfg_yaml = f"""
data:
  folder: '{folder}'
  timeframe_pool: ["M15", "D1"]
  max_bars: 2000
  max_bars_market_closed: 0
  train_ratio: 0.7
  val_ratio: 0.3
  purge_bars: 10
  embargo_hours: 2
  lockbox_start: "{lockbox_start}"
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
fundamental:
  enabled: false
"""
    cfg = yaml.safe_load(cfg_yaml)
    get_data_fn, _ = autonomous_agent.make_data_provider(cfg)

    train_df, val_df, _, _, _ = get_data_fn("M15")
    assert len(train_df) > 0, "le lockbox désactivé pour ce style doit laisser un train_df NON VIDE"
    assert any("lockbox" in r.message.lower() and "désactivé" in r.message.lower() for r in caplog.records), \
        "un avertissement clair doit être journalisé quand le lockbox est désactivé pour un style"

    # D1, lui, a bien des données avant lockbox_start -- le lockbox reste actif.
    train_df_d1, val_df_d1, _, _, _ = get_data_fn("D1")
    assert len(train_df_d1) > 0
    assert (pd.to_datetime(train_df_d1["time"]) < pd.Timestamp(lockbox_start)).all()
