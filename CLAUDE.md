# Consignes pour Claude

- Après chaque fusion (merge) sur `main`, lancer aussitôt le workflow « Mer de nuages — mise à jour »
  (`.github/workflows/pipeline.yml`, `workflow_dispatch` sur `main`) pour publier le site,
  puis vérifier que l'exécution se termine avec succès. Le workflow ne se déclenche pas sur un push.
- Le bot du workflow pousse des commits « Données … » sur `main` : récupérer `origin/main` avant de fusionner.
- Le site publié est https://riderfou.github.io/cloud9/ (source GitHub Pages : GitHub Actions).
