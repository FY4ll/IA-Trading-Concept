"""
Active l'EXAMEN TOURNANT d'AUREXIS (09/10/2026, voir src/aurexis_data.rotation_window).

Constat du 09/10 : le champion choisi sur la période d'examen FIXE (début 2023) faisait +0,8 %/mois et 36 % de
réussite au challenge simulé sur cette période ; rejoué sur les 12 derniers mois (jamais vus), il aurait raté 99 %
des challenges. Désormais chaque cycle juge le champion et les candidats sur une période de 105 jours tirée au
hasard entre janvier 2023 et septembre 2025 (or compris) ; le petit examen pioche dans la même plage. Les 12 derniers
mois (octobre 2025 -> aujourd'hui) restent CACHÉS : ils servent au vrai verdict (prédiction, examen du jour).

    python scripts/examen_tournant_config.py        (cwd = code/, Run A ARRÊTÉ ; lancé par boundary_apply_staged.ps1)
"""
import os, shutil, time
import yaml

CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_config_A.yaml"))


def edit(text: str) -> str:
    old = "    max_val_bars: 7000   # 09/10 : ~56 examens de marchés -> 7 000 bougies chacun (08/10 : 10 000)\n"
    assert text.count(old) == 1, "ancre max_val_bars introuvable"
    text = text.replace(old, old +
        "    # 09/10 15h : EXAMEN TOURNANT -- une période de 105 jours tirée au hasard à chaque cycle entre `from` et `to`\n"
        "    # (or compris), au lieu de toujours la même (la sélection s'adaptait à CETTE période : 36 % de réussite au\n"
        "    # challenge dessus, 1 % sur les 12 mois suivants). Après `to` : caché, réservé au vrai verdict.\n"
        "    rotation: {enabled: true, from: \"2023-01-01\", to: \"2025-09-30\", days: 105}\n")
    cfg = yaml.safe_load(text)
    rot = cfg["multi_market"]["selection"]["rotation"]
    assert rot["enabled"] is True and rot["to"] == "2025-09-30" and rot["days"] == 105
    return text


def main():
    text = open(CONFIG, encoding="utf-8").read()
    if "rotation: {enabled: true" in text:
        print("Rien à faire : examen tournant déjà actif."); return
    new = edit(text)
    shutil.copy(CONFIG, CONFIG + f".bak_tournant_{time.strftime('%Y%m%d_%H%M')}")
    open(CONFIG, "w", encoding="utf-8").write(new)
    print("OK : examen tournant actif (105 jours tirés au hasard entre 01/2023 et 09/2025 à chaque cycle)")


if __name__ == "__main__":
    main()
