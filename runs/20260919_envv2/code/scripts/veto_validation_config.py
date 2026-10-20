"""Ancienne validation (seuils sur l'or seul) : plus de veto sur les promotions d'AUREXIS (12/10/2026, accord de
l'utilisateur). continuous.validation_veto_by_style: {AUREXIS: false} -- voir src/continuous_trainer._validation_veto."""
import os, shutil, time
import yaml
CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_config_A.yaml"))


def main():
    t = open(CONFIG, encoding="utf-8").read()
    if "validation_veto_by_style:" in t:
        print("Rien à faire : veto déjà réglé."); return
    old = "  promotion_trial_by_style: {AUREXIS: 4}\n"
    assert t.count(old) == 1, "ancre promotion_trial_by_style introuvable"
    t = t.replace(old, old +
                  "  # 12/10 : l'ancienne validation (seuils sur l'or seul) ne bloque plus les promotions d'AUREXIS -- 12\n"
                  "  # candidats bloqués en une nuit dont un à +2,4 %/+2,5 %/mois sur le compte fidèle. Le juge = compte fidèle\n"
                  "  # + période d'essai ; la démo a sa propre règle (scripts/regle_demo_aurexis.py).\n"
                  "  validation_veto_by_style: {AUREXIS: false}\n")
    assert yaml.safe_load(t)["continuous"]["validation_veto_by_style"] == {"AUREXIS": False}
    shutil.copy(CONFIG, CONFIG + f".bak_veto_{time.strftime('%Y%m%d_%H%M')}")
    open(CONFIG, "w", encoding="utf-8").write(t)
    print("OK : plus de veto de l'ancienne validation pour AUREXIS")


if __name__ == "__main__":
    main()
