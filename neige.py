"""
Calque de neige à partir de Meteosat MTG (jour) : visible 0,6 µm et infrarouge court 2,2 µm.

La neige est très brillante dans le visible et sombre à 2,2 µm (indice de neige NDSI élevé) ; les nuages
d'eau sont brillants dans les deux canaux. Pour chaque pixel MTG (500 m) sans nuage, on estime une fraction
enneigée, puis on la répartit sur le relief à l'intérieur du pixel : la neige occupe la partie la plus haute
(même principe que pour les nuages bas, qui occupent la partie la plus basse). La limite d'enneigement suit
ainsi le relief à 100 m.

Composite : web/data/neige.png garde, pour chaque point de la grille, la dernière observation sans nuage.
Images utilisées : celles proches du midi solaire (moins d'ombres portées en montagne). Le même jour, on garde
le maximum (une ombre ou un voile fin fait baisser la fraction, rarement l'inverse).

  neige.png : R = fraction enneigée (0-255), G/B = heure de la dernière observation sans nuage
              (heures depuis REF, sur 16 bits ; 0 = jamais observé)
  neige.json : date de mise à jour, images utilisées, surface enneigée, altitude de la limite d'enneigement
"""
import os, json, datetime as dt
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from scipy import ndimage
import mer2nuages as m2n

REF = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
SEUILS = {"ndsi_neige": 0.40, "swir_neige_max": 0.15, "vis_neige_min": 0.20,      # neige (au moins en partie)
          "vis_sol": 0.15, "vis_neige_pure": 0.60,                                # références de la fraction
          "nuage_swir_min": 0.20, "nuage_vis_min": 0.25}                           # nuage d'eau
HEURES_MIDI = 2.5     # images utilisées : ± 2 h 30 autour du midi solaire


def midi_solaire(quand, lon=5.8):
    """Heure UTC du midi solaire à la longitude donnée (équation du temps incluse, à la minute près)."""
    j = quand.timetuple().tm_yday
    b = 2 * np.pi * (j - 81) / 364
    eot = 9.87 * np.sin(2 * b) - 7.53 * np.cos(b) - 1.5 * np.sin(b)          # minutes
    m = 12 * 60 - 4 * lon - eot
    return quand.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(minutes=float(m))


def proche_midi(quand):
    return abs((quand - midi_solaire(quand)).total_seconds()) <= HEURES_MIDI * 3600


def fraction_pixels(v):
    """Fraction enneigée par pixel MTG : 0..1, NaN si nuageux (inconnu)."""
    i1, i3 = v["I1"], v["I3"]
    ndsi = (i1 - i3) / np.maximum(i1 + i3, 1e-6)
    s = SEUILS
    nuage = ((i3 > s["nuage_swir_min"]) & (i1 > s["nuage_vis_min"])) | ((i1 > 0.5) & (ndsi < 0.25))
    neige = (ndsi > s["ndsi_neige"]) & (i3 < s["swir_neige_max"]) & (i1 > s["vis_neige_min"])
    f = np.where(neige, np.clip((i1 - s["vis_sol"]) / (s["vis_neige_pure"] - s["vis_sol"]), 0, 1), 0.0)
    f[nuage & ~neige] = np.nan
    f[~np.isfinite(i1) | ~np.isfinite(i3)] = np.nan
    return f


def vers_grille(v, f, z, parallaxe, max_dist=1200.0):
    """Répartit la fraction de chaque pixel sur la grille web (100 m) : la neige occupe la partie la plus haute
    du relief de chaque pixel. Renvoie un tableau (GH, GW) : 0..1, NaN = inconnu (nuage, hors image)."""
    GH, GW = z.shape
    pas = (m2n.AOI[2] - m2n.AOI[0]) / GW
    jj, ii = np.meshgrid(np.arange(GW), np.arange(GH))
    X = m2n.AOI[0] + (jj + .5) * pas + z * parallaxe[0]
    Y = m2n.AOI[3] - (ii + .5) * pas + z * parallaxe[1]
    ok = np.isfinite(v["x"]) & np.isfinite(v["y"])
    fv = f[ok]
    d, idx = cKDTree(np.c_[v["x"][ok], v["y"][ok]]).query(np.c_[X.ravel(), Y.ravel()], distance_upper_bound=max_dist)
    has = np.isfinite(d)
    out = np.full(z.size, np.nan, "float32")
    zr = z.ravel()
    pts = np.where(has)[0]
    order = np.argsort(idx[pts], kind="stable"); pts = pts[order]; pix = idx[pts]
    bornes = np.searchsorted(pix, np.arange(len(fv) + 1))
    for p in np.unique(pix):
        sel = pts[bornes[p]:bornes[p + 1]]
        fr = fv[p]
        if not np.isfinite(fr):
            continue
        if fr <= 0.02:
            out[sel] = 0.0
        elif fr >= 0.98:
            out[sel] = 1.0
        else:
            seuil = np.quantile(zr[sel], 1 - fr)      # les points les plus hauts sont enneigés
            out[sel] = (zr[sel] >= seuil).astype("float32")
    return out.reshape(z.shape)


def charger(dossier):
    p = os.path.join(dossier, "neige.png")
    if not os.path.exists(p):
        return None, None
    a = np.asarray(Image.open(p).convert("RGB")).astype(np.int32)
    return a[..., 0] / 255.0, a[..., 1] * 256 + a[..., 2]


def mettre_a_jour(dossier, grille, quand, z, image_id=None):
    """Fusionne une observation (grille 0..1 / NaN) dans le composite. Renvoie les statistiques publiées."""
    frac, heure = charger(dossier)
    h = int((quand - REF).total_seconds() // 3600)
    if frac is None or frac.shape != grille.shape:
        frac = np.zeros(grille.shape); heure = np.zeros(grille.shape, np.int32)
    vu = np.isfinite(grille)
    # même jour (UTC) : maximum ; jour plus récent : remplacement ; jour plus ancien (rattrapage) : ignoré
    meme_jour = vu & ((heure // 24) == (h // 24))
    plus_recent = vu & ((heure // 24) < (h // 24))
    nouv = np.where(meme_jour, np.maximum(frac, grille), np.where(plus_recent, grille, frac))
    heure = np.where(meme_jour, np.maximum(heure, h), np.where(plus_recent, h, heure))
    # léger lissage des bords (pixels isolés)
    nouv = ndimage.median_filter(nouv, size=3)
    r = np.clip(np.round(nouv * 255), 0, 255).astype(np.uint8)
    g, b = (heure // 256).astype(np.uint8), (heure % 256).astype(np.uint8)
    Image.fromarray(np.dstack([r, g, b]), "RGB").save(os.path.join(dossier, "neige.png"), optimize=True)
    # statistiques : surface enneigée, limite d'enneigement (altitude où la moitié du terrain est enneigée)
    connu = heure > 0
    alt_limite = None
    if (nouv[connu] > 0.5).sum() > 50:
        bins = np.arange(200, 4000, 100)
        part = [np.mean(nouv[connu & (z >= lo) & (z < lo + 100)] > 0.5) if (connu & (z >= lo) & (z < lo + 100)).sum() > 200 else np.nan
                for lo in bins]
        au_dessus = [lo for lo, p in zip(bins, part) if p == p and p >= 0.5]
        alt_limite = int(min(au_dessus)) if au_dessus else None
    j = os.path.join(dossier, "neige.json")
    meta = json.load(open(j)) if os.path.exists(j) else {}
    images = (meta.get("images") or [])[-23:] + [{"id": image_id, "date_utc": quand.isoformat(), "vu": round(float(vu.mean()), 3)}]
    meta.update({"source": "Meteosat MTG-FCI (visible 0,6 µm et 2,2 µm), composite des dernières observations sans nuage",
                 "maj_utc": quand.isoformat(), "ref_heures": REF.isoformat(), "images": images,
                 "surface_enneigee_km2": round(float((nouv > 0.5).sum() * (z.size and ((m2n.AOI[2] - m2n.AOI[0]) / z.shape[1]) ** 2) / 1e6), 1),
                 "part_observee": round(float(connu.mean()), 3), "limite_enneigement_m": alt_limite})
    json.dump(meta, open(j, "w"), ensure_ascii=False, separators=(",", ":"))
    return meta
