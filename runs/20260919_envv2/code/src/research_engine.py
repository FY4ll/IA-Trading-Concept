"""
research_engine.py
===================
Recherche autonome contrôlée (05/10/2026, vision "Autonomous Trader V1", §28-31,
§49, §63-64) : OBSERVATION -> HYPOTHÈSE -> EXPÉRIENCE -> CONCLUSION.

  - Registre append-only reports/research_journal.jsonl : chaque hypothèse et
    chaque expérience (question, motivation, méthode, règle de décision fixée
    AVANT le résultat, résultat, conclusion). Rien n'est jamais effacé, les
    échecs restent visibles ; le nombre total d'expériences est suivi
    (tests multiples).
  - generate_hypotheses(diagnostics) : transforme les signaux du diagnostic
    (src/diagnostics.py) en hypothèses testables, sans doublon et avec un
    budget par style (pas de recherche sans fin jusqu'à un résultat chanceux).
  - Filtres ADOPTÉS (data/research_adopted.json) : la seule chose que la
    recherche peut changer seule est un filtre d'ouverture par style, lu par
    src/market_gate.py. Elle ne peut JAMAIS toucher aux limites de risque, au
    coupe-circuit, aux portes de validation ni à l'historique.
"""
from __future__ import annotations
import json
import os
import time
import uuid
from datetime import datetime, timezone

JOURNAL_PATH = os.path.join("reports", "research_journal.jsonl")
ADOPTED_PATH = os.path.join("data", "research_adopted.json")
MAX_OPEN_PER_STYLE = 3
ALLOWED_FILTER_KEYS = ("block_vol_classes", "block_regimes")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def load(path: str = JOURNAL_PATH) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def record(entry: dict, path: str = JOURNAL_PATH) -> dict:
    entry = {"id": entry.get("id") or uuid.uuid4().hex[:12], "ts_utc": _now(), **entry}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return entry


def latest_by_id(entries: list[dict]) -> dict[str, dict]:
    """Le registre est append-only : l'état courant d'une hypothèse est sa DERNIÈRE ligne."""
    state: dict[str, dict] = {}
    for e in entries:
        state[e["id"]] = {**state.get(e["id"], {}), **e}
    return state


def n_experiments(path: str = JOURNAL_PATH) -> int:
    return sum(1 for e in latest_by_id(load(path)).values() if e.get("kind") == "experiment")


def open_hypotheses(path: str = JOURNAL_PATH) -> list[dict]:
    return [e for e in latest_by_id(load(path)).values()
            if e.get("kind") == "hypothesis" and e.get("status") in ("proposed", "running")]


def _hyp(style, key, observation, hypothesis, question, experiment, decision_rule, hyp_type, params=None):
    return {"kind": "hypothesis", "status": "proposed", "style": style, "key": key, "type": hyp_type,
            "observation": observation, "hypothesis": hypothesis, "question": question,
            "experiment": experiment, "decision_rule": decision_rule, "params": params or {}}


def generate_hypotheses(diag: dict, path: str = JOURNAL_PATH) -> list[dict]:
    """Nouvelles hypothèses à partir d'un diagnostic, enregistrées dans le registre."""
    existing = latest_by_id(load(path)).values()
    known_keys = {e.get("key") for e in existing if e.get("kind") == "hypothesis"
                  and e.get("status") in ("proposed", "running")}
    open_count: dict[str, int] = {}
    for e in existing:
        if e.get("kind") == "hypothesis" and e.get("status") in ("proposed", "running"):
            open_count[e.get("style")] = open_count.get(e.get("style"), 0) + 1
    new = []
    for style, s in (diag.get("styles") or {}).items():
        cands = []
        for vol, st in ((s.get("live_by_vol_class") or {}).items()):
            if st.get("n", 0) >= 10 and (st.get("avg_r") or 0) < -0.3:
                cands.append(_hyp(
                    style, f"{style}:vol:{vol}",
                    f"{st['n']} trades live ouverts en volatilité {vol} : R moyen {st['avg_r']:+.2f}.",
                    f"Bloquer les ouvertures en volatilité {vol} améliore l'espérance sans dégrader le profil prop firm.",
                    f"Un filtre volatilité {vol} améliore-t-il le Sharpe hors échantillon ?",
                    "Rejouer le champion avec le filtre (scripts/regime_report.py) sur la période d'avant la lockbox "
                    "puis sur la lockbox.",
                    "Adopter si Sharpe >= base sur les DEUX périodes, drawdown <= base + 1 pt, "
                    "Challenge FTMO lockbox >= base - 2 pts.", "regime_filter", {"block_vol_classes": [vol]}))
        for reg, st in ((s.get("live_by_regime") or {}).items()):
            if st.get("n", 0) >= 10 and (st.get("avg_r") or 0) < -0.3:
                cands.append(_hyp(
                    style, f"{style}:regime:{reg}",
                    f"{st['n']} trades live ouverts en régime {reg} : R moyen {st['avg_r']:+.2f}.",
                    f"Bloquer les ouvertures en régime {reg} améliore l'espérance.",
                    f"Un filtre régime {reg} améliore-t-il le Sharpe hors échantillon ?",
                    "Rejouer le champion avec le filtre sur la période d'avant la lockbox puis sur la lockbox.",
                    "Adopter si Sharpe >= base sur les DEUX périodes, drawdown <= base + 1 pt, "
                    "Challenge FTMO lockbox >= base - 2 pts.", "regime_filter", {"block_regimes": [reg]}))
        flags = set(s.get("flags") or [])
        if "edge_degradation" in flags or "win_rate_drop" in flags:
            cands.append(_hyp(
                style, f"{style}:degradation", f"Résultats live sous l'attendu ({', '.join(sorted(flags))}).",
                "Le marché récent diffère de la période d'entraînement (dérive) ou l'exécution coûte plus que prévu.",
                "La dégradation vient-elle de la dérive des variables, du régime ou de l'exécution ?",
                "Comparer dérive (PSI), régimes récents et slippage ; si dérive forte, réentraîner sur données récentes.",
                "Conclure sur la cause dominante ; un réentraînement passe par la porte lockbox normale.", "diagnosis"))
        if "inactivity" in flags:
            cands.append(_hyp(
                style, f"{style}:inactivity", "Beaucoup moins de trades live qu'attendu d'après la lockbox.",
                "Un garde-fou d'exécution ou un seuil de décision bloque plus souvent qu'en backtest.",
                "Quelles raisons de WAIT dominent, et sont-elles légitimes ?",
                "Lire les raisons de WAIT du journal de décision et les comparer au backtest.",
                "Corriger seulement un blocage non voulu ; ne jamais forcer des trades.", "diagnosis"))
        if "overtrading" in flags:
            cands.append(_hyp(
                style, f"{style}:overtrading", "Beaucoup plus de trades live qu'attendu d'après la lockbox.",
                "Des allers-retours d'exécution (taille, cooldown) multiplient les trades.",
                "Les trades supplémentaires viennent-ils de l'IA ou de l'exécution ?",
                "Compter les clôtures/réouvertures dans la même direction dans le journal.",
                "Corriger l'exécution si elle est en cause.", "diagnosis"))
        if (diag.get("drift") or {}).get("max_psi", 0) >= 0.25 and style == next(iter(diag["styles"])):
            cands.append(_hyp(
                "ALL", "ALL:drift", f"Dérive forte des variables (PSI max {diag['drift']['max_psi']:.2f}).",
                "Le marché actuel sort de la distribution vue en entraînement.",
                "Les champions restent-ils fiables sur le régime actuel ?",
                "Rejouer les champions sur les 3 derniers mois et comparer à la lockbox.",
                "Si dégradation significative : réentraîner (porte lockbox normale).", "diagnosis"))
        for c in cands:
            st_name = c["style"]
            if c["key"] in known_keys or open_count.get(st_name, 0) >= MAX_OPEN_PER_STYLE:
                continue
            new.append(record(c, path))
            known_keys.add(c["key"])
            open_count[st_name] = open_count.get(st_name, 0) + 1
    return new


def adopted_filters(path: str = ADOPTED_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def adopt_filter(style: str, filt: dict, experiment_id: str, path: str = ADOPTED_PATH) -> dict:
    """Seuls des filtres d'ouverture (volatilité/régime) peuvent être adoptés -- jamais un réglage de risque."""
    clean = {k: list(v) for k, v in filt.items() if k in ALLOWED_FILTER_KEYS}
    if not clean:
        raise ValueError(f"filtre non autorisé : {filt}")
    data = adopted_filters(path)
    data[style] = {**clean, "experiment_id": experiment_id, "adopted_at": _now()}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data[style]


def filter_decision(base: dict, filt: dict) -> tuple[bool, str]:
    """Règle de décision fixée à l'avance pour un filtre d'ouverture.
    `base`/`filt` : {"pre_lockbox": summary, "lockbox": summary} (src/lockbox_analysis.summary)."""
    why = []
    for period in ("pre_lockbox", "lockbox"):
        b, f = base[period], filt[period]
        if f["sharpe"] < b["sharpe"]:
            why.append(f"{period} : Sharpe {f['sharpe']:.2f} < base {b['sharpe']:.2f}")
        if f["max_drawdown"] > b["max_drawdown"] + 0.01:
            why.append(f"{period} : drawdown {f['max_drawdown']:.1%} > base {b['max_drawdown']:.1%} + 1 pt")
    bc = (base["lockbox"].get("prop_firm") or {}).get("challenge_pass")
    fc = (filt["lockbox"].get("prop_firm") or {}).get("challenge_pass")
    if bc is not None and fc is not None and fc < bc - 0.02:
        why.append(f"Challenge FTMO {fc:.0%} < base {bc:.0%} - 2 pts")
    return (not why, "; ".join(why) or "toutes les conditions remplies")
