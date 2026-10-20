"""
Ajoute à AUREXIS tous les marchés FTMO téléchargés (09/10/2026, accord de l'utilisateur) -- entraînement, petit examen
et compte « tous marchés » de la note d'examen. Un marché dont le fichier n'est pas encore téléchargé est ignoré
(avertissement) et rejoint l'entraînement tout seul dès que son fichier arrive.

Mémoire (16 Go) : 30 000 bougies d'entraînement par marché (~15 mois de devises) au lieu de 50 000, 7 000 bougies
d'examen au lieu de 10 000, miroirs (marchés inversés) seulement pour les 11 marchés d'origine.

    python scripts/ajout_marches_ftmo.py        (cwd = code/, Run A ARRÊTÉ ; lancé par boundary_apply_staged.ps1)
"""
import os, shutil, time
import yaml

CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_config_A.yaml"))
FX = "C:/Users/utilisateur/Documents/Test_IA/data/fx_intraday"
NEW = {   # nom FTMO -> fichier Dukascopy
    "AUDCAD": "AUDCAD", "AUDCHF": "AUDCHF", "AUDJPY": "AUDJPY", "AUDNZD": "AUDNZD", "CADCHF": "CADCHF",
    "CADJPY": "CADJPY", "CHFJPY": "CHFJPY", "EURAUD": "EURAUD", "EURCAD": "EURCAD", "EURCHF": "EURCHF",
    "EURGBP": "EURGBP", "EURJPY": "EURJPY", "EURNZD": "EURNZD", "GBPAUD": "GBPAUD", "GBPCAD": "GBPCAD",
    "GBPCHF": "GBPCHF", "GBPJPY": "GBPJPY", "GBPNZD": "GBPNZD", "NZDCAD": "NZDCAD", "NZDCHF": "NZDCHF",
    "NZDJPY": "NZDJPY", "NZDUSD": "NZDUSD", "USDCAD": "USDCAD",
    "US100": "USATECHIDXUSD", "UK100": "GBRIDXGBP", "JP225": "JPNIDXJPY", "FRA40": "FRAIDXEUR", "EU50": "EUSIDXEUR",
    "AUS200": "AUSIDXAUD", "USOIL": "LIGHTCMDUSD", "UKOIL": "BRENTCMDUSD", "NATGAS": "GASCMDUSD",
    "ETHUSD": "ETHUSD", "LTCUSD": "LTCUSD", "XRPUSD": "XRPUSD",
}
ORIGINAL = ["XAUUSD", "EURUSD", "USDJPY", "US500", "GBPUSD", "XAGUSD", "AUDUSD", "USDCHF", "BTCUSD", "US30", "GER40"]


def edit(text: str) -> str:
    def sub(old, new):
        nonlocal text
        assert text.count(old) == 1, f"ancre introuvable : {old!r}"
        text = text.replace(old, new)

    sub("  max_bars_per_market: 50000   # 08/10 : 80000 -> 50000 (10 marchés au lieu de 4, même mémoire)",
        "  max_bars_per_market: 30000   # 09/10 : 50000 -> 30000 (~45 marchés FTMO au lieu de 10 ; ~15 mois de devises chacun)")
    sub("  mirror_max_bars: 20000   # 08/10 : 30000 -> 20000 (11 miroirs au lieu de 5)",
        "  mirror_max_bars: 20000   # 08/10 : 30000 -> 20000 (11 miroirs au lieu de 5)\n"
        "  # 09/10 : miroirs seulement pour les 11 marchés d'origine (les ~35 nouveaux montent ET baissent déjà).\n"
        f"  mirror_markets: [{', '.join(ORIGINAL)}]")
    sub("    max_val_bars: 10000   # 08/10 : 20 examens de marchés au lieu de 9 -> 10 000 bougies chacun",
        "    max_val_bars: 7000   # 09/10 : ~56 examens de marchés -> 7 000 bougies chacun (08/10 : 10 000)")
    sub('    GBPUSD: "C:/Users/utilisateur/Documents/Test_IA/data/kaggle_gbpusd/GBPUSD_m15_data.csv"',
        f'    GBPUSD: "{FX}/GBPUSD_M15.csv"   # 09/10 : Dukascopy (jusqu\'à aujourd\'hui) au lieu du fichier Kaggle')
    anchor = f'    GER40: "{FX}/DEUIDXEUR_M15.csv"'
    lines = [anchor, "    # 09/10 : TOUS les marchés FTMO téléchargés (Dukascopy depuis 2018) -- devises, indices, énergies, cryptos.",
             "    # Fichier absent = ignoré jusqu'à la fin de son téléchargement."]
    lines += [f'    {k}: "{FX}/{v}_M15.csv"' for k, v in NEW.items()]
    sub(anchor, "\n".join(lines))
    cfg = yaml.safe_load(text)
    mm = cfg["multi_market"]
    assert len(mm["markets"]) == 10 + len(NEW) and mm["markets"]["US100"].endswith("USATECHIDXUSD_M15.csv")
    assert mm["max_bars_per_market"] == 30000 and mm["selection"]["max_val_bars"] == 7000
    assert mm["mirror_markets"] == ORIGINAL and mm["markets"]["GBPUSD"].endswith("fx_intraday/GBPUSD_M15.csv")
    return text


def main():
    text = open(CONFIG, encoding="utf-8").read()
    if "mirror_markets:" in text:
        print("Rien à faire : marchés FTMO déjà ajoutés."); return
    new = edit(text)
    shutil.copy(CONFIG, CONFIG + f".bak_marches_{time.strftime('%Y%m%d_%H%M')}")
    open(CONFIG, "w", encoding="utf-8").write(new)
    present = sum(os.path.exists(f"{FX}/{v}_M15.csv") for v in NEW.values())
    print(f"OK : {len(NEW)} marchés FTMO ajoutés ({present} déjà téléchargés, les autres arriveront seuls)")


if __name__ == "__main__":
    main()
