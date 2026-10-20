"""
data_loader.py
==============
Fournit des données OHLCV sous forme de DataFrame pandas.

Ce projet est 100% automatique et multi-timeframe : la seule source de
données d'ENTRAÎNEMENT est le dossier de CSV configuré dans
config/autonomous.yaml (data.folder), lu via `load_kaggle_ohlcv_csv`. Les
données de DÉMO/décision en direct passent par src/mt5_connector.py, qui
interroge directement le terminal MetaTrader5 (pas ce module).

`generate_synthetic_ohlcv` sert uniquement aux tests (pas de dépendance
réseau ni de fichier requis pour les faire tourner).
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def generate_synthetic_ohlcv(n_bars: int = 20000, seed: int = 42) -> pd.DataFrame:
    """Génère une série de prix synthétique mais réaliste (utilisée par les
    tests uniquement) :
    - tendance qui change de régime de temps en temps
    - volatilité qui varie (clusters de volatilité, comme les vrais marchés)
    - bruit gaussien
    """
    rng = np.random.default_rng(seed)
    n_regimes = max(3, n_bars // 1000)
    regime_len = n_bars // n_regimes

    prices = [100.0]
    vol = 0.0006
    drift = 0.0

    for i in range(1, n_bars):
        if i % regime_len == 0:
            drift = rng.uniform(-0.0004, 0.0004)
            vol = rng.uniform(0.0003, 0.0015)
        shock = rng.normal(drift, vol)
        new_price = prices[-1] * (1 + shock)
        prices.append(max(new_price, 0.01))

    prices = np.array(prices)
    high = prices * (1 + np.abs(rng.normal(0, vol, n_bars)))
    low = prices * (1 - np.abs(rng.normal(0, vol, n_bars)))
    open_ = np.roll(prices, 1)
    open_[0] = prices[0]
    volume = rng.integers(100, 5000, n_bars)
    time_index = pd.date_range(end=pd.Timestamp.today(), periods=n_bars, freq="h")

    df = pd.DataFrame(
        {
            "time": time_index,
            "open": open_,
            "high": np.maximum.reduce([high, open_, prices]),
            "low": np.minimum.reduce([low, open_, prices]),
            "close": prices,
            "volume": volume,
        }
    )
    return df


def generate_synthetic_ohlcv_garch(n_bars: int = 20000, seed: int = 42,
                                     omega: float = 1.5e-8, alpha: float = 0.08,
                                     beta: float = 0.90, dof: float = 5.0) -> pd.DataFrame:
    """Génère une série de prix synthétique via une VRAIE récursion GARCH(1,1)
    codée à la main avec numpy (aucune dépendance ajoutée -- ni `arch` ni
    `statsmodels` ne sont dans requirements.txt), utilisée par les tests
    uniquement, comme `generate_synthetic_ohlcv`.

    POURQUOI (audit institutionnel) : `generate_synthetic_ohlcv` change de
    régime de volatilité de façon DISCRÈTE (un tirage uniforme d'une nouvelle
    vol tous les `regime_len` pas) -- réaliste pour un changement de régime
    macro lent, mais ça ne capture ni le "clustering" de volatilité continu
    des marchés réels (une grosse bougie a tendance à être suivie d'autres
    grosses bougies, sans palier discret) ni les queues épaisses
    (leptokurtose) des rendements réels, qui rendent les mouvements extrêmes
    bien plus fréquents que sous une hypothèse gaussienne -- deux propriétés
    que tout backtest doit pouvoir stresser pour ne pas sur-estimer la
    robustesse d'un agent calibré sur un bruit trop "propre".

    RÉCURSION GARCH(1,1) (Bollerslev 1986) :
        sigma2_t = omega + alpha * eps_{t-1}^2 + beta * sigma2_{t-1}
        eps_t = sigma_t * z_t
    `z_t` est tiré d'une loi de Student standardisée (`rng.standard_t(dof)`
    divisé par `sqrt(dof / (dof - 2))`, l'écart-type théorique d'un Student à
    `dof` degrés de liberté, pour ramener sa variance à 1) au lieu d'une
    gaussienne -- c'est ce qui produit les queues épaisses (leptokurtose)
    recherchées : `dof=5.0` par défaut donne un excès de kurtosis théorique
    de 6/(dof-4) = 6.0 pour le bruit `z_t` seul, largement au-dessus de 0
    (gaussien), et le mélange avec la variance conditionnelle qui varie dans
    le temps (le clustering lui-même) amplifie encore la kurtosis du
    rendement final `eps_t`.

    CHOIX DES PARAMÈTRES PAR DÉFAUT (documentés, tous overridables) :
    `alpha=0.08, beta=0.90` -> `alpha + beta = 0.98 < 1` (condition de
    stationnarité du GARCH(1,1) : la variance ne diverge pas, la variance
    inconditionnelle `omega / (1 - alpha - beta)` existe). `beta` élevé par
    rapport à `alpha` (comme sur la plupart des séries financières réelles
    calibrées empiriquement) => la volatilité est surtout "persistante"
    (mémoire longue du niveau de vol récent) plutôt que réactive au seul
    dernier choc. `omega=1.5e-8` est choisi pour que la volatilité
    INCONDITIONNELLE (`sqrt(omega / (1 - alpha - beta))`) vaille environ
    8.7e-4 par bougie, du même ordre de grandeur que la fourchette de vol
    (0.0003 à 0.0015) déjà utilisée par bougie dans `generate_synthetic_ohlcv`
    (bougies horaires) -- pour rester un remplacement crédible/comparable,
    pas une série à une échelle de volatilité complètement différente.

    Construit les bougies OHLC à partir de la série de rendements cumulée
    (même approche générale que `generate_synthetic_ohlcv` : bande de bruit
    haute/basse autour du close, volume aléatoire, colonne "time" via
    `pd.date_range`) -- même contrat de colonnes en sortie
    (`time, open, high, low, close, volume`) que `generate_synthetic_ohlcv`
    et `load_kaggle_ohlcv_csv`, donc utilisable en remplacement direct
    partout où une série synthétique est utilisée dans les tests.
    """
    if dof <= 2:
        raise ValueError("dof doit être > 2 (sinon la variance du Student n'existe pas -- standardisation impossible).")
    rng = np.random.default_rng(seed)

    t_std = np.sqrt(dof / (dof - 2))  # écart-type théorique d'un Student(dof), pour standardiser z_t à variance 1
    z = rng.standard_t(dof, size=n_bars) / t_std

    sigma2 = np.empty(n_bars)
    eps = np.empty(n_bars)
    # Amorçage à la variance INCONDITIONNELLE du processus -- évite un
    # transitoire artificiel (vol qui parte de 0 ou d'une valeur arbitraire)
    # en début de série.
    sigma2[0] = omega / max(1e-12, (1 - alpha - beta))
    eps[0] = np.sqrt(sigma2[0]) * z[0]
    for t in range(1, n_bars):
        sigma2[t] = omega + alpha * eps[t - 1] ** 2 + beta * sigma2[t - 1]
        eps[t] = np.sqrt(sigma2[t]) * z[t]

    # Rendements LOG (convention standard pour un GARCH) -> prix par somme
    # cumulée exponentiée, ce qui garantit un prix toujours strictement
    # positif (pas de plancher artificiel à appliquer, contrairement à
    # generate_synthetic_ohlcv qui travaille en rendements multiplicatifs
    # simples).
    log_prices = np.log(100.0) + np.cumsum(eps)
    close = np.exp(log_prices)

    sigma = np.sqrt(sigma2)
    # Bande haute/basse proportionnelle à la vol CONDITIONNELLE du pas
    # courant (pas une constante globale) -- pendant les clusters de forte
    # volatilité, les mèches haute/basse s'élargissent aussi, cohérent avec
    # de vraies bougies OHLC en marché agité.
    high_noise = np.abs(rng.normal(0, 1, n_bars)) * sigma * close
    low_noise = np.abs(rng.normal(0, 1, n_bars)) * sigma * close
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = rng.integers(100, 5000, n_bars)
    time_index = pd.date_range(end=pd.Timestamp.today(), periods=n_bars, freq="h")

    df = pd.DataFrame(
        {
            "time": time_index,
            "open": open_,
            "high": np.maximum.reduce([close + high_noise, open_, close]),
            "low": np.minimum.reduce([close - low_noise, open_, close]),
            "close": close,
            "volume": volume,
        }
    )
    return df


def _detect_separator(path: str) -> str:
    """Détecte le séparateur d'un CSV (virgule, point-virgule ou tabulation)
    à partir de sa première ligne, sans charger tout le fichier -- essentiel
    pour les gros fichiers (le dataset Kaggle XAUUSD 1m fait plusieurs
    centaines de Mo). Le dataset Kaggle XAUUSD utilise ';' comme séparateur,
    pas ',', ce qu'un simple pd.read_csv(path) par défaut ne détecte pas.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        first_line = f.readline()
    counts = {sep: first_line.count(sep) for sep in [";", ",", "\t"]}
    return max(counts, key=counts.get) if max(counts.values()) > 0 else ","


def load_kaggle_ohlcv_csv(path: str, nrows: int | None = None) -> pd.DataFrame:
    """Chargeur robuste pour des CSV OHLCV "génériques" (Kaggle, MT4/MT5
    exportés, etc.) dont les noms de colonnes ET le séparateur varient d'une
    source à l'autre. Détecte automatiquement :
      - le séparateur (',' ';' ou tabulation)
      - une colonne datetime unique ("Date", "Time", "Datetime", "Timestamp")
      - OU deux colonnes séparées Date + Time (format MT4/MT5 classique :
        "2004.06.11" + "00:00:00") qui sont recombinées automatiquement
      - les colonnes open/high/low/close (insensible à la casse)
      - une colonne volume optionnelle (si absente, mise à 0)

    `nrows` (optionnel) : ne lit que les N premières lignes du fichier --
    utile pour inspecter/vérifier un gros fichier (le dataset Kaggle XAUUSD
    1m fait plusieurs centaines de Mo) sans le charger en entier.
    """
    sep = _detect_separator(path)
    raw = pd.read_csv(path, sep=sep, nrows=nrows)
    raw.columns = [c.strip() for c in raw.columns]
    lower = {c.lower(): c for c in raw.columns}

    def find(*candidates):
        for c in candidates:
            if c in lower:
                return lower[c]
        return None

    date_col = find("date")
    time_col = find("time")
    datetime_col = find("datetime", "timestamp", "gmt time", "local time")

    if datetime_col:
        dt = pd.to_datetime(raw[datetime_col], errors="coerce")
    elif date_col and time_col and date_col != time_col:
        # format MT4/MT5 classique : colonnes Date + Time séparées
        dt = pd.to_datetime(
            raw[date_col].astype(str).str.replace(".", "-", regex=False)
            + " " + raw[time_col].astype(str),
            errors="coerce",
        )
    elif date_col:
        # format Kaggle XAUUSD : une seule colonne "Date" contenant déjà
        # la date ET l'heure, ex "2004.06.11 07:15"
        dt = pd.to_datetime(raw[date_col].astype(str).str.replace(".", "-", regex=False),
                             errors="coerce")
    else:
        raise ValueError(
            f"Impossible de trouver une colonne date/heure dans {path}. "
            f"Colonnes disponibles : {list(raw.columns)}"
        )

    open_col = find("open")
    high_col = find("high")
    low_col = find("low")
    close_col = find("close")
    volume_col = find("volume", "vol", "tick_volume", "tickvol")

    for name, col in [("open", open_col), ("high", high_col), ("low", low_col), ("close", close_col)]:
        if col is None:
            raise ValueError(f"Colonne '{name}' introuvable dans {path}. Colonnes : {list(raw.columns)}")

    df = pd.DataFrame({
        "time": dt,
        "open": pd.to_numeric(raw[open_col], errors="coerce"),
        "high": pd.to_numeric(raw[high_col], errors="coerce"),
        "low": pd.to_numeric(raw[low_col], errors="coerce"),
        "close": pd.to_numeric(raw[close_col], errors="coerce"),
        "volume": pd.to_numeric(raw[volume_col], errors="coerce") if volume_col else 0.0,
    })
    df = df.dropna(subset=["time", "open", "high", "low", "close"])
    df = df.sort_values("time").drop_duplicates(subset="time").reset_index(drop=True)
    return df


def chronological_split(df: pd.DataFrame, train_ratio: float, val_ratio: float,
                          purge_bars: int = 0, embargo_bars: int = 0):
    """Découpe le DataFrame en train/val/test SANS mélanger l'ordre temporel,
    afin d'éviter toute fuite d'information (data leakage) du futur vers le passé.

    PURGE & EMBARGO (standard institutionnel, Marcos López de Prado,
    "Advances in Financial Machine Learning") -- optionnels, désactivés par
    défaut (`purge_bars=0, embargo_bars=0` reproduit EXACTEMENT le
    comportement d'origine, bit pour bit, pour tout appelant existant qui ne
    passe pas ces deux nouveaux paramètres) :

    - `purge_bars` retire les `purge_bars` DERNIÈRES bougies de train (juste
      avant la frontière train/val) ET les `purge_bars` DERNIÈRES bougies de
      val (juste avant la frontière val/test). Raison : les features
      techniques (RSI, MACD, ATR, moyennes mobiles...) sont calculées avec
      des fenêtres glissantes qui regardent en ARRIÈRE -- une bougie juste
      avant une frontière peut donc avoir des indicateurs qui se recouvrent
      partiellement avec la fenêtre de la période suivante. Sans purge, le
      modèle voit à l'entraînement des indicateurs statistiquement "trop
      proches" de ceux qu'il verra en validation/test, un vecteur de fuite
      classique et subtil (pas une fuite du PRIX futur, mais de la
      STRUCTURE STATISTIQUE des indicateurs autour de la frontière).

    - `embargo_bars` retire EN PLUS les `embargo_bars` PREMIÈRES bougies de
      val (juste après la frontière train/val) ET les `embargo_bars`
      PREMIÈRES bougies de test (juste après la frontière val/test).
      Représente la règle du "blackout 24-48h" : juste après une période
      test/OOS, on ne réutilise pas immédiatement les bougies suivantes pour
      entraîner/valider, car la corrélation sérielle des marchés (momentum,
      volatilité qui persiste) peut encore transmettre de l'information de
      la période qu'on vient d'évaluer vers la période suivante.

    Combinés, purge+embargo créent un VRAI TROU (des bougies qui n'existent
    dans AUCUN split, jetées) de part et d'autre de chaque frontière, au
    lieu du découpage actuel à écart nul.

    Comportement si purge_bars/embargo_bars sont trop grands par rapport à
    la taille d'un split : cette fonction ne lève JAMAIS d'exception --
    chaque borne est simplement bornée ("clip") à l'intervalle valide
    [0, n], quitte à produire un split VIDE (0 ligne) si le trou demandé
    dépasse la taille du split concerné. Choix délibéré : un appelant
    automatisé (entraînement continu 24/7) ne doit jamais planter sur un
    réglage agressif de purge/embargo ; c'est à l'appelant de vérifier
    `len(split) > 0` s'il a besoin de cette garantie.

    Retourne toujours 3 DataFrames (train, val, test), chacun avec un index
    remis à zéro (`reset_index(drop=True)`).
    """
    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_stop = max(0, min(n, train_end - purge_bars))
    val_start = max(0, min(n, train_end + embargo_bars))
    val_stop = max(0, min(n, val_end - purge_bars))
    test_start = max(0, min(n, val_end + embargo_bars))

    return (
        df.iloc[:train_stop].reset_index(drop=True),
        df.iloc[val_start:val_stop].reset_index(drop=True),
        df.iloc[test_start:].reset_index(drop=True),
    )


def split_by_calendar_dates(df: pd.DataFrame, train_end, val_end):
    """Découpe train/val/test par DATES ABSOLUES (pas des ratios, contrairement
    à chronological_split) -- LOT 2, phase 4, point 6 : permet d'appliquer aux
    données d'UN symbole les MÊMES frontières temporelles déjà calculées sur
    un AUTRE (typiquement l'or, la référence), pour garantir qu'aucun segment
    d'entraînement d'un symbole ne chevauche temporellement la validation ou
    le jeu sous clé d'un autre -- même quand les deux symboles ont des
    historiques de longueurs différentes. `train_end`/`val_end` : tout ce qui
    est interprétable par `pd.Timestamp`. Ne lève jamais d'exception (un
    split peut être vide si `df` ne couvre pas cette période)."""
    train_end = pd.Timestamp(train_end)
    val_end = pd.Timestamp(val_end)
    times = pd.to_datetime(df["time"])
    train_df = df[times < train_end].reset_index(drop=True)
    val_df = df[(times >= train_end) & (times < val_end)].reset_index(drop=True)
    test_df = df[times >= val_end].reset_index(drop=True)
    return train_df, val_df, test_df


def default_lockbox_start(df: pd.DataFrame) -> pd.Timestamp:
    """Date par défaut du jeu sous clé (LOT 2, phase 1) : les 15% les plus
    récents de l'historique, arrondis au DÉBUT du mois."""
    times = pd.to_datetime(df["time"])
    earliest, latest = times.min(), times.max()
    raw_start = latest - (latest - earliest) * 0.15
    return pd.Timestamp(raw_start.year, raw_start.month, 1)


def split_lockbox(df: pd.DataFrame, lockbox_start, purge_bars: int = 0, embargo_bars: int = 0):
    """Sépare `df` en (visible, lockbox) autour d'une date calendaire fixe
    `lockbox_start` -- `lockbox` (tout ce qui est à partir de cette date) ne
    doit JAMAIS être vu par l'entraînement, la validation, le walk-forward ou
    la promotion (seul scripts/lockbox_eval.py y accède légitimement).
    `purge_bars + embargo_bars` retirent en plus les dernières bougies de
    `visible`, juste avant la frontière (même logique que
    chronological_split), pour qu'aucune bougie adjacente ne fuite
    d'information dans le jeu sous clé. `lockbox_start=None` désactive le
    mécanisme (renvoie `df` entier, lockbox vide)."""
    if lockbox_start is None:
        return df.reset_index(drop=True), df.iloc[0:0].reset_index(drop=True)
    lockbox_start = pd.Timestamp(lockbox_start)
    times = pd.to_datetime(df["time"])
    mask = times < lockbox_start
    visible = df[mask]
    lockbox = df[~mask]
    gap = max(0, purge_bars) + max(0, embargo_bars)
    if gap > 0:
        visible = visible.iloc[:max(0, len(visible) - gap)]
    return visible.reset_index(drop=True), lockbox.reset_index(drop=True)
