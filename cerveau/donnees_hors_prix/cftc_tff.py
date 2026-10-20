"""Positions des grands acteurs sur les contrats à terme de 7 devises (rapport CFTC « Traders in Financial Futures »,
contrats à terme seuls) — fournée 1, fiche F002 (20/10/2026).

Source (gratuite, domaine public) : https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/
index.htm : fin_fut_txt_2006_2016.zip puis fut_fin_txt_<année>.zip (2017 -> 2023), dans data/hors_prix/cftc_tff/.
Contrats gardés (Bourse de Chicago, CME), repérés par leur code CFTC (les noms ont changé en 2022) :
EURO FX 099741, JAPANESE YEN 097741, BRITISH POUND 096742, AUSTRALIAN DOLLAR 232741, SWISS FRANC 092741,
CANADIAN DOLLAR 090741, NZ DOLLAR 112741.
SENS : un contrat est TOUJOURS « la devise contre le dollar » (acheteur du contrat yen = acheteur du yen) ; pour
USDJPY, USDCHF, USDCAD le sens est donc INVERSÉ (colonne `sens_paire` = -1).

Catégories (positions en nombre de contrats) : intermediaires (banques teneuses de marché, « Dealer »), gerants
(gérants d'actifs : caisses de retraite, assureurs, fonds de placement), levier (fonds à effet de levier),
autres (autres déclarés), non_declares (petits). `<cat>_net` = achat - vente.

DATE DE PUBLICATION (`publie`, heure du serveur = New York + 7 h), rien n'est écrit dans les fichiers de la CFTC :
1. Règle : positions du mardi (lundi si le mardi est férié), publiées le VENDREDI 15h30 New York. Chaque jour de
   fermeture de l'État fédéral entre le lendemain des positions et ce vendredi (férié officiel ou fermeture
   exceptionnelle : deuils nationaux, veilles de Noël données) retarde la publication d'un jour ouvré
   (« Federal holidays may delay release by one or two days », page officielle du calendrier).
2. Exceptions OFFICIELLES (`PUBLICATIONS_ANNONCEES`, relevées sur cftc.gov le 20/10/2026 : annonces spéciales,
   communiqués 6745-13 et 7864-19), qui remplacent la règle :
   - arrêt de l'État d'octobre 2013 : rapport du 01/10 publié le 25/10 ; ceux du 08/10 et du 15/10 « pendant la
     semaine du 28/10 » et ceux du 22/10 et du 29/10 « pendant la semaine du 04/11 » : jour exact INCONNU -> règle
     prudente = le VENDREDI de la semaine annoncée (01/11 et 08/11), source « annonce_cftc_fin_de_semaine » ;
   - ARRÊT DE L'ÉTAT 22/12/2018 -> 25/01/2019 : aucune publication du 22/12/2018 au 31/01/2019 ; rattrapage dans
     l'ordre, un rapport le mardi et un le vendredi, du 01/02/2019 au 08/03/2019 (11 rapports, positions du
     24/12/2018 au 05/03/2019), dates confirmées une à une par le calendrier de MetaTrader ;
   - incident informatique ION de février-mars 2023 (7 rapports publiés du 24/02 au 21/03/2023) ;
   - jours fériés particuliers annoncés (12/2014, 07/2015, 12/2018, 12/2020, 06/2021).
3. Vérification (tests) : sur 2010-2023, la date retenue n'est JAMAIS avant la date de publication relevée dans le
   calendrier économique de MetaTrader (data/calendrier/mt5_calendrier_histoire.csv), sauf octobre 2013 où ce
   calendrier a recopié les dates prévues (faux : rien n'est sorti pendant l'arrêt).
Colonne `source_publie` : « regle », « annonce_cftc » ou « annonce_cftc_fin_de_semaine ».

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m cerveau.donnees_hors_prix.cftc_tff   (re-télécharge les fichiers)
"""
from __future__ import annotations

import time
import zipfile

import pandas as pd
import requests

from cerveau.donnees_hors_prix import DOSSIER, couper, feries_us, jour_ouvre_suivant, ny_vers_serveur

ICI = DOSSIER / "cftc_tff"
HISTOIRE = "https://www.cftc.gov/files/dea/history/"
FICHIERS = ["fin_fut_txt_2006_2016.zip"] + [f"fut_fin_txt_{a}.zip" for a in range(2017, 2024)]
HEURE = pd.Timedelta(hours=15, minutes=30)                # New York

# code CFTC -> (devise, paire FTMO, sens de la paire quand on est acheteur du contrat)
CONTRATS = {"099741": ("EUR", "EURUSD", 1), "097741": ("JPY", "USDJPY", -1), "096742": ("GBP", "GBPUSD", 1),
            "232741": ("AUD", "AUDUSD", 1), "092741": ("CHF", "USDCHF", -1), "090741": ("CAD", "USDCAD", -1),
            "112741": ("NZD", "NZDUSD", 1)}
CATEGORIES = {"intermediaires": "Dealer", "gerants": "Asset_Mgr", "levier": "Lev_Money", "autres": "Other_Rept",
              "non_declares": "NonRept"}

# Fermetures de l'État fédéral hors fériés officiels (décrets, deuils nationaux, ouragan Sandy)
FERMETURES_EXCEPTIONNELLES = ["2007-01-02", "2012-10-29", "2012-10-30", "2012-12-24", "2013-12-24", "2014-12-26",
                              "2015-12-24", "2018-12-05", "2018-12-24", "2019-12-24", "2020-12-24"]

# Date des positions -> (jour de publication, source). Relevé sur cftc.gov le 20/10/2026.
PUBLICATIONS_ANNONCEES = {
    # fériés annoncés
    "2014-12-23": ("2014-12-30", "annonce_cftc"),     # fériés des 25 et 26/12/2014
    "2015-06-30": ("2015-07-06", "annonce_cftc"),     # férié du 03/07/2015 (sortie partielle le 03/07 ignorée)
    "2015-12-22": ("2015-12-28", "annonce_cftc"),     # calendrier officiel 2015 (« 28* ») et MetaTrader d'accord
    "2018-12-04": ("2018-12-10", "annonce_cftc"),     # deuil national (G. H. W. Bush) le 05/12/2018
    "2020-12-21": ("2020-12-28", "annonce_cftc"),     # férié supplémentaire du 24/12/2020
    "2021-06-15": ("2021-06-21", "annonce_cftc"),     # nouveau férié du 18/06/2021 (Juneteenth)
    # arrêt de l'État d'octobre 2013 (communiqué 6745-13 du 23/10/2013)
    "2013-10-01": ("2013-10-25", "annonce_cftc"),
    "2013-10-08": ("2013-11-01", "annonce_cftc_fin_de_semaine"),
    "2013-10-15": ("2013-11-01", "annonce_cftc_fin_de_semaine"),
    "2013-10-22": ("2013-11-08", "annonce_cftc_fin_de_semaine"),
    "2013-10-29": ("2013-11-08", "annonce_cftc_fin_de_semaine"),
    # arrêt de l'État 22/12/2018 -> 25/01/2019 (communiqué 7864-19 du 29/01/2019)
    "2018-12-24": ("2019-02-01", "annonce_cftc"),
    "2018-12-31": ("2019-02-05", "annonce_cftc"),
    "2019-01-08": ("2019-02-08", "annonce_cftc"),
    "2019-01-15": ("2019-02-12", "annonce_cftc"),
    "2019-01-22": ("2019-02-15", "annonce_cftc"),
    "2019-01-29": ("2019-02-19", "annonce_cftc"),
    "2019-02-05": ("2019-02-22", "annonce_cftc"),
    "2019-02-12": ("2019-02-26", "annonce_cftc"),
    "2019-02-19": ("2019-03-01", "annonce_cftc"),
    "2019-02-26": ("2019-03-05", "annonce_cftc"),
    "2019-03-05": ("2019-03-08", "annonce_cftc"),
    # incident informatique ION (annonces spéciales de février-mars 2023)
    "2023-01-31": ("2023-02-24", "annonce_cftc"),
    "2023-02-07": ("2023-03-03", "annonce_cftc"),
    "2023-02-14": ("2023-03-08", "annonce_cftc"),
    "2023-02-21": ("2023-03-10", "annonce_cftc"),
    "2023-02-28": ("2023-03-14", "annonce_cftc"),
    "2023-03-07": ("2023-03-16", "annonce_cftc"),
    "2023-03-14": ("2023-03-21", "annonce_cftc"),
}


def telecharger():
    ICI.mkdir(parents=True, exist_ok=True)
    for nom in FICHIERS:
        for essai in range(4):
            r = requests.get(HISTOIRE + nom, headers={"User-Agent": "Mozilla/5.0 (Test_IA recherche personnelle)"},
                             timeout=120)
            if r.status_code == 429:
                time.sleep(30 * (essai + 1))
                continue
            r.raise_for_status()
            (ICI / nom).write_bytes(r.content)
            print(f"{nom} : {len(r.content)} octets", flush=True)
            break
        time.sleep(1)


def _fermetures() -> set:
    return set(feries_us("2005-01-01", "2026-12-31")) | set(pd.to_datetime(FERMETURES_EXCEPTIONNELLES))


def publication_regle(date_positions: pd.Timestamp, fermetures: set | None = None) -> pd.Timestamp:
    """Jour de publication selon la règle (sans les exceptions annoncées)."""
    fer = _fermetures() if fermetures is None else fermetures
    d = pd.Timestamp(date_positions).normalize()
    vendredi = d + pd.Timedelta(days=(4 - d.dayofweek) % 7)
    # jours de travail de la CFTC entre les positions et la publication : mercredi, jeudi, vendredi (positions du
    # lundi quand le mardi est férié : publication le vendredi comme d'habitude, annonce du 21/12/2018)
    mercredi = vendredi - pd.Timedelta(days=2)
    retard = sum(1 for j in pd.date_range(mercredi, vendredi) if j in fer)
    pub = jour_ouvre_suivant(vendredi, fer, inclus=True)       # vendredi férié : déjà un jour de retard
    for _ in range(retard - (1 if vendredi in fer else 0)):
        pub = jour_ouvre_suivant(pub, fer)
    return pub


def publications(dates) -> pd.DataFrame:
    """Pour chaque date de positions : jour de publication et source (règle ou annonce officielle)."""
    fer = _fermetures()
    out = []
    for d in pd.DatetimeIndex(dates):
        cle = f"{d:%Y-%m-%d}"
        if cle in PUBLICATIONS_ANNONCEES:
            jour, source = PUBLICATIONS_ANNONCEES[cle]
            out.append((pd.Timestamp(jour), source))
        else:
            out.append((publication_regle(d, fer), "regle"))
    return pd.DataFrame(out, columns=["jour_publication", "source_publie"])


def _brut() -> pd.DataFrame:
    morceaux = []
    for nom in FICHIERS:
        f = ICI / nom
        if not f.exists():
            raise FileNotFoundError(f"{f} : lancer python -m cerveau.donnees_hors_prix.cftc_tff")
        with zipfile.ZipFile(f) as z:
            d = pd.read_csv(z.open(z.namelist()[0]), low_memory=False, dtype={"CFTC_Contract_Market_Code": str})
        d.columns = [c.strip() for c in d.columns]
        morceaux.append(d)
    d = pd.concat(morceaux, ignore_index=True)
    d["CFTC_Contract_Market_Code"] = d["CFTC_Contract_Market_Code"].str.strip()
    d = d[d["CFTC_Contract_Market_Code"].isin(CONTRATS)]
    # la colonne « Report_Date » change de format selon les fichiers (MM/JJ/AAAA ou AAAA-MM-JJ) : on lit AAMMJJ
    d["date"] = pd.to_datetime(d["As_of_Date_In_Form_YYMMDD"].astype(int).astype(str).str.zfill(6), format="%y%m%d")
    return d.drop_duplicates(["CFTC_Contract_Market_Code", "date"], keep="last")


def charger(limite=None) -> pd.DataFrame:
    """Une ligne par (date des positions, devise), publiée STRICTEMENT avant `limite` (heure du serveur ; défaut et
    maximum : 2024-01-01)."""
    d = _brut()
    out = pd.DataFrame({"date": d["date"].values, "code_cftc": d["CFTC_Contract_Market_Code"].values,
                        "marche_cftc": d["Market_and_Exchange_Names"].str.strip().values})
    out["devise"] = out["code_cftc"].map(lambda c: CONTRATS[c][0])
    out["paire_ftmo"] = out["code_cftc"].map(lambda c: CONTRATS[c][1])
    out["sens_paire"] = out["code_cftc"].map(lambda c: CONTRATS[c][2])
    out["interet_ouvert"] = d["Open_Interest_All"].astype(float).values
    for nom, cat in CATEGORIES.items():
        achat = d[f"{cat}_Positions_Long_All"].astype(float).values
        vente = d[f"{cat}_Positions_Short_All"].astype(float).values
        out[f"{nom}_achat"], out[f"{nom}_vente"], out[f"{nom}_net"] = achat, vente, achat - vente
        if f"{cat}_Positions_Spread_All" in d:
            out[f"{nom}_ecart"] = d[f"{cat}_Positions_Spread_All"].astype(float).values
    jours = sorted(out["date"].unique())
    pub = publications(jours)
    pub["date"] = pd.DatetimeIndex(jours)
    out = out.merge(pub, on="date", how="left")
    out["publie"] = ny_vers_serveur(out["jour_publication"] + HEURE)
    cols = ["date", "publie", "source_publie", "devise", "paire_ftmo", "sens_paire", "code_cftc", "marche_cftc",
            "interet_ouvert"] + [c for c in out.columns if any(c.startswith(n + "_") for n in CATEGORIES)]
    out = out[cols].sort_values(["date", "devise"]).reset_index(drop=True)
    return couper(out, limite)


if __name__ == "__main__":
    telecharger()
