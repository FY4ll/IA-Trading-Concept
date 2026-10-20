"""Tests des chargeurs de DONNÉES HORS PRIX (fournée 1, 20/10/2026) : colonnes, date de publication toujours après la
date mesurée, rien de publié à partir de la date limite (coffre fermé au 01/01/2024), nombres de lignes plausibles,
et dates de publication vérifiées contre des sources indépendantes (calendrier MetaTrader, calendriers officiels
archivés de la CFTC, fichier data/macro_events_real.csv)."""
from __future__ import annotations

import glob
import re
import zipfile

import numpy as np
import pandas as pd
import pytest

from cerveau.donnees_hors_prix import COFFRE, RACINE, cftc_tff, fed_liquidite, fomc, gld

H = pd.Timedelta


@pytest.fixture(scope="module")
def cftc():
    return cftc_tff.charger()


@pytest.fixture(scope="module")
def fed():
    return {s: fed_liquidite.charger(s) for s in fed_liquidite.SERIES}


@pytest.fixture(scope="module")
def decisions():
    return fomc.charger()


@pytest.fixture(scope="module")
def fonds_or():
    return gld.charger()


# ------------------------------------------------------------------ règles communes
def _commun(df: pd.DataFrame, colonnes: list[str]):
    assert set(colonnes) <= set(df.columns)
    assert df["publie"].notna().all() and df["date"].notna().all()
    assert (df["publie"] > df["date"]).all(), "une valeur publiée avant (ou à) sa date de mesure"
    assert df["publie"].max() < COFFRE, "une valeur publiée après le début du coffre"
    assert df["publie"].is_monotonic_increasing


def test_limite_plus_tardive_refusee():
    for f in (cftc_tff.charger, fomc.charger, gld.charger, lambda limite: fed_liquidite.charger("WALCL", limite)):
        with pytest.raises(ValueError):
            f(limite="2024-01-02")


@pytest.mark.parametrize("limite", ["2015-01-01", "2019-06-07 22:00", "2020-03-15 23:59"])
def test_rien_apres_la_limite_et_coupe_sans_futur(limite, cftc, fed, decisions, fonds_or):
    """Couper à une date ne change AUCUNE valeur publiée avant : on obtient exactement les lignes du chargement
    complet publiées avant la limite."""
    lim = pd.Timestamp(limite)
    paires = [(cftc_tff.charger(limite), cftc), (fomc.charger(limite), decisions), (gld.charger(limite), fonds_or)]
    paires += [(fed_liquidite.charger(s, limite), fed[s]) for s in fed_liquidite.SERIES]
    for court, complet in paires:
        assert len(court) and court["publie"].max() < lim
        attendu = complet[complet["publie"] < lim].reset_index(drop=True)
        pd.testing.assert_frame_equal(court.reset_index(drop=True), attendu)


# ------------------------------------------------------------------ CFTC
def test_cftc_colonnes_et_couverture(cftc):
    cols = ["date", "publie", "source_publie", "devise", "paire_ftmo", "sens_paire", "interet_ouvert",
            "gerants_achat", "gerants_vente", "gerants_net", "levier_achat", "levier_vente", "levier_net",
            "intermediaires_net", "autres_net", "non_declares_net"]
    _commun(cftc, cols)
    assert set(cftc["devise"]) == {"EUR", "JPY", "GBP", "AUD", "CHF", "CAD", "NZD"}
    assert cftc["date"].min() == pd.Timestamp("2006-06-13") and cftc["date"].max() == pd.Timestamp("2023-12-26")
    semaines = cftc.drop_duplicates("date")
    par_an = semaines.groupby(semaines["date"].dt.year).size()
    assert par_an.loc[2007:2023].between(52, 53).all()
    assert 6300 < len(cftc) < 6500
    assert not cftc.duplicated(["date", "devise"]).any()
    # sens de la paire : acheteur du contrat yen = vendeur de USDJPY
    s = cftc.drop_duplicates("devise").set_index("devise")["sens_paire"]
    assert s["EUR"] == 1 and s["JPY"] == -1 and s["CHF"] == -1 and s["CAD"] == -1 and s["AUD"] == 1
    assert (cftc["gerants_net"] == cftc["gerants_achat"] - cftc["gerants_vente"]).all()
    # publication : un vendredi 15h30 New York (22h30 serveur) en temps normal, au moins 2 jours après les positions
    assert ((cftc["publie"] - cftc["date"]) >= H(days=2, hours=22, minutes=30)).all()
    assert (cftc["publie"].dt.strftime("%H:%M") == "22:30").all()
    normal = cftc[cftc["source_publie"] == "regle"]
    assert (normal["publie"].dt.dayofweek == 4).mean() > 0.90         # ~3 semaines fériées par an -> lundi


def test_cftc_arret_de_l_etat_2018_2019(cftc):
    """Rien de publié entre le 22/12/2018 et le 31/01/2019 ; rattrapage 01/02 -> 08/03/2019, un mardi et un vendredi."""
    pub = cftc.drop_duplicates("date").set_index("date")["publie"]
    assert not ((pub > "2018-12-22") & (pub < "2019-02-01")).any()
    rattrapage = pub[(pub >= "2019-02-01") & (pub < "2019-03-09")]
    assert len(rattrapage) == 11
    assert set(rattrapage.dt.dayofweek) == {1, 4}
    assert pub[pd.Timestamp("2018-12-24")] == pd.Timestamp("2019-02-01 22:30")
    assert pub[pd.Timestamp("2019-03-05")] == pd.Timestamp("2019-03-08 22:30")
    assert pub[pd.Timestamp("2019-03-12")] == pd.Timestamp("2019-03-15 22:30")       # retour à la normale


def test_cftc_jamais_avant_metatrader(cftc):
    """2015-2023 : la date retenue n'est jamais AVANT la publication relevée par le calendrier de MetaTrader (rapport
    reconnu par sa valeur : position nette des non commerciaux sur l'euro, ancien rapport local), et lui est égale
    hors annonces officielles."""
    from collapsar.donnees.calendrier import MT5_HISTOIRE, _lire_mt5
    leg = []
    for an in range(2014, 2024):
        with zipfile.ZipFile(RACINE / "data" / "foule_devises" / "cftc_brut" / f"deacot{an}.zip") as z:
            d = pd.read_csv(z.open(z.namelist()[0]), low_memory=False, dtype={"CFTC Contract Market Code": str})
        d.columns = [c.strip() for c in d.columns]
        d = d[d["CFTC Contract Market Code"].str.strip() == "099741"]
        leg.append(pd.DataFrame({"date": pd.to_datetime(d["As of Date in Form YYYY-MM-DD"]),
                                 "net": (d["Noncommercial Positions-Long (All)"]
                                         - d["Noncommercial Positions-Short (All)"]) / 1000}))
    leg = pd.concat(leg).drop_duplicates("date").sort_values("date")
    m = _lire_mt5(MT5_HISTOIRE)
    m = m[m["annonce"].str.contains("CFTC EUR Positions nettes non commerciales") & (m["temps"] >= "2015-01-01")]
    pub = cftc.drop_duplicates("date").set_index("date")
    vus, egaux = 0, 0
    for _, r in m.iterrows():
        jour = (r["temps"] - H(hours=7)).normalize()
        c = leg[(leg["date"] < jour) & (leg["date"] >= jour - H(days=60))]
        c = c[(c["net"] - float(r["publie"])).abs() < 0.051]
        if not len(c) or c["date"].iloc[-1] not in pub.index:
            continue
        ligne = pub.loc[c["date"].iloc[-1]]
        vus += 1
        assert ligne["publie"] >= r["temps"], f"positions {c['date'].iloc[-1]:%Y-%m-%d} publiées trop tôt"
        egaux += ligne["publie"] == r["temps"]
    assert vus > 400 and egaux / vus > 0.98


def test_cftc_calendriers_officiels_archives(cftc):
    """Calendriers officiels de la CFTC (archives 2010-2023) : même jour de publication pour plus de 95 % des
    semaines ; les écarts viennent des annonces officielles (retards annoncés après coup)."""
    mois = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                        "September", "October", "November", "December"], 1)}
    off = set()
    for f in glob.glob(str(cftc_tff.ICI / "calendriers_archives" / "calendrier_*.txt")):
        t = open(f, encoding="utf-8-sig").read().split("*Delayed")[0]
        for an, bloc in re.findall(r"(\d{4}) Dates (.*?)(?=\d{4} Dates|$)", t):
            m = None
            for tok in bloc.split():
                tok = tok.strip("*")
                if tok in mois:
                    m = mois[tok]
                elif tok.isdigit() and m:
                    off.add(pd.Timestamp(int(an), m, int(tok)))
    if len(off) < 500:
        pytest.skip("calendriers archivés absents")
    off = pd.Series(sorted(off))
    pub = cftc.drop_duplicates("date")
    pub = pub[pub["date"] >= off.min() - H(days=3)]
    ok = n = 0
    for _, r in pub.iterrows():
        c = off[(off > r["date"]) & (off <= r["date"] + H(days=12))]
        if len(c):
            n += 1
            ok += (r["publie"] - H(hours=22, minutes=30)) == c.iloc[0]
    assert n > 700 and ok / n > 0.95


def test_cftc_regle_jours_feries():
    r = cftc_tff.publication_regle
    assert r(pd.Timestamp("2019-11-26")) == pd.Timestamp("2019-12-02")    # Thanksgiving -> lundi (« 2* »)
    assert r(pd.Timestamp("2017-07-03")) == pd.Timestamp("2017-07-07")    # positions du lundi, vendredi normal
    assert r(pd.Timestamp("2016-11-08")) == pd.Timestamp("2016-11-14")    # vendredi férié -> lundi
    assert r(pd.Timestamp("2013-12-24")) == pd.Timestamp("2013-12-30")    # Noël mercredi -> lundi (« 30* »)
    assert r(pd.Timestamp("2018-03-13")) == pd.Timestamp("2018-03-16")    # semaine ordinaire


# ------------------------------------------------------------------ Fed : bilan, Trésor, pensions
def test_fed_colonnes_et_couverture(fed):
    for s, d in fed.items():
        _commun(d, ["date", "publie", "valeur", "premiere_publication", "serie"])
        assert (d["serie"] == s).all() and not d["date"].duplicated().any()
    for s in fed_liquidite.HEBDO:
        d = fed[s]
        assert d["date"].min() == pd.Timestamp("2002-12-18") and 1090 <= len(d) <= 1100
        assert (d["date"].dt.dayofweek == 2).all()                       # mercredi
        assert (d["publie"].dt.strftime("%H:%M") == "23:30").all()       # 16h30 New York
        assert ((d["publie"] - d["date"]) >= H(days=1, hours=23, minutes=30)).all()   # jamais avant le jeudi
        assert d["premiere_publication"].sum() > 600
    assert fed["WALCL"]["premiere_publication"].idxmax() == fed["WALCL"]["date"].searchsorted(
        pd.Timestamp("2011-07-13"))
    rrp = fed["RRPONTSYD"]
    assert 2500 < len(rrp) < 2800 and (rrp["publie"] - rrp["date"] == H(hours=20, minutes=15)).all()
    # unités : millions de dollars partout (bilan ~7 700 milliards fin 2023 ; compte du Trésor ~700 milliards)
    fin = {s: d[d["date"] >= "2023-12-01"]["valeur"].median() for s, d in fed.items()}
    assert 7e6 < fin["WALCL"] < 8.5e6 and 3e5 < fin["WTREGEN"] < 1.2e6 and 3e5 < fin["WDTGAL"] < 1.2e6
    assert 3e5 < fin["RRPONTSYD"] < 2e6


def test_fed_jour_ferie_et_retard_alfred(fed):
    w = fed["WALCL"].set_index("date")["publie"]
    assert w[pd.Timestamp("2023-11-22")] == pd.Timestamp("2023-11-24 23:30")   # jeudi de Thanksgiving -> vendredi
    assert w[pd.Timestamp("2018-01-03")] == pd.Timestamp("2018-01-11 23:30")   # première trace ALFRED (prudent)
    assert w[pd.Timestamp("2019-05-15")] == pd.Timestamp("2019-05-16 23:30")   # semaine ordinaire


# ------------------------------------------------------------------ Fed : décisions
def test_fomc_colonnes_et_nombres(decisions):
    _commun(decisions, ["date", "publie", "prevue", "nature", "intitule", "heure_ny", "source_heure", "url"])
    p = decisions[decisions["prevue"]]
    an = p["date"].dt.year
    assert len(p) == 111 and an.between(2012, 2019).sum() == 64 and an.between(2020, 2023).sum() == 31
    assert (p.groupby(an).size().drop(2020) == 8).all()
    exc = decisions[~decisions["prevue"]]
    assert {"2020-03-03", "2020-03-15"} <= set(exc["date"].dt.strftime("%Y-%m-%d"))
    assert exc["publie"].dt.strftime("%Y-%m-%d %H:%M").tolist().count("2020-03-16 00:00") == 1   # dimanche 17h NY
    # heures : 14h15 (2010 -> 30/01/2013), 12h30 (conférences de presse 2011-2012), 14h00 ensuite
    h = p.set_index(p["date"].dt.strftime("%Y-%m-%d"))["heure_ny"]
    assert h["2010-08-10"] == "14:15" and h["2012-09-13"] == "12:30" and h["2013-01-30"] == "14:15"
    assert h["2013-03-20"] == "14:00" and (p[p["date"] >= "2013-03-20"]["heure_ny"] == "14:00").all()
    assert (p[p["date"] >= "2016-01-01"]["source_heure"] == "communique").all()


def test_fomc_identique_au_fichier_macro(decisions):
    """Les réunions prévues 2015-2023 et leur heure = celles de data/macro_events_real.csv (relevées séparément le
    21/09/2026 sur federalreserve.gov)."""
    m = pd.read_csv(RACINE / "data" / "macro_events_real.csv", comment="#")
    m = m[m["event_type"] == "FOMC"]
    t = pd.to_datetime(m["timestamp_utc"]).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    t = t[(t >= "2015-01-01") & (t < "2024-01-01")]
    p = decisions[decisions["prevue"] & (decisions["date"] >= "2015-01-01")]
    assert sorted(t + H(hours=7)) == sorted(p["publie"])


# ------------------------------------------------------------------ fonds d'or GLD
def test_gld_colonnes_et_publication(fonds_or):
    _commun(fonds_or, ["date", "publie", "tonnes_or", "variation_tonnes", "cloture", "prime_decote_pct"])
    g = fonds_or
    assert g["date"].min() == pd.Timestamp("2004-11-18") and 4700 < len(g) < 4900
    assert g["tonnes_or"].notna().all() and (g["tonnes_or"] > 0).all()
    assert (g["date"].dt.dayofweek < 5).all()
    # publié le jour de Bourse SUIVANT à 10h00 New York (17h00 serveur)
    assert (g["publie"].dt.strftime("%H:%M") == "17:00").all()
    assert (g["publie"].iloc[:-1].dt.normalize().values == g["date"].iloc[1:].values).all()
    assert ((g["publie"] - g["date"]) >= H(days=1, hours=17)).all()
    v = g["tonnes_or"].diff()
    assert np.allclose(g["variation_tonnes"].iloc[1:], v.iloc[1:])
    assert g["variation_tonnes"].iloc[1:].notna().all()          # plus de trou le lendemain des jours fériés
