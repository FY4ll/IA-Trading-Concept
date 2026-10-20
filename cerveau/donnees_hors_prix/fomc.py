"""Décisions de la Fed (FOMC) 2010 -> 2023, prévues ET exceptionnelles, avec l'HEURE réelle de l'annonce
(fournée 1, fiche F007 ; 20/10/2026).

Source : site officiel de la Fed (gratuit) :
- dates des réunions : https://www.federalreserve.gov/monetarypolicy/fomchistorical<année>.htm (2010-2020) et
  https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (2021-2023) ;
- heure : lue sur CHAQUE communiqué (« For release at 2:00 p.m. EST »), page
  https://www.federalreserve.gov/newsevents/pressreleases/monetary<AAAAMMJJ>a.htm.
  Les communiqués de 2010 à 2015 disent seulement « For immediate release » : heure de l'époque (14h15 ; 12h30 les
  jours de conférence de presse 2011-2012 ; 14h00 depuis le 20/03/2013), source_heure = « usage_epoque_verifie »
  (vérifiée sur Forex Factory, MetaTrader et le saut des prix ; voir `heure_sans_ecrit`).
Pages brutes gardées dans data/hors_prix/fomc/pages/ ; table propre : data/hors_prix/fomc/decisions_fomc.csv.

Colonnes rendues : date (jour de l'annonce, New York), publie (instant de l'annonce, heure du serveur), prevue (réunion
du calendrier publié d'avance : True ; urgence / vote par écrit : False), nature, intitule, heure_ny, source_heure, url.
Les DATES des réunions prévues sont connues longtemps à l'avance (calendrier de l'année publié l'année d'avant) ;
`publie` est l'instant où le CONTENU de la décision devient public. Les réunions exceptionnelles ne sont connues qu'à
`publie` (jamais avant).
Réunions sans aucune annonce publique (conférences téléphoniques du 15/10/2010, 01/08/2011, 16/10/2013, 04/03/2014 ;
réunion annulée des 17-18/03/2020) : absentes (rien n'a été publié).

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m cerveau.donnees_hors_prix.fomc   (re-télécharge et refait la table)
"""
from __future__ import annotations

import re
import time

import pandas as pd
import requests

from cerveau.donnees_hors_prix import DOSSIER, couper, ny_vers_serveur

ICI = DOSSIER / "fomc"
PAGES = ICI / "pages"
TABLE = ICI / "decisions_fomc.csv"
SITE = "https://www.federalreserve.gov"
ENTETE = {"User-Agent": "Mozilla/5.0 (Test_IA recherche personnelle, lecture seule)"}
ANNEES = range(2010, 2024)

# Communiqués 2010 -> 2015 sans heure écrite (« For immediate release ») : heure de l'époque, VÉRIFIÉE le 20/10/2026
# sur trois sources indépendantes (journal usine/travailleur/journal.md) : heure précise de Forex Factory (à 1-8 min
# près, 41 réunions sur 48), calendrier MetaTrader (14 réunions), et saut de prix de l'euro et du yen dans la bougie
# de 15 min de l'annonce (48 sur 48). Règle de l'époque : 14h15 jusqu'au 30/01/2013 ; 12h30 les jours de conférence
# de presse de 2011-2012 ; 14h00 à partir du 20/03/2013.
MIDI_TRENTE = {"2011-04-27", "2011-06-22", "2011-11-02", "2012-01-25", "2012-04-25", "2012-06-20", "2012-09-13",
               "2012-12-12"}


def heure_sans_ecrit(jour: pd.Timestamp) -> str:
    """Heure (New York) d'un communiqué prévu de 2010-2015 dont la page ne donne pas l'heure."""
    if jour.year > 2015:
        raise ValueError(f"{jour:%Y-%m-%d} : pas d'heure écrite après 2015 (inattendu)")
    if f"{jour:%Y-%m-%d}" in MIDI_TRENTE:
        return "12:30"
    return "14:15" if jour <= pd.Timestamp("2013-01-30") else "14:00"

# Annonces EXCEPTIONNELLES (hors calendrier) avec un communiqué public. Les autres conférences téléphoniques n'ont
# rien annoncé. Clé : communiqué ; valeur : (nature, réunion d'origine).
EXCEPTIONNELLES = {
    "monetary20100509a": ("liquidite_devises", "conférence téléphonique du 09/05/2010 (lignes d'échange de dollars)"),
    "monetary20111130a": ("liquidite_devises", "conférence téléphonique du 28/11/2011 (action coordonnée des banques "
                                               "centrales, annoncée le 30/11)"),
    "monetary20191011a": ("bilan", "réunion non prévue du 04/10/2019 (achats de bons du Trésor, annoncés le 11/10)"),
    "monetary20200303a": ("taux_urgence", "réunion non prévue du 02/03/2020 (baisse de 0,5 point)"),
    "monetary20200315a": ("taux_urgence", "réunion non prévue du 15/03/2020 (baisse à 0-0,25 %, dimanche)"),
    "monetary20200319b": ("liquidite_devises", "vote par écrit du 19/03/2020 (lignes d'échange élargies)"),
    "monetary20200323a": ("bilan", "vote par écrit du 23/03/2020 (achats d'actifs sans limite)"),
    "monetary20200331a": ("liquidite_devises", "vote par écrit du 31/03/2020 (pensions pour banques centrales)"),
    "monetary20200827a": ("strategie", "vote par écrit du 27/08/2020 (nouvelle stratégie, ciblage d'inflation "
                                       "moyenne)"),
}


def _get(url: str) -> str:
    for essai in range(4):
        r = requests.get(url, headers=ENTETE, timeout=60)
        if r.status_code == 429:
            time.sleep(30 * (essai + 1))
            continue
        r.raise_for_status()
        return r.text
    raise RuntimeError(f"{url} : trop de refus (429)")


def _page(nom: str, url: str, rafraichir: bool) -> str:
    f = PAGES / nom
    if f.exists() and not rafraichir:
        return f.read_text(encoding="utf-8", errors="replace")
    f.parent.mkdir(parents=True, exist_ok=True)
    t = _get(url)
    f.write_text(t, encoding="utf-8")
    time.sleep(0.5)
    return t


MOIS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                    "september", "october", "november", "december"], 1)}


def _dernier_jour_2010(titre: str) -> pd.Timestamp:
    """« January 26-27 Meeting - 2010 » -> 2010-01-27 ; « March 16 Meeting - 2010 » -> 2010-03-16."""
    m = re.match(r"([A-Za-z]+) (\d+)(?:-(\d+))? Meeting - (\d{4})", titre)
    if not m:
        raise ValueError(titre)
    return pd.Timestamp(int(m.group(4)), MOIS[m.group(1).lower()], int(m.group(3) or m.group(2)))


def _reunions_prevues(rafraichir: bool) -> list[dict]:
    """Les réunions prévues 2010-2023 et l'adresse de leur communiqué."""
    out = []
    for an in range(2010, 2021):
        t = _page(f"fomchistorical{an}.htm", f"{SITE}/monetarypolicy/fomchistorical{an}.htm", rafraichir)
        for bloc in re.split(r'<div class="panel panel-default', t)[1:]:
            h = re.search(r"<h5[^>]*>(.*?)</h5>", bloc, re.S)
            if not h:
                continue
            titre = re.sub(r"\s+", " ", h.group(1)).strip()
            if not re.search(r"\bMeeting\b", titre) or re.search(r"unscheduled|cancelled|notation", titre):
                continue
            liens = re.findall(r'href="[^"]*pressreleases/(monetary\d{8}a)\.htm"[^>]*>\s*Statement\s*<', bloc)
            if liens:
                code = liens[0]
            elif an == 2010:
                code = f"monetary{_dernier_jour_2010(titre):%Y%m%d}a"
            else:
                raise ValueError(f"réunion sans communiqué : {titre}")
            out.append({"code": code, "intitule": f"réunion prévue {titre}"})
    t = _page("fomccalendars.htm", f"{SITE}/monetarypolicy/fomccalendars.htm", rafraichir)
    pos = sorted((m.start(), int(m.group(1))) for m in re.finditer(r"(\d{4}) FOMC Meetings</a></h4>", t))
    for k, (p, an) in enumerate(pos):
        if an not in (2021, 2022, 2023):
            continue
        seg = t[p:pos[k + 1][0] if k + 1 < len(pos) else len(t)]
        for row in re.split(r'<div class="[^"]*row fomc-meeting', seg)[1:]:
            mois = re.search(r"fomc-meeting__month[^>]*><strong>([^<]*)</strong>", row)
            jours = re.search(r"fomc-meeting__date[^>]*>([^<]*)<", row)
            code = re.search(r'href="/newsevents/pressreleases/(monetary\d{8}a)\.htm"', row)
            if not code:
                raise ValueError(f"réunion {an} sans communiqué")
            out.append({"code": code.group(1),
                        "intitule": f"réunion prévue {mois.group(1)} {jours.group(1).strip()} - {an}"})
    return out


def _heure(page: str) -> tuple[pd.Timestamp, str | None]:
    """(jour de l'annonce, « HH:MM » ou None si « For immediate release »)."""
    texte = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)).replace("&nbsp;", " ")
    d = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December) "
                  r"(\d{1,2}), (\d{4})", texte)
    jour = pd.Timestamp(int(d.group(3)), MOIS[d.group(1).lower()], int(d.group(2)))
    h = re.search(r"For release at (\d{1,2}):(\d{2}) ?([ap])\.?m\.? ?(EST|EDT|ET)?", texte, re.I)
    if not h:
        if re.search(r"For immediate release", texte, re.I):
            return jour, None
        raise ValueError("heure introuvable")
    hh = int(h.group(1)) % 12 + (12 if h.group(3).lower() == "p" else 0)
    return jour, f"{hh:02d}:{h.group(2)}"


def telecharger(rafraichir: bool = False) -> pd.DataFrame:
    """Lit les pages officielles (gardées sur disque) et écrit data/hors_prix/fomc/decisions_fomc.csv."""
    lignes = []
    evenements = [dict(e, prevue=True, nature="reunion_prevue") for e in _reunions_prevues(rafraichir)]
    evenements += [{"code": c, "intitule": v[1], "prevue": False, "nature": v[0]} for c, v in EXCEPTIONNELLES.items()]
    for e in evenements:
        url = f"{SITE}/newsevents/pressreleases/{e['code']}.htm"
        jour, heure = _heure(_page(f"communiques/{e['code']}.htm", url, rafraichir))
        if jour != pd.Timestamp(e["code"][8:16]):
            raise ValueError(f"{e['code']} : date de la page {jour:%Y-%m-%d} différente de l'adresse")
        if heure is None:
            if not e["prevue"]:
                raise ValueError(f"{e['code']} : annonce exceptionnelle sans heure écrite")
            heure, source = heure_sans_ecrit(jour), "usage_epoque_verifie"
        else:
            source = "communique"
        lignes.append({"date": jour.date().isoformat(), "heure_ny": heure, "source_heure": source,
                       "prevue": e["prevue"], "nature": e["nature"], "intitule": e["intitule"], "url": url})
    df = pd.DataFrame(lignes).sort_values(["date", "heure_ny"]).reset_index(drop=True)
    df = df[pd.to_datetime(df["date"]).dt.year.isin(list(ANNEES))]
    ICI.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLE, index=False)
    return df


def charger(limite=None, prevues_seulement: bool = False) -> pd.DataFrame:
    """Décisions de la Fed annoncées STRICTEMENT avant `limite` (heure du serveur ; défaut et maximum : 2024-01-01)."""
    if not TABLE.exists():
        raise FileNotFoundError(f"{TABLE} : lancer python -m cerveau.donnees_hors_prix.fomc")
    d = pd.read_csv(TABLE, dtype={"heure_ny": str})
    d["date"] = pd.to_datetime(d["date"])
    d["publie"] = ny_vers_serveur(d["date"] + pd.to_timedelta(d["heure_ny"] + ":00"))
    if prevues_seulement:
        d = d[d["prevue"]]
    cols = ["date", "publie", "prevue", "nature", "intitule", "heure_ny", "source_heure", "url"]
    return couper(d[cols], limite)


if __name__ == "__main__":
    t = telecharger()
    print(t.groupby([pd.to_datetime(t["date"]).dt.year, "prevue"]).size().unstack(fill_value=0))
    print(t["heure_ny"].value_counts())
