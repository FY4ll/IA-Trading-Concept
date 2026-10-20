"""
scripts/archive_snapshot.py
============================
Instantané complet et vérifiable de l'état du projet (modèles, configs,
état runtime, logs, code source), créé pour LOT 2 phase 0 (archivage
avant toute modification de code) -- notre point de retour en l'absence
d'accès à `git` depuis les outils de l'assistant sur cette machine. Voir
scripts/restore_archive.py pour la restauration, et RAPPORT_LOT2.md pour
le contexte complet.

Produit archive/<AAAAMMJJ_HHMM>_<tag>/ contenant :
  - models/   : copie intégrale (champions, slots, search_state, historique
                des snapshots versionnés -- tout ce que contient models/)
  - config/   : copie intégrale (autonomous.yaml, risk_profiles/*.yaml)
  - logs/     : copie intégrale
  - reports/  : copie intégrale (inclut le rapport du lot 1)
  - data/     : copie SÉLECTIVE -- tout SAUF data/kaggle_gold/ (données de
                marché brutes, ~500 Mo, statiques, non modifiées par ce lot,
                hors de la liste explicite de la phase 0). Couvre donc de
                facto l'état account_guard, les overrides settings_server,
                les logs d'exécution/slippage et la base EpisodicMemory --
                QUAND ces fichiers existent (certains n'existent pas encore
                à ce stade, ex: aucun ordre réel encore loggé).
  - source_pre_lot2.zip : copie complète de src/, scripts/, tests/,
                autonomous_agent.py, config/ (point de retour du CODE).
  - MANIFEST.json : chemin, taille, sha256 et date de CHAQUE fichier
                archivé, métriques connues de chaque champion, et
                "env_version": 1 (état d'avant l'introduction de
                ENV_VERSION=2 en phase 1).

Puis vérifie l'archive (relit chaque sha256) et verrouille chaque fichier
en lecture seule.

Usage : py scripts/archive_snapshot.py [--tag pre_lot2]
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import zipfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TREES_TO_COPY = ["models", "config", "logs", "reports"]

# Données de marché statiques, non modifiées par ce lot, hors de la liste
# explicite de la phase 0 -- exclues pour ne pas dupliquer ~500 Mo à chaque
# archive. Tout le reste de data/ (état runtime, caches, petits fichiers)
# est copié.
DATA_EXCLUDE_DIRS = {"kaggle_gold"}

SOURCE_ITEMS = ["src", "scripts", "tests", "autonomous_agent.py", "config"]

CHAMPION_STYLES = ["M15", "M30", "H1", "H4", "D1"]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_data_selective(dest_data_dir: str):
    src_data_dir = os.path.join(ROOT, "data")
    if not os.path.isdir(src_data_dir):
        return
    for entry in os.listdir(src_data_dir):
        if entry in DATA_EXCLUDE_DIRS:
            continue
        src_path = os.path.join(src_data_dir, entry)
        dst_path = os.path.join(dest_data_dir, entry)
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dst_path)
        else:
            os.makedirs(dest_data_dir, exist_ok=True)
            shutil.copy2(src_path, dst_path)


def _zip_sources(dest_zip_path: str):
    with zipfile.ZipFile(dest_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in SOURCE_ITEMS:
            src_path = os.path.join(ROOT, item)
            if os.path.isfile(src_path):
                zf.write(src_path, arcname=item)
            elif os.path.isdir(src_path):
                for dirpath, dirnames, filenames in os.walk(src_path):
                    # __pycache__ regénéré automatiquement -- pas du code
                    # source, gonflerait le zip pour rien.
                    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                    for fn in filenames:
                        if fn.endswith(".pyc"):
                            continue
                        full = os.path.join(dirpath, fn)
                        arcname = os.path.relpath(full, ROOT)
                        zf.write(full, arcname=arcname)


def _champion_metrics(archive_dir: str) -> dict:
    """Résumé des métriques connues de chaque champion (score, sharpe,
    trades, génération) lu depuis les meta.json déjà copiés -- aperçu
    rapide sans rouvrir chaque meta.json individuellement."""
    out = {}
    models_dir = os.path.join(archive_dir, "models")
    for style in CHAMPION_STYLES + ["demo_champion"]:
        dirname = "demo_champion" if style == "demo_champion" else f"champion_{style}"
        meta_path = os.path.join(models_dir, dirname, "meta.json")
        if not os.path.exists(meta_path):
            continue
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            continue
        metrics = meta.get("metrics") or {}
        out[style] = {
            "generation": meta.get("generation"),
            "score": meta.get("score"),
            "sharpe": metrics.get("sharpe"),
            "n_trades": metrics.get("n_trades"),
            # Absent avant LOT 2 phase 1 -- normal et attendu dans CETTE
            # archive (instantané pré-phase-1).
            "env_version": meta.get("env_version"),
        }
    return out


def build_manifest(archive_dir: str) -> dict:
    entries = []
    for dirpath, dirnames, filenames in os.walk(archive_dir):
        for fn in filenames:
            if fn == "MANIFEST.json":
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, archive_dir).replace(os.sep, "/")
            st = os.stat(full)
            entries.append({
                "path": rel,
                "size_bytes": st.st_size,
                "sha256": _sha256(full),
                "source_mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            })
    entries.sort(key=lambda e: e["path"])
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "env_version": 1,
        "note": ("Instantané pré-LOT 2 : avant introduction de ENV_VERSION=2, "
                 "risk_engine unique, stops en multiples d'ATR, pipeline "
                 "multi-paires. Voir RAPPORT_LOT2.md."),
        "champion_metrics": _champion_metrics(archive_dir),
        "file_count": len(entries),
        "total_size_bytes": sum(e["size_bytes"] for e in entries),
        "files": entries,
    }


def _verify_and_lock(archive_dir: str, manifest: dict):
    """Relit chaque sha256 (garantit que ce qui a été écrit correspond
    bien au manifest) puis verrouille chaque fichier en lecture seule --
    évite qu'une archive-point-de-retour soit modifiée par erreur
    ensuite."""
    for entry in manifest["files"]:
        full = os.path.join(archive_dir, entry["path"].replace("/", os.sep))
        actual = _sha256(full)
        if actual != entry["sha256"]:
            raise RuntimeError(f"Vérification échouée pour {entry['path']} : "
                                f"sha256 relu ne correspond pas au manifest.")
    locked = 0
    for dirpath, dirnames, filenames in os.walk(archive_dir):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            os.chmod(full, stat.S_IREAD)
            locked += 1
    return locked


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", default="pre_lot2")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    archive_dir = os.path.join(ROOT, "archive", f"{ts}_{args.tag}")
    if os.path.exists(archive_dir):
        print(f"ERREUR : {archive_dir} existe déjà.", file=sys.stderr)
        sys.exit(1)
    os.makedirs(archive_dir)

    print(f"Archive : {archive_dir}")
    for tree in TREES_TO_COPY:
        src = os.path.join(ROOT, tree)
        if not os.path.isdir(src):
            print(f"  [!] {tree}/ introuvable, ignoré")
            continue
        print(f"  copie de {tree}/ ...")
        shutil.copytree(src, os.path.join(archive_dir, tree))

    print("  copie sélective de data/ (kaggle_gold/ exclu) ...")
    _copy_data_selective(os.path.join(archive_dir, "data"))

    print("  zip des sources (src/, scripts/, tests/, autonomous_agent.py, config/) ...")
    _zip_sources(os.path.join(archive_dir, "source_pre_lot2.zip"))

    print("  écriture du MANIFEST.json (sha256 de chaque fichier) ...")
    manifest = build_manifest(archive_dir)
    manifest_path = os.path.join(archive_dir, "MANIFEST.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("  vérification (relecture des sha256) + verrouillage en lecture seule ...")
    locked = _verify_and_lock(archive_dir, manifest)

    print(f"\nOK -- {manifest['file_count']} fichiers ({manifest['total_size_bytes'] / 1e6:.1f} Mo), "
          f"{locked} fichiers verrouillés en lecture seule.")
    print(archive_dir)


if __name__ == "__main__":
    main()
