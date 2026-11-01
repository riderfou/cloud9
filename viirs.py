"""
Analyse d'une granule VIIRS (NOAA, AWS open data) : estimation du sommet de la mer de nuages
avec un pixel à 375 m, en exploitant le MNT à 20 m à l'intérieur de chaque pixel.

Méthode "fraction sous-pixel" :
  pour un pixel VIIRS partiellement nuageux (fraction f entre 0,15 et 0,85), si la mer de nuages
  remplit tout ce qui est sous H, alors f = proportion des points du MNT du pixel qui sont sous H.
  => H = quantile f des altitudes MNT du pixel. Chaque pixel de bord donne ainsi une estimation de H.
"""
import glob, sys, json, numpy as np, h5py
from scipy.spatial import cKDTree
from rasterio.warp import transform as wtransform
import mer2nuages as m2n

def load(dirn, tag):
    geo = h5py.File(glob.glob(f"{dirn}/GITCO_*{tag}*.h5")[0])["All_Data/VIIRS-IMG-GEO-TC_All"]
    lat, lon = geo["Latitude"][:], geo["Longitude"][:]
    sel = (lat > 44.75) & (lat < 45.7) & (lon > 5.2) & (lon < 6.55)   # zone + marge (voir mtg.BBOX)
    r, c = np.where(sel)
    r0, r1, c0, c1 = r.min(), r.max() + 1, c.min(), c.max() + 1
    out = {"lat": lat[r0:r1, c0:c1], "lon": lon[r0:r1, c0:c1],
           "sza": geo["SolarZenithAngle"][r0:r1, c0:c1], "vza": geo["SatelliteZenithAngle"][r0:r1, c0:c1]}
    for b in ("I1", "I2", "I3"):
        n = int(b[1])
        d = h5py.File(glob.glob(f"{dirn}/SVI0{n}_*{tag}*.h5")[0])[f"All_Data/VIIRS-{b}-SDR_All"]
        raw = d["Reflectance"][r0:r1, c0:c1].astype("float32"); fac = d["ReflectanceFactors"][:2]
        refl = np.where(raw >= 65528, np.nan, raw * fac[0] + fac[1])
        out[b] = refl  # la réflectance SDR est déjà normalisée par cos(SZA)
    x, y = wtransform("EPSG:4326", m2n.CRS, out["lon"].ravel(), out["lat"].ravel())
    out["x"], out["y"] = np.array(x).reshape(out["lat"].shape), np.array(y).reshape(out["lat"].shape)
    return out

# Seuils par capteur : "I3" est le canal infrarouge court où la neige est sombre
# (1,6 µm pour VIIRS ; 2,2 µm pour MTG-FCI HRFI, où les nuages d'eau sont un peu moins brillants).
SEUILS_VIIRS = {"neige_swir_max": 0.15, "nuage_swir_min": 0.30}


def cloud_fraction(v, seuils=SEUILS_VIIRS):
    """Fraction nuageuse 0..1 par pixel : visible brillant ET infrarouge court brillant (la neige y est sombre)."""
    i1, i3 = v["I1"], v["I3"]
    ndsi = (i1 - i3) / np.maximum(i1 + i3, 1e-6)
    snow = (ndsi > 0.35) & (i3 < seuils["neige_swir_max"])
    # références auto-calibrées sur l'image (dépendent de l'éclairage, de l'épaisseur du nuage...)
    ins = (v["x"] > m2n.AOI[0]) & (v["x"] < m2n.AOI[2]) & (v["y"] > m2n.AOI[1]) & (v["y"] < m2n.AOI[3]) & ~snow
    cloudy = ins & (i3 > seuils["nuage_swir_min"]) & (i1 > 0.25)
    clearp = ins & (i1 < 0.2)
    cloud_ref = float(np.nanmedian(i1[cloudy])) if cloudy.sum() > 200 else 0.6
    clear_ref = float(np.nanmedian(i1[clearp])) if clearp.sum() > 200 else 0.06
    v["refs"] = {"sol": clear_ref, "nuage": cloud_ref}
    f = np.clip((i1 - clear_ref) / (cloud_ref - clear_ref), 0, 1)
    f = np.where(snow, 0, f)  # neige : pas nuage
    return f, ndsi

def robust_core(h, bw=40.0, half=250.0):
    """Garde les estimations autour du MODE de la distribution (noyau gaussien, largeur bw).
    Les bords "parasites" (nappe fine en plaine, neige/ombres en altitude) forment des bosses secondaires."""
    if len(h) < 20:
        return h
    grid = np.arange(0, 3500, 10.0)
    dens = np.exp(-0.5 * ((grid[:, None] - h[None, :]) / bw) ** 2).sum(1)
    mode = grid[np.argmax(dens)]
    return h[np.abs(h - mode) < half]

def analyse(dirn, tag, label):
    return analyse_pixels(load(dirn, tag), label)


def analyse_pixels(v, label, capteur="VIIRS 375 m", seuils=SEUILS_VIIRS, max_dist=700.0, parallaxe=(0.0, 0.0),
                   min_points=150, voisin_couvert=None):
    """v : dict de tableaux 2D x, y (UTM 31, m), I1 (visible), I3 (infrarouge court), vza (degrés).
    parallaxe : déplacement apparent (m) par mètre d'altitude (dx, dy). Nul pour une géolocalisation
    corrigée du relief (VIIRS GITCO) ; ≈ tan(vza) × direction opposée au satellite pour MTG.
    voisin_couvert : si renseigné (m), un pixel de bord n'est retenu que s'il a, dans ce rayon, un pixel
    entièrement couvert (fraction > 0,85) : le bord d'une nappe touche la nappe. Écarte les pentes
    rocheuses bien éclairées, plus brillantes que la référence « sol », isolées en haute montagne."""
    # fraction nuageuse fournie (méthode de nuit, infrarouge) ou calculée sur le visible / infrarouge court
    f = v["frac"] if "frac" in v else cloud_fraction(v, seuils)[0]
    dem = m2n.load_dem()
    # attribution de chaque point MNT (20 m) au pixel le plus proche de sa position APPARENTE
    # (empreinte de Voronoï ; avec parallaxe, un point en altitude apparaît décalé)
    ok = np.isfinite(v["x"]) & np.isfinite(f)
    tree = cKDTree(np.c_[v["x"][ok], v["y"][ok]])
    jj, ii = np.meshgrid(np.arange(m2n.W), np.arange(m2n.H))
    X = m2n.AOI[0] + (jj + .5) * m2n.RES; Y = m2n.AOI[3] - (ii + .5) * m2n.RES
    zz = np.nan_to_num(dem, nan=0.0)
    X = X + zz * parallaxe[0]; Y = Y + zz * parallaxe[1]
    dist, idx = tree.query(np.c_[X.ravel(), Y.ravel()], distance_upper_bound=max_dist)
    has = np.isfinite(dist) & np.isfinite(dem.ravel())
    pix = np.where(has, idx, -1)
    fv = f[ok]
    # carte de fraction nuageuse à 20 m (pour l'affichage) et estimation par pixel
    fmap = np.full(dem.size, np.nan, "float32"); fmap[has] = fv[pix[has]]; fmap = fmap.reshape(dem.shape)
    order = np.argsort(pix[has]); p_sorted = pix[has][order]; z_sorted = dem.ravel()[has][order]
    bounds = np.searchsorted(p_sorted, np.arange(len(fv) + 1))
    cand = np.where((fv > 0.15) & (fv < 0.85))[0]
    if voisin_couvert:
        pts = np.c_[v["x"][ok], v["y"][ok]]
        plein = np.zeros(len(fv), bool)
        for i, vois in zip(cand, tree.query_ball_point(pts[cand], voisin_couvert)):
            plein[i] = bool((fv[vois] > 0.85).any())
        cand = cand[plein[cand]]
    est = []
    for p in cand:
        z = z_sorted[bounds[p]:bounds[p + 1]]
        if len(z) < min_points or np.ptp(z) < 120:  # pixel incomplet ou trop plat : peu informatif
            continue
        est.append((p, float(np.quantile(z, fv[p])), float(np.ptp(z))))
    est = np.array(est)
    h = est[:, 1] if len(est) else np.array([])
    hf = robust_core(h)
    q = np.percentile(hf, [10, 25, 50, 75, 90]).tolist() if len(hf) > 20 else [np.nan] * 5
    iqr = q[3] - q[1]
    # Garde-fou physique : autour des pixels de bord (3 km), le terrain situé nettement SOUS H
    # doit être majoritairement couvert. Sinon ce sont des pixels mixtes neige/rocher, des
    # cumulus isolés... et pas une mer de nuages.
    remplissage = np.nan
    if len(hf) > 20:
        core_pix = est[np.abs(h - q[2]) < 250, 0].astype(int)
        is_edge = np.zeros(dem.size, bool); is_edge[has] = np.isin(pix[has], core_pix)
        from scipy import ndimage
        near = ndimage.distance_transform_edt(~is_edge.reshape(dem.shape)) * m2n.RES < 3000
        below = near & (dem < q[2] - 150) & np.isfinite(fmap)
        remplissage = float(np.nanmean(fmap[below] > 0.5)) if below.sum() > 1000 else 0.0
    detected = bool(len(hf) > 40 and iqr < 300 and remplissage > 0.4)
    # mailles de 5 km
    grid = []
    if len(est):
        # position vraie = position apparente − h × parallaxe
        px = v["x"][ok][est[:, 0].astype(int)] - h * parallaxe[0]
        py = v["y"][ok][est[:, 0].astype(int)] - h * parallaxe[1]
        keep = np.abs(h - q[2]) < 300
        for x0 in np.arange(m2n.AOI[0], m2n.AOI[2], 5000):
            for y0 in np.arange(m2n.AOI[1], m2n.AOI[3], 5000):
                s = keep & (px >= x0) & (px < x0 + 5000) & (py >= y0) & (py < y0 + 5000)
                if s.sum() >= 4:
                    grid.append({"x": float(x0 + 2500), "y": float(y0 + 2500), "h": float(np.median(h[s])), "n": int(s.sum())})
    res = {"scene": label, "capteur": capteur, "n_pixels_bord": int(len(hf)),
           "h_bords_quantiles_10_25_50_75_90": q, "ecart_interquartile_m": float(iqr),
           "mer_de_nuages_detectee": detected, "remplissage_sous_H": remplissage, "sommet_estime_m": float(q[2]) if detected else None,
           "incertitude_m": float(iqr / 2) if detected else None,
           "angle_zenithal_satellite": float(np.nanmedian(v["vza"])), "references_reflectance": v.get("refs"), "mailles": grid}
    return res, v, fmap, dem, est

def figure(res, v, fmap, dem, est, out):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from scipy.interpolate import griddata
    ext = [m2n.AOI[0] / 1e3, m2n.AOI[2] / 1e3, m2n.AOI[1] / 1e3, m2n.AOI[3] / 1e3]
    jj, ii = np.meshgrid(np.arange(0, m2n.W, 5), np.arange(0, m2n.H, 5))
    X = m2n.AOI[0] + (jj + .5) * m2n.RES; Y = m2n.AOI[3] - (ii + .5) * m2n.RES
    pts = np.c_[v["x"].ravel(), v["y"].ravel()]
    rgb = np.dstack([griddata(pts, v[b].ravel(), (X, Y), method="nearest") for b in ("I2", "I2", "I1")])
    rgb[..., 0] = griddata(pts, v["I3"].ravel(), (X, Y), method="nearest")  # composite 1.6/0.86/0.64
    rgb = np.clip(rgb / 0.9, 0, 1) ** 0.7
    hh = res["h_bords_quantiles_10_25_50_75_90"][2]
    fig = plt.figure(figsize=(17, 7.5))
    ax = fig.add_subplot(1, 3, 1); ax.imshow(rgb, extent=ext)
    ax.contour(np.flipud(dem), levels=[hh], colors="yellow", linewidths=0.7, extent=ext)
    ax.set_title(f"{res['scene']}\nComposite 1.6/0.86/0.64 µm (nuage = blanc, neige = cyan)\ncourbe {hh:.0f} m en jaune")
    ax = fig.add_subplot(1, 3, 2); ax.imshow(fmap, extent=ext, cmap="Blues", vmin=0, vmax=1)
    ax.contour(np.flipud(dem), levels=[hh], colors="red", linewidths=0.6, extent=ext)
    for g in res["mailles"]:
        ax.text(g["x"] / 1e3, g["y"] / 1e3, f"{g['h']:.0f}", fontsize=7, ha="center", va="center",
                bbox=dict(fc="white", alpha=0.7, lw=0, pad=0.5))
    ax.set_title("Fraction nuageuse VIIRS + estimations par maille 5 km")
    ax = fig.add_subplot(1, 3, 3)
    if len(est): ax.hist(est[:, 1], np.arange(0, 3000, 50), color="tab:blue")
    ax.axvline(hh, color="red", ls="--", label=f"médiane {hh:.0f} m")
    ax.set_xlabel("altitude estimée par pixel de bord (m)"); ax.legend()
    ax.set_title(f"{res['n_pixels_bord']} pixels mixtes informatifs")
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)

if __name__ == "__main__":
    dirn, tag, label = sys.argv[1], sys.argv[2], sys.argv[3]
    res, v, fmap, dem, est = analyse(dirn, tag, label)
    figure(res, v, fmap, dem, est, f"out/{label}.png")
    print(json.dumps({k: x for k, x in res.items() if k != "mailles"}, ensure_ascii=False, indent=1))
    json.dump(res, open(f"out/resultats_{label}.json", "w"), ensure_ascii=False, indent=1)
