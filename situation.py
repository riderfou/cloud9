"""
Diagnostic de la situation : y a-t-il vraiment une mer de nuages ?

Deux sources indépendantes :

1. L'image satellite (masque de fraction nuageuse + relief). Dans une vraie mer de nuages, le relief
   nettement SOUS le sommet estimé H est couvert, et le relief nettement AU-DESSUS est dégagé.
   Quand la nappe se disloque (vent, air qui devient instable), des nuages accrochent les sommets :
   le relief au-dessus de H se couvre et H n'a plus de sens.

2. La masse d'air (profil AROME). Une mer de nuages a besoin d'un air stable en basse couche
   (température qui baisse peu avec l'altitude, voire inversion), de peu de vent et pas de pluie.

Seuils calés sur deux journées seulement (31/10/2026 : mer de nuages nette ; 01/11/2026 : nappe qui
monte puis se disloque avec le vent du nord) : à affiner avec d'autres cas (été, pluie, ciel clair).
"""
import numpy as np

# ------------------------------------------------------------------ satellite
MARGE_M = 300            # on ignore le relief à ± MARGE_M de H (bord de nappe, incertitude)
SEUILS_SAT = {
    "dessus_mer": 0.15,          # relief au-dessus de H+300 couvert : < 15 % -> mer de nuages
    "dessus_degradee": 0.35,     # 15-35 % -> nappe qui se dégrade (sommets qui accrochent)
    "dessous_min": 0.45,         # relief sous H-300 couvert : au moins 45 %
    "couvert_total": 0.85,       # tout est couvert (sommets compris) -> couvert / pluie
    "degage_total": 0.08,        # quasi rien de couvert -> pas de nuages bas
}

LIBELLES = {
    "mer": "Mer de nuages",
    "degradee": "Mer de nuages qui se dégrade",
    "disloquee": "Nappe disloquée, nuages accrochés aux sommets",
    "couvert": "Ciel couvert",
    "degage": "Pas de nuages bas",
    "indetermine": "Situation indéterminée",
}
VALIDES = ("mer", "degradee")    # situations où l'altitude du sommet a un sens


def metriques_masque(frac, z, h):
    """frac : fraction nuageuse 0..1 (grille), z : altitude (même grille), h : sommet estimé (m) ou None."""
    ok = np.isfinite(frac) & np.isfinite(z)
    couvert = (frac > 0.5) & ok
    m = {"couvert_total": float(couvert.sum() / max(ok.sum(), 1))}
    if h is not None and np.isfinite(h):
        dessus, dessous = ok & (z > h + MARGE_M), ok & (z < h - MARGE_M)
        m["couvert_dessus"] = float(couvert[dessus].mean()) if dessus.sum() > 200 else None
        m["couvert_dessous"] = float(couvert[dessous].mean()) if dessous.sum() > 200 else None
    return m


def classer_image(m, detectee, h):
    """Situation d'une image d'après ses métriques (voir metriques_masque) et la détection d'origine."""
    s = SEUILS_SAT
    if m["couvert_total"] >= s["couvert_total"]:
        return "couvert"
    if m["couvert_total"] <= s["degage_total"]:
        return "degage"
    dessus, dessous = m.get("couvert_dessus"), m.get("couvert_dessous")
    if h is None or dessous is None:
        return "disloquee" if m["couvert_total"] > 0.25 else "degage"
    if dessus is None:          # rien au-dessus de H+300 dans la zone : on ne peut pas vérifier
        return "mer" if detectee and dessous >= s["dessous_min"] else "indetermine"
    if dessous < s["dessous_min"] or dessus >= s["dessus_degradee"]:
        return "disloquee"
    if not detectee:
        return "indetermine"
    return "mer" if dessus < s["dessus_mer"] else "degradee"


# ------------------------------------------------------------------ masse d'air (AROME)
SEUILS_AIR = {
    "gradient_stable": 4.0,      # °C/km entre la vallée et ~2 000 m : <= 4 -> stable
    "gradient_instable": 6.0,    # >= 6 -> instable (proche de l'adiabatique humide)
    "vent_limite": 25.0,         # km/h à 850 hPa (~1 500 m)
    "vent_fort": 40.0,
    "pluie": 0.3,                # mm/h
}


def masse_air(profil, vent850=None, dir850=None, vent700=None, pluie=None):
    """profil : [{z, T, rh}] (niveaux pression). Renvoie un dict : gradient, inversion, vent, diagnostic."""
    pr = sorted((p for p in profil if p.get("z") is not None and p.get("T") is not None and p["z"] > 230),
                key=lambda p: p["z"])
    out = {"gradient_c_km": None, "inversion": None, "vent850_kmh": vent850, "dir850": dir850,
           "vent700_kmh": vent700, "pluie_mm": pluie}
    if len(pr) < 3:
        out["diagnostic"] = "inconnu"; out["raisons"] = []; return out
    bas = pr[0]
    haut = min(pr, key=lambda p: abs(p["z"] - 2000))
    if haut["z"] - bas["z"] > 600:
        out["gradient_c_km"] = round((bas["T"] - haut["T"]) / (haut["z"] - bas["z"]) * 1000, 1)
    # inversion : couche entre 400 et 3 000 m où la température augmente avec l'altitude
    for a, b in zip(pr, pr[1:]):
        if 400 < a["z"] < 3000 and b["T"] - a["T"] >= 0.3:
            out["inversion"] = {"base_m": round(a["z"]), "sommet_m": round(b["z"]), "ecart_c": round(b["T"] - a["T"], 1)}
            break
    s, raisons, score = SEUILS_AIR, [], 0          # score : 0 favorable, 1 limite, 2 défavorable
    g = out["gradient_c_km"]
    if g is not None:
        if g >= s["gradient_instable"] and not out["inversion"]:
            score = 2; raisons.append("air instable")
        elif g > s["gradient_stable"] and not out["inversion"]:
            score = max(score, 1); raisons.append("air peu stable")
    if vent850 is not None:
        de = f" de {direction(dir850)}" if dir850 is not None else ""
        de = de.replace("de est", "d'est").replace("de ouest", "d'ouest").replace("de nord", "du nord").replace("de sud", "du sud")
        if vent850 >= s["vent_fort"]:
            score = 2; raisons.append(f"vent fort{de} ({round(vent850)} km/h à 1 500 m)")
        elif vent850 >= s["vent_limite"]:
            score = max(score, 1); raisons.append(f"vent{de} ({round(vent850)} km/h à 1 500 m)")
    if pluie is not None and pluie >= s["pluie"]:
        score = 2; raisons.append("pluie")
    out["diagnostic"] = ["favorable", "limite", "defavorable"][score]
    out["raisons"] = raisons
    return out


def direction(deg):
    if deg is None:
        return ""
    return ["nord", "nord-est", "est", "sud-est", "sud", "sud-ouest", "ouest", "nord-ouest"][int((deg + 22.5) % 360 // 45)]
