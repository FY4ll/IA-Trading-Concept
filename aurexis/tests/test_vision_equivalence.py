"""PREUVE de l'étape 1 : la nouvelle vision (aurexis) calcule EXACTEMENT les mêmes informations que Run A, valeur pour
valeur, sur l'or, une devise, une crypto, un indice et un marché inversé (vraies données)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest
import yaml

RUN_A = r"C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
CFG = r"C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\run_config_A.yaml"
CONTEXTE = ["M30", "H1", "H4", "D1", "W1", "MN1"]


@pytest.fixture(scope="module")
def ancien():
    if RUN_A not in sys.path:
        sys.path.append(RUN_A)
    os.chdir(RUN_A)                                   # l'ancien code lit son cache FRED en relatif (data/cache)
    import src.aurexis_data as old
    from src.fred_feed import FredFeed
    cfg = yaml.safe_load(open(CFG, encoding="utf-8"))
    return old, FredFeed(cfg), cfg


@pytest.mark.parametrize("nom, inverse", [("XAUUSD", False), ("EURUSD", False), ("BTCUSD", False),
                                          ("GER40", False), ("US500", True)])
def test_meme_vision_que_run_a(ancien, nom, inverse):
    from aurexis.donnees import marches, reserve
    from aurexis.donnees.fred import Fred
    from aurexis.vision.fabrique import construire
    old, old_fred, cfg = ancien
    src = marches.source(nom)
    if not os.path.exists(src):
        pytest.skip(f"{nom} pas encore téléchargé")
    m15 = reserve.lire(nom, src).tail(9000).reset_index(drop=True)
    m15_old = old.load_m15(src).tail(9000).reset_index(drop=True)
    pd.testing.assert_frame_equal(m15, m15_old, check_dtype=False)
    if inverse:
        m15, m15_old = reserve.inverser(m15), old.mirror_m15(m15_old)
    dossier = cfg["data"]["cross_asset_folder"]
    attendu = old.build_market_frame(nom, m15_old, CONTEXTE, dossier, fred=old_fred, toolbox=True)
    nouveau = construire(nom, m15, CONTEXTE, dossier,
                         fred=Fred((cfg.get("fred") or {}).get("api_key", ""), os.path.join(RUN_A, "data", "cache")))
    assert list(nouveau.columns) == list(attendu.columns), "mêmes informations, même ordre"
    num = [c for c in attendu.columns if pd.api.types.is_numeric_dtype(attendu[c])]
    a, b = attendu[num].to_numpy(np.float64), nouveau[num].to_numpy(np.float64)
    ecart = np.nanmax(np.abs(a - b)) if np.isfinite(a).any() else 0.0
    assert np.array_equal(np.isnan(a), np.isnan(b)) and ecart <= 1e-9, f"écart max {ecart}"
    assert (nouveau["time"].to_numpy() == attendu["time"].to_numpy()).all()


def test_melangeur_et_inversion_identiques(ancien):
    from aurexis.donnees import reserve
    old = ancien[0]
    m15 = reserve.lire("XAUUSD", __import__("aurexis.donnees.marches", fromlist=["x"]).source("XAUUSD")).tail(3000)
    a = reserve.melanger_jours(m15, np.random.default_rng(5))
    b = old.mix_days(m15, np.random.default_rng(5))
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))
    pd.testing.assert_frame_equal(reserve.inverser(m15, 4.0e6), old.mirror_m15(m15, 4.0e6))
