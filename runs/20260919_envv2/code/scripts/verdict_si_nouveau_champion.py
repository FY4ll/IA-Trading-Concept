"""VERDICT DES 12 MOIS SEULEMENT POUR UN NOUVEAU CHAMPION (12/10/2026, demande de l'utilisateur : « on n'a pas besoin
du verdict si c'est toujours le même champion »). Tâche Windows « TestIA_Verdict12Mois » toutes les 15 minutes :
  - champion AUREXIS déjà jugé (même génération que reports/verdict_12_mois.json) -> rien ;
  - verdict déjà en cours (data/verdict_en_cours.lock de moins de 3 h) ou maintenance en cours -> rien ;
  - mémoire virtuelle libre < 3 Go -> on réessaie au passage suivant (testé le 12/10 : verdict + cycles en parallèle
    = cycles allongés de quelques minutes, mémoire libre jamais sous 2,6 Go) ;
  - sinon : lance scripts/verdict_12_mois.py (lecture seule, ne sert jamais à choisir le champion) puis envoie le
    résultat sur le téléphone.

    python scripts/verdict_si_nouveau_champion.py           (cwd indifférent)
    python scripts/verdict_si_nouveau_champion.py --essai   (dit seulement ce qu'il ferait)
"""
import json, os, subprocess, sys, time
CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, CODE)
os.chdir(CODE)
LOCK = os.path.join("data", "verdict_en_cours.lock")
LOG = os.path.join("logs", "verdict_12_mois.txt")
MIN_FREE_GB = 3.0


def _gen(path, key=None):
    try:
        d = json.load(open(path, encoding="utf-8"))
        return (d.get(key) or {}).get("generation") if key else d.get("generation")
    except (OSError, ValueError):
        return None


def _free_commit_gb() -> float:
    """Mémoire virtuelle libre (même mesure que le gardien : limite de mémoire engagée - mémoire engagée)."""
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 2 ** 30


def decision() -> str:
    champ = _gen(os.path.join("models", "champion_AUREXIS", "meta.json"))
    judged = _gen(os.path.join("reports", "verdict_12_mois.json"), "champion")
    if champ is None:
        return "rien : champion illisible"
    if champ == judged:
        return f"rien : champion {champ} déjà jugé"
    for lock in (LOCK, os.path.join("data", "maintenance.lock")):
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 3 * 3600:
            return f"rien : {os.path.basename(lock)} présent"
    free = _free_commit_gb()
    if free < MIN_FREE_GB:
        return f"attente : mémoire libre {free:.1f} Go < {MIN_FREE_GB:.0f} Go"
    return f"verdict : nouveau champion {champ} (dernier jugé : {judged})"


def main(essai: bool):
    d = decision()
    stamp = time.strftime("%Y-%m-%d %H:%M")
    if essai or not d.startswith("verdict"):
        print(f"{stamp} {d}")
        return
    open(LOCK, "w").write(stamp)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"\n===== {stamp} {d}\n")
            f.flush()
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            for k in ("PRED_MODELE", "PRED_SORTIE", "PRED_DEPART"):
                env.pop(k, None)
            subprocess.run([sys.executable, "-u", os.path.join("scripts", "verdict_12_mois.py")], cwd=CODE,
                           stdout=f, stderr=subprocess.STDOUT, env=env, check=False)
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass
    try:
        v = json.load(open(os.path.join("reports", "verdict_12_mois.json"), encoding="utf-8"))
        fr = v.get("compte_fidele_frein") or {}
        msg = (f"Verdict 12 mois cachés du champion AUREXIS {v['champion']['generation']} : compte fidèle "
               f"{fr.get('compte', float('nan')) * 100:+.1f} % (plus forte baisse {fr.get('baisse_max', float('nan')) * 100:.1f} %"
               + (", mur touché" if fr.get("arret") else "") + ")")
    except Exception as e:
        msg = f"Verdict 12 mois : résultat illisible ({type(e).__name__})"
    print(f"{stamp} {msg}")
    try:
        import yaml
        from src.notifier import send_alert
        send_alert(yaml.safe_load(open(os.path.join("..", "run_config_A.yaml"), encoding="utf-8")),
                   subject="AUREXIS - verdict 12 mois", message=msg)
    except Exception as e:
        print(f"notification impossible ({type(e).__name__}: {e})")


if __name__ == "__main__":
    main("--essai" in sys.argv)
