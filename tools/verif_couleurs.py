#!/usr/bin/env python3
"""Vérifie les couleurs du design system (web/ds/tokens.css), en thème clair et sombre.

1. Contrastes WCAG 2.2 : texte 4,5:1 (1.4.3), éléments graphiques et contrôles 3:1 (1.4.11).
2. Daltonisme : les couleurs qui doivent se distinguer (séries du graphique, états,
   pastilles de la carte, bandes de masse d'air) restent distinctes en vision simulée
   protanope, deutéranope, tritanope (Machado et al. 2009, sévérité maximale) et
   achromate. Écart mesuré dans l'espace perceptif OKLab (ΔE × 100).
   Seuil : 10 pour une couleur qui porte seule l'information, 4 quand elle est doublée
   d'une forme, d'un pictogramme ou d'un texte (« redondance »).
3. Échelle du vent : luminosité strictement croissante dans toutes les visions simulées.

Usage : python3 tools/verif_couleurs.py [--rapport docs/design-system/verif-couleurs.md]
                                        [--planche docs/design-system/planche-daltonisme.svg]
Code de sortie 1 si une vérification échoue.
"""
import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
TOKENS = RACINE / "web" / "ds" / "tokens.css"

# ------------------------------------------------------------------ lecture des tokens
def lire_tokens(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    bloc = css[css.index(":root {"):]
    bloc = bloc[:bloc.index("\n}")]
    return dict(re.findall(r"--([\w-]+)\s*:\s*([^;]+);", bloc))


def couleur(txt):
    txt = txt.strip()
    if txt.startswith("#"):
        h = txt[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*(?:/\s*([\d.]+))?\s*\)", txt)
    if m:
        return (int(m[1]), int(m[2]), int(m[3]), float(m[4]) if m[4] else 1.0)
    return None


def resoudre(tokens, nom, theme, pile=()):
    if nom in pile:
        raise ValueError(f"référence circulaire : {nom}")
    v = tokens[nom].strip()
    m = re.fullmatch(r"light-dark\((.*)\)", v)
    if m:
        a, b = separer(m[1])
        v = a if theme == "clair" else b
    return valeur(tokens, v, theme, pile + (nom,))


def valeur(tokens, v, theme, pile):
    v = v.strip()
    m = re.fullmatch(r"var\(--([\w-]+)\)", v)
    if m:
        return resoudre(tokens, m[1], theme, pile)
    m = re.fullmatch(r"light-dark\((.*)\)", v)
    if m:
        a, b = separer(m[1])
        return valeur(tokens, a if theme == "clair" else b, theme, pile)
    c = couleur(v)
    if c is None:
        raise ValueError(f"valeur non reconnue : {v}")
    return c


def separer(s):
    prof = 0
    for i, ch in enumerate(s):
        prof += ch == "("
        prof -= ch == ")"
        if ch == "," and prof == 0:
            return s[:i], s[i + 1:]
    raise ValueError(s)


def composer(c, fond):
    a = c[3]
    return tuple(round(c[i] * a + fond[i] * (1 - a)) for i in range(3)) + (1.0,)


# ------------------------------------------------------------------ colorimétrie
def lin(c8):
    c = c8 / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(c):
    r, g, b = (lin(x) for x in c[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


MACHADO = {
    "protanopie": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutéranopie": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritanopie": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}
VISIONS = ["normale", "protanopie", "deutéranopie", "tritanopie", "achromatopsie"]


def simuler(c, vision):
    r, g, b = (lin(x) for x in c[:3])
    if vision == "normale":
        return (r, g, b)
    if vision == "achromatopsie":
        y = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return (y, y, y)
    M = MACHADO[vision]
    return tuple(min(1, max(0, M[i][0] * r + M[i][1] * g + M[i][2] * b)) for i in range(3))


def oklab(rgb_lin):
    r, g, b = rgb_lin
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (x ** (1 / 3) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def ecart(c1, c2, vision):
    a, b = oklab(simuler(c1, vision)), oklab(simuler(c2, vision))
    return 100 * sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


# ------------------------------------------------------------------ ce qu'on vérifie
# Fonds sur lesquels se posent les étiquettes de la carte (image satellite) : forêt sombre, neige.
FONDS_CARTE = {"forêt": (45, 59, 42, 1.0), "neige": (244, 246, 248, 1.0)}

TEXTE = [  # (texte, fond, usage) : 4,5:1
    ("text-primary", "surface-1", "texte courant"),
    ("text-primary", "surface-2", "texte dans une carte"),
    ("text-secondary", "surface-1", "texte secondaire"),
    ("text-secondary", "surface-2", "texte secondaire dans une carte"),
    ("text-muted", "surface-1", "notes, légendes"),
    ("text-muted", "surface-2", "notes dans une carte"),
    ("text-muted", "surface-3", "notes sur un survol"),
    ("text-secondary", "surface-raised", "infobulle, fenêtre"),
    ("accent", "surface-1", "liens"),
    ("accent", "surface-2", "liens dans une carte"),
    ("accent", "accent-soft", "élément sélectionné"),
    ("text-on-accent", "accent", "bouton principal"),
    ("marque-texte", "marque", "touche de marque (Chartreuse)"),
    ("good", "good-bg", "pastille « au-dessus », « air favorable »"),
    ("warn", "warn-bg", "pastille « au bord », « air limite »"),
    ("info", "info-bg", "pastille « dessous », « air défavorable »"),
    ("danger", "danger-bg", "message d'erreur"),
    ("good", "surface-2", "statut « mer de nuages »"),
    ("warn", "surface-2", "statut « se dégrade »"),
    ("info", "surface-2", "statut « pas de mer de nuages »"),
]
TEXTE_CARTE = [  # (texte, fond semi-transparent) composé sur l'image
    ("map-label-fg", "map-label-bg"), ("map-label-sub", "map-label-bg"),
    ("map-label-fg", "map-label-bg-r2"),
    ("map-label-dessous-fg", "map-label-dessous-bg"), ("map-label-fg", "map-label-bord-bg"),
    ("ardoise-0", "map-label-mesure-bg"),
]
GRAPHIQUE = [  # (élément, fond) : 3:1
    ("series-arome", "surface-1", "ligne AROME"),
    ("series-satellite", "surface-1", "points satellite"),
    ("focus-ring", "surface-1", "anneau de focus"),
    ("focus-ring", "surface-2", "anneau de focus dans une carte"),
    ("control-off", "surface-1", "interrupteur éteint"),
    ("control-off", "surface-2", "interrupteur éteint dans une carte"),
    ("accent", "surface-2", "interrupteur allumé, curseur"),
    ("good", "surface-2", "pastille d'état « mer »"),
    ("warn", "surface-2", "pastille d'état « dégradée »"),
    ("info", "surface-2", "pastille d'état « absente »"),
    ("text-muted", "surface-1", "marqueur « pas de mer de nuages »"),
]
DISTINCTS = [  # (groupe, [tokens], redondance) : doivent se distinguer deux à deux
    ("Graphique : AROME / satellite", ["series-arome", "series-satellite"], "ligne / points"),
    ("Statut de la carte « en ce moment »", ["good", "warn", "info", "series-arome"], "texte du statut"),
    ("Pastilles de position (fond)", ["good-bg", "warn-bg", "info-bg"], "pictogramme ☀ ≈ ☁ + texte"),
    ("Pastilles de position (texte)", ["good", "warn", "info"], "pictogramme ☀ ≈ ☁ + texte"),
    ("Webcams sur la carte", ["map-pin", "map-pin-dessus", "map-pin-dessous"], None, "carte"),
    ("Étiquettes de la carte", ["map-label-bg", "map-label-dessous-bg", "map-label-bord-bg"], "texte grisé sous la nappe", "carte"),
    ("Graphique : bandes de masse d'air", ["chart-air-defav", "chart-air-limite", "surface-1"], "légende + infobulle"),
]
VENT = [f"vent-{k}" for k in range(7)]
SEUIL_SEUL, SEUIL_REDONDANT = 10.0, 4.0


def verifier(tokens):
    lignes, echecs = [], 0

    def tab(titre, entete, rangs):
        lignes.append(f"\n## {titre}\n")
        lignes.append("| " + " | ".join(entete) + " |")
        lignes.append("|" + "---|" * len(entete))
        lignes.extend("| " + " | ".join(str(x) for x in r) + " |" for r in rangs)

    for theme in ("clair", "sombre"):
        R = lambda n: resoudre(tokens, n, theme)
        fond_page = R("surface-1")

        def opaque(n, fond=None):
            c = R(n)
            return composer(c, fond or fond_page) if c[3] < 1 else c

        lignes.append(f"\n# Thème {theme}\n")
        rangs = []
        for t, f, usage in TEXTE:
            r = contraste(opaque(t, opaque(f)), opaque(f))
            ok = r >= 4.5
            echecs += not ok
            rangs.append((usage, f"`{t}` sur `{f}`", f"{r:.2f}:1", "✅" if ok else "❌ < 4,5"))
        for t, f in TEXTE_CARTE:
            pires = []
            for nom_fond, fc in FONDS_CARTE.items():
                fond = composer(R(f), fc)
                pires.append((contraste(composer(R(t), fond), fond), nom_fond))
            r, ou = min(pires)
            ok = r >= 4.5
            echecs += not ok
            rangs.append((f"étiquette de carte (pire cas : {ou})", f"`{t}` sur `{f}`", f"{r:.2f}:1", "✅" if ok else "❌ < 4,5"))
        tab("Contraste du texte (WCAG 1.4.3, 4,5:1)", ["Usage", "Couleurs", "Contraste", ""], rangs)

        rangs = []
        for t, f, usage in GRAPHIQUE:
            r = contraste(opaque(t, opaque(f)), opaque(f))
            ok = r >= 3
            echecs += not ok
            rangs.append((usage, f"`{t}` sur `{f}`", f"{r:.2f}:1", "✅" if ok else "❌ < 3"))
        tab("Contraste des éléments graphiques (WCAG 1.4.11, 3:1)", ["Usage", "Couleurs", "Contraste", ""], rangs)

        rangs = []
        for groupe, noms, redondance, *sur in DISTINCTS:
            seuil = SEUIL_REDONDANT if redondance else SEUIL_SEUL
            fond = FONDS_CARTE["forêt"] if sur == ["carte"] else None
            cols = [opaque(n, fond) for n in noms]
            # doublée d'un autre indice, la couleur n'a pas à survivre à l'achromatopsie (vision sans
            # aucune couleur, ≈ 1 personne sur 30 000) : écart affiché mais non exigé
            exigees = VISIONS[:4] if redondance else VISIONS
            for i in range(len(noms)):
                for j in range(i + 1, len(noms)):
                    ds = {v: ecart(cols[i], cols[j], v) for v in VISIONS}
                    pire = min(exigees, key=ds.get)
                    ok = ds[pire] >= seuil
                    echecs += not ok
                    rangs.append((groupe, f"`{noms[i]}` / `{noms[j]}`",
                                  " · ".join(f"{ds[v]:.0f}" for v in VISIONS),
                                  f"{ds[pire]:.1f} ({pire})", f"≥ {seuil:g}" + (f" ({redondance})" if redondance else ""),
                                  "✅" if ok else "❌"))
        tab("Couleurs à distinguer, vision simulée (ΔE OKLab × 100)",
            ["Groupe", "Paire", "normale · protan · deutan · tritan · achroma", "Pire cas", "Seuil", ""], rangs)

        rangs = []
        cols = [R(n) for n in VENT]
        for v in VISIONS:
            L = [oklab(simuler(c, v))[0] * 100 for c in cols]
            mono = all(b > a + 2 for a, b in zip(L, L[1:]))
            adj = min(ecart(a, b, v) for a, b in zip(cols, cols[1:]))
            ok = mono and adj >= 6
            echecs += not ok
            rangs.append((v, " → ".join(f"{x:.0f}" for x in L), f"{adj:.1f}", "✅" if ok else "❌"))
        tab("Échelle du vent : luminosité croissante (L OKLab × 100)",
            ["Vision", "Luminosité des 7 paliers", "Écart mini entre paliers", ""], rangs)

    return lignes, echecs


def planche(tokens):
    """SVG : chaque groupe de couleurs vu dans les 5 visions, thèmes clair et sombre."""
    groupes = [(g, n, sur) for g, n, _r, *sur in DISTINCTS] + [("Échelle du vent", VENT, [])]
    noms_vis = {"normale": "Vision normale", "protanopie": "Protanopie", "deutéranopie": "Deutéranopie",
                "tritanopie": "Tritanopie", "achromatopsie": "Achromatopsie"}
    W_LIB, W_COL, H_RANG, PAD = 250, 150, 34, 16
    hauteur = PAD * 2 + 2 * (40 + len(groupes) * H_RANG) + 20
    largeur = W_LIB + W_COL * len(VISIONS) + PAD
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largeur} {hauteur}" font-family="Barlow, system-ui, sans-serif" font-size="12">']
    y = PAD
    for theme in ("clair", "sombre"):
        fond = resoudre(tokens, "surface-1", theme)
        texte = resoudre(tokens, "text-primary", theme)
        rgb = lambda c: f"rgb({c[0]},{c[1]},{c[2]})"
        bloc_h = 40 + len(groupes) * H_RANG
        out.append(f'<rect x="0" y="{y - 8}" width="{largeur}" height="{bloc_h + 8}" fill="{rgb(fond)}"/>')
        out.append(f'<text x="{PAD}" y="{y + 14}" font-weight="700" font-size="14" fill="{rgb(texte)}">Thème {theme}</text>')
        for k, v in enumerate(VISIONS):
            out.append(f'<text x="{W_LIB + k * W_COL}" y="{y + 14}" font-weight="600" fill="{rgb(texte)}">{noms_vis[v]}</text>')
        y += 30
        for g, noms, sur in groupes:
            out.append(f'<text x="{PAD}" y="{y + 18}" fill="{rgb(texte)}">{g}</text>')
            base = FONDS_CARTE["forêt"] if sur == ["carte"] else fond
            for k, v in enumerate(VISIONS):
                w = (W_COL - 14) / len(noms)
                for i, n in enumerate(noms):
                    c = resoudre(tokens, n, theme)
                    c = composer(c, base) if c[3] < 1 else c
                    r, gg, b = (round(255 * (x ** (1 / 2.4) * 1.055 - 0.055 if x > 0.0031308 else 12.92 * x)) for x in simuler(c, v))
                    out.append(f'<rect x="{W_LIB + k * W_COL + i * w:.1f}" y="{y + 4}" width="{w - 2:.1f}" height="22" rx="3" '
                               f'fill="rgb({r},{gg},{b})" stroke="rgb(128,128,128)" stroke-opacity=".35"><title>{n}</title></rect>')
            y += H_RANG
        y += 20
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rapport", type=Path, help="écrit le rapport Markdown dans ce fichier")
    ap.add_argument("--planche", type=Path, help="écrit la planche SVG des visions simulées dans ce fichier")
    args = ap.parse_args()
    tokens = lire_tokens(TOKENS.read_text(encoding="utf-8"))
    lignes, echecs = verifier(tokens)
    entete = ["# Vérification des couleurs — design system « Grelou »", "",
              "Rapport produit par `python3 tools/verif_couleurs.py --rapport docs/design-system/verif-couleurs.md` "
              "à partir de `web/ds/tokens.css`. Ne pas modifier à la main.", "",
              "- Contrastes : WCAG 2.2 niveau AA.",
              "- Daltonisme : simulation Machado et al. (2009), sévérité maximale ; achromatopsie = luminance seule.",
              f"- Écarts en OKLab × 100 (≈ 2 = à peine perceptible). Seuil {SEUIL_SEUL:g} si la couleur porte seule "
              f"l'information, {SEUIL_REDONDANT:g} si elle est doublée d'une forme, d'un pictogramme ou d'un texte "
              "(dans ce cas l'achromatopsie est affichée mais non exigée).",
              "- Couleurs semi-transparentes : composées sur le panneau, ou sur une forêt sombre pour la carte.", "",
              f"**Résultat : {'tout est conforme ✅' if not echecs else f'{echecs} échec(s) ❌'}**"]
    texte = "\n".join(entete + lignes) + "\n"
    if args.planche:
        args.planche.parent.mkdir(parents=True, exist_ok=True)
        args.planche.write_text(planche(tokens), encoding="utf-8")
    if args.rapport:
        args.rapport.parent.mkdir(parents=True, exist_ok=True)
        args.rapport.write_text(texte, encoding="utf-8")
    print(texte if not args.rapport else f"{args.rapport} : {echecs} échec(s)")
    sys.exit(1 if echecs else 0)


if __name__ == "__main__":
    main()
