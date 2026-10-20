"""
scripts/restore_archive.py
============================
Restaure un instantané complet produit par scripts/archive_snapshot.py
(voir son MANIFEST.json). Filet de sécurité en l'absence d'accès à `git`
depuis les outils de l'assistant sur cette machine (voir RAPPORT_LOT2.md,
phase 0).

Vérifie TOUJOURS l'intégrité (sha256 de chaque fichier archivé comparé au
manifest) avant de restaurer quoi que ce soit -- une restauration depuis
une archive corrompue ou incomplète est refusée.

Restaure l'état complet : models/, config/, logs/, reports/, data/ (tels
que copiés dans l'archive -- data/kaggle_gold/ n'y a jamais été inclus,
voir archive_snapshot.py, donc n'est jamais touché par une restauration)
ET le code source (source_pre_lot2.zip -> src/, scripts/, tests/,
autonomous_agent.py, config/).

Usage :
  py scripts/restore_archive.py archive/<horodatage>_pre_lot2 --dry-run
  py scripts/restore_archive.py archive/<horodatage>_pre_lot2
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RESTORABLE_TREES = ["models", "config", "logs", "reports", "data"]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(archive_dir: str) -> dict:
    manifest_path = os.path.join(archive_dir, "MANIFEST.json")
    if not os.path.exists(manifest_path):
        print(f"ERREUR : {manifest_path} introuvable -- ce dossier n'est pas "
              f"une archive valide (produite par archive_snapshot.py).", file=sys.stderr)
        sys.exit(1)
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def _verify_integrity(archive_dir: str, manifest: dict) -> bool:
    ok = True
    for entry in manifest["files"]:
        full = os.path.join(archive_dir, entry["path"].replace("/", os.sep))
        if not os.path.exists(full):
            print(f"  [MANQUANT] {entry['path']}")
            ok = False
            continue
        if _sha256(full) != entry["sha256"]:
            print(f"  [CORROMPU] {entry['path']} (sha256 ne correspond pas au manifest)")
            ok = False
    return ok


def _plan_tree_actions(archive_dir: str, target_root: str):
    actions = []
    for tree in RESTORABLE_TREES:
        src_tree = os.path.join(archive_dir, tree)
        if not os.path.isdir(src_tree):
            continue
        for dirpath, dirnames, filenames in os.walk(src_tree):
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, src_tree)
                dest_rel = os.path.join(tree, rel)
                dest_abs = os.path.join(target_root, dest_rel)
                action = "ÉCRASE" if os.path.exists(dest_abs) else "CRÉE"
                actions.append((dest_rel, action, full, dest_abs))
    return actions


def _plan_zip_actions(archive_dir: str, target_root: str):
    zip_path = os.path.join(archive_dir, "source_pre_lot2.zip")
    if not os.path.exists(zip_path):
        return []
    actions = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            dest_abs = os.path.join(target_root, name)
            action = "ÉCRASE" if os.path.exists(dest_abs) else "CRÉE"
            actions.append((name, action, dest_abs))
    return actions


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("archive_dir", help="Dossier d'archive (ex: archive/20260920_1000_pre_lot2)")
    parser.add_argument("--dry-run", action="store_true", help="Liste ce qui serait écrasé/créé, ne modifie rien")
    parser.add_argument("--target-root", default=ROOT,
                         help="Racine où restaurer (défaut : racine réelle du projet). "
                              "Utilisé pour tester la restauration sur un dossier temporaire "
                              "sans toucher au projet réel.")
    args = parser.parse_args()

    archive_dir = os.path.abspath(args.archive_dir)
    if not os.path.isdir(archive_dir):
        print(f"ERREUR : {archive_dir} n'existe pas.", file=sys.stderr)
        sys.exit(1)

    manifest = _load_manifest(archive_dir)
    print(f"Archive : {archive_dir}")
    print(f"Créée le {manifest['created_utc']} -- env_version={manifest['env_version']} -- "
          f"{manifest['file_count']} fichiers, {manifest['total_size_bytes'] / 1e6:.1f} Mo")

    print("Vérification d'intégrité (sha256) ...")
    if not _verify_integrity(archive_dir, manifest):
        print("\nERREUR : archive corrompue ou incomplète -- restauration annulée.", file=sys.stderr)
        sys.exit(1)
    print("  OK, tous les sha256 correspondent au manifest.")

    target_root = os.path.abspath(args.target_root)
    tree_actions = _plan_tree_actions(archive_dir, target_root)
    zip_actions = _plan_zip_actions(archive_dir, target_root)

    if args.dry_run:
        print(f"\n--dry-run : {len(tree_actions)} fichiers d'état (models/config/logs/reports/data) "
              f"+ {len(zip_actions)} fichiers de code seraient restaurés :\n")
        for dest_rel, action, _, _ in tree_actions:
            print(f"  [{action}] {dest_rel}")
        for name, action, _ in zip_actions:
            print(f"  [{action}] {name}  (depuis source_pre_lot2.zip)")
        print("\nRien n'a été modifié (--dry-run).")
        return

    print(f"\nRestauration de {len(tree_actions)} fichiers d'état ...")
    for dest_rel, action, src_abs, dest_abs in tree_actions:
        os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
        if os.path.exists(dest_abs):
            try:
                os.chmod(dest_abs, 0o666)
            except OSError:
                pass
        shutil.copy2(src_abs, dest_abs)

    zip_path = os.path.join(archive_dir, "source_pre_lot2.zip")
    if os.path.exists(zip_path):
        print(f"Restauration du code depuis {os.path.basename(zip_path)} ...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target_root)

    print(f"\nOK -- {len(tree_actions)} fichiers d'état + {len(zip_actions)} fichiers de code restaurés.")


if __name__ == "__main__":
    main()
