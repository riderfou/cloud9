"""
Pipeline mer2nuages : produit les données de la webapp dans web/data/.

  python3 pipeline.py statique            # relief, texture, sommets (une fois)
  python3 pipeline.py viirs AAAA/MM/JJ    # passages VIIRS du jour (≈ 11 h - 14 h UTC)
  python3 pipeline.py s2 [jours]          # scènes Sentinel-2 récentes (défaut : 5 derniers jours)
  python3 pipeline.py mtg [AAAA-MM-JJ]    # Meteosat MTG, une image toutes les 30 min de jour (identifiants EUMETSAT)
  python3 pipeline.py arome               # prévision AROME (Open-Meteo)
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
    scene = "S2C_31TGL_20251104_0_L2A"
    url = f"{m2n.S2}/2025/11/{scene}/TCI.tif"
    tw, th = m2n.W * 2 // 3, m2n.H * 2 // 3
    with rasterio.open(url) as s:
        a = s.read(window=from_bounds(*m2n.AOI, s.transform), out_shape=(3, th, tw),
                   resampling=Resampling.average, boundless=True, fill_value=0)
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


def run_mtg(jour=None, pas_min=30, max_images=24):
    """Analyse les images MTG du jour (une toutes les `pas_min` minutes, de jour) pas encore traitées."""
    import mtg
    from pyorbital.astronomy import sun_zenith_angle
    if not (os.environ.get("EUMETSAT_CONSUMER_KEY") and os.environ.get("EUMETSAT_CONSUMER_SECRET")):
        print("MTG : identifiants EUMETSAT absents, étape ignorée"); return
    os.makedirs(os.path.join(OUT, "analyses"), exist_ok=True)
    jour = jour or dt.datetime.now(dt.timezone.utc).date()
    debut = dt.datetime.combine(jour, dt.time(5, 0), dt.timezone.utc)
    fin = min(dt.datetime.combine(jour, dt.time(18, 0), dt.timezone.utc),
              dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=20))
    fait = 0
    for ident, t0, ent in mtg.chercher(debut, fin):
        if t0.minute % pas_min or fait >= max_images:
            continue
        if sun_zenith_angle(t0.replace(tzinfo=None), mtg.LON, mtg.LAT) > 78:   # nuit / soleil trop bas
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


# ------------------------------------------------------------------ observations Météo-France
MF = "https://public-api.meteofrance.fr/public"
DEPTS_MF = ("38", "73")


def _mf_get(chemin, key, **params):
    r = requests.get(f"{MF}/{chemin}", headers={"apikey": key, "accept": "*/*"}, params=params, timeout=60)
    return r


def run_obs_mf(jours=7):
    """Observations horaires des stations Météo-France de la zone (Isère, Savoie) -> obs_mf.json.
    Le paquet horaire couvre les dernières 24 h : on cumule à chaque passage et on garde `jours` jours.
    Altitude prise sur le MNT à la position de la station (cohérente avec le reste de l'analyse)."""
    key = os.environ.get("MF_OBS_API_KEY")
    if not key:
        print("Obs MF : MF_OBS_API_KEY absente, étape ignorée"); return
    dst = os.path.join(OUT, "obs_mf.json")
    base = json.load(open(dst)) if os.path.exists(dst) else {"stations": {}, "mesures": {}}
    noms = {}
    r = _mf_get("DPObs/v1/liste-stations", key)
    print("Obs MF : liste-stations", r.status_code, r.headers.get("content-type"), r.text[:200].replace("\n", " | "))
    if r.ok and "json" not in (r.headers.get("content-type") or ""):
        import csv, io
        for row in csv.DictReader(io.StringIO(r.text), delimiter=";"):
            k = {c.lower(): v for c, v in row.items() if c}
            if k.get("id_station"): noms[k["id_station"]] = k.get("nom_usuel") or k.get("nom")
    dem = m2n.load_dem()
    n_new = 0
    for d in DEPTS_MF:
        r = _mf_get("DPPaquetObs/v1/paquet/horaire", key, **{"id-departement": d, "format": "json"})
        print(f"Obs MF : paquet horaire {d}", r.status_code, r.headers.get("content-type"), (r.text[:300] if not r.ok else ""))
        if not r.ok:
            continue
        lignes = r.json()
        if lignes:
            print("Obs MF : champs", sorted(lignes[0]))
        for o in lignes:
            sid, la, lo = str(o.get("geo_id_insee")), o.get("lat"), o.get("lon")
            if la is None or lo is None:
                continue
            if sid not in base["stations"]:
                x, y = wtransform("EPSG:4326", m2n.CRS, [lo], [la]); x, y = x[0], y[0]
                j, i = int((x - m2n.AOI[0]) / m2n.RES), int((m2n.AOI[3] - y) / m2n.RES)
                if not (0 <= i < m2n.H and 0 <= j < m2n.W) or not np.isfinite(dem[i, j]):
                    continue
                base["stations"][sid] = {"id": sid, "nom": noms.get(sid, sid), "lat": la, "lon": lo,
                                         "x": round(x, 1), "y": round(y, 1), "alt": round(float(dem[i, j]))}
            k = lambda c: o.get(c)
            t = k("t"); td = k("td")
            m = {"t": k("validity_time"), "T": None if t is None else round(t - 273.15, 1),
                 "Td": None if td is None else round(td - 273.15, 1), "U": k("u"), "vv": k("vv"),
                 "n": k("n"), "ff": k("ff"), "dd": k("dd"), "rr1": k("rr1"), "insolh": k("insolh")}
            serie = base["mesures"].setdefault(sid, [])
            if m["t"] and all(x["t"] != m["t"] for x in serie):
                serie.append(m); n_new += 1
    limite = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=jours)).isoformat()
    for sid in list(base["mesures"]):
        base["mesures"][sid] = sorted((x for x in base["mesures"][sid] if x["t"] >= limite[:19]), key=lambda x: x["t"])
    base["maj_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    base["source"] = "Météo-France, données publiques d'observation"
    write_json("obs_mf.json", base)
    print(f"Obs MF OK : {len(base['stations'])} stations dans la zone, {n_new} nouvelles mesures")


# ------------------------------------------------------------------ webcams (Windy)
WINDY = "https://api.windy.com/webcams/api/v3/webcams"


def run_webcams(lat=45.27, lon=5.94, rayon_km=40, age_max_h=12):
    """Liste des webcams Windy dans la zone -> webcams.json (position, altitude MNT, lecteur intégrable).
    Les URL d'images de l'offre gratuite expirent au bout de quelques minutes : on ne garde que le
    lecteur Windy (iframe public, sans clé) et le lien vers la page de la webcam."""
    key = os.environ.get("WINDY_WEBCAMS_API_KEY")
    if not key:
        print("Webcams : WINDY_WEBCAMS_API_KEY absente, étape ignorée"); return
    dst = os.path.join(OUT, "webcams.json")
    if os.path.exists(dst):
        try:
            maj = dt.datetime.fromisoformat(json.load(open(dst))["maj_utc"])
            if dt.datetime.now(dt.timezone.utc) - maj < dt.timedelta(hours=age_max_h):
                print("Webcams : liste récente, pas de nouvelle requête"); return
        except Exception:
            pass
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
                    "x": round(x, 1), "y": round(y, 1), "lat": la, "lon": lo, "alt_mnt": round(float(dem[i, j])),
                    "lecteur": lecteur, "lien": urls.get("detail") or (f"https://www.windy.com/webcams/{wid}" if wid else None),
                    "maj": w.get("lastUpdatedOn")})
    out.sort(key=lambda c: -c["alt_mnt"])
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
    elif cmd == "mtg": run_mtg(dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif cmd == "arome": run_arome()
    elif cmd == "webcams": run_webcams(age_max_h=0)
    elif cmd == "obs": run_obs_mf()
    elif cmd == "reclasser":       # après un changement de seuils : analyses publiées + diagnostic AROME
        reclasser()
        a = json.load(open(os.path.join(OUT, "arome.json"))); diagnostiquer_air(a["heures"]); write_json("arome.json", a)
    elif cmd == "tout":
        if not os.path.exists(os.path.join(OUT, "relief.png")): statique()
        run_mtg(); run_viirs(dt.date.today().strftime("%Y/%m/%d")); run_s2(); run_arome(); run_webcams()
    if cmd != "statique": index()
