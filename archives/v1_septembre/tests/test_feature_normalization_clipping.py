"""Bug reel trouve le 21/09 en observant M30 rester plat sur 207 decisions
d'affilee en demo : `fundamental_score` etait CONSTANT pendant tout
l'entrainement (flux RSS des banques centrales en echec permanent, retombe
sur le meme score neutre a chaque fois) -> ecart-type appris quasiment nul
-> une valeur live meme legerement differente de cette constante explosait
en un z-score absurde (observe : 21 millions de sigma sur M30) une fois
divisee par cet ecart-type quasi nul. `normalize_features` (src/features.py)
plafonne desormais chaque z-score a +/-Z_SCORE_CLIP."""
from __future__ import annotations
import pandas as pd

from src.features import normalize_features, Z_SCORE_CLIP


def test_near_zero_variance_training_feature_does_not_explode_on_live_value():
    """Reproduit EXACTEMENT l'incident M30 : une feature constante a
    l'entrainement (stats calcules dessus), puis une valeur LIVE differente
    de cette constante -- doit etre plafonnee, jamais laissee exploser."""
    train_df = pd.DataFrame({"fundamental_score": [-0.217] * 50})
    _, stats = normalize_features(train_df, columns=["fundamental_score"])
    mean, std = stats["fundamental_score"]
    assert std < 1e-6, "l'ecart-type d'une feature constante doit etre quasiment nul (plancher +1e-8)"

    live_df = pd.DataFrame({"fundamental_score": [0.0]})
    live_norm, _ = normalize_features(live_df, stats=stats, columns=["fundamental_score"])
    z = live_norm["fundamental_score"].iloc[0]
    assert abs(z) <= Z_SCORE_CLIP, f"le z-score doit etre plafonne a +/-{Z_SCORE_CLIP}, obtenu {z}"


def test_constant_training_feature_normalizes_to_zero_never_clipped():
    """Sur les donnees D'ENTRAINEMENT elles-memes (valeur == moyenne partout),
    le z-score doit rester exactement 0 -- le plafond ne doit JAMAIS affecter
    ce que les modeles deja entraines ont appris (aucun retraining requis par
    ce correctif)."""
    train_df = pd.DataFrame({"fundamental_score": [-0.217] * 50})
    train_norm, stats = normalize_features(train_df, columns=["fundamental_score"])
    # tolerance flottante (bruit de calcul mean/std sur des valeurs
    # constantes, de l'ordre de 1e-9) -- jamais pres du plafond +/-5.0.
    assert (train_norm["fundamental_score"].abs() < 1e-6).all()


def test_extreme_but_legitimate_reading_is_bounded_not_distorted_below_clip():
    """Une lecture reellement extreme (pas un bug de variance nulle) doit
    rester plafonnee a la borne, sans jamais depasser -- comportement voulu
    pour les cas comme MN1_trend_signal observes a des z-scores de 5-6."""
    train_df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0]})
    _, stats = normalize_features(train_df, columns=["x"])
    live_df = pd.DataFrame({"x": [1000.0]})  # tres loin de la moyenne d'entrainement
    live_norm, _ = normalize_features(live_df, stats=stats, columns=["x"])
    assert live_norm["x"].iloc[0] == Z_SCORE_CLIP


def test_normal_range_values_unaffected_by_clip():
    """Une valeur dans une plage normale (quelques ecarts-types) ne doit
    jamais etre alteree par le plafond -- non-regression du comportement
    existant pour la tres grande majorite des features."""
    train_df = pd.DataFrame({"x": list(range(100))})
    _, stats = normalize_features(train_df, columns=["x"])
    live_df = pd.DataFrame({"x": [50.0]})  # proche de la moyenne
    live_norm, _ = normalize_features(live_df, stats=stats, columns=["x"])
    assert abs(live_norm["x"].iloc[0]) < 1.0
