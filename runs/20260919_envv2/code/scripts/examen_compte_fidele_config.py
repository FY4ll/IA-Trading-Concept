"""Examen sur le compte fidèle (11/10/2026, accord de l'utilisateur) : note_argent_by_style.AUREXIS.compte_fidele = true
(src/note_argent.note_compte_fidele). Le prétendant en cours, noté avec l'ancienne note, est retiré (essai non
comparable) -- il est mis de côté dans models/ecartes_AUREXIS/."""
import os, re, shutil, time
import yaml
CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG = os.path.join(CODE, "..", "run_config_A.yaml")


def main():
    t = open(CONFIG, encoding="utf-8").read()
    if "compte_fidele: true" in t:
        print("Rien à faire : compte fidèle déjà actif.")
    else:
        old = "    AUREXIS: {month_unit: 0.01, ftmo_weight: 5.0, gain_cap: 1.5, dd_wall: 0.06, dd_slope: 25.0}\n"
        assert t.count(old) == 1, "ancre note_argent_by_style introuvable"
        new = ("  # 11/10 : note calculée sur le COMPTE FIDÈLE (budget de risque 4 %, murs FTMO, frein, ordre réel des\n"
               "  # trades) -- verdict de la nuit : 79 % des trades du champion 442 refusés par le vrai compte.\n"
               "    AUREXIS: {month_unit: 0.01, ftmo_weight: 5.0, gain_cap: 1.5, dd_wall: 0.06, dd_slope: 25.0,\n"
               "              compte_fidele: true}\n")
        t = t.replace(old, new)
        assert yaml.safe_load(t)["continuous"]["note_argent_by_style"]["AUREXIS"]["compte_fidele"] is True
        shutil.copy(CONFIG, CONFIG + f".bak_fidele_{time.strftime('%Y%m%d_%H%M')}")
        open(CONFIG, "w", encoding="utf-8").write(t)
        print("OK : examen sur le compte fidèle")
    p = os.path.join(CODE, "models", "pretendant_AUREXIS")
    if os.path.isdir(p):
        dst = os.path.join(CODE, "models", "ecartes_AUREXIS", f"pretendant_ancienne_note_{time.strftime('%Y%m%d_%H%M')}")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(p, dst)
        print("OK : prétendant noté à l'ancienne mis de côté")


if __name__ == "__main__":
    main()
