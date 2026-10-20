"""
Activité d'AUREXIS mesurée sur TOUS les marchés (09/10/2026, accord de l'utilisateur).

Avant : ≥ 100 trades sur l'or (période de validation fixe) -- règle de l'époque où AUREXIS ne tradait que l'or. Au
cycle 400, le meilleur candidat jamais mesuré (+4,35 %/mois, 100 % de réussite FTMO) a été écarté pour 65 trades sur
l'or alors qu'il trade ~50 marchés. Désormais : au moins 10 trades par marché EN MOYENNE sur l'examen (deux périodes)
-- toujours impossible de devenir champion en ne faisant rien -- et la note fiable compte les trades de tous les
marchés (seuil 1 000 au total au lieu de 300 sur l'or).

    python scripts/activite_tous_marches.py        (cwd = code/, Run A ARRÊTÉ ; lancé par boundary_apply_staged.ps1)
"""
import os, shutil, time
import yaml

CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_config_A.yaml"))


def edit(text: str) -> str:
    def sub(old, new):
        nonlocal text
        assert text.count(old) == 1, f"ancre introuvable : {old!r}"
        text = text.replace(old, new)
    sub("    AUREXIS: {min_trades: 100, min_market_trades: 200}",
        "    # 09/10 20h : activité mesurée sur TOUS les marchés de l'examen (avant : 100 trades sur l'or -> le meilleur\n"
        "    # candidat du cycle 400 écarté pour 65 trades sur l'or) : au moins 10 trades par marché en moyenne.\n"
        "    AUREXIS: {min_trades: 0, min_market_trades: 0, min_avg_market_trades: 10}")
    sub("    AUREX: 300\n    AUREXIS: 300\n",
        "    AUREX: 300\n    AUREXIS: 1000      # 09/10 : trades de TOUS les marchés de l'examen (avant : or seul, 300)\n")
    cfg = yaml.safe_load(text)
    assert cfg["continuous"]["min_activity_by_style"]["AUREXIS"]["min_avg_market_trades"] == 10
    assert cfg["continuous"]["min_trades_for_confident_score_by_style"]["AUREXIS"] == 1000
    return text


def main():
    text = open(CONFIG, encoding="utf-8").read()
    if "min_avg_market_trades" in text:
        print("Rien à faire : activité déjà mesurée sur tous les marchés."); return
    new = edit(text)
    shutil.copy(CONFIG, CONFIG + f".bak_activite_{time.strftime('%Y%m%d_%H%M')}")
    open(CONFIG, "w", encoding="utf-8").write(new)
    print("OK : activité d'AUREXIS mesurée sur tous les marchés (10 trades par marché en moyenne, confiance 1 000)")


if __name__ == "__main__":
    main()
