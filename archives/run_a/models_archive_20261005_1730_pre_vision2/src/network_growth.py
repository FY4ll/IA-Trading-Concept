"""
network_growth.py
==================
Croissance À FONCTION PRÉSERVÉE (technique "Net2Net", Chen et al. 2016) du
LSTM de `src/policy_networks.py::LSTMFeaturesExtractor` -- fait grandir
`lstm_hidden_size` d'un agent déjà entraîné SANS repartir de zéro : les
nouveaux neurones sont ajoutés de façon à ce que la décision produite par le
réseau soit RIGOUREUSEMENT IDENTIQUE juste après la croissance, puis
divergent au fil de l'entraînement suivant à mesure qu'ils apprennent.

Contrairement à une simple augmentation de `agent.lstm_hidden_size` dans la
config (qui casse le warm start -- l'ancien réseau ne peut plus être chargé
dans le nouveau, voir agent.py::_warm_start), cette fonction construit
explicitement le nouveau réseau et y RECOPIE les poids existants -- rien
n'est perdu.

PRINCIPE (voir la démonstration complète dans la conversation qui a motivé
ce module, 29/09) : trois endroits du réseau doivent être modifiés en
cohérence pour que la garantie tienne de bout en bout :
  1. Le LSTM lui-même (`features_extractor.lstm`) : les nouvelles unités
     cachées ne doivent JAMAIS influencer les anciennes (bloc
     ancien-vers-nouveau de `weight_hh_l0` mis à zéro), mais peuvent lire
     librement les anciennes ET s'initialiser aléatoirement pour le reste --
     elles n'affectent rien tant que l'étape 3 les bloque en aval.
  2. La tête `features_extractor.head` (Linear après le LSTM) : les
     anciennes lignes de sortie ne doivent lire QUE les anciennes unités
     cachées (poids nuls vers les nouvelles) -- les variables "extra"
     (position, pnl...) sont RE-POSITIONNÉES (elles glissent après les
     nouvelles unités dans le vecteur concaténé, voir
     LSTMFeaturesExtractor.forward).
  3. La première couche de `policy_net`/`value_net` de PPO (SB3
     `MlpExtractor`) : les nouvelles colonnes d'entrée (correspondant aux
     nouvelles features en sortie de la tête) sont mises à zéro -- ainsi,
     quoi que calculent les nouvelles unités en amont, ça n'atteint jamais
     la décision finale avant que l'entraînement ne les "active"
     graduellement par la suite.

Ne gère QUE la croissance de `lstm_hidden_size` (donc de `features_dim`,
qui lui est égal dans agent.py) -- PAS `net_arch` (la largeur des couches
256/256 de PPO elle-même), qui reste inchangée : ça suffit à augmenter
significativement la capacité de perception temporelle sans multiplier la
complexité de cette chirurgie. `use_lstm=False` (MlpPolicy pur, sans
extracteur personnalisé) ou un algorithme SAC/TD3 ne sont pas supportés --
lève NotImplementedError explicitement plutôt qu'un résultat silencieusement
faux.
"""
from __future__ import annotations
import torch
import torch.nn as nn


def _grow_lstm_state_dict(old_lstm: nn.LSTM, new_hidden_size: int, dtype, device) -> dict:
    """Construit les 4 tenseurs de poids/biais d'un `nn.LSTM` agrandi à
    `new_hidden_size`, à partir des poids de `old_lstm`. Retourne un dict
    prêt à fusionner dans le state_dict complet du nouveau modèle (clés
    préfixées `lstm.` -- voir l'appelant)."""
    old_hidden_size = old_lstm.hidden_size
    input_size = old_lstm.input_size
    grown = int(new_hidden_size) - int(old_hidden_size)
    if grown <= 0:
        raise ValueError(f"new_hidden_size ({new_hidden_size}) doit être STRICTEMENT supérieur "
                          f"à l'actuel ({old_hidden_size}) -- cette fonction ne fait que grandir, "
                          "jamais rétrécir.")

    old_w_ih = old_lstm.weight_ih_l0.detach()   # (4*H, input_size)
    old_w_hh = old_lstm.weight_hh_l0.detach()   # (4*H, H)
    old_b_ih = old_lstm.bias_ih_l0.detach()     # (4*H,)
    old_b_hh = old_lstm.bias_hh_l0.detach()     # (4*H,)

    new_w_ih = torch.zeros(4 * new_hidden_size, input_size, dtype=dtype, device=device)
    new_w_hh = torch.zeros(4 * new_hidden_size, new_hidden_size, dtype=dtype, device=device)
    new_b_ih = torch.zeros(4 * new_hidden_size, dtype=dtype, device=device)
    new_b_hh = torch.zeros(4 * new_hidden_size, dtype=dtype, device=device)

    # Petite échelle d'initialisation aléatoire pour les unités NEUVES --
    # cohérente avec l'init par défaut de PyTorch pour nn.LSTM (uniforme
    # dans [-1/sqrt(H), 1/sqrt(H)]), pour ne pas déstabiliser l'entraînement
    # qui suivra par des poids anormalement grands.
    init_scale = 1.0 / (new_hidden_size ** 0.5)

    # Découpage par PORTE : PyTorch concatène [input, forget, cell, output]
    # le long de la dimension 0, chaque bloc de taille H -- il faut traiter
    # CHAQUE porte séparément, jamais une simple concaténation globale.
    for gate in range(4):
        old_lo, old_hi = gate * old_hidden_size, (gate + 1) * old_hidden_size
        new_lo, new_hi = gate * new_hidden_size, gate * new_hidden_size + old_hidden_size
        new_extra_lo, new_extra_hi = new_lo + old_hidden_size, new_hi + grown

        # weight_ih : lignes anciennes préservées, lignes neuves = aléatoire
        # (lisent l'observation brute -- rien à préserver, aucune contrainte).
        new_w_ih[new_lo:new_hi, :] = old_w_ih[old_lo:old_hi, :]
        new_w_ih[new_extra_lo:new_extra_hi, :] = (
            torch.empty(grown, input_size, dtype=dtype, device=device).uniform_(-init_scale, init_scale))

        # weight_hh : bloc ancien->ancien préservé, ancien->neuf figé à ZÉRO
        # (les anciennes unités ne doivent JAMAIS "voir" les nouvelles --
        # c'est CE zéro qui garantit que leur trajectoire est inchangée),
        # neuf->tout = aléatoire (les nouvelles unités peuvent lire
        # librement, ça n'affecte que leur propre valeur, jamais celle des
        # anciennes).
        new_w_hh[new_lo:new_hi, :old_hidden_size] = old_w_hh[old_lo:old_hi, :]
        # new_w_hh[new_lo:new_hi, old_hidden_size:new_hidden_size] reste à 0 (init torch.zeros ci-dessus)
        new_w_hh[new_extra_lo:new_extra_hi, :] = (
            torch.empty(grown, new_hidden_size, dtype=dtype, device=device).uniform_(-init_scale, init_scale))

        # biais : anciens préservés, neufs à zéro (les nouvelles unités
        # démarrent "neutres" -- leur poids d'entrée aléatoire suffit à les
        # faire diverger au fil de l'entraînement, pas besoin d'un biais
        # non nul dès le départ).
        new_b_ih[new_lo:new_hi] = old_b_ih[old_lo:old_hi]
        new_b_hh[new_lo:new_hi] = old_b_hh[old_lo:old_hi]

    return {
        "weight_ih_l0": new_w_ih, "weight_hh_l0": new_w_hh,
        "bias_ih_l0": new_b_ih, "bias_hh_l0": new_b_hh,
    }


def grow_agent(agent, new_hidden_size: int, env):
    """Fait grandir `agent.model` (un `src.agent.TradingAgent`, PPO +
    `LSTMFeaturesExtractor`) EN PLACE jusqu'à `new_hidden_size` -- voir le
    docstring du module pour la garantie de préservation de fonction.
    `env` sert UNIQUEMENT à construire le nouvel agent (même environnement
    que celui utilisé pour créer `agent` -- jamais utilisé pour autre chose
    qu'obtenir les bonnes dimensions d'observation/action). Modifie
    `agent.hyperparams["lstm_hidden_size"]` pour rester cohérent avec le
    réseau reconstruit (utile si l'appelant sauvegarde ces hyperparamètres à
    côté du modèle)."""
    from src.policy_networks import LSTMFeaturesExtractor

    policy = agent.model.policy
    old_extractor = policy.features_extractor
    if not isinstance(old_extractor, LSTMFeaturesExtractor):
        raise NotImplementedError(
            "grow_agent ne supporte que les agents avec use_lstm=true (LSTMFeaturesExtractor) -- "
            f"extracteur actuel : {type(old_extractor).__name__}.")
    if type(agent.model).__name__ != "PPO":
        raise NotImplementedError("grow_agent ne supporte que PPO pour l'instant (SAC/TD3 non couverts).")

    old_hidden_size = old_extractor.lstm.hidden_size
    if new_hidden_size <= old_hidden_size:
        raise ValueError(f"new_hidden_size ({new_hidden_size}) doit dépasser l'actuel ({old_hidden_size}).")
    extra_dim = old_extractor.extra_dim

    device = next(policy.parameters()).device
    dtype = old_extractor.lstm.weight_ih_l0.dtype

    # 1) reconstruit un extracteur/policy NEUFS à la nouvelle taille, via le
    #    même mécanisme que TradingAgent.__init__ (jamais une deuxième
    #    implémentation de la construction du réseau qui pourrait diverger).
    from src.agent import TradingAgent
    new_hp = {**agent.hyperparams, "lstm_hidden_size": new_hidden_size, "use_lstm": True}
    new_agent = TradingAgent(env, new_hp, warm_start_model_path=None)
    new_policy = new_agent.model.policy
    new_extractor = new_policy.features_extractor

    # 2) LSTM -- voir _grow_lstm_state_dict.
    grown_lstm_sd = _grow_lstm_state_dict(old_extractor.lstm, new_hidden_size, dtype, device)
    new_extractor.lstm.load_state_dict(grown_lstm_sd)

    # 3) tête (Linear après le LSTM) -- voir le docstring du module, point 2.
    old_head_w = old_extractor.head[0].weight.detach()   # (features_dim_old, H_old + extra_dim)
    old_head_b = old_extractor.head[0].bias.detach()     # (features_dim_old,)
    features_dim_old = old_head_w.shape[0]
    new_head_w = torch.empty_like(new_extractor.head[0].weight.data).uniform_(
        -1.0 / (new_hidden_size ** 0.5), 1.0 / (new_hidden_size ** 0.5))
    new_head_b = torch.zeros_like(new_extractor.head[0].bias.data)
    new_head_w[:features_dim_old, :old_hidden_size] = old_head_w[:, :old_hidden_size]
    new_head_w[:features_dim_old, old_hidden_size:new_hidden_size] = 0.0
    new_head_w[:features_dim_old, new_hidden_size:new_hidden_size + extra_dim] = old_head_w[:, old_hidden_size:old_hidden_size + extra_dim]
    new_head_b[:features_dim_old] = old_head_b
    new_extractor.head[0].weight.data.copy_(new_head_w)
    new_extractor.head[0].bias.data.copy_(new_head_b)

    # 4) première couche de policy_net/value_net (SB3 MlpExtractor) -- voir
    #    le docstring du module, point 3 : SEULES les colonnes d'entrée
    #    grandissent (features_dim), la largeur de sortie (net_arch[0])
    #    est INCHANGÉE, donc pas de découpage par ligne nécessaire ici.
    old_mlp = policy.mlp_extractor
    new_mlp = new_policy.mlp_extractor
    for net_name in ("policy_net", "value_net"):
        old_layer = getattr(old_mlp, net_name)[0] if len(getattr(old_mlp, net_name)) else None
        new_layer = getattr(new_mlp, net_name)[0] if len(getattr(new_mlp, net_name)) else None
        if old_layer is None or new_layer is None:
            continue  # net_arch vide pour ce réseau (jamais le cas ici, mais pas une erreur en soi)
        new_w = torch.zeros_like(new_layer.weight.data)
        new_w[:, :features_dim_old] = old_layer.weight.detach()
        new_layer.weight.data.copy_(new_w)
        new_layer.bias.data.copy_(old_layer.bias.detach())

    # 5) le reste de la politique (couches suivantes de policy_net/value_net,
    #    et les têtes action_net/value_net finales) NE dépend QUE de la
    #    sortie de policy_net[0]/value_net[0] -- puisque ses colonnes neuves
    #    sont nulles (étape 4), sa sortie est déjà identique à l'ancienne,
    #    donc TOUT ce qui suit peut être copié tel quel sans aucune
    #    transformation.
    new_params_by_name = dict(new_policy.named_parameters())
    for name, old_param in policy.named_parameters():
        if name.startswith("features_extractor.") or name.startswith("mlp_extractor.policy_net.0") \
                or name.startswith("mlp_extractor.value_net.0"):
            continue  # déjà traités ci-dessus (1, 2, 3, 4)
        new_param = new_params_by_name[name]
        if new_param.shape == old_param.shape:
            new_param.data.copy_(old_param.detach())
        # sinon (théoriquement jamais atteint pour ce type de croissance) :
        # garde l'initialisation neuve plutôt qu'une copie invalide.

    agent.model = new_agent.model
    agent.hyperparams = new_hp
    return agent


def grow_agent_from_path(old_model_path: str, new_hidden_size: int, env, hyperparams: dict):
    """Variante autonome (sans instance `TradingAgent` déjà vivante) : charge
    le modèle sauvegardé à `old_model_path`, construit un nouvel agent à
    `new_hidden_size` sur `env`, et lui transplante les poids grandis. Utilisé
    par continuous_trainer.py, qui ne garde jamais d'objet TradingAgent vivant
    entre deux cycles (seulement des chemins de fichiers, voir
    _train_candidate_worker)."""
    from src.agent import TradingAgent
    old_agent = TradingAgent(env, hyperparams, warm_start_model_path=old_model_path)
    return grow_agent(old_agent, new_hidden_size, env)


def add_action_dim(agent, new_env, new_hyperparams: dict):
    """Ajoute une (ou plusieurs) dimension(s) à l'espace d'action DISCRET
    MultiDiscrete de `agent.model` (PPO) -- ex: `learn_take_profit` qui
    ajoute le choix d'un multiple de take-profit en plus de la direction et
    du stop-loss déjà appris (voir src/trading_env.py) -- SANS RIEN PERDRE
    des dimensions déjà apprises.

    Contrairement à `grow_agent` (qui doit zéro-initialiser plusieurs
    couches en cascade pour préserver la fonction, voir son docstring), ce
    cas est plus simple : SB3 construit la distribution `MultiCategorical`
    à partir d'UNE SEULE couche (`action_net`, voir
    stable_baselines3.common.distributions.MultiCategoricalDistribution.
    proba_distribution_net) dont la sortie est la CONCATÉNATION des logits
    de chaque dimension, dans l'ORDRE de `action_dims` -- ajouter une
    dimension à la FIN ne fait qu'AJOUTER des lignes de sortie à cette
    couche, sans toucher aux lignes existantes ni à rien en amont
    (features_extractor, mlp_extractor, value_net sont TOUS inchangés,
    puisque seule la dimension de SORTIE de `action_net` grandit, jamais son
    entrée). Les anciennes dimensions (direction, stop-loss) produisent donc
    des logits RIGOUREUSEMENT IDENTIQUES à avant ; seule la nouvelle
    dimension démarre non-entraînée (aléatoire), ce qui est inévitable
    puisqu'elle n'a jamais existé.

    `new_env`/`new_hyperparams` doivent refléter le NOUVEL espace d'action
    complet (ex: `learn_take_profit=True` déjà positionné sur l'env) --
    c'est cette forme qui détermine la taille de la nouvelle `action_net`.
    """
    policy = agent.model.policy
    old_action_net = policy.action_net
    if not isinstance(old_action_net, nn.Linear):
        raise NotImplementedError(
            "add_action_dim ne supporte que les politiques discrètes MultiDiscrete "
            f"(action_net attendu de type nn.Linear, obtenu {type(old_action_net).__name__}).")

    from src.agent import TradingAgent
    new_agent = TradingAgent(new_env, new_hyperparams, warm_start_model_path=None)
    new_policy = new_agent.model.policy
    new_action_net = new_policy.action_net
    old_out = old_action_net.weight.shape[0]
    new_out = new_action_net.weight.shape[0]
    if new_out <= old_out:
        raise ValueError(f"Le nouvel espace d'action ({new_out} logits) n'est pas plus grand que "
                          f"l'actuel ({old_out}) -- rien à ajouter.")

    new_weight = new_action_net.weight.data.clone()
    new_bias = new_action_net.bias.data.clone()
    new_weight[:old_out, :] = old_action_net.weight.detach()
    new_bias[:old_out] = old_action_net.bias.detach()
    # new_weight[old_out:, :] / new_bias[old_out:] gardent l'initialisation
    # neuve de new_action_net (aléatoire, non entraînée -- la nouvelle
    # dimension, voir docstring).
    new_action_net.weight.data.copy_(new_weight)
    new_action_net.bias.data.copy_(new_bias)

    # Tout le reste (features_extractor, mlp_extractor, value_net) est
    # INCHANGÉ de forme -- copié tel quel, sans transformation.
    new_params_by_name = dict(new_policy.named_parameters())
    for name, old_param in policy.named_parameters():
        if name == "action_net.weight" or name == "action_net.bias":
            continue  # déjà traités ci-dessus
        new_param = new_params_by_name[name]
        if new_param.shape == old_param.shape:
            new_param.data.copy_(old_param.detach())

    agent.model = new_agent.model
    agent.hyperparams = new_hyperparams
    return agent


def add_action_dim_from_path(old_model_path: str, old_env, new_env, old_hyperparams: dict, new_hyperparams: dict):
    """Variante autonome de `add_action_dim` (sans instance `TradingAgent`
    déjà vivante) -- charge le modèle sauvegardé à `old_model_path` sur
    `old_env`/`old_hyperparams` (SON espace d'action ORIGINAL -- sans quoi le
    warm start échoue silencieusement en formes incompatibles, voir
    agent.py::_warm_start, et le modèle repartirait de zéro sans qu'on s'en
    rende compte), puis transplante vers `new_env`/`new_hyperparams` (nouvel
    espace d'action, ex: `learn_take_profit=True`)."""
    from src.agent import TradingAgent
    old_agent = TradingAgent(old_env, old_hyperparams, warm_start_model_path=old_model_path)
    return add_action_dim(old_agent, new_env, new_hyperparams)


def add_input_features(agent, new_env, new_hyperparams: dict):
    """Élargit l'ENTRÉE du LSTM (nouvelles variables d'observation ajoutées À LA FIN de la liste de
    features) sans rien perdre : les colonnes neuves de `lstm.weight_ih_l0` sont initialisées à 0, donc
    tant que l'apprentissage ne les utilise pas, la politique produit EXACTEMENT les mêmes décisions
    qu'avant. Tout le reste du réseau garde sa forme et est copié tel quel."""
    from src.agent import TradingAgent

    old_ex = agent.model.policy.features_extractor
    new_agent = TradingAgent(new_env, new_hyperparams, warm_start_model_path=None)
    new_policy = new_agent.model.policy
    new_ex = new_policy.features_extractor
    n_old, n_new = old_ex.n_features, new_ex.n_features
    if n_new <= n_old:
        raise ValueError(f"Pas plus de variables ({n_new} <= {n_old}) : rien à ajouter.")
    new_params = dict(new_policy.named_parameters())
    for name, old_param in agent.model.policy.named_parameters():
        new_param = new_params[name]
        if name == "features_extractor.lstm.weight_ih_l0":
            w = torch.zeros_like(new_param.data)
            w[:, :n_old] = old_param.detach()
            new_param.data.copy_(w)
        elif new_param.shape == old_param.shape:
            new_param.data.copy_(old_param.detach())
        else:
            raise ValueError(f"Forme inattendue pour {name} : {tuple(old_param.shape)} -> {tuple(new_param.shape)}")
    agent.model = new_agent.model
    agent.hyperparams = new_hyperparams
    return agent


def add_input_features_from_path(old_model_path: str, old_env, new_env, old_hyperparams: dict, new_hyperparams: dict):
    from src.agent import TradingAgent
    old_agent = TradingAgent(old_env, old_hyperparams, warm_start_model_path=old_model_path)
    return add_input_features(old_agent, new_env, new_hyperparams)