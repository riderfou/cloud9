# mer2nuages — altitude de la mer de nuages autour de Grenoble

Estimation de l'altitude du sommet de la mer de nuages autour de Grenoble à partir d'**images satellite**
et d'un **modèle numérique de terrain (MNT)**, avec une webapp 3D de visualisation.

## Contenu

| Fichier | Rôle |
|---|---|
| `mer2nuages.py` | Méthode Sentinel-2 (20 m) : masque nuage bas + altitude des bords latéraux |
| `viirs.py` | Méthode VIIRS (375 m) : fraction nuageuse par pixel + MNT 20 m à l'intérieur du pixel |
| `mtg.py` | Meteosat MTG-FCI toutes les 10 min : visible 500 m le jour, infrarouge 1 km la nuit ; chunk 36 seulement, correction de parallaxe (identifiants EUMETSAT) |
| `tools/nuit_mtg.py` | Prototype de la méthode de nuit, comparée au visible et aux stations |
| `tools/calibrage_mtg.py` | Calibrage MTG sur une journée (variantes parallaxe, seuils, filtre de bord) |
| Webcams Windy | `pipeline.py webcams` : webcams de la zone (API Windy v3, clé `WINDY_WEBCAMS_API_KEY`), placées sur la carte avec leur altitude et un lecteur intégré |
| `webcams_corrections.json` | Corrections d'altitude ou de position des webcams Windy mal placées (souvent déclarées au centre du village), appliquées à chaque passage |
| `web/editeur-webcams.html` | Éditeur en ligne de ces corrections : glisser-déposer des webcams sur une carte topographique, export du fichier |
| `viirs_find.py`, `viirs_fetch.py` | Recherche et téléchargement des passages VIIRS (NOAA, AWS Open Data, sans compte) |
| `pipeline.py` | Produit les données de la webapp (`web/data/`) : analyses, prévision AROME, relief, sommets, webcams, observations Météo-France (`obs_mf.json`, clé `MF_OBS_API_KEY`, API DPObs v2) |
| `pipeline.py vent` | Champ de vent AROME sur une grille 11 × 11 de la zone (`web/data/vent.json`, u/v heure par heure à 10 m et 850 hPa), animé en particules dans la webapp |
| `web/` | Webapp statique (Three.js) : relief 3D, nappe simulée, nuage observé, graphique, sommets |
| `.github/workflows/pipeline.yml` | Mise à jour automatique + publication sur GitHub Pages |
| `scan_dates.py` | Planche contact Sentinel-2 pour repérer des journées de mer de nuages |

## Webapp

```bash
python3 pipeline.py statique                 # relief, texture, sommets (une fois)
python3 pipeline.py tout                     # VIIRS du jour + Sentinel-2 récents + AROME + index
cd web && python3 -m http.server 8000        # puis http://localhost:8000
```

## Zone d'étude

80 × 75 km en UTM 31N (689 960-769 960 × 4 980 200-5 055 000), élargie de 10 km de chaque côté le 01/11/2026 :
Chartreuse, Vercors nord, Belledonne, Grésivaudan, Voironnais, Chambéry, Matheysine. MNT Copernicus à 20 m (4 tuiles).
Sentinel-2 : tuile 31TGL complétée par 31TFL, 31TGK et 31TFK (même passage). Les analyses antérieures à
l'élargissement gardent leur emprise d'origine (champ `emprise`), leurs masques étant recadrés dans la nouvelle grille.

## Meteosat MTG

`mtg.py` télécharge uniquement le chunk FCI HRFI qui couvre Grenoble (n° 36/40, ≈ 22 Mo) et corrige la parallaxe
(un point à l'altitude z apparaît décalé de ≈ 1,29 z vers le nord). Nécessite `EUMETSAT_CONSUMER_KEY` et
`EUMETSAT_CONSUMER_SECRET` d'un compte ayant la licence « Meteosat > 1 hr latency » (« < 1 hr » pour le temps réel),
en local ou en secrets GitHub Actions.

Calibrage du 31/10/2026 (`tools/calibrage_mtg.py`) :

| | 12:08 | 12:38 | 12:48 | 11:58-13:08 (8 images) |
|---|---|---|---|---|
| MTG (version actuelle) | – | 1 291 ± 65 m | 1 290 ± 67 m | |
| MTG sans filtre « contact nappe » | 1 281 | 1 271 | 1 276 | 1 266-1 281 m |
| MTG sans parallaxe | 1 107 | 610 | 585 | 585-1 153 m (incohérent) |
| VIIRS | 1 220 (12:01) | 1 234 | 1 264 (12:58) | |

Observation visuelle : 1 300-1 400 m. MTG est 10 à 60 m au-dessus de VIIRS, donc plus proche de l'observation,
ce qui va dans le sens d'une sous-estimation par VIIRS.
- La parallaxe est indispensable. La valeur théorique minimise la dispersion, et ±10 % changent le résultat de moins de 20 m.
- Les seuils du canal 2,2 µm sont peu sensibles (seuils VIIRS : −10 m).
- Filtre « contact nappe » (`voisin_couvert`) : un pixel de bord doit toucher, à moins de 1 200 m, un pixel entièrement
  couvert. Sans lui, des pentes rocheuses éclairées de Belledonne créaient un second pic d'altitudes vers 2 200 m,
  qui comptait plus de pixels que le vrai bord.
- Journée complète (`pipeline.py mtg 2026-10-31`, une image toutes les 30 min) : nappe détectée sur les 15 images de 8 h 08 à 15 h 08 UTC.
  Le sommet reste entre 1 198 et 1 332 m de 8 h 38 à 14 h 38. Les deux images à soleil bas s'écartent : 8 h 08 → 1 150 m,
  15 h 08 → 1 062 m. À confirmer : erreur de mesure ou vraie évolution de la nappe ?
- Pas encore évalué : autres journées.

```bash
python3 mtg.py chercher 2026-10-31T10:00 2026-10-31T12:00   # sans compte
python3 mtg.py analyser 2026-10-31T10:50                     # avec identifiants -> out/mtg_*.png
```

### La nuit : infrarouge

De nuit (soleil à plus de 87° du zénith), le nuage bas est repéré par l'écart de température de brillance
10,5 - 3,8 µm (canaux à 1 km du même fichier) : environ +4 K sur un nuage de gouttelettes, environ 0 K sur un sol dégagé
ou enneigé. La fraction nuageuse qui en découle passe dans la même méthode des bords (parallaxe, contact avec la nappe).
Entre 78° et 87° (aube, crépuscule), aucune des deux méthodes n'est fiable : pas d'analyse.

Nuit du 31/10 au 01/11/2026 (`tools/nuit_mtg.py`) : mer de nuages détectée sur toutes les images de 16 h 08 à 6 h 08 UTC,
la nappe montant de 1 330 à 1 556 m. Au matin, le visible prend le relais à 1 623 m. Chaque fois que les stations
Météo-France donnent une fourchette, l'infrarouge y tombe (exemple à 2 h : Col de Porte, 1 325 m, est saturé ;
Saint-Hilaire, 1 756 m, est sec et plus doux ; l'infrarouge donne 1 495 m). AROME sous-estime la nappe d'environ 500 m cette nuit-là.

## Neige (`neige.py`)

Le fond de carte est l'image Sentinel-2 du 22/07/2026 (sans nuages, sans neige saisonnière). La neige du moment vient
des images Meteosat MTG de jour : neige = brillante dans le visible (0,6 µm) et sombre à 2,2 µm (indice NDSI > 0,4) ;
nuage d'eau = brillant dans les deux, laissé inconnu. La fraction enneigée d'un pixel de 500 m est posée sur la partie la
plus haute du relief qu'il couvre. Composite `web/data/neige.png` : dernière observation sans nuage de chaque point, images
à ± 2 h 30 du midi solaire, maximum du jour. 31/10-01/11/2026 : environ 50-65 km² enneigés (glaciers des Grandes Rousses et
des Écrins), limite d'enneigement vers 3 100-3 400 m. S'y ajoute la fraction enneigée Sentinel-2 à 20 m de Theia
(LIS FSC, collection `LIS_FSC_PREOP` sur hydroweb.next, clé `HYDROWEB_API_KEY`, étape `pipeline.py lis` au plus toutes
les 6 h). Elle est moyennée à 100 m ; nuages (205) et zones sans donnée (255) sont ignorés, ainsi que les fichiers
`-QCFLAGS`. Fusion point par point : l'observation la plus récente l'emporte ; le même jour, LIS est prioritaire sur
Meteosat. La source de chaque point est dans le canal alpha de `neige.png` (255 LIS, 254 Meteosat, 253 aucune).
Au 01/11/2026 : 20 produits LIS (22-29/10), qui renseignent 7 % de la zone restée sous la mer de nuages pour Meteosat.

## Situation : mer de nuages ou pas ? (`situation.py`)

Une image où l'on trouve des « bords » de nuage n'est pas forcément une mer de nuages. Deux diagnostics indépendants :

- **Satellite.** On calcule la part du relief couverte au-dessus de H + 300 m et au-dessous de H − 300 m :
  - mer de nuages : moins de 15 % au-dessus ;
  - nappe qui se dégrade : 15 à 35 % ;
  - disloquée : plus de 35 % au-dessus, ou moins de 45 % au-dessous ;
  - couvert : plus de 85 % de toute la zone couverte ;
  - pas de nuages bas : moins de 8 % couvert.

  Seules les deux premières situations donnent une altitude.
- **Masse d'air (AROME).** Décroissance de la température entre le fond de vallée et environ 2 000 m (stable si ≤ 4 °C/km
  ou en cas d'inversion, instable si ≥ 6 °C/km), vent à 850 hPa (gêne à partir de 25 km/h, fort à partir de 40 km/h)
  et pluie. Le vent ne compte que si l'air n'est pas stable : au-dessus d'une inversion, la nuit du 31/10 au 01/11,
  un vent de 27 à 41 km/h a laissé la nappe intacte. Résultat : favorable, limite ou défavorable.

Cas du 01/11/2026 : la nappe monte de 1 620 à 2 085 m dans la matinée, puis se disloque avec le vent du nord.

| Heure UTC | Couvert au-dessus de H | Situation (satellite) | Masse d'air (AROME) |
|---|---|---|---|
| 8 h 08 - 11 h 08 | 4-13 % | mer de nuages | favorable (≤ 10 h), limite (11 h) |
| 11 h 38 - 13 h 08 | 18-27 % | se dégrade | limite (gradient 4,5-5,7 °C/km) |
| 13 h 38 - 15 h 08 | 45-52 % | disloquée | défavorable (6,2-7 °C/km) |

Le 31/10 (mer de nuages nette), toutes les images sont classées « mer de nuages », avec 0 à 7 % couvert au-dessus,
et l'air est favorable. Ces seuils reposent sur ces deux journées seulement et restent à confirmer (été, pluie,
ciel clair). Après un changement de seuils, `python3 pipeline.py reclasser` recalcule toutes les analyses publiées.

Webapp : l'encadré affiche la dernière image si elle a moins de 90 min. Sinon, il affiche la médiane des mesures
du même régime sur 3 h au plus, ou à défaut la prévision AROME. La nappe simulée n'est affichée que s'il y a une mer
de nuages ; sinon, c'est le nuage observé par satellite qui s'affiche.

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
