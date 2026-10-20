"""
RÈGLE DE PASSAGE AUTOMATIQUE D'AUREXIS EN DÉMO (09/10/2026, accord de l'utilisateur donné une fois pour toutes).

Chaque matin (tâche « TestIA_RegleDemo », après le verdict de la nuit), trois critères -- tous les trois :
  1. EXAMEN TOURNANT : le champion a été positif sur LES DEUX périodes (ancienne ET récente) lors de ses 10 dernières
     réévaluations d'affilée (journaux de l'entraînement) ;
  2. 12 MOIS CACHÉS : le verdict de la nuit (reports/verdict_12_mois.json) pour CE champion est positif ;
  3. UNE SEMAINE RÉELLE : les 7 derniers examens du jour sont positifs sans challenge raté, ET le compte fictif « à
     blanc » (data/aurexis_live) est positif, sans mur touché, depuis au moins 7 jours.
Tous remplis et mode « blanc » -> mode « démo » (scripts/aurexis_direct.py envoie alors de vrais ordres sur le compte
démo) + notification. En démo : compte fictif à -5 % ou plus, ou mur total touché -> retour « à blanc » + notification.
Chaque matin : une notification courte avec l'avancement des critères.

    python scripts/regle_demo_aurexis.py [--essai]       (cwd = code/ ; --essai : aucune écriture ni notification)
"""
import glob, json, os, re, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DIR = os.path.join("data", "aurexis_live")
NEED_CYCLES, NEED_DAYS, STOP_LOSS_DEMO = 10, 7, -0.05
RE_CHAMP = re.compile(r"\[AUREXIS\] champion r.+valu.+score=")
RE_PER = re.compile(r"\[AUREXIS\] période (\d) : .*note ([+-]?\d+(?:\.\d+)?)")


def champion_streak(log_dir="logs") -> tuple[int, int]:
    """(réévaluations d'affilée positives sur toutes les périodes, réévaluations à deux périodes vues)."""
    evals = []
    for path in sorted(glob.glob(os.path.join(log_dir, "stderr_*.txt")), key=os.path.getmtime):
        cur = None
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if RE_CHAMP.search(line):
                    cur = []
                    evals.append(cur)
                    continue
                m = RE_PER.search(line)
                if m and cur is not None:
                    cur.append(float(m.group(2)))
                elif cur is not None and ("challenge FTMO" in line or "] score=" in line):
                    cur = None                                # fin des résultats du champion (résumé ou 1er candidat)
    evals = [e[:2] for e in evals if len(e) >= 2]
    streak = 0
    for e in reversed(evals):
        if all(n > 0 for n in e):
            streak += 1
        else:
            break
    return streak, len(evals)


def criteria(code_dir=".") -> dict:
    out = {}
    s, n = champion_streak(os.path.join(code_dir, "logs"))
    out["examen_tournant"] = {"ok": s >= NEED_CYCLES, "detail": f"{s}/{NEED_CYCLES} réévaluations positives d'affilée"}
    meta = json.load(open(os.path.join(code_dir, "models", "champion_AUREXIS", "meta.json"), encoding="utf-8"))
    try:
        v = json.load(open(os.path.join(code_dir, "reports", "verdict_12_mois.json"), encoding="utf-8"))
        same = (v.get("champion") or {}).get("generation") == meta.get("generation")
        fid = v.get("compte_fidele_frein")          # 10/10 : compte fidèle (budget, murs, frein) quand il existe
        total = float(fid["compte"]) if fid else float(v.get("compte_total", -1))
        ok = same and total > 0 and not (fid and fid.get("arret") == "total")
        out["douze_mois"] = {"ok": ok, "detail": f"{total:+.1%} sur 12 mois" + (" (compte fidèle)" if fid else "")
                             + ("" if same else " (ancien champion : verdict à refaire)")}
    except (OSError, ValueError):
        out["douze_mois"] = {"ok": False, "detail": "pas encore de verdict"}
    try:
        hist = json.load(open(os.path.join(code_dir, "reports", "examen_du_jour.json"), encoding="utf-8"))["historique"]
        last = hist[-NEED_DAYS:]
        good = [h for h in last if (h.get("compte") or {}).get("compte", 0) > 0
                and not str((h.get("compte") or {}).get("verdict", "")).startswith("RATÉ")]
        ex_ok = len(last) >= NEED_DAYS and len(good) == len(last)
        ex_detail = f"{len(good)}/{NEED_DAYS} examens du jour positifs"
    except (OSError, ValueError, KeyError):
        ex_ok, ex_detail = False, "pas encore d'examen du jour"
    try:
        etat = json.load(open(os.path.join(code_dir, DIR, "etat.json"), encoding="utf-8"))
        debut = json.load(open(os.path.join(code_dir, DIR, "debut.json"), encoding="utf-8"))["debut"]
        jours = (time.time() - float(debut)) / 86400
        perf = float(etat["equity"]) / float(etat["start_equity"]) - 1
        bl_ok = jours >= NEED_DAYS and perf > 0 and etat.get("halted") != "total"
        bl_detail = f"compte à blanc {perf:+.2%} depuis {jours:.1f} jour(s)"
    except (OSError, ValueError, KeyError):
        bl_ok, bl_detail, perf = False, "compte à blanc pas encore démarré", 0.0
    out["semaine_reelle"] = {"ok": ex_ok and bl_ok, "detail": f"{ex_detail}, {bl_detail}"}
    out["_perf_blanc"] = perf
    out["_generation"] = meta.get("generation")
    return out


def current_mode(code_dir=".") -> str:
    try:
        return json.load(open(os.path.join(code_dir, DIR, "mode.json"), encoding="utf-8")).get("mode", "blanc")
    except (OSError, ValueError):
        return "blanc"


def decide(c: dict, mode: str) -> tuple[str, str]:
    """(nouveau mode, raison)."""
    all_ok = all(v["ok"] for k, v in c.items() if not k.startswith("_"))
    if mode == "blanc" and all_ok:
        return "demo", "les trois critères sont remplis"
    if mode == "demo" and c["_perf_blanc"] <= STOP_LOSS_DEMO:
        return "blanc", f"compte en baisse de {c['_perf_blanc']:.1%} : retour à blanc"
    return mode, ""


def main(essai: bool):
    import yaml
    c = criteria()
    mode = current_mode()
    new, why = decide(c, mode)
    lines = [f"{'OK' if v['ok'] else '..'} {k.replace('_', ' ')} : {v['detail']}" for k, v in c.items() if not k.startswith("_")]
    txt = f"AUREXIS démo -- mode {mode}" + (f" -> {new} ({why})" if new != mode else "") + " | " + " | ".join(lines)
    print(txt, flush=True)
    if essai:
        return
    if new != mode:
        os.makedirs(DIR, exist_ok=True)
        json.dump({"mode": new, "depuis": time.strftime("%Y-%m-%d %H:%M"), "raison": why, "criteres": c,
                   "generation": c["_generation"]}, open(os.path.join(DIR, "mode.json"), "w", encoding="utf-8"),
                  indent=1, default=str)
    try:
        from src.notifier import send_alert
        cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
        send_alert(cfg, subject=("AUREXIS PASSE EN DÉMO" if new == "demo" and mode != "demo" else
                                 "AUREXIS revient à blanc" if new == "blanc" and mode == "demo" else
                                 "AUREXIS - critères démo"), message=txt)
    except Exception as e:
        print(f"(notification impossible : {e})", flush=True)


if __name__ == "__main__":
    os.chdir(os.environ.get("REGLE_CODE") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    main("--essai" in sys.argv)
