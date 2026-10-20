"""DESSINER UN TRADE DU JOURNAL (18/10/2026, demande du chef de projet) : comme sur MetaTrader 5, 4 panneaux
(journalier, 4 h, 1 h, 15 min) avec les bougies, SES zones visibles au moment où elle a décidé (demande en vert, offre
en rouge), une flèche BLEUE (achat) ou ROUGE (vente) au prix d'entrée, une croix à la sortie, les lignes du stop
d'origine, du stop final, de l'objectif 1 et de la destination. Image JPEG de 1400 x 900 points.

Un trade du journal par son numéro (colonne « ticket » d'un fichier <branche>_<phase>_historique.csv) :
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.journal_dessin <fichier historique.csv> <ticket> [--sortie f.jpg]
(les réglages de l'arbre de l'or sont choisis seuls si le fichier est dans vie/arbre_or ; sinon --reglages <yaml>).
Le cœur dessine seul les 5 meilleurs et les 5 pires trades de la cime à l'examen toutes les 50 générations
(journal_trades/images/gNNNNN/, les 10 derniers lots gardés).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

PANNEAUX = (("D1", 45), ("H4", 60), ("H1", 80), ("M15", 110))       # unité, bougies avant l'entrée
GARDER_LOTS = 10


def _ns(texte) -> int:
    import pandas as pd
    return int(pd.Timestamp(str(texte).replace(".", "-", 2)).value) if isinstance(texte, str) and texte else 0


def _num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def dessiner(trade, fichier: Path) -> Path:
    """Dessine un trade (ligne d'un fichier historique, dict ou pandas.Series) dans `fichier` (JPEG)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from collapsar.ecole.precision import structure as S
    from collapsar.ecole.precision.reglages import R
    from collapsar.mains.fiches import MIROIR
    tr = dict(trade)
    marche = str(tr["marche"])
    nom, mir = (marche[:-len(MIROIR)], True) if marche.endswith(MIROIR) else (marche, False)
    x = S.lire(nom, mir)
    t15 = np.asarray(x["t15"], np.int64)
    Q = int(pd.Timedelta(minutes=15).value)
    t_ouv, t_fin, t_dec = _ns(tr["ouverture"]), _ns(tr["fermeture"]), _ns(tr.get("pose_le", ""))
    t_dec = t_dec or t_ouv
    achat = str(tr["sens"]).startswith("achat")
    K = R().yeux.zones_par_cote
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), dpi=100)
    for ax, (u, avant) in zip(axes.ravel(), PANNEAUX):
        if u not in x:
            ax.set_title(f"{u} : pas de données")
            continue
        du = int(pd.Timedelta({"D1": "1D", "H4": "4h", "H1": "1h", "M15": "15min"}[u]).value)
        debut = t_ouv - avant * du
        fin = max(t_fin + max(8, avant // 6) * du, t_ouv + 10 * du)
        if (fin - debut) / du > 3 * avant:                               # trade très long : on garde l'entrée et la sortie
            fin = t_fin + 4 * du
        a, b = np.searchsorted(t15, debut - du), np.searchsorted(t15, fin + du)
        df = pd.DataFrame({"time": t15[a:b].astype("datetime64[ns]"), "open": np.asarray(x["o"][a:b]),
                           "high": np.asarray(x["h"][a:b]), "low": np.asarray(x["l"][a:b]),
                           "close": np.asarray(x["c"][a:b])})
        bu = S.bougies_unite(df, None, u)
        keep = (bu["debut"] >= debut) & (bu["debut"] <= fin)
        tt = mdates.date2num(pd.to_datetime(bu["debut"][keep]))
        o_, h_, l_, c_ = (bu[k][keep] for k in ("open", "high", "low", "close"))
        w = (du / 86400e9) * 0.7
        for xi, oo, hh, ll, cc in zip(tt, o_, h_, l_, c_):
            col = "#26a69a" if cc >= oo else "#ef5350"
            ax.vlines(xi + w / 2, ll, hh, color=col, linewidth=0.8)
            ax.add_patch(plt.Rectangle((xi, min(oo, cc)), w, max(abs(cc - oo), 1e-12), color=col))
        # ses zones visibles à la décision (les 2 plus proches de chaque côté, de cette unité)
        i15 = max(int(np.searchsorted(t15, t_dec - Q)), 0)
        i15 = min(i15, len(t15) - 1)
        lig = int(np.asarray(x[u]["ligne"])[i15])
        x0, x1 = (tt[0], tt[-1] + w) if len(tt) else (0, 1)
        if lig >= 0:
            ids = np.asarray(x[u]["knn"])[lig].reshape(2, K)
            for cote in (0, 1):
                for z in ids[cote]:
                    if z < 0:
                        continue
                    hi, lo = float(x[u]["top"][z]), float(x[u]["bot"][z])
                    ax.add_patch(plt.Rectangle((x0, lo), x1 - x0, hi - lo, alpha=0.18,
                                               color="green" if cote == 0 else "red", linewidth=0))
        xo = mdates.date2num(pd.Timestamp(t_ouv))
        xf = mdates.date2num(pd.Timestamp(t_fin))
        po, pf = _num(tr["prix_ouverture"]), _num(tr["prix_fermeture"])
        for cle, style, couleur, nom_l in (("stop_origine", "--", "red", "stop"), ("stop_final", ":", "orange", "stop final"),
                                           ("objectif1", "--", "green", "objectif 1"), ("destination", "-", "green", "destination")):
            v = _num(tr.get(cle))
            if v is not None:
                ax.hlines(v, xo, max(xf, xo + w), colors=couleur, linestyles=style, linewidth=1.2, label=nom_l)
        if po is not None:
            ax.plot([xo], [po], marker="^" if achat else "v", color="blue" if achat else "red", markersize=13,
                    markeredgecolor="black", zorder=5)
        if pf is not None:
            ax.plot([xf], [pf], marker="x", color="black", markersize=11, markeredgewidth=2.5, zorder=5)
        if len(tt):
            ax.set_xlim(x0 - w, x1 + w)
            vals = np.r_[l_, h_, [v for v in (po, pf, _num(tr.get("stop_origine"))) if v is not None]]
            etendue = vals.max() - vals.min()
            for cle in ("objectif1", "destination", "stop_final"):           # visibles s'ils ne sont pas trop loin
                v = _num(tr.get(cle))
                if v is not None and po is not None and abs(v - po) <= 2 * etendue:
                    vals = np.r_[vals, v]
            pad = (vals.max() - vals.min()) * 0.05 or 1e-6
            ax.set_ylim(vals.min() - pad, vals.max() + pad)
        ax.set_title(f"{u}", fontsize=11)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %Hh" if u != "D1" else "%d/%m/%y"))
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.2)
    axes.ravel()[0].legend(fontsize=7, loc="upper left")
    fig.suptitle(f"ticket {tr.get('ticket')} : {tr['sens']} {marche} ({tr.get('entree', '')}) le {tr['ouverture']}, "
                 f"sortie le {tr['fermeture']} ({tr.get('raison', '')}) | R {float(tr.get('r', 0)):+.2f}, meilleur "
                 f"{float(tr.get('meilleur_r', 0)):+.2f} | risque {tr.get('risque_pct', '')} %", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fichier = Path(fichier)
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(fichier, format="jpg", dpi=100, pil_kwargs={"quality": 85})
    plt.close(fig)
    return fichier


def images_meilleurs_pires(csv: Path, dossier: Path, n: int = 5) -> list[Path]:
    """Les n meilleurs et n pires trades fermés (en R) d'un fichier historique, dessinés dans `dossier`."""
    import pandas as pd
    d = pd.read_csv(csv)
    d = d[~d["raison"].astype(str).str.startswith("fin du challenge")]
    if d.empty:
        return []
    out = []
    for genre, sel in (("meilleur", d.nlargest(n, "r")), ("pire", d.nsmallest(n, "r"))):
        for i, (_, row) in enumerate(sel.iterrows()):
            out.append(dessiner(row, Path(dossier) / f"{genre}_{i + 1}_ticket{int(row['ticket'])}.jpg"))
    return out


def tourner_images(racine: Path, garder: int = GARDER_LOTS) -> list[str]:
    lots = sorted(p for p in Path(racine).glob("g[0-9]*") if p.is_dir())
    out = []
    for p in lots[:-garder] if len(lots) > garder else []:
        shutil.rmtree(p, ignore_errors=True)
        out.append(p.name)
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description="dessiner un trade du journal comme sur MT5")
    ap.add_argument("fichier", help="fichier <branche>_<phase>_historique.csv")
    ap.add_argument("ticket", type=int)
    ap.add_argument("--sortie", default=None)
    ap.add_argument("--reglages", default=None, help="fichier de réglages de l'arbre (par défaut : deviné)")
    a = ap.parse_args(argv)
    if a.reglages:
        os.environ["COLLAPSAR_PRECISION_REGLAGES"] = str(Path(a.reglages).resolve())
    elif "arbre_or" in str(Path(a.fichier).resolve()) and not os.environ.get("COLLAPSAR_PRECISION_REGLAGES"):
        os.environ["COLLAPSAR_PRECISION_REGLAGES"] = str(Path(__file__).with_name("reglages_or.yaml"))
    import pandas as pd
    d = pd.read_csv(a.fichier)
    t = d[d["ticket"] == a.ticket]
    if t.empty:
        raise SystemExit(f"ticket {a.ticket} absent de {a.fichier}")
    sortie = Path(a.sortie) if a.sortie else Path(a.fichier).with_name(f"trade_{a.ticket}.jpg")
    print(dessiner(t.iloc[0], sortie))


if __name__ == "__main__":
    main()
