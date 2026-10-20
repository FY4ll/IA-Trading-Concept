"""
Progression du nouvel AUREXIS (08/10/2026) : tableau tour par tour lu dans les journaux d'entraînement.

    python scripts/progression_aurexis.py [journaux...]      (cwd = code/ ; défaut : journaux depuis le 08/10 13h12)
"""
import glob, os, re, sys

os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def main(files):
    rows, cur = [], None
    st = dict(candidats=0, elimines_petit_examen=0, examens_complets=0, promotions=0,
              veines_nees=0, veines_progres=0, veines_mortes=0)
    for f in files:
        for line in open(f, encoding="utf-8", errors="ignore"):
            m = re.search(r"=== Cycle d.évolution continue #(\d+)", line)
            if m:
                cur = {"cycle": int(m.group(1)), "t": line[5:16], "best": None, "promo": "", "quick": ""}
                rows.append(cur)
                continue
            if cur is None:
                continue
            m = re.search(r"petit examen \((tirage [^ ]+(?: miroir)?)", line)
            if m:
                cur["quick"] = m.group(1).replace("tirage ", "")
            m = re.search(r"champion réévalué.*score=(-?[\d.]+).*sharpe=(-?[\d.]+) drawdown=([\d.]+)% "
                          r"return=(-?[\d.]+)% trades=(\d+)", line)
            if m:
                cur.update(champ=float(m.group(1)), sh=float(m.group(2)), dd=float(m.group(3)),
                           ret=float(m.group(4)), tr=int(m.group(5)), want=True)
                continue
            m = re.search(r"note or (-?[\d.]+) \| autres marchés (-?[\d.]+)", line)
            if m and cur.get("want"):
                cur.update(gold=float(m.group(1)), oth=float(m.group(2)), want=False)
                continue
            m = re.search(r"\[AUREXIS\] score=(-?[\d.]+)", line)
            if m:
                s = float(m.group(1))
                st["candidats"] += 1
                st["elimines_petit_examen" if s < -5 else "examens_complets"] += 1
                if s >= -5:
                    cur["best"] = s if cur["best"] is None else max(cur["best"], s)
                continue
            m = re.search(r"nouveau champion technique .AUREXIS. \(score=(-?[\d.]+)", line)
            if m:
                cur["promo"] = f"oui ({float(m.group(1)):+.2f})"
                st["promotions"] += 1
            st["veines_nees"] += "NOUVELLE veine" in line
            st["veines_progres"] += "PROGRESSE" in line
            st["veines_mortes"] += "disparaît" in line
    print(f"{'tour':>4} {'jour/heure':>11} {'champion':>8} {'or':>6} {'autres':>6} {'régul.':>6} {'rend.':>7} "
          f"{'baisse':>6} {'trades':>6} {'meilleur':>8}  {'promu':12} petit examen")
    for r in rows:
        if "champ" not in r:
            continue
        b = "" if r["best"] is None else f"{r['best']:+.2f}"
        print(f"{r['cycle']:4d} {r['t']:>11} {r['champ']:+8.2f} {r.get('gold', float('nan')):+6.2f} "
              f"{r.get('oth', float('nan')):+6.2f} {r['sh']:+6.2f} {r['ret']:+6.2f}% {r['dd']:5.1f}% {r['tr']:6d} "
              f"{b:>8}  {r['promo'] or '-':12} {r['quick']}")
    print(st)


if __name__ == "__main__":
    files = sys.argv[1:] or [f for f in sorted(glob.glob("logs/stderr_*.txt"), key=os.path.getmtime)
                             if os.path.getmtime(f) > os.path.getmtime("logs/stderr_1312.txt") - 1]
    main(files)
