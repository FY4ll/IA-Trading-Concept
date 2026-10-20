"""Une notification par cycle (10/10/2026, demande de l'utilisateur) : fin de cycle seulement, en français simple."""
import os, shutil, time
import yaml
CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_config_A.yaml"))


def main():
    t = open(CONFIG, encoding="utf-8").read()
    if "notify_cycle_start:" in t:
        print("Rien à faire : notifications déjà réglées."); return
    old = "notify_cycle_every_n: 10"
    i = t.find(old)
    assert i >= 0 and t.count(old) == 1, "ancre notify_cycle_every_n introuvable"
    line_start = t.rfind("\n", 0, i) + 1
    indent = t[line_start:i]
    j = t.index("\n", i)
    t = t[:line_start] + f"{indent}# 10/10 : une notification à CHAQUE cycle (fin de cycle, résultats d'AUREXIS en clair), pas de début\n" \
        f"{indent}notify_cycle_every_n: 1\n{indent}notify_cycle_start: false" + t[j:]
    n = yaml.safe_load(t)["notifications"]
    assert n["notify_cycle_every_n"] == 1 and n["notify_cycle_start"] is False
    shutil.copy(CONFIG, CONFIG + f".bak_notif_{time.strftime('%Y%m%d_%H%M')}")
    open(CONFIG, "w", encoding="utf-8").write(t)
    print("OK : une notification par cycle")


if __name__ == "__main__":
    main()