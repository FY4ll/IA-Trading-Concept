"""Audit du 16/10, défaut 1 : pandas 3 lit les heures en MICROsecondes, le labo SMC compte en NANOsecondes.
Ces tests vérifient que toutes les heures rendues par les chargeurs sont en ns, et que `bt` (début des bougies) et
`mt` (les minutes) du labo sont dans la même unité."""
import numpy as np
import pandas as pd

from collapsar.donnees import histdata
from collapsar.donnees import marches as dm
from collapsar.donnees import minutes as dmin
from collapsar.regarder.smc import bougies as sb

NS = np.dtype("datetime64[ns]")


def _minutes_us(debut="2014-11-20", jours=70) -> pd.DataFrame:
    """Minutes inventées, heures en µs (comme pandas 3 les lit)."""
    t = pd.date_range(debut, periods=jours * 24 * 60, freq="1min").astype("datetime64[us]")
    rng = np.random.default_rng(3)
    c = 1200 + np.cumsum(rng.normal(0, 0.2, len(t)))
    return pd.DataFrame({"ny": t, "open": c, "high": c + 0.3, "low": c - 0.3, "close": c, "volume": 1.0})


def test_bt_et_mt_meme_unite_ns():
    m1 = _minutes_us()
    assert m1["ny"].dtype == np.dtype("datetime64[us]")
    for unite in ("M15", "H1", "H4"):
        b = sb.bougies("XAUUSD", unite, pd.Timestamp("2015-02-01"), m1=m1)
        assert b.t.dtype == NS
        assert b.n > 10
        # bt = début de la bougie en ns : même valeur que b.t et même ordre de grandeur que mt
        assert b.bt[0] == pd.Timestamp(b.t[0]).value
        assert 1.4e18 < b.bt[0] < 1.5e18 and 1.4e18 < b.mt[-1] < 1.5e18
        assert b.duree == pd.Timedelta(sb.FREQ[unite]).value
        assert b.bt[1] - b.bt[0] == b.duree
        # chaque début de bougie est une minute du tableau minute (même unité, même horloge)
        assert np.isin(b.bt, b.mt).all()
        # la 1re minute de chaque bougie retrouvée par recherche = la bonne
        k = np.searchsorted(b.mt, b.bt)
        assert (b.mt[k] == b.bt).all()


def _ecrire_m15(dossier, nom):
    t = pd.date_range("2020-01-01", periods=500, freq="15min")
    c = 100 + np.arange(500) * 0.01
    pd.DataFrame({"time": t.strftime("%Y-%m-%d %H:%M:%S"), "open": c, "high": c + 0.05, "low": c - 0.05,
                  "close": c, "volume": 1.0}).to_csv(dossier / f"{nom}_M15.csv", index=False)
    return t


def test_dm_charger_meme_unite_sans_et_avec_cache(tmp_path, monkeypatch):
    (tmp_path / "m15").mkdir()
    monkeypatch.setattr(dm, "DOSSIER_M15", tmp_path / "m15")
    monkeypatch.setattr(dm, "CACHE", tmp_path / "cache")
    t = _ecrire_m15(tmp_path / "m15", "ZZTEST")
    fin = pd.Timestamp("2100-01-01")
    a = dm.charger("ZZTEST", jusqua=fin)                  # 1er appel : pas de cache
    assert list((tmp_path / "cache").glob("*.npz"))
    b = dm.charger("ZZTEST", jusqua=fin)                  # 2e appel : depuis le cache
    c = dm.charger("ZZTEST", jusqua=fin, cache=False)
    for d in (a, b, c):
        assert d["time"].dtype == NS
        assert d["time"].values.astype(np.int64)[0] == pd.Timestamp(t[0]).value
    assert (a["time"].values == b["time"].values).all()
    assert (a["time"].values.astype(np.int64) == b["time"].values.astype(np.int64)).all()


def test_histdata_minutes_horaire_en_ns(tmp_path, monkeypatch):
    # HistData (S&P 500, Nasdaq, euro)
    (tmp_path / "hd" / "SPXUSD").mkdir(parents=True)
    pd.DataFrame({"t": ["20150102 093000", "20150102 093100"], "open": [1., 2.], "high": [1., 2.], "low": [1., 2.],
                  "close": [1., 2.], "volume": [0, 0]}).to_csv(tmp_path / "hd" / "SPXUSD" / "2015.csv", index=False)
    monkeypatch.setattr(histdata, "DOSSIER", tmp_path / "hd")
    h = histdata.charger("SPXUSD")
    assert h["ny"].dtype == NS
    assert h["ny"].values.astype(np.int64)[0] == pd.Timestamp("2015-01-02 09:30").value
    # minutes Dukascopy
    (tmp_path / "mn" / "ZZ").mkdir(parents=True)
    pd.DataFrame({"time": ["2020-01-02 15:00:00"], "open": [1.], "high": [1.], "low": [1.], "close": [1.]}).to_csv(
        tmp_path / "mn" / "ZZ" / "2020-01.csv", index=False)
    monkeypatch.setattr(dmin, "DOSSIER", tmp_path / "mn")
    m = dmin.charger("ZZ")
    assert m["time"].dtype == NS and m["ny"].dtype == NS
    assert m["ny"].values.astype(np.int64)[0] == pd.Timestamp("2020-01-02 10:00").value
    # bougies d'une heure
    (tmp_path / "h1").mkdir()
    pd.DataFrame({"time": ["2019-01-02 10:00:00"], "open": [1.], "high": [1.], "low": [1.], "close": [1.],
                  "volume": [1.]}).to_csv(tmp_path / "h1" / "ZZ_H1.csv", index=False)
    monkeypatch.setattr(dm, "DOSSIER_H1", tmp_path / "h1")
    g = dm.charger_horaire("ZZ", avant=pd.Timestamp("2020-01-01"))
    assert g["time"].dtype == NS and len(g) == 1
