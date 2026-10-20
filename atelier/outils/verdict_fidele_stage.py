"""Lance le verdict des 12 mois de la copie de travail (atelier/code_stage) sur les données et modèles de production,
sans toucher à la production : code du stage d'abord dans le chemin, sortie dans atelier/."""
import os, sys
PROD = r"C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code"
STAGE = r"C:\Users\utilisateur\Documents\Test_IA\atelier\code_stage"
os.environ.setdefault("PRED_SORTIE", r"C:\Users\utilisateur\Documents\Test_IA\atelier\verdict_fidele.json")
src = open(os.path.join(STAGE, "scripts", "verdict_12_mois.py"), encoding="utf-8").read()
src = src.replace('CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))', f"CODE = r'{PROD}'")
src = src.replace("sys.path.insert(0, CODE)", f"sys.path.insert(0, CODE); sys.path.insert(0, r'{STAGE}')", 1)
assert f"r'{STAGE}'" in src and f"r'{PROD}'" in src
exec(compile(src, "verdict_12_mois(stage)", "exec"), {"__name__": "__main__", "__file__": os.path.join(PROD, "scripts", "x.py")})
