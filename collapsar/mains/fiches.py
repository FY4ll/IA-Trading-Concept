"""La fiche de chaque marché FTMO : famille, devise de cotation, frais, levier, frais de nuit.

Compte visé (choix du chef de projet, 13/10/2026) : FTMO « Normal » (en compte financé, pas de position gardée le
week-end). Levier : celui du compte d'essai FTMO Swing MESURÉ le 15/10/2026 (mains/conditions_ftmo.json ; audit du
16/10, défaut 12 : les fiches donnaient 1:100 aux devises et 1:30 aux indices et métaux, plus que le compte mesuré).
- frais : coût d'un trade complet (écart + commission), en part du montant ; devises recalées le 13/10 sur les
  conditions publiques FTMO (~1,3 x), autres marchés : estimations prudentes d'AUREXIS ; à remplacer par les frais
  MESURÉS sur le compte FTMO (essai gratuit) ; les frais fidèles à chaque époque sont dans mains/frais_ftmo.py ;
- levier : devises 1:30, indices et métaux 1:15, pétrole 1:15, gaz 1:9, cryptos 1:1 (compte Swing mesuré, marché par
  marché quand il est relevé ; sinon la valeur de la famille, LEVIER) ;
- frais de nuit : taux annuel payé par une position gardée après le passage de minuit du serveur (23h à Prague),
  triple la nuit du mercredi (devises, métaux) ou du vendredi (indices, énergies, cryptos) : mains/horloge.py ;
  prudent : achat ET vente paient (en réalité certaines positions en reçoivent ; les frais de chaque époque, achat et
  vente séparés, sont dans mains/nuit.py).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

DEVISES = ("EUR", "USD", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD")
# nom des fichiers de données -> nom FTMO, devise de cotation
INDICES = {"USA500IDXUSD": ("US500", "USD"), "USATECHIDXUSD": ("US100", "USD"), "USA30IDXUSD": ("US30", "USD"),
           "DEUIDXEUR": ("GER40", "EUR"), "GBRIDXGBP": ("UK100", "GBP"), "FRAIDXEUR": ("FRA40", "EUR"),
           "EUSIDXEUR": ("EU50", "EUR"), "JPNIDXJPY": ("JP225", "JPY"), "AUSIDXAUD": ("AUS200", "AUD")}
ENERGIES = {"LIGHTCMDUSD": "USOIL", "BRENTCMDUSD": "UKOIL", "GASCMDUSD": "NATGAS"}
METAUX = ("XAUUSD", "XAGUSD")
CRYPTOS = ("BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD")
OBLIGATIONS = {"USTBONDTRUSD": "USBOND"}

FRAIS = {"XAUUSD": 0.00012, "XAGUSD": 0.00060, "US500": 0.00012, "US100": 0.00012, "US30": 0.00012,
         "GER40": 0.00012, "UK100": 0.00016, "FRA40": 0.00016, "EU50": 0.00024, "JP225": 0.00024,
         "AUS200": 0.00024, "USOIL": 0.00060, "UKOIL": 0.00060, "NATGAS": 0.00180, "BTCUSD": 0.00080,
         "ETHUSD": 0.00100, "LTCUSD": 0.00160, "XRPUSD": 0.00160, "USBOND": 0.00030}
MAJEURES = ("EURUSD", "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD")
# compte FTMO Swing mesuré (15/10/2026) ; avant le 16/10 : devise 100, métal 30, indice 30, énergie 10, crypto 2
LEVIER = {"devise": 30.0, "metal": 15.0, "indice": 15.0, "energie": 10.0, "crypto": 1.0, "obligation": 10.0}
NUIT = {"devise": 0.02, "metal": 0.03, "indice": 0.05, "energie": 0.05, "crypto": 0.20, "obligation": 0.03}


CONDITIONS = Path(__file__).with_name("conditions_reelles.json")    # écrit par surveillance/controle_conditions.py
CONDITIONS_FTMO = Path(__file__).with_name("conditions_ftmo.json")  # compte d'essai FTMO Swing, 15/10/2026
MIROIR = "_MIROIR"


@lru_cache(maxsize=1)
def _reelles() -> dict:
    if CONDITIONS.exists():
        return json.loads(CONDITIONS.read_text(encoding="utf-8")).get("marches", {})
    return {}


@lru_cache(maxsize=1)
def _leviers_ftmo() -> dict:
    """Nom FTMO -> levier mesuré sur le compte FTMO (arrondi : 29,99 -> 30)."""
    try:
        d = json.loads(CONDITIONS_FTMO.read_text(encoding="utf-8")).get("marches", {})
    except (FileNotFoundError, ValueError):
        return {}
    return {nom: float(round(m["levier"])) for nom, m in d.items() if m.get("levier")}


@dataclass(frozen=True)
class Fiche:
    fichier: str          # nom dans les données (ex. USA500IDXUSD)
    nom: str              # nom FTMO (ex. US500)
    famille: str
    cotation: str         # devise dans laquelle le prix est exprimé
    frais: float          # trade complet, en part du montant
    levier: float
    nuit_achat: float     # taux annuel des frais de nuit d'une position acheteuse (payé)
    nuit_vente: float     # ... vendeuse
    pas_unites: float     # pas de lot de MT5 (0,01 lot), en unités ; 0 = pas de 100 $ (pas_dollars)
    min_unites: float     # plus petit ordre accepté, en unités (0 = pas de minimum connu)

    @property
    def pas_dollars(self) -> float:
        return 0.0 if self.pas_unites else 100.0

    @property
    def demi_ecart(self) -> float:
        """Ce que coûte un passage d'ordre (la moitié d'un trade complet), en part du prix."""
        return self.frais / 2


def fiche(fichier: str) -> Fiche:
    if fichier.endswith(MIROIR):                       # marché retourné (entraînement) : mêmes conditions
        base = fiche(fichier[:-len(MIROIR)])
        return replace(base, fichier=fichier, nom=base.nom + MIROIR)
    if fichier in INDICES:
        nom, cot = INDICES[fichier]
        fam = "indice"
    elif fichier in ENERGIES:
        nom, cot, fam = ENERGIES[fichier], "USD", "energie"
    elif fichier in METAUX:
        nom, cot, fam = fichier, "USD", "metal"
    elif fichier in CRYPTOS:
        nom, cot, fam = fichier, "USD", "crypto"
    elif fichier in OBLIGATIONS:
        nom, cot, fam = OBLIGATIONS[fichier], "USD", "obligation"
    elif len(fichier) == 6 and fichier[:3] in DEVISES and fichier[3:] in DEVISES:
        nom, cot, fam = fichier, fichier[3:], "devise"
    else:
        raise ValueError(f"marché inconnu : {fichier}")
    # devises (13/10, conditions publiques FTMO : commission 3 $ par lot aller-retour + écart variable serré) :
    # ~0,0045 % sur l'euro-dollar -> 0,006 % simulé pour les grandes paires, 0,012 % pour les croisées (~1,3 x FTMO)
    frais = FRAIS.get(nom, 0.00006 if nom in MAJEURES else 0.00012 if fam == "devise" else None)
    if frais is None:
        raise ValueError(f"frais inconnus pour {nom}")
    # vraies conditions relevées sur le compte (check-up du 13/10/2026) : pour les frais de nuit, le PLUS CHER entre
    # notre estimation et le relevé, sens par sens ; pas de lot et taille minimum du courtier
    r = _reelles().get(nom, {})
    prudent = lambda v: max(NUIT[fam], v) if v is not None else NUIT[fam]
    pas = r.get("pas_unites") or (1000.0 if fam == "devise" else 0.0)
    minimum = r.get("min_unites") or 0.0
    levier = _leviers_ftmo().get(nom, LEVIER[fam])
    return Fiche(fichier, nom, fam, cot, frais, levier, prudent(r.get("nuit_achat")),
                 prudent(r.get("nuit_vente")), float(pas), float(minimum))


def taux_vers_dollar(cotation: str) -> tuple[str | None, bool]:
    """Quel marché donne la conversion d'une devise en dollars : (fichier, inverser ?). USD : (None, False)."""
    if cotation == "USD":
        return None, False
    if cotation in ("EUR", "GBP", "AUD", "NZD"):
        return f"{cotation}USD", False
    return f"USD{cotation}", True               # JPY, CHF, CAD : 1 / USDxxx
