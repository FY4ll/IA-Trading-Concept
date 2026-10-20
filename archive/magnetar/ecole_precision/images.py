"""Les deux images de l'arbre HYPERNOVA envoyées au téléphone (après la 1re génération, puis à 8h et 20h), au style
des images de l'arbre de COLLAPSAR (collapsar/surveillance/dessin.py, dont on réutilise les briques) :
1. l'ARBRE : une carte par branche (note de l'examen 2022-2023, %/mois contre son jumeau au hasard, challenges
   réussis), reliée à sa mère ; la cime est marquée ;
2. la COURBE de la cime au fil des générations : %/mois, celui de son jumeau au hasard, % de challenges réussis.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402

from collapsar.arbre.jardinier import Arbre  # noqa: E402
from collapsar.ecole.precision.reglages import etiquette_selection  # noqa: E402
from collapsar.surveillance import dessin as D  # noqa: E402

BAS, HAUT = -3.0, 3.0               # couleur des cartes : note d'examen (0 = rien de mieux que le hasard)


def _v(x, n=2, signe=True):
    if x is None or x != x:
        return "—"
    s = f"{x:+.{n}f}" if signe else f"{x:.{n}f}"
    return s.replace(".", ",")


def _couleur(note):
    if note is None:
        return D.GRIS
    return D.COULEURS(min(1.0, max(0.0, (note - BAS) / (HAUT - BAS))))


def _colonnes(arbre: Arbre) -> dict[str, int]:
    """Les branches de la graine côte à côte ; une fille au plus près de sa mère, sur une colonne libre à sa naissance
    (comme dessin.couloirs, qui ne prévoit qu'une seule graine)."""
    places: dict[str, int] = {}
    ordre = sorted(arbre.branches.values(), key=lambda b: (b.nee, b.nom))
    racines = [b for b in ordre if not b.parents]
    for i, b in enumerate(racines):
        places[b.nom] = i
    for b in ordre:
        if b.nom in places:
            continue
        mere = places.get(b.parents[0], 0)
        prises = {places[o.nom] for o in ordre if o.nom in places and D._t(o.nee) <= D._t(b.nee)
                  and (o.morte is None or D._t(o.morte) > D._t(b.nee))}
        for d in range(0, 100):
            for c in ((mere + d, mere - d) if d else (mere,)):
                if c not in prises and c >= 0:
                    places[b.nom] = c
                    break
            if b.nom in places:
                break
    return places


def dessiner_arbre(arbre: Arbre, examens: dict, fichier: Path, nom: str = "HYPERNOVA") -> Path:
    places = _colonnes(arbre)
    montrees = D._a_montrer(arbre)
    racines = [n for n in montrees if not arbre.branches[n].parents]
    autres = [n for n in montrees if arbre.branches[n].parents]
    rang = {**{n: 1 for n in racines}, **{n: i + 2 for i, n in enumerate(autres)}}
    cols = sorted({places[n] for n in montrees} | {0})
    colx = {c: i * 2.3 for i, c in enumerate(cols)}
    xc = (colx[cols[0]] + colx[cols[-1]]) / 2
    L, H, PAS = 2.0, 1.05, 1.45
    demi = max(3.4, (colx[cols[-1]] - colx[cols[0]]) / 2 + L / 2 + 0.3)
    x0, x1 = xc - demi, xc + demi
    y0, y1 = -0.7, PAS * max(rang.values()) + H / 2 + 1.0
    fig = plt.figure(figsize=(x1 - x0 + 0.6, y1 - y0 + 1.4), dpi=140)
    lf, hf = fig.get_size_inches()
    ax = fig.add_axes([0.3 / lf, 0.55 / hf, (x1 - x0) / lf, (y1 - y0) / hf])
    fig.patch.set_facecolor(D.FOND)
    ax.set_facecolor(D.FOND)
    D._carte(ax, xc, 0, 3.2, 0.8, f"GRAINE {nom}",
             ["ses zones · stop de structure · objectif 1"], "#8A6A4A")
    pos = {n: (colx[places[n]], rang[n] * PAS) for n in montrees}
    for n in montrees:
        b = arbre.branches[n]
        x, y = pos[n]
        if not b.parents or not any(p in pos for p in b.parents):
            D._coude(ax, xc, 0.4, x, y - H / 2, D.GRIS)
        for p in b.parents:
            if p in pos:
                px, py = pos[p]
                D._coude(ax, px, py + H / 2, x, y - H / 2, D.BLEU)
    for n in montrees:
        b = arbre.branches[n]
        x, y = pos[n]
        ex = examens.get(n)
        vivante = b.morte is None
        note = f"note {_v(b.score)}" if b.score is not None else "pas encore examinée"
        if ex:
            l2 = f"{_v(ex['gain_pct_mois'])} %/mois (jumeau {_v(ex['jumeau']['gain_pct_mois'])})"
            l3 = f"réussis {ex['reussis_pct']:.0f} % · morts {ex['murs_pct']:.0f} %"
        else:
            l2, l3 = (b.temperament.get("nom", ""), "")
        if not vivante:
            l3 = {"coupée": "coupée, archivée"}.get(b.cause, b.cause or "")
        D._carte(ax, x, y, L, H, f"Branche {n}", [note, l2, l3], _couleur(b.score) if vivante else D.GRIS,
                 attenue=not vivante, entete="CIME" if n == arbre.cime else None)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.axis("off")
    cime = arbre.branches.get(arbre.cime) if arbre.cime else None
    sous = f"génération {arbre.battements} · {len(arbre.vivantes())} branche(s) vivante(s) sur {arbre.r.places} places"
    if cime and cime.score is not None:
        sous += f" · cime {cime.nom} : note {_v(cime.score)}"
    fig.text(0.3 / lf, 1 - 0.2 / hf, f"COLLAPSAR — arbre {nom}", fontsize=15, fontweight="bold", color=D.ENCRE, va="top")
    fig.text(0.3 / lf, 1 - 0.55 / hf, sous, fontsize=8.5, color=D.GRIS, va="top")
    fig.text(0.3 / lf, 0.12 / hf, f"note = examen {etiquette_selection()} (jamais appris) : réussir vite +5 à +10, mur -10, gain au-delà "
             "du jumeau au hasard\nliseré : rouge -3 · jaune 0 · vert +3", fontsize=7, color=D.GRIS, va="bottom")
    return D._enregistrer(fig, fichier)


def dessiner_courbe(lignes: list[dict], fichier: Path, nom: str = "HYPERNOVA") -> Path:
    gens = [l for l in lignes if l.get("quoi") == "generation" and l.get("cime_examen")]
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7, 6), dpi=140, sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    fig.patch.set_facecolor(D.FOND)
    if gens:
        g = [l["generation"] for l in gens]
        elle = [l["cime_examen"]["gain_pct_mois"] for l in gens]
        jum = [l["cime_examen"]["jumeau"]["gain_pct_mois"] for l in gens]
        reu = [l["cime_examen"]["reussis_pct"] for l in gens]
        jreu = [l["cime_examen"]["jumeau"]["reussis_pct"] for l in gens]
        ax.axhspan(8, 10, color="#1E9E5A", alpha=0.10)
        ax.axhline(0, color="#D64545", lw=1.0)
        ax.plot(g, jum, color=D.GRIS, lw=1.4, ls="--", label="son jumeau au hasard (mêmes gestes, sens à pile ou face)")
        ax.plot(g, elle, color=D.BLEU, lw=2.6, marker="o", ms=3, label="la cime")
        ax.text(g[0], 9, "objectif 8-10 %/mois", fontsize=7.5, color="#17804A", va="center")
        ax.set_ylabel(f"%/mois (examen {etiquette_selection()}, jamais appris)", fontsize=8, color=D.GRIS)
        ax.legend(loc="upper right", bbox_to_anchor=(1, 0.75), fontsize=7, frameon=False)
        ax.set_ylim(min(-2.0, min(elle + jum) - 0.5), max(11.0, max(elle + jum) + 0.5))
        ax2.plot(g, jreu, color=D.GRIS, lw=1.2, ls="--")
        ax2.plot(g, reu, color=D.VIOLET, lw=2.2, marker="o", ms=3)
        ax2.set_ylabel("challenges réussis %", fontsize=8, color=D.GRIS)
        ax2.set_xlabel("génération", fontsize=8, color=D.GRIS)
        fig.text(0.03, 0.985, f"COLLAPSAR — arbre {nom}, génération {g[-1]}", fontsize=12, fontweight="bold",
                 color=D.ENCRE, va="top")
        fig.text(0.03, 0.945, f"la cime : {_v(elle[-1])} %/mois (jumeau au hasard {_v(jum[-1])}), challenges réussis "
                 f"{reu[-1]:.0f} % (jumeau {jreu[-1]:.0f} %)", fontsize=8.5,
                 color=D.GRIS, va="top")
        ax2.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    else:
        ax.text(0.5, 0.5, "pas encore de génération", ha="center", transform=ax.transAxes, color=D.GRIS)
    for a in (ax, ax2):
        a.set_facecolor(D.CARTE)
        a.grid(color="#E6EAF1", lw=0.8)
        a.tick_params(colors=D.GRIS, labelsize=8)
        for c in a.spines.values():
            c.set_color(D.TRAIT)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return D._enregistrer(fig, fichier)
