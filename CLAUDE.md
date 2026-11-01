# Consignes pour Claude

- Après chaque fusion (merge) sur `main`, lancer aussitôt le workflow « Mer de nuages — mise à jour »
  (`.github/workflows/pipeline.yml`, `workflow_dispatch` sur `main`) pour publier le site,
  puis vérifier que l'exécution se termine avec succès. Le workflow ne se déclenche pas sur un push.
- Le bot du workflow pousse des commits « Données … » sur `main` : récupérer `origin/main` avant de fusionner.
- Le site publié est https://riderfou.github.io/cloud9/ (source GitHub Pages : GitHub Actions).
- Fusionner sans changer de branche ni `reset --hard` (qui efface les modifications non commitées) :
  tout commiter, puis `git fetch origin main && git merge origin/main && git push origin HEAD:main`.
- Ne pas pousser sur `main` pendant qu'une exécution du workflow est en cours (son push serait refusé).
- Interface : toute couleur, taille ou durée passe par les tokens de `web/ds/tokens.css` (design system
  « Grelou », doc dans `docs/design-system/README.md`) ; pas de couleur en dur dans les pages. Après une
  modification des tokens, lancer `python3 tools/verif_couleurs.py --rapport docs/design-system/verif-couleurs.md
  --planche docs/design-system/planche-daltonisme.svg` (contrastes WCAG et daltonisme) et corriger tout échec.
