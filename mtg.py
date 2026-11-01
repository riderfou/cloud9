"""
Meteosat Third Generation (MTG-I1, imageur FCI) — une image toutes les 10 minutes.

Produit : FCI L1c HRFI (EO:EUM:DAT:0665) : visible 0,6 µm à 500 m et 2,2 µm à 1 km.
On ne télécharge que le(s) « chunk(s) » qui couvrent Grenoble (le n° 36 sur 40, ≈ 30-60 Mo),
pas le disque complet.

Identifiants : variables d'environnement EUMETSAT_CONSUMER_KEY et EUMETSAT_CONSUMER_SECRET
(https://api.eumetsat.int/api-key/). La recherche dans le catalogue fonctionne sans compte.

Spécificité : la géolocalisation FCI est rapportée à l'ellipsoïde (pas au relief). Vu depuis
l'orbite géostationnaire (angle zénithal ≈ 52° à Grenoble), un point à l'altitude z apparaît
décalé de ≈ 1,28 z vers le nord et 0,18 z vers l'est. On projette donc chaque point du MNT à sa
position apparente avant de l'attribuer à un pixel (voir viirs.analyse_pixels, paramètre parallaxe).

Usage :
  python3 mtg.py chercher 2026-10-31T10:00 2026-10-31T12:00     # sans compte
  python3 mtg.py analyser 2026-10-31T10:50                       # avec identifiants
"""
import os, sys, re, glob, json, shutil, datetime as dt
import numpy as np, requests
from rasterio.warp import transform as wtransform
import mer2nuages as m2n

API = "https://api.eumetsat.int"
COLLECTION = "EO:EUM:DAT:0665"           # FCI L1c HRFI, disque complet
LAT, LON = 45.2, 5.8
BBOX = (5.3, 44.85, 6.4, 45.55)           # lon/lat de la zone à lire (un peu plus large que l'AOI)
VOISIN_COUVERT = 1200.0                   # m : un pixel de bord doit toucher la nappe (voir viirs.analyse_pixels)
SAT_LON = 0.0                             # MTG-I1 au-dessus de 0°
SEUILS_MTG = {"neige_swir_max": 0.10, "nuage_swir_min": 0.20}   # canal 2,2 µm : à affiner sur cas réels


# ------------------------------------------------------------------ géométrie
def visee(lat=LAT, lon=LON, sat_lon=SAT_LON, h=35786e3, R=6378137.0):
    """Angle zénithal et azimut du satellite géostationnaire vus depuis (lat, lon)."""
    la, lo = np.radians(lat), np.radians(lon)
    p = R * np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    s = (R + h) * np.array([np.cos(np.radians(sat_lon)), np.sin(np.radians(sat_lon)), 0.0])
    d = (s - p) / np.linalg.norm(s - p)
    up = p / np.linalg.norm(p)
    east = np.array([-np.sin(lo), np.cos(lo), 0.0]); north = np.cross(up, east)
    return float(np.degrees(np.arccos(d @ up))), float(np.degrees(np.arctan2(d @ east, d @ north)) % 360)


def parallaxe_utm(lat=LAT, lon=LON):
    """Déplacement apparent (dx, dy) en mètres UTM par mètre d'altitude (convergence des méridiens incluse)."""
    vza, az = visee(lat, lon)
    t = np.tan(np.radians(vza)); a = np.radians(az)
    de, dn = -t * np.sin(a), -t * np.cos(a)            # éloignement du satellite, en m par m
    # conversion est/nord géographique -> grille UTM : on transforme un déplacement de 1000 m
    x0, y0 = wtransform("EPSG:4326", m2n.CRS, [lon], [lat])
    dlat = dn * 1000 / 111320.0; dlon = de * 1000 / (111320.0 * np.cos(np.radians(lat)))
    x1, y1 = wtransform("EPSG:4326", m2n.CRS, [lon + dlon], [lat + dlat])
    return (x1[0] - x0[0]) / 1000.0, (y1[0] - y0[0]) / 1000.0


def chunks_utiles(lat_min=BBOX[1], lat_max=BBOX[3], lon=LON):
    """N° des chunks (1 = sud, 40 = nord) qui couvrent la bande de latitude, d'après la grille FCI."""
    from satpy.area import get_area_def
    a = get_area_def("mtg_fci_fdss_1km")
    n = a.shape[0]
    out = set()
    for lat in (lat_min, lat_max):
        _, row = a.get_array_indices_from_lonlat(lon, lat)
        out.add(int((n - row) // (n / 40)) + 1)
    return sorted(range(min(out), max(out) + 1))


# ------------------------------------------------------------------ catalogue / téléchargement
def chercher(debut, fin):
    """Produits HRFI entre deux instants (UTC) : [(identifiant, début, {n° chunk: url})]. Sans compte."""
    out, start = [], 0
    while True:
        r = requests.get(f"{API}/data/search-products/1.0.0/os", timeout=60, params={
            "format": "json", "pi": COLLECTION, "si": start, "c": 100,
            "dtstart": debut.strftime("%Y-%m-%dT%H:%M:%SZ"), "dtend": fin.strftime("%Y-%m-%dT%H:%M:%SZ")}).json()
        feats = r.get("features", [])
        for f in feats:
            p = f["properties"]
            t0 = dt.datetime.fromisoformat(p["date"].split("/")[0].replace("Z", "+00:00"))
            ent = {}
            for e in p["links"].get("sip-entries", []):
                m = re.search(r"CHK-BODY.*_(\d{4})\.nc$", e["title"])
                if m: ent[int(m.group(1))] = e["href"]
            out.append((p["identifier"], t0, ent))
        start += len(feats)
        if not feats or start >= r.get("totalResults", 0):
            break
    return sorted(out, key=lambda x: x[1])


class LicenceManquante(RuntimeError):
    """Le compte EUMETSAT n'a pas accepté la licence de données requise pour la collection."""


def jeton():
    key, secret = os.environ.get("EUMETSAT_CONSUMER_KEY"), os.environ.get("EUMETSAT_CONSUMER_SECRET")
    if not key or not secret:
        raise RuntimeError("EUMETSAT_CONSUMER_KEY / EUMETSAT_CONSUMER_SECRET absents de l'environnement")
    r = requests.post(f"{API}/token", data={"grant_type": "client_credentials"}, auth=(key, secret), timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


def telecharger(url, dossier, token):
    os.makedirs(dossier, exist_ok=True)
    nom = requests.utils.unquote(url.split("name=")[-1])
    dst = os.path.join(dossier, nom)
    if not os.path.exists(dst):
        with requests.get(url, headers={"Authorization": f"Bearer {token}"}, stream=True, timeout=300) as r:
            if r.status_code == 403 and "License" in r.text:
                raise LicenceManquante(f"téléchargement refusé par EUMETSAT ({r.text.strip()[:200]}) : "
                                       "accepter la licence de données MTG sur le compte EUMETSAT")
            r.raise_for_status()
            with open(dst + ".part", "wb") as f:
                for c in r.iter_content(1 << 20): f.write(c)
        os.replace(dst + ".part", dst)
    return dst


# ------------------------------------------------------------------ lecture
def lire(fichiers, quand):
    """Lit vis_06 (500 m) et nir_22 (1 km, ré-échantillonné à 500 m) sur la zone ; renvoie le dict attendu
    par viirs.analyse_pixels (réflectances normalisées par cos(angle zénithal solaire))."""
    from satpy import Scene
    from pyorbital.astronomy import sun_zenith_angle
    scn = Scene(reader="fci_l1c_nc", filenames=fichiers)
    noms = scn.available_dataset_names()
    vis = next(n for n in ("vis_06_hr", "vis_06") if n in noms)
    swir = next(n for n in ("nir_22_hr", "nir_22") if n in noms)
    scn.load([vis, swir], calibration="reflectance")
    scn = scn.resample(scn.finest_area(), resampler="native")
    scn = scn.crop(ll_bbox=BBOX)
    lon, lat = scn[vis].attrs["area"].get_lonlats()
    sza = sun_zenith_angle(quand.replace(tzinfo=None), lon, lat)
    mu = np.cos(np.radians(np.clip(sza, 0, 85)))
    v = {"I1": np.asarray(scn[vis].values, "float32") / 100.0 / mu,
         "I3": np.asarray(scn[swir].values, "float32") / 100.0 / mu,
         "sza": sza, "lat": lat, "lon": lon}
    ok = np.isfinite(lon) & np.isfinite(lat)
    x = np.full(lon.shape, np.nan); y = np.full(lon.shape, np.nan)
    xx, yy = wtransform("EPSG:4326", m2n.CRS, lon[ok].tolist(), lat[ok].tolist())
    x[ok], y[ok] = xx, yy
    v["x"], v["y"] = x, y
    v["vza"] = np.full(lon.shape, visee()[0])
    return v


def lire_nuit(fichiers, quand):
    """Nuit : nuage bas d'après l'écart de température de brillance 10,5 - 3,8 µm (canaux à 1 km).
    Les gouttelettes d'un nuage bas émettent moins à 3,8 µm : écart de +2 à +5 K ; sol dégagé ou neige : ~0 K.
    Renvoie le dict attendu par viirs.analyse_pixels, avec la fraction nuageuse dans v["frac"]."""
    from satpy import Scene
    scn = Scene(reader="fci_l1c_nc", filenames=fichiers)
    scn.load(["ir_38", "ir_105"])
    scn = scn.crop(ll_bbox=BBOX)
    lon, lat = scn["ir_105"].attrs["area"].get_lonlats()
    btd = np.asarray(scn["ir_105"].values - scn["ir_38"].values, "float32")
    # références auto-calibrées sur l'image, comme de jour (bornées pour rester physiques)
    nuage = float(np.clip(np.nanmedian(btd[btd > 2.0]), 2.5, 6.0)) if (btd > 2.0).sum() > 100 else 3.5
    clair = float(np.clip(np.nanmedian(btd[btd < 1.2]), -1.0, 1.0)) if (btd < 1.2).sum() > 100 else 0.3
    v = {"frac": np.clip((btd - clair) / max(nuage - clair, 0.5), 0, 1), "btd": btd, "lat": lat, "lon": lon,
         "bt105": np.asarray(scn["ir_105"].values, "float32"), "refs": {"sol": clair, "nuage": nuage}}
    ok = np.isfinite(lon) & np.isfinite(lat)
    x = np.full(lon.shape, np.nan); y = np.full(lon.shape, np.nan)
    xx, yy = wtransform("EPSG:4326", m2n.CRS, lon[ok].tolist(), lat[ok].tolist())
    x[ok], y[ok] = xx, yy
    v["x"], v["y"] = x, y
    v["vza"] = np.full(lon.shape, visee()[0])
    return v


PARAMS_NUIT = dict(capteur="MTG-FCI IR 1 km (nuit)", max_dist=2000.0, min_points=1000, voisin_couvert=2000.0)


def analyser(instant, dossier=None, garder=False):
    """Analyse l'image MTG la plus proche de `instant` (datetime UTC). Renvoie (res, v, fmap, dem, est, meta)."""
    import viirs
    prods = chercher(instant - dt.timedelta(minutes=10), instant + dt.timedelta(minutes=10))
    if not prods:
        raise RuntimeError(f"aucun produit HRFI autour de {instant:%Y-%m-%d %H:%M}")
    ident, t0, ent = min(prods, key=lambda p: abs((p[1] - instant).total_seconds()))
    besoin = [c for c in chunks_utiles() if c in ent]
    if not besoin:
        raise RuntimeError("chunk(s) utile(s) absent(s) du produit")
    dossier = dossier or f"tmp_mtg_{t0:%Y%m%d_%H%M}"
    tok = jeton()
    fichiers = [telecharger(ent[c], dossier, tok) for c in besoin]
    # heure d'acquisition au-dessus de Grenoble : début du chunk (dans le nom de fichier)
    m = re.search(r"_OPE_(\d{14})_(\d{14})_", os.path.basename(fichiers[0]))
    quand = dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc) if m else t0
    try:
        v = lire(fichiers, quand)
        label = f"mtg_{quand:%Y%m%d_%H%M}"
        res, v, fmap, dem, est = viirs.analyse_pixels(
            v, label, capteur="MTG-FCI 500 m", seuils=SEUILS_MTG, max_dist=1200.0,
            parallaxe=parallaxe_utm(), min_points=300, voisin_couvert=VOISIN_COUVERT)
    finally:
        if not garder:
            shutil.rmtree(dossier, ignore_errors=True)
    meta = {"id": label, "date_utc": quand.isoformat(), "capteur": "MTG-FCI", "satellite": "MTG-I1",
            "resolution_m": 500, "produit": ident}
    return res, v, fmap, dem, est, meta


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "chercher"
    if cmd == "chercher":
        a = dt.datetime.fromisoformat(sys.argv[2]).replace(tzinfo=dt.timezone.utc)
        b = dt.datetime.fromisoformat(sys.argv[3]).replace(tzinfo=dt.timezone.utc)
        need = chunks_utiles()
        print("chunks utiles :", need, "| visée :", [round(x, 1) for x in visee()], "| parallaxe UTM :",
              [round(x, 3) for x in parallaxe_utm()])
        for ident, t0, ent in chercher(a, b):
            print(f"{t0:%Y-%m-%d %H:%M}  chunks dispo {len(ent):2d}  utiles présents : {[c for c in need if c in ent]}")
    elif cmd == "analyser":
        import viirs
        t = dt.datetime.fromisoformat(sys.argv[2]).replace(tzinfo=dt.timezone.utc)
        res, v, fmap, dem, est, meta = analyser(t, garder="--garder" in sys.argv)
        os.makedirs("out", exist_ok=True)
        viirs.figure(res, {**v, "I2": v["I1"]}, fmap, dem, est, f"out/{meta['id']}.png")
        print(json.dumps({k: x for k, x in res.items() if k != "mailles"}, ensure_ascii=False, indent=1))
