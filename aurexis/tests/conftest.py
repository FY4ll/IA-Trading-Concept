import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # Test_IA
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)
