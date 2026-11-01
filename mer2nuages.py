"""
mer2nuages — estimation de l'altitude du sommet d'une mer de nuages autour de Grenoble
à partir d'une image satellite (ici Sentinel-2 L2A) et d'un modèle numérique de terrain.

Principe : le bord d'une mer de nuages épouse les courbes de niveau. On construit un masque
"nuage bas" puis on cherche l'altitude H qui sépare au mieux nuage (terrain < H) et sol
dégagé (terrain > H). On calcule aussi l'altitude du terrain le long des bords du nuage,
globalement et par maille de 5 km (pour voir si la couche est inclinée).

Usage : python3 mer2nuages.py S2B_31TGL_20241104_0_L2A [...]
"""
import sys, json, numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.transform import from_origin
from scipy import ndimage

S2_BASE = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/31/T"
S2 = f"{S2_BASE}/GL"               # tuile principale 31TGL (Grenoble, Grésivaudan, Belledonne)
# La zone déborde de 31TGL à l'ouest et au sud : tuiles voisines du même passage, en complément
TUILES_VOISINES = ("FL", "GK", "FK")
DEM = "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{lat}_00_E00{lon}_00_DEM/Copernicus_DSM_COG_10_N{lat}_00_E00{lon}_00_DEM.tif"
CRS = "EPSG:32631"
# Grenoble, Grésivaudan, Chartreuse, Vercors, Belledonne, Voironnais, Chambéry, Matheysine
# (zone d'origine 699960-759960 x 4990200-5045000, élargie de 10 km de chaque côté le 01/11/2026)
AOI = (689960, 4980200, 769960, 5055000)
RES = 20.0
W, H = int((AOI[2] - AOI[0]) / RES), int((AOI[3] - AOI[1]) / RES)
TRANSFORM = from_origin(AOI[0], AOI[3], RES, RES)


def lire_s2(scene, fichier, bandes=1, out_shape=None):
    """Lit un fichier d'une scène 31TGL sur la zone, complété par les tuiles voisines du même passage
    (même date, même satellite) là où 31TGL n'a pas de données. 0 = pas de donnée."""
    y, m = scene.split("_")[2][:4], str(int(scene.split("_")[2][4:6]))
    out_shape = out_shape or (H, W)
    out = None
    for tuile in ("GL",) + TUILES_VOISINES:
        sc = scene.replace("_31TGL_", f"_31T{tuile}_")
        try:
            with rasterio.open(f"{S2_BASE}/{tuile}/{y}/{m}/{sc}/{fichier}") as s:
                idx = 1 if bandes == 1 else list(range(1, bandes + 1))
                a = s.read(idx, window=from_bounds(*AOI, s.transform), out_shape=out_shape if bandes == 1 else (bandes,) + out_shape,
                           resampling=Resampling.average, boundless=True, fill_value=0)
        except Exception as e:
            if tuile == "GL":
                print(f"  Sentinel-2 : {sc}/{fichier} illisible ({e})")
            continue                       # tuile voisine absente pour ce passage
        if out is None:
            out = a
        else:
            vide = (out == 0) if bandes == 1 else (out == 0).all(axis=0, keepdims=True)
            out = np.where(vide, a, out)
    if out is None:
        raise FileNotFoundError(f"{scene}/{fichier}")
    return out


def read_band(scene, band, scale=1e-4):
    return lire_s2(scene, f"{band}.tif").astype("float32") * scale


def load_dem(cache="dem_zone_v2_20m.npy"):
    try:
        return np.load(cache)
    except FileNotFoundError:
        pass
    out = np.full((H, W), np.nan, "float32")
    for lat, lon in ((45, 5), (45, 6), (44, 5), (44, 6)):
        with rasterio.open(DEM.format(lat=lat, lon=lon)) as s:
            tmp = np.full((H, W), np.nan, "float32")
            reproject(rasterio.band(s, 1), tmp, dst_transform=TRANSFORM, dst_crs=CRS,
                      resampling=Resampling.bilinear, dst_nodata=np.nan)
            out = np.where(np.isnan(out), tmp, out)
    np.save(cache, out)
    return out


def cloud_mask(scene):
    """Nuage bas d'eau liquide : brillant dans le visible, brillant aussi en SWIR (B11).
    La neige est brillante dans le visible mais sombre en SWIR (NDSI élevé)."""
    g, swir, blue = read_band(scene, "B03"), read_band(scene, "B11"), read_band(scene, "B02")
    valid = (g > 0) & (swir > 0)
    ndsi = (g - swir) / np.maximum(g + swir, 1e-6)
    cloud = valid & (g > 0.20) & (blue > 0.20) & (ndsi < 0.25) & (swir > 0.15)
    # nettoyage morphologique (bruit, routes, toits)
    cloud = ndimage.binary_opening(cloud, iterations=2)
    cloud = ndimage.binary_closing(cloud, iterations=2)
    return cloud, valid, ndsi


def estimate(scene, dem):
    cloud, valid, ndsi = cloud_mask(scene)
    ok = valid & np.isfinite(dem)
    z = dem[ok]; c = cloud[ok]
    # 1) seuil optimal : H qui maximise l'accord "nuage <=> terrain < H"
    hs = np.arange(150, 2500, 10)
    zs = np.sort(z); order = np.argsort(z); cs = c[order]
    cum_cloud = np.concatenate([[0], np.cumsum(cs)])
    n = len(zs); ntot_cloud = cs.sum()
    idx = np.searchsorted(zs, hs)
    # pixels sous H nuageux + pixels au-dessus de H dégagés
    acc = (cum_cloud[idx] + ((n - idx) - (ntot_cloud - cum_cloud[idx]))) / n
    h_best = float(hs[np.argmax(acc)])
    # score de type "mer de nuages" : comparaison à la meilleure règle triviale
    baseline = max(c.mean(), 1 - c.mean())
    # 2) altitude du terrain le long des bords (côté dégagé, adjacent au nuage)
    clear = ok & ~cloud
    edge = clear & ndimage.binary_dilation(cloud, iterations=1)
    # On ne garde que les bords "latéraux" : pente > 8° et terrain qui MONTE quand on sort du nuage.
    # Les bords sur terrain plat (bout de la nappe, trous) ne renseignent pas sur l'altitude du sommet.
    dz_y, dz_x = np.gradient(np.nan_to_num(dem, nan=0.0), RES)
    slope = np.degrees(np.arctan(np.hypot(dz_x, dz_y)))
    cf = ndimage.gaussian_filter(cloud.astype("float32"), 3)
    cf_y, cf_x = np.gradient(cf)
    uphill_out = (dz_x * -cf_x + dz_y * -cf_y) > 0
    edge &= (slope > 8) & uphill_out
    # on ignore les bords trop loin de l'altitude estimée (nuages convectifs isolés, etc.)
    ez = dem[edge]
    # filtrage robuste itératif autour de la médiane (indépendant du seuil global)
    ez_f = ez
    for _ in range(3):
        if len(ez_f) == 0: break
        ez_f = ez[np.abs(ez - np.median(ez_f)) < 400]
    q = np.percentile(ez_f, [10, 25, 50, 75, 90]).tolist() if len(ez_f) > 50 else [np.nan] * 5
    # 3) par maille de 5 km
    cell = int(5000 / RES); grid = []
    for i in range(0, H - cell + 1, cell):
        for j in range(0, W - cell + 1, cell):
            e = edge[i:i + cell, j:j + cell]; d = dem[i:i + cell, j:j + cell][e]
            d = d[np.abs(d - (np.median(ez_f) if len(ez_f) else h_best)) < 400]
            if len(d) >= 30:
                x = AOI[0] + (j + cell / 2) * RES; y = AOI[3] - (i + cell / 2) * RES
                grid.append({"x": x, "y": y, "h": float(np.median(d)), "n": int(len(d))})
    # pente de la couche : régression plane h = a + b*x + c*y
    tilt = None
    if len(grid) >= 6:
        A = np.array([[1, g["x"] / 1000, g["y"] / 1000] for g in grid]); b = np.array([g["h"] for g in grid])
        coef, *_ = np.linalg.lstsq(A, b, rcond=None)
        tilt = {"m_par_km_est": float(coef[1]), "m_par_km_nord": float(coef[2]),
                "residu_m": float(np.std(b - A @ coef))}
    res = {
        "scene": scene,
        "couverture_nuage_bas": float(c.mean()),
        "h_seuil_optimal": h_best,
        "accord": float(acc.max()), "accord_trivial": float(baseline),
        "gain": float(acc.max() - baseline),
        "h_bords_quantiles_10_25_50_75_90": q,
        "n_pixels_bord": int(len(ez_f)),
        "inclinaison": tilt,
        "mailles": grid,
    }
    # diagnostic
    # Une mer de nuages = beaucoup de bords latéraux, à une altitude cohérente (écart interquartile faible)
    iqr = q[3] - q[1] if np.isfinite(q[1]) else np.inf
    res["ecart_interquartile_m"] = float(iqr)
    res["mer_de_nuages_detectee"] = bool(len(ez_f) > 1500 and iqr < 300 and 0.01 < c.mean() < 0.95)
    res["sommet_estime_m"] = float(q[2]) if res["mer_de_nuages_detectee"] else None
    res["incertitude_m"] = float(iqr / 2) if res["mer_de_nuages_detectee"] else None
    return res, cloud, acc, hs


def figure(scene, dem, cloud, res, acc, hs, out):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rgb = np.dstack([read_band(scene, b) for b in ("B04", "B03", "B02")])
    rgb = np.clip(rgb / 0.35, 0, 1) ** 0.8
    h = res["h_bords_quantiles_10_25_50_75_90"][2]
    ext = [AOI[0] / 1000, AOI[2] / 1000, AOI[1] / 1000, AOI[3] / 1000]
    fig = plt.figure(figsize=(17, 7.5))
    ax = fig.add_subplot(1, 3, 1); ax.imshow(rgb, extent=ext)
    ax.contour(np.flipud(dem), levels=[h], colors="red", linewidths=0.6, extent=ext)
    ax.set_title(f"{scene}\nImage + courbe de niveau {h:.0f} m (rouge)")
    ax = fig.add_subplot(1, 3, 2)
    ax.imshow(np.where(cloud, 1.0, np.nan), extent=ext, cmap="Blues", vmin=0, vmax=1.3)
    ax.imshow(np.ma.masked_where(dem > h, dem), extent=ext, cmap="Reds", alpha=0.35)
    for g in res["mailles"]:
        ax.text(g["x"] / 1000, g["y"] / 1000, f"{g['h']:.0f}", fontsize=7, ha="center", va="center",
                bbox=dict(fc="white", alpha=0.7, lw=0, pad=0.5))
    ax.set_title("Masque nuage bas (bleu) / terrain < H (rouge)\naltitude médiane des bords par maille 5 km")
    ax = fig.add_subplot(1, 3, 3)
    ok = np.isfinite(dem)
    bins = np.arange(150, 3000, 25)
    ax.hist(dem[ok & cloud], bins, alpha=0.6, label="pixels nuageux", color="tab:blue")
    ax.hist(dem[ok & ~cloud], bins, alpha=0.5, label="pixels dégagés", color="tab:orange")
    ax2 = ax.twinx(); ax2.plot(hs, acc, "k-", lw=1); ax2.set_ylabel("accord du seuil")
    ax.axvline(h, color="red", ls="--", label=f"bords : {h:.0f} m")
    ax.axvline(res["h_seuil_optimal"], color="k", ls=":", label=f"seuil optimal : {res['h_seuil_optimal']:.0f} m")
    ax.set_xlabel("altitude du terrain (m)"); ax.legend(fontsize=8); ax.set_xlim(150, 2800)
    ax.set_title("Distribution des altitudes")
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)


if __name__ == "__main__":
    dem = load_dem()
    allres = []
    for scene in sys.argv[1:]:
        res, cloud, acc, hs = estimate(scene, dem)
        figure(scene, dem, cloud, res, acc, hs, f"out/{scene}.png")
        short = {k: v for k, v in res.items() if k != "mailles"}
        print(json.dumps(short, ensure_ascii=False, indent=1))
        allres.append(res)
    json.dump(allres, open(sys.argv[0].replace("mer2nuages.py","") + "out/resultats_" + "_".join(a.split("_")[2] for a in sys.argv[1:]) + ".json", "w"), ensure_ascii=False, indent=1)
