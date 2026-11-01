// Mer de nuages · design system « Grelou » — thème clair / sombre / automatique.
// À charger dans <head> SANS defer ni module : l'attribut data-theme est posé avant le premier rendu
// (pas de flash de la mauvaise couleur). Les boutons [data-theme-toggle] font tourner
// automatique → clair → sombre → automatique ; le choix est mémorisé dans le navigateur.
// Événement « themechange » sur document à chaque changement (choix ou système), pour la scène 3D.
(() => {
  const CLE = "mdn-theme", racine = document.documentElement;
  const ORDRE = ["auto", "light", "dark"];
  const NOMS = { auto: "automatique (selon l'appareil)", light: "clair", dark: "sombre" };
  const ICONES = {
    auto: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/></svg>',
    light: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    dark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
  };
  const sombreSysteme = matchMedia("(prefers-color-scheme: dark)");
  const lire = () => { try { return localStorage.getItem(CLE) || "auto"; } catch (e) { return "auto"; } };
  const effectif = () => racine.dataset.theme || (sombreSysteme.matches ? "dark" : "light");

  function majBoutons() {
    const choix = lire(), suivant = ORDRE[(ORDRE.indexOf(choix) + 1) % ORDRE.length];
    for (const b of document.querySelectorAll("[data-theme-toggle]")) {
      b.innerHTML = ICONES[choix];
      b.setAttribute("aria-label", `Thème ${NOMS[choix]}. Passer au thème ${NOMS[suivant]}`);
      b.title = `Thème ${NOMS[choix]}`;
    }
  }
  function signaler() {
    // couleur de la barre du navigateur mobile : le ciel de la scène
    const m = document.querySelector('meta[name="theme-color"]');
    if (m) m.content = effectif() === "dark" ? "#0b1424" : "#4f86c2";
    document.dispatchEvent(new CustomEvent("themechange", { detail: { theme: effectif() } }));
  }
  function appliquer(choix) {
    if (choix === "light" || choix === "dark") racine.dataset.theme = choix; else delete racine.dataset.theme;
  }
  function choisir(choix) {
    try { if (choix === "auto") localStorage.removeItem(CLE); else localStorage.setItem(CLE, choix); } catch (e) { /* navigation privée */ }
    appliquer(choix); majBoutons(); signaler();
  }

  appliquer(lire());
  sombreSysteme.addEventListener("change", () => { if (lire() === "auto") signaler(); });
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-theme-toggle]");
    if (b) choisir(ORDRE[(ORDRE.indexOf(lire()) + 1) % ORDRE.length]);
  });
  const pret = () => { majBoutons(); signaler(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", pret); else pret();
  window.dsTheme = { choix: lire, effectif, choisir };
})();
