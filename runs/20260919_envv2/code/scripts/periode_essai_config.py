"""Période d'essai avant promotion d'AUREXIS (10/10/2026, accord de l'utilisateur) : 4 examens (le cycle gagnant + 3
cycles suivants), promotion seulement si meilleur en cumulé (src/continuous_trainer._trial_verdict)."""
import os, shutil, time
import yaml
CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_config_A.yaml"))


def main():
    t = open(CONFIG, encoding="utf-8").read()
    if "promotion_trial_by_style:" in t:
        print("Rien à faire : période d'essai déjà réglée."); return
    old = "  ftmo_weight_by_style: {AUREXIS: 0.0}\n"
    assert t.count(old) == 1, "ancre ftmo_weight_by_style introuvable"
    t = t.replace(old, old +
                  "  # 10/10 : PÉRIODE D'ESSAI -- le gagnant d'un cycle devient prétendant, repasse l'examen des 3 cycles\n"
                  "  # suivants à côté du champion, promu seulement s'il fait mieux en cumulé (génération 424 promue sur\n"
                  "  # un seul bon tirage, puis négative). 0 ou absent = promotion immédiate.\n"
                  "  promotion_trial_by_style: {AUREXIS: 4}\n")
    assert yaml.safe_load(t)["continuous"]["promotion_trial_by_style"] == {"AUREXIS": 4}
    shutil.copy(CONFIG, CONFIG + f".bak_essai_{time.strftime('%Y%m%d_%H%M')}")
    open(CONFIG, "w", encoding="utf-8").write(t)
    print("OK : période d'essai de 4 examens pour AUREXIS")


if __name__ == "__main__":
    main()
