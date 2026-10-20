"""
finbert_sentiment.py
======================
Sentiment financier RÉEL, pas un lexique générique : FinBERT
(ProsusAI/finbert) est un modèle BERT spécifiquement affiné sur du texte
financier (dépêches Reuters), capable de distinguer le sens financier réel
d'une phrase -- ce qu'un lexique mot-à-mot comme VADER ne peut pas faire,
faute de contexte (ex: "les taux montent" n'est ni bon ni mauvais en soi,
son sens dépend du contexte financier).

100% LOCAL, PAS D'API : les poids (~440 Mo) sont téléchargés UNE SEULE FOIS
depuis Hugging Face (mis en cache localement par la bibliothèque
`transformers`), puis chaque analyse tourne entièrement sur cette machine
-- aucune connexion internet ni service payant à l'exécution une fois le
modèle en cache.

Chargement paresseux (au premier appel, pas à l'import) et échec silencieux
(retourne None si `transformers` n'est pas installé ou si le téléchargement
initial échoue) : l'appelant (fundamental_feed.py) retombe alors sur VADER,
jamais de plantage du pipeline pour ça.
"""
from __future__ import annotations
import logging
import threading

log = logging.getLogger("finbert_sentiment")

MODEL_NAME = "ProsusAI/finbert"
_model = None
_tokenizer = None
_id2label = None
_unavailable = False
# Deux instances de AutoFundamentalFeed existent en pratique (une pour
# l'entraînement dans autonomous_agent.py, une pour la démo dans
# demo_trader.py), tournant dans des threads DIFFÉRENTS -- sans ce verrou,
# les deux pourraient voir `_model is None` en même temps et charger FinBERT
# deux fois en parallèle (double consommation mémoire, écriture concurrente
# du cache Hugging Face). Le verrou ne protège QUE le chargement paresseux ;
# une fois chargé, l'inference (score()) elle-même n'a pas besoin d'être
# sérialisée (un forward pass PyTorch en mode eval ne mute aucun état
# partagé).
_load_lock = threading.Lock()


def _get_model():
    """Charge FinBERT en appelant DIRECTEMENT AutoTokenizer/
    AutoModelForSequenceClassification -- PAS `transformers.pipeline()`,
    qui importe inconditionnellement des utilitaires de traitement d'image
    (donc `torchvision`) même pour une tâche purement textuelle. Évite
    ainsi toute dépendance à torchvision (dont la version peut être
    incompatible avec celle de torch installée pour l'entraînement RL, un
    conflit sans rapport avec ce module mais qui casserait `pipeline()`)."""
    global _model, _tokenizer, _id2label, _unavailable
    if _model is not None or _unavailable:
        return _model, _tokenizer, _id2label
    with _load_lock:
        if _model is not None or _unavailable:  # un autre thread a chargé pendant l'attente du verrou
            return _model, _tokenizer, _id2label
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
            _model.eval()
            _id2label = {i: label.lower() for i, label in _model.config.id2label.items()}
            log.info(f"FinBERT chargé ({MODEL_NAME}) -- sentiment financier local, sans API, sans lexique générique.")
        except Exception as e:
            log.warning(f"FinBERT indisponible ({type(e).__name__}: {e}) -> repli sur VADER (lexique générique) "
                        f"pour cette session.")
            _unavailable = True
            _model = None
    return _model, _tokenizer, _id2label


def score(text: str) -> float | None:
    """Retourne un score de sentiment financier dans [-1, 1] (positif -
    négatif), ou None si FinBERT est indisponible -- l'appelant retombe
    alors sur VADER pour ce titre précis."""
    if not text:
        return None
    model, tokenizer, id2label = _get_model()
    if model is None:
        return None
    try:
        import torch
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = model(**inputs).logits[0]
        probs = torch.softmax(logits, dim=0).tolist()
        scores = {id2label[i]: p for i, p in enumerate(probs)}
        return float(scores.get("positive", 0.0) - scores.get("negative", 0.0))
    except Exception as e:
        log.warning(f"Échec de scoring FinBERT pour un titre ({type(e).__name__}: {e}) -> repli VADER pour celui-ci.")
        return None
