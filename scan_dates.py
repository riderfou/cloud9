"""Planche contact des scènes Sentinel-2 (tuile 31TGL) autour de Grenoble pour repérer les jours de mer de nuages."""
import re, sys, requests, numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw
B="https://sentinel-cogs.s3.us-west-2.amazonaws.com"
AOI=(700000,5000000,760000,5040000)  # UTM31 : Grenoble/Grésivaudan/Chartreuse/Vercors nord
def scenes(ym):
    y,m=ym
    x=requests.get(f"{B}/?list-type=2&prefix=sentinel-s2-l2a-cogs/31/T/GL/{y}/{m}/&delimiter=/").text
    return re.findall(r"<Prefix>([^<]+_L2A/)</Prefix>",x)
def thumb(p):
    try:
        with rasterio.open(f"{B}/{p}TCI.tif") as s:
            w=from_bounds(*AOI,s.transform)
            a=s.read(window=w,out_shape=(3,250,375),resampling=Resampling.average)
        if a.mean()<5: return None
        return p.split("/")[-2], np.moveaxis(a,0,-1)
    except Exception as e: return None
months=[(y,m) for y,ms in [(2024,[11,12]),(2025,[1,2,10,11,12]),(2026,[1,2])] for m in ms]
ps=sorted(set(sum(ThreadPoolExecutor(8).map(scenes,months),[])),key=lambda p:p.split("_")[2])
ps=[p for p in ps if "_0_L2A" in p or True]
res=[r for r in ThreadPoolExecutor(16).map(thumb,ps) if r]
cols=8; rows=(len(res)+cols-1)//cols
sheet=Image.new("RGB",(cols*375,rows*270),"black"); d=ImageDraw.Draw(sheet)
for i,(n,a) in enumerate(res):
    x,y=(i%cols)*375,(i//cols)*270
    sheet.paste(Image.fromarray(a),(x,y+20)); d.text((x+4,y+4),n,fill="yellow")
sheet.save("scan/contact.jpg",quality=80); print(len(res),"scènes")
