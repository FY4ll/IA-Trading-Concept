"""LE TALENT DES MAÎTRES DURE-T-IL ? (15/10/2026)

Parmi des milliers de traders, quelques-uns battent le hasard PAR CHANCE (un sur quinze dépasse une force de 1,5 sans
aucun talent). Choisir les « maîtres » sur tout leur historique, c'est donc en partie choisir des chanceux. Le seul
test honnête : couper l'historique de chaque trader en deux moitiés dans le temps, choisir sur la PREMIÈRE, et
regarder ce qu'ils font sur la SECONDE (qu'on n'a pas regardée pour choisir).

- force d'une moitié = somme des gains / racine(somme des carrés) (comme maitres/juge.py), en DOLLARS et aussi en
  gain RAPPORTÉ À LA TAILLE du trade (un gros trade chanceux ne pèse plus tout) ;
- persistance = lien de rang (Spearman) entre la force de la 1re et de la 2de moitié, sur tous les traders ;
- test du choix : force moyenne en 2de moitié des traders retenus sur la 1re (force > 1,5), contre tous les autres.
Si le talent dure, les retenus restent meilleurs en 2de moitié ; sinon le choix des maîtres ne vaut rien.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.maitres.persistance
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from collapsar.donnees.marches import RACINE
from collapsar.maitres.trades import lire_tous

MIN_TRADES = 60
SEUIL = 1.5


def _force(x: pd.Series) -> float:
    s = float((x ** 2).sum())
    return float(x.sum() / np.sqrt(s)) if s > 0 else 0.0


def moities(t: pd.DataFrame, min_trades: int = MIN_TRADES) -> pd.DataFrame:
    t = t.dropna(subset=["gain"]).sort_values("fin")
    t = t.assign(rendement=t["gain"] / t["volume"].where(t["volume"] > 0))
    lignes = []
    for maitre, g in t.groupby("maitre"):
        if len(g) < min_trades:
            continue
        a, b = g.iloc[: len(g) // 2], g.iloc[len(g) // 2:]
        hors_crypto = float((~g["marche"].isin(["BTCUSD", "ETHUSD"]) & g["marche"].notna()).mean())
        lignes.append({"maitre": maitre, "source": g["source"].iloc[0], "trades": len(g), "hors_crypto": hors_crypto,
                       "force_1": _force(a["gain"]), "force_2": _force(b["gain"]),
                       "force_taille_1": _force(a["rendement"].dropna()), "force_taille_2": _force(b["rendement"].dropna())})
    return pd.DataFrame(lignes)


def bilan(m: pd.DataFrame, cle: str = "force") -> dict:
    if len(m) < 10:
        return {"traders": len(m)}
    a, b = m[f"{cle}_1"], m[f"{cle}_2"]
    retenus = a > SEUIL
    rang = float(a.rank().corr(b.rank()))
    return {"traders": int(len(m)), "lien_de_rang": rang,
            "retenus_sur_1re_moitie": int(retenus.sum()),
            "force_2de_moitie_retenus": float(b[retenus].mean()) if retenus.any() else None,
            "force_2de_moitie_autres": float(b[~retenus].mean()),
            "retenus_encore_positifs_pct": float((b[retenus] > 0).mean() * 100) if retenus.any() else None,
            "autres_positifs_pct": float((b[~retenus] > 0).mean() * 100),
            "retenus_encore_au_dessus_du_seuil_pct": float((b[retenus] > SEUIL).mean() * 100) if retenus.any() else None}


def main():
    t = lire_tous()
    m = moities(t)
    sortie = {}
    for nom, sel in [("tous", m), ("hors_crypto", m[m["hors_crypto"] >= 0.5])] + \
                     [(f"source_{s}", m[m["source"] == s]) for s in sorted(m["source"].unique())]:
        sortie[nom] = {"en_dollars": bilan(sel, "force"), "rapporte_a_la_taille": bilan(sel, "force_taille")}
    f = RACINE / "collapsar" / "vie" / "ecole_maitres" / "persistance.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    m.to_csv(f.with_suffix(".csv"), index=False)
    for nom, r in sortie.items():
        for genre, b in r.items():
            if b.get("traders", 0) < 10:
                continue
            print(f"{nom:22s} {genre:20s} traders {b['traders']:5d}  lien {b['lien_de_rang']:+.2f}  retenus "
                  f"{b['retenus_sur_1re_moitie']:4d}  force ensuite {b['force_2de_moitie_retenus'] or 0:+.2f} "
                  f"(autres {b['force_2de_moitie_autres']:+.2f})  encore positifs "
                  f"{b['retenus_encore_positifs_pct'] or 0:.0f} % (autres {b['autres_positifs_pct']:.0f} %)")
    print(f"(enregistré : {f})")


if __name__ == "__main__":
    main()
