"""Un FORMAT COMMUN pour les trades des maîtres, quelle que soit la source (15/10/2026).

Chaque trade : maitre, source, marche (nom de NOS données : EURUSD, XAUUSD, USA500IDXUSD, BTCUSD...), symbole
d'origine, debut, fin (heure du SERVEUR MetaTrader, New York + 7 h, comme nos bougies), sens (+1 achat, -1 vente),
volume (unité d'origine), prix_entree, prix_sortie, stop, objectif (NaN si inconnus), gain (devise du compte).

Sources lues :
- export CSV d'un signal MQL5 (onglet « Trading history ») : colonnes reconnues par leur nom, séparateur ; ou , ;
- Paul Wei (BitMEX, data/maitres/coolish) : allers-retours complets sur le bitcoin ;
- Hyperliquid (data/maitres/hyperliquid/historiques) : allers-retours de la position nulle à la position nulle.
Les heures UTC (BitMEX, Hyperliquid) sont converties à l'heure du serveur ; celles de MQL5 sont celles du serveur
du courtier (souvent UTC+2/+3, comme le nôtre) : à vérifier signal par signal (décalage estimé sur les prix).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from collapsar.donnees.marches import RACINE

COLONNES = ["maitre", "source", "marche", "symbole", "debut", "fin", "sens", "volume", "prix_entree",
            "prix_sortie", "stop", "objectif", "gain"]
# symbole d'origine (sans suffixe de courtier) -> nos données
CORRESPONDANCE = {"XAUUSD": "XAUUSD", "GOLD": "XAUUSD", "XAGUSD": "XAGUSD", "SILVER": "XAGUSD",
                  "US500": "USA500IDXUSD", "SPX500": "USA500IDXUSD", "SP500": "USA500IDXUSD", "SPX": "USA500IDXUSD",
                  "US100": "USATECHIDXUSD", "NAS100": "USATECHIDXUSD", "USTEC": "USATECHIDXUSD", "NDX": "USATECHIDXUSD",
                  "US30": "USA30IDXUSD", "DJ30": "USA30IDXUSD", "GER40": "DEUIDXEUR", "DE40": "DEUIDXEUR",
                  "GER30": "DEUIDXEUR", "DAX40": "DEUIDXEUR", "UK100": "GBRIDXGBP", "FRA40": "FRAIDXEUR",
                  "JP225": "JPNIDXJPY", "AUS200": "AUSIDXAUD", "EU50": "EUSIDXEUR", "USOIL": "LIGHTCMDUSD",
                  "WTI": "LIGHTCMDUSD", "XTIUSD": "LIGHTCMDUSD", "OIL": "LIGHTCMDUSD", "UKOIL": "BRENTCMDUSD",
                  "BRENT": "BRENTCMDUSD", "XBRUSD": "BRENTCMDUSD", "BRENTOIL": "BRENTCMDUSD",
                  "BTCUSD": "BTCUSD", "XBTUSD": "BTCUSD", "BTC": "BTCUSD", "ETHUSD": "ETHUSD", "ETH": "ETHUSD"}
DEVISES = ("EUR", "USD", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD")


def notre_marche(symbole: str) -> str | None:
    s = str(symbole).upper().split(":")[-1]
    s = re.sub(r"[^A-Z0-9]", "", s.split(".")[0])                    # retire les suffixes de courtier (.f, .cash...)
    if s in CORRESPONDANCE:
        return CORRESPONDANCE[s]
    for k, v in CORRESPONDANCE.items():
        if s.startswith(k):
            return v
    if len(s) >= 6 and s[:3] in DEVISES and s[3:6] in DEVISES:
        return s[:6]
    if s in ("EUR", "JPY", "GBP"):                                   # Hyperliquid : devise contre dollar
        return {"EUR": "EURUSD", "GBP": "GBPUSD", "JPY": "USDJPY"}[s]
    return None


def utc_vers_serveur(t: pd.Series) -> pd.Series:
    """UTC -> heure du serveur MetaTrader (New York + 7 h), comme nos bougies."""
    t = pd.to_datetime(t, utc=True)
    return t.dt.tz_convert("America/New_York").dt.tz_localize(None) + pd.Timedelta(hours=7)


def _num(x) -> pd.Series:
    return pd.to_numeric(pd.Series(x).astype(str).str.replace(" ", "").str.replace(",", "."), errors="coerce")


def lire_mql5(fichier: Path, maitre: str | None = None) -> pd.DataFrame:
    """Export « Trading history » d'un signal MQL5 : une ligne par position (ouverture ... clôture)."""
    brut = Path(fichier).read_text(encoding="utf-8-sig", errors="replace")
    sep = ";" if brut.count(";") > brut.count(",") else ","
    df = pd.read_csv(Path(fichier), sep=sep, encoding="utf-8-sig", engine="python")
    cols = [c.strip().lower() for c in df.columns]
    df.columns = cols
    def prend(*noms, n=0):
        trouves = [c for c in cols if any(c.startswith(x) for x in noms)]
        return df[trouves[n]] if len(trouves) > n else pd.Series([np.nan] * len(df))
    temps = [c for c in cols if c.startswith("time") or c.startswith("date")]
    prix = [c for c in cols if c.startswith("price")]
    type_ = prend("type").astype(str).str.lower()
    sens = np.where(type_.str.contains("buy"), 1, np.where(type_.str.contains("sell"), -1, 0))
    t = pd.DataFrame({
        "maitre": maitre or Path(fichier).stem, "source": "mql5", "symbole": prend("symbol"),
        "debut": pd.to_datetime(df[temps[0]], errors="coerce") if temps else pd.NaT,
        "fin": pd.to_datetime(df[temps[1]], errors="coerce") if len(temps) > 1 else pd.NaT,
        "sens": sens, "volume": _num(prend("volume", "size", "lots")),
        "prix_entree": _num(df[prix[0]]) if prix else np.nan, "prix_sortie": _num(df[prix[1]]) if len(prix) > 1 else np.nan,
        "stop": _num(prend("s / l", "s/l", "sl", "stop")), "objectif": _num(prend("t / p", "t/p", "tp", "take")),
        "gain": _num(prend("profit"))})
    t["marche"] = t["symbole"].map(notre_marche)
    t.loc[t["stop"] <= 0, "stop"] = np.nan
    t.loc[t["objectif"] <= 0, "objectif"] = np.nan
    return t[(t["sens"] != 0) & t["debut"].notna()][COLONNES].reset_index(drop=True)


def lire_coolish() -> pd.DataFrame:
    """Paul Wei : allers-retours complets sur le contrat bitcoin XBTUSD (BitMEX), position nulle -> nulle."""
    d = RACINE / "data" / "maitres" / "coolish" / "BTC-Trading-Since-2020-main" / "api-v1-execution-tradeHistory.csv"
    x = pd.read_csv(d, low_memory=False, parse_dates=["timestamp"])
    x = x[(x.execType == "Trade") & (x.symbol == "XBTUSD")].sort_values("timestamp").reset_index(drop=True)
    q = np.where(x.side == "Buy", 1.0, -1.0) * x.lastQty.to_numpy(float)
    px = x.lastPx.to_numpy(float)
    lignes, pos, debut, entree_num, entree_den, sortie_num, sortie_den, sens = [], 0.0, None, 0.0, 0.0, 0.0, 0.0, 0
    for i in range(len(x)):
        if pos == 0:
            debut, entree_num, entree_den, sortie_num, sortie_den, sens = x.timestamp[i], 0.0, 0.0, 0.0, 0.0, np.sign(q[i])
        if np.sign(q[i]) == sens:
            entree_num += abs(q[i]); entree_den += abs(q[i]) / px[i]
        else:
            sortie_num += abs(q[i]); sortie_den += abs(q[i]) / px[i]
        pos += q[i]
        if abs(pos) < 1e-9 and debut is not None:
            pe, ps = entree_num / entree_den, (sortie_num / sortie_den if sortie_den else np.nan)
            lignes.append({"debut": debut, "fin": x.timestamp[i], "sens": int(sens), "volume": entree_num,
                           "prix_entree": pe, "prix_sortie": ps,
                           "gain": sens * entree_num * (1 / pe - 1 / ps) if np.isfinite(ps) else np.nan})
            pos, debut = 0.0, None
    t = pd.DataFrame(lignes)
    t["debut"], t["fin"] = utc_vers_serveur(t["debut"]), utc_vers_serveur(t["fin"])
    t["maitre"], t["source"], t["symbole"], t["marche"] = "paul_wei", "bitmex", "XBTUSD", "BTCUSD"
    t["stop"], t["objectif"] = np.nan, np.nan
    return t[COLONNES]


def lire_gtrade(fichier: Path) -> pd.DataFrame:
    """gTrade : un trade = (paire, numéro de trade) de son ouverture à sa fermeture. Stop / objectif connus après
    coup quand le trade s'est fermé dessus (« TradeClosedSL » / « TradeClosedTP » : prix de sortie = niveau)."""
    df = pd.read_csv(fichier)
    if not len(df) or "action" not in df:
        return pd.DataFrame(columns=COLONNES)
    df = df.sort_values("date")
    lignes = []
    for (paire, idx), g in df.groupby(["pair", "tradeIndex"]):
        ouv = g[g["action"].astype(str).str.startswith("TradeOpened")]
        fer = g[g["action"].astype(str).str.startswith("TradeClosed")]
        if not len(ouv) or not len(fer):
            continue
        o, f = ouv.iloc[0], fer.iloc[-1]
        sortie = str(f["action"])
        lignes.append({"debut": o["date"], "fin": f["date"], "sens": 1 if bool(o["long"]) else -1,
                       "volume": float(o["size"]) if pd.notna(o["size"]) else np.nan,
                       "prix_entree": float(o["price"]), "prix_sortie": float(f["price"]),
                       "stop": float(f["price"]) if sortie.endswith("SL") else np.nan,
                       "objectif": float(f["price"]) if sortie.endswith("TP") else np.nan,
                       "gain": float(g["pnl_net"].fillna(0).sum()), "symbole": paire,
                       "levier": float(o["leverage"]) if pd.notna(o["leverage"]) else np.nan,
                       "liquide": sortie.endswith("LIQ")})
    t = pd.DataFrame(lignes)
    if not len(t):
        return pd.DataFrame(columns=COLONNES)
    t["debut"], t["fin"] = utc_vers_serveur(t["debut"]), utc_vers_serveur(t["fin"])
    t["maitre"], t["source"] = "gtrade_" + Path(fichier).stem, "gtrade"
    t["marche"] = t["symbole"].map(lambda p: notre_marche(p.replace("/", "")) if "/" in p else notre_marche(p))
    t.loc[t["symbole"].str.startswith("SPY"), "marche"] = "USA500IDXUSD"
    t.loc[t["symbole"].str.startswith("QQQ"), "marche"] = "USATECHIDXUSD"
    return t[COLONNES + ["levier", "liquide"]]


# noms des marchés Hyperliquid (HIP-3, « xyz:… ») que la table commune ne reconnaît pas
HYPERLIQUID = {"CL": "LIGHTCMDUSD", "WTI": "LIGHTCMDUSD", "BRENTOIL": "BRENTCMDUSD", "NATGAS": "GASCMDUSD",
               "XYZ100": "USATECHIDXUSD", "SP500": "USA500IDXUSD", "GOLD": "XAUUSD", "SILVER": "XAGUSD"}


def lire_hyperliquid(fichier: Path) -> pd.DataFrame:
    """Hyperliquid : trades de la position nulle à la position nulle, par marché (exécutions d'un même ordre remises
    dans l'ordre : la position avance dans le sens de l'ordre, vérifié à ~100 %)."""
    if Path(fichier).stat().st_size == 0:
        return pd.DataFrame(columns=COLONNES)
    df = pd.read_csv(fichier, low_memory=False)
    if not len(df):
        return pd.DataFrame(columns=COLONNES)
    df = df.assign(_cle=df["startPosition"].astype(float) * np.where(df["side"] == "B", 1.0, -1.0))
    df = df.sort_values(["time", "_cle"])
    lignes = []
    for coin, g in df.groupby("coin"):
        signe = np.where(g["side"].to_numpy() == "B", 1.0, -1.0)
        sz, px = g["sz"].astype(float).to_numpy(), g["px"].astype(float).to_numpy()
        avant = g["startPosition"].astype(float).to_numpy()
        apres = avant + signe * sz
        net = g["closedPnl"].astype(float).to_numpy() - g["fee"].astype(float).to_numpy()
        tt = g["time"].to_numpy()
        ouvert = None
        for i in range(len(g)):
            if ouvert is None and abs(avant[i]) < 1e-12 and abs(apres[i]) > 0:
                ouvert = {"debut": tt[i], "sens": int(np.sign(apres[i])), "prix_entree": px[i], "gain": 0.0,
                          "volume": abs(apres[i])}
            if ouvert is None:
                continue
            ouvert["gain"] += net[i]
            if abs(apres[i]) < 1e-9 * max(1.0, abs(avant[i])):
                lignes.append({**ouvert, "fin": tt[i], "prix_sortie": px[i], "symbole": coin})
                ouvert = None
    tr = pd.DataFrame(lignes)
    if not len(tr):
        return pd.DataFrame(columns=COLONNES)
    tr["debut"] = utc_vers_serveur(pd.to_datetime(tr["debut"], unit="ms", utc=True))
    tr["fin"] = utc_vers_serveur(pd.to_datetime(tr["fin"], unit="ms", utc=True))
    tr["maitre"], tr["source"] = "hyperliquid_" + Path(fichier).stem, "hyperliquid"
    tr["marche"] = tr["symbole"].map(lambda s: HYPERLIQUID.get(str(s).split(":")[-1].upper()) or notre_marche(s))
    tr["stop"], tr["objectif"] = np.nan, np.nan
    return tr[COLONNES]


def lire_ostium(fichier: Path) -> pd.DataFrame:
    """Ostium : un trade = (portefeuille, numéro de trade), de l'ordre d'ouverture à la dernière fermeture (complète,
    ou sur stop / objectif / liquidation). Gain = argent rendu - mise, fermeture par fermeture (frais compris)."""
    from collapsar.maitres.ostium import FERMETURES, MARCHES
    df = pd.read_csv(fichier, dtype={"trader": str, "tradeID": str, "orderAction": str})
    if not len(df):
        return pd.DataFrame(columns=COLONNES)
    df = df.drop_duplicates("id").sort_values("executedAt")
    ouv = df[df["orderAction"] == "Open"].drop_duplicates(["trader", "tradeID"]).set_index(["trader", "tradeID"])
    fer = df[df["orderAction"].isin(FERMETURES)].copy()
    fer["gain"] = (fer["amountSentToTrader"].astype(float) - fer["collateral"].astype(float)) / 1e6
    g = fer.groupby(["trader", "tradeID"])
    der = g.tail(1).set_index(["trader", "tradeID"])
    fini = (der["closePercent"].astype(float) >= 10000) | (der["orderAction"] != "Close")
    der = der[fini]
    cle = der.index.intersection(ouv.index)
    o, f = ouv.loc[cle], der.loc[cle]
    t = pd.DataFrame({"maitre": "ostium_" + cle.get_level_values(0), "source": "ostium",
                      "symbole": o["paire"].to_numpy(), "debut": pd.to_datetime(o["executedAt"].to_numpy(), unit="s", utc=True),
                      "fin": pd.to_datetime(f["executedAt"].to_numpy(), unit="s", utc=True),
                      "sens": np.where(o["isBuy"].astype(str) == "True", 1, -1),
                      "volume": o["notional"].astype(float).to_numpy() / 1e6,
                      "prix_entree": o["price"].astype(float).to_numpy() / 1e18,
                      "prix_sortie": f["price"].astype(float).to_numpy() / 1e18,
                      "gain": g["gain"].sum().loc[cle].to_numpy(),
                      "levier": o["leverage"].astype(float).to_numpy() / 100,
                      "liquide": (f["orderAction"] == "Liquidation").to_numpy()})
    t["stop"] = np.where(f["orderAction"].to_numpy() == "StopLoss", t["prix_sortie"], np.nan)
    t["objectif"] = np.where(f["orderAction"].to_numpy() == "TakeProfit", t["prix_sortie"], np.nan)
    t["debut"], t["fin"] = utc_vers_serveur(t["debut"]), utc_vers_serveur(t["fin"])
    t["marche"] = t["symbole"].map(MARCHES)
    return t[COLONNES + ["levier", "liquide"]].reset_index(drop=True)


def lire_synthetix(fichier: Path) -> pd.DataFrame:
    """Synthetix (Optimism, maitres/synthetix.py) : un trade = (compte, génération) de la position nulle au retour à
    la position nulle ; un passage direct d'achat à vente ferme le trade et en ouvre un autre au même prix.
    GAIN = variation de la marge (le dépôt du compte chez Synthetix) hors dépôts et retraits : il contient donc
    exactement le résultat du prix, le financement entre acheteurs et vendeurs et tous les frais. Liquidation : la
    marge restante est perdue. Prix d'entrée / de sortie = moyennes pondérées des morceaux ; volume = plus grosse
    taille du trade en dollars ; levier = taille / marge à l'ouverture. Synthetix n'a ni stop ni objectif : NaN."""
    df = pd.read_csv(fichier, dtype={"compte": str, "tx": str})
    if not len(df):
        return pd.DataFrame(columns=COLONNES)
    df = df.drop_duplicates(["tx", "index_log", "evenement"]).sort_values(["bloc", "index_log"])
    nom = Path(fichier).stem.split("_")[-1]
    lignes = []
    for (gen, compte), g in df.groupby(["generation", "compte"], sort=False):
        taille, ref, tr = 0.0, 0.0, None
        for ev, heure, tx, marge, s, prix, frais, delta in zip(
                g["evenement"], g["heure"], g["tx"], g["marge"], g["taille"], g["prix"], g["frais"], g["delta_marge"]):
            if ev == "MarginTransferred":
                ref += float(delta)
                continue
            if ev == "PositionModified":
                s, marge, prix = float(s), float(marge), float(prix)
                dm, ref, p = marge - ref, marge, taille
                if tr is None and s != 0:
                    tr = {"debut": heure, "sens": int(np.sign(s)), "e_num": 0.0, "e_qte": 0.0, "s_num": 0.0,
                          "s_qte": 0.0, "max_qte": abs(s), "gain": 0.0, "frais": 0.0, "liquide": False,
                          "levier": abs(s) * prix / marge if marge > 0 else np.nan, "tx_fin": None,
                          "marge_entree": marge}
                    p = 0.0
                if tr is not None:
                    tr["gain"] += dm
                    tr["frais"] += float(frais or 0)
                    if p != 0 and s != 0 and np.sign(s) != np.sign(p):          # retournement
                        tr["s_num"] += abs(p) * prix; tr["s_qte"] += abs(p)
                        tr.update(fin=heure, tx_fin=tx); lignes.append(tr)
                        tr = {"debut": heure, "sens": int(np.sign(s)), "e_num": abs(s) * prix, "e_qte": abs(s),
                              "s_num": 0.0, "s_qte": 0.0, "max_qte": abs(s), "gain": 0.0, "frais": 0.0,
                              "liquide": False, "levier": abs(s) * prix / marge if marge > 0 else np.nan,
                              "tx_fin": None, "marge_entree": marge}
                    elif abs(s) > abs(p):
                        tr["e_num"] += (abs(s) - abs(p)) * prix; tr["e_qte"] += abs(s) - abs(p)
                        tr["max_qte"] = max(tr["max_qte"], abs(s))
                    elif abs(s) < abs(p):
                        tr["s_num"] += (abs(p) - abs(s)) * prix; tr["s_qte"] += abs(p) - abs(s)
                    if s == 0:
                        tr.update(fin=heure, tx_fin=tx); lignes.append(tr); tr = None
                taille = s
            elif ev == "PositionLiquidated":
                if tr is not None:
                    q = abs(taille)
                    tr["s_num"] += q * float(prix); tr["s_qte"] += q
                    tr["gain"] += -ref
                    tr.update(fin=heure, tx_fin=tx, liquide=True); lignes.append(tr); tr = None
                    ref, taille = 0.0, 0.0
                elif lignes and lignes[-1].get("tx_fin") == tx and lignes[-1].get("compte", compte) == compte:
                    lignes[-1]["liquide"] = True
        for x in lignes:
            x.setdefault("compte", compte)
            x.setdefault("generation", gen)
    t = pd.DataFrame(lignes)
    if not len(t):
        return pd.DataFrame(columns=COLONNES)
    t["sortie"] = np.where(t["liquide"], "liquidation", "main")
    t["stop"], t["objectif"] = np.nan, np.nan
    ordres = Path(fichier).with_name("ordres_conditionnels.csv")
    if ordres.exists():
        _stops_kwenta(t, pd.read_csv(ordres, dtype={"compte": str}), nom)
    t["prix_entree"] = t["e_num"] / t["e_qte"]
    t["prix_sortie"] = t["s_num"] / t["s_qte"].where(t["s_qte"] > 0)
    t["volume"] = t["max_qte"] * t["prix_entree"]
    t["debut"] = utc_vers_serveur(pd.to_datetime(t["debut"], unit="s", utc=True))
    t["fin"] = utc_vers_serveur(pd.to_datetime(t["fin"], unit="s", utc=True))
    t["maitre"], t["source"], t["symbole"] = "synthetix_" + t["compte"], "synthetix", "s" + nom
    t["marche"] = {"XAU": "XAUUSD", "XAG": "XAGUSD", "EUR": "EURUSD", "GBP": "GBPUSD", "AUD": "AUDUSD"}.get(nom)
    return t[COLONNES + ["levier", "liquide", "frais", "generation", "sortie", "marge_entree"]].reset_index(drop=True)


def _stops_kwenta(t: pd.DataFrame, o: pd.DataFrame, nom: str) -> None:
    """Stops / objectifs des comptes Kwenta (ordres conditionnels « réduction seule ») : le PREMIER stop placé
    pendant le trade du côté de la perte, le premier ordre limité du côté du gain. Sortie « stop » / « objectif » si
    un tel ordre du compte a été rempli dans les 10 minutes avant la fermeture (l'exécution chez Synthetix vient
    quelques secondes après). En place dans t (heures encore en secondes UTC)."""
    if not len(o) or not len(t):
        return
    o = o.dropna(subset=["heure"]).drop_duplicates(["tx", "index_log"])
    place = o[(o["genre"] == "place") & (o["marche"] == nom) & (o["reduction_seule"].astype(str) == "True")]
    if not len(place):
        return
    types = place.drop_duplicates(["compte", "id_ordre"]).set_index(["compte", "id_ordre"])["type"].to_dict()
    par_compte = {c: g.sort_values("heure") for c, g in place.groupby("compte")}
    rempli = o[o["genre"] == "rempli"]
    rempli = rempli.assign(type=[types.get((c, i)) for c, i in zip(rempli["compte"], rempli["id_ordre"])])
    remplis = {c: g.sort_values("heure") for c, g in rempli.dropna(subset=["type"]).groupby("compte")}
    entree = t["e_num"] / t["e_qte"]
    for k in range(len(t)):
        c = t.at[k, "compte"]
        g = par_compte.get(c)
        if g is None:
            continue
        d, f, sens, pe = t.at[k, "debut"], t.at[k, "fin"], t.at[k, "sens"], entree.iat[k]
        x = g[(g["heure"] >= d - 60) & (g["heure"] <= f)]
        perte = (x["prix_cible"] - pe) * sens < 0
        st = x[(x["type"] == 1) & perte]
        ob = x[(x["type"] == 0) & ~perte]
        if len(st):
            t.at[k, "stop"] = float(st["prix_cible"].iloc[0])
        if len(ob):
            t.at[k, "objectif"] = float(ob["prix_cible"].iloc[0])
        r = remplis.get(c)
        if r is not None and not t.at[k, "liquide"]:
            y = r[(r["heure"] >= f - 600) & (r["heure"] <= f)]
            if len(y):
                t.at[k, "sortie"] = "stop" if y["type"].iloc[-1] == 1 else "objectif"


def lire_tous() -> pd.DataFrame:
    morceaux = []
    for f in sorted((RACINE / "data" / "maitres" / "mql5").glob("*.csv")):
        try:
            morceaux.append(lire_mql5(f))
        except Exception as e:
            print(f"{f.name} : illisible ({type(e).__name__})")
    for f in sorted((RACINE / "data" / "maitres" / "gtrade" / "historiques").glob("*.csv")):
        try:
            morceaux.append(lire_gtrade(f))
        except Exception as e:
            print(f"{f.name} : illisible ({type(e).__name__})")
    for f in sorted((RACINE / "data" / "maitres" / "hyperliquid" / "historiques").glob("0x*.csv")):
        try:
            morceaux.append(lire_hyperliquid(f))
        except Exception as e:
            print(f"{f.name} : illisible ({type(e).__name__})")
    if (RACINE / "data" / "maitres" / "ostium" / "ordres.csv").exists():
        morceaux.append(lire_ostium(RACINE / "data" / "maitres" / "ostium" / "ordres.csv"))
    if (RACINE / "data" / "maitres" / "coolish").exists():
        morceaux.append(lire_coolish())
    return pd.concat(morceaux, ignore_index=True) if morceaux else pd.DataFrame(columns=COLONNES)
