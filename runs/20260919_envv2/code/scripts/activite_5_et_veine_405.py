"""
(10/10/2026, accord de l'utilisateur : « fais ce qui te semble juste »)
1) Activité minimale d'AUREXIS : 10 -> 5 trades par marché et par période en moyenne. Au cycle 405, le meilleur
   candidat (+1,1 %/mois sur les DEUX périodes, mieux que le champion) a été écarté avec 874 trades au total (~8 par
   marché et par période) : 10 était trop sévère pour une IA qui suit la tendance sans s'agiter. 5 reste un garde-fou
   solide contre les IA qui ne font rien.
2) Ce candidat (mis à l'abri : models/ecartes_AUREXIS/gen405_AUREXIS_0_1.zip) revient en compétition comme VEINE : il
   sera nourri et rejugé sur les prochains cycles, et ne devient champion que s'il bat le champion (mêmes règles).

    python scripts/activite_5_et_veine_405.py        (cwd = code/, Run A ARRÊTÉ ; lancé par boundary_apply_staged.ps1)
"""
import json, os, shutil, time
import yaml

CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG = os.path.join(CODE, "..", "run_config_A.yaml")
SRC = os.path.join(CODE, "models", "ecartes_AUREXIS", "gen405_AUREXIS_0_1.zip")
VDIR = os.path.join(CODE, "models", "champion_AUREXIS", "veines")
VID = "ECART405"


def main():
    text = open(CONFIG, encoding="utf-8").read()
    old = "    AUREXIS: {min_trades: 0, min_market_trades: 0, min_avg_market_trades: 10}"
    if old in text:
        shutil.copy(CONFIG, CONFIG + f".bak_activite5_{time.strftime('%Y%m%d_%H%M')}")
        text = text.replace(old, "    # 10/10 : 10 -> 5 (cycle 405 : le meilleur candidat écarté avec ~8 trades par marché et par période)\n"
                                 "    AUREXIS: {min_trades: 0, min_market_trades: 0, min_avg_market_trades: 5}")
        assert yaml.safe_load(text)["continuous"]["min_activity_by_style"]["AUREXIS"]["min_avg_market_trades"] == 5
        open(CONFIG, "w", encoding="utf-8").write(text)
        print("activité minimale : 5 trades par marché et par période")
    vj = os.path.join(VDIR, "veines.json")
    veins = json.load(open(vj, encoding="utf-8")) if os.path.exists(vj) else []
    if not any(v["id"] == VID for v in veins) and os.path.exists(SRC):
        gen = int(json.load(open(os.path.join(CODE, "models", "_progress.json"), encoding="utf-8")).get("generation", 0))
        path = os.path.join(VDIR, VID)
        shutil.copy(SRC, path + ".zip")
        veins.append({"id": VID, "score": 0.0, "gap": 0.0, "best_gap": 0.0, "flux": 1.5, "stall": 0, "tries": 0,
                      "born": gen, "last_gen": gen, "reason": "candidat du cycle 405 écarté pour l'activité "
                      "(+1,1 %/mois sur les deux périodes, mieux que le champion)", "hyperparams": None,
                      "history": [], "path": path})
        shutil.copy(vj, vj + f".bak_{time.strftime('%Y%m%d_%H%M')}")
        json.dump(veins, open(vj + ".tmp", "w", encoding="utf-8"), indent=1, default=str)
        os.replace(vj + ".tmp", vj)
        print(f"veine {VID} ajoutée ({len(veins)} veines)")


if __name__ == "__main__":
    main()
