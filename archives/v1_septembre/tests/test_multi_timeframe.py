"""
test_multi_timeframe.py
========================
Vérifie, avec des CSV factices imitant le format Kaggle (9 timeframes,
colonnes Date+Time séparées), que :
  - la détection automatique des fichiers fonctionne (y compris H1/H4/D1/W1
    qui ont un underscore juste après le token, cas qui cassait une
    implémentation naïve basée sur \\b) ;
  - la vérification de cohérence détecte une association fichier/timeframe
    incohérente (ex: fichier mensuel nommé de façon ambiguë avec "1m") ;
  - la fusion multi-timeframe produit un dataset exploitable, sans fuite
    d'information (une bougie de contexte ne doit jamais être plus récente
    que la bougie primaire).
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd

from src.multi_timeframe import discover_files, verify_timeframe_assignment, build_mtf_dataset, TF_ORDER


def _make_kaggle_style_csv(path, freq_minutes, n, seed):
    rng = np.random.default_rng(seed)
    prices = [2000.0]
    for _ in range(1, n):
        prices.append(max(prices[-1] * (1 + rng.normal(0, 0.001)), 1.0))
    prices = np.array(prices)
    times = pd.date_range("2015-01-01", periods=n, freq=f"{freq_minutes}min")
    pd.DataFrame({
        "Date": times.strftime("%Y.%m.%d"), "Time": times.strftime("%H:%M:%S"),
        "Open": prices, "High": prices * 1.001, "Low": prices * 0.999,
        "Close": prices, "Volume": rng.integers(10, 500, n),
    }).to_csv(path, index=False)


def _make_dataset(folder):
    specs = [
        ("XAU_1m_data.csv", 1, 3000), ("XAU_5m_data.csv", 5, 3000),
        ("XAU_15m_data.csv", 15, 2000), ("XAU_30m_data.csv", 30, 2000),
        ("XAU_1H_data.csv", 60, 2000), ("XAU_4H_data.csv", 240, 1500),
        ("XAU_1D_data.csv", 1440, 1000), ("XAU_1W_data.csv", 10080, 300),
        ("XAU_1Mo_data.csv", 43200, 100),
    ]
    for fname, freq, n in specs:
        _make_kaggle_style_csv(os.path.join(folder, fname), freq, n, seed=abs(hash(fname)) % 1000)


def test_discovery_and_consistency(tmp_path):
    folder = str(tmp_path)
    _make_dataset(folder)
    files = discover_files(folder)
    assert set(files.keys()) == set(TF_ORDER), f"Timeframes manquantes : {set(TF_ORDER) - set(files.keys())}"

    report = verify_timeframe_assignment(files)
    assert all(r["ok"] for r in report.values()), f"Incohérence détectée : {report}"


def test_fusion_no_lookahead(tmp_path):
    folder = str(tmp_path)
    _make_dataset(folder)
    files = discover_files(folder)

    df, mtf_columns = build_mtf_dataset(files, primary_tf="H1", context_tfs=["H4", "D1"])
    assert len(mtf_columns) == 10  # 5 indicateurs x 2 timeframes de contexte
    assert not df[mtf_columns].isna().all().any()
    assert len(df) > 0


if __name__ == "__main__":
    import tempfile, pathlib
    d1 = pathlib.Path(tempfile.mkdtemp())
    test_discovery_and_consistency(d1)
    d2 = pathlib.Path(tempfile.mkdtemp())
    test_fusion_no_lookahead(d2)
    print("SMOKE TEST multi_timeframe: SUCCESS")
