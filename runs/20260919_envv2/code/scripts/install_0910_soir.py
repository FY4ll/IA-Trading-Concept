"""Installation du 09/10 au soir (Run A ARRÊTÉ) : 1) veine « professeur » ; 2) vision des tendances de fond (greffe
du champion, du professeur et de TOUTES les veines -- dont celle du professeur -- puis réglage)."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import veine_professeur
veine_professeur.main()
import vision_tendances_aurexis
vision_tendances_aurexis.main(False)
