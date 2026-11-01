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
const obsMat = new THREE.MeshBasicMaterial({ color: 0xff7a3d, transparent: true, opacity: 0.42, depthWrite: false,
  polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
const obsMesh = new THREE.Mesh(geo, obsMat); obsMesh.visible = false; scene.add(obsMesh);

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
  renderPeaks();
}

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
function renderPeaks() {
  for (const { s, L } of peakLabels) {
    const st = statusOf(s.alt);
    L.el.className = "lbl " + (st === "dessous" ? "dessous" : st === "bord" ? "bord" : "");
    L.el.innerHTML = `${s.nom} <small>${nf.format(s.alt)} m</small>`;
  }
  const ul = $("peaks"); ul.replaceChildren();
  for (const s of [...lieux].sort((a, b) => b.alt - a.alt)) {
    const st = statusOf(s.alt), li = document.createElement("li");
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
  const showPeaks = $("t-labels").checked, showCells = $("t-cells").checked;
  for (const L of labels) {
    const isCell = L.cls === "cell";
    if ((isCell && !showCells) || (!isCell && !showPeaks)) { L.el.style.display = "none"; continue; }
    v.copy(toWorld(L.x, L.y, isCell ? L.z : zAt(L.x, L.y) + 30)).project(camera);
    if (v.z > 1 || Math.abs(v.x) > 1.1 || Math.abs(v.y) > 1.1) { L.el.style.display = "none"; continue; }
    L.el.style.display = ""; L.el.style.left = `${(v.x * .5 + .5) * w}px`; L.el.style.top = `${(-v.y * .5 + .5) * h}px`;
  }
}

// ------------------------------------------------------------------ analyse affichée
async function showAnalysis(id, synthese = false) {
  const a = await getJSON(`data/analyses/${id}.json`);
  state.analysis = a; state.synthese = synthese;
  const img = await loadImage(`data/${a.masque}`);
  const t = new THREE.Texture(img); t.needsUpdate = true; t.flipY = true;
  if (obsMat.alphaMap) obsMat.alphaMap.dispose();
  obsMat.alphaMap = t; obsMat.needsUpdate = true;
  setCells(a.detectee ? a.mailles : []);
  document.querySelectorAll("#analyses tr").forEach((tr) => tr.classList.toggle("sel", tr.dataset.id === id));
  renderHero(a, synthese ? syntheseRecente() : null);
}

// Médiane des détections des FENETRE_H heures qui précèdent la dernière détection (tous capteurs) :
// une image isolée (soleil bas, bord de nappe fragmenté...) ne fait pas basculer la valeur affichée.
const FENETRE_H = 3;
const fmtHM = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", hour: "2-digit", minute: "2-digit" });
const mediane = (xs) => { const s = [...xs].sort((p, q) => p - q), k = s.length >> 1; return s.length % 2 ? s[k] : (s[k - 1] + s[k]) / 2; };
function syntheseRecente() {
  const det = hist.analyses.filter((a) => a.detectee && a.sommet_m != null);
  if (!det.length) return null;
  const t1 = Math.max(...det.map((a) => Date.parse(a.date_utc)));
  const sel = det.filter((a) => Date.parse(a.date_utc) > t1 - FENETRE_H * 3.6e6);
  return {
    sommet_m: Math.round(mediane(sel.map((a) => a.sommet_m))),
    incertitude_m: Math.round(mediane(sel.map((a) => a.incertitude_m))),
    n: sel.length, t0: Math.min(...sel.map((a) => Date.parse(a.date_utc))), t1,
    capteurs: [...new Set(sel.map((a) => a.capteur))],
  };
}

function renderHero(a, syn = null) {
  const now = Date.now();
  const recentDet = (a && a.detectee) || syn;
  const chip = $("hero-chip");
  if (recentDet) {
    const v = syn || a;
    state.estimate = v.sommet_m; state.sigma = v.incertitude_m;
    $("hero-num").textContent = nf.format(v.sommet_m);
    $("hero-pm").textContent = `± ${v.incertitude_m}`;
    if (syn && syn.n > 1) {
      $("hero-label").textContent = `Sommet de la mer de nuages (médiane sur ${FENETRE_H} h)`;
      $("hero-src").textContent = `${syn.n} mesures · ${syn.capteurs.join(", ")} · ${fmtH.format(new Date(syn.t0))} → ${fmtHM.format(new Date(syn.t1))}`;
    } else {
      const b = syn ? hist.analyses.find((x) => Date.parse(x.date_utc) === syn.t1) : a;
      $("hero-label").textContent = "Sommet de la mer de nuages (mesuré)";
      $("hero-src").textContent = `${b.capteur} · ${b.satellite} · ${fmtH.format(new Date(b.date_utc))}`;
    }
    const ageH = (now - (syn ? syn.t1 : Date.parse(a.date_utc))) / 3.6e6;
    chip.className = "chip good"; chip.textContent = ageH < 30 ? "✓ Mer de nuages détectée" : "✓ Mer de nuages détectée (mesure ancienne)";
    setH(v.sommet_m);
  } else {
    // pas de détection sur l'analyse choisie : on affiche la prévision AROME la plus proche de maintenant
    const fc = aromeNow();
    state.sigma = null;
    $("hero-label").textContent = fc ? "Sommet de la couche humide (prévision AROME)" : "Sommet de la mer de nuages";
    $("hero-num").textContent = fc ? nf.format(fc.v) : "—";
    $("hero-pm").textContent = "";
    $("hero-src").textContent = a ? `Dernière image : ${a.capteur} · ${a.satellite} · ${fmtH.format(new Date(a.date_utc))}` : "Aucune image analysée";
    chip.className = a ? "chip info" : "chip warn";
    chip.textContent = a ? "Pas de mer de nuages détectée sur cette image" : "Pas encore de mesure";
    state.estimate = fc ? fc.v : null;
    setH(fc ? fc.v : 200);
  }
}
function aromeNow() {
  if (!arome) return null;
  const now = Date.now(); let best = null;
  for (const h of arome.heures) {
    const d = Math.abs(Date.parse(h.t) - now);
    if (h.sommet_lisse_m != null && (!best || d < best.d)) best = { d, v: h.sommet_lisse_m };
  }
  return best && best.d < 3 * 3.6e6 ? best : null;
}

// ------------------------------------------------------------------ tableau des analyses
function renderTable() {
  const tb = $("analyses"); tb.replaceChildren();
  for (const a of [...hist.analyses].reverse()) {
    const tr = document.createElement("tr"); tr.dataset.id = a.id; tr.tabIndex = 0;
    const c1 = document.createElement("td"); c1.textContent = fmtH.format(new Date(a.date_utc));
    const c2 = document.createElement("td"); c2.textContent = `${a.capteur} ${a.satellite}`;
    const c3 = document.createElement("td"); c3.className = "num";
    if (a.detectee) c3.textContent = `${nf.format(a.sommet_m)} ± ${a.incertitude_m} m`;
    else { c3.textContent = "non détectée"; c3.classList.add("nd"); }
    tr.append(c1, c2, c3);
    tr.addEventListener("click", () => showAnalysis(a.id));
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter") showAnalysis(a.id); });
    tb.appendChild(tr);
  }
}

// ------------------------------------------------------------------ graphique (SVG)
function renderChart() {
  const W = 344, Hh = 190, m = { l: 40, r: 8, t: 8, b: 22 };
  const now = Date.now();
  const t0 = now - 48 * 3.6e6, t1 = now + 30 * 3.6e6;
  const obs = hist.analyses.filter((a) => a.detectee && Date.parse(a.date_utc) >= t0);
  const fc = (arome ? arome.heures : []).filter((h) => { const t = Date.parse(h.t); return t >= t0 && t <= t1; });
  const vals = [...obs.map((a) => a.sommet_m + a.incertitude_m), ...fc.map((h) => h.sommet_lisse_m).filter((x) => x != null), 1500];
  const yMax = Math.ceil(Math.max(...vals) / 500) * 500, yMin = 0;
  const X = (t) => m.l + ((t - t0) / (t1 - t0)) * (W - m.l - m.r);
  const Y = (z) => m.t + (1 - (z - yMin) / (yMax - yMin)) * (Hh - m.t - m.b);
  const ns = "http://www.w3.org/2000/svg";
  const el = (tag, at, parent) => { const e = document.createElementNS(ns, tag); for (const k in at) e.setAttribute(k, at[k]); parent && parent.appendChild(e); return e; };
  const svg = el("svg", { viewBox: `0 0 ${W} ${Hh}`, role: "img", "aria-label": "Altitude du sommet de la mer de nuages : mesures satellite et prévision AROME" });
  const grid = el("g", { class: "grid" }, svg), axis = el("g", { class: "axis" }, svg);
  for (let z = 0; z <= yMax; z += 500) {
    el("line", { x1: m.l, x2: W - m.r, y1: Y(z), y2: Y(z) }, grid);
    el("text", { x: m.l - 6, y: Y(z) + 3, "text-anchor": "end" }, axis).textContent = nf.format(z);
  }
  // graduations : minuit et midi, heure locale
  for (let t = Math.ceil(t0 / 3.6e6) * 3.6e6; t <= t1; t += 3.6e6) {
    const hh = Number(fmtHour.format(new Date(t)));
    if (hh === 0 || hh === 12) {
      el("text", { x: X(t), y: Hh - 6, "text-anchor": "middle" }, axis).textContent = hh === 0 ? fmtDay.format(new Date(t)) : "12 h";
      if (hh === 0) el("line", { x1: X(t), x2: X(t), y1: m.t, y2: Hh - m.b }, grid);
    }
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
    const x = X(Date.parse(a.date_utc));
    el("line", { x1: x, x2: x, y1: Y(a.sommet_m - a.incertitude_m), y2: Y(a.sommet_m + a.incertitude_m), stroke: "var(--series-2)", "stroke-width": 2 }, svg);
    el("circle", { cx: x, cy: Y(a.sommet_m), r: a.capteur === "MTG-FCI" ? 3 : 4.5, fill: "var(--series-2)", stroke: "var(--surface-1)", "stroke-width": a.capteur === "MTG-FCI" ? 1 : 2 }, svg);
  }
  // survol : réticule vertical + infobulle
  const hair = el("line", { y1: m.t, y2: Hh - m.b, stroke: "var(--text-muted)", "stroke-width": 1, visibility: "hidden" }, svg);
  const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: Hh - m.t - m.b, fill: "transparent" }, svg);
  const tip = $("tooltip");
  hit.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect(), sx = ((e.clientX - r.left) / r.width) * W;
    const t = t0 + ((sx - m.l) / (W - m.l - m.r)) * (t1 - t0);
    const h = fc.reduce((b, x) => (Math.abs(Date.parse(x.t) - t) < Math.abs(Date.parse(b.t) - t) ? x : b), fc[0]);
    const o = obs.filter((a) => Math.abs(Date.parse(a.date_utc) - t) < 1.5 * 3.6e6)
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
    if (o) row("var(--series-2)", `${nf.format(o.sommet_m)} ± ${o.incertitude_m} m`, `${o.satellite} ${new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", hour: "2-digit", minute: "2-digit" }).format(new Date(o.date_utc))}`);
    tip.hidden = false; tip.style.left = `${e.clientX + 14}px`; tip.style.top = `${e.clientY - 10}px`;
  });
  hit.addEventListener("pointerleave", () => { tip.hidden = true; hair.setAttribute("visibility", "hidden"); });
  $("chart").replaceChildren(svg);
  $("chart-legend").innerHTML = `<span><i class="l-dot"></i>Mesure satellite</span><span><i class="l-line"></i>Prévision AROME</span>`;
}

// ------------------------------------------------------------------ interface
$("h-slider").addEventListener("input", (e) => setH(Number(e.target.value)));
$("btn-reset").addEventListener("click", () => state.estimate != null && setH(state.estimate));
$("t-sea").addEventListener("change", (e) => { sea.visible = e.target.checked; renderPeaks(); });
$("t-obs").addEventListener("change", (e) => (obsMesh.visible = e.target.checked));
$("t-cells").addEventListener("change", () => updateLabels());
$("t-exag").addEventListener("change", (e) => { state.exag = e.target.checked ? 1.5 : 1; applyHeights(); setH(state.H); });
const afficherMaj = () => { $("maj").textContent = `Mise à jour : ${fmtH.format(new Date(hist.maj_utc))}`; };
afficherMaj();

function resize() {
  const w = host.clientWidth, h = host.clientHeight;
  renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
}
addEventListener("resize", resize); resize();

renderTable(); renderChart();
const startId = hist.derniere_detection || hist.derniere_analyse;
if (startId) await showAnalysis(startId, true); else renderHero(null);
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
      afficherMaj(); renderTable();
      const id = hist.derniere_detection || hist.derniere_analyse;
      if (state.synthese && id) await showAnalysis(id, true);
      else if (state.analysis) {
        document.querySelectorAll("#analyses tr").forEach((tr) => tr.classList.toggle("sel", tr.dataset.id === state.analysis.id));
        renderHero(state.analysis);
      }
    }
    renderChart();   // le repère « maintenant » avance même sans nouvelles données
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
renderer.setAnimationLoop(() => {
  seaMat.uniforms.uTime.value = clock.getElapsedTime();
  avancerAnimation();
  controls.update(); renderer.render(scene, camera); updateLabels(); majBoussole();
});
