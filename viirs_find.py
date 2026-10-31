"""Trouve les granules VIIRS (GITCO) d'une date qui couvrent Grenoble, en lisant seulement
les attributs G-Ring à distance (quelques Ko par fichier).
Usage : python3 viirs_find.py AAAA/MM/JJ [tHHMM début] [tHHMM fin]"""
import sys, re, requests, fsspec, h5py, numpy as np
from concurrent.futures import ThreadPoolExecutor

LAT, LON = 45.2, 5.8
BUCKETS = {"noaa-nesdis-snpp-pds": "Suomi-NPP", "noaa-nesdis-n20-pds": "NOAA-20", "noaa-nesdis-n21-pds": "NOAA-21"}
_fs = fsspec.filesystem("https", block_size=256 * 1024)


def list_keys(bucket, date, t0, t1):
    keys, token = [], None
    while True:
        params = {"list-type": "2", "prefix": f"VIIRS-IMG-GEO-TC/{date}/"}
        if token: params["continuation-token"] = token
        x = requests.get(f"https://{bucket}.s3.amazonaws.com/", params=params, timeout=60).text
        keys += re.findall(r"<Key>([^<]+)</Key>", x)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", x)
        if not m: break
        token = m.group(1)
    return [(bucket, k) for k in keys if t0 <= k.split("_")[3] <= t1]


def _check(bk):
    b, k = bk
    try:
        with _fs.open(f"https://{b}.s3.amazonaws.com/{k}") as f, h5py.File(f) as h:
            g = h["Data_Products/VIIRS-IMG-GEO-TC/VIIRS-IMG-GEO-TC_Gran_0"].attrs
            la, lo = g["G-Ring_Latitude"].ravel(), g["G-Ring_Longitude"].ravel()
        inside = la.min() < LAT < la.max() and lo.min() < LON < lo.max()
        return (b, k, inside, float(np.hypot(la.mean() - LAT, (lo.mean() - LON) * 0.7)))
    except Exception:
        return (b, k, False, 99.0)


def find(date, t0="t1030", t1="t1400", max_dist=6.0):
    """Renvoie [(bucket, clé GITCO, distance_centre_deg)] triés, au plus un par satellite et par passage."""
    allk = []
    for b in BUCKETS:
        allk += list_keys(b, date, t0, t1)
    hits = [r for r in ThreadPoolExecutor(24).map(_check, allk) if r[2] and r[3] < max_dist]
    best = {}
    for b, k, _, d in hits:  # une seule granule par satellite (la plus centrée)
        if b not in best or d < best[b][2]:
            best[b] = (b, k, d)
    return sorted(best.values(), key=lambda r: r[1].split("_")[3])


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else "2026/10/31"
    t0, t1 = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("t1030", "t1400")
    for b, k, d in find(date, t0, t1):
        print(b, k, f"{d:.2f}")
