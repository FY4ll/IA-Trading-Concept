# Repris de Run A (src/memory_features.py, version du 08/10/2026) pour l'architecture v3 -- calculs IDENTIQUES
# (prouvé par tests/test_cerveau_equivalence.py). Toute modification doit garder ce test vert.
"""
memory_features.py
===================
Traduit un instantané de mémoire épisodique (voir src/episodic_memory.py)
en un signal directement exploitable par l'agent, PENDANT l'entraînement et
la décision : "dans des situations de marché proches de celle-ci, qu'est-ce
que mes versions précédentes ont obtenu (pnl, drawdown) ?"

Avant ce module, la mémoire épisodique était peuplée à chaque cycle
(continuous_trainer.py) mais jamais relue : `retrieve_similar()` restait du
code mort. `MemoryQuery` est ce qui manquait pour fermer la boucle.

Volontairement séparé de `EpisodicMemory` : ce module ne touche jamais à
sqlite, il travaille sur un instantané déjà chargé en mémoire (tableaux
numpy). C'est ce qui le rend utilisable tel quel dans un processus
d'entraînement séparé (voir `continuous_trainer.py`, un processus par
candidat) : on calcule l'instantané UNE FOIS par cycle dans le processus
principal, on le transmet (picklable), et chaque candidat interroge sa
propre copie en mémoire -- jamais de connexion sqlite partagée entre
processus, jamais de requête disque à chaque pas de simulation.
"""
from __future__ import annotations
import numpy as np

# Borne le nombre d'épisodes réellement comparés à chaque requête, quel que
# soit `memory.max_episodes` dans la config : au-delà de quelques milliers,
# le coût d'une recherche par similarité (même vectorisée) par PAS de
# simulation deviendrait significatif sur un entraînement de 16000+ pas.
# Un sous-échantillon aléatoire (tiré une seule fois, à la construction)
# garde un signal statistiquement représentatif à coût borné.
_MAX_QUERY_POOL = 3000


class MemoryQuery:
    """Recherche vectorisée des k plus proches voisins dans un instantané de
    mémoire épisodique (voir `EpisodicMemory.snapshot`). Sans mémoire
    (snapshot vide ou absent -- typique des tout premiers cycles), retourne
    un signal neutre (0.0, 0.0) : l'agent démarre donc sans biais tant qu'il
    n'a pas d'expérience passée à consulter, jamais de crash."""

    def __init__(self, snapshot, top_k: int = 5):
        self.top_k = max(1, top_k)
        self.contexts = None
        if snapshot is not None:
            contexts, pnls, drawdowns = snapshot
            contexts = np.asarray(contexts, dtype=np.float32)
            if len(contexts) > _MAX_QUERY_POOL:
                idx = np.random.default_rng(0).choice(len(contexts), _MAX_QUERY_POOL, replace=False)
                contexts, pnls, drawdowns = contexts[idx], np.asarray(pnls)[idx], np.asarray(drawdowns)[idx]
            if len(contexts) > 0:
                self.contexts = contexts
                self.pnls = np.asarray(pnls, dtype=np.float32)
                self.drawdowns = np.asarray(drawdowns, dtype=np.float32)

    def query(self, context: np.ndarray) -> tuple[float, float]:
        """Retourne (pnl_pct moyen, drawdown moyen) des k épisodes passés les
        plus proches du contexte de marché actuel."""
        if self.contexts is None:
            return 0.0, 0.0
        k = min(self.top_k, len(self.contexts))
        dists = np.linalg.norm(self.contexts - context, axis=1)
        nearest = np.argpartition(dists, k - 1)[:k]
        return float(self.pnls[nearest].mean()), float(self.drawdowns[nearest].mean())

    def query_many(self, X: np.ndarray, chunk: int = 2048) -> np.ndarray:
        """07/10/2026 : même recherche que `query` pour TOUTES les lignes de X d'un coup (calcul matriciel :
        |x - c|² = |x|² + |c|² - 2 x·c), ~50x plus rapide qu'un appel par bougie. Retourne un tableau (n, 2) :
        (pnl moyen, drawdown moyen) des k plus proches voisins de chaque ligne."""
        X = np.asarray(X)
        out = np.zeros((len(X), 2), dtype=np.float64)
        if self.contexts is None or len(X) == 0:
            return out
        k = min(self.top_k, len(self.contexts))
        if len(X) >= 50_000:
            gpu = self._query_many_gpu(X, k)          # gros volume (entraînement) : carte graphique si disponible
            if gpu is not None:
                return gpu
        C = self.contexts.astype(np.float64)
        c2 = (C * C).sum(axis=1)
        for a in range(0, len(X), chunk):
            x = X[a:a + chunk].astype(np.float64)
            d2 = (x * x).sum(axis=1)[:, None] + c2[None, :] - 2.0 * (x @ C.T)
            nn = np.argpartition(d2, k - 1, axis=1)[:, :k]
            out[a:a + chunk, 0] = self.pnls[nn].mean(axis=1)
            out[a:a + chunk, 1] = self.drawdowns[nn].mean(axis=1)
        return out

    def _query_many_gpu(self, X: np.ndarray, k: int, chunk: int = 4096):
        """Même calcul en simple précision sur la carte graphique (None si indisponible). Réservé à l'entraînement :
        une égalité parfaite de voisins n'y est pas nécessaire, l'évaluation garde le calcul processeur exact."""
        try:
            import torch
            if not torch.cuda.is_available():
                return None
            dev = torch.device("cuda")
            C = torch.as_tensor(self.contexts, dtype=torch.float32, device=dev)
            c2 = (C * C).sum(dim=1)
            pn = torch.as_tensor(self.pnls, dtype=torch.float32, device=dev)
            dd = torch.as_tensor(self.drawdowns, dtype=torch.float32, device=dev)
            out = np.zeros((len(X), 2), dtype=np.float64)
            with torch.no_grad():
                for a in range(0, len(X), chunk):
                    x = torch.as_tensor(np.ascontiguousarray(X[a:a + chunk], dtype=np.float32), device=dev)
                    d2 = (x * x).sum(dim=1, keepdim=True) + c2[None, :] - 2.0 * (x @ C.T)
                    nn = torch.topk(d2, k, dim=1, largest=False).indices
                    out[a:a + chunk, 0] = pn[nn].mean(dim=1).double().cpu().numpy()
                    out[a:a + chunk, 1] = dd[nn].mean(dim=1).double().cpu().numpy()
            return out
        except Exception:
            return None
