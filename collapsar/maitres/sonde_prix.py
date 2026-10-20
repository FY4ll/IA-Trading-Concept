"""LA SONDE DU PRIX (15/10/2026) : des yeux qui ont « compris la foule » lisent-ils mieux le prix ?

Pour chaque paire d'yeux (cerveau préappris sur la masse, cerveau NEUF au hasard, meilleur élève de l'école), on lit
chaque heure les graphiques de 8 marchés ; une simple régression (la même pour tous, réglée sur les heures AVANT le
01/03/2026, comme le préapprentissage) essaie d'en tirer le mouvement des 4 h et 1 jour suivants (rapporté à
l'agitation). Jugé sur MAI -> OCTOBRE 2026, jamais vu : lien de rang entre la prévision et le vrai mouvement, part de
sens justes (équilibrée), force = lien x racine(nombre d'heures indépendantes). Repère : la tendance des 20 jours.
Si les yeux de la masse ne font pas mieux que des yeux neufs, la masse ne leur a rien appris sur le PRIX.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.maitres.sonde_prix
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

from collapsar.cerveau.humain import TraderHumain
from collapsar.donnees import marches as dm
from collapsar.maitres import imitation as im

MARCHES = ["XAUUSD", "EURUSD", "USDJPY", "USA500IDXUSD", "XAGUSD", "USATECHIDXUSD", "LIGHTCMDUSD", "GBPUSD"]
DEBUT, FIN_REGLAGE, DEBUT_JUGE, FIN = (pd.Timestamp("2024-09-01"), pd.Timestamp("2026-03-01"),
                                       pd.Timestamp("2026-05-01"), pd.Timestamp("2026-10-10"))
HORIZONS = {"4 h": 16, "1 jour": 96}
VIE = dm.RACINE / "collapsar" / "vie"


def cerveaux(appareil):
    sortie = {}
    for nom, f in (("masse", VIE / "ecole_maitres" / "masse.pt"), ("ecole", VIE / "ecole_mondes" / "meilleur.pt"),
                   ("neuf", None)):
        torch.manual_seed(0)
        a = TraderHumain().to(appareil)
        if f is not None:
            a.charger(torch.load(f, map_location=appareil, weights_only=False)["cerveau"])
        a.eval()
        sortie[nom] = a
    return sortie


@torch.no_grad()
def lire(c, agents, idx_local) -> tuple[dict, np.ndarray]:
    idx = (c.offset[0] + torch.as_tensor(idx_local, device=c.dev)).long()
    traits = {n: [] for n in agents}
    tailles = []
    for d in range(0, len(idx), 2048):
        f, x = c.g.voir(idx[d:d + 2048])
        tailles.append(torch.exp(x[:, c.i_jour] * 3 - 6).cpu().numpy())
        for n, a in agents.items():
            traits[n].append(a.yeux.comprendre(f, x).float().cpu().numpy())
    return {n: np.concatenate(v) for n, v in traits.items()}, np.concatenate(tailles)


def main():
    appareil = "cuda" if torch.cuda.is_available() else "cpu"
    agents = cerveaux(appareil)
    lignes = {n: [] for n in agents}
    meta = []
    for marche in MARCHES:
        c = im.classe_marche(marche, appareil)
        temps = c.h.temps
        prix = c.h.c[:, 0].cpu().numpy()
        t = np.flatnonzero((temps >= DEBUT) & (temps < FIN) & (temps.minute == 0) & (c.h.local[:, 0].cpu().numpy() >= 0))
        t = t[t + max(HORIZONS.values()) < len(temps)]
        traits, taille = lire(c, agents, c.h.local[t, 0].cpu().numpy())
        m = pd.DataFrame({"marche": marche, "temps": temps[t]})
        for nom, k in HORIZONS.items():
            m[nom] = (prix[t + k] / prix[t] - 1) / taille
        m["tendance"] = np.sign(prix[t] / prix[np.maximum(t - 20 * 96, 0)] - 1)
        meta.append(m)
        for n in agents:
            lignes[n].append(traits[n])
        print(f"{marche} : {len(t)} heures lues", flush=True)
    meta = pd.concat(meta, ignore_index=True)
    regle = (meta["temps"] < FIN_REGLAGE).to_numpy()
    juge = (meta["temps"] >= DEBUT_JUGE).to_numpy()
    resultats = {}
    for nom, k in HORIZONS.items():
        y = meta[nom].to_numpy()
        ok_r, ok_j = regle & np.isfinite(y), juge & np.isfinite(y)
        n_indep = ok_j.sum() / max(k / 4, 1)
        res = {}
        for n in agents:
            X = np.concatenate(lignes[n])
            sc = StandardScaler().fit(X[ok_r])
            mod = RidgeCV(alphas=np.logspace(0, 5, 11)).fit(sc.transform(X[ok_r]), np.clip(y[ok_r], -5, 5))
            p = mod.predict(sc.transform(X[ok_j]))
            res[n] = _note(p, y[ok_j], n_indep)
        res["tendance 20 jours"] = _note(meta.loc[ok_j, "tendance"].to_numpy(), y[ok_j], n_indep)
        resultats[nom] = res
    f = VIE / "ecole_maitres" / "sonde_prix.json"
    f.write_text(json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8")
    for nom, res in resultats.items():
        print(f"== prix {nom} plus tard (mai -> octobre 2026, jamais vu)")
        for n, r in res.items():
            print(f"  {n:18s} lien {r['lien']:+.4f}  force {r['force']:+.1f}  sens juste (équilibré) {r['sens_equilibre']:.1f} %")
    print(f"(enregistré : {f})")


def _note(p, y, n_indep) -> dict:
    lien = float(pd.Series(p).rank().corr(pd.Series(y).rank()))
    haut, bas = y > 0, y < 0
    juste_h = float(np.mean(p[haut] > 0)) if haut.any() else np.nan
    juste_b = float(np.mean(p[bas] < 0)) if bas.any() else np.nan
    return {"lien": lien, "force": lien * float(np.sqrt(n_indep)), "sens_equilibre": (juste_h + juste_b) / 2 * 100}


if __name__ == "__main__":
    main()
