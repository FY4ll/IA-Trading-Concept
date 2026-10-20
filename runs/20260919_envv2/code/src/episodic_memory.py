"""
episodic_memory.py
===================
Donne à l'agent une "mémoire" persistante de ses expériences passées,
au-delà du simple replay buffer interne de l'algorithme RL.

Chaque épisode marquant (trade clôturé) est stocké avec :
  - le contexte de marché au moment de la décision (features résumées)
  - l'action prise
  - le résultat obtenu (pnl, drawdown associé)
  - la génération/version de l'agent qui l'a produit

Cela permet :
  1. d'analyser a posteriori "dans quelles situations l'agent réussit/échoue"
  2. de faire une recherche par similarité ("ai-je déjà vu une situation
     proche de celle-ci, et qu'est-ce que ça avait donné ?") utilisable
     comme signal additionnel ou pour du diagnostic humain.
"""
from __future__ import annotations
import sqlite3
import json
import time
import threading
import numpy as np


class EpisodicMemory:
    def __init__(self, db_path: str = "data/episodic_memory.sqlite", max_episodes: int = 5000,
                 private_styles=None):
        """`private_styles` (07/10/2026, ex. ["AUREXIS"]) : styles qui ont leur PROPRE mémoire -- ils ne lisent
        que leurs propres épisodes (colonne `style`), les autres ne les voient jamais, et chaque mémoire a sa
        propre limite `max_episodes` (les nouveaux trades d'un style privé n'effacent jamais la mémoire commune)."""
        self.db_path = db_path
        self.max_episodes = max_episodes
        self.private_styles = tuple(private_styles or ())
        self._init_db()

    def _shared_clause(self) -> tuple[str, list]:
        """Condition SQL de la mémoire COMMUNE (tout sauf les styles à mémoire privée)."""
        if not self.private_styles:
            return "1=1", []
        return (f"(style IS NULL OR style NOT IN ({','.join('?' for _ in self.private_styles)}))",
                list(self.private_styles))

    def _init_db(self):
        # check_same_thread=False : l'instance EpisodicMemory est créée dans
        # le thread principal (autonomous_agent.py) mais utilisée depuis le
        # thread d'évolution continue ("EVOLUTION"). SQLite interdit ça par
        # défaut ; on l'autorise explicitement puisqu'un seul thread à la
        # fois y accède réellement (pas d'écriture concurrente).
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL,
                generation INTEGER,
                context TEXT,      -- vecteur de features au moment du trade (JSON)
                action INTEGER,
                pnl_pct REAL,
                drawdown REAL,
                source TEXT DEFAULT 'backtest',
                style TEXT
            )
        """)
        # MIGRATION : les bases créées avant l'ajout de `style`/`symbol`
        # n'ont pas la colonne -- ALTER TABLE ... ADD COLUMN est sans effet
        # sur les lignes déjà présentes (reste NULL pour elles, ce qui est
        # correct : on ne peut pas rétroactivement savoir de quel
        # style/symbole elles viennent -- toutes les lignes d'avant LOT 2
        # phase 4 sont implicitement de l'or, seul symbole qui existait).
        existing_cols = {row[1] for row in self.conn.execute("PRAGMA table_info(episodes)")}
        if "style" not in existing_cols:
            self.conn.execute("ALTER TABLE episodes ADD COLUMN style TEXT")
        if "symbol" not in existing_cols:
            self.conn.execute("ALTER TABLE episodes ADD COLUMN symbol TEXT")
        self.conn.commit()

    def store(self, context: np.ndarray, action: int, pnl_pct: float,
              drawdown: float, generation: int = 0, source: str = "backtest",
              style: str | None = None, symbol: str | None = None):
        """`source` distingue un épisode issu d'un BACKTEST (rejoue de données
        historiques pendant l'entraînement) d'un épisode issu du trading LIVE
        réel (voir demo_trader.py::_LiveMemoryTracker). Cette distinction
        existe pour une seule raison : `snapshot(sources=["backtest"])` (voir
        continuous_trainer.py) exclut les épisodes live du signal mémoire
        donné aux candidats à l'entraînement -- sans ça, un trade réel de
        CETTE nuit (contexte de marché très récent) pouvait être retrouvé par
        similarité lors de l'évaluation d'un candidat sur une fenêtre
        historique bien ANTÉRIEURE, une fuite d'information du futur vers le
        passé qui gonflerait artificiellement la vraisemblance des scores.
        Le trading live (memory.snapshot() sans filtre `sources`, voir
        demo_trader.py) continue lui de voir TOUT l'historique (backtest ET
        live) -- ça ne pose aucun problème, une décision réelle prise
        aujourd'hui a parfaitement le droit de s'appuyer sur l'expérience
        déjà accumulée jusqu'à maintenant.

        `style` (ex: "M15", "H1") identifie le style de trading qui a produit
        cet épisode -- None pour les épisodes anciens ou dont le style n'est
        pas pertinent (voir reliability_tracker.py, qui compare chaque style
        live à SON PROPRE backtest walk-forward plutôt qu'à un agrégat).

        `symbol` (LOT 2, phase 4, point 9 -- ex: "XAUUSD", "EURUSD")
        identifie le symbole tradé -- None pour les épisodes d'avant ce
        mécanisme (implicitement de l'or). Le trading live n'interroge
        JAMAIS que l'or (voir `snapshot(symbols=["XAUUSD"])`, appelé depuis
        demo_trader.py) : un souvenir d'un trade EURUSD synthétique
        n'a aucune pertinence pour une décision réelle sur l'or."""
        with self._lock:
            self.conn.execute(
                "INSERT INTO episodes (created_at, generation, context, action, pnl_pct, drawdown, source, style, symbol) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), generation, json.dumps(context.tolist()), int(action),
                 float(pnl_pct), float(drawdown), source, style, symbol),
            )
            self.conn.commit()
            self._prune()

    def store_many(self, records: list[dict]):
        """Écriture GROUPÉE (06/10/2026) : une seule transaction et un seul élagage pour tous les épisodes d'un
        candidat -- `store()` un par un coûtait une écriture disque + un comptage par trade (20 à 40 min perdues
        par cycle d'évolution pour 8 x 2000 trades). Chaque record : mêmes champs que `store()`."""
        if not records:
            return
        now = time.time()
        rows = [(now, int(r.get("generation", 0)), json.dumps(np.asarray(r["context"]).tolist()), int(r["action"]),
                 float(r["pnl_pct"]), float(r["drawdown"]), r.get("source", "backtest"), r.get("style"),
                 r.get("symbol")) for r in records]
        with self._lock:
            self.conn.executemany(
                "INSERT INTO episodes (created_at, generation, context, action, pnl_pct, drawdown, source, style, symbol) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
            self.conn.commit()
            self._prune()

    def _prune(self):
        # une limite par mémoire : la mémoire commune, puis chaque style à mémoire privée
        groups = [self._shared_clause()] + [("style = ?", [s]) for s in self.private_styles]
        for clause, params in groups:
            count = self.conn.execute(f"SELECT COUNT(*) FROM episodes WHERE {clause}", params).fetchone()[0]
            if count > self.max_episodes:
                to_delete = count - self.max_episodes
                self.conn.execute(
                    "DELETE FROM episodes WHERE id IN "
                    f"(SELECT id FROM episodes WHERE {clause} ORDER BY created_at ASC LIMIT ?)",
                    (*params, to_delete),
                )
                self.conn.commit()

    def snapshot(self, dim: int | None = None, sources: list[str] | None = None,
                 symbols: list[str] | None = None, style: str | None = None):
        """Retourne un instantané (contexts, pnls, drawdowns) en tableaux
        numpy, calculé UNE FOIS (pas à chaque pas de simulation) et pensé
        pour être transmis à `src.memory_features.MemoryQuery` -- y compris
        à travers un `ProcessPoolExecutor` (voir continuous_trainer.py),
        puisqu'il ne contient que des tableaux numpy picklables, jamais la
        connexion sqlite elle-même.

        `dim` filtre sur les épisodes dont le contexte a exactement cette
        dimension : plusieurs styles de trading (timeframes différentes)
        partagent la même base mais ont des jeux de features de tailles
        différentes, donc pas directement comparables entre eux.

        `sources` (ex: ["backtest"]) restreint aux épisodes dont la colonne
        `source` correspond -- voir `store()` pour la raison (empêcher les
        épisodes live de fuiter dans l'évaluation historique). None (par
        défaut) ne filtre pas : utilisé par le trading live, qui doit voir
        tout l'historique disponible.

        `symbols` (LOT 2, phase 4, point 9 -- ex: ["XAUUSD"]) restreint aux
        épisodes dont la colonne `symbol` correspond, INCLUANT les lignes
        `symbol IS NULL` (tous les épisodes d'avant ce mécanisme, ou tout
        entraînement mono-actif qui ne le renseigne jamais -- implicitement
        de l'or, jamais exclus silencieusement). Le trading live
        n'interroge QUE l'or (voir demo_trader.py) : un souvenir d'un trade
        EURUSD synthétique n'a aucune pertinence pour une décision réelle.

        `style` (07/10/2026) : style qui va lire cette mémoire. S'il fait partie
        de `private_styles`, seuls SES épisodes sont retournés, tous marchés
        confondus (`symbols` ignoré : il apprend sur plusieurs marchés) ; sinon
        les épisodes des styles à mémoire privée sont exclus.

        Retourne None si aucun épisode ne correspond (mémoire vide, ou
        aucun épisode de cette dimension encore enregistré).
        """
        private = style is not None and style in self.private_styles
        with self._lock:
            conditions, params = [], []
            if private:
                conditions.append("style = ?")
                params.append(style)
                symbols = None
            elif self.private_styles:
                clause, p = self._shared_clause()
                conditions.append(clause)
                params.extend(p)
            if sources:
                conditions.append(f"source IN ({','.join('?' for _ in sources)})")
                params.extend(sources)
            if symbols:
                conditions.append(f"(symbol IN ({','.join('?' for _ in symbols)}) OR symbol IS NULL)")
                params.extend(symbols)
            query = "SELECT context, pnl_pct, drawdown FROM episodes"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            rows = self.conn.execute(query, tuple(params)).fetchall()
        contexts, pnls, drawdowns = [], [], []
        for ctx_json, pnl_pct, drawdown in rows:
            ctx = np.asarray(json.loads(ctx_json), dtype=np.float32)
            if dim is not None and ctx.shape != (dim,):
                continue
            contexts.append(ctx)
            pnls.append(pnl_pct)
            drawdowns.append(drawdown)
        if not contexts:
            return None
        return np.stack(contexts), np.array(pnls, dtype=np.float32), np.array(drawdowns, dtype=np.float32)

    def stats_by_generation(self):
        with self._lock:
            rows = self.conn.execute(
                "SELECT generation, AVG(pnl_pct), AVG(drawdown), COUNT(*) "
                "FROM episodes GROUP BY generation ORDER BY generation"
            ).fetchall()
        return [
            {"generation": g, "avg_pnl_pct": avg_pnl, "avg_drawdown": avg_dd, "n_trades": n}
            for g, avg_pnl, avg_dd, n in rows
        ]

    def close(self):
        with self._lock:
            self.conn.close()
