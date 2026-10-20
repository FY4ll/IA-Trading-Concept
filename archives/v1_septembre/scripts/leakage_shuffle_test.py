"""
scripts/leakage_shuffle_test.py
================================
Diagnostic de FUITE DE DONNÉES par "target shuffling" (voir
src/stress_test.py::shuffle_target_relative_to_features pour le
raisonnement complet) : entraîne un petit agent RL sur des données
d'ENTRAÎNEMENT dont les colonnes prix (open/high/low/close) ont été
décalées CIRCULAIREMENT par rapport à leurs propres features/indicateurs
techniques (rompt volontairement toute relation causale réelle
"features observées à t" -> "prix qui a suivi"), puis l'évalue via la
marche en avant standard (src.backtester.evaluate_agent_walkforward) sur
des données de VALIDATION RÉELLES, non décalées.

RAISONNEMENT : si l'agent obtient malgré tout un score clairement positif
sur ces données réelles après avoir été entraîné sur une association
features->prix ARTIFICIELLEMENT décorrélée, ça ne peut logiquement venir
que d'une fuite d'information ailleurs dans le pipeline (normalisation
calculée sur des statistiques qui débordent sur la période évaluée, feature
qui regarde involontairement en avant, split qui laisse fuiter de
l'info...) -- jamais d'un vrai edge appris sur le prix, puisque cette
relation n'existe plus dans les données d'entraînement. Imprime donc DEUX
scores pour comparaison directe :
  - le score RÉEL (entraînement + évaluation sur données NON décalées) --
    sert de référence : doit normalement être positif/raisonnable si le
    pipeline sait effectivement apprendre quelque chose de réel sur ce
    petit budget d'entraînement.
  - le score MÉLANGÉ (entraînement sur données décalées, évaluation sur
    données réelles) -- verdict PASS si <= ~0 (nul/négatif, comme attendu
    sur une relation features->prix décorrélée), WARN (message visible) si
    clairement positif.

Script DIAGNOSTIC autonome (à lancer manuellement/périodiquement), PAS un
test pytest -- même un entraînement RL minimal prend de l'ordre de la
minute, pas de la milliseconde (voir tests/test_leakage_shuffle.py pour le
test unitaire RAPIDE de la fonction de mélange elle-même, sans
entraînement). Isolé de la production comme les autres scripts
scripts/pilot_m15_v*.py : ne touche JAMAIS models/, aucune config sur
disque n'est modifiée, ne persiste rien -- tourne entièrement en mémoire.

Lancement :
    python scripts/leakage_shuffle_test.py
    python scripts/leakage_shuffle_test.py --synthetic       (sans dépendre des CSV Kaggle, plus rapide)
    python scripts/leakage_shuffle_test.py --timesteps 8000  (sonde plus longue/fiable, plus lente)
"""
import sys
import os
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--synthetic", action="store_true",
                     help="utilise generate_synthetic_ohlcv au lieu d'un CSV Kaggle réel "
                          "(plus rapide, aucune dépendance de fichier -- utile en CI/hors machine de dev).")
parser.add_argument("--csv", default="data/kaggle_gold/XAU_1h_data.csv",
                     help="CSV Kaggle utilisé si --synthetic n'est pas passé.")
parser.add_argument("--timesteps", type=int, default=4000,
                     help="pas d'entraînement PAR agent (2 agents entraînés dans ce script : "
                          "REEL et MELANGE) -- volontairement petit, diagnostic pas entraînement de production.")
parser.add_argument("--bars", type=int, default=6000,
                     help="nombre de bougies utilisées avant split train/val (les plus récentes si CSV réel).")
parser.add_argument("--seed", type=int, default=1)
parser.add_argument("--seeds", type=int, default=10,
                     help="LOT 2, phase 6 : nombre de graines de MÉLANGE indépendantes évaluées -- "
                          "une seule graine peut donner un score mélangé positif par pur hasard "
                          "statistique (faux négatif du diagnostic) ; répéter sur plusieurs graines "
                          "et regarder la MOYENNE/l'écart-type est plus robuste qu'un seul essai.")
args = parser.parse_args()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [LEAKAGE-SHUFFLE] %(message)s")
log = logging.getLogger("leakage_shuffle_test")

from src.data_loader import load_kaggle_ohlcv_csv, generate_synthetic_ohlcv, chronological_split
from src.features import add_technical_features, FEATURE_COLUMNS, normalize_features
from src.stress_test import shuffle_target_relative_to_features
from src.trading_env import TradingEnv
from src.agent import TradingAgent
from src.backtester import evaluate_agent_walkforward


# --------------------------------------------------------------------- #
# 1) Données : réelles (Kaggle, sous-échantillon récent) ou synthétiques.
# --------------------------------------------------------------------- #
if args.synthetic:
    log.info(f"Données SYNTHÉTIQUES ({args.bars} bougies, seed={args.seed}).")
    raw_df = generate_synthetic_ohlcv(n_bars=args.bars, seed=args.seed)
else:
    log.info(f"Données RÉELLES : {args.csv} (limité aux {args.bars} bougies les plus récentes).")
    full_df = load_kaggle_ohlcv_csv(args.csv)
    raw_df = full_df.tail(args.bars).reset_index(drop=True)

df = add_technical_features(raw_df)
train_df, val_df, _ = chronological_split(df, 0.7, 0.3)
log.info(f"train={len(train_df)} bougies, val={len(val_df)} bougies.")

# Normalisation (z-score) : stats calculées sur TRAIN uniquement, réutilisées
# telles quelles pour val -- jamais de fuite via la normalisation. Même
# ordre exact que autonomous_agent.py (split PUIS normalize, stats du train
# propagées à val) pour que ce diagnostic reflète fidèlement le pipeline réel.
train_norm, stats = normalize_features(train_df, columns=FEATURE_COLUMNS)
val_norm, _ = normalize_features(val_df, stats, columns=FEATURE_COLUMNS)

# --------------------------------------------------------------------- #
# 2) Hyperparamètres volontairement PETITS/RAPIDES : pas de LSTM (features
#    extractor le plus lourd du projet), réseau étroit, peu de pas -- ce
#    script est un diagnostic de quelques minutes, pas un entraînement de
#    production (voir README continuous_trainer pour les vrais budgets).
# --------------------------------------------------------------------- #
HYPERPARAMS = {
    "algo": "PPO",
    "use_lstm": False,
    "net_arch": [64, 64],
    "learning_rate": 3e-4,
    "n_steps": 512,
    "batch_size": 64,
    "n_epochs": 4,
    "ent_coef": 0.01,
}
ENV_KWARGS = dict(
    window_size=30,
    initial_balance=10000,
    transaction_cost=0.0002,
    reward_type="risk_adjusted",
    drawdown_penalty=2.0,
    max_position=1,
    feature_columns=FEATURE_COLUMNS,
)


def _shuffle_score_stats(scores: list[float]) -> dict:
    """Cœur testable de l'agrégation --seeds (LOT 2, phase 6) -- séparé pour
    être testé rapidement sans ré-entraîner d'agent (voir
    tests/test_leakage_shuffle_seeds.py). `stdev` nécessite au moins 2
    valeurs (statistics.stdev lève sinon) -- 0.0 pour une seule graine,
    jamais une exception."""
    import statistics
    return {
        "mean": statistics.mean(scores),
        "std": statistics.stdev(scores) if len(scores) > 1 else 0.0,
        "min": min(scores),
        "max": max(scores),
        "n_positive": sum(1 for s in scores if s > 0),
        "n_seeds": len(scores),
    }


def _train_and_evaluate(train_data, val_data, label: str) -> dict:
    log.info(f"[{label}] entraînement ({args.timesteps} pas)...")
    env = TradingEnv(train_data, **ENV_KWARGS)
    agent = TradingAgent(env, HYPERPARAMS)
    agent.learn(args.timesteps, label=label)
    metrics = evaluate_agent_walkforward(agent, val_data, ENV_KWARGS, n_windows=2)
    # Même formule de score que les scripts pilotes (sharpe pénalisé par le
    # drawdown) -- comparable directement à ce qui est utilisé en production.
    score = metrics["sharpe"] - 2.0 * metrics["max_drawdown"]
    log.info(f"[{label}] sharpe={metrics['sharpe']:.3f} max_drawdown={metrics['max_drawdown']:.3f} "
              f"n_trades={metrics['n_trades']} -> score={score:.3f}")
    return {"metrics": metrics, "score": score}


# --------------------------------------------------------------------- #
# 3) Référence : entraînement + évaluation sur données RÉELLES (non décalées).
#    Une seule fois -- sert de point de comparaison, pas ce que --seeds répète.
# --------------------------------------------------------------------- #
real_result = _train_and_evaluate(train_norm, val_norm, label="REEL")

# --------------------------------------------------------------------- #
# 4) Sonde répétée sur PLUSIEURS graines de mélange indépendantes (LOT 2,
#    phase 6) : entraînement sur TRAIN décalé (prix décorrélés de leurs
#    propres features), évaluation sur VAL réelle (non décalée) -- voir
#    docstring en tête de fichier pour le raisonnement complet. Seul TRAIN
#    est mélangé à CHAQUE graine : VAL doit rester réelle pour que le score
#    mesuré ait un sens (sinon on testerait autre chose : la robustesse du
#    pipeline d'évaluation lui-même face à des données mélangées, pas une
#    fuite de l'entraînement).
# --------------------------------------------------------------------- #
shuffled_scores = []
for i in range(args.seeds):
    seed_i = args.seed + i
    shuffled_train = shuffle_target_relative_to_features(train_norm, seed=seed_i)
    result_i = _train_and_evaluate(shuffled_train, val_norm, label=f"MELANGE seed={seed_i}")
    shuffled_scores.append(result_i["score"])

stats = _shuffle_score_stats(shuffled_scores)
mean_score, std_score, min_score, max_score, n_positive = (
    stats["mean"], stats["std"], stats["min"], stats["max"], stats["n_positive"])

# --------------------------------------------------------------------- #
# 5) Verdict -- sur la MOYENNE des graines mélangées (une seule graine
#    positive par hasard statistique ne doit pas suffire à faire échouer
#    le diagnostic, ni une seule graine négative à le faire réussir).
# --------------------------------------------------------------------- #
print("\n" + "=" * 70)
print("DIAGNOSTIC TARGET SHUFFLING -- détection de fuite de données")
print("=" * 70)
print(f"Score REEL     (train reel    -> val reelle) : {real_result['score']:.3f} "
      f"(sharpe={real_result['metrics']['sharpe']:.3f}, n_trades={real_result['metrics']['n_trades']})")
print(f"\nScore MELANGE sur {args.seeds} graine(s) indépendante(s) (seeds {args.seed}..{args.seed + args.seeds - 1}) :")
print(f"  moyenne = {mean_score:.3f} | écart-type = {std_score:.3f} | "
      f"min = {min_score:.3f} | max = {max_score:.3f} | "
      f"graines > 0 = {n_positive}/{args.seeds}")

WARN_THRESHOLD = 0.0
if mean_score > WARN_THRESHOLD:
    print("\n*** WARN : le score MOYEN sur données MELANGEES est CLAIREMENT POSITIF. ***")
    print("*** Ceci suggere une FUITE DE DONNEES quelque part dans le pipeline  ***")
    print("*** (normalisation, calcul de features, split train/val/test...) -- ***")
    print("*** l'agent ne devrait PAS pouvoir apprendre une relation utile     ***")
    print("*** features->prix sur des donnees volontairement decorrelees.      ***")
    print("*** A investiguer avant de faire confiance aux scores de validation ***")
    print("*** de la production.                                              ***")
    verdict = "WARN"
else:
    print("\nPASS : le score moyen sur donnees melangees est nul/negatif, comme attendu")
    print("sur une relation features->prix decorrelee. Pas de signe de fuite")
    print("detecte par cette sonde (sur ce budget d'entrainement/ces donnees).")
    verdict = "PASS"
print("=" * 70)
print(f"VERDICT: {verdict}")
