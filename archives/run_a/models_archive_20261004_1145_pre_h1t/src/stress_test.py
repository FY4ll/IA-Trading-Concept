"""
stress_test.py
===============
Génère des scénarios de marché ADVERSARIAUX à partir de l'historique réel,
pour valider un candidat sur des situations qu'il n'a PAS vues telles
quelles à l'entraînement -- pas seulement sur les fenêtres walk-forward
découpées dans l'historique existant (qui restent, par construction, des
morceaux du MÊME passé, dans le MÊME ordre).

Choix de conception : on réordonne/sélectionne des BLOCS DE LIGNES ENTIÈRES
(prix ET features déjà calculées ensemble), jamais les prix seuls -- une
bougie donnée garde toujours SES features d'origine. Fabriquer un OHLC
synthétique aurait cassé la cohérence entre le prix et les indicateurs
techniques déjà normalisés (il aurait fallu tout recalculer, avec un risque
de fuite d'information ou d'incohérence). Ici, chaque scénario reste composé
de VRAIS morceaux de marché, juste réarrangés ou sélectionnés différemment.

EXCEPTION DÉLIBÉRÉE (`garch_stress_dataset`, tâche "brancher GARCH comme
scénario de stress" -- voir plus bas) : ce SEUL scénario fabrique de l'OHLC
synthétique, précisément parce que son but est de tester une DYNAMIQUE de
volatilité (queues épaisses, clustering GARCH) qui n'existe PAS dans
l'historique réel, quel que soit le réarrangement -- reformuler l'historique
réel ne peut par construction jamais produire ce test. Le risque de fuite/
incohérence que le paragraphe ci-dessus évoque est traité explicitement :
les features sont RECALCULÉES proprement sur la série synthétique (jamais
mélangées avec des features réelles), puis normalisées avec les stats DÉJÀ
AJUSTÉES sur l'historique réel d'entraînement (jamais réajustées sur la
série synthétique elle-même), exactement le principe déjà appliqué par
scripts/cross_asset_survival_test.py pour la même raison.
"""
from __future__ import annotations
import json
import os
import numpy as np
import pandas as pd


_PRICE_COLS = ["open", "high", "low", "close"]

# Valeurs PESSIMISTES par défaut (LOT 2, phase 5, "frictions calibrables") --
# IDENTIQUES aux défauts déjà en place dans inject_macro_shocks (voir plus
# bas) : dupliquées ici en constantes nommées UNIQUEMENT pour que
# resolve_friction_params puisse les renvoyer explicitement pour le profil
# "pessimistic", sans changer le comportement déjà en place si cette
# fonction n'est jamais appelée.
DEFAULT_SPREAD_MULTIPLIER_RANGE = (3.0, 5.0)
DEFAULT_SLIPPAGE_PRICE_RANGE = (0.02, 0.05)
FRICTION_CALIBRATION_PATH = os.path.join("data", "friction_calibration.json")


def resolve_friction_params(profile: str = "pessimistic", calibration_path: str = FRICTION_CALIBRATION_PATH) -> dict:
    """Résout `frictions.profile` (LOT 2, phase 5) en paramètres concrets
    pour inject_macro_shocks : "pessimistic" (DÉFAUT -- ne change AUCUNE
    valeur par défaut existante) renvoie exactement les constantes
    ci-dessus. "calibrated" lit `scripts/slippage_report.py::
    build_calibration` (écrite dans `calibration_path`) SI elle existe --
    sinon repli silencieux sur "pessimistic" (jamais une exception, jamais
    une valeur inventée sans mesure réelle derrière).

    `spread_multiplier_range` n'est JAMAIS calibré (non mesurable depuis le
    journal d'exécution actuel, voir build_calibration) -- reste toujours à
    la valeur pessimiste, même en profil "calibrated"."""
    if profile != "calibrated":
        return {"spread_multiplier_range": DEFAULT_SPREAD_MULTIPLIER_RANGE,
                "slippage_price_range": DEFAULT_SLIPPAGE_PRICE_RANGE}
    if not os.path.exists(calibration_path):
        return {"spread_multiplier_range": DEFAULT_SPREAD_MULTIPLIER_RANGE,
                "slippage_price_range": DEFAULT_SLIPPAGE_PRICE_RANGE}
    try:
        with open(calibration_path, encoding="utf-8") as f:
            calibration = json.load(f)
        slippage_range = tuple(calibration["slippage_price_range"])
    except Exception:
        return {"spread_multiplier_range": DEFAULT_SPREAD_MULTIPLIER_RANGE,
                "slippage_price_range": DEFAULT_SLIPPAGE_PRICE_RANGE}
    return {"spread_multiplier_range": DEFAULT_SPREAD_MULTIPLIER_RANGE, "slippage_price_range": slippage_range}


def _rebase_and_concat(chunks: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatène des morceaux de marché pris à des ÉPOQUES DIFFÉRENTES en
    évitant l'artefact de raccord qui casserait tout calcul de PnL en aval :
    l'historique XAUUSD couvre ~400$ (2004) à ~2600$+ (2020s), donc coller
    bout à bout deux morceaux SANS ajustement créerait un écart de prix qui
    n'a JAMAIS existé (ex: une bougie à 400$ suivie d'une bougie à 2400$)
    -- un artefact de raccord, pas un vrai mouvement de marché, qui
    dominerait le drawdown mesuré par TradingEnv au lieu de la robustesse
    réelle de l'agent. Chaque morceau (sauf le premier) est mis à l'échelle
    pour que son OPEN de départ se raccorde exactement au CLOSE où le
    morceau précédent s'est arrêté -- préserve la dynamique RELATIVE propre
    à ce morceau (ses propres rendements, sa propre volatilité) sans
    téléportation de niveau de prix. Le volume n'est jamais mis à l'échelle
    (ce n'est pas un niveau de prix). Les indicateurs techniques déjà
    calculés dans les autres colonnes restent, eux, non recalculés après ce
    raccord -- une incohérence mineure et déjà présente dans la conception
    d'origine, largement atténuée par la normalisation (z-score) avant
    l'entrée dans le réseau, sans commune mesure avec l'artefact de prix
    corrigé ici.
    """
    rebased = []
    carry_price = None
    for block in chunks:
        if len(block) == 0:
            continue
        block = block.copy()
        if carry_price is not None:
            first_open = float(block.iloc[0]["open"])
            if first_open > 0:
                scale = carry_price / first_open
                for col in _PRICE_COLS:
                    if col in block.columns:
                        block[col] = block[col] * scale
        carry_price = float(block.iloc[-1]["close"])
        rebased.append(block)
    return pd.concat(rebased, ignore_index=True)


def block_bootstrap_rows(df: pd.DataFrame, block_size: int = 150, seed: int | None = None) -> pd.DataFrame:
    """Réordonne aléatoirement des BLOCS de bougies consécutives (pas bougie
    par bougie -- détruirait toute autocorrélation à court terme). Teste la
    robustesse de l'agent à une SÉQUENCE différente des mêmes régimes de
    marché, plutôt qu'à l'ordre chronologique réel exact. Voir
    _rebase_and_concat pour le traitement des écarts de prix entre blocs
    d'époques différentes.

    `block_size` par défaut relevé de 50 à 150 (audit institutionnel) : un
    bloc de 50 bougies est trop court pour préserver l'autocorrélation
    réaliste de moyen terme (tendances, régimes de vol qui durent plusieurs
    heures/jours selon le timeframe) -- 150 tombe dans la fourchette
    150-200 recommandée pour ce type de rééchantillonnage par blocs sur des
    séries financières, tout en restant overridable par l'appelant (ex:
    `evaluate_agent_walkforward` dans backtester.py, qui calibre déjà son
    propre `block_size` en fonction de la longueur du dataset évalué)."""
    rng = np.random.default_rng(seed)
    n = len(df)
    n_blocks = max(1, n // block_size)
    order = rng.permutation(n_blocks)
    chunks = [df.iloc[i * block_size:(i + 1) * block_size] for i in order]
    return _rebase_and_concat(chunks)


def stationary_block_bootstrap(df: pd.DataFrame, min_block: int = 100, max_block: int = 200,
                                 seed: int | None = None) -> pd.DataFrame:
    """Rééchantillonnage par BOOTSTRAP STATIONNAIRE (Politis & Romano, 1994)
    -- la version "manuel scolaire" du bootstrap par blocs, plus rigoureuse
    que `block_bootstrap_rows` sur un point précis :

    DIFFÉRENCE AVEC `block_bootstrap_rows` : celui-ci réordonne des blocs de
    taille FIXE, NON chevauchants, qui partitionnent exactement le
    DataFrame d'origine (chaque bougie appartient à exactement un bloc,
    juste rebattu). `stationary_block_bootstrap` tire au contraire des blocs
    de LONGUEUR ALÉATOIRE, à des POINTS DE DÉPART ALÉATOIRES tirés AVEC
    REMISE dans tout le DataFrame (une même bougie peut apparaître dans
    zéro, un ou plusieurs blocs ; certaines bougies d'origine peuvent ne
    jamais être piochées) -- exactement la construction du bootstrap
    stationnaire de Politis & Romano, dont la propriété clé (d'où le nom) est
    que la série rééchantillonnée reste elle-même STATIONNAIRE au sens
    strict (ses statistiques ne dépendent pas de la position du point de
    départ), contrairement au bootstrap par blocs fixes qui introduit une
    légère non-stationnarité aux coutures entre blocs adjacents d'origine.

    Longueur de bloc : tirée d'une loi GÉOMÉTRIQUE (le choix "manuel
    scolaire" de Politis & Romano, car elle est SANS MÉMOIRE -- la
    probabilité de "prolonger" le bloc courant d'une bougie de plus ne
    dépend jamais de sa longueur déjà atteinte, ce qui est précisément la
    propriété qui rend la série résultante stationnaire) avec
    `p = 1 / longueur_moyenne_visee`, `longueur_moyenne_visee` étant le
    milieu de l'intervalle `[min_block, max_block]` -- puis bornée à un
    minimum de 20 bougies pour éviter des blocs dégénérés à 1 bougie (trop
    fréquents avec une géométrique de moyenne élevée, et sans intérêt : un
    bloc d'une seule bougie ne préserve aucune autocorrélation de court
    terme, tout l'intérêt d'un bootstrap PAR BLOCS plutôt que bougie par
    bougie).

    Point de départ : tiré uniformément dans `[0, n)` avec remise. Si le
    bloc tiré dépasse la fin du DataFrame, il est scindé en DEUX morceaux
    (fin du DataFrame, puis reprise depuis le début -- construction
    "circulaire" standard du bootstrap stationnaire, pour ne jamais avoir à
    raccourcir artificiellement les blocs tirés près de la fin de la
    série) ; les deux morceaux sont ajoutés comme des chunks SÉPARÉS avant
    l'appel à `_rebase_and_concat`, qui les reprix chacun individuellement
    -- évite l'écart de prix artificiel qu'un unique bloc "recollé" en
    interne (dernière bougie de la série suivie directement de la première)
    aurait sinon introduit.

    Le tirage continue jusqu'à couvrir au moins `len(df)` bougies, puis le
    résultat est tronqué exactement à `len(df)` lignes (le dernier bloc
    pioché est éventuellement coupé net) -- la sortie a donc TOUJOURS la
    même longueur que l'entrée, comme `block_bootstrap_rows`."""
    n = len(df)
    if n == 0:
        return df.copy()
    rng = np.random.default_rng(seed)
    mean_block_len = (min_block + max_block) / 2.0
    p = 1.0 / max(1.0, mean_block_len)
    min_len_floor = 20

    chunks = []
    total = 0
    while total < n:
        block_len = max(min_len_floor, int(rng.geometric(p)))
        start = int(rng.integers(0, n))
        end = start + block_len
        if end <= n:
            block = df.iloc[start:end]
            chunks.append(block)
            total += len(block)
        else:
            # dépasse la fin -> repli circulaire en DEUX chunks distincts
            # (voir docstring) plutôt qu'un seul bloc "recollé" en interne.
            first_part = df.iloc[start:n]
            second_part = df.iloc[0:end - n]
            chunks.append(first_part)
            chunks.append(second_part)
            total += len(first_part) + len(second_part)

    result = _rebase_and_concat(chunks)
    return result.iloc[:n].reset_index(drop=True)


def high_volatility_subset(df: pd.DataFrame, window_size: int = 500, top_k: int = 3,
                            price_col: str = "close") -> pd.DataFrame:
    """Concatène les `top_k` fenêtres de `window_size` bougies qui ont
    RÉELLEMENT connu la plus forte volatilité réalisée dans l'historique --
    stress-teste l'agent spécifiquement sur les conditions de marché les
    plus turbulentes déjà vécues, plutôt que sur un échantillon moyen. Ces
    fenêtres ne sont PAS forcément adjacentes dans le temps (voir
    _rebase_and_concat pour le traitement des écarts de prix entre elles)."""
    returns = df[price_col].pct_change().fillna(0.0).values
    n = len(df)
    if n < window_size * 2:
        return df.copy()
    n_windows = n // window_size
    vol_per_window = [returns[i * window_size:(i + 1) * window_size].std() for i in range(n_windows)]
    worst = np.argsort(vol_per_window)[-top_k:]
    chunks = [df.iloc[i * window_size:(i + 1) * window_size] for i in sorted(worst)]
    return _rebase_and_concat(chunks)


def load_macro_events_csv(path: str) -> list:
    """Charge une liste d'horodatages d'événements macro RÉELS (CPI/NFP/FOMC...)
    depuis un CSV, pour alimenter l'argument `event_timestamps` déjà existant
    de `inject_macro_shocks` (voir ci-dessous) -- audit institutionnel,
    section 3, "Identifier les timestamps des annonces majeures".

    FORMAT ATTENDU (voir data/macro_events_example.csv pour un gabarit
    COMMENTÉ, avec des dates PLACEHOLDER explicitement marquées comme
    telles -- jamais de vraies dates présentées comme réelles dans ce
    dépôt) : un CSV avec au minimum une colonne `timestamp_utc` (horodatage
    ISO 8601, interprété comme UTC mais gardé NAÏF -- sans fuseau explicite
    -- pour rester cohérent avec le reste du pipeline, où `load_kaggle_ohlcv_csv`
    ne fixe pas non plus `utc=True`, voir docstring de ce module) et une
    colonne `event_type` (texte libre, ex: "CPI"/"NFP"/"FOMC" -- purement
    informatif, PAS utilisé par `inject_macro_shocks`, qui ne se sert que du
    timestamp). Les lignes commençant par "#" sont ignorées (commentaires).

    Retourne une liste de `pandas.Timestamp` (jamais de DataFrame) -- prête à
    passer directement à `inject_macro_shocks(df, event_timestamps=...)`.
    Lève `FileNotFoundError`/`ValueError` si le fichier est introuvable ou
    mal formé -- volontairement PAS de repli silencieux ici (contrairement à
    `inject_macro_shocks` elle-même, qui retombe sur son proxy statistique
    si `event_timestamps=None`) : un chemin de CSV EXPLICITEMENT configuré
    qui échoue à charger doit être visible, pas masqué.
    """
    raw = pd.read_csv(path, comment="#")
    if "timestamp_utc" not in raw.columns:
        raise ValueError(
            f"Colonne 'timestamp_utc' introuvable dans {path}. Colonnes présentes : {list(raw.columns)}."
        )
    timestamps = pd.to_datetime(raw["timestamp_utc"], errors="raise")
    return list(timestamps)


def inject_macro_shocks(df: pd.DataFrame, event_timestamps: list | None = None,
                          spread_multiplier_range: tuple = (3.0, 5.0),
                          slippage_price_range: tuple = (0.02, 0.05),
                          seed: int | None = None) -> pd.DataFrame:
    """Simule le choc de COÛT D'EXÉCUTION (pas de choc de PRIX -- voir plus
    bas) qui entoure les publications macro à fort impact (CPI, NFP,
    décisions de taux Fed/FOMC...) : à ces instants précis, le spread réel
    s'élargit brutalement chez la plupart des brokers, ET les ordres
    subissent un slippage bien plus marqué qu'en temps normal -- deux effets
    qu'un coût de transaction fixe (`transaction_cost` de TradingEnv) ne
    peut par construction jamais représenter.

    CONTRAT DE COLONNES EN SORTIE (à ne pas dévier -- consommé directement
    par TradingEnv sur `self.df`, hors `feature_columns`/observation, pour
    ne JAMAIS donner à l'agent un signal explicite "un choc a lieu
    maintenant" en entrée -- seul son EFFET sur le coût doit s'appliquer) :
      - `cost_multiplier` (float, >= 1.0) : multiplicatif, vaut 1.0 partout
        sauf sur les bougies "choc" flaguées, où il est tiré uniformément
        dans `spread_multiplier_range` (défaut x3 à x5 -- ordre de grandeur
        observé sur l'élargissement de spread XAUUSD au moment d'un NFP/CPI
        chez la plupart des brokers retail/ECN).
      - `slippage_price_offset` (float, >= 0.0) : additif, déjà exprimé en
        UNITÉS DE PRIX (pas en pips ni en %), vaut 0.0 partout sauf sur les
        bougies flaguées. Hypothèse documentée : pour XAUUSD, ~1 pip ≈
        0.01$, donc `slippage_price_range=(0.02, 0.05)` par défaut représente
        environ 2 à 5 pips de glissement -- cohérent avec un slippage de
        marché agité sur l'or, mais À AJUSTER si l'instrument ou la
        convention de pip change. C'est toujours une MAGNITUDE (jamais de
        signe) -- au code appelant de décider dans quel sens l'appliquer
        (contre la position ouverte, typiquement).
    Retourne toujours une COPIE de `df` (jamais de mutation en place).

    SOURCE DES ÉVÉNEMENTS :
    - Si `event_timestamps` est fourni (liste de timestamps interprétables
      par pandas -- ex: vrais horaires CPI/NFP/FOMC issus d'un calendrier
      économique externe), on flague, pour CHAQUE timestamp, la bougie de
      `df` dont la colonne "time" est la PLUS PROCHE, à condition que cet
      écart reste inférieur ou égal à la durée typique d'UNE bougie
      (médiane des écarts consécutifs de "time") -- "au sein d'une bougie"
      comme demandé, pas n'importe quelle bougie la plus proche même très
      loin.
    - Si `event_timestamps` est `None` (cas le plus courant -- l'intégration
      calendrier économique de ce projet, `fundamental.calendar_url`, est
      documentée ailleurs dans le code comme actuellement MORTE/non câblée
      en production, donc on ne peut pas supposer un calendrier réel
      disponible), on retombe sur un PROXY STATISTIQUE : une bougie est
      flaguée "choc probable" si elle est SIMULTANÉMENT (a) dans le TOP 1%
      des rendements absolus (`|close.pct_change()|`) ET (b) dans le TOP 10%
      du volume -- MAIS seulement si une colonne "volume" existe ET n'est
      pas triviale (pas entièrement à 0/NaN) ; si le volume est absent ou
      trivial, seul le critère (a) est utilisé. Ce proxy N'EST PAS un
      substitut à un vrai calendrier -- il capture statistiquement les
      bougies qui RESSEMBLENT le plus à une vraie surprise macro (mouvement
      extrême + volume anormal en même temps), mais peut manquer de vrais
      événements "calmes en apparence" ou flaguer à tort un flash-move sans
      lien avec une annonce macro. Préférez toujours `event_timestamps` avec
      un vrai calendrier CPI/NFP/FOMC quand disponible.
    """
    out = df.copy()
    out["cost_multiplier"] = 1.0
    out["slippage_price_offset"] = 0.0
    n = len(out)
    if n == 0:
        return out

    rng = np.random.default_rng(seed)

    if event_timestamps:
        if "time" not in out.columns:
            raise ValueError("event_timestamps fourni mais df n'a pas de colonne 'time'.")
        times = pd.to_datetime(out["time"])
        diffs_between_bars = times.diff().dropna()
        bar_duration = diffs_between_bars.median() if len(diffs_between_bars) else pd.Timedelta(0)
        flagged = set()
        for ev in event_timestamps:
            ev_ts = pd.Timestamp(ev)
            gap = (times - ev_ts).abs()
            idx = gap.idxmin()
            if bar_duration == pd.Timedelta(0) or gap.loc[idx] <= bar_duration:
                flagged.add(idx)
        flagged_idx = sorted(flagged)
    else:
        abs_ret = out["close"].pct_change().abs().fillna(0.0) if "close" in out.columns else pd.Series(0.0, index=out.index)
        ret_threshold = abs_ret.quantile(0.99)
        ret_flag = abs_ret >= ret_threshold

        has_volume = "volume" in out.columns and pd.to_numeric(out["volume"], errors="coerce").fillna(0).abs().sum() > 0
        if has_volume:
            volume = pd.to_numeric(out["volume"], errors="coerce").fillna(0)
            vol_threshold = volume.quantile(0.90)
            vol_flag = volume >= vol_threshold
            shock_flag = ret_flag & vol_flag
        else:
            shock_flag = ret_flag
        flagged_idx = out.index[shock_flag].tolist()

    if flagged_idx:
        multipliers = rng.uniform(spread_multiplier_range[0], spread_multiplier_range[1], size=len(flagged_idx))
        slippages = rng.uniform(slippage_price_range[0], slippage_price_range[1], size=len(flagged_idx))
        out.loc[flagged_idx, "cost_multiplier"] = multipliers
        out.loc[flagged_idx, "slippage_price_offset"] = slippages

    return out


def shuffle_target_relative_to_features(df: pd.DataFrame, seed: int | None = None) -> pd.DataFrame:
    """Sonde de détection de FUITE DE DONNÉES par "target shuffling"
    (technique classique de validation de pipeline ML) : décale
    CIRCULAIREMENT les colonnes PRIX (open/high/low/close -- la "cible" sur
    laquelle l'agent est en fin de compte récompensé, via les variations de
    équity qu'elles déterminent) d'un offset aléatoire non nul, en laissant
    TOUTES les autres colonnes (features déjà calculées, volume, time...)
    parfaitement inchangées et à leur index d'origine.

    POURQUOI : ça casse volontairement l'alignement temporel réel entre "les
    features observées à l'instant t" et "le prix qui a RÉELLEMENT suivi à
    t" -- un agent entraîné puis évalué sur des données ainsi décalées ne
    PEUT PAS apprendre de relation causale réelle features -> prix futur,
    puisque cette relation n'existe plus. Si, malgré ça, un candidat obtient
    quand même un score walk-forward clairement positif sur des données
    décalées de cette façon, c'est le signal qu'une fuite d'information
    existe AILLEURS dans le pipeline (ex: normalisation calculée sur des
    statistiques qui débordent sur la période de test, feature qui regarde
    involontairement en avant...), pas que l'agent a un vrai edge.

    Un DÉCALAGE CIRCULAIRE (`np.roll`, pas un shift qui introduirait des
    NaN en bord de série, et pas un mélange/shuffle aléatoire ligne par
    ligne) est choisi précisément pour préserver EXACTEMENT les propriétés
    statistiques internes de chaque colonne prix (sa propre distribution,
    son autocorrélation, sa volatilité réalisée...) -- seul l'ALIGNEMENT
    avec les autres colonnes est détruit. C'est ce qui rend cette sonde
    plus rigoureuse qu'un simple ajout de bruit : un modèle qui "trublerait"
    sur du bruit pur ne prouverait rien de précis sur une fuite
    d'alignement temporel, alors qu'ici toute performance positive ne peut
    logiquement venir QUE d'une fuite, jamais d'un vrai signal prix.

    L'offset est tiré uniformément dans `[1, len(df) - 1]` (jamais 0, pour
    garantir que l'alignement change réellement) ; pour `len(df) < 2`, aucun
    décalage n'est possible et une simple copie est retournée. Retourne
    toujours une COPIE de `df` (jamais de mutation en place), sans jamais
    introduire de NaN."""
    out = df.copy()
    n = len(out)
    if n < 2:
        return out
    rng = np.random.default_rng(seed)
    offset = int(rng.integers(1, n))  # dans [1, n-1] -- jamais 0
    for col in _PRICE_COLS:
        if col in out.columns:
            out[col] = np.roll(out[col].to_numpy(), offset)
    return out


# Fréquence PANDAS de rééchantillonnage OHLC pour chaque timeframe -- utilisée
# UNIQUEMENT pour dériver des timeframes plus LARGES à partir de la série
# GARCH de base (voir garch_stress_dataset ci-dessous). Ne couvre QUE H1 et
# plus large : `generate_synthetic_ohlcv_garch` génère sa colonne "time" à
# fréquence HORAIRE FIXE (voir src/data_loader.py -- `freq="h"`, non
# paramétrable, hors périmètre de cette tâche de le modifier) -- on ne peut
# donc JAMAIS en dériver honnêtement une timeframe plus FINE que H1 (M15/M30
# nécessiteraient une résolution intra-heure qui n'existe pas dans la série
# de base). Voir GARCH_STRESS_MIN_PRIMARY_TF ci-dessous.
_GARCH_RESAMPLE_FREQ = {"H1": "1h", "H4": "4h", "D1": "1D", "W1": "1W", "MN1": "1MS"}

# Timeframes primaires pour lesquelles garch_stress_dataset peut honnêtement
# construire une série (voir commentaire ci-dessus) -- toute timeframe plus
# fine (M1/M5/M15/M30) est HORS de portée de ce générateur à fréquence fixe.
GARCH_STRESS_SUPPORTED_PRIMARY_TFS = frozenset({"H1", "H4", "D1", "W1", "MN1"})


def _resample_ohlc(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Ré-échantillonne un DataFrame OHLCV (colonne "time") vers une
    fréquence plus large par agrégation OHLC standard (open=premier,
    high=max, low=min, close=dernier, volume=somme) -- sert à dériver les
    timeframes de CONTEXTE synthétiques d'un scénario GARCH à partir de sa
    série de base horaire, sans dépendre d'aucune donnée réelle."""
    idx = df.set_index(pd.to_datetime(df["time"]))
    agg = idx.resample(freq).agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    })
    agg = agg.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return agg


def garch_stress_dataset(primary_tf: str, context_tfs: list[str], feature_columns: list[str],
                          stats: dict, n_primary_bars: int = 500, seed: int | None = None,
                          dof: float = 5.0, alpha: float = 0.08, beta: float = 0.90):
    """Construit un dataset de stress GARCH complet (multi-timeframe, features
    calculées, NORMALISÉ) -- audit institutionnel, "brancher generate_synthetic_
    ohlcv_garch comme scénario de stress-test supplémentaire" (voir
    src/data_loader.py::generate_synthetic_ohlcv_garch pour la récursion
    GARCH(1,1)/queues épaisses elle-même, inchangée ici).

    POURQUOI UN TRAITEMENT DIFFÉRENT DES 4 AUTRES SCÉNARIOS (voir docstring de
    ce module) : ceux-là réordonnent des LIGNES RÉELLES (prix+features déjà
    cohérents) ; ici, aucune réorganisation de l'historique réel ne peut
    produire une dynamique de volatilité qui n'y existe pas -- il faut donc
    fabriquer une série entièrement synthétique, recalculer ses features, et
    les normaliser avec les stats déjà ajustées sur l'entraînement RÉEL
    (jamais réajustées ici, jamais mélangées avec des données réelles).

    LIMITE HONNÊTE (voir GARCH_STRESS_SUPPORTED_PRIMARY_TFS) : la série de
    base de `generate_synthetic_ohlcv_garch` est à fréquence HORAIRE FIXE --
    ce scénario ne peut donc être construit que pour un `primary_tf` de H1 ou
    plus large (H1/H4/D1/W1/MN1), et pour des `context_tfs` eux-mêmes tous
    dérivables par agrégation depuis l'heure (donc également >= H1). Pour un
    style M15/M30 (primaire plus fin que H1), ou dont le contexte réel exige
    une timeframe plus fine que H1 (ex: M15 a besoin de M30/H1 en contexte),
    retourne None -- L'APPELANT DOIT gérer ce None comme "scénario non
    applicable à ce style" (voir evaluate_agent_walkforward, même
    try/except-et-skip que les 4 autres scénarios adversariaux). Ne PAS
    interpréter un None comme une erreur.

    Retourne un DataFrame normalisé prêt pour TradingEnv(feature_columns=...),
    ou None si non constructible pour ce `primary_tf`/`context_tfs`.
    """
    from src.data_loader import generate_synthetic_ohlcv_garch
    from src.features import add_technical_features, normalize_features
    from src.multi_timeframe import fuse_mtf_frames, TF_ORDER

    if primary_tf not in GARCH_STRESS_SUPPORTED_PRIMARY_TFS:
        return None
    # Tout contexte plus fin que H1 (M1/M5/M15/M30) est également hors de
    # portée -- s'il en existe un parmi context_tfs, la fusion serait
    # incomplète pour ce style (colonnes de contexte manquantes -> mismatch
    # avec feature_columns attendu par l'agent) : on refuse tout, plutôt que
    # de fusionner partiellement en silence.
    for tf in context_tfs:
        if tf not in GARCH_STRESS_SUPPORTED_PRIMARY_TFS:
            return None

    # Marge généreuse : le passage à une fréquence plus large PERD des
    # bougies (agrégation), et le contexte le plus large (MN1) doit encore
    # contenir plusieurs bougies après agrégation pour que le merge_asof de
    # fuse_mtf_frames ait un sens -- 24 bougies horaires par bougie "D1"
    # équivalente x quelques centaines de bougies primaires peut demander
    # une série de base de plusieurs dizaines de milliers de points, mais
    # generate_synthetic_ohlcv_garch est une simple récursion numpy (rapide
    # même à cette échelle).
    primary_hours = {"H1": 1, "H4": 4, "D1": 24, "W1": 168, "MN1": 730}[primary_tf]
    base_n_bars = max(2000, int(n_primary_bars * primary_hours * 1.2) + 200)
    base_df = generate_synthetic_ohlcv_garch(n_bars=base_n_bars, seed=seed, dof=dof, alpha=alpha, beta=beta)

    dfs = {}
    dfs["H1"] = base_df
    primary_df = base_df if primary_tf == "H1" else _resample_ohlc(base_df, _GARCH_RESAMPLE_FREQ[primary_tf])
    primary_df = primary_df.tail(n_primary_bars + 60).reset_index(drop=True)  # +60 : marge pour le warmup des indicateurs
    dfs[primary_tf] = primary_df
    for tf in context_tfs:
        if tf == primary_tf:
            continue
        dfs[tf] = base_df if tf == "H1" else _resample_ohlc(base_df, _GARCH_RESAMPLE_FREQ[tf])

    fused, _mtf_cols = fuse_mtf_frames(dfs, primary_tf, context_tfs)
    featured = add_technical_features(fused)  # fundamental_score neutre (0.0) sans fundamental_feed -- attendu ici
    if any(c not in featured.columns for c in feature_columns):
        # Un des context_tfs demandés n'a en fait pas pu être fusionné (ex:
        # absent de TF_ORDER, ou égal/plus étroit que primary_tf -- voir
        # fuse_mtf_frames) -- mismatch avec ce que l'agent attend, on refuse
        # plutôt que de laisser TradingEnv lever un KeyError plus tard.
        return None

    normalized, _ = normalize_features(featured, stats=stats, columns=feature_columns)
    return normalized
