"""
DEUX PÉRIODES D'EXAMEN PAR CYCLE pour AUREXIS (09/10/2026, accord de l'utilisateur : « les deux examens c'est bon »).

Le champion du cycle 399 avait été promu sur UNE période de début 2024 (+1,24 %/mois, 60 % de réussite FTMO) puis
perdait 29 % sur les 12 mois cachés. Désormais chaque cycle tire une période dans la première moitié de la plage
(01/2023 -> 05/2024) et une dans la seconde (05/2024 -> 09/2025) ; la note est celle de la MOINS BONNE. Mémoire :
5 000 bougies par marché et par période (au lieu de 7 000 pour une seule).

    python scripts/deux_periodes_config.py        (cwd = code/, Run A ARRÊTÉ ; lancé par boundary_apply_staged.ps1)
"""
import os, shutil, time
import yaml

CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_config_A.yaml"))


def edit(text: str) -> str:
    def sub(old, new):
        nonlocal text
        assert text.count(old) == 1, f"ancre introuvable : {old!r}"
        text = text.replace(old, new)
    sub('    rotation: {enabled: true, from: "2023-01-01", to: "2025-09-30", days: 105}',
        '    # 09/10 19h45 : DEUX périodes par cycle (une dans chaque moitié de la plage), note = la moins bonne des deux\n'
        '    rotation: {enabled: true, from: "2023-01-01", to: "2025-09-30", days: 105, windows: 2}')
    sub("    max_val_bars: 7000   # 09/10 : ~56 examens de marchés -> 7 000 bougies chacun (08/10 : 10 000)",
        "    max_val_bars: 5000   # 09/10 19h45 : 2 périodes x ~53 marchés -> 5 000 bougies chacun (avant 7 000, 1 période)")
    cfg = yaml.safe_load(text)
    sel = cfg["multi_market"]["selection"]
    assert sel["rotation"]["windows"] == 2 and sel["max_val_bars"] == 5000
    return text


def main():
    text = open(CONFIG, encoding="utf-8").read()
    if "windows: 2}" in text:
        print("Rien à faire : deux périodes déjà actives."); return
    new = edit(text)
    shutil.copy(CONFIG, CONFIG + f".bak_deux_periodes_{time.strftime('%Y%m%d_%H%M')}")
    open(CONFIG, "w", encoding="utf-8").write(new)
    print("OK : deux périodes d'examen par cycle (la moins bonne compte), 5 000 bougies par marché et par période")


if __name__ == "__main__":
    main()
