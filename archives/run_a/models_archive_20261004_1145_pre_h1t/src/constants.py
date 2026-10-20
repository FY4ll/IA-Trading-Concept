"""
constants.py
============
Constantes partagées entre plusieurs modules -- centralisées ici pour éviter
que la même valeur en dur diverge silencieusement d'un fichier à l'autre.
"""
from __future__ import annotations

# Identifiant MT5 des ordres envoyés par ce bot (voir mt5_connector.py::send_order)
# -- permet de reconnaître ses propres positions parmi celles du compte.
MAGIC_NUMBER = 20260911

# Tolérance de comparaison de volumes (lots) -- en dessous, deux volumes sont
# considérés égaux (évite une fermeture/réouverture inutile pour un écart
# de flottant négligeable).
LOT_TOLERANCE = 1e-4

# Tolérance de comparaison de prix/exposition -- en dessous, une valeur est
# considérée nulle (évite un test d'égalité flottante strict).
PRICE_TOLERANCE = 1e-6
