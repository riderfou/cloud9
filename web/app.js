import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const S = 100;                 // 1 unité 3D = 100 m
const $ = (id) => document.getElementById(id);
const fmtH = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const fmtHour = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", hour: "2-digit" });
const fmtDay = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", weekday: "short", day: "numeric" });
const nf = new Intl.NumberFormat("fr-FR");

const state = { H: 1200, exag: 1, estimate: null, sigma: null, analysis: null };

// "no-cache" : le navigateur revalide auprès du serveur (GitHub Pages met les fichiers en cache 10 min)
async function getJSON(p) { const r = await fetch(p, { cache: "no-cache" }); if (!r.ok) throw new Error(p); return r.json(); }
function loadImage(src) { return new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = src; }); }

// ------------------------------------------------------------------ données
let [meta, hist, arome, lieux, reliefImg] = await Promise.all([
  getJSON("data/meta.json"), getJSON("data/historique.json"), getJSON("data/arome.json").catch(() => null),
  getJSON("data/sommets.json"), loadImage("data/relief.png"),
]);
const webcams = await getJSON("data/webcams.json").then((d) => d.webcams || []).catch(() => []);
const [GW, GH] = meta.grille_web;
const [X0, Y0, X1, Y1] = meta.aoi;
const step = meta.pas_m;
const Wm = GW * step, Hm = GH * step;           // étendue en mètres
const cx = X0 + Wm / 2, cy = Y1 - Hm / 2;
const toWorld = (x, y, z) => new THREE.Vector3((x - cx) / S, (z * state.exag) / S, -(y - cy) / S);

// décodage du relief (terrarium)
const cv = document.createElement("canvas"); cv.width = GW; cv.height = GH;
const ctx = cv.getContext("2d", { willReadFrequently: true }); ctx.drawImage(reliefImg, 0, 0);
const px = ctx.getImageData(0, 0, GW, GH).data;
const Z = new Float32Array(GW * GH);
for (let k = 0; k < GW * GH; k++) Z[k] = px[4 * k] * 256 + px[4 * k + 1] + px[4 * k + 2] / 256 - 32768;
const zAt = (x, y) => {
  const j = Math.min(GW - 1, Math.max(0, Math.round((x - X0) / step - 0.5)));
  const i = Math.min(GH - 1, Math.max(0, Math.round((Y1 - y) / step - 0.5)));
  return Z[i * GW + j];
};

// ------------------------------------------------------------------ scène
const host = $("scene");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
host.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0xb8d3ec, 450, 1300);
const camera = new THREE.PerspectiveCamera(45, 1, 1, 5000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.47;
controls.minDistance = 40; controls.maxDistance = 900;

scene.add(new THREE.HemisphereLight(0xdfeeff, 0x4a4030, 1.1));
const sun = new THREE.DirectionalLight(0xfff3e0, 2.2);   // soleil de fin d'automne, plein sud, bas
sun.position.set(-150, 220, 400);
scene.add(sun);

// terrain
const geo = new THREE.BufferGeometry();
const pos = new Float32Array(GW * GH * 3), uv = new Float32Array(GW * GH * 2);
for (let i = 0; i < GH; i++) for (let j = 0; j < GW; j++) {
  const k = i * GW + j;
  pos[3 * k] = ((j + 0.5) * step - Wm / 2) / S;
  pos[3 * k + 2] = ((i + 0.5) * step - Hm / 2) / S;
  uv[2 * k] = j / (GW - 1); uv[2 * k + 1] = 1 - i / (GH - 1);
}
const idx = new Uint32Array((GW - 1) * (GH - 1) * 6); let n = 0;
for (let i = 0; i < GH - 1; i++) for (let j = 0; j < GW - 1; j++) {
  const a = i * GW + j, b = a + 1, c = a + GW, d = c + 1;
  idx[n++] = a; idx[n++] = c; idx[n++] = b; idx[n++] = b; idx[n++] = c; idx[n++] = d;
}
geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
geo.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
geo.setIndex(new THREE.BufferAttribute(idx, 1));
function applyHeights() {
  for (let k = 0; k < GW * GH; k++) pos[3 * k + 1] = (Z[k] * state.exag) / S;
  geo.attributes.position.needsUpdate = true; geo.computeVertexNormals(); geo.computeBoundingSphere();
}
applyHeights();
const tex = await new THREE.TextureLoader().loadAsync("data/texture.jpg");
tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
const terrain = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: tex, roughness: 0.95, metalness: 0 }));
scene.add(terrain);

// nuage observé (fraction nuageuse satellite, drapée sur le relief)
const obsMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.85, depthWrite: false,
  polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
const obsMesh = new THREE.Mesh(geo, obsMat); obsMesh.visible = false; scene.add(obsMesh);

// neige (composite MTG des dernières observations sans nuage) : R = fraction enneigée.
// Le fond de carte est une image d'été (sans neige saisonnière) : c'est ce calque qui montre la neige du moment.
const neigeMeta = await getJSON("data/neige.json").catch(() => null);
const neigeMat = new THREE.MeshLambertMaterial({ color: 0xf6f9ff, transparent: true, opacity: 0.95, depthWrite: false,
  polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
const neigeMesh = new THREE.Mesh(geo, neigeMat); neigeMesh.visible = false; scene.add(neigeMesh);
if (neigeMeta) {
  try {
    const img = await loadImage(`data/neige.png?v=${encodeURIComponent(neigeMeta.maj_utc)}`);
    const c = document.createElement("canvas"); c.width = img.width; c.height = img.height;
    const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(img, 0, 0);
    const d = g.getImageData(0, 0, c.width, c.height);
    for (let k = 0; k < d.data.length; k += 4) { const r = d.data[k]; d.data[k + 1] = r; d.data[k + 2] = r; d.data[k + 3] = 255; }
    g.putImageData(d, 0, 0);
    const c2 = document.createElement("canvas"); c2.width = c.width; c2.height = c.height;
    const g2 = c2.getContext("2d"); g2.filter = "blur(0.6px)"; g2.drawImage(c, 0, 0);   // alphaMap : canal vert
    const t = new THREE.CanvasTexture(c2); t.flipY = true;
    neigeMat.alphaMap = t; neigeMat.needsUpdate = true; neigeMesh.visible = true;
  } catch (e) { console.warn("neige indisponible", e); }
}

// mer de nuages simulée : plan horizontal à H, bords adoucis là où le relief affleure
const hTex = new THREE.DataTexture(Z, GW, GH, THREE.RedFormat, THREE.FloatType);
hTex.magFilter = THREE.LinearFilter; hTex.minFilter = THREE.LinearFilter; hTex.needsUpdate = true;
const seaMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, fog: true,
  uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
    uHeight: { value: hTex }, uH: { value: 1200 }, uTime: { value: 0 }, uSize: { value: new THREE.Vector2(Wm / S, Hm / S) },
    uSun: { value: sun.position.clone().normalize() },
  }]),
  vertexShader: `
    varying vec2 vUv; varying vec3 vW;
    #include <fog_pars_vertex>
    void main(){ vUv = uv; vec4 w = modelMatrix * vec4(position,1.); vW = w.xyz;
      vec4 mvPosition = viewMatrix * w; gl_Position = projectionMatrix * mvPosition;
      #include <fog_vertex>
    }`,
  fragmentShader: `
    uniform sampler2D uHeight; uniform float uH; uniform float uTime; uniform vec2 uSize; uniform vec3 uSun;
    varying vec2 vUv; varying vec3 vW;
    #include <fog_pars_fragment>
    float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
    float noise(vec2 p){ vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.-2.*f);
      return mix(mix(h(i),h(i+vec2(1,0)),u.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),u.x), u.y); }
    float fbm(vec2 p){ float s=0., a=.5; for(int k=0;k<5;k++){ s+=a*noise(p); p*=2.03; a*=.5; } return s; }
    void main(){
      vec2 tuv = vec2((vW.x + uSize.x*.5)/uSize.x, (vW.z + uSize.y*.5)/uSize.y);
      float zt = texture2D(uHeight, tuv).r;
      float depth = uH - zt;                         // épaisseur de nuage au-dessus du sol (m)
      vec2 p = vW.xz * .045 + vec2(uTime*.010, uTime*.004);
      float n = fbm(p), n2 = fbm(p*3.1 + 7.);
      float a = smoothstep(-10., 90., depth + (n-.5)*120.);
      vec2 e = min(tuv, 1. - tuv);                   // fondu sur les bords de la zone
      a *= smoothstep(0., .035, min(e.x, e.y));
      if (a < .01) discard;
      float shade = .80 + .22*n + .08*n2;
      vec3 col = mix(vec3(.80,.84,.90), vec3(1.), shade);
      col *= .92 + .10*clamp(uSun.y,0.,1.);
      gl_FragColor = vec4(col, a*.97);
      #include <fog_fragment>
    }`,
});
const sea = new THREE.Mesh(new THREE.PlaneGeometry(Wm / S, Hm / S, 1, 1), seaMat);
sea.rotation.x = -Math.PI / 2; sea.renderOrder = 2; scene.add(sea);

function setH(H) {
  state.H = H;
  sea.position.y = (H * state.exag) / S; seaMat.uniforms.uH.value = H;
  $("h-slider").value = H; $("h-val").textContent = `${nf.format(H)} m`;
  renderPeaks(); majBoutonSimulation();
}
// « Revenir à la simulation » : masqué s'il n'y a pas d'altitude simulée (pas de conditions pour une mer
// de nuages), inactif tant que le curseur n'a pas été déplacé.
function majBoutonSimulation() {
  const b = $("btn-reset");
  b.hidden = state.estimate == null;
  b.disabled = state.estimate == null || state.H === state.estimate || !$("t-sea").checked;
}

// ------------------------------------------------------------------ vent : particules (à la Windy)
// Champ AROME sur une grille régulière (vent.json) interpolé dans l'espace et dans le temps ; chaque
// particule laisse une traînée qui s'efface, colorée selon la vitesse, posée sur le relief (vent à 10 m)
// ou à 1 500 m (850 hPa, au-dessus de la mer de nuages).
let vent = await getJSON("data/vent.json").catch(() => null);
const VENT_N = matchMedia("(pointer: coarse)").matches ? 1800 : 3200;   // particules
const VENT_T = 12;                 // points par traînée
const VENT_ACC = 650;              // accélération du temps : 10 m/s -> 6,5 km par seconde à l'écran
const VENT_PAS_TRAINEE = 0.05;     // s entre deux points de traînée
// échelle de couleur (km/h), proche de celle de Windy
const VENT_ECHELLE = [[0, [98, 113, 183]], [10, [57, 160, 202]], [20, [74, 196, 133]], [35, [168, 214, 74]],
  [55, [240, 190, 55]], [70, [232, 104, 52]], [100, [200, 45, 110]]];
function couleurVent(kmh) {
  const E = VENT_ECHELLE;
  if (kmh >= E[E.length - 1][0]) return E[E.length - 1][1];
  for (let k = 1; k < E.length; k++) if (kmh < E[k][0]) {
    const [a, ca] = E[k - 1], [b, cb] = E[k], f = (kmh - a) / (b - a);
    return ca.map((c, i) => c + (cb[i] - c) * f);
  }
  return E[0][1];
}
const ventGeo = new THREE.BufferGeometry();
const ventPos = new Float32Array(VENT_N * (VENT_T - 1) * 2 * 3);
const ventCol = new Float32Array(VENT_N * (VENT_T - 1) * 2 * 4);
ventGeo.setAttribute("position", new THREE.BufferAttribute(ventPos, 3).setUsage(THREE.DynamicDrawUsage));
ventGeo.setAttribute("color", new THREE.BufferAttribute(ventCol, 4).setUsage(THREE.DynamicDrawUsage));
const ventLignes = new THREE.LineSegments(ventGeo, new THREE.LineBasicMaterial({
  vertexColors: true, transparent: true, depthWrite: false, fog: true }));
ventLignes.frustumCulled = false; ventLignes.renderOrder = 3; ventLignes.visible = false;
scene.add(ventLignes);
// particules : position (m, UTM), âge, durée de vie, traînée (anneau de positions monde) et couleurs
const P = Array.from({ length: VENT_N }, () => ({ x: 0, y: 0, age: 0, vie: 0, tr: new Float32Array(VENT_T * 3), nb: 0, c: [1, 1, 1] }));
const ventEtat = { niveau: "sol", k0: 0, k1: 0, f: 0, horloge: 0, t: null };
function ventChamp() { return vent && vent.niveaux[ventEtat.niveau]; }
// heure affichée : maintenant, ou l'heure de l'analyse choisie dans le tableau
function ventHeure() { return state.analysis && !state.synthese ? Date.parse(state.analysis.date_utc) : Date.now(); }
function ventMajTemps() {
  if (!vent) return false;
  const t = ventHeure(), T = vent.heures.map(Date.parse);
  if (t < T[0] - 1.8e6 || t > T[T.length - 1] + 1.8e6) return false;
  let k = T.findIndex((x) => x > t); if (k < 0) k = T.length - 1;
  ventEtat.k1 = Math.max(k, 0); ventEtat.k0 = Math.max(k - 1, 0);
  ventEtat.f = ventEtat.k0 === ventEtat.k1 ? 0 : THREE.MathUtils.clamp((t - T[ventEtat.k0]) / (T[ventEtat.k1] - T[ventEtat.k0]), 0, 1);
  ventEtat.t = t;
  return true;
}
// vent (u, v en m/s) au point (x, y) : bilinéaire sur la grille, linéaire entre deux heures
const vUV = [0, 0];
function ventEn(x, y) {
  const ch = ventChamp(), { nx, ny } = vent, gx = vent.x, gy = vent.y;
  const fx = THREE.MathUtils.clamp((x - gx[0]) / (gx[nx - 1] - gx[0]) * (nx - 1), 0, nx - 1.001);
  const fy = THREE.MathUtils.clamp((y - gy[0]) / (gy[ny - 1] - gy[0]) * (ny - 1), 0, ny - 1.001);
  const j = Math.floor(fx), i = Math.floor(fy), a = fx - j, b = fy - i;
  const w = [(1 - a) * (1 - b), a * (1 - b), (1 - a) * b, a * b], id = [i * nx + j, i * nx + j + 1, (i + 1) * nx + j, (i + 1) * nx + j + 1];
  let u = 0, v = 0, ws = 0;
  for (const [k, f] of [[ventEtat.k0, 1 - ventEtat.f], [ventEtat.k1, ventEtat.f]]) {
    if (f === 0) continue;
    const U = ch.u[k], V = ch.v[k];
    for (let q = 0; q < 4; q++) { if (U[id[q]] == null) continue; u += U[id[q]] * w[q] * f; v += V[id[q]] * w[q] * f; ws += w[q] * f; }
  }
  vUV[0] = ws ? u / ws : 0; vUV[1] = ws ? v / ws : 0;
  return vUV;
}
// altitude d'affichage : juste au-dessus du sol, ou 1 500 m (sans passer sous le relief)
const ventZ = (x, y) => ventEtat.niveau === "sol" ? zAt(x, y) + 60 : Math.max(1500, zAt(x, y) + 60);
function ventNaissance(p, ageAleatoire) {
  p.x = X0 + Math.random() * Wm; p.y = Y1 - Math.random() * Hm;
  p.vie = 2 + Math.random() * 3; p.age = ageAleatoire ? Math.random() * p.vie : 0; p.nb = 0;
  ventPoint(p);
}
function ventPoint(p) {   // ajoute la position courante en tête de traînée
  p.tr.copyWithin(3, 0, (VENT_T - 1) * 3);
  p.tr[0] = (p.x - cx) / S; p.tr[1] = (ventZ(p.x, p.y) * state.exag) / S; p.tr[2] = -(p.y - cy) / S;
  p.nb = Math.min(p.nb + 1, VENT_T);
}
function ventReinit() { for (const p of P) ventNaissance(p, true); }
function ventAvancer(dt) {
  ventEtat.horloge += dt;
  const pose = ventEtat.horloge >= VENT_PAS_TRAINEE; if (pose) ventEtat.horloge = 0;
  let n = 0;
  for (const p of P) {
    p.age += dt;
    const [u, v] = ventEn(p.x, p.y);
    p.x += u * dt * VENT_ACC; p.y += v * dt * VENT_ACC;
    const sort = p.x < X0 || p.x > X0 + Wm || p.y > Y1 || p.y < Y1 - Hm;
    if (p.age > p.vie || sort) { ventNaissance(p, false); }
    else if (pose) ventPoint(p);
    else { p.tr[0] = (p.x - cx) / S; p.tr[1] = (ventZ(p.x, p.y) * state.exag) / S; p.tr[2] = -(p.y - cy) / S; }
    // couleur selon la vitesse ; apparition et disparition en fondu
    const c = couleurVent(Math.hypot(u, v) * 3.6);
    const fondu = Math.min(1, p.age / 0.4, (p.vie - p.age) / 0.6);
    for (let s = 0; s < VENT_T - 1; s++, n++) {
      const o = n * 6, oc = n * 8;
      if (s + 1 >= p.nb) {   // segment pas encore tracé : dégénéré, invisible
        ventPos.fill(0, o, o + 6); ventCol.fill(0, oc, oc + 8); continue;
      }
      for (let q = 0; q < 2; q++) {
        const a = (s + q) * 3;
        ventPos[o + q * 3] = p.tr[a]; ventPos[o + q * 3 + 1] = p.tr[a + 1]; ventPos[o + q * 3 + 2] = p.tr[a + 2];
        const al = fondu * (1 - (s + q) / (VENT_T - 1));
        // couleur éclaircie (35 % de blanc) : lisible sur la forêt comme sur la neige
        ventCol.set([(c[0] * .65 + 89) / 255, (c[1] * .65 + 89) / 255, (c[2] * .65 + 89) / 255, al], oc + q * 4);
      }
    }
  }
  ventGeo.attributes.position.needsUpdate = true; ventGeo.attributes.color.needsUpdate = true;
}
// texte sous la case à cocher : heure, vitesse moyenne et direction dominante
const POINTS_CARDINAUX = ["nord", "nord-est", "est", "sud-est", "sud", "sud-ouest", "ouest", "nord-ouest"];
function ventResume() {
  const info = $("vent-info"), ok = ventMajTemps();
  $("vent-ctrl").hidden = !vent;
  $("t-vent").closest("label").hidden = !vent;
  if (!vent) return;
  if (!ok) { info.textContent = "Pas de prévision de vent à cette heure."; ventLignes.visible = false; return; }
  ventLignes.visible = $("t-vent").checked;
  let su = 0, sv = 0, sf = 0, n = 0;
  for (const x of vent.x) for (const y of vent.y) { const [u, v] = ventEn(x, y); su += u; sv += v; sf += Math.hypot(u, v); n++; }
  const kmh = Math.round((sf / n) * 3.6);
  const dir = (Math.atan2(-su, -sv) * 180 / Math.PI + 360) % 360;   // d'où vient le vent
  const de = kmh < 3 ? "vent calme" : `vent moyen ${kmh} km/h, de ${POINTS_CARDINAUX[Math.round(dir / 45) % 8]}`;
  info.textContent = `${ventEtat.niveau === "sol" ? "À 10 m du sol" : "À 1 500 m (850 hPa)"} · ${fmtH.format(new Date(ventEtat.t))} · ${de} · AROME`;
}
$("vent-legende").innerHTML = VENT_ECHELLE.map(([k, c]) => `<span style="background:rgb(${c.map(Math.round)})">${k}</span>`).join("") + "<em>km/h</em>";
if (vent) ventReinit();

// caméra : depuis le sud-ouest, regard vers Grenoble / Grésivaudan
const target = toWorld(723000, 5015000, 600);
controls.target.copy(target);
camera.position.copy(target.clone().add(new THREE.Vector3(-150, 150, 230)));

// ------------------------------------------------------------------ étiquettes
const labelsEl = $("labels");
const labels = [];   // {el, x, y, z}
function addLabel(html, cls, x, y, z) {
  const el = document.createElement("div"); el.className = "lbl " + cls; el.innerHTML = html;
  labelsEl.appendChild(el); const L = { el, x, y, z, cls }; labels.push(L); return L;
}
const peakLabels = lieux.map((s) => ({ s, L: addLabel("", "", s.x, s.y, s.alt_mnt) }));
let cellLabels = [];
function statusOf(alt) {
  const tol = Math.max(60, state.sigma || 0);
  if (!$("t-sea").checked) return "dessus";
  return alt > state.H + tol ? "dessus" : alt < state.H - tol ? "dessous" : "bord";
}
const ST_TXT = { dessus: "au-dessus", bord: "au niveau du bord", dessous: "dans / sous la mer" };
// ------------------------------------------------------------------ webcams (Windy)
const ICONE_CAM = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h3l2-2h6l2 2h3v12H4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><circle cx="12" cy="13" r="3.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
// altitude retenue (corrigée si besoin, voir webcams_corrections.json), sinon relief à la position Windy
const altCam = (c) => c.alt ?? c.alt_mnt;
// webcams au même endroit (< 150 m) : une seule pastille, avec leur nombre
const groupesCam = [];
for (const c of webcams) {
  const g = groupesCam.find((g) => Math.hypot(g.x - c.x, g.y - c.y) < 150);
  if (g) g.cams.push(c); else groupesCam.push({ x: c.x, y: c.y, alt: altCam(c), cams: [c] });
}
const camLabels = groupesCam.map((g) => {
  const n = g.cams.length;
  const L = addLabel(ICONE_CAM + (n > 1 ? `<span class="nb">${n}</span>` : ""), "cam", g.x, g.y, g.alt);
  L.el.title = n > 1 ? `${n} webcams · ${g.cams[0].ville || g.cams[0].titre} · ${nf.format(g.alt)} m` : `${g.cams[0].titre} · ${nf.format(g.alt)} m`;
  L.el.setAttribute("role", "button"); L.el.tabIndex = 0;
  L.el.addEventListener("click", () => ouvrirWebcam(g.cams[0], g.cams));
  L.el.addEventListener("keydown", (e) => { if (e.key === "Enter") ouvrirWebcam(g.cams[0], g.cams); });
  return { g, L };
});
const CAMS_REPLIEES = 8;
let camsDepliees = false;
function renderWebcams() {
  const sec = $("webcams-section"); sec.hidden = !webcams.length;
  $("t-cams").closest("label").hidden = !webcams.length;
  for (const { g, L } of camLabels) L.el.className = "lbl cam " + (!sea.visible ? "" : statusOf(g.alt));
  const ul = $("cams"); ul.replaceChildren();
  webcams.forEach((c, k) => {
    if (!camsDepliees && k >= CAMS_REPLIEES) return;
    const li = document.createElement("li"), st = statusOf(altCam(c));
    const b = document.createElement("button"); b.type = "button"; b.className = "lien-cam"; b.textContent = c.titre;
    b.addEventListener("click", () => ouvrirWebcam(c, (groupesCam.find((g) => g.cams.includes(c)) || { cams: [c] }).cams));
    const alt = document.createElement("span"); alt.className = "alt"; alt.textContent = `${nf.format(altCam(c))} m`;
    li.append(b, alt);
    if (sea.visible) { const chip = document.createElement("span"); chip.className = "st " + st;
      chip.textContent = (st === "dessus" ? "☀ " : st === "bord" ? "≈ " : "☁ ") + ST_TXT[st]; li.appendChild(chip); }
    ul.appendChild(li);
  });
  const plus = $("cams-plus");
  plus.hidden = webcams.length <= CAMS_REPLIEES;
  plus.textContent = camsDepliees ? "Afficher moins" : `Afficher les ${webcams.length} webcams`;
}
$("cams-plus").addEventListener("click", () => { camsDepliees = !camsDepliees; renderWebcams(); });
function ouvrirWebcam(c, groupe = [c]) {
  const d = $("cam-dialog");
  $("cam-titre").textContent = c.titre;
  const st = statusOf(altCam(c));
  $("cam-info").textContent = `${nf.format(altCam(c))} m${c.corrige ? " (corrigée)" : ""}${c.ville ? ` · ${c.ville}` : ""}`
    + (sea.visible ? ` · ${ST_TXT[st]} de la nappe affichée (${nf.format(state.H)} m)` : "");
  const f = $("cam-player");
  if (c.lecteur) { f.src = c.lecteur; f.hidden = false; } else { f.removeAttribute("src"); f.hidden = true; }
  $("cam-lien").href = c.lien || "https://www.windy.com/webcams";
  // autres webcams au même endroit
  const nav = $("cam-groupe"); nav.replaceChildren(); nav.hidden = groupe.length < 2;
  for (const o of groupe) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = o.titre.replace(/^[^:›]+[:›]\s*/, "") || o.titre;
    b.setAttribute("aria-pressed", String(o === c));
    b.addEventListener("click", () => ouvrirWebcam(o, groupe));
    nav.appendChild(b);
  }
  if (!d.open) d.showModal();
}
$("cam-dialog").addEventListener("close", () => { $("cam-player").removeAttribute("src"); });
$("cam-fermer").addEventListener("click", () => $("cam-dialog").close());
$("cam-dialog").addEventListener("click", (e) => { if (e.target === $("cam-dialog")) $("cam-dialog").close(); });

function renderPeaks() {
  for (const { s, L } of peakLabels) {
    const st = statusOf(s.alt);
    L.el.className = "lbl " + (!sea.visible ? "" : st === "dessous" ? "dessous" : st === "bord" ? "bord" : "");
    L.el.innerHTML = `${s.nom} <small>${nf.format(s.alt)} m</small>`;
  }
  renderWebcams();
  const ul = $("peaks"); ul.replaceChildren();
  $("peaks-note").hidden = sea.visible;
  for (const s of [...lieux].sort((a, b) => b.alt - a.alt)) {
    const st = statusOf(s.alt), li = document.createElement("li");
    if (!sea.visible) { const n = document.createElement("span"); n.textContent = s.nom;
      const al = document.createElement("span"); al.className = "alt"; al.textContent = `${nf.format(s.alt)} m`;
      li.append(n, al); ul.appendChild(li); continue; }
    const name = document.createElement("span"); name.textContent = s.nom;
    const alt = document.createElement("span"); alt.className = "alt"; alt.textContent = `${nf.format(s.alt)} m`;
    const chip = document.createElement("span"); chip.className = "st " + st;
    chip.textContent = (st === "dessus" ? "☀ " : st === "bord" ? "≈ " : "☁ ") + ST_TXT[st];
    li.append(name, alt, chip); ul.appendChild(li);
  }
}
function setCells(mailles) {
  cellLabels.forEach((L) => { L.el.remove(); labels.splice(labels.indexOf(L), 1); });
  cellLabels = (mailles || []).map((g) => addLabel(`${nf.format(g.h)}`, "cell", g.x, g.y, g.h));
  cellLabels.forEach((L) => (L.el.style.display = $("t-cells").checked ? "" : "none"));
}
const v = new THREE.Vector3();
function updateLabels() {
  const w = renderer.domElement.clientWidth, h = renderer.domElement.clientHeight;
  const showPeaks = $("t-labels").checked, showCells = $("t-cells").checked, showCams = $("t-cams").checked;
  for (const L of labels) {
    const isCell = L.cls === "cell", isCam = L.cls.startsWith("cam");
    if ((isCell && !showCells) || (isCam && !showCams) || (!isCell && !isCam && !showPeaks)) { L.el.style.display = "none"; continue; }
    v.copy(toWorld(L.x, L.y, isCell ? L.z : zAt(L.x, L.y) + (isCam ? 0 : 30))).project(camera);
    if (v.z > 1 || Math.abs(v.x) > 1.1 || Math.abs(v.y) > 1.1) { L.el.style.display = "none"; continue; }
    L.el.style.display = ""; L.el.style.left = `${(v.x * .5 + .5) * w}px`; L.el.style.top = `${(-v.y * .5 + .5) * h}px`;
  }
}

// ------------------------------------------------------------------ analyse affichée
async function showAnalysis(id, synthese = false) {
  const a = await getJSON(`data/analyses/${id}.json`);
  state.analysis = a; state.synthese = synthese;
  const img = await loadImage(`data/${a.masque}`);
  // léger flou : les pixels satellite (375-500 m) donnent sinon un rendu en escalier
  const cvm = document.createElement("canvas"); cvm.width = img.width; cvm.height = img.height;
  const cm = cvm.getContext("2d"); cm.filter = "blur(1.5px)"; cm.drawImage(img, 0, 0);
  const t = new THREE.CanvasTexture(cvm); t.flipY = true;
  if (obsMat.alphaMap) obsMat.alphaMap.dispose();
  obsMat.alphaMap = t; obsMat.needsUpdate = true;
  setCells(VALIDE(a) ? a.mailles : []);
  document.querySelectorAll("#analyses tr").forEach((tr) => tr.classList.toggle("sel", tr.dataset.id === id));
  renderEtat(synthese ? etatCourant() : etatDeAnalyse(a));
  ventResume();
}

// ------------------------------------------------------------------ état courant
// Priorité au temps réel : la dernière image si elle est récente ; sinon la médiane des mesures du
// même régime (sans mélanger une nappe nette et une nappe disloquée) ; sinon la prévision AROME,
// pondérée par le diagnostic de masse d'air (stabilité, vent, pluie).
const AGE_DIRECT_MIN = 90, AGE_MEDIANE_H = 3;
const fmtHM = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", hour: "2-digit", minute: "2-digit" });
const mediane = (xs) => { const s = [...xs].sort((p, q) => p - q), k = s.length >> 1; return s.length % 2 ? s[k] : (s[k - 1] + s[k]) / 2; };
const situationDe = (a) => a.situation || (a.detectee ? "mer" : "indetermine");
const VALIDE = (a) => a.detectee && a.sommet_m != null;
const SIT = {
  mer:        { etat: "mer",     statut: "Mer de nuages",                   court: null },
  degradee:   { etat: "alerte",  statut: "Mer de nuages qui se dégrade",    court: "se dégrade",
                note: "Des nuages commencent à accrocher les sommets" },
  disloquee:  { etat: "absente", statut: "Pas de mer de nuages",            court: "disloquée",
                titre: "Nappe disloquée", note: "Des nuages accrochent les sommets" },
  couvert:    { etat: "absente", statut: "Pas de mer de nuages",            court: "ciel couvert", titre: "Ciel couvert" },
  degage:     { etat: "absente", statut: "Pas de mer de nuages",            court: "pas de nuages bas", titre: "Pas de nuages bas" },
  indetermine:{ etat: "absente", statut: "Pas de mer de nuages nette",      court: "non détectée", titre: "Situation incertaine" },
};
const AIR = { favorable: "favorable", limite: "limite", defavorable: "défavorable", inconnu: "inconnue" };
function ageTxt(ms) {
  const min = Math.round(ms / 60e3);
  if (min < 60) return `il y a ${min} min`;
  if (min < 6 * 60) return `il y a ${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")}`;
  return `il y a ${Math.round(min / 60)} h`;
}
function heureArome(t = Date.now()) {
  if (!arome) return null;
  let best = null;
  for (const h of arome.heures) { const d = Math.abs(Date.parse(h.t) - t); if (!best || d < best.d) best = { d, h }; }
  return best && best.d < 3 * 3.6e6 ? best.h : null;
}
const NOM_CAPTEUR = { "MTG-FCI": () => "Meteosat", "MTG-FCI IR": () => "Meteosat (infrarouge, nuit)", "VIIRS": (a) => `VIIRS ${a.satellite}`, "Sentinel-2": () => "Sentinel-2" };
const nomSource = (a) => (NOM_CAPTEUR[a.capteur] || (() => `${a.capteur} ${a.satellite}`))(a);
const fmtJour = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", weekday: "short", day: "numeric", month: "short" });
// « à 16:08 » aujourd'hui, « le dim. 1 nov. à 16:08 » sinon
const quand = (a) => { const d = new Date(a.date_utc), j = fmtJour.format(d);
  return `${j === fmtJour.format(new Date()) ? "" : `le ${j} `}à ${fmtHM.format(d)}`; };
function detailsAir(air) {
  const det = [...(air.raisons || [])];
  if (!det.length) {
    if (air.inversion) det.push(`inversion vers ${nf.format(air.inversion.base_m)}-${nf.format(air.inversion.sommet_m)} m`);
    else if (air.gradient_c_km != null) det.push("air stable");
    if (air.vent850_kmh != null) det.push(air.vent850_kmh < 25 ? `vent faible (${Math.round(air.vent850_kmh)} km/h)`
      : `vent de ${Math.round(air.vent850_kmh)} km/h à 1 500 m, sans effet sous l'inversion`);
  }
  return det.join(", ");
}
// mesures valides consécutives qui finissent par `fin` (même régime), sur AGE_MEDIANE_H heures au plus
function regime(fin) {
  const tri = [...hist.analyses].sort((p, q) => Date.parse(p.date_utc) - Date.parse(q.date_utc));
  const out = [];
  for (let i = tri.findIndex((x) => x.id === fin.id); i >= 0; i--) {
    const x = tri[i];
    if (Date.parse(fin.date_utc) - Date.parse(x.date_utc) > AGE_MEDIANE_H * 3.6e6) break;
    if (!VALIDE(x)) { if (situationDe(x) === "indetermine") continue; break; }
    out.push(x);
  }
  return out;
}
function etatCourant() {
  const now = Date.now(), ah = heureArome(), air = ah && ah.air;
  const tri = [...hist.analyses].sort((p, q) => Date.parse(p.date_utc) - Date.parse(q.date_utc));
  // dernière image exploitable (une image "indéterminée" ne masque pas la précédente)
  const L = [...tri].reverse().find((x) => situationDe(x) !== "indetermine") || tri[tri.length - 1];
  const age = L ? now - Date.parse(L.date_utc) : Infinity;
  if (L && age <= AGE_MEDIANE_H * 3.6e6) {
    if (!VALIDE(L)) return { mode: "situation", situation: situationDe(L), src: L, age, air };
    if (age <= AGE_DIRECT_MIN * 60e3) return { mode: "mesure", situation: situationDe(L), sommet: L.sommet_m, incert: L.incertitude_m, src: L, age, air };
    const r = regime(L);
    return { mode: "mediane", situation: situationDe(L), sommet: Math.round(mediane(r.map((x) => x.sommet_m))),
             incert: Math.round(mediane(r.map((x) => x.incertitude_m))), n: r.length, src: L, age, air,
             capteurs: [...new Set(r.map((x) => x.capteur))] };
  }
  // pas d'image récente (nuit, panne) : prévision
  return { mode: "prevision", sommet: ah ? ah.sommet_lisse_m : null, air, src: L, age };
}
function etatDeAnalyse(a) {
  return VALIDE(a) ? { mode: "analyse", situation: situationDe(a), sommet: a.sommet_m, incert: a.incertitude_m, src: a }
                   : { mode: "analyse", situation: situationDe(a), src: a, air: (heureArome(Date.parse(a.date_utc)) || {}).air };
}

function renderEtat(e) {
  state.etat = e;
  const hero = $("hero");
  const prevision = e.mode === "prevision";
  const diag = e.air && e.air.diagnostic;
  const avecValeur = e.sommet != null && (!prevision || diag !== "defavorable");
  const sit = SIT[e.situation] || SIT.indetermine;
  // 1. statut
  let etat, statut, titre = null, detail;
  if (prevision) {
    etat = diag === "defavorable" ? "absente" : "prevision";
    statut = diag === "defavorable" ? "Mer de nuages peu probable" : diag === "favorable" ? "Prévision : mer de nuages probable" : "Prévision : conditions incertaines";
    if (!avecValeur) titre = "Peu probable";
    detail = (avecValeur ? "Sommet prévu par AROME · " : "") + (e.src ? `pas d'image satellite récente (dernière ${quand(e.src)})` : "aucune image satellite");
  } else {
    etat = sit.etat; statut = sit.statut;
    if (!avecValeur) titre = sit.titre;
    const age = e.mode === "analyse" ? "" : ` (${ageTxt(e.age)})`;
    detail = e.mode === "mediane"
      ? `Médiane de ${e.n} mesures du même épisode · dernière ${quand(e.src)}${age}`
      : `${avecValeur ? "Sommet mesuré par" : "Image"} ${nomSource(e.src)} ${quand(e.src)}${age}`;
    if (sit.note) detail = `${sit.note}. ${detail}`;
  }
  hero.dataset.etat = etat;
  $("hero-statut").textContent = statut;
  // 2. altitude, ou à défaut un titre explicite (jamais un tiret seul)
  $("hero-value").hidden = !avecValeur; $("hero-titre").hidden = avecValeur;
  $("hero-num").textContent = avecValeur ? (prevision ? "≈ " : "") + nf.format(e.sommet) : "";
  $("hero-pm").textContent = avecValeur && e.incert ? `± ${e.incert} m` : "";
  $("hero-titre").textContent = titre || "";
  // 3. source et fraîcheur
  $("hero-detail").textContent = detail;
  // 4. masse d'air
  const air = e.air && diag && diag !== "inconnu";
  $("hero-air").hidden = !air;
  if (air) {
    const b = $("air-badge"); b.className = "air-badge " + diag; b.textContent = `Air ${AIR[diag]}`;
    const d = detailsAir(e.air); $("air-txt").textContent = d ? `${d} · AROME` : "AROME";
  }
  state.estimate = avecValeur ? e.sommet : null; state.sigma = avecValeur ? e.incert : null;
  const valide = avecValeur && (prevision ? diag !== "defavorable" : e.situation in { mer: 1, degradee: 1 });
  appliquerCalques(valide, !prevision && e.src);
  majCases();
  setH(avecValeur ? e.sommet : state.H);
}
// Nappe simulée seulement s'il y a une mer de nuages ; sinon on montre le nuage réellement observé.
// Appliqué seulement quand la situation change : l'utilisateur garde la main sur les cases à cocher.
function appliquerCalques(valide, avecImage) {
  const cle = `${valide}|${!!avecImage}`;
  if (state.cleCalques === cle) return;
  state.cleCalques = cle;
  $("t-sea").checked = sea.visible = !!valide;
  $("t-obs").checked = obsMesh.visible = !!avecImage;
  renderPeaks(); majCases();
}
// « Altitudes mesurées » n'a de sens que si l'image affichée montre une mer de nuages ;
// les réglages de la nappe ne servent que si la nappe est affichée.
function majCases() {
  const cb = $("t-cells"), ok = !!(state.analysis && VALIDE(state.analysis));
  if (!ok && !cb.disabled) { state.cellsPref = cb.checked; cb.checked = false; }
  if (ok && cb.disabled) cb.checked = !!state.cellsPref;
  cb.disabled = !ok;
  $("lbl-cells").classList.toggle("inactif", !ok);
  $("lbl-cells").title = ok ? "" : "Pas de mer de nuages sur l'image affichée";
  updateLabels();
  const nc = $("nappe-ctrl"), on = $("t-sea").checked;
  nc.classList.toggle("inactif", !on);
  nc.querySelectorAll("input").forEach((x) => (x.disabled = !on));
  majBoutonSimulation();
}

// ------------------------------------------------------------------ tableau des analyses
function renderTable() {
  const tb = $("analyses"); tb.replaceChildren();
  for (const a of [...hist.analyses].reverse()) {
    const tr = document.createElement("tr"); tr.dataset.id = a.id; tr.tabIndex = 0;
    const c1 = document.createElement("td"); c1.textContent = fmtH.format(new Date(a.date_utc));
    const c2 = document.createElement("td"); c2.textContent = `${a.capteur} ${a.satellite}`;
    const c3 = document.createElement("td"); c3.className = "num";
    const sit = situationDe(a);
    if (VALIDE(a)) c3.textContent = `${nf.format(a.sommet_m)} ± ${a.incertitude_m} m${sit === "degradee" ? " ⚠" : ""}`;
    else { c3.textContent = (SIT[sit] || SIT.indetermine).court; c3.classList.add("nd"); }
    if (sit === "degradee") c3.title = "Mer de nuages qui se dégrade : des nuages accrochent les sommets";
    tr.append(c1, c2, c3);
    tr.addEventListener("click", () => showAnalysis(a.id));
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter") showAnalysis(a.id); });
    tb.appendChild(tr);
  }
}

// Infobulle à droite du pointeur, ou à gauche si elle déborderait de l'écran ; toujours dans la fenêtre.
function placerInfobulle(tip, x, y) {
  tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight, marge = 8, ecart = 14;
  let gauche = x + ecart;
  if (gauche + w > innerWidth - marge) gauche = x - ecart - w;
  gauche = Math.max(marge, gauche);
  const haut = Math.min(Math.max(marge, y - 10), innerHeight - h - marge);
  tip.style.left = `${gauche}px`; tip.style.top = `${haut}px`;
}

// ------------------------------------------------------------------ graphique (SVG)
function renderChart() {
  const W = 344, Hh = 190, m = { l: 50, r: 8, t: 8, b: 22 };
  const now = Date.now();
  const t0 = now - 48 * 3.6e6, t1 = now + 30 * 3.6e6;
  const recents = hist.analyses.filter((a) => Date.parse(a.date_utc) >= t0);
  const obs = recents.filter(VALIDE), sansMer = recents.filter((a) => !VALIDE(a) && situationDe(a) !== "indetermine");
  const fc = (arome ? arome.heures : []).filter((h) => { const t = Date.parse(h.t); return t >= t0 && t <= t1; });
  const vals = [...obs.map((a) => a.sommet_m + a.incertitude_m), ...fc.map((h) => h.sommet_lisse_m).filter((x) => x != null), 1500];
  const yMax = Math.ceil(Math.max(...vals) / 500) * 500, yMin = 0;
  const X = (t) => m.l + ((t - t0) / (t1 - t0)) * (W - m.l - m.r);
  const Y = (z) => m.t + (1 - (z - yMin) / (yMax - yMin)) * (Hh - m.t - m.b);
  const ns = "http://www.w3.org/2000/svg";
  const el = (tag, at, parent) => { const e = document.createElementNS(ns, tag); for (const k in at) e.setAttribute(k, at[k]); parent && parent.appendChild(e); return e; };
  const svg = el("svg", { viewBox: `0 0 ${W} ${Hh}`, role: "img", "aria-label": "Altitude du sommet de la mer de nuages : mesures satellite et prévision AROME" });
  const fond = el("g", {}, svg);   // bandes « air défavorable », sous la grille
  const grid = el("g", { class: "grid" }, svg), axis = el("g", { class: "axis" }, svg);
  for (let z = 0; z <= yMax; z += 500) {
    el("line", { x1: m.l, x2: W - m.r, y1: Y(z), y2: Y(z) }, grid);
    el("text", { x: m.l - 6, y: Y(z) + 3, "text-anchor": "end" }, axis).textContent = `${nf.format(z)} m`;
  }
  // graduations : minuit et midi, heure locale
  for (let t = Math.ceil(t0 / 3.6e6) * 3.6e6; t <= t1; t += 3.6e6) {
    const hh = Number(fmtHour.format(new Date(t)));
    if (hh === 0 || hh === 12) {
      el("text", { x: X(t), y: Hh - 6, "text-anchor": "middle" }, axis).textContent = hh === 0 ? fmtDay.format(new Date(t)) : "12 h";
      if (hh === 0) el("line", { x1: X(t), x2: X(t), y1: m.t, y2: Hh - m.b }, grid);
    }
  }
  // fond : heures où la masse d'air est défavorable (gris foncé) ou limite (gris clair)
  for (const h of fc) {
    const dg = h.air && h.air.diagnostic;
    if (dg !== "defavorable" && dg !== "limite") continue;
    const tx = Date.parse(h.t);
    el("rect", { x: X(tx - 1.8e6), y: m.t, width: X(tx + 1.8e6) - X(tx - 1.8e6) + 0.2, height: Hh - m.t - m.b,
                 class: dg === "defavorable" ? "air-defav" : "air-limite" }, fond);
  }
  const nowG = el("g", { class: "now" }, svg);
  el("line", { x1: X(now), x2: X(now), y1: m.t, y2: Hh - m.b }, nowG);
  el("text", { x: X(now) + 3, y: m.t + 9 }, nowG).textContent = "maintenant";
  // AROME : ligne, interrompue quand pas de couche humide
  let d = "", pen = false;
  for (const h of fc) {
    if (h.sommet_lisse_m == null) { pen = false; continue; }
    d += `${pen ? "L" : "M"}${X(Date.parse(h.t)).toFixed(1)},${Y(h.sommet_lisse_m).toFixed(1)}`; pen = true;
  }
  el("path", { d, fill: "none", stroke: "var(--series-1)", "stroke-width": 2, "stroke-linejoin": "round" }, svg);
  // observations : point + barre d'incertitude
  for (const a of obs) {
    const x = X(Date.parse(a.date_utc)), deg = situationDe(a) === "degradee";
    el("line", { x1: x, x2: x, y1: Y(a.sommet_m - a.incertitude_m), y2: Y(a.sommet_m + a.incertitude_m), stroke: "var(--series-2)", "stroke-width": 2, opacity: deg ? 0.45 : 1 }, svg);
    el("circle", { cx: x, cy: Y(a.sommet_m), r: a.capteur.startsWith("MTG") ? 3 : 4.5, fill: "var(--series-2)", "fill-opacity": deg ? 0.45 : 1, stroke: "var(--surface-1)", "stroke-width": a.capteur.startsWith("MTG") ? 1 : 2 }, svg);
  }
  // images sans mer de nuages : marqueur creux sur la ligne de base (l'altitude n'a pas de sens)
  for (const a of sansMer) {
    el("circle", { cx: X(Date.parse(a.date_utc)), cy: Y(0) - 5, r: 3, fill: "var(--surface-1)", stroke: "var(--text-muted)", "stroke-width": 1.5 }, svg);
  }
  // survol : réticule vertical + infobulle
  const hair = el("line", { y1: m.t, y2: Hh - m.b, stroke: "var(--text-muted)", "stroke-width": 1, visibility: "hidden" }, svg);
  const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: Hh - m.t - m.b, fill: "transparent" }, svg);
  const tip = $("tooltip");
  hit.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect(), sx = ((e.clientX - r.left) / r.width) * W;
    const t = t0 + ((sx - m.l) / (W - m.l - m.r)) * (t1 - t0);
    const h = fc.reduce((b, x) => (Math.abs(Date.parse(x.t) - t) < Math.abs(Date.parse(b.t) - t) ? x : b), fc[0]);
    const o = [...obs, ...sansMer].filter((a) => Math.abs(Date.parse(a.date_utc) - t) < 1.5 * 3.6e6)
      .sort((a, b) => Math.abs(Date.parse(a.date_utc) - t) - Math.abs(Date.parse(b.date_utc) - t))[0];
    if (!h) return;
    hair.setAttribute("x1", X(Date.parse(h.t))); hair.setAttribute("x2", X(Date.parse(h.t))); hair.setAttribute("visibility", "visible");
    tip.replaceChildren();
    const head = document.createElement("div"); head.textContent = fmtH.format(new Date(h.t)); tip.appendChild(head);
    const row = (color, val, lab) => { const d = document.createElement("div"); d.className = "tt-row";
      const s = document.createElement("span"); s.className = "sw"; s.style.background = color;
      const b = document.createElement("strong"); b.textContent = val; const l = document.createElement("span"); l.textContent = lab;
      d.append(s, b, l); tip.appendChild(d); };
    row("var(--series-1)", h.sommet_lisse_m != null ? `${nf.format(h.sommet_lisse_m)} m` : "—", "AROME");
    if (h.air && h.air.diagnostic && h.air.diagnostic !== "inconnu")
      row("var(--grid)", `air ${AIR[h.air.diagnostic]}`, (h.air.raisons || []).join(", "));
    if (o) {
      const lab = `${o.satellite} ${fmtHM.format(new Date(o.date_utc))}`;
      if (VALIDE(o)) row("var(--series-2)", `${nf.format(o.sommet_m)} ± ${o.incertitude_m} m`, lab + (situationDe(o) === "degradee" ? " · se dégrade" : ""));
      else row("var(--text-muted)", (SIT[situationDe(o)] || SIT.indetermine).court, lab);
    }
    placerInfobulle(tip, e.clientX, e.clientY);
  });
  hit.addEventListener("pointerleave", () => { tip.hidden = true; hair.setAttribute("visibility", "hidden"); });
  $("chart").replaceChildren(svg);
  $("chart-legend").innerHTML = `<span><i class="l-dot"></i>Mesure satellite</span><span><i class="l-hollow"></i>Pas de mer de nuages</span>`
    + `<span><i class="l-line"></i>Prévision AROME</span><span><i class="l-band"></i>Air défavorable</span>`;
}

// ------------------------------------------------------------------ interface
$("h-slider").addEventListener("input", (e) => setH(Number(e.target.value)));
$("btn-reset").addEventListener("click", () => state.estimate != null && setH(state.estimate));
$("t-sea").addEventListener("change", (e) => { sea.visible = e.target.checked; renderPeaks(); majCases(); });
$("t-obs").addEventListener("change", (e) => (obsMesh.visible = e.target.checked));
$("t-neige").addEventListener("change", (e) => (neigeMesh.visible = e.target.checked && !!neigeMat.alphaMap));
if (neigeMeta && neigeMat.alphaMap) {
  const d = new Date(neigeMeta.maj_utc);
  $("t-neige-date").textContent = ` · ${new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", day: "numeric", month: "short" }).format(d)}`;
  $("t-neige").closest("label").title = `Composite Meteosat des dernières observations sans nuage (mise à jour ${fmtH.format(d)})`
    + (neigeMeta.limite_enneigement_m ? ` · limite d'enneigement vers ${nf.format(neigeMeta.limite_enneigement_m)} m` : "");
} else { $("t-neige").closest("label").hidden = true; }
$("t-cells").addEventListener("change", () => updateLabels());
$("t-cams").addEventListener("change", () => updateLabels());
$("t-exag").addEventListener("change", (e) => { state.exag = e.target.checked ? 1.5 : 1; applyHeights(); setH(state.H); if (vent) ventReinit(); });
$("t-vent").addEventListener("change", () => ventResume());
document.querySelectorAll("input[name=niveau-vent]").forEach((r) => r.addEventListener("change", (e) => {
  ventEtat.niveau = e.target.value; ventReinit(); ventResume();
}));
const afficherMaj = () => { $("maj").textContent = `mis à jour ${fmtH.format(new Date(hist.maj_utc))}`; };
afficherMaj();

function resize() {
  const w = host.clientWidth, h = host.clientHeight;
  renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
}
addEventListener("resize", resize); resize();

renderTable(); renderChart();
// image affichée par défaut : celle qui fonde l'état courant (la plus récente exploitable)
const idCourant = () => { const e = etatCourant(); return (e.src && e.src.id) || hist.derniere_analyse; };
if (idCourant()) await showAnalysis(idCourant(), true); else renderEtat(etatCourant());
$("loading").remove();

// ------------------------------------------------------------------ rafraîchissement automatique
// Recharge les données toutes les 10 min et au retour sur l'onglet (page laissée ouverte, téléphone en veille...).
// Si l'utilisateur a choisi une analyse dans le tableau, elle reste affichée ; sinon on passe à la nouvelle synthèse.
const RAFRAICHIR_MS = 10 * 60e3;
let dernierControle = Date.now(), enCours = false;
async function rafraichir() {
  if (enCours) return;
  enCours = true; dernierControle = Date.now();
  try {
    const h = await getJSON("data/historique.json");
    if (h.maj_utc !== hist.maj_utc) {
      hist = h;
      arome = await getJSON("data/arome.json").catch(() => arome);
      const ancienVent = vent;
      vent = await getJSON("data/vent.json").catch(() => vent);
      if (vent && !vent.niveaux[ventEtat.niveau]) ventEtat.niveau = "sol";
      if (vent && !ancienVent) ventReinit();
      afficherMaj(); renderTable();
      const id = idCourant();
      if (state.synthese && id) await showAnalysis(id, true);
      else if (state.analysis) {
        document.querySelectorAll("#analyses tr").forEach((tr) => tr.classList.toggle("sel", tr.dataset.id === state.analysis.id));
        renderEtat(etatDeAnalyse(state.analysis));
      }
    } else if (state.synthese) renderEtat(etatCourant());   // l'âge de la mesure change : direct -> médiane -> prévision
    renderChart();   // le repère « maintenant » avance même sans nouvelles données
    ventResume();
  } catch (e) {
    console.warn("rafraîchissement impossible", e);   // hors ligne... : on réessaiera au prochain tour
  } finally { enCours = false; }
}
setInterval(rafraichir, RAFRAICHIR_MS);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && Date.now() - dernierControle > 60e3) rafraichir();
});

// ------------------------------------------------------------------ navigation : nord et zoom
// Le nord est vers -Z. Azimut (theta) de la caméra autour de la cible : 0 = caméra au sud, regard vers le nord.
const sph = new THREE.Spherical(), off = new THREE.Vector3();
let anim = null;   // {t0, dur, de: {theta, radius}, vers: {theta, radius}}
function animerCamera(vers, dur = 600) {
  off.copy(camera.position).sub(controls.target); sph.setFromVector3(off);
  const de = { theta: sph.theta, radius: sph.radius };
  vers = { theta: vers.theta ?? de.theta, radius: vers.radius ?? de.radius };
  // plus court chemin angulaire
  let d = vers.theta - de.theta; d = Math.atan2(Math.sin(d), Math.cos(d)); vers.theta = de.theta + d;
  anim = { t0: performance.now(), dur, de, vers };
}
function avancerAnimation() {
  if (!anim) return;
  const k = Math.min(1, (performance.now() - anim.t0) / anim.dur), e = 1 - Math.pow(1 - k, 3);
  off.copy(camera.position).sub(controls.target); sph.setFromVector3(off);
  sph.theta = anim.de.theta + (anim.vers.theta - anim.de.theta) * e;
  sph.radius = anim.de.radius + (anim.vers.radius - anim.de.radius) * e;
  camera.position.copy(controls.target).add(off.setFromSpherical(sph));
  if (k >= 1) anim = null;
}
controls.addEventListener("start", () => { anim = null; });   // l'utilisateur reprend la main
const zoomer = (f) => {
  off.copy(camera.position).sub(controls.target);
  const r = (anim ? anim.vers.radius : off.length()) * f;
  animerCamera({ radius: THREE.MathUtils.clamp(r, controls.minDistance, controls.maxDistance) }, 300);
};
$("btn-nord").addEventListener("click", () => animerCamera({ theta: 0 }));
$("btn-zoom-in").addEventListener("click", () => zoomer(0.7));
$("btn-zoom-out").addEventListener("click", () => zoomer(1 / 0.7));
const boussole = $("boussole");
let angleAffiche = null;
function majBoussole() {
  off.copy(camera.position).sub(controls.target);
  const a = Math.round(THREE.MathUtils.radToDeg(Math.atan2(off.x, off.z)) * 10) / 10;
  if (a !== angleAffiche) { boussole.style.transform = `rotate(${a}deg)`; angleAffiche = a; }
}

const clock = new THREE.Clock();
// niveau 850 hPa absent du fichier : pas de choix d'altitude
if (vent && !vent.niveaux["1500m"]) document.querySelector(".niveaux-vent").hidden = true;
ventResume();
setInterval(() => { if (state.synthese || !state.analysis) ventResume(); }, 60e3);   // interpolation horaire
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (ventLignes.visible && document.visibilityState === "visible") ventAvancer(dt);
  seaMat.uniforms.uTime.value = clock.getElapsedTime();
  avancerAnimation();
  controls.update(); renderer.render(scene, camera); updateLabels(); majBoussole();
});
