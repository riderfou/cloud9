"""
Pipeline mer2nuages : produit les données de la webapp dans web/data/.

  python3 pipeline.py statique            # relief, texture, sommets (une fois)
  python3 pipeline.py viirs AAAA/MM/JJ    # passages VIIRS du jour (≈ 11 h - 14 h UTC)
  python3 pipeline.py s2 [jours]          # scènes Sentinel-2 récentes (défaut : 5 derniers jours)
  python3 pipeline.py mtg [AAAA-MM-JJ]    # Meteosat MTG toutes les 30 min, visible le jour, infrarouge la nuit
                                          # (sans date : 6 dernières heures ; avec date : la journée UTC entière)
  python3 pipeline.py arome               # prévision AROME (Open-Meteo)
  python3 pipeline.py vent                # champ de vent AROME sur la zone (animation de la webapp)
  python3 pipeline.py tout                # viirs du jour + s2 + arome + index

À lancer toutes les 30 min entre 11 h et 15 h UTC (VIIRS) et toutes les 3 h (AROME).
"""
import sys, os, json, glob, shutil, datetime as dt, re
import numpy as np, requests
from PIL import Image
from scipy import ndimage
from rasterio.warp import transform as wtransform
import mer2nuages as m2n
import situation as sit
import neige

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "web", "data")
STEP = 5  # 5 x 20 m = grille web à 100 m
GW, GH = m2n.W // STEP, m2n.H // STEP


def down(a, reducer=np.nanmean):
    a = a[:GH * STEP, :GW * STEP].reshape(GH, STEP, GW, STEP)
    return reducer(reducer(a, axis=3), axis=1)


def write_json(name, obj):
    os.makedirs(os.path.dirname(os.path.join(OUT, name)), exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def to_lonlat(x, y):
    lo, la = wtransform(m2n.CRS, "EPSG:4326", [x], [y])
    return round(lo[0], 5), round(la[0], 5)


# ------------------------------------------------------------------ statique
SOMMETS = [  # nom, lat, lon, altitude officielle (m), type
    ("Grenoble (centre)", 45.188, 5.724, 214, "lieu"),
    ("La Bastille", 45.1985, 5.7255, 476, "lieu"),
    ("Mont Rachais", 45.2125, 5.7330, 1046, "sommet"),
    ("Néron", 45.2250, 5.7000, 1299, "sommet"),
    ("Mont Saint-Eynard", 45.2360, 5.7740, 1379, "sommet"),
    ("Le Sappey-en-Chartreuse", 45.2620, 5.7760, 1000, "lieu"),
    ("Col de Porte", 45.2920, 5.7680, 1326, "lieu"),
    ("Chamechaude", 45.2880, 5.7880, 2082, "sommet"),
    ("Charmant Som", 45.3080, 5.7280, 1867, "sommet"),
    ("Dent de Crolles", 45.3100, 5.8530, 2062, "sommet"),
    ("Saint-Hilaire-du-Touvet", 45.3050, 5.8870, 1000, "lieu"),
    ("Mont Granier", 45.4658, 5.9381, 1933, "sommet"),
    ("Saint-Nizier-du-Moucherotte", 45.1670, 5.6330, 1168, "lieu"),
    ("Moucherotte", 45.1500, 5.6300, 1901, "sommet"),
    ("Lans-en-Vercors", 45.1280, 5.5880, 1020, "lieu"),
    ("Pic Saint-Michel", 45.0919, 5.6061, 1966, "sommet"),
    ("Uriage", 45.1430, 5.8280, 414, "lieu"),
    ("Croix de Chamrousse", 45.1240, 5.8890, 2253, "sommet"),
    ("Grand Colon", 45.1410, 5.9570, 2394, "sommet"),
    ("Croix de Belledonne", 45.1825, 5.9997, 2926, "sommet"),
    ("Prapoutel (7 Laux)", 45.2550, 5.9900, 1400, "lieu"),
    # marges de la zone élargie (+10 km)
    ("Chambéry", 45.5646, 5.9178, 270, "lieu"),
    ("Voiron", 45.3640, 5.5890, 290, "lieu"),
    ("Villard-de-Lans", 45.0710, 5.5530, 1040, "lieu"),
    ("Vizille", 45.0780, 5.7710, 280, "lieu"),
    ("Allevard", 45.3940, 6.0750, 475, "lieu"),
    ("Le Bourg-d'Oisans", 45.0550, 6.0310, 720, "lieu"),
    ("Le Grand Som", 45.3700, 5.7770, 2026, "sommet"),
    ("Le Taillefer", 45.0480, 5.9520, 2857, "sommet"),
]


def statique():
    os.makedirs(OUT, exist_ok=True)
    dem = m2n.load_dem()
    # relief à 100 m, encodage "terrarium" (R*256 + G + B/256 - 32768)
    z = down(dem)
    z = np.where(np.isfinite(z), z, 0) + 32768.0
    rgb = np.dstack([np.floor(z / 256), np.floor(z % 256), np.floor((z % 1) * 256)]).astype(np.uint8)
    Image.fromarray(rgb).save(os.path.join(OUT, "relief.png"))
    # texture : Sentinel-2 couleurs naturelles d'une journée dégagée, 30 m
    import rasterio
    from rasterio.windows import from_bounds
    from rasterio.enums import Resampling
    scene = "S2C_31TGL_20260722_0_L2A"   # 22/07/2026 : sans nuages, sans neige saisonnière (seuls les glaciers)
    tw, th = m2n.W * 2 // 3, m2n.H * 2 // 3
    a = m2n.lire_s2(scene, "TCI.tif", bandes=3, out_shape=(th, tw))   # mosaïque des tuiles du même passage
    a = np.moveaxis(a, 0, -1).astype("float32")
    a = np.clip((a / 255.0) ** 0.85 * 1.15, 0, 1) * 255
    Image.fromarray(a.astype(np.uint8)).save(os.path.join(OUT, "texture.jpg"), quality=82)
    # sommets : position recalée sur le point le plus haut du MNT à moins de 300 m
    out = []
    for nom, la, lo, alt, typ in SOMMETS:
        x, y = wtransform("EPSG:4326", m2n.CRS, [lo], [la]); x, y = x[0], y[0]
        j, i = int((x - m2n.AOI[0]) / m2n.RES), int((m2n.AOI[3] - y) / m2n.RES)
        if not (0 <= i < m2n.H and 0 <= j < m2n.W):
            continue
        if typ == "sommet":
            # maximum local (600 m) dont l'altitude MNT colle à l'altitude officielle, le plus proche (< 5 km)
            r = 250
            i0, j0 = max(i - r, 0), max(j - r, 0)
            win = dem[i0:i + r, j0:j + r]
            loc = (win == ndimage.maximum_filter(np.nan_to_num(win, nan=-1), size=31)) & (np.abs(win - alt) < 80)
            ci, cj = np.where(loc)
            if len(ci):
                k = np.argmin((ci + i0 - i) ** 2 + (cj + j0 - j) ** 2)
                i, j = ci[k] + i0, cj[k] + j0
        zdem = float(dem[i, j])
        out.append({"nom": nom, "type": typ, "alt": alt, "alt_mnt": round(zdem),
                    "x": m2n.AOI[0] + (j + .5) * m2n.RES, "y": m2n.AOI[3] - (i + .5) * m2n.RES})
        if abs(zdem - alt) > 100:
            print(f"  ⚠ {nom}: altitude MNT {zdem:.0f} m vs officielle {alt} m")
    write_json("sommets.json", out)
    write_json("meta.json", {"crs": m2n.CRS, "aoi": m2n.AOI, "grille_web": [GW, GH], "pas_m": m2n.RES * STEP,
                             "texture": {"scene": scene}, "relief": "Copernicus DEM GLO-30"})
    print("statique OK", GW, GH, len(out), "lieux")


# ------------------------------------------------------------------ analyses
def save_analysis(res, frac20, meta):
    """frac20 : fraction nuageuse (0..1) sur la grille 20 m."""
    aid = meta["id"]
    f = down(frac20.astype("float32"))
    alpha = (np.clip(np.nan_to_num(f), 0, 1) * 255).astype(np.uint8)
    Image.fromarray(alpha, "L").save(os.path.join(OUT, "analyses", f"{aid}.png"), optimize=True)
    mailles = [{"x": g["x"], "y": g["y"], "h": round(g["h"]), "n": g["n"]} for g in res.get("mailles", [])]
    rec = {**meta,
           "detectee": res["mer_de_nuages_detectee"],
           "sommet_m": None if res.get("sommet_estime_m") is None else round(res["sommet_estime_m"]),
           "incertitude_m": None if res.get("incertitude_m") is None else round(res["incertitude_m"]),
           "quantiles": [None if (q != q) else round(q) for q in res["h_bords_quantiles_10_25_50_75_90"]],
           "n_bords": res["n_pixels_bord"], "mailles": mailles, "masque": f"analyses/{aid}.png"}
    for k in ("remplissage_sous_H", "inclinaison", "angle_zenithal_satellite"):
        if res.get(k) is not None:
            rec[k] = res[k]
    if rec["sommet_m"] is None and rec["quantiles"][2] is not None:
        rec["sommet_brut_m"] = rec["quantiles"][2]       # médiane des bords, même si non détectée
    classer(rec, f, relief_web())
    write_json(f"analyses/{aid}.json", rec)
    print(f"  {aid}: {rec['situation']} sommet={rec['sommet_m']} ± {rec['incertitude_m']} {rec['metriques']}")
    return rec


_RELIEF = None
def relief_web():
    """Altitude sur la grille de la webapp (celle des masques), décodée de relief.png."""
    global _RELIEF
    if _RELIEF is None:
        r = np.asarray(Image.open(os.path.join(OUT, "relief.png")).convert("RGB")).astype(float)
        _RELIEF = r[..., 0] * 256 + r[..., 1] + r[..., 2] / 256 - 32768
    return _RELIEF


def classer(rec, frac, z):
    """Ajoute à une analyse sa situation (mer, dégradée, disloquée, couvert, dégagé) et ses métriques.
    `detectee` ne reste vrai que si l'altitude du sommet a un sens (situations sit.VALIDES)."""
    if "detectee_brute" not in rec:
        rec["detectee_brute"] = rec["detectee"]
    h = rec["sommet_m"] if rec["sommet_m"] is not None else rec.get("sommet_brut_m")
    if rec.get("emprise"):     # analyse faite sur une zone plus petite (avant l'élargissement) : métriques sur cette zone
        e = rec["emprise"]; pas = m2n.RES * STEP
        c0, c1 = int((e[0] - m2n.AOI[0]) / pas), int((e[2] - m2n.AOI[0]) / pas)
        r0, r1 = int((m2n.AOI[3] - e[3]) / pas), int((m2n.AOI[3] - e[1]) / pas)
        frac, z = frac[r0:r1, c0:c1], z[r0:r1, c0:c1]
    m = sit.metriques_masque(frac, z, h)
    rec["metriques"] = {k: (None if v is None else round(v, 3)) for k, v in m.items()}
    rec["situation"] = sit.classer_image(m, rec["detectee_brute"], h)
    rec["detectee"] = rec["situation"] in sit.VALIDES
    if rec["detectee"] and rec["sommet_m"] is None:      # cas rare : non détectée à l'origine
        rec["detectee"] = False
    return rec


def reclasser():
    """Recalcule la situation de toutes les analyses déjà publiées, à partir de leur masque."""
    for f in sorted(glob.glob(os.path.join(OUT, "analyses", "*.json"))):
        rec = json.load(open(f))
        if rec.get("sommet_m") is None and rec.get("sommet_brut_m") is None and rec["quantiles"][2] is not None:
            rec["sommet_brut_m"] = rec["quantiles"][2]
        frac = np.asarray(Image.open(os.path.join(OUT, rec["masque"])).convert("L")).astype(float) / 255
        classer(rec, frac, relief_web())
        write_json(os.path.relpath(f, OUT), rec)
        print(f"  {rec['id']:30s} {rec['situation']:11s} H={rec['sommet_m'] or rec.get('sommet_brut_m')} {rec['metriques']}")


def run_viirs(date):
    import viirs, viirs_find
    os.makedirs(os.path.join(OUT, "analyses"), exist_ok=True)
    for bucket, key, dist in viirs_find.find(date):
        tag = key.split("_")[3]
        sat = viirs_find.BUCKETS[bucket]
        d = key.split("_")[2][1:]
        aid = f"viirs_{sat.lower().replace('-', '')}_{d}_{tag[1:5]}"
        if os.path.exists(os.path.join(OUT, "analyses", f"{aid}.json")):
            continue
        tmp = os.path.join(ROOT, "tmp_" + aid)
        os.system(f"python3 {ROOT}/viirs_fetch.py {bucket} {date} {tag} {tmp} > /dev/null")
        try:
            res, v, fmap, dem, est = viirs.analyse(tmp, tag, aid)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        t = dt.datetime.strptime(d + tag[1:7], "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)
        save_analysis(res, np.nan_to_num(fmap), {"id": aid, "date_utc": t.isoformat(), "capteur": "VIIRS",
                                                  "satellite": sat, "resolution_m": 375})


def run_s2(days=5):
    os.makedirs(os.path.join(OUT, "analyses"), exist_ok=True)
    today = dt.date.today()
    months = sorted({(today - dt.timedelta(d)).strftime("%Y/%-m") for d in range(days + 1)})
    for ym in months:
        x = requests.get(f"https://sentinel-cogs.s3.us-west-2.amazonaws.com/?list-type=2&prefix=sentinel-s2-l2a-cogs/31/T/GL/{ym}/&delimiter=/").text
        for scene in re.findall(r"(S2[ABC]_31TGL_\d{8}_\d_L2A)/</Prefix>", x):
            d = dt.datetime.strptime(scene.split("_")[2], "%Y%m%d").date()
            if (today - d).days > days:
                continue
            aid = f"s2_{scene.split('_')[2]}_{scene[:3].lower()}{scene.split('_')[3]}"
            if os.path.exists(os.path.join(OUT, "analyses", f"{aid}.json")):
                continue
            meta_url = f"{m2n.S2}/{ym}/{scene}/{scene}.json"
            try:
                when = requests.get(meta_url, timeout=30).json()["properties"]["datetime"]
            except Exception:
                when = d.isoformat() + "T10:50:00Z"
            try:
                res, cloud, acc, hs = m2n.estimate(scene, m2n.load_dem())
            except Exception as e:
                print("  échec", scene, e); continue
            save_analysis(res, cloud.astype("float32"), {"id": aid, "date_utc": when.replace("Z", "+00:00"),
                                                          "capteur": "Sentinel-2", "satellite": scene[:3],
                                                          "resolution_m": 20})


def run_mtg(debut=None, fin=None, pas_min=30, max_images=16, heures=6):
    """Analyse les images MTG (une toutes les `pas_min` minutes) pas encore traitées, de jour (visible)
    comme de nuit (infrarouge). Par défaut : les `heures` dernières heures, les plus récentes d'abord."""
    import mtg
    if not (os.environ.get("EUMETSAT_CONSUMER_KEY") and os.environ.get("EUMETSAT_CONSUMER_SECRET")):
        print("MTG : identifiants EUMETSAT absents, étape ignorée"); return
    os.makedirs(os.path.join(OUT, "analyses"), exist_ok=True)
    maintenant = dt.datetime.now(dt.timezone.utc)
    fin = min(fin or maintenant, maintenant - dt.timedelta(minutes=20))
    debut = debut or fin - dt.timedelta(hours=heures)
    fait = 0
    for ident, t0, ent in sorted(mtg.chercher(debut, fin), key=lambda p: p[1], reverse=True):
        if t0.minute % pas_min or fait >= max_images:
            continue
        if mtg.methode(t0 + dt.timedelta(minutes=8)) is None:      # aube / crépuscule
            continue
        if glob.glob(os.path.join(OUT, "analyses", f"mtg_{t0:%Y%m%d_%H}{t0.minute // 10}*.json")):
            continue
        try:
            res, v, fmap, dem, est, meta = mtg.analyser(t0 + dt.timedelta(minutes=1))
        except mtg.LicenceManquante as e:
            print(f"  MTG : {e}"); return
        except Exception as e:
            print(f"  MTG {t0:%H:%M} : échec ({e})"); continue
        save_analysis(res, np.nan_to_num(fmap), meta)
        fait += 1
        quand = dt.datetime.fromisoformat(meta["date_utc"])
        if meta["capteur"] == "MTG-FCI" and neige.proche_midi(quand):      # jour, près du midi solaire
            try:
                n = neige.mettre_a_jour(OUT, neige.vers_grille(v, neige.fraction_pixels(v), relief_web(), mtg.parallaxe_utm()),
                                        quand, relief_web(), meta["id"])
                print(f"  neige : {n['surface_enneigee_km2']} km², limite ~{n['limite_enneigement_m']} m, zone observée {n['part_observee']:.0%}")
            except Exception as e:
                print(f"  neige : échec ({e})")


# ------------------------------------------------------------------ neige Sentinel-2 (Theia LIS)
def _lire_fsc(tif):
    """Fraction enneigée LIS (0-100 %, 205 nuage, 255 sans donnée) moyennée sur la grille web (100 m) : 0..1 / NaN."""
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    with rasterio.open(tif) as s:
        a = s.read(1).astype("float32")
        a[(a > 100)] = np.nan
        out = np.full((GH, GW), np.nan, "float32")
        reproject(a, out, src_transform=s.transform, src_crs=s.crs, src_nodata=np.nan,
                  dst_transform=from_origin(m2n.AOI[0], m2n.AOI[3], m2n.RES * STEP, m2n.RES * STEP), dst_crs=m2n.CRS,
                  dst_nodata=np.nan, resampling=Resampling.average)
    return out / 100.0


def run_lis(jours=10, intervalle_h=6, forcer=False):
    """Fraction enneigée Sentinel-2 à 20 m (Theia LIS FSC, collection LIS_FSC_PREOP sur hydroweb.next), fusionnée
    dans le composite de neige. Requête au plus toutes les `intervalle_h` heures, sur la zone et les derniers jours."""
    import zipfile, tempfile
    if not os.environ.get("HYDROWEB_API_KEY"):
        print("LIS : HYDROWEB_API_KEY absente, étape ignorée"); return
    import py_hydroweb
    jn = os.path.join(OUT, "neige.json")
    meta = json.load(open(jn)) if os.path.exists(jn) else {}
    maintenant = dt.datetime.now(dt.timezone.utc)
    if not forcer and meta.get("lis_verifie_utc") and maintenant - dt.datetime.fromisoformat(meta["lis_verifie_utc"]) < dt.timedelta(hours=intervalle_h):
        print("LIS : vérifié récemment, étape ignorée"); return
    deja = set(meta.get("lis_produits", []))
    lo, la = wtransform(m2n.CRS, "EPSG:4326", [m2n.AOI[0], m2n.AOI[2], m2n.AOI[0], m2n.AOI[2]], [m2n.AOI[1], m2n.AOI[1], m2n.AOI[3], m2n.AOI[3]])
    bbox = [round(min(lo), 4), round(min(la), 4), round(max(lo), 4), round(max(la), 4)]
    debut = maintenant - dt.timedelta(days=jours)
    client = py_hydroweb.Client("https://hydroweb.next.theia-land.fr/api")
    panier = py_hydroweb.DownloadBasket(f"mer2nuages_lis_{maintenant:%Y%m%dT%H%M}")
    panier.add_collection(collection_id="LIS_FSC_PREOP", bbox=bbox,
                          datetime=f"{debut:%Y-%m-%dT00:00:00Z}/{maintenant:%Y-%m-%dT%H:%M:%SZ}")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            zp = client.submit_and_download_zip(panier, zip_filename="lis.zip", output_folder=tmp)
        except Exception as e:
            print(f"LIS : échec de la requête ({type(e).__name__}: {str(e)[:300]})"); return
        with zipfile.ZipFile(zp) as z:
            noms = z.namelist()
            print(f"LIS : archive {os.path.getsize(zp) // 1_000_000} Mo, {len(noms)} fichiers ; exemples :", noms[:12])
            z.extractall(tmp)
        tifs = [os.path.join(tmp, n) for n in noms if n.lower().endswith((".tif", ".tiff"))]
        # fraction « au sol » (corrigée de la forêt) si elle existe, sinon « vue du dessus »
        fsc = [t for t in tifs if "FSCOG" in os.path.basename(t).upper()] or [t for t in tifs if "FSCTOC" in os.path.basename(t).upper()] \
              or [t for t in tifs if "FSC" in os.path.basename(t).upper()]
        print(f"LIS : {len(tifs)} GeoTIFF, {len(fsc)} de fraction enneigée")
        produits = []
        for t in fsc:
            nom = os.path.basename(t)
            m = re.search(r"(20\d{6})T?(\d{6})?", nom)
            if not m:
                print("  LIS : date introuvable dans", nom); continue
            quand = dt.datetime.strptime(m.group(1) + (m.group(2) or "103000"), "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)
            produits.append((quand, nom, t))
        relief = relief_web()
        for quand, nom, t in sorted(produits):
            if nom in deja:
                continue
            try:
                g = _lire_fsc(t)
            except Exception as e:
                print(f"  LIS : {nom} illisible ({e})"); continue
            if np.isfinite(g).sum() < 100:
                deja.add(nom); continue           # tuile hors zone ou entièrement nuageuse
            n = neige.mettre_a_jour(OUT, g, quand, relief, nom, source="lis")
            deja.add(nom)
            print(f"  LIS {quand:%d/%m %H:%M} {nom} : {np.isfinite(g).mean():.0%} de la zone vue, "
                  f"{np.nanmean(g > 0.5):.1%} enneigé ; composite {n['surface_enneigee_km2']} km², limite ~{n['limite_enneigement_m']} m")
    meta = json.load(open(jn)) if os.path.exists(jn) else {}
    meta["lis_verifie_utc"] = maintenant.isoformat(timespec="minutes")
    meta["lis_produits"] = sorted(deja)[-200:]
    write_json("neige.json", meta)


# ------------------------------------------------------------------ observations Météo-France
MF = "https://public-api.meteofrance.fr/public"


def _mf_get(chemin, key, **params):
    r = requests.get(f"{MF}/{chemin}", headers={"apikey": key, "accept": "*/*"}, params=params, timeout=60)
    return r


def run_obs_mf(jours=7, max_requetes=280):
    """Observations horaires des stations Météo-France de la zone (API DPObs v2, station par station) -> obs_mf.json.
    À chaque passage : dernière observation de chaque station, plus les heures manquantes des dernières 24 h
    (rattrapage), dans la limite de `max_requetes` (quota de l'API : ~50 requêtes / min). Historique : `jours` jours."""
    import csv, io, time
    key = os.environ.get("MF_OBS_API_KEY")
    if not key:
        print("Obs MF : MF_OBS_API_KEY absente, étape ignorée"); return
    dst = os.path.join(OUT, "obs_mf.json")
    base = json.load(open(dst)) if os.path.exists(dst) else {"stations": {}, "mesures": {}}
    r = _mf_get("DPObs/v2/liste-stations", key)
    if not r.ok:
        print("Obs MF : liste-stations", r.status_code, r.text[:200]); return
    for row in csv.DictReader(io.StringIO(r.text), delimiter=";"):
        try:
            la, lo = float(row["Latitude"]), float(row["Longitude"])
        except (KeyError, ValueError):
            continue
        x, y = wtransform("EPSG:4326", m2n.CRS, [lo], [la]); x, y = x[0], y[0]
        if m2n.AOI[0] <= x <= m2n.AOI[2] and m2n.AOI[1] <= y <= m2n.AOI[3]:
            sid = row["Id_station"]
            base["stations"][sid] = {"id": sid, "nom": row.get("Nom_usuel", sid).title(), "lat": la, "lon": lo,
                                     "x": round(x, 1), "y": round(y, 1), "alt": int(float(row.get("Altitude") or 0)),
                                     "pack": row.get("Pack")}
    print(f"Obs MF : {len(base['stations'])} stations dans la zone")
    n_req, t_req = 0, [0.0]

    def appel(sid, quand=None):
        nonlocal n_req
        attente = 1.3 - (time.time() - t_req[0])
        if attente > 0: time.sleep(attente)
        t_req[0] = time.time(); n_req += 1
        p = {"id_station": sid, "format": "json"}
        if quand: p["date"] = quand.strftime("%Y-%m-%dT%H:00:00Z")
        return _mf_get("DPObs/v2/station/horaire", key, **p)

    def ajouter(sid, lignes):
        serie = base["mesures"].setdefault(sid, []); deja = {x["t"] for x in serie}; n = 0
        for o in (lignes if isinstance(lignes, list) else [lignes]):
            t = o.get("validity_time")
            if not t or t in deja: continue
            T, Td = o.get("t"), o.get("td")
            serie.append({"t": t, "T": None if T is None else round(T - 273.15, 1), "Td": None if Td is None else round(Td - 273.15, 1),
                          "U": o.get("u"), "vv": o.get("vv"), "n": o.get("n"), "ff": o.get("ff"), "dd": o.get("dd"),
                          "rr1": o.get("rr1"), "insolh": o.get("insolh")})
            deja.add(t); n += 1
        return n

    n_new, maintenant = 0, dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    premier = True
    for sid in sorted(base["stations"]):
        r = appel(sid)
        if premier:
            print(f"Obs MF : station/horaire {sid} -> {r.status_code} {r.headers.get('content-type')} {r.text[:300]}")
            premier = False
        if not r.ok:
            if r.status_code in (401, 403, 404): print(f"Obs MF : {sid} {r.status_code}"); continue
            continue
        try: n_new += ajouter(sid, r.json())
        except ValueError: pass
    # rattrapage des heures manquantes (24 h), les plus récentes d'abord
    for h in range(1, 25):
        quand = maintenant - dt.timedelta(hours=h); cle = quand.strftime("%Y-%m-%dT%H:00:00")
        for sid in sorted(base["stations"]):
            if n_req >= max_requetes: break
            if any(x["t"].startswith(cle) for x in base["mesures"].get(sid, [])): continue
            r = appel(sid, quand)
            if r.ok:
                try: n_new += ajouter(sid, r.json())
                except ValueError: pass
        if n_req >= max_requetes:
            print(f"Obs MF : limite de {max_requetes} requêtes atteinte, rattrapage poursuivi au prochain passage"); break
    limite = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=jours)).strftime("%Y-%m-%dT%H:%M:%S")
    for sid in list(base["mesures"]):
        base["mesures"][sid] = sorted((x for x in base["mesures"][sid] if x["t"] >= limite), key=lambda x: x["t"])
    base["maj_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    base["source"] = "Météo-France, données publiques d'observation (DPObs v2)"
    write_json("obs_mf.json", base)
    print(f"Obs MF OK : {len(base['stations'])} stations, {n_new} nouvelles mesures, {n_req} requêtes")


# ------------------------------------------------------------------ webcams (Windy)
WINDY = "https://api.windy.com/webcams/api/v3/webcams"


CORRECTIONS_WEBCAMS = os.path.join(ROOT, "webcams_corrections.json")


def corriger_webcams(cams):
    """Applique webcams_corrections.json : beaucoup de webcams de stations sont déclarées dans Windy à la
    position du village, pas de la caméra. Par identifiant Windy : "alt" (m) et/ou "lat"/"lon" corrigés.
    Champs produits : x, y, lat, lon, alt_mnt (relief à la position retenue), alt (altitude retenue), corrige."""
    try:
        table = {k: v for k, v in json.load(open(CORRECTIONS_WEBCAMS)).items() if not k.startswith("_")}
    except FileNotFoundError:
        table = {}
    dem = m2n.load_dem()
    out = []
    for c in cams:
        c = dict(c)
        la, lo = c.get("lat_windy", c.get("lat")), c.get("lon_windy", c.get("lon"))
        c["lat_windy"], c["lon_windy"] = la, lo
        corr = table.get(str(c["id"])) or {}
        if "lat" in corr and "lon" in corr:
            la, lo = corr["lat"], corr["lon"]
        x, y = wtransform("EPSG:4326", m2n.CRS, [lo], [la]); x, y = x[0], y[0]
        j, i = int((x - m2n.AOI[0]) / m2n.RES), int((m2n.AOI[3] - y) / m2n.RES)
        if not (0 <= i < m2n.H and 0 <= j < m2n.W) or not np.isfinite(dem[i, j]):
            continue
        c.update({"lat": la, "lon": lo, "x": round(x, 1), "y": round(y, 1), "alt_mnt": round(float(dem[i, j]))})
        c["alt"] = int(corr["alt"]) if "alt" in corr else c["alt_mnt"]
        c["corrige"] = {k: corr[k] for k in ("alt", "lat", "lon", "note") if k in corr} or None
        out.append(c)
    n = sum(1 for c in out if c["corrige"])
    if table:
        print(f"Webcams : {n} corrigée(s) sur {len(table)} correction(s) dans {os.path.basename(CORRECTIONS_WEBCAMS)}")
    return sorted(out, key=lambda c: -c["alt"])


def run_webcams(lat=45.27, lon=5.94, rayon_km=60, age_max_h=12):
    """Liste des webcams Windy dans la zone -> webcams.json (position, altitude MNT, lecteur intégrable).
    Les URL d'images de l'offre gratuite expirent au bout de quelques minutes : on ne garde que le
    lecteur Windy (iframe public, sans clé) et le lien vers la page de la webcam."""
    dst = os.path.join(OUT, "webcams.json")
    key = os.environ.get("WINDY_WEBCAMS_API_KEY")
    recente = False
    if os.path.exists(dst):
        try:
            maj = dt.datetime.fromisoformat(json.load(open(dst))["maj_utc"])
            recente = dt.datetime.now(dt.timezone.utc) - maj < dt.timedelta(hours=age_max_h)
        except Exception:
            pass
    if recente or not key:
        # pas de nouvelle requête : on réapplique seulement les corrections (fichier peut-être modifié)
        if os.path.exists(dst):
            d = json.load(open(dst))
            d["webcams"] = corriger_webcams(d["webcams"])
            write_json("webcams.json", d)
        print("Webcams :", "liste récente" if recente else "WINDY_WEBCAMS_API_KEY absente", "- corrections réappliquées"); return
    brut, offset = [], 0
    while True:
        r = requests.get(WINDY, headers={"x-windy-api-key": key}, timeout=60, params={
            "nearby": f"{lat},{lon},{rayon_km}", "limit": 50, "offset": offset, "lang": "fr",
            "include": "categories,location,player,urls"})
        if r.status_code != 200:
            print(f"Webcams : erreur HTTP {r.status_code} {r.text[:300]}"); return
        d = r.json()
        lot = d.get("webcams", [])
        brut += lot; offset += len(lot)
        if not lot or offset >= d.get("total", 0) or offset >= 500:
            break
    if brut:   # trace de la structure reçue (sans la clé), pour vérifier le format dans le journal
        w = brut[0]
        print("Webcams : total", len(brut), "| champs", sorted(w), "| location", sorted(w.get("location", {})),
              "| player", sorted((w.get("player") or {})), "| urls", sorted((w.get("urls") or {})))
    dem = m2n.load_dem()
    out = []
    for w in brut:
        loc = w.get("location") or {}
        la, lo = loc.get("latitude"), loc.get("longitude")
        if la is None or lo is None or w.get("status", "active") != "active":
            continue
        x, y = wtransform("EPSG:4326", m2n.CRS, [lo], [la]); x, y = x[0], y[0]
        j, i = int((x - m2n.AOI[0]) / m2n.RES), int((m2n.AOI[3] - y) / m2n.RES)
        if not (0 <= i < m2n.H and 0 <= j < m2n.W) or not np.isfinite(dem[i, j]):
            continue
        player = w.get("player") or {}
        lecteur = player.get("day") or player.get("live") or player.get("month")
        if isinstance(lecteur, dict):      # selon les versions : {"embed": url, ...} ou directement l'URL
            lecteur = lecteur.get("embed") or lecteur.get("link")
        urls = w.get("urls") or {}
        wid = w.get("webcamId", w.get("id"))
        out.append({"id": wid, "titre": w.get("title", ""), "ville": loc.get("city"),
                    "x": round(x, 1), "y": round(y, 1), "lat_windy": la, "lon_windy": lo, "alt_mnt": round(float(dem[i, j])),
                    "lecteur": lecteur, "lien": urls.get("detail") or (f"https://www.windy.com/webcams/{wid}" if wid else None),
                    "maj": w.get("lastUpdatedOn")})
    out = corriger_webcams(out)
    write_json("webcams.json", {"source": "Windy.com Webcams", "maj_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                                "webcams": out})
    print(f"Webcams OK : {len(out)} dans la zone (sur {len(brut)} à moins de {rayon_km} km)")


# ------------------------------------------------------------------ AROME
NIVEAUX = [1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 700, 650, 600]
# variables hors profil, et leur nom dans arome.json
SURFACE = {"temperature_2m": "t2m", "relative_humidity_2m": "rh2m", "cloud_cover_low": "nuages_bas",
           "cloud_cover_mid": "nuages_moyens", "cloud_cover_high": "nuages_hauts", "precipitation": "pluie",
           "wind_speed_850hPa": "vent850", "wind_direction_850hPa": "dir850", "wind_speed_700hPa": "vent700"}


def sommet_arome(z, rh, t, seuil=80.0, base_max=2000.0):
    """Sommet de la couche humide de basse couche : altitude où l'humidité relative repasse sous `seuil`
    en montant, au-dessus de la première couche humide trouvée sous `base_max`. La base peut être au-dessus
    du fond de vallée (stratus décollé, fond de vallée asséché l'après-midi). None s'il n'y a pas de couche
    humide en basse couche, ou si l'humidité reste élevée trop haut (couvert, pas une mer de nuages)."""
    ok = [k for k in range(len(z)) if z[k] is not None and rh[k] is not None and z[k] > 230]
    z = [z[k] for k in ok]; rh = [rh[k] for k in ok]
    if len(z) < 3:
        return None
    base = next((k for k in range(len(z)) if rh[k] >= seuil and z[k] < base_max), None)
    if base is None:
        return None
    for k in range(base + 1, len(z)):
        if rh[k] < seuil:
            h = z[k - 1] + (rh[k - 1] - seuil) / (rh[k - 1] - rh[k]) * (z[k] - z[k - 1])
            return round(h) if h < 3000 else None
    return None


def diagnostiquer_air(heures):
    """Ajoute à chaque heure le diagnostic de masse d'air (stabilité, vent, pluie) : favorable / limite / défavorable."""
    for hh in heures:
        hh["air"] = sit.masse_air(hh["profil"], hh.get("vent850"), hh.get("dir850"), hh.get("vent700"), hh.get("pluie"))


def lisser(heures):
    """Médiane glissante sur 3 h (l'heuristique heure par heure est bruitée)."""
    vals = [hh["sommet_m"] for hh in heures]
    for i, hh in enumerate(heures):
        w = [v for v in vals[max(i - 1, 0):i + 2] if v is not None]
        hh["sommet_lisse_m"] = round(float(np.median(w))) if len(w) >= 2 else None


def run_arome(lat=45.25, lon=5.85):
    var = []
    for p in NIVEAUX:
        var += [f"temperature_{p}hPa", f"relative_humidity_{p}hPa", f"geopotential_height_{p}hPa"]
    def appel(variables):
        return requests.get("https://api.open-meteo.com/v1/meteofrance", timeout=60, params={
            "latitude": lat, "longitude": lon, "hourly": ",".join(variables),
            "past_days": 1, "forecast_days": 2, "timezone": "UTC"}).json()
    r = appel(var + list(SURFACE))
    if "hourly" not in r:   # une variable refusée ? on retente avec le strict nécessaire (profil)
        print("AROME : requête complète refusée :", r.get("reason", r))
        r = appel(var + ["temperature_2m", "relative_humidity_2m", "cloud_cover_low"])
    if "hourly" not in r:  # quota dépassé, panne... : on garde le fichier précédent
        print("AROME indisponible :", r.get("reason", r)); return
    h = r["hourly"]
    niveaux = [p for p in NIVEAUX if any(v is not None for v in h.get(f"geopotential_height_{p}hPa", []))
               and any(v is not None for v in h.get(f"relative_humidity_{p}hPa", []))]
    heures = []
    for i, t in enumerate(h["time"]):
        z = [h[f"geopotential_height_{p}hPa"][i] for p in niveaux]
        rh = [h[f"relative_humidity_{p}hPa"][i] for p in niveaux]
        tt = [h[f"temperature_{p}hPa"][i] for p in niveaux]
        heures.append({"t": t + ":00+00:00", "sommet_m": sommet_arome(z, rh, tt),
                       "profil": [{"p": p, "z": zz, "rh": r_, "T": t_} for p, zz, r_, t_ in zip(niveaux, z, rh, tt)
                                  if zz is not None and r_ is not None and t_ is not None],
                       **{nom: h[var][i] for var, nom in SURFACE.items() if var in h}})
    lisser(heures)
    diagnostiquer_air(heures)
    write_json("arome.json", {"source": "AROME / ARPEGE Météo-France via Open-Meteo", "lat": lat, "lon": lon,
                              "maj_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                              "seuil_humidite": 80, "heures": heures})
    print("AROME OK", len(heures), "heures, niveaux", niveaux)


# ------------------------------------------------------------------ vent (champ AROME sur la zone)
VENT_NIVEAUX = {"sol": "10m", "1500m": "850hPa"}   # nom dans vent.json -> suffixe Open-Meteo


def run_vent(nx=11, ny=11):
    """Champ de vent AROME sur une grille régulière nx × ny de la zone (UTM), pour l'animation de particules
    de la webapp : composantes u (vers l'est) et v (vers le nord) en m/s, heure par heure, à 10 m et à 850 hPa.
    Une requête Open-Meteo multi-points (compte pour nx × ny appels dans le quota quotidien)."""
    X0, Y0, X1, Y1 = m2n.AOI
    xs = [X0 + (X1 - X0) * (j + .5) / nx for j in range(nx)]
    ys = [Y0 + (Y1 - Y0) * (i + .5) / ny for i in range(ny)]          # du sud au nord
    gx, gy = [x for y in ys for x in xs], [y for y in ys for x in xs]  # ligne par ligne, du sud au nord
    lon, lat = wtransform(m2n.CRS, "EPSG:4326", gx, gy)

    def appel(niveaux):
        var = [f"wind_{g}_{s}" for s in niveaux.values() for g in ("speed", "direction")]
        r = requests.get("https://api.open-meteo.com/v1/meteofrance", timeout=90, params={
            "latitude": ",".join(f"{v:.4f}" for v in lat), "longitude": ",".join(f"{v:.4f}" for v in lon),
            "hourly": ",".join(var), "wind_speed_unit": "ms", "past_days": 0, "forecast_days": 2,
            "timezone": "UTC"}).json()
        return r if isinstance(r, list) else [r] if "hourly" in r else r
    niveaux = dict(VENT_NIVEAUX)
    r = appel(niveaux)
    if not isinstance(r, list):   # niveau d'altitude refusé ? on garde le vent à 10 m
        print("Vent : requête complète refusée :", r.get("reason", r))
        niveaux = {"sol": "10m"}; r = appel(niveaux)
    if not isinstance(r, list) or len(r) != nx * ny:
        print("Vent indisponible :", r.get("reason", r) if isinstance(r, dict) else f"{len(r)} points"); return
    temps = r[0]["hourly"]["time"]
    out = {}
    for nom, s in niveaux.items():
        U, V = [], []
        for k in range(len(temps)):
            u, v = [], []
            for p in r:
                f, d = p["hourly"].get(f"wind_speed_{s}", [None])[k], p["hourly"].get(f"wind_direction_{s}", [None])[k]
                if f is None or d is None:
                    u.append(None); v.append(None); continue
                a = np.radians(d)              # direction d'où vient le vent
                u.append(round(float(-f * np.sin(a)), 1)); v.append(round(float(-f * np.cos(a)), 1))
            U.append(u); V.append(v)
        if any(x is not None for row in U for x in row):
            out[nom] = {"u": U, "v": V}
    if not out:
        print("Vent : aucune valeur"); return
    write_json("vent.json", {"source": "AROME Météo-France via Open-Meteo", "unite": "m/s",
                             "maj_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                             "nx": nx, "ny": ny, "x": [round(x) for x in xs], "y": [round(y) for y in ys],
                             "heures": [t + ":00+00:00" for t in temps], "niveaux": out})
    print("Vent OK", len(temps), "heures,", nx * ny, "points, niveaux", list(out))


# ------------------------------------------------------------------ index
def index():
    recs = []
    for f in sorted(glob.glob(os.path.join(OUT, "analyses", "*.json"))):
        r = json.load(open(f))
        recs.append({k: r.get(k) for k in ("id", "date_utc", "capteur", "satellite", "resolution_m", "detectee",
                                           "sommet_m", "incertitude_m", "remplissage_sous_H", "situation", "sommet_brut_m")})
    recs.sort(key=lambda r: r["date_utc"])
    det = [r for r in recs if r["detectee"]]
    write_json("historique.json", {"maj_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                                   "analyses": recs, "derniere_detection": det[-1]["id"] if det else None,
                                   "derniere_analyse": recs[-1]["id"] if recs else None})
    print("index OK", len(recs), "analyses")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tout"
    if cmd == "statique": statique()
    elif cmd == "viirs": run_viirs(sys.argv[2] if len(sys.argv) > 2 else dt.date.today().strftime("%Y/%m/%d"))
    elif cmd == "s2": run_s2(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    elif cmd == "mtg":
        if len(sys.argv) > 2:
            j = dt.datetime.combine(dt.date.fromisoformat(sys.argv[2]), dt.time(0), dt.timezone.utc)
            run_mtg(j, j + dt.timedelta(days=1), max_images=48)
        else:
            run_mtg()
    elif cmd == "arome": run_arome()
    elif cmd == "vent": run_vent()
    elif cmd == "webcams": run_webcams(age_max_h=0)
    elif cmd == "webcams-corrections": run_webcams(age_max_h=10 ** 6)   # réapplique les corrections sans requête
    elif cmd == "obs": run_obs_mf()
    elif cmd == "lis": run_lis(forcer="--forcer" in sys.argv)
    elif cmd == "reclasser":       # après un changement de seuils : analyses publiées + diagnostic AROME
        reclasser()
        a = json.load(open(os.path.join(OUT, "arome.json"))); diagnostiquer_air(a["heures"]); write_json("arome.json", a)
    elif cmd == "tout":
        if not os.path.exists(os.path.join(OUT, "relief.png")): statique()
        run_mtg(); run_viirs(dt.date.today().strftime("%Y/%m/%d")); run_s2(); run_arome(); run_vent(); run_webcams()
    if cmd != "statique": index()
