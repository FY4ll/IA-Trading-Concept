"""AUREXIS apprend sur la carte graphique (10/10/2026, demande de l'utilisateur : « profiter du GPU »). Mesuré :
356 pas/s sur la carte contre 132 sur le processeur (x2,7), 455 Mo de carte par candidat (4 en parallèle ~1,8 Go sur
6). Les programmes sans carte rechargent le cerveau sur le processeur (src/agent.py, tests/test_device_gpu.py)."""
import os, shutil, time
import yaml
CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_config_A.yaml"))


def main():
    t = open(CONFIG, encoding="utf-8").read()
    old = "    AUREXIS: {learning_rate: 0.0002, n_epochs: 8, ent_coef: 0.01, clip_range: 0.2, target_kl: 0.03, lstm_hidden_size: 512}"
    if "lstm_hidden_size: 512, device: cuda}" in t:
        print("Rien à faire : AUREXIS apprend déjà sur la carte graphique."); return
    assert t.count(old) == 1, "ancre agent.style_overrides.AUREXIS introuvable"
    t = t.replace(old, "    # 10/10 : apprentissage sur la carte graphique (x2,7 mesuré)\n" + old[:-1] + ", device: cuda}")
    assert yaml.safe_load(t)["agent"]["style_overrides"]["AUREXIS"]["device"] == "cuda"
    shutil.copy(CONFIG, CONFIG + f".bak_gpu_{time.strftime('%Y%m%d_%H%M')}")
    open(CONFIG, "w", encoding="utf-8").write(t)
    print("OK : AUREXIS apprend sur la carte graphique")


if __name__ == "__main__":
    main()