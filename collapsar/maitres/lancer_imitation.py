"""Lance l'école avec maîtres (maitres/imitation.py) sur tous les trades disponibles (maitres/trades.py).

Contrôle honnête : pour chaque maître, ses 20 % de trades les plus RÉCENTS ne servent jamais à apprendre ; on y
mesure si COLLAPSAR retrouve ses gestes (garder / changer) et surtout le SENS de ses entrées (50 % = hasard).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.maitres.lancer_imitation [--epoques 30] [--depart eleve.pt]
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime

import numpy as np
import pandas as pd
import torch

from collapsar.cerveau.humain import TraderHumain
from collapsar.donnees import marches as dm
from collapsar.maitres import imitation as im
from collapsar.maitres.juge import juger_standard
from collapsar.maitres.trades import lire_tous

DOSSIER = dm.RACINE / "collapsar" / "vie" / "ecole_maitres"


def dire(t):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {t}", flush=True)


def coupes(tr: pd.DataFrame, part: float = 0.8) -> dict:
    """Pour chaque maître, la date qui sépare ses 80 % de trades les plus anciens (apprendre, choisir) du reste."""
    return {m: g["debut"].sort_values().iloc[min(math.ceil(len(g) * part), len(g) - 1)]
            for m, g in tr.groupby("maitre") if len(g) >= 2}


def preparer(tr: pd.DataFrame, appareil: str, graine: int = 0, poids: dict | None = None):
    """`poids` : {maître: poids} — seuls les maîtres retenus par le juge, pesant selon leur force contre le hasard."""
    rng = np.random.default_rng(graine)
    poids = poids or {}
    fin_appr, coupe = coupes(tr, 0.7), coupes(tr, 0.8)
    lots = []
    for marche, g in tr.dropna(subset=["marche"]).groupby("marche"):
        if len(g) < 30 or not (dm.DOSSIER_M15 / f"{marche}_M15.csv").exists() and marche != "XAUUSD":
            continue
        c = im.classe_marche(marche, appareil)
        for maitre, gm in g.groupby("maitre"):
            gm = gm.sort_values("debut").reset_index(drop=True)
            if maitre not in coupe:
                continue
            # apprendre (70 % les plus anciens), validation (10 % : choisir quand s'arrêter), contrôle (20 % les
            # plus récents : jamais vus, ni pour choisir les maîtres ni pour choisir l'arrêt)
            avant, ap = gm["debut"] < coupe[maitre], gm["debut"] < fin_appr[maitre]
            for nom, part in (("apprend", gm[ap]), ("validation", gm[avant & ~ap]), ("controle", gm[~avant])):
                ex = im.exemples(c, part.reset_index(drop=True), rng, poids.get(maitre, 1.0))
                if not len(ex):
                    continue
                idx, vm, vc = im.etats(c, ex)
                _, x = c.g.voir(idx.reshape(-1))
                taille = torch.exp(x[:, c.i_jour] * 3 - 6).reshape(len(ex), 1)
                lots.append({"marche": marche, "maitre": maitre, "partie": nom, "classe": c, "idx": idx, "vm": vm,
                             "vc": vc, "cibles": im.cibles(c, ex, taille), "n": len(ex)})
        dire(f"{marche} : {len(g)} trades -> exemples prêts")
    return lots


@torch.no_grad()
def mesurer(agent, lots, partie):
    """Moyennes sur tous les maîtres (pondérées par le nombre d'exemples) : geste juste, sens des entrées juste."""
    agent.eval()
    somme = {"geste_juste": [0.0, 0.0], "sens_entree_juste": [0.0, 0.0], "juste_achats": [0.0, 0.0],
             "juste_ventes": [0.0, 0.0]}
    for l in [x for x in lots if x["partie"] == partie]:
        _, m = im.perte(agent, l["classe"], l["idx"], l["vm"], l["vc"], l["cibles"])
        poids = {"juste_achats": m["achats"], "juste_ventes": m["ventes"]}
        for k in somme:
            if np.isfinite(m[k]):
                somme[k][0] += m[k] * poids.get(k, l["n"])
                somme[k][1] += poids.get(k, l["n"])
    r = {k: round(s / max(n, 1e-9), 3) for k, (s, n) in somme.items()}
    r["sens_equilibre"] = round((r["juste_achats"] + r["juste_ventes"]) / 2, 3)
    r["part_achats"] = round(somme["juste_achats"][1] / max(somme["juste_achats"][1] + somme["juste_ventes"][1], 1), 3)
    return r


def _rang(tr: pd.DataFrame) -> pd.Series:
    """Place de chaque trade dans l'historique de son maître, de 0 (le plus ancien) à 1."""
    g = tr.sort_values("debut").groupby("maitre")
    return (g.cumcount() / g["debut"].transform("size")).reindex(tr.index)


def choisir(tr: pd.DataFrame, part: float = 0.8) -> tuple[dict, pd.DataFrame]:
    """Les maîtres sont choisis sur la PREMIÈRE partie de leur historique seulement (la même qui sert à apprendre) :
    le contrôle (leurs 20 % les plus récents) n'a jamais servi à les choisir. Juge en gain rapporté à la taille."""
    passe = tr[_rang(tr) < part]
    v = juger_standard(passe, rapporte_a_la_taille=True)
    retenus = v[v["maitre_retenu"]]
    return {m: float(min(f, 5.0)) for m, f in zip(retenus["maitre"], retenus["force"])}, v


def bilan_controle(tr: pd.DataFrame, poids: dict, part: float = 0.8) -> dict:
    """Ce que les maîtres choisis ont fait ENSUITE (leurs 20 % les plus récents, jamais vus pour les choisir)."""
    futur = tr[_rang(tr) >= part]
    v = juger_standard(futur, rapporte_a_la_taille=True)
    r, a = v[v["maitre"].isin(poids)], v[~v["maitre"].isin(poids)]
    return {"maitres_choisis": len(r), "force_ensuite_choisis": round(float(r["force"].mean()), 2) if len(r) else None,
            "encore_gagnants_pct": round(float((r["force"] > 0).mean() * 100)) if len(r) else None,
            "force_ensuite_autres": round(float(a["force"].mean()), 2) if len(a) else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epoques", type=int, default=30)
    ap.add_argument("--depart", default=None)
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--paquet", type=int, default=256)
    args = ap.parse_args()
    DOSSIER.mkdir(parents=True, exist_ok=True)
    tr = lire_tous()
    poids, verdicts = choisir(tr)
    dire(f"maîtres retenus par le juge (sur leur passé seulement) : {len(poids)} sur {len(verdicts)} ; "
         f"ce qu'ils ont fait ENSUITE : {json.dumps(bilan_controle(tr, poids), ensure_ascii=False)}")
    tr = tr[tr["maitre"].isin(poids)]
    dire(f"{len(tr)} trades ; marchés : {tr['marche'].value_counts().to_dict()}")
    lots = preparer(tr, args.appareil, poids=poids)
    agent = TraderHumain().to(args.appareil)
    if args.depart:
        agent.charger(torch.load(args.depart, map_location=args.appareil, weights_only=False)["cerveau"])
    opt = torch.optim.AdamW(agent.parameters(), lr=3e-4, weight_decay=1e-4)
    dire(f"avant : contrôle {json.dumps(mesurer(agent, lots, 'controle'), ensure_ascii=False)}")
    appr = [l for l in lots if l["partie"] == "apprend"]
    rng = np.random.default_rng(1)
    meilleur, etat_meilleur, ep_meilleur = -1.0, None, 0
    for ep in range(args.epoques):
        agent.train()
        total, n = 0.0, 0
        # tous les maîtres et tous les marchés MÉLANGÉS d'un pas à l'autre (un maître après l'autre = il oublie)
        pas = []
        for l in appr:
            ordre = torch.randperm(l["n"], device=l["idx"].device)
            pas += [(l, ordre[d:d + args.paquet]) for d in range(0, l["n"], args.paquet)]
        for k in rng.permutation(len(pas)):
            l, i = pas[k]
            cib = {c: v[i] for c, v in l["cibles"].items()}
            p, _ = im.perte(agent, l["classe"], l["idx"][i], l["vm"][i], l["vc"][i], cib)
            opt.zero_grad(set_to_none=True)
            p.backward()
            torch.nn.utils.clip_grad_norm_(agent.parameters(), 1.0)
            opt.step()
            total += float(p)
            n += 1
        val = mesurer(agent, lots, "validation")
        dire(f"époque {ep + 1} : perte {total / max(n, 1):.3f} | apprend {json.dumps(mesurer(agent, lots, 'apprend'), ensure_ascii=False)}"
             f" | validation {json.dumps(val, ensure_ascii=False)}")
        if val["sens_equilibre"] > meilleur:
            meilleur, ep_meilleur = val["sens_equilibre"], ep + 1
            etat_meilleur = {k: v.detach().clone() for k, v in agent.state_dict().items()}
    agent.load_state_dict(etat_meilleur)
    dire(f"arrêt retenu (sur la validation) : époque {ep_meilleur} ; CONTRÔLE jamais vu : "
         f"{json.dumps(mesurer(agent, lots, 'controle'), ensure_ascii=False)}")
    torch.save({"cerveau": agent.state_dict(), "source": "école avec maîtres", "maitres": sorted(poids),
                "epoque": ep_meilleur}, DOSSIER / "eleve.pt")
    dire(f"élève sauvé : {DOSSIER / 'eleve.pt'}")


if __name__ == "__main__":
    main()
