# Design system « Grelou »

Le petit design system de **Mer de nuages**. Il est montagnard, outdoor et grenoblois, et reste rigoureux sur
l'accessibilité. Tout est dans le dépôt : il n'y a pas de page de référence publiée.

| Fichier | Rôle |
|---|---|
| [`web/ds/tokens.css`](../../web/ds/tokens.css) | Tokens : palette, rôles sémantiques (clair et sombre), codes de l'application, typographie, espaces, formes, mouvement |
| [`web/ds/components.css`](../../web/ds/components.css) | Composants génériques, préfixés `.ds-` |
| [`web/ds/theme.js`](../../web/ds/theme.js) | Thème automatique, clair ou sombre, et bouton pour basculer |
| [`web/ds/fonts/`](../../web/ds/fonts/) | Barlow et Barlow Semi Condensed, hébergées dans le dépôt (licence OFL) |
| [`tools/verif_couleurs.py`](../../tools/verif_couleurs.py) | Vérification des contrastes WCAG et du daltonisme |
| [`verif-couleurs.md`](verif-couleurs.md) | Dernier rapport de vérification (généré) |
| [`planche-daltonisme.svg`](planche-daltonisme.svg) | Toutes les couleurs à distinguer, dans les cinq visions simulées (générée) |
| [`../audit-ux-ui.md`](../audit-ux-ui.md) | Audit UX/UI qui a conduit à ce système |

Ordre de chargement d'une page :

```html
<link rel="stylesheet" href="ds/tokens.css">
<link rel="stylesheet" href="ds/components.css">
<link rel="stylesheet" href="style.css">        <!-- mise en page propre à la page -->
<script src="ds/theme.js"></script>             <!-- dans <head>, sans defer : évite le flash de thème -->
```

---

## 1. Principes

1. **La réponse d'abord.** On vient pour une question : y a-t-il une mer de nuages, et où faut-il monter pour
   être au soleil ? L'état et l'altitude sont toujours le premier élément vu, sur ordinateur comme sur téléphone
   (résumé flottant sur la carte).
2. **La couleur n'est jamais seule.** Chaque code couleur est doublé d'un texte, d'un pictogramme (☀ ≈ ☁) ou d'une
   forme (ligne ou points). La palette est vérifiée par un script, pas à l'œil.
3. **Honnête sur la donnée.** Les valeurs sont expérimentales. On affiche l'incertitude (±), la source, l'âge de la
   mesure, et on distingue une mesure d'une prévision (« ≈ », couleur AROME).
4. **Montagne, pas gadget.** L'identité vient de la palette (ardoise, ciel, chartreuse, balise), de la typographie
   condensée qui rappelle les panneaux de sentier, et du ton. Pas de décor inutile par-dessus la carte.
5. **Un seul endroit pour chaque décision.** Une couleur, une taille ou une durée se définit dans
   `tokens.css`, puis se consomme partout par `var(--…)`. Aucune valeur hexadécimale dans les pages, sauf
   exception documentée (voir § 7).

---

## 2. Tokens

Il y a trois niveaux. On ne consomme les primitives directement que pour une raison précise, comme le logo ou
l'échelle du vent.

### 2.1 Primitives : la palette du pays grenoblois

| Famille | Inspiration | Usage principal |
|---|---|---|
| `--ardoise-0…950` | La pierre des toits et des falaises du Vercors | Neutres : surfaces, textes, bordures |
| `--ciel-50…900` | Le bleu d'altitude au-dessus de la nappe | Couleur de marque, actions, série AROME |
| `--chartreuse-200…800` | La liqueur et le massif | Accent de marque : logo, sélection de texte |
| `--soleil-100…800` | L'or des crêtes au soleil | Avertissement (« au bord », « air limite »), webcams au soleil |
| `--balise-100…800` | L'orange-rouge du balisage des sentiers | Série satellite, erreurs, aiguille de la boussole |
| `--sapin-100…800` | Les forêts de Chartreuse | Positif (« mer de nuages », « au soleil », « air favorable ») |
| `--brume-100…800` | Le gris-bleu du dessous de la nappe | Information neutre (« dans la nappe », « pas de mer de nuages ») |

### 2.2 Sémantiques : un rôle, deux thèmes

Chaque token sémantique est écrit avec `light-dark(clair, sombre)`. Le navigateur choisit selon `color-scheme`,
lui-même piloté par `data-theme` sur `<html>` ou, à défaut, par le réglage du système.

| Token | Rôle |
|---|---|
| `--surface-0` / `-1` / `-2` / `-3` | Fond de page, panneau, carte posée, enfoncé ou survol |
| `--surface-raised` | Fenêtre, infobulle, bouton |
| `--border`, `--border-strong`, `--control-off` | Séparateurs ; contour d'un contrôle inactif (contraste 3:1 garanti) |
| `--text-primary` / `-secondary` / `-muted` | Trois niveaux de texte, tous à 4,5:1 au minimum sur toutes les surfaces |
| `--text-on-accent` | Texte posé sur `--accent` |
| `--accent`, `--accent-hover`, `--accent-soft` | Liens, bouton principal, interrupteur allumé, ligne sélectionnée |
| `--focus-ring` | Anneau de focus clavier |
| `--marque`, `--marque-texte` | Chartreuse et texte posé dessus |
| `--good`, `--warn`, `--info`, `--danger` (+ `-bg`, `-solid`) | Tons d'état : texte, fond de pastille, aplat |

### 2.3 Domaine : les codes de l'application

Ces codes font partie du système. On les change ici, puis on relance la vérification.

| Code | Tokens | Sens | Doublé par |
|---|---|---|---|
| État « en ce moment » | `--etat-mer`, `--etat-alerte`, `--etat-absente`, `--etat-prevision` | Mer de nuages nette, nappe qui se dégrade, pas de mer, prévision faute d'image | Texte du statut, liseré de la carte d'état |
| Position d'un lieu | `--pos-dessus`, `--pos-bord`, `--pos-dessous` (+ `-bg`) | Au soleil, au bord, dans la nappe | ☀ ≈ ☁ et libellé |
| Masse d'air | tons `good` / `warn` / `info` | Favorable, limite, défavorable | Libellé « Air … » et raisons |
| Graphique | `--series-arome` (bleu), `--series-satellite` (orange) | Prévision et mesure | Ligne et points ; paire bleu/orange sûre pour les daltoniens |
| Graphique (fond) | `--chart-air-defav`, `--chart-air-limite`, `--chart-grid` | Heures où l'air est défavorable ou limite | Légende et infobulle |
| Vent | `--vent-0` à `--vent-6` | 0, 10, 20, 35, 55, 70 et 100 km/h | Graduations ; luminosité croissante (voir § 5) |
| Carte | `--map-label-*`, `--map-pin*` | Étiquettes et pastilles posées sur l'image satellite | Étiquette grisée sous la nappe, pictogramme caméra |
| Scène 3D | `--scene-ciel-*`, `--scene-brume` | Ciel de jour ou de crépuscule ; brume lue par `app.js` | — |

`app.js` lit ces couleurs à l'exécution avec `couleurToken("scene-brume")`, qui renvoie la valeur résolue pour le
thème affiché. La brume de la scène se met à jour à chaque événement `themechange`.

### 2.4 Typographie

| Token | Valeur | Usage |
|---|---|---|
| `--font-sans` | Barlow | Tout le texte courant |
| `--font-display` | Barlow Semi Condensed | Titres, grands chiffres, sur-titres : l'esprit des panneaux de sentier |
| `--text-2xs` … `--text-3xl` | 11 · 12 · 13 · 14 · 16 · 20 · 26 · 34 px | Échelle ; corps de texte à 14 px |
| `--text-display` | 60 px (54 px sur téléphone) | L'altitude du sommet de la nappe |
| `--leading-*`, `--tracking-*` | | Interlignage, approche des grands chiffres et des sur-titres |

Les chiffres sont toujours en `font-variant-numeric: tabular-nums` (classe `.ds-num`), pour que les altitudes
restent alignées et ne « sautent » pas quand elles changent.

### 2.5 Espaces, formes, profondeur, mouvement

- Espaces sur une base de 4 px : `--space-1` (4) à `--space-12` (48).
- Rayons : `--radius-xs` (4) à `--radius-xl` (22), `--radius-pill`.
- Tailles : `--control-h` 36 px ; `--tap-min` 44 px (cible tactile des lignes de réglage) ; `--panel-w` 400 px.
- Ombres : `--shadow-1` (posé), `-2` (flottant), `-3` (fenêtre), `--shadow-map` (sur la carte).
- Mouvement : `--dur-fast` 120 ms, `--dur-base` 200 ms, `--dur-slow` 420 ms, `--ease-out`. Avec
  `prefers-reduced-motion`, les durées tombent à 0 ; l'application coupe aussi le vent animé par défaut, le
  glissé de la caméra et la dérive de la nappe.
- Profondeur : `--z-labels`, `--z-map-ui`, `--z-sticky`, `--z-tooltip`, `--z-overlay`.

---

## 3. Composants

Tous dans `components.css`. Un composant ne lit que des tokens.

| Classe | Description | Notes d'accessibilité |
|---|---|---|
| `.ds-display`, `.ds-title`, `.ds-eyebrow`, `.ds-note`, `.ds-prose` | Styles de texte | `.ds-eyebrow` sert aux titres de section (`<h2>`) |
| `.ds-card` (`--outline`) | Carte posée | |
| `.ds-btn` (`--primary`, `--sm`, `--text`) | Bouton en forme de pilule | `:disabled` et `aria-disabled` stylés |
| `.ds-icon-btn` (`--map`) | Bouton rond à pictogramme, 40 px | `aria-label` obligatoire |
| `.ds-chip[data-tone]` | Pastille `good` · `warn` · `info` · `danger` · `accent` | Toujours avec un libellé, souvent un pictogramme |
| `.ds-dot` (`--live`) | Point d'état, qui pulse quand la mesure est en direct | `aria-hidden` ; animation coupée si mouvement réduit |
| `.ds-switch` | Interrupteur : une vraie `<input type="checkbox">` stylée | Garde la sémantique native, focus visible |
| `.ds-toggle` | Ligne de réglage : pictogramme, libellé, sous-libellé, interrupteur | Toute la ligne est cliquable, 44 px de haut |
| `.ds-segmented` | Choix exclusif en pilule : de vraies radios | Mettre `role="radiogroup"` et `aria-label` sur le conteneur |
| `.ds-range` | Curseur ; remplissage par `--pct` | Valeur annoncée par `<output for>` ; repère de la mesure via `<datalist>` |
| `.ds-list` | Liste à lignes séparées ; `.ds-list-fin` pour la valeur à droite | |
| `.ds-table` | Tableau ; une ligne cliquable a `tabindex="0"` et la ligne choisie `aria-current="true"` | Entrée et Espace activent la ligne |
| `.ds-disclosure` | `<details>` / `<summary>` stylé | Natif : clavier et lecteurs d'écran |
| `.ds-dialog` | `<dialog>` modal, fond flouté | `aria-labelledby`, fermeture par Échap native |
| `.ds-tooltip` | Infobulle flottante | `role="tooltip"` |
| `.ds-legend`, `.ds-swatch--line/dot/ring/band` | Légendes de graphique | `--c` change la couleur d'un échantillon |
| `.ds-callout[data-tone]` | Message encadré | |
| `.ds-logo` | Logo carré arrondi | `alt=""` à côté d'un titre |
| `.ds-sr-only` | Texte réservé aux lecteurs d'écran | |

### Exemples

```html
<!-- ligne de réglage avec interrupteur -->
<label class="ds-toggle">
  <svg class="ds-toggle-ico" viewBox="0 0 24 24" aria-hidden="true">…</svg>
  <span class="ds-toggle-txt">Nuages observés<small>image satellite</small></span>
  <input type="checkbox" class="ds-switch" id="t-obs" checked>
</label>

<!-- pastille de position : couleur + pictogramme + texte -->
<span class="ds-chip" data-tone="good">☀ au soleil</span>

<!-- choix segmenté -->
<div class="ds-segmented" role="radiogroup" aria-label="Altitude du vent">
  <label><input type="radio" name="niveau" value="sol" checked><span>Au sol</span></label>
  <label><input type="radio" name="niveau" value="1500m"><span>À 1 500 m</span></label>
</div>

<!-- bouton de thème (rempli par theme.js) -->
<button class="ds-icon-btn" type="button" data-theme-toggle aria-label="Changer de thème"></button>
```

---

## 4. Thème clair, sombre, automatique

- Par défaut, le thème suit le réglage de l'appareil.
- Un bouton `[data-theme-toggle]`, en haut du panneau et de l'éditeur, fait tourner les modes
  **automatique → clair → sombre**. Le pictogramme et l'`aria-label` indiquent le mode actuel et le suivant.
- Le choix est mémorisé dans le navigateur (`localStorage`, clé `mdn-theme`), sans erreur en navigation privée.
- `theme.js` pose `data-theme` avant le premier rendu : la page ne s'affiche jamais d'abord dans le mauvais thème.
- Il émet l'événement `themechange`, qu'il s'agisse d'un choix de l'utilisateur ou d'un changement du système. Il
  met aussi à jour `theme-color`, la couleur de la barre du navigateur mobile, qui prend celle du ciel de la scène.
- En sombre, la scène 3D passe au crépuscule (ciel et brume). Les étiquettes posées sur l'image satellite restent
  claires dans les deux thèmes, puisque l'image elle-même ne change pas.

---

## 5. Daltonisme et contrastes : la règle

```bash
python3 tools/verif_couleurs.py --rapport docs/design-system/verif-couleurs.md --planche docs/design-system/planche-daltonisme.svg
```

À relancer **après chaque modification de `tokens.css`**. Le code de sortie vaut 1 en cas d'échec, ce qui
permet de l'utiliser en CI. Le script lit les tokens directement : il n'y a pas de copie des valeurs à maintenir.

Ce qu'il vérifie, dans les deux thèmes :

1. **Texte à 4,5:1** (WCAG 1.4.3) sur toutes les surfaces où il apparaît, y compris les étiquettes de la carte
   composées sur le pire fond (forêt sombre ou neige).
2. **Éléments graphiques à 3:1** (WCAG 1.4.11) : séries du graphique, anneau de focus, interrupteurs, pastilles
   d'état.
3. **Distinction en vision simulée.** Simulation de Machado et al. (2009), sévérité maximale, pour la protanopie,
   la deutéranopie et la tritanopie, plus l'achromatopsie. L'écart se mesure en OKLab × 100. Seuils :
   10 quand la couleur porte seule l'information (pastilles de webcam sur la carte) ; 4 quand elle est doublée d'un
   autre indice. Dans ce second cas, l'achromatopsie est affichée mais non exigée.
4. **Échelle du vent** : luminosité strictement croissante, avec au moins 6 d'écart entre deux paliers, dans les
   cinq visions. L'ancienne échelle arc-en-ciel, reprise de Windy, mettait côte à côte des verts et des rouges
   de même clarté : elle a été remplacée par une échelle de type « plasma » optimisée (indigo → violet → prune →
   brique → saumon → or → jaune).

Résultat actuel : **tout est conforme**, avec 0 échec. Voir [`verif-couleurs.md`](verif-couleurs.md) et
[`planche-daltonisme.svg`](planche-daltonisme.svg).

---

## 6. Ton et microcopie : « grelou », mais fiable

- On tutoie la montagne, pas l'utilisateur : le ton est direct et chaleureux, sans familiarité forcée.
  Le vouvoiement est conservé dans les consignes.
- Des formulations concrètes et utiles plutôt que techniques : « Au soleil au-dessus de 1 350 m environ : Mont
  Saint-Eynard, Charmant Som… », « Qui est au soleil ? », « au soleil · au bord · dans la nappe ».
- Un clin d'œil local, à petite dose : « On monte au-dessus des nuages… » au chargement, « Fait à Grenoble, entre
  Chartreuse, Vercors et Belledonne. » en pied de page. Le logo dessine la Dent de Crolles.
- Toujours la source et l'âge : « Sommet mesuré par Meteosat à 13:08 (il y a 25 min) ». Jamais un tiret seul à la
  place d'une valeur : à défaut d'altitude, on donne un titre explicite (« Nappe disloquée », « Ciel couvert »).
- Les messages d'erreur disent quoi faire : « Impossible de charger les données. Vérifiez la connexion, puis
  réessayez. » avec un bouton **Réessayer**.
- Nombres au format français (`Intl.NumberFormat("fr-FR")`, espace fine pour les milliers), unités séparées par
  une espace : `1 290 m`, `± 72 m`, `16 km/h`.

---

## 7. Exceptions assumées

- **Étiquettes et pastilles de la carte** : couleurs fixes, quel que soit le thème, parce qu'elles sont posées
  sur l'image satellite, qui ne change pas. Elles ont leurs propres tokens (`--map-*`) et sont vérifiées sur fond
  de forêt et de neige.
- **Webcam « au soleil » en or** (`--map-pin-dessus`) alors que « au soleil » est vert (`--pos-dessus`) dans le
  panneau : une pastille verte disparaîtrait sur la forêt. Le pictogramme et la légende des listes lèvent
  l'ambiguïté.
- **Logo, `favicon.svg` et couleurs Leaflet** dans l'éditeur : valeurs hexadécimales recopiées des primitives,
  puisqu'un SVG statique ou une option JavaScript ne peut pas lire une variable CSS. Elles sont commentées comme
  telles.
- **Bandes de masse d'air** : faible contraste volontaire (ce sont des fonds). Elles restent distinctes entre elles
  et de la surface en vision simulée, et sont nommées dans la légende et l'infobulle.

---

## 8. Ajouter ou modifier

1. Besoin d'une couleur : chercher d'abord un token sémantique existant. Sinon, ajouter un token sémantique ou de
   domaine dans `tokens.css`, au bon niveau, avec ses valeurs claire et sombre.
2. S'il doit se distinguer d'autres couleurs, l'ajouter aux listes `TEXTE`, `GRAPHIQUE` ou `DISTINCTS` de
   `tools/verif_couleurs.py`.
3. Relancer le script, puis régénérer le rapport et la planche.
4. Nouveau composant : le préfixer `.ds-`, n'y utiliser que des tokens, et le documenter au § 3 avec ses règles
   d'accessibilité.
5. Vérifier le résultat en clair, en sombre, sur téléphone (390 px) et au clavier seul.
