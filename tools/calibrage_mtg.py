"""
Calibrage MTG-FCI contre VIIRS sur une journée : télécharge les chunks utiles (cache local),
puis analyse chaque image avec plusieurs variantes (parallaxe, seuils 2,2 µm).

  python3 tools/calibrage_mtg.py 2026-10-31 09:00 15:00 [pas_min]
"""
import os, sys, re, glob, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import mtg, viirs

CACHE = "tmp_mtg_cal"


def telecharger_jour(jour, h0, h1, pas):
    a = dt.datetime.combine(jour, h0, dt.timezone.utc); b = dt.datetime.combine(jour, h1, dt.timezone.utc)
    tok = mtg.jeton(); need = mtg.chunks_utiles(); out = []
    for ident, t0, ent in mtg.chercher(a, b):
        if t0.minute % pas:
            continue
        fs = [mtg.telecharger(ent[c], CACHE, tok) for c in need if c in ent]
        m = re.search(r"_OPE_(\d{14})_", os.path.basename(fs[0]))
        out.append((dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc), fs))
    return out


VARIANTES = {
    "reference":        dict(seuils=mtg.SEUILS_MTG, parallaxe=None),
    "sans_voisin":      dict(seuils=mtg.SEUILS_MTG, parallaxe=None, voisin_couvert=None),
    "sans_parallaxe":   dict(seuils=mtg.SEUILS_MTG, parallaxe=(0.0, 0.0)),
    "seuils_viirs":     dict(seuils=viirs.SEUILS_VIIRS, parallaxe=None),
    "seuils_bas":       dict(seuils={"neige_swir_max": 0.08, "nuage_swir_min": 0.15}, parallaxe=None),
}

if __name__ == "__main__":
    jour = dt.date.fromisoformat(sys.argv[1])
    h0, h1 = dt.time.fromisoformat(sys.argv[2]), dt.time.fromisoformat(sys.argv[3])
    pas = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    variantes = sys.argv[5].split(",") if len(sys.argv) > 5 else list(VARIANTES)
    lignes = []
    for quand, fs in telecharger_jour(jour, h0, h1, pas):
        v = mtg.lire(fs, quand)
        ligne = {"t": f"{quand:%H:%M}"}
        for nom in variantes:
            p = VARIANTES[nom]
            par = mtg.parallaxe_utm() if p["parallaxe"] is None else p["parallaxe"]
            res, *_ = viirs.analyse_pixels(dict(v), f"mtg_{quand:%Y%m%d_%H%M}", capteur="MTG-FCI 500 m",
                                           seuils=p["seuils"], max_dist=1200.0, parallaxe=par, min_points=300,
                                           voisin_couvert=p.get("voisin_couvert", mtg.VOISIN_COUVERT))
            ligne[nom] = (round(res["sommet_estime_m"]) if res["sommet_estime_m"] else None,
                          round(res["ecart_interquartile_m"]), res["n_pixels_bord"])
        print(json.dumps(ligne, ensure_ascii=False), flush=True)
        lignes.append(ligne)
    os.makedirs("out", exist_ok=True)
    json.dump(lignes, open(f"out/calibrage_mtg_{jour:%Y%m%d}.json", "w"), ensure_ascii=False, indent=1)
