"""Les deux images envoyées au chef de projet (matin et soir), au style « plan de réseau » :
1. l'ARBRE : chaque branche est une carte (note, sève, battements), reliée à sa mère (bourgeon) ou à ses deux mères
   (fusion) ; la cime est marquée ; les portes (compte à blanc, démo, FTMO) sont en haut avec leur état ;
2. la COURBE de progrès de la cime.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from collapsar.arbre.jardinier import Arbre  # noqa: E402

COULEURS = plt.get_cmap("RdYlGn")
BAS, HAUT = 49.0, 53.0          # 50 % = le hasard ; au-dessus, elle devine mieux que le hasard
FOND = "#F4F6FA"
CARTE = "#FFFFFF"
TRAIT = "#C9D1DE"
ENCRE = "#1F2A3C"
GRIS = "#7A8699"
BLEU = "#2F6FDE"
VIOLET = "#7B4FD6"
OR = "#E8A800"
MAX_CARTES = 8                 # au-delà, le texte devient illisible sur un téléphone
PORTES = ["école", "compte à blanc", "démo réelle", "compte FTMO"]


def _t(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _virgule(x: float, n: int = 1) -> str:
    return f"{x:.{n}f}".replace(".", ",")


BAS_T, HAUT_T = 0.0, 6.0        # vision du trader : lien prévu/réel en % (0 = elle ne voit rien)


def _couleur(score, trader: bool = False):
    if score is None:
        return GRIS
    bas, haut = (BAS_T, HAUT_T) if trader else (BAS, HAUT)
    return COULEURS(min(1.0, max(0.0, (score - bas) / (haut - bas))))


def couloirs(arbre: Arbre) -> dict[str, int]:
    """Colonne de chaque branche : un bourgeon se place au plus près de sa mère, sur une colonne libre ;
    une fusion continue dans la colonne de la meilleure de ses deux mères."""
    places: dict[str, int] = {}
    ordre = sorted(arbre.branches.values(), key=lambda b: b.nee)
    for b in ordre:
        if not b.parents:
            places[b.nom] = 0
            continue
        if len(b.parents) >= 2:
            places[b.nom] = places[b.parents[0]]
            continue
        mere = places[b.parents[0]]
        prises = {places[o.nom] for o in ordre if o.nom in places
                  and _t(o.nee) <= _t(b.nee) and (o.morte is None or _t(o.morte) > _t(b.nee))}
        for d in range(1, 100):
            for c in (mere + d, mere - d):
                if c not in prises:
                    places[b.nom] = c
                    break
            if b.nom in places:
                break
    return places


def _a_montrer(arbre: Arbre) -> list[str]:
    """Les vivantes, leurs ancêtres, puis les plus récentes disparues, jusqu'à MAX_CARTES."""
    garde = []
    pile = [b.nom for b in arbre.vivantes()]
    while pile:
        n = pile.pop()
        if n not in garde:
            garde.append(n)
            pile.extend(arbre.branches[n].parents)
    for b in sorted(arbre.branches.values(), key=lambda b: b.nee, reverse=True):
        if len(garde) >= MAX_CARTES:
            break
        if b.nom not in garde:
            garde.append(b.nom)
    return sorted(garde, key=lambda n: arbre.branches[n].nee)[-MAX_CARTES:]


def _coude(ax, x0, y0, x1, y1, couleur, style="-", largeur=1.8):
    """Connexion à angles droits, comme sur un plan de réseau : monte, tourne, monte."""
    ym = (y0 + y1) / 2
    ax.plot([x0, x0, x1, x1], [y0, ym, ym, y1], color=couleur, lw=largeur, ls=style, zorder=1,
            solid_joinstyle="miter", solid_capstyle="butt")
    ax.plot([x1], [y1], marker="^", color=couleur, markersize=5, zorder=1)


def _carte(ax, x, y, l, h, titre, lignes, bord, fond=CARTE, entete=None, attenue=False):
    ax.add_patch(FancyBboxPatch((x - l / 2, y - h / 2), l, h, boxstyle="round,pad=0,rounding_size=0.06",
                                fc=fond, ec=TRAIT if attenue else bord, lw=1.2 if attenue else 2.2, zorder=3))
    ax.add_patch(FancyBboxPatch((x - l / 2, y - h / 2), 0.07, h, boxstyle="square,pad=0", fc=bord, ec="none",
                                zorder=4, alpha=0.35 if attenue else 1))
    ax.text(x - l / 2 + 0.16, y + h / 2 - 0.11, titre, fontsize=9.5, fontweight="bold", va="top",
            color=GRIS if attenue else ENCRE, zorder=5)
    for i, ligne in enumerate(lignes):
        ax.text(x - l / 2 + 0.16, y + h / 2 - 0.42 - i * 0.24, ligne, fontsize=7.6, va="top",
                color=GRIS, zorder=5)
    if entete:
        ax.text(x + l / 2 - 0.1, y + h / 2 - 0.11, entete, fontsize=7, fontweight="bold", va="top", ha="right",
                color="white", zorder=6, bbox=dict(boxstyle="round,pad=0.25", fc=OR, ec="none"))


def dessiner_arbre(arbre: Arbre, fichier: Path, portes: list[tuple[str, str]] = (), maintenant: datetime | None = None,
                   trader: bool = False):
    places = couloirs(arbre)
    montrees = _a_montrer(arbre)
    rang = {n: i + 1 for i, n in enumerate(montrees)}             # une rangée par naissance, de bas en haut
    cols = sorted({places[n] for n in montrees} | {0})
    colx = {c: i * 2.3 for i, c in enumerate(cols)}
    xc = (colx[cols[0]] + colx[cols[-1]]) / 2
    L, H, PAS = 2.0, 1.05, 1.45
    parts = arbre.parts_de_seve()
    haut_y = PAS * (len(montrees) + 1)
    # 1 unité du plan = 1 pouce : les cartes gardent la même taille quel que soit l'arbre
    demi = max(3.4, (colx[cols[-1]] - colx[cols[0]]) / 2 + L / 2 + 0.3)
    x0, x1 = xc - demi, xc + demi
    y0, y1 = -0.7, PAS * len(montrees) + H / 2 + 1.75
    marge_g, marge_d, marge_b, marge_h = 0.3, 0.3, 0.55, 0.85
    fig = plt.figure(figsize=(x1 - x0 + marge_g + marge_d, y1 - y0 + marge_b + marge_h), dpi=140)
    lf, hf = fig.get_size_inches()
    ax = fig.add_axes([marge_g / lf, marge_b / hf, (x1 - x0) / lf, (y1 - y0) / hf])
    fig.patch.set_facecolor(FOND)
    ax.set_facecolor(FOND)

    # les racines
    _carte(ax, xc, 0, 3.0, 0.8, "RACINES · étage « regarder »",
           ["coups libres jugés par le vrai marché" if trader else "exercices corrigés par le marché"], "#8A6A4A")
    pos = {}
    for n in montrees:
        pos[n] = (colx[places[n]], rang[n] * PAS)
    for n in montrees:
        b = arbre.branches[n]
        x, y = pos[n]
        if not b.parents or not any(p in pos for p in b.parents):
            _coude(ax, xc, 0.4, x, y - H / 2, GRIS)
        for p in b.parents:
            if p in pos:
                px, py = pos[p]
                fusion = len(b.parents) >= 2
                _coude(ax, px, py + H / 2, x, y - H / 2, VIOLET if fusion else BLEU)
    for n in montrees:
        b = arbre.branches[n]
        x, y = pos[n]
        vivante = b.morte is None
        if b.score is None:
            note = "pas encore notée"
        elif trader:
            note = f"lien {'+' if b.score >= 0 else ''}{_virgule(b.score, 2)} %"
        else:
            note = f"{_virgule(b.score, 2)} % bien devinés"
        if vivante:
            etat = f"sève {round(parts.get(n, 0) * 100)} % · {b.battements} battement(s)"
        else:
            etat = {"coupée": "coupée, archivée", "fusion": "fusionnée"}.get(b.cause, b.cause or "")
        origine = ("fusion " + " + ".join(b.parents)) if len(b.parents) >= 2 else (
            f"bourgeon de {b.parents[0]}" if b.parents else "graine")
        _carte(ax, x, y, L, H, f"Branche {n}", [note, etat, origine],
               _couleur(b.score, trader) if vivante else GRIS, attenue=not vivante,
               entete="CIME" if n == arbre.cime else None)

    # les portes, en haut
    ouvertes = {nom for _, nom in portes}
    y_portes = max(y for _, y in pos.values()) + H / 2 + 0.75 if pos else haut_y
    largeur = x1 - x0 - 0.6
    for i, nom in enumerate(PORTES):
        px = x0 + 0.3 + largeur * (i + 0.5) / len(PORTES)
        ouverte = nom in ouvertes
        ax.text(px, y_portes, ("●  " if ouverte else "○  ") + nom, ha="center", va="center", fontsize=8.2,
                color="#1E9E5A" if ouverte else GRIS, fontweight="bold" if ouverte else "normal",
                bbox=dict(boxstyle="round,pad=0.45", fc=CARTE, ec="#1E9E5A" if ouverte else TRAIT, lw=1.3))
    ax.text(x0 + 0.3, y_portes + 0.42, "PORTES VERS LE COMPTE FTMO", fontsize=7.5, color=GRIS, fontweight="bold")
    ax.axhline(y_portes - 0.45, color=TRAIT, lw=0.8, xmin=0.03, xmax=0.97)

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.axis("off")
    cime = arbre.branches.get(arbre.cime) if arbre.cime else None
    sous = f"{arbre.battements} battement(s) · {len(arbre.vivantes())} branche(s) vivante(s) sur {arbre.r.places} places"
    if cime and cime.score is not None:
        sous += (f" · cime {cime.nom} : lien prévu/réel {_virgule(cime.score, 2)} %" if trader
                 else f" · cime {cime.nom} : {_virgule(cime.score, 2)} %")
    fig.text(0.3 / lf, 1 - 0.2 / hf, "COLLAPSAR", fontsize=16, fontweight="bold", color=ENCRE, va="top")
    fig.text(0.3 / lf, 1 - 0.55 / hf, sous, fontsize=8.5, color=GRIS, va="top")
    cachees = len(arbre.branches) - len(montrees)
    pied = ("bleu = bourgeon · violet = fusion · liseré = lien entre gain prévu et gain réel (rouge 0 = elle ne "
            "voit rien · vert 6 %)" if trader else
            "bleu = bourgeon · violet = fusion · liseré = note (rouge 49 % · jaune 51 % · vert 53 %) · 50 % = hasard")
    if cachees:
        pied += f"\n{cachees} ancienne(s) branche(s) archivée(s) non affichée(s)"
    fig.text(0.3 / lf, 0.12 / hf, pied, fontsize=7, color=GRIS, va="bottom")
    return _enregistrer(fig, fichier)


def dessiner_courbe(lignes: list[dict], fichier: Path, trader: bool = False):
    """Progrès de la cime dans le temps, d'après le journal de croissance."""
    bat = [l for l in lignes if l.get("quoi") == "battement" and l.get("cime_score") is not None
           and (l.get("vision") == "trader") == trader]
    fig, ax = plt.subplots(figsize=(7, 4.6), dpi=140)
    fig.patch.set_facecolor(FOND)
    ax.set_facecolor(CARTE)
    if bat and trader:
        t = [_t(l["heure"]) for l in bat]
        s = [l["cime_score"] for l in bat]
        rep = [l.get("meme_reponse") for l in bat]
        bas, haut = min(-1.0, min(s) - 0.5), max(6.0, max(s) + 0.5)
        ax.axhspan(bas, 0, color="#D64545", alpha=0.10, zorder=0)
        ax.axhspan(0, haut, color="#1E9E5A", alpha=0.07, zorder=0)
        marge = max((t[-1] - t[0]) * 0.05, timedelta(minutes=30))
        ax.set_xlim(t[0] - marge, t[-1] + marge)
        x_txt = t[0] - marge * 0.8
        ax.text(x_txt, -0.1, "elle ne voit rien (hasard)", color="#B03030", fontsize=8, va="top")
        ax.text(x_txt, haut - 0.15, "ce qu'elle prévoit se réalise", color="#17804A", fontsize=8, va="top")
        ax.axhline(0, color="#D64545", lw=1.2, zorder=1)
        if all(r is not None for r in rep) and any(r for r in rep):
            ax.plot(t, rep, color=GRIS, lw=1.2, ls="--", zorder=2, label="meilleur coup fixe joué sans regarder")
            ax.legend(loc="lower right", fontsize=7, frameon=False)
        ax.plot(t, s, color=BLEU, lw=2.8, marker="o", ms=5, zorder=3)
        d = s[-1]
        ax.annotate(f"{'+' if d >= 0 else ''}{_virgule(d, 2)} %", (t[-1], d), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=11, fontweight="bold", color=BLEU)
        fig.text(0.03, 0.975, f"Progrès de COLLAPSAR : lien prévu/réel {'+' if d >= 0 else ''}{_virgule(d, 2)} %",
                 fontsize=12.5, fontweight="bold", color=ENCRE, va="top")
        fig.text(0.03, 0.915, "Dans 300 000 situations de 2020-2022 jamais apprises, elle prévoit ce que rapporte "
                 "n'importe quel coup (sens, stop, objectif).\nLa ligne : à quel point ses prévisions collent à ce qui "
                 "s'est VRAIMENT passé, frais compris. 0 = au hasard.", fontsize=8, color=GRIS, va="top")
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=7))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%Hh%M"))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{_virgule(v, 0)} %"))
        ax.set_ylim(bas, haut)
    elif bat:
        t = [_t(l["heure"]) for l in bat]
        s = [l["cime_score"] for l in bat]
        bas, haut = min(48.5, min(s) - 0.5), max(54, max(s) + 1)
        ax.axhspan(bas, 50, color="#D64545", alpha=0.10, zorder=0)
        ax.axhspan(50, haut, color="#1E9E5A", alpha=0.07, zorder=0)
        marge = max((t[-1] - t[0]) * 0.05, timedelta(minutes=30))
        ax.set_xlim(t[0] - marge, t[-1] + marge)
        x_txt = t[0] - marge * 0.8
        ax.text(x_txt, 49.6, "pas mieux que le hasard (pile ou face)", color="#B03030", fontsize=8, va="top")
        ax.text(x_txt, haut - 0.15, "elle devine mieux que le hasard", color="#17804A", fontsize=8, va="top")
        ax.axhline(50, color="#D64545", lw=1.2, zorder=1)
        ax.plot(t, s, color=BLEU, lw=2.8, marker="o", ms=5, zorder=3)
        dernier = bat[-1]
        ax.annotate(f"{_virgule(dernier['cime_score'])} %", (t[-1], s[-1]), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=11, fontweight="bold", color=BLEU)
        fig.text(0.03, 0.975, f"Progrès de COLLAPSAR : {_virgule(dernier['cime_score'])} % bien devinés",
                 fontsize=12.5, fontweight="bold", color=ENCRE, va="top")
        fig.text(0.03, 0.915, "Elle doit deviner si le marché monte ou baisse, sur 300 000 situations de 2020-2022 "
                 "jamais apprises (3 ans).\nPlus la ligne monte, mieux elle comprend les graphiques.",
                 fontsize=8, color=GRIS, va="top")
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=7))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%Hh%M"))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{_virgule(v, 0)} %"))
        ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(1))
        ax.set_ylim(bas, haut)
    else:
        ax.text(0.5, 0.5, "pas encore de battement", ha="center", transform=ax.transAxes, color=GRIS)
    ax.grid(color="#E6EAF1", lw=0.8)
    for c in ax.spines.values():
        c.set_color(TRAIT)
    ax.tick_params(colors=GRIS, labelsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    return _enregistrer(fig, fichier)


def _enregistrer(fig, fichier: Path, cote_max: int = 1400) -> Path:
    """Image légère pour le téléphone : au plus 1 400 pixels de côté, en JPEG (13/10 : l'arbre grandissait jusqu'à
    2 000 x 2 800 pixels et ntfy ne l'affichait plus)."""
    l, h = fig.get_size_inches()
    dpi = min(140, cote_max / max(l, h))
    fichier = Path(fichier).with_suffix(".jpg")
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(fichier, facecolor=fig.get_facecolor(), dpi=dpi, pil_kwargs={"quality": 85, "optimize": True})
    plt.close(fig)
    return fichier
