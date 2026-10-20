"""
Remet en place le champion AUREXIS du cycle 399 (09/10/2026, incident du cycle 402).

Le champion du cycle 399 (veine « professeur » + vision des tendances : +1,24 %, +1,92 % et +4,04 %/mois sur trois
périodes tirées au hasard, 60 à 98 % de réussite FTMO) a été remplacé au cycle 402 par un candidat qui gagnait de 0,13
point sur la seule période catastrophique en étant 3x pire sur l'autre (-10,9 %/mois contre -3,5 %). La règle est
corrigée (continuous_trainer : il faut aussi ne pas être moins bon en moyenne). Son cerveau avait été mis à l'abri à
18h20 (models/sauvetage_cycle399/AUREXIS_0_2.zip, sa promotion ayant planté avant l'archivage).

Fiche COMPLÈTE (leçon du 08/10) : on part de la fiche actuelle (toutes les clés) et on ne change que l'identité et la
note ; l'entraînement réévalue de toute façon le champion dès le cycle suivant.

    python scripts/restaurer_champion_399.py        (cwd = code/, Run A ARRÊTÉ ; lancé par boundary_apply_staged.ps1)
"""
import json, os, shutil, time

CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CH = os.path.join(CODE, "models", "champion_AUREXIS")
SRC = os.path.join(CODE, "models", "sauvetage_cycle399", "AUREXIS_0_2.zip")


def main():
    meta_path = os.path.join(CH, "meta.json")
    meta = json.load(open(meta_path, encoding="utf-8"))
    if meta.get("restaure_depuis") == "cycle 399":
        print("Rien à faire : champion du cycle 399 déjà en place."); return
    if not os.path.exists(SRC):
        raise SystemExit("ABANDON : cerveau du cycle 399 introuvable")
    stamp = time.strftime("%Y%m%d_%H%M")
    backup = os.path.join(CH, "history", f"remplace_gen{meta.get('generation')}_{stamp}")
    os.makedirs(backup, exist_ok=True)
    for f in ("agent.zip", "meta.json", "norm_stats.json"):
        shutil.copy(os.path.join(CH, f), backup)
    shutil.copy(SRC, os.path.join(CH, "agent.zip"))
    required = {"score", "metrics", "feature_columns", "context_timeframes", "env_version"}
    assert required <= set(meta) and {"sharpe", "max_drawdown", "n_trades"} <= set(meta["metrics"]), "fiche incomplète"
    meta.update(generation=399, score=4.242446002525002, updated_at=time.time(), restaure_depuis="cycle 399",
                origin=f"champion du cycle 399 remis en place le {time.strftime('%d/%m/%Y %H:%M')} (incident du cycle "
                       f"402 : promotion au bruit sur une période catastrophique)")
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), indent=1, default=str)
    print(f"OK : champion du cycle 399 remis en place (gen 402 sauvegardé dans {backup})")


if __name__ == "__main__":
    main()
