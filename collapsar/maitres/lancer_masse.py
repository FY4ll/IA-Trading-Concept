"""LE PRÉAPPRENTISSAGE SUR LA MASSE (15/10/2026, idée du chef de projet : « comme toi tu as appris : mes fautes
veulent dire quelque chose ; il faut qu'elle bouffe de l'information »).

Comme un modèle de langage apprend d'abord à deviner le mot suivant dans des milliards de textes (bons et mauvais),
COLLAPSAR apprend d'abord à deviner les GESTES de TOUTE la foule des traders (Ostium, gTrade, Hyperliquid, Paul Wei :
~410 000 trades, ~15 000 traders, gagnants ET perdants, sans aucun tri) : entrer, acheter ou vendre, tenir, sortir,
où mettre le stop, quand revenir. Elle n'en copie pas les erreurs : elle doit en COMPRENDRE la logique. L'argent,
c'est ensuite l'école des mille mondes.

Honnêteté : coupe dans le TEMPS pour tout le monde : apprendre avant le 01/03/2026, validation (choix de l'arrêt)
03-04/2026, CONTRÔLE 05 -> 10/2026 (jamais vu). Le sens est mesuré ÉQUILIBRÉ (achats et ventes à part : « toujours acheter »
= 50 %). Puis `maitres/sonde_prix.py` vérifie si ces yeux-là lisent mieux le PRIX que des yeux neufs.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.maitres.lancer_masse [--epoques 3]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

import numpy as np
import pandas as pd
import torch

from collapsar.cerveau.humain import TraderHumain
from collapsar.donnees import marches as dm
from collapsar.maitres import imitation as im
from collapsar.maitres.lancer_imitation import mesurer
from collapsar.maitres.trades import lire_tous

DOSSIER = dm.RACINE / "collapsar" / "vie" / "ecole_maitres"
# la foule d'Ostium est surtout active depuis fin 2025 : la coupure laisse la majorité des exemples à l'apprentissage
FIN_APPRENTISSAGE, FIN_VALIDATION = pd.Timestamp("2026-03-01"), pd.Timestamp("2026-05-01")
MORCEAU = 20_000                      # états calculés par morceaux (les graphiques de 400 000 états ne tiennent pas)


def dire(t):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {t}", flush=True)


def _lot(c, ex: pd.DataFrame, marche: str, partie: str) -> dict:
    idx, vm, vc, tailles = [], [], [], []
    for d in range(0, len(ex), MORCEAU):
        morceau = ex.iloc[d:d + MORCEAU].reset_index(drop=True)
        i, m, v = im.etats(c, morceau)
        _, x = c.g.voir(i.reshape(-1))
        idx.append(i), vm.append(m), vc.append(v)
        tailles.append(torch.exp(x[:, c.i_jour] * 3 - 6).reshape(len(morceau), 1))
    idx, vm, vc, taille = torch.cat(idx), torch.cat(vm), torch.cat(vc), torch.cat(tailles)
    return {"marche": marche, "maitre": "masse", "partie": partie, "classe": c, "idx": idx, "vm": vm, "vc": vc,
            "cibles": im.cibles(c, ex.reset_index(drop=True), taille), "n": len(ex)}


def preparer(tr: pd.DataFrame, appareil: str, graine: int = 0) -> list[dict]:
    rng = np.random.default_rng(graine)
    lots = []
    for marche, g in tr.groupby("marche"):
        if len(g) < 300 or not ((dm.DOSSIER_M15 / f"{marche}_M15.csv").exists() or marche == "XAUUSD"):
            continue
        c = im.classe_marche(marche, appareil)
        debut = pd.to_datetime(g["debut"])
        for partie, sel in (("apprend", debut < FIN_APPRENTISSAGE),
                            ("validation", (debut >= FIN_APPRENTISSAGE) & (debut < FIN_VALIDATION)),
                            ("controle", debut >= FIN_VALIDATION)):
            morceaux = [im.exemples(c, gm.sort_values("debut").reset_index(drop=True), rng)
                        for _, gm in g[sel].groupby("maitre")]
            morceaux = [m for m in morceaux if len(m)]
            if not morceaux:
                continue
            ex = pd.concat(morceaux, ignore_index=True)
            lots.append(_lot(c, ex, marche, partie))
        dire(f"{marche} : {len(g)} trades -> " + ", ".join(f"{l['partie']} {l['n']}" for l in lots if l["marche"] == marche))
    return lots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epoques", type=int, default=3)
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--paquet", type=int, default=512)
    args = ap.parse_args()
    DOSSIER.mkdir(parents=True, exist_ok=True)
    tr = lire_tous().dropna(subset=["marche"])
    dire(f"la masse : {len(tr)} trades, {tr['maitre'].nunique()} traders, sans aucun tri")
    lots = preparer(tr, args.appareil)
    n = {p: sum(l["n"] for l in lots if l["partie"] == p) for p in ("apprend", "validation", "controle")}
    dire(f"exemples : {n}")
    agent = TraderHumain().to(args.appareil)
    opt = torch.optim.AdamW(agent.parameters(), lr=3e-4, weight_decay=1e-4)
    dire(f"avant : CONTRÔLE 05-10/2026 {json.dumps(mesurer(agent, lots, 'controle'), ensure_ascii=False)}")
    appr = [l for l in lots if l["partie"] == "apprend"]
    rng = np.random.default_rng(1)
    meilleur, etat_meilleur, ep_meilleur = -1.0, None, 0
    for ep in range(args.epoques):
        agent.train()
        pas = []
        for l in appr:
            ordre = torch.randperm(l["n"], device=l["idx"].device)
            pas += [(l, ordre[d:d + args.paquet]) for d in range(0, l["n"], args.paquet)]
        total, k = 0.0, 0
        for j in rng.permutation(len(pas)):
            l, i = pas[j]
            cib = {c: v[i] for c, v in l["cibles"].items()}
            p, _ = im.perte(agent, l["classe"], l["idx"][i], l["vm"][i], l["vc"][i], cib)
            opt.zero_grad(set_to_none=True)
            p.backward()
            torch.nn.utils.clip_grad_norm_(agent.parameters(), 1.0)
            opt.step()
            total, k = total + float(p), k + 1
            if k % 500 == 0:
                dire(f"époque {ep + 1} : {k}/{len(pas)} pas, perte {total / k:.3f}")
        val = mesurer(agent, lots, "validation")
        dire(f"époque {ep + 1} : perte {total / max(k, 1):.3f} | validation {json.dumps(val, ensure_ascii=False)}")
        if val["sens_equilibre"] + val["geste_juste"] > meilleur:
            meilleur, ep_meilleur = val["sens_equilibre"] + val["geste_juste"], ep + 1
            etat_meilleur = {a: b.detach().clone() for a, b in agent.state_dict().items()}
            torch.save({"cerveau": etat_meilleur, "source": "préapprentissage sur la masse", "epoque": ep_meilleur},
                       DOSSIER / "masse.pt")
    agent.load_state_dict(etat_meilleur)
    ctrl = mesurer(agent, lots, "controle")
    dire(f"arrêt retenu : époque {ep_meilleur} ; CONTRÔLE 05-10/2026 jamais vu : {json.dumps(ctrl, ensure_ascii=False)}")
    (DOSSIER / "masse.json").write_text(json.dumps({"exemples": n, "epoque": ep_meilleur, "controle_mai_octobre_2026": ctrl},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")
    dire(f"cerveau sauvé : {DOSSIER / 'masse.pt'}")


if __name__ == "__main__":
    main()
