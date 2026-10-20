"""Compte partagé à l'entraînement d'AUREXIS (11/10/2026, demande de l'utilisateur) : environment.training_only.AUREXIS
reçoit account_shared: true (les 8 parties en parallèle tradent un seul compte, src/shared_account.py) et
account_episode_bars: 2000 (parties coupées à ~3 semaines de bougies de 15 min pour garder les horloges proches)."""
import os, shutil, time
import yaml
CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_config_A.yaml"))


def main():
    t = open(CONFIG, encoding="utf-8").read()
    if "account_shared:" in t:
        print("Rien à faire : compte partagé déjà actif."); return
    old = "              ftmo_death_penalty: 20.0, ftmo_success_bonus: 5.0}\n"
    assert t.count(old) == 1, "ancre training_only.AUREXIS introuvable"
    t = t.replace(old,
        "              ftmo_death_penalty: 20.0, ftmo_success_bonus: 5.0,\n"
        "              # 11/10 : COMPTE PARTAGÉ -- les 8 parties en parallèle tradent UN compte (marchés différents aux\n"
        "              # mêmes dates, budget pris par ses propres positions), parties coupées à 2000 bougies.\n"
        "              account_shared: true, account_episode_bars: 2000}\n")
    to = yaml.safe_load(t)["environment"]["training_only"]["AUREXIS"]
    assert to["account_shared"] is True and to["account_episode_bars"] == 2000 and to["ftmo_rules"] is True
    shutil.copy(CONFIG, CONFIG + f".bak_compte_partage_{time.strftime('%Y%m%d_%H%M')}")
    open(CONFIG, "w", encoding="utf-8").write(t)
    print("OK : compte partagé à l'entraînement d'AUREXIS")


if __name__ == "__main__":
    main()
