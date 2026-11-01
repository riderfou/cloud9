# Vérification des couleurs — design system « Grelou »

Rapport produit par `python3 tools/verif_couleurs.py --rapport docs/design-system/verif-couleurs.md` à partir de `web/ds/tokens.css`. Ne pas modifier à la main.

- Contrastes : WCAG 2.2 niveau AA.
- Daltonisme : simulation Machado et al. (2009), sévérité maximale ; achromatopsie = luminance seule.
- Écarts en OKLab × 100 (≈ 2 = à peine perceptible). Seuil 10 si la couleur porte seule l'information, 4 si elle est doublée d'une forme, d'un pictogramme ou d'un texte (dans ce cas l'achromatopsie est affichée mais non exigée).
- Couleurs semi-transparentes : composées sur le panneau, ou sur une forêt sombre pour la carte.

**Résultat : tout est conforme ✅**

# Thème clair


## Contraste du texte (WCAG 1.4.3, 4,5:1)

| Usage | Couleurs | Contraste |  |
|---|---|---|---|
| texte courant | `text-primary` sur `surface-1` | 17.76:1 | ✅ |
| texte dans une carte | `text-primary` sur `surface-2` | 16.81:1 | ✅ |
| texte secondaire | `text-secondary` sur `surface-1` | 9.58:1 | ✅ |
| texte secondaire dans une carte | `text-secondary` sur `surface-2` | 9.07:1 | ✅ |
| notes, légendes | `text-muted` sur `surface-1` | 5.85:1 | ✅ |
| notes dans une carte | `text-muted` sur `surface-2` | 5.54:1 | ✅ |
| notes sur un survol | `text-muted` sur `surface-3` | 5.09:1 | ✅ |
| infobulle, fenêtre | `text-secondary` sur `surface-raised` | 10.03:1 | ✅ |
| liens | `accent` sur `surface-1` | 6.20:1 | ✅ |
| liens dans une carte | `accent` sur `surface-2` | 5.87:1 | ✅ |
| élément sélectionné | `accent` sur `accent-soft` | 5.90:1 | ✅ |
| bouton principal | `text-on-accent` sur `accent` | 6.49:1 | ✅ |
| touche de marque (Chartreuse) | `marque-texte` sur `marque` | 12.14:1 | ✅ |
| pastille « au-dessus », « air favorable » | `good` sur `good-bg` | 6.73:1 | ✅ |
| pastille « au bord », « air limite » | `warn` sur `warn-bg` | 5.11:1 | ✅ |
| pastille « dessous », « air défavorable » | `info` sur `info-bg` | 6.28:1 | ✅ |
| message d'erreur | `danger` sur `danger-bg` | 6.25:1 | ✅ |
| statut « mer de nuages » | `good` sur `surface-2` | 7.20:1 | ✅ |
| statut « se dégrade » | `warn` sur `surface-2` | 5.23:1 | ✅ |
| statut « pas de mer de nuages » | `info` sur `surface-2` | 8.20:1 | ✅ |
| étiquette de carte (pire cas : forêt) | `map-label-fg` sur `map-label-bg` | 15.56:1 | ✅ |
| étiquette de carte (pire cas : forêt) | `map-label-sub` sur `map-label-bg` | 5.79:1 | ✅ |
| étiquette de carte (pire cas : forêt) | `map-label-fg` sur `map-label-bg-r2` | 12.43:1 | ✅ |
| étiquette de carte (pire cas : forêt) | `map-label-dessous-fg` sur `map-label-dessous-bg` | 4.77:1 | ✅ |
| étiquette de carte (pire cas : forêt) | `map-label-fg` sur `map-label-bord-bg` | 13.07:1 | ✅ |
| étiquette de carte (pire cas : neige) | `ardoise-0` sur `map-label-mesure-bg` | 4.85:1 | ✅ |

## Contraste des éléments graphiques (WCAG 1.4.11, 3:1)

| Usage | Couleurs | Contraste |  |
|---|---|---|---|
| ligne AROME | `series-arome` sur `surface-1` | 4.40:1 | ✅ |
| points satellite | `series-satellite` sur `surface-1` | 3.56:1 | ✅ |
| anneau de focus | `focus-ring` sur `surface-1` | 4.40:1 | ✅ |
| anneau de focus dans une carte | `focus-ring` sur `surface-2` | 4.17:1 | ✅ |
| interrupteur éteint | `control-off` sur `surface-1` | 4.42:1 | ✅ |
| interrupteur éteint dans une carte | `control-off` sur `surface-2` | 4.19:1 | ✅ |
| interrupteur allumé, curseur | `accent` sur `surface-2` | 5.87:1 | ✅ |
| pastille d'état « mer » | `good` sur `surface-2` | 7.20:1 | ✅ |
| pastille d'état « dégradée » | `warn` sur `surface-2` | 5.23:1 | ✅ |
| pastille d'état « absente » | `info` sur `surface-2` | 8.20:1 | ✅ |
| marqueur « pas de mer de nuages » | `text-muted` sur `surface-1` | 5.85:1 | ✅ |

## Couleurs à distinguer, vision simulée (ΔE OKLab × 100)

| Groupe | Paire | normale · protan · deutan · tritan · achroma | Pire cas | Seuil |  |
|---|---|---|---|---|---|
| Graphique : AROME / satellite | `series-arome` / `series-satellite` | 32 · 23 · 29 · 33 · 5 | 23.0 (protanopie) | ≥ 4 (ligne / points) | ✅ |
| Statut de la carte « en ce moment » | `good` / `warn` | 16 · 7 · 12 · 19 · 7 | 6.6 (protanopie) | ≥ 4 (texte du statut) | ✅ |
| Statut de la carte « en ce moment » | `good` / `info` | 10 · 9 · 8 · 5 · 3 | 4.5 (tritanopie) | ≥ 4 (texte du statut) | ✅ |
| Statut de la carte « en ce moment » | `good` / `series-arome` | 23 · 23 · 22 · 16 · 13 | 16.1 (tritanopie) | ≥ 4 (texte du statut) | ✅ |
| Statut de la carte « en ce moment » | `warn` / `info` | 18 · 15 · 19 · 18 · 10 | 15.3 (protanopie) | ≥ 4 (texte du statut) | ✅ |
| Statut de la carte « en ce moment » | `warn` / `series-arome` | 26 · 25 · 26 · 21 · 5 | 20.6 (tritanopie) | ≥ 4 (texte du statut) | ✅ |
| Statut de la carte « en ce moment » | `info` / `series-arome` | 19 · 21 · 19 · 19 · 16 | 18.6 (deutéranopie) | ≥ 4 (texte du statut) | ✅ |
| Pastilles de position (fond) | `good-bg` / `warn-bg` | 5 · 4 · 5 · 5 · 1 | 4.0 (protanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Pastilles de position (fond) | `good-bg` / `info-bg` | 7 · 7 · 7 · 6 · 6 | 6.2 (tritanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Pastilles de position (fond) | `warn-bg` / `info-bg` | 11 · 10 · 12 · 9 · 8 | 8.7 (tritanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Pastilles de position (texte) | `good` / `warn` | 16 · 7 · 12 · 19 · 7 | 6.6 (protanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Pastilles de position (texte) | `good` / `info` | 10 · 9 · 8 · 5 · 3 | 4.5 (tritanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Pastilles de position (texte) | `warn` / `info` | 18 · 15 · 19 · 18 · 10 | 15.3 (protanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Webcams sur la carte | `map-pin` / `map-pin-dessus` | 54 · 50 · 55 · 52 · 51 | 49.6 (protanopie) | ≥ 10 | ✅ |
| Webcams sur la carte | `map-pin` / `map-pin-dessous` | 26 · 27 · 26 · 26 · 26 | 25.6 (achromatopsie) | ≥ 10 | ✅ |
| Webcams sur la carte | `map-pin-dessus` / `map-pin-dessous` | 33 · 29 · 34 · 30 · 25 | 25.1 (achromatopsie) | ≥ 10 | ✅ |
| Étiquettes de la carte | `map-label-bg` / `map-label-dessous-bg` | 17 · 16 · 17 · 17 · 17 | 16.3 (protanopie) | ≥ 4 (texte grisé sous la nappe) | ✅ |
| Étiquettes de la carte | `map-label-bg` / `map-label-bord-bg` | 11 · 13 · 11 · 8 · 6 | 8.3 (tritanopie) | ≥ 4 (texte grisé sous la nappe) | ✅ |
| Étiquettes de la carte | `map-label-dessous-bg` / `map-label-bord-bg` | 15 · 14 · 16 · 13 · 11 | 13.5 (tritanopie) | ≥ 4 (texte grisé sous la nappe) | ✅ |
| Graphique : bandes de masse d'air | `chart-air-defav` / `chart-air-limite` | 5 · 5 · 5 · 5 · 5 | 5.2 (protanopie) | ≥ 4 (légende + infobulle) | ✅ |
| Graphique : bandes de masse d'air | `chart-air-defav` / `surface-1` | 10 · 9 · 10 · 10 · 10 | 9.4 (protanopie) | ≥ 4 (légende + infobulle) | ✅ |
| Graphique : bandes de masse d'air | `chart-air-limite` / `surface-1` | 4 · 4 · 4 · 4 · 4 | 4.2 (protanopie) | ≥ 4 (légende + infobulle) | ✅ |

## Échelle du vent : luminosité croissante (L OKLab × 100)

| Vision | Luminosité des 7 paliers | Écart mini entre paliers |  |
|---|---|---|---|
| normale | 22 → 37 → 48 → 60 → 71 → 81 → 94 | 11.6 | ✅ |
| protanopie | 25 → 37 → 45 → 54 → 66 → 79 → 92 | 11.6 | ✅ |
| deutéranopie | 23 → 37 → 48 → 61 → 72 → 82 → 94 | 11.7 | ✅ |
| tritanopie | 23 → 37 → 48 → 60 → 72 → 82 → 93 | 11.5 | ✅ |
| achromatopsie | 21 → 35 → 47 → 58 → 70 → 81 → 94 | 11.5 | ✅ |

# Thème sombre


## Contraste du texte (WCAG 1.4.3, 4,5:1)

| Usage | Couleurs | Contraste |  |
|---|---|---|---|
| texte courant | `text-primary` sur `surface-1` | 15.01:1 | ✅ |
| texte dans une carte | `text-primary` sur `surface-2` | 13.38:1 | ✅ |
| texte secondaire | `text-secondary` sur `surface-1` | 12.31:1 | ✅ |
| texte secondaire dans une carte | `text-secondary` sur `surface-2` | 10.98:1 | ✅ |
| notes, légendes | `text-muted` sur `surface-1` | 6.14:1 | ✅ |
| notes dans une carte | `text-muted` sur `surface-2` | 5.48:1 | ✅ |
| notes sur un survol | `text-muted` sur `surface-3` | 4.85:1 | ✅ |
| infobulle, fenêtre | `text-secondary` sur `surface-raised` | 10.98:1 | ✅ |
| liens | `accent` sur `surface-1` | 7.69:1 | ✅ |
| liens dans une carte | `accent` sur `surface-2` | 6.86:1 | ✅ |
| élément sélectionné | `accent` sur `accent-soft` | 6.05:1 | ✅ |
| bouton principal | `text-on-accent` sur `accent` | 8.37:1 | ✅ |
| touche de marque (Chartreuse) | `marque-texte` sur `marque` | 12.14:1 | ✅ |
| pastille « au-dessus », « air favorable » | `good` sur `good-bg` | 7.45:1 | ✅ |
| pastille « au bord », « air limite » | `warn` sur `warn-bg` | 7.41:1 | ✅ |
| pastille « dessous », « air défavorable » | `info` sur `info-bg` | 7.42:1 | ✅ |
| message d'erreur | `danger` sur `danger-bg` | 7.11:1 | ✅ |
| statut « mer de nuages » | `good` sur `surface-2` | 7.93:1 | ✅ |
| statut « se dégrade » | `warn` sur `surface-2` | 10.26:1 | ✅ |
| statut « pas de mer de nuages » | `info` sur `surface-2` | 10.57:1 | ✅ |
| étiquette de carte (pire cas : forêt) | `map-label-fg` sur `map-label-bg` | 15.56:1 | ✅ |
| étiquette de carte (pire cas : forêt) | `map-label-sub` sur `map-label-bg` | 5.79:1 | ✅ |
| étiquette de carte (pire cas : forêt) | `map-label-fg` sur `map-label-bg-r2` | 12.43:1 | ✅ |
| étiquette de carte (pire cas : forêt) | `map-label-dessous-fg` sur `map-label-dessous-bg` | 4.77:1 | ✅ |
| étiquette de carte (pire cas : forêt) | `map-label-fg` sur `map-label-bord-bg` | 13.07:1 | ✅ |
| étiquette de carte (pire cas : neige) | `ardoise-0` sur `map-label-mesure-bg` | 4.85:1 | ✅ |

## Contraste des éléments graphiques (WCAG 1.4.11, 3:1)

| Usage | Couleurs | Contraste |  |
|---|---|---|---|
| ligne AROME | `series-arome` sur `surface-1` | 5.30:1 | ✅ |
| points satellite | `series-satellite` sur `surface-1` | 6.02:1 | ✅ |
| anneau de focus | `focus-ring` sur `surface-1` | 7.69:1 | ✅ |
| anneau de focus dans une carte | `focus-ring` sur `surface-2` | 6.86:1 | ✅ |
| interrupteur éteint | `control-off` sur `surface-1` | 4.55:1 | ✅ |
| interrupteur éteint dans une carte | `control-off` sur `surface-2` | 4.06:1 | ✅ |
| interrupteur allumé, curseur | `accent` sur `surface-2` | 6.86:1 | ✅ |
| pastille d'état « mer » | `good` sur `surface-2` | 7.93:1 | ✅ |
| pastille d'état « dégradée » | `warn` sur `surface-2` | 10.26:1 | ✅ |
| pastille d'état « absente » | `info` sur `surface-2` | 10.57:1 | ✅ |
| marqueur « pas de mer de nuages » | `text-muted` sur `surface-1` | 6.14:1 | ✅ |

## Couleurs à distinguer, vision simulée (ΔE OKLab × 100)

| Groupe | Paire | normale · protan · deutan · tritan · achroma | Pire cas | Seuil |  |
|---|---|---|---|---|---|
| Graphique : AROME / satellite | `series-arome` / `series-satellite` | 29 · 21 · 26 · 31 · 3 | 21.3 (protanopie) | ≥ 4 (ligne / points) | ✅ |
| Statut de la carte « en ce moment » | `good` / `warn` | 17 · 10 · 15 · 18 · 8 | 10.1 (protanopie) | ≥ 4 (texte du statut) | ✅ |
| Statut de la carte « en ce moment » | `good` / `info` | 15 · 11 · 11 · 12 · 9 | 10.7 (protanopie) | ≥ 4 (texte du statut) | ✅ |
| Statut de la carte « en ce moment » | `good` / `series-arome` | 22 · 21 · 22 · 13 · 14 | 12.8 (tritanopie) | ≥ 4 (texte du statut) | ✅ |
| Statut de la carte « en ce moment » | `warn` / `info` | 17 · 17 · 17 · 10 · 1 | 10.2 (tritanopie) | ≥ 4 (texte du statut) | ✅ |
| Statut de la carte « en ce moment » | `warn` / `series-arome` | 35 · 31 · 37 · 28 · 22 | 27.5 (tritanopie) | ≥ 4 (texte du statut) | ✅ |
| Statut de la carte « en ce moment » | `info` / `series-arome` | 25 · 23 · 27 · 24 · 23 | 22.6 (protanopie) | ≥ 4 (texte du statut) | ✅ |
| Pastilles de position (fond) | `good-bg` / `warn-bg` | 11 · 7 · 10 · 12 · 7 | 6.8 (protanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Pastilles de position (fond) | `good-bg` / `info-bg` | 10 · 10 · 9 · 8 · 8 | 8.4 (tritanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Pastilles de position (fond) | `warn-bg` / `info-bg` | 10 · 10 · 10 · 8 · 1 | 8.4 (tritanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Pastilles de position (texte) | `good` / `warn` | 17 · 10 · 15 · 18 · 8 | 10.1 (protanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Pastilles de position (texte) | `good` / `info` | 15 · 11 · 11 · 12 · 9 | 10.7 (protanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Pastilles de position (texte) | `warn` / `info` | 17 · 17 · 17 · 10 · 1 | 10.2 (tritanopie) | ≥ 4 (pictogramme ☀ ≈ ☁ + texte) | ✅ |
| Webcams sur la carte | `map-pin` / `map-pin-dessus` | 54 · 50 · 55 · 52 · 51 | 49.6 (protanopie) | ≥ 10 | ✅ |
| Webcams sur la carte | `map-pin` / `map-pin-dessous` | 26 · 27 · 26 · 26 · 26 | 25.6 (achromatopsie) | ≥ 10 | ✅ |
| Webcams sur la carte | `map-pin-dessus` / `map-pin-dessous` | 33 · 29 · 34 · 30 · 25 | 25.1 (achromatopsie) | ≥ 10 | ✅ |
| Étiquettes de la carte | `map-label-bg` / `map-label-dessous-bg` | 17 · 16 · 17 · 17 · 17 | 16.3 (protanopie) | ≥ 4 (texte grisé sous la nappe) | ✅ |
| Étiquettes de la carte | `map-label-bg` / `map-label-bord-bg` | 11 · 13 · 11 · 8 · 6 | 8.3 (tritanopie) | ≥ 4 (texte grisé sous la nappe) | ✅ |
| Étiquettes de la carte | `map-label-dessous-bg` / `map-label-bord-bg` | 15 · 14 · 16 · 13 · 11 | 13.5 (tritanopie) | ≥ 4 (texte grisé sous la nappe) | ✅ |
| Graphique : bandes de masse d'air | `chart-air-defav` / `chart-air-limite` | 6 · 6 · 6 · 6 · 6 | 6.2 (deutéranopie) | ≥ 4 (légende + infobulle) | ✅ |
| Graphique : bandes de masse d'air | `chart-air-defav` / `surface-1` | 12 · 13 · 12 · 12 · 12 | 12.0 (tritanopie) | ≥ 4 (légende + infobulle) | ✅ |
| Graphique : bandes de masse d'air | `chart-air-limite` / `surface-1` | 6 · 6 · 6 · 6 · 6 | 5.7 (tritanopie) | ≥ 4 (légende + infobulle) | ✅ |

## Échelle du vent : luminosité croissante (L OKLab × 100)

| Vision | Luminosité des 7 paliers | Écart mini entre paliers |  |
|---|---|---|---|
| normale | 22 → 37 → 48 → 60 → 71 → 81 → 94 | 11.6 | ✅ |
| protanopie | 25 → 37 → 45 → 54 → 66 → 79 → 92 | 11.6 | ✅ |
| deutéranopie | 23 → 37 → 48 → 61 → 72 → 82 → 94 | 11.7 | ✅ |
| tritanopie | 23 → 37 → 48 → 60 → 72 → 82 → 93 | 11.5 | ✅ |
| achromatopsie | 21 → 35 → 47 → 58 → 70 → 81 → 94 | 11.5 | ✅ |
