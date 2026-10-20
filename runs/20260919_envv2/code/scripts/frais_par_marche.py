"""
Frais réalistes par marché pour AUREXIS (09/10/2026) : coût de référence de son environnement = celui de l'or
(0,012 % par trade complet au lieu de 0,02 %) ; chaque autre marché paie ses propres frais (src/aurexis_data.py,
COST_ROUND_TRIP, colonne `cost_multiplier` invisible pour l'IA). AUREX (or seul, gelé) n'est pas touché.

    python scripts/frais_par_marche.py        (cwd = code/, Run A ARRÊTÉ ; lancé par boundary_apply_staged.ps1)
"""
import os, shutil, time
import yaml

CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_config_A.yaml"))


def edit(text: str) -> str:
    old = ("      reward_type: trade_argent\n"
           "      learn_position_size: true\n")
    assert text.count(old) == 1, "ancre AUREXIS introuvable"
    text = text.replace(old, old + "      # 09/10 14h : frais réalistes -- or 0,012 % par trade complet (avant 0,02 % pour tous les marchés) ; les\n"
                                   "      # autres marchés paient leurs propres frais (src/aurexis_data.py, COST_ROUND_TRIP).\n"
                                   "      transaction_cost: 0.00012\n")
    cfg = yaml.safe_load(text)
    assert cfg["environment"]["style_overrides"]["AUREXIS"]["transaction_cost"] == 0.00012
    assert "transaction_cost" not in cfg["environment"]["style_overrides"]["AUREX"], "AUREX inchangé"
    return text


def main():
    text = open(CONFIG, encoding="utf-8").read()
    if "transaction_cost: 0.00012" in text:
        print("Rien à faire : frais déjà réglés."); return
    new = edit(text)
    shutil.copy(CONFIG, CONFIG + f".bak_frais_{time.strftime('%Y%m%d_%H%M')}")
    open(CONFIG, "w", encoding="utf-8").write(new)
    print("OK : frais réalistes par marché pour AUREXIS (or 0,012 % par trade complet)")


if __name__ == "__main__":
    main()
