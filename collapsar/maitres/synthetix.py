"""Maîtres de SYNTHETIX (contrats perpétuels sur la chaîne publique Optimism ; 19/10/2026).

Chaque ordre est inscrit sur la chaîne : impossible à truquer, perdants compris. Marchés hors crypto : or (XAU),
argent (XAG), euro (EUR), livre (GBP), dollar australien (AUD). Deux générations :
- « V1 » (FuturesMarket, adresses directes) : or, argent, euro, ouverts le 31/03/2022 ;
- « V2 » (PerpsV2, adresses « proxy » qui émettent les événements) : or, argent, euro, livre, dollar australien,
  ouverts le 06-07/02/2023, fermés le 25/08/2025 (positions closes de force).
Adresses : fichier officiel publish/deployed/mainnet-ovm/deployment.json du paquet `synthetix` (npm).

Source : les ÉVÉNEMENTS de la chaîne lus directement (eth_getLogs) sur des points d'accès publics gratuits, sans clé,
lentement (pause entre deux demandes, rotation si un point refuse). Les index publics de Kwenta (The Graph hébergé,
Satsuma) sont éteints depuis 2024 : vérifié le 19/10/2026.

Fichiers : data/maitres/synthetix/evenements_<MARCHE>.csv (un événement par ligne, montants déjà divisés par 1e18),
data/maitres/synthetix/etat.json (dernier bloc lu par contrat : la collecte reprend où elle s'est arrêtée).
Lecture au format commun : collapsar.maitres.trades.lire_synthetix.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.maitres.synthetix [XAU XAG ...]
"""
from __future__ import annotations

import json
import sys
import time

import pandas as pd
import requests

from collapsar.donnees.marches import RACINE

DOSSIER = RACINE / "data" / "maitres" / "synthetix"
ETAT = DOSSIER / "etat.json"
# 19/10 : seuls ces deux points gratuits gardent tout l'historique (publicnode, 1rpc, nodies : 50 blocs ou clé)
RPC = ["https://mainnet.optimism.io", "https://optimism.drpc.org"]
PAUSE = 0.6
PAS_MAX = 200_000                 # blocs par demande (réduit tout seul si le point d'accès refuse)
# (marché, génération) -> adresse qui émet les événements
CONTRATS = {
    ("XAU", "v1"): "0x4434f56ddBdE28fab08C4AE71970a06B300F8881",
    ("XAG", "v1"): "0xb147C69BEe211F57290a6cde9d1BAbfD0DCF3Ea3",
    ("EUR", "v1"): "0xad44873632840144fFC97b2D1de716f6E2cF0366",
    ("XAU", "v2"): "0x549dbDFfbd47bD5639f9348eBE82E63e2f9F777A",
    ("XAG", "v2"): "0xdcB8438c979fA030581314e5A5Df42bbFEd744a0",
    ("EUR", "v2"): "0x87AE62c5720DAB812BDacba66cc24839440048d1",
    ("GBP", "v2"): "0x1dAd8808D8aC58a0df912aDC4b215ca3B93D6C49",
    ("AUD", "v2"): "0x9De146b5663b82F44E5052dEDe2aA3Fd4CBcDC99",
}
NOTRE_MARCHE = {"XAU": "XAUUSD", "XAG": "XAGUSD", "EUR": "EURUSD", "GBP": "GBPUSD", "AUD": "AUDUSD"}
# fin de lecture : 30/09/2025 (après la fermeture forcée du 25/08/2025) ; bloc calculé (2 s par bloc depuis
# la mise à jour « Bedrock » du 06/06/2023, bloc 105 235 063 à 16:28:23 UTC)
BEDROCK_BLOC, BEDROCK_HEURE = 105_235_063, 1_686_068_903
FIN_HEURE = int(pd.Timestamp("2025-09-30", tz="UTC").timestamp())
FIN_BLOC = BEDROCK_BLOC + (FIN_HEURE - BEDROCK_HEURE) // 2

# ---------------------------------------------------------------------------------------------------------------
# empreinte des événements (keccak-256, celui d'Ethereum ; écrit ici pour ne dépendre d'aucune bibliothèque)
_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
       0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
       0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
       0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
       0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M64 = (1 << 64) - 1


def _rol(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & _M64 if n else x


def keccak256(data: bytes) -> bytes:
    rate = 136
    p = bytearray(data) + b"\x01" + b"\x00" * ((rate - (len(data) + 1) % rate) % rate)
    p[-1] |= 0x80
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(p), rate):
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(p[off + 8 * i: off + 8 * i + 8], "little")
        for rc in _RC:
            c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
            d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
            a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
            b = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    b[y][(2 * x + 3 * y) % 5] = _rol(a[x][y], _ROT[x][y])
            a = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
            a[0][0] ^= rc
    return b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


# événements utiles : nom -> (signature, noms des champs dans l'ordre) ; les champs « indexés » sont toujours les
# premiers (règle des contrats Synthetix) : leur nombre se lit sur l'événement lui-même
EVENEMENTS = {
    "PositionModified": [("PositionModified(uint256,address,uint256,int256,int256,uint256,uint256,uint256,int256)",
                          "id account margin size tradeSize lastPrice fundingIndex fee skew"),
                         ("PositionModified(uint256,address,uint256,int256,int256,uint256,uint256,uint256)",
                          "id account margin size tradeSize lastPrice fundingIndex fee")],
    "PositionLiquidated": [("PositionLiquidated(uint256,address,address,int256,uint256,uint256,uint256,uint256)",
                            "id account liquidator size price flaggerFee liquidatorFee stakersFee"),
                           ("PositionLiquidated(uint256,address,address,int256,uint256,uint256)",
                            "id account liquidator size price fee")],
    "MarginTransferred": [("MarginTransferred(address,int256)", "account marginDelta")],
    "PositionFlagged": [("PositionFlagged(uint256,address,address,uint256,uint256)",
                         "id account flagger price timestamp")],
}
TYPES = {"id": "uint", "account": "address", "liquidator": "address", "flagger": "address", "timestamp": "uint"}
SUJETS: dict[str, tuple[str, list[str]]] = {}
for _nom, _versions in EVENEMENTS.items():
    for _sig, _champs in _versions:
        SUJETS["0x" + keccak256(_sig.encode()).hex()] = (_nom, _champs.split())
COLONNES = ["generation", "bloc", "heure", "tx", "index_log", "evenement", "compte", "id_position", "marge", "taille",
            "taille_ordre", "prix", "frais", "delta_marge", "liquidateur"]


def _mot(m: str, signe: bool) -> int:
    v = int(m, 16)
    return v - (1 << 256) if signe and v >= 1 << 255 else v


def decoder(log: dict, generation: str) -> dict | None:
    s = SUJETS.get(log["topics"][0])
    if s is None:
        return None
    nom, champs = s
    indexes = [t[2:] for t in log["topics"][1:]]
    donnees = log["data"][2:]
    mots = indexes + [donnees[i:i + 64] for i in range(0, len(donnees), 64)]
    if len(mots) < len(champs):
        return None
    v = {}
    for c, m in zip(champs, mots):
        if TYPES.get(c) == "address":
            v[c] = "0x" + m[-40:]
        elif TYPES.get(c) == "uint" or c in ("margin", "lastPrice", "fundingIndex", "fee", "price", "flaggerFee",
                                             "liquidatorFee", "stakersFee"):
            v[c] = _mot(m, False)
        else:
            v[c] = _mot(m, True)
    e = 1e18
    frais = v.get("fee", v.get("flaggerFee", 0) + v.get("liquidatorFee", 0) + v.get("stakersFee", 0))
    return {"generation": generation, "bloc": int(log["blockNumber"], 16),
            "heure": int(log["blockTimestamp"], 16) if log.get("blockTimestamp") else None,
            "tx": log["transactionHash"], "index_log": int(log["logIndex"], 16), "evenement": nom,
            "compte": v["account"].lower(), "id_position": v.get("id"),
            "marge": v["margin"] / e if "margin" in v else None,
            "taille": v["size"] / e if "size" in v else None,
            "taille_ordre": v["tradeSize"] / e if "tradeSize" in v else None,
            "prix": (v.get("lastPrice", v.get("price")) or 0) / e or None,
            "frais": frais / e if frais else 0.0,
            "delta_marge": v["marginDelta"] / e if "marginDelta" in v else None,
            "liquidateur": v.get("liquidator", v.get("flagger"))}


# ---------------------------------------------------------------------------------------------------------------
class Chaine:
    """Points d'accès publics, l'un après l'autre ; on change de point au moindre refus."""

    def __init__(self):
        self.i = 0

    def appel(self, methode: str, params: list, essais: int = 12):
        for k in range(essais):
            url = RPC[self.i % len(RPC)]
            try:
                r = requests.post(url, json={"jsonrpc": "2.0", "id": 1, "method": methode, "params": params},
                                  timeout=90)
                if r.status_code == 429:
                    time.sleep(20 * (k + 1))
                    self.i += 1
                    continue
                d = r.json()
                if "error" not in d:
                    return d["result"]
                err = str(d["error"])
                if any(x in err.lower() for x in ("range", "limit", "too many", "10000", "exceed", "size", "large")):
                    self.i += 1
                    raise TropGros(err)
                print(f"{url} : {err[:160]}", flush=True)
            except TropGros:
                raise
            except Exception as e:
                print(f"{url} : réseau {type(e).__name__}", flush=True)
            self.i += 1
            time.sleep(5 * (k + 1))
        raise RuntimeError("aucun point d'accès public ne répond")


class TropGros(Exception):
    pass


def bloc_de_creation(ch: Chaine, adresse: str, haut: int) -> int:
    bas = 0
    while bas < haut:
        mil = (bas + haut) // 2
        if ch.appel("eth_getCode", [adresse, hex(mil)]) not in ("0x", "0x0"):
            haut = mil
        else:
            bas = mil + 1
        time.sleep(0.15)
    return bas


PAS_SUR = 10_000                  # ce que tous les serveurs du point d'accès officiel acceptent


def collecter(generations: list[str] | None = None) -> None:
    """Une génération à la fois, tous ses marchés dans la même demande (le point d'accès accepte une liste
    d'adresses). Le point d'accès officiel d'Optimism est servi par plusieurs machines : la plupart acceptent
    200 000 blocs par demande, certaines 10 000 seulement -> on réessaie, puis on découpe ce morceau-là."""
    DOSSIER.mkdir(parents=True, exist_ok=True)
    etat = json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else {}
    ch = Chaine()
    sujets = [list(SUJETS)]
    for gen in ("v1", "v2"):
        if generations and gen not in generations:
            continue
        adresses = {adr.lower(): m for (m, g), adr in CONTRATS.items() if g == gen}
        if gen not in etat:
            debut = min(bloc_de_creation(ch, adr, FIN_BLOC) for adr in adresses)
            etat[gen] = {"creation": debut, "suivant": debut}
            ETAT.write_text(json.dumps(etat, indent=1), encoding="utf-8")
        e = etat[gen]
        if e.get("fini"):
            continue
        n, refus = e.get("evenements", 0), 0
        print(f"{gen} : depuis le bloc {e['suivant']} (création {e['creation']}, fin {FIN_BLOC})", flush=True)
        while e["suivant"] <= FIN_BLOC:
            pas = PAS_MAX if refus < 4 else PAS_SUR
            a, b = e["suivant"], min(e["suivant"] + pas - 1, FIN_BLOC)
            try:
                logs = ch.appel("eth_getLogs", [{"address": [*adresses], "fromBlock": hex(a), "toBlock": hex(b),
                                                 "topics": sujets}])
            except TropGros:
                refus += 1
                time.sleep(PAUSE)
                continue
            refus = 0
            lignes = []
            for l in logs:
                x = None if l.get("removed") else decoder(l, gen)
                if x:
                    x["marche"] = adresses[l["address"].lower()]
                    lignes.append(x)
            for x in lignes:                          # point d'accès sans heure dans les événements : on la demande
                if x["heure"] is None:
                    x["heure"] = int(ch.appel("eth_getBlockByNumber", [hex(x["bloc"]), False])["timestamp"], 16)
            if lignes:
                df = pd.DataFrame(lignes)
                for m, g in df.groupby("marche"):
                    f = DOSSIER / f"evenements_{m}.csv"
                    g[COLONNES].to_csv(f, mode="a", header=not f.exists(), index=False)
            n += len(lignes)
            e["suivant"], e["evenements"] = b + 1, n
            ETAT.write_text(json.dumps(etat, indent=1), encoding="utf-8")
            if lignes:
                print(f"{gen} : bloc {b} ({pd.Timestamp(lignes[-1]['heure'], unit='s'):%d/%m/%Y}) {n} événements",
                      flush=True)
            time.sleep(PAUSE)
        e["fini"] = True
        ETAT.write_text(json.dumps(etat, indent=1), encoding="utf-8")
        print(f"{gen} : fini, {n} événements", flush=True)


# ---------------------------------------------------------------------------------------------------------------
# STOPS et OBJECTIFS : Synthetix n'en a pas ; Kwenta (l'interface principale, comptes « smart margin ») les tient
# sous forme d'« ordres conditionnels » (type 0 = à cours limité / objectif, 1 = stop), inscrits par son contrat
# « Events » (adresse 0xc3d16e00... dans deploy-addresses/optimism.json du dépôt smart-margin ; d'autres versions
# existent : on lit donc par le seul nom d'événement, toutes adresses, et on garde nos marchés).
ORDRES = DOSSIER / "ordres_conditionnels.csv"
ETAT_ORDRES = DOSSIER / "etat_ordres.json"        # à part : les deux collectes peuvent tourner en même temps
# 19/10 : les marchés or, argent, devises de V2 ont été retirés en juillet 2024 (SCCP-2127 du 17/07/2024 ; dernier
# trade d'or lu : 09/07/2024) -> les ordres conditionnels ne sont lus que jusqu'au 15/08/2024
FIN_ORDRES = BEDROCK_BLOC + (int(pd.Timestamp("2024-08-15", tz="UTC").timestamp()) - BEDROCK_HEURE) // 2
SIG_PLACE = {"ConditionalOrderPlaced(address,uint256,bytes32,bytes32,int256,int256,uint256,uint8,uint256,bool)":
             "account id gelato marketKey marginDelta sizeDelta targetPrice type desiredFillPrice reduceOnly",
             "ConditionalOrderPlaced(address,uint256,bytes32,int256,int256,uint256,uint8,uint128,bool)":
             "account id marketKey marginDelta sizeDelta targetPrice type priceImpactDelta reduceOnly",
             "ConditionalOrderPlaced(address,uint256,bytes32,int256,int256,uint256,uint8,uint256,bool)":
             "account id marketKey marginDelta sizeDelta targetPrice type priceImpactDelta reduceOnly"}
SIG_REMPLI = {"ConditionalOrderFilled(address,uint256,bytes32,uint256,uint256,uint8)":
              "account id gelato fillPrice keeperFee oracle",
              "ConditionalOrderFilled(address,uint256,uint256,uint256)": "account id fillPrice keeperFee",
              "ConditionalOrderFilled(address,uint256,bytes32,uint256,uint256)": "account id gelato fillPrice keeperFee"}
SIG_ANNULE = {"ConditionalOrderCancelled(address,uint256,bytes32,uint8)": "account id gelato reason",
              "ConditionalOrderCancelled(address,uint256,uint8)": "account id reason"}
CLES = {("s" + m + "PERP").encode().ljust(32, b"\0").hex(): m for m in NOTRE_MARCHE}
ORDRES_SUJETS = {"0x" + keccak256(s.encode()).hex(): (genre, c.split()) for genre, d in
                 (("place", SIG_PLACE), ("rempli", SIG_REMPLI), ("annule", SIG_ANNULE)) for s, c in d.items()}
ORDRES_COLONNES = ["genre", "bloc", "heure", "tx", "index_log", "contrat", "compte", "id_ordre", "marche", "type",
                   "taille_ordre", "prix_cible", "reduction_seule", "prix_rempli"]


def decoder_ordre(log: dict) -> dict | None:
    s = ORDRES_SUJETS.get(log["topics"][0])
    if s is None:
        return None
    genre, champs = s
    donnees = log["data"][2:]
    mots = [t[2:] for t in log["topics"][1:]] + [donnees[i:i + 64] for i in range(0, len(donnees), 64)]
    if len(mots) < len(champs):
        return None
    v = dict(zip(champs, mots))
    e = 1e18
    return {"genre": genre, "bloc": int(log["blockNumber"], 16),
            "heure": int(log["blockTimestamp"], 16) if log.get("blockTimestamp") else None,
            "tx": log["transactionHash"], "index_log": int(log["logIndex"], 16), "contrat": log["address"].lower(),
            "compte": "0x" + v["account"][-40:], "id_ordre": int(v["id"], 16),
            "marche": CLES.get(v.get("marketKey", "")), "type": int(v["type"], 16) if "type" in v else None,
            "taille_ordre": _mot(v["sizeDelta"], True) / e if "sizeDelta" in v else None,
            "prix_cible": int(v["targetPrice"], 16) / e if "targetPrice" in v else None,
            "reduction_seule": bool(int(v["reduceOnly"], 16)) if "reduceOnly" in v else None,
            "prix_rempli": int(v["fillPrice"], 16) / e if "fillPrice" in v else None}


def collecter_ordres() -> None:
    """Ordres conditionnels Kwenta sur nos marchés, de l'ouverture de V2 au retrait des marchés. On garde les « placés » sur nos
    marchés, et les « remplis » / « annulés » des comptes déjà vus (même compte + même numéro d'ordre)."""
    etat = json.loads(ETAT_ORDRES.read_text(encoding="utf-8")) if ETAT_ORDRES.exists() else {}
    e = etat.setdefault("ordres", {"suivant": 72_642_948})       # création des marchés V2 (06/02/2023)
    if e.get("fini"):
        return
    vus = set()
    if ORDRES.exists():
        o = pd.read_csv(ORDRES, usecols=["compte", "id_ordre", "genre"])
        vus = set(zip(o.loc[o["genre"] == "place", "compte"], o.loc[o["genre"] == "place", "id_ordre"]))
    ch, refus, n = Chaine(), 0, e.get("gardes", 0)
    sujets = [list(ORDRES_SUJETS)]
    print(f"ordres : depuis le bloc {e['suivant']}", flush=True)
    while e["suivant"] <= FIN_ORDRES:
        pas = max(PAS_MAX >> (2 * refus), 1000)     # 200 000, 50 000, 12 500, 3 125, puis 1 000 blocs
        a, b = e["suivant"], min(e["suivant"] + pas - 1, FIN_ORDRES)
        try:
            logs = ch.appel("eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(b), "topics": sujets}])
        except TropGros:
            refus = min(refus + 1, 4)
            time.sleep(PAUSE)
            continue
        refus = max(refus - 1, 0)                     # on regrandit doucement après un succès
        garde = []
        for l in logs:
            x = None if l.get("removed") else decoder_ordre(l)
            if x is None:
                continue
            if x["genre"] == "place" and x["marche"]:
                vus.add((x["compte"], x["id_ordre"]))
                garde.append(x)
            elif x["genre"] != "place" and (x["compte"], x["id_ordre"]) in vus:
                garde.append(x)
        for x in garde:                               # point d'accès sans heure dans les événements : on la demande
            if x["heure"] is None:
                x["heure"] = int(ch.appel("eth_getBlockByNumber", [hex(x["bloc"]), False])["timestamp"], 16)
        if garde:
            pd.DataFrame(garde)[ORDRES_COLONNES].to_csv(ORDRES, mode="a", header=not ORDRES.exists(), index=False)
        n += len(garde)
        e["suivant"], e["gardes"] = b + 1, n
        ETAT_ORDRES.write_text(json.dumps(etat, indent=1), encoding="utf-8")
        if garde:
            print(f"ordres : bloc {b} ({pd.Timestamp(garde[-1]['heure'], unit='s'):%d/%m/%Y}) {n} gardés "
                  f"(sur {len(logs)} lus)", flush=True)
        time.sleep(PAUSE)
    e["fini"] = True
    ETAT_ORDRES.write_text(json.dumps(etat, indent=1), encoding="utf-8")
    print(f"ordres : fini, {n} gardés", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["ordres"]:
        collecter_ordres()
    else:
        collecter(sys.argv[1:] or None)
