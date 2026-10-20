"""Le jardinier : les règles de croissance de l'arbre (CONCEPTION, section 7). Aucune règle de trading ici.

- Places : la machine a une taille finie, donc un nombre fixe de branches vivantes en même temps.
- Sève : à chaque battement, TOUTES les branches vivantes s'entraînent, chacune un temps proportionnel à sa sève
  (décision du chef de projet, 13/10). Plus une branche est bonne, plus elle a de sève ; une jeune branche reçoit un
  minimum le temps de faire ses preuves, et pousse dès sa naissance.
- Bourgeon : la cime fait naître une branche au tempérament légèrement différent, s'il reste une place.
- Coupe : une branche qui ne progresse plus et reste loin derrière la cime est coupée et archivée.
- Fusion : les deux meilleures branches sont mélangées ; la fusion n'est gardée que si elle fait mieux que les deux.
- Cime : la branche vivante la mieux notée.
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

TEMPERAMENT_GRAINE = {"vitesse": 3e-4, "lot": 512, "oubli": 0.1, "usure": 1e-4}
NIVEAU_SUR = 3                    # le niveau d'une branche = moyenne de ses 3 dernières notes


def maintenant() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Branche:
    nom: str
    parents: list[str]
    nee: str
    temperament: dict
    morte: str | None = None
    cause: str | None = None
    battements: int = 0
    scores: list = field(default_factory=list)          # [(heure, score)]
    seve: list = field(default_factory=list)            # [(heure, part de sève)]
    meilleur: float | None = None
    sans_progres: int = 0                               # battements d'affilée sans battre son meilleur score
    record: float | None = None                         # vision du trader : meilleure note jamais mesurée (sauvegardée)
    retours: int = 0                                    # retours à cette meilleure version (contre le par cœur)

    @property
    def score(self) -> float | None:
        """Le NIVEAU de la branche : la moyenne de ses 3 dernières notes (une seule note est trop bruitée : la cime
        changeait pour 0,04 point de hasard de mesure). C'est lui qui décide de tout : cime, sève, coupe, fusion."""
        if not self.scores:
            return None
        dernieres = [s[1] for s in self.scores[-NIVEAU_SUR:]]
        return sum(dernieres) / len(dernieres)

    @property
    def derniere_note(self) -> float | None:
        return self.scores[-1][1] if self.scores else None


@dataclass
class Reglages:
    places: int = 4
    bourgeon_tous: int = 2           # battements de l'arbre entre deux bourgeons
    jeunesse: int = 3                # battements pendant lesquels une jeune branche a une sève minimale
    seve_jeune: float = 0.2
    coupe_apres: int = 3             # battements sans progrès avant de pouvoir être coupée
    coupe_ecart: float = 0.3         # points de retard sur la cime pour être coupée
    fusion_tous: int = 6             # battements de l'arbre entre deux essais de fusion
    fusion_maturite: int = 3         # battements minimum de chaque branche avant de fusionner


class Arbre:
    def __init__(self, reglages: Reglages | None = None):
        self.r = reglages or Reglages()
        self.branches: dict[str, Branche] = {}
        self.battements = 0
        self.dernier_bourgeon = 0
        self.dernier_essai_fusion = 0
        self.nees = 0
        self.cime: str | None = None
        self.envois: dict = {}                               # dernières images envoyées au téléphone

    # ---- naissance, mort ----
    def _nouveau_nom(self) -> str:
        n = self.nees
        self.nees += 1
        return chr(65 + n % 26) + (str(n // 26 + 1) if n >= 26 else "")

    def naitre(self, parents: list[str], temperament: dict, heure: str | None = None) -> Branche:
        b = Branche(self._nouveau_nom(), list(parents), heure or maintenant(), dict(temperament))
        self.branches[b.nom] = b
        return b

    def mourir(self, nom: str, cause: str, heure: str | None = None):
        b = self.branches[nom]
        b.morte, b.cause = heure or maintenant(), cause
        self._elire_cime()

    def vivantes(self) -> list[Branche]:
        return [b for b in self.branches.values() if b.morte is None]

    # ---- battement : toutes les branches vivantes poussent, la sève décide combien de temps chacune ----
    def noter(self, nom: str, score: float, heure: str | None = None, bonnes: float | None = None,
              battement: bool = True):
        """Note une branche après son entraînement. `battement=False` : première note d'une fusion."""
        b = self.branches[nom]
        b.scores.append((heure or maintenant(), score, bonnes))
        if b.meilleur is None or b.score > b.meilleur:          # progrès mesuré sur le niveau, pas sur une note
            b.meilleur, b.sans_progres = b.score, 0
        else:
            b.sans_progres += 1
        if battement:
            b.battements += 1
        self._elire_cime()

    def fin_de_battement(self):
        self.battements += 1

    def _elire_cime(self):
        """La cime : le meilleur niveau parmi les branches qui ont fait leurs preuves (au moins 3 notes) ; une jeune
        branche brillante sur une seule note doit d'abord confirmer."""
        notees = [b for b in self.vivantes() if b.score is not None]
        confirmees = [b for b in notees if len(b.scores) >= NIVEAU_SUR] or notees
        self.cime = max(confirmees, key=lambda b: b.score).nom if confirmees else None

    def parts_de_seve(self) -> dict[str, float]:
        vivantes = self.vivantes()
        if not vivantes:
            return {}
        rang = sorted(vivantes, key=lambda b: (b.score is not None, b.score or 0), reverse=True)
        brut = {b.nom: float(len(rang) - i) for i, b in enumerate(rang)}
        total = sum(brut.values())
        parts = {k: v / total for k, v in brut.items()}
        for b in vivantes:                                   # une jeune branche a le temps de faire ses preuves
            if b.battements < self.r.jeunesse:
                parts[b.nom] = max(parts[b.nom], self.r.seve_jeune)
        total = sum(parts.values())
        return {k: v / total for k, v in parts.items()}

    def noter_seve(self, heure: str | None = None):
        heure = heure or maintenant()
        for nom, part in self.parts_de_seve().items():
            self.branches[nom].seve.append((heure, round(part, 4)))

    # ---- décisions du jardinier ----
    def decisions(self) -> list[tuple]:
        """Ce que le jardinier veut faire après ce battement : ("couper", nom), ("fusion", a, b), ("bourgeon", parent)."""
        actions = []
        vivantes = self.vivantes()
        cime = self.branches.get(self.cime) if self.cime else None
        if cime is None:
            return actions
        for b in vivantes:
            if (b.nom != cime.nom and b.battements >= self.r.jeunesse + self.r.coupe_apres
                    and b.sans_progres >= self.r.coupe_apres and b.score is not None
                    and b.score < cime.score - self.r.coupe_ecart):
                actions.append(("couper", b.nom))
        coupees = {a[1] for a in actions}
        restantes = [b for b in vivantes if b.nom not in coupees]
        mures = sorted([b for b in restantes if b.battements >= self.r.fusion_maturite and b.score is not None],
                       key=lambda b: b.score, reverse=True)
        if len(mures) >= 2 and self.battements - self.dernier_essai_fusion >= self.r.fusion_tous:
            actions.append(("fusion", mures[0].nom, mures[1].nom))
        if (len(restantes) < self.r.places and cime.battements >= 2
                and self.battements - self.dernier_bourgeon >= self.r.bourgeon_tous):
            actions.append(("bourgeon", cime.nom))
        return actions

    @staticmethod
    def muter(temperament: dict, rng: random.Random) -> dict:
        """Un tempérament légèrement différent : plus ou moins rapide, plus ou moins prudent."""
        t = dict(temperament)
        if t.get("miroir", 0.0) == 0.0 and rng.random() < 0.5:
            t["miroir"] = 0.5            # 13/10 : essayer les graphiques retournés (contre l'apprentissage par cœur)
            return t
        # 14/10 : flou et échelles cachées (contre le par cœur, vision du trader) mutent s'ils existent
        trait = rng.choice(["vitesse", "lot", "oubli", "usure"] + [k for k in ("bruit", "masque") if k in t])
        if trait == "bruit":
            t["bruit"] = round(min(0.5, max(0.0, t["bruit"] * rng.choice([0.5, 2.0]) if t["bruit"] else 0.05)), 3)
        elif trait == "masque":
            t["masque"] = round(min(0.5, max(0.0, t["masque"] + rng.choice([-0.1, 0.1]))), 3)
        elif trait == "vitesse":
            t["vitesse"] = min(3e-3, max(3e-5, t["vitesse"] * rng.choice([0.5, 2.0])))
        elif trait == "lot":
            t["lot"] = int(min(2048, max(128, t["lot"] * rng.choice([0.5, 2.0]))))
        elif trait == "oubli":
            t["oubli"] = round(min(0.4, max(0.0, t["oubli"] + rng.choice([-0.05, 0.05]))), 3)
        else:
            t["usure"] = min(1e-2, max(1e-6, t["usure"] * rng.choice([0.1, 10.0])))
        return t

    # ---- mémoire ----
    def sauver(self, fichier: Path):
        etat = {"battements": self.battements, "dernier_bourgeon": self.dernier_bourgeon,
                "dernier_essai_fusion": self.dernier_essai_fusion, "nees": self.nees, "cime": self.cime,
                "envois": self.envois, "reglages": asdict(self.r),
                "branches": {k: asdict(b) for k, b in self.branches.items()}}
        tmp = fichier.with_suffix(".tmp")
        tmp.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(fichier)

    @classmethod
    def charger(cls, fichier: Path) -> "Arbre":
        etat = json.loads(fichier.read_text(encoding="utf-8"))
        a = cls(Reglages(**etat["reglages"]))
        for k in ("battements", "dernier_bourgeon", "dernier_essai_fusion", "nees", "cime", "envois"):
            setattr(a, k, etat[k])
        a.branches = {k: Branche(**b) for k, b in etat["branches"].items()}
        for b in a.branches.values():                  # progrès recalculé sur le niveau (règle du 13/10)
            notes, b.meilleur, b.sans_progres = b.scores, None, 0
            for i in range(1, len(notes) + 1):
                fen = [s[1] for s in notes[max(0, i - NIVEAU_SUR):i]]
                niveau = sum(fen) / len(fen)
                if b.meilleur is None or niveau > b.meilleur:
                    b.meilleur, b.sans_progres = niveau, 0
                else:
                    b.sans_progres += 1
        a._elire_cime()
        return a
