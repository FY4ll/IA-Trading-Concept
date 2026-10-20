"""Audit : inventaire des journaux sqlite de l'ancien direct (AUREX) pour mesurer le glissement réel."""
import glob
import os
import sqlite3

for f in glob.glob("runs/20260919_envv2/code/data/*.sqlite"):
    c = sqlite3.connect(f)
    print(f, os.path.getsize(f))
    for (n,) in c.execute("select name from sqlite_master where type='table'"):
        cols = [r[1] for r in c.execute(f"pragma table_info({n})")]
        cnt = c.execute(f"select count(*) from {n}").fetchone()[0]
        print("   ", n, cnt, cols[:40])
