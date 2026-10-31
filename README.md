# mer2nuages — altitude de la mer de nuages autour de Grenoble

Estimation de l'altitude du sommet de la mer de nuages autour de Grenoble à partir d'**images satellite**
et d'un **modèle numérique de terrain (MNT)**, avec une webapp 3D de visualisation.

## Contenu

| Fichier | Rôle |
|---|---|
| `mer2nuages.py` | Méthode Sentinel-2 (20 m) : masque nuage bas + altitude des bords latéraux |
| `viirs.py` | Méthode VIIRS (375 m) : fraction nuageuse par pixel + MNT 20 m à l'intérieur du pixel |
| `mtg.py` | Meteosat MTG-FCI (500 m, toutes les 10 min) : chunk 36 seulement, correction de parallaxe (identifiants EUMETSAT) |
| `viirs_find.py`, `viirs_fetch.py` | Recherche et téléchargement des passages VIIRS (NOAA, AWS Open Data, sans compte) |
| `pipeline.py` | Produit les données de la webapp (`web/data/`) : analyses, prévision AROME, relief, sommets |
| `web/` | Webapp statique (Three.js) : relief 3D, nappe simulée, nuage observé, graphique, sommets |
| `.github/workflows/pipeline.yml` | Mise à jour automatique + publication sur GitHub Pages |
| `scan_dates.py` | Planche contact Sentinel-2 pour repérer des journées de mer de nuages |

## Webapp

```bash
python3 pipeline.py statique                 # relief, texture, sommets (une fois)
python3 pipeline.py tout                     # VIIRS du jour + Sentinel-2 récents + AROME + index
cd web && python3 -m http.server 8000        # puis http://localhost:8000
```

## Meteosat MTG (en cours)

`mtg.py` télécharge uniquement le chunk FCI HRFI qui couvre Grenoble (n° 36/40) et corrige la parallaxe
(un point à l'altitude z apparaît décalé de ≈ 1,29 z vers le nord). Nécessite `EUMETSAT_CONSUMER_KEY` et
`EUMETSAT_CONSUMER_SECRET` (environnement local, ou secrets GitHub Actions pour la mise à jour automatique).
**Recherche catalogue testée ; téléchargement, lecture et seuils du canal 2,2 µm pas encore validés sur données réelles.**

```bash
python3 mtg.py chercher 2026-10-31T10:00 2026-10-31T12:00   # sans compte
python3 mtg.py analyser 2026-10-31T10:50                     # avec identifiants -> out/mtg_*.png
```

## Validation (31/10/2026 et cas passés)

| Date | Capteur | Sommet estimé | Comparaison |
|---|---|---|---|
| 31/10/2026 12:01 UTC | VIIRS NOAA-21 | 1 220 ± 66 m | observation visuelle : ~1 300-1 400 m |
| 31/10/2026 12:38 UTC | VIIRS Suomi-NPP | 1 234 ± 65 m | AROME (couche humide) 12-13 h : 1 176-1 192 m |
| 31/10/2026 12:58 UTC | VIIRS NOAA-20 | 1 264 ± 62 m | |
| 30/10/2026 10:50 UTC | Sentinel-2C | 1 116 ± 112 m | VIIRS 12:20 : nappe dissipée → non détectée (correct) |
| 14/12/2025 | S2 10:50 / VIIRS 12:20 | 502 / 468 m | écart 34 m |
| 29/12/2025 | S2 10:50 / VIIRS 12:39 | 517 / 491 m | écart 26 m |
| 14/11/2024 | S2 10:38 / VIIRS 12:27 | 1 612 m / non détectée | nappe probablement morcelée entre les deux passages (non vérifié) |

VIIRS semble **sous-estimer de 30 à 150 m** (nuage plus fin au bord de la nappe → fraction nuageuse sous-estimée).
À calibrer avec des observations au sol (webcams, randonneurs).

---

# Méthode Sentinel-2 (prototype n°1)

## Principe

Le bord d'une mer de nuages épouse les courbes de niveau. Donc :

1. **Masque « nuage bas »** (Sentinel-2, 20 m) : pixel brillant dans le visible (B02, B03 > 0,20)
   **et** brillant dans l'infrarouge à ondes courtes (B11 > 0,15, NDSI < 0,25).
   La neige est brillante dans le visible mais sombre en B11 : elle est exclue (les sommets enneigés
   de Belledonne ne sont pas pris pour des nuages). Les nuages de glace (cirrus, nuages élevés)
   ont aussi un NDSI élevé et sont exclus.
2. **Bords latéraux** : pixels dégagés au contact du nuage, sur une pente > 8°,
   où le terrain **monte** quand on sort du nuage. C'est là que le sommet de la couche coupe le relief.
   Les bords sur terrain plat (bout de nappe dans la vallée) sont ignorés.
3. **Altitude** = médiane du MNT (Copernicus GLO-30) sur ces bords, filtrée de manière robuste.
   L'incertitude est la demi-largeur de l'écart interquartile.
4. **Par maille de 5 km**, plus un plan ajusté : on voit si la couche est inclinée.
5. **Détection** : il y a une mer de nuages si plus de 1 500 pixels de bord latéral ont une altitude cohérente
   (écart interquartile < 300 m).

## Résultats sur des cas réels (tuile Sentinel-2 31TGL)

| Date       | Détectée | Sommet estimé | ± | Commentaire |
|------------|----------|---------------|---|-------------|
| 04/11/2024 | oui | **388 m** | 54 | nappe fine dans le Grésivaudan |
| 14/11/2024 | oui | **1 612 m** | 131 | sommets de Chartreuse et Belledonne qui émergent ; couche un peu plus haute côté Belledonne |
| 27/12/2024 | oui | **464 m** | 61 | Grésivaudan rempli |
| 03/01/2025 | non | – | – | nuages irréguliers, pas une nappe (IQR 397 m) |
| 04/11/2025 | non | – | – | ciel dégagé (contrôle) |
| 24/11/2025 | non | – | – | couvert épais / nuages de glace (contrôle) |
| 14/12/2025 | oui | **502 m** | 72 | Grésivaudan et cluse de l'Isère |
| 29/12/2025 | oui | **517 m** | 68 | voir `out/S2A_31TGL_20251229_1_L2A.png` |

Pour chaque date, `out/<scène>.png` montre l'image avec la courbe de niveau estimée en rouge,
le masque nuage avec les altitudes par maille, et les histogrammes d'altitude nuage / dégagé.

⚠️ Aucune vérité terrain pour l'instant : les valeurs sont **cohérentes visuellement**
(la courbe de niveau suit le bord du nuage) mais pas encore comparées à des webcams ou à des sondages.

## Lancer

```bash
pip install rasterio scipy matplotlib numpy requests pillow
python3 mer2nuages.py S2A_31TGL_20251229_1_L2A        # une ou plusieurs scènes
python3 scan_dates.py                                  # planche contact pour trouver des journées intéressantes
```
Données ouvertes sans compte : Sentinel-2 L2A COG (`sentinel-cogs` sur AWS) et Copernicus DEM (`copernicus-dem-30m` sur AWS).

## Limites connues

- Sentinel-2 ne passe que tous les 2 à 5 jours vers 10 h 50 : ça sert à **valider l'algorithme**, pas à suivre en temps réel.
- La zone couverte est limitée par la tuile 31TGL : le sud du Vercors et le Trièves sont coupés (ajouter les tuiles 31TGK et 31TFL).
- Le masque rate les brumes fines et grises au-dessus de l'agglomération.
- Des nuages plus hauts au-dessus de la mer de nuages la masquent.

## Pistes

1. **MTG-FCI (Meteosat 3ᵉ génération)**, une image toutes les 10 minutes : même algorithme avec
   les canaux VIS 0.6 / NIR 1.6 µm (équivalents de B03 / B11) à environ 1 km.
   On peut l'affiner par recalage : on garde le masque grossier et on cherche l'altitude H
   qui reproduit au mieux le masque observé une fois dégradé à 1 km.
   Accès : EUMETSAT Data Store (compte gratuit) ou EUMETView WMS.
   La nuit : produit brouillard / nuages bas (3,9 − 10,8 µm).
2. **AROME (Open-Meteo / Météo-France)** : profil d'humidité et de température → valeur de départ et prévision.
3. **Webcams** : classement au-dessus / dedans / en dessous, pour valider et combler les trous.
4. **Fusion bayésienne** + carte 3D (MapLibre) avec le MNT « inondé » à l'altitude estimée.
