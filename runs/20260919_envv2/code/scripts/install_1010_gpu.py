"""Installation du 10/10 ~1h40 : une notification par cycle + apprentissage d'AUREXIS sur la carte graphique."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import notif_chaque_cycle
notif_chaque_cycle.main()
import apprentissage_gpu
apprentissage_gpu.main()