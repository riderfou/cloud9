"""Télécharge une granule VIIRS (GITCO + I1/I2/I3) : python3 viirs_fetch.py <bucket> <AAAA/MM/JJ> <tHHMMSSs> <dossier>"""
import sys, re, requests, os
from concurrent.futures import ThreadPoolExecutor
bucket, date, tag, outd = sys.argv[1:5]
os.makedirs(outd, exist_ok=True)
def get(p):
    x = requests.get(f"https://{bucket}.s3.amazonaws.com/?list-type=2&prefix={p}/{date}/").text
    k = [k for k in re.findall(r"<Key>([^<]+)</Key>", x) if f"_{tag}_" in k][0]
    dst = f"{outd}/{os.path.basename(k)}"
    if not os.path.exists(dst):
        with requests.get(f"https://{bucket}.s3.amazonaws.com/{k}", stream=True) as r, open(dst, "wb") as f:
            for c in r.iter_content(1 << 20): f.write(c)
    return dst
print(list(ThreadPoolExecutor(4).map(get, ["VIIRS-IMG-GEO-TC", "VIIRS-I1-SDR", "VIIRS-I2-SDR", "VIIRS-I3-SDR"])))
