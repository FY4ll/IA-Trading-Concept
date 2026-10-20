"""Les permis par marché tiennent-ils sur l'année cachée ? Permis décidés sur le carnet (examen tournant 2023-2025,
champion depuis le cycle 408), vérifiés sur le verdict des 12 mois cachés (jamais utilisé pour décider)."""
import csv, collections, json, os
os.chdir(r"C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code")
rows = [r for r in csv.DictReader(open("reports/carnet_marches.csv", encoding="utf-8"))
        if r["role"] == "champion" and int(r["cycle"]) >= 408 and "miroir" not in r["marche"]
        and not r["periode"].startswith("période fixe")]
by = collections.defaultdict(list)
for r in rows:
    by[r["marche"]].append(float(r["rendement_pct"]))
win = {m: sum(v > 0 for v in x) / len(x) for m, x in by.items()}
v = json.load(open("reports/verdict_12_mois.json", encoding="utf-8"))
hid = {m: d["rendement"] for m, d in v["marches"].items() if isinstance(d, dict) and "rendement" in d}
for seuil in (0.0, 0.4, 0.5, 0.6):
    perm = [m for m in hid if win.get(m, 0) >= seuil]
    tot = sum(hid[m] for m in perm)
    print(f"permis si gagnant >= {seuil:.0%} des périodes : {len(perm):2d} marchés, 12 mois cachés {tot:+.1%} "
          f"(moyenne {tot / max(1, len(perm)):+.2%} par marché)")
low = [m for m in hid if win.get(m, 1) < 0.4]
print(f"écartés (< 40 %) : {len(low)} marchés, leur total sur les 12 mois cachés {sum(hid[m] for m in low):+.1%} : {low}")
print(f"verdict complet : {v['compte_total']:+.1%}, plus forte baisse {v['baisse_max']:.1%}")
