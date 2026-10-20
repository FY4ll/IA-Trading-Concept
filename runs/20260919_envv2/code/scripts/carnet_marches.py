"""
CARNET DE RÉSULTATS PAR MARCHÉ d'AUREXIS (09/10/2026, demande de l'utilisateur : « garder un historique de
performance ») -- lecture seule, ne touche pas à l'entraînement.

Relit TOUS les journaux de l'entraînement (logs/stderr_*.txt) : à chaque cycle, le résultat du champion réévalué (et
de chaque candidat passé à l'examen complet) sur chaque marché, avec la période jouée (« examen tournant » depuis le
09/10 15h24 ; avant : période fixe début 2023). Écrit :
  reports/carnet_marches.csv   une ligne par (cycle, rôle, marché) : date, période, rendement en %
  reports/carnet_marches.json  le bilan par marché (champions, périodes tournantes uniquement) : nombre de périodes,
                               part de périodes gagnantes, rendement moyen
Reconstruit tout à chaque lancement (idempotent). Appelé aussi par l'examen du jour.

    python scripts/carnet_marches.py        (cwd = code/)
"""
import glob, json, os, re, sys

LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
REPORTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")
RE_CYCLE = re.compile(r"^(\S+ \S+) .*Cycle d'.volution continue #(\d+)")
RE_WINDOW = re.compile(r"examen tournant de ce cycle : (.*)")
RE_PAIR = re.compile(r"(\d\d/\d\d/\d{4}) -> (\d\d/\d\d/\d{4})")
RE_CHAMP = re.compile(r"\[AUREXIS\] champion r.+valu")
RE_CAND = re.compile(r"\[AUREXIS(?: pop\d+)?\] score=")
RE_MARKETS = re.compile(r"\[AUREXIS\] note or .*?\((.*)\)\s*$")
RE_ITEM = re.compile(r"([A-Z0-9]+(?: miroir)?)(?: p(\d))? ([+-]?\d+(?:\.\d+)?)%")


def parse() -> list:
    rows, seen = [], set()
    files = sorted(glob.glob(os.path.join(LOGS, "stderr_*.txt")), key=os.path.getmtime)
    for path in files:
        cycle, date, windows, role, n_cand = None, None, ["période fixe (début 2023)"], None, 0
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = RE_CYCLE.search(line)
                if m:
                    date, cycle = m.group(1)[:16], int(m.group(2))
                    windows, role, n_cand = ["période fixe (début 2023)"], None, 0
                    continue
                m = RE_WINDOW.search(line)
                if m:
                    windows = [f"{a} -> {b}" for a, b in RE_PAIR.findall(m.group(1))] or windows
                    continue
                if RE_CHAMP.search(line):
                    role = "champion"
                    continue
                if RE_CAND.search(line):
                    n_cand += 1
                    role = f"candidat {n_cand}"
                    continue
                m = RE_MARKETS.search(line)
                if m and cycle is not None and role:
                    key = (cycle, date, role)
                    if key in seen:                       # un cycle interrompu puis relancé : on garde le premier
                        role = None
                        continue
                    seen.add(key)
                    for name, k, val in RE_ITEM.findall(m.group(1)):
                        k = int(k) if k else 1                    # « EURUSD p2 » = période 2 du cycle
                        per = windows[k - 1] if k - 1 < len(windows) else windows[-1]
                        rows.append({"cycle": cycle, "date": date, "periode": per, "role": role,
                                     "marche": name, "rendement_pct": float(val)})
                    role = None
    return rows


def bilan(rows: list) -> dict:
    out = {}
    for r in rows:
        if r["role"] != "champion" or r["periode"].startswith("période fixe") or "miroir" in r["marche"]:
            continue
        b = out.setdefault(r["marche"], {"periodes": 0, "gagnantes": 0, "somme": 0.0})
        b["periodes"] += 1
        b["gagnantes"] += int(r["rendement_pct"] > 0)
        b["somme"] += r["rendement_pct"]
    for b in out.values():
        b["part_gagnante"] = round(b["gagnantes"] / b["periodes"], 3)
        b["rendement_moyen_pct"] = round(b.pop("somme") / b["periodes"], 3)
    return dict(sorted(out.items(), key=lambda kv: (-kv[1]["part_gagnante"], -kv[1]["rendement_moyen_pct"])))


def main():
    rows = parse()
    os.makedirs(REPORTS, exist_ok=True)
    import csv
    with open(os.path.join(REPORTS, "carnet_marches.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cycle", "date", "periode", "role", "marche", "rendement_pct"])
        w.writeheader(); w.writerows(rows)
    b = bilan(rows)
    json.dump({"lignes": len(rows), "cycles": len({r["cycle"] for r in rows}), "bilan_champion_periodes_tournantes": b},
              open(os.path.join(REPORTS, "carnet_marches.json"), "w", encoding="utf-8"), indent=1)
    print(f"{len(rows)} résultats, {len({r['cycle'] for r in rows})} cycles ; périodes tournantes jouées par le champion : "
          f"{max((v['periodes'] for v in b.values()), default=0)}")
    return b


if __name__ == "__main__":
    main()
