"""
Prototype : mer de nuages la nuit avec l'infrarouge MTG (écart 10,5 - 3,8 µm), comparée à la méthode visible
aux heures de jour (recouvrement au crépuscule / à l'aube).

  python3 tools/nuit_mtg.py 2026-10-31T16:00 2026-11-01T09:00 [pas_min]
"""
import os, sys, re, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from pyorbital.astronomy import sun_zenith_angle
import mtg, viirs, pipeline, situation as sit

CACHE = "tmp_mtg_nuit"


def analyser(v, quand, nuit):
    p = dict(mtg.PARAMS_NUIT) if nuit else dict(capteur="MTG-FCI 500 m", seuils=mtg.SEUILS_MTG, max_dist=1200.0,
                                                min_points=300, voisin_couvert=mtg.VOISIN_COUVERT)
    res, v2, fmap, dem, est = viirs.analyse_pixels(v, f"mtg_{quand:%Y%m%d_%H%M}", parallaxe=mtg.parallaxe_utm(), **p)
    h = res["sommet_estime_m"] if res["sommet_estime_m"] else res["h_bords_quantiles_10_25_50_75_90"][2]
    f = pipeline.down(np.nan_to_num(fmap).astype("float32"))
    m = sit.metriques_masque(f, pipeline.relief_web(), h if h == h else None)
    s = sit.classer_image(m, res["mer_de_nuages_detectee"], h if h == h else None)
    return res, fmap, dem, est, s, m


if __name__ == "__main__":
    a = dt.datetime.fromisoformat(sys.argv[1]).replace(tzinfo=dt.timezone.utc)
    b = dt.datetime.fromisoformat(sys.argv[2]).replace(tzinfo=dt.timezone.utc)
    pas = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    tok = mtg.jeton(); lignes = []
    for ident, t0, ent in mtg.chercher(a, b):
        if t0.minute % pas or (t0.minute + t0.hour * 60) % pas:
            continue
        f = mtg.telecharger(ent[36], CACHE, tok)
        quand = dt.datetime.strptime(re.search(r"_OPE_(\d{14})_", f).group(1), "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)
        sza = float(sun_zenith_angle(quand.replace(tzinfo=None), mtg.LON, mtg.LAT))
        ligne = {"t": f"{quand:%d/%m %H:%M}", "sza": round(sza), "refs_ir": None}
        vn = mtg.lire_nuit([f], quand); ligne["refs_ir"] = {k: round(x, 2) for k, x in vn["refs"].items()}
        res, fmap, dem, est, s, m = analyser(vn, quand, True)
        rd = lambda x: None if x is None or x != x else round(x)
        ligne["ir"] = (rd(res["sommet_estime_m"]), rd(res["ecart_interquartile_m"]), res["n_pixels_bord"], s,
                       m.get("couvert_dessus") and round(m["couvert_dessus"], 2), m.get("couvert_dessous") and round(m["couvert_dessous"], 2))
        if sza < 80:    # jour : méthode visible pour comparer
            r2, *_rest = analyser(mtg.lire([f], quand), quand, False)
            ligne["visible"] = (rd(r2["sommet_estime_m"]), _rest[3])
        print(json.dumps(ligne, ensure_ascii=False), flush=True)
        lignes.append(ligne)
    json.dump(lignes, open("out/nuit_mtg.json", "w"), ensure_ascii=False, indent=1)
